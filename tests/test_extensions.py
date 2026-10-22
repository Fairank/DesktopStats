"""Behavioral regressions for the expandable registry, migrations and power flow."""

import copy
import ctypes
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/extension-unit-data"),
)
from activity_sensors import Rates
from battery_sensor import SystemBatteryState, decode
from metrics import METRICS, display_value, metric_value, required_sources
from native_controller import Controller
from native_layout import LayoutCapacityError, grid_plan, windows
from stats_config import DEFAULT, validate
from widget_catalog import TEMPLATES


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.loader = patch("native_controller.load", return_value=copy.deepcopy(DEFAULT))
        self.loader.start()
        self.ui = Controller()

    def tearDown(self):
        self.loader.stop()

    def test_legacy_unused_tabs_are_not_added_widgets(self):
        config = validate(
            {"version": 4, "widgets": {k: {"enabled": k == "cpu"} for k in DEFAULT["widgets"]}}
        )
        self.assertEqual(config["widget_order"], ["cpu"])
        self.assertEqual(validate(config), config)

    def test_add_duplicate_remove_order_survives_serialization(self):
        one = self.ui.addWidget("network")
        two = self.ui.duplicateWidget(one)
        self.assertNotEqual(one, two)
        self.ui.moveWidget(two, -1)
        self.ui.removeWidget(one)
        checked = validate(copy.deepcopy(self.ui._draft))
        self.assertNotIn(one, checked["widgets"])
        self.assertIn(two, checked["widget_order"])
        self.assertEqual(checked["widgets"][two]["content"], ["net_download", "net_upload"])

    def test_removing_all_widgets_does_not_resurrect_defaults(self):
        for key in list(self.ui._draft["widgets"]):
            self.ui.removeWidget(key)
        self.assertEqual(validate(self.ui._draft)["widgets"], {})
        self.assertEqual(windows(self.ui._draft), [])
        self.assertEqual(required_sources(self.ui._draft), set())

    def test_distinct_instances_keep_independent_units_and_targets(self):
        a = self.ui.addWidget("network")
        b = self.ui.duplicateWidget(a)
        self.ui.changeWidget(b, "network_unit", "Mbps")
        self.ui.changeWidget(b, "network_target", "Wi-Fi")
        self.assertEqual(self.ui._draft["widgets"][a]["network_unit"], "MBps")
        self.assertEqual(self.ui._draft["widgets"][b]["network_target"], "Wi-Fi")
        self.assertEqual(
            display_value({"net_download": 1.25}, "net_download", self.ui._draft["widgets"][b])[0],
            None,
        )
        self.assertEqual(
            display_value(
                {"networks": {"Wi-Fi": {"net_download": 1.25}}},
                "net_download",
                self.ui._draft["widgets"][b],
            )[:2],
            (10.0, "Mbps"),
        )

    def test_disconnected_selected_device_cannot_fall_back_to_other_device(self):
        data = {"net_download": 50, "networks": {"other": {"net_download": 50}}}
        self.assertIsNone(metric_value(data, "net_download", {"network_target": "missing"}))

    def test_all_gallery_templates_use_registered_metrics_and_valid_preferences(self):
        for key in TEMPLATES:
            instance = self.ui.addWidget(key)
            self.assertTrue(instance, key)
            self.assertTrue(
                all(metric in METRICS for metric in self.ui._draft["widgets"][instance]["content"])
            )
            self.assertEqual(validate(self.ui._draft), self.ui._draft)

    def test_template_search_includes_reading_names_and_units(self):
        row = next(item for item in self.ui.catalog["templates"] if item["id"] == "network")
        self.assertIn("MB/s", row["search"])
        self.assertIn("net_download", row["search"])

    def test_widget_count_and_bad_ids_are_bounded(self):
        while len(self.ui._draft["widget_order"]) < 24:
            self.assertTrue(self.ui.addWidget("custom"))
        self.assertEqual(self.ui.addWidget("custom"), "")
        for bad in ("../bad", "settings", "group", "w_a/b"):
            config = copy.deepcopy(DEFAULT)
            config["widgets"][bad] = copy.deepcopy(config["widgets"]["cpu"])
            with self.assertRaises(ValueError):
                validate(config)

    def test_invalid_order_and_unhashable_entries_are_rejected(self):
        for order in ([{}], ["cpu", "cpu"], ["missing"]):
            with self.assertRaises(ValueError):
                validate(dict(DEFAULT, widget_order=order))

    def test_desktop_resize_preserves_pending_content_edits(self):
        self.ui.changeWidget("cpu", "title", "pending")
        with patch("native_controller.save") as save:
            self.ui.resizeWidget("cpu", 198, 132)
        self.assertEqual(self.ui._saved["widgets"]["cpu"]["size"], 132)
        self.assertEqual(self.ui._saved["widgets"]["cpu"]["title"], "")
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["title"], "pending")
        self.assertTrue(save.called)

    def test_locked_widget_cannot_resize(self):
        self.ui._saved["locked"] = True
        with patch("native_controller.save") as save:
            self.ui.resizeWidget("cpu", 200)
        save.assert_not_called()

    def test_full_grid_wraps_fits_and_never_overlaps(self):
        for index in range(18):
            self.ui.addWidget("power" if index % 2 else "cpu")
        # The previous 1000x650 case only fitted by shrinking 23 mixed-width
        # cards below their text minimum. Reject that, then verify a real fit.
        with self.assertRaises(LayoutCapacityError):
            grid_plan(windows(self.ui._draft), 1000, 650)
        specs, points = grid_plan(windows(self.ui._draft), 1280, 720)
        rects = []
        for item, (x, y) in zip(specs, points):
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + item["width"], 1280)
            self.assertLessEqual(y + item["height"], 720)
            self.assertTrue(all(cell["height"] >= 114 for cell in item["cells"]))
            current = (x, y, x + item["width"], y + item["height"])
            for prior in rects:
                self.assertFalse(
                    current[0] < prior[2]
                    and current[2] > prior[0]
                    and current[1] < prior[3]
                    and current[3] > prior[1]
                )
            rects.append(current)


class RatesAndPowerTests(unittest.TestCase):
    def test_rates_need_baseline_and_discard_resets_reconnects_and_sleep(self):
        rate = Rates()
        self.assertEqual(rate.sample({"wifi": (100, 200)}, 10)["wifi"], [None, None])
        self.assertEqual(rate.sample({"wifi": (300, 300)}, 12)["wifi"], [100, 50])
        self.assertEqual(rate.sample({"wifi": (10, 400)}, 14)["wifi"], [None, None])
        self.assertEqual(rate.sample({"wifi": (100, 500)}, 60)["wifi"], [None, None])
        rate.sample({}, 62)
        self.assertEqual(rate.sample({"wifi": (200, 800)}, 64)["wifi"], [None, None])
        self.assertEqual(rate.sample({"wifi": (200, 800)}, 66)["wifi"], [0, 0])

    def test_battery_charge_discharge_idle_unknown_and_ambiguous_direction(self):
        state = SystemBatteryState()
        state.present = 1
        state.charging = 1
        state.rate = 24000
        self.assertEqual(
            (decode(state)["battery_charge_watts"], decode(state)["battery_discharge_watts"]),
            (24, 0),
        )
        state.charging = 0
        state.discharging = 1
        state.rate = ctypes.c_uint32(-17000).value
        self.assertEqual(
            (decode(state)["battery_charge_watts"], decode(state)["battery_discharge_watts"]),
            (0, 17),
        )
        state.rate = 0
        self.assertEqual(
            (decode(state)["battery_charge_watts"], decode(state)["battery_discharge_watts"]),
            (0, 0),
        )
        state.rate = 0x80000000
        self.assertIsNone(decode(state)["battery_discharge_watts"])
        state.rate = 18000
        state.charging = 1
        self.assertIsNone(decode(state)["battery_charge_watts"])

    def test_power_from_distinct_domains_is_never_added_to_guess_total(self):
        data = {
            "battery_charge_watts": 20,
            "battery_discharge_watts": 0,
            "cpu_power": 25,
            "gpu_power": 40,
        }
        self.assertIsNone(metric_value(data, "adapter_input_watts"))
        self.assertIsNone(metric_value(data, "system_power"))

    def test_unknown_capacity_and_battery_life_are_not_huge_sentinels(self):
        state = SystemBatteryState()
        state.present = 1
        state.remaining = 0xFFFFFFFF
        state.estimated_time = 0xFFFFFFFF
        self.assertIsNone(decode(state)["battery_remaining_wh"])
        self.assertIsNone(decode(state)["battery_time_minutes"])

    def test_temperature_conversion_applies_only_to_temperature(self):
        self.assertEqual(
            display_value({"cpu_temp": 25}, "cpu_temp", {"temperature_unit": "F"})[:2], (77.0, "°F")
        )
        self.assertEqual(
            display_value({"gpu_power": 25}, "gpu_power", {"temperature_unit": "F"})[:2], (25, "W")
        )


if __name__ == "__main__":
    unittest.main()
