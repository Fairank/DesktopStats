"""Reviewed exact-board fan studies and actual SVG rotors; no hardware or windows."""
import base64
import json
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
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext

import hardware_appearance as hardware
from hardware_fan_profiles import GROUP_A, GROUP_B, PROFILES, profile_for
from hardware_series import SERIES_CATALOG
from tools.generate_hardware_fan_data import payload

ROOT = Path(__file__).resolve().parents[1]
GPU_ROWS = {row[0]: row for row in hardware.CATALOG if row[1] == "gpu"}
STYLES = ("solid", "miniature", "soft")


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
        self.assertEqual(guarded_models, set(GPU_ROWS))

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

    def test_all_three_styles_draw_exact_confirmed_blades_and_neutral_unknowns(self):
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
        self.assertGreater(unknown_seen, 100)

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

    def test_source_confirmed_reversal_and_mixed_blades_survive_projection(self):
        for series in ("asus_tuf", "asrock_phantom", "asrock_taichi", "asrock_taichi_rdna4", "gigabyte_aorus"):
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
        self.assertIsNone(PROFILES["leadtek_hurricane"]["blades"])


if __name__ == "__main__":
    unittest.main()
