"""Real diagnostic cards/exports retain API facts without device identities."""
import copy
import json
import unittest
from unittest.mock import patch

import diagnostic_actions as diagnostics
import sensors
from tests import test_workspace_tools as workspace_fixture
from tests.test_provider_recovery import synthetic_nvml


class DiagnosticExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace_fixture.WorkspaceToolsTests.setUpClass()

    def setUp(self):
        self.fixture = workspace_fixture.WorkspaceToolsTests()
        self.fixture.setUp()
        self.ui = self.fixture.ui

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def export(self, sample):
        self.ui._data = sample
        path = self.fixture.root / "synthetic-diagnostics.json"
        self.assertTrue(self.ui.exportDiagnosticsPath(path))
        return json.loads(path.read_text(encoding="utf-8"))

    def test_asus_dictionary_channel_fault_is_partial_and_recovers_after_the_fault_clears(self):
        sample = dict(provider_status={"asus": dict(state="connected", channel_errors={
            "0x00110013": dict(api="DeviceIoControl", winerror=5)})})
        self.ui._data = sample
        card = self.ui.diagnosticCards[0]
        self.assertFalse(card["healthy"])
        self.assertEqual(card["badge"], "部分可用")
        self.assertIn("DeviceIoControl", card["errors"])
        self.assertIn("Win32 5", card["errors"])
        report = self.export(sample)
        self.assertTrue(any(row.get("api") == "DeviceIoControl" and row.get("winerror") == 5
                            for row in report["sources"]["asus"]["failures"]))
        sample["provider_status"]["asus"]["channel_errors"].clear()
        self.assertTrue(self.ui.diagnosticCards[0]["healthy"])
        self.assertNotIn("failures", self.export(sample)["sources"]["asus"])

    def test_real_nvml_channel_failure_is_exported_anonymously_with_the_original_code(self):
        source, library = synthetic_nvml()
        try:
            sample = source.read()
            sample["provider_status"] = dict(nvml=dict(state="connected", error={}))
            report = self.export(sample)
            failures = report["sources"]["nvml"]["failures"]
            self.assertTrue(any(row.get("metric") == "gpu_fan_percent"
                                and row.get("api") == "nvmlDeviceGetFanSpeed"
                                and row.get("status_code") == 3 for row in failures))
            encoded = json.dumps(report)
            self.assertNotIn("Synthetic GPU", encoded)
            self.assertNotIn("gpus", report)
            self.assertFalse(any(row.get("state") == "available" for row in failures))
            library.failures.update({(device, "nvmlDeviceGetFanSpeed"): 0 for device in (1, 2)})
            recovered = source.read()
            recovered["provider_status"] = dict(nvml=dict(state="connected", error={}))
            self.assertNotIn("failures", self.export(recovered)["sources"]["nvml"])
        finally:
            source.close()

    def test_device_volume_registry_and_storage_failures_keep_safe_facts_only(self):
        private = "PRIVATE-NAME 10.0.0.8 C:/personal/secret.txt"
        fault = dict(api="psutil.disk_usage", errno=13, message=private, device_id=private)
        sample = dict(time=100, cpu_usage=99, provider_status={
            "volumes": dict(state="partial", device_errors={private: fault}),
            "hwinfo": dict(state="query_failed", exports=[dict(hive=private, state="query_failed",
                error=dict(api="winreg.OpenKey", winerror=5, message=private))]),
            "nvml": dict(state="connected")},
            gpus={private: dict(device_status=dict(state="query_failed",
                error=dict(api="nvmlDeviceGetHandleByIndex_v2", status_code=15, message=private)))},
            storage_status=dict(state="ready"), storages={private: dict(state="query_failed",
                api="IOCTL_STORAGE_QUERY_PROPERTY(NVMe health)", winerror=1, message=private)})
        report = self.export(sample)
        self.assertEqual(report["sources"]["volumes"]["failures"][0]["errno"], 13)
        self.assertEqual(report["sources"]["hwinfo"]["failures"][0]["error"]["winerror"], 5)
        self.assertEqual(report["sources"]["nvml"]["failures"][0]["error"]["status_code"], 15)
        self.assertEqual(report["sources"]["storage_status"]["failures"][0]["winerror"], 1)
        self.assertNotIn(private, json.dumps(report))
        self.assertNotIn("cpu_usage", report)

    def test_arbitrary_strings_and_device_keys_never_become_exported_machine_facts(self):
        private = "PRIVATE-NAME 10.0.0.8 C:/personal/secret.txt"
        sample = dict(provider_status={"nvml": dict(state="connected", channel_errors={private: {
            "state": private, "api": private, "reason": private, "type": private,
            "label": private, "message": private, "value": 99, "unit": private,
            "errno": True, "winerror": "5"}})}, gpus={private: dict(channel_status={private: {
                "state": "query_failed", "api": "nvmlDeviceGetFanSpeed", "status_code": 3,
                "arguments": [private], "label": private, "message": private}})})
        before = copy.deepcopy(sample)
        report = self.export(sample)
        self.assertNotIn(private, json.dumps(report))
        self.assertEqual(sample, before)
        failures = report["sources"]["nvml"]["failures"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["status_code"], 3)
        self.assertNotIn("metric", failures[0])
        self.assertNotIn("arguments", failures[0])

    def test_large_failure_sets_are_bounded_and_explicit_about_truncation(self):
        devices = {f"private-device-{index}": {"channel_status": {
            f"private-channel-{channel}": dict(state="query_failed", api="nvmlDeviceGetFanSpeed",
                status_code=3) for channel in range(100)}} for index in range(100)}
        report = self.export(dict(provider_status={"nvml": dict(state="connected")}, gpus=devices))
        source = report["sources"]["nvml"]
        self.assertLessEqual(len(source["failures"]), 64)
        self.assertTrue(source["failures_truncated"])
        self.assertNotIn("private-device", json.dumps(report))
        self.assertNotIn("private-channel", json.dumps(report))

    def test_hwinfo_list_channel_errors_and_healthy_sources_keep_their_existing_contract(self):
        sample = dict(provider_status={"hwinfo": dict(state="partial", channel_errors=[
            dict(api="HWiNFO VSB registry query", state="parse_error")]),
            "battery": dict(state="no_battery", ntstatus=0)})
        cards = diagnostics.cards(sample)
        self.assertFalse(cards[0]["healthy"])
        self.assertTrue(cards[1]["healthy"])
        report = self.export(sample)
        self.assertEqual(report["sources"]["hwinfo"]["failures"][0]["state"], "parse_error")
        self.assertNotIn("failures", report["sources"]["battery"])

    def test_real_two_hive_registry_optional_absence_is_healthy_but_actual_faults_remain_visible(self):
        class Key:
            def __init__(self, mode):
                self.mode = mode

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

        def registry(backup, primary=True):
            def open_key(hive, _path):
                mode = "ready" if hive == sensors.winreg.HKEY_CURRENT_USER and primary else (
                    backup if hive == sensors.winreg.HKEY_LOCAL_MACHINE else "missing")
                if mode in ("missing", "denied"):
                    error = FileNotFoundError("Synthetic optional hive") if mode == "missing" else PermissionError(
                        "Synthetic actual access failure")
                    error.winerror = 2 if mode == "missing" else 5
                    raise error
                return Key(mode)

            def entries(key):
                return list(dict(Sensor0="CPU Synthetic", Label0="CPU Package Power",
                                 ValueRaw0="1,234" if key.mode == "parse" else "43.8", Value0="43.8 W").items())

            with (patch("sensors.winreg.OpenKey", side_effect=open_key),
                  patch("sensors.winreg.QueryInfoKey", side_effect=lambda key: (
                      0, 4, int((1000 - (31 if key.mode == "stale" else 0) + 11644473600) * 1e7))),
                  patch("sensors.winreg.EnumValue", side_effect=lambda key, index: (
                      *entries(key)[index], sensors.winreg.REG_SZ)),
                  patch("sensors.time.time", return_value=1000),
                  patch("sensors.c.WinDLL", side_effect=AssertionError("No DLL")),
                  patch("sensors.c.CDLL", side_effect=AssertionError("No library"))):
                return sensors.hwinfo_registry()

        for backup in ("missing", "ready", "denied", "parse", "stale"):
            with self.subTest(backup=backup):
                reading = registry(backup)
                self.assertEqual(reading.diagnostics["state"], "available")
                sample = dict(provider_status={"hwinfo": reading.diagnostics})
                self.ui._data = sample
                card = self.ui.diagnosticCards[0]
                report = self.export(sample)["sources"]["hwinfo"]
                if backup in ("missing", "ready"):
                    self.assertTrue(card["healthy"])
                    self.assertNotIn("failures", report)
                else:
                    self.assertFalse(card["healthy"])
                    self.assertTrue(report["failures"])
                    if backup == "denied":
                        self.assertTrue(any(row.get("error", {}).get("winerror") == 5
                                            for row in report["failures"]))
        absent = registry("missing", primary=False)
        self.assertEqual(absent.diagnostics["state"], "export_absent")
        self.ui._data = dict(provider_status={"hwinfo": absent.diagnostics})
        self.assertFalse(self.ui.diagnosticCards[0]["healthy"])
        self.assertEqual(self.ui.diagnosticCards[0]["badge"], "未发现导出")
        self.assertEqual(self.export(self.ui._data)["sources"]["hwinfo"]["state"], "export_absent")


if __name__ == "__main__":
    unittest.main()
