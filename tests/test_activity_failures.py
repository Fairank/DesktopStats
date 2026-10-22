"""Real Activity -> Sampler -> Controller diagnostics with mocked read-only APIs."""

import copy
import json
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


class ActivityFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("No desktop UI in activity regressions")

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.native = self.stack.enter_context(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native API"))
        )
        self.process = self.stack.enter_context(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        self.now, self.net_bytes, self.disk_bytes = 10.0, 100, 100
        self.network_error = self.stats_error = self.disk_error = self.volume_error = None
        config = copy.deepcopy(DEFAULT)
        config.update(widget_order=[], widgets={})
        config["top_bar"].update(
            enabled=True,
            items=[
                dict(id="b_network", metric="net_download", prefs={"style": "duplex"}),
                dict(id="b_disk", metric="disk_read", prefs={"style": "value"}),
                dict(id="b_volume", metric="disk_percent", prefs={"style": "value"}),
            ],
        )
        self.config = validate(config)
        self.stack.enter_context(patch.dict(os.environ, {"SystemDrive": "C:"}))
        self.stack.enter_context(
            patch("activity_sensors.time.monotonic", side_effect=lambda: self.now)
        )
        self.stack.enter_context(patch("sensors.cpu_name", return_value="Synthetic CPU"))
        self.stack.enter_context(
            patch("sensors.AsusTemperature", return_value=SimpleNamespace(close=lambda: None))
        )
        self.stack.enter_context(
            patch(
                "sensors.AsusFans",
                return_value=SimpleNamespace(sample_times={}, close=lambda: None),
            )
        )
        self.stack.enter_context(
            patch("sensors.CpuPackagePower", return_value=SimpleNamespace(close=lambda: None))
        )
        self.stack.enter_context(
            patch(
                "sensors.Battery", return_value=SimpleNamespace(read=lambda: {}, close=lambda: None)
            )
        )
        self.stack.enter_context(
            patch(
                "sensors.StorageHealth",
                return_value=SimpleNamespace(read=lambda *_: {}, close=lambda: None),
            )
        )
        self.stack.enter_context(
            patch(
                "sensors.ExternalEngine",
                return_value=SimpleNamespace(
                    read=lambda *_: {"external_sensors": {}}, close=lambda: None
                ),
            )
        )
        self.stack.enter_context(
            patch("sensors.hwinfo_registry", return_value=sensors.RegistryReadings())
        )
        self.stack.enter_context(patch("sensors.psutil.cpu_count", return_value=8))
        self.stack.enter_context(patch("sensors.psutil.cpu_percent", return_value=25))
        self.stack.enter_context(patch("sensors.psutil.sensors_battery", return_value=None))
        self.stack.enter_context(
            patch(
                "sensors.psutil.virtual_memory",
                return_value=SimpleNamespace(
                    percent=50, used=8 * 2**30, total=16 * 2**30, available=8 * 2**30
                ),
            )
        )
        self.stack.enter_context(
            patch("sensors.psutil.swap_memory", return_value=SimpleNamespace(percent=0, used=0))
        )
        self.stack.enter_context(
            patch("activity_sensors.psutil.net_io_counters", side_effect=self.net_counters)
        )
        self.stack.enter_context(
            patch("activity_sensors.psutil.net_if_stats", side_effect=self.net_stats)
        )
        self.stack.enter_context(
            patch("activity_sensors.psutil.disk_io_counters", side_effect=self.disk_counters)
        )
        self.stack.enter_context(
            patch("activity_sensors.psutil.disk_usage", side_effect=self.disk_usage)
        )
        self.sampler = sensors.Sampler()
        self.sampler.first = False
        self.sampler.config_provider = lambda: self.config
        self.sampler.activity.volumes = ["C:\\"]
        self.sampler.activity.next_volumes = float("inf")
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
        self.native.assert_not_called()
        self.process.assert_not_called()

    @staticmethod
    def failure(code=5):
        error = PermissionError(13, "PRIVATE_ADAPTER_AND_FILE_CONTENT", "C:/private/secret.txt")
        error.winerror = code
        return error

    def net_counters(self, **_kwargs):
        if self.network_error:
            raise self.network_error
        return {
            "Synthetic NIC": SimpleNamespace(bytes_recv=self.net_bytes, bytes_sent=self.net_bytes)
        }

    def net_stats(self):
        if self.stats_error:
            raise self.stats_error
        return {"Synthetic NIC": SimpleNamespace(isup=True)}

    def disk_counters(self, **_kwargs):
        if self.disk_error:
            raise self.disk_error
        return {
            "Synthetic disk": SimpleNamespace(
                read_bytes=self.disk_bytes, write_bytes=self.disk_bytes
            )
        }

    def disk_usage(self, _path):
        if self.volume_error:
            raise self.volume_error
        return SimpleNamespace(percent=25, used=25 * 2**30, free=75 * 2**30, total=100 * 2**30)

    def sample(self):
        self.now = round(self.now + 0.1, 6)
        data = self.sampler.sample()
        self.ui.receive(data)
        return data

    def row(self, metric):
        return next(row for row in self.ui.sensorRows if row["id"] == metric)

    def assert_private_text_absent(self, data):
        visible = json.dumps(
            [data.get("provider_status"), self.ui.sourceDiagnostics, self.ui.sensorRows]
        )
        self.assertNotIn("PRIVATE_ADAPTER", visible)
        self.assertNotIn("secret.txt", visible)
        self.assertNotIn("C:/private", visible)

    def test_network_api_denial_reaches_controller_with_exact_codes(self):
        self.network_error = self.failure()
        data = self.sample()
        status = data["provider_status"]["network"]
        self.assertEqual(status["state"], "query_failed")
        self.assertEqual(status["error"]["api"], "psutil.net_io_counters")
        self.assertEqual(status["error"]["winerror"], 5)
        self.assertEqual(status["error"]["errno"], 13)
        row = self.row("net_download")
        self.assertFalse(row["available"])
        self.assertIn("psutil.net_io_counters", row["reason"])
        self.assertIn("Win32 5", row["reason"])
        self.assertNotIn("两次", row["reason"])
        diagnostic = next(row for row in self.ui.sourceDiagnostics if row["id"] == "network")
        self.assertIn("Win32 5", diagnostic["errors"])
        self.assertEqual(data["provider_status"]["asus"]["error"]["winerror"], 2)
        self.assert_private_text_absent(data)

    def test_interface_status_failure_does_not_claim_counter_api_failed(self):
        self.stats_error = RuntimeError("PRIVATE_ADAPTER_AND_FILE_CONTENT")
        data = self.sample()
        error = data["provider_status"]["network"]["error"]
        self.assertEqual(error["api"], "psutil.net_if_stats")
        self.assertNotIn("winerror", error)
        self.assertIn("psutil.net_if_stats", self.row("net_download")["reason"])
        self.assert_private_text_absent(data)

    def test_disk_io_failure_does_not_hide_successful_volume_capacity(self):
        self.disk_error = self.failure(21)
        data = self.sample()
        self.assertEqual(data["provider_status"]["disk"]["error"]["api"], "psutil.disk_io_counters")
        self.assertIn("Win32 21", self.row("disk_read")["reason"])
        self.assertTrue(self.row("disk_percent")["available"])
        self.assertEqual(data["disk_percent"], 25)
        self.assert_private_text_absent(data)

    def test_volume_failure_discards_old_capacity_without_claiming_disconnection(self):
        self.sample()
        self.assertTrue(self.row("disk_percent")["available"])
        self.volume_error = self.failure()
        data = self.sample()
        self.assertIsNone(data.get("disk_percent"))
        self.assertNotIn("disk_percent", data["volumes"]["C:\\"])
        row = self.row("disk_percent")
        self.assertFalse(row["available"])
        self.assertIn("psutil.disk_usage", row["reason"])
        self.assertNotIn("未连接", row["reason"])
        self.assertEqual(data["provider_status"]["disk"]["state"], "ready")
        self.assert_private_text_absent(data)

    def test_recovery_rebuilds_baseline_without_clearing_other_failure(self):
        self.sample()
        self.net_bytes += 1000000
        self.disk_bytes += 1000000
        self.sample()
        self.assertTrue(self.row("net_download")["available"])
        self.network_error = self.disk_error = self.failure()
        self.sample()
        self.assertFalse(self.row("net_download")["available"])
        self.assertFalse(self.row("disk_read")["available"])
        self.network_error = None
        self.net_bytes += 1000000
        data = self.sample()
        self.assertEqual(data["provider_status"]["network"]["state"], "warming_up")
        self.assertNotIn("error", data["provider_status"]["network"])
        self.assertFalse(self.row("net_download")["available"])
        self.assertNotIn("Win32", self.row("net_download")["reason"])
        self.assertEqual(data["provider_status"]["disk"]["state"], "query_failed")
        self.net_bytes += 1000000
        data = self.sample()
        self.assertEqual(data["provider_status"]["network"]["state"], "ready")
        self.assertTrue(self.row("net_download")["available"])
        self.assertAlmostEqual(data["net_download"], 10)
        self.assertIn("Win32 5", self.row("disk_read")["reason"])

    def test_empty_inventory_is_distinct_from_query_failure_and_warmup(self):
        with patch("activity_sensors.psutil.net_io_counters", return_value={}):
            data = self.sample()
        self.assertEqual(data["provider_status"]["network"]["state"], "no_devices")
        self.assertNotIn("两次", self.row("net_download")["reason"])
        self.assertNotIn("error", data["provider_status"]["network"])

    def test_partition_query_failure_has_its_own_provider(self):
        self.sampler.activity.next_volumes = 0
        drive_type = Mock(return_value=3)
        with (
            patch(
                "activity_sensors.ctypes.windll",
                SimpleNamespace(kernel32=SimpleNamespace(GetDriveTypeW=drive_type)),
            ),
            patch("activity_sensors.psutil.disk_partitions", side_effect=self.failure()),
        ):
            data = self.sample()
        self.assertEqual(
            data["provider_status"]["volumes"]["error"]["api"], "psutil.disk_partitions"
        )
        self.assertIn("psutil.disk_partitions", self.row("disk_percent")["reason"])
        self.assert_private_text_absent(data)

    def test_selected_adapter_query_failure_is_not_mislabeled_as_disconnection(self):
        prefs = self.ui._saved["top_bar"]["items"][0]["prefs"]
        prefs["network_target"] = "Synthetic NIC"
        self.network_error = self.failure()
        data = self.sample()
        item = self.ui.topBarRows()[0]
        self.assertFalse(item["available"])
        self.assertIn("psutil.net_io_counters", item["reason"])
        self.assertNotIn("未连接", item["reason"])
        self.assertEqual(data["networks"], {})
        self.assertNotIn("net_received_gb", data)
        self.assert_private_text_absent(data)

    def test_partial_volume_error_does_not_hide_healthy_volume_or_survive_recovery(self):
        self.sampler.activity.volumes = ["C:\\", "D:\\"]

        def read_volume(path):
            if path == "C:\\":
                raise self.failure()
            return self.disk_usage(path)

        with patch("activity_sensors.psutil.disk_usage", side_effect=read_volume):
            data = self.sample()
        self.assertEqual(data["provider_status"]["volumes"]["state"], "partial")
        self.assertEqual(data["volumes"]["D:\\"]["disk_percent"], 25)
        self.assertFalse(self.row("disk_percent")["available"])
        self.assertIn("psutil.disk_usage", self.row("disk_percent")["reason"])
        self.assert_private_text_absent(data)
        data = self.sample()
        self.assertEqual(data["provider_status"]["volumes"]["state"], "ready")
        self.assertNotIn("device_errors", data["provider_status"]["volumes"])
        self.assertTrue(self.row("disk_percent")["available"])
        diagnostic = next(row for row in self.ui.sourceDiagnostics if row["id"] == "volumes")
        self.assertEqual(diagnostic["errors"], "")

    def test_psutil_exception_omits_private_text_and_invented_os_codes(self):
        self.network_error = sensors.psutil.Error("PRIVATE_ADAPTER_AND_FILE_CONTENT")
        data = self.sample()
        error = data["provider_status"]["network"]["error"]
        self.assertEqual(error, dict(api="psutil.net_io_counters", reason="psutil.Error"))
        self.assertIn("psutil.net_io_counters", self.row("net_download")["reason"])
        self.assertNotIn("Win32", self.row("net_download")["reason"])
        self.assert_private_text_absent(data)


if __name__ == "__main__":
    unittest.main()
