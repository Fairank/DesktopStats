"""Actual-size opt-in state feedback, using only owned synthetic offscreen QML."""
# ruff: noqa: E402 - Fix the private profile and offscreen platform before Qt imports.

import copy
import hashlib
import json
import math
import os
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DESKTOP_STATS_DATA", str(ROOT / "qa-private/audit-sampling39/test-profile"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, QPointF, QUrl
from PySide6.QtGui import QImage
from PySide6.QtQml import (
    QQmlComponent,
    QQmlEngine,
    QQmlExpression,
    qmlContext,
    qmlRegisterType,
    qmlTypeId,
)
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class MetricStateFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.audit_evidence = {"engine_model": "one per suite", "cases": []}
        cls.shared_engine = QQmlEngine()
        cls.initial_quit_flag = cls.app.quitOnLastWindowClosed()
        cls.audit_evidence["quit_on_last_window_closed"] = cls.initial_quit_flag
        cls.clock_component = QQmlComponent(cls.shared_engine)
        cls.clock_component.setData(b'''import QtQml
import "../native/MetricEffectClock.js" as Clock
QtObject { function activeCount() { return Clock.activeWindowCount() } }
''', QUrl.fromLocalFile(str(ROOT / "tests/metric-state-clock-fixture.qml")))
        cls.clock_probe = cls.clock_component.create()
        if cls.clock_probe is None:
            raise AssertionError([error.toString() for error in cls.clock_component.errors()])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Metric feedback tests require owned offscreen windows")

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = type(self).shared_engine
        self.warnings = []
        self.warning_callback = lambda errors: self.warnings.extend(error.toString() for error in errors)
        self.engine.warnings.connect(self.warning_callback)
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../../native" as Product
Window {id:scene;width:96;height:64;visible:false;color:dark?"#20242b":"white";
 property string glyph:"memory";property string quantity:"ram_percent";
 property string choice:"pulse";property var reading:.6;property bool valid:true;
 property string automaticMode:"";
 property var hardware:({});
 property bool motionAllowed:true;property real strength:.5;property real tempo:1;
 property real iconSize:18;property bool dark:false;
 Item {id:host;objectName:"host";anchors.fill:parent;
  Product.MetricIcon {objectName:"feedbackIcon";x:16;y:16;width:scene.iconSize;height:width;
   name:scene.glyph;metric:scene.quantity;effect:scene.choice;level:scene.reading;
   automaticEffect:scene.automaticMode;
   hardwareState:scene.hardware;
   available:scene.valid;motionEnabled:scene.motionAllowed;intensity:scene.strength;
   speed:scene.tempo;ink:scene.dark?"#f5f6f8":"#202833"}
  Product.Icon {objectName:"staticIcon";x:48;y:16;width:scene.iconSize;height:width;
   name:scene.glyph;ink:scene.dark?"#f5f6f8":"#202833"}
 }}''', QUrl.fromLocalFile(str(ROOT / "qa-private/audit-sampling39/feedback-fixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.assertIsInstance(self.window, QQuickWindow)
        self.window.show()
        QTest.qWait(35)
        self.audit_initial_exposed = self.window.isExposed()
        self.icon = self.window.findChild(QObject, "feedbackIcon")
        self.assertIsNotNone(self.icon)
        self.now = 1000.0
        self.stop_clock()

    def tearDown(self):
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.engine.warnings.disconnect(self.warning_callback)
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()
        expression = QQmlExpression(qmlContext(type(self).clock_probe), type(self).clock_probe, "activeCount()")
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        self.assertEqual(value[0] if isinstance(value, tuple) else value, 0)
        context = self.engine.rootContext()
        for key in ("barState", "actualRow", "row", "ui", "controller", "details", "config"):
            self.assertIsNone(context.contextProperty(key), key)
        self.assertEqual(self.app.topLevelWindows(), [])
        self.assertEqual(self.app.quitOnLastWindowClosed(), type(self).initial_quit_flag)
        self.audit_evidence["cases"].append(dict(test=self.id(), engine_id=id(self.engine),
            active_clock_windows=0, top_level_windows=0, root_context_state=False,
            warning_callback_disconnected=True, initial_exposed=self.audit_initial_exposed,
            quit_on_last_window_closed=self.app.quitOnLastWindowClosed()))

    @classmethod
    def tearDownClass(cls):
        cls.clock_probe.deleteLater()
        cls.clock_component.deleteLater()
        cls.shared_engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        cls.app.processEvents()
        cls.audit_evidence["engine_destroyed_at_suite_end"] = True
        cls.shared_engine = None

    def evaluate(self, source):
        expression = QQmlExpression(qmlContext(self.icon), self.icon, source)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def stop_clock(self):
        clock = self.window.findChild(QObject, "metricIconAnimation")
        if clock is not None:
            clock.stop()

    def visible_image_states(self):
        states = []
        for item in self.visual_items(self.window):
            source = item.property("source")
            if not item.inherits("QQuickImage") or not isinstance(source, QUrl) or source.isEmpty():
                continue
            if item.width() <= 0 or item.height() <= 0:
                continue
            opacity, ancestry, parent = 1.0, [], item
            while parent is not None:
                opacity *= parent.opacity() if parent.isVisible() else 0
                ancestry.append(dict(name=parent.objectName(), visible=parent.isVisible(),
                                     opacity=parent.opacity()))
                parent = parent.parentItem()
            if opacity <= 0:
                continue
            expression = QQmlExpression(qmlContext(item), item, "JSON.stringify({status:status,progress:progress})")
            value = expression.evaluate()
            self.assertFalse(expression.hasError(), expression.error().toString())
            info = json.loads(value[0] if isinstance(value, tuple) else value)
            states.append(dict(name=item.objectName(), source=source.toString(),
                               status=info["status"], progress=info["progress"],
                               effective_opacity=opacity, ancestors=ancestry,
                               feedback=any(parent["name"] == "feedbackIcon" for parent in ancestry)))
        return states

    def configure(self, **properties):
        for key, value in properties.items():
            self.window.setProperty(key, value)
        self.app.processEvents()
        if set(properties).intersection(("iconSize", "glyph", "quantity", "choice", "automaticMode")):
            # A virtual elapsed-time tick does not decode/render newly created
            # SVG textures. Finish one real frame after changing the glyph or
            # optional composition before judging its actual-size pixels.
            self.window.requestUpdate()
            QTest.qWait(20)
            # I/O readiness is a condition, not a100ms performance benchmark.
            # Reinspect live nodes: a transparent/hidden retained atlas need
            # not decode until it can actually contribute to this frame.
            started = time.monotonic()
            deadline = started + 1
            while True:
                states = self.visible_image_states()
                diagnostic = json.dumps(states, ensure_ascii=False)
                self.assertFalse(any(state["status"] == 3 for state in states),
                                 "Image.Error before pixel assertion: " + diagnostic)
                if any(state["feedback"] for state in states) and all(state["status"] == 1 for state in states):
                    break
                self.assertLess(time.monotonic(), deadline,
                                "Visible source failed to become Ready within1s: " + diagnostic)
                self.window.requestUpdate()
                QTest.qWait(5)
                self.stop_clock()
        if "iconSize" in properties:
            self.assertEqual(self.icon.width(), properties["iconSize"])
            self.assertEqual(self.icon.height(), properties["iconSize"])
        self.stop_clock()

    def advance(self, milliseconds):
        # Exercise the same elapsed-time entry used by the window's shared
        # clock. No displayed value or phase-derived color is assigned here.
        self.icon.setProperty("previousTick", self.now)
        self.now += milliseconds
        self.evaluate("advanceClock(" + repr(self.now) + ")")
        self.app.processEvents()

    def settle(self, level):
        self.configure(reading=level)
        for _ in range(20):
            self.advance(100)
        self.assertAlmostEqual(self.icon.property("displayedLevel"), level, delta=.002)

    def frame(self, phase=.25, control=False):
        # Equal phases isolate state feedback from incidental clock timing.
        self.stop_clock()
        self.icon.setProperty("phase", phase)
        self.app.processEvents()
        frame = self.window.grabWindow()
        dpr = self.window.devicePixelRatio()
        self.assertAlmostEqual(frame.width(), self.window.width() * dpr, delta=1)
        self.assertAlmostEqual(frame.height(), self.window.height() * dpr, delta=1)
        size = self.window.property("iconSize")
        return frame.copy(round((48 if control else 16) * dpr), round(16 * dpr), round(size * dpr), round(size * dpr))

    @staticmethod
    def pixels(image):
        return bytes(image.constBits())

    @staticmethod
    def chromatic_pixels(image):
        return sum(max(color.red(), color.green(), color.blue()) - min(color.red(), color.green(), color.blue()) >= 40
                   for y in range(image.height()) for x in range(image.width())
                   for color in (image.pixelColor(x, y),))

    @staticmethod
    def changed_pixels(first, second):
        return sum(sum(abs(a - b) for a, b in zip(
            first.pixelColor(x, y).getRgb()[:3], second.pixelColor(x, y).getRgb()[:3])) >= 20
            for y in range(first.height()) for x in range(first.width()))

    @staticmethod
    def state(profile, **values):
        channels = dict.fromkeys(("load", "thermal", "energy", "inbound", "outbound", "spin"))
        channels.update(values)
        return dict(channels, profile=profile, available=True)

    def settle_state(self, state, **properties):
        self.configure(choice="auto", hardware=state, **properties)
        self.window.requestUpdate()
        QTest.qWait(20)
        self.stop_clock()
        for _ in range(20):
            self.advance(100)
        for channel in ("load", "thermal", "energy", "inbound", "outbound", "spin"):
            value = state[channel] if state.get("available") is True else None
            expected = value if type(value) in (int, float) and 0 <= value <= 1 else 0
            self.assertAlmostEqual(self.icon.property("displayed" + channel.capitalize()), expected, delta=.002)

    def hardware_frame(self, phase=.075):
        for channel in ("load", "energy", "inbound", "outbound", "spin", "thermalArc"):
            self.assertTrue(self.icon.setProperty(channel + "Phase", phase))
        # This is an explicitly chosen active burst time, not an assertion that
        # intermittent discharges are coloured at every arbitrary phase.
        return self.frame(phase)

    @staticmethod
    def visual_items(window):
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(item.childItems())

    def actual_controller(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate

        with patch.object(controls, "load", return_value=validate(copy.deepcopy(DEFAULT))):
            controller = controls.Controller()
        self.addCleanup(controller.close)
        return controller

    @staticmethod
    def actual_row(controller, metric="cpu_usage", **preferences):
        controller._saved["top_bar"]["items"] = [dict(id="b_actual", metric=metric, prefs=dict(
            style="icon_value", icon_effect="auto") | preferences)]
        return controller.topBarRows()[0]

    @contextmanager
    def actual_content(self, row, height=32):
        # No glyph/name/effect is reconstructed here: the real production
        # component receives the exact controller row and owns its bindings.
        self.window.hide()
        component = QQmlComponent(self.engine)
        component.setData(b'''import QtQuick
import "../../native" as Product
Window { id:scene;width:360;height:100;visible:false;color:"white";
 property var actualRow:({});property bool motionAllowed:true;property real barHeight:32;
 Product.TopBarMetricContent {objectName:"actualContent";x:24;y:24;width:implicitWidth;
  height:scene.barHeight;row:scene.actualRow;motionEnabled:scene.motionAllowed;
  fontFamily:"Segoe UI Variable";ink:"#202833";muted:"#566272"}
}''', QUrl.fromLocalFile(str(ROOT / "qa-private/audit-sampling39/actual-content-fixture.qml")))
        window = component.createWithInitialProperties({"actualRow": row, "barHeight": height})
        self.assertIsInstance(window, QQuickWindow, [error.toString() for error in component.errors()])
        try:
            window.show()
            QTest.qWait(35)
            self.stop_window_clock(window)
            yield window
        finally:
            window.hide()
            window.destroy()
            window.deleteLater()
            component.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()

    @contextmanager
    def actual_details(self, controller):
        from native_surface import MaterialSurface
        from tests.test_top_bar_module_qml import ModuleState

        class DetailState(ModuleState):
            motionEnabled = Property(bool, lambda self: True, constant=True)

        self.window.hide()
        if qmlTypeId("DesktopStats", 1, 0, "MaterialSurface") < 0:
            qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
        state = DetailState()
        state.preferences = copy.deepcopy(controller._saved)
        state.details = controller.topBarDetailRow("b_actual")
        component = QQmlComponent(self.engine)
        component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        window = component.createWithInitialProperties({"barState": state})
        self.assertIsInstance(window, QQuickWindow, [error.toString() for error in component.errors()])
        try:
            window.show()
            QTest.qWait(35)
            self.stop_window_clock(window)
            yield window, state
        finally:
            window.hide()
            window.destroy()
            window.deleteLater()
            component.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()

    def named_visual(self, window, name):
        result = next((item for item in self.visual_items(window) if item.objectName() == name), None)
        self.assertIsNotNone(result, name)
        return result

    @staticmethod
    def stop_window_clock(window):
        clock = window.findChild(QObject, "metricIconAnimation")
        if clock is not None:
            clock.stop()

    def routed_frame(self, window, item, padding=0):
        self.stop_window_clock(window)
        self.app.processEvents()
        image = window.grabWindow()
        dpr = window.devicePixelRatio()
        self.assertAlmostEqual(image.width(), window.width()*dpr, delta=1)
        self.assertAlmostEqual(image.height(), window.height()*dpr, delta=1)
        start = item.mapToScene(QPointF(-padding, -padding))
        return image.copy(round(start.x()*dpr), round(start.y()*dpr),
                          round((item.width()+2*padding)*dpr), round((item.height()+2*padding)*dpr))

    def publish_actual_row(self, window, row):
        window.setProperty("actualRow", row)
        window.requestUpdate()
        QTest.qWait(25)
        self.stop_window_clock(window)

    def advance_actual(self, window, icon, milliseconds=100):
        self.stop_window_clock(window)
        icon.setProperty("previousTick", self.now)
        self.now += milliseconds
        expression = QQmlExpression(qmlContext(icon), icon, "advanceClock(" + repr(self.now) + ")")
        expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        self.app.processEvents()

    def test_real_atlas_has_short_dark_gaps_distinct_positions_and_reproducible_inputs(self):
        # Artwork generation remains an optional Pillow dependency. The shipped
        # product/clean-source test inspects actual PNG pixels using Qt only.
        manifest = json.loads((ROOT / "assets/metric-motion/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["stage_count"], manifest["frame_count"]), (10, 48))
        for field in ("generator", "noise"):
            self.assertEqual(hashlib.sha256((ROOT / manifest[field]).read_bytes()).hexdigest(),
                             manifest[field + "_sha256"])
        self.assertNotEqual(manifest["burst_schedules"]["warm"], manifest["burst_schedules"]["blue"])
        observations = {}
        for texture in manifest["textures"]:
            path = ROOT / texture["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), texture["sha256"])
            channel = "warm" if "warm" in path.name else "blue"
            sheet = QImage(str(path))
            self.assertFalse(sheet.isNull())
            self.assertEqual([sheet.width(), sheet.height()], texture["size"])
            cell = manifest["cell_pixels"]
            stages = []
            for index in range(10):
                frames = [sheet.copy(f*cell, index*cell, cell, cell).convertToFormat(QImage.Format_RGBA8888)
                          for f in range(48)]
                alphas = [bytes(frame.constBits())[3::4] for frame in frames]
                active = [i for i, alpha in enumerate(alphas) if any(alpha)]
                gaps = [i for i, alpha in enumerate(alphas) if not any(alpha)]
                self.assertTrue(active, (channel, index))
                self.assertTrue(gaps, "A real atlas must contain empty time, not a permanent carrier")
                centres = []
                for slot in range(3):
                    phase = manifest["burst_schedules"][channel][slot] + .6 * (
                        manifest["stage_parameters"][index]["burst_duration"] * manifest["duration_weights"][slot])
                    alpha = alphas[round(phase*48) % 48]
                    visible = [(pixel % cell, pixel // cell, value) for pixel, value in enumerate(alpha) if value >= 24]
                    self.assertTrue(visible, (channel, index, slot))
                    total = sum(value for _, _, value in visible)
                    centres.append(tuple(sum(point[axis]*point[2] for point in visible)/total/cell*32
                                         for axis in (0, 1)))
                for a in range(3):
                    for b in range(a):
                        self.assertGreater(math.dist(centres[a], centres[b]), 2,
                                           "Three event labels must not conceal one fixed roof")
                areas = [sum(value >= 24 for value in alpha) for alpha in alphas]
                stages.append(dict(stage=index+1, active_frames=len(active), dark_frames=len(gaps),
                                   max_coverage=max(areas), centres=centres,
                                   unique_frames=len({bytes(frame.constBits()) for frame in frames})))
            self.assertGreater(stages[-1]["active_frames"], stages[0]["active_frames"])
            self.assertGreater(stages[-1]["max_coverage"], stages[0]["max_coverage"])
            self.assertEqual(len({(row["active_frames"], row["max_coverage"], row["unique_frames"])
                                  for row in stages}), 10)
            observations[channel] = stages
        self.audit_evidence["real_atlas_cycles"] = observations

    def test_controller_ten_stage_cycles_keep_sources_clock_and_digits_fixed(self):
        ui = self.actual_controller()
        ui._data = dict(time=time.time(), cpu_usage=0, cpu_temp=41.875, cpu_power=20)
        with self.actual_content(self.actual_row(ui)) as window:
            icon = self.named_visual(window, "topBarContentIcon")
            warm = self.named_visual(window, "metricIconWarmDischarge")
            blue = self.named_visual(window, "metricIconBlueDischarge")
            images = [item for item in self.visual_items(window)
                      if item.objectName().startswith("metricDischargeCell_")]
            self.assertEqual(len(images), 8)
            sources = [item.property("source") for item in images]
            self.assertTrue(all(isinstance(value, QUrl) and value.toLocalFile().endswith(".png") for value in sources))
            changes = []
            for item in images:
                item.sourceChanged.connect(lambda: changes.append(True))
            initial_count = len(list(self.visual_items(window)))
            rows = []
            for index in range(10):
                activity = (index+1)/10
                ui._data.update(cpu_temp=125*(.28+.55*activity), cpu_power=200*activity)
                row = self.actual_row(ui)
                self.assertEqual(row["numeric_value"], 0)
                self.publish_actual_row(window, row)
                for _ in range(20):
                    self.advance_actual(window, icon)
                self.assertAlmostEqual(warm.property("stagePosition"), index, delta=.003)
                self.assertAlmostEqual(blue.property("stagePosition"), index, delta=.003)
                frames, digits = [], []
                content = self.named_visual(window, "actualContent")
                for frame_index in range(48):
                    phase = frame_index/48
                    icon.setProperty("thermalArcPhase", phase)
                    icon.setProperty("energyPhase", (phase+.137)%1)
                    frames.append(self.pixels(self.routed_frame(window, icon, padding=5)))
                    text = self.routed_frame(window, content)
                    start = round(22*window.devicePixelRatio())
                    digits.append(self.pixels(text.copy(start, 0, text.width()-start, text.height())))
                self.assertGreater(len(set(frames)), 8, "Ten stage labels must drive actual time-varying pixels")
                self.assertEqual(len(set(digits)), 1, "Discharges must not blink the numbers or their gap")
                self.assertEqual([item.property("source") for item in images], sources)
                self.assertEqual(len(list(self.visual_items(window))), initial_count)
                rows.append(dict(stage=index+1, unique_frames=len(set(frames)),
                                 source_count=len(images), visual_nodes=initial_count))
            # Cold/hot transitions while power remains live must retain the warm
            # layer and its four quads, not rebuild/decode them on every sample.
            ui._data["cpu_temp"] = 30
            self.publish_actual_row(window, self.actual_row(ui))
            for _ in range(20):
                self.advance_actual(window, icon)
            self.assertFalse(icon.property("thermalArcActive"))
            self.assertEqual(self.named_visual(window, "metricIconWarmDischarge"), warm)
            ui._data["cpu_temp"] = 100
            self.publish_actual_row(window, self.actual_row(ui))
            self.assertEqual(self.named_visual(window, "metricIconWarmDischarge"), warm)
            self.assertEqual([item.property("source") for item in images], sources)
            self.assertEqual(changes, [])
            self.assertEqual(len([item for item in window.findChildren(QObject)
                                  if item.objectName() == "metricEffectClock"]), 1)
            window.hide()
            self.assertFalse(icon.property("animationRunning"))
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
            self.assertIsNone(window.findChild(QObject, "metricIconAnimation"))
            self.audit_evidence["actual_controller_cycles"] = rows

    def test_real_content_18px_cold_hot_layers_guards_and_digit_clearance(self):
        ui = self.actual_controller()
        ui._data = dict(time=time.time(), cpu_usage=0, cpu_temp=30, cpu_power=0)
        row = self.actual_row(ui)
        with self.actual_content(row) as window:
            icon = self.named_visual(window, "topBarContentIcon")
            content = self.named_visual(window, "actualContent")
            value = self.named_visual(window, "topBarContentValue")
            self.assertEqual((icon.property("name"), icon.property("metric"), icon.width()), ("cpu", "cpu_usage", 18))
            self.assertFalse(icon.property("thermalArcActive"))
            self.assertFalse(icon.property("animationRunning"))
            self.assertIsNone(window.findChild(QObject, "metricIconAnimation"))
            self.assertEqual(value.x(), 23)
            ui._data.update(cpu_temp=100, cpu_power=160)
            row = self.actual_row(ui)
            self.publish_actual_row(window, row)
            self.assertTrue(icon.property("thermalArcActive"))
            self.assertTrue(icon.property("energyActive"))
            geometry = (content.width(), content.height(), content.implicitWidth(), value.x())
            text_frames = []
            # Include a DIP of the gap before text: external arcs must not
            # change either the numeral ink or its immediate background.
            text_region = value.parentItem()
            for phase in (.1, .3, .5, .7, .9):
                for field in ("thermalArcPhase", "energyPhase", "phase", "loadPhase"):
                    self.assertTrue(icon.setProperty(field, phase))
                text = self.routed_frame(window, text_region)
                dpr = window.devicePixelRatio()
                text = text.copy(round(22*dpr), 0, text.width()-round(22*dpr), text.height())
                text_frames.append(self.pixels(text))
                self.assertEqual((content.width(), content.height(), content.implicitWidth(), value.x()), geometry)
            self.assertEqual(len(set(text_frames)), 1, "Arcs must not reach the real digits starting at23DIP")
            for missing, expected in (("cpu_temp", (False, True)), ("cpu_power", (True, False))):
                ui._data = dict(time=time.time(), cpu_usage=0, cpu_temp=100, cpu_power=160)
                del ui._data[missing]
                self.publish_actual_row(window, self.actual_row(ui))
                for _ in range(20):
                    self.advance_actual(window, icon)
                self.assertEqual((icon.property("thermalArcActive"), icon.property("energyActive")), expected)
            for preferences in (dict(icon_effect="off"), dict(effect_intensity=0)):
                ui._data = dict(time=time.time(), cpu_usage=0, cpu_temp=100, cpu_power=160)
                self.publish_actual_row(window, self.actual_row(ui, **preferences))
                self.assertFalse(icon.property("animationRunning"))
                inactive = self.pixels(self.routed_frame(window, icon, padding=3))
                window.setProperty("motionAllowed", False)
                self.assertEqual(self.pixels(self.routed_frame(window, icon, padding=3)), inactive)
                window.setProperty("motionAllowed", True)
            self.publish_actual_row(window, self.actual_row(ui))
            window.setProperty("motionAllowed", False)
            self.assertFalse(icon.property("animationRunning"))
            window.setProperty("motionAllowed", True)
            self.assertTrue(icon.property("animationRunning"))
            ui._data["time"] = time.time()-100
            self.publish_actual_row(window, self.actual_row(ui))
            self.assertFalse(icon.property("animationRunning"))
            self.assertFalse(icon.property("thermalArcActive"))
            self.assertFalse(icon.property("energyActive"))

    def test_real_pair_11px_uses_selected_network_and_canonical_units(self):
        ui = self.actual_controller()
        ui._data = dict(time=time.time(), cpu_temp=125, net_download=99, net_upload=99,
                        networks={"chosen": dict(net_download=20, net_upload=0),
                                  "other": dict(net_download=99, net_upload=99)})
        row = self.actual_row(ui, "net_download", style="duplex", network_target="chosen", network_unit="Mbps")
        with self.actual_content(row) as window:
            down = self.named_visual(window, "topBarPairIcon_0")
            up = self.named_visual(window, "topBarPairIcon_1")
            self.assertEqual((down.width(), up.width()), (11, 11))
            self.assertEqual((down.property("name"), up.property("name")), ("download", "upload"))
            self.assertEqual(down.property("level"), .2)
            self.assertEqual(row["paired_rows"][0]["numeric_value"], 160)
            self.assertTrue(down.property("inboundActive"))
            self.assertFalse(up.property("animationRunning"))
            self.assertFalse(down.property("thermalArcActive"))
            ui._data["networks"]["chosen"]["net_download"] = None
            self.publish_actual_row(window, self.actual_row(ui, "net_download", style="duplex",
                                                          network_target="chosen", network_unit="Mbps"))
            # Repeater delegates may be replaced on a fresh controller row.
            down = self.named_visual(window, "topBarPairIcon_0")
            up = self.named_visual(window, "topBarPairIcon_1")
            self.assertFalse(down.property("animationRunning"))
            self.assertFalse(up.property("animationRunning"))
            self.assertIsNone(window.findChild(QObject, "metricIconAnimation"))

    def test_real_details_16px_inherits_selected_gpu_and_fan_is_spin_only(self):
        ui = self.actual_controller()
        ui._data = dict(time=time.time(), gpus={"0": dict(gpu_usage=100, gpu_temp=125, gpu_power=300),
                        "chosen": dict(gpu_usage=0, gpu_temp=100, gpu_power=150, gpu_fan_percent=0)})
        self.actual_row(ui, "gpu_usage", gpu_target="chosen")
        with self.actual_details(ui) as (window, state):
            icons = [item for item in self.visual_items(window)
                     if item.metaObject().indexOfProperty("hardwareState") >= 0 and item.width() == 16]
            self.assertEqual(len(icons), 1)
            icon = icons[0]
            self.assertEqual((icon.property("name"), icon.property("metric")), ("gpu", "gpu_usage"))
            hardware = icon.property("hardwareState")
            hardware = hardware.toVariant() if hasattr(hardware, "toVariant") else hardware
            self.assertEqual((hardware["load"], hardware["thermal"], hardware["energy"]), (0, .8, .5))
            self.assertTrue(icon.property("energyActive"))
            self.assertTrue(icon.property("thermalActive"))
            self.assertEqual(state.details["numeric_value"], 0)
        row = self.actual_row(ui, "gpu_fan_percent", gpu_target="chosen")
        with self.actual_content(row) as window:
            icon = self.named_visual(window, "topBarContentIcon")
            self.assertEqual(icon.property("name"), "fan")
            self.assertFalse(icon.property("animationRunning"), "A stopped fan must not subscribe because itsGPU is hot")
            self.assertFalse(icon.property("thermalArcActive"))
            self.assertIsNone(window.findChild(QObject, "metricIconAnimation"))

    @staticmethod
    def color_counts(image):
        warm, blue = 0, 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                warm += color.red() > color.green() + 30 and color.red() > color.blue() + 30
                blue += color.blue() > color.red() + 30 and color.blue() > color.green() + 20
        return warm, blue

    def interior(self, image, bounds):
        # Fixed semantic interiors from the original24-unit Lucide bodies,
        # expressed in the18DIP icon. Do not count tinted outer strokes/text.
        dpr = self.window.devicePixelRatio()
        x, y, width, height = bounds
        return image.copy(round(x*dpr), round(y*dpr), round(width*dpr), round(height*dpr))

    def test_real_percentage_fills_change_a_large_part_of_the_native_size_interior(self):
        cases = (("processor", "cpu", "cpu_usage", (6.75, 6.75, 4.5, 4.5)),
                 ("processor", "gpu", "gpu_usage", (3, 10, 10, 2)),
                 ("memory", "memory", "ram_percent", (3, 6, 12, 4)),
                 ("battery", "battery", "battery_percent", (3, 6, 9.5, 4)),
                 ("volume", "disk", "disk_percent", (3, 10.5, 12, 3.5)))
        for dark in (False, True):
            for profile, glyph, metric, interior in cases:
                with self.subTest(dark=dark, profile=profile, glyph=glyph):
                    self.configure(dark=dark, glyph=glyph, quantity=metric, strength=.5)
                    extents, frames = [], []
                    for level in (.1, .5, .9):
                        self.settle_state(self.state(profile, load=level), reading=level)
                        chamber = self.named_visual(self.window, "metricIconPulseCore")
                        self.assertAlmostEqual(chamber.property("fillExtent"), level, delta=.002)
                        extents.append(chamber.width()*chamber.height())
                        frames.append(self.pixels(self.interior(self.hardware_frame(), interior)))
                    # Proportional geometry remains real data, even when a
                    # transient filament or low-opacity CPU ink affects RGB.
                    self.assertAlmostEqual(extents[1]/extents[0], 5, delta=.01)
                    self.assertAlmostEqual(extents[2]/extents[0], 9, delta=.01)
                    self.assertEqual(len(set(frames)), 3)
        # The saved manualRAMpulse needs the same large-area distinction.
        self.configure(glyph="memory", quantity="ram_percent", choice="pulse", hardware={},
                       automaticMode="", dark=False, strength=.5)
        fills = []
        for level in (.1, .5, .9):
            self.settle(level)
            chamber = self.named_visual(self.window, "metricIconPulseCore")
            self.assertAlmostEqual(chamber.property("fillExtent"), level, delta=.002)
            fills.append(self.pixels(self.interior(self.frame(.075), (3, 6, 12, 4))))
        self.assertEqual(len(set(fills)), 3)

    def test_cold_processor_stays_quiet_and_hot_decoration_preserves_the_original_skeleton(self):
        for dark in (False, True):
            for glyph, metric in (("cpu", "cpu_usage"), ("gpu", "gpu_usage")):
                with self.subTest(dark=dark, glyph=glyph):
                    self.configure(glyph=glyph, quantity=metric, dark=dark, strength=.5)
                    self.configure(choice="auto", hardware=self.state("processor", thermal=30/125), reading=0)
                    self.assertFalse(self.icon.property("thermalArcActive"))
                    self.assertFalse(self.icon.property("animationRunning"))
                    self.settle_state(self.state("processor", thermal=100/125), reading=0)
                    self.assertTrue(self.icon.property("thermalArcActive"))
                    skeleton = self.named_visual(self.window, "metricIconGlyph")
                    self.assertTrue(skeleton.isVisible())
                    self.assertEqual((skeleton.width(), skeleton.height(), skeleton.property("name")), (18, 18, glyph))
                    self.assertGreaterEqual(skeleton.opacity(), .8)
                    # Local warm arcs may preserve neutral pins/frame. The old
                    # half-outline recolouring draft is deliberately retired;
                    # actual native-size motion still requires design review.
                    self.assertEqual(self.window.property("reading"), 0)

    def test_actual_memory_amount_uses_real_occupancy_and_strength_never_changes_fill_extent(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate

        with patch.object(controls, "load", return_value=validate(copy.deepcopy(DEFAULT))):
            ui = controls.Controller()
        self.addCleanup(ui.close)
        ui._data = dict(time=time.time(), ram_used_gb=8, ram_total_gb=16, ram_percent=50)
        frames = []
        for metric in ("ram_used_gb", "ram_percent"):
            ui._saved["top_bar"]["items"] = [dict(id="b_amount", metric=metric, prefs=dict(
                style="icon_value", icon_effect="auto"))]
            row = ui.topBarRows()[0]
            self.assertEqual(row["hardware_state"]["load"], .5)
            self.settle_state(row["hardware_state"], glyph=row["icon"], quantity=metric,
                              reading=row["effect_level"], valid=row["available"])
            frames.append(self.pixels(self.hardware_frame()))
        self.assertEqual(frames[0], frames[1], "8of16GB means50%, not8of128GB display scale")
        chamber = self.window.findChild(QObject, "metricIconPulseCore")
        self.assertIsNotNone(chamber)
        extent = (chamber.width(), chamber.height(), chamber.x(), chamber.y())
        for strength in (.1, .5, 1):
            self.configure(strength=strength)
            self.frame(.8)
            self.assertEqual((chamber.width(), chamber.height(), chamber.x(), chamber.y()), extent)
            self.assertEqual(chamber.property("fillExtent"), .5)
        self.configure(glyph="memory", quantity="ram_used_gb", choice="pulse", hardware={}, strength=.5)
        sizes = []
        for amount in (.05, .95):
            self.settle(amount)
            self.frame(.075)
            self.assertFalse(chamber.property("proportional"))
            sizes.append((chamber.width(), chamber.height()))
        self.assertEqual(sizes[0], sizes[1], "An arbitraryGB display scale must not become a percentage fill")

    def test_ten_state_points_render_for_every_profile_without_quantizing_between_anchors(self):
        cases = (("processor", "cpu", "cpu_usage", "load"),
                 ("memory", "memory", "ram_percent", "load"),
                 ("network", "network", "net_download", "inbound"),
                 ("disk", "disk", "disk_read", "inbound"),
                 ("battery", "battery", "battery_percent", "load"),
                 ("fan", "fan", "cpu_fan_rpm", "spin"),
                 ("volume", "disk", "disk_percent", "load"),
                 ("storage", "disk", "storage_temp", "thermal"))
        for profile, glyph, metric, channel in cases:
            with self.subTest(profile=profile):
                self.configure(glyph=glyph, quantity=metric)
                values = []
                for index in range(10):
                    # Cold temperature is allowed to remain quiet. Load and
                    # other activity still retain the full0..1 ten-point range.
                    value = .35+.65*index/9 if channel == "thermal" else index/9
                    self.settle_state(self.state(profile, **{channel: value}), reading=None, valid=False)
                    values.append(self.icon.property("displayed" + channel.capitalize()))
                    self.assertAlmostEqual(values[-1], value, delta=.002)
                self.assertEqual(len(set(values)), 10)
                # Ten runtime atlas sequences are checked separately. A fixed
                # phase may correctly be dark in multiple stages.
        self.configure(glyph="cpu", quantity="cpu_usage")
        colors = []
        for value in (1/3, .37, 4/9):
            self.settle_state(self.state("processor", thermal=value), reading=None, valid=False)
            colors.append(self.icon.property("thermalColor").getRgbF()[:3])
        self.assertNotEqual(colors[0], colors[1])
        self.assertNotEqual(colors[1], colors[2])
        for before, middle, after in zip(*colors):
            self.assertGreaterEqual(middle, min(before, after) - .0001)
            self.assertLessEqual(middle, max(before, after) + .0001)
        self.assertAlmostEqual(self.icon.property("displayedThermal"), 4/9, delta=.002)

    def test_hot_processor_has_simultaneous_warm_heat_and_blue_energy_with_primary_load_zero(self):
        self.configure(glyph="cpu", quantity="cpu_usage")
        state = self.state("processor", load=0, thermal=.9, energy=.9)
        self.settle_state(state, reading=0, valid=True)
        self.assertFalse(self.icon.property("loadActive"))
        self.assertTrue(self.icon.property("thermalActive"))
        self.assertTrue(self.icon.property("energyActive"))
        self.assertIsNotNone(self.named_visual(self.window, "metricIconWarmDischarge"))
        self.assertIsNotNone(self.named_visual(self.window, "metricIconBlueDischarge"))
        both = self.pixels(self.hardware_frame())
        state["energy"] = None
        self.settle_state(state, reading=None, valid=False)
        self.assertFalse(self.icon.property("energyActive"))
        warm_only = self.pixels(self.hardware_frame())
        self.assertNotEqual(both, warm_only)
        state.update(thermal=None, energy=.9)
        self.settle_state(state, reading=None, valid=False)
        self.assertFalse(self.icon.property("thermalActive"))
        energy_only = self.pixels(self.hardware_frame())
        self.assertNotEqual(warm_only, energy_only)

    def test_explicit_unavailable_or_zero_channels_never_fall_back_to_a_positive_primary(self):
        self.configure(glyph="cpu", quantity="cpu_usage")
        cases = (self.state("processor"),
                 self.state("processor", load=0, thermal=0, energy=0),
                 dict(self.state("processor", load=1, thermal=1, energy=1), available=False),
                 dict(self.state("processor", load=1), profile="unknown"))
        for state in cases:
            with self.subTest(state=state):
                self.configure(choice="auto", hardware=state, reading=1, valid=True)
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
                self.assertFalse(self.icon.property("animationRunning"))
                self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
                self.assertIsNone(self.window.findChild(QObject, "metricIconAnimation"))
        state = self.state("processor", thermal=.7, energy=.6)
        self.settle_state(state, reading=None, valid=False)
        for field in ("motionAllowed",):
            self.configure(**{field: False})
            self.assertFalse(self.icon.property("thermalActive"))
            self.assertFalse(self.icon.property("energyActive"))
            self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
            self.configure(**{field: True})
            self.settle_state(state, reading=None, valid=False)
        host = self.window.findChild(QObject, "host")
        host.setVisible(False)
        self.assertEqual(self.icon.property("displayedThermal"), 0)
        self.assertEqual(self.icon.property("displayedEnergy"), 0)
        self.assertFalse(self.icon.property("animationRunning"))
        host.setVisible(True)
        self.settle_state(state, reading=None, valid=False)
        self.assertGreaterEqual(self.chromatic_pixels(self.hardware_frame()), 6)

    def test_actual_controller_selected_gpu_state_reaches_qml_without_borrowing_hot_peer(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate

        value = copy.deepcopy(DEFAULT)
        value["top_bar"]["items"] = [dict(id="b_gpu", metric="gpu_usage", prefs=dict(
            gpu_target="1", style="icon_value", icon_effect="auto"))]
        with patch.object(controls, "load", return_value=validate(value)):
            ui = controls.Controller()
        self.addCleanup(ui.close)
        ui._data = dict(time=time.time(), gpu_usage=100, gpu_temp=125, gpu_power=300,
                        gpus={"0": dict(gpu_usage=100, gpu_temp=125, gpu_power=300),
                              "1": dict(gpu_usage=20, gpu_temp=25, gpu_power=30)})
        row = ui.topBarRows()[0]
        state = row["hardware_state"]
        self.assertEqual(row["icon"], "gpu")
        self.assertEqual([state[key] for key in ("load", "thermal", "energy")], [.2, .2, .1])
        self.settle_state(state, glyph=row["icon"], quantity=row["metric"], reading=row["effect_level"], valid=row["available"])
        first = self.pixels(self.hardware_frame())
        ui._data["gpus"]["0"].update(gpu_usage=0, gpu_temp=0, gpu_power=0)
        self.assertEqual(ui.topBarRows()[0]["hardware_state"], state)
        self.assertEqual(self.pixels(self.hardware_frame()), first)
        del ui._data["gpus"]["1"]
        missing = ui.topBarRows()[0]
        self.assertFalse(missing["hardware_state"]["available"])
        self.configure(hardware=missing["hardware_state"], reading=missing["effect_level"], valid=missing["available"])
        self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))

    def test_actual_battery_power_glyph_uses_only_its_own_real_power_channel(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate

        value = copy.deepcopy(DEFAULT)
        value["top_bar"]["items"] = [dict(id="b_battery", metric="battery_charge_watts", prefs=dict(
            style="icon_value", icon_effect="auto"))]
        with patch.object(controls, "load", return_value=validate(value)):
            ui = controls.Controller()
        self.addCleanup(ui.close)
        ui._data = dict(time=time.time(), battery_percent=80, battery_charge_watts=20)
        charge = ui.topBarRows()[0]
        self.assertEqual(charge["icon"], "power")
        self.assertEqual(charge["hardware_state"]["energy"], .2)
        self.settle_state(charge["hardware_state"], glyph=charge["icon"], quantity=charge["metric"],
                          reading=charge["effect_level"], valid=charge["available"])
        self.assertTrue(self.icon.property("energyActive"))
        self.assertIsNotNone(self.named_visual(self.window, "metricIconBlueDischarge"))
        cycle = {self.pixels(self.hardware_frame(frame/48)) for frame in range(48)}
        self.assertGreater(len(cycle), 2, "Its own power must reach actual intermittent drawing")
        ui._saved["top_bar"]["items"][0]["metric"] = "battery_discharge_watts"
        missing_discharge = ui.topBarRows()[0]
        self.assertIsNone(missing_discharge["hardware_state"]["energy"])
        self.configure(glyph=missing_discharge["icon"], quantity=missing_discharge["metric"],
                       hardware=missing_discharge["hardware_state"], reading=missing_discharge["effect_level"],
                       valid=missing_discharge["available"])
        self.assertFalse(self.icon.property("animationRunning"), "Charging or SOC must not invent discharge activity")
        self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))

    def test_default_off_keeps_texture_budget_at_or_below_the_original_static_icon(self):
        self.configure(choice="off", hardware=self.state("processor", load=1, thermal=1, energy=1))
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        images, pending = [], [self.icon]
        while pending:
            item = pending.pop()
            source = item.property("source")
            if isinstance(source, QUrl) and not source.isEmpty():
                images.append(source.toString())
            pending.extend(item.childItems())
        # The immutable0.24 component had one main glyph plus two dormant heat
        # textures. A ten-color palette must not multiply dormant SVG objects.
        self.assertLessEqual(len(images), 3, images)
        self.assertIsNone(self.window.findChild(QObject, "metricIconAnimation"))
        self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))

    def test_real_frequency_and_battery_time_routes_render_their_truthful_activity(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate

        with patch.object(controls, "load", return_value=validate(copy.deepcopy(DEFAULT))):
            ui = controls.Controller()
        self.addCleanup(ui.close)
        ui._data = dict(time=time.time(), cpu_frequency=4,
                        gpus={"chosen": dict(gpu_clock=2000, gpu_memory_clock=6000)},
                        battery_time_minutes=180, battery_percent=70,
                        battery_charge_watts=20, battery_discharge_watts=0)
        for metric, preferences in (("cpu_frequency", {}),
                                    ("gpu_clock", {"gpu_target": "chosen"}),
                                    ("gpu_memory_clock", {"gpu_target": "chosen"}),
                                    ("battery_time_minutes", {})):
            with self.subTest(metric=metric):
                ui._saved["top_bar"]["items"] = [dict(id="b_route", metric=metric,
                    prefs=dict(style="icon_value", icon_effect="auto", **preferences))]
                row = ui.topBarRows()[0]
                self.assertTrue(row["available"])
                self.configure(glyph=row["icon"], quantity=metric, choice=row["icon_effect"],
                               hardware=row["hardware_state"], automaticMode=row["auto_effect"],
                               reading=row["effect_level"], valid=row["available"])
                if metric == "battery_time_minutes":
                    self.assertEqual(row["icon"], "time")
                    self.settle_state(row["hardware_state"])
                    self.assertTrue(self.icon.property("loadActive"))
                    self.assertTrue(self.icon.property("inboundActive"))
                    self.assertFalse(self.icon.property("outboundActive"))
                    image = self.hardware_frame()
                else:
                    self.assertEqual(row["icon"], "frequency")
                    self.assertEqual(row["hardware_state"], {})
                    self.assertEqual(row["effect_level"], .5)
                    self.settle(row["effect_level"])
                    image = self.frame(.075)
                self.assertGreaterEqual(self.chromatic_pixels(image), 3)
                ui._data["time"] = time.time() - 100
                stale = ui.topBarRows()[0]
                self.configure(hardware=stale["hardware_state"], reading=stale["effect_level"],
                               valid=stale["available"])
                self.assertFalse(self.icon.property("animationRunning"))
                self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
                ui._data["time"] = time.time()

    def test_real_external_typed_routes_do_not_infer_hardware_from_misleading_names(self):
        import native_controller as controls
        from external_sensor import PROVIDER, SENSOR_TYPES
        from stats_config import DEFAULT, validate

        with patch.object(controls, "load", return_value=validate(copy.deepcopy(DEFAULT))):
            ui = controls.Controller()
        self.addCleanup(ui.close)
        expected = {"Temperature": ("temperature", "heat"), "Fan": ("fan", "spin"), "Noise": ("noise", "off"),
                    "Voltage": ("voltage", "flow"), "Current": ("voltage", "flow"),
                    "Power": ("power", "flow"), "Clock": ("frequency", "pulse"),
                    "Load": ("grid", "pulse"), "Level": ("grid", "pulse"),
                    "Throughput": ("sensors", "pulse")}
        for kind, meta in SENSOR_TYPES.items():
            with self.subTest(sensor_type=kind):
                binding = dict(provider=PROVIDER, sensor_id="/synthetic/exact/channel",
                               sensor_type=kind, name="CPU Fan Power Temperature Download",
                               hardware_name="Synthetic unclassified hardware")
                ui._saved["top_bar"]["items"] = [dict(id="b_typed", metric="external_1", prefs=dict(
                    style="icon_value", icon_effect="auto", sensor_bindings={"external_1": binding}))]
                ui._data = dict(time=time.time(), external_sensors={binding["sensor_id"]: dict(
                    id=binding["sensor_id"], type=kind, unit=meta["unit"],
                    value=meta["maximum"]*.5, available=True)})
                row = ui.topBarRows()[0]
                self.assertEqual((row["icon"], row["auto_effect"]), expected.get(kind, ("sensors", "off")))
                self.assertEqual(row["hardware_state"], {})
                self.configure(glyph=row["icon"], quantity=row["metric"], choice=row["icon_effect"],
                               automaticMode=row["auto_effect"], hardware=row["hardware_state"],
                               reading=row["effect_level"], valid=row["available"])
                if row["auto_effect"] == "off":
                    self.assertFalse(self.icon.property("animationRunning"))
                    self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
                else:
                    self.settle(row["effect_level"])
                    self.assertGreaterEqual(self.chromatic_pixels(self.frame(.075)), 3)
                ui._data["external_sensors"][binding["sensor_id"]]["type"] = "invalid"
                invalid = ui.topBarRows()[0]
                self.assertFalse(invalid["available"])
                self.configure(reading=invalid["effect_level"], valid=invalid["available"])
                self.assertFalse(self.icon.property("animationRunning"))
                self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))

    def test_low_middle_high_state_changes_real18px_color_and_rendered_pixels(self):
        for dark in (False, True):
            self.configure(dark=dark)
            for glyph, metric, effect in (("temperature", "cpu_temp", "heat"),
                                          ("fan", "cpu_fan_rpm", "spin"),
                                          ("network", "net_download", "flow"),
                                          ("memory", "ram_percent", "pulse")):
                with self.subTest(dark=dark, glyph=glyph):
                    self.configure(glyph=glyph, quantity=metric, choice=effect)
                    sequences = []
                    for level in ((.4, .65, .9) if effect == "heat" else (.1, .5, .9)):
                        self.settle(level)
                        cycle = tuple(self.pixels(self.frame(frame/48)) for frame in range(48))
                        static = self.pixels(self.frame(.075, control=True))
                        # A left-clipped network glyph is legitimately dark
                        # while another perimeter packet flashes on the right.
                        # Inspect the full real cycle rather than demanding a
                        # visible line at a hand-picked time on both halves.
                        self.assertTrue(any(frame != static for frame in cycle))
                        sequences.append(cycle)
                    self.assertEqual(len(set(sequences)), 3)

    def test_ram_saved_half_strength_and_actual_compact_sizes_keep_visible_feedback(self):
        self.configure(glyph="memory", quantity="ram_percent", choice="pulse", strength=.5, tempo=1)
        self.settle(.6)
        first = self.frame(.5)
        self.settle(.9)
        last = self.frame(.5)
        self.assertGreaterEqual(self.chromatic_pixels(first), 6)
        self.assertGreaterEqual(self.chromatic_pixels(last), 6)
        self.assertGreaterEqual(self.changed_pixels(first, last), 2)
        for size, glyph, metric, effect in ((11, "download", "net_download", "flow"),
                                           (16, "fan", "cpu_fan_rpm", "spin")):
            with self.subTest(actual_size=size):
                self.configure(iconSize=size, glyph=glyph, quantity=metric, choice=effect)
                self.settle(.6)
                self.assertGreaterEqual(self.chromatic_pixels(self.frame(.075)), 3)

    def test_higher_fan_state_changes_actual_elapsed_rhythm_and_preserves_user_speed(self):
        self.configure(glyph="fan", quantity="cpu_fan_rpm", choice="spin")
        steps = []
        for level in (.1, .5, .9):
            self.settle(level)
            self.icon.setProperty("phase", 0)
            self.advance(100)
            steps.append(self.icon.property("phase"))
        self.assertLess(steps[0], steps[1])
        self.assertLess(steps[1], steps[2])
        self.assertLess(steps[2], .25)
        self.settle(.6)
        self.configure(tempo=.5)
        slow = self.icon.property("cycleDuration")
        self.configure(tempo=2)
        fast = self.icon.property("cycleDuration")
        self.assertAlmostEqual(slow, 4 * fast)

    def test_user_intensity_approaches_zero_without_dropping_the_static_carrier(self):
        for glyph, metric, effect in (("memory", "ram_percent", "pulse"),
                                      ("fan", "cpu_fan_rpm", "spin"),
                                      ("download", "net_download", "flow")):
            with self.subTest(glyph=glyph):
                self.configure(glyph=glyph, quantity=metric, choice=effect)
                opacity, distance, colored_coverage = [], [], []
                for intensity in (0, .0001, .01, .1, .5, 1):
                    self.configure(strength=intensity)
                    # Crossing zero creates the optional moving composition;
                    # let its fixed SVG textures finish one actual render.
                    self.window.requestUpdate()
                    QTest.qWait(20)
                    self.stop_clock()
                    if intensity:
                        self.settle(.6)
                    image, static = self.frame(.075), self.frame(.35, control=True)
                    alpha = self.icon.property("accentOpacity")
                    self.assertTrue(math.isfinite(alpha))
                    self.assertGreaterEqual(alpha, 0)
                    self.assertLessEqual(alpha, 1)
                    opacity.append(alpha)
                    colored_coverage.append(self.chromatic_pixels(image))
                    distance.append(sum(sum(abs(a-b) for a, b in zip(image.pixelColor(x, y).getRgb()[:3], static.pixelColor(x, y).getRgb()[:3]))
                                        for y in range(image.height()) for x in range(image.width())))
                self.assertEqual(opacity[0], 0)
                self.assertTrue(all(a < b for a, b in zip(opacity, opacity[1:])))
                self.assertEqual(distance[0], 0)
                # The one-basis-point setting must approach the static image,
                # rather than replacing a whole arrow/rotor with a faded gap.
                self.assertLessEqual(distance[1], max(3, distance[-1] * .05))
                self.assertLess(distance[2], distance[-1] * .2)
                # Moving geometry can have a nonmonotonic distance from the
                # static glyph. Check the colored coverage itself instead.
                self.assertTrue(all(a <= b for a, b in zip(colored_coverage, colored_coverage[1:])), colored_coverage)
                self.assertGreaterEqual(colored_coverage[-1], 6)
        self.configure(strength=.5)

    def test_state_transition_has_a_real_intermediate_color_and_keeps_phase_continuous(self):
        self.configure(glyph="memory", quantity="ram_percent", choice="pulse")
        self.settle(.1)
        first = self.frame(.075)
        before_phase = self.icon.property("phase")
        self.configure(reading=.9)
        self.assertAlmostEqual(self.icon.property("displayedLevel"), .1, delta=.002)
        self.assertEqual(self.icon.property("phase"), before_phase)
        stages = []
        for elapsed in (80, 80, 80):
            self.advance(elapsed)
            stages.append((self.icon.property("displayedLevel"), self.frame(.075)))
            self.assertEqual(self.window.property("reading"), .9, "Only decoration is eased")
        levels = [.1, *(level for level, _frame in stages), .9]
        self.assertTrue(all(a < b for a, b in zip(levels, levels[1:])))
        self.settle(.9)
        last = self.frame(.075)
        # A gradual early frame need not cross a large perceptibility threshold.
        # It must actually change pixels, remain between endpoints, then become
        # visibly distinct in the middle of the transition at the same phase.
        self.assertNotEqual(self.pixels(first), self.pixels(stages[0][1]))
        self.assertNotEqual(self.pixels(stages[0][1]), self.pixels(last))
        self.assertGreaterEqual(self.changed_pixels(first, stages[1][1]), 2)
        self.assertGreaterEqual(self.changed_pixels(stages[1][1], last), 1)
        self.assertGreaterEqual(self.changed_pixels(first, last), 2)

    def test_zero_missing_off_and_reduced_motion_return_to_actual_static_icon_then_restore(self):
        for field, value, restored in (("reading", 0, .6), ("reading", None, .6),
                                       ("valid", False, True), ("choice", "off", "pulse"),
                                       ("motionAllowed", False, True)):
            with self.subTest(field=field, value=value):
                self.settle(.6)
                self.configure(**{field: value})
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
                self.assertEqual(self.icon.property("displayedLevel"), 0)
                self.assertEqual(self.icon.property("phase"), 0)
                self.assertIsNone(self.window.findChild(QObject, "metricIconAnimation"))
                self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
                self.assertEqual(self.window.property("strength"), .5)
                self.assertEqual(self.window.property("tempo"), 1)
                self.configure(**{field: restored})
                self.settle(.6)
                self.assertGreaterEqual(self.chromatic_pixels(self.frame(.5)), 6)

    def test_invalid_levels_controls_and_clock_values_cannot_reanimate_or_paint_invalid_state(self):
        for field, value, restored in (("reading", float("nan"), .6), ("reading", float("inf"), .6),
                                       ("reading", -.1, .6), ("reading", 1.1, .6),
                                       ("strength", float("nan"), .5), ("strength", -1, .5),
                                       ("tempo", .49, 1), ("tempo", 2.01, 1)):
            with self.subTest(field=field, value=value):
                self.configure(**{field: value})
                self.assertEqual(self.icon.property("displayedLevel"), 0)
                self.assertEqual(self.pixels(self.frame()), self.pixels(self.frame(control=True)))
                self.configure(**{field: restored})
                self.settle(.6)
        before = self.icon.property("phase")
        self.evaluate("advanceClock(NaN)")
        self.evaluate("advanceClock(Infinity)")
        self.assertEqual(self.icon.property("phase"), before)
        self.advance(-1000)
        self.assertEqual(self.icon.property("phase"), before)
        self.advance(10**9)
        self.assertTrue(math.isfinite(self.icon.property("phase")))
        self.assertGreaterEqual(self.icon.property("phase"), 0)
        self.assertLess(self.icon.property("phase"), 1)


if __name__ == "__main__":
    unittest.main()
