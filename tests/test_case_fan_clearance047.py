"""Selected fan bodies must not be rendered through a GPU, in any style."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtGui import QGuiApplication,QOpenGLContext
from PySide6.QtQml import QQmlEngine
from assembly_cooling import add_cooling
from assembly_geometry import Mesh,box
from assembly_parts import fit_messages
from assembly_profiles import bake_profiles
from assembly_scene_cache import SceneCache
from assembly_spec import build_spec
from case_fan_clearance047 import _bounds,conflicts,envelope
import hardware_packs
from hardware_packs import PackStore
from stats_config import DEFAULT

SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


class CaseFanClearance047Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('Geometry only')))
        scratch=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(hardware_packs,'_store',PackStore(scratch/'packs')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))

    def tearDown(self):
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertEqual(self.warnings,[])
        self.assertEqual(self.app.topLevelWindows(),[])
        self.assertIsNone(QOpenGLContext.currentContext())

    def spec(self,case,**updates):
        cfg=copy.deepcopy(DEFAULT)
        cfg['assembly'].update(case_model=case,cpu_model='intel-13700kf',gpu_model='asus-astral-5090',
            board_model='asus-rog-strix-z790-a-wifi-d4',detail_level='eco',
            cooler_model='arctic-liquid-freezer-iii-240',cooler_mount='top',gpu_waterblock=False,
            case_fans=[dict(model='arctic-p12-pwm',mount='rear',count=1,direction='exhaust')],cables_enabled=False)
        cfg['assembly'].update(updates)
        return bake_profiles(build_spec({},cfg,{},[]),self.engine)

    def test_actual_north_5000d_y70_retain_full_rear_fan_clear_of_gpu_in_six_styles(self):
        for case in ('fractal-north-mesh','corsair-5000d-airflow','hyte-y70'):
            with self.subTest(case=case):
                spec=self.spec(case);cache=SceneCache();base=cache.build(spec)
                cooling=base.metadata['cooling']
                fans=[f for f in cooling['fans'] if f['role']=='case']
                self.assertEqual(len(fans),1,cooling['rejected'])
                self.assertFalse(cooling['rejected'])
                self.assertGreater(fans[0]['position'][1],100.)
                self.assertIsNone(fans[0]['rpm'])
                obstacles=[(m.part_id,m.name,_bounds(m.vertices,m.position)) for m in base.meshes if m.component=='gpu']
                for mesh in base.meshes:
                    if mesh.part_id=='fans:rear:0' and 'lead' not in mesh.name and 'connector' not in mesh.name:
                        self.assertEqual(conflicts(_bounds(mesh.vertices,mesh.position),obstacles),[],mesh.name)
                for style in SIX:
                    scene=cache.build(dict(spec,visual_style=style))
                    self.assertTrue(all(a.vertices is b.vertices for a,b in zip(base.meshes,scene.meshes)))
                    self.assertEqual(scene.metadata['cooling']['fans'],cooling['fans'])
                    self.assertEqual(len([m for m in scene.meshes if m.part_id=='fans:rear:0' and m.rotor]),1)
                cache.clear()

    def test_all_lods_use_the_same_reference_rear_fan_pose(self):
        positions=[]
        for level in ('eco','balanced','close'):
            cache=SceneCache();scene=cache.build(self.spec('fractal-north-mesh',detail_level=level))
            positions.append(next(f['position'] for f in scene.metadata['cooling']['fans'] if f['role']=='case'))
            cache.clear()
        self.assertEqual(positions,[positions[0]]*3)

    def test_authored_conflicting_plane_is_not_moved_or_silently_cropped(self):
        anchors=dict(case_dimensions=(400.,500.,400.),case_mount_planes={
            'rear':dict(position=(0.,0.,-200.),normal=(0.,0.,-1.),up=(0.,1.,0.))})
        gpu=Mesh('gpu-shroud',box(80.,40.,40.),(1.,1.,1.,1.),(0.,0.,-180.),'gpu',part_id='gpu:0')
        original=copy.deepcopy((anchors,gpu))
        selected=dict(cooling=dict(case_fans=[dict(model='arctic-p12-pwm',mount='rear',count=1)]))
        meshes,meta=add_cooling((gpu,),selected,anchors=anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['fans'],[])
        self.assertEqual(meta['rejected'][0]['reason'],'case_fan_clearance_conflict')
        self.assertEqual(meta['rejected'][0]['conflicting_parts'],['gpu:0'])
        self.assertEqual(meta['rejected'][0]['omitted_count'],1)
        self.assertEqual((anchors,gpu),original)
        self.assertIn('整组风扇未放入',fit_messages({},dict(cooling=meta))[0])

    def test_one_obstructed_fan_rejects_the_whole_group_not_one_fan(self):
        anchors=dict(case_dimensions=(400.,500.,400.),case_mount_planes={
            'front':dict(position=(0.,0.,200.),normal=(0.,0.,1.),up=(0.,1.,0.))})
        gpu=Mesh('gpu-shroud',box(12.,12.,30.),(1.,1.,1.,1.),(0.,60.,185.),'gpu',part_id='gpu:0')
        meshes,meta=add_cooling((gpu,),dict(cooling=dict(case_fans=[dict(model='arctic-p12-pwm',mount='front',count=2)])),anchors=anchors)
        self.assertEqual(meshes,());self.assertEqual(meta['parts'],[]);self.assertEqual(meta['wire_anchors'],[])
        self.assertEqual(meta['rejected'][0]['omitted_count'],2)

    def test_swept_volume_rejects_an_object_inside_the_rotor_aperture(self):
        from cooling_catalog import get_fan
        model=get_fan('arctic-p12-pwm')
        full=envelope(model,(0.,0.,0.),((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
        self.assertEqual(conflicts(full,[('gpu:0','gpu-bracket',((-2.,-2.,-2.),(2.,2.,2.)))]),['gpu:0'])
        self.assertEqual(conflicts(full,[('gpu:0','gpu-bracket',((200.,200.,200.),(202.,202.,202.)))]),[])

    def test_air_and_aio_reserve_top_psu_once_before_case_fan_clearance(self):
        import assembly_auxiliary
        for cooler,mount in (('noctua-nh-u12a','top'),('arctic-liquid-freezer-iii-240','front')):
            with self.subTest(cooler=cooler):
                spec=self.spec('fractal-torrent-tg',cooler_model=cooler,cooler_mount=mount,psu_model='corsair-rm1000x-2024')
                cache=SceneCache()
                with patch.object(assembly_auxiliary,'auxiliary_stages',wraps=assembly_auxiliary.auxiliary_stages) as stages, \
                     patch.object(assembly_auxiliary,'finish_auxiliary',wraps=assembly_auxiliary.finish_auxiliary) as finish, \
                     patch.object(assembly_auxiliary,'add_auxiliary',side_effect=AssertionError('Do not construct auxiliary bodies twice')):
                    base=cache.build(spec)
                    for style in SIX:cache.build(dict(spec,visual_style=style))
                    self.assertEqual(stages.call_count,1);self.assertEqual(finish.call_count,1)
                self.assertEqual(base.metadata['auxiliary']['device_counts']['psu'],1)
                psus=[(m.part_id,m.name,_bounds(m.vertices,m.position)) for m in base.meshes if m.component=='psu']
                self.assertTrue(psus)
                fans=[m for m in base.meshes if m.part_id=='fans:rear:0' and 'lead' not in m.name and 'connector' not in m.name]
                if fans:
                    for fan in fans:self.assertEqual(conflicts(_bounds(fan.vertices,fan.position),psus),[])
                else:
                    rejected=[r for r in base.metadata['cooling']['rejected'] if r.get('mount')=='rear']
                    self.assertEqual(len(rejected),1)
                    self.assertEqual(rejected[0]['reason'],'case_fan_clearance_conflict')
                    self.assertTrue(any(p.startswith('psu:') for p in rejected[0]['conflicting_parts']))
                    self.assertEqual(rejected[0]['omitted_count'],1)
                cache.clear()


if __name__=='__main__':unittest.main()
