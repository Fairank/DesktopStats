"""Static hardware shapes and existing feedback; synthetic offscreen Qt only."""
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QWindow
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import getCppPointer

from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]


def gpu(count=None, style="gpu_axial", confidence="model"):
    return dict(kind="gpu", vendor="nvidia", board_vendor="unknown", style=style,
                fan_count=count, shroud="soft", accent="#729b42", confidence=confidence,
                label="Synthetic GPU", source_url="")


class HardwareAppearanceQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.window = self.component = None
        self.state = None

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

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def assign(self, name, value):
        # New JS objects match actual live projection delivery. QVariantMap's
        # coercing equality can otherwise swallow a number-to-string update.
        self.evaluate(self.window, name + " = JSON.parse(" + json.dumps(json.dumps(value)) + ")")
        self.app.processEvents()

    def find(self, name):
        found = self.window.findChild(QObject, name)
        if found is None:
            pending = [self.window.contentItem()]
            while pending:
                item = pending.pop()
                if item.objectName() == name:
                    found = item
                    break
                pending.extend(item.childItems())
        self.assertIsNotNone(found, name)
        return found

    def load_icon(self):
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
Window {
 id:scene; width:160; height:100; visible:false; color:"#f6f8fb"
 property string glyph:"gpu"
 property var appearance:({kind:"gpu",vendor:"nvidia",style:"gpu_axial",fan_count:2})
 property var channels:({profile:"processor",available:true,load:.3,thermal:.4,energy:.2})
 property bool motionAllowed:true
 Product.MetricIcon {
  objectName:"appearanceMetric"; x:16; y:16; width:18; height:18
  name:scene.glyph; metric:scene.glyph==="gpu"?"gpu_usage":scene.glyph==="cpu"?"cpu_usage":"cpu_temp"
  hardwareAppearance:scene.appearance; hardwareState:scene.channels
  effect:"auto"; level:.3; available:true; motionEnabled:scene.motionAllowed; ink:"#202833"
 }
 Product.HardwareGlyph {
  objectName:"controlGlyph"; x:64; y:16; width:64; height:64
  appearance:scene.appearance; ink:"#202833"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareAppearanceFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        QTest.qWait(30)

    @staticmethod
    def svg(item):
        source = item.property("svgSource").toString()
        header, body = source.split(",", 1)
        return base64.b64decode(body).decode() if ";base64" in header else unquote(body)

    def fan_layout(self, svg):
        """Measure actual rendered SVG fan discs, including per-fan offsets.

        Checking the facade's intermediate geometry alone would miss a theme
        dropping variable radii or vertical placement when emitting its SVG.
        """
        tree = ET.fromstring(svg)
        parents = {child: parent for parent in tree.iter() for child in parent}
        layout = []
        for hub in tree.iter():
            if hub.get("class") != "hardware-fan-hub":
                continue
            group = parents[hub]
            match = re.fullmatch(r"translate\(([^)]+)\)\s*scale\(([^)]+)\)", group.get("transform", ""))
            self.assertIsNotNone(match, "A front fan must have a measurable circular plane")
            center = [float(value) for value in re.split(r"[,\s]+", match.group(1).strip())]
            scale = [float(value) for value in re.split(r"[,\s]+", match.group(2).strip())]
            self.assertEqual(len(center), 2)
            self.assertIn(len(scale), (1, 2))
            sx, sy = scale[0], scale[-1]
            self.assertAlmostEqual(sx, sy, msg="Front fan discs must stay round in every theme")
            radii = [float(node.get("r")) for node in group if node.tag.endswith("circle")]
            self.assertGreater(len(radii), 1)
            radius = max(radii) * sx
            self.assertTrue(all(math.isfinite(number) for number in (*center, radius)))
            self.assertGreater(radius, 0)
            # A parent transform could silently change these measurements.
            ancestor = parents.get(group)
            while ancestor is not None:
                self.assertNotIn("transform", ancestor.attrib)
                ancestor = parents.get(ancestor)
            layout.append((center[0], center[1], radius))
        return sorted(layout)

    def assert_front_fans_fit(self, layout):
        for x, y, radius in layout:
            self.assertGreaterEqual(x - radius, 0)
            self.assertGreaterEqual(y - radius, 0)
            self.assertLessEqual(x + radius, 24)
            self.assertLessEqual(y + radius, 24)
        for left, right in zip(layout, layout[1:]):
            distance = math.hypot(left[0] - right[0], left[1] - right[1])
            self.assertGreater(distance, left[2] + right[2], "Adjacent physical fans must remain separate")

    def test_verified_fan_layouts_are_distinct_and_unknown_is_not_a_two_fan_guess(self):
        self.load_icon()
        glyph = self.find("controlGlyph")
        sources = []
        for count in (1, 2, 3):
            self.assign("appearance", gpu(count))
            svg = self.svg(glyph)
            hubs = [node for node in ET.fromstring(svg).iter()
                    if node.tag.endswith("circle") and node.get("r") == ".51"]
            self.assertEqual(len(hubs), count)
            sources.append(svg)
        self.assertEqual(len(set(sources)), 3)
        for appearance in (gpu(None), gpu(0), gpu("2"), gpu(3, "gpu_neutral"), gpu(None, "gpu_integrated")):
            self.assign("appearance", appearance)
            self.assertFalse(any(node.tag.endswith("circle") for node in ET.fromstring(self.svg(glyph)).iter()))
        self.assertFalse(self.window.grabWindow().isNull())

    def test_only_matching_processor_semantics_activate_the_shape_and_legacy_stays_available(self):
        self.load_icon()
        icon = self.find("appearanceMetric")
        loader = self.find("metricHardwareGlyphLoader")
        for name, appearance in (("gpu", gpu(2)), ("cpu", dict(kind="cpu", vendor="amd", style="am5"))):
            self.window.setProperty("glyph", name)
            self.assign("appearance", appearance)
            self.assertTrue(icon.property("hasHardwareAppearance"))
            self.assertTrue(loader.property("active"))
            self.assertIsNotNone(loader.property("item"))
            self.assertEqual((icon.width(), icon.height()), (18, 18))
        for name, appearance in (("gpu", {}), ("gpu", dict(kind="cpu")), ("temperature", dict(kind="cpu"))):
            self.window.setProperty("glyph", name)
            self.assign("appearance", appearance)
            self.assertFalse(loader.property("active"))
            self.assertIsNone(loader.property("item"))
            self.assertTrue(self.find("metricIconGlyph").isVisible())

    def test_fresh_equal_maps_and_real_channel_updates_retain_shape_source_item_and_clock(self):
        self.load_icon()
        self.assign("appearance", gpu(2))
        icon = self.find("appearanceMetric")
        glyph = self.find("metricHardwareGlyphLoader").property("item")
        pointer = getCppPointer(glyph)[0]
        source = glyph.property("svgSource")
        changes = QSignalSpy(glyph.svgSourceChanged)
        self.assertTrue(changes.isValid())
        clock = self.find("metricEffectClock")
        self.find("metricIconAnimation").stop()
        subscription = icon.property("clockSubscription")
        icon.setProperty("loadPhase", .413)
        for index in range(8):
            self.assign("appearance", gpu(2))
            thermal = .2 + index * .05
            self.assign("channels", dict(profile="processor", available=True, load=.2 + index * .07,
                                          thermal=thermal, energy=.25))
            self.assertEqual(getCppPointer(self.find("metricHardwareGlyphLoader").property("item"))[0], pointer)
            self.assertEqual(glyph.property("svgSource"), source)
            self.assertTrue(subscription.strictlyEquals(icon.property("clockSubscription")))
            self.assertAlmostEqual(icon.property("thermalTarget"), thermal)
            self.assertAlmostEqual(icon.property("loadPhase"), .413)
        self.assertEqual(changes.count(), 0)
        self.assertEqual(clock.property("subscriberCount"), 1)

    def test_shapes_add_no_clock_and_hidden_minimized_or_reduced_motion_release_existing_clock(self):
        self.load_icon()
        icon = self.find("appearanceMetric")
        glyph = self.find("metricHardwareGlyphLoader").property("item")
        pointer = getCppPointer(glyph)[0]
        self.assertEqual(len(self.window.findChildren(QObject, "metricEffectClock")), 1)
        self.assertEqual(self.find("metricEffectClock").property("subscriberCount"), 1)
        for pause, resume in ((self.window.hide, self.window.showNormal),
                              (lambda: self.window.setVisibility(QWindow.Minimized), self.window.showNormal),
                              (lambda: self.window.setProperty("motionAllowed", False),
                               lambda: self.window.setProperty("motionAllowed", True))):
            pause()
            QTest.qWait(25)
            self.assertFalse(icon.property("animationRunning"))
            self.assertIsNone(self.window.findChild(QObject, "metricEffectClock"))
            resume()
            QTest.qWait(25)
            self.assertTrue(icon.property("animationRunning"))
            self.assertEqual(self.find("metricEffectClock").property("subscriberCount"), 1)
            self.assertEqual(getCppPointer(self.find("metricHardwareGlyphLoader").property("item"))[0], pointer)

    def test_cpu_appearance_cannot_turn_temperature_into_a_processor_or_invent_a_missing_channel(self):
        self.load_icon()
        self.window.setProperty("glyph", "temperature")
        self.assign("appearance", dict(kind="cpu", vendor="amd", style="am5"))
        icon = self.find("appearanceMetric")
        self.assertFalse(icon.property("hasHardwareAppearance"))
        self.assertTrue(icon.property("thermometerEnabled"))
        self.assertAlmostEqual(icon.property("thermometerTarget"), .4)
        self.assign("channels", dict(profile="processor", available=True, load=.9, thermal=None, energy=.9))
        self.assertFalse(icon.property("thermometerEnabled"))
        self.assertFalse(icon.property("animationRunning"))
        self.assertIsNone(icon.property("thermalTarget"))

    def test_real_controller_projection_keeps_selected_appearance_off_and_stale_without_changing_channels(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate
        config = copy.deepcopy(DEFAULT)
        config["top_bar"]["hardware_icon_style"] = "outline"
        config["top_bar"]["items"] = [dict(id="b_chosen", metric="gpu_usage", prefs=dict(
            gpu_target="1", style="icon_value", icon_effect="off"))]
        with patch.object(controls, "load", return_value=validate(config)):
            controller = controls.Controller()
        self.addCleanup(controller.close)
        controller._data = dict(time=time.time(), cpu_name="AMD Synthetic CPU", cpu_usage=40, cpu_temp=40,
                                gpus={"0": dict(label="AMD Other GPU", gpu_usage=99, gpu_temp=110, gpu_power=290),
                                      "1": dict(label="NVIDIA Chosen GPU", gpu_usage=20, gpu_temp=25, gpu_power=30)})
        row = controller.topBarRows()[0]
        appearance = row["hardware_appearance"]
        self.assertEqual((appearance["kind"], appearance["vendor"]), ("gpu", "nvidia"))
        self.assertIsNone(appearance["fan_count"])
        self.assertEqual(row["numeric_value"], 20)
        self.assertEqual(row["hardware_state"], {})
        self.load_icon()
        self.assign("appearance", appearance)
        glyph = self.find("metricHardwareGlyphLoader").property("item")
        self.assertIsNotNone(glyph)
        self.assertEqual(self.svg(glyph), self.svg(self.find("controlGlyph")))
        controller._saved["top_bar"]["items"][0]["prefs"]["icon_effect"] = "auto"
        state = controller.topBarRows()[0]["hardware_state"]
        self.assertEqual([state[key] for key in ("load", "thermal", "energy")], [.2, .2, .1])
        controller._data["time"] = time.time() - 1000
        stale = controller.topBarRows()[0]
        self.assertEqual(stale["hardware_appearance"], appearance)
        self.assertFalse(stale["available"])
        self.assertFalse(stale["hardware_state"]["available"])
        self.assertTrue(all(stale["hardware_state"][key] is None for key in ("load", "thermal", "energy")))
        controller._saved["top_bar"]["items"] = [dict(id="b_cpu", metric="cpu_usage", prefs=dict(icon_effect="off"))]
        self.assertEqual(controller.topBarRows()[0]["hardware_appearance"]["kind"], "cpu")

    def test_real_controller_to_bar_state_keeps_optional_sg_front_when_none_crosses_qvariant_map(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate
        from top_bar_runtime import BarViewState
        config = copy.deepcopy(DEFAULT)
        config["language"] = "zh-CN"
        config["top_bar"]["hardware_icon_style"] = "solid"
        config["top_bar"]["items"] = [dict(id="b_sg", metric="gpu_usage", prefs=dict(
            gpu_target="0", style="icon_value", icon_effect="off"))]
        with patch.object(controls, "load", return_value=validate(config)):
            controller = controls.Controller()
        self.addCleanup(controller.close)
        # Demand may register a synthetic lease, but must never start a process
        # monitor. All values originate in this test, not a collector.
        controller._process_sampling_enabled = False
        controller._data = dict(time=time.time(), gpus={"0": dict(
            label="GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC",
            gpu_usage=20, gpu_temp=40, gpu_power=30)})
        manager = QObject()
        manager.controller = controller
        manager.enter_panel = lambda: None
        manager.leave = lambda: None
        self.addCleanup(manager.deleteLater)
        self.state = BarViewState(manager, "synthetic-sg")
        self.state._config = copy.deepcopy(controller._saved)
        self.state._detail = controller.topBarDetailRow("b_sg")
        actual = self.state._detail["hardware_appearance"]
        self.assertEqual(actual["confidence"], "model")
        self.assertIsNone(actual["fan_count"])
        self.assertEqual(actual["visible_fan_count"], 3)
        self.engine.rootContext().setContextProperty("stats", controller)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        self.window = self.component.createWithInitialProperties({"barState": self.state})
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        self.window.setProperty("showMetadata", True)
        QTest.qWait(20)
        for style in ("solid", "miniature", "soft"):
            with self.subTest(style=style):
                controller._saved["top_bar"]["hardware_icon_style"] = style
                self.state._detail = controller.topBarDetailRow("b_sg")
                self.state.detailChanged.emit()
                self.app.processEvents()
                # Unlike JSON.parse fixtures, Python None can become JS
                # undefined at the real QVariantMap property boundary.
                self.assertTrue(self.evaluate(self.window, "detail.hardware_appearance.fan_count == null"))
                caption = self.find("topBarDetailAppearance").property("text")
                self.assertIn("风扇总数未确认", caption)
                self.assertIn("正面可见风扇: 3", caption)
                self.assertNotIn("风扇数量: 3", caption)
                glyph = self.find("topBarDetailAppearanceLoader").property("item")
                self.assertIsNotNone(glyph)
                layout = self.fan_layout(self.svg(glyph))
                self.assertEqual(len(layout), 3)
                self.assert_front_fans_fit(layout)
                self.assertIsNone(controller._process_monitor)

    def test_real_details_metadata_distinguishes_match_levels_and_only_confirms_model_fan_counts(self):
        self.state = fixture.ModuleState()
        self.state.details.update(family="gpu", icon="gpu", hardware_name="Synthetic GPU", source="Synthetic provider")
        self.engine.rootContext().setContextProperty("stats", self.state)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        self.window = self.component.createWithInitialProperties({"barState": self.state})
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        QTest.qWait(30)
        collapsed_height = self.window.height()
        text = self.find("topBarDetailAppearance")
        loader = self.find("topBarDetailAppearanceLoader")
        self.assertIsNone(loader.property("item"))
        cases = [(gpu(None, confidence="generic"), "通用外观"),
                 (gpu(3, confidence="brand"), "品牌外观 · Synthetic GPU"),
                 (gpu(None, confidence="series"), "系列外观"),
                 (gpu(3, confidence="series"), "系列外观"),
                 (gpu(None), "型号外观 · Synthetic GPU · 风扇总数未确认"),
                 (gpu("2"), "型号外观 · Synthetic GPU"),
                 (gpu(2), "型号外观 · Synthetic GPU · 风扇数量: 2"),
                 (dict(gpu(4), visible_fan_count=3),
                  "型号外观 · Synthetic GPU · 风扇数量: 4 · 正面可见风扇: 3"),
                 (dict(gpu(2), visible_fan_count=1),
                  "型号外观 · Synthetic GPU · 风扇数量: 2 · 正面可见风扇: 1"),
                 (dict(gpu(None), visible_fan_count=3),
                  "型号外观 · Synthetic GPU · 风扇总数未确认 · 正面可见风扇: 3"),
                 (dict(kind="cpu", confidence="model", label="Synthetic CPU", fan_count=3), "型号外观 · Synthetic CPU")]
        for index, (appearance, expected) in enumerate(cases):
            self.window.setProperty("showMetadata", False)
            self.state.details = dict(self.state.details, hardware_appearance=appearance, source="Synthetic provider " + str(index))
            self.state.changed.emit()
            QTest.qWait(10)
            self.assertFalse(text.isVisible())
            self.assertIsNone(loader.property("item"))
            self.assertEqual(self.window.height(), collapsed_height)
            self.window.setProperty("showMetadata", True)
            QTest.qWait(10)
            self.assertEqual(text.property("text"), expected, (appearance,
                self.evaluate(self.window, "typeof detail.hardware_appearance.fan_count")))
            self.assertTrue(text.isVisible())
            self.assertTrue(self.evaluate(text, "textFormat === Text.PlainText"))
            glyph = loader.property("item")
            self.assertIsNotNone(glyph)
            self.assertEqual((glyph.width(), glyph.height()), (64, 64))
        self.window.setProperty("showMetadata", False)
        QTest.qWait(10)
        self.assertIsNone(loader.property("item"))

    def test_real_details_series_features_are_bounded_and_expanded_texture_releases_when_hidden(self):
        self.state = fixture.ModuleState()
        appearance = dict(gpu(None, "gpu_neutral", "series"), series_id="synthetic_series",
                          series_label="Synthetic series", features=["已翻译特征一", "已翻译特征二", "不能显示的第三项"])
        self.state.details.update(family="gpu", icon="gpu", hardware_name="Synthetic GPU", source="Synthetic provider",
                                  hardware_appearance=appearance)
        self.engine.rootContext().setContextProperty("stats", self.state)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        self.window = self.component.createWithInitialProperties({"barState": self.state})
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        QTest.qWait(20)
        loader = self.find("topBarDetailAppearanceLoader")
        self.assertIsNone(loader.property("item"))
        self.window.setProperty("showMetadata", True)
        QTest.qWait(20)
        self.assertIsNotNone(loader.property("item"))
        self.assertEqual(self.find("topBarDetailAppearanceSeries").property("text"), "Synthetic series")
        self.assertEqual(self.find("topBarDetailAppearanceFeatures").property("text"), "已翻译特征一\n已翻译特征二")
        self.assertEqual(self.find("topBarDetailAppearance").property("text"), "系列外观")
        self.window.hide()
        QTest.qWait(15)
        self.assertTrue(self.window.property("showMetadata"))
        self.assertIsNone(loader.property("item"))
        self.window.show()
        QTest.qWait(15)
        self.assertIsNotNone(loader.property("item"))
        self.window.setProperty("hostMinimized", True)
        QTest.qWait(15)
        self.assertIsNone(loader.property("item"))
        self.window.setProperty("hostMinimized", False)
        QTest.qWait(15)
        self.assertIsNotNone(loader.property("item"))

    def test_series_use_individual_filled_faces_without_guessing_any_fans(self):
        from hardware_series import SERIES_CATALOG
        self.load_icon()
        glyph = self.find("controlGlyph")
        for style in ("solid", "miniature", "soft"):
            faces = []
            for series in SERIES_CATALOG:
                value = dict(gpu(3), icon_set=style, board_vendor=series["board_vendor"],
                             series_id=series["id"], accent="#7e8b98")
                self.assign("appearance", value)
                tree = ET.fromstring(self.svg(glyph))
                face = next(node for node in tree.iter()
                            if node.get("class", "").split() == ["hardware-series-face", series["id"]])
                self.assertGreaterEqual(len(list(face)), 2)
                self.assertTrue(any(node.tag.split("}")[-1] in ("path", "rect")
                                    and node.get("fill") not in (None, "none")
                                    for node in face))
                self.assertEqual(sum(node.get("class") == "hardware-fan-hub" for node in tree.iter()), 3)
                # Remove the identifying class before comparing physical paths.
                face.attrib.pop("class")
                faces.append(ET.tostring(face))
                self.assign("appearance", dict(value, fan_count=None))
                self.assertFalse(any(node.get("class") == "hardware-fan-hub"
                                     for node in ET.fromstring(self.svg(glyph)).iter()))
            self.assertEqual(len(set(faces)), len(SERIES_CATALOG))

    def test_conflicting_series_brand_cannot_select_another_manufacturers_face(self):
        self.load_icon()
        glyph = self.find("controlGlyph")
        for style in ("solid", "miniature", "soft"):
            self.assign("appearance", dict(gpu(2), icon_set=style, board_vendor="asus", series_id="msi_suprim"))
            self.assertFalse(any("hardware-series-face" in node.get("class", "")
                                 for node in ET.fromstring(self.svg(glyph)).iter()))

    def test_outline_keeps_exact_gpu_drawings_and_guarded_cpu_package_drawings(self):
        # CPU package/SKU drawing is intentional; legacy GPU hashes stay exact.
        from hardware_appearance import appearance_for
        from tests.test_hardware_cartoon import assert_cpu_artwork
        cases = (
            ("cpu", "Intel Core i7-13700KF", "a82bae4cf9e8b4a7c5ef6ec66a3414d48c1d577e3d246730e8da994c4014bf41"),
            ("cpu", "AMD Ryzen 9 9950X", "63190769e5b03ec7cb5a970553c3726e309da3656a9033b45cae66cf204fa183"),
            ("gpu", "DUAL-RTX4060-O8G", "b08a961cb281d10a62d105d9a2e8a306afdeb1195b3805767145549d30f9cfbe"),
            ("gpu", "TUF-RTX4070TIS-O16G-GAMING", "19827c993b8a33978631ac6d2919a07de67e1324b73a05f2ad2631b04cc199d0"),
            ("gpu", "NVIDIA GeForce RTX 4070", "8c9cc5541d145f68bb67bae0d7b1d80cc559dac6c989e95e0dac0df394df6a68"),
        )
        self.load_icon()
        glyph = self.find("controlGlyph")
        glyph.setProperty("ink", "#303a48")
        for kind, name, expected in cases:
            value=dict(appearance_for(kind,name),icon_set='outline');self.assign('appearance',value)
            if kind=='cpu':assert_cpu_artwork(self,value,dict(key=glyph.property('geometryKey'),source=glyph.property('svgSource')))
            self.assertEqual(hashlib.sha256(self.svg(glyph).encode()).hexdigest(), expected)

    def test_three_new_versions_render_only_the_confirmed_number_of_physical_fans(self):
        self.load_icon()
        glyph = self.find("controlGlyph")
        distinct = []
        for style in ("solid", "miniature", "soft"):
            for count in (1, 2, 3, 0, None, "2", True):
                self.assign("appearance", dict(gpu(count), icon_set=style))
                svg = self.svg(glyph)
                tree = ET.fromstring(svg)
                hubs = [node for node in tree.iter() if node.get("class") == "hardware-fan-hub"]
                self.assertEqual(len(hubs), count if type(count) is int and count in (1, 2, 3) else 0)
                for node in tree.iter():
                    self.assertNotIn(node.tag.split("}")[-1], ("image", "filter", "text", "script", "animate"))
                if type(count) is int and count == 2:
                    distinct.append(svg)
            for silhouette in ("gpu_neutral", "gpu_integrated"):
                self.assign("appearance", dict(gpu(3, style=silhouette), icon_set=style))
                self.assertFalse(any(node.get("class") == "hardware-fan-hub"
                                     for node in ET.fromstring(self.svg(glyph)).iter()))
        self.assertEqual(len(set(distinct)), 3)

    def test_verified_front_planes_draw_separately_from_physical_totals_in_all_modern_styles(self):
        from hardware_appearance import appearance_for
        cases = (
            ("ROG-ASTRAL-RTX5080-O16G-GAMING", 4, 3),
            ("GALAX GeForce RTX 5080 HOF Extreme", 4, 3),
            ("INNO3D GeForce RTX 3080 iCHILL X4", 4, 3),
            ("MSI GeForce RTX 4080 SUPER 16G EXPERT", 2, 1),
            ("GALAX GeForce RTX 4070 Ti SUPER SG Plus 1-Click OC", None, 3),
        )
        self.load_icon()
        glyph = self.find("controlGlyph")
        for style in ("solid", "miniature", "soft"):
            for model, physical, front in cases:
                with self.subTest(style=style, model=model):
                    value = appearance_for("gpu", model)
                    self.assertEqual(value["confidence"], "model")
                    self.assertEqual((value["fan_count"], value["visible_fan_count"]), (physical, front))
                    self.assign("appearance", dict(value, icon_set=style))
                    layout = self.fan_layout(self.svg(glyph))
                    self.assertEqual(len(layout), front)
                    self.assert_front_fans_fit(layout)
                    # EXPERT's push/pull second fan belongs to the back. Its
                    # one visible front fan sits at the right end of the slab.
                    if front == 1:
                        self.assertGreater(layout[0][0], 13)

    def test_four_physical_fans_without_a_valid_front_count_never_become_three(self):
        self.load_icon()
        glyph = self.find("controlGlyph")
        for style in ("solid", "miniature", "soft"):
            value = dict(gpu(4), icon_set=style, board_vendor="asus", series_id="asus_astral")
            # The known series silhouette is not evidence for a front layout.
            for front in ("absent", None, "3", True, -1, 4, [], {}):
                with self.subTest(style=style, front=front):
                    candidate = dict(value)
                    if front != "absent":
                        candidate["visible_fan_count"] = front
                    self.assign("appearance", candidate)
                    self.assertEqual(self.fan_layout(self.svg(glyph)), [])
            for silhouette in ("gpu_neutral", "gpu_integrated"):
                self.assign("appearance", dict(value, style=silhouette, visible_fan_count=3))
                self.assertEqual(self.fan_layout(self.svg(glyph)), [])
            # An impossible front total is rejected without losing the known
            # ordinary two-fan layout; optional fronts require a model match.
            self.assign("appearance", dict(gpu(2), icon_set=style, visible_fan_count=3))
            self.assertEqual(len(self.fan_layout(self.svg(glyph))), 2)
            self.assign("appearance", dict(gpu(None, confidence="series"), icon_set=style,
                                           visible_fan_count=3))
            self.assertEqual(self.fan_layout(self.svg(glyph)), [])

    def test_total_only_metadata_updates_keep_the_same_static_front_texture(self):
        self.load_icon()
        glyph = self.find("controlGlyph")
        for style in ("solid", "miniature", "soft"):
            value = dict(gpu(3), icon_set=style, visible_fan_count=3)
            self.assign("appearance", value)
            source = glyph.property("svgSource")
            changed = QSignalSpy(glyph.svgSourceChanged)
            # Synthetic metadata-only updates model an optional rear fan being
            # confirmed; the already-confirmed front must not be re-encoded.
            for total in (None, 4, 3, None):
                self.assign("appearance", dict(value, fan_count=total))
                self.assertEqual(glyph.property("svgSource"), source)
                self.assertEqual(len(self.fan_layout(self.svg(glyph))), 3)
            self.assertEqual(changed.count(), 0)

    def test_larger_advanced_and_ex_center_and_lower_ftw3_center_survive_every_modern_theme(self):
        from hardware_appearance import appearance_for
        self.load_icon()
        glyph = self.find("controlGlyph")
        cases = (("Colorful iGame GeForce RTX 4070 Ti Advanced OC-V", "colorful_advanced", 1.15),
                 ("GALAX GeForce RTX 4070 EX Gamer 1-Click OC D6", "galax_ex_gamer", 1.05),
                 ("10G-P5-3895-KR", "evga_ftw3", None))
        for style in ("solid", "miniature", "soft"):
            for model, series, minimum_center_ratio in cases:
                with self.subTest(style=style, series=series):
                    value = appearance_for("gpu", model)
                    self.assertEqual(value["series_id"], series)
                    self.assign("appearance", dict(value, icon_set=style))
                    layout = self.fan_layout(self.svg(glyph))
                    self.assertEqual(len(layout), 3)
                    self.assert_front_fans_fit(layout)
                    left, center, right = layout
                    self.assertAlmostEqual(left[2], right[2])
                    if minimum_center_ratio is not None:
                        self.assertGreater(center[2], left[2] * minimum_center_ratio)
                        self.assertAlmostEqual(left[1], center[1])
                        self.assertAlmostEqual(center[1], right[1])
                    else:
                        self.assertGreater(center[1] - left[1], .4)
                        self.assertAlmostEqual(left[1], right[1])
                        self.assertAlmostEqual(left[2], center[2])

    def test_version_switch_preserves_existing_feedback_phase_and_clock(self):
        self.load_icon()
        icon = self.find("appearanceMetric")
        glyph = self.find("metricHardwareGlyphLoader").property("item")
        pointer = getCppPointer(glyph)[0]
        subscription = icon.property("clockSubscription")
        self.find("metricIconAnimation").stop()
        icon.setProperty("loadPhase", .413)
        sources = []
        for style in ("outline", "solid", "miniature", "soft"):
            self.assign("appearance", dict(gpu(2), icon_set=style))
            self.assertEqual(getCppPointer(self.find("metricHardwareGlyphLoader").property("item"))[0], pointer)
            self.assertTrue(subscription.strictlyEquals(icon.property("clockSubscription")))
            self.assertAlmostEqual(icon.property("loadPhase"), .413)
            self.assertAlmostEqual(icon.property("thermalTarget"), .4)
            self.assertEqual(self.find("metricEffectClock").property("subscriberCount"), 1)
            source = glyph.property("svgSource")
            changes = QSignalSpy(glyph.svgSourceChanged)
            self.assign("appearance", dict(gpu(2), icon_set=style))
            self.assertEqual(changes.count(), 0)
            sources.append(source.toString())
        self.assertEqual(len(set(sources)), 4)

    def test_classic_version_uses_original_metric_glyph_and_a_lazy_detail_glyph(self):
        self.load_icon()
        self.assign("appearance", dict(gpu(2), icon_set="classic"))
        icon = self.find("appearanceMetric")
        self.assertFalse(icon.property("hasHardwareAppearance"))
        self.assertIsNone(self.find("metricHardwareGlyphLoader").property("item"))
        self.assertTrue(self.find("metricIconGlyph").isVisible())
        control = self.find("controlGlyph")
        self.assertEqual(control.property("svgSource").toString(), "")
        loader = control.findChild(QObject, "hardwareClassicGlyphLoader")
        self.assertIsNotNone(loader.property("item"))
        self.assertEqual(loader.property("item").property("name"), "gpu")
        self.assertAlmostEqual(icon.property("thermalTarget"), .4)
        self.assign("appearance", dict(kind="cpu", style="am5", icon_set="classic"))
        self.assertEqual(loader.property("item").property("name"), "cpu")

    def test_classic_detail_caption_does_not_claim_a_matching_physical_drawing(self):
        self.state = fixture.ModuleState()
        self.state.details.update(family="gpu", icon="gpu", hardware_name="Synthetic GPU",
                                  source="Synthetic provider",
                                  hardware_appearance=dict(gpu(2), icon_set="classic",
                                                           series_label="Synthetic series", features=["Synthetic feature"]))
        self.engine.rootContext().setContextProperty("stats", self.state)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        self.window = self.component.createWithInitialProperties(dict(barState=self.state))
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        self.window.setProperty("showMetadata", True)
        QTest.qWait(20)
        caption = self.find("topBarDetailAppearance").property("text")
        self.assertIn("经典通用", caption)
        self.assertNotIn("型号外观", caption)
        self.assertIn("风扇数量: 2", caption)
        self.assertEqual(self.find("topBarDetailAppearanceSeries").property("text"), "")
        self.assertEqual(self.find("topBarDetailAppearanceFeatures").property("text"), "")


if __name__ == "__main__":
    unittest.main()
