"""Actual cached PDH -> Sampler -> local history, with synthetic APIs only."""
import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sensors
from energy_sensor import SOURCE, CpuPackagePower
from history_store import HistoryStore
from stats_config import DEFAULT, validate

BASE = 1_700_000_040


class Counter:
    def __init__(self):
        self.values = 0
        self.failure = False

    def open(self):
        return 1, 2

    def collect(self, _query):
        if self.failure:
            raise OSError("Synthetic unavailable counter")

    def value(self, _counter):
        self.values += 1
        return 100_000 if self.values == 1 else 0

    def close(self, _query):
        pass


class HistorySamplingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="synthetic-pdh-history-"))
        self.now = 0.0
        self.wall = float(BASE)
        self.asus_reading = {}
        self.extra = sensors.RegistryReadings()
        self.api = Counter()
        self.stack.enter_context(patch("energy_sensor.time.time", side_effect=lambda: self.wall))
        self.stack.enter_context(patch("sensors.time.monotonic", side_effect=lambda: self.now))
        self.power = CpuPackagePower(api=self.api, clock=lambda: self.now)
        self.stack.callback(self.power.close)
        self.native = self.stack.enter_context(patch("ctypes.WinDLL", side_effect=AssertionError("No native DLL")))
        self.library = self.stack.enter_context(patch("ctypes.CDLL", side_effect=AssertionError("No native library")))
        self.process = self.stack.enter_context(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.worker = self.stack.enter_context(patch("threading.Thread.start", side_effect=AssertionError("No worker")))
        def empty():
            return SimpleNamespace(read=lambda *_: {}, close=lambda: None)
        replacements = dict(
            CpuPackagePower=lambda: self.power,
            AsusTemperature=lambda: SimpleNamespace(read=lambda: dict(self.asus_reading), close=lambda: None),
            AsusFans=lambda *_: SimpleNamespace(read=lambda: {}, sample_times={}, close=lambda: None),
            Battery=empty, Activity=empty, StorageHealth=lambda *_: empty(),
            ExternalEngine=lambda: SimpleNamespace(read=lambda *_: {"external_sensors": {}}, close=lambda: None),
            hwinfo_registry=lambda cache=None: self.extra, cpu_name=lambda: "Synthetic CPU", INSPECT_UNTIL=0)
        for name, value in replacements.items():
            self.stack.enter_context(patch.object(sensors, name, value))
        for name, value in dict(cpu_count=8, cpu_percent=25, cpu_freq=None, sensors_battery=None,
            virtual_memory=SimpleNamespace(percent=50, used=8 * 2**30, total=16 * 2**30, available=8 * 2**30),
            swap_memory=SimpleNamespace(percent=0, used=0)).items():
            self.stack.enter_context(patch("sensors.psutil." + name, return_value=value))
        config = copy.deepcopy(DEFAULT)
        config.update(refresh=.01, widget_order=["cpu"], widgets={"cpu": config["widgets"]["cpu"]})
        config["widgets"]["cpu"]["content"] = ["cpu_power"]
        config["top_bar"]["enabled"] = False
        self.config = validate(config)
        self.sampler = sensors.Sampler()
        self.stack.callback(self.sampler.close)
        self.sampler.first = False
        self.sampler.config_provider = lambda: self.config
        self.history = HistoryStore(Path(self.folder) / "history.sqlite3", metrics=("cpu_power",), scopes=(),
                                    clock=lambda: self.now, wall_clock=lambda: self.wall)
        self.stack.callback(self.history.close)

    def sample(self, now):
        self.now, self.wall = now, BASE + now
        reading = self.sampler.sample()
        self.history.record(reading)
        return reading

    def test_cached_power_is_one_independent_observation_and_does_not_bias_the_mean(self):
        readings = [self.sample(now) for now in (0, .05, .06, .07, .08, .09, .11)]
        self.assertEqual(self.api.values, 2)
        result = self.history.query("cpu_power", end=BASE + 1)["summary"]
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["mean"], 50)
        self.assertEqual((result["minimum"], result["peak"], result["latest"]), (0, 100, 0))
        self.assertEqual([row["metric_timestamps"]["cpu_power"] for row in readings[1:-1]], [BASE + .05] * 5)
        self.assertEqual(readings[-1]["metric_timestamps"]["cpu_power"], BASE + .11)
        self.native.assert_not_called()
        self.library.assert_not_called()
        self.process.assert_not_called()
        self.worker.assert_not_called()

    def test_power_timestamp_clears_on_failure_sleep_clock_reset_and_close(self):
        self.sample(0)
        self.sample(.05)
        self.assertEqual(self.power.sample_time, BASE + .05)
        self.api.failure = True
        failed = self.sample(.11)
        self.assertIsNone(self.power.sample_time)
        self.assertNotIn("cpu_power", failed["metric_timestamps"])
        self.api.failure = False
        self.sample(61)
        self.assertIsNone(self.power.sample_time)
        self.sample(61.1)
        self.assertEqual(self.power.sample_time, BASE + 61.1)
        self.sample(92.2)
        self.assertIsNone(self.power.sample_time)
        self.sample(92.3)
        self.sample(92.1)
        self.assertIsNone(self.power.sample_time)
        self.power.close()
        self.assertIsNone(self.power.sample_time)

    def test_replacement_source_never_inherits_a_pdh_timestamp_even_at_the_same_value(self):
        self.sample(0)
        self.asus_reading = dict(cpu_power=100, cpu_power_source="Synthetic replacement")
        replaced = self.sample(.05)
        self.assertEqual(replaced["cpu_power"], 100)
        self.assertEqual(replaced["metric_sources"]["cpu_power"], "Synthetic replacement")
        self.assertNotIn("cpu_power", replaced["metric_timestamps"])
        self.asus_reading = {}
        pdh = self.sample(.06)
        self.assertEqual(pdh["metric_sources"]["cpu_power"], SOURCE)
        self.assertEqual(pdh["metric_timestamps"]["cpu_power"], BASE + .05)

    def test_hwinfo_fallback_preserves_its_own_observation_time(self):
        self.extra["cpu_power"] = 43.2
        self.extra.sample_times["cpu_power"] = BASE - 2
        reading = self.sample(0)
        self.assertEqual(reading["cpu_power"], 43.2)
        self.assertEqual(reading["metric_sources"]["cpu_power"], "HWiNFO VSB")
        self.assertEqual(reading["metric_timestamps"]["cpu_power"], BASE - 2)
        self.assertIsNone(self.power.sample_time)

    def test_hwinfo_fallback_never_borrows_a_previous_pdh_observation_timestamp(self):
        self.sample(0)
        self.sample(.05)
        self.config["refresh"] = .05  # A rapid non-cached read returns no new PDH value.
        self.extra["cpu_power"] = 100
        self.extra.sample_times["cpu_power"] = BASE - .5
        reading = self.sample(.06)
        self.assertEqual(self.power.sample_time, BASE + .05)
        self.assertEqual(reading["cpu_power"], 100)
        self.assertEqual(reading["metric_sources"]["cpu_power"], "HWiNFO VSB")
        self.assertEqual(reading["metric_timestamps"]["cpu_power"], BASE - .5)


if __name__ == "__main__":
    unittest.main()
