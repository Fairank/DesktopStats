"""Complete optional cartoon drawings and retained wide GPU planes; no device I/O."""
import base64
from collections import Counter
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QSignalSpy, QTest

from hardware_appearance import CATALOG, appearance_for
from memory_appearance import CATALOG as MEMORY_CATALOG, appearance_for_memory
from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]


def decode(source):
    if isinstance(source, QUrl):
        source = source.toString()
    header, payload = source.split(",", 1)
    return base64.b64decode(payload).decode() if ";base64" in header else unquote(payload)


def all_appearances():
    return [appearance_for(row[1], row[-1][0]) for row in CATALOG] + [
        appearance_for_memory(model=row["aliases"][0]) for row in MEMORY_CATALOG
    ]


class HardwareCartoonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native I/O")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
import "../native/HardwareShapes.js" as Shapes
Window {
 id: scene; width:120; height:64; visible:false
 property var appearance:({})
 property string genericName:"disk"
 function artwork(value,ink) {
  const key=Shapes.key(value,ink)
  return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)})
 }
 function generic(name,ink,moving) { return Shapes.genericSource(name,ink,moving) }
 Product.HardwareGlyph {
  objectName:"cartoonWideGlyph";x:8;y:8;width:30;height:22
  appearance:scene.appearance;ink:"#303a48";fanMotionEnabled:true;fanRotation:90
 }
 Product.MetricIcon {
  objectName:"cartoonMetric";x:52;y:8;width:30;height:22
  name:"gpu";metric:"gpu_usage";hardwareAppearance:scene.appearance
  effect:"auto";available:true;motionEnabled:true;intensity:1
  hardwareState:({profile:"processor",available:true,load:.4,thermal:.5,energy:.2,
   fan_speed:{available:true,rpm:1440,semantics:"measured",scope:"card",
    source:"Synthetic card RPM",timestamp:Date.now()/1000,display_slowdown:120}})
 }
 Product.MetricIcon {
  objectName:"cartoonGenericMetric";x:92;y:8;width:22;height:22
  name:scene.genericName;iconStyle:"cartoon";effect:"off";motionEnabled:false
  available:true;ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareCartoonFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])

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

    def evaluate(self, expression, item=None):
        item = item or self.window
        code = QQmlExpression(qmlContext(item), item, expression)
        result = code.evaluate()
        self.assertFalse(code.hasError(), code.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def drawing(self, appearance, ink="#303a48"):
        return json.loads(self.evaluate("artwork(" + json.dumps(appearance) + "," + json.dumps(ink) + ")"))

    def visual_item(self, root, name):
        pending = [root]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        return None

    def valid_svg(self, source):
        svg = decode(source)
        tree = ET.fromstring(svg)
        self.assertTrue(QSvgRenderer(svg.encode()).isValid())
        self.assertTrue(any(node.tag.endswith(("path", "rect", "circle", "ellipse", "polygon"))
                            for node in tree.iter()))
        self.assertFalse(any(node.tag.endswith(("filter", "script", "animate", "animateTransform", "image", "text"))
                             for node in tree.iter()))
        return tree

    def test_every_current_model_has_valid_cartoon_art_in_both_surface_inks(self):
        appearances = all_appearances()
        self.assertEqual(len(appearances), 178)
        self.assertEqual(Counter(row["kind"] for row in appearances), dict(cpu=3, gpu=147, memory=28))
        self.assertEqual(len({row["id"] for row in appearances}), len(appearances))
        for value in appearances:
            for ink in ("#303a48", "#e6eef5"):
                with self.subTest(model=value["id"], ink=ink):
                    data = self.drawing(dict(value, icon_set="cartoon"), ink)
                    fields = data["key"].split("|")
                    self.assertEqual(fields[10], "cartoon")
                    if value["kind"] == "cpu":
                        self.assertEqual(len(fields), 11)
                        self.assertEqual(fields[3], value["style"])
                    else:
                        self.assertEqual(fields[11:], [value["id"]])
                    self.valid_svg(data["source"])
                    self.valid_svg(data["layers"]["baseSource"])
                    for rotor in data["layers"]["rotors"]:
                        self.valid_svg(rotor["source"])
                    if value["kind"] != "gpu" or value.get("fan_count") == 0:
                        self.assertEqual(data["layers"]["rotors"], [])

    def test_cartoon_keeps_model_specific_fans_reversal_passive_and_unknown_identity(self):
        cases = {
            "asus-astral-5090": (3, [1, -1, 1]),
            "zotac-solo-4060": (1, [1]),
            "gigabyte-gt1030-silent-lp-2g": (0, []),
        }
        appearances = {row["id"]: row for row in all_appearances()}
        for identity, (count, directions) in cases.items():
            with self.subTest(model=identity):
                data = self.drawing(dict(appearances[identity], icon_set="cartoon"))
                self.assertEqual(len(data["layers"]["rotors"]), count)
                self.assertEqual([rotor["direction"] for rotor in data["layers"]["rotors"]], directions)
        unknown = dict(appearance_for("gpu", "NVIDIA GeForce RTX 5090"), icon_set="cartoon")
        data = self.drawing(unknown)
        self.assertNotEqual(unknown["confidence"], "model")
        self.assertEqual(len(data["key"].split("|")), 11)
        self.assertEqual(data["layers"]["rotors"], [])

    def test_cartoon_memory_preserves_reviewed_pcb_key_and_contact_opening(self):
        def pcb_geometry(tree):
            contours = [node.get("d") for node in tree.iter()
                        if node.tag.endswith("path") and "V11.2H" in node.get("d", "")
                        and "V12.2H" in node.get("d", "") and "Q" in node.get("d", "")]
            self.assertEqual(len(contours), 1)
            contacts = [(node.get("x"), node.get("width")) for node in tree.iter()
                        if node.tag.endswith("rect") and node.get("y") == "16.4"
                        and node.get("height") == "1.15"]
            self.assertEqual(len(contacts), 2)
            return contours, contacts

        for row in MEMORY_CATALOG:
            with self.subTest(model=row["id"]):
                value = appearance_for_memory(model=row["aliases"][0])
                original = self.valid_svg(self.drawing(dict(value, icon_set="solid"))["source"])
                cartoon = self.valid_svg(self.drawing(dict(value, icon_set="cartoon"))["source"])
                self.assertEqual(pcb_geometry(cartoon), pcb_geometry(original))

    def test_unknown_blades_keep_the_actual_metric_static(self):
        values = [row for row in all_appearances() if row["kind"] == "gpu"
                  and row.get("visible_fan_count") and not row.get("fan_profile", {}).get("render_ready")]
        self.assertTrue(values)
        icon = self.window.findChild(QObject, "cartoonMetric")
        for value in values:
            with self.subTest(model=value["id"]):
                self.window.setProperty("appearance", dict(value, icon_set="cartoon"))
                self.app.processEvents()
                self.assertFalse(icon.property("gpuFanCanAnimate"))
                self.assertFalse(icon.property("gpuFanMotionActive"))

    def test_wide_gpu_uses_the_same_frame_for_static_art_and_retained_circular_rotors(self):
        value = next(row for row in all_appearances() if row["id"] == "asus-astral-5090")
        self.window.setProperty("appearance", dict(value, icon_set="cartoon"))
        self.window.show()
        QTest.qWait(25)
        glyph = self.window.findChild(QObject, "cartoonWideGlyph")
        self.assertTrue(glyph.property("wideGpu"))
        self.assertAlmostEqual(glyph.property("artworkUnit"), 1.25)
        self.assertAlmostEqual(glyph.property("artworkLeft"), 0)
        self.assertAlmostEqual(glyph.property("artworkTop"), -4)
        self.assertTrue(glyph.property("fanMotionActive"))
        changes = QSignalSpy(glyph.svgSourceChanged)
        data = self.drawing(dict(value, icon_set="cartoon"))["layers"]["rotors"]
        for index, expected in enumerate(data):
            rotor = self.visual_item(glyph, "hardwareFanRotor_" + str(index))
            self.assertIsNotNone(rotor)
            self.assertAlmostEqual(rotor.property("width"), rotor.property("height"))
            self.assertGreaterEqual(rotor.property("x"), 0)
            self.assertGreaterEqual(rotor.property("y"), 0)
            self.assertLessEqual(rotor.property("x") + rotor.property("width"), 30)
            self.assertLessEqual(rotor.property("y") + rotor.property("height"), 22)
            self.assertAlmostEqual(rotor.property("x") + rotor.property("width") / 2, expected["cx"] * 1.25)
            self.assertAlmostEqual(rotor.property("y") + rotor.property("height") / 2, expected["cy"] * 1.25 - 4)
        glyph.setProperty("fanRotation", 180)
        self.app.processEvents()
        self.assertEqual(changes.count(), 0)

    def test_generic_hardware_and_quantity_symbols_remain_valid_and_distinct(self):
        names = ("disk", "disk_read", "disk_write", "network", "download", "upload", "battery", "fan",
                 "temperature", "power", "voltage", "frequency", "time", "noise", "memory", "grid", "sensors")
        sources = {}
        for name in names:
            for ink in ("#303a48", "#e6eef5"):
                with self.subTest(kind=name, ink=ink):
                    code = "generic(" + ",".join(json.dumps(value) for value in (name, ink, False)) + ")"
                    source = self.evaluate(code)
                    self.valid_svg(source)
                    sources[name] = source
        for pair in (("disk_read", "disk_write"), ("download", "upload"), ("temperature", "power"),
                     ("fan", "frequency"), ("memory", "disk")):
            self.assertNotEqual(sources[pair[0]], sources[pair[1]])

    def test_generic_cartoon_can_return_to_classic_without_hiding_the_metric(self):
        self.window.show()
        self.app.processEvents()
        icon = self.window.findChild(QObject, "cartoonGenericMetric")
        cartoon = self.visual_item(icon, "metricCartoonSymbol")
        classic = self.visual_item(icon, "metricIconGlyph")
        self.assertIsNotNone(cartoon)
        self.assertIsNotNone(classic)
        for name in ("disk", "network", "battery", "fan", "memory", "temperature", "power"):
            with self.subTest(kind=name):
                self.window.setProperty("genericName", name)
                icon.setProperty("iconStyle", "cartoon")
                self.app.processEvents()
                self.assertTrue(cartoon.isVisible())
                self.assertFalse(classic.isVisible())
                self.valid_svg(cartoon.property("source"))
                self.assertFalse(icon.property("animationRunning"))
                icon.setProperty("iconStyle", "classic")
                self.app.processEvents()
                self.assertFalse(cartoon.isVisible())
                self.assertTrue(classic.isVisible())


if __name__ == "__main__":
    unittest.main()
