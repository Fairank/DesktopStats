"""Only MetricIcon: actual 18 px offscreen renders, independent synthetic configuration."""

import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
os.environ.setdefault("DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign39/metric-effects/profile"))

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

    def load(self, many=False, count=64):
        child = '''Item {id:visibilityHost;objectName:"host";anchors.fill:parent;
            Product.MetricIcon {objectName:"icon";x:16;y:16;width:18;height:18;
                name:scene.glyph;metric:scene.quantity;effect:scene.choice;level:scene.reading;
                available:scene.valid;motionEnabled:scene.motionAllowed;intensity:scene.strength;
                speed:scene.tempo;hardwareState:scene.channels;ink:scene.dark?"#f5f6f8":"#202833"}
            Product.Icon {objectName:"control";x:56;y:16;width:18;height:18;
                name:scene.glyph;ink:scene.dark?"#f5f6f8":"#202833"}
        }'''
        if many:
            child = '''Repeater {model:scene.iconCount;Product.MetricIcon {required property int index;
                objectName:"icon_"+index;x:12+(index%8)*32;y:12+Math.floor(index/8)*32;width:18;height:18;
                readonly property string mode:scene.uniformEffect || ["heat","flow","spin","pulse"][index%4]
                name:mode==="heat"?"temperature":mode==="flow"?"network":mode==="spin"?"fan":"cpu";
                metric:mode==="heat"?"cpu_temp":mode==="flow"?"net_download":mode==="spin"?"gpu_fan_percent":"cpu_usage";
                effect:mode==="hardware"?"auto":mode;level:.6;available:true;
                hardwareState:mode==="hardware"?scene.channels:({});
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
    property var channels:({});
    property int iconCount:ICON_COUNT;
''' + child + "\n}"
        code=code.replace("ICON_COUNT",str(count))
        self.component = QQmlComponent(self.engine)
        self.component.setData(code.encode(), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign39/metric-fixture.qml")))
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
        # Lazy palette delegates and their raster textures can be created after
        # a glyph change. Observe image readiness, then complete a renderer
        # preparation pass before comparing the frozen-phase frame. A static
        # unchanged scene need not emit frameSwapped, so that is not a gate.
        for _ in range(50):
            images=[item for item in self.items() if item.inherits("QQuickImage") and item.isVisible()]
            if all(self.evaluate(item,"status === Image.Ready") for item in images):
                break
            QTest.qWait(5)
        self.assertTrue(all(self.evaluate(item,"status === Image.Ready") for item in images))
        self.window.requestUpdate()
        self.assertFalse(self.window.grabWindow().isNull())
        self.app.processEvents()
        return self.window.grabWindow()

    def settle_level(self, value):
        self.window.setProperty("reading", value)
        icon = self.find("icon")
        clock = self.window.findChild(QObject, "metricIconAnimation")
        if clock is not None:
            clock.stop()
        icon.setProperty("previousTick", 1000)
        for now in range(1100, 2701, 100):
            self.evaluate(icon, f"advanceClock({now})")
        self.assertAlmostEqual(icon.property("displayedLevel"), value, delta=.001)
        return icon

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

    def test_heat_bursts_change_geometry_with_stationary_thermometer_and_continuous_loop(self):
        self.load()
        self.configure("temperature", "cpu_temp", "heat")
        first, second = self.frame(.12), self.frame(.38)
        self.assertNotEqual(self.pixels(self.crop(first, x=11, y=0, width=7, height=10)),
                            self.pixels(self.crop(second, x=11, y=0, width=7, height=10)))
        self.assertEqual(self.pixels(self.crop(first, y=11, height=7)), self.pixels(self.crop(second, y=11, height=7)))
        discharge=self.find("metricIconWarmDischarge")
        self.assertEqual(discharge.height(),10)
        self.assertTrue(discharge.clip())
        # Loader resizes its direct child to18DIP. The actual atlas clipping
        # must remain on the inner child for every perimeter burst, not just
        # one lucky pair of frames away from the lower bulb.
        bulb=self.pixels(self.crop(first,y=11,height=7))
        upper_frames=[]
        for index in range(48):
            current=self.frame(index/48)
            self.assertEqual(self.pixels(self.crop(current,y=11,height=7)),bulb,index)
            upper_frames.append(self.pixels(self.crop(current,y=0,height=10)))
        self.assertGreater(len(set(upper_frames)),3)
        self.assertEqual(self.pixels(self.frame(0)), self.pixels(self.frame(1)))

    def test_pulse_changes_core_ink_without_dimming_outer_glyph(self):
        self.load()
        self.configure("cpu", "cpu_usage", "pulse")
        first = self.frame(0)
        core_height = self.find("metricIconPulseCore").height()
        first_y = self.find("metricIconLoadHighlight").y()
        second = self.frame(.75)
        self.assertLess(self.find("metricIconLoadHighlight").y(), first_y)
        self.assertEqual(self.find("metricIconPulseCore").height(), core_height)
        self.assertEqual(self.pixels(self.crop(first, y=0, height=5)), self.pixels(self.crop(second, y=0, height=5)))
        self.assertNotEqual(self.pixels(self.crop(first, x=6, y=6, width=6, height=6)),
                            self.pixels(self.crop(second, x=6, y=6, width=6, height=6)))
        self.assertEqual(self.find("metricIconGlyph").property("opacity"), 1)

    def test_percentage_fill_spans_actual_load_without_pulse_or_strength_rescaling(self):
        self.load()
        # Lucide's inner frame is 6x6 including its 1.5 DIP stroke. The actual
        # empty cavity is 4.4 DIP; occupancy must not paint over the frame.
        for glyph, metric, dimension, extent in (("cpu", "cpu_usage", "height", 4.4),
                                                 ("memory", "ram_percent", "width", 13),
                                                 ("battery", "battery_percent", "width", 10)):
            self.configure(glyph, metric, "pulse")
            sizes=[]
            for reading in (.1,.9):
                self.settle_level(reading)
                core=self.find("metricIconPulseCore")
                self.frame(0)
                size=core.property(dimension)
                self.assertAlmostEqual(size,extent*reading,delta=.02)
                self.frame(.5)
                self.assertAlmostEqual(core.property(dimension),size,delta=.001)
                for strength in (.01,.5,1):
                    self.window.setProperty("strength",strength)
                    self.assertAlmostEqual(core.property(dimension),size,delta=.001)
                self.window.setProperty("strength",.5)
                sizes.append(size)
            self.assertGreater(sizes[1]-sizes[0],extent*.75)
        # Absolute GB has a reference normalization, not a known capacity ratio.
        self.configure("memory","ram_used_gb","pulse")
        self.settle_level(.1)
        first=self.find("metricIconPulseCore").width()
        self.settle_level(.9)
        self.assertAlmostEqual(self.find("metricIconPulseCore").width(),first,delta=.001)
        self.assertFalse(self.find("metricIconPulseCore").property("proportional"))

    def test_processor_thermal_outline_and_blue_energy_are_independent_of_load(self):
        self.load()
        self.configure("cpu","cpu_usage","auto")
        icon=self.find("icon")
        states=[]
        for thermal in (.1,.9):
            self.window.setProperty("channels",dict(profile="processor",available=True,
                load=.1,thermal=thermal,energy=.9,inbound=None,outbound=None,spin=None))
            clock=self.window.findChild(QObject,"metricIconAnimation")
            clock.stop()
            icon.setProperty("previousTick",1000)
            for now in range(1100,2701,100):
                self.evaluate(icon,f"advanceClock({now})")
            icon.setProperty("thermalArcPhase", .355)
            icon.setProperty("energyPhase", .355)
            self.frame(.355)
            warm=self.find("metricIconWarmDischarge")
            states.append(warm.isVisible())
            self.assertEqual(warm.isVisible(), thermal>.28)
            self.assertTrue(icon.property("energyActive"))
            self.assertAlmostEqual(icon.property("displayedEnergy"),.9,delta=.001)
            self.assertAlmostEqual(self.find("metricIconPulseCore").height(),.44,delta=.02)
            self.assertEqual(self.find("metricIconGlyph").property("opacity"), 1)
        self.assertEqual(states, [False, True])

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

    def test_strength_and_speed_remain_independent_of_state_feedback(self):
        self.load()
        for glyph, metric, effect in CASES:
            self.configure(glyph, metric, effect)
            images = []
            for strength in (.1, 1):
                self.window.setProperty("strength", strength)
                images.append(self.pixels(self.crop(self.frame(.355))))
            self.assertNotEqual(*images, effect)
            durations = []
            for tempo in (.5, 2):
                self.window.setProperty("tempo", tempo)
                durations.append(self.find("icon").property("cycleDuration"))
                self.assertTrue(self.find("icon").property("animationRunning"))
            self.assertEqual(durations[0], durations[1]*4)
            self.window.setProperty("tempo", 1)
            low_duration = self.settle_level(.35 if effect=="heat" else .1).property("cycleDuration")
            high_duration = self.settle_level(.9).property("cycleDuration")
            # A complete multi-position burst cycle is now 2.4 s at unit
            # activity, with a restrained state-dependent tempo. Fan rotation
            # retains its wider low/high speed range.
            self.assertGreater(low_duration, high_duration * (2 if effect=="spin" else 1.15 if effect=="heat" else 1.25))

    def test_low_mid_high_state_is_colored_and_distinct_at_11_16_18_pixels(self):
        self.load()
        self.window.setProperty("strength", .5)
        for dark in (False, True):
            self.window.setProperty("dark", dark)
            for glyph, metric, effect in (*CASES, ("memory", "ram_percent", "pulse"),
                                          ("power", "cpu_power", "flow"), ("voltage", "voltage", "flow")):
                self.configure(glyph, metric, effect)
                icon = self.find("icon")
                for size in (11, 16, 18):
                    icon.setWidth(size)
                    icon.setHeight(size)
                    # Source-size and layout changes reach the actual renderer on
                    # its next frame; an immediate grab can still be empty backing.
                    self.window.requestUpdate()
                    QTest.qWait(20)
                    images, durations = [], []
                    # Cold thermal data deliberately has no decorative heat.
                    readings=(.35,.55,.85) if effect=="heat" else (.1,.5,.9)
                    for reading in readings:
                        self.settle_level(reading)
                        # .355 is a real dark gap for the low network packet;
                        # .145 is inside its bottom-perimeter burst. Temperature
                        # uses the independently timed warm right-side packet.
                        active_phase=.355 if effect=="heat" else .145
                        image = self.crop(self.frame(active_phase), width=size, height=size)
                        chromatic = sum(max((pixel.red(), pixel.green(), pixel.blue()))
                                        - min((pixel.red(), pixel.green(), pixel.blue())) > 30
                                        for y in range(image.height()) for x in range(image.width())
                                        for pixel in (image.pixelColor(x, y),))
                        if glyph=="cpu" and reading==.1:
                            # A truthful 10% fill is .44 DIP high inside the
                            #4.4DIP cavity (<1 physical pixel even at18DIP/175%).
                            # Do not inflate it or recolour the neutral pins to
                            # manufacture two saturated pixels. Mid/high colour
                            # and three distinct state frames remain required.
                            self.assertAlmostEqual(self.find("metricIconPulseCore").height(),.44,delta=.002)
                            self.assertEqual(self.find("metricIconGlyph").property("opacity"),1)
                        else:
                            self.assertGreaterEqual(chromatic, 2, (dark, glyph, size, reading))
                        images.append(self.pixels(image))
                        durations.append(icon.property("cycleDuration"))
                    self.assertEqual(len(set(images)), 3, (dark, glyph, size))
                    self.assertGreater(durations[0], durations[1])
                    self.assertGreater(durations[1], durations[2])
                    self.assertEqual((icon.width(), icon.height(), icon.scale()), (size, size, 1))

    def test_positive_state_changes_settle_in_both_directions_and_zero_stops_immediately(self):
        self.load()
        self.configure("memory", "ram_percent", "pulse")
        icon = self.settle_level(.1)
        self.window.setProperty("reading", .9)
        self.assertAlmostEqual(icon.property("displayedLevel"), .1, delta=.001)
        icon.setProperty("previousTick", 1000)
        self.evaluate(icon, "advanceClock(1100)")
        middle = icon.property("displayedLevel")
        self.assertGreater(middle, .1)
        self.assertLess(middle, .9)
        self.evaluate(icon, "advanceClock(1200)")
        self.assertGreater(icon.property("displayedLevel"), middle)
        self.settle_level(.9)
        self.window.setProperty("reading", .1)
        self.assertAlmostEqual(icon.property("displayedLevel"), .9, delta=.001)
        icon.setProperty("previousTick", 1000)
        self.evaluate(icon, "advanceClock(1100)")
        self.assertGreater(icon.property("displayedLevel"), .1)
        self.assertLess(icon.property("displayedLevel"), .9)
        self.window.setProperty("reading", 0)
        self.assertFalse(icon.property("animationRunning"))
        self.assertEqual(icon.property("displayedLevel"), 0)
        self.assertEqual(icon.property("phase"), 0)
        clock = self.window.findChild(QObject, "metricIconAnimation")
        self.assertTrue(clock is None or not clock.property("running"))
        self.assertEqual(self.evaluate(icon, "EffectClock.subscriberCount(clockHost)"), 0)
        QTest.qWait(1)  # QML destroy() schedules QObject deletion after this script.
        self.assertIsNone(self.window.findChild(QObject, "metricIconAnimation"))
        self.window.setProperty("reading", .6)
        self.assertTrue(icon.property("animationRunning"))
        self.assertEqual(icon.property("displayedLevel"), .6)
        self.assertEqual(icon.property("phase"), 0)

    def test_level_feedback_keeps_svg_sources_and_outer_geometry_while_tint_changes(self):
        self.load()
        for glyph, metric, effect in (*CASES, ("power", "cpu_power", "flow")):
            self.configure(glyph, metric, effect)
            self.settle_level(.4 if effect=="heat" else .1)
            sources = [item.property("source") for item in self.items() if item.property("source") is not None]
            nodes = len(self.window.findChildren(QObject))
            glyph_item=self.find("metricIconGlyph")
            geometry=tuple(glyph_item.property(field) for field in ("x","y","width","height","rotation","scale"))
            first = self.frame(.355)
            self.settle_level(.9)
            second = self.frame(.355)
            self.assertEqual([item.property("source") for item in self.items() if item.property("source") is not None], sources)
            self.assertEqual(len(self.window.findChildren(QObject)), nodes)
            self.assertEqual(tuple(glyph_item.property(field) for field in ("x","y","width","height","rotation","scale")),geometry)
            if glyph == "cpu":
                self.assertEqual(self.find("metricIconGlyph").property("opacity"), 1)
                # The original neutral pins remain intact. Real occupancy
                # changes the empty core, never a pulse of the complete shell.
                self.assertEqual(self.pixels(self.crop(first, y=0, height=5)), self.pixels(self.crop(second, y=0, height=5)))
                self.assertNotEqual(self.pixels(self.crop(first,x=6,y=6,width=6,height=6)),
                                    self.pixels(self.crop(second,x=6,y=6,width=6,height=6)))

    def test_strength_approaches_static_icon_continuously_without_losing_carrier(self):
        self.load()
        for glyph, metric, effect in CASES:
            self.configure(glyph, metric, effect)
            self.settle_level(.6)
            self.window.setProperty("strength", 0)
            static = self.crop(self.frame(.355))
            previous_opacity = 0
            differences = []
            for strength in (.0001, .01, .1, .5, 1):
                self.window.setProperty("strength", strength)
                self.window.requestUpdate()
                QTest.qWait(20)
                frame = self.crop(self.frame(.355))
                opacity = self.find("icon").property("accentOpacity")
                self.assertGreater(opacity, previous_opacity)
                previous_opacity = opacity
                difference = sum(abs(a.red()-b.red())+abs(a.green()-b.green())+abs(a.blue()-b.blue())
                    for y in range(frame.height()) for x in range(frame.width())
                    for a,b in ((frame.pixelColor(x,y),static.pixelColor(x,y)),))
                differences.append(difference)
            self.assertLess(differences[0], differences[-1] * .12, (glyph, differences))
            self.assertGreater(differences[-1], differences[2], (glyph, differences))

    def test_hardware_auto_renders_real_secondary_channels_when_primary_is_zero_or_missing(self):
        self.load()
        self.configure("cpu", "cpu_usage", "auto")
        self.window.setProperty("reading", 0)
        self.window.setProperty("valid", False)
        self.window.setProperty("channels", dict(profile="processor",available=True,load=None,thermal=.9,energy=.8))
        QTest.qWait(30)
        icon=self.find("icon")
        self.assertTrue(icon.property("compositeActive"))
        self.assertTrue(icon.property("animationRunning"))
        self.assertFalse(icon.property("loadActive"))
        self.assertTrue(icon.property("thermalActive"))
        self.assertTrue(icon.property("energyActive"))
        icon.setProperty("thermalArcPhase",.355)
        icon.setProperty("energyPhase",.355)
        image=self.crop(self.frame(.355))
        warm=sum(p.red()>p.blue()+35 and p.red()>p.green()+10 for y in range(image.height()) for x in range(image.width()) for p in (image.pixelColor(x,y),))
        blue=sum(p.blue()>p.red()+30 for y in range(image.height()) for x in range(image.width()) for p in (image.pixelColor(x,y),))
        self.assertGreater(warm,1)
        self.assertGreater(blue,1)
        self.window.setProperty("channels",dict(profile="processor",available=False,load=.9,thermal=.9,energy=.9))
        self.assertFalse(icon.property("animationRunning"))
        for name in ("displayedLoad","displayedThermal","displayedEnergy","phase"):
            self.assertEqual(icon.property(name),0)

    def test_auto_profiles_keep_only_the_channels_their_real_glyph_can_show(self):
        self.load()
        cases=[("memory","ram_percent","memory",dict(load=.7),{"loadActive"}),
            ("network","net_download","network",dict(inbound=.5,outbound=.8),{"inboundActive","outboundActive"}),
            ("download","net_download","network",dict(inbound=.5,outbound=.8),{"inboundActive"}),
            ("upload","net_upload","network",dict(inbound=.5,outbound=.8),{"outboundActive"}),
            ("disk_read","disk_read","disk",dict(inbound=.5,outbound=.8),{"inboundActive"}),
            ("battery","battery_percent","battery",dict(load=.7,inbound=.8,outbound=0),{"loadActive","inboundActive"}),
            ("time","battery_time_minutes","battery",dict(load=.7,inbound=.8,outbound=0),{"loadActive","inboundActive"}),
            ("power","battery_charge_watts","battery",dict(energy=.6,inbound=.8),{"energyActive"}),
            ("fan","cpu_fan_rpm","fan",dict(spin=.6),{"spinChannelActive"}),
            ("disk","disk_percent","volume",dict(load=.7),{"loadActive"}),
            ("temperature","storage_temp","storage",dict(thermal=.6),{"thermalActive"})]
        flags={"loadActive","thermalActive","energyActive","inboundActive","outboundActive","spinChannelActive"}
        for glyph,metric,profile,channels,expected in cases:
            self.configure(glyph,metric,"auto")
            self.window.setProperty("channels",dict(profile=profile,available=True,**channels))
            QTest.qWait(20)
            icon=self.find("icon")
            self.assertTrue(icon.property("animationRunning"),(glyph,profile))
            self.assertEqual({name for name in flags if icon.property(name)},expected,(glyph,profile))
            self.window.setProperty("channels",dict(profile=profile,available=True))
            self.assertFalse(icon.property("animationRunning"))

    def test_explicit_automatic_quantity_policy_can_disable_but_never_overrides_manual_choice(self):
        self.load()
        self.configure("sensors","external_0","auto")
        icon=self.find("icon")
        for policy in ("heat","flow","pulse","off","unvalidated"):
            icon.setProperty("automaticEffect",policy)
            expected=policy if policy!="unvalidated" else "off"
            self.assertEqual(icon.property("resolvedEffect"),expected)
            self.assertEqual(icon.property("animationRunning"),expected!="off")
        self.window.setProperty("choice","pulse")
        icon.setProperty("automaticEffect","off")
        self.assertEqual(icon.property("resolvedEffect"),"pulse")
        self.assertTrue(icon.property("animationRunning"))

    def test_ten_real_state_anchors_and_between_anchor_values_remain_continuous(self):
        self.load()
        self.configure("cpu","cpu_usage","auto")
        icon=self.find("icon")
        clock=None
        frames=[]
        for index in range(1,11):
            value=index/10
            self.window.setProperty("channels",dict(profile="processor",available=True,load=value,thermal=value,energy=value))
            self.settle_level(value)
            clock=self.window.findChild(QObject,"metricIconAnimation")
            if clock is not None:
                clock.stop()
            for name in ("loadPhase","thermalArcPhase","energyPhase"):
                icon.setProperty(name,.355)
            self.window.requestUpdate()
            QTest.qWait(20)
            frames.append(self.pixels(self.crop(self.frame(.355))))
        self.assertEqual(len(set(frames)),10)
        for value in (.32,.321,.322):
            self.window.setProperty("channels",dict(profile="processor",available=True,load=value,thermal=value,energy=value))
            self.settle_level(value)
            color=icon.property("thermalColor")
            if value==.32:
                before=color
            else:
                self.assertNotEqual(color,before)
                self.assertLess(abs(color.redF()-before.redF())+abs(color.greenF()-before.greenF())+abs(color.blueF()-before.blueF()),.03)
                before=color

    def test_64_composite_icons_keep_one_clock_and_fixed_sources_under_100ms_channel_updates(self):
        self.load(many=True)
        self.window.setProperty("uniformEffect","hardware")
        self.window.setProperty("channels",dict(profile="processor",available=True,load=.2,thermal=.2,energy=.2))
        QTest.qWait(160)
        icons=[self.find("icon_"+str(index)) for index in range(64)]
        clocks=[item for item in self.window.findChildren(QObject) if item.objectName()=="metricEffectClock"]
        self.assertEqual(len(clocks),1)
        self.assertEqual(clocks[0].property("subscriberCount"),64)
        nodes=len(self.items())
        qobject_descendants=len(self.window.findChildren(QObject))
        visual=self.items()
        images=[item for item in visual if item.inherits("QQuickImage")]
        self.assertGreater(len(images),64)
        self.assertTrue(any(str(item.property("source")).startswith("PySide6.QtCore.QUrl('data:image/svg+xml")
                            or item.property("source").toString().startswith("data:image/svg+xml") for item in images))
        source_changes,structure_changes=[0],[0]
        for item in images:
            item.sourceChanged.connect(lambda:source_changes.__setitem__(0,source_changes[0]+1))
        for item in visual:
            item.childrenChanged.connect(lambda:structure_changes.__setitem__(0,structure_changes[0]+1))
        sources=[item.property("source") for item in images]
        bounds=[]
        for icon in icons:
            rect=icon.mapRectToScene(icon.boundingRect())
            self.assertTrue(icon.isVisible() and icon.property("exposed"))
            self.assertGreaterEqual(rect.left(),0)
            self.assertGreaterEqual(rect.top(),0)
            self.assertLessEqual(rect.right(),self.window.width())
            self.assertLessEqual(rect.bottom(),self.window.height())
            bounds.append(dict(name=icon.objectName(),x=rect.x(),y=rect.y(),width=rect.width(),height=rect.height(),visible=True,exposed=True))
        frames,ticks=[0],[0]
        self.window.frameSwapped.connect(lambda:frames.__setitem__(0,frames[0]+1))
        self.find("metricIconAnimation").triggered.connect(lambda:ticks.__setitem__(0,ticks[0]+1))
        cpu_start,wall_start=time.process_time(),time.perf_counter()
        values=[]
        for level in (.2,.8,.2)*3:
            self.window.setProperty("channels",dict(profile="processor",available=True,load=level,thermal=level,energy=level))
            QTest.qWait(100)
            values.append(dict(target=level,load=icons[0].property("displayedLoad"),thermal=icons[0].property("displayedThermal"),energy=icons[0].property("displayedEnergy")))
        self.composite_perf=dict(icons=64,nodes=nodes,frames=frames[0],ticks=ticks[0],
            wall_seconds=time.perf_counter()-wall_start,cpu_seconds=time.process_time()-cpu_start,
            qobject_descendants=qobject_descendants,image_count=len(images),channels=3,update_ms=100,values=values,
            svg_source_changes=source_changes[0],visual_structure_changes=structure_changes[0],bounds=bounds,
            measurement_scope="Actual software render and QML updates only; node/source scans and image capture are outside the CPU interval")
        self.find("metricIconAnimation").stop()
        self.assertEqual(len(self.items()),nodes)
        self.assertEqual([item.property("source") for item in images],sources)
        self.assertEqual(source_changes[0],0)
        self.assertEqual(structure_changes[0],0)
        self.assertGreater(ticks[0],0)
        self.assertLessEqual(frames[0],ticks[0]+12,self.composite_perf)
        frame=self.window.grabWindow()
        dpr=self.window.devicePixelRatio()
        colors=[]
        for rect in bounds:
            color_count=sum(max(p.red(),p.green(),p.blue())-min(p.red(),p.green(),p.blue())>30
                for y in range(round(rect["y"]*dpr),round((rect["y"]+rect["height"])*dpr))
                for x in range(round(rect["x"]*dpr),round((rect["x"]+rect["width"])*dpr))
                for p in (frame.pixelColor(x,y),))
            self.assertGreater(color_count,0,rect)
            colors.append(color_count)
        self.composite_perf["colored_pixels_per_icon"]=colors
        proof=os.environ.get("DESKTOP_STATS_QA_PRESSURE_PROOF")
        if proof:
            target=Path(proof).resolve()
            self.assertTrue(target.is_relative_to(ROOT/"qa-private"))
            self.assertFalse(target.exists())
            self.assertTrue(frame.save(str(target)))
            self.composite_perf["own_window_png"]=str(target)
        self.window.hide()
        self.assertTrue(all(not icon.property("animationRunning") for icon in icons))
        self.assertEqual(self.evaluate(icons[0],"EffectClock.activeWindowCount()"),0)

    def test_typical_5_and_12_composite_icons_update_without_extra_source_work(self):
        self.load(many=True,count=5)
        self.window.setProperty("uniformEffect","hardware")
        self.window.setProperty("channels",dict(profile="processor",available=True,load=.2,thermal=.2,energy=.2))
        self.typical_perf=[]
        for count in (5,12):
            self.window.setProperty("iconCount",count)
            QTest.qWait(100)
            icons=[self.find("icon_"+str(index)) for index in range(count)]
            clock=self.find("metricIconAnimation")
            self.assertEqual(self.find("metricEffectClock").property("subscriberCount"),count)
            nodes=len(self.items())
            images=[item for item in self.items() if item.inherits("QQuickImage")]
            sources=[item.property("source") for item in images]
            frames,ticks=[0],[0]
            def frame_tick():
                frames[0]+=1
            def clock_tick():
                ticks[0]+=1
            self.window.frameSwapped.connect(frame_tick)
            clock.triggered.connect(clock_tick)
            clock.start()
            cpu,wall=time.process_time(),time.perf_counter()
            for value in (.2,.8,.2)*3:
                self.window.setProperty("channels",dict(profile="processor",available=True,load=value,thermal=value,energy=value))
                QTest.qWait(100)
            sample=dict(icons=count,frames=frames[0],ticks=ticks[0],nodes=nodes,images=len(images),
                cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall,
                measurement_scope="Actual software QML render and100ms updates; no node/source traversals in CPU interval")
            clock.stop()
            self.window.frameSwapped.disconnect(frame_tick)
            clock.triggered.disconnect(clock_tick)
            self.assertGreater(sample["ticks"],0)
            self.assertLessEqual(sample["frames"],sample["ticks"]+12)
            self.assertEqual(len(self.items()),nodes)
            self.assertEqual([item.property("source") for item in images],sources)
            self.assertTrue(all(icon.property("animationRunning") for icon in icons))
            self.typical_perf.append(sample)

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
    available:true;level:.5;motionEnabled:true}}''', QUrl.fromLocalFile(str(ROOT / "qa-private/redesign39/second-window.qml")))
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
