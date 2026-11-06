"""Optional appearance schemes preserve the catalog, physical fans and retained clock."""

from collections import Counter
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import getCppPointer

from tests import test_hardware_cartoon as drawing_fixture
from tests import test_hardware_notebook as notebook_fixture

ROOT = Path(__file__).resolve().parents[1]
STYLES = ("sticker", "papercut", "inkwash")


def channels(rpm=1440, timestamp=None):
    return dict(profile="processor", available=True, load=0, thermal=None, energy=None,
                fan_speed=dict(available=True, rpm=rpm, semantics="measured", scope="card",
                               source="Synthetic card RPM", timestamp=time.time() if timestamp is None else timestamp,
                               display_slowdown=120))


class HardwareVariantsTests(unittest.TestCase):
    setUpClass = classmethod(drawing_fixture.HardwareCartoonTests.setUpClass.__func__)
    tearDown = drawing_fixture.HardwareCartoonTests.tearDown
    evaluate = drawing_fixture.HardwareCartoonTests.evaluate
    drawing = drawing_fixture.HardwareCartoonTests.drawing
    visual_item = drawing_fixture.HardwareCartoonTests.visual_item
    raster = notebook_fixture.HardwareNotebookTests.raster
    assert_transparent_fit = notebook_fixture.HardwareNotebookTests.assert_transparent_fit
    nodes = staticmethod(notebook_fixture.HardwareNotebookTests.nodes)

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
import "../native/MetricEffectClock.js" as Clock
Window {
 id:scene;width:100;height:60;visible:false
 property var appearance:({})
 property var channels:({})
 property string style:"sticker"
 function artwork(value,ink) {
  const key=Shapes.key(value,ink)
  return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)})
 }
 function generic(name,ink,moving) {return Shapes.genericSource(name,ink,moving,scene.style)}
 function source(key) {return Shapes.source(key)}
 function clockCount() {return Clock.activeWindowCount()}
 function subscribers() {return Clock.subscriberCount(scene.contentItem)}
 Product.MetricIcon {
  objectName:"variantMetric";x:8;y:8;width:30;height:22
  name:"gpu";metric:"gpu_usage";hardwareAppearance:scene.appearance;hardwareState:scene.channels
  effect:"auto";available:true;motionEnabled:true;intensity:.65;ink:"#303a48"
 }
 Product.MetricIcon {
  objectName:"variantGenericMetric";x:56;y:8;width:22;height:22
  name:"disk";iconStyle:scene.style;effect:"off";available:true;motionEnabled:false;ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareVariantsFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])

    def valid_svg(self, source):
        svg = drawing_fixture.decode(source)
        tree = ET.fromstring(svg)
        self.assertTrue(QSvgRenderer(svg.encode()).isValid())
        self.assertTrue(any(node.tag.endswith(("path", "rect", "circle", "ellipse", "polygon")) for node in tree.iter()))
        self.assertFalse(any(node.tag.endswith(("filter", "script", "image", "animate", "animateTransform", "clipPath"))
                             for node in tree.iter()))
        self.assertFalse(any(any(word in node.get("class", "") for word in ("smile", "expression"))
                             for node in tree.iter()))
        return tree

    def assign(self, name, value):
        self.evaluate(name + " = JSON.parse(" + json.dumps(json.dumps(value)) + ")")
        self.app.processEvents()

    def stop_clock(self):
        clock = self.window.findChild(QObject, "metricIconAnimation")
        if clock is not None:
            clock.stop()

    def metric_glyph(self):
        icon = self.window.findChild(QObject, "variantMetric")
        return self.visual_item(icon, "metricHardwareGlyphLoader").property("item")

    def test_all_three_schemes_keep_every_catalog_identity_and_transparent_bounds(self):
        values = drawing_fixture.all_appearances()
        self.assertEqual(len(values), 178)
        self.assertEqual(Counter(row["kind"] for row in values), dict(cpu=3, gpu=147, memory=28))
        for style in STYLES:
            for value in values:
                with self.subTest(style=style, model=value["id"]):
                    data = self.drawing(dict(value, icon_set=style))
                    self.assertEqual(data["key"].split("|")[10:], [style, value["id"]])
                    tree = self.valid_svg(data["source"])
                    self.assertTrue(self.nodes(tree, "hardware-variants"))
                    self.valid_svg(data["layers"]["baseSource"])
                    for rotor in data["layers"]["rotors"]:
                        self.valid_svg(rotor["source"])
                    self.assert_transparent_fit(self.raster(source=data["source"]), wide_gpu=value["kind"] == "gpu")

    def test_confirmed_fan_planes_blades_directions_and_links_remain_original(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances()}
        for style in STYLES:
            for identity in ("asus-astral-5090", "asus-dual-4060-oc", "msi-suprim-x-4090-24g", "zotac-solo-4060",
                             "asus-tuf-rx6800xt-o16g", "asrock-a380-challenger-itx-6g"):
                with self.subTest(style=style, model=identity):
                    original = self.drawing(dict(values[identity], icon_set="solid"))["layers"]["rotors"]
                    actual = self.drawing(dict(values[identity], icon_set=style))["layers"]["rotors"]
                    self.assertEqual(len(actual), len(original))
                    for before, after in zip(original, actual):
                        for field in ("cx", "cy", "radius", "kind", "direction"):
                            self.assertEqual(after[field], before[field])
                        old = ET.fromstring(drawing_fixture.decode(before["source"]))
                        new = self.valid_svg(after["source"])
                        self.assertEqual(len(self.nodes(new, "hardware-fan-blade")), len(self.nodes(old, "hardware-fan-blade")))
                        self.assertEqual(len(self.nodes(new, "hardware-fan-hub")), 1)
                        # Full source contours or their open hand-ink leading
                        # edges are both valid; all source-backed leaves remain.
                        before_links = sum("A2.55 2.55" in node.get("d", "") for node in old.iter())
                        after_links = sum("A2.55 2.55" in node.get("d", "") for node in new.iter())
                        self.assertEqual(after_links, before_links)
            for identity in ("intel-limited-arc-a770-16g", "acer-bifrost-a770-16g-oc"):
                with self.subTest(style=style, model=identity):
                    data = self.drawing(dict(values[identity], icon_set=style))
                    self.assertEqual(data["layers"]["rotors"], [])
                    tree = self.valid_svg(data["source"])
                    self.assertFalse(self.nodes(tree, "hardware-fan-blade"))
                    self.assertEqual(len(self.nodes(tree, "hardware-fan-hub")), 2)
            for value in (values["gigabyte-gt1030-silent-lp-2g"],
                          drawing_fixture.appearance_for("gpu", "R5450-MD1GD3H/LP")):
                self.assertEqual(value["confidence"], "model")
                data = self.drawing(dict(value, icon_set=style))
                self.assertEqual(data["layers"]["rotors"], [])
                self.assertFalse(self.nodes(self.valid_svg(data["source"]), "hardware-fan-hub"))

    def test_zero_degree_layers_reconstruct_each_scheme_without_pixel_changes(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances()}
        for style in STYLES:
            for identity in ("asus-astral-5090", "asus-dual-4060-oc", "msi-suprim-x-4090-24g",
                             "asus-tuf-rx6800xt-o16g", "asrock-a380-challenger-itx-6g",
                             "acer-bifrost-a770-16g-oc", "leadtek-hurricane-4090-24g", "gigabyte-gt1030-silent-lp-2g"):
                with self.subTest(style=style, model=identity):
                    data = self.drawing(dict(values[identity], icon_set=style))
                    self.assertEqual(self.raster(source=data["source"], size=128), self.raster(layers=data["layers"], size=128))

    def test_cpu_marks_are_guarded_and_all_memory_keys_stay_mechanical(self):
        values = drawing_fixture.all_appearances()
        for style in STYLES:
            for value in values:
                if value["kind"] not in ("cpu", "memory"):
                    continue
                with self.subTest(style=style, model=value["id"]):
                    tree = self.valid_svg(self.drawing(dict(value, icon_set=style))["source"])
                    if value["kind"] == "cpu":
                        marks = self.nodes(tree, "cpu-model-mark")
                        self.assertEqual(len(marks), 1)
                        expected = {"intel-13700kf": "13700KF", "amd-9950x": "9950X", "amd-7800x3d": "7800X3D"}[value["id"]]
                        self.assertIn(expected, "".join(marks[0].itertext()))
                        for mutation in (dict(id='<script/>'), dict(confidence="vendor"), dict(vendor="unknown")):
                            guarded = self.drawing(dict(value, icon_set=style, **mutation))
                            self.assertEqual(len(guarded["key"].split("|")), 11)
                            self.assertFalse(self.nodes(self.valid_svg(guarded["source"]), "cpu-model-mark"))
                    else:
                        original = ET.fromstring(drawing_fixture.decode(self.drawing(dict(value, icon_set="solid"))["source"]))
                        def pcb_paths(root):
                            return [node.get("d") for node in root.iter() if node.tag.endswith("path")
                                    and "V11.2H" in node.get("d", "") and "V12.2H" in node.get("d", "")]
                        self.assertEqual(pcb_paths(tree), pcb_paths(original))
                        self.assertEqual(len(pcb_paths(tree)), 1)

    def test_three_palettes_differ_and_keep_small_icons_readable_on_both_surfaces(self):
        values = {row["id"]: row for row in drawing_fixture.all_appearances()}
        representative = ("intel-13700kf", "amd-9950x", "asus-astral-5090", "asus-dual-4060-oc",
                          "intel-limited-arc-a770-16g", "gigabyte-gt1030-silent-lp-2g",
                          "corsair-cmk16gx4m2b3200c16", "gskill-f4-3600c18d-16gtrs", "kingston-kvr32s22s8-16")
        def luminance(rgb):
            channels = [channel / 255 for channel in rgb]
            linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4 for channel in channels]
            return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))
        for identity in representative:
            for ink, background in (("#303a48", (245, 247, 250)), ("#e6eef5", (23, 30, 38))):
                distinct = set()
                for style in STYLES:
                    with self.subTest(style=style, model=identity, ink=ink):
                        source = self.drawing(dict(values[identity], icon_set=style), ink)["source"]
                        self.valid_svg(source)
                        image = self.raster(source=source, size=30)
                        distinct.add(bytes(image.constBits()))
                        visible_contrast = 0
                        paper = luminance(background)
                        for y in range(4 if values[identity]["kind"] == "gpu" else 0,
                                       26 if values[identity]["kind"] == "gpu" else 30):
                            for x in range(30):
                                color = image.pixelColor(x, y)
                                alpha = color.alphaF()
                                if alpha < .2:
                                    continue
                                mixed = [round(channel * alpha + back * (1 - alpha))
                                         for channel, back in zip((color.red(), color.green(), color.blue()), background)]
                                value = luminance(mixed)
                                if (max(value, paper) + .05) / (min(value, paper) + .05) >= 1.8:
                                    visible_contrast += 1
                        self.assertGreaterEqual(visible_contrast, 12, "Too little legible hardware ink at bar size")
                self.assertEqual(len(distinct), 3, "Optional schemes render identically")

    def test_real_rpm_uses_one_clock_and_retains_sources_in_all_three_schemes(self):
        value = drawing_fixture.appearance_for("gpu", "ROG-ASTRAL-RTX5090-32G-GAMING")
        icon = self.window.findChild(QObject, "variantMetric")
        for style in STYLES:
            with self.subTest(style=style):
                self.assign("appearance", dict(value, icon_set=style))
                self.assign("channels", channels())
                self.window.show()
                QTest.qWait(20)
                self.stop_clock()
                glyph = self.metric_glyph()
                self.assertTrue(icon.property("gpuFanMotionActive"))
                self.assertTrue(glyph.property("wideGpu"))
                self.assertEqual(self.evaluate("clockCount()"), 1)
                self.assertEqual(self.evaluate("subscribers()"), 1)
                self.assertFalse(self.window.findChild(QObject, "metricEffectClock").property("frameDriven"))
                self.assertEqual(self.window.findChild(QObject, "metricIconAnimation").property("interval"), 34)
                source = glyph.property("svgSource")
                changed = QSignalSpy(glyph.svgSourceChanged)
                rotors = [self.visual_item(glyph, "hardwareFanRotor_" + str(index)) for index in range(3)]
                self.assertTrue(all(rotors))
                pointers = [getCppPointer(rotor)[0] for rotor in rotors]
                textures = [self.visual_item(glyph, "hardwareFanRotorImage_" + str(index)).property("source") for index in range(3)]
                for rpm in (1200, 2400):
                    self.assign("channels", channels(rpm))
                    self.stop_clock()
                    icon.setProperty("gpuFanPhase", .2)
                    self.evaluate("advanceClock(previousTick + 100)", icon)
                    phase = .2 + 100 * rpm / (60000 * 120)
                    self.assertAlmostEqual(icon.property("gpuFanPhase"), phase)
                    for rotor, direction in zip(rotors, (1, -1, 1)):
                        self.assertAlmostEqual(rotor.property("rotation"), (phase * 360 * direction) % 360)
                    self.assertEqual([getCppPointer(self.visual_item(glyph, "hardwareFanRotor_" + str(index)))[0] for index in range(3)], pointers)
                    self.assertEqual([self.visual_item(glyph, "hardwareFanRotorImage_" + str(index)).property("source") for index in range(3)], textures)
                for sample in (channels(0), channels(timestamp=time.time() - 4)):
                    self.assign("channels", sample)
                    self.stop_clock()
                    icon.setProperty("gpuFanPhase", .31)
                    self.assertFalse(icon.property("gpuFanMotionActive"))
                    self.evaluate("advanceClock(previousTick + 100)", icon)
                    self.assertAlmostEqual(icon.property("gpuFanPhase"), .31)
                    self.assertEqual(self.evaluate("clockCount()"), 0)
                self.assertEqual(changed.count(), 0)
                self.assign("channels", channels())
                self.stop_clock()
                self.window.hide()
                self.app.processEvents()
                self.assertEqual(self.evaluate("clockCount()"), 0)
                self.assertFalse(icon.property("gpuFanMotionActive"))
                self.assertEqual(glyph.property("svgSource"), source)
                self.assign("appearance", dict(drawing_fixture.appearance_for("gpu", "APBF-IA770-16G-OC"), icon_set=style))
                self.window.show()
                self.app.processEvents()
                self.assertFalse(icon.property("gpuFanCanAnimate"))
                self.assertEqual(self.evaluate("clockCount()"), 0)

    def test_generic_symbols_and_public_svg_inputs_keep_safe_semantics(self):
        names = ("disk", "disk_read", "disk_write", "network", "download", "upload", "battery", "fan",
                 "temperature", "power", "voltage", "frequency", "time", "noise", "memory", "grid", "sensors")
        for style in STYLES:
            self.window.setProperty("style", style)
            sources = {}
            for name in names:
                source = self.evaluate("generic(" + ",".join(json.dumps(value) for value in (name, "#303a48", False)) + ")")
                self.valid_svg(source)
                sources[name] = source
            for first, second in (("disk_read", "disk_write"), ("download", "upload"), ("memory", "disk"), ("temperature", "power")):
                self.assertNotEqual(sources[first], sources[second])
            self.window.show()
            self.app.processEvents()
            generic = self.window.findChild(QObject, "variantGenericMetric")
            self.assertTrue(self.visual_item(generic, "metricCartoonSymbol").isVisible())
        for malicious in ('sticker\"><script/>', 'papercut\" onload=\"bad', 'inkwash\"><image/>'):
            self.window.setProperty("style", malicious)
            svg = drawing_fixture.decode(self.evaluate('generic("gpu", "#303a48", false)'))
            tree = ET.fromstring(svg)
            self.assertFalse(any(node.tag.endswith(("script", "image")) for node in tree.iter()))
            self.assertNotIn("onload", svg)


if __name__ == "__main__":
    unittest.main()
