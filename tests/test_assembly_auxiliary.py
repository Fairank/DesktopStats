"""Pure auxiliary geometry, documented identity, endpoints and routing checks."""
import copy
import math
import unittest
from unittest.mock import patch

from assembly_auxiliary import add_auxiliary,route_cable,segment_hits_box,vent_panel,_connector_basis,_GpuObstacle
from component_catalog import CATALOG,choices,coverage,get_component,validate_catalog,valid_component_id


def anchors():
    return dict(case_dimensions=(400.,600.,650.),case=dict(layout='dual_chamber',features=[]),
        gpu=dict(center=(20.,-20.,-60.),bounds=dict(min=(-55.,-60.,-220.),max=(95.,20.,100.)),
                 power=[dict(type='16pin',position=(-55.,15.,-30.),normal=(-1.,0.,0.),along=(0.,0.,1.),position_schematic=True)]),
        connectors=dict(atx24=[dict(position=(130.,60.,80.),normal=(-1.,0.,0.),along=(0.,1.,0.))],
            eps8=[dict(position=(130.,180.,-100.),normal=(-1.,0.,0.),along=(0.,0.,1.))],
            sata=[dict(position=(130.,-100.,80.),normal=(0.,0.,1.)),dict(position=(130.,-108.,80.),normal=(0.,0.,1.))],
            usb3=[dict(position=(130.,-160.,130.),normal=(-1.,0.,0.))],front_io=[],
            m2=[dict(position=(130.,30.,-70.),normal=(-1.,0.,0.),along=(0.,0.,1.)),
                dict(position=(132.,60.,-70.),normal=(1.,0.,0.),along=(0.,0.,1.),side='rear')],
            pcie=[dict(position=(125.,y,-140.),normal=(-1.,0.,0.),along=(0.,0.,1.),kind='x16',rear_position=(125.,y,-250.)) for y in (-20.,-140.,-180.)]),
        case_front_io=[dict(position=(20.,-230.,325.),normal=(0.,0.,1.),kind='usb_a'),
                       dict(position=(36.,-230.,325.),normal=(0.,0.,1.),kind='usb_a')])


def full_spec():
    return dict(auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),
        storage=[dict(model_id='samsung-990-pro-2tb',count=2),dict(model_id='samsung-870-evo-1tb',count=1),
                 dict(model_id='wd-blue-wd40ezax',count=1)],
        expansion_cards=[dict(model_id='creative-audigy-fx-v2'),dict(model_id='elgato-4k-pro')],
        cables_enabled=True,cable_color='#6c8496'))


class AuxiliaryGeometryTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Auxiliary parts perform no I/O or workers')))

    def assert_finite_normals(self,meshes):
        for mesh in meshes:
            self.assertEqual(len(mesh.vertices)%18,0,mesh.name)
            self.assertTrue(all(math.isfinite(value) and abs(value)<5000 for value in mesh.vertices),mesh.name)
            for n in range(3,len(mesh.vertices),6):self.assertAlmostEqual(sum(value*value for value in mesh.vertices[n:n+3]),1.,places=5,msg=mesh.name)

    def test_catalog_is_source_linked_detached_and_complete_by_category(self):
        self.assertTrue(validate_catalog());self.assertEqual(coverage(),dict(psu=21,storage=5,expansion=3))
        for record in CATALOG:
            self.assertTrue(valid_component_id(record['id'],record['category']))
            self.assertTrue(all(url.startswith('https://') for url in record['sources']))
        value=get_component('corsair-rm1000x-2024');value['dimensions_mm']['length']=1
        self.assertEqual(get_component(value['id'])['dimensions_mm']['length'],160)
        listed=choices('storage');listed[0]['label']='changed';self.assertNotEqual(choices('storage')[0]['label'],'changed')
        self.assertFalse(valid_component_id('corsair-rm1000x-2024','storage'))
        for bad in (None,False,{},'not-registered','../psu'):
            self.assertIsNone(get_component(bad));self.assertFalse(valid_component_id(bad))

    def test_empty_or_unknown_selections_never_infer_installed_devices(self):
        meshes,meta=add_auxiliary({},{});self.assertEqual(meshes,())
        self.assertEqual(meta['device_counts'],dict(psu=0,storage=0,expansion=0));self.assertEqual(meta['parts'],[])
        spec=dict(auxiliary=dict(psu=dict(model_id='unknown'),storage=[dict(model_id='unknown',count=1)],
                  expansion_cards=[dict(model_id='unknown')],cables_enabled=True))
        meshes,meta=add_auxiliary(spec,{})
        self.assertFalse(meshes);self.assertFalse(meta['actual_installed_devices_inferred']);self.assertEqual(meta['cable_count'],0)

    def test_each_psu_keeps_physical_envelope_and_only_unknown_tachometer_rotors_move(self):
        for row in choices('psu'):
            for level in ('eco','balanced','close'):
                with self.subTest(model=row['id'],level=level):
                    meshes,meta=add_auxiliary(dict(auxiliary=dict(psu=dict(model_id=row['id']))),anchors(),level)
                    record=get_component(row['id']);shell=next(mesh for mesh in meshes if mesh.name=='psu-shell')
                    extents=[max(shell.vertices[n::6])-min(shell.vertices[n::6]) for n in range(3)]
                    self.assertEqual(extents,[record['dimensions_mm'][key] for key in ('height','width','length')])
                    rotors=[mesh for mesh in meshes if mesh.rotor]
                    self.assertEqual(len(rotors),2 if record['fan_count'] else 0)
                    self.assertTrue(all(mesh.name in ('psu-fan-blades','psu-fan-hub') and mesh.component=='psu' for mesh in rotors))
                    self.assertTrue(all(mesh.axis==(1.,0.,0.) for mesh in rotors))
                    self.assertFalse(meta['psu_fan_tachometer_available']);self.assertIsNone(meta['devices'][0]['live_power_w'])
                    self.assertTrue(all(mesh.part_id=='psu:0' for mesh in meshes if mesh.component=='psu'))
                    if level=='eco':self.assertLess(sum(mesh.vertex_count//3 for mesh in meshes if mesh.component=='psu'),15000)
                    self.assert_finite_normals(meshes)

    def test_all_storage_models_have_source_dimensions_and_m2_respects_rear_mount_normal(self):
        for row in choices('storage'):
            with self.subTest(model=row['id']):
                meshes,meta=add_auxiliary(dict(auxiliary=dict(storage=[dict(model_id=row['id'],count=2)])),anchors())
                self.assertEqual(meta['device_counts']['storage'],2)
                self.assertEqual(len({part['id'] for part in meta['parts']}),2)
                self.assertTrue(all(device['dimensions_mm']==get_component(row['id'])['dimensions_mm'] for device in meta['devices']))
                if get_component(row['id'])['form_factor']=='m2_nvme':
                    pcbs=[mesh for mesh in meshes if mesh.name.endswith('-m2-pcb')]
                    self.assertLess(pcbs[0].position[0],130.)
                    self.assertGreater(pcbs[1].position[0],132.)
                    self.assertEqual(sum(mesh.name.endswith('-m2-socket') for mesh in meshes),2)
                    self.assertEqual(sum(mesh.name.endswith('-m2-fixing-screw') for mesh in meshes),2)
                self.assert_finite_normals(meshes)

    def test_full_build_counts_stable_part_ids_and_cable_endpoints_match_connector_backs(self):
        spec=full_spec();mounts=anchors();before=copy.deepcopy((spec,mounts))
        meshes,meta=add_auxiliary(spec,mounts)
        self.assertEqual((spec,mounts),before)
        self.assertEqual(meta['device_counts'],dict(psu=1,storage=4,expansion=2))
        self.assertEqual(meta['cable_count'],8)
        self.assertFalse(meta['issues'],meta['issues'])
        self.assertEqual(meta['gpu_power_inlets'],1)
        self.assertEqual(len(meta['parts']),8)
        self.assertEqual(len({part['id'] for part in meta['parts']}),8)
        part_ids={part['id'] for part in meta['parts']}
        self.assertTrue(all(mesh.part_id in part_ids for mesh in meshes if mesh.component!='gpu'))
        self.assertTrue(all(not mesh.part_id for mesh in meshes if mesh.component=='gpu'))
        gpu_bounds=(mounts['gpu']['bounds']['min'],mounts['gpu']['bounds']['max'])
        for cable in meta['cables']:
            self.assertEqual(cable['path'][0],cable['start']);self.assertEqual(cable['path'][-1],cable['end'])
            self.assertFalse(cable['routing_failed']);self.assertFalse(cable['external_route'])
            self.assertTrue(all(not segment_hits_box(a,b,gpu_bounds,5.) for a,b in zip(cable['path'],cable['path'][1:])))
        self.assert_finite_normals(meshes)
        self.assertEqual(add_auxiliary(spec,mounts),(meshes,meta))

    def test_visibility_routes_round_around_real_obstacle_and_report_external_incompatible_route(self):
        obstacle=((-20.,-50.,-50.),(20.,50.,50.));start=(-90.,0.,-100.);end=(90.,0.,100.)
        path,state=route_cable(start,end,(0,0,-1),(0,0,1),(obstacle,),(300,300,300),width=10)
        self.assertFalse(state['routing_failed']);self.assertFalse(state['external_route'])
        self.assertEqual(path[0],start);self.assertEqual(path[-1],end);self.assertGreater(len(path),4)
        self.assertTrue(all(not segment_hits_box(a,b,obstacle,5) for a,b in zip(path,path[1:])))
        path,state=route_cable(start,end,(0,0,-1),(0,0,1),(((-40.,-90.,-90.),(40.,90.,90.)),),(200,160,160),width=10)
        self.assertTrue(path);self.assertTrue(state['external_route']);self.assertFalse(state['routing_failed'])

    def test_known_gpu_power_types_are_preserved_and_unknown_types_are_not_invented(self):
        mount=anchors();mount['gpu']['power']=[dict(type=kind,position=(-55.,15.,n*35.),normal=(-1.,0.,0.)) for n,kind in enumerate(('4pin','6pin','8pin','12pin','16pin','unknown'))]
        meshes,meta=add_auxiliary({},mount)
        self.assertEqual(meta['gpu_power_inlets'],5)
        self.assertEqual(sum(mesh.name.startswith('gpu-power-inlet-') for mesh in meshes),5)
        self.assertEqual(meta['device_counts'],dict(psu=0,storage=0,expansion=0))
        self.assert_finite_normals(meshes)

    def test_source_grille_families_are_distinct_open_sheets_and_never_rotors(self):
        from assembly_viewer import ray_triangle
        expected={'corsair-rm850x-2024':'rounded_y','corsair-sf750-2024':'triangle',
                  'seasonic-focus-gx850-atx31':'quadrant_slots','seasonic-prime-fanless-tx700':'honeycomb'}
        geometries=[]
        for identity,pattern in expected.items():
            self.assertEqual(get_component(identity)['grille_pattern'],pattern)
            vertices=vent_panel(100.,100.,pattern)
            geometries.append(vertices)
            # Each family has real openings, rather than dark disks or an
            # opaque rectangle with a decorative pattern painted on it.
            hits=[]
            for x,y in ((0.,0.),(12.,12.),(20.,20.),(-20.,20.),(-30.,-12.)):
                hit=any(ray_triangle((x,y,10.),(0.,0.,-1.),tuple(vertices[n:n+3]),tuple(vertices[n+6:n+9]),tuple(vertices[n+12:n+15])) is not None for n in range(0,len(vertices),18))
                hits.append(hit)
            self.assertIn(False,hits,pattern)
        self.assertEqual(len(set(geometries)),4)
        meshes,_=add_auxiliary(dict(auxiliary=dict(psu=dict(model_id='seasonic-prime-fanless-tx700'))),anchors())
        self.assertFalse(any(mesh.rotor for mesh in meshes))
        self.assertEqual(sum(mesh.name=='psu-passive-side-honeycomb' for mesh in meshes),2)
        self.assertFalse(any('fixed-fan-grille' in mesh.name for mesh in meshes))

    def test_top_labels_face_outward_and_source_model_labels_keep_distinct_geometry(self):
        for identity in ('wd-blue-wd40ezax','samsung-870-evo-1tb'):
            meshes,_=add_auxiliary(dict(auxiliary=dict(storage=[dict(model_id=identity,count=1)])),anchors())
            mark=next(mesh for mesh in meshes if mesh.name.endswith('-hdd-label-model') or mesh.name.endswith('-ssd-original-model-mark'))
            # Rear-chamber mounted label faces case +X, not a mirrored backface.
            self.assertIn((1.,0.,0.),[tuple(mark.vertices[n:n+3]) for n in range(3,len(mark.vertices),6)])
        self.assertTrue(get_component('crucial-t500-1tb')['appearance_unverified'])
        self.assertTrue(all(row.get('series') and row.get('brand') for row in CATALOG))

    def test_eps4_is_two_by_two_and_connector_long_axis_matches_header(self):
        mount=anchors();mount['connectors']['eps4']=[dict(position=(130.,170.,-80.),normal=(-1.,0.,0.),along=(0.,0.,1.))]
        meshes,meta=add_auxiliary(full_spec(),mount)
        cables=[row for row in meta['cables'] if row['kind']=='aux4']
        self.assertEqual(len(cables),1);self.assertEqual(meta['cable_count'],9)
        self.assertEqual(_connector_basis((-1.,0.,0.),(0.,1.,0.))[0],(0.,1.,0.))
        self.assertTrue(any('aux4-target-plug-shell' in mesh.name for mesh in meshes))

    def test_half_height_case_and_gpu_blocked_expansion_slots_report_unsupported(self):
        spec=dict(auxiliary=dict(expansion_cards=[dict(model_id='elgato-4k-pro')]))
        mount=anchors();mount['case']['id']='hyte-y70'
        meshes,meta=add_auxiliary(spec,mount)
        self.assertEqual(meta['device_counts']['expansion'],0)
        self.assertEqual(meta['rejected'][0]['reason'],'low_profile_bracket_required')
        mount=anchors();mount['model']='verified-board';mount['connectors']['pcie']=mount['connectors']['pcie'][:1]
        _,meta=add_auxiliary(spec,mount)
        self.assertEqual(meta['device_counts']['expansion'],0)
        self.assertEqual(meta['rejected'][0]['reason'],'no_expansion_slot')

    def test_gpu_narrowphase_retains_hollow_aperture_and_conservative_swept_rotor(self):
        from assembly_geometry import Mesh,fan_rotor
        from assembly_detail import chamfer_rect,perforated_plate
        vertices=perforated_plate(chamfer_rect(20,20,1),(chamfer_rect(8,8,.5),),2.)
        shell=Mesh('gpu-hollow-shell',vertices,(.2,.2,.2,1.),component='gpu')
        bounds=((-10.,-10.,-1.),(10.,10.,1.))
        obstacle=_GpuObstacle(bounds,(shell,))
        self.assertFalse(segment_hits_box((0.,0.,8.),(0.,0.,-8.),obstacle,1.))
        self.assertTrue(segment_hits_box((8.,0.,8.),(8.,0.,-8.),obstacle,1.))
        rotor=Mesh('gpu-fan-blades',fan_rotor(dict(blades=7,shape='wide'),4.),(.2,.2,.2,1.),component='gpu',rotor=True)
        swept=_GpuObstacle(bounds,(shell,rotor))
        self.assertTrue(segment_hits_box((0.,0.,8.),(0.,0.,-8.),swept,1.))

    def test_rendered_fan_connector_boundary_is_attached_but_foreign_part_is_not_ignored(self):
        mount=dict(case_dimensions=(300.,300.,300.),connectors=dict(fan=[dict(position=(-80.,50.,-80.),normal=(-1.,0.,0.))]),
            cooling=dict(wire_anchors=[dict(position=(30.,10.,50.),normal=(1.,0.,0.),kind='fan4',owner='fans:front:0',connector_rendered=True)]),
            obstacles=[dict(name='case-fan-power-connector',part_id='fans:front:0',bounds=dict(min=(23.,7.5,48.5),max=(30.,12.5,51.5)))])
        spec=dict(auxiliary=dict(cables_enabled=True))
        _,meta=add_auxiliary(spec,mount)
        self.assertEqual(meta['cable_count'],1);self.assertFalse(meta['omitted_routes'])
        mount['obstacles'].append(dict(name='foreign-heatsink',part_id='board:0',bounds=dict(min=(25.,0.,40.),max=(45.,20.,60.))))
        _,meta=add_auxiliary(spec,mount)
        self.assertEqual(meta['cable_count'],0);self.assertEqual(meta['omitted_route_count'],1)

    def test_all_expansion_rear_cavities_are_above_the_pcb_and_not_filled_by_board_material(self):
        from assembly_viewer import ray_triangle
        rays=0
        for record in choices('expansion'):
            meshes,_=add_auxiliary(dict(auxiliary=dict(expansion_cards=[dict(model_id=record['id'])])),anchors())
            for target in (mesh for mesh in meshes if mesh.name.endswith('-port-dark-cavity')):
                normal=target.vertices[3:6]
                origin=tuple(target.position[n]+normal[n]*20. for n in range(3));direction=tuple(-x for x in normal)
                nearest=None
                for mesh in meshes:
                    if mesh.component!='expansion':continue
                    for i in range(0,len(mesh.vertices),18):
                        points=[tuple(mesh.vertices[i+k+n]+mesh.position[n] for n in range(3)) for k in (0,6,12)]
                        distance=ray_triangle(origin,direction,*points)
                        if distance is not None and (nearest is None or distance<nearest[0]):nearest=(distance,mesh.name)
                self.assertIsNotNone(nearest,record['id'])
                self.assertEqual(nearest[1],target.name,record['id']);rays+=1
        self.assertEqual(rays,9)


if __name__=='__main__':unittest.main()
