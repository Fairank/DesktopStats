"""Real software QML: only source-reviewed partial rotors may move."""
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QML_DISABLE_DISK_CACHE','1')
from PySide6.QtCore import QCoreApplication,QEvent,QObject,QUrl
from PySide6.QtGui import QGuiApplication,QImage
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression,qmlContext
from PySide6.QtQuick import QQuickWindow,QSGRendererInterface
from PySide6.QtTest import QTest
from shiboken6 import getCppPointer
from hardware_appearance import CATALOG,appearance_for
from top_bar_config import HARDWARE_ICON_STYLES

ROOT=Path(__file__).resolve().parents[1]


class PartialGpuMotion051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickWindow.setGraphicsApi(QSGRendererInterface.Software)
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        assert cls.app.platformName()=='offscreen'

    def setUp(self):
        for name in ('ctypes.WinDLL','socket.socket','subprocess.Popen','threading.Thread.start'):
            self.enterContext(patch(name,side_effect=AssertionError('Synthetic software QML only')))
        self.engine=QQmlEngine();self.warnings=[]
        self.engine.warnings.connect(lambda rows:self.warnings.extend(r.toString() for r in rows))
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Window
import "../native" as Product
import "../native/MetricEffectClock.js" as Clock
Window {
 id:root;width:360;height:240;visible:false;color:"transparent"
 flags:Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
 property var card:({})
 property var state:({})
 property real angle:0
 property bool requested:false
 property bool metrics:false
 property bool permitted:true
 property bool second:false
 function count(){return Clock.activeWindowCount()}
 function subscribers(){return Clock.subscriberCount(root.contentItem)}
 function layers(){return JSON.stringify(direct.fanLayerData || ({}))}
 Product.HardwareGlyph {
  id:direct;objectName:"partialDirect";width:360;height:240;visible:!root.metrics
  appearance:root.card;modelMode:true;fanMotionEnabled:root.requested;fanRotation:root.angle;ink:"#303a48"
 }
 Product.MetricIcon {
  objectName:"partialMetric";width:180;height:180;visible:root.metrics;name:"gpu";modelMode:true
  hardwareAppearance:root.card;hardwareState:root.state;effect:"auto";available:true;motionEnabled:root.permitted;ink:"#303a48"
 }
 Product.MetricIcon {
  objectName:"secondPartialMetric";x:180;width:180;height:180;visible:root.metrics && root.second;name:"gpu";modelMode:true
  hardwareAppearance:root.card;hardwareState:root.state;effect:"auto";available:true;motionEnabled:root.permitted;ink:"#303a48"
 }
}''',QUrl.fromLocalFile(str(ROOT/'tests/PartialGpuMotion051Fixture.qml')))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[e.toString() for e in self.component.errors()])
        # The test platform is offscreen/software. No OS-visible/native/GL
        # surface is presented; QML's real Window visibility gates still run.
        self.window.show();self.settle()

    def tearDown(self):
        self.window.hide();self.settle();self.assertEqual(self.evaluate('count()'),0)
        self.window.destroy();self.window.deleteLater();self.component.deleteLater();self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])

    def settle(self):
        self.app.processEvents();self.window.requestUpdate();QTest.qWait(8);self.app.processEvents()

    def evaluate(self,code):
        expression=QQmlExpression(qmlContext(self.window),self.window,code);value=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        value=value[0] if isinstance(value,tuple) else value
        return value.toVariant() if hasattr(value,'toVariant') else value

    def assign(self,key,value):
        self.evaluate(key+'=JSON.parse('+json.dumps(json.dumps(value))+')');self.settle()

    def card(self,identity='GV-N5070GAMING-OC-12GD',style='miniature'):
        return dict(appearance_for('gpu',identity),icon_set=style)

    def rotations(self):
        root=self.window.findChild(QObject,'partialDirect');stack=[root];values=[]
        while stack:
            item=stack.pop();stack.extend(item.childItems())
            if item.objectName().startswith('hardwareFanRotor_'):
                values.append((int(item.objectName().rsplit('_',1)[1]),item))
        return [item for _,item in sorted(values)]

    def test_partial_model_0_37_0_all_styles_keeps_unknown_discs_and_cached_textures(self):
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                card=self.card(style=style);self.assertFalse(card['fan_profile']['render_ready'])
                self.assign('card',card);self.assign('requested',True);self.assign('angle',0)
                layers=json.loads(self.evaluate('layers()'));rotors=self.rotations()
                self.assertEqual(len(rotors),len(layers['rotors']))
                self.assertEqual([r['source_index'] for r in layers['rotors'] if r['known']],[1])
                self.assertEqual(sum(r['known'] for r in layers['rotors']),1)
                pointers=[getCppPointer(r)[0] for r in rotors]
                sources=[r.findChild(QObject,'hardwareFanRotorImage_'+str(i)).property('source') for i,r in enumerate(rotors)]
                zero=self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
                self.assign('angle',37);turned=self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
                self.assertFalse(zero.isNull());self.assertNotEqual(zero,turned)
                for item,descriptor in zip(self.rotations(),layers['rotors']):
                    self.assertAlmostEqual(item.property('rotation'),323. if descriptor['known'] else 0.)
                self.assertEqual([getCppPointer(r)[0] for r in self.rotations()],pointers)
                self.assign('angle',0)
                self.assertEqual(self.window.grabWindow().convertToFormat(QImage.Format_RGBA8888),zero)
                self.assertEqual([r.findChild(QObject,'hardwareFanRotorImage_'+str(i)).property('source') for i,r in enumerate(self.rotations())],sources)
                self.assertEqual(self.evaluate('count()'),0)

    def test_real_rpm_partial_two_icons_share_clock_and_stop_at_zero_unknown_or_permission(self):
        self.assign('metrics',True);self.assign('card',self.card())
        def channels(rpm):return dict(profile='processor',available=True,load=None,thermal=None,energy=None,
            fan_speed=dict(available=True,rpm=rpm,semantics='measured',scope='card',source='Synthetic QA only',timestamp=time.time()))
        metric=self.window.findChild(QObject,'partialMetric')
        self.assign('state',channels(1200));self.assertTrue(metric.property('gpuFanCanAnimate'))
        self.assertTrue(metric.property('gpuFanMotionActive'));self.assertEqual(self.evaluate('count()'),1)
        self.assertEqual(self.evaluate('subscribers()'),1)
        self.assign('second',True);self.assertEqual(self.evaluate('count()'),1);self.assertEqual(self.evaluate('subscribers()'),2)
        self.assign('state',channels(0));self.assertFalse(metric.property('gpuFanCanAnimate'));self.assertEqual(self.evaluate('count()'),0)
        alias=next(r[-1][0] for r in CATALOG if r[0]=='nvidia-gtx780ti-reference')
        unknown=self.card(alias)
        self.assertEqual(unknown['id'],'nvidia-gtx780ti-reference');self.assertEqual(unknown['confidence'],'model')
        self.assertFalse(unknown['fan_profile']['render_ready'])
        self.assign('card',unknown);self.assign('state',channels(1200))
        self.assertFalse(metric.property('gpuFanCanAnimate'));self.assertEqual(self.evaluate('count()'),0)
        self.assign('card',self.card());self.assertEqual(self.evaluate('count()'),1)
        self.assign('permitted',False);self.assertFalse(metric.property('gpuFanMotionActive'));self.assertEqual(self.evaluate('count()'),0)
        self.assign('permitted',True);self.assertEqual(self.evaluate('count()'),1)
        self.window.hide();self.settle();self.assertEqual(self.evaluate('count()'),0)

    def test_partial_rpm_capability_uses_one_window_clock_for_all_preserved_styles(self):
        self.assign('metrics',True);self.assign('second',True)
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                self.assign('card',self.card(style=style))
                self.assign('state',dict(profile='processor',available=True,load=None,thermal=None,energy=None,
                    fan_speed=dict(available=True,rpm=1200,semantics='measured',scope='card',timestamp=time.time())))
                self.assertEqual(self.evaluate('count()'),1)
                self.assertEqual(self.evaluate('subscribers()'),2)
                self.assign('permitted',False);self.assertEqual(self.evaluate('count()'),0)
                self.assign('permitted',True);self.assertEqual(self.evaluate('count()'),1)


if __name__=='__main__':unittest.main()
