"""Real viewport host state and fake VBO backend share one finite clock."""
import copy
from dataclasses import replace
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assembly_geometry import Scene,vertex_bytes
from assembly_part_motion052 import PartMotion,PartMotionPlanner
from assembly_scene_cache import SceneCache
from assembly_style import apply_model_styles
from assembly_viewer import AssemblyViewport
from test_gpu_insertion_renderer049 import viewport as old_viewport
from test_part_pose_renderer052 import renderer,scene


class PlanStub:
    def __init__(self):self.calls=[]
    def plan(self,target,**options):
        self.calls.append((target,copy.deepcopy(options)))
        identity='cpu:0' if target=='cpu' else target
        return dict(available=identity not in options['hidden_parts'],target=identity,part_ids=(identity,),
                    direction=(0.,1.,0.),distance_mm=70.,allowed_opened_mesh_names=(),hide_mesh_names=(),
                    reason='socket_disengagement_reference',scope='visible_reference_clearance')
    def clear(self):self.calls.clear()


def viewport(value):
    node,state=old_viewport(value)
    node._renderer=renderer(value);node._selected='';node._part_motion=PartMotion();node._part_planner=PlanStub()
    node._part_plan={};node._part_plan_key=None;node._hidden_parts=frozenset();node._hidden_connection_names=frozenset()
    node._opened_retention_names=frozenset();node._changing_scene=False;node._pending=False
    node._inspection_cutaway=False;node._show_psu=False;node._transparent_background=False
    node._yaw=0.;node._pitch=0.;node._zoom=1.;node._dark=False;node._real_cpu_rotor_parts=()
    node.devicePixelRatioF=lambda:1.;node.width=lambda:1000;node.height=lambda:800
    node.partAssemblyChanged=SimpleNamespace(emit=Mock());node.componentSelected=SimpleNamespace(emit=Mock())
    node.sceneChanged=SimpleNamespace(emit=Mock())
    node.part_motion_state=lambda:AssemblyViewport.part_motion_state(node)
    node.set_inspection_cutaway=lambda value:AssemblyViewport.set_inspection_cutaway(node,value)
    node.set_show_psu=lambda value:AssemblyViewport.set_show_psu(node,value)
    return node,state


class PartMotionViewportTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native/device/worker')))

    def test_explicit_selection_plans_once_and_actual_motion_frames_never_replan_or_upload(self):
        value=scene('notebook_line');raw=vertex_bytes(value);node,_=viewport(value)
        self.addCleanup(node._renderer.close)
        self.assertEqual(node._part_planner.calls,[])
        AssemblyViewport.select_component(node,'cpu:0')
        self.assertEqual(len(node._part_planner.calls),1)
        AssemblyViewport.select_component(node,'cpu:0');self.assertEqual(len(node._part_planner.calls),1)
        self.assertTrue(AssemblyViewport.preview_part_motion(node,True));self.assertTrue(node._clock_active_state)
        with patch.object(node._part_planner,'plan',side_effect=AssertionError('No per-frame clearance scan')):
            for _ in range(8):
                AssemblyViewport.advance_animations(node,136.)
                AssemblyViewport.paintGL(node)
                self.assertTrue(node.part_motion_state()['available'])
            self.assertEqual(node._part_motion.progress,1.);self.assertFalse(node._clock_active_state)
            self.assertEqual(node._renderer.pick(*node._renderer.project_point((-20.,85.,0.))[:2]),'cpu:0')
            self.assertTrue(AssemblyViewport.preview_part_motion(node,False))
            for _ in range(8):AssemblyViewport.advance_animations(node,136.);AssemblyViewport.paintGL(node)
        self.assertEqual(node._part_motion.progress,0.);self.assertFalse(node._clock_active_state)
        self.assertEqual(node._renderer.upload_count,1);self.assertEqual(vertex_bytes(value),raw)

    def test_selection_uses_real_part_identity_and_rejects_missing_same_family_id(self):
        value=scene()
        value=replace(value,meshes=value.meshes+(replace(value.meshes[-1],name='case-fan-frame',
                                                       component='fans',part_id='case-fan:0'),))
        node,_=viewport(value);self.addCleanup(node._renderer.close)
        self.assertTrue(AssemblyViewport.select_component(node,'case-fan:0'))
        self.assertEqual(node._selected,'case-fan:0')
        self.assertFalse(AssemblyViewport.select_component(node,'cpu:missing'))
        self.assertEqual(node._selected,'case-fan:0')
        node._focus='case-fan:0';node.reset_camera=lambda:None
        node.focusChanged=SimpleNamespace(emit=Mock())
        self.assertTrue(AssemblyViewport.focus_component(node,'case-fan:0'))
        self.assertFalse(AssemblyViewport.focus_component(node,'case-fan:missing'))

    def test_hidden_minimized_motion_gate_and_other_focus_reset_instead_of_running_in_background(self):
        for cause in ('hidden','minimized','motion','focus'):
            with self.subTest(cause=cause):
                node,state=viewport(scene());self.addCleanup(node._renderer.close)
                AssemblyViewport.select_component(node,'memory:0')
                self.assertTrue(AssemblyViewport.preview_part_motion(node,True))
                AssemblyViewport.advance_animations(node,136.)
                if cause=='hidden':state['visible']=False
                elif cause=='minimized':state['minimized']=True
                elif cause=='motion':node._motion=False
                else:node._focus='cpu'
                node._update_animation_state()
                self.assertEqual(node._part_motion.progress,0.);self.assertFalse(node._part_motion.active)
                self.assertFalse(node._clock_active_state);self.assertIsNone(node._renderer._pick_state)
                self.assertFalse(AssemblyViewport.preview_part_motion(node,True))

    def test_changed_hidden_mask_restores_motion_first_and_does_not_rebake_the_scene(self):
        value=scene();node,_=viewport(value);self.addCleanup(node._renderer.close)
        AssemblyViewport.select_component(node,'cpu:0');AssemblyViewport.preview_part_motion(node,True)
        AssemblyViewport.advance_animations(node,136.)
        self.assertTrue(AssemblyViewport.set_part_hidden(node,'memory:0',True))
        self.assertEqual(node._part_motion.progress,0.);self.assertFalse(node._clock_active_state)
        self.assertIs(node._scene,value);self.assertIsNone(node._renderer._pick_state)
        AssemblyViewport.paintGL(node)
        self.assertEqual(node._renderer._pick_state['hidden_parts'],frozenset(('memory:0',)))
        self.assertFalse(AssemblyViewport.set_part_hidden(node,'all',True))
        self.assertTrue(AssemblyViewport.restore_hidden_parts(node));AssemblyViewport.paintGL(node)
        self.assertNotIn('hidden_parts',node._renderer._pick_state)
        self.assertEqual(node._renderer.upload_count,1)

    def test_style_only_scene_reuses_physical_planner_index_and_close_drops_all_scene_owners(self):
        import weakref
        value=scene();node,_=viewport(value);self.addCleanup(node._renderer.close)
        node._part_planner=PartMotionPlanner(value);planner=node._part_planner
        old_ref=weakref.ref(value)
        values,meta=apply_model_styles(value.meshes,'notebook_color',{},value.dimensions,{'front':'open'})
        styled=Scene(values,value.dimensions,meta)
        node._scene_cache=SceneCache();node._scene_cache.base=value
        # A Mock's return-value cycles would themselves retain the scene and
        # confuse the immediate ownership check below. Use a short-lived
        # direct builder override, then restore the real method before close.
        node._scene_cache.build=lambda _spec:styled
        AssemblyViewport.set_scene(node,{})
        del node._scene_cache.build
        self.assertIs(node._part_planner,planner);self.assertIs(planner.scene,styled)
        self.assertTrue(node._pending)
        AssemblyViewport.paintGL(node)
        node._scene_cache.base=styled
        del value
        self.assertIsNone(old_ref(),'Rebinding must not retain the previous Scene wrapper')
        current_ref=weakref.ref(styled);del styled,values,meta
        AssemblyViewport._retire_cpu_scene(node)
        self.assertTrue(current_ref() is None);self.assertIsNone(planner.scene)
        self.assertEqual(planner.cache_info()['triangles'],0);self.assertIsNone(node._part_planner)


if __name__=='__main__':unittest.main()
