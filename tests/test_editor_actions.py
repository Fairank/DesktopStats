"""Mouse-oriented editor commands are atomic and preserve unrelated preferences."""

import copy
import unittest
from unittest.mock import patch

import native_controller as controls
from layout_assist import resize_layout
from stats_config import DEFAULT
from widget_catalog import from_template


class EditorActionTests(unittest.TestCase):
    def setUp(self):
        config = copy.deepcopy(DEFAULT)
        prefs = from_template("custom")
        prefs.update(
            content=["cpu_power", "gpu_power"],
            width=500,
            height=160,
            form="free",
            show_title=False,
            title="Power",
            precision="2",
            network_unit="Mbps",
        )
        config.update(widgets={"w_edit": prefs}, widget_order=["w_edit"], mode="separate")
        with patch.object(controls, "load", return_value=config):
            self.ui = controls.Controller()

    def test_batch_picker_adds_several_metrics_with_one_undo(self):
        before = copy.deepcopy(self.ui._draft)
        self.assertTrue(self.ui.addMetrics("w_edit", ["net_download", "cpu_temp"]))
        self.assertEqual(
            self.ui._draft["widgets"]["w_edit"]["content"],
            ["cpu_power", "gpu_power", "net_download", "cpu_temp"],
        )
        self.assertEqual(len(self.ui._undo_drafts), 1)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, before)

    def test_bad_batch_never_partially_adds_or_records_undo(self):
        before = copy.deepcopy(self.ui._draft)
        self.assertFalse(self.ui.addMetrics("w_edit", ["cpu_temp", "not_a_sensor"]))
        self.assertEqual(self.ui._draft, before)
        self.assertFalse(self.ui.canUndoDraft)
        self.assertFalse(self.ui.addMetrics("w_edit", ["cpu_temp"] * 2))
        self.assertEqual(self.ui._draft, before)

    def test_preset_preserves_metrics_units_title_and_can_restore_previous_layout(self):
        original = copy.deepcopy(self.ui._draft)
        self.assertTrue(self.ui.applyLayoutPreset("w_edit", "horizontal"))
        prefs = self.ui._draft["widgets"]["w_edit"]
        self.assertEqual((prefs["width"], prefs["height"], prefs["dock"]), (900, 40, "top"))
        for field in ("content", "precision", "title", "network_unit"):
            self.assertEqual(prefs[field], original["widgets"]["w_edit"][field])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, original)

    def test_drag_preview_is_read_only_and_cancel_does_not_add_undo(self):
        self.ui.changeWidget("w_edit", "layout_mode", "manual")
        before = copy.deepcopy(self.ui._draft)
        positions = before["widgets"]["w_edit"]["metric_positions"]
        depth = len(self.ui._undo_drafts)
        for offset in range(30):
            rect = dict(positions["cpu_power"], x=0.01 * offset)
            self.ui.previewMetricPlacement("w_edit", "cpu_power", rect, "move", True, False)
        self.assertEqual(self.ui._draft, before)
        self.assertEqual(len(self.ui._undo_drafts), depth)

    def test_swap_is_atomic_and_does_not_resize_the_window(self):
        self.ui.changeWidget("w_edit", "layout_mode", "manual")
        before = copy.deepcopy(self.ui._draft)
        positions = before["widgets"]["w_edit"]["metric_positions"]
        response = self.ui.previewLayoutOperation("w_edit", "swap", ["cpu_power", "gpu_power"])
        self.assertTrue(response["valid"])
        self.assertEqual(self.ui._draft, before)
        self.assertTrue(self.ui.commitMetricPositions("w_edit", response["positions"]))
        after = self.ui._draft["widgets"]["w_edit"]
        self.assertEqual(after["metric_positions"]["cpu_power"], positions["gpu_power"])
        self.assertEqual(
            (after["width"], after["height"]),
            (before["widgets"]["w_edit"]["width"], before["widgets"]["w_edit"]["height"]),
        )
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, before)

    def test_tiny_advanced_rectangle_cannot_expand_the_whole_widget(self):
        self.ui.changeWidget("w_edit", "layout_mode", "manual")
        before = copy.deepcopy(self.ui._draft)
        positions = copy.deepcopy(before["widgets"]["w_edit"]["metric_positions"])
        positions["cpu_power"]["width"] = 0.025
        self.assertFalse(self.ui.commitMetricPositions("w_edit", positions))
        self.assertEqual(self.ui._draft, before)

    def test_manual_append_keeps_old_actual_geometry_and_undo_restores_outer_size(self):
        self.ui.changeWidget("w_edit", "layout_mode", "manual")
        before = copy.deepcopy(self.ui._draft)
        old = {r["id"]: r for r in self.ui.widgetContentLayout("w_edit", 500, 160)["readings"]}
        self.assertTrue(self.ui.addMetrics("w_edit", ["cpu_temp", "ram_percent"]))
        dimensions = self.ui.widgetDimensions("w_edit")
        new = {
            r["id"]: r
            for r in self.ui.widgetContentLayout(
                "w_edit", dimensions["width"], dimensions["height"]
            )["readings"]
        }
        for metric in old:
            for field in ("x", "y", "width", "height"):
                self.assertAlmostEqual(old[metric][field], new[metric][field], places=6)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, before)

    def test_manual_append_at_fractional_readable_floor_never_grows_an_extra_pixel(self):
        for show_title in (False, True):
            # 30 / (30 / 104) is 104.00000000000001 on Python. Blind ceil
            # used to add a pixel after append, moving/resizing every old item.
            for old_body_height in (66, 69, 72, 79, 161, 163, 170):
                with self.subTest(show_title=show_title, old_body_height=old_body_height):
                    title_padding = 22 if show_title else 0
                    old_height = old_body_height + 8 + title_padding
                    config = copy.deepcopy(DEFAULT)
                    prefs = from_template("custom")
                    prefs.update(
                        content=["cpu_power"],
                        form="free",
                        width=300,
                        height=old_height,
                        layout_mode="manual",
                        show_title=show_title,
                        chart=False,
                        metric_positions={"cpu_power": dict(x=0, y=0, width=1, height=1)},
                    )
                    config.update(widgets={"w_edit": prefs}, widget_order=["w_edit"])
                    with patch.object(controls, "load", return_value=config):
                        ui = controls.Controller()
                    before = copy.deepcopy(ui.draft)
                    old_rect = ui.widgetContentLayout("w_edit", 300, old_height)["readings"][0]
                    self.assertTrue(ui.addMetrics("w_edit", ["gpu_power"]))
                    effective = ui.widgetDimensions("w_edit")
                    self.assertEqual(
                        (effective["width"], effective["height"]), (300, old_height + 38)
                    )
                    readings = ui.widgetContentLayout("w_edit", 300, old_height + 38)["readings"]
                    self.assertEqual([row["id"] for row in readings], ["cpu_power", "gpu_power"])
                    for field in ("x", "y", "width", "height"):
                        self.assertAlmostEqual(old_rect[field], readings[0][field], places=8)
                    self.assertEqual(len(ui._undo_drafts), 1)
                    self.assertTrue(ui.undoDraft())
                    self.assertEqual(ui.draft, before)

    def test_same_size_manual_resize_does_not_ceil_normalization_noise(self):
        for width in (196, 197, 206, 214, 237, 239, 249, 253, 4076):
            for height in (52, 55, 104, 107, 110, 117, 199, 201, 2152):
                with self.subTest(width=width, height=height):
                    body = dict(width=width, height=height)
                    positions = {"cpu_power": dict(x=0, y=0, width=128 / width, height=30 / height)}
                    response = resize_layout(positions, body, body)
                    self.assertTrue(response["valid"])
                    self.assertEqual(response["body"], body)
                    self.assertFalse(response["resized"])
                    self.assertFalse(response["expanded"])

    def test_manual_append_reaching_outer_height_limit_is_accepted_without_dip_drift(self):
        config = copy.deepcopy(DEFAULT)
        prefs = from_template("custom")
        prefs.update(
            content=["cpu_power"],
            form="free",
            width=300,
            height=2122,
            layout_mode="manual",
            show_title=False,
            chart=False,
            metric_positions={"cpu_power": dict(x=0, y=0, width=1, height=1)},
        )
        config.update(widgets={"w_edit": prefs}, widget_order=["w_edit"])
        with patch.object(controls, "load", return_value=config):
            ui = controls.Controller()
        old_rect = ui.widgetContentLayout("w_edit", 300, 2122)["readings"][0]
        self.assertTrue(ui.addMetrics("w_edit", ["gpu_power"]))
        self.assertEqual(ui.widgetDimensions("w_edit")["height"], 2160)
        new_rect = ui.widgetContentLayout("w_edit", 300, 2160)["readings"][0]
        for field in ("x", "y", "width", "height"):
            self.assertAlmostEqual(old_rect[field], new_rect[field], places=8)

    def test_over_limit_manual_append_keeps_all_content_geometry_and_history(self):
        config = copy.deepcopy(DEFAULT)
        prefs = from_template("custom")
        prefs.update(
            content=["cpu_power"],
            form="free",
            width=300,
            height=2123,
            layout_mode="manual",
            show_title=False,
            chart=False,
            metric_positions={"cpu_power": dict(x=0, y=0, width=1, height=1)},
        )
        config.update(widgets={"w_edit": prefs}, widget_order=["w_edit"])
        with patch.object(controls, "load", return_value=config):
            ui = controls.Controller()
        before = copy.deepcopy(ui.draft)
        self.assertFalse(ui.addMetrics("w_edit", ["gpu_power"]))
        self.assertEqual(ui.draft, before)
        self.assertEqual(ui.saved, before)
        self.assertFalse(ui.canUndoDraft)


if __name__ == "__main__":
    unittest.main()
