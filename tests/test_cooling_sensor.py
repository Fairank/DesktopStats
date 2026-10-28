"""ASUS fan protocol, throttling and sampler integration without hardware I/O."""

import copy
import ctypes as c
import math
import struct
import time
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

import sensors
from cooling_sensor import FAN_ENDPOINTS, SOURCE, AsusFans, decode_asus_fan
from sensor_diagnostics import cooling_noise_rows
from stats_config import DEFAULT


class CoolingSensorTests(unittest.TestCase):
    def setUp(self):
        self.now, self.wall = 10.0, 1000.0
        self.raw = {0x00110013: 0x10034, 0x00110014: 0x10037}
        self.calls = []
        self.sensor = AsusFans(self.status, clock=lambda: self.now, wall_clock=lambda: self.wall)

    def status(self, endpoint):
        self.calls.append((endpoint, self.now))
        value = self.raw.get(endpoint)
        if isinstance(value, Exception):
            raise value
        return value

    def advance(self, delta=0.5):
        self.now += delta
        self.wall += delta
        return self.sensor.read()

    def test_decode_presence_and_hundred_rpm_units_including_stopped_fan(self):
        for raw, rpm in (
            (0x10000, 0),
            (0x10034, 5200),
            (0x10038, 5600),
            (0x10078, 12000),
            (0x70034, 5200),
        ):
            self.assertEqual(decode_asus_fan(raw), rpm)
        for raw in (
            None,
            True,
            "0x10034",
            65588.0,
            -1,
            0,
            52,
            0x10079,
            0xFFFFFFFF,
            0xFFFFFFFE,
            0x80010034,
            0x100000000,
        ):
            self.assertIsNone(decode_asus_fan(raw), raw)

    def test_fixed_two_endpoints_never_probe_mid_or_control_devices(self):
        self.assertEqual(FAN_ENDPOINTS, {"cpu_fan_rpm": 0x00110013, "gpu_fan_rpm": 0x00110014})
        self.assertEqual(self.sensor.read(), {"cpu_fan_rpm": 5200, "gpu_fan_rpm": 5500})
        self.assertEqual([call[0] for call in self.calls], list(FAN_ENDPOINTS.values()))
        self.assertEqual(self.sensor.sample_times, {"cpu_fan_rpm": 1000.0, "gpu_fan_rpm": 1000.0})

    def test_ten_millisecond_requests_poll_each_endpoint_at_most_twice_a_second(self):
        for index in range(101):
            self.now, self.wall = 10 + index / 100, 1000 + index / 100
            result = self.sensor.read()
            self.assertEqual(result, {"cpu_fan_rpm": 5200, "gpu_fan_rpm": 5500})
            result["cpu_fan_rpm"] = -1
        for endpoint in FAN_ENDPOINTS.values():
            stamps = [stamp for key, stamp in self.calls if key == endpoint]
            self.assertEqual(stamps, [10, 10.5, 11])
            self.assertTrue(all(b - a >= 0.5 for a, b in zip(stamps, stamps[1:])))

    def test_zero_is_cached_as_valid_and_failure_drops_previous_success(self):
        self.raw[0x00110013] = 0x10000
        self.assertEqual(self.sensor.read()["cpu_fan_rpm"], 0)
        self.raw[0x00110013] = OSError("Fan endpoint unavailable")
        self.assertEqual(self.advance(0.49)["cpu_fan_rpm"], 0)
        self.assertNotIn("cpu_fan_rpm", self.advance(0.01))
        self.assertNotIn("cpu_fan_rpm", self.sensor.sample_times)
        count = len(self.calls)
        for _ in range(20):
            self.assertNotIn("cpu_fan_rpm", self.advance(0.01))
        self.assertEqual(len(self.calls), count)
        self.raw[0x00110013] = 0x10034
        self.assertEqual(self.advance(0.31)["cpu_fan_rpm"], 5200)

    def test_one_unsupported_fan_never_hides_the_other_or_fabricates_zero(self):
        self.raw[0x00110014] = 0
        self.assertEqual(self.sensor.read(), {"cpu_fan_rpm": 5200})
        self.assertEqual(self.sensor.state, "ready")

    def test_failure_attempts_are_throttled_even_without_any_successful_cache(self):
        self.raw = {}
        self.assertEqual(self.sensor.read(), {})
        for index in range(1, 50):
            self.now, self.wall = 10 + index / 100, 1000 + index / 100
            self.assertEqual(self.sensor.read(), {})
        self.assertEqual(len(self.calls), 2)
        self.advance(0.02)
        self.assertEqual(len(self.calls), 4)

    def test_clock_reversal_clears_cached_values_and_establishes_new_throttle(self):
        self.sensor.read()
        self.now, self.wall = 9, 999
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.sensor.sample_times, {})
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.advance(0.49), {})
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.advance(0.02), {"cpu_fan_rpm": 5200, "gpu_fan_rpm": 5500})

    def test_sleep_or_wall_clock_jump_cannot_return_old_cached_values(self):
        self.sensor.read()
        self.raw = {}
        self.wall += 60
        self.now += 0.01
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.sensor.sample_times, {})
        self.assertEqual(len(self.calls), 2, "Wall time jump must not bypass throttle")
        self.advance(31)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.sensor.sample_times, {})

    def test_old_success_is_replaced_by_a_fresh_post_sleep_read(self):
        self.sensor.read()
        self.raw[0x00110013] = 0x10038
        sample = self.advance(31)
        self.assertEqual(sample["cpu_fan_rpm"], 5600)
        self.assertEqual(self.sensor.sample_times["cpu_fan_rpm"], 1031)

    def test_clock_gap_during_io_drops_earlier_result_and_timestamp(self):
        reader = self.sensor._read_status

        def slow(endpoint):
            value = reader(endpoint)
            if endpoint == 0x00110013:
                self.now += 31
                self.wall += 31
            return value

        self.sensor._read_status = slow
        self.assertEqual(self.sensor.read(), {"gpu_fan_rpm": 5500})
        self.assertEqual(set(self.sensor.sample_times), {"gpu_fan_rpm"})

    def test_invalid_clock_discards_cache_and_waits_before_retry(self):
        for bad in (math.nan, math.inf, -1):
            with self.subTest(bad=bad):
                self.setUp()
                self.sensor.read()
                self.now = bad
                self.assertEqual(self.sensor.read(), {})
                self.assertEqual(self.sensor.sample_times, {})
                self.now = 20
                self.wall = 1010
                self.assertEqual(self.sensor.read(), {})
                self.assertEqual(len(self.calls), 2)
                self.assertIn("cpu_fan_rpm", self.advance(0.5))

    def test_unavailable_provider_and_close_never_open_or_close_shared_hardware(self):
        self.assertEqual(AsusFans().read(), {})
        self.sensor.read()
        self.sensor.close()
        self.sensor.close()
        self.assertEqual(self.advance(60), {})
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.sensor.sample_times, {})
        self.assertEqual(self.sensor.state, "closed")


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class FakeKernel32:
    def __init__(self):
        self.queries = []
        self.closes = []
        self.raw = 0x10000 + 78
        self.ok = True
        self.count = 4
        self.CreateFileW = Function(lambda *args: 123)
        self.DeviceIoControl = Function(self.io)
        self.CloseHandle = Function(lambda handle: self.closes.append(handle) or 1)

    def io(self, handle, code, query, length, output, capacity, count, overlap):
        self.queries.append(
            (handle, code, struct.unpack("<IIII", query), length, capacity, overlap)
        )
        c.memmove(output, struct.pack("<I", self.raw), 4)
        count._obj.value = self.count
        return self.ok


class AsusStatusBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.lib = FakeKernel32()
        with patch("sensors.c.WinDLL", return_value=self.lib):
            self.sensor = sensors.AsusTemperature()

    def test_existing_cpu_temperature_path_is_preserved_and_fans_share_handle(self):
        self.assertEqual(self.sensor.read(), {"cpu_temp": 78, "cpu_temp_source": "ASUS ACPI"})
        self.lib.raw = 0x10034
        self.assertEqual(self.sensor.read_status(0x00110013), 0x10034)
        self.assertEqual(
            self.lib.queries,
            [
                (123, 0x0022240C, (0x53545344, 8, 0x00120094, 0), 16, 16, None),
                (123, 0x0022240C, (0x53545344, 8, 0x00110013, 0), 16, 16, None),
            ],
        )

    def test_unsupported_or_short_io_never_becomes_temperature_or_speed(self):
        self.lib.ok = False
        self.assertEqual(self.sensor.read(), {})
        self.assertIsNone(self.sensor.read_status(0x00110013))
        self.lib.ok = True
        self.lib.count = 2
        self.assertEqual(self.sensor.read(), {})
        self.lib.count = 17
        self.assertIsNone(self.sensor.read_status(0x00110013))
        self.lib.count = 4
        self.lib.raw = 0x10000 + 125
        self.assertEqual(self.sensor.read(), {})

    def test_unapproved_endpoints_are_rejected_without_any_ioctl(self):
        for endpoint in (0x00110031, 0x00110018, 0x00110024, "0x00110013", True):
            with self.assertRaises(ValueError):
                self.sensor.read_status(endpoint)
        self.assertEqual(self.lib.queries, [])

    def test_close_is_once_and_read_after_close_does_not_issue_io(self):
        self.sensor.close()
        self.sensor.close()
        self.assertEqual(self.lib.closes, [123])
        self.assertEqual(self.sensor.read(), {})
        self.assertEqual(self.lib.queries, [])


class CoolingSamplerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.asus = SimpleNamespace(
            read=Mock(return_value={"cpu_temp": 78, "cpu_temp_source": "ASUS ACPI"}),
            read_status=Mock(
                side_effect=lambda endpoint: {0x00110013: 0x10034, 0x00110014: 0x10037}[endpoint]
            ),
            close=Mock(),
        )
        self.power = Mock(state="ready")
        self.power.read.return_value = {}
        self.battery = Mock()
        self.battery.read.return_value = {}
        self.activity = Mock()
        self.activity.read.return_value = {}
        replacements = {
            "cpu_name": lambda: "Fake CPU",
            "CpuPackagePower": lambda: self.power,
            "AsusTemperature": lambda: self.asus,
            "Battery": lambda: self.battery,
            "Activity": lambda: self.activity,
            "load": lambda: copy.deepcopy(DEFAULT),
            "hwinfo_registry": lambda cache=None: {},
            "INSPECT_UNTIL": 0,
            "ExternalEngine": lambda: SimpleNamespace(
                read=lambda *a: {"external_sensors": {}}, close=lambda: None
            ),
        }
        for name, value in replacements.items():
            self.stack.enter_context(patch("sensors." + name, value))
        for name, value in (
            ("cpu_count", 8),
            ("cpu_percent", 20),
            ("cpu_freq", None),
            ("sensors_battery", None),
            ("virtual_memory", SimpleNamespace(percent=50, used=1, total=2, available=1)),
            ("swap_memory", SimpleNamespace(percent=0, used=0)),
        ):
            self.stack.enter_context(patch("sensors.psutil." + name, return_value=value))
        self.sampler = sensors.Sampler()
        self.addCleanup(self.sampler.close)

    def test_only_cooling_dependency_or_inspect_reads_fan_status(self):
        with patch("sensors.required_sources", return_value={"cpu"}):
            self.assertEqual(self.sampler.sample()["cpu_temp"], 78)
        self.asus.read_status.assert_not_called()
        with patch("sensors.required_sources", return_value={"cooling"}):
            sample = self.sampler.sample()
        self.assertEqual(sample["cpu_fan_rpm"], 5200)
        self.assertEqual(sample["gpu_fan_rpm"], 5500)
        self.assertEqual(sample["metric_sources"]["cpu_fan_rpm"], SOURCE)
        self.assertEqual(sample["metric_sources"]["gpu_fan_rpm"], SOURCE)
        self.assertNotIn("system_fan_rpm", sample)
        self.assertEqual(set(sample["metric_timestamps"]), set(FAN_ENDPOINTS))
        self.assertEqual(self.asus.read_status.call_count, 2)

    def test_inspection_reads_fans_without_gpu_nvml_dependency(self):
        with (
            patch("sensors.required_sources", return_value=set()),
            patch("sensors.INSPECT_UNTIL", float("inf")),
            patch("sensors.Nvidia", side_effect=OSError("No NVML")),
        ):
            sample = self.sampler.sample()
        self.assertEqual(sample["gpu_fan_rpm"], 5500)
        self.assertNotIn("gpu_fan_percent", sample)

    def test_close_twice_releases_shared_handle_once_and_never_reopens(self):
        self.sampler.close()
        self.sampler.close()
        self.asus.close.assert_called_once()
        self.power.close.assert_called_once()
        self.assertEqual(self.sampler.sample(), {})
        self.asus.read_status.assert_not_called()

    def test_non_asus_host_stays_unavailable_without_querying_any_fan(self):
        with patch("sensors.AsusTemperature", side_effect=OSError("No ATKACPI device")):
            unsupported = sensors.Sampler()
        self.addCleanup(unsupported.close)
        with patch("sensors.required_sources", return_value={"cooling"}):
            sample = unsupported.sample()
        self.assertNotIn("cpu_fan_rpm", sample)
        self.assertNotIn("gpu_fan_rpm", sample)
        self.assertEqual(sample["metric_sources"], {})
        self.asus.read_status.assert_not_called()


class CoolingNoiseContextTests(unittest.TestCase):
    def test_real_controller_detail_uses_discovered_acoustic_inventory_without_new_probe(self):
        import native_controller as controls
        with patch.object(controls, 'load', return_value=copy.deepcopy(DEFAULT)):
            ui = controls.Controller()
        try:
            ui._saved['top_bar']['items'] = [dict(id='b_fan', metric='cpu_fan_rpm', prefs={})]
            ui.receive(dict(time=time.time(), cpu_fan_rpm=5200,
                            external_sensors={}, external_status=dict(state='ready'),
                            external_catalog={'/sound': dict(type='Noise', unit='dBA', value=38.6,
                                                             name='Case sound', hardware_name='Case')}))
            self.assertNotIn('/sound', ui._data['external_sensors'])
            detail = ui.topBarDetailRow('b_fan')
            self.assertEqual(detail['number_text'], '5200')
            acoustic = next(row for row in detail['related'] if row['label'].startswith('环境噪声'))
            self.assertEqual(acoustic['value'], '38.6 dBA')
            self.assertTrue(acoustic['available'])
        finally:
            ui.close()
            ui.deleteLater()

    def test_no_rpm_to_db_guess_and_explicit_collection_scope(self):
        row, = cooling_noise_rows(dict(cpu_fan_rpm=12000, gpu_fan_rpm=12000))
        self.assertFalse(row['available'])
        self.assertEqual(row['value'], '—')
        self.assertIn('未发现 Noise / dBA', row['reason'])
        self.assertIn('不能据此判断硬件不支持', row['reason'])

    def test_only_observed_noise_channels_with_canonical_units_and_finite_values(self):
        sensor = dict(type='Noise', unit='dBA', name='Case sound', hardware_name='Case', value=0)
        for value in (0, 38.6, 140):
            data = dict(external_sensors={'/sound': dict(sensor, value=value)}, external_status={'state': 'ready'})
            row, = cooling_noise_rows(data)
            self.assertTrue(row['available'])
            self.assertEqual(row['value'], f'{value:.1f} dBA')
            self.assertIn('Case', row['source'])
        for change in (dict(type='Fan'), dict(unit='RPM')):
            row, = cooling_noise_rows(dict(external_sensors={'/sound': dict(sensor, **change)}))
            self.assertFalse(row['available'])
        for value in (None, True, -1, float('nan'), float('inf')):
            row, = cooling_noise_rows(dict(external_sensors={'/sound': dict(sensor, value=value)}))
            self.assertFalse(row['available'])
            self.assertEqual(row['value'], '—')

    def test_stale_provider_failure_and_bounded_inventory(self):
        sensor = dict(type='Noise', unit='dBA', name='Case sound', value=38.6)
        data = dict(external_sensors={str(i): sensor for i in range(20)}, external_status={'state': 'ready'})
        self.assertEqual(len(cooling_noise_rows(data)), 6)
        self.assertTrue(all(not row['available'] and row['reason'] == '读数已过期'
                            for row in cooling_noise_rows(data, stale=True)))
        data['external_status'] = dict(state='error', detail='Observed provider error')
        self.assertTrue(all(not row['available'] and row['reason'] == 'Observed provider error'
                            for row in cooling_noise_rows(data)))


if __name__ == "__main__":
    unittest.main()
