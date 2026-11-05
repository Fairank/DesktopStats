"""ASUS bridge freshness, identity and load limits, without native access."""

import struct
import unittest
from unittest.mock import patch

from cpu_temperature import API, MAGIC, SENSOR_ID, SOURCE, AsusCpuTemperature, is_requested

WALL = 1_700_000_000.0


def snapshot(*, raw=485, stamp=WALL, state=1, result=0, sensor=SENSOR_ID,
             app_pid=123, seq=2, magic=MAGIC, schema=1, helper_pid=456):
    return struct.pack("<7IiqI20x", magic, schema, seq, state, helper_pid,
                       sensor, raw, result, int(stamp * 1000), app_pid)


class Memory:
    def __init__(self):
        self.value = snapshot()
        self.error = None
        self.reads = self.closes = 0

    def read(self):
        self.reads += 1
        if self.error:
            raise self.error
        return self.value

    def close(self):
        self.closes += 1


class CpuTemperatureTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.wall = 10.0, WALL
        self.memory = Memory()
        self.sensor = AsusCpuTemperature(api=self.memory, app_pid=123, enabled=True,
                                         clock=lambda: self.clock, wall_clock=lambda: self.wall)
        self.addCleanup(self.sensor.close)

    def advance(self, seconds=2):
        self.clock += seconds
        self.wall += seconds
        return self.sensor.read()

    def test_exact_asus_cpu_tenths_and_observation_time(self):
        self.assertEqual(self.sensor.read(), {"cpu_temp": 48.5, "cpu_temp_source": SOURCE})
        self.assertEqual(self.sensor.sample_time, WALL)
        self.assertEqual(self.sensor.status(True)["state"], "ready")

    def test_fast_sampling_does_not_add_reads_or_invent_source_timestamps(self):
        self.sensor.read()
        for _ in range(100):
            self.advance(0.01)
        self.assertEqual(self.memory.reads, 1)
        self.assertEqual(self.sensor.sample_time, WALL)
        self.advance(2)
        self.assertEqual(self.memory.reads, 2)
        self.assertEqual(self.sensor.sample_time, WALL)

    def test_old_or_future_values_are_cleared(self):
        for stamp in (WALL - 8.001, WALL + 0.001):
            with self.subTest(stamp=stamp):
                self.memory.value = snapshot(stamp=stamp)
                self.clock += 2
                self.assertEqual(self.sensor.read(), {})
                self.assertIsNone(self.sensor.sample_time)
                self.assertEqual(self.sensor.state, "stale")

    def test_cache_expiry_is_checked_before_poll_throttle(self):
        self.sensor.read()
        self.wall += 10
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.sensor.state, "stale")

    def test_a_snapshot_published_during_read_is_not_mistaken_for_future_data(self):
        def read():
            self.wall += 0.01
            return snapshot(stamp=self.wall)
        self.memory.read = read
        self.assertEqual(self.sensor.read()["cpu_temp"], 48.5)

    def test_default_cpu_widget_and_grouped_top_bar_request_temperature(self):
        config = {"widgets": {"cpu": {"enabled": True, "content": None, "primary": "temp"}}}
        self.assertTrue(is_requested(config))
        config["visible"] = False
        self.assertFalse(is_requested(config))
        config["top_bar"] = {"enabled": True, "items": [
            {"metric": "cpu_usage", "prefs": {"metrics": ["cpu_usage", "cpu_temp"]}}]}
        self.assertTrue(is_requested(config))

    def test_protocol_and_sensor_identity_are_not_guessed(self):
        for fields in (dict(sensor=0x06030015), dict(app_pid=124), dict(seq=3),
                       dict(magic=0), dict(schema=2), dict(helper_pid=0)):
            with self.subTest(fields=fields):
                self.memory.value = snapshot(**fields)
                self.clock += 2
                self.assertEqual(self.sensor.read(), {})
                self.assertEqual(self.sensor.state, "invalid_value")

    def test_invalid_raw_values_are_missing_not_zero_or_wrapped_temperature(self):
        for raw in (0, 1250, 0xFFFFFFFF, 4294964296):
            with self.subTest(raw=raw):
                self.memory.value = snapshot(raw=raw)
                self.clock += 2
                self.assertEqual(self.sensor.read(), {})
                self.assertIsNone(self.sensor.sample_time)

    def test_reserved_bytes_and_wrong_size_are_rejected(self):
        for payload in (b"", snapshot()[:-1], snapshot()[:-1] + b"\x01"):
            self.memory.value = payload
            self.clock += 2
            self.assertEqual(self.sensor.read(), {})
            self.assertEqual(self.sensor.state, "invalid_value")

    def test_source_failure_clears_value_and_keeps_specific_hresult(self):
        self.sensor.read()
        self.memory.value = snapshot(state=2, result=-2147024891, raw=0, stamp=0)
        self.assertEqual(self.advance(), {})
        self.assertIsNone(self.sensor.sample_time)
        self.assertEqual(self.sensor.status(True)["error"], {"api": API, "status_code": -2147024891})

    def test_memory_failure_clears_the_previous_value_and_recovers(self):
        self.sensor.read()
        error = OSError("PRIVATE local path")
        error.winerror = 2
        self.memory.error = error
        self.assertEqual(self.advance(), {})
        self.assertEqual(self.sensor.state, "missing")
        self.assertNotIn("PRIVATE", str(self.sensor.status(True)))
        self.memory.error = None
        self.memory.value = snapshot(stamp=self.wall + 2, raw=510)
        self.assertEqual(self.advance()["cpu_temp"], 51)

    def test_permission_failure_has_bounded_backoff_and_no_elevation(self):
        error = PermissionError("PRIVATE")
        error.winerror = 5
        self.memory.error = error
        with patch("subprocess.Popen", side_effect=AssertionError("No process or elevation")):
            self.assertEqual(self.sensor.read(), {})
            for _ in range(20):
                self.advance()
        self.assertEqual(self.memory.reads, 1)
        self.assertEqual(self.sensor.state, "query_failed")

    def test_disabled_and_unrequested_read_do_not_load_native_apis(self):
        with patch("cpu_temperature._Mapping", side_effect=AssertionError("No native access")):
            disabled = AsusCpuTemperature(enabled=False)
            self.assertEqual(disabled.read(), {})
            fresh = AsusCpuTemperature(enabled=True)
            self.assertEqual(fresh.read(requested=False), {})
            fresh.close()
            disabled.close()

    def test_closed_or_unused_source_never_keeps_a_temperature(self):
        self.sensor.read()
        self.assertEqual(self.sensor.read(requested=False), {})
        self.assertIsNone(self.sensor.sample_time)
        self.sensor.close()
        reads = self.memory.reads
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.memory.reads, reads)

    def test_diagnostics_export_keeps_fixed_source_api_and_error_code(self):
        from diagnostic_actions import safe_report
        report = safe_report({"provider_status": {"cpu_thermal": {
            "state": "query_failed", "api": API,
            "error": {"api": API, "status_code": -2147024891, "message": "PRIVATE"},
        }}}, "synthetic")
        self.assertIn(API, str(report))
        self.assertIn("-2147024891", str(report))
        self.assertNotIn("PRIVATE", str(report))


if __name__ == "__main__":
    unittest.main()
