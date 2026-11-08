"""Actual draw/pick visibility flow with a fake GPU backend, never a GL context."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_config import DEFAULT_ASSEMBLY,validate_assembly
from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_scene_cache import SceneCache
from assembly_style import apply_model_styles
from assembly_viewer import AssemblyRenderer,AssemblyViewport,GL_LINES,GL_TRIANGLES
from assembly_visibility048 import mesh_visible
from top_bar_config import HARDWARE_ICON_STYLES


class Backend:
    """Records calls only; no Qt graphics object or context exists."""
    def __init__(self):self.calls=[]
    def __getattr__(self,name):
        def call(*args):self.calls.append((name,args))
        return call


class InspectionVisibilityTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(name,side_effect=AssertionError('No device/window/process/background activity')))
        self.meshes=(
            Mesh('front-panel',box(30,30,1),(.2,.3,.4,1.),(0.,0.,10.),'case'),
            Mesh('psu-shroud',box(30,10,24),(.2,.3,.4,1.),(0.,-15.,0.),'case'),
            Mesh('left-glass',box(1,30,24),(.4,.5,.6,.15),(-16.,0.,0.),'panel'),
            Mesh('case-depth-rail',box(2,2,30),(.3,.4,.5,1.),(20.,15.,0.),'case'),
            Mesh('psu-shell',box(8,8,8),(.3,.4,.5,1.),(0.,0.,0.),'psu',part_id='psu:0'),
            Mesh('ram-pcb',box(1,15,4),(.3,.5,.4,1.),(8.,0.,0.),'memory',part_id='memory:0'))

    def renderer(self,style='miniature'):
        meshes,meta=apply_model_styles(self.meshes,style,{},(40,40,40),{'front':'open'})
        scene=Scene(meshes,(40,40,40),meta)
        renderer=AssemblyRenderer()
        renderer.program=Backend();renderer.buffer=Backend();renderer.vao=Backend();renderer.functions=Backend()
        renderer._uniforms={'backgroundMode':1,'shadeMix':2}
        renderer.upload(scene)
        self.addCleanup(renderer.close)
        return renderer

    def test_default_is_unchanged_boolean_is_strict_and_controller_accepts_the_option(self):
        self.assertIs(DEFAULT_ASSEMBLY['inspection_cutaway'],False)
        self.assertIs(validate_assembly()['inspection_cutaway'],False)
        for state in (False,True):
            self.assertIs(validate_assembly({'inspection_cutaway':state})['inspection_cutaway'],state)
        for state in (None,1,0,'true',{},[]):
            with self.assertRaises(ValueError):validate_assembly({'inspection_cutaway':state})
        from assembly_tools import AssemblyTools
        edited=[]
        controller=SimpleNamespace(_draft={'assembly':validate_assembly()},edit=lambda value,**kw:edited.append((value,kw)))
        AssemblyTools.changeAssembly(controller,'inspection_cutaway',True)
        self.assertEqual(len(edited),1)
        self.assertIs(validate_assembly(edited[0][0]['assembly'])['inspection_cutaway'],True)
        self.assertEqual(edited[0][1]['merge_key'],('assembly','inspection_cutaway'))

    def test_only_declared_covers_hide_hardware_frames_and_unknown_batches_stay(self):
        for mesh in self.meshes:self.assertTrue(mesh_visible(mesh))
        self.assertEqual([mesh.name for mesh in self.meshes if not mesh_visible(mesh,True)],
                         ['front-panel','psu-shroud','left-glass'])
        for name,component in (('case-tubular-metal-frame','case'),('open-frame-tray','case'),
            ('case-bench-metal-platform','case'),('case-foot','case'),('unknown-future-case','case'),
            ('translucent-stand','panel'),('psu-shroud','psu'),('left-glass','memory')):
            self.assertTrue(mesh_visible(SimpleNamespace(name=name,component=component),True),(name,component))

    def test_actual_draw_and_ink_pass_share_visibility_for_every_style_without_reupload(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                renderer=self.renderer(style)
                scene=renderer.scene;physical=vertex_bytes(scene);rows=renderer.ranges;edges=renderer.edge_ranges
                calls=[]
                renderer._draw_part=lambda row,*args,**kw:calls.append((row[0].name,kw.get('mode',GL_TRIANGLES)))
                renderer.draw(320,240,yaw=0,pitch=0)
                normal=tuple(calls);calls.clear()
                self.assertIn(('front-panel',GL_TRIANGLES),normal)
                renderer.draw(320,240,yaw=0,pitch=0,inspection_cutaway=True)
                visible=tuple(calls);calls.clear()
                self.assertTrue(visible)
                self.assertFalse(any(name in ('front-panel','psu-shroud','left-glass') for name,mode in visible))
                self.assertIn(('psu-shell',GL_TRIANGLES),visible)
                self.assertIn(('ram-pcb',GL_TRIANGLES),visible)
                self.assertIn(('case-depth-rail',GL_TRIANGLES),visible)
                if renderer.edge_ranges:self.assertTrue(any(mode==GL_LINES for name,mode in visible))
                renderer.draw(320,240,yaw=0,pitch=0,inspection_cutaway=False)
                self.assertEqual(tuple(calls),normal)
                self.assertEqual(renderer.upload_count,1)
                self.assertIs(renderer.scene,scene);self.assertIs(renderer.ranges,rows);self.assertIs(renderer.edge_ranges,edges)
                self.assertEqual(vertex_bytes(scene),physical)
                self.assertEqual(sum(name=='allocate' for name,args in renderer.buffer.calls),1)
                renderer.close();self.assertEqual(renderer._cutaway_hidden,frozenset())

    def test_actual_click_ray_passes_through_hidden_shell_then_restores_occlusion(self):
        renderer=self.renderer('notebook_line')
        renderer._draw_part=lambda *args,**kwargs:None
        for cutaway,expected in ((False,'case'),(True,'psu:0'),(False,'case')):
            renderer.draw(640,480,yaw=0,pitch=0,inspection_cutaway=cutaway)
            point=renderer.project_point((0.,0.,0.))
            self.assertEqual(renderer.pick(*point[:2]),expected)
        self.assertEqual(renderer.upload_count,1)

    def test_cutaway_is_not_a_physical_cache_field_and_never_rebuilds_geometry(self):
        from assembly_spec import build_spec
        config={'assembly':{'inspection_cutaway':True}}
        spec=build_spec({},config,{},[],identify_case=lambda *args,**kwargs:{})
        self.assertIs(spec['inspection_cutaway'],True)
        self.assertIs(spec['options']['inspection_cutaway'],True)
        self.assertEqual(spec['memory']['count'],0,'Inspection must not invent RAM')
        base=Scene(self.meshes,(40,40,40),{'visual_style':'miniature'})
        built=[]
        def build(value):built.append(value);return base
        cache=SceneCache()
        with patch('assembly_scene_cache.build_scene',side_effect=build):
            for state in (False,True,False,True):
                self.assertIs(cache.build(dict(spec,visual_style='miniature',inspection_cutaway=state)),base)
        self.assertEqual(len(built),1)
        self.assertNotIn('inspection_cutaway',built[0])

    def test_viewport_toggle_invalidates_only_click_state_and_forwards_actual_draw_option(self):
        updates=[];draws=[]
        class Renderer:
            _pick_state={'old':'cover'}
            def draw(self,*args,**kwargs):draws.append((args,kwargs))
            def upload(self,*args):raise AssertionError('Display toggle must not upload geometry')
        viewport=SimpleNamespace(_renderer=Renderer(),_inspection_cutaway=False,_error='',_pending=False,
            _yaw=0.,_pitch=0.,_zoom=1.,_exploded=False,_phase=0.,_dark=False,_focus='all',
            _transparent_background=False,update=lambda:updates.append(True),
            devicePixelRatioF=lambda:1.,width=lambda:320,height=lambda:240)
        AssemblyViewport.set_inspection_cutaway(viewport,True)
        self.assertEqual(updates,[True]);self.assertIsNone(viewport._renderer._pick_state)
        self.assertFalse(viewport._pending)
        AssemblyViewport.set_inspection_cutaway(viewport,True)
        self.assertEqual(len(updates),1)
        AssemblyViewport.paintGL(viewport)
        self.assertTrue(draws[-1][1]['inspection_cutaway'])
        AssemblyViewport.set_inspection_cutaway(viewport,False)
        AssemblyViewport.paintGL(viewport)
        self.assertNotIn('inspection_cutaway',draws[-1][1])

    def test_inspector_and_desktop_share_display_option_forwarding(self):
        from assembly_window import AssemblyWindow
        changes=[]
        class Viewport:
            def set_selection_effects_enabled(self,value):pass
            def set_exploded(self,value):pass
            def set_fan_motion(self,value):pass
            def set_fan_animation_enabled(self,value):pass
            def set_inspection_cutaway(self,value):changes.append(value)
        window=SimpleNamespace(viewport=Viewport(),controller=SimpleNamespace(motionEnabled=False),
            property=lambda key:False,_renderer_error=False)
        for state in (False,True,False):
            options=validate_assembly({'inspection_cutaway':state})
            AssemblyWindow._apply_motion_options(window,options)
        self.assertEqual(changes,[False,True,False])

    def test_actual_outer_window_signature_does_not_rebake_or_set_scene_for_the_toggle(self):
        from assembly_window import AssemblyWindow
        scenes=[];changes=[];bakes=[]
        class Viewport:
            def set_scene(self,value):scenes.append(value)
            def set_selection_effects_enabled(self,value):pass
            def set_exploded(self,value):pass
            def set_fan_motion(self,value):pass
            def set_fan_animation_enabled(self,value):pass
            def set_inspection_cutaway(self,value):changes.append(value)
        window=SimpleNamespace(_closing=False,_spec=None,_geometry_key='',_profile_key='',_profile_shapes={},engine=None,
            viewport=Viewport(),fit_notice=SimpleNamespace(setText=lambda text:None,setVisible=lambda value:None),
            controller=SimpleNamespace(tr=lambda text:text,motionEnabled=False),_refresh_part_choices=lambda:None,
            property=lambda key:False,_renderer_error=False)
        def bake(value,engine):bakes.append(value);return copy.deepcopy(value)
        spec=dict(case={},gpu={},cpu={},memory={},board={},cooling={},auxiliary={})
        with patch('assembly_window.bake_profiles',side_effect=bake),patch('assembly_parts.fit_messages',return_value=[]):
            for state in (False,True,False):
                options=validate_assembly({'inspection_cutaway':state})
                self.assertTrue(AssemblyWindow._apply_scene(window,dict(spec,inspection_cutaway=state,options=options)))
                AssemblyWindow._apply_motion_options(window,options)
        self.assertEqual(len(bakes),1);self.assertEqual(len(scenes),1)
        self.assertEqual(changes,[False,True,False])


if __name__=='__main__':unittest.main()
