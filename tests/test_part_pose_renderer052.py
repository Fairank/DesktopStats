"""Independent part transforms reach real triangle/ink/pick paths, no GPU."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PySide6.QtGui import QVector3D
from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_effects import effect_sample
from assembly_style import apply_model_styles
from assembly_pose052 import valid_offsets,valid_hidden,posed_bounds
from assembly_viewer import AssemblyRenderer,GL_LINES,GL_TRIANGLES
from test_assembly_visibility048 import Backend

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def scene(style='miniature'):
    meshes=(Mesh('frame-left',box(2,2,2),(.2,.3,.4,1.),(-100,-140,-90),'case'),
            Mesh('frame-right',box(2,2,2),(.2,.3,.4,1.),(100,140,90),'case'),
            Mesh('cpu-lid',box(16,16,6),(.6,.7,.8,1.),(-20,15,0),'cpu',part_id='cpu:0'),
            Mesh('ram-a',box(5,35,9),(.2,.4,.3,1.),(25,20,0),'memory',part_id='memory:0'),
            Mesh('ram-b',box(5,35,9),(.2,.4,.3,1.),(42,20,0),'memory',part_id='memory:1'))
    values,metadata=apply_model_styles(meshes,style,{},(240,360,240),{'front':'open'})
    return Scene(values,(240,360,240),metadata)


def renderer(value):
    node=AssemblyRenderer();node.program=Backend();node.buffer=Backend();node.vao=Backend();node.functions=Backend()
    node._uniforms={'backgroundMode':1,'shadeMix':2};node.upload(value)
    return node


class PartPoseRendererTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native GPU, device or worker')))

    def test_all_six_styles_move_actual_solid_and_ink_without_upload_or_mesh_changes(self):
        offsets={'cpu:0':(0.,70.,40.),'memory:0':(0.,-70.,40.)}
        for style in SIX:
            with self.subTest(style=style):
                value=scene(style);original=vertex_bytes(value);node=renderer(value)
                try:
                    allocations=sum(name=='allocate' for name,_ in node.buffer.calls)
                    seen=[];draw=node._draw_part
                    def record(row,*args,**kwargs):
                        draw(row,*args,**kwargs)
                        matrix=next(args[1] for name,args in reversed(node.program.calls)
                                    if name=='setUniformValue' and args[0]=='modelMatrix')
                        p=matrix.map(QVector3D());seen.append((row[0],kwargs.get('mode',GL_TRIANGLES),(p.x(),p.y(),p.z())))
                    node._draw_part=record
                    node.draw(1000,800,yaw=0,pitch=0,part_offsets=offsets,part_extents=offsets)
                    for mesh,mode,position in seen:
                        delta=offsets.get(mesh.part_id,(0,0,0))
                        self.assertEqual(position,tuple(mesh.position[k]+delta[k] for k in range(3)))
                    for target in offsets:
                        self.assertTrue(any(m.part_id==target and mode==GL_TRIANGLES for m,mode,_ in seen))
                        if style!='miniature':self.assertTrue(any(m.part_id==target and mode==GL_LINES for m,mode,_ in seen))
                    for point,target in (((-20.,85.,40.),'cpu:0'),((25.,-50.,40.),'memory:0'),((42.,20.,0.),'memory:1')):
                        projected=node.project_point(point)
                        self.assertEqual(node.pick(*projected[:2]),target)
                    self.assertEqual(node.pick(*node.project_point((-20.,15.,0.))[:2]),'')
                    self.assertEqual(sum(name=='allocate' for name,_ in node.buffer.calls),allocations)
                    self.assertEqual(vertex_bytes(value),original)
                finally:node.close()

    def test_explicit_hidden_part_and_name_gates_apply_to_solids_lines_and_clicks(self):
        node=renderer(scene('notebook_line'));self.addCleanup(node.close)
        seen=[];draw=node._draw_part
        def record(row,*args,**kwargs):seen.append(row[0].name);draw(row,*args,**kwargs)
        node._draw_part=record
        node.draw(900,700,yaw=0,pitch=0,hidden_parts={'memory:0'},hidden_mesh_names={'cpu-lid'})
        self.assertNotIn('ram-a',seen);self.assertNotIn('cpu-lid',seen);self.assertIn('ram-b',seen)
        self.assertEqual(node.pick(*node.project_point((-20.,15.,0.))[:2]),'')
        self.assertEqual(node.pick(*node.project_point((25.,20.,0.))[:2]),'')
        self.assertEqual(node.pick(*node.project_point((42.,20.,0.))[:2]),'memory:1')
        seen.clear();node.draw(900,700,yaw=0,pitch=0,hidden_parts={'memory'})
        self.assertNotIn('ram-a',seen);self.assertNotIn('ram-b',seen)
        self.assertEqual(node.pick(*node.project_point((-20.,15.,0.))[:2]),'cpu:0')
        seen.clear();node.draw(900,700,yaw=0,pitch=0)
        self.assertIn('ram-a',seen);self.assertEqual(node.upload_count,1)

    def test_finite_pose_extent_keeps_camera_inverse_fixed_across_motion_ticks(self):
        node=renderer(scene());self.addCleanup(node.close)
        extent={'memory:0':(0.,-70.,40.)};inverse=None;key=None
        with patch('assembly_viewer.scene_bounds',side_effect=AssertionError('No per-frame geometry scan')):
            for progress in (0.,.25,.5,.75,1.):
                pose={'memory:0':tuple(v*progress for v in extent['memory:0'])}
                node.draw(1000,800,yaw=0,pitch=0,focus='memory:0',part_offsets=pose,part_extents=extent)
                if inverse is None:inverse=node._pick_inverse;key=node._pick_camera_key
                self.assertIs(node._pick_inverse,inverse);self.assertEqual(node._pick_camera_key,key)
                point=(25.,20.-70*progress,40*progress)
                self.assertEqual(node.pick(*node.project_point(point)[:2]),'memory:0')
        self.assertEqual(node.upload_count,1)

    def test_selection_effect_center_follows_the_actual_part_and_forget_releases_pose_state(self):
        node=renderer(scene('cartoon'));self.addCleanup(node.close)
        node.draw(900,700,part_offsets={'cpu:0':(0.,70.,40.)},effect=effect_sample('cartoon',100.,'cpu:0'))
        centers=[args[1] for name,args in node.program.calls if name=='setUniformValue' and args[0]=='effectCenter']
        self.assertEqual((centers[-1].x(),centers[-1].y(),centers[-1].z()),(-20.,85.,40.))
        node.forget_scene();self.assertEqual(node._frame_part_offsets,{})
        self.assertEqual(node._mesh_names,frozenset());self.assertIsNone(node.scene)

    def test_malformed_pose_is_rejected_as_a_whole_and_family_bounds_remain_conservative(self):
        known={'cpu:0','memory:0','memory:1','memory'}
        for bad in ({'cpu:0':(0.,True,2.)},{'cpu:0':(0.,math.nan,2.)},{'cpu:0':(0.,0.,2001.)},
                    {'cpu:0':(0,2,3),'missing:0':(0,0,0)},{'cpu:0':[0,1]},['cpu:0']):
            self.assertEqual(valid_offsets(bad,known),{})
        self.assertEqual(valid_hidden({'cpu:0','missing'},known),frozenset())
        node=renderer(scene());self.addCleanup(node.close)
        bounds=posed_bounds(node.pick_bounds,'memory',False,{'memory:0':(0,-70,40)})
        self.assertLessEqual(bounds[0][1],-67.5);self.assertGreaterEqual(bounds[1][0],44.5)
        node.draw(900,700,yaw=0,pitch=0,part_offsets={'cpu:0':(0.,math.nan,0.)})
        self.assertNotIn('part_offsets',node._pick_state)
        self.assertEqual(node.pick(*node.project_point((-20.,15.,0.))[:2]),'cpu:0')

    def test_exact_override_of_a_moved_family_keeps_the_actual_part_clickable(self):
        node=renderer(scene('notebook_line'));self.addCleanup(node.close)
        offsets={'memory':(0.,70.,0.),'memory:0':(0.,-80.,0.)}
        for focus in ('all','memory','memory:0'):
            node.draw(1000,800,yaw=0,pitch=0,focus=focus,part_offsets=offsets,part_extents=offsets)
            point=node.project_point((25.,-60.,0.))
            self.assertEqual(node.pick(*point[:2]),'memory:0')
        node.draw(1000,800,yaw=0,pitch=0,part_offsets=offsets)
        self.assertEqual(node.pick(*node.project_point((42.,90.,0.))[:2]),'memory:1')
        self.assertEqual(node.upload_count,1)

    def test_case_family_moves_its_panel_and_nonstandard_part_id_uses_source_family(self):
        mesh=Mesh('glass',box(8,8,1),(.2,.3,.4,.2),(-25,0,0),'panel',part_id='panel:left')
        fan=Mesh('source-fan',box(8,8,2),(.2,.3,.4,1.),(25,0,0),'fans',part_id='case-fan:0')
        value=Scene((mesh,fan),(100,100,100),{'visual_style':'notebook_line'})
        node=renderer(value);self.addCleanup(node.close)
        offsets={'case':(0.,30.,0.),'fans':(0.,-30.,0.)}
        self.assertEqual(node._shift(mesh,False,None,offsets),(0.,30.,0.))
        for focus in ('all','case-fan:0','fans'):
            node.draw(900,700,yaw=0,pitch=0,focus=focus,part_offsets=offsets,part_extents=offsets)
            self.assertEqual(node.pick(*node.project_point((25.,-30.,0.))[:2]),'case-fan:0')
        panel_bounds=posed_bounds(node.pick_bounds,'panel:left',False,offsets,families=node._pose_families)
        self.assertEqual(panel_bounds[0][1],26.)


if __name__=='__main__':unittest.main()
