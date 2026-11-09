"""GPU pose/ink/pick and finite shared-clock flow, without native graphics."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from PySide6.QtGui import QVector3D
from assembly_effects import SelectionEffect,effect_sample
from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_gpu_insertion049 import GpuInsertion,insertion_plan
from assembly_style import apply_model_styles
from assembly_viewer import AssemblyRenderer,AssemblyViewport,GL_LINES,GL_TRIANGLES
from top_bar_config import HARDWARE_ICON_STYLES
from test_assembly_visibility048 import Backend


def scene(style='miniature',unmapped=False):
    meshes=(Mesh('frame-a',box(2,2,2),(.2,.3,.4,1.),(-100.,-150.,-100.),'case'),
            Mesh('frame-b',box(2,2,2),(.2,.3,.4,1.),(100.,150.,100.),'case'),
            Mesh('gpu-shroud',box(10,10,10),(.3,.4,.5,1.),(0.,0.,0.),'gpu',part_id='gpu:0'),
            Mesh('cable-2-gpu16-target',box(2,2,2),(.2,.3,.4,1.),(0.,20.,0.),'cables',part_id='cables:all'),
            Mesh('cable-20-gpu16-target',box(2,2,2),(.2,.3,.4,1.),(30.,20.,0.),'cables',part_id='cables:all'),
            Mesh('cable-0-atx24-target',box(2,2,2),(.2,.3,.4,1.),(60.,20.,0.),'cables',part_id='cables:all'))
    if not unmapped:meshes=tuple(mesh for mesh in meshes if mesh.name!='cable-20-gpu16-target')
    metadata=dict(gpu_mount='horizontal',attachment_anchors=dict(board=dict(normal=(-1.,0.,0.))),
                  auxiliary=dict(cable_count=2,cables=[dict(target_owner='gpu',mesh_prefix='cable-2-gpu16'),
                                                        dict(target_owner='board',mesh_prefix='cable-0-atx24')]))
    styled,appearance=apply_model_styles(meshes,style,{},(240,500,500),{'front':'open'})
    return Scene(styled,(240,500,500),dict(metadata,**appearance))


def renderer(value):
    node=AssemblyRenderer();node.program=Backend();node.buffer=Backend();node.vao=Backend();node.functions=Backend()
    node._uniforms={'backgroundMode':1,'shadeMix':2};node.upload(value)
    return node


def viewport(value):
    state=dict(visible=True,minimized=False)
    node=SimpleNamespace(_closed=False,_error='',_motion=True,_exploded=False,_focus='all',_animate=False,
        _scene=value,_gpu_plan=insertion_plan(value),_gpu_insertion=GpuInsertion(),_renderer=SimpleNamespace(_pick_state={'old':True}),
        _effect=SelectionEffect(),_effect_active=False,_selection_effects=False,_clock_active_state=False,_active=False,
        _fan_available=False,_rpm=0.,_phase=0.,_fan_expiry=0.,_demo=False,_demo_phase=0.,_gpu_demo_phase=0.,
        _cpu_available=False,_cpu_tach_usable=False,_cpu_rpm=0.,_cpu_phase=0.,_cpu_expiry=0.,
        isVisible=lambda:state['visible'],window=lambda:SimpleNamespace(isMinimized=lambda:state['minimized']),
        animationActiveChanged=SimpleNamespace(emit=Mock()),gpuAssemblyChanged=SimpleNamespace(emit=Mock()),update=Mock())
    node._update_animation_state=lambda:AssemblyViewport._update_animation_state(node)
    node.gpu_insertion_state=lambda:AssemblyViewport.gpu_insertion_state(node)
    return node,state


class GpuInsertionRendererTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native graphics, device or worker')))

    def test_all_saved_styles_share_triangle_and_ink_offset_without_another_upload(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                value=scene(style,unmapped=True);before=vertex_bytes(value);node=renderer(value);calls=[]
                allocations=len(node.buffer.calls)
                node._draw_part=lambda row,*args,**kw:calls.append((row[0],kw))
                node.draw(1000,800,yaw=0,pitch=0,gpu_offset=(-40.,0.,0.),hide_gpu_power=True,inspection_cutaway=True)
                self.assertEqual(len(node.buffer.calls),allocations)
                self.assertEqual(vertex_bytes(value),before)
                gpu=[kw for mesh,kw in calls if mesh.component=='gpu']
                self.assertTrue(gpu);self.assertTrue(all(kw['gpu_offset']==(-40.,0.,0.) for kw in gpu))
                self.assertTrue(any(kw.get('mode',GL_TRIANGLES)==GL_TRIANGLES for kw in gpu))
                if node.edge_ranges:self.assertTrue(any(kw.get('mode')==GL_LINES for kw in gpu))
                names={mesh.name for mesh,_ in calls}
                self.assertNotIn('cable-2-gpu16-target',names)
                self.assertIn('cable-20-gpu16-target',names);self.assertIn('cable-0-atx24-target',names)
                node.close()

    def test_actual_model_matrix_and_translated_triangle_pick_agree(self):
        node=renderer(scene());self.addCleanup(node.close)
        node.draw(1000,800,yaw=0,pitch=0,gpu_offset=(-40.,0.,0.),hide_gpu_power=True)
        point=node.project_point((-40.,0.,0.));self.assertIsNotNone(point)
        self.assertEqual(node.pick(*point[:2]),'gpu:0')
        old=node.project_point((0.,0.,0.));self.assertEqual(node.pick(*old[:2]),'')
        matrices=[args[1] for name,args in node.program.calls if name=='setUniformValue' and args[0]=='modelMatrix']
        # Actual triangle draws set the same model translation used by picking.
        self.assertTrue(any(abs(matrix.map(QVector3D()).x()+40.)<1e-5 for matrix in matrices))

    def test_finite_insertion_subscribes_only_while_moving_and_keeps_scene_immutable(self):
        value=scene();before=vertex_bytes(value);node,_=viewport(value)
        self.assertTrue(AssemblyViewport.preview_gpu_insertion(node,True))
        self.assertIsNone(node._renderer._pick_state);self.assertTrue(node._clock_active_state)
        for _ in range(29):AssemblyViewport.advance_animations(node,34.)
        self.assertEqual(node._gpu_insertion.progress,1.);self.assertFalse(node._gpu_insertion.active)
        self.assertFalse(node._clock_active_state)
        updates=node.update.call_count
        for _ in range(5):self.assertFalse(AssemblyViewport.advance_animations(node,34.))
        self.assertEqual(node.update.call_count,updates)
        self.assertTrue(AssemblyViewport.preview_gpu_insertion(node,False))
        for _ in range(29):AssemblyViewport.advance_animations(node,34.)
        self.assertEqual(node._gpu_insertion.progress,0.);self.assertFalse(node._clock_active_state)
        self.assertEqual(vertex_bytes(value),before)

    def test_hidden_minimized_and_disabled_motion_reset_and_stop_the_shared_clock(self):
        for cause in ('hidden','minimized','disabled'):
            with self.subTest(cause=cause):
                node,state=viewport(scene());self.assertTrue(AssemblyViewport.preview_gpu_insertion(node,True))
                AssemblyViewport.advance_animations(node,136.)
                if cause=='hidden':state['visible']=False
                elif cause=='minimized':state['minimized']=True
                else:node._motion=False
                updates=node.update.call_count
                node._update_animation_state()
                self.assertEqual(node._gpu_insertion.progress,0.);self.assertFalse(node._gpu_insertion.active)
                self.assertFalse(node._clock_active_state)
                self.assertGreater(node.update.call_count,updates,'Restored pose/cables need one repaint after reset')
                self.assertFalse(AssemblyViewport.preview_gpu_insertion(node,True))

    def test_selected_gpu_effect_follows_the_same_pose_but_case_effect_does_not(self):
        node=renderer(scene());self.addCleanup(node.close)
        for target,expected_x in (('gpu:0',-40.),('gpu',-40.),('case',0.)):
            node.draw(1000,800,yaw=0,pitch=0,gpu_offset=(-40.,0.,0.),effect=effect_sample('sticker',100.,target))
            centers=[args[1] for name,args in node.program.calls if name=='setUniformValue' and args[0]=='effectCenter']
            self.assertAlmostEqual(centers[-1].x(),expected_x,places=5)

    def test_colored_showcase_styles_apply_matte_depth_in_the_actual_renderer(self):
        for style in ('cartoon','notebook_color','sticker','papercut','notebook_line'):
            with self.subTest(style=style):
                node=renderer(scene(style))
                try:
                    node.draw(1000,800,yaw=-34,pitch=18)
                    shades=[args[1] for name,args in node.functions.calls if name=='glUniform1f' and args[0]==2]
                    self.assertTrue(shades)
                    self.assertEqual(max(shades)>0,style!='notebook_line')
                    gpu=next(mesh for mesh in node.scene.meshes if mesh.component=='gpu')
                    material=node._materials[id(gpu)]
                    self.assertEqual(material[:2],(0.,1.),'Colored art stays matte, not metallic')
                finally:node.close()


if __name__=='__main__':unittest.main()
