"""Exact fan release/pose reaches retained draw paths and finite host clock."""
from dataclasses import replace
import unittest
from unittest.mock import Mock,patch
from assembly_geometry import Mesh,box,vertex_bytes
from assembly_viewer import AssemblyViewport
from test_part_motion_viewport052 import viewport,scene,PlanStub


class FanPlanner(PlanStub):
    def plan(self,target,**options):
        if target!='case-fan:0':return super().plan(target,**options)
        self.calls.append((target,options.copy()))
        released=target in options.get('released_mounts',())
        return dict(available=released,target=target,part_ids=(target,),kind='case_fan',
            direction=(0.,-1.,0.),distance_mm=40.,allowed_opened_mesh_names=(),
            allowed_mount_release_part_ids=(target,),mount_released=released,
            hide_mesh_names=('cable-fan-plug',) if released else (),
            reason='case_fan_mount_disengagement_reference' if released else 'case_fan_release_required')


def fan_viewport():
    value=scene('notebook_line')
    frame=Mesh('case-fan-frame',box(18,5,18),(.3,.4,.5,1.),(0.,90.,0.),'fans',part_id='case-fan:0')
    rotor=replace(frame,name='case-fan-leaves',vertices=box(4,2,4),rotor=True,axis=(0.,1.,0.))
    cable=Mesh('cable-fan-plug',box(2,2,2),(.2,.2,.2,1.),(15.,80.,0.),'cables',part_id='cables:all')
    value=replace(value,meshes=value.meshes+(frame,rotor,cable),metadata=dict(value.metadata,
        cooling={'parts':[dict(id='case-fan:0',kind='case_fan')]}))
    node,state=viewport(value);node._part_planner=FanPlanner();node._released_mounts=frozenset()
    node._demo=True;node._animate=True
    AssemblyViewport.select_component(node,'case-fan:0')
    return node,state


class CaseFanHostTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No device, GL or worker')))

    def test_exact_explicit_release_stops_rotor_hides_only_its_plug_and_moves_real_pick(self):
        node,_=fan_viewport();self.addCleanup(node._renderer.close)
        raw=vertex_bytes(node._scene)
        self.assertFalse(AssemblyViewport.preview_part_motion(node,True))
        self.assertTrue(node._active)
        self.assertTrue(AssemblyViewport.set_mount_released(node,True))
        self.assertFalse(node._active);self.assertFalse(node._clock_active_state)
        self.assertTrue(AssemblyViewport.preview_part_motion(node,True))
        with patch.object(node._part_planner,'plan',side_effect=AssertionError('No frame-time replan')):
            for _ in range(8):AssemblyViewport.advance_animations(node,136.);AssemblyViewport.paintGL(node)
        self.assertEqual(node._part_motion.progress,1.);self.assertFalse(node._clock_active_state)
        self.assertIn('cable-fan-plug',node._renderer._pick_state['hidden_mesh_names'])
        self.assertEqual(node._renderer._pick_state['phase']['case-fan:0'],0.)
        self.assertEqual(node._renderer.pick(*node._renderer.project_point((0.,50.,0.))[:2]),'case-fan:0')
        self.assertTrue(AssemblyViewport.set_mount_released(node,False))
        self.assertEqual(node._part_motion.progress,0.);AssemblyViewport.paintGL(node)
        self.assertNotIn('hidden_mesh_names',node._renderer._pick_state)
        self.assertTrue(node._active);self.assertEqual(node._renderer.upload_count,1)
        self.assertEqual(vertex_bytes(node._scene),raw)

    def test_hide_motion_focus_and_visibility_changes_clear_reference_release(self):
        for cause in ('hidden','minimized','motion','focus','cutaway','psu','selection'):
            with self.subTest(cause=cause):
                node,state=fan_viewport();self.addCleanup(node._renderer.close)
                self.assertTrue(AssemblyViewport.set_mount_released(node,True))
                self.assertTrue(AssemblyViewport.preview_part_motion(node,True))
                AssemblyViewport.advance_animations(node,136.)
                calls=len(node._part_planner.calls)
                if cause=='hidden':state['visible']=False
                elif cause=='minimized':state['minimized']=True
                elif cause=='motion':node._motion=False
                elif cause=='focus':node._focus='cpu'
                elif cause=='cutaway':AssemblyViewport.set_inspection_cutaway(node,True)
                elif cause=='psu':AssemblyViewport.set_show_psu(node,True)
                elif cause=='selection':AssemblyViewport.select_component(node,'cpu:0')
                node._update_animation_state()
                self.assertFalse(node._released_mounts);self.assertEqual(node._part_motion.progress,0.)
                if cause in ('hidden','minimized','motion'):
                    self.assertEqual(len(node._part_planner.calls),calls)

    def test_hiding_releases_planner_work_cache_without_losing_cached_plan_or_scene(self):
        node,state=fan_viewport();self.addCleanup(node._renderer.close)
        planner=node._part_planner;planner.discard_geometry_cache=Mock()
        value=node._scene;plan=node._part_plan.copy();calls=len(planner.calls)
        state['visible']=False;node._update_animation_state()
        planner.discard_geometry_cache.assert_called_once()
        self.assertIs(node._part_planner,planner);self.assertIs(node._scene,value)
        self.assertEqual(node._part_plan,plan);self.assertEqual(len(planner.calls),calls)
        state['visible']=True;node._update_animation_state()
        self.assertEqual(planner.discard_geometry_cache.call_count,1)
        self.assertEqual(len(planner.calls),calls)

    def test_compatible_focus_change_resets_motion_and_reference_release(self):
        for focus in ('case-fan:0','fans'):
            with self.subTest(focus=focus):
                node,_=fan_viewport();self.addCleanup(node._renderer.close)
                self.assertTrue(AssemblyViewport.set_mount_released(node,True))
                self.assertTrue(AssemblyViewport.preview_part_motion(node,True))
                AssemblyViewport.advance_animations(node,136.)
                node.reset_camera=lambda:None;node.focusChanged=type('Signal',(),{'emit':lambda *_:None})()
                self.assertTrue(AssemblyViewport.focus_component(node,focus))
                self.assertFalse(node._released_mounts);self.assertEqual(node._part_motion.progress,0.)
                self.assertEqual(node.part_motion_state()['reason'],'case_fan_release_required')

    def test_all_six_styles_keep_exact_fan_identity_for_finite_selection_effects(self):
        from assembly_style import apply_model_styles
        from assembly_geometry import Scene
        from test_part_pose_renderer052 import renderer
        for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            with self.subTest(style=style):
                node,_=fan_viewport();node._renderer.close()
                meshes,meta=apply_model_styles(node._scene.meshes,style,{},node._scene.dimensions,{'front':'open'})
                node._scene=Scene(meshes,node._scene.dimensions,dict(node._scene.metadata,**meta))
                node._renderer=renderer(node._scene);self.addCleanup(node._renderer.close)
                raw=vertex_bytes(node._scene);node._selection_effects=True;node._demo=False
                node._focus='fans'
                self.assertTrue(AssemblyViewport.preview_effect(node,'case-fan:0'))
                self.assertEqual(node._effect.sample()['component'],'case-fan:0')
                self.assertEqual(node._effect.sample()['family'],'fans')
                self.assertFalse(AssemblyViewport.preview_effect(node,'case-fan:missing'))
                AssemblyViewport.advance_animations(node,136.);AssemblyViewport.paintGL(node)
                self.assertEqual(node._renderer._frame_effect_samples[style]['component'],'case-fan:0')
                self.assertTrue(node._renderer._frame_effect_samples[style]['active'])
                for _ in range(8):AssemblyViewport.advance_animations(node,136.)
                self.assertFalse(node._clock_active_state);self.assertEqual(node._renderer.upload_count,1)
                self.assertEqual(vertex_bytes(node._scene),raw)


if __name__=='__main__':unittest.main()
