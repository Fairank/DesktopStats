"""Pure data contracts for selected-card RPM; no clocks, hardware or workers."""

import copy
import time
import unittest
from unittest.mock import patch

from top_bar_feedback import GPU_FAN_MAX_AGE, gpu_fan_feedback, hardware_feedback


class GpuFanFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.now = time.time()
        self.enterContext(patch("top_bar_feedback.time.time", return_value=self.now))
        for target in ("ctypes.CDLL", "ctypes.WinDLL", "subprocess.Popen", "threading.Thread.start"):
            self.enterContext(patch(target, side_effect=AssertionError("Pure feedback must not perform I/O")))

    def row(self, rpm=1500, semantics="measured", **changes):
        row = dict(gpu_fan_rpm=rpm, gpu_fan_rpm_timestamp=self.now,
                   gpu_fan_rpm_source="Synthetic tachometer", gpu_fan_rpm_semantics=semantics,
                   gpu_fan_rpm_scope="card", channel_status={"gpu_fan_rpm": {"state": "available"}})
        row.update(changes)
        return row

    def data(self, **changes):
        data = dict(gpu_fan_rpm=9999, gpu_fan_percent=100,
                    gpus={"0": self.row(1200), "1": self.row(1800)})
        data.update(changes)
        return data

    def test_measured_and_driver_current_rpm_are_distinct_accepted_sources(self):
        for semantics in ("measured", "driver_current_rpm"):
            data = dict(gpus={"0": self.row(1500.5, semantics)})
            result = gpu_fan_feedback(data, {})
            self.assertTrue(result["available"])
            self.assertEqual(result["rpm"], 1500.5)
            self.assertEqual(result["semantics"], semantics)
            self.assertEqual(result["scope"], "card")
            self.assertEqual(result["display_slowdown"], 120)
            self.assertEqual(result["timestamp"], self.now)

    def test_selected_gpu_is_exact_and_default_is_zero_without_other_card_fallback(self):
        data = self.data()
        self.assertEqual(gpu_fan_feedback(data, {})["rpm"], 1200)
        self.assertEqual(gpu_fan_feedback(data, {"gpu_target": "1"})["rpm"], 1800)
        self.assertFalse(gpu_fan_feedback(data, {"gpu_target": "missing"})["available"])
        del data["gpus"]["1"]
        self.assertFalse(gpu_fan_feedback(data, {"gpu_target": "1"})["available"])
        self.assertEqual(gpu_fan_feedback(data, {})["rpm"], 1200)

    def test_flat_chassis_rpm_or_percentage_never_substitute_a_selected_card_reading(self):
        for data in (dict(gpu_fan_rpm=1800), dict(gpu_fan_percent=80),
                     dict(gpu_fan_rpm=1800, gpus={"0": {"gpu_fan_percent": 80}}),
                     dict(gpu_fan_rpm=1800, gpus={"1": self.row(2500)})):
            result = gpu_fan_feedback(data, {})
            self.assertFalse(result["available"])
            self.assertIsNone(result["rpm"])
        for scope in ("chassis", "cooler_channel", "", None):
            result = gpu_fan_feedback(dict(gpus={"0": self.row(gpu_fan_rpm_scope=scope)}), {})
            self.assertFalse(result["available"])

    def test_intended_percent_and_unknown_semantics_are_rejected(self):
        for semantics in ("intended", "intended_rpm", "percent", "reported", "unknown", "", None):
            result = gpu_fan_feedback(dict(gpus={"0": self.row(semantics=semantics)}), {})
            self.assertFalse(result["available"])
            self.assertIsNone(result["rpm"])
            self.assertEqual(result["semantics"], "unknown")

    def test_missing_stale_future_and_explicit_stale_never_return_old_rpm(self):
        for stamp in (None, self.now-GPU_FAN_MAX_AGE-.001, self.now+1, float("nan"), float("inf"), True):
            result = gpu_fan_feedback(dict(gpus={"0": self.row(gpu_fan_rpm_timestamp=stamp)}), {})
            self.assertFalse(result["available"])
            self.assertIsNone(result["timestamp"])
        fresh = dict(gpus={"0": self.row(gpu_fan_rpm_timestamp=self.now-GPU_FAN_MAX_AGE)})
        self.assertTrue(gpu_fan_feedback(fresh, {})["available"])
        self.assertFalse(gpu_fan_feedback(self.data(), {}, stale=True)["available"])

    def test_zero_is_a_valid_stationary_reading_and_invalid_values_are_not_clamped(self):
        result = gpu_fan_feedback(dict(gpus={"0": self.row(0)}), {})
        self.assertTrue(result["available"])
        self.assertEqual(result["rpm"], 0)
        for value in (None, -1, True, "1200", float("inf"), float("nan"), 100001):
            result = gpu_fan_feedback(dict(gpus={"0": self.row(value)}), {})
            self.assertFalse(result["available"])
            self.assertIsNone(result["rpm"])

    def test_provider_failure_blank_source_and_malformed_selected_row_fail_closed(self):
        for state in ("query_failed", "unsupported", "entrypoint_missing", "invalid_value"):
            row = self.row(channel_status={"gpu_fan_rpm": {"state": state}})
            self.assertFalse(gpu_fan_feedback(dict(gpus={"0": row}), {})["available"])
        for source in ("", " ", None, 20):
            row = self.row(gpu_fan_rpm_source=source)
            self.assertFalse(gpu_fan_feedback(dict(gpus={"0": row}), {})["available"])
        for row in (None, [], "not a GPU row"):
            self.assertFalse(gpu_fan_feedback(dict(gpus={"0": row}), {})["available"])

    def test_hardware_projection_uses_selected_rpm_and_preserves_fixed_slowdown(self):
        prefs = dict(icon_effect="auto", gpu_target="1", effect_speed=2)
        data = self.data()
        original = copy.deepcopy(data)
        for load, temp, power in ((0, 0, 0), (100, 125, 300), (50, 50, 100)):
            data["gpus"]["1"].update(gpu_usage=load, gpu_temp=temp, gpu_power=power)
            for speed in (.5, 1, 2):
                prefs["effect_speed"] = speed
                result = hardware_feedback(data, "gpu_usage", prefs)
                self.assertEqual(result["fan_speed"]["rpm"], 1800)
                self.assertEqual(result["fan_speed"]["display_slowdown"], 120)
        self.assertEqual(data["gpus"]["0"], original["gpus"]["0"])
        self.assertEqual(hardware_feedback(data, "gpu_usage", dict(prefs, icon_effect="off")), {})
        stale = hardware_feedback(data, "gpu_usage", prefs, stale=True)
        self.assertFalse(stale.get("fan_speed", {}).get("available", False))
        self.assertFalse(stale["available"])

    def test_scoped_rpm_can_exist_without_unrelated_load_or_temperature(self):
        result = hardware_feedback(dict(gpus={"1": self.row(900)}), "gpu_usage",
                                   dict(icon_effect="auto", gpu_target="1"))
        self.assertTrue(result["available"])
        self.assertEqual(result["fan_speed"]["rpm"], 900)
        self.assertIsNone(result["load"])
        self.assertIsNone(result["thermal"])


if __name__ == "__main__":
    unittest.main()
