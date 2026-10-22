"""High-frequency requests keep sensor baselines and bounded file writes."""

import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/sampling-unit-data")
)

import sensors
from activity_sensors import Rates
from energy_sensor import SOURCE, CpuPackagePower


class Counter:
    def __init__(self):
        self.count = 0
        self.failure = False

    def open(self):
        return 1, 2

    def collect(self, query):
        self.count += 1
        if self.failure:
            raise OSError("counter disconnected")

    def value(self, counter):
        return 43200

    def close(self, query):
        pass


class FastSamplingTests(unittest.TestCase):
    def test_ten_millisecond_network_and_disk_deltas_are_not_permanently_missing(self):
        rates = Rates()
        self.assertEqual(rates.sample({"device": (0, 0)}, 10)["device"], [None, None])
        for index in range(1, 101):
            value = rates.sample({"device": (index * 100, index * 50)}, 10 + index / 100)
            self.assertAlmostEqual(value["device"][0], 10000)
            self.assertAlmostEqual(value["device"][1], 5000)
        self.assertEqual(rates.sample({"device": (0, 0)}, 11.01)["device"], [None, None])
        self.assertEqual(rates.sample({"device": (100, 50)}, 45)["device"], [None, None])

    def test_fast_power_requests_hold_only_a_recent_successful_sensor_value(self):
        now = [10.0]
        api = Counter()
        power = CpuPackagePower(api=api, clock=lambda: now[0])
        self.addCleanup(power.close)
        self.assertEqual(power.read(allow_cached=True), {})
        now[0] += 0.06
        expected = {"cpu_power": 43.2, "cpu_power_source": SOURCE}
        self.assertEqual(power.read(allow_cached=True), expected)
        collected = api.count
        for _ in range(4):
            now[0] += 0.01
            sample = power.read(allow_cached=True)
            self.assertEqual(sample, expected)
            sample["cpu_power"] = -1
        self.assertEqual(api.count, collected)
        now[0] += 0.02
        api.failure = True
        self.assertEqual(power.read(allow_cached=True), {})
        self.assertEqual(power.state, "unavailable")
        now[0] += 0.01
        self.assertEqual(power.read(allow_cached=True), {})

    def test_power_warmup_resume_and_close_never_keep_a_cached_value(self):
        now = [10.0]
        power = CpuPackagePower(api=Counter(), clock=lambda: now[0])
        self.assertEqual(power.read(allow_cached=True), {})
        now[0] += 0.01
        self.assertEqual(power.read(allow_cached=True), {})
        now[0] += 0.1
        self.assertIn("cpu_power", power.read(allow_cached=True))
        now[0] += 31
        self.assertEqual(power.read(allow_cached=True), {})
        now[0] += 0.01
        self.assertEqual(power.read(allow_cached=True), {})
        power.close()
        self.assertEqual(power.read(allow_cached=True), {})

    def test_file_exports_are_throttled_but_actual_sample_dictionary_is_not_modified(self):
        sampler = sensors.Sampler.__new__(sensors.Sampler)
        data = {"time": 1, "cpu_usage": 20}
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("sensors.BASE", Path(directory)),
            patch("sensors.time.monotonic") as clock,
            patch("sensors.view", side_effect=lambda reading: str(reading["time"])),
        ):
            clock.return_value = 10
            sampler.write(data)
            path = Path(directory) / "latest.json"
            initial = path.read_bytes()
            clock.return_value = 10.01
            sampler.write({"time": 2, "cpu_usage": 50})
            self.assertEqual(path.read_bytes(), initial)
            clock.return_value = 10.25
            sampler.write({"time": 3, "cpu_usage": 70})
            self.assertNotEqual(path.read_bytes(), initial)
        self.assertEqual(data, {"time": 1, "cpu_usage": 20})

    def test_rate_clock_reversal_or_duplicate_timestamp_does_not_emit_infinity(self):
        rates = Rates()
        rates.sample({"device": (100, 100)}, 10)
        for stamp in (10, 9, 9):
            values = rates.sample({"device": (200, 300)}, stamp)["device"]
            self.assertTrue(all(v is None or math.isfinite(v) for v in values))
            self.assertEqual(values, [None, None])


if __name__ == "__main__":
    unittest.main()
