"""Mechanical construction, clear openings and bounded static component detail."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_detail import (TRIANGLE_BUDGETS,bevel_extrude,chamfer_rect,detail_level,
                             hollow_cover,perforated_plate)
from assembly_geometry import build_scene
from assembly_viewer import ray_triangle
from chassis_catalog import CASES
from hardware_appearance import CATALOG,appearance_for
from memory_appearance import CATALOG as MEMORY_CATALOG,appearance_for_memory


def extent(mesh,axis):return max(mesh.vertices[axis::6])-min(mesh.vertices[axis::6])


def hits(mesh,origin,direction):
    for index in range(0,len(mesh.vertices),18):
        points=[tuple(mesh.vertices[index+n+k]+mesh.position[k] for k in range(3)) for n in (0,6,12)]
        if ray_triangle(origin,direction,*points) is not None:return True
    return False


def nearest_gpu_hit(scene,origin,direction):
    found=[]
    for mesh in scene.meshes:
        if mesh.component!='gpu':continue
        for index in range(0,len(mesh.vertices),18):
            points=[tuple(mesh.vertices[index+n+k]+mesh.position[k] for k in range(3)) for n in (0,6,12)]
            distance=ray_triangle(origin,direction,*points)
            if distance is not None:found.append((distance,mesh.name))
    return min(found)[1] if found else None


def fixture(level='balanced',memory=2):
    gpu=appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')
    ram=appearance_for_memory(model='F4-3200C16D-16GTZR')
    return dict(detail_level=level,case=copy.deepcopy(CASES[10]),
        gpu=dict(appearance=gpu),cpu=dict(style='lga_rect',appearance=appearance_for('cpu','Intel Core i7-13700KF')),
        memory=dict(count=memory,modules=[dict(appearance=ram) for _ in range(memory)]),
        board=dict(dimensions_mm=dict(height=305,width=244),detail_profile='asus_z790_a_d4',pcb_color='#242a2d',
            heatsink_color='#c5cbd0',slot_counts=dict(dimm=4,pcie_x16=3,pcie_x1=1,m2=4,sata=4),
            rear_ports=dict(usb_a=8,usb_c=2,hdmi=1,displayport=1,audio_3_5=5,spdif=1,lan=1,buttons=2)))


class AssemblyDetailTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('Geometry cannot query devices or create work')))

    def test_bevels_have_real_slopes_without_changing_exterior_bounds(self):
        vertices=bevel_extrude(chamfer_rect(40,30,2.),4.,.6)
        self.assertEqual(len(vertices)%18,0)
        for axis,size in enumerate((40,30,4)):
            self.assertAlmostEqual(max(vertices[axis::6])-min(vertices[axis::6]),size)
        normals=[vertices[n+3:n+6] for n in range(0,len(vertices),6)]
        self.assertTrue(any(sum(abs(v)>1e-5 for v in normal)>1 for normal in normals))
        self.assertTrue(all(abs(sum(v*v for v in normal)-1)<1e-8 for normal in normals))

    def test_panel_holes_and_hollow_cover_are_open_geometry_not_painted_circles(self):
        from assembly_geometry import Mesh
        plate=Mesh('plate',perforated_plate(chamfer_rect(40,30,1),[(0,0,8)],2),(.5,.5,.5,1))
        self.assertFalse(hits(plate,(0,0,20),(0,0,-1)))
        self.assertTrue(hits(plate,(12,0,20),(0,0,-1)))
        cover=Mesh('cover',hollow_cover(chamfer_rect(40,30,1),[(0,0,8)],15),(.5,.5,.5,1))
        self.assertFalse(hits(cover,(0,0,20),(0,0,-1)))
        self.assertTrue(hits(cover,(12,0,20),(0,0,-1)))
        self.assertAlmostEqual(extent(cover,2),15)

    def test_front_fans_remain_visible_through_body_and_decorative_cover_panels(self):
        value=fixture();value['case']={'dimensions_mm':dict(width=250,height=500,depth=500),'layout':'tower'}
        value['gpu'].update(shell_polygon=[[0,0],[1,0],[1,1],[0,1]],
            detail_polygons=[dict(points=[[0,0],[1,0],[1,1],[0,1]],color='#b0bec8')])
        scene=build_scene(value);openings=[m for m in scene.meshes if m.name=='gpu-fan-opening']
        blockers=[m for m in scene.meshes if m.name in ('gpu-shroud','gpu-cover-panel')]
        self.assertEqual(len(openings),3)
        for fan in openings:
            origin=(fan.position[0],fan.position[1]-100,fan.position[2])
            for panel in blockers:self.assertFalse(hits(panel,origin,(0,1,0)),panel.name)

    def test_astral_rear_fan_is_photo_observed_and_static_with_actual_backplate_opening(self):
        value=fixture();value['case']={'layout':'tower'};scene=build_scene(value)
        meta=scene.metadata['detail']['gpu'];self.assertEqual(meta['observed_rear_fans'],1)
        self.assertEqual(meta['rear_blades'],7);self.assertEqual(meta['rear_rotation_direction'],'unverified')
        self.assertFalse(meta['rear_independent_tachometer']);self.assertTrue(meta['rear_photo_source'].startswith('https://dlcdnwebimgs.asus.com/'))
        rear=[m for m in scene.meshes if m.name.startswith('detail-gpu-rear-observed')]
        self.assertEqual(len(rear),3);self.assertFalse(any(m.rotor for m in rear))
        self.assertEqual(scene.metadata['rotor_count'],3);self.assertEqual(scene.metadata['front_fan_count'],3)
        self.assertEqual(scene.metadata['rear_fan_count'],1);self.assertEqual(scene.metadata['unplaced_fans'],0)
        hub=next(m for m in rear if m.name.endswith('hub'));back=next(m for m in scene.meshes if m.name=='gpu-backplate')
        self.assertFalse(hits(back,(hub.position[0],hub.position[1]+100,hub.position[2]),(0,-1,0)))
        self.assertTrue(meta['pcb_pass_through_cutaway_schematic'])

    def test_observed_astral_side_opening_exposes_real_fins_and_ports_have_recessed_clearance(self):
        value=fixture();value['case']={'layout':'tower'};scene=build_scene(value)
        meta=scene.metadata['detail']['gpu'];self.assertTrue(meta['observed_side_fin_window'])
        self.assertEqual(meta['side_window_geometry'],'official_photo_observed_schematic')
        self.assertTrue(meta['side_window_source'].startswith('https://dlcdnwebimgs.asus.com/'))
        fins=next(m for m in scene.meshes if m.name=='detail-gpu-heatsink-fins')
        # Sample actual individual fin faces at quarter/middle/three-quarter
        # lengths, so empty rays through the gaps cannot falsely pass.
        for index in (8,17,26):
            vertices=fins.vertices[index*216:(index+1)*216]
            center=tuple((min(vertices[k::6])+max(vertices[k::6]))/2+fins.position[k] for k in range(3))
            self.assertEqual(nearest_gpu_hit(scene,(center[0]-200,center[1],center[2]),(1,0,0)),
                             'detail-gpu-heatsink-fins')
        for port in (m for m in scene.meshes if m.name.startswith('gpu-reference-port-')):
            center=port.position
            self.assertEqual(nearest_gpu_hit(scene,(center[0],center[1],center[2]-100),(0,0,1)),
                             'detail-gpu-port-recesses')
        shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
        rear=scene.metadata['canonical_gpu_bracket_mm']
        # The bracket front must not share a second solid cooler-end plane;
        # equal-depth triangles flicker even when their holes are aligned.
        self.assertFalse(any(all(abs(shell.vertices[n+k+2]+shell.position[2]-rear)<1e-8 for k in (0,6,12))
                             for n in range(0,len(shell.vertices),18)))
        # Observing one model does not assert a side opening in other coolers.
        other=fixture();other['gpu']['appearance']=appearance_for('gpu','NVIDIA GeForce RTX 4090')
        self.assertFalse(build_scene(other).metadata['detail']['gpu']['observed_side_fin_window'])

    def test_documented_gpu_ports_cover_all_native_connector_classes_without_invented_unknowns(self):
        types=('displayport','mini_displayport','hdmi','mini_hdmi','dvi','vga','usb_c','tv_out')
        spec={'gpu':dict(length_mm=300,width_mm=150,thickness_mm=70,appearance=dict(style='gpu_neutral',
            board_details=dict(ports=[dict(type=kind,count=1) for kind in types],backplate=False)))}
        scene=build_scene(spec)
        self.assertEqual(scene.metadata['detail']['gpu']['port_types'],types)
        for kind in types:
            self.assertEqual(sum(m.name=='gpu-reference-port-'+kind for m in scene.meshes),1)
            port=next(m for m in scene.meshes if m.name=='gpu-reference-port-'+kind)
            center=port.position
            self.assertEqual(nearest_gpu_hit(scene,(center[0],center[1],center[2]-100),(0,0,1)),
                             'detail-gpu-port-recesses')
        self.assertFalse(any(m.name=='gpu-backplate' for m in scene.meshes))
        unknown=build_scene({'gpu':dict(length_mm=300,width_mm=150,thickness_mm=70,appearance=dict(style='gpu_neutral'))})
        self.assertEqual(unknown.metadata['detail']['gpu']['ports'],0)
        self.assertFalse(any(m.name.startswith('gpu-reference-port-') for m in unknown.meshes))
        self.assertEqual(unknown.metadata['detail']['gpu']['heatsink_fins'],0)

    def test_port_clearance_crosses_chamfered_and_rounded_end_facets_without_opening_far_end(self):
        shapes=(
            [[.03,0],[.97,0],[1,.15],[1,.85],[.97,1],[.03,1],[0,.65],[0,.35]],
            [[.025,0],[.975,0],[1,.12],[1,.88],[.975,1],[.025,1],[.007,.8],[0,.5],[.007,.2]])
        for shape in shapes:
            value=fixture();value['case']={'layout':'tower'};value['gpu']['shell_polygon']=shape
            scene=build_scene(value)
            for port in (m for m in scene.meshes if m.name.startswith('gpu-reference-port-')):
                spans=tuple(extent(port,k) for k in range(3))
                for dx,dy in ((0,0),(-.15,0),(.15,0),(0,-.15),(0,.15)):
                    origin=(port.position[0]+dx*spans[0],port.position[1]+dy*spans[1],port.position[2]-100)
                    self.assertEqual(nearest_gpu_hit(scene,origin,(0,0,1)),'detail-gpu-port-recesses')
            shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
            center=shell.position
            self.assertTrue(hits(shell,(center[0],center[1],center[2]+300),(0,0,-1)))
            self.assertAlmostEqual(extent(shell,2),357.6)

    def test_board_rear_gpu_bracket_and_edge_connector_align_without_shrinking(self):
        spec=fixture();spec['case']={'layout':'tower','dimensions_mm':dict(width=250,height=500,depth=500)}
        scene=build_scene(spec);rear=scene.metadata['canonical_board_rear_mm']
        board=next(m for m in scene.meshes if m.name=='motherboard-reference')
        bracket=next(m for m in scene.meshes if m.name=='gpu-bracket')
        self.assertAlmostEqual(board.position[2]+min(board.vertices[2::6]),rear)
        self.assertAlmostEqual(bracket.position[2]+min(bracket.vertices[2::6]),rear)
        self.assertEqual(rear,-236.)
        slot=next(m for m in scene.meshes if m.name=='board-expansion-slot')
        gold=next(m for m in scene.meshes if m.name=='detail-gpu-separated-edge-contacts')
        self.assertAlmostEqual(slot.position[2]+min(slot.vertices[2::6]),rear+15)
        gold_low=gold.position[2]+min(gold.vertices[2::6]);gold_high=gold.position[2]+max(gold.vertices[2::6])
        self.assertGreater(gold_low,rear+15);self.assertLess(gold_high,rear+15+89)
        pcb=next(m for m in scene.meshes if m.name=='gpu-pcb')
        self.assertAlmostEqual(pcb.position[1],slot.position[1])
        shell=next(m for m in scene.meshes if m.name=='gpu-shroud')
        self.assertAlmostEqual(extent(shell,0),149.3);self.assertAlmostEqual(extent(shell,1),76.)
        self.assertAlmostEqual(extent(shell,2),357.6)

    def test_dimm_stands_perpendicular_to_board_while_sodimm_stays_flat(self):
        dimm=appearance_for_memory(model='F4-3200C16D-16GTZR')
        short=dict(kind='memory',style='sodimm',shroud='bare')
        scene=build_scene({'memory':dict(count=3,modules=[dict(appearance=dimm),dict(appearance=dimm),dict(appearance=short)])})
        pcbs=[m for m in scene.meshes if m.name=='ram-pcb']
        self.assertAlmostEqual(extent(pcbs[0],1),133.35)
        self.assertAlmostEqual(extent(pcbs[0],2),1.2)
        self.assertAlmostEqual(pcbs[0].position[0],pcbs[1].position[0])
        self.assertAlmostEqual(pcbs[1].position[2]-pcbs[0].position[2],10)
        self.assertAlmostEqual(extent(pcbs[2],0),1.2);self.assertAlmostEqual(extent(pcbs[2],2),69.6)

    def test_reviewed_ddr_key_is_a_real_slot_and_contacts_do_not_bridge_it(self):
        ram=appearance_for_memory(model='F4-3200C16D-16GTZR');facts=ram['board_details']
        scene=build_scene({'memory':dict(count=1,modules=[dict(appearance=ram)])})
        pcb=next(m for m in scene.meshes if m.name=='ram-pcb')
        length=extent(pcb,1);height=extent(pcb,0)
        key=(facts['notch_ratio']-.5)*length
        local_y=-height/2+facts['notch_depth_ratio']*height*.45
        point=(pcb.position[0]-local_y,pcb.position[1]+key,pcb.position[2]+20)
        self.assertFalse(hits(pcb,point,(0,0,-1)))
        contacts=next(m for m in scene.meshes if m.name=='detail-ram-separated-contacts')
        self.assertFalse(hits(contacts,point,(0,0,-1)))
        record=scene.metadata['detail']['memory'][0]
        self.assertEqual(record['nominal_pins'],288);self.assertTrue(record['contact_samples_are_not_pin_count'])

    def test_known_asus_profile_uses_sourced_counts_and_finish_without_fake_ssds(self):
        scene=build_scene(fixture());meta=scene.metadata['detail']['board']
        board=next(m for m in scene.meshes if m.name=='motherboard-reference')
        self.assertEqual(board.color,tuple(int('242a2d'[n:n+2],16)/255 for n in (0,2,4))+(1.,))
        self.assertEqual(meta['documented_slot_counts'],dict(dimm=4,pcie_x16=3,pcie_x1=1,m2=4,sata=4))
        self.assertEqual(meta['rendered_memory_sockets'],4)
        self.assertEqual(sum(meta['documented_rear_ports'].values()),21)
        self.assertEqual(sum(m.name=='detail-board-m2-heatsink' for m in scene.meshes),3)
        self.assertEqual(sum(m.name=='detail-board-sata-socket' for m in scene.meshes),4)
        self.assertFalse(meta['installed_ssd_count_inferred']);self.assertTrue(meta['rear_io_layout_schematic'])
        unknown=build_scene({'board':{'label':'ROG STRIX Z790-A GAMING WIFI D4'}})
        self.assertEqual(unknown.metadata['detail']['board']['documented_slot_counts'],{})
        self.assertFalse(any(m.name.startswith('detail-board-rear-usb') for m in unknown.meshes))

    def test_modes_are_bounded_and_do_not_modify_source_or_create_installed_cooling(self):
        for bad in (None,False,{},'unsupported'):self.assertEqual(detail_level(bad),'balanced')
        for level in ('eco','balanced','close'):
            spec=fixture(level,8);before=copy.deepcopy(spec);scene=build_scene(spec)
            self.assertEqual(spec,before);self.assertEqual(scene.metadata['detail_level'],level)
            self.assertLessEqual(scene.triangle_count,TRIANGLE_BUDGETS[level])
            self.assertEqual(scene.metadata['optional_detail_meshes_removed'],0)
            self.assertEqual(scene.metadata['installed_case_fans_assumed'],0)
            self.assertFalse(any(m.name in ('installed-psu','installed-case-fan','installed-cpu-cooler') for m in scene.meshes))
        eco=build_scene(fixture('eco'))
        self.assertFalse(any(m.name.startswith('detail-gpu-') for m in eco.meshes))

    def test_all_28_memory_models_keep_form_key_and_reference_count_without_filling_missing_slots(self):
        self.assertEqual(len(MEMORY_CATALOG),28)
        for model in MEMORY_CATALOG:
            appearance=appearance_for_memory(model=model['aliases'][0]);short=appearance['style']=='sodimm'
            scene=build_scene({'memory':dict(count=2,modules=[dict(appearance=appearance)]*2)})
            pcbs=[m for m in scene.meshes if m.name=='ram-pcb']
            with self.subTest(model=model['id']):
                self.assertEqual(len(pcbs),2)
                self.assertAlmostEqual(extent(pcbs[0],2 if short else 1),69.6 if short else 133.35)
                self.assertEqual(scene.metadata['detail']['memory'][0]['key_ratio'],appearance['board_details'].get('notch_ratio'))
        over=build_scene(fixture('balanced',8)).metadata['detail']['board']
        self.assertEqual(over['rendered_memory_sockets'],4)
        self.assertEqual(over['documented_slot_counts']['dimm'],4)
        self.assertTrue(over['memory_population_exceeds_documented_slots'])

    def test_all_147_gpu_models_preserve_finite_geometry_and_balanced_budget(self):
        rows=[row for row in CATALOG if row[1]=='gpu'];self.assertEqual(len(rows),147)
        for row in rows:
            with self.subTest(model=row[0]):
                appearance=appearance_for('gpu',row[-1][0]);scene=build_scene({'gpu':dict(appearance=appearance)})
                self.assertLessEqual(scene.triangle_count,40000)
                self.assertTrue(all(math.isfinite(value) for m in scene.meshes for value in m.vertices))
                self.assertEqual(scene.metadata['physical_total_fans'],appearance.get('fan_count'))

    def test_all_64_cases_keep_dimensions_and_close_budget(self):
        spec=fixture('close',4)
        for case in CASES:
            spec['case']=case
            with self.subTest(case=case['id']):
                scene=build_scene(spec)
                self.assertEqual(scene.dimensions,tuple(case['dimensions_mm'][k] for k in ('width','height','depth')))
                self.assertLessEqual(scene.triangle_count,80000)
                self.assertEqual(scene.metadata['rotor_count'],3)

    def test_vertical_top_io_rotates_all_components_axes_and_rear_reference_toward_top(self):
        base=fixture();base['case']={'layout':'tower','dimensions_mm':dict(width=300,height=550,depth=300)}
        upright=build_scene(base)
        vertical=copy.deepcopy(base);vertical['case']['layout']='vertical';vertical['case']['features']=['top_io']
        turned=build_scene(vertical)
        for original,rotated in zip((m for m in upright.meshes if m.component in ('cpu','gpu','memory','board')),
                                    (m for m in turned.meshes if m.component in ('cpu','gpu','memory','board'))):
            self.assertEqual(original.name,rotated.name)
            x,y,z=original.position;self.assertEqual(rotated.position,(x,-z,y))
            ax,ay,az=original.axis;self.assertEqual(rotated.axis,(ax,-az,ay))
        shield=next(m for m in turned.meshes if m.name=='detail-board-rear-io-shield')
        self.assertGreater(shield.position[1],0)
        front=next(m for m in turned.meshes if m.rotor)
        self.assertEqual(front.axis,(0,0,1))


if __name__=='__main__':unittest.main()
