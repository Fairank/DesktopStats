"""Two observed 2010 exteriors; unknown rotors and reference scope stay honest."""
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QCoreApplication,QEvent,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtSvg import QSvgRenderer

from hardware_appearance import CATALOG,appearance_for
from hardware_board_details import drawing_payload,PROFILES
from hardware_fan_profiles import profile_for

ROOT=Path(__file__).resolve().parents[1]
MSI='msi-n480gtx-m2d15'
GIGA='gigabyte-gtx460-oc-1g-rev1'
SIX=('miniature','cartoon','notebook_color','notebook_line','sticker','papercut')


def appearance(identity):
    return appearance_for('gpu',next(r for r in CATALOG if r[0]==identity)[-1][0])


def decode(source):
    return unquote(source.split(',',1)[1])


class OldGpuExterior052Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        cls.engine=QQmlEngine()
        cls.component=QQmlComponent(cls.engine)
        cls.component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/HardwareModelNvidia042.js" as Model
import "../native/HardwareSolid.js" as Solid
import "../native/HardwareBoardDesigns.js" as Board
import "../native/HardwareVariantGroupA.js" as VariantA
QtObject {
 function art(a,style) {a.icon_set=style;a.model_mode=true;
  var key=Shapes.key(a,'#1f242b');return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)});}
 function face(a) {a.model_id=a.id;a.icon_set='solid';a.ink='#1f242b';
  return JSON.stringify({geometry:Solid.geometry(a),body:Board.variantFace(a,Solid.geometry(a),Board.colors(a,Solid.palette(a))),row:Model.profile(a)});}
 function foreign(a) {return JSON.stringify({fixed:VariantA.legacy052Fixed(a,{},[]),
  face:VariantA.face('a_msi_480_observed',{}, {},a),tones:VariantA.legacy052FanTones(a,'unchanged')});}
}''',QUrl.fromLocalFile(str(ROOT/'tests/OldGpuExterior052Fixture.qml')))
        cls.object=cls.component.create()
        if cls.object is None:raise AssertionError([e.toString()for e in cls.component.errors()])

    @classmethod
    def tearDownClass(cls):
        cls.object.deleteLater();cls.component.deleteLater();cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def setUp(self):
        for name in ('socket.socket','ctypes.WinDLL','threading.Thread.start','subprocess.Popen'):
            self.enterContext(patch(name,side_effect=AssertionError('Software-only source/geometry check')))

    def call(self,name,*args):
        expression=QQmlExpression(qmlContext(self.object),self.object,name+'('+','.join(json.dumps(v)for v in args)+')')
        result=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return json.loads(result[0]if isinstance(result,tuple)else result)

    def test_exact_primary_facts_do_not_promote_unknown_blades_or_rev2(self):
        facts=drawing_payload()
        for identity,recipe in ((MSI,'a_msi_480_observed'),(GIGA,'a_gigabyte_460_rev1_observed')):
            self.assertEqual(facts[identity]['recipe'],recipe)
            profile=profile_for(appearance(identity))
            self.assertIsNone(profile['blades']);self.assertFalse(profile['render_ready'])
            self.assertEqual(profile['artwork_status'],'pending')
            self.assertEqual(facts[identity]['power_position'],'unknown')
        self.assertEqual(facts[MSI]['dimensions_mm'],dict(length=265,height=120,thickness=33))
        self.assertIn('not a total heatpipe count',PROFILES['msi_blower_fermi']['notes'])
        self.assertIsNone(facts[MSI]['power_connectors'])
        self.assertEqual(facts[GIGA]['pcb_tone'],'blue')
        self.assertTrue(all(v is None for v in facts[GIGA]['dimensions_mm'].values()))
        for identity in ('gigabyte-gtx460-oc-1g-rev2','gigabyte-gtx460-oc-1g-rev3'):
            self.assertNotEqual(facts[identity]['recipe'],facts[GIGA]['recipe'])

    def test_generated_board_data_matches_authoring_without_touching_fan_data(self):
        text=(ROOT/'native/HardwareBoardProfileData.js').read_text(encoding='utf8')
        self.assertEqual(json.loads(text.split('var models = ',1)[1]),drawing_payload())
        from tools.generate_hardware_fan_data import payload
        text=(ROOT/'native/HardwareFanProfileData.js').read_text(encoding='utf8')
        self.assertEqual(json.loads(text.split('var profiles = ',1)[1]),payload())

    def test_native_faces_keep_ridge_samples_arcs_and_exact_dark_blue_revision(self):
        m=self.call('face',appearance(MSI));g=self.call('face',appearance(GIGA))
        for row in (m,g):
            self.assertIs(row['row']['inline_observed_face'],True)
            self.assertEqual(row['row']['traces'],[])
            self.assertEqual(row['row']['fan_ref']['profile_status'],'pending')
            self.assertIn('blade_geometry_not_reviewed',row['row']['unknown'])
        xml=ET.fromstring('<svg>'+m['body']+'</svg>')
        ridges=[e for e in xml.iter()if e.get('data-reference')=='sampled-horizontal-ridge']
        self.assertEqual(len(ridges),16)
        self.assertTrue(all(float(e.get('width'))>float(e.get('height'))for e in ridges))
        arcs=next(e for e in xml.iter()if e.get('data-reference')=='four-observed-visible-arc-segments-not-total')
        self.assertEqual(arcs.get('d').count('M'),4)
        self.assertIn('#28333d',g['body']);self.assertNotIn('hardware-fan-blade',g['body'])
        self.assertEqual(self.call('foreign',dict(kind='gpu',model_id='gigabyte-gtx460-oc-1g-rev2')),
                         dict(fixed='',face='',tones='unchanged'))

    def test_six_actual_sources_keep_static_brand_in_replayed_cap_and_real_openings(self):
        for identity in (MSI,GIGA):
            for style in SIX:
                with self.subTest(identity=identity,style=style):
                    art=self.call('art',appearance(identity),style)
                    source=decode(art['source']);base=decode(art['layers']['baseSource'])
                    self.assertTrue(QSvgRenderer(source.encode()).isValid())
                    self.assertNotIn('<image',source);self.assertNotIn('<text',source)
                    self.assertNotIn('hardware-fan-blade',source)
                    self.assertTrue(all(not r['known']for r in art['layers']['rotors']))
                    if identity==MSI:
                        self.assertIn('hardware-source-model-badge',base)
                        self.assertIn('hardware-static-brand-label-vector',source)
                        # A fixed cap underneath a replayed dark disc vanished
                        # in the first integration attempt. Test the real layer.
                        if art['layers']['rotors']:
                            self.assertEqual(len(art['layers']['rotors']),1)
                            rotor=decode(art['layers']['rotors'][0]['source'])
                            self.assertIn('hardware-static-brand-label-vector',rotor)
                            self.assertNotIn('hardware-static-brand-label-vector',base)
                        else:self.assertIn('hardware-static-brand-label-vector',base)
                        if style in ('notebook_color','notebook_line'):
                            self.assertIn('hardware-observed-bank-pen',source)
                    elif style=='papercut':
                        xml=ET.fromstring(source)
                        fans=[e for e in xml.iter()if e.get('class')=='hardware-fan']
                        self.assertEqual(len(fans),2)
                        for fan in fans:
                            self.assertEqual(next(e for e in fan if e.get('r')=='3').get('fill'),'#f3dfbd')
                            disk=next(e for e in fan if e.get('r')=='2.90')
                            self.assertEqual(disk.get('stroke'),'#d39978')
                            self.assertEqual(disk.get('stroke-width'),'.065')

    def test_real_profile_planes_unknown_rotors_and_three_lod_budgets(self):
        from assembly_profiles import bake_profiles,ProfileReader
        from assembly_geometry import build_scene
        reader=ProfileReader(self.engine)
        try:
            for identity,expected in ((MSI,[(18.,11.739,3.293)]),
                                      (GIGA,[(7.3692,11.746,3.744),(16.9308,11.746,3.744)])):
                a=appearance(identity);profile=reader.read(a)
                self.assertEqual(len(profile['fans']),len(expected))
                for fan,pose in zip(profile['fans'],expected):
                    self.assertEqual(fan['blade_paths'],[]);self.assertFalse(fan['known'])
                    for key,value in zip(('cx','cy','radius'),pose):self.assertAlmostEqual(fan[key],value,places=6)
                dimensions=drawing_payload()[identity]['dimensions_mm']
                spec=bake_profiles(dict(case={'layout':'tower'},visual_style='miniature',
                    cpu={'appearance':appearance_for('cpu','Intel Core i7-13700KF')},memory={'count':0,'modules':[]},
                    gpu=dict(appearance=a,length_mm=dimensions['length']or 270,width_mm=dimensions['height']or 130,
                             thickness_mm=dimensions['thickness']or 45)),self.engine)
                for level in ('eco','balanced','close'):
                    scene=build_scene(dict(spec,detail_level=level));meshes=[m for m in scene.meshes if m.component=='gpu']
                    self.assertLess(sum(len(m.vertices)//18 for m in meshes),7000)
                    self.assertFalse(any(m.rotor for m in meshes))
                    for mesh in meshes:
                        self.assertTrue(all(math.isfinite(v)for v in mesh.vertices))
                        for n in range(0,len(mesh.vertices),6):
                            self.assertAlmostEqual(sum(v*v for v in mesh.vertices[n+3:n+6]),1.,places=5)
        finally:reader.close()


if __name__=='__main__':unittest.main()
