"""Physical proportions, guarded fan meshes and static buffer contracts; no GL."""
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from assembly_geometry import (AM5_LID, blade_polygon, box, build_scene, extrude,
                               fan_rotor, known_fan_profiles, ring, vertex_bytes)
from hardware_appearance import CATALOG, appearance_for


def extent(mesh,axis):
    values=mesh.vertices[axis::6]
    return max(values)-min(values)


class AssemblyGeometryTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('Geometry cannot access devices or workers')))

    def assert_mesh(self,vertices):
        self.assertTrue(vertices)
        self.assertEqual(len(vertices)%18,0)
        self.assertTrue(all(math.isfinite(v) for v in vertices))
        for index in range(0,len(vertices),6):
            self.assertAlmostEqual(sum(v*v for v in vertices[index+3:index+6]),1,places=6)

    def test_primitive_buffers_have_real_depth_unit_normals_and_triangle_winding(self):
        for vertices in (box(5,8,2),ring(10,7,2),extrude(AM5_LID,2.4)):
            self.assert_mesh(vertices)
            self.assertGreater(max(vertices[2::6])-min(vertices[2::6]),1)
            for index in range(0,len(vertices),18):
                a,b,c=[vertices[index+k:index+k+3] for k in (0,6,12)]
                ab=[b[k]-a[k] for k in range(3)];ac=[c[k]-a[k] for k in range(3)]
                normal=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                self.assertGreater(sum(normal[k]*vertices[index+3+k] for k in range(3)),0)

    def test_am5_concave_caps_leave_eight_real_edge_cutouts(self):
        vertices=extrude(AM5_LID,2)
        caps=[vertices[i:i+18] for i in range(0,len(vertices),18) if vertices[i+5]>.99]
        def inside(p,a,b,c):
            def cr(x,y,z):return (y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])
            values=(cr(a,b,p),cr(b,c,p),cr(c,a,p))
            return min(values)>=-1e-8
        for point in ((-11,-18),(11,-18),(18,-11),(18,11),(11,18),(-11,18),(-18,11),(-18,-11)):
            self.assertFalse(any(inside(point,row[0:2],row[6:8],row[12:14]) for row in caps))
        self.assertTrue(any(inside((0,0),row[0:2],row[6:8],row[12:14]) for row in caps))

    def test_unknown_blades_do_not_gain_invented_rotating_vanes(self):
        for profile in ({},{'blades':None,'shape':'neutral'},{'blades':True,'shape':'wide'},
                        {'blades':None,'blade_polygons':[[[0,0],[1,0],[0,1]]]}):
            self.assertEqual(fan_rotor(profile,40),())
        value=appearance_for('gpu','APBF-IA770-16G-OC')
        scene=build_scene({'gpu':{'appearance':value}})
        self.assertEqual(scene.metadata['front_fan_count'],2)
        self.assertEqual(scene.metadata['rotor_count'],0)
        self.assertEqual(sum(mesh.name=='gpu-fan-hub' for mesh in scene.meshes),2)

    def test_existing_gpu_catalog_all_models_produce_bounded_finite_geometry(self):
        records=[row for row in CATALOG if row[1]=='gpu']
        self.assertEqual(len(records),147)
        for row in records:
            value=appearance_for('gpu',row[-1][0])
            with self.subTest(model=row[0]):
                scene=build_scene({'gpu':{'appearance':value}})
                self.assertEqual(scene.metadata['gpu_model'],value['id'])
                self.assertLess(scene.triangle_count,30000)
                self.assertTrue(all(math.isfinite(v) and abs(v)<=1000 for mesh in scene.meshes for v in mesh.vertices))
                self.assertEqual(scene.metadata['front_fan_count'],len(known_fan_profiles(value)))
                self.assertEqual(len(vertex_bytes(scene)),sum(len(mesh.vertices) for mesh in scene.meshes)*4)

    def test_supplied_exact_blades_keep_full_ring_and_grouped_tip_links(self):
        leaf=[[-.2,-.6],[-.9,-2.1],[.1,-2.5],[.7,-.8]]
        profile={'blades':3,'shape':'swept','blade_polygons':[leaf,leaf,leaf]}
        base=fan_rotor(profile,30)
        self.assertGreater(len(fan_rotor(dict(profile,outer_ring=True),30)),len(base))
        self.assertGreater(len(fan_rotor(dict(profile,group_size=3),30)),len(base))
        self.assert_mesh(base)

    def test_actual_board_and_gpu_dimensions_never_shrink_to_fit_a_small_case(self):
        scene=build_scene({'case':{'dimensions_mm':{'width':150,'height':220,'depth':210},'layout':'compact'},
                           'board':{'dimensions_mm':{'height':305,'width':244},'schematic':False},
                           'gpu':{'length_mm':357.6,'width_mm':149.3,'thickness_mm':76}})
        board=next(m for m in scene.meshes if m.name=='motherboard-reference')
        gpu=next(m for m in scene.meshes if m.name=='gpu-shroud')
        self.assertAlmostEqual(extent(board,1),305)
        self.assertAlmostEqual(extent(board,2),244)
        self.assertAlmostEqual(extent(gpu,2),357.6)
        self.assertAlmostEqual(extent(gpu,0),149.3)
        self.assertAlmostEqual(extent(gpu,1),76)
        self.assertFalse(scene.metadata['board_is_reference'])
        self.assertFalse(scene.metadata['cad_or_fit_guarantee'])

    def test_case_mount_support_does_not_invent_installed_case_fans(self):
        scene=build_scene({'case':{'fan_mounts':[{'position':'front','count':3,'size_mm':140}],
                                        'dimensions_mm':{'width':230,'height':470,'depth':460},'dimensions_verified':False}})
        self.assertEqual(scene.metadata['installed_case_fans_assumed'],0)
        self.assertFalse(scene.metadata['dimensions_verified'])
        self.assertFalse(any(m.rotor for m in scene.meshes))
        self.assertFalse(any(m.component=='gpu' for m in scene.meshes))

    def test_integrated_gpu_has_no_fabricated_discrete_card(self):
        for gpu in ({'appearance':{'style':'gpu_integrated'}},{'present':False}):
            scene=build_scene({'gpu':gpu})
            self.assertFalse(any(m.component=='gpu' for m in scene.meshes))

    def test_memory_population_short_form_and_bare_modules_are_preserved(self):
        scene=build_scene({'memory':{'count':2,'style':'sodimm','heat_spreader':False}})
        sticks=[m for m in scene.meshes if m.name=='ram-pcb']
        self.assertEqual(len(sticks),2)
        self.assertAlmostEqual(extent(sticks[0],2),69.6)
        self.assertFalse(any(m.name in ('ram-spreader','ram-diffuser') for m in scene.meshes))
        self.assertEqual(build_scene({'memory':{'count':True}}).metadata['memory_count'],0)
        self.assertEqual(build_scene({'memory':{'count':999}}).metadata['memory_count'],0)

    def test_exact_polygons_and_fan_centers_are_not_replaced_by_generic_boxes(self):
        outline=[[0,.2],[.1,0],[.9,0],[1,.25],[.95,1],[0,1]]
        scene=build_scene({'gpu':{'shell_polygon':outline,'length_mm':300,'width_mm':120,'thickness_mm':40,
            'fans':[{'center_uv':[.23,.48],'radius_mm':35,'blade_count':7,'shape':'wide','direction':-1},
                    {'center_uv':[.77,.52],'radius_mm':40,'blade_count':None}]}})
        shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
        self.assertNotEqual(shell.vertices,box(120,40,300))
        rotors=[m for m in scene.meshes if m.rotor]
        self.assertEqual(len(rotors),1);self.assertEqual(rotors[0].direction,-1)
        hubs=[m for m in scene.meshes if m.name=='gpu-fan-hub']
        self.assertAlmostEqual(hubs[1].position[2]-hubs[0].position[2],.54*300)

    def test_physical_total_is_distinct_from_reviewed_visible_front_layout(self):
        value=appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')
        scene=build_scene({'gpu':{'appearance':value}})
        self.assertEqual(scene.metadata['physical_total_fans'],4)
        self.assertEqual(scene.metadata['front_fan_count'],3)
        self.assertEqual(scene.metadata['unplaced_fans'],0)
        self.assertEqual(scene.metadata['rear_fan_count'],1)
        self.assertEqual(scene.metadata['rotor_count'],3)
        self.assertEqual(scene.metadata['detail']['gpu']['rear_rotation_direction'],'unverified')
        self.assertEqual(build_scene({'gpu':{'appearance':value},'detail_level':'eco'}).metadata['unplaced_fans'],0)

    def test_same_input_rebuilds_same_buffers_without_render_or_polling_state(self):
        spec={'cpu':{'style':'am5'},'memory':{'count':2}}
        first,second=build_scene(spec),build_scene(spec)
        self.assertEqual(first,second)
        self.assertEqual(vertex_bytes(first),vertex_bytes(second))

    def test_viewport_shared_clock_math_stops_when_cached_rpm_expires(self):
        from assembly_viewer import AssemblyViewport
        from unittest.mock import Mock
        widget=SimpleNamespace(_fan_available=True,_fan_expiry=103.,_active=True,_rpm=1200.,_phase=0.,update=Mock())
        widget._update_animation_state=lambda:setattr(widget,'_active',widget._fan_available)
        with patch('assembly_viewer.time.monotonic',return_value=100.):
            self.assertTrue(AssemblyViewport.advance_fans(widget,100))
            self.assertAlmostEqual(widget._phase,6.)
            widget._rpm=2400.
            self.assertTrue(AssemblyViewport.advance_fans(widget,100))
            self.assertAlmostEqual(widget._phase,18.)
        with patch('assembly_viewer.time.monotonic',return_value=104.):
            self.assertFalse(AssemblyViewport.advance_fans(widget,100))
            self.assertAlmostEqual(widget._phase,18.)
            self.assertFalse(widget._fan_available)

    def test_viewport_rejects_non_numeric_boolean_future_and_stale_rpm_inputs(self):
        from assembly_viewer import AssemblyViewport
        from unittest.mock import Mock
        widget=SimpleNamespace(_update_animation_state=Mock())
        with patch('assembly_viewer.time.time',return_value=100.),patch('assembly_viewer.time.monotonic',return_value=50.):
            for rpm,stamp in ((True,100),(-1,100),('1200',100),(float('nan'),100),(1200,104),(1200,96)):
                AssemblyViewport.set_fan_state(widget,rpm,True,stamp)
                self.assertFalse(widget._fan_available)
            AssemblyViewport.set_fan_state(widget,0,True,100)
            self.assertTrue(widget._fan_available);self.assertEqual(widget._rpm,0)
            AssemblyViewport.set_fan_state(widget,1440,True,99)
            self.assertTrue(widget._fan_available);self.assertEqual(widget._fan_expiry,52.)

    def test_individual_memory_modules_retain_their_own_cover_and_color(self):
        scene=build_scene({'memory':{'count':2,'appearance':{'id':'first','shroud':'rgb'},'modules':[
            {'appearance':{'id':'first','style':'dimm','shroud':'rgb'},'colors':{'body':'#ffffff'},'diffuser':True},
            {'appearance':{'id':'second','style':'sodimm','shroud':'bare'},'colors':{'pcb':'#aa0000'}}]}})
        self.assertEqual(scene.metadata['memory_models'],['first','second'])
        self.assertEqual(sum(m.name=='ram-spreader' for m in scene.meshes),1)
        self.assertEqual(sum(m.name=='ram-diffuser' for m in scene.meshes),1)
        pcbs=[m for m in scene.meshes if m.name=='ram-pcb']
        self.assertAlmostEqual(extent(pcbs[0],1),133.35)
        self.assertAlmostEqual(extent(pcbs[1],2),69.6)
        self.assertNotEqual(pcbs[0].color,pcbs[1].color)

    def test_exact_gpu_colors_and_cover_panels_survive_into_the_mesh(self):
        spec={'gpu':{'colors':{'body':'#ffffff','metal':'#aa6633','pcb':'#112233'},
                     'detail_polygons':[[[.1,.1],[.4,.1],[.4,.2],[.1,.2]]]}}
        scene=build_scene(spec)
        self.assertEqual(next(m for m in scene.meshes if m.name=='gpu-shroud').color,(1,1,1,1))
        self.assertEqual(sum(m.name=='gpu-cover-panel' for m in scene.meshes),1)
        self.assertEqual(next(m for m in scene.meshes if m.name=='gpu-cover-panel').color,(170/255,102/255,51/255,1))

    def test_only_allowlisted_cpu_model_marks_enter_geometry(self):
        for identity,style in (('intel-13700kf','lga_rect'),('amd-9950x','am5'),('amd-7800x3d','am5')):
            scene=build_scene({'cpu':{'appearance':{'id':identity},'style':style}})
            self.assertEqual(scene.metadata['cpu_model_mark'],identity)
            self.assertEqual(sum(m.name=='cpu-model-mark' for m in scene.meshes),2)
        self.assertFalse(any(m.name=='cpu-model-mark' for m in build_scene({'cpu':{'model_id':'arbitrary text'}}).meshes))

    def test_actual_widget_paint_forwards_focus_without_reuploading_meshes(self):
        from assembly_viewer import AssemblyViewport
        from unittest.mock import Mock
        renderer=Mock()
        widget=SimpleNamespace(_error='',_pending=False,_renderer=renderer,_scene=build_scene({}),
            _yaw=-80.,_pitch=12.,_zoom=.9,_exploded=True,_phase=35.,_dark=True,_focus='cpu',
            devicePixelRatioF=lambda:1.5,width=lambda:800,height=lambda:600)
        AssemblyViewport.paintGL(widget)
        renderer.upload.assert_not_called()
        renderer.draw.assert_called_once_with(1200,900,pixel_scale=1.5,yaw=-80.,pitch=12.,zoom=.9,
            exploded=True,phase=35.,dark=True,focus='cpu')

    def test_all_80_cases_keep_source_dimensions_and_no_installed_fan_guess(self):
        from chassis_catalog import CASES
        self.assertEqual(len(CASES),80)
        for case in CASES:
            scene=build_scene({'case':case})
            self.assertEqual(scene.dimensions,tuple(case['dimensions_mm'][key] for key in ('width','height','depth')))
            self.assertEqual(scene.metadata['installed_case_fans_assumed'],0)
            self.assertTrue(all(math.isfinite(v) for mesh in scene.meshes for v in mesh.vertices))

    def test_memory_physical_population_can_exceed_the_eight_mesh_display_limit(self):
        scene=build_scene({'memory':{'count':16,'rendered_count':8}})
        self.assertEqual(scene.metadata['memory_count'],16)
        self.assertEqual(scene.metadata['memory_rendered_count'],8)
        self.assertEqual(sum(m.name=='ram-pcb' for m in scene.meshes),8)

    def test_open_frame_does_not_gain_enclosing_walls_or_top_vents(self):
        scene=build_scene({'case':{'layout':'open_frame','panels':{'left':'open','front':'open'}}})
        names={mesh.name for mesh in scene.meshes}
        self.assertIn('open-frame-tray',names)
        self.assertTrue(names.isdisjoint(('case-back','case-right','front-panel','left-panel','top-vent','psu-shroud')))

    def test_glass_roof_and_pillarless_construction_keep_their_open_corner(self):
        scene=build_scene({'case':{'panels':{'top':'glass'},'features':['pillarless_glass_corner']}})
        self.assertEqual(sum(m.name=='case-upright' for m in scene.meshes),3)
        self.assertTrue(any(m.name=='top-glass' and m.color[3]<1 for m in scene.meshes))
        self.assertFalse(any(m.name=='top-vent' for m in scene.meshes))

    def test_slim_case_and_upper_power_shroud_keep_physical_construction(self):
        scene=build_scene({'case':{'dimensions_mm':{'width':84,'height':244,'depth':217},'layout':'compact'}})
        self.assertEqual(scene.dimensions,(84,244,217))
        top=build_scene({'case':{'features':['top_psu_shroud']}})
        self.assertFalse(any(m.name=='psu-shroud' for m in top.meshes))
        self.assertGreater(next(m.position[1] for m in top.meshes if m.name=='top-psu-shroud'),0)


if __name__=='__main__':unittest.main()
