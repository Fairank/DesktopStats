"""Real QML coloured notebook geometry and software pixels, no native UI/GL."""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QObject,QUrl,QSizeF,QCoreApplication,QEvent
from PySide6.QtGui import QImage,QColor,QOpenGLContext
from PySide6.QtWidgets import QApplication
from PySide6.QtQuick import QQuickRenderControl,QQuickRenderTarget,QQuickWindow,QSGRendererInterface,QQuickItem
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtTest import QTest
from hardware_appearance import CATALOG,appearance_for

ROOT=Path(__file__).resolve().parents[1]
GPU_ROWS={r[0]:r for r in CATALOG if r[1]=='gpu'}
REPRESENTATIVES=('asus-astral-5090','amd-reference-rx7900xtx-24g','intel-limited-arc-a770-16g')


def decode(uri):return unquote(uri.split(',',1)[1])


def dense_ink_contract():
    """Read the finite reviewed table; never approximate a changed contour."""
    values={};coverage=None
    for line in (ROOT/'native/HardwareDenseInk052.js').read_text(encoding='utf8').splitlines():
        if line.startswith('    case '):
            key,value=line[9:].split(':return ',1)
            radius,original=json.loads(key).split('|',1)
            trimmed=json.loads(value.rstrip(';'))
            if trimmed in values and values[trimmed]!=(float(radius),original):
                raise AssertionError('Ambiguous dense-ink inverse')
            values[trimmed]=(float(radius),original)
        elif line.startswith('function coverage() {return '):
            coverage=json.loads(line[len('function coverage() {return '):-1])
    if coverage is None or len(values)!=coverage['templates']:
        raise AssertionError('Complete generated dense-ink declaration required')
    return values,{row['id']:row for row in coverage['covered']}


DENSE_TRIMS,DENSE_MODELS=dense_ink_contract()


def physical_tree(source,*,dense_identity=None,normalized=None):
    """Keep every contour/plane, reversing only declared cap-occluded ink.

    The 052 dense table clips invisible roots under a round hub and changes
    two pen widths. Its independent curve/cap tests remain in test_dense_ink052.
    Only exact tagged paths from that table may map back to the source curve;
    model, leaf counts, rotations, centres and every other attribute stay locked.
    """
    model=DENSE_MODELS.get(dense_identity)
    radii={row['hub_radius'] for row in model['rotors']} if model else set()
    def visit(node):
        classes=node.get('class','').split()
        if 'hardware-notebook-pencil' in classes or any(c.startswith('hardware-notebook-color-') for c in classes):return None
        attributes=dict(node.attrib)
        if classes:attributes['class']=' '.join(c for c in classes if c not in ('notebook_color','notebook_line'))
        if model and 'hardware-fan-blade' in classes and attributes.get('data-contour')=='cap-occluded-source-leading-edge-and-tip':
            if attributes.get('stroke-width')!='.15' or attributes.get('fill')!='none':
                raise AssertionError('Exact declared dense leaf pen required')
            radius,original=DENSE_TRIMS[attributes['d']]
            if radius not in radii:raise AssertionError('Unreviewed model/hub template')
            attributes.update(d=original,**{'stroke-width':'0.18','data-contour':'open-source-leading-edge-and-tip'})
            if normalized is not None:normalized['leaves']+=1
        if model and 'hardware-fan-hub' in classes and attributes.get('stroke-width')=='.16':
            if float(attributes['r']) not in radii or attributes.get('fill')!='none':
                raise AssertionError('Exact declared dense hub required')
            attributes['stroke-width']='0.18'
            if normalized is not None:normalized['hubs']+=1
        children=[visit(child) for child in node]
        return node.tag,attributes,node.text,tuple(child for child in children if child is not None)
    return visit(ET.fromstring(source))


class NotebookColor046Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        assert cls.app.platformName()=='offscreen'
        QQuickWindow.setGraphicsApi(QSGRendererInterface.Software)
    def setUp(self):
        for target in ('ctypes.WinDLL','subprocess.Popen','threading.Thread.start','socket.socket'):
            self.enterContext(patch(target,side_effect=AssertionError('No native UI, collector, network or worker')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
import "../native/HardwareShapes.js" as Shapes
import "../native/MetricEffectClock.js" as Clock
Item {
 id:root;width:320;height:180
 property var card:({})
 function clockCount(){return Clock.activeWindowCount()}
 function artwork(value){const key=Shapes.key(Object.assign({},value,{model_mode:true}),"#1f242b");return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)})}
 function generic(style){return Shapes.genericSource("gpu","#1f242b",false,style)}
 Product.HardwareGlyph {id:glyph;objectName:"color046Glyph";anchors.fill:parent
  modelMode:true;appearance:root.card;ink:"#1f242b";fanMotionEnabled:false;fanRotation:0}
}''',QUrl.fromLocalFile(str(ROOT/'tests/_notebook_color046_fixture.qml')))
        self.item=self.component.create();self.assertIsNotNone(self.item,[e.toString() for e in self.component.errors()])
        self.control=None;self.window=None
    def tearDown(self):
        if self.control is not None:
            self.control.invalidate();self.item.setParentItem(None);self.window.deleteLater();self.control.deleteLater()
        self.item.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[]);self.assertEqual(self.app.topLevelWindows(),[])
    def evaluate(self,code):
        exp=QQmlExpression(qmlContext(self.item),self.item,code);result=exp.evaluate()
        self.assertFalse(exp.hasError(),exp.error().toString())
        return result[0] if isinstance(result,tuple) else result
    def appearance(self,identity,style):
        row=GPU_ROWS[identity];value=appearance_for('gpu',row[-1][0]);self.assertEqual(value['id'],identity)
        return dict(value,icon_set=style)
    def drawing(self,identity,style):
        return json.loads(self.evaluate('artwork('+json.dumps(self.appearance(identity,style))+')'))
    def walk(self):
        pending=[self.item];seen={}
        while pending:
            obj=pending.pop()
            if id(obj) in seen:continue
            seen[id(obj)]=obj;yield obj;pending.extend(obj.children())
            if isinstance(obj,QQuickItem):pending.extend(obj.childItems())
    def render(self,identity,style):
        if self.control is None:
            self.control=QQuickRenderControl();self.window=QQuickWindow(self.control)
            self.window.resize(320,180);self.window.contentItem().setSize(QSizeF(320,180));self.window.setColor(QColor('transparent'))
            self.item.setParentItem(self.window.contentItem())
            self.target=QImage(320,180,QImage.Format_ARGB32_Premultiplied);self.target.fill(0)
            self.window.setRenderTarget(QQuickRenderTarget.fromPaintDevice(self.target))
        self.item.setProperty('card',self.appearance(identity,style))
        # This bounded resource-settle is for twelve static captures only.
        # Software adaptation does not use initialize/beginFrame/endFrame.
        for _ in range(4):
            self.app.processEvents();QTest.qWait(10);self.control.polishItems();self.control.sync();self.control.render()
        self.assertFalse(self.window.isVisible());self.assertIsNone(QOpenGLContext.currentContext())
        self.assertEqual(self.window.rendererInterface().graphicsApi(),QSGRendererInterface.Software)
        self.assertEqual(self.evaluate('clockCount()'),0)
        glyph=next(o for o in self.walk() if o.objectName()=='color046Glyph')
        self.assertFalse(glyph.property('fanMotionActive'))
        images=[o for o in self.walk() if o.objectName()=='hardwareGlyphImage' or o.objectName().startswith('hardwareFanRotorImage_')]
        for image in images:
            exp=QQmlExpression(qmlContext(image),image,'status');status=exp.evaluate()
            if isinstance(status,tuple):status=status[0]
            self.assertEqual(status,1)
        return self.target.copy().convertToFormat(QImage.Format_RGBA8888),glyph
    def angle(self,degrees):
        # The hidden-window motion gate intentionally remains closed. This
        # narrow proof rotates ONLY the actual retained QQuickItem sprites at
        # explicit reference angles; it does not claim live-RPM/gate testing.
        for item in self.walk():
            if not item.objectName().startswith('hardwareFanRotor_'):continue
            exp=QQmlExpression(qmlContext(item),item,'modelData.direction');direction=exp.evaluate()
            if isinstance(direction,tuple):direction=direction[0]
            item.setProperty('rotation',degrees*(-1 if direction==-1 else 1))
        for _ in range(3):
            self.app.processEvents();self.control.polishItems();self.control.sync();self.control.render()
        self.assertEqual(self.evaluate('clockCount()'),0)
        self.assertFalse(self.window.isVisible());self.assertIsNone(QOpenGLContext.currentContext())
        return self.target.copy().convertToFormat(QImage.Format_RGBA8888)
    @staticmethod
    def pixels(image):
        data=bytes(image.constBits())
        return [tuple(data[i:i+4]) for i in range(0,len(data),4)]
    @staticmethod
    def colored(pixel):
        r,g,b,a=pixel;return a>=96 and max(r,g,b)-min(r,g,b)>=22
    def test_all148_gpus_keep_model_outline_holes_blades_and_retained_planes(self):
        self.assertEqual(len(GPU_ROWS),148)
        for identity in GPU_ROWS:
            with self.subTest(identity=identity):
                color=self.drawing(identity,'notebook_color');line=self.drawing(identity,'notebook_line')
                counts=dict(leaves=0,hubs=0)
                self.assertEqual(physical_tree(decode(color['source'])),physical_tree(decode(line['source']),dense_identity=identity,normalized=counts))
                reviewed=DENSE_MODELS.get(identity,{}).get('rotors',())
                self.assertEqual(counts,dict(leaves=sum(row['blades'] for row in reviewed),hubs=len(reviewed)))
                self.assertEqual(len(color['layers']['rotors']),len(line['layers']['rotors']))
                retained=dict(leaves=0,hubs=0)
                for a,b in zip(color['layers']['rotors'],line['layers']['rotors']):
                    self.assertEqual({k:v for k,v in a.items() if k!='source'},{k:v for k,v in b.items() if k!='source'})
                    self.assertEqual(physical_tree(decode(a['source'])),physical_tree(decode(b['source']),dense_identity=identity,normalized=retained))
                self.assertEqual(retained,counts)
                tree=ET.fromstring(decode(color['source']))
                self.assertTrue(any('hardware-notebook-color-wash' in n.get('class','') for n in tree.iter()))
                self.assertNotIn('hardware-notebook-color-',decode(line['source']))
    def test_actual_three_vendor_qml_pixels_distinguish_color_and_line_inside_real_leaves(self):
        for identity in REPRESENTATIVES:
            with self.subTest(identity=identity):
                color,glyph=self.render(identity,'notebook_color')
                colors=self.pixels(color);color_count=sum(map(self.colored,colors));self.assertGreater(color_count,300)
                layers=json.loads(self.evaluate('JSON.stringify(card)'))
                actual=self.drawing(identity,'notebook_color')['layers']['rotors']
                unit=glyph.property('artworkUnit');left=glyph.property('artworkLeft');top=glyph.property('artworkTop')
                for rotor in actual:
                    cx,cy=left+rotor['cx']*unit,top+rotor['cy']*unit;radius=rotor['radius']*unit;count=0
                    for y in range(max(0,int(cy-radius)),min(color.height(),int(cy+radius)+1)):
                        for x in range(max(0,int(cx-radius)),min(color.width(),int(cx+radius)+1)):
                            d=(x+.5-cx)**2+(y+.5-cy)**2
                            if (.35*radius)**2<d<(.85*radius)**2 and self.colored(colors[y*color.width()+x]):count+=1
                    self.assertGreater(count,20,(identity,rotor['cx'],'Real leaf annulus must contain rendered colour'))
                line,_=self.render(identity,'notebook_line');line_count=sum(map(self.colored,self.pixels(line)))
                self.assertEqual(line_count,0,'Plain line must have no coloured fill')
                self.assertNotEqual(color,line)
    def test_six_main_styles_rotate_only_the_actual_retained_fans_with_color_wash(self):
        identity=REPRESENTATIVES[0]
        for style in ('miniature','cartoon','notebook_color','notebook_line','sticker','papercut'):
            with self.subTest(style=style):
                _,glyph=self.render(identity,style);data=self.drawing(identity,style)['layers']
                if style=='notebook_color':
                    self.assertNotIn('hardware-notebook-color-blade-wash',decode(data['baseSource']))
                    self.assertTrue(all('hardware-notebook-color-blade-wash' in decode(r['source']) for r in data['rotors']))
                zero=self.angle(0);key=glyph.property('geometryKey');before=self.evaluate('JSON.stringify(card)')
                turn=self.angle(37);back=self.angle(0)
                self.assertEqual(zero,back);self.assertEqual(glyph.property('geometryKey'),key)
                self.assertEqual(self.evaluate('JSON.stringify(card)'),before)
                unit=glyph.property('artworkUnit');left=glyph.property('artworkLeft');top=glyph.property('artworkTop')
                disks=[(left+r['cx']*unit,top+r['cy']*unit,r['radius']*unit*1.05+2.) for r in data['rotors']]
                a,b=self.pixels(zero),self.pixels(turn);inside=outside=0
                for n,(x,y) in enumerate(zip(a,b)):
                    if x==y:continue
                    px,py=n%zero.width()+.5,n//zero.width()+.5
                    if any((px-cx)**2+(py-cy)**2<radius**2 for cx,cy,radius in disks):inside+=1
                    else:outside+=1
                self.assertGreater(inside,100)
                self.assertEqual(outside,0,'Fixed cover/PCB must not drift with a rotor')
    def test_other_generic_styles_do_not_receive_the_new_colored_template(self):
        from top_bar_config import HARDWARE_ICON_STYLES
        for style in HARDWARE_ICON_STYLES:
            source=decode(self.evaluate('generic('+json.dumps(style)+')'))
            if style=='notebook_color':self.assertIn('hardware-notebook-color-wash',source)
            else:self.assertNotIn('hardware-notebook-color-wash',source,style)


if __name__=='__main__':unittest.main()
