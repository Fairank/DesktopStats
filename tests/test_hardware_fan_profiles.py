"""Reviewed exact-board fan studies and actual SVG rotors; no hardware or windows."""
import base64
import json
import math
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtSvg import QSvgRenderer

import hardware_appearance as hardware
from hardware_fan_profiles import GROUP_A, GROUP_B, PROFILES, profile_for
from hardware_variants import base_identity
from hardware_series import SERIES_CATALOG
from tools.generate_hardware_fan_data import payload

ROOT = Path(__file__).resolve().parents[1]
GPU_ROWS = {row[0]: row for row in hardware.CATALOG if row[1] == "gpu"}
STYLES = ("solid", "miniature", "soft", "cartoon")


def exact_appearance(model_id, style="solid"):
    row = GPU_ROWS[model_id]
    value = hardware.appearance_for("gpu", row[-1][0])
    if value["id"] != model_id or value["confidence"] != "model":
        raise AssertionError((model_id, value))
    return dict(value, icon_set=style)


def effective_profile(row, index):
    overrides = row.get("fans", ())
    return dict(row, **(overrides[index] if index < len(overrides) else {}))


def decode(source):
    header, body = source.split(",", 1)
    return base64.b64decode(body).decode() if ";base64" in header else unquote(body)


def blade_paths(tree):
    # Blade copies rotate individually; tip arcs and the hub are separate paths.
    return [node for node in tree.iter()
            if node.tag.endswith("path") and re.fullmatch(r"rotate\([-+.0-9eE]+\)", node.get("transform", ""))]


def rendered_blade_sections(node):
    """Measure the exported leaf silhouette, independently of its SVG commands."""
    leaf = ET.Element("path", {"d": node.get("d"), "fill": "#ffffff"})
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 6 6">'
           + ET.tostring(leaf, encoding="unicode") + '</svg>')
    image = QImage(600, 600, QImage.Format_ARGB32)
    image.fill(0)
    renderer = QSvgRenderer(svg.encode())
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    sections = []
    for radius in (1.25, 2.4):
        angles = []
        for step in range(-480, 481):
            angle = step / 4
            radians = math.radians(angle - 90)
            x = round(300 + math.cos(radians) * radius * 100)
            y = round(300 + math.sin(radians) * radius * 100)
            if image.pixelColor(x, y).alpha() >= 128:
                angles.append(angle)
        if not angles:
            raise AssertionError("The actual leaf has no visible section at radius " + str(radius))
        sections.append(((min(angles) + max(angles)) / 2, max(angles) - min(angles)))
    return sections


class HardwareFanProfileDataTests(unittest.TestCase):
    def test_every_reviewed_series_has_one_guarded_exact_profile(self):
        self.assertFalse(GROUP_A.keys() & GROUP_B.keys())
        self.assertEqual(set(PROFILES), {row["id"] for row in SERIES_CATALOG})
        self.assertEqual(len(PROFILES), 103)
        guarded_models = set()
        for series, row in PROFILES.items():
            with self.subTest(series=series):
                self.assertEqual(len(row.get("model_ids", ())), 1)
                model_id = row["model_ids"][0]
                self.assertNotIn(model_id, guarded_models)
                guarded_models.add(model_id)
                self.assertEqual(hardware._MODEL_SERIES[model_id], series)
                self.assertEqual(exact_appearance(model_id)["series_id"], series)
                url = urlparse(row["source_url"])
                self.assertEqual(url.scheme, "https")
                self.assertTrue(url.hostname)
                self.assertIn(row["evidence"], {"explicit_count", "official_front_view", "family_description"})
                for index in range(max(1, len(row.get("fans", ())))):
                    fan = effective_profile(row, index)
                    blades = fan.get("blades")
                    self.assertTrue(blades is None or type(blades) is int and 2 <= blades <= 64)
                    ratio = fan.get("hub_ratio")
                    self.assertTrue(ratio is None or type(ratio) in (int, float) and 0 < ratio < 1)
                    self.assertIs(type(fan["outer_ring"]), bool)
                    self.assertIn(fan.get("group_size", 1), (1, 2, 3))
                    self.assertIn(fan.get("direction", 1), (1, -1))
        self.assertEqual(guarded_models, {base_identity(model) for model in GPU_ROWS})

    def test_series_brand_other_sku_and_non_gpu_cannot_claim_reviewed_technology(self):
        for series, row in PROFILES.items():
            with self.subTest(series=series):
                value = exact_appearance(row["model_ids"][0])
                answer = profile_for(value)
                self.assertEqual(answer["technology"], row["technology"])
                self.assertEqual(answer["blades"], row.get("blades"))
                self.assertEqual(answer["verified"], row["technology"] != "unknown")
                for confidence in ("series", "brand", "generic", ""):
                    self.assertEqual(profile_for(dict(value, confidence=confidence)), {})
                self.assertEqual(profile_for(dict(value, id="different-sku")), {})
                self.assertEqual(profile_for(dict(value, kind="cpu")), {})
                self.assertEqual(profile_for(dict(value, kind="memory")), {})
                answer["label"] = "caller mutation"
                self.assertEqual(profile_for(value)["label"], row["label"])


class HardwareFanProfileGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = cls.enterClassContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native I/O"), create=True))
        cls.process = cls.enterClassContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.engine = QQmlEngine()
        cls.warnings = []
        cls.engine.warnings.connect(lambda errors: cls.warnings.extend(error.toString() for error in errors))
        cls.component = QQmlComponent(cls.engine)
        cls.component.setData(b'''import QtQml
import "../native/HardwareShapes.js" as Shapes
import "../native/HardwareFanDesigns.js" as Fans
import "../native/HardwareFanProfileData.js" as Data
QtObject {
 function table() { return JSON.stringify(Data.profiles) }
 function study(series,index,kind) {
  const p=Fans.profile(series,index,kind)
  const c={blade:"#576d82",disk:"#26323f",hub:"#dae3e9",rim:"#7a8fa3"}
  return JSON.stringify({profile:p,svg:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 6 6">'+Fans.rotor(p,c)+'</svg>'})
 }
 function layers(value) { return JSON.stringify(Shapes.layers(Shapes.key(value,"#303a48"))) }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HardwareFanProfileFixture.qml")))
        cls.item = cls.component.create()
        if cls.item is None:
            raise AssertionError([error.toString() for error in cls.component.errors()])

    @classmethod
    def tearDownClass(cls):
        cls.item.deleteLater()
        cls.component.deleteLater()
        cls.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        cls.app.processEvents()
        if cls.warnings:
            raise AssertionError(cls.warnings)
        cls.native.assert_not_called()
        cls.process.assert_not_called()

    def evaluate(self, source):
        expression = QQmlExpression(qmlContext(self.item), self.item, source)
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return json.loads(value[0] if isinstance(value, tuple) else value)

    def study(self, series, index=0, kind="axial"):
        return self.evaluate("study(" + ",".join(json.dumps(v) for v in (series, index, kind)) + ")")

    def layers(self, appearance):
        return self.evaluate("layers(" + json.dumps(appearance) + ")")

    def test_generated_table_matches_reviewed_offline_data_without_provenance_payload(self):
        table = self.evaluate("table()")
        self.assertEqual(table, payload())
        encoded = json.dumps(table)
        for private_or_unused in ("source_url", "source_image_url", "representative", "model_ids", "notes"):
            self.assertNotIn('"' + private_or_unused + '"', encoded)

    def test_all_modern_styles_draw_exact_confirmed_blades_and_neutral_unknowns(self):
        unknown_seen = known_seen = 0
        for style in STYLES:
            for series, row in PROFILES.items():
                value = exact_appearance(row["model_ids"][0], style)
                result = self.layers(value)
                visible = value.get("visible_fan_count")
                visible = visible if visible is not None else value["fan_count"]
                expected_count = visible if type(visible) is int and 1 <= visible <= 3 else 0
                with self.subTest(style=style, series=series):
                    self.assertEqual(len(result["rotors"]), expected_count)
                    base = ET.fromstring(decode(result["baseSource"]))
                    self.assertFalse(any(node.get("class") == "hardware-fan-hub" for node in base.iter()))
                    for index, rotor in enumerate(result["rotors"]):
                        expected = effective_profile(row, index)
                        svg = ET.fromstring(decode(rotor["source"]))
                        blades = blade_paths(svg)
                        count = expected.get("blades")
                        if count is None:
                            unknown_seen += 1
                            self.assertEqual(blades, [], "Unverified blades must not inherit the old 5/6-blade fan")
                            self.assertEqual(sum(node.tag.endswith("path") and node.get("class") != "hardware-fan-hub" for node in svg.iter()), 0)
                        else:
                            known_seen += 1
                            self.assertEqual(len(blades), count)
                            self.assertEqual(len({node.get("transform") for node in blades}), count)
                        self.assertEqual(sum(node.get("class") == "hardware-fan-hub" for node in svg.iter()), 1)
                        self.assertEqual(rotor["direction"], expected.get("direction", 1))
        self.assertGreater(known_seen, 100)

    def test_rotating_tip_rings_linked_groups_and_triangle_hub_are_distinct(self):
        for series in ("asus_dual", "msi_ventus", "msi_suprim", "asrock_steel_legend", "amd_reference", "colorful_advanced"):
            with self.subTest(series=series):
                row = PROFILES[series]
                svg = ET.fromstring(self.study(series)["svg"])
                rings = [node for node in svg.iter() if node.tag.endswith("circle") and node.get("r") == "2.62"]
                self.assertEqual(len(rings), int(row["outer_ring"]))
                arcs = [node for node in svg.iter() if node.tag.endswith("path") and "A2.55 2.55" in node.get("d", "")]
                group_size = row.get("group_size", 1)
                expected_arcs = row["blades"] // group_size if group_size > 1 and not row["outer_ring"] else 0
                self.assertEqual(len(arcs), expected_arcs)
                hub = next(node for node in svg.iter() if node.get("class") == "hardware-fan-hub")
                if series == "amd_reference":
                    self.assertTrue(hub.tag.endswith("path"))
                    self.assertEqual(hub.get("d").count("L"), 2)
                else:
                    self.assertTrue(hub.tag.endswith("circle"))
        # Gravity Rim is part of the fixed Advanced casing, not a blade-tip band.
        self.assertFalse(PROFILES["colorful_advanced"]["outer_ring"])
        self.assertFalse(PROFILES["asrock_steel_legend"]["outer_ring"])

    def test_rendered_axial_leaves_have_sweep_and_open_space_instead_of_radial_spokes(self):
        # Dense 11/13-leaf fans once lost almost all curvature. Rendering the
        # actual single leaf catches that regression without mirroring JS math.
        for series, index in (("asus_rog_strix", 0), ("msi_suprim", 0),
                              ("asus_dual", 0), ("asus_tuf_rdna2", 1)):
            with self.subTest(series=series, fan=index):
                row = self.study(series, index)
                leaf = blade_paths(ET.fromstring(row["svg"]))[0]
                inner, outer = rendered_blade_sections(leaf)
                sweep = abs(outer[0] - inner[0])
                self.assertGreaterEqual(sweep, 16, "Leaf silhouette collapsed into a radial spoke")
                self.assertLess(sweep, 50, "Leaf folds around the hub instead of sweeping outward")
                pitch = 360 / row["profile"]["blades"]
                self.assertGreater(outer[1] / pitch, .25, "Leaf became an outer-edge wire")
                self.assertLess(outer[1] / pitch, .85, "Leaves close into a featureless full disc")

    def test_source_confirmed_reversal_and_mixed_blades_survive_projection(self):
        for series in ("asus_tuf", "asus_astral", "asrock_phantom", "asrock_taichi", "asrock_taichi_rdna4", "gigabyte_aorus"):
            row = PROFILES[series]
            result = self.layers(exact_appearance(row["model_ids"][0]))
            self.assertEqual([rotor["direction"] for rotor in result["rotors"]], [1, -1, 1])
            for index, rotor in enumerate(result["rotors"]):
                tree = ET.fromstring(decode(rotor["source"]))
                mirrored = [n for n in tree.iter() if n.get("transform") == "scale(-1 1)"]
                self.assertEqual(len(mirrored), int(index == 1))
        tuf = self.layers(exact_appearance(PROFILES["asus_tuf_rdna2"]["model_ids"][0]))
        self.assertEqual([len(blade_paths(ET.fromstring(decode(r["source"])))) for r in tuf["rotors"]], [11, 13, 11])
        self.assertEqual([r["direction"] for r in tuf["rotors"]], [1, -1, 1])

    def test_hybrid_fans_keep_distinct_kinds_and_unknown_never_inherits_other_model(self):
        for style in STYLES:
            acer = self.layers(exact_appearance(PROFILES["acer_bifrost_arc_a770"]["model_ids"][0], style))
            self.assertEqual([r["kind"] for r in acer["rotors"]], ["blower", "axial"])
            self.assertLess(acer["rotors"][0]["radius"], acer["rotors"][1]["radius"])
            for rotor in acer["rotors"]:
                self.assertEqual(blade_paths(ET.fromstring(decode(rotor["source"]))), [])
        missing = ET.fromstring(self.study("unregistered_series")["svg"])
        self.assertEqual(blade_paths(missing), [])
        self.assertEqual(sum(node.tag.endswith("path") for node in missing.iter()), 0)
        self.assertIsNone(PROFILES["powercolor_reaper"]["blades"])
        leadtek=PROFILES['leadtek_hurricane']
        self.assertEqual([effective_profile(leadtek,index).get('blades') for index in range(3)],[9,None,9])
        self.assertFalse(profile_for(exact_appearance(leadtek['model_ids'][0]))['render_ready'])

    def test_legacy_torx_keeps_seven_wide_and_seven_narrow_leaves(self):
        for series in ('msi_gaming_pascal','msi_lightning_pascal','msi_gaming_maxwell'):
            for style in STYLES:
                with self.subTest(series=series,style=style):
                    value=exact_appearance(PROFILES[series]['model_ids'][0],style)
                    self.assertEqual(profile_for(value)['blade_pattern'],'alternating')
                    for rotor in self.layers(value)['rotors']:
                        blades=blade_paths(ET.fromstring(decode(rotor['source'])))
                        paths={node.get('d') for node in blades}
                        self.assertEqual(len(blades),14)
                        self.assertEqual(len(paths),2)
                        self.assertEqual(sorted(sum(node.get('d')==path for node in blades)
                                                for path in paths),[7,7])
                        first,second=(rendered_blade_sections(node)[1][1] for node in blades[:2])
                        self.assertGreater(max(first,second)/min(first,second),1.3)
        uniform=blade_paths(ET.fromstring(self.study('msi_suprim')['svg']))
        self.assertEqual(len({node.get('d') for node in uniform}),1)

    def test_b580_titan_and_luna_caps_keep_their_own_finish(self):
        def luminance(color):
            return sum(int(color[index:index+2],16)*weight
                       for index,weight in ((1,.2126),(3,.7152),(5,.0722)))
        for style in STYLES:
            base=exact_appearance('sparkle-b580-titan-12g-oc',style)
            luna=exact_appearance('sparkle-b580-titan-luna-12g-oc',style)
            self.assertEqual(profile_for(base)['hub_tone'],'dark')
            self.assertEqual(profile_for(luna)['hub_tone'],'light')
            for dark,light in zip(self.layers(base)['rotors'],self.layers(luna)['rotors']):
                dark_tree,light_tree=(ET.fromstring(decode(row['source'])) for row in (dark,light))
                dark_hub=next(node for node in dark_tree.iter() if node.get('class')=='hardware-fan-hub')
                light_hub=next(node for node in light_tree.iter() if node.get('class')=='hardware-fan-hub')
                self.assertGreater(luminance(light_hub.get('fill'))-luminance(dark_hub.get('fill')),100)
                self.assertEqual([node.get('d') for node in blade_paths(dark_tree)],
                                 [node.get('d') for node in blade_paths(light_tree)])
                self.assertEqual(len(blade_paths(dark_tree)),9)
            # Two exact TORX 5.0 boards do not establish the same cap finish.
            silver=self.layers(exact_appearance('msi-suprim-x-4090-24g',style))['rotors'][0]
            shadow=self.layers(exact_appearance('msi-shadow-5080oc',style))['rotors'][0]
            caps=[next(node for node in ET.fromstring(decode(row['source'])).iter()
                       if node.get('class')=='hardware-fan-hub') for row in (silver,shadow)]
            silver_luma,dark_luma=(luminance(cap.get('fill')) for cap in caps)
            if style=='cartoon':
                # Pastel paint intentionally lifts dark retail tones. Preserve
                # recognisable light/dark cap finishes instead of requiring the
                # physical treatments' metallic contrast from this illustration.
                self.assertGreater(silver_luma,192)
                self.assertLess(dark_luma,128)
            self.assertGreater(silver_luma-dark_luma,75 if style=='cartoon' else 100)

    def test_taichi_rdna3_and_rdna4_do_not_share_center_fan_paint(self):
        def paints(svg):
            return [node.get('stop-color') for node in ET.fromstring(svg).iter()
                    if node.tag.endswith('stop')]
        for style in STYLES:
            rdna3=self.layers(exact_appearance(PROFILES['asrock_taichi']['model_ids'][0],style))['rotors']
            rdna4=self.layers(exact_appearance(PROFILES['asrock_taichi_rdna4']['model_ids'][0],style))['rotors']
            self.assertEqual(paints(decode(rdna3[0]['source'])),paints(decode(rdna3[1]['source'])))
            self.assertNotEqual(paints(decode(rdna4[0]['source'])),paints(decode(rdna4[1]['source'])))
            for rotors in (rdna3,rdna4):
                self.assertEqual([len(blade_paths(ET.fromstring(decode(row['source'])))) for row in rotors],[11,13,11])
                self.assertEqual([row['direction'] for row in rotors],[1,-1,1])

    def test_exact_new_white_and_compact_variants_keep_per_fan_overrides(self):
        cases={
            'asrock-taichi-7900xtx-white-oc':([11,13,11],[1,-1,1]),
            'asrock-taichi-rx9070xt-white-16g-oc':([11,13,11],[1,-1,1]),
            'zotac-twin-4060ti-oc-white':([11,11],[1,1]),
            'asus-astral-5080-oc-white':([7,7,7],[1,-1,1]),
            'powercolor-fighter-7800xt-mini':([9,9],[1,1]),
        }
        for identity,(counts,directions) in cases.items():
            for style in STYLES:
                with self.subTest(model=identity,style=style):
                    value=exact_appearance(identity,style)
                    rotors=self.layers(value)['rotors']
                    self.assertEqual([len(blade_paths(ET.fromstring(decode(row['source'])))) for row in rotors],counts)
                    self.assertEqual([row['direction'] for row in rotors],directions)
                    self.assertTrue(profile_for(value)['render_ready'])


if __name__ == "__main__":
    unittest.main()
