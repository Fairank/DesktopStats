"""CPU package silhouette, bounded type and contact-side contracts; no devices."""
import copy
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtSvg import QSvgRenderer

from assembly_cpu import PACKAGE_SHAPES,build_cpu_meshes,package_geometry,package_style
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]


def cpu(identity,label='9950X'):
    p=PACKAGE_SHAPES[identity]
    model_id='fixture-'+identity.replace('_','-')
    return dict(id=model_id,kind='cpu',vendor=p['vendor'],style=package_style(identity),
                confidence='model',cpu_package=dict(id=identity,model_id=model_id,vendor=p['vendor'],label_ascii=label,width_mm=p['size'][0],length_mm=p['size'][1],
                dimensions_status='verified',substrate_mm=None,pin_count=None,source_urls=['https://example.invalid/primary-fixture']))


class CpuMeshTests(unittest.TestCase):
    def setUp(self):
        for name in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('CPU mesh construction must remain pure')))

    def test_all_packages_levels_finite_normalized_and_bounded(self):
        for identity in PACKAGE_SHAPES:
            for level in ('eco','balanced','close'):
                value=cpu(identity);before=copy.deepcopy(value);meshes,meta=build_cpu_meshes(value,level=level)
                self.assertEqual(value,before);self.assertTrue(meta['available']);self.assertEqual(meta['new_pollers'],0)
                self.assertFalse(meta['internal_layout_verified']);self.assertFalse(meta['ihs_depth_verified'])
                self.assertIsNone(meta['physical_pin_count']);self.assertFalse(meta['cooler_inferred'])
                self.assertLess(sum(len(m.vertices)//18 for m in meshes),20000)
                for mesh in meshes:
                    self.assertEqual(mesh.component,'cpu');self.assertEqual(mesh.part_id,'cpu:0');self.assertFalse(mesh.rotor)
                    self.assertEqual(len(mesh.vertices)%18,0)
                    self.assertTrue(all(math.isfinite(v) and abs(v)<100 for v in mesh.vertices))
                    for i in range(0,len(mesh.vertices),6):self.assertAlmostEqual(sum(v*v for v in mesh.vertices[i+3:i+6]),1.,places=6)
                substrate=next(m for m in meshes if m.name=='cpu-substrate')
                self.assertAlmostEqual(max(substrate.vertices[2::6])-min(substrate.vertices[2::6]),value['cpu_package']['width_mm'])
                self.assertAlmostEqual(max(substrate.vertices[1::6])-min(substrate.vertices[1::6]),value['cpu_package']['length_mm'])

    def test_same_package_skus_change_only_text(self):
        for identity in PACKAGE_SHAPES:
            a,_=build_cpu_meshes(cpu(identity,'9950X'));b,_=build_cpu_meshes(cpu(identity,'7800X3D'))
            self.assertEqual(tuple(m for m in a if m.name!='cpu-model-mark'),tuple(m for m in b if m.name!='cpu-model-mark'))
            self.assertNotEqual(tuple(m for m in a if m.name=='cpu-model-mark'),tuple(m for m in b if m.name=='cpu-model-mark'))

    def test_am4_pins_face_board_instead_of_side_leads(self):
        meshes,meta=build_cpu_meshes(cpu('amd_am4'))
        pins=next(m for m in meshes if m.name=='cpu-pins-reference')
        substrate=next(m for m in meshes if m.name=='cpu-substrate')
        self.assertGreaterEqual(min(pins.vertices[0::6]),max(substrate.vertices[0::6])-.00001)
        self.assertEqual(meta['contact_layout'],'schematic_density_samples_not_pin_map')
        for identity in PACKAGE_SHAPES:
            if identity=='amd_am4':continue
            meshes,_=build_cpu_meshes(cpu(identity));self.assertFalse(any('pins-' in m.name for m in meshes))

    def test_am5_lid_has_eight_true_open_cutouts(self):
        meshes,_=build_cpu_meshes(cpu('amd_am5'));lid=next(m for m in meshes if m.name=='cpu-lid')
        caps=[lid.vertices[i:i+18] for i in range(0,len(lid.vertices),18) if lid.vertices[i+3]<-.99]
        def contains(uv,row):
            points=[(row[i+2]/40+.5,.5-row[i+1]/40) for i in (0,6,12)]
            def cross(a,b,p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
            c=[cross(points[i],points[(i+1)%3],uv) for i in range(3)]
            return min(c)>=-1e-8 or max(c)<=1e-8
        for uv in ((.29,.12),(.71,.12),(.88,.29),(.88,.71),(.71,.88),(.29,.88),(.12,.71),(.12,.29)):
            self.assertFalse(any(contains(uv,row) for row in caps),uv)
        self.assertTrue(any(contains((.5,.5),row) for row in caps))

    def test_unknown_dimension_and_stackup_status_are_honest(self):
        value=cpu('amd_tr4_family');value['cpu_package'].update(width_mm=None,length_mm=None,dimensions_status='reference')
        meshes,meta=build_cpu_meshes(value);self.assertTrue(meshes);self.assertFalse(meta['dimensions_verified'])
        self.assertFalse(meta['substrate_thickness_verified']);self.assertTrue(meta['geometry_is_reference'])
        value['cpu_package'].update(width_mm=1000,length_mm=True,dimensions_status='primary_verified',pin_count=True)
        _,meta=build_cpu_meshes(value);self.assertFalse(meta['dimensions_verified']);self.assertIsNone(meta['physical_pin_count'])
        meshes,meta=build_cpu_meshes({'cpu_package':{'id':'not-a-package'}});self.assertFalse(meshes);self.assertFalse(meta['available'])

    def test_basis_pose_rotates_once_and_invalid_text_never_enters_meshes(self):
        value=cpu('intel_lga1700_1851');value['cpu_package']['label_ascii']='<script>'
        meshes,meta=build_cpu_meshes(value,position=(1,2,3),normal=(0,1,0),up=(0,0,1))
        self.assertFalse(meta['model_mark_lines']);self.assertFalse(any(m.name=='cpu-model-mark' for m in meshes))
        lid=next(m for m in meshes if m.name=='cpu-lid');self.assertEqual(lid.position,(1.,2.,3.))
        self.assertAlmostEqual((min(lid.vertices[1::6])+max(lid.vertices[1::6]))/2,0.)

    def test_package_identity_cannot_be_reused_for_a_different_model(self):
        original=cpu('intel_lga1700_1851')
        for mutation in ({'id':'different-model'},{'style':'am5'},{'vendor':'amd'},{'confidence':'vendor'}):
            value=dict(original,**mutation);meshes,meta=build_cpu_meshes(value)
            self.assertFalse(meshes);self.assertEqual(meta['reason'],'inconsistent_model_identity')


class CpuSvgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.engine=QQmlEngine();self.warnings=[];self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/HardwareCpuPackages.js" as Cpu
import "../native/AssemblyProfiles.js" as Profiles
QtObject {
 function draw(v){const k=Shapes.key(v,"#425265");return JSON.stringify({key:k,source:Shapes.source(k),layers:Shapes.layers(k),profile:Profiles.profile(v)})}
 function shape(id){return JSON.stringify(Cpu.profile(id))}
}''',QUrl.fromLocalFile(str(ROOT/'tests/CpuPackageFixture.qml')))
        self.object=self.component.create();self.assertIsNotNone(self.object,[r.toString() for r in self.component.errors()])

    def tearDown(self):
        self.object.deleteLater();self.component.deleteLater();self.engine.deleteLater();self.app.processEvents()
        self.assertEqual(self.warnings,[])

    def evaluate(self,text):
        code=QQmlExpression(qmlContext(self.object),self.object,text);result=code.evaluate()
        self.assertFalse(code.hasError(),code.error().toString())
        return json.loads(result[0] if isinstance(result,tuple) else result)

    def drawing(self,value):return self.evaluate('draw('+json.dumps(value)+')')

    def test_python_and_js_share_all_normalized_package_contours(self):
        for identity in PACKAGE_SHAPES:
            self.assertEqual(self.evaluate('shape('+json.dumps(identity)+')'),json.loads(json.dumps(package_geometry(identity))))

    def test_all_thirteen_styles_share_mechanics_without_original_faces(self):
        ns={'s':'http://www.w3.org/2000/svg'}
        for identity in PACKAGE_SHAPES:
            paths=[];hashes=set()
            for style in HARDWARE_ICON_STYLES:
                value=cpu(identity);value['icon_set']=style;result=self.drawing(value)
                svg=unquote(result['source'].split(',',1)[1]);self.assertTrue(QSvgRenderer(svg.encode()).isValid())
                tree=ET.fromstring(svg);classes=[node.get('class','') for node in tree.iter()]
                paths.append(tuple(node.get('d') for node in tree.findall('.//s:path',ns) if node.get('class') in ('cpu-package-outline','cpu-lid-outline')))
                expressions=[c for c in classes if c in ('hardware-cartoon-expression','notebook-smile')]
                self.assertEqual(bool(expressions),style in ('cartoon','notebook_smile'))
                self.assertEqual(result['layers']['rotors'],[]);hashes.add(svg)
            self.assertTrue(paths[0]);self.assertTrue(all(p==paths[0] for p in paths));self.assertEqual(len(hashes),13)

    def test_bad_package_and_xml_labels_do_not_pass_canonical_boundary(self):
        value=cpu('amd_am5');value['cpu_package']['label_ascii']='\"/><script>'
        result=self.drawing(value);svg=unquote(result['source'].split(',',1)[1]);ET.fromstring(svg)
        self.assertNotIn('<script',svg);self.assertNotIn('script',result['key'])
        value['cpu_package']['id']='unknown';self.assertNotIn('cpu@',self.drawing(value)['key'])
        original=cpu('intel_lga1700_1851')
        for mutation in ({'id':'different-model'},{'style':'am5'},{'vendor':'amd'},{'confidence':'vendor'}):
            value=dict(original,icon_set='notebook_line',**mutation)
            result=self.drawing(value);self.assertNotIn('cpu@',result['key'])
            svg=unquote(result['source'].split(',',1)[1]);self.assertNotIn('cpu-model-mark',svg)


if __name__=='__main__':unittest.main()
