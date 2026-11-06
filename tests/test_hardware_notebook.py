"""Notebook hardware drawings, guarded identities and retained motion; no device I/O."""

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
from shiboken6 import getCppPointer

from tests import test_hardware_cartoon as drawing_fixture
from top_bar_config import HARDWARE_ICON_STYLES

ROOT = Path(__file__).resolve().parents[1]
STYLES = ("notebook_line", "notebook_color", "notebook_smile")


class HardwareNotebookTests(unittest.TestCase):
    setUpClass = classmethod(drawing_fixture.HardwareCartoonTests.setUpClass.__func__)
    tearDown = drawing_fixture.HardwareCartoonTests.tearDown
    evaluate = drawing_fixture.HardwareCartoonTests.evaluate
    drawing = drawing_fixture.HardwareCartoonTests.drawing
    visual_item = drawing_fixture.HardwareCartoonTests.visual_item

    def test_original_is_the_pre_smiley_miniature_and_cute_remains_separate(self):
        self.assertEqual(HARDWARE_ICON_STYLES[:4],
                         ("miniature", "cartoon", "notebook_color", "notebook_line"))
        for value in drawing_fixture.all_appearances():
            with self.subTest(model=value["id"]):
                svg = drawing_fixture.decode(self.drawing(dict(value, icon_set="miniature"))["source"])
                self.assertTrue(QSvgRenderer(svg.encode()).isValid())
                original = ET.fromstring(svg)
                expressions = [node for node in original.iter()
                               if any(word in node.get("class", "") for word in ("expression", "smile"))]
                self.assertEqual(expressions, [])
                if value["kind"] == "cpu":
                    cute = ET.fromstring(drawing_fixture.decode(
                        self.drawing(dict(value, icon_set="cartoon"))["source"]))
                    self.assertTrue(self.nodes(cute, "hardware-cartoon-expression"))

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
 id:scene; width:120; height:64; visible:false
 property var appearance:({})
 property string style:"notebook_line"
 property string genericName:"disk"
 function artwork(value,ink) {
  const key=Shapes.key(value,ink)
  return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)})
 }
 function generic(name,ink,moving) { return Shapes.genericSource(name,ink,moving,scene.style) }
 function canonicalSource(key) { return Shapes.source(key) }
 Product.HardwareGlyph {
  objectName:"notebookWideGlyph";x:8;y:8;width:30;height:22
  appearance:scene.appearance;ink:"#303a48";fanMotionEnabled:true;fanRotation:0
 }
 Product.MetricIcon {
  objectName:"notebookMetric";x:52;y:8;width:30;height:22
  name:"gpu";metric:"gpu_usage";hardwareAppearance:scene.appearance
  effect:"auto";available:true;motionEnabled:true;intensity:1
  hardwareState:({profile:"processor",available:true,load:.4,thermal:.5,energy:.2,
   fan_speed:{available:true,rpm:1440,semantics:"measured",scope:"card",
    source:"Synthetic card RPM",timestamp:Date.now()/1000,display_slowdown:120}})
 }
 Product.MetricIcon {
  objectName:"notebookGenericMetric";x:92;y:8;width:22;height:22
  name:scene.genericName;iconStyle:scene.style;effect:"off";motionEnabled:false
  available:true;ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareNotebookFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])

    def valid_svg(self, source):
        svg = drawing_fixture.decode(source)
        tree = ET.fromstring(svg)
        self.assertTrue(QSvgRenderer(svg.encode()).isValid())
        self.assertTrue(any(node.tag.endswith(("path", "rect", "circle", "ellipse", "polygon"))
                            for node in tree.iter()))
        self.assertFalse(any(node.tag.endswith(("filter", "script", "animate", "animateTransform", "image",
                                               "linearGradient", "radialGradient", "clipPath")) for node in tree.iter()))
        return tree

    @staticmethod
    def nodes(tree, name):
        return [node for node in tree.iter() if name in node.get("class", "").split()]

    def raster(self, source=None, layers=None, size=96):
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        def draw(uri, rect):
            renderer = QSvgRenderer(drawing_fixture.decode(uri).encode())
            self.assertTrue(renderer.isValid())
            renderer.render(painter, rect)

        draw(source if source else layers["baseSource"], QRectF(0, 0, size, size))
        if layers:
            for rotor in layers["rotors"]:
                radius = rotor["radius"] * size / 24
                painter.save()
                painter.translate(rotor["cx"] * size / 24, rotor["cy"] * size / 24)
                draw(rotor["source"], QRectF(-radius, -radius, 2 * radius, 2 * radius))
                painter.restore()
        painter.end()
        return image

    def assert_transparent_fit(self, image, *, wide_gpu=False):
        size, stride = image.width(), image.bytesPerLine()
        pixels = memoryview(image.constBits())
        alpha = pixels[3::4]
        self.assertTrue(any(value >= 32 for value in alpha), "Empty notebook icon")
        self.assertFalse(any(pixels[3:stride:4]), "Top edge is clipped or painted")
        self.assertFalse(any(pixels[(size - 1) * stride + 3:size * stride:4]), "Bottom edge is clipped or painted")
        self.assertFalse(any(pixels[3::stride]), "Left edge is clipped or painted")
        self.assertFalse(any(pixels[(size - 1) * 4 + 3::stride]), "Right edge is clipped or painted")
        if wide_gpu:
            # A 30x22 bar glyph crops the same square source to y=3.2..20.8.
            # Strong casing/fan ink must survive that existing retained view.
            margin = int(size * 3.2 / 24)
            self.assertFalse(any(value >= 32 for value in pixels[3:margin * stride:4]))
            self.assertFalse(any(value >= 32 for value in pixels[(size - margin) * stride + 3::4]))

    def test_all_registered_models_have_transparent_bounded_art_in_all_notebook_styles(self):
        values = drawing_fixture.all_appearances()
        counts = Counter(row["kind"] for row in values)
        self.assertEqual(counts["gpu"], 147)
        self.assertEqual(counts["memory"], 28)
        self.assertIn(counts["cpu"], (3, 4))
        self.assertEqual(len({row["id"] for row in values}), len(values))
        for style in STYLES:
            for value in values:
                for ink in ("#303a48", "#e6eef5"):
                    with self.subTest(style=style, model=value["id"], ink=ink):
                        data = self.drawing(dict(value, icon_set=style), ink)
                        self.assertEqual(data["key"].split("|")[10:], [style, value["id"]])
                        tree = self.valid_svg(data["source"])
                        self.assertTrue(self.nodes(tree, "hardware-notebook"))
                        if style != "notebook_smile":
                            self.assertFalse(self.nodes(tree, "hardware-notebook-expression"))
                        self.valid_svg(data["layers"]["baseSource"])
                        for rotor in data["layers"]["rotors"]:
                            self.valid_svg(rotor["source"])
                        self.assert_transparent_fit(self.raster(source=data["source"]),
                                                    wide_gpu=value["kind"] == "gpu")

    def test_known_blades_keep_counts_tip_links_directions_and_confirmed_planes(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances()}
        for style in STYLES:
            for identity in ("asus-astral-5090", "asus-dual-4060-oc", "msi-suprim-x-4090-24g",
                             "zotac-solo-4060"):
                with self.subTest(style=style, model=identity):
                    value = values[identity]
                    before = self.drawing(dict(value, icon_set="solid"))["layers"]["rotors"]
                    after = self.drawing(dict(value, icon_set=style))["layers"]["rotors"]
                    self.assertEqual(len(before), len(after))
                    for old, new in zip(before, after):
                        for field in ("cx", "cy", "radius", "kind", "direction"):
                            self.assertEqual(old[field], new[field])
                        old_tree = ET.fromstring(drawing_fixture.decode(old["source"]))
                        new_tree = self.valid_svg(new["source"])
                        self.assertEqual(len(self.nodes(new_tree, "hardware-fan-blade")),
                                         len(self.nodes(old_tree, "hardware-fan-blade")))
                        self.assertEqual(len(self.nodes(new_tree, "hardware-fan-hub")), 1)
                        for blade in self.nodes(new_tree, "hardware-fan-blade"):
                            self.assertNotIn("Z", blade.get("d", "").upper())
                            self.assertEqual(blade.get("data-contour"), "open-source-leading-edge-and-tip")
                    if identity == "asus-astral-5090":
                        self.assertEqual([row["direction"] for row in after], [1, -1, 1])
                    if identity == "msi-suprim-x-4090-24g":
                        self.assertEqual(sum(len(self.nodes(self.valid_svg(row["source"]),
                                                            "hardware-fan-tip-link")) for row in after), 9)
        mixed = drawing_fixture.appearance_for("gpu", "APBF-IA770-16G-OC")
        for style in STYLES:
            data = self.drawing(dict(mixed, icon_set=style))
            self.assertEqual(data["layers"]["rotors"], [])
            openings = self.nodes(self.valid_svg(data["source"]), "hardware-notebook-fan-opening")
            planes = self.drawing(dict(mixed, icon_set="solid"))["layers"]["rotors"]
            self.assertEqual([row["kind"] for row in planes], ["blower", "axial"])
            self.assertEqual(len(openings), 2)
            for opening, plane in zip(openings, planes):
                for attribute, field in (("cx", "cx"), ("cy", "cy"), ("r", "radius")):
                    self.assertAlmostEqual(float(opening.get(attribute)), plane[field], places=4)
            self.assertLess(float(openings[0].get("r")), float(openings[1].get("r")))

    def test_unknown_blades_and_unreviewed_model_keys_stay_static(self):
        unknown = drawing_fixture.appearance_for("gpu", "NVIDIA GeForce RTX 5090")
        values = [row for row in drawing_fixture.all_appearances() if row["kind"] == "gpu"
                  and row.get("visible_fan_count") and not row.get("fan_profile", {}).get("render_ready")]
        self.assertTrue(values)
        for style in STYLES:
            fallback = self.drawing(dict(unknown, icon_set=style))
            self.assertEqual(len(fallback["key"].split("|")), 11)
            self.assertEqual(fallback["layers"]["rotors"], [])
            for value in values:
                with self.subTest(style=style, model=value["id"]):
                    data = self.drawing(dict(value, icon_set=style))
                    profile = value.get("fan_profile", {})
                    if profile.get("blades") is None and not any(profile.get("blade_counts", [])):
                        self.assertEqual(data["layers"]["rotors"], [])
                        self.assertFalse(self.nodes(self.valid_svg(data["source"]), "hardware-fan-blade"))
                    # A neutral/unreviewed cooler makes no assertion about
                    # physical openings even if a driver supplied a fan count.
                    if value["style"] != "gpu_neutral":
                        self.assertTrue(self.nodes(self.valid_svg(data["source"]), "hardware-notebook-fan-opening"))
                    self.window.setProperty("appearance", dict(value, icon_set=style))
                    self.app.processEvents()
                    icon = self.window.findChild(QObject, "notebookMetric")
                    self.assertFalse(icon.property("gpuFanCanAnimate"))

    def test_cpu_model_marks_are_allowlisted_and_packages_remain_real(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances() if row["kind"] == "cpu"}
        self.assertTrue({"intel-13700kf", "amd-9950x", "amd-7800x3d"} <= values.keys())
        for style in STYLES:
            trees = {identity: self.valid_svg(self.drawing(dict(value, icon_set=style))["source"])
                     for identity, value in values.items()}
            lid_a = self.nodes(trees["amd-9950x"], "cpu-lid-outline")
            lid_b = self.nodes(trees["amd-7800x3d"], "cpu-lid-outline")
            self.assertEqual(len(lid_a), 1)
            self.assertEqual([node.get("d") for node in lid_a], [node.get("d") for node in lid_b])
            self.assertNotEqual(["".join(node.itertext()) for node in self.nodes(trees["amd-9950x"], "cpu-model-mark")],
                                ["".join(node.itertext()) for node in self.nodes(trees["amd-7800x3d"], "cpu-model-mark")])
            self.assertEqual(len(self.nodes(trees["intel-13700kf"], "cpu-package-outline")), 1)
            for mutation in (dict(id='<script>alert(1)</script>'), dict(confidence="vendor"),
                             dict(style="am5"), dict(id="amd-9950x"), dict(vendor="amd")):
                value = dict(values["intel-13700kf"], icon_set=style, **mutation)
                result = self.drawing(value)
                self.assertEqual(len(result["key"].split("|")), 11)
                tree = self.valid_svg(result["source"])
                self.assertFalse(self.nodes(tree, "cpu-model-mark"))
                self.assertNotIn("alert", drawing_fixture.decode(result["source"]))

    def test_memory_keeps_reviewed_pcb_keys_and_distinct_spreader_shapes(self):
        values = [row for row in drawing_fixture.all_appearances() if row["kind"] == "memory"]
        shapes = {}
        for style in STYLES:
            for value in values:
                with self.subTest(style=style, model=value["id"]):
                    original = self.valid_svg(self.drawing(dict(value, icon_set="solid"))["source"])
                    original_pcb = [node.get("d") for node in original.iter()
                                    if node.tag.endswith("path") and "V11.2H" in node.get("d", "")
                                    and "V12.2H" in node.get("d", "")]
                    tree = self.valid_svg(self.drawing(dict(value, icon_set=style))["source"])
                    actual_pcb = self.nodes(tree, "notebook-memory-pcb")
                    self.assertEqual([node.get("d") for node in actual_pcb], original_pcb)
                    self.assertEqual(len(self.nodes(tree, "notebook-memory-contacts")), 1)
                    self.assertTrue(self.nodes(tree, "notebook-memory-enclosure"))
                    self.assertEqual(self.nodes(tree, "hardware-notebook-memory")[0].get("data-form"), value["style"])
                    shapes[value["id"]] = [node.get("d") for node in self.nodes(tree, "notebook-memory-enclosure")]
        self.assertNotEqual(shapes["corsair-cmk16gx4m2b3200c16"], shapes["corsair-cmt32gx5m2b5600c36"])
        self.assertNotEqual(shapes["gskill-f4-3600c18d-16gtrs"], shapes["kingston-kvr32s22s8-16"])

    def test_zero_degree_layers_reconstruct_the_static_notebook_pixels(self):
        for style in STYLES:
            for model in ("DUAL-RTX4060-O8G", "MSI GeForce RTX 4080 SUPER 16G EXPERT",
                          "APBF-IA770-16G-OC", "ROG-ASTRAL-RTX5090-32G-GAMING"):
                with self.subTest(style=style, model=model):
                    value = drawing_fixture.appearance_for("gpu", model)
                    self.assertEqual(value["confidence"], "model")
                    data = self.drawing(dict(value, icon_set=style))
                    self.assertEqual(self.raster(source=data["source"], size=128),
                                     self.raster(layers=data["layers"], size=128))

    def test_pencil_stays_out_of_real_fan_openings_without_svg_clipping(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances()}
        size = 144
        for style in ("notebook_color", "notebook_smile"):
            for identity in ("asus-astral-5090", "asus-dual-4060-oc", "msi-suprim-x-4090-24g",
                             "intel-limited-arc-a770-16g", "acer-bifrost-a770-16g-oc"):
                with self.subTest(style=style, model=identity):
                    tree = self.valid_svg(self.drawing(dict(values[identity], icon_set=style))["source"])
                    pencil = self.nodes(tree, "hardware-notebook-pencil")
                    self.assertEqual(len(pencil), 1)
                    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                           + ET.tostring(pencil[0], encoding="unicode") + '</svg>')
                    image = self.raster(source="data:image/svg+xml;utf8," + svg, size=size)
                    pixels, stride = memoryview(image.constBits()), image.bytesPerLine()
                    self.assertTrue(any(pixels[3::4]), "Colored notebook style lost every pencil stroke")
                    for opening in self.nodes(tree, "hardware-notebook-fan-opening"):
                        cx, cy, radius = (float(opening.get(field)) for field in ("cx", "cy", "r"))
                        for y in range(size):
                            for x in range(size):
                                if ((x + .5) * 24 / size - cx) ** 2 + ((y + .5) * 24 / size - cy) ** 2 < (radius - .08) ** 2:
                                    self.assertEqual(pixels[y * stride + x * 4 + 3], 0)

    def test_rotation_retains_sources_and_items_on_the_existing_clock(self):
        value = drawing_fixture.appearance_for("gpu", "ROG-ASTRAL-RTX5090-32G-GAMING")
        glyph = self.window.findChild(QObject, "notebookWideGlyph")
        icon = self.window.findChild(QObject, "notebookMetric")
        for style in STYLES:
            self.window.setProperty("appearance", dict(value, icon_set=style))
            self.app.processEvents()
            self.assertFalse(icon.property("animationRunning"))
            self.assertTrue(self.evaluate("clockSubscription === null", icon))
            self.window.show()
            QTest.qWait(35)
            self.assertTrue(glyph.property("wideGpu"))
            self.assertTrue(glyph.property("fanMotionActive"))
            self.assertTrue(icon.property("gpuFanMotionActive"))
            self.assertTrue(self.evaluate("clockSubscription !== null && clockSubscription.active", icon))
            source_changes = QSignalSpy(glyph.svgSourceChanged)
            source = glyph.property("svgSource")
            rotors = [self.visual_item(glyph, "hardwareFanRotor_" + str(index)) for index in range(3)]
            pointers = [getCppPointer(rotor)[0] for rotor in rotors]
            sources = [self.visual_item(glyph, "hardwareFanRotorImage_" + str(index)).property("source")
                       for index in range(3)]
            for angle in (90, 215, 359):
                glyph.setProperty("fanRotation", angle)
                self.app.processEvents()
                self.assertEqual(glyph.property("svgSource"), source)
                self.assertEqual([getCppPointer(self.visual_item(glyph, "hardwareFanRotor_" + str(index)))[0]
                                  for index in range(3)], pointers)
                self.assertEqual([self.visual_item(glyph, "hardwareFanRotorImage_" + str(index)).property("source")
                                  for index in range(3)], sources)
            self.assertEqual(source_changes.count(), 0)
            for rotor in rotors:
                self.assertAlmostEqual(rotor.width(), rotor.height())
                self.assertGreaterEqual(rotor.y(), 0)
                self.assertLessEqual(rotor.y() + rotor.height(), 22)
            self.window.hide()
            self.app.processEvents()
            self.assertFalse(icon.property("animationRunning"))
            self.assertTrue(self.evaluate("clockSubscription === null", icon))

    def test_generic_quantities_have_transparent_semantic_symbols_and_preserve_switching(self):
        names = ("disk", "disk_read", "disk_write", "network", "download", "upload", "battery", "fan",
                 "temperature", "power", "voltage", "frequency", "time", "noise", "memory", "grid", "sensors")
        for style in STYLES:
            self.window.setProperty("style", style)
            sources = {}
            for name in names:
                with self.subTest(style=style, name=name):
                    source = self.evaluate("generic(" + ",".join(json.dumps(row) for row in (name, "#303a48", False)) + ")")
                    tree = self.valid_svg(source)
                    self.assertTrue(self.nodes(tree, "hardware-notebook"))
                    if style != "notebook_smile":
                        self.assertFalse(self.nodes(tree, "hardware-notebook-expression"))
                    self.assert_transparent_fit(self.raster(source=source))
                    sources[name] = source
            for first, second in (("disk_read", "disk_write"), ("download", "upload"),
                                  ("temperature", "power"), ("fan", "frequency"), ("memory", "disk")):
                self.assertNotEqual(sources[first], sources[second])
        icon = self.window.findChild(QObject, "notebookGenericMetric")
        self.window.show()
        self.app.processEvents()
        self.assertTrue(self.visual_item(icon, "metricCartoonSymbol").isVisible())
        self.window.setProperty("style", "classic")
        self.app.processEvents()
        self.assertTrue(self.visual_item(icon, "metricIconGlyph").isVisible())
        self.assertFalse(self.visual_item(icon, "metricCartoonSymbol").isVisible())

    def test_public_svg_inputs_cannot_inject_names_or_styles(self):
        value = drawing_fixture.appearance_for("gpu", "DUAL-RTX4060-O8G")
        for style in STYLES:
            artwork = self.drawing(dict(value, icon_set=style))
            fields = artwork["key"].split("|")
            for index, payload in ((7, '#fff\"><script/>'), (10, 'notebook_\"><script/>'),
                                   (11, 'unreviewed\"><script/>')):
                malformed = fields.copy()
                malformed[index] = payload
                source = self.evaluate("canonicalSource(" + json.dumps("|".join(malformed)) + ")")
                tree = ET.fromstring(drawing_fixture.decode(source))
                self.assertFalse(any(node.tag.endswith("script") for node in tree.iter()))
        for style in ('notebook_\"><script/>', 'notebook_unknown', 'notebook_line" onload="bad'):
            self.window.setProperty("style", style)
            source = self.evaluate('generic("gpu", "#303a48", false)')
            svg = drawing_fixture.decode(source)
            tree = ET.fromstring(svg)
            self.assertFalse(any(node.tag.endswith("script") for node in tree.iter()))
            self.assertNotIn("onload", svg)


if __name__ == "__main__":
    unittest.main()
