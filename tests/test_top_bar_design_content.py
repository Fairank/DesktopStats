"""Three content designs and restrained effects, synthetic owned offscreen Qt only."""

import copy
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign37/test-profile"))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl, Slot
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QTest

from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = ("classic", "capsule", "instrument")
STYLES = ("label_value", "value", "icon_value", "stacked", "trend_value", "graph",
          "bar_value", "ring_value", "duplex", "duplex_inline")


def sample_row(style="icon_value"):
    return dict(id="b_cpu", metric="cpu_usage", label="CPU", bar_label="CPU", style=style,
                value="34 %", number_text="34", number_reserve="999.9", unit_text="%", unit="%",
                available=True, numeric_value=34, icon="cpu", icon_effect="off", effect_level=.34,
                gauge_available=True, gauge_supported=True, gauge_fraction=.34, pair_supported=True,
                trend_available=True, trend_points=[dict(x=0, y=.7), dict(x=.2, y=.5), None,
                                                   dict(x=.65, y=.8), dict(x=1, y=.3)],
                paired_rows=[dict(metric="net_download", direction="download", label="Download", number_text="0",
                                  unit_text="MB/s", value="0 MB/s", numeric_value=0, available=True, effect_level=0),
                             dict(metric="net_upload", direction="upload", label="Upload", number_text="—",
                                  unit_text="MB/s", value="—", numeric_value=None, available=False, effect_level=None)])


class DesignState(fixture.ModuleState):
    def __init__(self):
        super().__init__()
        self.row = sample_row()
        self.preferences["top_bar"]["items"][0]["prefs"].update(style="icon_value", icon_effect="off")

    @Slot(str, str, float)
    def changeTopBarEffect(self, identifier, field, value):
        self.actions.append((identifier, field, value))
        self.preferences["top_bar"]["items"][0]["prefs"][field] = value
        self.changed.emit()

    @Slot(str, "QVariantList", result=bool)
    def setTopBarGroupMetrics(self, identifier, values):
        self.actions.append((identifier, "metrics", list(values)))
        self.row["group_metrics"] = list(values)
        self.preferences["top_bar"]["items"][0]["prefs"]["metrics"] = list(values)
        self.changed.emit()
        return True


class DesignContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.state = DesignState()
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

    def load(self, kind="metric"):
        if kind == "inspector":
            child = '''Product.TopBarItemInspector {objectName:"subject";x:16;y:16;width:350;
                item:stats.draft.top_bar.items[0];row:stats.previewRow;design:scene.visualDesign}'''
        elif kind == "many":
            child = '''Repeater {model:64;Product.MetricIcon {required property int index;
                objectName:"manyIcon_"+index;width:18;height:18;x:20+(index%8)*36;y:20+Math.floor(index/8)*36;
                name:index%4===0?"temperature":index%4===1?"download":index%4===2?"fan":"cpu";
                metric:index%4===2?"gpu_fan_percent":"cpu_usage";
                effect:["heat","flow","spin","pulse"][index%4];level:.5;available:true;
                motionEnabled:scene.motionAllowed;intensity:.7;speed:1.5}}'''
        else:
            component = "TopBarGroupContent" if kind == "group" else "TopBarMetricContent"
            child = '''Product.''' + component + ''' {objectName:"subject";x:16;y:16;
                width:implicitWidth;height:implicitHeight;row:stats.previewRow;design:scene.visualDesign;
                ink:stats.ink;muted:stats.muted;fontFamily:stats.fontFamily;
                reserveValueWidth:scene.reserveValue;motionEnabled:scene.motionAllowed}'''
        code = '''import QtQuick
import QtQuick.Controls
import "../../native" as Product
Window {id:scene;width:740;height:860;visible:false;color:stats.theme==="dark"?"#20242b":"#f6f8fb";
    property string visualDesign:"classic";property bool reserveValue:false;property bool motionAllowed:true;
''' + child + "\n}"
        self.component = QQmlComponent(self.engine)
        self.component.setData(code.encode(), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign37/content-fixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()
        QTest.qWait(80)

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

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def click(self, name):
        item = self.find(name)
        self.assertTrue(item.isVisible(), name)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())
        QTest.qWait(15)

    def test_ten_styles_keep_original_geometry_across_three_designs_and_reserved_widths(self):
        self.load()
        subject = self.find("subject")
        for reserve in (False, True):
            self.window.setProperty("reserveValue", reserve)
            for style in STYLES:
                with self.subTest(style=style, reserve=reserve):
                    self.state.row = sample_row(style)
                    self.publish()
                    expected = None
                    for design in DESIGNS:
                        self.window.setProperty("visualDesign", design)
                        self.app.processEvents()
                        geometry = (subject.implicitWidth(), subject.implicitHeight(),
                                    self.find("topBarContentValue").x(), self.find("topBarContentValue").y())
                        if expected is None:
                            expected = geometry
                        self.assertEqual(geometry, expected)
                        self.assertLessEqual(subject.implicitHeight(), 24)
                        self.assertEqual(self.find("topBarContentValue").property("font").weight(), 500)
        self.window.setProperty("visualDesign", "unknown-future")
        self.assertEqual(subject.property("effectiveDesign"), "classic")

    def test_duplex_preserves_zero_missing_real_units_and_direction_for_all_designs(self):
        self.state.row = sample_row("duplex_inline")
        self.load()
        for design in DESIGNS:
            self.window.setProperty("visualDesign", design)
            self.assertEqual(self.find("topBarPairNumber_0").property("text"), "0")
            self.assertEqual(self.find("topBarPairNumber_1").property("text"), "—")
            self.assertEqual(self.find("topBarPairUnit_0").property("text"), "MB/s")
            self.assertEqual(self.find("topBarPairUnit_1").property("text"), "MB/s")
            self.assertEqual(self.find("topBarPairIcon_0").property("name"), "download")
            self.assertEqual(self.find("topBarPairIcon_1").property("name"), "upload")
            self.assertEqual(self.find("topBarDuplexDivider").isVisible(), design != "classic")
        self.state.row["paired_rows"][1].update(unit_text="Mbps", number_text="1.5", available=True,
                                               numeric_value=1.5, effect_level=.2)
        self.publish()
        self.assertEqual(self.find("topBarPairUnit_1").property("text"), "Mbps")

    def test_group_propagates_design_with_same_width_independent_units_and_internal_dividers(self):
        members = [sample_row(), dict(sample_row(), metric="cpu_temp", number_text="50", unit_text="°C"),
                   dict(sample_row(), metric="cpu_power", number_text="—", unit_text="W", available=False)]
        self.state.row.update(grouped=True, group_rows=members)
        self.load("group")
        subject = self.find("subject")
        width = subject.implicitWidth()
        for design in DESIGNS:
            self.window.setProperty("visualDesign", design)
            self.assertEqual(subject.implicitWidth(), width)
            for member in members:
                content = self.find("topBarGroupMember_" + member["metric"])
                self.assertEqual(content.property("design"), design)
            self.assertFalse(self.find("topBarGroupDivider_0").isVisible())
            self.assertTrue(self.find("topBarGroupDivider_1").isVisible())
            divider = self.find("topBarGroupDivider_1")
            self.assertLess(divider.x(), 0)
            self.assertGreaterEqual(divider.x(), -10)

    def test_percent_gauges_have_distinct_actual_paint_and_do_not_invent_missing_or_zero(self):
        self.state.row = sample_row("bar_value")
        self.load()
        images = []
        scale = self.window.devicePixelRatio()
        for design in DESIGNS:
            self.window.setProperty("visualDesign", design)
            QTest.qWait(40)
            image = self.window.grabWindow().copy(round(16*scale), round(16*scale), round(22*scale), round(18*scale))
            images.append(bytes(image.constBits()))
        self.assertEqual(len(set(images)), 3)
        for fraction, available in ((0, True), (None, False), (float("nan"), True), (1.1, True)):
            self.state.row.update(gauge_fraction=fraction, available=available, number_text="0" if available else "—")
            self.publish()
            self.assertEqual(self.find("subject").property("gaugeAvailable"), fraction == 0 and available)
            self.assertEqual(self.find("topBarContentValue").property("text"), "0" if available else "—")

    def test_gallery_renders_selected_design_and_keeps_effect_setting_until_explicit_style_action(self):
        self.state.preferences["top_bar"]["items"][0]["prefs"].update(style="value", icon_effect="heat")
        self.state.row.update(style="value", icon_effect="heat")
        self.load("inspector")
        inspector = self.find("subject")
        self.window.setProperty("visualDesign", "instrument")
        self.assertEqual(self.find("topBarCurrentStyleSample").property("design"), "instrument")
        self.assertTrue(self.find("topBarIconEffectInactiveHint").isVisible())
        self.assertEqual(self.state.actions, [])
        self.click("topBarStyleChooser")
        for style in STYLES:
            self.assertEqual(self.find("topBarStyleSample_" + style).property("design"), "instrument")
        self.evaluate(inspector, "closeGallery()")
        self.app.processEvents()
        self.click("topBarUseIconStyle")
        self.assertEqual(self.state.actions, [("b_cpu", "style", "icon_value")])
        self.assertEqual(self.state.preferences["top_bar"]["items"][0]["prefs"]["icon_effect"], "heat")
        self.assertFalse(self.find("topBarIconEffectInactiveHint").isVisible())

    def test_effect_sliders_send_continuous_numeric_values_and_support_keyboard_endpoints(self):
        self.state.preferences["top_bar"]["items"][0]["prefs"]["icon_effect"] = "pulse"
        self.load("inspector")
        for name, field, minimum, maximum in (("topBarEffectIntensity", "effect_intensity", 0, 1),
                                               ("topBarEffectSpeed", "effect_speed", .5, 2)):
            slider = self.find(name)
            self.assertTrue(slider.isVisible())
            self.assertEqual(slider.property("from"), minimum)
            self.assertEqual(slider.property("to"), maximum)
            slider.forceActiveFocus()
            QTest.keyClick(self.window, Qt.Key_End)
            self.assertEqual(self.state.actions[-1], ("b_cpu", field, maximum))
            QTest.keyClick(self.window, Qt.Key_Home)
            self.assertEqual(self.state.actions[-1], ("b_cpu", field, minimum))
        self.assertNotIn(("b_cpu", "style", "icon_value"), self.state.actions)

    def test_group_pending_edits_survive_design_change_cancel_and_confirm_stay_atomic(self):
        self.state.row.update(group_supported=True, group_metrics=["cpu_usage", "cpu_temp"],
                              group_options=[dict(metric=value, label=value) for value in
                                             ("cpu_usage", "cpu_temp", "cpu_power")])
        self.load("inspector")
        inspector = self.find("subject")
        self.evaluate(inspector, "openGroup()")
        self.evaluate(inspector, 'setGroup(["cpu_usage","cpu_temp","cpu_power"])')
        self.assertTrue(inspector.property("pendingGroupEdits"))
        self.window.setProperty("visualDesign", "capsule")
        self.assertTrue(inspector.property("pendingGroupEdits"))
        self.assertEqual(self.state.actions, [])
        self.evaluate(inspector, "cancelGroupEditing()")
        QTest.qWait(20)
        self.assertEqual(self.state.row["group_metrics"], ["cpu_usage", "cpu_temp"])
        self.evaluate(inspector, "openGroup()")
        self.evaluate(inspector, 'setGroup(["cpu_usage","cpu_temp","cpu_power"])')
        self.evaluate(inspector, "confirmGroup()")
        self.assertEqual(self.state.actions, [("b_cpu", "metrics", ["cpu_usage", "cpu_temp", "cpu_power"])])

    def test_effect_controls_propagate_to_main_and_both_direction_icons(self):
        self.state.row.update(icon_effect="pulse", effect_intensity=.8, effect_speed=1.7)
        self.load()
        icon = self.find("topBarContentIcon")
        self.assertEqual(icon.property("intensity"), .8)
        self.assertEqual(icon.property("speed"), 1.7)
        self.state.row["style"] = "duplex"
        self.publish()
        for index in range(2):
            icon = self.find("topBarPairIcon_" + str(index))
            self.assertEqual(icon.property("intensity"), .8)
            self.assertEqual(icon.property("speed"), 1.7)
            self.assertFalse(icon.property("animationRunning"))

    def test_fan_percent_auto_and_all_zero_invalid_hidden_reduced_conditions_are_static(self):
        self.state.row.update(icon_effect="auto", metric="gpu_fan_percent", icon="fan", numeric_value=50,
                              effect_level=.5, effect_intensity=.5, effect_speed=1)
        self.load()
        icon = self.find("topBarContentIcon")
        self.assertEqual(icon.property("resolvedEffect"), "spin")
        self.assertTrue(icon.property("animationRunning"))
        for field, value in (("effect_level", 0), ("available", False), ("numeric_value", None),
                             ("effect_intensity", 0), ("effect_intensity", -1), ("effect_intensity", 1.1),
                             ("effect_speed", .4), ("effect_speed", 2.1)):
            original = copy.deepcopy(self.state.row)
            self.state.row[field] = value
            self.publish()
            self.assertFalse(icon.property("animationRunning"), (field, value))
            self.assertEqual(icon.property("phase"), 0)
            self.state.row = original
            self.publish()
        self.window.setProperty("motionAllowed", False)
        self.assertFalse(icon.property("animationRunning"))
        self.window.setProperty("motionAllowed", True)
        self.window.hide()
        self.assertFalse(icon.property("animationRunning"))
        self.assertEqual(icon.property("phase"), 0)

    def test_64_effects_have_bounded_clocks_constant_heat_paths_fixed_size_and_no_svg_churn(self):
        self.load("many")
        icons = [self.find("manyIcon_" + str(index)) for index in range(64)]
        self.assertTrue(all(icon.property("animationRunning") for icon in icons))
        images = [item for item in self.items() if item.objectName() == "lucideImage"]
        sources = [image.property("source") for image in images]
        heats = [item for item in self.items() if item.objectName() == "metricIconHeat" and item.isVisible()]
        before = [heat.property("paintCount") for heat in heats]
        started = time.process_time()
        QTest.qWait(450)
        self.cpu_seconds_64 = time.process_time() - started
        self.assertTrue(all(icon.property("phase") > 0 for icon in icons))
        self.assertEqual([image.property("source") for image in images], sources)
        self.assertEqual([heat.property("paintCount") for heat in heats], before)
        for item in self.items():
            if item.objectName() == "metricIconAnimation":
                self.assertGreaterEqual(item.property("interval"), 34)
        for icon in icons:
            self.assertEqual((icon.width(), icon.height(), icon.scale()), (18, 18, 1))
            glyph = icon.findChild(QObject, "metricIconGlyph")
            self.assertEqual(glyph.property("scale"), 1)
            center = glyph.mapToItem(icon, QPointF(9, 9))
            self.assertAlmostEqual(center.x(), 9)
            self.assertAlmostEqual(center.y(), 9)
        self.window.setProperty("motionAllowed", False)
        self.assertTrue(all(not icon.property("animationRunning") and icon.property("phase") == 0 for icon in icons))

    def test_fan_intensity_changes_rendered_ink_without_changing_geometry_or_rotation_speed(self):
        self.state.row.update(icon_effect="spin", icon="fan", metric="cpu_fan_rpm", effect_level=.5,
                              numeric_value=1200, effect_intensity=.1, effect_speed=1)
        self.load()
        icon = self.find("topBarContentIcon")
        clock = self.find("metricIconAnimation")
        clock.stop()
        icon.setProperty("phase", .5)
        location = icon.mapToScene(QPointF())
        scale = self.window.devicePixelRatio()
        before = None
        duration = icon.property("cycleDuration")
        for intensity in (.1, 1):
            self.state.row["effect_intensity"] = intensity
            self.publish()
            image = self.window.grabWindow().copy(round(location.x()*scale), round(location.y()*scale),
                                                  round(18*scale), round(18*scale))
            brightness = sum(image.pixelColor(x, y).red() for y in range(image.height()) for x in range(image.width()))
            if before is None:
                before = brightness
            else:
                self.assertGreater(brightness, before, "Continuous strength must visibly change the actual fan ink")
            self.assertEqual(icon.property("cycleDuration"), duration)
            self.assertEqual((icon.width(), icon.height(), icon.scale()), (18, 18, 1))


if __name__ == "__main__":
    unittest.main()
