"""Selected loops reserve actual auxiliary bodies once, without native I/O."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

import assembly_auxiliary
from assembly_geometry import Mesh,box,build_scene
from assembly_spec import build_spec
from hardware_packs import PackStore
import hardware_packs
from liquid_aux_clearance046 import auxiliary_bounds,component_conflicts
from stats_config import DEFAULT


def configuration(case='corsair-5000d-airflow',two_hdd=False):
    config=copy.deepcopy(DEFAULT)
    config['assembly'].update(case_model=case,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
        board_model='asus-rog-strix-z790-a-wifi-d4',memory_models=['gskill-f4-3200c16d-16gtzr']*2,
        psu_model='corsair-rm1000x-2024',storage=[dict(model_id='samsung-990-pro-2tb',count=1)],
        cooler_model='custom-loop-360-reference',cooler_mount='top',detail_level='balanced' if two_hdd else 'eco',gpu_waterblock=False,
        loop_components_mode='selected',cpu_block_model='alphacool-core1-black',pump_reservoir_model='corsair-xd5-rgb-gen2',
        fitting_model='alphacool-eiszapfen-soft-13-10',tubing_model='alphacool-alphatube-hf-13-10',radiator_model='corsair-xr5-360',
        radiator_fan_layout='single',radiator_fan_model='arctic-p12-pwm',
        case_fans=[dict(model='arctic-p12-pwm',mount='front',count=3,direction='intake'),dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')],
        cables_enabled=True)
    if two_hdd:
        config['assembly'].update(storage=[dict(model_id='samsung-990-pro-heatsink-2tb',count=1),
            dict(model_id='samsung-870-evo-1tb',count=1),dict(model_id='wd-blue-wd40ezax',count=2)],
            expansion_cards=[dict(model_id='tp-link-archer-tx3000e-v1')])
    return config


class AuxiliaryStage046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/network/window/worker')))

    def test_independent_devices_keep_the_empty_corridor_and_exclude_the_cable_loom(self):
        meshes=[Mesh('drive-left',box(10,10,10),(1,1,1,1),(-50,0,0),'storage',part_id='storage:left:0'),
            Mesh('drive-right',box(10,10,10),(1,1,1,1),(50,0,0),'storage',part_id='storage:right:0'),
            Mesh('cable-loom',box(120,120,120),(1,1,1,1),component='cables',part_id='cables:all')]
        obstacles=auxiliary_bounds(meshes);self.assertEqual(len(obstacles),2)
        candidate=[Mesh('pump',box(20,20,20),(1,1,1,1),component='cooler',part_id='cooler:pump')]
        self.assertEqual(component_conflicts(candidate,obstacles),())
        self.assertEqual(component_conflicts(meshes[:1],obstacles),('storage:left:0',))

    def test_stages_reuse_the_same_bodies_and_receive_new_cooling_wire_anchors(self):
        spec=dict(auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),cables_enabled=True))
        anchors=dict(case_dimensions=(600,800,800),connectors=dict(fan=[dict(position=(0,100,0),normal=(1,0,0))]))
        stages=assembly_auxiliary.auxiliary_stages(spec,anchors,'eco')
        try:
            with patch.object(assembly_auxiliary,'vent_panel',wraps=assembly_auxiliary.vent_panel) as vents:
                bodies=next(stages);count=vents.call_count
                self.assertTrue(bodies);self.assertFalse(any(m.component=='cables' for m in bodies))
                updated=dict(anchors,cooling=dict(wire_anchors=[dict(position=(-10,50,50),normal=(1,0,0),
                    kind='fan4',owner='cooler:radiator:front:0')]))
                meshes,metadata=assembly_auxiliary.finish_auxiliary(stages,updated)
                self.assertEqual(vents.call_count,count)
            self.assertTrue(all(first is second for first,second in zip(bodies,meshes)))
            self.assertTrue(any(row['source_owner']=='cooler:radiator:front:0' for row in metadata['cables']))
            json.dumps(metadata,allow_nan=False)
            self.assertIsNone(stages.gi_frame)
        finally:stages.close()

    def test_legacy_wrapper_and_explicit_same_anchor_stages_are_identical(self):
        spec=dict(auxiliary=dict(psu=dict(model_id='corsair-rm1000x-2024'),
            storage=[dict(model_id='samsung-990-pro-2tb',count=1)],cables_enabled=False))
        anchors=dict(case_dimensions=(600,800,800))
        original=assembly_auxiliary.add_auxiliary(spec,anchors,'eco')
        stages=assembly_auxiliary.auxiliary_stages(spec,anchors,'eco')
        try:next(stages);actual=assembly_auxiliary.finish_auxiliary(stages,anchors)
        finally:stages.close()
        self.assertEqual(actual,original)


class ActualAuxiliaryLoop046Tests(unittest.TestCase):
    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device/network/window/worker')))
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.store=PackStore(root/'installed')
        self.store.install(Path(__file__).resolve().parents[1]/'model-packs/v046/DesktopStats-loop-collection-046-1.0.0.dspack')
        self.enterContext(patch.object(hardware_packs,'_store',self.store))

    def test_haf_and_regular_5000d_still_connect_without_auxiliary_penetration(self):
        for case in ('cooler-master-haf-700-evo','corsair-5000d-airflow'):
            with self.subTest(case=case):
                scene=build_scene(build_spec({},configuration(case),{},[]));loop=scene.metadata['cooling']['selected_loop']
                self.assertTrue(loop['connected_reference_loop'],loop['issues']);self.assertEqual(len(loop['routes']),3)
                blockers=auxiliary_bounds(scene.meshes)
                for identity in ('cooler:cpu','cooler:pump-reservoir'):
                    meshes=[m for m in scene.meshes if m.part_id==identity]
                    self.assertTrue(meshes);self.assertEqual(component_conflicts(meshes,blockers),())

    def test_two_hdd_real_5000d_cannot_draw_xd5_or_fittings_through_the_hdd_body(self):
        scene=build_scene(build_spec({},configuration(two_hdd=True),{},[]));loop=scene.metadata['cooling']['selected_loop']
        bodies=[m for m in scene.meshes if m.component=='storage' and m.name.endswith('-drive-body')]
        self.assertEqual(len(bodies),3)  # SATA SSD + two actual HDD instances.
        blockers=auxiliary_bounds(scene.meshes);parts={}
        for mesh in scene.meshes:
            if mesh.component=='cooler' and not mesh.part_id.startswith('cooler:tubing:'):
                parts.setdefault(mesh.part_id,[]).append(mesh)
                for drive in bodies:
                    low=tuple(min(drive.vertices[i::6])+drive.position[i] for i in range(3))
                    high=tuple(max(drive.vertices[i::6])+drive.position[i] for i in range(3))
                    for at in range(0,len(mesh.vertices),6):
                        point=tuple(mesh.vertices[at+i]+mesh.position[i] for i in range(3))
                        self.assertFalse(all(low[i]+1<point[i]<high[i]-1 for i in range(3)),
                            (mesh.name,drive.name,point))
        for identity,meshes in parts.items():self.assertEqual(component_conflicts(meshes,blockers),(),identity)
        if not loop['connected_reference_loop']:
            self.assertTrue(loop['issues']);self.assertEqual(loop['routes'],[])
            self.assertFalse(any(m.name=='loop-reference-routed-tube' for m in scene.meshes))
        json.dumps(scene.metadata,allow_nan=False)

    def test_geometry_error_closes_the_suspended_auxiliary_build(self):
        captures=[];real=assembly_auxiliary.auxiliary_stages
        def stages(*args,**kwargs):
            value=real(*args,**kwargs);captures.append(value);return value
        with patch.object(assembly_auxiliary,'auxiliary_stages',side_effect=stages),patch('assembly_cooling.add_cooling',side_effect=ValueError('injected build failure')):
            with self.assertRaisesRegex(ValueError,'injected build failure'):
                build_scene(build_spec({},configuration(),{},[]))
        self.assertEqual(len(captures),1);self.assertIsNone(captures[0].gi_frame)


if __name__=='__main__':unittest.main()
