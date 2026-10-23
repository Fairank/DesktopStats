"""Transient-source recovery boundaries, with no hardware, helper or worker."""
import copy
import ctypes
import os
import struct
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DESKTOP_STATS_DATA", str(
    Path(__file__).resolve().parents[1] / "qa-private/provider-recovery-test-data"))
import sensors
from stats_config import DEFAULT

REAL_NVIDIA = sensors.Nvidia


def fail_io(*args, **kwargs):
    raise AssertionError("Unexpected real source/process operation")


def asus_source(cpu=78, cpu_rpm=3200, gpu_rpm=3300):
    raw = {0x00110013: 0x10000 + cpu_rpm // 100,
           0x00110014: 0x10000 + gpu_rpm // 100}
    return SimpleNamespace(
        needs_reconnect=False, last_error={}, status_errors={},
        read=Mock(return_value={"cpu_temp": cpu, "cpu_temp_source": "ASUS ACPI"}),
        read_status=Mock(side_effect=lambda endpoint: raw[endpoint]), close=Mock())


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ("sensors.c.WinDLL", "sensors.c.CDLL", "sensors.winreg.OpenKey",
                       "subprocess.Popen", "threading.Thread.start"):
            self.stack.enter_context(patch(target, side_effect=fail_io))
        self.now = 100.0
        self.stack.enter_context(patch("sensors.time.monotonic", side_effect=lambda: self.now))
        self.stack.enter_context(patch("sensors.time.time", side_effect=lambda: self.now + 1000))
        self.asus = asus_source()
        self.asus_factory = self.stack.enter_context(patch("sensors.AsusTemperature", return_value=self.asus))
        self.gpu = Mock()
        self.gpu.read.return_value = dict(gpu_usage=0, gpu_power=0.0,
            gpu_source="NVIDIA NVML", gpus={"0": dict(gpu_usage=0, gpu_power=0.0)})
        self.gpu_factory = self.stack.enter_context(patch("sensors.Nvidia", return_value=self.gpu))
        self.power = Mock(state="ready", read=Mock(return_value=dict(
            cpu_power=43.2, cpu_power_source="Synthetic package")))
        self.battery = Mock(read=Mock(return_value={"battery_watts": 0.0}))
        self.activity = Mock(read=Mock(return_value={"net_download": 0.0}))
        self.needed = {"cpu", "cooling", "gpu"}
        replacements = dict(
            load=lambda: copy.deepcopy(DEFAULT), cpu_name=lambda: "Synthetic CPU",
            CpuPackagePower=lambda: self.power, Battery=lambda: self.battery,
            Activity=lambda: self.activity, hwinfo_registry=lambda cache=None: {}, INSPECT_UNTIL=0,
            required_sources=lambda config: self.needed,
            ExternalEngine=lambda: SimpleNamespace(
                read=lambda *args: {"external_sensors": {}}, close=Mock()))
        for key, value in replacements.items():
            self.stack.enter_context(patch("sensors." + key, value))
        for key, value in dict(cpu_count=8, cpu_percent=12,
            cpu_freq=SimpleNamespace(current=4000), sensors_battery=None,
            virtual_memory=SimpleNamespace(percent=20, used=20, total=100, available=80),
            swap_memory=SimpleNamespace(percent=0, used=0)).items():
            self.stack.enter_context(patch("sensors.psutil." + key, return_value=value))
        self.log = self.stack.enter_context(patch("sensors.logging.exception"))
        self.sampler = sensors.Sampler()
        self.addCleanup(self.sampler.close)

    def assert_healthy_other_sources(self, sample):
        self.assertEqual(sample["cpu_power"], 43.2)
        self.assertEqual(sample["battery_watts"], 0.0)
        self.assertEqual(sample["net_download"], 0.0)
        self.assertEqual(sample["ram_percent"], 20)

    def test_native_sampling_uses_current_committed_config_without_disk_reload(self):
        committed = copy.deepcopy(DEFAULT)
        self.sampler.config_provider = lambda: committed
        with patch("sensors.load", side_effect=AssertionError("Per-sample disk reload")):
            self.assert_healthy_other_sources(self.sampler.sample())
            committed = copy.deepcopy(committed)
            committed["refresh"] = 0.01
            self.assert_healthy_other_sources(self.sampler.sample())

    def test_pending_storage_cleanup_retains_owner_for_an_explicit_retry(self):
        pending = Mock(close=Mock(side_effect=[False, True]))
        self.sampler.storage = pending
        with patch("sensors.logging.error") as report:
            self.assertFalse(self.sampler.close())
            self.assertIs(self.sampler.storage, pending)
            report.assert_called_once_with("Sensor cleanup still pending: %s", "storage")
        self.assertTrue(self.sampler.close())
        self.assertIsNone(self.sampler.storage)
        self.assertEqual(pending.close.call_count, 2)

    def test_nvml_failure_keeps_healthy_readings_and_exact_failure_metadata(self):
        error = OSError("Synthetic device loss")
        error.winerror = 1167
        self.gpu.read.side_effect = error
        sample = self.sampler.sample()
        self.assert_healthy_other_sources(sample)
        self.assertEqual(sample["cpu_temp"], 78)
        self.assertEqual(sample["cpu_fan_rpm"], 3200)
        self.assertNotIn("gpu_power", sample)
        status = sample["provider_status"]["nvml"]
        self.assertEqual(status["state"], "waiting_retry")
        self.assertEqual(status["reason"], "read_failed")
        self.assertEqual(status["error"]["winerror"], 1167)
        self.assertEqual(status["retry_in_seconds"], 5)
        self.gpu.close.assert_called_once()

    def test_nvml_retries_only_at_deadline_and_clears_error_after_recovery(self):
        self.gpu.read.side_effect = RuntimeError("Synthetic reset")
        self.sampler.sample()
        self.now = 104.999
        self.sampler.sample()
        self.gpu_factory.assert_called_once()
        recovered = Mock(read=Mock(return_value={"gpu_usage": 0, "gpu_power": 0.0}))
        self.gpu_factory.return_value = recovered
        self.now = 105
        sample = self.sampler.sample()
        self.assertEqual(sample["gpu_power"], 0.0)
        self.assertEqual(sample["provider_status"]["nvml"]["state"], "connected")
        self.assertEqual(sample["provider_status"]["nvml"]["error"], {})
        recovered.close.assert_not_called()

    def test_missing_sdk_entrypoint_isolated_but_arbitrary_coding_error_is_not_hidden(self):
        self.gpu.read.side_effect = AttributeError("Synthetic missing symbol")
        self.assert_healthy_other_sources(self.sampler.sample())
        self.now += 5
        self.gpu.read.side_effect = ValueError("Synthetic coding error")
        with self.assertRaisesRegex(ValueError, "coding error"):
            self.sampler.sample()

    def test_failed_nvml_cleanup_does_not_drop_other_sources_or_retry_immediately(self):
        self.gpu.read.side_effect = RuntimeError("Synthetic read failure")
        self.gpu.close.side_effect = OSError("Synthetic close failure")
        self.assert_healthy_other_sources(self.sampler.sample())
        self.assertIsNone(self.sampler.nvidia)
        self.assertEqual(self.sampler.nvml_retry, 105)
        self.log.assert_called_once()

    def test_no_dependency_cleanup_failure_isolated_and_next_demand_can_open(self):
        self.sampler.sample()
        self.gpu.close.side_effect = OSError("Synthetic close failure")
        self.needed = {"cpu"}
        self.assert_healthy_other_sources(self.sampler.sample())
        self.assertIsNone(self.sampler.nvidia)
        self.assertFalse(self.sampler.sample()["provider_status"]["nvml"]["requested"])
        self.needed.add("gpu")
        self.gpu.close.side_effect = None
        self.assert_healthy_other_sources(self.sampler.sample())
        self.assertEqual(self.gpu_factory.call_count, 1)
        self.assertEqual(self.gpu.close.call_count, 1)
        self.now += 5
        self.assert_healthy_other_sources(self.sampler.sample())
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertEqual(self.gpu.close.call_count, 2)
        self.assertEqual(self.gpu_factory.call_count, 2)

    def test_valid_zero_and_other_gpu_device_prevent_false_disconnect(self):
        self.assertEqual(self.sampler.sample()["gpu_power"], 0.0)
        self.gpu.close.assert_not_called()
        self.gpu.read.return_value = {"gpus": {"0": {}, "1": {"gpu_usage": 0}}}
        self.assertEqual(self.sampler.sample()["gpus"]["1"]["gpu_usage"], 0)
        self.gpu.close.assert_not_called()

    def test_failed_gpu_read_does_not_reuse_previous_success(self):
        self.assertEqual(self.sampler.sample()["gpu_power"], 0.0)
        self.gpu.read.side_effect = OSError("Synthetic later loss")
        sample = self.sampler.sample()
        self.assertNotIn("gpu_power", sample)
        self.assertNotIn("gpus", sample)
        self.assert_healthy_other_sources(sample)

    def test_initial_asus_open_failure_recovers_on_demand_after_bounded_retry(self):
        error = OSError("Synthetic missing interface")
        error.winerror = 2
        self.asus_factory.side_effect = [error, asus_source(cpu=67, cpu_rpm=4400)]
        sampler = sensors.Sampler()
        self.addCleanup(sampler.close)
        self.assertEqual(sampler.sample()["provider_status"]["asus"]["error"]["winerror"], 2)
        self.now = 159.999
        self.assertIsNone(sampler.sample()["cpu_temp"])
        self.assertEqual(self.asus_factory.call_count, 2)  # original and failed new sampler
        self.now = 170
        self.needed = {"gpu"}
        sampler.sample()
        self.assertEqual(self.asus_factory.call_count, 2)
        self.needed = {"cpu", "cooling"}
        sample = sampler.sample()
        self.assertEqual(sample["cpu_temp"], 67)
        self.assertEqual(sample["cpu_fan_rpm"], 4400)
        self.assertEqual(sample["provider_status"]["asus"]["state"], "connected")
        self.assertEqual(self.asus_factory.call_count, 3)

    def test_asus_handle_loss_clears_cached_fans_and_rebinds_after_retry(self):
        self.assertEqual(self.sampler.sample()["cpu_fan_rpm"], 3200)
        old_cooling = self.sampler.cooling
        def lost():
            self.asus.needs_reconnect = True
            self.asus.last_error = dict(api="DeviceIoControl", winerror=6, endpoint="0x00120094")
            return {}
        self.asus.read.side_effect = lost
        self.now += 0.1  # fan reads would otherwise return the successful cache
        sample = self.sampler.sample()
        self.assertIsNone(sample["cpu_temp"])
        self.assertNotIn("cpu_fan_rpm", sample)
        self.assertNotIn("gpu_fan_rpm", sample)
        self.assertEqual(sample["metric_timestamps"], {})
        self.assertEqual(old_cooling.sample_times, {})
        self.assertEqual(sample["provider_status"]["asus"]["error"]["winerror"], 6)
        self.asus.close.assert_called_once()
        recovered = asus_source(cpu=65, cpu_rpm=0, gpu_rpm=4400)
        self.asus_factory.return_value = recovered
        self.now = 160.1
        sample = self.sampler.sample()
        self.assertEqual(sample["cpu_fan_rpm"], 0)
        self.assertEqual(sample["gpu_fan_rpm"], 4400)
        self.assertEqual(sample["cpu_temp"], 65)
        self.assertEqual(sample["provider_status"]["asus"]["error"], {})
        recovered.read_status.assert_called()

    def test_asus_read_and_cleanup_failures_are_isolated_and_do_not_reopen_after_close(self):
        self.asus.read.side_effect = OSError("Synthetic failed read")
        self.asus.close.side_effect = OSError("Synthetic failed close")
        sample = self.sampler.sample()
        self.assert_healthy_other_sources(sample)
        self.assertIsNone(sample["cpu_temp"])
        self.assertEqual(sample["provider_status"]["asus"]["reason"], "read_failed")
        self.sampler.close()
        calls = self.asus_factory.call_count
        self.now = 1000
        self.assertEqual(self.sampler.sample(), {})
        self.sampler.close()
        self.assertEqual(self.asus_factory.call_count, calls)
        self.asus.close.assert_called_once()

    def test_unsupported_asus_channel_does_not_trigger_reopen_or_guess_cause(self):
        self.asus.read.return_value = {}
        self.asus.read_status.side_effect = None
        self.asus.read_status.return_value = None
        self.asus.status_errors = {"0x00110013": {"api": "DeviceIoControl", "winerror": 1}}
        for stamp in (100, 101, 200):
            self.now = stamp
            sample = self.sampler.sample()
            self.assertNotIn("cpu_fan_rpm", sample)
        self.asus_factory.assert_called_once()
        self.assertEqual(sample["provider_status"]["asus"]["channel_errors"]["0x00110013"]["winerror"], 1)
        self.assertEqual(sample["provider_status"]["asus"]["state"], "connected")

    def test_sampler_carries_per_device_diagnostics_and_pdh_error(self):
        source, lib = synthetic_nvml()
        self.gpu_factory.return_value = source
        self.power.last_error = "PDH status 0xc0000bb9"
        sample = self.sampler.sample()
        self.assertEqual(sample["gpus"]["0"]["channel_status"]["gpu_fan_percent"]["status_code"], 3)
        self.assertEqual(sample["gpus"]["0"]["channel_status"]["gpu_power"]["state"], "available")
        self.assertEqual(sample["cpu_power_error"], "PDH status 0xc0000bb9")
        self.assertIs(self.sampler.nvidia, source)

    def test_top_bar_only_external_binding_is_retained_only_when_enabled(self):
        config = copy.deepcopy(DEFAULT)
        config["top_bar"] = dict(enabled=True, items=[dict(metric="external_1", prefs={
            "sensor_bindings": {"external_1": {"sensor_id": "/synthetic/voltage"}}})])
        rows = {"/synthetic/voltage": {"value": 0}, "/unbound": {"value": 1}}
        self.sampler.external = SimpleNamespace(read=lambda *args: {"external_sensors": rows})
        self.needed = {"external"}
        with patch("sensors.load", return_value=config):
            self.assertEqual(self.sampler.sample()["external_sensors"], {"/synthetic/voltage": {"value": 0}})
            config["top_bar"]["enabled"] = False
            self.assertEqual(self.sampler.sample()["external_sensors"], {})

    def test_hwinfo_diagnostics_are_carried_separately_from_metric_values(self):
        result = sensors.RegistryReadings()
        result["adapter_input_watts"] = 0.0
        result.diagnostics.update(state="available", available_count=1)
        with patch("sensors.hwinfo_registry", return_value=result):
            sample = self.sampler.sample()
        self.assertEqual(sample["adapter_input_watts"], 0.0)
        self.assertEqual(sample["provider_status"]["hwinfo"]["state"], "available")
        self.assertNotIn("diagnostics", sample["metric_sources"])

    def test_asus_channel_diagnostic_survives_owned_handle_retirement(self):
        self.asus.channel_status = {"cpu_temp": dict(state="query_failed", winerror=6, reason="handle_lost")}
        self.asus.needs_reconnect = True
        self.asus.last_error = dict(api="DeviceIoControl", winerror=6, endpoint="0x00120094")
        sample = self.sampler.sample()
        self.assertEqual(sample["provider_status"]["asus"]["channel_status"]["cpu_temp"]["winerror"], 6)
        self.assertEqual(sample["provider_status"]["asus"]["state"], "waiting_retry")
        self.assertIsNone(sample["cpu_temp"])


class Function:
    def __init__(self, function): self.function = function
    def __call__(self, *args): return self.function(*args)


class SyntheticNvml:
    def __init__(self):
        self.calls, self.text_calls, self.failures = [], [], {}
        self.text_result = b"Not Supported"
        self.memory_total = 8 * 1024**3
        for api in ("nvmlDeviceGetName", "nvmlDeviceGetTemperature", "nvmlDeviceGetUtilizationRates",
                    "nvmlDeviceGetPowerUsage", "nvmlDeviceGetMemoryInfo", "nvmlDeviceGetClockInfo",
                    "nvmlDeviceGetFanSpeed"):
            setattr(self, api, Function(lambda *args, api=api: self.query(api, *args)))
        self.nvmlErrorString = Function(self.error_string)
        self.nvmlShutdown = Function(lambda: 0)

    def error_string(self, code):
        self.text_calls.append(code)
        if isinstance(self.text_result, Exception):
            raise self.text_result
        return self.text_result

    def query(self, api, device, *args):
        self.calls.append((api, device))
        failure = self.failures.get((device, api), 3 if api == "nvmlDeviceGetFanSpeed" else 0)
        if isinstance(failure, Exception):
            raise failure
        if failure:
            return failure
        if api == "nvmlDeviceGetName":
            args[0].value = f"Synthetic GPU {device}".encode()
        elif api == "nvmlDeviceGetUtilizationRates":
            args[0]._obj.gpu = 0
            args[0]._obj.memory = 0
        elif api == "nvmlDeviceGetMemoryInfo":
            args[0]._obj.used, args[0]._obj.total = 0, self.memory_total
        else:
            args[-1]._obj.value = 0
        return 0


def synthetic_nvml():
    source = REAL_NVIDIA.__new__(REAL_NVIDIA)
    source.lib, source.name, source.handles = SyntheticNvml(), "Synthetic GPU", {"0": 1, "1": 2}
    return source, source.lib


class ChannelDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ("sensors.c.WinDLL", "sensors.c.CDLL", "subprocess.Popen", "threading.Thread.start"):
            self.stack.enter_context(patch(target, side_effect=fail_io))
        self.source, self.lib = synthetic_nvml()

    def test_each_existing_getter_has_status_and_zero_is_available(self):
        data = self.source.read()
        for key, device in data["gpus"].items():
            for metric in ("gpu_temp", "gpu_usage", "gpu_power", "gpu_clock", "gpu_memory_clock", "vram_gb", "vram_percent"):
                self.assertEqual(device[metric], 0)
                self.assertEqual(device["channel_status"][metric]["state"], "available")
                self.assertEqual(device["channel_status"][metric]["status_code"], 0)
            fan = device["channel_status"]["gpu_fan_percent"]
            self.assertEqual((fan["state"], fan["status_code"], fan["status_text"]), ("query_failed", 3, "Not Supported"))
            self.assertNotIn("gpu_fan_percent", device)
        self.assertEqual(self.lib.text_calls, [3])
        self.assertEqual(len(self.lib.calls), 16)  # eight existing reads, two devices
        self.assertFalse(any("NumFans" in api for api, _ in self.lib.calls))

    def test_one_device_channel_failure_keeps_other_device_and_fields(self):
        self.lib.failures[(1, "nvmlDeviceGetPowerUsage")] = 9
        self.lib.failures[(2, "nvmlDeviceGetFanSpeed")] = 0
        data = self.source.read()["gpus"]
        self.assertNotIn("gpu_power", data["0"])
        self.assertEqual(data["0"]["channel_status"]["gpu_power"]["status_code"], 9)
        self.assertEqual(data["1"]["gpu_power"], 0)
        self.assertEqual(data["1"]["gpu_fan_percent"], 0)

    def test_entrypoint_missing_differs_from_query_exception(self):
        del self.lib.nvmlDeviceGetFanSpeed
        error = OSError("Synthetic getter failure")
        error.winerror = 1167
        self.lib.failures[(1, "nvmlDeviceGetPowerUsage")] = error
        data = self.source.read()["gpus"]["0"]
        self.assertEqual(data["channel_status"]["gpu_fan_percent"]["state"], "entrypoint_missing")
        self.assertIsNone(data["channel_status"]["gpu_fan_percent"]["status_code"])
        power = data["channel_status"]["gpu_power"]
        self.assertEqual(power["state"], "query_failed")
        self.assertIsNone(power["status_code"])
        self.assertEqual(power["error"]["winerror"], 1167)
        self.assertEqual(data["gpu_temp"], 0)

    def test_status_text_is_optional_cached_and_bounded(self):
        for outcome in (OSError("No error text"), None, b"x" * 5000, "y" * 5000):
            with self.subTest(outcome_type=type(outcome).__name__):
                source, lib = synthetic_nvml()
                lib.text_result = outcome
                for _ in range(2):
                    data = source.read()["gpus"]["0"]
                    self.assertLessEqual(len(data["channel_status"]["gpu_fan_percent"]["status_text"]), 160)
                    self.assertEqual(data["gpu_power"], 0)
                self.assertEqual(lib.text_calls, [3])
        source, lib = synthetic_nvml()
        del lib.nvmlErrorString
        self.assertEqual(source.read()["gpus"]["0"]["channel_status"]["gpu_fan_percent"]["status_text"], "")
        for code in range(1, 100):
            self.source._status_text(code)
        self.assertEqual(len(self.source._error_strings), 32)
        self.assertEqual(len(self.lib.text_calls), 32)

    def test_later_failure_does_not_retain_old_channel_value_or_metadata(self):
        self.assertEqual(self.source.read()["gpus"]["0"]["gpu_power"], 0)
        self.lib.failures[(1, "nvmlDeviceGetPowerUsage")] = 3
        device = self.source.read()["gpus"]["0"]
        self.assertNotIn("gpu_power", device)
        self.assertEqual(device["channel_status"]["gpu_power"]["state"], "query_failed")
        self.assertEqual(device["channel_status"]["gpu_usage"]["state"], "available")

    def test_one_memory_api_result_maps_all_three_metrics_without_extra_query(self):
        self.lib.failures[(1, "nvmlDeviceGetMemoryInfo")] = 3
        device = self.source.read()["gpus"]["0"]
        for metric in ("vram_gb", "vram_total_gb", "vram_percent"):
            self.assertNotIn(metric, device)
            self.assertEqual(device["channel_status"][metric]["status_code"], 3)
        self.assertEqual(sum(api == "nvmlDeviceGetMemoryInfo" for api, dev in self.lib.calls if dev == 1), 1)

    def test_zero_memory_denominator_has_specific_reason_without_division_error(self):
        self.lib.memory_total = 0
        device = self.source.read()["gpus"]["0"]
        self.assertEqual(device["vram_total_gb"], 0)
        self.assertIsNone(device["vram_percent"])
        self.assertEqual(device["channel_status"]["vram_percent"]["reason"], "zero_total_memory")
        self.assertEqual(device["channel_status"]["vram_gb"]["state"], "available")


class RegistryDiagnosticsTests(unittest.TestCase):
    def registry(self, raw="43.8", *, age=0, error=None, count=1, both=False, display=None):
        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): return None
        values = {}
        for index in range(count):
            values.update({f"Sensor{index}": "CPU [#0] Synthetic", f"Label{index}": "CPU Package Power",
                f"ValueRaw{index}": raw, f"Value{index}": display or f"{raw} W"})
        entries = list(values.items())
        def open_key(hive, path):
            if error is not None:
                raise error
            if not both and hive == sensors.winreg.HKEY_LOCAL_MACHINE:
                raise FileNotFoundError()
            return Key()
        stamp = int((1000 - age + 11644473600) * 1e7)
        with (
            patch("sensors.time.time", return_value=1000),
            patch("sensors.winreg.OpenKey", side_effect=open_key) as opens,
            patch("sensors.winreg.QueryInfoKey", return_value=(0, len(entries), stamp)),
            patch("sensors.winreg.EnumValue", side_effect=lambda key, index: (*entries[index], sensors.winreg.REG_SZ)),
            patch("sensors.c.WinDLL", side_effect=fail_io), patch("sensors.c.CDLL", side_effect=fail_io),
        ):
            result = sensors.hwinfo_registry()
        self.assertEqual(opens.call_count, 2)  # same existing hive queries
        return result

    def test_explicit_numeric_formats_and_zero_are_preserved(self):
        for raw, value in (("43.8", 43.8), (43.8, 43.8), (0, 0), ("0", 0), ("1e2", 100), (" .5 ", 0.5)):
            with self.subTest(raw=raw):
                result = self.registry(raw)
                self.assertEqual(result["cpu_power"], value)
                self.assertEqual(result.diagnostics["state"], "available")

    def test_comma_grouping_and_ambiguous_raw_are_rejected_without_guessing(self):
        for raw in ("43,8", "1,234", "1,234.5", "1.234,5", "1 234.5", True, "NaN", "Infinity", float("inf")):
            with self.subTest(raw=raw):
                result = self.registry(raw)
                self.assertNotIn("cpu_power", result)
                self.assertEqual(result.diagnostics["state"], "parse_error")
                self.assertEqual(result.diagnostics["parse_error_count"], 1)
                self.assertEqual(result.diagnostics["channel_errors"][0]["state"], "parse_error")

    def test_display_localization_does_not_change_explicit_raw_or_watt_scope(self):
        self.assertEqual(self.registry("43.8", display="43,8 W")["cpu_power"], 43.8)
        self.assertNotIn("cpu_power", self.registry("43.8", display="43.8 mW"))

    def test_future_and_stale_exports_are_not_fresh(self):
        for age, state in ((-3600, "future_timestamp"), (31, "stale")):
            result = self.registry(age=age)
            self.assertEqual(result, {})
            self.assertEqual(result.diagnostics["state"], state)
            self.assertEqual(result.diagnostics["exports"][0]["state"], state)

    def test_absent_export_and_actual_permission_error_remain_distinct(self):
        for code, state in ((2, "export_absent"), (5, "query_failed")):
            error = OSError("Synthetic registry query failure")
            error.winerror = code
            result = self.registry(error=error)
            self.assertEqual(result.diagnostics["state"], state)
            self.assertTrue(all(row["error"]["winerror"] == code for row in result.diagnostics["exports"]))

    def test_error_details_are_bounded_and_same_value_in_both_hives_is_available(self):
        result = self.registry("1,234", count=100)
        self.assertEqual(result.diagnostics["parse_error_count"], 100)
        self.assertEqual(len(result.diagnostics["channel_errors"]), 32)
        result = self.registry(both=True)
        self.assertEqual([row["state"] for row in result.diagnostics["exports"]], ["available", "available"])


class StatusBoundaryTests(unittest.TestCase):
    def test_success_with_short_asus_response_has_no_raw_value_or_false_io_error(self):
        def ioctl(handle, code, query, length, output, capacity, count, overlap):
            count._obj.value = 2
            return 1
        lib = SimpleNamespace(CreateFileW=Function(lambda *args: 123),
            DeviceIoControl=Function(ioctl), CloseHandle=Function(lambda *args: 1))
        with patch("sensors.c.WinDLL", return_value=lib):
            source = sensors.AsusTemperature()
        self.assertIsNone(source.read_status(0x00110013))
        status = source.channel_status["cpu_fan_rpm"]
        self.assertEqual(status["reason"], "invalid_response_length")
        self.assertNotIn("winerror", status)
        self.assertFalse(source.needs_reconnect)
        source.close()

    def test_asus_raw_decode_reasons_differ_from_interface_failure_and_zero_speed(self):
        cases = (
            (0x00110013, 0, "invalid_value", "presence_missing"),
            (0x00110013, 0x80010001, "invalid_value", "unknown_flags"),
            (0x00110013, 0x10079, "invalid_value", "rpm_out_of_range"),
            (0x00110013, 0x10000, "available", None),
            (0x00120094, 0x10000, "invalid_value", "temperature_out_of_range"),
            (0x00120094, 0x10000 + 94, "available", None),
        )
        for endpoint, raw, state, reason in cases:
            with self.subTest(endpoint=endpoint, raw=raw):
                calls = []
                def ioctl(handle, code, query, length, output, capacity, count, overlap):
                    calls.append(query)
                    ctypes.memmove(output, struct.pack("<I", raw), 4)
                    count._obj.value = 4
                    return 1
                lib = SimpleNamespace(CreateFileW=Function(lambda *args: 123),
                    DeviceIoControl=Function(ioctl), CloseHandle=Function(lambda *args: 1))
                with patch("sensors.c.WinDLL", return_value=lib):
                    source = sensors.AsusTemperature()
                self.assertEqual(source.read_status(endpoint), raw)
                metric = "cpu_temp" if endpoint == 0x00120094 else "cpu_fan_rpm"
                status = source.channel_status[metric]
                self.assertEqual(status["state"], state)
                self.assertEqual(status.get("reason"), reason)
                self.assertEqual(status["raw"], raw)
                self.assertFalse(source.needs_reconnect)
                self.assertEqual(len(calls), 1)
                source.close()

    def test_only_explicit_handle_loss_requests_reconnect_and_records_actual_code(self):
        for code, retry in ((0, False), (1, False), (5, False), (6, True), (1167, True)):
            with self.subTest(code=code):
                calls = []
                def ioctl(*args):
                    calls.append(args)
                    ctypes.set_last_error(code)
                    return 0
                lib = SimpleNamespace(CreateFileW=Function(lambda *args: 123),
                    DeviceIoControl=Function(ioctl), CloseHandle=Function(lambda *args: 1))
                with patch("sensors.c.WinDLL", return_value=lib):
                    source = sensors.AsusTemperature()
                self.assertIsNone(source.read_status(0x00110013))
                self.assertEqual(source.needs_reconnect, retry)
                self.assertEqual(source.last_error["winerror"], code)
                status = source.channel_status["cpu_fan_rpm"]
                self.assertEqual(status["reason"], "handle_lost" if retry else "ioctl_failed")
                self.assertIsNone(status["raw"])
                source.read_status(0x00110014)
                self.assertEqual(len(calls), 1 if retry else 2)
                source.close()

    def test_nvml_initialization_keeps_specific_api_status(self):
        lib = SimpleNamespace(nvmlDeviceGetHandleByIndex_v2=Function(lambda *args: 0),
                              nvmlInit_v2=Function(lambda: 9))
        with patch("sensors.c.CDLL", return_value=lib), self.assertRaises(sensors.ProviderApiError) as raised:
            sensors.Nvidia()
        error = sensors.provider_error(raised.exception, "Nvidia")
        self.assertEqual(error["api"], "nvmlInit_v2")
        self.assertEqual(error["status_code"], 9)


if __name__ == "__main__":
    unittest.main()
