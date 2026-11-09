"""Independent hardware treatments retain one geometry upload and one finite clock."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assembly_effects import SelectionEffect,effect_for,effect_sample
from assembly_geometry import Mesh,Scene,box
from assembly_style import MAX_STYLE_EDGES,apply_model_styles,edge_batches
from assembly_viewer import AssemblyRenderer,AssemblyViewport


class MixedAssemblyStyleTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Mixed styles perform no I/O')))
        self.meshes=tuple(Mesh('part-'+str(n),box(10,20,4),(.2,.4,.6,1.),position=(x,0,0),
            component=group,part_id=part) for n,(group,part,x) in enumerate((
                ('memory','memory:0',-25),('memory','memory:1',0),('gpu','gpu:0',25))))

    def renderer(self,meshes,meta):
        renderer=AssemblyRenderer();renderer.program=Mock();renderer.buffer=Mock();renderer.vao=Mock()
        renderer.functions=Mock();renderer._uniforms={'backgroundMode':4,'shadeMix':9}
        renderer.upload(Scene(meshes,(100,100,100),meta))
        self.addCleanup(renderer.close)
        return renderer

    def test_instance_overrides_family_and_default_without_changing_physical_models(self):
        overrides={'memory':'notebook_color','memory:1':'notebook_line','gpu':'miniature'}
        before=copy.deepcopy(overrides)
        meshes,meta=apply_model_styles(self.meshes,'cartoon',overrides,(100,100,100),{'front':'open'})
        self.assertEqual(meta['mesh_style_ids'],('notebook_color','notebook_line','miniature'))
        self.assertEqual(meta['part_style_map']['memory'],'notebook_color')
        self.assertEqual(meta['part_style_map']['memory:1'],'notebook_line')
        self.assertFalse(meta['decorative_expression']);self.assertEqual(overrides,before)
        for source,painted in zip(self.meshes,meshes):
            self.assertIs(source.vertices,painted.vertices)
            self.assertEqual((source.position,source.component,source.part_id,source.rotor,source.axis),
                             (painted.position,painted.component,painted.part_id,painted.rotor,painted.axis))
        self.assertEqual(meshes[2],self.meshes[2])

    def test_only_the_effective_case_style_can_add_an_expression(self):
        for default,overrides,expected in (
                ('miniature',{'gpu':'cartoon'},False),('cartoon',{'case':'miniature'},False),
                ('miniature',{'case':'notebook_smile'},True)):
            meshes,meta=apply_model_styles(self.meshes,default,overrides,(100,100,100),{})
            self.assertEqual(meta['decorative_expression'],expected)
            self.assertEqual(len(meshes),len(self.meshes)+expected)

    def test_mixed_materials_ink_and_picking_share_a_single_immutable_upload(self):
        meshes,meta=apply_model_styles(self.meshes,'miniature',{'memory':'notebook_line'},(100,100,100),{})
        renderer=self.renderer(meshes,meta)
        self.assertEqual(renderer.buffer.allocate.call_count,1)
        self.assertEqual({mesh.part_id for mesh,_,_ in renderer.edge_ranges},{'memory:0','memory:1'})
        renderer.draw(640,480,yaw=0,pitch=0)
        for mesh in meshes:
            point=renderer.project_point(mesh.position)
            self.assertEqual(renderer.pick(*point[:2]),mesh.part_id)
        renderer.draw(640,480,yaw=0,pitch=0,focus='memory:1',selected='memory:1',
                      effect=effect_sample('notebook_line',100,'memory:1'))
        self.assertEqual(renderer.upload_count,1)
        self.assertEqual(renderer._frame_effect_samples.keys(),{'notebook_line'})
        self.assertEqual(renderer._materials[id(meshes[2])][0],.23)
        self.assertEqual(renderer._materials[id(meshes[1])],(0.,1.,0.,0.))
        renderer.close();self.assertEqual(renderer._mesh_policies,{})

    def test_all_mixed_ink_uses_one_global_edge_budget(self):
        meshes=self.meshes*1000;styles=tuple(('miniature','notebook_color','notebook_line')[n%3] for n in range(len(meshes)))
        batches=edge_batches(meshes,'miniature',styles)
        self.assertLessEqual(sum(len(vertices)//12 for _,vertices in batches),MAX_STYLE_EDGES)
        self.assertTrue(batches)

    def test_main_frame_keeps_its_closed_outline_when_small_contacts_fill_the_budget(self):
        frame=Mesh('case-side-mount-frame',box(5,450,5),(.4,.5,.6,1.))
        pins=tuple(Mesh('board-socket-spring-heads',box(2,2,1),(.4,.5,.6,1.),
                        position=(n,0,0),component='board') for n in range(700))
        meshes=(*pins,frame)
        for style,expected in (('outline',12),('notebook_line',16)):
            batches=edge_batches(meshes,style)
            self.assertEqual(next(len(lines)//12 for mesh,lines in batches if mesh is frame),expected)
            self.assertLessEqual(sum(len(lines)//12 for _,lines in batches),MAX_STYLE_EDGES)

    def test_structural_edges_survive_the_local_perforation_sampling_limit(self):
        from assembly_style import crease_edges
        from assembly_detail import translated
        vertices=box(300,200,2)+tuple(v for n in range(100) for v in translated(box(2,2,1),(n,10,0)))
        long_edges={edge for edge in crease_edges(box(300,200,2)) if __import__('math').dist(*edge)>100}
        self.assertTrue(long_edges.issubset(set(crease_edges(vertices,64))))

    def test_line_width_tracks_pixel_density_within_the_drivers_supported_range(self):
        meshes,meta=apply_model_styles(self.meshes,'notebook_line',{},(100,100,100),{})
        renderer=self.renderer(meshes,meta);renderer._wide_lines=True
        renderer.draw(640,480,pixel_scale=1.75)
        self.assertTrue(any(abs(call.args[0]-2.8)<1e-8 for call in renderer.functions.glLineWidth.call_args_list))

    def test_family_selection_uses_each_parts_effect_then_retires_at_the_longest_duration(self):
        meshes,meta=apply_model_styles(self.meshes,'miniature',
            {'memory:0':'notebook_line','memory:1':'notebook_color'},(100,100,100),{})
        node=SimpleNamespace(_closed=False,_error='',_motion=True,_selection_effects=True,
            _effect=SelectionEffect(),_effect_active=False,_clock_active_state=False,
            _animate=False,_fan_available=False,_rpm=0.,_fan_expiry=0.,_active=False,_phase=0.,
            _focus='all',_scene=Scene(meshes,(100,100,100),meta),_pending=False,
            animationActiveChanged=Mock(),update=Mock(),isVisible=lambda:True,
            window=lambda:SimpleNamespace(isMinimized=lambda:False))
        node._update_animation_state=lambda:AssemblyViewport._update_animation_state(node)
        self.assertTrue(AssemblyViewport.preview_effect(node,'memory'))
        expected=max(effect_for(style)['duration_ms'] for style in meta['mesh_style_ids'][:2])
        self.assertEqual(effect_for(node._effect.style)['duration_ms'],expected)
        for _ in range(30):AssemblyViewport.advance_animations(node,34)
        self.assertFalse(node._clock_active_state);self.assertFalse(node._effect_active)
        self.assertEqual(node._phase,0.);self.assertFalse(node._pending)


if __name__=='__main__':unittest.main()
