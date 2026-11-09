"""Explicit complete examples, independent of unavailable host inventory."""
import copy
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine

import hardware_packs
from hardware_packs import PackStore
from assembly_config import validate_assembly
from assembly_parts import reference_preset,fit_messages
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from assembly_inspection import snapshot
from stats_config import DEFAULT
from top_bar_config import HARDWARE_ICON_STYLES

IDENTITIES=dict(cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
    board_model='asus-rog-strix-z790-a-wifi-d4',
    memory_models=['gskill-f4-3200c16d-16gtzr']*2)
KINDS=('air','aio','loop')
CASES=dict(air='corsair-5000d-airflow',aio='fractal-north-xl-mesh',loop='cooler-master-haf-700-evo')


class ReferencePresets048Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        if cls.app.platformName()!='offscreen':raise unittest.SkipTest('Software-only reference construction')

    def setUp(self):
        for target in ('ctypes.WinDLL','socket.socket','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(target,side_effect=AssertionError('No device, network, workers or application')))
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',PackStore(root/'packs')))

    def tearDown(self):
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def config(self,kind):
        result=copy.deepcopy(DEFAULT)
        result['assembly']=reference_preset({},kind)
        return result

    def test_missing_host_inventory_stays_empty_until_the_user_requests_an_example(self):
        config=copy.deepcopy(DEFAULT);before=copy.deepcopy(config)
        spec=build_spec({},config,{},[])
        self.assertEqual(spec['memory']['count'],0)
        self.assertEqual(spec['memory']['modules'],[])
        self.assertEqual(spec['auxiliary']['psu']['model_id'],'')
        self.assertEqual(spec['cooling']['case_fans'],[])
        self.assertFalse(spec['options']['inspection_cutaway'])
        self.assertEqual(config,before)

    def test_requested_examples_replace_core_references_without_mutating_other_preferences(self):
        options=validate_assembly(dict(cpu_model='amd-9950x',gpu_model='zotac-solo-4060',
            memory_models=['corsair-cmh32gx5m2b6000c30'],board_model='asus-rog-strix-x670e-e-wifi',
            appearance_style='notebook_line',part_styles={'memory:1':'cartoon','gpu':'miniature'}))
        before=copy.deepcopy(options)
        for kind in KINDS:
            value=reference_preset(options,kind)
            self.assertEqual(value['case_model'],CASES[kind])
            for key,expected in IDENTITIES.items():self.assertEqual(value[key],expected)
            self.assertTrue(value['inspection_cutaway'])
            self.assertEqual(value['lighting_preview'],'mint')
            self.assertEqual(value['appearance_style'],options['appearance_style'])
            self.assertEqual(value['part_styles'],options['part_styles'])
            self.assertIsNot(value['memory_models'],options['memory_models'])
            self.assertIsNot(value['part_styles'],options['part_styles'])
        self.assertEqual(options,before)

    def test_reference_core_models_never_borrow_installed_readings(self):
        data=dict(time=100.,cpu_name='AMD Ryzen 9 9950X',cpu_usage=12,cpu_temp=45,
            ram_percent=40,gpus={'0':dict(gpu_name='Intel Arc A770',gpu_usage=30,gpu_temp=51)})
        modules=[dict(manufacturer='CORSAIR',part_number='CMH32GX5M2B6000C30')]
        before=copy.deepcopy((data,modules))
        for kind in KINDS:
            config=self.config(kind);spec=build_spec(data,config,{},modules)
            self.assertEqual(spec['memory']['count'],2)
            self.assertEqual(spec['cpu']['appearance']['id'],IDENTITIES['cpu_model'])
            self.assertEqual(spec['gpu']['appearance']['id'],IDENTITIES['gpu_model'])
            self.assertEqual(spec['board']['model_id'],IDENTITIES['board_model'])
            self.assertEqual(spec['cpu']['detected_label'],data['cpu_name'])
            self.assertEqual(spec['gpu']['detected_label'],'Intel Arc A770')
            for family in ('cpu','gpu','memory'):
                self.assertFalse(spec[family]['telemetry_bound'])
                state=snapshot(data,spec,config,family,now=100.)
                self.assertFalse(any(row['available'] for row in state['rows'] if row.get('metric')))
            self.assertTrue(all(check['state']=='within_limit' for check in spec['checks']),spec['checks'])
        self.assertEqual((data,modules),before)

    def test_real_baked_examples_include_every_selected_part_and_no_hidden_rejection(self):
        engine=QQmlEngine();warnings=[]
        engine.warnings.connect(lambda rows:warnings.extend(value.toString() for value in rows))
        try:
            for kind in KINDS:
                with self.subTest(kind=kind):
                    spec=bake_profiles(build_spec({},self.config(kind),{},[]),engine)
                    self.assertTrue(all(check['state']=='within_limit' for check in spec['checks']))
                    self.assertTrue(spec['gpu']['shell_polygon'])
                    self.assertTrue(all(module['case_polygon'] for module in spec['memory']['modules']))
                    before=copy.deepcopy(spec);cache=SceneCache()
                    try:
                        scene=cache.build(spec);meta=scene.metadata
                        self.assertLessEqual(scene.triangle_count,160000)
                        self.assertEqual(meta['memory_rendered_count'],2)
                        self.assertEqual(sum(mesh.name=='ram-pcb' for mesh in scene.meshes),2)
                        self.assertTrue(any(mesh.part_id=='psu:0' for mesh in scene.meshes))
                        self.assertEqual(meta['cooling']['rejected'],[])
                        self.assertEqual(meta['auxiliary']['rejected'],[])
                        self.assertEqual(meta['auxiliary']['omitted_routes'],[])
                        # Zero omitted known routes must not turn an absent
                        # case-I/O profile into a claim of completefrontwiring.
                        known_io=meta['attachment_anchors'].get('case_front_io') or []
                        io_profile=(spec['case'].get('exterior_details') or {}).get('io')
                        cable_kinds=Counter(row['kind'] for row in meta['auxiliary']['cables'])
                        self.assertEqual(meta['auxiliary']['cable_count'],14 if kind=='air' else 9 if kind=='aio' else 8)
                        if kind=='air':
                            self.assertIsInstance(io_profile,dict)
                            self.assertEqual(len(known_io),6)
                            self.assertEqual(cable_kinds['front_io'],4)
                        else:
                            self.assertIsNone(io_profile)
                            self.assertEqual(known_io,[])
                            self.assertEqual(cable_kinds['front_io'],0)
                            self.assertEqual(cable_kinds,dict(atx24=1,eps8=2,gpu16=1,fan4=5 if kind=='aio' else 4))
                            if kind=='aio':
                                control=[r for r in meta['auxiliary']['cables'] if r.get('role')=='aio_control_reference']
                                self.assertEqual(len(control),1);self.assertEqual(control[0]['target_header_label'],'CPU_FAN')
                                self.assertFalse(control[0]['telemetry_bound']);self.assertFalse(control[0]['installed_control_mode_verified'])
                        self.assertEqual(meta.get('attachment_notices'),[])
                        self.assertEqual(fit_messages(spec,meta),[])
                        devices=meta['auxiliary']['parts']
                        self.assertEqual(sum(row['kind']=='psu' for row in devices),1)
                        self.assertEqual(sum(row['kind']=='storage' for row in devices),1)
                        case_fans=[fan for fan in meta['cooling']['fans'] if fan['role']=='case']
                        self.assertEqual(len(case_fans),4)
                        self.assertEqual({fan['model_id'] for fan in case_fans},{'arctic-p12-pwm'})
                        self.assertEqual(meta['gpu_air_cooler_replaced'],kind=='loop')
                        self.assertEqual(meta['physical_total_fans'],0 if kind=='loop' else 4)
                        ram_zones=[zone for zone in meta['lighting_preview']['zones']
                            if scene.meshes[zone['mesh_index']].name=='ram-diffuser']
                        self.assertEqual({row['part_id'] for row in ram_zones},{'memory:0','memory:1'})
                        self.assertFalse(meta['lighting_preview']['device_control'])
                        physical=[mesh for mesh in scene.meshes if not mesh.name.startswith('style-')]
                        identities=Counter((mesh.component,mesh.part_id,mesh.name) for mesh in physical)
                        for style in HARDWARE_ICON_STYLES:
                            styled=cache.build(dict(spec,visual_style=style))
                            actual=[mesh for mesh in styled.meshes if not mesh.name.startswith('style-')]
                            self.assertEqual(Counter((mesh.component,mesh.part_id,mesh.name) for mesh in actual),identities)
                            self.assertTrue(all(a.vertices is b.vertices and a.position==b.position
                                and a.axis==b.axis and a.rotor==b.rotor and a.direction==b.direction
                                for a,b in zip(physical,actual)))
                        self.assertEqual(spec,before)
                    finally:cache.clear()
        finally:
            engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(warnings,[])


if __name__=='__main__':unittest.main()
