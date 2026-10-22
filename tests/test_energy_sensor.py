"""CPU package counter behavior without touching real hardware."""

import math
import unittest
from unittest.mock import patch

from energy_sensor import COUNTER_PATH, SOURCE, CpuPackagePower, _Pdh


class FakePdh:
    def __init__(self):
        self.opens = 0
        self.collections = 0
        self.closes = []
        self.value_reads = 0
        self.milliwatts = 43200.0
        self.failure = None

    def open(self):
        self.opens += 1
        if self.failure == "open":
            raise OSError("No matching package channel")
        return self.opens, self.opens + 100

    def collect(self, query):
        self.collections += 1
        if self.failure == "collect":
            raise OSError("Counter unavailable")

    def value(self, counter):
        self.value_reads += 1
        if self.failure == "value":
            raise OSError("Invalid sample status")
        return self.milliwatts

    def close(self, query):
        self.closes.append(query)


class EnergySensorTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.api = FakePdh()
        self.sensor = CpuPackagePower(api=self.api, clock=lambda: self.now)

    def tearDown(self):
        self.sensor.close()

    def advance(self, seconds=2):
        self.now += seconds
        return self.sensor.read()

    def test_exact_package_channel_does_not_sum_cores_or_total(self):
        self.assertEqual(COUNTER_PATH, r"\Energy Meter(RAPL_Package0_PKG)\Power")

    def test_first_sample_is_baseline_then_milliwatts_convert_to_watts(self):
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.api.value_reads, 0)
        self.assertEqual(self.advance(), {"cpu_power": 43.2, "cpu_power_source": SOURCE})
        self.assertEqual(self.sensor.state, "ready")

    def test_rapid_repeat_never_reuses_a_previous_value(self):
        self.sensor.read()
        self.advance()
        collections = self.api.collections
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.api.collections, collections)

    def test_sleep_resume_requires_a_new_baseline(self):
        self.sensor.read()
        self.advance()
        self.assertEqual(self.advance(31), {})
        self.assertEqual(self.sensor.state, "warming_up")
        self.assertEqual(self.advance()["cpu_power"], 43.2)

    def test_clock_reset_requires_a_new_baseline(self):
        self.sensor.read()
        self.assertEqual(self.advance(-1), {})
        self.assertEqual(self.advance()["cpu_power"], 43.2)

    def test_missing_channel_retries_after_backoff(self):
        self.api.failure = "open"
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.sensor.state, "unavailable")
        self.assertIn("package", self.sensor.last_error)
        self.advance(59)
        self.assertEqual(self.api.opens, 1)
        self.api.failure = None
        self.assertEqual(self.advance(1), {})
        self.assertEqual(self.api.opens, 2)
        self.assertEqual(self.advance()["cpu_power"], 43.2)

    def test_initial_collect_failure_releases_open_query(self):
        self.api.failure = "collect"
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.api.closes, [1])

    def test_running_read_failure_drops_value_and_releases_query(self):
        self.sensor.read()
        self.advance()
        self.api.failure = "value"
        self.assertEqual(self.advance(), {})
        self.assertEqual(self.api.closes, [1])
        self.assertEqual(self.sensor.state, "unavailable")
        self.api.failure = None
        self.assertEqual(self.advance(60), {})
        self.assertEqual(self.advance()["cpu_power"], 43.2)

    def test_zero_is_valid_and_not_missing(self):
        self.sensor.read()
        self.api.milliwatts = 0.0
        self.assertEqual(self.advance()["cpu_power"], 0.0)

    def test_invalid_values_do_not_escape(self):
        for value in (math.nan, math.inf, -1, 2_000_001, None, "43W"):
            with self.subTest(value=value):
                api = FakePdh()
                sensor = CpuPackagePower(api=api, clock=lambda: self.now)
                sensor.read()
                api.milliwatts = value
                self.now += 2
                self.assertEqual(sensor.read(), {})
                self.assertEqual(api.closes, [1])
                sensor.close()

    def test_close_is_idempotent_and_does_not_reopen(self):
        self.sensor.read()
        self.sensor.close()
        self.sensor.close()
        self.assertEqual(self.advance(100), {})
        self.assertEqual(self.api.closes, [1])
        self.assertEqual(self.api.opens, 1)
        self.assertEqual(self.sensor.state, "closed")

    def test_close_without_open_is_safe(self):
        self.sensor.close()
        self.assertEqual(self.api.closes, [])
        self.assertEqual(self.sensor.read(), {})


class NativePdhWrapperTests(unittest.TestCase):
    """Exercise status handling and resource ownership at the native boundary."""

    @staticmethod
    def library():
        class Function:
            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        class Library:
            def __init__(self):
                self.closed = []
                self.paths = []
                self.formats = []
                self.add_status = self.sample_status = self.call_status = 0
                self.PdhOpenQueryW = Function(self.open)
                self.PdhAddEnglishCounterW = Function(self.add)
                self.PdhCollectQueryData = Function(lambda _: self.call_status)
                self.PdhGetFormattedCounterValue = Function(self.formatted)
                self.PdhCloseQuery = Function(lambda query: self.closed.append(query.value) or 0)

            @staticmethod
            def open(name, user, output):
                output._obj.value = 123
                return 0

            def add(self, query, path, user, output):
                self.paths.append(path)
                output._obj.value = 456
                return self.add_status

            def formatted(self, counter, format_flags, type_output, output):
                self.formats.append(format_flags)
                output._obj.status = self.sample_status
                output._obj.value = 43200.5
                return self.call_status

        return Library()

    def test_english_counter_and_double_format_keep_full_power(self):
        lib = self.library()
        with patch("energy_sensor.c.WinDLL", return_value=lib):
            api = _Pdh()
        query, counter = api.open()
        api.collect(query)
        self.assertEqual(api.value(counter), 43200.5)
        self.assertEqual(lib.paths, [COUNTER_PATH])
        self.assertEqual(lib.formats, [0x8200])
        api.close(query)
        self.assertEqual(lib.closed, [123])

    def test_add_counter_failure_closes_owned_query(self):
        lib = self.library()
        lib.add_status = -1073738824
        with patch("energy_sensor.c.WinDLL", return_value=lib):
            api = _Pdh()
        with self.assertRaises(OSError):
            api.open()
        self.assertEqual(lib.closed, [123])

    def test_bad_status_is_never_treated_as_a_reading(self):
        lib = self.library()
        with patch("energy_sensor.c.WinDLL", return_value=lib):
            api = _Pdh()
        query, counter = api.open()
        for sample_status in (0, 1):
            lib.sample_status = sample_status
            self.assertEqual(api.value(counter), 43200.5)
        lib.sample_status = 0xC0000BC6
        with self.assertRaises(OSError):
            api.value(counter)
        lib.call_status = -1073738824
        with self.assertRaises(OSError):
            api.collect(query)
        with self.assertRaises(OSError):
            api.value(counter)
        api.close(query)


if __name__ == "__main__":
    unittest.main()
