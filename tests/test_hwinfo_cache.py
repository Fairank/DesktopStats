"""Unchanged VSB exports avoid repeated enumeration without refreshing their age."""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import sensors


class HwinfoCacheTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.updated = 1000.0
        self.values = {f"{name}{index}": value for index in range(200) for name, value in (
            ("Sensor", "CPU [#0] Synthetic"), ("Label", "CPU Package Power"),
            ("ValueRaw", "43.8"), ("Value", "43.8 W"))}
        self.entries = lambda: list(self.values.items())
        self.signature = lambda: (0, len(self.values), int((self.updated + 11644473600) * 1e7))
        self.denied = False
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        def open_key(hive, _path):
            if hive == sensors.winreg.HKEY_LOCAL_MACHINE:
                raise FileNotFoundError()
            if self.denied:
                raise PermissionError(13, "Synthetic private exception content")
            return Key()

        self.stack.enter_context(patch("sensors.winreg.OpenKey", side_effect=open_key))
        self.info = self.stack.enter_context(patch("sensors.winreg.QueryInfoKey", side_effect=lambda _: self.signature()))
        self.enum = self.stack.enter_context(patch("sensors.winreg.EnumValue", side_effect=lambda _, i: (*self.entries()[i], 1)))
        self.stack.enter_context(patch("sensors.time.time", side_effect=lambda: self.now))
        self.cache = {}

    def test_hundred_samples_enumerate_unchanged_export_only_once_and_keep_original_time(self):
        for index in range(100):
            self.now = 1000 + index / 100
            reading = sensors.hwinfo_registry(self.cache)
            self.assertEqual(reading["cpu_power"], 43.8)
            self.assertEqual(reading.sample_times["cpu_power"], 1000.0)
        self.assertEqual(self.enum.call_count, 800)
        self.assertEqual(self.info.call_count, 101)

    def test_new_filetime_parses_fresh_values_and_removed_channels_disappear(self):
        sensors.hwinfo_registry(self.cache)
        self.updated = self.now = 1001
        self.values = dict(Sensor0="CPU", Label0="CPU Package Power", ValueRaw0="0", Value0="0 W")
        reading = sensors.hwinfo_registry(self.cache)
        self.assertEqual(reading["cpu_power"], 0)
        self.assertEqual(reading.sample_times["cpu_power"], 1001)
        self.updated = self.now = 1002
        self.values = {}
        self.assertNotIn("cpu_power", sensors.hwinfo_registry(self.cache))

    def test_cache_does_not_override_stale_future_or_unreadable_export(self):
        sensors.hwinfo_registry(self.cache)
        for now, expected in ((1031, "stale"), (999, "future_timestamp")):
            self.now = now
            reading = sensors.hwinfo_registry(self.cache)
            self.assertEqual(reading, {})
            self.assertEqual(reading.diagnostics["state"], expected)
        self.now = 1001
        self.denied = True
        reading = sensors.hwinfo_registry(self.cache)
        self.assertEqual(reading, {})
        self.assertEqual(reading.diagnostics["state"], "query_failed")
        self.assertNotIn("HKCU", self.cache)
        self.denied = False
        self.assertEqual(sensors.hwinfo_registry(self.cache)["cpu_power"], 43.8)
        self.assertEqual(self.enum.call_count, 1600)

    def test_returned_readings_and_diagnostics_cannot_poison_next_sample(self):
        self.values["ValueRaw0"] = "invalid"
        first = sensors.hwinfo_registry(self.cache)
        before = copy.deepcopy(first.diagnostics)
        first["cpu_power"] = -100
        first.diagnostics["channel_errors"][0]["reason"] = "altered"
        later = sensors.hwinfo_registry(self.cache)
        self.assertEqual(later["cpu_power"], 43.8)
        self.assertEqual(later.diagnostics, before)

    def test_export_changed_mid_enumeration_is_discarded_and_retried(self):
        original = self.signature()
        changed = (original[0], original[1], original[2] + 1)
        self.info.side_effect = [original, changed]
        reading = sensors.hwinfo_registry(self.cache)
        self.assertEqual(reading, {})
        self.assertEqual(reading.diagnostics["state"], "query_failed")
        self.assertNotIn("HKCU", self.cache)
        self.info.side_effect = lambda _: self.signature()
        self.assertEqual(sensors.hwinfo_registry(self.cache)["cpu_power"], 43.8)


if __name__ == "__main__":
    unittest.main()
