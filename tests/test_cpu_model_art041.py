"""Retained CPU model artwork: actual JS/QtSvg, no devices or native windows."""
import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PySide6.QtCore import QUrl,Qt
from PySide6.QtGui import QFontDatabase,QGuiApplication,QImage,QPainter
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtSvg import QSvgRenderer

from cpu_catalog import MODELS,PACKAGE_IDS
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
SVG='http://www.w3.org/2000/svg'


class CpuModelArt041Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'
        # Windows' offscreen platform can expose no fonts at all. Register
        # existing system faces in this test process; never install font files
        # or accept empty/tofu glyphs as evidence of readable product artwork.
        if os.name=='nt' and 'Segoe UI' not in QFontDatabase.families():
            folder=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','seguisb.ttf','segoeuib.ttf'):
                if (folder/name).is_file():
                    assert QFontDatabase.addApplicationFont(str(folder/name))>=0
            assert 'Segoe UI' in QFontDatabase.families(),'Software art verification requires an available system typeface'

    def setUp(self):
        self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native/device API')))
        self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No processes')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQml
import "../native/HardwareCpuModel.js" as Model
import "../native/HardwareCpuPackages.js" as Cpu
QtObject {
 function draw(v){return Model.modelBody(v)}
 function contours(v){return JSON.stringify(Cpu.paths(v))}
 function profile(id){return JSON.stringify(Cpu.profile(id))}
 function old(v){return Cpu.body(v)}
 function insets(v){return JSON.stringify(Model.lidInsetPoints(v[0],v[1]))}
 function family(v){return Model.familyMark(v)}
}''',QUrl.fromLocalFile(str(ROOT/'tests/CpuModelArt041Fixture.qml')))
        self.object=self.component.create()
        self.assertIsNotNone(self.object,[e.toString() for e in self.component.errors()])

    def tearDown(self):
        self.object.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        self.app.processEvents();self.assertEqual(self.warnings,[])

    def call(self,function,value):
        expression=QQmlExpression(qmlContext(self.object),self.object,function+'('+json.dumps(value)+')')
        result=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return result[0] if isinstance(result,tuple) else result

    def drawing(self,row,style='miniature',ink='#425564'):
        body=self.call('draw',dict(cpu_package=row['cpu_package'],icon_set=style,ink=ink))
        source='<svg xmlns="'+SVG+'" viewBox="0 0 24 24">'+body+'</svg>'
        return source,ET.fromstring(source)

    @staticmethod
    def raster(source,size=240):
        renderer=QSvgRenderer(source.encode());assert renderer.isValid()
        image=QImage(size,size,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
        painter=QPainter(image)
        try:renderer.render(painter)
        finally:painter.end()
        return image

    def test_all_seventy_five_cpu_labels_render_in_all_thirteen_styles_with_bounded_svg(self):
        self.assertEqual(len(MODELS),75);self.assertEqual(len(PACKAGE_IDS),7)
        for row in MODELS:
            for style in HARDWARE_ICON_STYLES:
                with self.subTest(model=row['id'],style=style):
                    source,root=self.drawing(row,style)
                    self.assertTrue(QSvgRenderer(source.encode()).isValid())
                    self.assertLessEqual(len(source.encode()),8192)
                    self.assertLessEqual(len(list(root.iter())),32)
                    self.assertLessEqual(len(root.findall('.//{'+SVG+'}path')),16)
                    self.assertNotIn('NaN',source);self.assertNotIn('Infinity',source)
                    texts=[node.text for node in root.findall('.//{'+SVG+'}text')]
                    label=row['cpu_package']['label_ascii']
                    self.assertEqual(texts[0],row['cpu_package']['vendor'].upper())
                    self.assertEqual(texts[-1],label.split()[-1])
                    self.assertEqual(len(texts),3)
                    self.assertNotIn(label,texts)
                    for tag in ('image','filter','animate','animateTransform','foreignObject'):
                        self.assertFalse(root.findall('.//{'+SVG+'}'+tag))

    def test_every_style_preserves_exact_shared_package_and_lid_paths_for_all_seven_families(self):
        examples={row['cpu_package']['id']:row for row in MODELS}
        self.assertEqual(set(examples),set(PACKAGE_IDS))
        for identity,row in examples.items():
            contour=json.loads(self.call('contours',row['cpu_package']))
            for style in HARDWARE_ICON_STYLES:
                _source,root=self.drawing(row,style)
                paths={node.get('class'):node.get('d') for node in root.findall('.//{'+SVG+'}path')}
                self.assertEqual(paths['cpu-model-package-outline'],contour['package']['d'])
                self.assertEqual(paths['cpu-model-lid-outline'],contour['lid']['d'])

    def test_faces_exist_only_in_the_two_opt_in_cute_styles(self):
        for style in HARDWARE_ICON_STYLES:
            _source,root=self.drawing(MODELS[0],style)
            classes={node.get('class') for node in root.iter()}
            self.assertEqual('cpu-model-cute-face' in classes,style in ('cartoon','notebook_smile'))

    def test_handdrawn_styles_change_contours_and_use_bounded_retracing(self):
        row=next(row for row in MODELS if row['cpu_package']['id']=='amd_am5')
        raster_hashes=set()
        for style in HARDWARE_ICON_STYLES:
            source,root=self.drawing(row,style)
            hand=[node for node in root.findall('.//{'+SVG+'}path') if node.get('class')=='cpu-model-hand-contour']
            self.assertEqual(bool(hand),style in ('sketch','notebook_line','notebook_color','notebook_smile','inkwash'))
            if hand:self.assertTrue(any('Q' in node.get('d','') for node in hand))
            image=self.raster(source)
            raster_hashes.add(hashlib.sha256(bytes(image.constBits())).hexdigest())
        self.assertEqual(len(raster_hashes),13)

    def test_lid_rims_carrier_and_index_are_reference_only_without_coolers_or_contact_arrays(self):
        examples={row['cpu_package']['id']:row for row in MODELS}
        for identity,row in examples.items():
            source,root=self.drawing(row)
            group=root.find('{'+SVG+'}g')
            self.assertEqual(group.get('data-detail-status'),'original-reference')
            self.assertEqual(group.get('data-view'),'top')
            self.assertEqual('cpu-model-carrier-reference' in source,identity in ('amd_tr4_family','amd_str5'))
            for token in ('heatpipe','cpu-fan','backside','smd-array','pin-map','serial-number'):
                self.assertNotIn(token,source)

    def test_small_large_and_light_dark_rasters_keep_real_alpha_outside_the_cpu(self):
        examples={row['cpu_package']['id']:row for row in MODELS}
        for row in examples.values():
            for size in (240,360):
                for style,ink in (('miniature','#425564'),('notebook_line','#e7edf2')):
                    source,_root=self.drawing(row,style,ink);image=self.raster(source,size)
                    self.assertEqual(image.pixelColor(0,0).alpha(),0)
                    self.assertEqual(image.pixelColor(size-1,size-1).alpha(),0)
                    self.assertGreater(image.pixelColor(size//2,size//2).alpha(),200)

    def test_unknown_packages_mismatched_vendors_and_injected_labels_stay_safe(self):
        self.assertEqual(self.call('draw',{'cpu_package':{'id':'unknown'}}),'')
        package=dict(MODELS[0]['cpu_package'],vendor='amd')
        self.assertEqual(self.call('draw',{'cpu_package':package}),'')
        package=dict(MODELS[0]['cpu_package'],label_ascii='\"/><script>')
        source=self.call('draw',{'cpu_package':package,'icon_set':'miniature','ink':'\" onload="bad'})
        ET.fromstring('<svg>'+source+'</svg>')
        self.assertNotIn('<script',source);self.assertNotIn('onload',source)
        self.assertNotIn('<text',source)


if __name__=='__main__':unittest.main()
