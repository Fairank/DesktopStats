"""Battery and real NVML-provider isolation through mocked native boundaries."""

import copy
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import native_controller as controls
import sensors
from stats_config import DEFAULT, validate


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


def denied():
    error = PermissionError(13, "PRIVATE_SOURCE_CONTENT", "C:/private/secret.txt")
    error.winerror = 5
    return error


class PowerLibrary:
    def __init__(self):
        self.calls = 0
        self.error = None
        self.ntstatus = 0
        self.present = True
        self.CallNtPowerInformation = Function(self.query)

    def query(self, _level, _input, _length, output, _size):
        self.calls += 1
        if self.error:
            raise self.error
        if self.ntstatus:
            return self.ntstatus
        state = output._obj
        state.present, state.online, state.charging = self.present, True, self.present
        state.rate, state.remaining, state.capacity = 15000, 30000, 60000
        state.estimated_time = 0xFFFFFFFF
        return 0


class NvmlLibrary:
    def __init__(self):
        self.device_count = 2
        self.count_status = 0
        self.handle_errors = {}
        self.requested_indices = []
        self.shutdowns = 0
        self.shutdown_status = 0
        self.shutdown_error = None
        self.nvmlInit_v2 = Function(lambda: 0)
        self.nvmlShutdown = Function(self.shutdown)
        self.nvmlDeviceGetCount_v2 = Function(self.count)
        self.nvmlDeviceGetHandleByIndex_v2 = Function(self.handle)
        self.nvmlDeviceGetName = Function(self.name)
        self.nvmlDeviceGetUtilizationRates = Function(self.utilization)

    def shutdown(self):
        self.shutdowns += 1
        if self.shutdown_error:
            raise self.shutdown_error
        return self.shutdown_status

    def count(self, output):
        output._obj.value = self.device_count
        return self.count_status

    def handle(self, index, output):
        self.requested_indices.append(index)
        error = self.handle_errors.get(index)
        if isinstance(error, Exception):
            raise error
        if error:
            return error
        output._obj.value = 1000 + index
        return 0

    @staticmethod
    def name(handle, output, _size):
        output.value = ("Synthetic GPU " + str(handle.value - 1000)).encode("ascii")
        return 0

    @staticmethod
    def utilization(handle, output):
        output._obj.gpu = (handle.value - 1000) * 20
        return 0


class SensorSourceIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Source regressions must not open a native window")

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.now = 100.0
        self.cpu_usage = 25
        self.power = PowerLibrary()
        self.nvml = NvmlLibrary()
        self.loader = self.stack.enter_context(
            patch("battery_sensor.c.WinDLL", return_value=self.power)
        )
        self.gpu_loader = self.stack.enter_context(patch("sensors.c.CDLL", return_value=self.nvml))
        self.process = self.stack.enter_context(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        self.thread = self.stack.enter_context(
            patch("threading.Thread.start", side_effect=AssertionError("No worker"))
        )
        self.stack.enter_context(patch("time.monotonic", side_effect=lambda: self.now))
        replacements = dict(
            cpu_name=lambda: "Synthetic CPU",
            AsusTemperature=lambda: SimpleNamespace(close=lambda: None),
            AsusFans=lambda *_: SimpleNamespace(sample_times={}, close=lambda: None),
            CpuPackagePower=lambda: SimpleNamespace(close=lambda: None),
            Activity=lambda: SimpleNamespace(
                read=lambda *_: dict(net_download=1.0), close=lambda: None
            ),
            StorageHealth=lambda *_: SimpleNamespace(read=lambda *_: {}, close=lambda: None),
            ExternalEngine=lambda: SimpleNamespace(
                read=lambda *_: dict(external_sensors={}), close=lambda: None
            ),
            hwinfo_registry=lambda cache=None: sensors.RegistryReadings(),
            INSPECT_UNTIL=0,
        )
        for name, value in replacements.items():
            self.stack.enter_context(patch.object(sensors, name, value))
        for name, value in dict(
            cpu_count=8,
            sensors_battery=None,
            virtual_memory=SimpleNamespace(
                percent=50, used=8 * 2**30, total=16 * 2**30, available=8 * 2**30
            ),
            swap_memory=SimpleNamespace(percent=0, used=0),
        ).items():
            self.stack.enter_context(patch("sensors.psutil." + name, return_value=value))
        self.stack.enter_context(
            patch("sensors.psutil.cpu_percent", side_effect=lambda **_: self.cpu_usage)
        )
        config = copy.deepcopy(DEFAULT)
        config.update(widget_order=[], widgets={})
        config["top_bar"].update(
            enabled=True,
            items=[
                dict(id="b_battery", metric="battery_watts", prefs={}),
                dict(id="b_network", metric="net_download", prefs={}),
                dict(id="b_memory", metric="ram_percent", prefs={}),
                dict(id="b_gpu", metric="gpu_usage", prefs={}),
            ],
        )
        self.config = validate(config)
        self.sampler = sensors.Sampler()
        self.sampler.first = False
        self.sampler.config_provider = lambda: self.config
        self.sampler.nvml_retry = float("inf")
        self.sampler.asus_status = dict(
            state="waiting_retry", error=dict(api="CreateFileW", winerror=2)
        )
        with patch.object(controls, "load", return_value=copy.deepcopy(self.config)):
            self.ui = controls.Controller()
        self.stack.enter_context(
            patch.object(controls, "save", side_effect=AssertionError("No persistence"))
        )

    def tearDown(self):
        self.ui.close()
        self.ui.deleteLater()
        self.sampler.close()
        self.app.processEvents()
        self.process.assert_not_called()
        self.thread.assert_not_called()

    def sample(self):
        self.now = round(self.now + 0.1, 6)
        data = self.sampler.sample()
        self.ui.receive(data)
        return data

    def row(self, metric, prefs=None):
        return next(row for row in self.ui.sensor_rows(prefs) if row["id"] == metric)

    def healthy(self, data):
        self.assertEqual(data["cpu_usage"], self.cpu_usage)
        self.assertEqual(data["ram_percent"], 50)
        self.assertEqual(data["net_download"], 1)
        self.assertEqual(data["provider_status"]["asus"]["error"]["winerror"], 2)

    def test_battery_load_is_lazy_and_failure_keeps_other_sources(self):
        self.loader.assert_not_called()
        self.loader.side_effect = denied()
        data = self.sample()
        self.healthy(data)
        status = data["battery_status"]
        self.assertEqual(status["state"], "query_failed")
        self.assertEqual(status["error"]["api"], "LoadLibraryW(PowrProf.dll)")
        self.assertEqual(status["error"]["winerror"], 5)
        self.assertIn("LoadLibraryW", self.row("battery_watts")["reason"])
        self.assertIn("Win32 5", self.row("battery_watts")["reason"])
        self.assertTrue(any(row["id"] == "battery" for row in self.ui.sourceDiagnostics))
        self.assertNotIn("PRIVATE_SOURCE", str(data["battery_status"]))

    def test_battery_load_backoff_and_recovery_require_no_restart(self):
        self.loader.side_effect = denied()
        self.sample()
        for _ in range(20):
            data = self.sample()
        self.loader.assert_called_once()
        self.assertEqual(data["battery_status"]["state"], "waiting_retry")
        self.loader.side_effect = None
        self.now = 160.1
        data = self.sample()
        self.assertEqual(self.loader.call_count, 2)
        self.assertEqual(data["battery_status"]["state"], "ready")
        self.assertNotIn("error", data["battery_status"])
        self.assertEqual(data["battery_watts"], 15)
        self.assertTrue(self.row("battery_watts")["available"])
        self.healthy(data)

    def test_battery_read_failure_drops_only_battery_values(self):
        self.assertEqual(self.sample()["battery_watts"], 15)
        self.power.error = denied()
        self.cpu_usage = 60
        data = self.sample()
        self.healthy(data)
        self.assertNotIn("battery_watts", data)
        self.assertNotIn("battery_present", data)
        self.assertFalse(self.row("battery_watts")["available"])
        self.assertIn("CallNtPowerInformation", self.row("battery_watts")["reason"])
        self.assertEqual(data["battery_status"]["error"]["errno"], 13)
        self.assertNotIn("secret.txt", str(data["battery_status"]))
        self.power.error = None
        self.now += 60
        self.assertEqual(self.sample()["battery_watts"], 15)

    def test_battery_ntstatus_is_preserved_during_backoff_and_cleared_on_success(self):
        self.power.ntstatus = -1073741790
        data = self.sample()
        self.assertEqual(data["battery_status"]["ntstatus"], -1073741790)
        self.assertEqual(data["battery_status"]["state"], "query_failed")
        self.assertIn("0xc0000022", self.row("battery_watts")["reason"].lower())
        data = self.sample()
        self.assertEqual(self.power.calls, 1)
        self.assertEqual(data["battery_status"]["state"], "waiting_retry")
        self.assertEqual(data["battery_status"]["ntstatus"], -1073741790)
        self.power.ntstatus = 0
        self.now += 60
        data = self.sample()
        self.assertEqual(data["battery_status"]["ntstatus"], 0)
        self.assertNotIn("error", data["battery_status"])

    def test_battery_absent_is_successful_query_and_not_api_failure(self):
        self.power.present = False
        data = self.sample()
        self.assertFalse(data["battery_present"])
        self.assertEqual(data["battery_status"]["state"], "no_battery")
        self.assertNotIn("error", data["battery_status"])
        self.assertIn("未发现电池", self.row("battery_watts")["reason"])
        diagnostic = next(row for row in self.ui.sourceDiagnostics if row["id"] == "battery")
        self.assertEqual(diagnostic["errors"], "")
        self.assertIn("查询成功", diagnostic["detail"])

    def test_missing_battery_entrypoint_is_local_and_does_not_hide_coding_errors(self):
        self.loader.return_value = SimpleNamespace()
        data = self.sample()
        self.healthy(data)
        self.assertEqual(
            data["battery_status"]["error"]["api"], "CallNtPowerInformation(SystemBatteryState)"
        )
        self.assertEqual(data["battery_status"]["error"]["reason"], "entrypoint_missing")
        self.loader.return_value = self.power
        self.now += 60
        self.power.error = ValueError("Synthetic coding error")
        with self.assertRaisesRegex(ValueError, "coding error"):
            self.sample()

    def enable_gpu(self):
        self.sampler.nvml_retry = 0

    def test_inaccessible_gpu_zero_retains_index_and_healthy_secondary_readings(self):
        self.nvml.handle_errors[0] = 4
        self.enable_gpu()
        data = self.sample()
        self.healthy(data)
        self.assertEqual(self.nvml.requested_indices, [0, 1])
        self.assertEqual(set(data["gpus"]), {"0", "1"})
        self.assertNotIn("gpu_usage", data)
        self.assertEqual(data["gpus"]["1"]["gpu_usage"], 20)
        self.assertTrue(self.row("gpu_usage", {"gpu_target": "1"})["available"])
        reason = self.row("gpu_usage", {"gpu_target": "0"})["reason"]
        self.assertIn("nvmlDeviceGetHandleByIndex_v2", reason)
        self.assertIn("status 4", reason)
        self.assertNotIn("未连接", reason)
        self.assertEqual(self.nvml.shutdowns, 0)

    def test_failed_secondary_gpu_does_not_replace_or_hide_primary_zero(self):
        self.nvml.handle_errors[1] = 15
        self.enable_gpu()
        data = self.sample()
        self.assertEqual(data["gpu_usage"], 0)
        self.assertEqual(data["gpus"]["0"]["gpu_usage"], 0)
        self.assertFalse(self.row("gpu_usage", {"gpu_target": "1"})["available"])
        self.assertIn("status 15", self.row("gpu_usage", {"gpu_target": "1"})["reason"])
        self.assertEqual(data["gpus"]["1"]["device_status"]["arguments"], [1])

    def test_known_failed_gpu_handle_retries_after_deadline_and_recovers_in_place(self):
        self.nvml.handle_errors[0] = 4
        self.enable_gpu()
        self.sample()
        for _ in range(20):
            self.sample()
        self.assertEqual(self.nvml.requested_indices, [0, 1])
        self.nvml.handle_errors.clear()
        self.now = 105.1
        data = self.sample()
        self.assertEqual(self.nvml.requested_indices, [0, 1, 0])
        self.assertEqual(data["gpu_usage"], 0)
        self.assertTrue(self.row("gpu_usage", {"gpu_target": "0"})["available"])
        self.assertEqual(data["gpus"]["0"]["device_status"]["state"], "available")
        self.assertEqual(self.gpu_loader.call_count, 1)

    def test_gpu_handle_exception_preserves_exact_api_error_and_peer(self):
        self.nvml.handle_errors[0] = denied()
        self.enable_gpu()
        data = self.sample()
        self.healthy(data)
        self.assertEqual(data["gpus"]["1"]["gpu_usage"], 20)
        reason = self.row("gpu_usage")["reason"]
        self.assertIn("nvmlDeviceGetHandleByIndex_v2", reason)
        self.assertIn("Win32 5", reason)
        diagnostic = next(row for row in self.ui.sourceDiagnostics if row["id"] == "nvml")
        self.assertIn("GPU 0", diagnostic["errors"])
        self.assertIn("Win32 5", diagnostic["errors"])
        self.assertNotIn("PRIVATE_SOURCE", str(diagnostic))
        self.assertNotIn("secret.txt", str(data["gpus"]["0"]))

    def test_all_gpu_handles_fail_then_global_backoff_recovers_without_old_values(self):
        self.nvml.handle_errors = {0: 4, 1: 15}
        self.enable_gpu()
        data = self.sample()
        self.healthy(data)
        self.assertIsNone(self.sampler.nvidia)
        self.assertEqual(self.nvml.shutdowns, 1)
        self.assertEqual(data["provider_status"]["nvml"]["reason"], "no_values")
        self.assertIn("status 15", self.row("gpu_usage", {"gpu_target": "1"})["reason"])
        for _ in range(20):
            data = self.sample()
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.assertNotIn("gpu_usage", data)
        self.nvml.handle_errors.clear()
        self.now = 105.1
        data = self.sample()
        self.assertEqual(self.gpu_loader.call_count, 2)
        self.assertEqual(data["gpu_usage"], 0)
        self.assertEqual(data["provider_status"]["nvml"]["state"], "connected")
        self.assertNotIn("error", data["gpus"]["0"]["device_status"])

    def test_gpu_count_failure_has_its_api_and_releases_initialized_library(self):
        self.nvml.count_status = 9
        self.enable_gpu()
        data = self.sample()
        self.healthy(data)
        status = data["provider_status"]["nvml"]
        self.assertEqual(status["error"]["api"], "nvmlDeviceGetCount_v2")
        self.assertEqual(status["error"]["status_code"], 9)
        self.assertEqual(self.nvml.shutdowns, 1)

    def test_no_gpu_devices_has_no_invented_status_error(self):
        self.nvml.device_count = 0
        self.enable_gpu()
        data = self.sample()
        self.healthy(data)
        self.assertEqual(data["gpus"], {})
        self.assertEqual(data["provider_status"]["nvml"]["error"], {})
        self.assertEqual(self.nvml.requested_indices, [])

    def test_gpu_coding_errors_are_not_swallowed_and_initialization_is_released(self):
        self.nvml.handle_errors[1] = ValueError("Synthetic coding error")
        self.enable_gpu()
        with self.assertRaisesRegex(ValueError, "coding error"):
            self.sample()
        self.assertEqual(self.nvml.shutdowns, 1)

    def test_failed_nvml_shutdown_can_be_retried_and_success_is_idempotent(self):
        for failure in (denied(), 9):
            with self.subTest(failure=type(failure).__name__):
                source = sensors.Nvidia.__new__(sensors.Nvidia)
                source.lib, source._initialized = self.nvml, True
                with patch.object(self.nvml, "nvmlShutdown", side_effect=[failure, 0]) as shutdown:
                    with self.assertRaises((OSError, sensors.ProviderApiError)):
                        source.close()
                    self.assertTrue(source._initialized)
                    source.close()
                    source.close()
                    self.assertFalse(source._initialized)
                    self.assertEqual(shutdown.call_count, 2)

    def test_sampler_close_exception_retains_each_owner_and_reports_incomplete(self):
        for field in ("nvidia", "storage", "external", "cpu_power"):
            with self.subTest(field=field):
                source = SimpleNamespace(close=Mock(side_effect=[OSError("Synthetic close"), None]))
                setattr(self.sampler, field, source)
                with patch("sensors.logging.exception"):
                    self.assertFalse(self.sampler.close())
                self.assertIs(getattr(self.sampler, field), source)
                self.assertEqual(source.close.call_count, 1)
                self.assertEqual(self.sampler.sample(), {})
                self.assertTrue(self.sampler.close())
                self.assertIsNone(getattr(self.sampler, field))
                self.assertEqual(source.close.call_count, 2)

    def test_failed_shutdown_retains_owner_and_read_error_until_bounded_recovery(self):
        self.enable_gpu()
        self.assertEqual(self.sample()["gpu_usage"], 0)
        source = self.sampler.nvidia
        loss = OSError("Synthetic read loss")
        loss.winerror = 1167
        self.nvml.shutdown_status = 9
        with patch.object(source, "read", side_effect=loss), patch("sensors.logging.exception"):
            data = self.sample()
        self.healthy(data)
        self.assertIsNone(self.sampler.nvidia)
        self.assertIs(self.sampler._nvml_cleanup, source)
        status = data["provider_status"]["nvml"]
        self.assertEqual(status["reason"], "read_failed")
        self.assertEqual(status["error"]["winerror"], 1167)
        self.assertTrue(status["cleanup_pending"])
        self.assertEqual(status["cleanup_error"]["api"], "nvmlShutdown")
        self.assertEqual(status["cleanup_error"]["status_code"], 9)
        self.assertGreater(status["cleanup_retry_in_seconds"], 0)
        diagnostic = next(row for row in self.ui.sourceDiagnostics if row["id"] == "nvml")
        self.assertIn("Win32 1167", diagnostic["errors"])
        self.assertIn("nvmlShutdown", diagnostic["errors"])
        self.assertIn("status 9", diagnostic["errors"])
        for _ in range(20):
            data = self.sample()
            self.healthy(data)
            self.assertNotIn("gpu_usage", data)
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.assertEqual(self.nvml.shutdowns, 1)
        self.nvml.shutdown_status = 0
        self.now += 5
        data = self.sample()
        self.assertEqual(self.nvml.shutdowns, 2)
        self.assertEqual(self.gpu_loader.call_count, 2)
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertFalse(source._initialized)
        self.assertEqual(data["gpu_usage"], 0)
        self.assertNotIn("cleanup_error", data["provider_status"]["nvml"])

    def test_pending_shutdown_failure_rearms_without_reinitializing(self):
        self.nvml.handle_errors = {0: 4, 1: 15}
        self.nvml.shutdown_error = denied()
        self.enable_gpu()
        with patch("sensors.logging.exception"):
            self.sample()
            source = self.sampler._nvml_cleanup
            self.now += 5
            data = self.sample()
            self.assertEqual(self.nvml.shutdowns, 2)
            for _ in range(20):
                data = self.sample()
        self.healthy(data)
        self.assertEqual(self.nvml.shutdowns, 2)
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.assertIs(self.sampler._nvml_cleanup, source)
        status = data["provider_status"]["nvml"]
        self.assertEqual(status["reason"], "no_values")
        self.assertEqual(status["cleanup_error"]["api"], "nvmlShutdown")
        self.assertEqual(status["cleanup_error"]["winerror"], 5)
        self.assertNotIn("PRIVATE_SOURCE", str(status["cleanup_error"]))
        self.assertNotIn("secret.txt", str(status["cleanup_error"]))
        self.nvml.shutdown_error = None

    def test_initialization_failure_retains_native_owner_when_shutdown_also_fails(self):
        self.nvml.count_status = 9
        self.nvml.shutdown_status = 4
        self.enable_gpu()
        with patch("sensors.logging.exception"):
            data = self.sample()
        source = self.sampler._nvml_cleanup
        self.healthy(data)
        self.assertIsNotNone(source)
        self.assertTrue(source._initialized)
        self.assertIsNone(self.sampler.nvidia)
        status = data["provider_status"]["nvml"]
        self.assertEqual(status["error"]["api"], "nvmlDeviceGetCount_v2")
        self.assertEqual(status["error"]["status_code"], 9)
        self.assertEqual(status["cleanup_error"]["api"], "nvmlShutdown")
        self.assertEqual(status["cleanup_error"]["status_code"], 4)
        for _ in range(20):
            self.sample()
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.assertEqual(self.nvml.shutdowns, 1)
        self.nvml.shutdown_status = self.nvml.count_status = 0
        self.now += 60
        self.assertEqual(self.sample()["gpu_usage"], 0)
        self.assertFalse(source._initialized)
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertEqual(self.gpu_loader.call_count, 2)

    def test_explicit_close_retries_pending_cleanup_without_waiting_or_reopening(self):
        self.nvml.handle_errors = {0: 4, 1: 15}
        self.nvml.shutdown_status = 9
        self.enable_gpu()
        with patch("sensors.logging.exception"):
            self.sample()
            source = self.sampler._nvml_cleanup
            self.assertFalse(self.sampler.close())
        self.assertIs(self.sampler._nvml_cleanup, source)
        self.assertEqual(self.nvml.shutdowns, 2)
        self.assertEqual(self.sampler.sample(), {})
        self.nvml.shutdown_status = 0
        self.assertTrue(self.sampler.close())
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertFalse(source._initialized)
        self.assertEqual(self.nvml.shutdowns, 3)
        self.assertEqual(self.gpu_loader.call_count, 1)

    def test_cleanup_false_is_pending_and_cannot_be_replaced_by_new_factory(self):
        source = SimpleNamespace(close=Mock(side_effect=[False, True]), read=Mock())
        self.sampler.nvidia = source
        self.sampler._release_nvidia("not_requested", retry_seconds=0)
        self.assertIs(self.sampler._nvml_cleanup, source)
        self.enable_gpu()
        self.healthy(self.sample())
        self.gpu_loader.assert_not_called()
        self.assertEqual(source.close.call_count, 1)
        self.now += 5
        data = self.sample()
        self.healthy(data)
        self.assertEqual(data["gpu_usage"], 0)
        self.assertEqual(source.close.call_count, 2)
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.gpu_loader.assert_called_once()

    def test_coding_error_with_failed_initialization_cleanup_remains_visible_and_owned(self):
        self.nvml.handle_errors[1] = ValueError("Synthetic coding error")
        self.nvml.shutdown_status = 9
        self.enable_gpu()
        with patch("sensors.logging.exception"), self.assertRaisesRegex(ValueError, "coding error"):
            self.sample()
        self.assertIsNotNone(self.sampler._nvml_cleanup)
        self.assertTrue(self.sampler._nvml_cleanup._initialized)
        self.assertEqual(self.sampler.nvml_status["reason"], "initialization_error")
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.nvml.shutdown_status = 0
        self.assertTrue(self.sampler.close())
        self.assertEqual(self.nvml.shutdowns, 2)

    def test_pending_cleanup_runs_without_gpu_demand_and_never_reopens_provider(self):
        self.enable_gpu()
        self.sample()
        source = self.sampler.nvidia
        self.config["top_bar"]["items"] = [
            row for row in self.config["top_bar"]["items"] if row["metric"] != "gpu_usage"
        ]
        self.nvml.shutdown_status = 9
        with patch("sensors.logging.exception"):
            data = self.sample()
        self.healthy(data)
        self.assertFalse(data["provider_status"]["nvml"]["requested"])
        self.assertEqual(data["provider_status"]["nvml"]["state"], "waiting_retry")
        self.assertGreater(data["provider_status"]["nvml"]["retry_in_seconds"], 0)
        self.assertIs(self.sampler._nvml_cleanup, source)
        self.nvml.shutdown_status = 0
        self.now += 5
        data = self.sample()
        self.healthy(data)
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertEqual(self.gpu_loader.call_count, 1)
        self.assertEqual(self.nvml.shutdowns, 2)
        self.assertEqual(data["provider_status"]["nvml"]["state"], "idle")
        self.assertNotIn("cleanup_error", data["provider_status"]["nvml"])


if __name__ == "__main__":
    unittest.main()
