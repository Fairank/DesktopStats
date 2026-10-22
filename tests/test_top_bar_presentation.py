"""Pure display/trend contracts; no collectors, Qt or native calls."""

import copy
import math
import sys
import unittest

from top_bar_layout import DISPLAY_STYLES, LayoutError, metric_icon, present_metric


def reading(history=(), *, available=True, unit="W"):
    return dict(id="b_one", metric="cpu_power", label="CPU power", value="24 W",
                unit=unit, available=available, history=list(history))


class TopBarPresentationTests(unittest.TestCase):
    def test_legacy_defaults_preserve_reading(self):
        source = reading([10, 20])
        result = present_metric(source)
        self.assertEqual((result["style"], result["placement"], result["icon"]),
                         ("label_value", "right", "power"))
        self.assertEqual(result["value"], source["value"])

    def test_all_styles_and_placements_are_exact(self):
        for style in DISPLAY_STYLES:
            for placement in ("left", "right"):
                result = present_metric(reading([10, 20]), dict(style=style, placement=placement))
                self.assertEqual((result["style"], result["placement"]), (style, placement))
        for prefs in ({"style": "unsupported"}, {"placement": "center"}):
            with self.assertRaises(LayoutError):
                present_metric(reading(), prefs)

    def test_icons_use_existing_vector_names(self):
        expected = {"cpu_temp":"temperature", "gpu_power":"power", "vram_percent":"memory",
                    "ram_percent":"memory", "swap_used":"memory", "battery_rate":"battery",
                    "net_upload":"upload", "disk_write":"disk_write", "volume_used":"disk",
                    "storage_temp":"temperature", "external_1":"sensors"}
        self.assertEqual({metric:metric_icon(metric) for metric in expected}, expected)

    def test_measured_quantity_wins_over_cpu_gpu_and_other_device_prefixes(self):
        for device in ("cpu", "gpu", "battery", "disk", "system", "network"):
            for quantity, icon in (("fan_rpm", "fan"), ("fan_noise_db", "noise"),
                                   ("temperature", "temperature"), ("power", "power"),
                                   ("voltage", "voltage"), ("frequency", "frequency")):
                with self.subTest(device=device, quantity=quantity):
                    self.assertEqual(metric_icon(device + "_" + quantity), icon)
        self.assertEqual(metric_icon("CPU_FAN_RPM"), "fan")

    def test_direction_and_family_icons_keep_their_actual_meaning(self):
        expected = {"net_download":"download", "net_received_gb":"download",
                    "net_upload":"upload", "net_sent_gb":"upload",
                    "disk_read":"disk_read", "disk_write":"disk_write",
                    "battery_time_minutes":"time", "battery_charge_watts":"power",
                    "adapter_input_watts":"power", "system_power":"power",
                    "gpu_memory_clock":"frequency", "vram_total_gb":"memory",
                    "cpu_fan_noise_dba":"noise"}
        self.assertEqual({metric:metric_icon(metric) for metric in expected}, expected)
        for metric in ("", "external_1", "unknown", "cpufake", "gpuish", "networkish"):
            with self.subTest(metric=metric):
                self.assertEqual(metric_icon(metric), "sensors")

    def test_every_registered_metric_has_a_reviewed_quantity_or_family_icon(self):
        from metrics import METRICS

        groups = {
            "temperature": ("cpu_temp", "gpu_temp", "storage_temp"),
            "cpu": ("cpu_usage", "cpu_cores", "cpu_threads"),
            "gpu": ("gpu_usage",),
            "frequency": ("cpu_frequency", "gpu_clock", "gpu_memory_clock"),
            "power": ("cpu_power", "gpu_power", "gpu_asic_power", "battery_watts",
                      "battery_charge_watts", "battery_discharge_watts", "adapter_input_watts",
                      "system_power"),
            "fan": ("gpu_fan_percent", "cpu_fan_rpm", "gpu_fan_rpm", "system_fan_rpm"),
            "memory": ("ram_percent", "ram_used_gb", "ram_available_gb", "ram_total_gb",
                       "swap_percent", "swap_used_gb", "vram_gb", "vram_total_gb", "vram_percent"),
            "battery": ("battery_percent", "battery_remaining_wh"),
            "voltage": ("voltage",),
            "time": ("battery_time_minutes",),
            "download": ("net_download", "net_received_gb"),
            "upload": ("net_upload", "net_sent_gb"),
            "disk_read": ("disk_read",),
            "disk_write": ("disk_write",),
            "disk": ("disk_percent", "disk_used_gb", "disk_free_gb", "disk_total_gb",
                     "storage_spare_percent", "storage_wear_percent"),
            "sensors": ("external_1", "external_2", "external_3", "external_4", "external_5", "external_6"),
        }
        expected = {metric:icon for icon, metrics in groups.items() for metric in metrics}
        self.assertEqual(set(expected), set(METRICS))
        self.assertEqual({metric:metric_icon(metric) for metric in METRICS}, expected)

    def test_history_is_latest_forty_without_filling_gaps(self):
        result = present_metric(reading(range(50)))
        self.assertEqual(result["trend"], list(range(10, 50)))
        self.assertEqual(len(result["trend_points"]), 40)
        self.assertEqual(result["trend_points"][0]["x"], 0)
        self.assertEqual(result["trend_points"][-1]["x"], 1)

    def test_zero_valid_and_invalid_values_break_the_line(self):
        result = present_metric(reading([0, None, True, float("nan"), float("inf"), 1, 2]))
        self.assertEqual(result["trend"], [0, None, None, None, None, 1, 2])
        self.assertIsNone(result["trend_points"][1])
        self.assertTrue(result["trend_available"])
        separated = present_metric(reading([1, None, 2]))
        self.assertFalse(separated["trend_available"])

    def test_unavailable_current_reading_never_reuses_old_history(self):
        for reason in ("stale", "failed", "not available"):
            source = dict(reading([1,2,3], available=False), reason=reason, value="—")
            result = present_metric(source, {"style":"trend_value"})
            self.assertEqual(result["trend"], [])
            self.assertEqual(result["trend_points"], [])
            self.assertFalse(result["trend_available"])
            self.assertIsNone(result["trend_min"])
            self.assertEqual(result["value"], "—")

    def test_percentage_fixed_scale_and_other_units_auto_range(self):
        percent = present_metric(reading([25,75], unit="%"))
        self.assertEqual((percent["trend_min"], percent["trend_max"]), (0,100))
        self.assertEqual([point["y"] for point in percent["trend_points"]], [.75,.25])
        temperature = present_metric(reading([59,77], unit="°F"))
        self.assertEqual((temperature["trend_min"], temperature["trend_max"]), (59,77))
        self.assertEqual([point["y"] for point in temperature["trend_points"]], [1,0])

    def test_constant_single_and_empty_history_are_honest(self):
        constant = present_metric(reading([24,24,24]))
        self.assertTrue(constant["trend_available"])
        self.assertEqual([point["y"] for point in constant["trend_points"]], [.5,.5,.5])
        for history in ([], [1], [None], "123", None):
            source = reading()
            source["history"] = history
            result = present_metric(source)
            self.assertFalse(result["trend_available"])

    def test_tiny_and_extreme_finite_values_have_finite_points(self):
        for history in ([0,5e-324], [-sys.float_info.max,0,sys.float_info.max], [10**5000,0,1]):
            result = present_metric(reading(history))
            for point in result["trend_points"]:
                if point is not None:
                    self.assertTrue(math.isfinite(point["x"]) and math.isfinite(point["y"]))
                    self.assertTrue(0 <= point["x"] <= 1 and 0 <= point["y"] <= 1)

    def test_no_input_mutation_or_accumulation_across_rows(self):
        first = reading([10,20])
        before = copy.deepcopy(first)
        first_result = present_metric(first, {"style":"trend_value"})
        self.assertEqual(first, before)
        second_result = present_metric(reading([100,200]))
        self.assertEqual(first_result["trend"], [10,20])
        self.assertEqual(second_result["trend"], [100,200])


if __name__ == "__main__":
    unittest.main()
