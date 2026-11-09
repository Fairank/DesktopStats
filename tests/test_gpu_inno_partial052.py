"""Exact 2020 RTX3080 X4: three reviewed fronts, unplaced unknown side."""
import json
import math
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QCoreApplication,QEvent,QObject
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlEngine
from shiboken6 import getCppPointer
from hardware_appearance import CATALOG,appearance_for
from hardware_fan_profiles import PROFILES,profile_for
from tests import test_gpu_partial_motion051 as fixture
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
EXACT='inno3d-ichill-x4-3080'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')
SOURCE='https://images.nvidia.com/aem-dam/Solutions/geforce/news/rtx-3080-3090-custom-card-roundup/Inno3D-GeForce-RTX-3080-ICHILL-X4-Photo-002.png'

def appearance():
    row=next(row for row in CATALOG if row[0]==EXACT)
    return appearance_for('gpu',row[-1][0])


class InnoExactEvidence052Tests(unittest.TestCase):
    def test_exact_front_counts_do_not_promote_unreviewed_side_or_whole_card(self):
        a=appearance();p=profile_for(a)
        self.assertEqual((a['fan_count'],a['visible_fan_count']),(4,3))
        self.assertEqual(p['blade_counts'],[11,11,11,None])
        self.assertIsNone(p['blades']);self.assertFalse(p['render_ready'])
        self.assertEqual(p['artwork_status'],'pending');self.assertEqual(p['source_url'],SOURCE)
        self.assertEqual([f['shape'] for f in PROFILES['inno3d_ichill_x4']['fans']],['wide']*3+['neutral'])
        self.assertEqual(profile_for(dict(a,id='inno3d-ichill-x4-3080ti')), {})
        self.assertEqual(profile_for(dict(a,id='inno3d-ichill-x4-3080-12gb')), {})
        self.assertEqual(profile_for(dict(a,id='inno3d-ichill-x4-3090')), {})
        pending=[row[0] for row in CATALOG if row[1]=='gpu'
                 and type((v:=appearance_for(row[1],row[-1][0])).get('fan_count')) is int
                 and v['fan_count']>0
                 and not profile_for(v).get('render_ready',False)]
        self.assertEqual(len(pending),20);self.assertIn(EXACT,pending)

    def test_generated_payload_and_source_guard_keep_the_fourth_entry_unknown(self):
        from tools.generate_hardware_fan_data import payload
        text=(ROOT/'native/HardwareFanProfileData.js').read_text(encoding='utf8')
        data=json.loads(text.split('var profiles = ',1)[1]);self.assertEqual(data,payload())
        native=data['inno3d_ichill_x4'];self.assertIsNone(native['blades'])
        self.assertEqual([f['blades'] for f in native['fans']],[11,11,11,None])
        self.assertEqual(native['fans'][3]['shape'],'neutral')
        text=(ROOT/'native/HardwareModelNvidia042.js').read_text(encoding='utf8')
        line=next(line.strip().rstrip(',') for line in text.splitlines() if line.startswith('    "'+EXACT+'":'))
        row=json.loads('{'+line+'}')[EXACT]
        self.assertEqual(row['fan_ref']['profile_status'],'pending')
        self.assertEqual((row['fan_ref']['reviewed_front_count'],row['fan_ref']['unreviewed_side_count']),(3,1))
        self.assertIn('side_fan_pose_unverified_not_placed',row['unknown']);self.assertIn(SOURCE,row['sources'])


class InnoNativeGeometry052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.PartialGpuMotion051Tests.setUpClass.__func__(cls)
        from assembly_profiles import bake_profiles
        cls.engine=QQmlEngine()
        a=appearance()
        # No manufacturing envelope is available for this exact old source.
        # The same bounded reference envelope is used for every style/LOD.
        cls.spec=bake_profiles(dict(case={'layout':'tower'},visual_style='miniature',
            cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},
            memory={'count':0,'modules':[]},
            gpu=dict(appearance=a,length_mm=270.,width_mm=130.,thickness_mm=45.)),cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('No native device/network/window/worker')))

    def test_three_native_eleven_leaf_rotors_keep_fourth_unplaced_all_lods_and_styles(self):
        from assembly_geometry import build_scene
        from assembly_style import apply_model_styles,edge_batches
        fans=self.spec['gpu']['fans']
        self.assertEqual([f['blades'] for f in fans],[11,11,11])
        self.assertEqual([len(f['blade_polygons']) for f in fans],[11,11,11])
        self.assertEqual(self.spec['gpu']['physical_fan_count'],4)
        self.assertTrue(all(f['face']=='front' for f in fans))
        for level in ('eco','balanced','close'):
            scene=build_scene(dict(self.spec,detail_level=level));meta=scene.metadata
            self.assertEqual((meta['physical_total_fans'],meta['front_fan_count'],meta['rear_fan_count'],meta['unplaced_fans']),(4,3,0,1))
            gpu=tuple(m for m in scene.meshes if m.component=='gpu')
            rotors=[m for m in gpu if m.name=='gpu-fan-rotor']
            self.assertEqual(len(rotors),3);self.assertTrue(all(m.rotor for m in rotors))
            self.assertEqual(len(meta['detail']['gpu']['axial_blade_depth_reference']),3)
            for m in rotors:
                self.assertTrue(all(math.isfinite(v) for v in m.vertices))
                for n in range(0,len(m.vertices),6):
                    self.assertAlmostEqual(sum(v*v for v in m.vertices[n+3:n+6]),1.,places=5)
                # Front fan is a source-preserving shallow curved mesh, not
                # a flat photograph or a made-up fourth side rotor.
                self.assertGreater(len({round(v,5) for v in m.vertices[1::6]}),2)
            self.assertFalse(any('side-fan' in m.name for m in gpu))
            for style in SIX:
                values,info=apply_model_styles(gpu,style,{},scene.dimensions,{'front':'open'})
                self.assertEqual(len(values),len(gpu))
                self.assertTrue(all(a.vertices is b.vertices for a,b in zip(values,gpu)))
                self.assertEqual([(m.part_id,m.position,m.axis,m.rotor)for m in values],[(m.part_id,m.position,m.axis,m.rotor)for m in gpu])
                self.assertLessEqual(sum(len(v)//12 for _,v in edge_batches(values,style,info['mesh_style_ids'])),8192)


class InnoPartialQml052Tests(unittest.TestCase):
    setUpClass=classmethod(fixture.PartialGpuMotion051Tests.setUpClass.__func__)
    setUp=fixture.PartialGpuMotion051Tests.setUp
    tearDown=fixture.PartialGpuMotion051Tests.tearDown
    settle=fixture.PartialGpuMotion051Tests.settle
    evaluate=fixture.PartialGpuMotion051Tests.evaluate
    assign=fixture.PartialGpuMotion051Tests.assign
    rotations=fixture.PartialGpuMotion051Tests.rotations

    def card(self,style='miniature'):
        return dict(appearance(),icon_set=style)

    def test_actual_model_zero_37_zero_keeps_three_known_fronts_and_no_side_delegate(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                card=self.card(style);self.assertFalse(card['fan_profile']['render_ready'])
                self.assign('card',card);self.assign('requested',True);self.assign('angle',0)
                layers=json.loads(self.evaluate('layers()'));rotors=self.rotations()
                self.assertEqual(len(rotors),3)
                self.assertEqual([r['source_index'] for r in layers['rotors']],[0,1,2])
                self.assertTrue(all(r['known'] for r in layers['rotors']))
                for descriptor in layers['rotors']:
                    xml=ET.fromstring(unquote(descriptor['source'].split(',',1)[1]))
                    self.assertEqual(sum(e.attrib.get('class')=='hardware-fan-blade'for e in xml.iter()),11)
                pointers=[getCppPointer(r)[0]for r in rotors]
                sources=[r.findChild(QObject,'hardwareFanRotorImage_'+str(i)).property('source')for i,r in enumerate(rotors)]
                zero=self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
                self.assign('angle',37);turned=self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
                self.assertNotEqual(zero,turned)
                self.assertTrue(all(r.property('rotation')==37. for r in self.rotations()))
                self.assertEqual([getCppPointer(r)[0]for r in self.rotations()],pointers)
                self.assign('angle',0);self.assertEqual(self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888),zero)
                self.assertEqual([r.findChild(QObject,'hardwareFanRotorImage_'+str(i)).property('source')for i,r in enumerate(self.rotations())],sources)
                self.assertEqual(self.evaluate('count()'),0)

    def test_actual_aggregate_rpm_stops_at_zero_stale_unknown_or_permission_all_six(self):
        self.assign('metrics',True);self.assign('second',True)
        metric=self.window.findChild(QObject,'partialMetric')
        def state(rpm=1200,age=0.,semantics='measured'):
            return dict(profile='processor',available=True,load=None,thermal=None,energy=None,
                fan_speed=dict(available=True,rpm=rpm,semantics=semantics,scope='card',source='Synthetic QA only',timestamp=time.time()-age))
        for style in SIX:
            with self.subTest(style=style):
                self.assign('card',self.card(style));self.assign('state',state())
                self.assertTrue(metric.property('gpuFanCanAnimate'));self.assertEqual(self.evaluate('count()'),1)
                self.assertEqual(self.evaluate('subscribers()'),2)
                for value in (state(0),state(age=4),state(semantics='percent')):
                    self.assign('state',value);self.assertFalse(metric.property('gpuFanCanAnimate'));self.assertEqual(self.evaluate('count()'),0)
                self.assign('state',state());self.assign('permitted',False)
                self.assertFalse(metric.property('gpuFanMotionActive'));self.assertEqual(self.evaluate('count()'),0)
                self.assign('permitted',True);self.assertEqual(self.evaluate('count()'),1)
                row=next(r for r in CATALOG if r[0]=='nvidia-gtx780ti-reference')
                self.assign('card',dict(appearance_for('gpu',row[-1][0]),icon_set=style))
                self.assertFalse(metric.property('gpuFanCanAnimate'));self.assertEqual(self.evaluate('count()'),0)


if __name__=='__main__':unittest.main()
