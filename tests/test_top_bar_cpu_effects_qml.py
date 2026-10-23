"""Actual CPU detail/icon QML, owned offscreen windows and synthetic readings only."""

import copy
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

from tests import test_top_bar_module_qml as module_fixture

ROOT = Path(__file__).resolve().parents[1]


def cpu_context(count=8):
    return dict(
        hardware_name="Synthetic CPU", physical_cores=max(1, count // 2),
        logical_processors=count, displayed_count=count, truncated=False,
        source="Windows / psutil", api="psutil.cpu_percent(percpu=True)",
        timestamp=1_700_000_000.0, available=True, available_count=count,
        state="available", reason="",
        logical_rows=[dict(index=index, label="CPU " + str(index), available=True,
                           numeric_value=index % 101, fraction=(index % 101) / 100,
                           value=str(index % 101) + " %", source="Windows / psutil", reason="")
                      for index in range(count)],
        related_rows=[
            dict(metric="cpu_frequency", label="CPU 频率", value="3.80 GHz", available=True,
                 source="Windows / psutil", reason=""),
            dict(metric="cpu_temp", label="CPU 温度", value="50 °C", available=True,
                 source="Synthetic thermal provider", reason=""),
            dict(metric="cpu_power", label="CPU 封装功率", value="12.5 W", available=True,
                 source="Synthetic meter", reason=""),
            dict(metric="cpu_fan_rpm", label="CPU 风扇转速", value="—", available=False,
                 source="Synthetic fan provider", reason="Synthetic unavailable fan"),
        ],
    )


class CpuEffectsQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_fixture.ModuleQmlTests.setUpClass()
        cls.app = module_fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.state = module_fixture.ModuleState()
        self.state.row.update(icon="cpu", style="icon_value", family="cpu")
        self.state.details.update(family="cpu", icon="cpu", cpu_context=cpu_context())
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.state)
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        self.component = self.window = None

    def tearDown(self):
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

    def load(self, kind="details"):
        self.component = QQmlComponent(self.engine)
        if kind == "details":
            self.component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
            self.window = self.component.createWithInitialProperties({"barState": self.state})
        else:
            if kind == "metric":
                child = '''Product.TopBarMetricContent { objectName:"metric"; x:16; y:16;
                    width:implicitWidth; height:implicitHeight; visible:scene.contentVisible;
                    row:stats.previewRow; ink:stats.ink; muted:stats.muted; fontFamily:stats.fontFamily;
                    motionEnabled:scene.motionAllowed }'''
            else:
                child = '''Product.MetricIcon { objectName:"icon"; x:16; y:16; width:18; height:18;
                    visible:scene.contentVisible; name:stats.previewRow.icon || "power";
                    metric:stats.previewRow.metric || ""; ink:stats.ink;
                    effect:stats.previewRow.icon_effect || "off";
                    level:stats.previewRow.effect_level === undefined ? null : stats.previewRow.effect_level;
                    available:stats.previewRow.available === true && Number.isFinite(stats.previewRow.numeric_value);
                    motionEnabled:scene.motionAllowed }'''
            qml = '''import QtQuick
import "../../native" as Product
Window { id:scene; width:336; height:96; visible:false; color:stats.theme==="dark"?"#20242b":"#f6f8fb";
    property bool motionAllowed:true; property bool contentVisible:true;
''' + child + "\n}"
            self.component.setData(qml.encode(), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign36/cpu-effects-fixture.qml")))
            self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()
        QTest.qWait(35)

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

    def publish(self):
        self.state.changed.emit()
        self.app.processEvents()
        QTest.qWait(15)

    def test_zero_and_missing_logical_channels_have_distinct_values_and_no_guessed_mapping(self):
        context = self.state.details["cpu_context"]
        context["logical_rows"][1].update(available=False, numeric_value=None, fraction=None, value="—")
        context["logical_rows"][2].update(available=True, numeric_value=100, fraction=1, value="100 %")
        self.load()
        self.assertEqual(self.find("topBarCpuLogicalValue_0").property("text"), "0 %")
        self.assertEqual(self.find("topBarCpuLogicalValue_1").property("text"), "—")
        self.assertEqual(self.find("topBarCpuLogicalValue_2").property("text"), "100 %")
        self.assertEqual(self.find("topBarCpuLogicalLabel_0").property("text"), "CPU 0")
        self.assertEqual(self.find("topBarCpuCoreGrid").property("count"), 8)
        self.assertIn("8", self.find("topBarCpuTopology").property("text"))
        self.assertEqual(self.find("topBarCpuRelatedValue_cpu_fan_rpm").property("text"), "—")

    def test_fake_psutil_through_actual_sampler_controller_and_qml_preserves_real_channels(self):
        from tests.test_cpu_details import CpuDetailsTests

        fixture = CpuDetailsTests("test_zero_one_real_call_source_time_and_logical_identity")
        fixture.setUp()
        try:
            fixture.sample()
            self.state.details = fixture.ui.topBarDetailRow("b_cpu")
            self.load()
            self.assertEqual(self.find("topBarCpuCoreGrid").property("count"), 4)
            self.assertEqual(self.find("topBarCpuLogicalValue_0").property("text"), "0 %")
            self.assertEqual(self.find("topBarCpuLogicalValue_1").property("text"), "25 %")
            self.assertEqual(self.find("topBarCpuLogicalValue_2").property("text"), "100 %")
            self.assertEqual(self.find("topBarCpuRelatedValue_cpu_power").property("text"), "12.5 W")
            self.assertEqual(self.find("topBarDetailDeviceName").property("text"), "Synthetic CPU")
        finally:
            fixture.doCleanups()

    def test_temperature_and_power_keep_cpu_context_without_mixing_other_units_into_trend(self):
        self.state.details.update(metric="cpu_temp", number_text="50", value="50 °C", unit="°C", unit_text="°C",
                                  numeric_value=50, history=[45, 46, 50], trend_min=45, trend_max=50)
        self.load()
        self.assertTrue(self.find("topBarCpuContext").isVisible())
        self.assertEqual(self.find("topBarDetailUnit").property("text"), "°C")
        self.assertEqual(self.window.property("chartScale").toVariant()["high"], 50)
        self.assertEqual(len(self.window.property("chartRows").toVariant()), 1)
        self.assertEqual(self.find("topBarCpuRelatedValue_cpu_power").property("text"), "12.5 W")
        self.state.details.update(metric="cpu_power", number_text="12.5", value="12.5 W", unit="W", unit_text="W",
                                  numeric_value=12.5, history=[10, 12.5, 15], trend_min=10, trend_max=15)
        self.publish()
        self.assertEqual(self.find("topBarDetailUnit").property("text"), "W")
        self.assertEqual(self.window.property("chartScale").toVariant()["high"], 15)
        self.assertEqual(self.find("topBarCpuRelatedValue_cpu_temp").property("text"), "50 °C")
        self.assertEqual(self.find("topBarCpuLogicalValue_0").property("text"), "0 %")

    def test_many_logical_channels_use_bounded_virtual_view_and_keep_scroll_on_refresh(self):
        self.state.details["cpu_context"] = cpu_context(1024)
        self.state.details["cpu_context"].update(logical_processors=2048, truncated=True)
        self.load()
        grid = self.find("topBarCpuCoreGrid")
        self.assertEqual(grid.property("count"), 1024)
        self.assertLessEqual(grid.height(), 208)
        self.assertLessEqual(self.window.height(), 640)
        instantiated = [item for item in self.items() if item.objectName().startswith("topBarCpuLogical_")]
        self.assertLessEqual(len(instantiated), 80)
        self.assertIn("1024 / 2048", self.find("topBarCpuContextTruncated").property("text"))
        grid.setProperty("contentY", grid.property("contentHeight") - grid.height())
        QTest.qWait(30)
        last = self.find("topBarCpuLogicalValue_1023")
        position = grid.property("contentY")
        self.state.details["cpu_context"]["logical_rows"][1023].update(numeric_value=75, value="75 %")
        self.publish()
        self.assertIs(self.find("topBarCpuLogicalValue_1023"), last)
        self.assertAlmostEqual(grid.property("contentY"), position, delta=1)
        self.assertEqual(last.property("text"), "75%")

    def test_baseline_and_stale_context_never_show_synthetic_zero(self):
        context = self.state.details["cpu_context"]
        context.update(state="warming_up", available=False, logical_rows=[], reason="逻辑处理器采样正在建立基线。")
        self.load()
        self.assertFalse(self.find("topBarCpuCoreGrid").isVisible())
        self.assertEqual(self.find("topBarCpuContextReason").property("text"), context["reason"])
        context.update(cpu_context(4))
        context.update(state="stale", available=False, reason="Synthetic stale logical readings")
        for row in context["logical_rows"]:
            row.update(available=False, numeric_value=None, fraction=None, value="—")
        self.publish()
        self.assertEqual(self.find("topBarCpuLogicalValue_0").property("text"), "—")
        self.assertEqual(self.find("topBarCpuRelatedValue_cpu_frequency").property("text"), "3.80 GHz")

    def test_icon_is_static_by_default_and_auto_is_static_for_unsupported_quantity(self):
        self.state.row.update(effect_level=0.5, numeric_value=30)
        self.load("icon")
        icon = self.find("icon")
        self.assertEqual(icon.property("effect"), "off")
        self.assertFalse(icon.property("animationRunning"))
        self.state.row.update(icon_effect="auto", metric="external_slot_0")
        self.publish()
        self.assertEqual(icon.property("resolvedEffect"), "off")
        self.assertFalse(icon.property("animationRunning"))
        self.assertEqual(icon.property("phase"), 0)

    def test_effects_stop_for_motion_hidden_window_unavailable_invalid_and_zero_flow(self):
        self.state.row.update(icon_effect="flow", effect_level=0.5, numeric_value=12.5, metric="cpu_power", icon="power")
        self.load("icon")
        icon = self.find("icon")
        self.assertTrue(icon.property("animationRunning"))
        QTest.qWait(80)
        self.assertGreater(icon.property("phase"), 0)
        for field, value in (("available", False), ("numeric_value", None), ("effect_level", None),
                             ("effect_level", -0.1), ("effect_level", 1.1), ("effect_level", 0)):
            with self.subTest(field=field, value=value):
                original = copy.deepcopy(self.state.row)
                self.state.row[field] = value
                self.publish()
                self.assertFalse(icon.property("animationRunning"))
                self.assertEqual(icon.property("phase"), 0)
                self.state.row = original
                self.publish()
        self.window.setProperty("motionAllowed", False)
        self.assertFalse(icon.property("animationRunning"))
        self.window.setProperty("motionAllowed", True)
        self.window.setProperty("contentVisible", False)
        self.assertFalse(icon.property("animationRunning"))
        self.window.setProperty("contentVisible", True)
        self.window.hide()
        self.assertFalse(icon.property("animationRunning"))

    def test_auto_selects_quantity_and_decorative_rotation_ignores_display_unit(self):
        self.state.row.update(icon_effect="auto", effect_level=0.6, numeric_value=1200,
                              metric="cpu_fan_rpm", icon="fan", unit="RPM")
        self.load("icon")
        icon = self.find("icon")
        self.assertEqual(icon.property("resolvedEffect"), "spin")
        self.assertTrue(icon.property("animationRunning"))
        self.state.row.update(effect_level=0, numeric_value=0)
        self.publish()
        self.assertFalse(icon.property("animationRunning"))
        self.state.row.update(metric="cpu_temp", icon="temperature", numeric_value=50,
                              effect_level=0.4, unit="°C")
        self.publish()
        self.assertEqual(icon.property("resolvedEffect"), "heat")
        self.assertTrue(icon.property("animationRunning"))
        self.state.row.update(numeric_value=122, unit="°F")
        self.publish()
        self.assertEqual(icon.property("resolvedEffect"), "heat")
        self.assertEqual(icon.property("level"), 0.4)
        self.state.row.update(metric="voltage", icon="voltage", numeric_value=12, unit="V")
        self.publish()
        self.assertEqual(icon.property("resolvedEffect"), "flow")
        for effect in ("heat", "flow", "spin", "pulse"):
            with self.subTest(zero_effect=effect):
                self.state.row.update(icon_effect=effect, effect_level=0, numeric_value=0)
                self.publish()
                self.assertFalse(icon.property("animationRunning"))
                self.assertEqual(icon.property("phase"), 0)

    def test_actual_metric_component_keeps_svg_and_animation_off_during_rapid_updates(self):
        self.state.row.update(icon_effect="off", effect_level=0.5, numeric_value=25)
        self.load("metric")
        icon = self.find("topBarContentIcon")
        image = self.find("lucideImage")
        source = image.property("source")
        started = time.process_time()
        for index in range(100):
            self.state.row.update(numeric_value=index, number_text=str(index), value=str(index) + " %")
            self.state.changed.emit()
            self.app.processEvents()
        self.assertLess(time.process_time() - started, 2)
        self.assertEqual(image.property("source"), source)
        self.assertFalse(icon.property("animationRunning"))
        self.assertEqual(icon.property("phase"), 0)
        self.state.row.update(icon_effect="pulse")
        self.publish()
        self.assertTrue(icon.property("animationRunning"))
        self.state.row.update(style="label_value")
        self.publish()
        self.assertFalse(icon.property("animationRunning"))

    def test_cpu_values_and_units_fit_at_current_device_scale(self):
        self.state.details["cpu_context"] = cpu_context(32)
        self.state.details["cpu_context"]["logical_rows"][0].update(numeric_value=100, value="100 %")
        self.load()
        for index in range(32):
            value = self.find("topBarCpuLogicalValue_" + str(index))
            self.assertFalse(value.property("truncated"))
            tile = self.find("topBarCpuLogical_" + str(index))
            edge = value.mapToItem(tile, QPointF(value.width(), value.height()))
            self.assertLessEqual(edge.x(), tile.width())
            self.assertLessEqual(edge.y(), tile.height())
        scale = float(os.environ.get("QT_SCALE_FACTOR", "1"))
        self.assertAlmostEqual(self.window.devicePixelRatio(), scale, delta=0.01)


if __name__ == "__main__":
    unittest.main()
