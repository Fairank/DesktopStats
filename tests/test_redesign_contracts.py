"""Regression contracts from actual 0.7 user-visible failures; no system windows."""

import copy
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from material_policy import render_policy
from native_controller import Controller
from native_layout import LayoutCapacityError, grid_plan, windows
from native_runtime import Runtime
from stats_config import DEFAULT, validate
from widget_catalog import from_template


class RedesignContracts(unittest.TestCase):
    def controller(self, mode="separate"):
        config = copy.deepcopy(DEFAULT)
        power = from_template("power")
        power.update(
            content=["cpu_power", "gpu_power", "battery_discharge_watts"],
            form="wide",
            presentation="list",
            size=76,
            show_title=False,
        )
        config.update(
            mode=mode,
            widgets={"w_power": power, "cpu": from_template("cpu")},
            widget_order=["w_power", "cpu"],
        )
        with patch("native_controller.load", return_value=validate(config)):
            return Controller()

    def test_skin_changes_no_content_shape_presentation_or_title(self):
        ui = self.controller()
        original = copy.deepcopy(ui._draft["widgets"]["w_power"])
        for skin in ("glass", "frost", "tint", "minimal"):
            result = ui.skinPreview("w_power", skin)["widgets"]["preview"]
            self.assertEqual(result, dict(original, skin=skin))
        self.assertEqual(ui._draft["widgets"]["w_power"], original)

    def test_selected_power_is_not_healthy_from_unrelated_fresh_cpu_reading(self):
        ui = self.controller()
        ui._data = dict(time=time.time(), cpu_usage=30)
        self.assertTrue(any(row["available"] for row in ui.sensorRows))
        health = ui.widgetHealth("w_power")
        self.assertEqual(
            (health["total"], health["available"], health["state"]), (3, 0, "unavailable")
        )
        self.assertEqual(len(health["missing"]), 3)
        self.assertTrue(all(row["reason"] for row in health["missing"]))

    def test_partial_zero_and_stale_readings_are_distinct(self):
        ui = self.controller()
        ui._data = dict(time=time.time(), cpu_power=55.1, gpu_power=30.7)
        self.assertEqual(ui.widgetHealth("w_power")["state"], "partial")
        ui._data.update(
            battery_present=True,
            battery_discharge_watts=0.0,
            battery_watts=0.0,
            power_online=True,
            charging=False,
            discharging=False,
        )
        self.assertEqual(ui.widgetHealth("w_power")["state"], "ready")
        self.assertEqual(ui.widgetHealth("w_power")["available"], 3)
        ui._data["time"] -= 40
        health = ui.widgetHealth("w_power")
        self.assertEqual((health["state"], health["available"]), ("stale", 0))
        self.assertTrue(all(row["reason"] == "读数已过期" for row in health["missing"]))

    def test_close_persists_individual_and_preserves_unrelated_draft(self):
        ui = self.controller()
        ui.changeWidget("cpu", "title", "Draft")
        with patch("native_controller.save") as save:
            self.assertTrue(ui.hideWindow("w_power"))
        self.assertFalse(save.call_args.args[0]["widgets"]["w_power"]["enabled"])
        self.assertEqual(ui._draft["widgets"]["cpu"]["title"], "Draft")
        self.assertEqual(ui._saved["widgets"]["cpu"]["title"], "")
        self.assertNotIn("w_power", [item["id"] for item in windows(ui._saved)])
        with patch("native_controller.save"):
            ui.apply()
        self.assertNotIn("w_power", [item["id"] for item in windows(ui._saved)])

    def test_group_close_is_atomic_and_does_not_commit_other_drafts(self):
        ui = self.controller("combined")
        ui.change("theme", "dark")
        key = windows(ui._saved)[0]["id"]
        self.assertEqual(key, "group")
        before = copy.deepcopy(ui._saved)
        with patch("native_controller.save", side_effect=OSError("disk full")):
            self.assertFalse(ui.hideWindow(key))
        self.assertEqual(ui._saved, before)
        self.assertEqual(ui._draft["theme"], "dark")
        with patch("native_controller.save") as save:
            self.assertTrue(ui.hideWindow(key))
        save.assert_called_once()
        self.assertEqual(windows(ui._saved), [])
        self.assertEqual(ui._saved["theme"], "light")

    def test_deferred_close_cannot_hide_a_replaced_window_or_during_shutdown(self):
        old = object()
        runtime = SimpleNamespace(
            widgets={"w_power": old},
            shutting_down=False,
            controller=SimpleNamespace(hideWindow=Mock()),
        )
        with patch("native_runtime.QTimer.singleShot") as later:
            Runtime.queue_window_close(runtime, "w_power")
        callback = later.call_args.args[1]
        runtime.widgets["w_power"] = object()
        callback()
        runtime.controller.hideWindow.assert_not_called()
        runtime.widgets["w_power"] = old
        runtime.shutting_down = True
        callback()
        runtime.controller.hideWindow.assert_not_called()
        runtime.shutting_down = False
        callback()
        runtime.controller.hideWindow.assert_called_once_with("w_power")

    def dense_config(self, mode="separate", form="wide"):
        config = copy.deepcopy(DEFAULT)
        template = from_template("power")
        template.update(
            size=76,
            form=form,
            content=[
                "cpu_power",
                "gpu_power",
                "battery_charge_watts",
                "battery_discharge_watts",
                "adapter_input_watts",
                "system_power",
            ],
        )
        config.update(
            mode=mode,
            widgets={f"w_{i}": copy.deepcopy(template) for i in range(24)},
            widget_order=[f"w_{i}" for i in range(24)],
        )
        return validate(config)

    def test_automatic_fit_cannot_bypass_dense_card_minimum(self):
        for mode, area in [("combined", (1920, 1080)), ("separate", (1280, 720))]:
            config = self.dense_config(mode)
            specs = windows(config)
            self.assertTrue(all(cell["height"] >= 132 for spec in specs for cell in spec["cells"]))
            with self.assertRaises(LayoutCapacityError):
                grid_plan(specs, *area, config["layout"])
        config = self.dense_config("separate", "square")
        specs, _ = grid_plan(windows(config), 1920, 1080, config["layout"])
        self.assertEqual(len(specs), 24)
        self.assertTrue(all(cell["height"] >= 132 for spec in specs for cell in spec["cells"]))

    def test_unfittable_dense_draft_does_not_replace_saved_config(self):
        ui = self.controller()
        ui.set_preview_area(1280, 720)
        before = copy.deepcopy(ui._saved)
        ui.edit(self.dense_config())
        self.assertEqual(len(ui.preview_windows()), 24)
        with (
            patch("native_controller.save") as save,
            patch("native_controller.set_autostart") as autostart,
        ):
            ui.apply()
        save.assert_not_called()
        autostart.assert_not_called()
        self.assertEqual(ui._saved, before)
        self.assertTrue(ui.dirty)
        self.assertIn("桌面空间不足", ui.status)

    def test_group_material_respects_per_widget_zero_and_independent_overrides(self):
        ui = self.controller("combined")
        config = ui._draft
        config["widgets"]["cpu"]["glass_transparency"] = 0.0
        config["widgets"]["w_power"]["glass_transparency"] = 100.0
        spec = windows(config)[0]
        policy = render_policy(config, spec)
        self.assertTrue(policy["card_surfaces"])
        self.assertIsNone(policy["panel_skin"])
        config["widgets"]["w_power"]["glass_transparency"] = 0.0
        policy = render_policy(config, windows(config)[0])
        self.assertFalse(policy["card_surfaces"])
        self.assertEqual(policy["panel_options"]["transparency"], 0.0)

    def test_show_all_quick_action_preserves_saved_hidden_layout_if_it_cannot_fit(self):
        ui = self.controller()
        config = self.dense_config()
        config["visible"] = False
        ui._saved = copy.deepcopy(config)
        ui._draft = copy.deepcopy(config)
        ui._draft["theme"] = "dark"
        ui.set_preview_area(1280, 720)
        before = copy.deepcopy(ui._draft)
        with patch("native_controller.save") as save:
            ui.quick("visible")
        save.assert_not_called()
        self.assertFalse(ui._saved["visible"])
        self.assertEqual(ui._draft, before)
        self.assertIn("桌面空间不足", ui.status)


if __name__ == "__main__":
    unittest.main()
