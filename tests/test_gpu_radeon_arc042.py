"""Exact Radeon/Arc static model contours: source geometry and software pixels.

No live Runtime, native window, GL context, hardware polling or added clock.
"""
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
from hardware_board_details import for_appearance
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
APPEARANCES={a['id']:a for r in CATALOG if r[1]=='gpu'
             for a in [appearance_for('gpu',r[-1][0])] if a['vendor'] in ('amd','intel')}
#0.43 reviewed both BIOSTAR official front images independently.
UNKNOWN_EXTERIORS=set()
MAIN_STYLES=('miniature','cartoon','notebook_color','notebook_line')


def decode(source):return unquote(source.split(',',1)[1])


def svg_image(source,size=360):
    renderer=QSvgRenderer(decode(source).encode('utf-8'))
    if not renderer.isValid():raise AssertionError('Invalid generated SVG')
    image=QImage(size,size,QImage.Format_ARGB32_Premultiplied);image.fill(0)
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);renderer.render(painter);painter.end()
    return image


def path_tokens(path):
    return [float(token) if not re.fullmatch('[a-zA-Z]',token) else token
            for token in re.findall(r'[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?',path)]


class RadeonArcGpu042Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        self.native=self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native API')))
        self.process=self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        self.engine=QQmlEngine();self.warnings=[];self.objects=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.probe=self.create('''import QtQml
import "../native/HardwareModelRadeonArc042.js" as Records
import "../native/HardwareSolid.js" as Solid
import "../native/HardwareBoardDesigns.js" as Board
import "../native/HardwareNotebook.js" as Notebook
import "../native/HardwareSketch.js" as Sketch
QtObject {
 function rows(){return Records.records()}
 function profile(s){return Records.profile(s)}
 function lazy(){return Records.rows===null}
 function shared(a,b){return Records.records()[a].traces===Records.records()[b].traces}
 function front(a) {
   const s={kind:"gpu",model_id:a.id,series_id:a.series_id,board_vendor:a.board_vendor,
     fan_count:a.fan_count,style:a.style,ink:"#303a48"}
   const g=Solid.geometry(s),c=Board.colors(s,Solid.palette(s))
   const z=Object.assign({},g,{x:0,y:0,w:100,h:100})
   z.centers=g.centers.map(x=>(x-g.x)/g.w*100)
   return {shapes:Notebook.sourceShapes(Solid.front(s,z,c)),geometry:g}
 }
 function study(a,model) {
   const s={kind:"gpu",model_id:a.id,series_id:a.series_id,board_vendor:a.board_vendor,
     fan_count:a.fan_count,style:a.style,ink:"#303a48",model_mode:model,icon_set:"notebook_line"}
   const g=Solid.geometry(s),c=Board.colors(s,Solid.palette(s)),front=Solid.front(s,g,c)
   c.ink=s.ink
   const first=Notebook.sourceShapes(front)[0],scale=Math.sqrt(Math.abs(first.m[0]*first.m[3]-first.m[1]*first.m[2]))||1
   const value=Notebook.shapeStudy(s,g,c,front,Notebook.fanLayout(s,g))
   return {d:value.d,m:value.m,polygon:Notebook.casePolygon(value),geometry:g,
     expectedLegacy:Sketch.wobblyPath(first.d,a.id+":case",.22/scale,2.2/scale)}
 }
}''')

    def create(self,source):
        component=QQmlComponent(self.engine)
        component.setData(source.encode(),QUrl.fromLocalFile(str(ROOT/'tests/RadeonArc042Probe.qml')))
        probe=component.create();self.assertIsNotNone(probe,[e.toString() for e in component.errors()])
        self.objects.extend([probe,component]);return probe

    def tearDown(self):
        for obj in self.objects:obj.deleteLater()
        self.engine.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        self.native.assert_not_called();self.process.assert_not_called()

    def evaluate(self,expression,probe=None):
        probe=probe or self.probe
        query=QQmlExpression(qmlContext(probe),probe,expression)
        result=query.evaluate();self.assertFalse(query.hasError(),query.error().toString())
        result=result[0] if isinstance(result,tuple) else result
        return result.toVariant() if hasattr(result,'toVariant') else result

    def artwork_probe(self):
        return self.create('''import QtQml
import "../native/HardwareShapes.js" as Shapes
QtObject {
 function artwork(a,model){
   const key=Shapes.key(Object.assign({},a,{model_mode:model}),"#303a48")
   return {key:key,source:Shapes.source(key),layers:Shapes.layers(key)}
 }
}''')

    def artwork(self,probe,identity,style,model=True):
        value=dict(APPEARANCES[identity],icon_set=style)
        return self.evaluate('artwork('+json.dumps(value)+','+str(model).lower()+')',probe)

    def test_complete_exact_inventory_and_safe_identity_guards(self):
        rows=self.evaluate('rows()')
        self.assertEqual(set(rows),set(APPEARANCES));self.assertEqual(len(rows),55)
        self.assertEqual(sum(a['vendor']=='amd' for a in APPEARANCES.values()),46)
        self.assertEqual(sum(a['vendor']=='intel' for a in APPEARANCES.values()),9)
        for identity,a in APPEARANCES.items():
            row=rows[identity];state=dict(kind='gpu',model_id=identity,series_id=a['series_id'])
            self.assertEqual(self.evaluate('profile('+json.dumps(state)+')'),row)
            for patch_value in ({'kind':'cpu'},{'model_id':'unknown-gpu'},{'series_id':'other-series'}):
                self.assertIsNone(self.evaluate('profile('+json.dumps(dict(state,**patch_value))+')'))
            self.assertEqual(row['profile_ref'],identity);self.assertEqual(row['recipe'],for_appearance(a)['recipe'])

    def test_fresh_engine_keeps_large_directory_lazy_for_cpu_nvidia_and_invalid_input(self):
        self.assertTrue(self.evaluate('lazy()'))
        for value in (None,{},dict(kind='cpu',model_id='sapphire-pulse-7600',series_id='sapphire_pulse'),
                      dict(kind='gpu',model_id='nvidia-founders-rtx5090-32g',series_id='nvidia_founders'),
                      dict(kind='gpu',model_id='unknown-gpu',series_id='sapphire_pulse'),
                      dict(kind='gpu',model_id='sapphire-pulse-7600',series_id=None)):
            self.assertIsNone(self.evaluate('profile('+json.dumps(value)+')'))
            self.assertTrue(self.evaluate('lazy()'),value)
        row=self.evaluate('profile({kind:"gpu",model_id:"sapphire-pulse-7600",series_id:"sapphire_pulse"})')
        self.assertEqual(row['profile_ref'],'sapphire-pulse-7600');self.assertFalse(self.evaluate('lazy()'))

    def test_fan_references_are_audit_metadata_without_invented_telemetry(self):
        rows=self.evaluate('rows()')
        for identity,a in APPEARANCES.items():
            row=rows[identity];fan=row['fan_ref']
            self.assertEqual(set(fan),{'series_id','physical_count','front_count','profile_status'})
            self.assertEqual(fan['series_id'],a['series_id'])
            self.assertEqual(fan['physical_count'],a['fan_count'])
            self.assertEqual(fan['front_count'],a['visible_fan_count'])
            self.assertEqual(fan['profile_status'],a['fan_profile']['artwork_status'])
            self.assertIn('pcb_internal',row['unknown']);self.assertIn('absolute_rotation',row['unknown'])
            if fan['profile_status']=='pending':self.assertIn('fan_blade_geometry',row['unknown'])
            if a['fan_count']==0:
                self.assertEqual(fan['profile_status'],'not_applicable')
                self.assertNotIn('fan_blade_geometry',row['unknown'])
            self.assertTrue(row['sources']);self.assertTrue(all(url.startswith('https://') for url in row['sources']))
            self.assertIn(a['source_url'],row['sources'])

    def test_contours_match_existing_exact_cover_primitives_not_generic_decorations(self):
        rows=self.evaluate('rows()')
        for identity,a in APPEARANCES.items():
            row=rows[identity]
            if identity in UNKNOWN_EXTERIORS:
                self.assertEqual(row['traces'],[]);self.assertIn('casing_geometry',row['unknown']);continue
            self.assertGreaterEqual(len(row['traces']),2);self.assertLessEqual(len(row['traces']),6)
            front=self.evaluate('front('+json.dumps(a)+')')['shapes']
            for trace in row['traces']:
                self.assertIn(trace['role'],('edge','material','trim','vent'))
                self.assertGreaterEqual(trace['width'],.08);self.assertLessEqual(trace['width'],.14)
                self.assertTrue((ROOT/trace['source_field'].split(':',1)[0]).is_file())
                self.assertTrue(all(math.isfinite(t) for t in path_tokens(trace['d']) if isinstance(t,float)))
                slots=re.search(r'/sourceShapes\[([0-9,]+)\]',trace['source_field'])
                if not slots:
                    self.assertIn('/all5petals-baked',trace['source_field']);continue
                original=''.join(front[int(index)]['d'] for index in slots.group(1).split(','))
                expected=path_tokens(original);actual=path_tokens(trace['d'])
                self.assertEqual(len(actual),len(expected),(identity,trace['source_field']))
                for got,want in zip(actual,expected):
                    if isinstance(want,str):self.assertEqual(got,want)
                    else:self.assertAlmostEqual(got,want,places=6)

    def test_sakura_factory_print_rotation_is_baked_without_extra_fans(self):
        rows=self.evaluate('rows()')
        for identity in ('powercolor-hellhound-7800xt-sakura','powercolor-hellhound-7800xt-sakura-limited'):
            flowers=[t for t in rows[identity]['traces'] if '/all5petals-baked' in t['source_field']]
            self.assertEqual(len(flowers),2)
            for trace in flowers:
                tokens=path_tokens(trace['d']);self.assertEqual(tokens.count('M'),5);self.assertEqual(tokens.count('Z'),5)
                starts=[i for i,t in enumerate(tokens) if t=='M']
                center=(64,10) if '(64,10' in trace['source_field'] else (29,88)
                size=.6 if center==(64,10) else .28
                for petal,start in enumerate(starts):
                    self.assertEqual(tokens[start+1:start+3],list(center))
                    angle=math.radians(petal*72)
                    # First actual C control point from the original printed
                    # petal, rotated about its own print center, not a rotor.
                    x=center[0]+size*(-2*math.cos(angle)+2*math.sin(angle))
                    y=center[1]+size*(-2*math.sin(angle)-2*math.cos(angle))
                    self.assertAlmostEqual(tokens[start+4],x,places=6)
                    self.assertAlmostEqual(tokens[start+5],y,places=6)
            self.assertEqual(rows[identity]['fan_ref']['front_count'],3)

    def test_shared_physical_fronts_reuse_arrays_but_keep_exact_variant_guards(self):
        for first,second in (
            ('sparkle-a750-titan-8g-oc','sparkle-a770-titan-16g-oc'),
            ('sparkle-b580-titan-12g-oc','sparkle-b580-titan-luna-12g-oc'),
            ('sapphire-nitro-9070xt-phantomlink','sapphire-nitro-9070xt-phantomlink-polar'),
            ('sapphire-nitro-9070xt-valor-mortis','sapphire-nitro-9070xt-crimson-desert'),
            ('powercolor-red-devil-7800xt-limited','powercolor-red-devil-7800xt-bp'),
            ('powercolor-hellhound-7800xt-sakura','powercolor-hellhound-7800xt-sakura-limited')):
            self.assertTrue(self.evaluate('shared('+json.dumps(first)+','+json.dumps(second)+')'))
        rows=self.evaluate('rows()')
        self.assertNotEqual(rows['sparkle-b580-roc-luna-12g-oc-ultra']['traces'],rows['sparkle-b580-titan-luna-12g-oc']['traces'])
        lcd=rows['asrock-taichi-rx9070xt-white-16g-oc']
        self.assertTrue(any(min(t for t in path_tokens(trace['d']) if isinstance(t,float))<0 for trace in lcd['traces']))
        self.assertEqual(lcd['fan_ref']['front_count'],3)
        external=[(identity,trace) for identity,row in rows.items() for trace in row['traces'] if trace.get('feature')]
        self.assertEqual(len(external),1)
        self.assertEqual(external[0][0],'asrock-taichi-rx9070xt-white-16g-oc')
        self.assertEqual(external[0][1]['feature'],'external_display')
        self.assertEqual(external[0][1]['source_field'],'native/HardwareVariantGroupB.js:b_taichi9070_white_lcd/sourceShapes[4,5]')

    def test_all_current_styles_use_exact_model_records_without_moving_fan_planes(self):
        probe=self.artwork_probe();rows=self.evaluate('rows()');styles=tuple(HARDWARE_ICON_STYLES)
        self.assertEqual(len(styles),13)
        for identity in APPEARANCES:
            visible_contours=0
            for style in styles:
                new=self.artwork(probe,identity,style)
                ET.fromstring(decode(new['source']))
                base=decode(new['layers']['baseSource'])
                if 'class="hardware-model-sku-contours"' in base:visible_contours+=1
                self.assertNotIn('NaN',base);self.assertNotIn('Infinity',base)
                self.assertNotIn('<image',base);self.assertNotIn('source_field',base)
                if style not in MAIN_STYLES:continue
                old=self.artwork(probe,identity,style,False)
                pose=lambda layers:[tuple(r[key] for key in ('cx','cy','radius','kind','direction')) for r in layers['rotors']]
                self.assertEqual(pose(new['layers']),pose(old['layers']),(identity,style))
                image=svg_image(new['source'])
                self.assertEqual(image.pixelColor(0,0).alpha(),0)
                self.assertGreater(sum(image.pixelColor(x,y).alpha()>0 for x in range(0,360,6) for y in range(0,360,6)),50)
            if rows[identity]['traces']:self.assertGreater(visible_contours,0,identity)
            else:self.assertEqual(visible_contours,0,identity)

    def test_all_exact_static_assets_equal_retained_zero_degree_in_four_main_styles(self):
        probe=self.artwork_probe()
        for identity in APPEARANCES:
            for style in MAIN_STYLES:
                output=self.artwork(probe,identity,style);layers=output['layers'];base=decode(layers['baseSource'])
                fragments=[]
                for rotor in layers['rotors']:
                    inner=decode(rotor['source']).split('>',1)[1].rsplit('</svg>',1)[0]
                    fragments.append('<g transform="translate('+str(rotor['cx'])+' '+str(rotor['cy'])+') scale('+str(rotor['radius']/3)+')">'+inner+'</g>')
                rebuilt='data:image/svg+xml;utf8,'+base.rsplit('</svg>',1)[0]+''.join(fragments)+'</svg>'
                self.assertEqual(svg_image(output['source'],240),svg_image(rebuilt,240),(identity,style))

    def test_taichi_white_lcd_keeps_its_real_protruding_unlit_frame_in_hand_styles(self):
        probe=self.artwork_probe();identity='asrock-taichi-rx9070xt-white-16g-oc'
        geometry=self.evaluate('front('+json.dumps(APPEARANCES[identity])+')')['geometry']
        # Original closed source panel: x77..95.5 / y-5.4..2.4. A portion above
        # the primary shroud is an actual LCD frame, not a floating cover line.
        left=geometry['x']+geometry['w']*.77;right=geometry['x']+geometry['w']*.955
        top=geometry['y']-geometry['h']*.054;bottom=geometry['y']-.30
        for style in HARDWARE_ICON_STYLES:
            base=decode(self.artwork(probe,identity,style)['layers']['baseSource'])
            self.assertEqual(base.count('data-model-feature="external_display"'),1,style)
        for style in ('notebook_line','notebook_color','notebook_smile','inkwash'):
            output=self.artwork(probe,identity,style)
            image=svg_image(output['layers']['baseSource'],480)
            count=sum(image.pixelColor(x,y).alpha()>0
                      for x in range(math.ceil(left*20),math.floor(right*20))
                      for y in range(math.ceil(top*20),math.floor(bottom*20)))
            self.assertGreater(count,10,(style,count))

    def test_yeston_model_cover_includes_real_ribbon_corners_without_changing_topbar_study(self):
        appearance=APPEARANCES['yeston-sakura-rx7800xt-16g']
        old=self.evaluate('study('+json.dumps(appearance)+',false)')
        model=self.evaluate('study('+json.dumps(appearance)+',true)')
        self.assertEqual(old['d'],old['expectedLegacy'])
        self.assertNotEqual(model['d'],old['d'])
        g=model['geometry']
        for x,y in ((0,4),(100,4),(100,98),(0,98)):
            expected=(g['x']+g['w']*x/100,g['y']+g['h']*y/100)
            self.assertTrue(any(abs(px-expected[0])<1e-6 and abs(py-expected[1])<1e-6 for px,py in model['polygon']),expected)
        probe=self.artwork_probe()
        for style in ('notebook_line','notebook_color','notebook_smile','inkwash'):
            output=self.artwork(probe,appearance['id'],style)
            self.assertEqual(len(output['layers']['rotors']),3)

    def test_data_module_has_no_runtime_work_or_telemetry_fields(self):
        source=(ROOT/'native/HardwareModelRadeonArc042.js').read_text(encoding='utf-8')
        for token in ('.import','Date.now','setInterval','setTimeout','Timer {','fetch(','XMLHttpRequest','<image','<filter','rpm','rotation_direction'):
            self.assertNotIn(token,source)


if __name__=='__main__':unittest.main()
