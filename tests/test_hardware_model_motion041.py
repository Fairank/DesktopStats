"""Real retained model glyphs at explicit angles; offscreen/software, no clock/RPM."""
import base64
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QRectF,QUrl
from PySide6.QtGui import QFontDatabase,QGuiApplication,QImage,QPainter
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtQuick import QQuickWindow
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from shiboken6 import getCppPointer

from hardware_appearance import CATALOG,appearance_for
from hardware_fan_profiles import profile_for
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]
REPRESENTATIVES=('nvidia-founders-rtx5090-32g','zotac-twin-4060ti-oc-white','msi-vega64-8g-reference')
GPU_ROWS={row[0]:row for row in CATALOG if row[1]=='gpu'}


def exact(identity,style):
    value=appearance_for('gpu',GPU_ROWS[identity][-1][0])
    assert value['id']==identity,(identity,value)
    return dict(value,icon_set=style)


def decode(uri):
    text=uri.toString() if isinstance(uri,QUrl) else str(uri)
    header,body=text.split(',',1)
    return base64.b64decode(body).decode() if ';base64' in header else unquote(body)


class HardwareModelMotion041Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen','Never show a native test surface'
        for name in ('arial.ttf','segoeui.ttf'):
            font=Path('C:/Windows/Fonts')/name
            if font.is_file():QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        self.native=self.enterContext(patch('ctypes.WinDLL',side_effect=AssertionError('No native/device I/O')))
        self.process=self.enterContext(patch('subprocess.Popen',side_effect=AssertionError('No process')))
        self.thread=self.enterContext(patch('threading.Thread.start',side_effect=AssertionError('No collector/worker')))
        self.network=self.enterContext(patch('socket.socket',side_effect=AssertionError('No network')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Window
import "../native" as Product
import "../native/HardwareShapes.js" as Shapes
import "../native/MetricEffectClock.js" as Clock
Window {
 id:scene; width:240; height:240; visible:false; color:"transparent"
 flags:Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
 property var card:({})
 property bool retained:false
 property real angle:0
 function clockCount(){return Clock.activeWindowCount()}
 function retainedLayers(){return JSON.stringify(glyph.fanLayerData || ({}))}
 function direct(){const key=Shapes.key(Object.assign({},card,{model_mode:true}),"#303a48");return Shapes.source(key)}
 Product.HardwareGlyph {
  id:glyph;objectName:"modelMotionGlyph";anchors.fill:parent
  appearance:scene.card;modelMode:true;ink:"#303a48"
  fanMotionEnabled:scene.retained;fanRotation:scene.angle
 }
}''',QUrl.fromLocalFile(str(ROOT/'tests/HardwareModelMotion041Fixture.qml')))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[e.toString() for e in self.component.errors()])
        self.window.show();self.settle()

    def tearDown(self):
        self.window.hide();self.assertEqual(self.evaluate('clockCount()'),0)
        self.window.destroy();self.window.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        for guard in (self.native,self.process,self.thread,self.network):guard.assert_not_called()

    def evaluate(self,code):
        expression=QQmlExpression(qmlContext(self.window),self.window,code);value=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return value[0] if isinstance(value,tuple) else value

    def assign(self,name,value):
        self.evaluate(name+' = JSON.parse('+json.dumps(json.dumps(value))+')');self.settle()

    def settle(self):
        self.app.processEvents();self.window.requestUpdate();QTest.qWait(8);self.app.processEvents()

    def glyph(self):return self.window.findChild(QObject,'modelMotionGlyph')

    @staticmethod
    def children(parent):
        pending=[parent]
        while pending:
            item=pending.pop();yield item;pending.extend(item.childItems())

    def rotors(self):
        return sorted((item for item in self.children(self.glyph()) if item.objectName().startswith('hardwareFanRotor_')),
                      key=lambda item:int(item.objectName().rsplit('_',1)[1]))

    def texture_identity(self):
        glyph=self.glyph()
        items=[item for item in self.children(glyph) if item.objectName()=='hardwareGlyphImage'
               or item.objectName().startswith('hardwareFanRotorImage_')]
        items.sort(key=lambda item:item.objectName())
        loader=glyph.findChild(QObject,'hardwareFanMotionLoader')
        return (getCppPointer(loader.property('item'))[0],
                tuple(getCppPointer(item)[0] for item in self.rotors()),
                tuple((item.objectName(),getCppPointer(item)[0],item.property('source')) for item in items))

    def capture(self):
        self.settle();image=self.window.grabWindow()
        self.assertFalse(image.isNull());self.assertEqual(image.width(),self.window.width())
        self.assertEqual(image.height(),self.window.height())
        return image.convertToFormat(QImage.Format_RGBA8888)

    @staticmethod
    def vector(uri,layers=None,size=240):
        image=QImage(size,size,QImage.Format_ARGB32_Premultiplied);image.fill(0);painter=QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        def draw(source,rect):
            renderer=QSvgRenderer(decode(source).encode())
            assert renderer.isValid();renderer.render(painter,rect)
        try:
            draw(layers['baseSource'] if layers else uri,QRectF(0,0,size,size))
            if layers:
                for rotor in layers['rotors']:
                    radius=rotor['radius']*size/24
                    painter.save();painter.translate(rotor['cx']*size/24,rotor['cy']*size/24)
                    draw(rotor['source'],QRectF(-radius,-radius,2*radius,2*radius));painter.restore()
        finally:painter.end()
        return image

    @staticmethod
    def delta(first,second):
        a,b=bytes(first.constBits()),bytes(second.constBits())
        changed=[i//4 for i in range(0,len(a),4) if a[i:i+4]!=b[i:i+4]]
        material=sum(max(abs(a[i+c]-b[i+c]) for c in range(4))>=32 for i in range(0,len(a),4))
        difference=[abs(left-right) for left,right in zip(a,b)]
        bounds=None
        if changed:
            width=first.width();xs=[i%width for i in changed];ys=[i//width for i in changed]
            bounds=(min(xs),min(ys),max(xs),max(ys))
        return dict(pixels=len(changed),material_pixels=material,bounds=bounds,
                    occupied=sum(value>0 for value in a[3::4]),
                    mean_rgba=sum(difference)/len(difference),max_rgba=max(difference,default=0))

    def test_model_static_svg_and_vector_zero_layers_are_pixel_identical(self):
        for identity in REPRESENTATIVES:
            for style in HARDWARE_ICON_STYLES:
                with self.subTest(model=identity,style=style):
                    self.assign('card',exact(identity,style));self.assign('retained',True)
                    layers=json.loads(self.evaluate('retainedLayers()'));uri=self.evaluate('direct()')
                    static=self.vector(uri);zero=self.vector(uri,layers)
                    self.assertTrue(static==zero,(identity,style,self.delta(static,zero)))
                    self.assertEqual(self.evaluate('clockCount()'),0)

    def test_actual_qml_retained_zero_rotation_and_return_preserve_the_same_model(self):
        for width,height in ((240,240),(360,180)):
            self.window.resize(width,height);self.settle()
            for identity in REPRESENTATIVES:
                for style in HARDWARE_ICON_STYLES:
                    with self.subTest(model=identity,style=style,width=width,height=height):
                        value=exact(identity,style);reviewed=profile_for(value)
                        self.assign('card',value);self.assign('angle',0);self.assign('retained',False)
                        static=self.capture();glyph=self.glyph();key=glyph.property('geometryKey')
                        self.assertIn('|model_',key);self.assertTrue(glyph.property('modelMode'))
                        self.assertEqual(glyph.property('wideGpu'),width>height)
                        self.assertTrue(glyph.property('layeredArtwork'))
                        self.assertFalse(glyph.property('fanMotionActive'))
                        self.assertGreater(sum(v>0 for v in bytes(static.constBits())[3::4]),500)
                        textures=self.texture_identity()
                        source=glyph.property('svgSource');self.assertEqual(source,QUrl(self.evaluate('direct()')))
                        self.assign('retained',True);zero=self.capture()
                        self.assertTrue(glyph.property('fanMotionActive'))
                        if static!=zero:self.fail((identity,style,'QML stopped->zero',self.delta(static,zero)))
                        self.assertEqual(self.texture_identity(),textures)
                        layers=json.loads(self.evaluate('retainedLayers()'));rotors=self.rotors()
                        self.assertEqual(len(rotors),len(layers['rotors']))
                        unit=glyph.property('artworkUnit')
                        for item,descriptor in zip(rotors,layers['rotors']):
                            self.assertAlmostEqual(item.x()+item.width()/2,glyph.property('artworkLeft')+descriptor['cx']*unit)
                            self.assertAlmostEqual(item.y()+item.height()/2,glyph.property('artworkTop')+descriptor['cy']*unit)
                            self.assertAlmostEqual(item.width(),descriptor['radius']*2*unit)
                        self.assign('angle',37);turned=self.capture()
                        if reviewed.get('render_ready') is True:
                            self.assertTrue(zero!=turned,(identity,style,'reviewed blades did not move'))
                        self.assertEqual(glyph.property('geometryKey'),key);self.assertEqual(glyph.property('svgSource'),source)
                        for item,descriptor in zip(self.rotors(),layers['rotors']):
                            self.assertAlmostEqual(item.property('rotation'),37 if descriptor.get('direction')!=-1 else 323)
                        self.assertEqual(self.texture_identity(),textures)
                        # Motion disabled with a nonzero requested angle must
                        # stop at zero without swapping any retained texture.
                        self.assign('retained',False);stopped=self.capture()
                        self.assertFalse(glyph.property('fanMotionActive'))
                        self.assertTrue(glyph.property('layeredArtwork'))
                        self.assertTrue(all(item.property('rotation')==0 for item in self.rotors()))
                        if stopped!=zero:self.fail((identity,style,'turn->stop',self.delta(zero,stopped)))
                        self.assertEqual(self.texture_identity(),textures)
                        self.assign('retained',True);resumed=self.capture()
                        if resumed!=turned:self.fail((identity,style,'resume same angle',self.delta(turned,resumed)))
                        self.assign('angle',0);restored=self.capture()
                        if restored!=zero:self.fail((identity,style,'return-zero',self.delta(restored,zero)))
                        self.assertEqual(self.texture_identity(),textures)
                        self.assertEqual(self.evaluate('clockCount()'),0)


if __name__=='__main__':unittest.main()
