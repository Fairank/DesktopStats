"""Retained GPU fan planes and the existing clock; synthetic offscreen Qt only."""

import base64
import copy
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

from PySide6.QtCore import QByteArray, Property, QCoreApplication, QEvent, QObject, QRectF, QUrl
from PySide6.QtGui import QImage, QPainter, QWindow
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtSvg import QSvgRenderer
from shiboken6 import getCppPointer

from hardware_appearance import appearance_for
from memory_appearance import appearance_for_memory
from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]
STYLES = ("solid", "miniature", "soft")
DUAL = "DUAL-RTX4060-O8G"


def appearance(model=DUAL, style="solid"):
    return dict(appearance_for("gpu", model), icon_set=style)


def processor_channels(*, load=.4, thermal=.5, energy=.2, rpm=1440,
                       semantics="measured", timestamp=None):
    return dict(profile="processor", available=True, load=load, thermal=thermal, energy=energy,
                fan_speed=dict(available=True, rpm=rpm, semantics=semantics, scope="card",
                               source="Synthetic card RPM", timestamp=time.time() if timestamp is None else timestamp,
                               display_slowdown=120))


def decode_source(source):
    value = source.toString() if isinstance(source, QUrl) else source
    header, body = value.split(",", 1)
    return base64.b64decode(body).decode() if ";base64" in header else unquote(body)


class HardwareFanMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native I/O")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(error.toString() for error in errors))
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
import "../native/HardwareShapes.js" as Shapes
import "../native/MetricEffectClock.js" as Clock
Window {
 id:scene; width:280; height:120; visible:false; color:"#edf1f5"
 property var appearance:({})
 property var channels:({profile:"processor",available:true,load:.4,thermal:.5,energy:.2})
 property var tempChannels:({profile:"processor",available:true,load:.3,thermal:.5,energy:.2})
 property bool motionAllowed:true
 property bool secondVisible:false
 property string secondGlyph:"gpu"
 property var secondChannels:channels
 property bool tempVisible:false
 property bool directMotion:false
 property real directRotation:0
 property string effect:"auto"
 property string glyph:"gpu"
 function layerData(value) { const key=Shapes.key(value,"#303a48"); return JSON.stringify({key:key,source:Shapes.source(key),layers:Shapes.layers(key)}) }
 function clockCount() { return Clock.activeWindowCount() }
 function subscribers() { return Clock.subscriberCount(scene.contentItem) }
 Product.MetricIcon {
  objectName:"fanMetric"; x:8;y:16;width:18;height:18
  name:scene.glyph;metric:scene.glyph==="gpu"?"gpu_usage":scene.glyph==="memory"?"ram_percent":"cpu_usage"
  hardwareAppearance:scene.appearance;hardwareState:scene.channels
  effect:scene.effect;level:.4;available:true;motionEnabled:scene.motionAllowed;ink:"#303a48"
 }
 Product.MetricIcon {
  objectName:"secondFanMetric"; x:40;y:16;width:18;height:18;visible:scene.secondVisible
  name:scene.secondGlyph;metric:scene.secondGlyph==="fan"?"gpu_fan_rpm":"gpu_usage";hardwareAppearance:scene.appearance;hardwareState:scene.secondChannels
  effect:scene.effect;level:.4;available:true;motionEnabled:scene.motionAllowed;ink:"#303a48"
 }
 Product.MetricIcon {
  objectName:"cpuThermometer";x:72;y:16;width:18;height:18;visible:scene.tempVisible
  name:"temperature";metric:"cpu_temp";hardwareAppearance:({kind:"cpu",style:"am5",icon_set:"solid"})
  hardwareState:scene.tempChannels;effect:"auto";available:true;motionEnabled:scene.motionAllowed;ink:"#303a48"
 }
 Product.HardwareGlyph {
  objectName:"directGlyph";x:108;y:16;width:64;height:64
  appearance:scene.appearance;ink:"#303a48"
  fanMotionEnabled:scene.directMotion;fanRotation:scene.directRotation
 }
 Product.HardwareGlyph {
  objectName:"staticControl";x:184;y:16;width:64;height:64
  appearance:scene.appearance;ink:"#303a48"
 }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareFanMotionFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.assign("appearance", appearance())
        self.assign("channels", processor_channels())
        self.window.show()
        QTest.qWait(25)
        self.stop_clock()

    def tearDown(self):
        if self.window is not None:
            self.window.hide()
            self.app.processEvents()
            self.assertEqual(self.evaluate(self.window, "clockCount()"), 0)
            self.window.destroy()
            self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def evaluate(self, item, source):
        expression = QQmlExpression(qmlContext(item), item, source)
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return value[0] if isinstance(value, tuple) else value

    def assign(self, name, value):
        self.evaluate(self.window, name + " = JSON.parse(" + json.dumps(json.dumps(value)) + ")")
        self.app.processEvents()

    @staticmethod
    def visual_items(parent):
        pending = [parent.contentItem() if isinstance(parent, QWindow) else parent]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(item.childItems())

    def find(self, name, parent=None, required=True):
        parent = self.window if parent is None else parent
        result = parent.findChild(QObject, name)
        if result is None:
            result = next((item for item in self.visual_items(parent) if item.objectName() == name), None)
        if required:
            self.assertIsNotNone(result, name)
        return result

    def stop_clock(self):
        clock = self.find("metricIconAnimation", required=False)
        if clock is not None:
            clock.stop()

    def layer_data(self, value):
        return json.loads(self.evaluate(self.window, "layerData(" + json.dumps(value) + ")"))

    def metric_glyph(self, icon=None):
        return self.find("metricHardwareGlyphLoader", icon or self.find("fanMetric")).property("item")

    def motion_loader(self, glyph):
        return self.find("hardwareFanMotionLoader", glyph)

    def rotors(self, glyph):
        return sorted((item for item in self.visual_items(glyph)
                       if item.objectName().startswith("hardwareFanRotor_")),
                      key=lambda item: int(item.objectName().rsplit("_", 1)[1]))

    def rotor_images(self, glyph):
        return [self.find("hardwareFanRotorImage_" + str(index), glyph)
                for index, _ in enumerate(self.rotors(glyph))]

    def static_layout(self, svg):
        root = ET.fromstring(svg)
        parents = {child: node for node in root.iter() for child in node}
        result = []
        for hub in root.iter():
            if hub.get("class") != "hardware-fan-hub":
                continue
            group = parents[hub]
            match = re.fullmatch(r"translate\(([^)]+)\)\s*scale\(([^)]+)\)", group.get("transform", ""))
            self.assertIsNotNone(match)
            cx, cy = [float(part) for part in re.split(r"[,\s]+", match.group(1).strip())]
            scales = [float(part) for part in re.split(r"[,\s]+", match.group(2).strip())]
            self.assertAlmostEqual(scales[0], scales[-1])
            radius = max(float(child.get("r")) for child in group if child.tag.endswith("circle")) * scales[0]
            kind = "blower" if group.get("class") == "hardware-blower" else "axial"
            result.append((cx, cy, radius, kind))
        return sorted(result)

    def test_layers_preserve_confirmed_front_planes_and_unequal_hybrid_fans(self):
        cases = (
            ("R5450-MD1GD3H/LP", 0),
            ("A380 CLI 6GO", 1),
            (DUAL, 2),
            ("TUF-RTX4070TIS-O16G-GAMING", 3),
            ("MSI GeForce RTX 4080 SUPER 16G EXPERT", 1),
            ("ROG-ASTRAL-RTX5080-O16G-GAMING", 3),
            ("APBF-IA770-16G-OC", 2),
            ("MSI Radeon RX 5700 XT 8G Reference", 1),
        )
        for style in STYLES:
            for model, count in cases:
                with self.subTest(style=style, model=model):
                    data = self.layer_data(appearance(model, style))
                    layers = data["layers"]
                    self.assertEqual(len(layers["rotors"]), count)
                    original = self.static_layout(decode_source(data["source"]))
                    projected = sorted((rotor["cx"], rotor["cy"], rotor["radius"], rotor["kind"])
                                       for rotor in layers["rotors"])
                    self.assertEqual(len(original), len(projected))
                    for before, after in zip(original, projected):
                        for left, right in zip(before[:3], after[:3]):
                            self.assertAlmostEqual(left, right, places=6)
                        self.assertEqual(before[3], after[3])
                    base = ET.fromstring(decode_source(layers["baseSource"]))
                    self.assertFalse(any(node.get("class") == "hardware-fan-hub" for node in base.iter()))
                    for rotor in layers["rotors"]:
                        tree = ET.fromstring(decode_source(rotor["source"]))
                        self.assertEqual(tree.get("viewBox"), "-3 -3 6 6")
                        self.assertEqual(sum(node.get("class") == "hardware-fan-hub" for node in tree.iter()), 1)
                        self.assertTrue(math.isfinite(rotor["radius"]) and rotor["radius"] > 0)
                    if model == "APBF-IA770-16G-OC":
                        self.assertEqual([rotor[3] for rotor in projected], ["blower", "axial"])
                        self.assertLess(projected[0][2], projected[1][2])
                    if "EXPERT" in model:
                        self.assertGreater(projected[0][0], 13)

    def test_unknown_passive_cpu_memory_classic_and_outline_have_no_rotors(self):
        values = [appearance("NVIDIA GeForce RTX 4090"), appearance("R5450-MD1GD3H/LP"),
                  dict(appearance_for("cpu", "AMD Ryzen 9 9950X"), icon_set="solid"),
                  dict(appearance_for_memory(model="CMK16GX4M2B3200C16"), icon_set="solid"),
                  appearance(style="classic"), appearance(style="outline")]
        self.window.setProperty("directMotion", True)
        glyph = self.find("directGlyph")
        for value in values:
            with self.subTest(kind=value["kind"], style=value["icon_set"], model=value["id"]):
                data = self.layer_data(value)
                self.assertEqual(data["layers"]["rotors"], [])
                self.assertEqual(data["layers"]["baseSource"], data["source"])
                self.assign("appearance", value)
                self.assertIsNone(self.motion_loader(glyph).property("item"))
                self.assertEqual(self.rotors(glyph), [])

    def test_default_static_image_survives_motion_toggle_without_source_changes(self):
        glyph = self.find("directGlyph")
        image = self.find("hardwareGlyphImage", glyph)
        pointer = getCppPointer(image)[0]
        self.assertFalse(glyph.property("fanMotionEnabled"))
        self.assertIsNone(self.motion_loader(glyph).property("item"))
        source, key = glyph.property("svgSource"), glyph.property("geometryKey")
        changed = QSignalSpy(glyph.svgSourceChanged)
        for enabled in (True, False, True, False):
            self.window.setProperty("directMotion", enabled)
            self.app.processEvents()
            self.assertEqual(getCppPointer(self.find("hardwareGlyphImage", glyph))[0], pointer)
            self.assertEqual(glyph.property("svgSource"), source)
            self.assertEqual(glyph.property("geometryKey"), key)
            self.assertTrue(image.isVisible())
            actual_source = self.evaluate(glyph, "fanMotionActive ? fanLayerData.baseSource : svgSource")
            self.assertEqual(image.property("source"), QUrl(actual_source))
            self.assertEqual(self.motion_loader(glyph).property("item") is not None, enabled)
        self.assertEqual(changed.count(), 0)

    def test_rotation_and_fresh_equal_maps_retain_all_sources_and_items(self):
        self.window.setProperty("directMotion", True)
        glyph = self.find("directGlyph")
        for style in STYLES:
            value = appearance("APBF-IA770-16G-OC", style)
            self.assign("appearance", value)
            rotors = self.rotors(glyph)
            self.assertEqual(len(rotors), 2)
            pointer = getCppPointer(self.motion_loader(glyph).property("item"))[0]
            rotor_pointers = [getCppPointer(rotor)[0] for rotor in rotors]
            images = self.rotor_images(glyph)
            sources = [image.property("source") for image in images]
            source = glyph.property("svgSource")
            key = glyph.property("geometryKey")
            changes = [QSignalSpy(image.sourceChanged) for image in images]
            glyph_changed = QSignalSpy(glyph.svgSourceChanged)
            base_changed = QSignalSpy(self.find("hardwareGlyphImage", glyph).sourceChanged)
            for rotation in (15, 72.5, 170, 280, 359):
                self.window.setProperty("directRotation", rotation)
                self.assign("appearance", dict(value))
                self.assertEqual(getCppPointer(self.motion_loader(glyph).property("item"))[0], pointer)
                self.assertEqual([getCppPointer(rotor)[0] for rotor in self.rotors(glyph)], rotor_pointers)
                self.assertEqual(glyph.property("svgSource"), source)
                self.assertEqual(glyph.property("geometryKey"), key)
                for image, original in zip(self.rotor_images(glyph), sources):
                    self.assertEqual(image.property("source"), original)
                for rotor in self.rotors(glyph):
                    self.assertAlmostEqual(rotor.property("rotation"), rotation)
            self.assertEqual(glyph_changed.count(), 0)
            self.assertEqual(base_changed.count(), 0)
            self.assertTrue(all(spy.count() == 0 for spy in changes))

    def test_zero_degree_layers_reconstruct_the_original_pixels(self):
        def raster(source=None, layers=None):
            image = QImage(128, 128, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(0)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            def draw(uri, rect):
                renderer = QSvgRenderer(QByteArray(decode_source(uri).encode()))
                self.assertTrue(renderer.isValid())
                renderer.render(painter, rect)

            draw(source if source else layers["baseSource"], QRectF(0, 0, 128, 128))
            if layers:
                for rotor in layers["rotors"]:
                    radius = rotor["radius"] * 128 / 24
                    painter.save()
                    painter.translate(rotor["cx"] * 128 / 24, rotor["cy"] * 128 / 24)
                    draw(rotor["source"], QRectF(-radius, -radius, 2 * radius, 2 * radius))
                    painter.restore()
            painter.end()
            return image

        for style in STYLES:
            for model in (DUAL, "MSI GeForce RTX 4080 SUPER 16G EXPERT", "APBF-IA770-16G-OC"):
                with self.subTest(style=style, model=model):
                    data = self.layer_data(appearance(model, style))
                    self.assertEqual(raster(source=data["source"]), raster(layers=data["layers"]))

    def test_rectangular_glyphs_letterbox_rotors_in_the_same_static_coordinate_system(self):
        glyph = self.find("directGlyph")
        self.window.setProperty("directMotion", True)
        self.assign("appearance", appearance("APBF-IA770-16G-OC"))
        data = self.layer_data(appearance("APBF-IA770-16G-OC"))["layers"]["rotors"]
        for width, height in ((64, 64), (96, 48), (48, 96)):
            glyph.setWidth(width)
            glyph.setHeight(height)
            self.app.processEvents()
            unit = min(width, height) / 24
            for rotor, expected in zip(self.rotors(glyph), data):
                self.assertAlmostEqual(rotor.x() + rotor.width() / 2, (width - unit*24)/2 + expected["cx"]*unit)
                self.assertAlmostEqual(rotor.y() + rotor.height() / 2, (height - unit*24)/2 + expected["cy"]*unit)
                self.assertAlmostEqual(rotor.width(), expected["radius"]*2*unit)
                self.assertAlmostEqual(rotor.height(), rotor.width())

    def test_standalone_glyph_guards_hidden_opacity_and_nonfinite_rotation_without_a_clock(self):
        glyph = self.find("directGlyph")
        self.window.setProperty("directMotion", True)
        self.app.processEvents()
        self.assertTrue(glyph.property("fanMotionActive"))
        self.assertEqual(self.evaluate(self.window, "subscribers()"), 1)
        for pause, resume in (
            (lambda: glyph.setVisible(False), lambda: glyph.setVisible(True)),
            (lambda: glyph.setOpacity(0), lambda: glyph.setOpacity(1)),
            (self.window.hide, self.window.show),
            (lambda: self.window.setVisibility(QWindow.Minimized), lambda: self.window.setVisibility(QWindow.Windowed)),
            (lambda: self.evaluate(self.window, "directRotation = NaN"), lambda: self.window.setProperty("directRotation", 45)),
            (lambda: self.evaluate(self.window, "directRotation = Infinity"), lambda: self.window.setProperty("directRotation", 90)),
        ):
            pause()
            self.app.processEvents()
            self.assertFalse(glyph.property("fanMotionActive"))
            self.assertIsNone(self.motion_loader(glyph).property("item"))
            self.assertEqual(self.find("hardwareGlyphImage", glyph).property("source"), glyph.property("svgSource"))
            resume()
            self.app.processEvents()
            self.stop_clock()
            self.assertTrue(glyph.property("fanMotionActive"))
            self.assertIsNotNone(self.motion_loader(glyph).property("item"))
            self.assertEqual(self.evaluate(self.window, "subscribers()"), 1)

    def test_gpu_rotors_reuse_one_background_clock_and_virtual_ticks(self):
        self.window.setProperty("secondVisible", True)
        self.app.processEvents()
        self.stop_clock()
        clock = self.find("metricEffectClock")
        clock_pointer = getCppPointer(clock)[0]
        self.assertEqual(self.evaluate(self.window, "clockCount()"), 1)
        self.assertEqual(self.evaluate(self.window, "subscribers()"), 2)
        self.assertFalse(clock.property("frameDriven"))
        self.assertEqual(self.find("metricIconAnimation").property("interval"), 34)
        self.assertEqual(self.find("metricEffectBackgroundDriver").property("interval"), 34)
        icons = [self.find("fanMetric"), self.find("secondFanMetric")]
        glyphs = [self.metric_glyph(icon) for icon in icons]
        self.assertTrue(all(self.motion_loader(glyph).property("item") is not None for glyph in glyphs))
        sources = [glyph.property("svgSource") for glyph in glyphs]
        phases = [icon.property("gpuFanPhase") for icon in icons]
        for icon in icons:
            self.evaluate(icon, "advanceClock(previousTick + 34)")
        for icon, previous, glyph, source in zip(icons, phases, glyphs, sources):
            self.assertNotEqual(icon.property("gpuFanPhase"), previous)
            self.assertNotEqual(self.rotors(glyph)[0].property("rotation"), 0)
            self.assertEqual(glyph.property("svgSource"), source)
        self.assertEqual(getCppPointer(self.find("metricEffectClock"))[0], clock_pointer)
        self.assertEqual(clock.property("subscriberCount"), 2)
        self.assertFalse(clock.property("frameDriven"))

    def test_measured_and_driver_rpm_use_fixed_120x_ratio_independent_of_load_and_speed(self):
        icon = self.find("fanMetric")
        glyph = self.metric_glyph()
        for semantics in ("measured", "driver_current_rpm"):
            for rpm in (1200, 2400):
                for load, speed in ((0, .5), (.2, 1), (1, 2)):
                    with self.subTest(semantics=semantics, rpm=rpm, load=load, speed=speed):
                        self.assign("channels", processor_channels(load=load, rpm=rpm, semantics=semantics))
                        icon.setProperty("speed", speed)
                        self.stop_clock()
                        icon.setProperty("gpuFanPhase", .2)
                        self.assertEqual(icon.property("gpuFanDisplaySlowdown"), 120)
                        self.assertEqual(icon.property("gpuFanRpm"), rpm)
                        self.assertTrue(icon.property("gpuFanMotionActive"))
                        self.evaluate(icon, "advanceClock(previousTick + 100)")
                        expected = .2 + 100 * rpm / (60000 * 120)
                        self.assertAlmostEqual(icon.property("gpuFanPhase"), expected)
                        self.assertAlmostEqual(self.rotors(glyph)[0].property("rotation"), expected * 360)

    def test_tuf_rdna2_counter_rotating_center_reaches_real_qml_transforms(self):
        icon = self.find("fanMetric")
        for style in STYLES:
            with self.subTest(style=style):
                value = appearance("TUF-RX6800XT-O16G-GAMING", style)
                self.assertEqual(value["id"], "asus-tuf-rx6800xt-o16g")
                self.assign("appearance", value)
                self.assign("channels", processor_channels())
                self.stop_clock()
                glyph = self.metric_glyph()
                self.assertTrue(icon.property("gpuFanMotionActive"))
                self.assertEqual([row["direction"] for row in self.layer_data(value)["layers"]["rotors"]],
                                 [1, -1, 1])
                icon.setProperty("gpuFanPhase", .25)
                self.app.processEvents()
                self.assertAlmostEqual(glyph.property("fanRotation"), 90)
                self.assertEqual([rotor.property("rotation") for rotor in self.rotors(glyph)],
                                 [90, 270, 90])

    def test_unknown_intended_percentage_stale_and_true_zero_keep_gpu_rotors_stationary(self):
        icon = self.find("fanMetric")
        glyph = self.metric_glyph()
        cases = [processor_channels(rpm=0), processor_channels(rpm=None),
                 processor_channels(semantics="intended"), processor_channels(semantics="percent"),
                 processor_channels(semantics="unknown"), processor_channels(timestamp=time.time()-4),
                 processor_channels(timestamp=time.time()+4)]
        unavailable = processor_channels()
        unavailable["fan_speed"]["available"] = False
        cases.append(unavailable)
        cases.append(dict(profile="processor", available=True, load=1, thermal=1, energy=1))
        for channels in cases:
            with self.subTest(sample=channels.get("fan_speed")):
                self.assign("channels", channels)
                self.stop_clock()
                icon.setProperty("gpuFanPhase", .31)
                self.assertFalse(icon.property("gpuFanMotionActive"))
                self.assertIsNone(self.motion_loader(glyph).property("item"))
                self.evaluate(icon, "advanceClock(previousTick + 100)")
                self.assertAlmostEqual(icon.property("gpuFanPhase"), .31)
                self.assertEqual(self.find("hardwareGlyphImage", glyph).property("source"), glyph.property("svgSource"))

    def test_selected_card_projection_never_animates_from_other_gpu_or_flat_chassis_rpm(self):
        from top_bar_feedback import hardware_feedback
        row = dict(gpu_usage=40, gpu_fan_rpm=2400, gpu_fan_rpm_timestamp=time.time(),
                   gpu_fan_rpm_source="Synthetic tachometer", gpu_fan_rpm_semantics="measured",
                   gpu_fan_rpm_scope="card")
        data = dict(gpu_fan_rpm=9000, gpu_fan_percent=100, gpus={"0": row, "1": dict(gpu_usage=40)})
        icon, glyph = self.find("fanMetric"), self.metric_glyph()
        self.assign("channels", hardware_feedback(data, "gpu_usage", dict(icon_effect="auto", gpu_target="1")))
        self.stop_clock()
        self.assertFalse(icon.property("gpuFanMotionActive"))
        self.assertIsNone(self.motion_loader(glyph).property("item"))
        self.assign("channels", hardware_feedback(data, "gpu_usage", dict(icon_effect="auto", gpu_target="0")))
        self.stop_clock()
        self.assertTrue(icon.property("gpuFanMotionActive"))
        self.assertEqual(icon.property("gpuFanRpm"), 2400)

    def test_hidden_minimized_off_and_reduced_motion_release_rotors_and_keep_phase(self):
        icon = self.find("fanMetric")
        glyph = self.metric_glyph()
        source = glyph.property("svgSource")
        pointer = getCppPointer(glyph)[0]
        pairs = (
            (self.window.hide, self.window.show),
            (lambda: self.window.setVisibility(QWindow.Minimized), lambda: self.window.setVisibility(QWindow.Windowed)),
            (lambda: self.window.setProperty("motionAllowed", False), lambda: self.window.setProperty("motionAllowed", True)),
            (lambda: self.window.setProperty("effect", "off"), lambda: self.window.setProperty("effect", "auto")),
            (lambda: self.assign("channels", dict(profile="processor", available=False, load=None, thermal=None)),
             lambda: self.assign("channels", processor_channels())),
        )
        for pause, resume in pairs:
            icon.setProperty("gpuFanPhase", .217)
            self.stop_clock()
            pause()
            self.app.processEvents()
            self.assertFalse(icon.property("animationRunning"))
            self.assertEqual(self.evaluate(self.window, "subscribers()"), 0)
            self.assertEqual(self.evaluate(self.window, "clockCount()"), 0)
            self.assertIsNone(self.motion_loader(glyph).property("item"))
            self.evaluate(icon, "advanceClock(previousTick + 1000)")
            self.assertAlmostEqual(icon.property("gpuFanPhase"), .217)
            resume()
            self.app.processEvents()
            self.stop_clock()
            self.assertEqual(getCppPointer(self.metric_glyph())[0], pointer)
            self.assertEqual(glyph.property("svgSource"), source)
            self.assertAlmostEqual(icon.property("gpuFanPhase"), .217)
            self.assertEqual(self.evaluate(self.window, "subscribers()"), 1)
            self.assertIsNotNone(self.motion_loader(glyph).property("item"))

    def test_gpu_keeps_background_cadence_when_a_chassis_fan_uses_rendered_frames(self):
        self.window.setProperty("secondGlyph", "fan")
        self.assign("secondChannels", dict(profile="fan", available=True, spin=.65))
        self.window.setProperty("secondVisible", True)
        self.app.processEvents()
        self.stop_clock()
        clock = self.find("metricEffectClock")
        gpu, fan = self.find("fanMetric"), self.find("secondFanMetric")
        self.assertTrue(clock.property("frameDriven"))
        self.assertEqual(clock.property("subscriberCount"), 2)
        gpu_changes, fan_changes = QSignalSpy(gpu.gpuFanPhaseChanged), QSignalSpy(fan.spinPhaseChanged)
        for _ in range(5):
            self.evaluate(clock, "step(8)")
        self.assertEqual(fan_changes.count(), 5)
        self.assertGreaterEqual(gpu_changes.count(), 1)
        self.assertLessEqual(gpu_changes.count(), 2)
        self.assertEqual(self.evaluate(self.window, "clockCount()"), 1)
        self.window.setProperty("secondVisible", False)
        self.app.processEvents()
        self.assertFalse(clock.property("frameDriven"))
        self.assertEqual(clock.property("subscriberCount"), 1)

    def test_manual_modes_do_not_drive_gpu_rotors_even_with_valid_card_rpm(self):
        self.assign("channels", processor_channels())
        icon = self.find("fanMetric")
        glyph = self.metric_glyph()
        for effect, expected in (("pulse", False), ("heat", False), ("flow", False), ("spin", False), ("off", False)):
            self.window.setProperty("effect", effect)
            self.app.processEvents()
            self.stop_clock()
            self.assertEqual(self.motion_loader(glyph).property("item") is not None, expected, effect)
        self.window.setProperty("effect", "auto")
        for kind, value in (("cpu", dict(appearance_for("cpu", "AMD Ryzen 9 9950X"), icon_set="solid")),
                            ("memory", dict(appearance_for_memory(model="CMK16GX4M2B3200C16"), icon_set="solid"))):
            self.window.setProperty("glyph", kind)
            self.assign("appearance", value)
            glyph = self.metric_glyph()
            self.assertFalse(icon.property("gpuFanMotionActive"))
            self.assertIsNone(self.motion_loader(glyph).property("item"))

    def test_live_channel_updates_do_not_rebuild_rotors_or_promote_missing_temperature(self):
        icon = self.find("fanMetric")
        glyph = self.metric_glyph()
        rotors = self.rotors(glyph)
        self.assertEqual(len(rotors), 2)
        pointers = [getCppPointer(rotor)[0] for rotor in rotors]
        sources = [image.property("source") for image in self.rotor_images(glyph)]
        source = glyph.property("svgSource")
        changed = QSignalSpy(glyph.svgSourceChanged)
        for load, thermal in ((.9, .2), (.1, .8), (.65, None), (.99, .3)):
            self.assign("channels", processor_channels(load=load, thermal=thermal, energy=.25))
            self.stop_clock()
            self.evaluate(icon, "advanceClock(previousTick + 34)")
            if thermal is None:
                self.assertIsNone(icon.property("thermalTarget"))
                self.assertEqual(icon.property("displayedThermal"), 0)
            else:
                self.assertAlmostEqual(icon.property("thermalTarget"), thermal)
            self.assertEqual(glyph.property("svgSource"), source)
            self.assertEqual([getCppPointer(rotor)[0] for rotor in self.rotors(glyph)], pointers)
            self.assertEqual([image.property("source") for image in self.rotor_images(glyph)], sources)
        self.assertEqual(changed.count(), 0)

    def test_real_cpu_temperature_projection_stays_independent_of_gpu_fan_phase(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate
        config = copy.deepcopy(DEFAULT)
        config["top_bar"]["hardware_icon_style"] = "solid"
        config["top_bar"]["items"] = [
            dict(id="b_temp", metric="cpu_temp", prefs=dict(style="icon_value", icon_effect="auto")),
            dict(id="b_gpu", metric="gpu_usage", prefs=dict(style="icon_value", icon_effect="auto")),
        ]
        with patch.object(controls, "load", return_value=validate(config)):
            controller = controls.Controller()
        self.addCleanup(controller.close)
        controller._data = dict(time=time.time(), cpu_name="AMD Ryzen 9 9950X", cpu_usage=30, cpu_temp=62.5,
                                gpus={"0": dict(gpu_name="NVIDIA GeForce RTX 4060", board_model=DUAL,
                                                board_vendor="ASUS", gpu_usage=40, gpu_temp=100, gpu_power=160,
                                                gpu_fan_rpm=1440, gpu_fan_rpm_timestamp=time.time(),
                                                gpu_fan_rpm_source="Synthetic tachometer",
                                                gpu_fan_rpm_semantics="measured", gpu_fan_rpm_scope="card")})
        temperature, gpu = controller.topBarRows()
        self.assertEqual(temperature["numeric_value"], 62.5)
        self.assertAlmostEqual(temperature["hardware_state"]["thermal"], .5)
        self.assign("tempChannels", temperature["hardware_state"])
        self.assign("appearance", gpu["hardware_appearance"])
        self.assign("channels", gpu["hardware_state"])
        self.window.setProperty("tempVisible", True)
        self.app.processEvents()
        self.stop_clock()
        thermometer, icon = self.find("cpuThermometer"), self.find("fanMetric")
        self.assertTrue(thermometer.property("thermometerEnabled"))
        self.assertFalse(thermometer.property("hasHardwareAppearance"))
        self.assertAlmostEqual(thermometer.property("thermometerTarget"), .5)
        for load in (.2, .9, .6):
            self.assign("channels", processor_channels(load=load, thermal=.95, energy=.7))
            self.evaluate(icon, "advanceClock(previousTick + 34)")
            self.assertAlmostEqual(thermometer.property("thermometerTarget"), .5)
        controller._data["cpu_temp"] = None
        missing = controller.topBarRows()[0]
        self.assign("tempChannels", missing["hardware_state"])
        self.assertFalse(thermometer.property("thermometerEnabled"))
        self.assertIsNone(thermometer.property("thermalTarget"))
        glyph = self.metric_glyph()
        self.assertIsNotNone(self.motion_loader(glyph).property("item"))

    def test_details_large_preview_follows_header_phase_without_another_subscription(self):
        class MotionDetailsState(fixture.ModuleState):
            motionEnabled = Property(bool, lambda self: True, constant=True)

        state = MotionDetailsState()
        state.details.update(family="gpu", metric="gpu_usage", icon="gpu", icon_effect="auto",
                             numeric_value=40, available=True, value="40 %", source="Synthetic provider",
                             hardware_name="Synthetic GPU", hardware_appearance=appearance(),
                             hardware_state=processor_channels())
        self.engine.rootContext().setContextProperty("stats", state)
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        details = component.createWithInitialProperties(dict(barState=state))
        self.assertIsNotNone(details, [error.toString() for error in component.errors()])
        try:
            details.show()
            QTest.qWait(20)
            self.find("metricIconAnimation", details).stop()
            headers = [item for item in self.visual_items(details)
                       if item.metaObject().indexOfProperty("gpuFanPhase") >= 0 and item.property("name") == "gpu"]
            self.assertEqual(len(headers), 1)
            header = headers[0]
            loader = self.find("topBarDetailAppearanceLoader", details)
            self.assertIsNone(loader.property("item"))
            self.assertEqual(self.evaluate(self.window, "clockCount()"), 2)
            details_clock = self.find("metricEffectClock", details)
            self.assertEqual(details_clock.property("subscriberCount"), 1)
            header.setProperty("gpuFanPhase", .133)
            details.setProperty("showMetadata", True)
            self.app.processEvents()
            large = loader.property("item")
            self.assertIsNotNone(large)
            self.assertEqual((large.width(), large.height()), (64, 64))
            self.assertTrue(large.property("fanMotionActive"))
            self.assertAlmostEqual(large.property("fanRotation"), .133*360)
            self.assertEqual(details_clock.property("subscriberCount"), 1)
            self.evaluate(header, "advanceClock(previousTick + 34)")
            self.assertAlmostEqual(large.property("fanRotation"), header.property("gpuFanPhase")*360)
            self.assertEqual(self.evaluate(self.window, "clockCount()"), 2)
            details.setProperty("hostMinimized", True)
            self.app.processEvents()
            self.assertIsNone(loader.property("item"))
            self.assertEqual(self.evaluate(self.window, "clockCount()"), 1)
        finally:
            details.hide()
            details.destroy()
            details.deleteLater()
            component.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()
            self.engine.rootContext().setContextProperty("stats", None)


if __name__ == "__main__":
    unittest.main()
