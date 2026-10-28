"""Actual controller -> menu-bar QML continuity, owned offscreen windows only."""

import copy
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/motion-continuity-profile"),
)

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

import native_controller as controls
from stats_config import DEFAULT, validate
from tests import test_top_bar_runtime as bars

ROOT = Path(__file__).resolve().parents[1]
PHASES = (
    "phase",
    "loadPhase",
    "thermalArcPhase",
    "energyPhase",
    "inboundPhase",
    "outboundPhase",
    "spinPhase",
)


class MotionContinuityTests(unittest.TestCase):
    setUpClass = classmethod(bars.QmlTopBarTests.setUpClass.__func__)

    def setUp(self):
        self.assertEqual(QApplication.instance().platformName(), "offscreen")
        self.native = self.enterContext(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native API"))
        )
        self.process = self.enterContext(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        value = copy.deepcopy(DEFAULT)
        value["top_bar"]["enabled"] = True
        value["top_bar"]["items"] = [
            dict(
                id="b_cpu",
                metric="cpu_usage",
                prefs=dict(
                    style="icon_value",
                    icon_effect="auto",
                    metrics=["cpu_usage", "cpu_temp", "cpu_power", "cpu_frequency"],
                ),
            ),
            dict(
                id="b_fan", metric="cpu_fan_rpm", prefs=dict(style="icon_value", icon_effect="auto")
            ),
            dict(
                id="b_memory",
                metric="ram_percent",
                prefs=dict(style="icon_value", icon_effect="auto"),
            ),
            dict(
                id="b_network",
                metric="net_download",
                prefs=dict(style="duplex", icon_effect="auto"),
            ),
        ]
        with patch.object(controls, "load", return_value=validate(value)):
            self.ui = controls.Controller()
        self.ui.set_motion_enabled(True)
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(
            lambda errors: self.warnings.extend(error.toString() for error in errors)
        )
        self.windows, self.components = [], []
        screen = bars.Screen("DISPLAY1", bars.PixelRect(0, 0, 1920, 1080))
        self.runtime = SimpleNamespace(
            app=bars.Application([screen]),
            controller=self.ui,
            headless=True,
            show_settings=lambda _: None,
            engine=self.engine,
        )
        self.manager = bars.TopBarManager(self.runtime, adapter=bars.QmlAdapter())
        self.receive(0)
        self.manager.apply(copy.deepcopy(self.ui._saved))
        self.host = self.manager.hosts["DISPLAY1"]
        QTest.qWait(40)
        self.stop_clocks(self.host.window)

    def tearDown(self):
        self.manager.close()
        self.ui.close()
        for window in self.windows:
            window.hide()
            window.destroy()
            window.deleteLater()
        for component in self.components:
            component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.instance().processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def receive(self, index):
        self.ui.receive(
            dict(
                time=time.time(),
                cpu_usage=60 + index % 20,
                cpu_temp=85 + index % 5,
                cpu_power=110 + index % 30,
                cpu_frequency=4.2,
                cpu_fan_rpm=5100 + index % 100,
                ram_percent=65 + index % 10,
                net_download=10 + index % 6,
                net_upload=5 + index % 3,
            )
        )
        self.manager.update_rows()
        QApplication.instance().processEvents()

    @staticmethod
    def items(window):
        pending, result = [window.contentItem()], []
        while pending:
            item = pending.pop()
            result.append(item)
            pending.extend(item.childItems())
        return result

    def icons(self, window):
        return [
            item
            for item in self.items(window)
            if item.metaObject().indexOfProperty("clockSubscription") >= 0
            and item.property("animationRunning")
        ]

    @staticmethod
    def stop_clocks(window):
        for clock in window.findChildren(QObject, "metricIconAnimation"):
            clock.stop()

    def evaluate(self, item, expression):
        value = QQmlExpression(qmlContext(item), item, expression)
        result = value.evaluate()
        self.assertFalse(value.hasError(), value.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def snapshot(self, window):
        self.stop_clocks(window)
        icons = self.icons(window)
        self.assertGreater(len(icons), 0)
        rows = []
        for icon in icons:
            for key in PHASES:
                self.assertTrue(icon.setProperty(key, 0.413))
            self.assertTrue(icon.setProperty("previousTick", 1000))
            rows.append((icon, icon.property("clockSubscription")))
        return rows

    def unchanged(self, window, rows):
        self.stop_clocks(window)
        self.assertEqual(len(self.icons(window)), len(rows))
        current = self.items(window)
        for icon, listener in rows:
            self.assertTrue(isValid(icon), "A live reading destroyed its animated icon")
            self.assertTrue(
                any(item is icon for item in current), "A live reading replaced its animated icon"
            )
            self.assertTrue(
                listener.strictlyEquals(icon.property("clockSubscription")),
                "A live reading restarted the clock subscription",
            )
            for key in PHASES:
                self.assertAlmostEqual(icon.property(key), 0.413, msg=key)
            self.assertEqual(icon.property("previousTick"), 1000)

    def load_preview(self):
        component = QQmlComponent(self.engine)
        component.setData(
            b"""import QtQuick
import "../../native" as Product
Window {id:scene;width:1400;height:100;visible:false;color:"white";property var readings:[]
 Product.TopBarPreviewStrip {objectName:"preview";width:scene.width;rows:scene.readings;
  barEnabled:true;appearanceConfig:stats.draft}
}""",
            QUrl.fromLocalFile(str(ROOT / "qa-private/redesign43/motion-preview.qml")),
        )
        window = component.createWithInitialProperties({"readings": self.ui.topBarDraftRows()})
        self.assertIsInstance(
            window, QQuickWindow, [error.toString() for error in component.errors()]
        )
        self.windows.append(window)
        self.components.append(component)
        window.show()
        QTest.qWait(40)
        return window

    def test_actual_bar_keeps_group_pair_and_single_icons_and_clock_between_live_readings(self):
        rows = self.snapshot(self.host.window)
        self.assertEqual(len(rows), 8)
        for index in range(1, 42):
            self.receive(index)
            self.unchanged(self.host.window, rows)
        self.assertEqual(self.host.state.rows[1]["numeric_value"], 5141)
        self.assert_live_targets(self.host.window, 41)

    def test_settings_preview_keeps_the_same_animated_icons_across_new_row_maps(self):
        window = self.load_preview()
        rows = self.snapshot(window)
        self.assertEqual(len(rows), 8)
        for index in range(1, 22):
            self.receive(index)
            window.setProperty("readings", self.ui.topBarDraftRows())
            QApplication.instance().processEvents()
            self.unchanged(window, rows)
        self.assert_live_targets(window, 21)

    def assert_live_targets(self, window, index):
        icons = self.icons(window)
        cpu = next(icon for icon in icons if icon.property("metric") == "cpu_usage")
        inbound = next(icon for icon in icons if icon.property("metric") == "net_download")
        self.assertAlmostEqual(cpu.property("loadTarget"), (60 + index % 20) / 100)
        self.assertAlmostEqual(inbound.property("inboundTarget"), (10 + index % 6) / 100)
        text = next(
            item for item in self.items(window) if item.objectName() == "topBarPairNumber_0"
        )
        pair = next(row for row in self.ui.topBarRows() if row["id"] == "b_network")["paired_rows"][
            0
        ]
        self.assertEqual(text.property("text"), pair["number_text"])

    def only_fan(self):
        self.ui._saved["top_bar"]["items"] = [self.ui._saved["top_bar"]["items"][1]]
        self.manager.apply(copy.deepcopy(self.ui._saved))
        QTest.qWait(20)
        return self.snapshot(self.host.window)

    def test_fan_phase_and_speed_advance_between_samples_and_survive_a_fresh_sample(self):
        rows = self.only_fan()
        self.assertEqual(len(rows), 1)
        icon = rows[0][0]
        for index in range(6):
            self.evaluate(icon, f"advanceClock({1034 + index * 34})")
        phase = icon.property("spinPhase")
        self.assertGreater(phase, 0.413)
        previous = icon.property("previousTick")
        self.receive(80)
        self.stop_clocks(self.host.window)
        self.assertTrue(rows[0][1].strictlyEquals(icon.property("clockSubscription")))
        self.assertAlmostEqual(icon.property("spinPhase"), phase)
        self.assertEqual(icon.property("previousTick"), previous)
        old_speed = icon.property("displayedSpin")
        self.evaluate(icon, f"advanceClock({previous + 34})")
        self.assertGreater(icon.property("spinPhase"), phase)
        self.assertGreater(icon.property("displayedSpin"), old_speed)
        self.assertLess(icon.property("displayedSpin"), icon.property("spinTarget"))

    def test_details_header_keeps_its_phase_while_live_detail_rows_change(self):
        self.manager.click("DISPLAY1", "b_cpu")
        panel = self.manager._panel["window"]
        QTest.qWait(40)
        rows = self.snapshot(panel)
        self.assertEqual(len(rows), 1)
        for index in range(1, 18):
            self.receive(index)
            self.unchanged(panel, rows)
        self.assertAlmostEqual(rows[0][0].property("loadTarget"), 0.77)

    def test_duplex_orientation_switch_keeps_phases_but_leaving_duplex_removes_its_clock(self):
        self.ui._saved["top_bar"]["items"] = [self.ui._saved["top_bar"]["items"][-1]]
        self.manager.apply(copy.deepcopy(self.ui._saved))
        QTest.qWait(20)
        rows = self.snapshot(self.host.window)
        self.assertEqual(len(rows), 2)
        self.ui._saved["top_bar"]["items"][0]["prefs"]["style"] = "duplex_inline"
        self.manager.apply(copy.deepcopy(self.ui._saved))
        QApplication.instance().processEvents()
        self.unchanged(self.host.window, rows)
        self.ui._saved["top_bar"]["items"][0]["prefs"]["style"] = "value"
        self.manager.apply(copy.deepcopy(self.ui._saved))
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.instance().processEvents()
        self.assertEqual(self.icons(self.host.window), [])
        for _, listener in rows:
            self.assertFalse(listener.property("active").toBool())

    def test_group_reordering_and_removal_update_members_without_resetting_other_metrics(self):
        rows = self.snapshot(self.host.window)
        unrelated = [
            entry
            for entry in rows
            if entry[0].property("metric")
            not in ("cpu_usage", "cpu_temp", "cpu_power", "cpu_frequency")
        ]
        prefs = self.ui._saved["top_bar"]["items"][0]["prefs"]
        for metrics in (
            ["cpu_usage", "cpu_power", "cpu_temp", "cpu_frequency"],
            ["cpu_usage", "cpu_temp", "cpu_power"],
            ["cpu_usage"],
        ):
            prefs["metrics"] = metrics
            self.manager.apply(copy.deepcopy(self.ui._saved))
            QApplication.instance().processEvents()
            self.stop_clocks(self.host.window)
            leaves = [
                item
                for item in self.items(self.host.window)
                if item.objectName().startswith("topBarGroupMember_")
            ]
            observed = sorted(item.property("row").toVariant()["metric"] for item in leaves)
            self.assertEqual(observed, sorted(metrics) if len(metrics) > 1 else [])
            for icon, listener in unrelated:
                self.assertTrue(any(item is icon for item in self.icons(self.host.window)))
                self.assertTrue(listener.strictlyEquals(icon.property("clockSubscription")))
                self.assertAlmostEqual(icon.property("phase"), 0.413)

    def test_zero_missing_and_recovery_stop_and_restart_clock_without_replacing_the_fan(self):
        icon, _ = self.only_fan()[0]
        for value in (0, None, 5300):
            self.stop_clocks(self.host.window)
            sample = copy.deepcopy(self.ui._data)
            sample.update(time=time.time(), cpu_fan_rpm=value)
            self.ui.receive(sample)
            self.manager.update_rows()
            QApplication.instance().processEvents()
            self.assertTrue(isValid(icon))
            if value in (0, None):
                self.assertFalse(icon.property("animationRunning"))
                self.assertEqual(icon.property("spinPhase"), 0)
                self.assertTrue(self.evaluate(icon, "clockSubscription === null"))
            else:
                self.assertTrue(icon.property("animationRunning"))
                self.assertAlmostEqual(icon.property("spinTarget"), value / 12000)
                self.assertTrue(self.evaluate(icon, "clockSubscription.active"))
        self.stop_clocks(self.host.window)

    def test_hidden_and_reduced_motion_release_all_window_subscribers(self):
        icons = self.icons(self.host.window)
        self.assertEqual(len(icons), 8)
        self.ui.set_motion_enabled(False)
        self.assertTrue(all(not icon.property("animationRunning") for icon in icons))
        self.assertTrue(all(self.evaluate(icon, "clockSubscription === null") for icon in icons))
        self.ui.set_motion_enabled(True)
        self.host.window.hide()
        self.assertTrue(all(not icon.property("animationRunning") for icon in icons))
        self.assertTrue(all(self.evaluate(icon, "clockSubscription === null") for icon in icons))
        self.host.window.show()
        QTest.qWait(20)
        self.assertEqual(len(self.icons(self.host.window)), 8)
        self.stop_clocks(self.host.window)


if __name__ == "__main__":
    unittest.main()
