"""All artwork schemes retain physical case/component geometry and idle budgets."""
import copy
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from assembly_geometry import Mesh,Scene,box,build_scene,vertex_bytes
from assembly_style import (MAX_STYLE_EDGES,apply_colors,crease_edges,edge_batches,
                            resolve_style,style_for)
from chassis_catalog import CASES
from hardware_appearance import appearance_for
from top_bar_config import HARDWARE_ICON_STYLES


class AssemblyStyleTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Artwork cannot access devices/workers')))

    def test_every_scheme_keeps_all_80_cases_and_component_shapes(self):
        self.assertEqual(len(CASES),80);self.assertEqual(len(HARDWARE_ICON_STYLES),13)
        gpu={'appearance':appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')}
        def physical(mesh):return (mesh.name,mesh.vertices,mesh.position,mesh.component,mesh.rotor,mesh.direction,mesh.axis)
        for case in CASES:
            base=build_scene({'case':case,'gpu':gpu,'memory':{'count':2}})
            source=[physical(m) for m in base.meshes]
            for style in HARDWARE_ICON_STYLES:
                with self.subTest(case=case['id'],style=style):
                    scene=build_scene({'case':case,'gpu':gpu,'memory':{'count':2},'visual_style':style})
                    self.assertEqual(scene.dimensions,base.dimensions)
                    self.assertEqual(scene.metadata['case_id'],case['id'])
                    self.assertEqual(scene.metadata['visual_style'],style)
                    self.assertEqual([physical(m) for m in scene.meshes if not m.name.startswith('style-')],source)
                    self.assertEqual(scene.metadata['rotor_count'],base.metadata['rotor_count'])
                    self.assertTrue(all(math.isfinite(v) for m in scene.meshes for v in m.color))
                    expressions=[m for m in scene.meshes if m.name=='style-case-expression']
                    if style not in ('cartoon','notebook_smile'):self.assertEqual(expressions,[])
                    self.assertTrue(all(m.vertex_count//3<=48 for m in expressions))
                    if style=='miniature':self.assertEqual(scene.meshes,base.meshes)

    def test_all_thirteen_treatments_are_distinct_and_unknown_inputs_keep_original(self):
        base=build_scene({'case':CASES[0]});fingerprints=set()
        for style in HARDWARE_ICON_STYLES:
            policy=style_for(style);scene=build_scene({'case':CASES[0],'visual_style':style})
            fingerprints.add((tuple(m.color for m in scene.meshes),policy['edges'],policy['wobble'],
                              policy['line_only'],policy['paper_grid'],policy['shading'],policy['ink']))
        self.assertEqual(len(fingerprints),13)
        for bad in (None,'',False,{},['cartoon'],'unknown'):
            self.assertEqual(resolve_style(bad),'miniature')
            self.assertEqual(build_scene({'case':CASES[0],'visual_style':bad}),base)

    def test_input_and_retained_model_vertices_are_immutable(self):
        value={'case':copy.deepcopy(CASES[0]),'visual_style':'notebook_color'};before=copy.deepcopy(value)
        scene=build_scene(value);self.assertEqual(value,before)
        base=build_scene({'case':CASES[0]});colored=apply_colors(base.meshes,'sticker')
        self.assertTrue(all(a.vertices is b.vertices for a,b in zip(base.meshes,colored)))
        batches=edge_batches(scene.meshes,'notebook_color')
        self.assertEqual(batches,edge_batches(scene.meshes,'notebook_color'))
        self.assertEqual(value,before)

    def test_crease_ink_excludes_internal_triangle_diagonals(self):
        self.assertEqual(len(crease_edges(box(10,20,30))),12)
        square=(0,0,0,0,0,1, 10,0,0,0,0,1, 10,10,0,0,0,1,
                0,0,0,0,0,1, 10,10,0,0,0,1, 0,10,0,0,0,1)
        edges=crease_edges(square);self.assertEqual(len(edges),4)
        self.assertNotIn(((0,0,0),(10,10,0)),edges)
        self.assertEqual(crease_edges(square,0),())

    def test_t_junctions_cancel_coplanar_partition_edges_without_inventing_chords(self):
        from assembly_geometry import _quad
        vertices=[]
        for left,right,bottom,top in ((0,10,0,20),(10,20,0,10),(10,20,10,20)):
            _quad(vertices,(left,bottom,0),(right,bottom,0),(right,top,0),(left,top,0))
        edges=crease_edges(tuple(vertices),4)
        self.assertEqual(set(edges),{((0,0,0),(0,20,0)),((0,0,0),(20,0,0)),
                                     ((0,20,0),(20,20,0)),((20,0,0),(20,20,0))})

    def test_repeated_triangle_vertices_quantize_once_without_retaining_a_cache(self):
        import assembly_style
        vertices=box(10,20,30)
        distinct=len({vertices[start:start+3] for start in range(0,len(vertices),6)})
        with patch.object(assembly_style,'_key',wraps=assembly_style._key) as quantize:
            first=crease_edges(vertices)
            self.assertEqual(quantize.call_count,distinct)
            second=crease_edges(vertices)
            self.assertEqual(quantize.call_count,distinct*2)
        self.assertEqual(first,second)
        self.assertEqual(len(first),12)

    def test_shared_contour_nodes_keep_whole_components_and_exact_spans(self):
        from assembly_style import _edge_groups
        center=(0.,0.,0.)
        corners=((-3.,-4.,0.),(3.,-4.,0.),(3.,4.,0.),(-3.,4.,0.))
        edges=tuple((center,point) for point in corners)+tuple(zip(corners,(*corners[1:],corners[0])))
        edges+=(((20.,0.,0.),(20.,5.,0.)),((20.,5.,0.),(25.,5.,0.)))
        self.assertEqual(_edge_groups(edges),[(tuple(range(8)),8.),((8,9),5.)])

    def test_main_fan_blades_and_hub_survive_dense_acceleration_grooves_whole(self):
        from assembly_cooling import add_cooling
        from assembly_style import _edge_groups,MAX_MESH_EDGES
        meshes,_=add_cooling((),{'cooling':{'case_fans':[dict(model='noctua-nf-a12x25-pwm',mount='front',count=1)]}},
                            anchors={'case_dimensions':(600,800,800)})
        rotor=next(mesh for mesh in meshes if mesh.rotor)
        raw=crease_edges(rotor.vertices,MAX_STYLE_EDGES);retained=set(crease_edges(rotor.vertices))
        main=[group for group,span in _edge_groups(raw) if span>=20]
        self.assertEqual(len(main),11)  # Nine separate leaves and two hub rims.
        self.assertEqual(sum(map(len,main)),480)
        self.assertLessEqual(len(retained),MAX_MESH_EDGES)
        self.assertTrue(all(raw[index] in retained for group in main for index in group))
        batches=edge_batches(meshes,'notebook_line')
        vertices=next(points for mesh,points in batches if mesh is rotor)
        ink={tuple(vertices[i:i+3]) for i in range(0,len(vertices),6)}
        self.assertTrue(all(point in ink for group in main for index in group for point in raw[index]))

    def test_dense_psu_grille_keeps_closed_apertures_with_bounded_candidates_and_final_ink(self):
        from assembly_auxiliary import add_auxiliary
        from assembly_style import _edge_groups,MAX_GRILLE_EDGES
        meshes,_=add_auxiliary({'auxiliary':{'psu':{'model_id':'corsair-rm1000x-2024'}}},
                              {'case_dimensions':(600,800,800),'psu':{'position':(0,0,0)}})
        panel=next(mesh for mesh in meshes if mesh.name=='psu-fan-panel')
        original=panel.vertices;edges=crease_edges(panel.vertices,MAX_GRILLE_EDGES)
        self.assertLessEqual(len(edges),MAX_GRILLE_EDGES)
        apertures=[group for group,span in _edge_groups(edges) if 5<span<20]
        self.assertGreater(len(apertures),40)
        for group in apertures:
            degree={}
            for index in group:
                for point in edges[index]:degree[point]=degree.get(point,0)+1
            self.assertGreaterEqual(min(degree.values()),2)
        batches=edge_batches(meshes,'notebook_line')
        self.assertLessEqual(sum(len(points)//12 for _,points in batches),MAX_STYLE_EDGES)
        self.assertIs(panel.vertices,original)

    def test_all_eight_fan_corner_pad_contours_survive_batched_partitions(self):
        from assembly_cooling import add_cooling
        from assembly_style import _edge_groups,MAX_MESH_EDGES
        meshes,_=add_cooling((),{'cooling':{'case_fans':[dict(model='noctua-nf-a12x25-pwm',mount='front',count=1)]}},
                            anchors={'case_dimensions':(600,800,800)})
        pads=next(mesh for mesh in meshes if mesh.name=='case-fan-pads')
        edges=crease_edges(pads.vertices,repair_partitions=True)
        self.assertLessEqual(len(edges),MAX_MESH_EDGES)
        contours=[group for group,span in _edge_groups(edges) if span>=15]
        self.assertEqual(len(contours),8)  # Four front and four back pads.
        self.assertEqual({len(group) for group in contours},{24})
        batches=edge_batches(meshes,'notebook_line')
        vertices=next(points for mesh,points in batches if mesh is pads)
        ink={tuple(vertices[i:i+3]) for i in range(0,len(vertices),6)}
        self.assertTrue(all(point in ink for group in contours for index in group for point in edges[index]))

    def test_wobbly_ink_has_one_bounded_static_budget_and_preserves_rotor_identity(self):
        vertices=box(10,10,10)
        meshes=tuple(Mesh('test-box',vertices,(.3,.4,.5,1.),rotor=n==799,direction=-1) for n in range(800))
        batches=edge_batches(meshes,'notebook_line')
        self.assertLessEqual(sum(len(v)//12 for _,v in batches),MAX_STYLE_EDGES)
        self.assertEqual(len(batches),len(meshes))
        self.assertIs(batches[-1][0],meshes[-1]);self.assertTrue(batches[-1][0].rotor)
        self.assertEqual(batches[-1][0].direction,-1)
        self.assertTrue(all(abs(v)<=6.2 for _,points in batches for n,v in enumerate(points) if n%6<3))
        self.assertEqual(edge_batches(meshes,'miniature'),())

    def test_hand_ink_vertices_stay_on_actual_surface_creases(self):
        mesh=Mesh('cpu-lid',box(1.4,37.5,45.),(.7,.8,.9,1.),component='cpu')
        edges=crease_edges(mesh.vertices)
        def on_edge(point,a,b):
            axis=max(range(3),key=lambda i:abs(b[i]-a[i]));t=(point[axis]-a[axis])/(b[axis]-a[axis])
            return -1e-9<=t<=1+1e-9 and all(abs(point[i]-(a[i]+t*(b[i]-a[i])))<1e-9 for i in range(3))
        for style in ('notebook_line','notebook_color','notebook_smile','sketch'):
            batches=edge_batches((mesh,),style);self.assertTrue(batches)
            for _,vertices in batches:
                for i in range(0,len(vertices),6):
                    self.assertTrue(any(on_edge(vertices[i:i+3],a,b) for a,b in edges),(style,vertices[i:i+3]))

    def test_ink_depth_bias_is_bounded_below_real_opaque_layer_separation(self):
        from assembly_viewer import ink_depth_bias
        for radius in (1.,20.,40.,400.,2000.):
            for multiplier in (1.98,3.6,9.):
                distance=radius*multiplier;bias=ink_depth_bias(distance,radius)
                self.assertGreaterEqual(bias,0.);self.assertLessEqual(bias,.00015)
                near=max(.1,distance-radius*1.5);far=distance+radius*2.;b=2*far*near/(far-near)
                farthest=distance+radius;shift=farthest-b/(b/farthest+bias)
                self.assertGreaterEqual(shift,0.);self.assertLessEqual(shift,.02500001)

    def fake_renderer(self,style,scene=None):
        from assembly_viewer import AssemblyRenderer
        renderer=AssemblyRenderer();renderer.program=Mock();renderer.buffer=Mock();renderer.vao=Mock()
        renderer.functions=Mock();renderer._uniforms={'backgroundMode':4,'shadeMix':9}
        renderer.upload(scene or build_scene({'case':CASES[0],'visual_style':style}))
        return renderer

    def test_original_uses_identical_single_buffer_without_face_ink_or_paper_pass(self):
        from assembly_viewer import GL_LINES,GL_POLYGON_OFFSET_FILL
        renderer=self.fake_renderer('miniature')
        self.assertEqual(renderer.buffer.allocate.call_count,1)
        self.assertEqual(renderer.buffer.allocate.call_args.args[0],vertex_bytes(renderer.scene))
        self.assertEqual(renderer.edge_segments,0);self.assertEqual(renderer.edge_ranges,[])
        renderer.draw(640,480)
        renderer.functions.glClearColor.assert_called_once_with(.94,.955,.965,1.)
        self.assertFalse(any(c.args[0]==GL_LINES for c in renderer.functions.glDrawArrays.call_args_list))
        self.assertFalse(any(c.args[0]==GL_POLYGON_OFFSET_FILL for c in renderer.functions.glEnable.call_args_list))
        self.assertEqual(renderer.upload_count,1)

    def test_notebook_grid_and_crease_lines_share_one_upload_with_cached_scalar_uniforms(self):
        from assembly_viewer import GL_LINES,GL_TRIANGLES
        renderer=self.fake_renderer('notebook_line')
        self.assertGreater(renderer.edge_segments,0)
        self.assertEqual(renderer.buffer.allocate.call_count,1)
        before=renderer.upload_count
        for phase in (0,16,32):renderer.draw(640,480,phase=phase)
        self.assertEqual(renderer.upload_count,before)
        self.assertEqual(renderer.functions.glDrawArrays.call_args_list[0].args,(GL_TRIANGLES,0,3))
        self.assertTrue(any(c.args[0]==GL_LINES for c in renderer.functions.glDrawArrays.call_args_list))
        scalars=[call.args for call in renderer.functions.glUniform1f.call_args_list]
        self.assertTrue(scalars);self.assertTrue(all(type(args[0]) is int for args in scalars))
        renderer.program.uniformLocation.assert_not_called()

    def test_close_releases_static_ink_and_main_graphics_resources(self):
        renderer=self.fake_renderer('notebook_color')
        buffer,vao,program=renderer.buffer,renderer.vao,renderer.program
        renderer.close();buffer.destroy.assert_called_once();vao.destroy.assert_called_once()
        program.removeAllShaders.assert_called_once()
        self.assertEqual(renderer.edge_ranges,[]);self.assertEqual(renderer.edge_segments,0)
        self.assertEqual(renderer._uniforms,{});self.assertIsNone(renderer.scene)
        renderer.close()

    def test_papercut_and_solid_have_readable_hardware_ink_without_outlining_case(self):
        meshes=(Mesh('case',box(20,20,20),(.3,.4,.5,.13),component='case'),
                Mesh('gpu-rotor',box(10,10,1),(.1,.1,.1,1.),component='gpu',rotor=True))
        for style in ('papercut','solid'):
            colored=apply_colors(meshes,style)
            self.assertEqual(colored[0].color[3],.13)
            self.assertGreater(sum(colored[1].color[:3]),1.8)
            batches=edge_batches(colored,style)
            self.assertEqual([mesh.component for mesh,_ in batches],['gpu'])

    def test_pure_ray_broadphase_and_triangle_geometry_are_two_sided(self):
        from assembly_viewer import ray_box,ray_triangle,posed_point
        self.assertEqual(ray_box((0,0,10),(0,0,-1),(-1,-1,-1),(1,1,1)),9)
        self.assertIsNone(ray_box((2,0,10),(0,0,-1),(-1,-1,-1),(1,1,1)))
        self.assertEqual(ray_box((0,0,0),(1,0,0),(-1,-1,-1),(1,1,1)),0)
        triangle=((-1,-1,0),(1,-1,0),(0,1,0))
        self.assertEqual(ray_triangle((0,0,10),(0,0,-1),*triangle),10)
        self.assertEqual(ray_triangle((0,0,10),(0,0,-1),*reversed(triangle)),10)
        self.assertIsNone(ray_triangle((3,0,10),(0,0,-1),*triangle))
        rotor=Mesh('rotor',box(2,2,1),(1,1,1,1),position=(4,5,6),rotor=True,direction=-1)
        point=posed_point(rotor,(1,0,0),(1,1,1),90)
        for a,b in zip(point,(5,5,7)):self.assertAlmostEqual(a,b)

    def test_click_ignores_glass_but_respects_opaque_case_and_real_mesh_gaps(self):
        def scene(alpha):
            return Scene((Mesh('gpu',box(20,20,4),(.4,.5,.6,1),component='gpu'),
                          Mesh('front',box(80,80,1),(.5,.6,.7,alpha),position=(0,0,25),component='panel')),
                         (100,100,100),{'visual_style':'miniature'})
        for alpha,expected in ((.13,'gpu'),(1.,'case')):
            renderer=self.fake_renderer('miniature',scene(alpha));renderer.draw(640,480,yaw=0,pitch=0)
            point=renderer.project_point((0,0,0))
            self.assertEqual(renderer.pick(*point[:2]),expected)
            self.assertEqual(renderer.pick(-1,-1),'')
        gap_scene=Scene((Mesh('ram-left',box(6,25,3),(.3,.5,.4,1),(-12,0,0),'memory'),
                         Mesh('ram-right',box(6,25,3),(.3,.5,.4,1),(12,0,0),'memory'),
                         Mesh('board',box(40,35,1),(.3,.4,.3,1),(0,0,-5),'board')),
                        (100,100,100),{'visual_style':'miniature'})
        renderer=self.fake_renderer('miniature',gap_scene);renderer.draw(640,480,yaw=0,pitch=0)
        point=renderer.project_point((0,0,0))
        self.assertEqual(renderer.pick(*point[:2]),'board')

    def test_picking_uses_rotated_and_exploded_component_poses(self):
        scene=Scene((Mesh('cpu',box(12,12,5),(.4,.4,.5,1),(-22,22,0),'cpu'),
                     Mesh('gpu',box(25,12,8),(.4,.5,.6,1),(30,-20,0),'gpu')),
                    (100,100,100),{'visual_style':'miniature'})
        renderer=self.fake_renderer('miniature',scene)
        for exploded in (False,True):
            for yaw in (-55,0,55):
                renderer.draw(960,720,yaw=yaw,pitch=15,exploded=exploded,phase=53)
                for mesh in scene.meshes:
                    shift=renderer._shift(mesh,exploded)
                    center=tuple(mesh.position[n]+shift[n] for n in range(3))
                    point=renderer.project_point(center)
                    with self.subTest(exploded=exploded,yaw=yaw,component=mesh.component):
                        self.assertEqual(renderer.pick(*point[:2]),mesh.component)

    def test_selection_changes_existing_pass_only_without_buffer_upload_or_camera_jump(self):
        from assembly_viewer import AssemblyViewport
        renderer=self.fake_renderer('notebook_line')
        renderer.draw(640,480);camera=renderer._pick_inverse
        renderer.draw(640,480,selected='cpu')
        self.assertEqual(renderer.buffer.allocate.call_count,1);self.assertEqual(renderer.upload_count,1)
        self.assertIs(renderer._pick_inverse,camera)
        cpu=next(m for m in renderer.scene.meshes if m.component=='cpu')
        self.assertNotEqual(renderer._highlight_tone(cpu,'cpu'),cpu.color)
        self.assertEqual(renderer._highlight_tone(cpu,'cpu')[3],cpu.color[3])
        widget=SimpleNamespace(_selected='',_focus='all',_yaw=-34.,_pitch=18.,
            componentSelected=Mock(),update=Mock())
        self.assertTrue(AssemblyViewport.select_component(widget,'cpu'))
        self.assertEqual((widget._focus,widget._yaw,widget._pitch),('all',-34.,18.))
        widget.componentSelected.emit.assert_called_once_with('cpu')
        self.assertTrue(AssemblyViewport.select_component(widget,'cpu'));self.assertEqual(widget.update.call_count,1)
        self.assertTrue(AssemblyViewport.select_component(widget,'all'))
        self.assertEqual(widget._selected,'');self.assertFalse(AssemblyViewport.select_component(widget,'invalid'))

    def test_mouse_click_selects_but_drag_only_rotates_without_hover_work(self):
        from PySide6.QtCore import QPointF,Qt
        from assembly_viewer import AssemblyViewport
        class Event:
            def __init__(self,x,y):self.point=QPointF(x,y)
            def position(self):return self.point
            def button(self):return Qt.LeftButton
            def accept(self):pass
        widget=SimpleNamespace(_pointer=None,_press_position=None,_dragging=False,_yaw=-34.,_pitch=18.,
            _renderer=SimpleNamespace(pick=Mock(return_value='gpu')),select_component=Mock(),
            devicePixelRatioF=lambda:1.5,update=Mock())
        AssemblyViewport.mousePressEvent(widget,Event(10,20))
        AssemblyViewport.mouseMoveEvent(widget,Event(12,22))
        AssemblyViewport.mouseReleaseEvent(widget,Event(12,22))
        widget._renderer.pick.assert_called_once_with(18.,33.)
        widget.select_component.assert_called_once_with('gpu');widget.update.assert_not_called()
        AssemblyViewport.mousePressEvent(widget,Event(10,20))
        AssemblyViewport.mouseMoveEvent(widget,Event(25,35))
        AssemblyViewport.mouseReleaseEvent(widget,Event(25,35))
        self.assertNotEqual((widget._yaw,widget._pitch),(-34.,18.))
        self.assertEqual(widget._renderer.pick.call_count,1);self.assertEqual(widget.select_component.call_count,1)


if __name__=='__main__':unittest.main()
