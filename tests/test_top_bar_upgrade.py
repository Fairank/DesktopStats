"""Bar materials, honest gauges, bounded presentation, and isolated live edits."""

import copy
import unittest
from unittest.mock import patch

import native_controller as controls
from stats_config import DEFAULT, validate
from top_bar_config import top_bar_style, validate_top_bar
from top_bar_layout import DISPLAY_STYLES, present_metric


class BarUpgradeTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)

    def test_material_local_edit_starts_at_global_and_preserves_desktop(self):
        before = copy.deepcopy(self.ui._saved)
        self.ui.change("skin", "frost")
        self.ui.change("glass_transparency", 38.5)
        self.ui.changeTopBarAppearance("glass_transparency", 72.25)
        appearance = self.ui._draft["top_bar"]["appearance"]
        self.assertEqual(appearance, dict(follow_global=False, skin="frost", glass_transparency=72.25))
        self.assertEqual(top_bar_style(self.ui._draft)["glass_transparency"], 72.25)
        self.assertEqual(self.ui._draft["glass_transparency"], 38.5)
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.applyTopBar())
        self.assertEqual(self.ui._saved["skin"], before["skin"])
        self.assertEqual(self.ui._saved["glass_transparency"], before["glass_transparency"])
        self.assertEqual(self.ui._draft["skin"], "frost")
        self.assertTrue(self.ui.dirty)

    def test_bar_apply_rebases_redo_and_disable_retains_pending_bar_edits(self):
        self.ui.change("size", 120)
        self.ui.change("refresh", .25)
        self.assertTrue(self.ui.undoDraft())
        self.assertTrue(self.ui.canRedoDraft)
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.applyTopBar())
        self.assertTrue(self.ui.canRedoDraft)
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui._draft["refresh"], .25)
        self.ui.changeTopBar("height", 40)
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.setTopBarEnabled(False))
        self.assertEqual(self.ui._draft["top_bar"]["height"], 40)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft["top_bar"]["height"], 32)
        self.assertFalse(self.ui._draft["top_bar"]["enabled"])

    def test_every_style_and_fractional_material_roundtrip(self):
        value = copy.deepcopy(DEFAULT)
        for style in DISPLAY_STYLES:
            value['top_bar']['items'][0]['metric'] = 'net_download' if style in ('duplex', 'duplex_inline') else 'cpu_usage'
            value["top_bar"]["items"][0]["prefs"]["style"] = style
            value["top_bar"]["appearance"].update(follow_global=False, glass_transparency=27.125)
            normalized = validate(value)
            self.assertEqual(validate(normalized), normalized)
        for number in (True, -1, 101, float("nan"), float("inf"), 10**5000):
            bar = copy.deepcopy(value["top_bar"])
            bar["appearance"]["glass_transparency"] = number
            with self.assertRaises(ValueError):
                validate_top_bar(bar)

    def test_gauges_require_real_known_range_zero_remains_valid(self):
        for number, expected in ((0, 0), (42, .42), (100, 1), (-1, None), (101, None), (True, None), (float("nan"), None)):
            row = present_metric(dict(available=True, unit="%", numeric_value=number))
            self.assertEqual(row["gauge_fraction"], expected)
            self.assertEqual(row["gauge_available"], expected is not None)
        for unit in ("W", "RPM", "°C", "V"):
            self.assertFalse(present_metric(dict(available=True, unit=unit, numeric_value=42))["gauge_available"])
        self.assertFalse(present_metric(dict(available=False, unit="%", numeric_value=42))["gauge_available"])

    def test_live_order_saves_only_bar_preserves_other_draft_and_ids(self):
        self.ui.change("size", 120)
        saved = copy.deepcopy(self.ui._saved)
        first, second = saved["top_bar"]["items"][:2]
        with patch.object(controls, "save") as persist:
            self.assertTrue(self.ui.placeLiveTopBarMetric(second["id"], first["id"], "right"))
            persist.assert_called_once()
        self.assertEqual(self.ui._saved["top_bar"]["items"][0]["id"], second["id"])
        self.assertEqual(self.ui._draft["size"], 120)
        self.assertEqual(self.ui._saved["size"], saved["size"])
        self.assertEqual(self.ui._draft["top_bar"], self.ui._saved["top_bar"])
        self.assertTrue(self.ui.dirty)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft["size"], saved["size"])
        self.assertEqual(self.ui._draft["top_bar"], self.ui._saved["top_bar"])
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui._draft["size"], 120)

    def test_live_order_rejects_pending_bar_edit_and_save_failure_without_mutation(self):
        a, b = self.ui._saved["top_bar"]["items"][:2]
        self.ui.changeTopBar("spacing", 7.5)
        before = copy.deepcopy(self.ui._draft)
        with patch.object(controls, "save") as persist:
            self.assertFalse(self.ui.placeLiveTopBarMetric(b["id"], a["id"], "right"))
            persist.assert_not_called()
        self.assertEqual(self.ui._draft, before)
        self.ui._draft = copy.deepcopy(self.ui._saved)
        before = copy.deepcopy(self.ui._saved)
        with patch.object(controls, "save", side_effect=OSError("synthetic")):
            self.assertFalse(self.ui.placeLiveTopBarMetric(b["id"], a["id"], "right"))
        self.assertEqual(self.ui._saved, before)
        self.assertEqual(self.ui._draft, before)

    def test_base_rows_skip_related_and_history_until_requested(self):
        self.ui._data = dict(time=100, cpu_usage=0, gpu_usage=20, ram_percent=40)
        self.ui._history.extend([self.ui._data] * 40)
        with patch.object(controls.time, "time", return_value=101):
            with patch.object(controls, "display_value", wraps=controls.display_value) as project:
                rows = self.ui.topBarRows()
            self.assertEqual(project.call_count, len(rows))
            self.assertTrue(all(row["related"] == [] and row["history"] == [] for row in rows))
            self.assertEqual(rows[0]["gauge_fraction"], 0)
            detail = self.ui.topBarDetailRow(rows[0]["id"])
            self.assertEqual(len(detail["history"]), 40)
            self.assertTrue(detail["related"])
            self.assertEqual(self.ui.topBarDetailRow("missing"), {})
            self.ui._saved["top_bar"]["items"][0]["prefs"]["style"] = "graph"
            self.assertEqual(len(self.ui.topBarRows()[0]["history"]), 40)

    def test_preset_does_not_replace_metrics_devices_or_commit(self):
        self.ui._draft["top_bar"]["items"][1]["prefs"]["gpu_target"] = "another"
        before = copy.deepcopy(self.ui._draft["top_bar"]["items"])
        with patch.object(controls, "save") as persist:
            self.assertTrue(self.ui.applyTopBarPreset("compact"))
            persist.assert_not_called()
        self.assertEqual([row["id"] for row in self.ui._draft["top_bar"]["items"]], [row["id"] for row in before])
        self.assertEqual(self.ui._draft["top_bar"]["items"][1]["prefs"]["gpu_target"], "another")
        self.assertTrue(all(row["prefs"]["style"] == "icon_value" for row in self.ui._draft["top_bar"]["items"]))


if __name__ == "__main__":
    unittest.main()
