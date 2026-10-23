"""Fake psutil -> actual Sampler -> actual Controller CPU details, no hardware."""
import copy
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

import native_controller as controls
import sensors
from stats_config import DEFAULT, validate


class CpuDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.wall = 1_700_000_000.0
        self.logical = [0, 25, 100, 50]
        self.logical_calls = 0
        self.other = dict(cpu_temp=50, cpu_temp_source="Synthetic thermal provider")
        for target in ("ctypes.WinDLL", "ctypes.CDLL", "sensors.winreg.OpenKey",
                       "subprocess.Popen", "threading.Thread.start"):
            operation = self.stack.enter_context(patch(target, side_effect=AssertionError("No real hardware/window/worker")))
            self.stack.callback(operation.assert_not_called)
        self.stack.enter_context(patch("sensors.time.time", side_effect=lambda: self.wall))
        self.stack.enter_context(patch("sensors.time.monotonic", side_effect=lambda: self.wall - 1_699_999_900))
        self.stack.enter_context(patch("sensors.psutil.cpu_percent", side_effect=self.cpu_percent))
        self.stack.enter_context(patch("sensors.psutil.cpu_count", side_effect=lambda logical=True: 8 if logical else 4))
        for name, value in dict(cpu_freq=SimpleNamespace(current=3800), sensors_battery=None,
            virtual_memory=SimpleNamespace(percent=40, used=4 * 2**30, total=10 * 2**30, available=6 * 2**30),
            swap_memory=SimpleNamespace(percent=0, used=0)).items():
            self.stack.enter_context(patch("sensors.psutil." + name, return_value=value))

        def empty():
            return SimpleNamespace(read=lambda *_: {}, close=Mock())

        for name, replacement in dict(
            cpu_name=lambda: "Synthetic CPU",
            AsusTemperature=lambda: SimpleNamespace(read=lambda: dict(self.other), close=Mock()),
            AsusFans=lambda *_: SimpleNamespace(read=lambda: dict(cpu_fan_rpm=1200), sample_times={}, close=Mock()),
            CpuPackagePower=lambda: SimpleNamespace(read=lambda **_: dict(cpu_power=12.5, cpu_power_source="Synthetic meter"),
                                                     state="ready", sample_time=None, last_error="", close=Mock()),
            Battery=empty, Activity=empty, StorageHealth=lambda *_: empty(),
            ExternalEngine=lambda: SimpleNamespace(read=lambda *_: {"external_sensors": {}}, close=Mock()),
            hwinfo_registry=lambda cache=None: {}, INSPECT_UNTIL=0,
        ).items():
            self.stack.enter_context(patch.object(sensors, name, replacement))
        config = copy.deepcopy(DEFAULT)
        config.update(widget_order=["cpu"], widgets={"cpu": config["widgets"]["cpu"]})
        config["widgets"]["cpu"]["content"] = ["cpu_usage", "cpu_fan_rpm"]
        config["top_bar"]["enabled"] = True
        config["top_bar"]["items"] = [dict(id="b_cpu", metric="cpu_usage", prefs=dict(style="value"))]
        self.config = validate(config)
        self.sampler = self.make_sampler()
        with patch.object(controls, "load", return_value=self.config):
            self.ui = controls.Controller()
        self.stack.callback(self.ui.close)

    def cpu_percent(self, interval=None, percpu=False):
        if not percpu:
            return 33
        self.logical_calls += 1
        if isinstance(self.logical, BaseException):
            raise self.logical
        return copy.deepcopy(self.logical)

    def make_sampler(self):
        sampler = sensors.Sampler()
        sampler.first = False
        sampler.config_provider = lambda: self.config
        self.stack.callback(sampler.close)
        return sampler

    def sample(self):
        reading = self.sampler.sample()
        self.ui.receive(reading)
        return reading, self.ui.topBarDetailRow("b_cpu")["cpu_context"]

    def test_zero_one_real_call_source_time_and_logical_identity(self):
        before = self.logical_calls
        reading, context = self.sample()
        self.assertEqual(self.logical_calls, before + 1)
        self.assertEqual(context["source"], "Windows / psutil")
        self.assertEqual(context["api"], "psutil.cpu_percent(percpu=True)")
        self.assertEqual(context["timestamp"], self.wall)
        self.assertEqual(reading["metric_timestamps"]["cpu_per_core"], self.wall)
        self.assertEqual(context["state"], "available")
        self.assertEqual(context["logical_processors"], 4)  # Current channels, not constructor's 8.
        self.assertEqual(reading["cpu_threads"], 4)
        self.assertEqual(context["physical_cores"], 4)
        self.assertEqual([row["label"] for row in context["logical_rows"]], ["CPU 0", "CPU 1", "CPU 2", "CPU 3"])
        self.assertEqual([row["numeric_value"] for row in context["logical_rows"]], self.logical)
        self.assertEqual(context["logical_rows"][0]["value"], "0 %")
        self.assertTrue(context["logical_rows"][0]["available"])
        self.assertEqual(context["logical_rows"][2]["fraction"], 1)
        self.assertNotIn("temperature", context["logical_rows"][0])
        self.assertNotIn("power", context["logical_rows"][0])
        for _ in range(20):
            self.ui.topBarDetailRow("b_cpu")
            self.ui.topBarRows()
        self.assertEqual(self.logical_calls, before + 1)  # Reading UI never samples.

    def test_bad_channels_preserve_indices_and_missing_instead_of_clamping(self):
        self.logical = [0, -1, 101, float("nan"), float("inf"), True, "20", None, 100, 10**1000]
        reading, context = self.sample()
        self.assertEqual(reading["cpu_per_core"], [0, None, None, None, None, None, None, None, 100, None])
        self.assertEqual(context["state"], "partial")
        self.assertEqual(context["available_count"], 2)
        self.assertEqual(context["logical_processors"], 10)
        for row in context["logical_rows"][1:8]:
            self.assertFalse(row["available"])
            self.assertIsNone(row["numeric_value"])
            self.assertIsNone(row["fraction"])
            self.assertEqual(row["value"], "—")
            self.assertTrue(row["reason"])

    def test_timestamp_is_when_percpu_returns_not_the_earlier_frame_start(self):
        started = self.wall

        def delayed(interval=None, percpu=False):
            if percpu:
                self.wall += .25
                return [0, 50]
            return 33

        with patch("sensors.psutil.cpu_percent", side_effect=delayed):
            reading, context = self.sample()
        self.assertEqual(reading["time"], started)
        self.assertEqual(reading["cpu_per_core_timestamp"], started + .25)
        self.assertEqual(context["timestamp"], started + .25)
        self.assertEqual(context["state"], "available")

    def test_cpu_channel_failure_does_not_drop_other_sources_then_recovers_without_fake_zero(self):
        self.sample()
        error = OSError(13, "Synthetic private contents must not be exposed")
        error.winerror = 5
        self.logical = error
        reading, context = self.sample()
        self.assertEqual(reading["cpu_usage"], 33)
        self.assertEqual(reading["cpu_power"], 12.5)
        self.assertEqual(reading["ram_percent"], 40)
        self.assertEqual(context["state"], "unavailable")
        self.assertEqual(context["logical_rows"], [])
        self.assertIn("Win32 5", context["reason"])
        self.assertIn("psutil.cpu_percent(percpu=True)", context["reason"])
        self.assertNotIn("Synthetic private", repr(context))
        self.assertNotIn("message", reading["cpu_per_core_status"]["error"])
        self.logical = [0, 0]
        self.wall += 1
        _, baseline = self.sample()
        self.assertEqual(baseline["state"], "warming_up")
        self.assertEqual(baseline["logical_rows"], [])
        self.logical = [0, 70]
        self.wall += 1
        _, recovered = self.sample()
        self.assertEqual([row["numeric_value"] for row in recovered["logical_rows"]], [0, 70])
        self.assertEqual(recovered["state"], "available")
        self.assertEqual(recovered["reason"], "")

    def test_initial_percpu_failure_isolated_and_first_success_only_establishes_baseline(self):
        self.sampler.close()
        self.logical = OSError(5, "Synthetic initialization failure")
        self.sampler = self.make_sampler()
        self.logical = [0, 0]
        reading, context = self.sample()
        self.assertEqual(reading["cpu_usage"], 33)
        self.assertEqual(context["state"], "warming_up")
        self.assertEqual(context["logical_rows"], [])
        self.logical = [40, 60]
        _, context = self.sample()
        self.assertEqual([row["numeric_value"] for row in context["logical_rows"]], [40, 60])

    def test_independent_core_timestamp_expiration_does_not_hide_fresh_related_readings(self):
        reading, _ = self.sample()
        self.wall += 40
        reading["time"] = self.wall
        self.ui.receive(reading)
        context = self.ui.topBarDetailRow("b_cpu")["cpu_context"]
        self.assertEqual(context["state"], "stale")
        self.assertFalse(context["available"])
        self.assertTrue(all(not row["available"] and row["value"] == "—" for row in context["logical_rows"]))
        self.assertTrue(all(row["available"] for row in context["related_rows"]))
        self.assertTrue(all("过期" in row["reason"] for row in context["logical_rows"]))
        reading["cpu_per_core_timestamp"] = self.wall + 10
        self.ui.receive(reading)
        self.assertEqual(self.ui.topBarDetailRow("b_cpu")["cpu_context"]["state"], "stale")

    def test_frame_stale_and_cpu_count_change_do_not_keep_old_or_physical_core_rows(self):
        reading, _ = self.sample()
        self.wall += 40
        self.ui.receive(reading)
        context = self.ui.topBarDetailRow("b_cpu")["cpu_context"]
        self.assertFalse(context["available"])
        self.assertTrue(all(not row["available"] for row in context["related_rows"]))
        self.logical = [10, 20]
        _, context = self.sample()
        self.assertEqual(context["logical_processors"], 2)
        self.assertEqual([row["index"] for row in context["logical_rows"]], [0, 1])
        self.logical = [10, 20, 30, 40, 50, 60]
        _, context = self.sample()
        self.assertEqual(context["logical_processors"], 6)
        self.assertEqual([row["index"] for row in context["logical_rows"]], list(range(6)))

    def test_changed_logical_count_matches_scalar_generic_related_and_single_thread_item(self):
        for values in ([0, 10], [20, 30, 40, 50, 60, 70]):
            with self.subTest(count=len(values)):
                self.logical = values
                reading, context = self.sample()
                self.assertEqual(reading["cpu_threads"], len(values))
                self.assertEqual(context["logical_processors"], len(values))
                related = next(row for row in self.ui.topBarDetailRow("b_cpu")["related"]
                               if row["metric"] == "cpu_threads")
                self.assertEqual(related["value"], str(len(values)))
                self.ui._saved["top_bar"]["items"][0]["metric"] = "cpu_threads"
                try:
                    detail = self.ui.topBarDetailRow("b_cpu")
                    self.assertEqual(detail["value"], str(len(values)))
                    self.assertEqual(detail["cpu_context"]["logical_processors"], len(values))
                finally:
                    self.ui._saved["top_bar"]["items"][0]["metric"] = "cpu_usage"
        self.logical = OSError(5, "Synthetic unavailable logical channels")
        reading, context = self.sample()
        self.assertEqual(reading["cpu_threads"], self.sampler.threads)
        self.assertEqual(context["logical_processors"], self.sampler.threads)
        self.assertEqual(context["logical_rows"], [])

    def test_cpu_family_context_is_on_demand_and_related_values_keep_unit_and_absence(self):
        self.sample()
        self.assertNotIn("cpu_context", self.ui.topBarRows()[0])
        self.assertNotIn("cpu_context", self.ui.topBarStylePreviewRow("b_cpu"))
        for metric in ("cpu_usage", "cpu_temp", "cpu_power", "cpu_frequency", "cpu_cores", "cpu_threads"):
            self.ui._saved["top_bar"]["items"][0]["metric"] = metric
            self.ui._saved["top_bar"]["items"][0]["prefs"]["temperature_unit"] = "F"
            context = self.ui.topBarDetailRow("b_cpu")["cpu_context"]
            related = {row["metric"]: row for row in context["related_rows"]}
            self.assertEqual(related["cpu_temp"]["value"], "122 °F")
            self.assertEqual(related["cpu_frequency"]["value"], "3.80 GHz")
            self.assertEqual(related["cpu_power"]["value"], "12.5 W")
            self.assertEqual(related["cpu_fan_rpm"]["value"], "1200 RPM")
        self.ui._data.pop("cpu_fan_rpm")
        context = self.ui.topBarDetailRow("b_cpu")["cpu_context"]
        missing = next(row for row in context["related_rows"] if row["metric"] == "cpu_fan_rpm")
        self.assertFalse(missing["available"])
        self.assertEqual(missing["value"], "—")
        self.assertTrue(missing["reason"])

    def test_bounded_rows_explicit_truncation_and_invalid_full_sequence(self):
        self.logical = [0] * 1025
        _, context = self.sample()
        self.assertEqual(context["logical_processors"], 1025)
        self.assertEqual(context["available_count"], 1025)
        self.assertEqual(context["displayed_count"], 1024)
        self.assertTrue(context["truncated"])
        self.assertEqual(context["logical_rows"][-1]["index"], 1023)
        for invalid in ([0] * 4097, [], None, 42, "0,40"):
            with self.subTest(kind=type(invalid).__name__):
                self.logical = invalid
                _, context = self.sample()
                self.assertFalse(context["available"])
                self.assertEqual(context["logical_rows"], [])
                self.assertTrue(context["reason"])

    def test_not_requested_skips_the_existing_query_and_reentry_does_not_report_old_usage(self):
        self.sample()
        self.config["visible"] = False
        self.config["top_bar"]["enabled"] = False
        before = self.logical_calls
        reading, context = self.sample()
        self.assertEqual(self.logical_calls, before)
        self.assertEqual(reading["cpu_per_core"], [])
        self.assertEqual(context["state"], "not_requested")
        self.config["top_bar"]["enabled"] = True
        _, context = self.sample()
        self.assertEqual(context["state"], "warming_up")
        _, context = self.sample()
        self.assertEqual(context["state"], "available")

    def test_programming_errors_are_not_misreported_as_expected_api_failures(self):
        self.logical = TypeError("Synthetic programming defect")
        with self.assertRaises(TypeError):
            self.sampler.sample()


if __name__ == "__main__":
    unittest.main()
