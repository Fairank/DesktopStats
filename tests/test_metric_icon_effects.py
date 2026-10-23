"""Only MetricIcon: actual 18 px offscreen renders, independent synthetic configuration."""

import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign38/metric-effects/profile"))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QWindow
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
CASES = (("temperature", "cpu_temp", "heat"), ("network", "net_download", "flow"),
         ("fan", "cpu_fan_rpm", "spin"), ("cpu", "cpu_usage", "pulse"))


class MetricIconEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Metric proof requires offscreen QPA")

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        self.component = self.window = None
        self.extra_windows = []
        self.extra_components = []

    def tearDown(self):
        for window in self.extra_windows:
            window.hide()
            window.destroy()
            window.deleteLater()
        for component in self.extra_components:
            component.deleteLater()
        if self.window is not None:
            self.window.hide()
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def load(self, many=False):
        child = '''Item {id:visibilityHost;objectName:"host";anchors.fill:parent;
            Product.MetricIcon {objectName:"icon";x:16;y:16;width:18;height:18;
                name:scene.glyph;metric:scene.quantity;effect:scene.choice;level:scene.reading;
                available:scene.valid;motionEnabled:scene.motionAllowed;intensity:scene.strength;
                speed:scene.tempo;ink:scene.dark?"#f5f6f8":"#202833"}
            Product.Icon {objectName:"control";x:56;y:16;width:18;height:18;
                name:scene.glyph;ink:scene.dark?"#f5f6f8":"#202833"}
        }'''
        if many:
            child = '''Repeater {model:64;Product.MetricIcon {required property int index;
                objectName:"icon_"+index;x:12+(index%8)*32;y:12+Math.floor(index/8)*32;width:18;height:18;
                readonly property string mode:scene.uniformEffect || ["heat","flow","spin","pulse"][index%4]
                name:mode==="heat"?"temperature":mode==="flow"?"network":mode==="spin"?"fan":"cpu";
                metric:mode==="heat"?"cpu_temp":mode==="flow"?"net_download":mode==="spin"?"gpu_fan_percent":"cpu_usage";
                effect:mode;level:.6;available:true;
                motionEnabled:scene.motionAllowed;intensity:scene.strength;speed:scene.tempo;
                ink:scene.dark?"#f5f6f8":"#202833"}}'''
        code = '''import QtQuick
import "../../native" as Product
import "../../native/MetricEffectClock.js" as EffectClock
Window {id:scene;width:300;height:300;visible:false;color:dark?"#20242b":"#f6f8fb";
    property string glyph:"cpu";property string quantity:"cpu_usage";property string choice:"off";
    property var reading:.5;property bool valid:true;property bool motionAllowed:true;
    property real strength:.5;property real tempo:1;property bool dark:false;
    property string uniformEffect:"";
''' + child + "\n}"
        self.component = QQmlComponent(self.engine)
        self.component.setData(code.encode(), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign38/metric-fixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.assertIsInstance(self.window, QQuickWindow)
        self.window.show()
        QTest.qWait(100)

    def items(self):
        result, pending = [], [self.window.contentItem()]
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(item.childItems())
        return result

    def find(self, name):
        result = self.window.findChild(QObject, name)
        if result is None:
            result = next((item for item in self.items() if item.objectName() == name), None)
        self.assertIsNotNone(result, name)
        return result

    def configure(self, glyph, quantity, effect):
        for key, value in (("glyph", glyph), ("quantity", quantity), ("choice", effect)):
            self.window.setProperty(key, value)
        self.app.processEvents()
        QTest.qWait(25)

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def frame(self, phase):
        clock = self.window.findChild(QObject, "metricIconAnimation")
        if clock is not None:
            clock.stop()
        self.find("icon").setProperty("phase", phase)
        self.app.processEvents()
        return self.window.grabWindow()

    def crop(self, image, x=0, y=0, width=18, height=18, origin=16):
        scale = self.window.devicePixelRatio()
        return image.copy(round((origin+x)*scale), round((16+y)*scale), round(width*scale), round(height*scale))

    @staticmethod
    def pixels(image):
        return bytes(image.constBits())

    def test_default_off_is_pixel_identical_to_static_icon_in_both_themes(self):
        self.load()
        for dark in (False, True):
            self.window.setProperty("dark", dark)
            for glyph, quantity, _effect in CASES:
                self.configure(glyph, quantity, "off")
                frame = self.frame(0)
                self.assertEqual(self.pixels(self.crop(frame)), self.pixels(self.crop(frame, origin=56)))
                self.assertFalse(self.find("icon").property("animationRunning"))
                self.assertEqual((self.find("icon").implicitWidth(), self.find("icon").implicitHeight()), (18, 18))

    def test_transport_moves_only_the_actual_arrow_and_keeps_tray_and_disk_body_fixed(self):
        self.load()
        for glyph, metric, direction, body_y in (("download", "net_download", 1, 15),
                                                 ("upload", "net_upload", -1, 15),
                                                 ("disk_read", "disk_read", -1, 11),
                                                 ("disk_write", "disk_write", 1, 11)):
            self.configure(glyph, metric, "flow")
            first, second = self.frame(.12), self.frame(.39)
            self.assertNotEqual(self.pixels(self.crop(first, y=0, height=10)), self.pixels(self.crop(second, y=0, height=10)))
            self.assertEqual(self.pixels(self.crop(first, y=body_y, height=18-body_y)),
                             self.pixels(self.crop(second, y=body_y, height=18-body_y)))
            self.assertEqual(self.find("icon").property("flowDirection"), direction)
            self.assertEqual(self.find("metricIconGlyph").property("rotation"), 0)

    def test_network_selected_direction_moves_while_opposite_channel_stays_fixed(self):
        self.load()
        for metric, fixed_x, active_x in (("net_download", 10, 0), ("net_upload", 0, 10)):
            self.configure("network", metric, "flow")
            first, second = self.frame(.12), self.frame(.39)
            self.assertEqual(self.pixels(self.crop(first, x=fixed_x, width=8)), self.pixels(self.crop(second, x=fixed_x, width=8)))
            self.assertNotEqual(self.pixels(self.crop(first, x=active_x, width=8)), self.pixels(self.crop(second, x=active_x, width=8)))

    def test_heat_changes_plume_geometry_with_stationary_thermometer_and_continuous_loop(self):
        self.load()
        self.configure("temperature", "cpu_temp", "heat")
        first, second = self.frame(.12), self.frame(.38)
        self.assertNotEqual(self.pixels(self.crop(first, x=11, y=0, width=7, height=10)),
                            self.pixels(self.crop(second, x=11, y=0, width=7, height=10)))
        self.assertEqual(self.pixels(self.crop(first, y=11, height=7)), self.pixels(self.crop(second, y=11, height=7)))
        self.assertEqual(self.pixels(self.frame(0)), self.pixels(self.frame(1)))

    def test_pulse_expands_inner_core_without_dimming_outer_glyph(self):
        self.load()
        self.configure("cpu", "cpu_usage", "pulse")
        first, second = self.frame(0), self.frame(.5)
        self.assertEqual(self.pixels(self.crop(first, y=0, height=5)), self.pixels(self.crop(second, y=0, height=5)))
        self.assertNotEqual(self.pixels(self.crop(first, x=6, y=6, width=6, height=6)),
                            self.pixels(self.crop(second, x=6, y=6, width=6, height=6)))
        self.assertEqual(self.find("metricIconGlyph").property("opacity"), 1)

    def test_rotor_moves_around_stationary_hub_and_preserves_frame_geometry(self):
        self.load()
        self.configure("fan", "gpu_fan_percent", "spin")
        first, second = self.frame(0), self.frame(.12)
        self.assertNotEqual(self.pixels(self.crop(first)), self.pixels(self.crop(second)))
        self.assertEqual(self.pixels(self.crop(first, x=8, y=8, width=2, height=2)),
                         self.pixels(self.crop(second, x=8, y=8, width=2, height=2)))
        hub = self.find("metricIconHub")
        self.assertEqual(hub.property("rotation"), 0)
        self.assertEqual((self.find("icon").width(), self.find("icon").height(), self.find("icon").scale()), (18, 18, 1))

    def test_energy_trace_leaves_voltage_needle_fixed_and_does_not_rebuild_svg(self):
        self.load()
        for glyph, metric in (("power", "cpu_power"), ("voltage", "voltage")):
            self.configure(glyph, metric, "flow")
            source = self.find("lucideImage").property("source")
            first, second = self.frame(.1), self.frame(.65)
            self.assertNotEqual(self.pixels(self.crop(first)), self.pixels(self.crop(second)))
            self.assertEqual(self.find("lucideImage").property("source"), source)
            self.assertEqual(self.find("metricIconGlyph").property("rotation"), 0)

    def test_auto_resolves_real_quantity_and_invalid_zero_hidden_reduced_minimized_all_stop(self):
        self.load()
        for glyph, metric, effect in (*CASES, ("fan", "gpu_fan_percent", "spin")):
            self.configure(glyph, metric, "auto")
            self.assertEqual(self.find("icon").property("resolvedEffect"), effect)
            self.assertTrue(self.find("icon").property("animationRunning"))
            for field, value, restore in (("reading", 0, .5), ("reading", None, .5), ("reading", -1, .5),
                                           ("reading", float("nan"), .5), ("reading", 1.1, .5),
                                           ("valid", False, True), ("motionAllowed", False, True),
                                           ("strength", 0, .5), ("strength", -1, .5), ("tempo", .4, 1), ("tempo", 2.1, 1)):
                self.window.setProperty(field, value)
                self.assertFalse(self.find("icon").property("animationRunning"), (effect, field, value))
                self.assertEqual(self.find("icon").property("phase"), 0)
                self.window.setProperty(field, restore)
            self.find("host").setVisible(False)
            self.assertFalse(self.find("icon").property("animationRunning"))
            self.find("host").setVisible(True)
            self.find("host").setOpacity(0)
            self.assertFalse(self.find("icon").property("animationRunning"))
            self.find("host").setOpacity(1)
            self.window.setVisibility(QWindow.Minimized)
            self.assertFalse(self.find("icon").property("animationRunning"))
            self.window.showNormal()
        self.configure("custom", "external_slot_0", "auto")
        self.assertFalse(self.find("icon").property("animationRunning"))
        self.window.hide()
        self.assertEqual(self.find("icon").property("phase"), 0)

    def test_strength_and_speed_extremes_remain_distinct_without_using_reading_as_an_rpm_scale(self):
        self.load()
        for glyph, metric, effect in CASES:
            self.configure(glyph, metric, effect)
            images = []
            for strength in (.1, 1):
                self.window.setProperty("strength", strength)
                images.append(self.pixels(self.crop(self.frame(.32))))
            self.assertNotEqual(*images, effect)
            durations = []
            for tempo in (.5, 2):
                self.window.setProperty("tempo", tempo)
                durations.append(self.find("icon").property("cycleDuration"))
                self.assertTrue(self.find("icon").property("animationRunning"))
            self.assertEqual(durations[0], durations[1]*4)
            duration = self.find("icon").property("cycleDuration")
            self.window.setProperty("reading", .99)
            self.assertEqual(self.find("icon").property("cycleDuration"), duration)

    def test_clock_uses_elapsed_time_and_late_stopped_ticks_cannot_resurrect_motion(self):
        self.load()
        self.configure("cpu", "cpu_usage", "pulse")
        icon, clock = self.find("icon"), self.find("metricIconAnimation")
        clock.stop()
        self.assertGreaterEqual(clock.property("interval"), 34)
        icon.setProperty("phase", 0)
        icon.setProperty("previousTick", 1000)
        self.evaluate(icon, "advanceClock(1100)")
        self.assertAlmostEqual(icon.property("phase"), 100/icon.property("cycleDuration"))
        before = icon.property("phase")
        self.evaluate(icon, "advanceClock(900)")
        self.assertEqual(icon.property("phase"), before)
        self.window.setProperty("motionAllowed", False)
        self.evaluate(icon, "advanceClock(999999)")
        self.assertEqual(icon.property("phase"), 0)

    def test_64_worst_case_effects_reuse_nodes_sources_and_stop_all_clocks(self):
        self.load(many=True)
        self.window.setProperty("strength", 1)
        self.window.setProperty("tempo", 2)
        icons = [self.find("icon_"+str(index)) for index in range(64)]
        count = [0]
        ticks = [0]
        clocks = [item for item in self.window.findChildren(QObject) if item.objectName() == "metricEffectClock"]
        self.assertEqual(len(clocks), 1)
        self.assertEqual(clocks[0].property("subscriberCount"), 64)
        self.find("metricIconAnimation").triggered.connect(lambda: ticks.__setitem__(0, ticks[0]+1))
        self.window.frameSwapped.connect(lambda: count.__setitem__(0, count[0]+1))
        self.perf_results = {}
        for effect in ("heat", "flow", "spin", "pulse"):
            self.window.setProperty("uniformEffect", effect)
            QTest.qWait(60)
            before_nodes = len(self.window.findChildren(QObject))
            before_sources = [item.property("source") for item in self.items() if item.property("source") is not None]
            count[0] = 0
            ticks[0] = 0
            start = time.process_time()
            wall = time.perf_counter()
            QTest.qWait(400)
            self.perf_results[effect] = dict(cpu_seconds=time.process_time()-start, frames=count[0],
                                             wall_seconds=time.perf_counter()-wall, ticks=ticks[0], nodes=before_nodes)
            self.assertTrue(all(icon.property("phase") > 0 for icon in icons))
            self.assertEqual(len(self.window.findChildren(QObject)), before_nodes)
            self.assertEqual([item.property("source") for item in self.items() if item.property("source") is not None], before_sources)
            self.assertLessEqual(count[0], 17, self.perf_results)
        self.assertFalse(any("Canvas" in item.metaObject().className() for item in self.items()))
        self.window.hide()
        self.assertTrue(all(not icon.property("animationRunning") and icon.property("phase") == 0 for icon in icons))
        QTest.qWait(80)
        self.assertTrue(all(icon.property("phase") == 0 for icon in icons))

    def test_shared_clock_is_per_window_releases_at_zero_and_reopens_without_stale_registry(self):
        self.load()
        self.configure("cpu", "cpu_usage", "pulse")
        first_icon = self.find("icon")
        first_clock = self.find("metricEffectClock")
        component = QQmlComponent(self.engine)
        component.setData(b'''import QtQuick
import "../../native" as Product
import "../../native/MetricEffectClock.js" as EffectClock
Window {width:80;height:80;visible:false;Product.MetricIcon {objectName:"otherIcon";
    width:18;height:18;name:"fan";metric:"cpu_fan_rpm";effect:"spin";
    available:true;level:.5;motionEnabled:true}}''', QUrl.fromLocalFile(str(ROOT / "qa-private/redesign38/second-window.qml")))
        other = component.create()
        self.assertIsNotNone(other, [error.toString() for error in component.errors()])
        self.extra_windows.append(other)
        self.extra_components.append(component)
        other.show()
        QTest.qWait(60)
        second_icon = other.findChild(QObject, "otherIcon")
        second_clock = other.findChild(QObject, "metricEffectClock")
        self.assertIsNot(first_clock, second_clock)
        self.assertEqual(self.evaluate(first_icon, "EffectClock.activeWindowCount()"), 2)
        self.window.hide()
        QTest.qWait(40)
        self.assertEqual(self.evaluate(second_icon, "EffectClock.activeWindowCount()"), 1)
        self.assertIsNone(self.window.findChild(QObject, "metricEffectClock"))
        phase = second_icon.property("phase")
        QTest.qWait(70)
        self.assertNotEqual(second_icon.property("phase"), phase)
        self.window.show()
        QTest.qWait(50)
        self.assertEqual(self.evaluate(first_icon, "EffectClock.activeWindowCount()"), 2)
        self.assertIsNot(self.find("metricEffectClock"), first_clock)
        other.deleteLater()
        self.extra_windows.remove(other)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QTest.qWait(40)
        self.assertEqual(self.evaluate(first_icon, "EffectClock.activeWindowCount()"), 1)
        self.window.setProperty("motionAllowed", False)
        QTest.qWait(40)
        self.assertEqual(self.evaluate(first_icon, "EffectClock.activeWindowCount()"), 0)
        self.assertIsNone(self.window.findChild(QObject, "metricIconAnimation"))
        self.window.setProperty("motionAllowed", True)
        QTest.qWait(40)
        self.assertEqual(self.evaluate(first_icon, "EffectClock.activeWindowCount()"), 1)

    def test_notification_snapshot_skips_retired_listener_and_defers_new_registration(self):
        self.load()
        self.configure("cpu", "cpu_usage", "pulse")
        icon = self.find("icon")
        self.find("metricIconAnimation").stop()
        result = self.evaluate(icon, '''(function() {
            var host=clockHost, order=[], later=null, b=null;
            var a=EffectClock.subscribe(host,function(now){
                order.push("a");EffectClock.unsubscribe(b);
                if(!later)later=EffectClock.subscribe(host,function(){order.push("c")});
            });
            b=EffectClock.subscribe(host,function(){order.push("b")});
            clockSubscription.entry.clock.stop();
            clockSubscription.entry.clock.tick(Date.now());
            var first=order.join(",");order=[];
            clockSubscription.entry.clock.tick(Date.now());
            var second=order.join(",");
            EffectClock.unsubscribe(a);EffectClock.unsubscribe(b);EffectClock.unsubscribe(later);
            return first+" / "+second+" / "+EffectClock.subscriberCount(host);
        })()''')
        self.assertEqual(result, "a / a,c / 1")
        self.window.setProperty("motionAllowed", False)
        result = self.evaluate(icon, '''(function() {
            var host=clockHost, order=[], original=null, replacement=null;
            original=EffectClock.subscribe(host,function(){
                order.push("old");EffectClock.unsubscribe(original);
                replacement=EffectClock.subscribe(host,function(){order.push("new")});
            });
            var retiredClock=original.entry.clock;retiredClock.stop();retiredClock.tick(Date.now());
            var first=order.join(",");
            replacement.entry.clock.stop();replacement.entry.clock.tick(Date.now());
            var second=order.join(",");EffectClock.unsubscribe(replacement);
            return first+" / "+second+" / "+EffectClock.activeWindowCount();
        })()''')
        self.assertEqual(result, "old / old,new / 0")

    def test_closed_engine_and_recreated_engine_have_independent_empty_registry(self):
        self.load()
        self.configure("fan", "cpu_fan_rpm", "spin")
        self.assertEqual(self.evaluate(self.find("icon"), "EffectClock.activeWindowCount()"), 1)
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.window = self.component = None
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.engine = QQmlEngine()
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        self.load()
        self.assertEqual(self.evaluate(self.find("icon"), "EffectClock.activeWindowCount()"), 0)
        self.configure("cpu", "cpu_usage", "pulse")
        self.assertEqual(self.evaluate(self.find("icon"), "EffectClock.activeWindowCount()"), 1)


if __name__ == "__main__":
    unittest.main()
