"""Ten exact GPU model studies, existing profiles and retained local rotors.

Software SVG/QML only: no window, renderer context, sampler or native API.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QCoreApplication,QEvent,QUrl
from PySide6.QtGui import QGuiApplication,QImage,QPainter
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtSvg import QSvgRenderer
from hardware_appearance import CATALOG,appearance_for
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
REPRESENTATIVES=('nvidia-founders-rtx5090-32g','nvidia-gtx1080-founders','nvidia-gtx780ti-reference',
 'msi-gtx980ti-gaming-6g','amd-reference-rx7900xtx-24g','intel-limited-arc-a770-16g',
 'asus-rog-strix-4090-oc','msi-suprim-x-4090-24g','zotac-twin-4060ti-oc-white','msi-vega64-8g-reference')
GPU_ROWS={row[0]:row for row in CATALOG if row[1]=='gpu'}


def exact(identity,style='miniature'):
    appearance=appearance_for('gpu',GPU_ROWS[identity][-1][0])
    assert appearance['id']==identity,(identity,appearance)
    return dict(appearance,icon_set=style)


def decode(source):
    return unquote(source.split(',',1)[1])


def svg_image(source,size=360):
    renderer=QSvgRenderer(decode(source).encode('utf-8'))
    if not renderer.isValid():raise AssertionError('Invalid generated SVG')
    image=QImage(size,size,QImage.Format_ARGB32_Premultiplied);image.fill(0)
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);renderer.render(painter);painter.end()
    return image


class GpuModelArt041Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        self.native=self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native API')))
        self.process=self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native/HardwareShapes.js" as Shapes
import "../native/HardwareModelDetails.js" as Details
import "../native/HardwareFanDesigns.js" as Fans
QtObject {
 function artwork(a,model) {
   const key=Shapes.key(Object.assign({},a,{model_mode:model}),"#303a48")
   return {key:key,source:Shapes.source(key),layers:Shapes.layers(key)}
 }
 function detail(state,base,rotors) {
   const before=JSON.parse(JSON.stringify(rotors))
   const output=Details.body(state,base,rotors)
   return {base:output,before:before,after:rotors}
 }
 function profile(state,index,kind){return Details.profile(state,index,kind)}
 function rotor(p,model){return model?Fans.modelRotor(p,{}):Fans.rotor(p,{})}
 function casing(base,holes){return Details.casingInk(base,holes)}
}''',QUrl.fromLocalFile(str(ROOT/'tests/GpuModelArt041Probe.qml')))
        self.probe=self.component.create()
        self.assertIsNotNone(self.probe,[e.toString() for e in self.component.errors()])

    def tearDown(self):
        self.probe.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        self.native.assert_not_called();self.process.assert_not_called()

    def evaluate(self,expression):
        query=QQmlExpression(qmlContext(self.probe),self.probe,expression)
        result=query.evaluate();self.assertFalse(query.hasError(),query.error().toString())
        result=result[0] if isinstance(result,tuple) else result
        return result.toVariant() if hasattr(result,'toVariant') else result

    def artwork(self,identity,style='miniature',model=True):
        return self.evaluate('artwork('+json.dumps(exact(identity,style))+','+str(model).lower()+')')

    def test_all_thirteen_styles_preserve_known_blade_counts_and_finite_local_planes(self):
        for identity in REPRESENTATIVES:
            appearance=exact(identity)
            expected=appearance.get('visible_fan_count') or appearance['fan_count']
            for style in HARDWARE_ICON_STYLES:
                result=self.artwork(identity,style)
                self.assertIn(identity,result['key'])
                rotors=result['layers']['rotors']
                if appearance['fan_profile']['render_ready']:
                    self.assertEqual(len(rotors),expected,(identity,style))
                else:self.assertLessEqual(len(rotors),expected,(identity,style))
                tree=ET.fromstring(decode(result['source']))
                self.assertFalse(any(node.tag.endswith(('image','script','foreignObject','filter')) for node in tree.iter()))
                for rotor in rotors:
                    self.assertTrue(all(math.isfinite(rotor[key]) for key in ('cx','cy','radius','direction')))
                    self.assertGreater(rotor['radius'],0)
                    self.assertIn(rotor['direction'],(-1,1))
                    text=decode(rotor['source'])
                    self.assertNotIn('NaN',text);self.assertNotIn('Infinity',text)
                    index=sorted(rotors,key=lambda value:value['cx']).index(rotor)
                    state=dict(kind='gpu',model_id=identity,series_id=appearance['series_id'],icon_set=style,ink='#303a48',fan_count=expected)
                    profile=self.evaluate('profile('+json.dumps(state)+','+str(index)+','+json.dumps(rotor['kind'])+')')
                    leaves=len(re.findall(r'class="hardware-fan-blade"',text))
                    if profile['blades'] is not None and profile['shape']!='neutral':
                        self.assertEqual(leaves,profile['blades'],(identity,style,index))
                    else:self.assertEqual(leaves,0,(identity,style,index))

    def test_model_details_preserve_original_retained_positions_and_directions(self):
        for identity in REPRESENTATIVES:
            for style in ('miniature','cartoon','notebook_color','notebook_line'):
                old=self.artwork(identity,style,False)['layers']['rotors']
                new=self.artwork(identity,style,True)['layers']['rotors']
                pose=lambda rows:[tuple(row[key] for key in ('cx','cy','radius','kind','direction')) for row in rows]
                self.assertEqual(pose(old),pose(new),(identity,style))

    def test_partial_collector_never_shifts_middle_fan_profile_onto_a_different_fan(self):
        identity='asus-rog-strix-4090-oc';appearance=exact(identity)
        state=dict(kind='gpu',model_id=identity,series_id=appearance['series_id'],icon_set='miniature',ink='#303a48',fan_count=3)
        rotors=[dict(cx=5.,cy=12.,radius=3.,kind='axial',basis=3,body='left-sentinel',direction=1),
                dict(cx=19.,cy=12.,radius=3.,kind='axial',basis=3,body='right-sentinel',direction=1)]
        result=self.evaluate('detail('+json.dumps(state)+',"",'+json.dumps(rotors)+')')
        self.assertEqual(result['before'],result['after'])
        state['model_id']='unreviewed-gpu'
        result=self.evaluate('detail('+json.dumps(state)+',"base-sentinel",'+json.dumps(rotors)+')')
        self.assertEqual(result['base'],'base-sentinel');self.assertEqual(result['after'],rotors)

    def test_older_unknown_blowers_and_arc_do_not_acquire_invented_blades(self):
        for identity in ('nvidia-gtx1080-founders','nvidia-gtx780ti-reference','intel-limited-arc-a770-16g'):
            self.assertFalse(exact(identity)['fan_profile']['render_ready'])
            for style in HARDWARE_ICON_STYLES:
                text=decode(self.artwork(identity,style)['source'])
                self.assertNotIn('class="hardware-fan-blade"',text,(identity,style))
                self.assertIn('hardware-model-intake-lip',text,(identity,style))

    def test_known_profiles_have_distinct_model_leaf_silhouettes_and_keep_their_caps(self):
        paths={}
        for identity in ('nvidia-founders-rtx5090-32g','asus-rog-strix-4090-oc','amd-reference-rx7900xtx-24g',
                         'msi-suprim-x-4090-24g','zotac-twin-4060ti-oc-white','msi-vega64-8g-reference'):
            result=self.artwork(identity)
            text=decode(result['layers']['rotors'][0]['source'])
            tree=ET.fromstring(text)
            paths[identity]=next(node.get('d') for node in tree.iter() if node.get('class')=='hardware-fan-blade')
            if identity=='amd-reference-rx7900xtx-24g':
                hub=next(node for node in tree.iter() if node.get('class')=='hardware-fan-hub')
                self.assertTrue(hub.tag.endswith('path'))
            if identity=='msi-suprim-x-4090-24g':self.assertIn('hardware-model-cap-finish',text)
        self.assertEqual(len(set(paths.values())),len(paths))
        text=decode(self.artwork('msi-gtx980ti-gaming-6g')['layers']['rotors'][0]['source'])
        leaves=[node.get('d') for node in ET.fromstring(text).iter() if node.get('class')=='hardware-fan-blade']
        self.assertEqual(len(leaves),14);self.assertEqual(len(set(leaves)),2)
        self.assertEqual(leaves[::2],[leaves[0]]*7);self.assertEqual(leaves[1::2],[leaves[1]]*7)

    def test_actual_large_svg_is_valid_nonempty_and_preserves_transparent_exterior(self):
        for identity in REPRESENTATIVES:
            for style in ('miniature','cartoon','notebook_color','notebook_line'):
                image=svg_image(self.artwork(identity,style)['source'])
                self.assertEqual(image.pixelColor(0,0).alpha(),0)
                count=sum(image.pixelColor(x,y).alpha()>0 for x in range(0,360,4) for y in range(0,360,4))
                self.assertGreater(count,100,(identity,style))

    def test_static_and_retained_zero_degree_assets_reassemble_identical_pixels(self):
        for identity in REPRESENTATIVES:
            for style in ('miniature','cartoon','notebook_color','notebook_line'):
                result=self.artwork(identity,style)
                layers=result['layers'];base=decode(layers['baseSource'])
                fragments=[]
                for rotor in layers['rotors']:
                    local=decode(rotor['source']).split('>',1)[1].rsplit('</svg>',1)[0]
                    fragments.append('<g transform="translate('+str(rotor['cx'])+' '+str(rotor['cy'])+') scale('+str(rotor['radius']/3)+')">'+local+'</g>')
                combined=base.rsplit('</svg>',1)[0]+''.join(fragments)+'</svg>'
                rebuilt='data:image/svg+xml;utf8,'+combined
                self.assertEqual(svg_image(result['source']),svg_image(rebuilt),(identity,style))

    def test_casing_clip_removes_only_intersections_and_keeps_external_pcb_branch(self):
        # One path mixes a crossing casing stroke and a PCB branch beyond the
        # cover, but within the complete viewBox. Clipping to the cover itself
        # would wrongly discard the second subpath.
        circle='<circle cx="12" cy="12" r="3" fill="none" stroke="#303a48"/>'
        filled='<path d="M0 0H24V24H0Z" fill="#fffef9"/>'
        untouched='<path d="M1 2L4 3Q5 3 6 2" fill="none" stroke="#303a48" stroke-width=".2"/>'
        mixed='<path d="M2 12H22M2 20H22" fill="none" stroke="#303a48" stroke-width=".2"/>'
        output=self.evaluate('casing('+json.dumps(filled+circle+untouched+mixed)+',[{cx:12,cy:12,radius:3}])')
        self.assertIn(filled,output);self.assertIn(circle,output);self.assertIn(untouched,output)
        self.assertIn('M2 20H22',output)
        self.assertNotIn('M2 12H22',output)
        tree=ET.fromstring('<svg>'+output+'</svg>')
        clipped=next(node for node in tree if node.get('data-model-casing-clip'))
        segments=re.findall(r'M([-+.0-9]+) ([-+.0-9]+)L([-+.0-9]+) ([-+.0-9]+)',clipped.get('d'))
        self.assertEqual(len(segments),2)
        self.assertLess(float(segments[0][2]),8.9);self.assertGreater(float(segments[1][0]),15.1)
        # A nonuniform parent transform keeps the path local, while its wider
        # world-space pen width supplies a safe aperture margin.
        transformed='<g transform="matrix(2 0 0 .5 2 6)"><path d="M0 12H10" fill="none" stroke="#303a48" stroke-width=".4"/></g>'
        output=self.evaluate('casing('+json.dumps(transformed)+',[{cx:12,cy:12,radius:3}])')
        self.assertIn('matrix(2 0 0 .5 2 6)',output)
        d=next(ET.fromstring('<svg>'+output+'</svg>').iter('path')).get('d')
        segments=re.findall(r'M([-+.0-9]+) ([-+.0-9]+)L([-+.0-9]+) ([-+.0-9]+)',d)
        self.assertLess(float(segments[0][2])*2+2,8.6)
        self.assertGreater(float(segments[1][0])*2+2,15.4)

    def test_hand_model_static_casing_stays_outside_rotating_strix_apertures(self):
        for style in ('notebook_line','notebook_color','sketch','inkwash'):
            result=self.artwork('asus-rog-strix-4090-oc',style)
            layers=result['layers'];base=decode(layers['baseSource'])
            image=svg_image(layers['baseSource'],480)
            for rotor in layers['rotors']:
                for x in range(-7,8):
                    for y in range(-7,8):
                        if x*x+y*y>=49:continue
                        px=round((rotor['cx']+x*rotor['radius']*.1)*20)
                        py=round((rotor['cy']+y*rotor['radius']*.1)*20)
                        color=image.pixelColor(px,py)
                        # Sketch deliberately keeps its original paper-filled
                        # circular opening. Test missing casing ink, not the
                        # removal of that legitimate fixed paper surface.
                        self.assertTrue(color.alpha()==0 or min(color.red(),color.green(),color.blue())>220,(style,x,y,color.name()))
            if style.startswith('notebook_'):self.assertIn('data-model-casing-clip',base)
        for style in ('notebook_color','notebook_line','sketch','inkwash'):
            text=decode(self.artwork('zotac-twin-4060ti-oc-white',style)['layers']['baseSource'])
            self.assertIn('hardware-model-twin-edge-band',text)

    def test_all_reviewed_gpu_hand_models_keep_valid_original_fan_planes(self):
        changed=0
        for identity in GPU_ROWS:
            for style in ('notebook_line','sketch','inkwash'):
                old=self.artwork(identity,style,False)['layers']
                new=self.artwork(identity,style,True)['layers']
                pose=lambda rows:[tuple(row[key] for key in ('cx','cy','radius','kind','direction')) for row in rows]
                self.assertEqual(pose(old['rotors']),pose(new['rotors']),(identity,style))
                base=decode(new['baseSource']);ET.fromstring(base)
                self.assertNotIn('NaN',base);self.assertNotIn('Infinity',base)
                changed+='data-model-casing-clip' in base
        self.assertGreater(changed,20)

    def test_detail_functions_have_no_clock_sampling_or_external_assets(self):
        source=(ROOT/'native/HardwareModelDetails.js').read_text(encoding='utf-8')
        for forbidden in ('Date.now','Timer {','XMLHttpRequest','fetch(','Qt.createQmlObject','file://','http://','https://'):
            self.assertNotIn(forbidden,source)
        for filename in ('HardwareModelDetails.js','HardwareFanDesigns.js'):
            source=(ROOT/'native'/filename).read_text(encoding='utf-8')
            self.assertNotIn('<image',source)


if __name__=='__main__':unittest.main()
