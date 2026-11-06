"""Historical identities and actual static SVG routing; synthetic offscreen only."""
import base64
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

import hardware_appearance as appearance
import hardware_catalog_nvidia_legacy as nvidia
import hardware_catalog_radeon_arc as radeon


PACKAGES = (nvidia, radeon)
ROOT = Path(__file__).resolve().parents[1]


def reviewed_rows():
    for package in PACKAGES:
        for row in package.CATALOG:
            yield package, row


def chip_name(package, row):
    return getattr(package, "MODEL_CHIPS", {}).get(row[0], row[4])


class HistoricalHardwareIdentityTests(unittest.TestCase):
    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))

    def tearDown(self):
        self.native.assert_not_called()
        self.process.assert_not_called()

    def test_every_new_complete_alias_routes_to_its_own_reviewed_design_and_fan_facts(self):
        aliases = set()
        for package, row in reviewed_rows():
            for alias in row[9]:
                with self.subTest(model=row[0], alias=alias):
                    normalized = appearance._text(alias)
                    self.assertNotIn(normalized, aliases)
                    aliases.add(normalized)
                    result = appearance.appearance_for("gpu", alias)
                    self.assertEqual((result["id"], result["confidence"]), (row[0], "model"))
                    self.assertEqual(result["series_id"], package.MODEL_SERIES[row[0]])
                    self.assertEqual(result["fan_count"], row[6])
                    expected_front = getattr(package, "VISIBLE_FANS", {}).get(row[0], row[6])
                    self.assertEqual(result["visible_fan_count"], expected_front)
                    self.assertEqual(result["style"], row[5])

    def test_chip_plus_exact_board_sku_handles_old_label_word_order_without_weakening_conflicts(self):
        self.assertEqual(set(nvidia.MODEL_CHIPS), {row[0] for row in nvidia.CATALOG})
        for package, row in reviewed_rows():
            canonical = chip_name(package, row)
            with self.subTest(model=row[0], chip=canonical):
                chips = appearance._gpu_chips(appearance._text(canonical))
                self.assertTrue(chips, "An official ASIC name must be explicit, even for N680GTX/NX8800GTS labels")
                self.assertEqual(chips, appearance._MODEL_CHIPS[row[0]])
                result = appearance.appearance_for("gpu", canonical, model=row[9][0], board_vendor=row[3])
                self.assertEqual((result["id"], result["confidence"]), (row[0], "model"))
                self.assertEqual(result["fan_count"], row[6])
                alternatives = ("NVIDIA GeForce RTX 4090", "AMD Radeon RX 7900 XTX",
                                "Intel Arc B580", "NVIDIA GeForce GTX 660")
                for wrong in alternatives:
                    if appearance._gpu_chips(appearance._text(wrong)) == chips:
                        continue
                    rejected = appearance.appearance_for("gpu", wrong, model=row[9][0], board_vendor=row[3])
                    self.assertNotEqual(rejected["confidence"], "model", wrong)
                    self.assertIsNone(rejected["fan_count"], wrong)
                    self.assertIsNone(rejected["visible_fan_count"], wrong)

    def test_naked_asics_and_explicit_non_reference_brands_never_inherit_a_reference_or_non_public_cooler(self):
        for package, row in reviewed_rows():
            canonical = chip_name(package, row)
            with self.subTest(model=row[0]):
                for board in ("", "asus", "msi", "sapphire"):
                    result = appearance.appearance_for("gpu", canonical, board_vendor=board)
                    self.assertNotEqual(result["confidence"], "model")
                    self.assertIsNone(result["fan_count"])
                    self.assertIsNone(result["visible_fan_count"])
                if row[3] in ("nvidia", "amd", "intel"):
                    rejected = appearance.appearance_for("gpu", canonical, model=row[9][0], board_vendor="asus")
                    self.assertNotEqual(rejected["confidence"], "model")
                    self.assertIsNone(rejected["fan_count"])

    def test_era_specific_series_keep_their_metadata_and_do_not_replace_modern_same_name_series(self):
        modern = {row["id"] for row in appearance.SERIES_CATALOG
                  if not row.get("legacy") and not row.get("era")}
        historical = []
        for package in PACKAGES:
            rows = {row[0]: row for row in package.CATALOG}
            for series in package.SERIES:
                if not series.get("legacy"):
                    continue
                historical.append(series)
                with self.subTest(series=series["id"]):
                    self.assertTrue(series.get("era"))
                    self.assertIn(series.get("tier"), ("entry", "mainstream", "flagship", "reference"))
                    self.assertNotIn(series["id"], modern)
                    representatives = [rows[key] for key, value in package.MODEL_SERIES.items()
                                       if value == series["id"]]
                    self.assertTrue(representatives)
                    for row in representatives:
                        result = appearance.appearance_for("gpu", row[9][0])
                        self.assertEqual(result["series_id"], series["id"])
                        self.assertEqual(result["tier"], series["tier"])
                        canonical_era = {"rdna1": "rx5000", "rdna2": "rx6000",
                                         "rdna3": "rx7000", "rdna4": "rx9000"}.get(series["era"], series["era"])
                        self.assertEqual(result["era"], canonical_era)
                    # Generic long-lived line words cannot select this precise
                    # historical cooler just because its manufacturer matches.
                    generic = series["board_vendor"] + " GAMING LIGHTNING WINDFORCE unidentified GPU"
                    self.assertNotEqual(appearance.appearance_for("gpu", generic)["series_id"], series["id"])
        self.assertGreaterEqual(len(historical), 16)
        self.assertTrue(any(row.get("legacy") for row in radeon.SERIES))

    def test_revised_white_and_laptop_names_cannot_reuse_a_historical_exact_count(self):
        for _package, row in reviewed_rows():
            for alias in row[9]:
                for suffix in (" revised", " WHITE", " Laptop GPU"):
                    with self.subTest(model=row[0], alias=alias, suffix=suffix):
                        result = appearance.appearance_for("gpu", alias + suffix)
                        self.assertNotEqual(result["confidence"], "model")
                        self.assertIsNone(result["fan_count"])
                        self.assertIsNone(result["visible_fan_count"])

    def test_passive_zero_and_blower_one_are_explicit_facts_not_inferred_from_silence(self):
        passive, blowers = [], []
        for package, row in reviewed_rows():
            result = appearance.appearance_for("gpu", row[9][0])
            if row[6] == 0:
                passive.append(row[0])
                self.assertEqual(result["visible_fan_count"], 0)
                self.assertIn(result["style"], ("gpu_axial", "gpu_passive"))
            if row[5] == "gpu_blower":
                blowers.append(row[0])
                self.assertEqual(result["fan_count"], 1)
                self.assertEqual(result["visible_fan_count"], 1)
        self.assertIn("gigabyte-gt1030-silent-lp-2g", passive)
        self.assertIn("nvidia-gtx1080-founders", blowers)
        self.assertIn("nvidia-gtx780ti-reference", blowers)
        # A separate old active FX5200 must not become fanless with its era.
        fx = appearance.appearance_for("gpu", "GV-N52128D")
        self.assertEqual((fx["fan_count"], fx["visible_fan_count"]), (1, 1))


class HistoricalHardwareSvgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_top_bar_module_qml import ModuleQmlTests
        ModuleQmlTests.setUpClass()
        cls.app = ModuleQmlTests.app

    def setUp(self):
        from PySide6.QtCore import QObject, QUrl
        from PySide6.QtQml import QQmlEngine, QQmlComponent
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
Window {
 id: scene; width: 128; height: 128; visible: false
 property var appearance: ({})
 Product.HardwareGlyph { objectName: "historicalGlyph"; x: 16; y: 16; width: 64; height: 64
  appearance: scene.appearance; ink: "#293847" }
}''', QUrl.fromLocalFile(str(ROOT / "tests/HistoricalHardwareFixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.glyph = self.window.findChild(QObject, "historicalGlyph")
        self.assertIsNotNone(self.glyph)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent
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

    def svg_for(self, row, style):
        from PySide6.QtQml import QQmlExpression, qmlContext
        from PySide6.QtSvg import QSvgRenderer
        value = dict(appearance.appearance_for("gpu", row[9][0]), icon_set=style)
        code = "appearance = JSON.parse(" + json.dumps(json.dumps(value)) + ")"
        expression = QQmlExpression(qmlContext(self.window), self.window, code)
        expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        self.app.processEvents()
        header, body = self.glyph.property("svgSource").toString().split(",", 1)
        svg = base64.b64decode(body).decode() if ";base64" in header else unquote(body)
        self.assertTrue(QSvgRenderer(svg.encode()).isValid())
        return ET.fromstring(svg)

    def test_legacy_blowers_keep_position_and_only_confirmed_blade_counts(self):
        from hardware_fan_profiles import PROFILES
        historical_ids = {row["id"] for package in PACKAGES for row in package.SERIES if row.get("legacy")}
        rows = [(package, row) for package, row in reviewed_rows()
                if row[5] == "gpu_blower" and package.MODEL_SERIES[row[0]] in historical_ids]
        self.assertGreaterEqual(len(rows), 4)
        for style in ("solid", "miniature", "soft"):
            for package, row in rows:
                with self.subTest(model=row[0], style=style):
                    tree = self.svg_for(row, style)
                    radial = [node for node in tree.iter() if node.get("class") == "hardware-blower"]
                    self.assertEqual(len(radial), 1)
                    if package is nvidia:
                        # These verified NVIDIA front views put the blower at
                        # the right end, not in the center of a shortened card.
                        cx = float(radial[0].get("transform").split("(", 1)[1].split()[0])
                        self.assertGreater(cx, 14)
                    self.assertEqual(sum(node.get("class") == "hardware-fan-hub" for node in tree.iter()), 1)
                    blades = [node for node in radial[0] if node.tag.endswith("path")
                              and "rotate(" in node.get("transform", "")]
                    profile = PROFILES[package.MODEL_SERIES[row[0]]]
                    self.assertEqual(len(blades), profile['blades'] or 0,
                                     "Unconfirmed radial blades must remain a neutral rotor")
                    self.assertTrue(any(node.get("class", "").split() ==
                                        ["hardware-series-face", package.MODEL_SERIES[row[0]]]
                                        for node in tree.iter()))
        self.assertFalse(self.window.grabWindow().isNull())

    def test_passive_fins_and_active_fx_card_remain_distinct_in_each_modern_style(self):
        rows = {row[0]: row for row in nvidia.CATALOG}
        for style in ("solid", "miniature", "soft"):
            passive = self.svg_for(rows["gigabyte-gt1030-silent-lp-2g"], style)
            active = self.svg_for(rows["gigabyte-fx5200-n52128d"], style)
            self.assertFalse(any(node.get("class") in ("hardware-fan-hub", "hardware-blower") for node in passive.iter()))
            self.assertEqual(sum(node.get("class") == "hardware-fan-hub" for node in active.iter()), 1)
            self.assertFalse(any(node.get("class") == "hardware-blower" for node in active.iter()))
            self.assertNotEqual(ET.tostring(passive), ET.tostring(active))


if __name__ == "__main__":
    unittest.main()
