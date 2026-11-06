"""Offline memory identities and the real QVariantMap -> QML glyph boundary."""

import base64
import copy
import os
import time
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, QUrl, Signal
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import getCppPointer

import hardware_appearance as hardware
import memory_appearance as memory
from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]


def module(part="CMK16GX4M2B3200C16", manufacturer="CORSAIR", form="dimm"):
    return dict(part_number=part, manufacturer=manufacturer, form_factor=form)


class MemoryIdentityTests(unittest.TestCase):
    def test_reviewed_complete_parts_have_sources_and_distinct_model_identities(self):
        aliases, series = set(), {row["id"]: row for row in memory.SERIES_CATALOG}
        self.assertGreaterEqual(len(memory.CATALOG), 12)
        for row in memory.CATALOG:
            with self.subTest(model=row["id"]):
                self.assertTrue(row["source_url"].startswith("https://"))
                self.assertEqual(series[row["series_id"]]["brand"], row["brand"])
                for alias in row["aliases"]:
                    self.assertNotIn(alias.casefold(), aliases)
                    aliases.add(alias.casefold())
                    value = memory.appearance_for_memory(model=alias.lower())
                    self.assertEqual((value["id"], value["confidence"]), (row["id"], "model"))
                    self.assertEqual(value["board_vendor"], row["brand"])
                    self.assertEqual(value["style"], row["form_factor"])
                    self.assertEqual(value["kind"], "memory")
                    self.assertIsNone(value["fan_count"])
                    self.assertIsNone(value["visible_fan_count"])

    def test_part_boundaries_do_not_strip_capacity_kit_color_or_revision_suffixes(self):
        exact={alias.casefold():row['id'] for row in memory.CATALOG for alias in row['aliases']}
        for row in memory.CATALOG:
            part = row["aliases"][0]
            for value in (part[:-1], "X" + part, part + "X", part + "-WHITE", part + "/1", part + ".1", part + "_EXTRA"):
                with self.subTest(part=part, invalid=value):
                    result=memory.appearance_for_memory(model=value)
                    if value.casefold() in exact:
                        self.assertEqual((result['confidence'],result['id']),('model',exact[value.casefold()]))
                    else:
                        self.assertNotEqual(result["confidence"], "model")
        # SMBIOS can expose the individual module, while a retail page names
        # the two-module kit. Neither is obtained by removing a kit suffix.
        for value in ("CMK8GX4M1B3200C16", "F4-4000C16-16GTZRA"):
            result = memory.appearance_for_memory(model=value, manufacturer="G.SKILL" if value.startswith("F4-") else "CORSAIR")
            self.assertNotEqual(result["confidence"], "model")
            self.assertEqual(result["series_id"], "")

    def test_series_requires_a_confirmed_brand_and_does_not_absorb_neighbor_series(self):
        for row in memory.SERIES_CATALOG:
            name = row["aliases"][0]
            with self.subTest(series=row["id"]):
                self.assertNotEqual(memory.appearance_for_memory(name=name)["confidence"], "series")
                result = memory.appearance_for_memory(name=name, manufacturer=memory.BRANDS[row["brand"]][0])
                self.assertEqual((result["series_id"], result["confidence"]), (row["id"], "series"))
                wrong = memory.appearance_for_memory(name=name, manufacturer="unrelated manufacturer")
                self.assertEqual(wrong["series_id"], "")
        for value in ("Kingston FURY Beast RGB", "Kingston FURY Renegade RGB", "G.SKILL Trident Z Royal Elite",
                      "G.SKILL Trident Z5 Royal", "G.SKILL Ripjaws SO-DIMM", "CORSAIR DOMINATOR TITANIUM RGB"):
            with self.subTest(neighbor=value):
                self.assertNotEqual(memory.appearance_for_memory(name=value)["confidence"], "series")

    def test_conflicting_brands_or_multiple_complete_parts_return_neutral(self):
        for values in (dict(model="CMK16GX4M2B3200C16", manufacturer="G.SKILL"),
                       dict(name="CORSAIR G.SKILL Vengeance LPX"),
                       dict(name="CMK16GX4M2B3200C16", model="F4-3200C16D-16GVKB")):
            with self.subTest(values=values):
                result = memory.appearance_for_memory(**values)
                self.assertEqual((result["confidence"], result["style"], result["series_id"]),
                                 ("generic", "memory_neutral", ""))

    def test_generic_ddr_rgb_and_manufacturer_do_not_invent_form_or_runtime_state(self):
        for name in ("32GB DDR5", "DDR4 RGB", "memory", "Crucial", "CORSAIR DDR5"):
            value = memory.appearance_for_memory(name=name)
            self.assertEqual(value["style"], "memory_neutral")
            self.assertEqual(value["presentation"], "neutral")
            self.assertNotIn("ddr_generation", value)
            self.assertNotIn("rgb_enabled", value)
        self.assertEqual(memory.appearance_for_memory(name="unknown SO-DIMM")["style"], "sodimm")
        self.assertEqual(memory.appearance_for_memory(name="unknown DIMM SO-DIMM")["style"], "memory_neutral")
        self.assertEqual(memory.appearance_for_memory(name="SO-DIMM", model="CMK16GX4M2B3200C16")["style"], "memory_neutral")

    def test_cached_result_does_not_share_mutable_fields(self):
        a = memory.appearance_for_memory(model="CMK16GX4M2B3200C16")
        a["label"] = "changed"
        a["features"].append("changed")
        b = memory.appearance_for_memory(model="CMK16GX4M2B3200C16")
        self.assertNotEqual(b["label"], "changed")
        self.assertNotIn("changed", b["features"])
        self.assertIsNot(a, b)
        self.assertIsNot(a["features"], b["features"])

    def test_input_bound_precedes_cache_even_for_expanding_unicode_and_non_strings(self):
        with patch.object(memory, "_resolve", wraps=memory._resolve) as resolver:
            memory.appearance_for_memory(name="\u0130" * 500, model="x" * 1000, manufacturer="G.SKILL" * 100)
            self.assertTrue(all(isinstance(value, str) and len(value) <= 256 for value in resolver.call_args.args))
            memory.appearance_for_memory(name=[], model={}, manufacturer=object())
            self.assertEqual(resolver.call_args.args, ("", "", ""))
        self.assertNotEqual(memory.appearance_for_memory(model="x" * 256 + "CMK16GX4M2B3200C16")["confidence"], "model")

    def test_cache_is_lru_bounded_to_128_identities(self):
        memory._resolve.cache_clear()
        self.addCleanup(memory._resolve.cache_clear)
        for index in range(129):
            memory.appearance_for_memory(model="unrecognized-" + str(index))
        before = memory._resolve.cache_info()
        self.assertEqual((before.maxsize, before.currsize), (128, 128))
        memory.appearance_for_memory(model="unrecognized-0")
        self.assertEqual(memory._resolve.cache_info().misses, before.misses + 1)
        memory.appearance_for_memory(model="unrecognized-0")
        self.assertEqual(memory._resolve.cache_info().hits, before.hits + 1)


class MemoryAggregationTests(unittest.TestCase):
    def test_uniform_reviewed_modules_match_without_choosing_an_arbitrary_slot(self):
        for row in memory.CATALOG:
            devices = [module(row["aliases"][0], memory.BRANDS[row["brand"]][0], row["form_factor"]) for _ in range(2)]
            with self.subTest(model=row["id"]):
                result = hardware.memory_appearance(dict(memory_modules=devices))
                self.assertEqual((result["id"], result["confidence"]), (row["id"], "model"))

    def test_mixed_parts_never_borrow_the_first_module_or_legacy_identity(self):
        devices = [module(), module("F4-3200C16D-16GVKB", "G.SKILL")]
        for rows in (devices, list(reversed(devices))):
            value = hardware.memory_appearance(dict(memory_modules=rows, memory_model="CMK16GX4M2B3200C16"))
            self.assertEqual((value["style"], value["series_id"], value["source_url"]), ("memory_neutral", "", ""))
            self.assertNotEqual(value["confidence"], "model")
            self.assertEqual(value["label"], "混合内存")

    def test_present_module_table_is_authoritative_even_when_empty_or_untrusted(self):
        invalid = ([], None, {}, "bad", (), [object()], [None], [module()] * 65,
                   [module(manufacturer=None)], [module(form=[])], [dict(part_number=7)])
        for devices in invalid:
            with self.subTest(type=type(devices).__name__, value=repr(devices)[:70]):
                value = hardware.memory_appearance(dict(memory_modules=devices, memory_model="CMK16GX4M2B3200C16",
                                                        memory_name="CORSAIR Vengeance LPX", memory_manufacturer="CORSAIR"))
                self.assertEqual(value["style"], "memory_neutral")
                self.assertEqual(value["series_id"], "")
                self.assertNotEqual(value["confidence"], "model")

    def test_unknown_authoritative_modules_do_not_borrow_legacy_but_absent_table_can(self):
        flat = dict(memory_model="CMK16GX4M2B3200C16", memory_manufacturer="CORSAIR")
        self.assertEqual(hardware.memory_appearance(flat)["confidence"], "model")
        value = hardware.memory_appearance(dict(flat, memory_modules=[module("unknown", "unrecognized")]))
        self.assertEqual((value["style"], value["confidence"]), ("dimm", "generic"))
        self.assertEqual((value["series_id"], value["source_url"]), ("", ""))

    def test_firmware_form_conflict_drops_verified_case_while_unknown_parts_can_use_known_form(self):
        conflict = hardware.memory_appearance(dict(memory_modules=[module(form="sodimm")]))
        self.assertEqual(conflict["style"], "sodimm")
        self.assertEqual((conflict["confidence"], conflict["series_id"], conflict["source_url"]), ("generic", "", ""))
        for form, expected in (("dimm", "dimm"), ("sodimm", "sodimm"), ("cudimm", "dimm"), ("csodimm", "sodimm")):
            with self.subTest(form=form):
                value = hardware.memory_appearance(dict(memory_modules=[module("F4-4000C16-16GTZRA", "G.SKILL", form)] * 2))
                self.assertEqual(value["style"], expected)
                self.assertEqual(value["series_id"], "")
                self.assertNotEqual(value["confidence"], "model")

    def test_ram_uses_memory_while_vram_scope_keeps_the_selected_gpu(self):
        data = dict(memory_modules=[module()], gpus={"0": dict(gpu_name="ASUS Dual GeForce RTX 4060 OC Edition 8GB")})
        ram = hardware.metric_appearance(data, "ram_usage", {})
        self.assertEqual((ram["kind"], ram["confidence"]), ("memory", "model"))
        vram = hardware.metric_appearance(data, "ram_usage", {}, scope="gpus", target="0")
        self.assertEqual((vram["kind"], vram["id"]), ("gpu", "asus-dual-4060-oc"))
        self.assertEqual(hardware.metric_appearance(data, "ram_usage", {}, external=True), {})

    def test_controller_ram_details_preserve_real_part_and_reading_without_inventing_a_series(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate
        config = copy.deepcopy(DEFAULT)
        config["top_bar"]["hardware_icon_style"] = "soft"
        config["top_bar"]["items"] = [dict(id="b_memory", metric="ram_percent", prefs=dict(style="icon_value", icon_effect="auto"))]
        with patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")), \
             patch("subprocess.Popen", side_effect=AssertionError("No process")), \
             patch("threading.Thread.start", side_effect=AssertionError("No thread")), \
             patch.object(controls, "load", return_value=validate(config)):
            controller = controls.Controller()
            try:
                controller._data = dict(time=time.time(), ram_percent=50, ram_used_gb=16, ram_total_gb=32,
                    memory_modules=[module("F4-4000C16-16GTZRA", "G Skill Intl") for _ in range(2)])
                row = controller.topBarDetailRow("b_memory")
                self.assertEqual(row["hardware_appearance"]["kind"], "memory")
                self.assertEqual(row["hardware_appearance"]["series_id"], "")
                self.assertIn("F4-4000C16-16GTZRA", row["hardware_name"])
                self.assertTrue(row["available"])
                self.assertAlmostEqual(row["hardware_state"]["load"], .5)
                self.assertIsNone(row["hardware_state"].get("thermal"))
            finally:
                controller.close()


class MemoryMapState(QObject):
    appearanceChanged = Signal()
    channelsChanged = Signal()

    def __init__(self):
        super().__init__()
        self.value = memory.appearance_for_memory(model="CMK16GX4M2B3200C16")
        self.channels_value = dict(profile="memory", available=True, load=.25)

    appearance = Property("QVariantMap", lambda self: copy.deepcopy(self.value), notify=appearanceChanged)
    channels = Property("QVariantMap", lambda self: dict(self.channels_value), notify=channelsChanged)

    def deliver(self, value):
        self.value = copy.deepcopy(value)
        self.appearanceChanged.emit()


class MemoryQVariantQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.thread = self.enterContext(patch("threading.Thread.start", side_effect=AssertionError("No worker")))
        self.state = MemoryMapState()
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        self.engine.rootContext().setContextProperty("memoryFixture", self.state)
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
Window {
 id:scene; width:150; height:100; visible:false; color:"#f5f7fa"
 property string glyphName:"memory"
 Product.MetricIcon {
  objectName:"memoryMetric"; x:12; y:16; width:18; height:18
  name:scene.glyphName; metric:"ram_usage"; hardwareAppearance:memoryFixture.appearance
  hardwareState:memoryFixture.channels; effect:"off"; motionEnabled:false; available:true; ink:"#303a48"
 }
 Product.HardwareGlyph {
  objectName:"memoryControl"; x:56; y:12; width:64; height:64
  appearance:memoryFixture.appearance; ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/MemoryAppearanceFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()
        QTest.qWait(20)

    def tearDown(self):
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()
        self.thread.assert_not_called()

    def find(self, name, parent=None):
        item = (parent or self.window).findChild(QObject, name)
        self.assertIsNotNone(item, name)
        return item

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return value[0] if isinstance(value, tuple) else value

    def deliver(self, value):
        self.state.deliver(value)
        self.app.processEvents()

    def assert_image_ready(self, image):
        # A real QVariant delivery can schedule a data-URL decode for the next
        # Qt event turn even with Image.asynchronous=false. Wait for readiness,
        # bounded to 200 ms, rather than relying on one incidental event cycle.
        for _ in range(40):
            status = self.evaluate(image, "Number(status)")
            if status == 1:
                return
            self.assertNotEqual(status, 3, "Static memory SVG failed to decode")
            QTest.qWait(5)
        self.fail("Static memory SVG did not become ready")

    @staticmethod
    def svg(glyph):
        source = glyph.property("svgSource").toString()
        header, body = source.split(",", 1)
        return base64.b64decode(body).decode() if ";base64" in header else unquote(body)

    def test_true_qvariant_map_dispatches_all_four_memory_themes_and_retains_static_source(self):
        control = self.find("memoryControl")
        icon = self.find("memoryMetric")
        loader = self.find("metricHardwareGlyphLoader", icon)
        sources = set()
        for style in ("outline", "solid", "miniature", "soft"):
            with self.subTest(style=style):
                value = dict(memory.appearance_for_memory(model="CMT32GX5M2B5600C36"), icon_set=style)
                self.deliver(value)  # Python QVariantMap, including real None, not JSON construction.
                self.assertTrue(icon.property("hasHardwareAppearance"))
                self.assertTrue(loader.property("active"))
                glyph = loader.property("item")
                pointer = getCppPointer(glyph)[0]
                key = control.property("geometryKey")
                fields = key.split("|")
                self.assertEqual((fields[0], fields[2], fields[3], fields[4], fields[5], fields[10]),
                                 ("memory", "corsair", "dimm", "-1", "rgb", style))
                self.assertEqual(fields[8], "corsair_dominator_platinum")
                source = self.svg(control)
                tree = ET.fromstring(source)
                self.assertEqual(tree.attrib["viewBox"], "0 0 24 24")
                self.assertNotIn("hardware-fan", source)
                self.assertNotIn("<text", source)
                self.assertNotIn("<filter", source)
                sources.add(source)
                image = self.find("hardwareGlyphImage", control)
                self.assert_image_ready(image)
                source_changes = QSignalSpy(control.svgSourceChanged)
                for index in range(4):
                    self.deliver(copy.deepcopy(value))
                    self.state.channels_value["load"] = .2 + index * .1
                    self.state.channelsChanged.emit()
                    self.app.processEvents()
                    self.assertEqual(control.property("geometryKey"), key)
                    self.assertEqual(self.svg(control), source)
                    self.assertEqual(getCppPointer(loader.property("item"))[0], pointer)
                self.assertEqual(source_changes.count(), 0)
        self.assertEqual(len(sources), 4)
        self.assertFalse(self.window.grabWindow().isNull())

    def test_real_memory_maps_switch_short_neutral_and_classic_without_borrowing_gpu_geometry(self):
        control = self.find("memoryControl")
        icon = self.find("memoryMetric")
        loader = self.find("metricHardwareGlyphLoader", icon)
        self.deliver(dict(memory.appearance_for_memory(model="KVR32S22S8/16"), icon_set="soft"))
        short_source = self.svg(control)
        self.assertEqual(control.property("geometryKey").split("|")[3], "sodimm")
        self.deliver(dict(memory.appearance_for_memory(name="DDR5 32GB"), icon_set="soft"))
        self.assertEqual(control.property("geometryKey").split("|")[3], "memory_neutral")
        self.assertNotEqual(self.svg(control), short_source)
        classic = dict(memory.appearance_for_memory(model="CMK16GX4M2B3200C16"), icon_set="classic")
        self.deliver(classic)
        self.assertFalse(loader.property("active"))
        self.assertIsNone(loader.property("item"))
        self.assertTrue(self.find("metricIconGlyph", icon).isVisible())
        self.assertEqual(control.property("geometryKey"), "")
        classic_loader = self.find("hardwareClassicGlyphLoader", control)
        self.assertTrue(classic_loader.property("active"))
        classic_item = classic_loader.property("item")
        self.assertEqual(classic_item.property("name"), "memory")
        lucide = self.find("lucideImage", classic_item)
        self.assert_image_ready(lucide)
        self.deliver(dict(classic, icon_set="solid"))
        self.assertTrue(loader.property("active"))
        # A VRAM symbol cannot consume a RAM appearance merely because both
        # metrics contain the word memory; processor semantics still gate it.
        self.window.setProperty("glyphName", "vram")
        self.app.processEvents()
        self.assertFalse(loader.property("active"))


if __name__ == "__main__":
    unittest.main()
