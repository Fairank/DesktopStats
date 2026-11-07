"""Source-qualified layout/clearance contracts, never hardware queries."""
import copy
import math
import unittest
from collections import Counter
from unittest.mock import patch

from assembly_geometry import Mesh,box,build_scene
from assembly_detail import TRIANGLE_BUDGETS
from assembly_motherboard import layout_anchors,attachment_bounds
from assembly_viewer import ray_triangle
from hardware_appearance import appearance_for
from memory_appearance import appearance_for_memory
from motherboard_catalog import MODELS,get_model,identify,resolve,choices


def hits(mesh,origin,direction):
    for n in range(0,len(mesh.vertices),18):
        points=[tuple(mesh.vertices[n+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)]
        if ray_triangle(origin,direction,*points) is not None:return True
    return False


def spec_for(identity='asus-rog-strix-z790-a-wifi-d4',count=2):
    return dict(case=dict(layout='tower',dimensions_mm=dict(width=250,height=500,depth=500)),
        board=dict(model_id=identity),cpu=dict(style='lga_rect',appearance=appearance_for('cpu','Intel Core i7-13700KF')),
        memory=dict(count=count,modules=[dict(appearance=appearance_for_memory(model='F4-3200C16D-16GTZR')) for _ in range(count)]))


class AssemblyMotherboardTests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(target,side_effect=AssertionError('Pure motherboard geometry must not query or launch work')))

    def test_sixteen_real_models_cover_vendor_platform_and_form_with_source_counted_rear_layouts(self):
        self.assertEqual(len(MODELS),16);self.assertEqual(len({row['id'] for row in MODELS}),16)
        self.assertTrue({(socket,form) for socket in ('LGA1700','AM5') for form in ('atx','matx','itx')}.issubset(
            {(row['socket'],row['form_factor']) for row in MODELS}))
        self.assertEqual({row['brand'] for row in MODELS},{'ASUS','MSI','ASRock','GIGABYTE'})
        sizes={'gigabyte-z790-aorus-master':(305.,260.),'asrock-x670e-taichi':(305.,267.),
            'msi-mag-x670e-tomahawk-wifi':(304.8,243.84),'msi-pro-b760m-a-wifi':(243.84,243.84),'msi-meg-x670e-godlike':(304.8,288.)}
        for row in MODELS:
            self.assertEqual(Counter(r['kind'] for r in row['rear_layout']),row['rear_ports'])
            self.assertTrue(row['manual'].startswith(('https://download','https://dlcdnets')))
            self.assertTrue(all(u.startswith('https://') for u in row['sources']))
            expected=sizes.get(row['id'],(305.,244.) if row['form_factor']=='atx' else (244.,244.) if row['form_factor']=='matx' else (170.,170.))
            self.assertEqual(tuple(row['dimensions_mm'][k] for k in ('height','width')),expected)
            self.assertFalse(row['cad_verified']);self.assertFalse(row['pcb_routing_verified'])
            self.assertTrue(row['series']);self.assertEqual(row['market_coverage'],'named_model_only')

    def test_identity_requires_exact_product_and_known_manufacturer_and_returns_detached_data(self):
        known=identify('ASUSTeK COMPUTER INC.','ROG STRIX Z790-A GAMING WIFI D4')
        self.assertEqual(known['state'],'detected');self.assertEqual(known['model']['id'],'asus-rog-strix-z790-a-wifi-d4')
        for maker,name in (('Unknown','ROG STRIX Z790-A GAMING WIFI D4'),('ASUS','ROG STRIX Z790-A'),('ASUS','ROG STRIX Z790-A GAMING WIFI')):
            self.assertIsNone(identify(maker,name)['model'])
        self.assertEqual(identify('Unknown','Unknown','asrock-z790-pg-itx-tb4')['state'],'manual')
        self.assertIsNone(identify('ASUS','ROG STRIX Z790-A GAMING WIFI D4','unknown')['model'])
        known['model']['dimensions_mm']['height']=1
        self.assertEqual(get_model('asus-rog-strix-z790-a-wifi-d4')['dimensions_mm']['height'],305.)
        self.assertEqual(len(choices()),16)
        self.assertIsNone(resolve({'label':'ROG STRIX Z790-A GAMING WIFI D4'}))

    def test_asus_socket_dimm_and_primary_pcie_landmarks_match_official_manual_regions(self):
        value=spec_for();a=layout_anchors(value,250,500,500,90,10,-236)
        self.assertTrue(130<a['cpu']['z']-a['board']['rear_z']<138)
        self.assertTrue(63<a['cpu']['y']-10<70)
        self.assertTrue(40<a['primary_pcie_start_z']+236<44)
        self.assertTrue(-33<a['primary_pcie_y']-10<-27)
        self.assertEqual(len(a['dimm_centers']),4)
        self.assertTrue(all(185<p[2]+236<220 for p in a['dimm_centers']))
        self.assertEqual(a['cpu']['normal'],(-1.,0.,0.))

    def test_two_modules_use_actual_a2_b2_slots_and_eight_do_not_invent_eight_documented_slots(self):
        scene=build_scene(spec_for());a=scene.metadata['attachment_anchors'];modules=[m for m in scene.meshes if m.name=='ram-pcb']
        for module,index in zip(modules,(1,3)):
            self.assertEqual(module.position[1:],a['dimm_centers'][index][1:])
        self.assertEqual(modules[0].position[0],modules[1].position[0])
        over=build_scene(spec_for(count=8));self.assertEqual(sum(m.name=='ram-pcb' for m in over.meshes),8)
        self.assertEqual(over.metadata['motherboard']['rendered_memory_sockets'],4)
        self.assertTrue(over.metadata['motherboard']['memory_population_exceeds_documented_slots'])

    def test_asus_nine_source_located_mounts_are_open_in_pcb_and_overlying_m2_cover(self):
        scene=build_scene(spec_for(count=0));a=scene.metadata['attachment_anchors'];model=get_model('asus-rog-strix-z790-a-wifi-d4')
        self.assertEqual(len(model['mount_uv']),9);self.assertIn('official',scene.metadata['motherboard']['mount_method'])
        pcb=next(m for m in scene.meshes if m.name=='motherboard-reference');bx,by,bz=a['board']['position']
        for u,v in model['mount_uv']:
            origin=(bx-100,by+(.5-v)*305,a['board']['rear_z']+u*244)
            self.assertFalse(hits(pcb,origin,(1,0,0)))
        u,v=.676,.538;origin=(bx-100,by+(.5-v)*305,a['board']['rear_z']+u*244)
        for mesh in scene.meshes:
            if mesh.name in ('detail-board-m2-heatsink','board-heatsink-recessed-crown'):
                self.assertFalse(hits(mesh,origin,(1,0,0)))

    def test_all_profiles_and_levels_keep_nominal_pcb_dimensions_unit_normals_and_unique_layouts(self):
        signatures=[]
        for model in MODELS:
            for level in ('eco','balanced','close'):
                value=spec_for(model['id']);value['detail_level']=level;scene=build_scene(value)
                pcb=next(m for m in scene.meshes if m.name=='motherboard-reference')
                self.assertAlmostEqual(max(pcb.vertices[1::6])-min(pcb.vertices[1::6]),model['dimensions_mm']['height'])
                self.assertAlmostEqual(max(pcb.vertices[2::6])-min(pcb.vertices[2::6]),model['dimensions_mm']['width'])
                self.assertLessEqual(scene.triangle_count,TRIANGLE_BUDGETS[level])
                for mesh in scene.meshes:
                    self.assertTrue(all(math.isfinite(v) for v in mesh.vertices))
                    self.assertTrue(all(abs(sum(v*v for v in mesh.vertices[n+3:n+6])-1)<1e-6 for n in range(0,len(mesh.vertices),6)))
                self.assertFalse(any('expression' in m.name for m in scene.meshes))
            signatures.append((model['cpu_uv'],model['dimm_uv'],tuple((r['kind'],r['uv']) for r in model['pcie']),
                tuple(c['polygon'] for c in model['heatsinks'])))
        self.assertEqual(len(set(signatures)),16)

    def test_product_specific_headers_native_storage_and_unknown_finish_are_honest(self):
        hero=build_scene(spec_for('asus-rog-maximus-z790-hero'))
        self.assertEqual(hero.metadata['motherboard']['documented_slot_counts']['m2'],3)
        self.assertEqual(hero.metadata['motherboard']['bundled_m2_accessory_slots'],2)
        self.assertFalse(hero.metadata['motherboard']['bundled_m2_accessory_installed'])
        prime=build_scene(spec_for('asus-prime-b650m-a-wifi-ii'))
        self.assertEqual(prime.metadata['motherboard']['m2_heatsinks'],0)
        self.assertFalse(any(m.name=='board-io-clear-inset' for m in prime.meshes))
        self.assertEqual(len(prime.metadata['attachment_anchors']['connectors']['eps4']),1)
        self.assertTrue(any(m.name=='board-eps4-housing' for m in prime.meshes))
        self.assertTrue(any(m.name=='detail-board-rear-ps2' for m in prime.meshes))
        self.assertTrue(any(m.name=='detail-board-rear-vga' for m in prime.meshes))
        for mesh in prime.meshes:
            if mesh.name=='board-header-usb_c':self.assertLess(max(mesh.vertices[2::6])-min(mesh.vertices[2::6]),10.)
        pro=build_scene(spec_for('msi-pro-b760m-a-wifi'))
        self.assertFalse(any(m.name=='board-cmos-battery' for m in pro.meshes))
        gig=build_scene(spec_for('gigabyte-z790-aorus-master'))
        self.assertEqual(gig.metadata['motherboard']['finish_status'],'pending_primary_photo')
        self.assertFalse(any('heatsink' in m.name for m in gig.meshes if m.component=='board'))
        self.assertEqual(get_model('asrock-x670e-taichi')['dimensions_mm']['width'],267.)
        self.assertEqual(build_scene(spec_for('asrock-b650e-steel-legend-wifi')).metadata['motherboard']['documented_slot_counts']['sata'],2)

    def test_original_physical_parts_have_stable_independent_ids_through_pose_and_styles(self):
        for layout in ('tower','vertical','horizontal'):
            value=spec_for();value['case']['layout']=layout
            value['part_styles']={'memory:0':'notebook_line','memory:1':'cartoon','cpu:0':'outline'}
            scene=build_scene(value);parts=scene.metadata['hardware']['parts']
            self.assertEqual({p['id'] for p in parts},{'cpu:0','board:0','memory:0','memory:1'})
            self.assertEqual([m.part_id for m in scene.meshes if m.name=='ram-pcb'],['memory:0','memory:1'])
            for m in scene.meshes:
                if m.component in ('memory','cpu','board'):self.assertTrue(m.part_id.startswith(m.component+':'))

    def test_y70_rigid_factory_riser_pose_keeps_full_card_and_real_side_mount_aperture(self):
        from chassis_catalog import get_case
        value=spec_for();value['case']=get_case('hyte-y70')
        value['gpu']={'appearance':appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')}
        scene=build_scene(value);gpu=scene.metadata['attachment_anchors']['gpu'];observation=scene.metadata['gpu_mount_observation']
        self.assertEqual(gpu['size'],(149.3,76.,357.6));self.assertEqual(gpu['normal'],(-1.,0.,0.))
        self.assertAlmostEqual(gpu['pcb']['center'][0],-51.2)
        pads=next(m for m in scene.meshes if m.name=='detail-gpu-separated-edge-contacts')
        ys=[pads.position[1]+v for v in pads.vertices[1::6]]
        self.assertAlmostEqual((min(ys)+max(ys))/2,-160.)
        self.assertFalse(observation['cad_verified']);self.assertIn('photo_observed',observation['method'])
        tray=next(m for m in scene.meshes if m.name=='rear-chamber-divider')
        for y in (-160.,0.,160.):
            self.assertFalse(hits(tray,(-180.,y,108.1),(1.,0.,0.)))
        self.assertTrue(hits(tray,(-180.,0.,-205.),(1.,0.,0.)))
        self.assertEqual(scene.metadata['attachment_notices'],scene.metadata['attachments_outside_reference'])
        self.assertEqual(scene.metadata['installed_case_fans_assumed'],0)
        self.assertTrue(any(m.name=='case-cold-floor-deck' for m in scene.meshes))
        self.assertGreater(gpu['bounds']['min'][1],-190.)

    def test_all_named_socket_beds_are_reachable_through_retention_opening(self):
        for model in MODELS:
            scene=build_scene(spec_for(model['id'],0));cp=scene.metadata['attachment_anchors']['cpu']['position']
            bed=next(m for m in scene.meshes if m.name=='board-socket-spring-heads')
            samples=[]
            for n in range(0,len(bed.vertices),18):
                triangle=[tuple(bed.vertices[n+j+k]+bed.position[k] for k in range(3)) for j in (0,6,12)]
                center=tuple(sum(p[k] for p in triangle)/3 for k in range(3));samples.append((sum((center[k]-cp[k])**2 for k in (1,2)),center))
            center=min(samples)[1];origin=(center[0]-100.,center[1],center[2]);nearest=[]
            for mesh in scene.meshes:
                if mesh.component!='board':continue
                for n in range(0,len(mesh.vertices),18):
                    points=[tuple(mesh.vertices[n+j+k]+mesh.position[k] for k in range(3)) for j in (0,6,12)]
                    distance=ray_triangle(origin,(1,0,0),*points)
                    if distance is not None:nearest.append((distance,mesh.name))
            self.assertTrue(nearest,model['id']);self.assertEqual(min(nearest)[1],'board-socket-spring-heads',model['id'])

    def test_shared_source_mount_anchor_and_transient_gpu_clearance_do_not_escape_metadata(self):
        import json
        from chassis_catalog import get_case
        captured=[]
        def auxiliary(spec,anchors,level):
            captured.append(anchors['_gpu_clearance_meshes'])
            for actual,expected in zip(anchors['case_mount_planes']['side']['position'],(108.8,0.,108.1)):self.assertAlmostEqual(actual,expected)
            self.assertFalse(anchors['case_mount_planes']['side']['dimensions_verified'])
            return (),{}
        value=spec_for();value['case']=get_case('hyte-y70')
        value['gpu']={'appearance':appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')}
        with patch('assembly_auxiliary.add_auxiliary',side_effect=auxiliary):scene=build_scene(value)
        self.assertTrue(captured[0]);self.assertTrue(all(isinstance(m,Mesh) and m.component=='gpu' for m in captured[0]))
        self.assertNotIn('_gpu_clearance_meshes',scene.metadata['attachment_anchors'])
        json.dumps(scene.metadata)

    def test_known_case_connectors_remain_rendered_at_eco_for_real_cable_endpoints(self):
        from chassis_catalog import get_case
        value=spec_for();value['case']=get_case('hyte-y70');value['detail_level']='eco'
        scene=build_scene(value);rows=scene.metadata['attachment_anchors']['case_front_io']
        self.assertEqual(len(rows),5)
        self.assertEqual(sum(row['kind']=='usb_a' for row in rows),2)
        for row in rows:self.assertTrue(any(m.name.startswith('case-io-'+row['kind']+'-') for m in scene.meshes))

    def test_vertical_and_horizontal_attachment_axes_match_drawn_cpu_and_board_poses(self):
        upright=build_scene(spec_for());base=upright.metadata['attachment_anchors']
        for layout,pose in (('vertical',lambda p:(p[0],-p[2],p[1])),('horizontal',lambda p:(p[1],-p[0],p[2]))):
            value=spec_for();value['case']['layout']=layout;scene=build_scene(value);a=scene.metadata['attachment_anchors']
            self.assertEqual(a['cpu']['position'],pose(base['cpu']['position']))
            self.assertEqual(a['cpu']['normal'],pose(base['cpu']['normal']))
            self.assertEqual(a['cpu']['up'],pose(base['cpu']['up']))
            self.assertEqual(a['connectors']['atx24'][0]['position'],pose(base['connectors']['atx24'][0]['position']))
            lid=next(m for m in scene.meshes if m.name=='cpu-lid');self.assertEqual(lid.position,a['cpu']['position'])

    def test_socket_and_ddr_mismatch_are_explicit_and_unknown_cpu_is_not_guessed(self):
        scene=build_scene(spec_for('asrock-b650i-lightning-wifi'))
        checks=scene.metadata['motherboard']['compatibility']
        self.assertEqual(next(r['state'] for r in checks if r['kind']=='cpu_socket'),'mismatch')
        self.assertTrue(all(r['state']=='mismatch' for r in checks if r['kind']=='memory_generation'))
        value=spec_for();value['cpu']={'label':'unknown'}
        checks=build_scene(value).metadata['motherboard']['compatibility']
        self.assertEqual(next(r['state'] for r in checks if r['kind']=='cpu_socket'),'unknown')

    def test_new_part_ids_survive_case_orientation_without_geometry_or_clock_changes(self):
        import assembly_motherboard
        original=assembly_motherboard.enrich_motherboard
        def add_part(meshes,spec,anchors,level):
            meshes,meta=original(meshes,spec,anchors,level)
            return (*meshes,Mesh('identity-probe',box(3,4,5),(.5,.5,.5,1),(2,3,4),'cpu',False,1,(0,1,0),'test:part')),meta
        with patch('assembly_motherboard.enrich_motherboard',side_effect=add_part):
            value=spec_for();value['case']['layout']='vertical';scene=build_scene(value)
        probe=next(m for m in scene.meshes if m.name=='identity-probe')
        self.assertEqual(probe.part_id,'test:part');self.assertEqual(probe.position,(2,-4,3));self.assertEqual(probe.axis,(0,0,1))

    def test_oversized_selected_cooler_has_actual_protrusion_warning_without_shrinking(self):
        value=spec_for();value['case']['dimensions_mm']['width']=100;value['cooling']={'cpu_cooler':'noctua-nh-d15'}
        scene=build_scene(value);notices=scene.metadata['attachment_notices']
        self.assertTrue(any(r['component']=='cooler' and max(r['excess_mm'])>7.5 for r in notices))
        cooler=[m for m in scene.meshes if m.component=='cooler'];self.assertTrue(cooler)
        xs=[m.position[0]+v for m in cooler for v in m.vertices[0::6]]
        self.assertGreater(max(xs)-min(xs),160.)
        self.assertFalse(any(r['actual_fit_verified'] for r in notices))

    def test_explicit_waterblock_success_replaces_only_cooler_and_default_retains_gpu(self):
        value=spec_for();value['gpu']={'appearance':appearance_for('gpu','ROG-ASTRAL-RTX5090-32G-GAMING')}
        base=build_scene(value);self.assertTrue(any(m.name=='gpu-shroud' for m in base.meshes))
        block=Mesh('reference-waterblock',box(20,20,20),(.4,.5,.6,1),component='gpu',part_id='gpu:waterblock')
        with patch('assembly_cooling.add_cooling',return_value=((block,),{'replace_gpu_cooler':True})):
            scene=build_scene(value)
        self.assertFalse(any(m.name=='gpu-shroud' or m.name.startswith('gpu-fan-') for m in scene.meshes))
        for name in ('gpu-pcb','gpu-bracket','detail-gpu-separated-edge-contacts','detail-gpu-port-recesses'):
            self.assertTrue(any(m.name==name for m in scene.meshes),name)
        self.assertTrue(scene.metadata['gpu_air_cooler_replaced']);self.assertEqual(scene.metadata['physical_total_fans'],0)
        self.assertFalse(scene.metadata['attachment_anchors']['gpu']['pcb']['dimensions_verified'])

    def test_inputs_remain_detached_and_missing_selections_do_not_add_devices(self):
        value=spec_for();before=copy.deepcopy(value);scene=build_scene(value)
        self.assertEqual(value,before);self.assertEqual(scene.metadata['cooling']['parts'],[])
        self.assertEqual(scene.metadata['auxiliary']['device_counts'],dict(psu=0,storage=0,expansion=0))
        scene.metadata['attachment_anchors']['board']['height']=1
        self.assertEqual(build_scene(value).metadata['attachment_anchors']['board']['height'],305.)


if __name__=='__main__':unittest.main()
