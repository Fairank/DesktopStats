"""Persistent layout transactions, migrations and multi-monitor geometry."""

import copy
import math
import unittest
from unittest.mock import patch

import native_controller as controls
from desktop_placement import desktop_plan
from native_layout import LayoutCapacityError, windows
from responsive_layout import dimensions, minimum_dimensions
from stats_config import DEFAULT, validate
from widget_catalog import from_template


def config():
    value = copy.deepcopy(DEFAULT)
    value.update(
        mode="separate",
        widgets={"w_bar": from_template("status_bar")},
        widget_order=["w_bar"],
        autostart=False,
    )
    return value


class LayoutCustomizationTests(unittest.TestCase):
    def controller(self, value=None):
        with patch.object(controls, "load", return_value=value or config()):
            return controls.Controller()

    def test_migration_keeps_dormant_preferences_and_explicit_order(self):
        source = config()
        source["version"] = 7
        source["widgets"]["old"] = from_template("cpu")
        source["widgets"]["old"].update(enabled=False, title="旧项目", skin="minimal")
        migrated = validate(source)
        self.assertEqual(migrated["version"], 8)
        self.assertEqual(migrated["widget_order"], ["w_bar"])
        self.assertEqual(migrated["widgets"]["old"]["title"], "旧项目")
        self.assertEqual(validate(migrated), migrated)

    def test_invalid_manual_geometry_is_transactionally_rejected(self):
        ui = self.controller()
        ui.changeWidget("w_bar", "layout_mode", "manual")
        before = copy.deepcopy(ui._draft)
        first = before["widgets"]["w_bar"]["content"][0]
        for x, y, w, h in (
            (0, 0, 1, 1),
            (-0.1, 0, 0.2, 0.2),
            (0, 0, math.nan, 0.2),
            (0, 0, 0, 0.2),
        ):
            self.assertFalse(ui.setMetricPosition("w_bar", first, x, y, w, h))
            self.assertEqual(ui._draft, before)

    def test_manual_add_remove_reseeds_complete_nonoverlapping_layout(self):
        ui = self.controller()
        ui.removeMetric("w_bar", 5)
        ui.changeWidget("w_bar", "layout_mode", "manual")
        ui.addMetric("w_bar", "gpu_temp")
        prefs = ui._draft["widgets"]["w_bar"]
        self.assertEqual(set(prefs["metric_positions"]), set(prefs["content"]))
        self.assertEqual(validate(ui._draft), ui._draft)
        self.assertEqual(
            len(ui.widgetContentLayout("w_bar", *dimensions(ui._draft, "w_bar"))["readings"]), 6
        )

    def test_desktop_resize_preserves_unrelated_editor_draft(self):
        ui = self.controller()
        ui.change("language", "de")
        ui.changeWidget("w_bar", "title", "Pending")
        with patch.object(controls, "save") as save:
            self.assertTrue(ui.resizeWindow("w_bar", 320, 40))
        written = save.call_args.args[0]
        self.assertEqual(written["language"], "zh-CN")
        self.assertEqual(written["widgets"]["w_bar"]["title"], "")
        self.assertEqual(ui._draft["language"], "de")
        self.assertEqual(ui._draft["widgets"]["w_bar"]["title"], "Pending")
        self.assertEqual(dimensions(written, "w_bar"), (320, 114))

    def test_monitor_fit_wraps_short_wide_strip_without_losing_height(self):
        value = config()
        specs, _ = desktop_plan(
            value, [dict(id="small", primary=True, x=0, y=0, width=420, height=400)]
        )
        cell = specs[0]["cells"][0]
        self.assertGreaterEqual(
            cell["height"], minimum_dimensions(value["widgets"]["w_bar"], cell["width"])[1]
        )
        self.assertLessEqual(specs[0]["width"], 396)

    def test_top_strip_stays_separate_after_undocking_in_combined_mode(self):
        value = config()
        value["mode"] = "combined"
        value["widgets"]["w_bar"]["dock"] = "free"
        self.assertEqual([s["id"] for s in windows(value)], ["w_bar"])

    def test_large_secondary_monitor_does_not_use_primary_capacity(self):
        value = config()
        value["widgets"]["w_bar"].update(width=2000, screen_target="large")
        screens = [
            dict(id="small", primary=True, x=0, y=0, width=800, height=600),
            dict(id="large", primary=False, x=-2560, y=0, width=2560, height=1440),
        ]
        specs, points = desktop_plan(value, screens)
        self.assertEqual(specs[0]["width"], 2000)
        self.assertEqual(points["w_bar"], [-2280, 8])

    def test_group_cannot_be_accepted_if_explicit_rows_would_hide_all_values(self):
        value = config()
        prefs = value["widgets"]["w_bar"]
        prefs.update(form="free", dock="free", width=900, height=200, layout_mode="horizontal")
        value["widgets"]["second"] = copy.deepcopy(prefs)
        value["widget_order"].append("second")
        value["mode"] = "combined"
        with self.assertRaises(LayoutCapacityError):
            desktop_plan(value, [dict(id="screen", primary=True, x=0, y=0, width=1000, height=600)])


if __name__ == "__main__":
    unittest.main()
