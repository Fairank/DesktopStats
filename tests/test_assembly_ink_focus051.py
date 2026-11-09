"""Focused real contours and unchanged physical upload, with a fake GPU only."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from assembly_auxiliary import add_auxiliary
from assembly_geometry import Mesh,Scene,box,vertex_bytes
from assembly_style import edge_batches,MAX_STYLE_EDGES,MAX_GRILLE_EDGES
from assembly_viewer import AssemblyRenderer,AssemblyViewport
from test_assembly_visibility048 import Backend


def segment_count(batches):return sum(len(vertices)//12 for _,vertices in batches)


class FocusedInkTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native graphics, device or worker')))

    def test_focus_keeps_original_style_indices_part_identity_and_case_panels(self):
        meshes=(Mesh('body',box(10,20,30),(.2,.3,.4,1.),component='case'),
                Mesh('glass',box(1,20,30),(.2,.3,.4,.2),component='panel'),
                Mesh('ram-a',box(1,20,10),(.2,.3,.4,1.),component='memory',part_id='memory:0'),
                Mesh('ram-b',box(1,20,10),(.2,.3,.4,1.),component='memory',part_id='memory:1'))
        styles=('notebook_line','notebook_line','miniature','notebook_line')
        self.assertEqual(edge_batches(meshes,'notebook_line',styles),
                         edge_batches(meshes,'notebook_line',styles,focus='all'))
        self.assertEqual({mesh.name for mesh,_ in edge_batches(meshes,'miniature',styles,focus='case')},
                         {'body','glass'})
        self.assertEqual(edge_batches(meshes,'notebook_line',styles,focus='memory:0'),())
        self.assertEqual([mesh.name for mesh,_ in edge_batches(meshes,'miniature',styles,focus='memory')],['ram-b'])
        self.assertEqual(edge_batches(meshes,'notebook_line',styles,focus='memory:99'),())

    def test_real_psu_apertures_receive_their_own_existing_bounded_budget(self):
        psu,_=add_auxiliary({'auxiliary':{'psu':{'model_id':'corsair-rm1000x-2024'}}},
                            {'case_dimensions':(600,800,800),'psu':{'position':(0,0,0)}})
        # Competing structural contours reproduce the whole-PC reservation
        # pressure without constructing another expensive full scene.
        frame=Mesh('case-frame',box(20,30,40),(.2,.3,.4,1.),component='case')
        meshes=tuple(replace(frame,name='case-frame-'+str(i)) for i in range(600))+tuple(psu)
        whole=edge_batches(meshes,'notebook_line')
        focused=edge_batches(meshes,'notebook_line',focus='psu')
        self.assertEqual(focused,edge_batches(psu,'notebook_line'))
        whole_panel=next((len(v)//12 for m,v in whole if m.name=='psu-fan-panel'),0)
        focused_panel=next(len(v)//12 for m,v in focused if m.name=='psu-fan-panel')
        self.assertGreater(focused_panel,whole_panel)
        self.assertGreater(focused_panel,1000,'A few dots are not a recognizable aperture grille')
        self.assertLessEqual(focused_panel,MAX_GRILLE_EDGES)
        self.assertLessEqual(segment_count(whole),MAX_STYLE_EDGES)
        self.assertLessEqual(segment_count(focused),MAX_STYLE_EDGES)
        self.assertTrue(all(m.component=='psu' for m,_ in focused))

    def test_focus_upload_keeps_all_physical_bytes_bounds_and_triangle_picking(self):
        meshes=(Mesh('psu-shell',box(10,10,10),(.2,.3,.4,1.),component='psu',part_id='psu:0'),
                Mesh('gpu-shroud',box(10,10,10),(.2,.3,.4,1.),(30,0,0),'gpu',part_id='gpu:0'))
        scene=Scene(meshes,(100,100,100),{'visual_style':'notebook_line'})
        node=AssemblyRenderer();node.program=Backend();node.buffer=Backend();node.vao=Backend();node.functions=Backend()
        node._uniforms={'backgroundMode':1,'shadeMix':2};self.addCleanup(node.close)
        node.upload(scene);bounds,pick,ranges=node.bounds,node.pick_bounds,node.ranges
        original=vertex_bytes(scene)
        node.upload(scene,ink_focus='psu:0')
        payload,size=[args for name,args in node.buffer.calls if name=='allocate'][-1]
        self.assertEqual(payload[:len(original)],original);self.assertEqual(len(payload),size)
        self.assertEqual((node.bounds,node.pick_bounds,node.ranges),(bounds,pick,ranges))
        self.assertEqual({m.part_id for m,_,_ in node.edge_ranges},{'psu:0'})
        allocations=sum(name=='allocate' for name,_ in node.buffer.calls)
        for phase in (0,12,24):node.draw(800,600,yaw=0,pitch=0,focus='psu:0',phase=phase)
        point=node.project_point((0,0,0));self.assertEqual(node.pick(*point[:2]),'psu:0')
        self.assertEqual(sum(name=='allocate' for name,_ in node.buffer.calls),allocations)
        node.upload(scene,ink_focus='all')
        self.assertEqual({m.part_id for m,_,_ in node.edge_ranges},{'psu:0','gpu:0'})
        self.assertEqual(vertex_bytes(scene),original)

    def test_viewport_rebuilds_static_ink_only_on_explicit_changed_valid_focus(self):
        scene=Scene((Mesh('psu-shell',box(1,2,3),(.2,.3,.4,1.),component='psu',part_id='psu:0'),),
                    (100,100,100),{'visual_style':'notebook_line'})
        node=SimpleNamespace(_error='',_pending=False,_renderer=Mock(),_scene=scene,_focus='all',
            _yaw=0.,_pitch=0.,_zoom=1.,_exploded=False,_phase=0.,_dark=False,_transparent_background=False,
            _update_animation_state=Mock(),reset_camera=Mock(),focusChanged=Mock(),
            devicePixelRatioF=lambda:1.,width=lambda:800,height=lambda:600)
        self.assertFalse(AssemblyViewport.focus_component(node,'memory:99'));self.assertFalse(node._pending)
        self.assertTrue(AssemblyViewport.focus_component(node,'psu:0'));self.assertTrue(node._pending)
        AssemblyViewport.paintGL(node)
        node._renderer.upload.assert_called_once_with(scene,ink_focus='psu:0')
        self.assertFalse(node._pending)
        self.assertTrue(AssemblyViewport.focus_component(node,'psu:0'));self.assertFalse(node._pending)
        for phase in (12,24,36):node._phase=phase;AssemblyViewport.paintGL(node)
        self.assertEqual(node._renderer.upload.call_count,1)
        self.assertTrue(AssemblyViewport.focus_component(node,'all'));self.assertTrue(node._pending)
        AssemblyViewport.paintGL(node)
        self.assertEqual(node._renderer.upload.call_count,2)
        self.assertEqual(node._renderer.upload.call_args.kwargs,{'ink_focus':'all'})
        scene.metadata['visual_style']='miniature'
        self.assertTrue(AssemblyViewport.focus_component(node,'psu'));self.assertFalse(node._pending)
        # A per-mesh line override in an otherwise original scene still needs
        # focus-specific preparation; use the actual override list, not canvas.
        scene.metadata['mesh_style_ids']=('notebook_line',)
        self.assertTrue(AssemblyViewport.focus_component(node,'all'));self.assertTrue(node._pending)


if __name__=='__main__':unittest.main()
