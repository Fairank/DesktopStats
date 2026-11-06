"""Optional hand-drawn hardware coverage and retained motion, without device I/O."""
from collections import Counter
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QObject, QRectF, QUrl
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QSignalSpy, QTest

from tests import test_hardware_cartoon as drawing_fixture

ROOT = Path(__file__).resolve().parents[1]


class HardwareSketchTests(unittest.TestCase):
    setUpClass = classmethod(drawing_fixture.HardwareCartoonTests.setUpClass.__func__)
    tearDown = drawing_fixture.HardwareCartoonTests.tearDown
    evaluate = drawing_fixture.HardwareCartoonTests.evaluate
    drawing = drawing_fixture.HardwareCartoonTests.drawing
    visual_item = drawing_fixture.HardwareCartoonTests.visual_item
    valid_svg = drawing_fixture.HardwareCartoonTests.valid_svg

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
import "../native/HardwareSketch.js" as Sketch
Window {
 id:scene; width:120; height:64; visible:false
 property var appearance:({})
 property string genericName:"disk"
 function artwork(value,ink) {
  const key=Shapes.key(value,ink)
  return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)})
 }
 function generic(name,ink,moving) { return Shapes.genericSource(name,ink,moving,"sketch") }
 Product.HardwareGlyph {
  objectName:"sketchWideGlyph";x:8;y:8;width:30;height:22
  appearance:scene.appearance;ink:"#303a48";fanMotionEnabled:true;fanRotation:90
 }
 Product.MetricIcon {
  objectName:"sketchMetric";x:52;y:8;width:30;height:22
  name:"gpu";metric:"gpu_usage";hardwareAppearance:scene.appearance
  effect:"auto";available:true;motionEnabled:true;intensity:1
  hardwareState:({profile:"processor",available:true,load:.4,thermal:.5,energy:.2,
   fan_speed:{available:true,rpm:1440,semantics:"measured",scope:"card",
    source:"Synthetic card RPM",timestamp:Date.now()/1000,display_slowdown:120}})
 }
 Product.MetricIcon {
  objectName:"sketchGenericMetric";x:92;y:8;width:22;height:22
  name:scene.genericName;iconStyle:"sketch";effect:"off";motionEnabled:false
  available:true;ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareSketchFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])

    def line_art(self, source):
        tree = self.valid_svg(source)
        self.assertTrue(any("hardware-sketch" in node.get("class", "").split() for node in tree.iter()))
        self.assertFalse(any(node.tag.endswith(("linearGradient", "radialGradient")) for node in tree.iter()))
        self.assertFalse(any("hardware-cartoon-expression" in node.get("class", "") for node in tree.iter()))
        self.assertTrue(any(node.get("stroke") not in (None, "none", "") for node in tree.iter()))
        return tree

    def test_every_current_model_has_valid_line_art_with_exact_identity_in_both_inks(self):
        appearances = drawing_fixture.all_appearances()
        self.assertEqual(len(appearances), 178)
        self.assertEqual(Counter(row["kind"] for row in appearances), dict(cpu=3, gpu=147, memory=28))
        for value in appearances:
            for ink in ("#303a48", "#e6eef5"):
                with self.subTest(model=value["id"], ink=ink):
                    result = self.drawing(dict(value, icon_set="sketch"), ink)
                    fields = result["key"].split("|")
                    self.assertEqual(fields[10], "sketch")
                    if value["kind"] == "cpu":
                        self.assertEqual(len(fields), 11)
                        self.assertEqual(fields[3], value["style"])
                    else:
                        self.assertEqual(fields[11:], [value["id"]])
                    self.line_art(result["source"])
                    self.line_art(result["layers"]["baseSource"])
                    for rotor in result["layers"]["rotors"]:
                        self.valid_svg(rotor["source"])
                    if value["kind"] != "gpu" or value.get("fan_count") == 0:
                        self.assertEqual(result["layers"]["rotors"], [])

    def test_reviewed_fan_leaf_contours_and_direction_are_preserved(self):
        def leaves(source):
            return [node.get("d") for node in ET.fromstring(drawing_fixture.decode(source)).iter()
                    if node.get("class") == "hardware-fan-blade"]

        values = drawing_fixture.all_appearances()
        checked = 0
        for value in values:
            if value["kind"] != "gpu":
                continue
            with self.subTest(model=value["id"]):
                original = self.drawing(dict(value, icon_set="solid"))["layers"]["rotors"]
                sketch = self.drawing(dict(value, icon_set="sketch"))["layers"]["rotors"]
                self.assertEqual(len(sketch), len(original))
                for old, new in zip(original, sketch):
                    self.assertEqual(new["direction"], old["direction"])
                    self.assertEqual(leaves(new["source"]), leaves(old["source"]))
                checked += len(sketch)
        self.assertGreater(checked, 100)
        astral = next(value for value in values if value["id"] == "asus-astral-5090")
        rotors = self.drawing(dict(astral, icon_set="sketch"))["layers"]["rotors"]
        self.assertEqual([row["direction"] for row in rotors], [1, -1, 1])

    def test_all_memory_keys_and_contact_openings_keep_reviewed_geometry(self):
        def pcb(tree):
            contours = [node.get("d") for node in tree.iter()
                        if node.tag.endswith("path") and "V11.2H" in node.get("d", "")
                        and "V12.2H" in node.get("d", "") and "Q" in node.get("d", "")]
            self.assertEqual(len(contours), 1)
            contacts = [(node.get("x"), node.get("width")) for node in tree.iter()
                        if node.tag.endswith("rect") and node.get("y") == "16.4"
                        and node.get("height") == "1.15"]
            self.assertEqual(len(contacts), 2)
            return contours, contacts

        for row in drawing_fixture.MEMORY_CATALOG:
            with self.subTest(model=row["id"]):
                value = drawing_fixture.appearance_for_memory(model=row["aliases"][0])
                original = self.valid_svg(self.drawing(dict(value, icon_set="solid"))["source"])
                sketch = self.line_art(self.drawing(dict(value, icon_set="sketch"))["source"])
                self.assertEqual(pcb(sketch), pcb(original))

    def test_unknown_coolers_and_unreviewed_blades_never_gain_guessed_motion(self):
        unknown = dict(drawing_fixture.appearance_for("gpu", "NVIDIA GeForce RTX 5090"), icon_set="sketch")
        result = self.drawing(unknown)
        self.assertNotEqual(unknown["confidence"], "model")
        self.assertEqual(len(result["key"].split("|")), 11)
        self.assertEqual(result["layers"]["rotors"], [])
        values = [row for row in drawing_fixture.all_appearances() if row["kind"] == "gpu"
                  and row.get("visible_fan_count") and not row.get("fan_profile", {}).get("render_ready")]
        self.assertTrue(values)
        icon = self.window.findChild(QObject, "sketchMetric")
        for value in values:
            with self.subTest(model=value["id"]):
                self.window.setProperty("appearance", dict(value, icon_set="sketch"))
                self.app.processEvents()
                self.assertFalse(icon.property("gpuFanCanAnimate"))
                self.assertFalse(icon.property("gpuFanMotionActive"))

    def test_passive_gt1030_keeps_its_main_heatsink_instead_of_only_the_pcb_strip(self):
        value = next(row for row in drawing_fixture.all_appearances()
                     if row["id"] == "gigabyte-gt1030-silent-lp-2g")
        self.assertEqual(value["fan_count"], 0)
        result = self.drawing(dict(value, icon_set="sketch"))
        self.assertEqual(result["layers"]["rotors"], [])
        tree = self.line_art(result["source"])
        self.assertFalse(any(node.get("class") == "hardware-fan-blade" for node in tree.iter()))
        main = [node for node in tree.iter() if node.get("class") == "hardware-sketch-passive"]
        self.assertEqual(len(main), 1)
        state = dict(value, model_id=value["id"], icon_set="sketch")
        geometry = json.loads(self.evaluate("JSON.stringify(Sketch.geometry(" + json.dumps(state) + "))"))
        # Isolate the actual fin stack so a tall bracket or connector cannot
        # make a missing heatsink appear to satisfy the silhouette test.
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
               + ET.tostring(main[0], encoding="unicode") + '</svg>')
        renderer = QSvgRenderer(svg.encode())
        self.assertTrue(renderer.isValid())
        size = 480
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        pixels = memoryview(image.constBits())
        stride = image.bytesPerLine()
        visible_rows = [y for y in range(size)
                        if any(alpha >= 32 for alpha in pixels[y * stride + 3:(y + 1) * stride:4])]
        self.assertTrue(visible_rows)
        height = (visible_rows[-1] - visible_rows[0] + 1) * 24 / size
        self.assertGreaterEqual(height, geometry["h"] * .75)

    def test_wide_fan_planes_are_circular_and_rotation_does_not_rebuild_art(self):
        value = next(row for row in drawing_fixture.all_appearances() if row["id"] == "asus-astral-5090")
        self.window.setProperty("appearance", dict(value, icon_set="sketch"))
        self.window.show()
        QTest.qWait(30)
        glyph = self.window.findChild(QObject, "sketchWideGlyph")
        self.assertTrue(glyph.property("wideGpu"))
        self.assertTrue(glyph.property("fanMotionActive"))
        changes = QSignalSpy(glyph.svgSourceChanged)
        for index in range(3):
            rotor = self.visual_item(glyph, "hardwareFanRotor_" + str(index))
            self.assertIsNotNone(rotor)
            self.assertAlmostEqual(rotor.width(), rotor.height())
            self.assertGreaterEqual(rotor.x(), 0)
            self.assertGreaterEqual(rotor.y(), 0)
            self.assertLessEqual(rotor.x() + rotor.width(), 30)
            self.assertLessEqual(rotor.y() + rotor.height(), 22)
        glyph.setProperty("fanRotation", 180)
        self.app.processEvents()
        self.assertEqual(changes.count(), 0)

    def test_hidden_static_and_reduced_effect_icons_have_no_active_clock(self):
        value = next(row for row in drawing_fixture.all_appearances() if row["id"] == "asus-astral-5090")
        self.window.setProperty("appearance", dict(value, icon_set="sketch"))
        icon = self.window.findChild(QObject, "sketchMetric")
        self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertTrue(self.evaluate("clockSubscription === null", icon))
        self.window.show()
        QTest.qWait(40)
        self.assertTrue(icon.property("gpuFanMotionActive"))
        self.assertTrue(self.evaluate("clockSubscription !== null && clockSubscription.active", icon))
        icon.setProperty("intensity", 0)
        self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertTrue(self.evaluate("clockSubscription === null", icon))
        icon.setProperty("intensity", 1)
        icon.setProperty("motionEnabled", False)
        self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertTrue(self.evaluate("clockSubscription === null", icon))
        icon.setProperty("motionEnabled", True)
        self.window.hide()
        self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertTrue(self.evaluate("clockSubscription === null", icon))

    def test_generic_quantities_are_distinct_line_art_and_can_return_to_classic(self):
        names = ("disk", "disk_read", "disk_write", "network", "download", "upload", "battery", "fan",
                 "temperature", "power", "voltage", "frequency", "time", "noise", "memory", "grid", "sensors")
        sources = {}
        for name in names:
            for ink in ("#303a48", "#e6eef5"):
                with self.subTest(kind=name, ink=ink):
                    result = self.evaluate("generic(" + ",".join(json.dumps(row) for row in (name, ink, False)) + ")")
                    self.line_art(result)
                    sources[name] = result
        for first, second in (("disk_read", "disk_write"), ("download", "upload"),
                              ("temperature", "power"), ("fan", "frequency"), ("memory", "disk")):
            self.assertNotEqual(sources[first], sources[second])
        self.window.show()
        self.app.processEvents()
        icon = self.window.findChild(QObject, "sketchGenericMetric")
        sketch = self.visual_item(icon, "metricCartoonSymbol")
        classic = self.visual_item(icon, "metricIconGlyph")
        self.assertIsNotNone(sketch)
        for name in ("disk", "network", "fan", "temperature", "power"):
            with self.subTest(kind=name):
                self.window.setProperty("genericName", name)
                icon.setProperty("iconStyle", "sketch")
                self.app.processEvents()
                self.assertTrue(sketch.isVisible())
                self.assertFalse(classic.isVisible())
                self.line_art(sketch.property("source"))
                self.assertFalse(icon.property("animationRunning"))
                icon.setProperty("iconStyle", "classic")
                self.app.processEvents()
                self.assertFalse(sketch.isVisible())
                self.assertTrue(classic.isVisible())


if __name__ == "__main__":
    unittest.main()
