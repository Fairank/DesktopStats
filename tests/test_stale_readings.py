"""Whole-sample expiry invalidates discovery, bindings and notified views together."""

import ast
import copy
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import native_controller as controls
from external_sensor import PROVIDER
from sensor_diagnostics import source_rows, unavailable_reason
from stats_config import DEFAULT, validate
from widget_catalog import from_template


class StaleReadingsTests(unittest.TestCase):
    def setUp(self):
        self.channel = dict(
            id="/synthetic/temperature/0",
            name="Synthetic temperature 原名",
            hardware_id="/synthetic",
            hardware_name="Synthetic device β",
            hardware_type="GpuNvidia",
            type="Temperature",
            unit="°C",
            value=42.0,
            min=40.0,
            max=43.0,
            available=True,
        )
        self.binding = dict(
            provider=PROVIDER,
            sensor_id=self.channel["id"],
            sensor_type="Temperature",
            name=self.channel["name"],
            hardware_name=self.channel["hardware_name"],
        )
        self.discovered = "lhm:" + hashlib.sha256(self.channel["id"].encode()).hexdigest()
        prefs = from_template("custom")
        prefs.update(
            content=["cpu_temp", "external_1"],
            sensor_bindings={"external_1": self.binding},
            width=300,
            height=160,
            form="free",
            show_title=False,
        )
        cfg = copy.deepcopy(DEFAULT)
        cfg.update(widgets={"one": prefs}, widget_order=["one"], mode="separate", language="en")
        with patch.object(controls, "load", return_value=validate(cfg)):
            self.ui = controls.Controller()
        for name in ("save", "set_autostart"):
            guard = patch.object(
                controls, name, side_effect=AssertionError("Unexpected IO: " + name)
            )
            guard.start()
            self.addCleanup(guard.stop)
        self.no_sampler = patch.object(
            controls.sensors, "Sampler", side_effect=AssertionError("No collector")
        )
        self.no_sampler.start()
        self.addCleanup(self.no_sampler.stop)
        self.events = []
        self.cached = {}
        self.ui.dataChanged.connect(lambda: self.events.append("data"))
        self.ui.sensorsChanged.connect(self.observe_sensors)

    def observe_sensors(self):
        self.events.append("sensors")
        self.cached.update(
            rows=copy.deepcopy(self.ui.sensorRows),
            status=copy.deepcopy(self.ui.externalStatus),
            diagnostics=copy.deepcopy(self.ui.sourceDiagnostics),
        )

    def sample(self, timestamp=100.0, **changes):
        data = dict(
            time=timestamp,
            cpu_temp=77.0,
            cpu_usage=18,
            cpu_temp_source="ASUS ACPI",
            gpus={
                "0": dict(
                    label="Synthetic GPU",
                    gpu_power=9.5,
                    gpu_usage=12,
                    gpu_source="NVIDIA NVML",
                    channel_status={
                        "gpu_fan_percent": dict(
                            state="query_failed", api="nvmlDeviceGetFanSpeed", status_code=3
                        )
                    },
                )
            },
            storages={
                "0": dict(
                    label="Synthetic NVMe",
                    storage_temp=59,
                    storage_spare_percent=100,
                    storage_wear_percent=2,
                    state="available",
                )
            },
            storage_status=dict(state="ready"),
            provider_status={
                "nvml": dict(state="connected"),
                "hwinfo": dict(state="export_absent"),
            },
            external_catalog={self.channel["id"]: self.channel},
            external_revision=1,
            external_status=dict(
                state="ready",
                sensor_count=1,
                available_count=1,
                hardware_count=1,
                updated_at=timestamp,
                version="synthetic",
            ),
        )
        data.update(changes)
        self.ui.receive(data)
        self.events.clear()
        return data

    def row(self, identifier, cached=False):
        rows = self.cached["rows"] if cached else self.ui.sensorRows
        return next(row for row in rows if row["id"] == identifier)

    def test_expiry_notifies_both_observers_and_clears_cached_values_once(self):
        self.sample()
        revision = self.ui.sensorRevision
        self.assertTrue(self.ui.expire_readings(135))
        self.assertEqual(self.events, ["data", "sensors"])
        self.assertEqual(self.ui.sensorRevision, revision + 1)
        self.assertEqual(self.row("cpu_temp", True)["value"], "—")
        self.assertEqual(self.row(self.discovered, True)["value"], "—")
        self.assertFalse(self.row(self.discovered, True)["available"])
        self.assertEqual(self.row("cpu_temp", True)["reason"], self.ui.tr("读数已过期"))
        self.assertEqual(self.row(self.discovered, True)["reason"], self.ui.tr("读数已过期"))
        self.assertEqual(self.cached["status"]["state"], "stale")
        self.assertEqual(self.cached["status"]["available_count"], 0)
        self.assertEqual(self.ui._data["time"], 100)
        self.assertEqual(self.ui._data["sample_status"]["last_sample_time"], 100)
        self.assertEqual(self.ui._data["sample_status"]["invalidated_at"], 135)
        before = copy.deepcopy(self.ui._data)
        self.events.clear()
        self.assertFalse(self.ui.expire_readings(140))
        self.assertEqual(self.ui._data, before)
        self.assertEqual(self.events, [])
        self.assertEqual(self.ui.sensorRevision, revision + 1)

    def test_expiry_retains_identity_unit_inventory_and_observed_errors_not_values(self):
        original = self.sample()
        source_snapshot = copy.deepcopy(original)
        devices = copy.deepcopy(self.ui.devices)
        discovered_ids = copy.deepcopy(self.ui._discovered_ids)
        self.assertTrue(self.ui.expire_readings(136))
        row = self.ui._external_rows[self.channel["id"]]
        for key in ("id", "name", "hardware_id", "hardware_name", "hardware_type", "type", "unit"):
            self.assertEqual(row[key], self.channel[key])
        for key in ("value", "min", "max"):
            self.assertIsNone(row[key])
        self.assertFalse(row["available"])
        self.assertEqual(self.ui._discovered_ids, discovered_ids)
        self.assertEqual(self.ui.devices, devices)
        self.assertEqual(original, source_snapshot)  # Do not mutate worker-owned catalog.
        self.assertEqual(self.ui._data["provider_status"], original["provider_status"])
        self.assertEqual(
            self.ui._data["gpus"]["0"]["channel_status"], original["gpus"]["0"]["channel_status"]
        )
        self.assertNotIn("gpu_power", self.ui._data["gpus"]["0"])
        self.assertNotIn("storage_temp", self.ui._data["storages"]["0"])
        self.assertNotIn("cpu_temp", self.ui._data)
        self.assertEqual(self.ui._data["external_status"]["updated_at"], 100)

    def test_existing_binding_and_style_edit_cannot_resurrect_old_value_or_history(self):
        self.sample()
        self.assertEqual(self.ui.readingFor("one", "external_1"), "42.0 °C")
        self.assertTrue(self.ui._history)
        self.ui.expire_readings(136)
        self.assertFalse(self.ui._history)
        self.assertEqual(self.ui.readingFor("one", "external_1"), "—")
        self.ui.change("theme", "dark")
        self.assertEqual(self.ui.readingFor("one", "external_1"), "—")
        self.assertIsNone(self.ui._data["external_sensors"][self.channel["id"]]["value"])
        self.assertEqual(self.ui._data["sample_status"]["state"], "stale")
        self.assertFalse(self.ui._history)

    def test_new_widget_and_top_bar_bindings_from_expired_discovery_remain_unavailable(self):
        self.ui.changeWidget("one", "content", ["cpu_temp"])
        self.ui.changeWidget("one", "sensor_bindings", {})
        self.sample()
        self.ui.expire_readings(136)
        self.ui.addMetric("one", self.discovered)
        self.assertEqual(self.ui.readingFor("one", "external_1"), "—")
        self.assertTrue(self.ui.addTopBarMetric(self.discovered))
        last = self.ui.topBarDraftRows()[-1]
        self.assertEqual(last["value"], "—")
        self.assertFalse(last["available"])
        self.assertIn(self.channel["id"], self.ui._data["external_sensors"])
        self.assertIsNone(self.ui._data["external_sensors"][self.channel["id"]]["value"])

    def test_fresh_sample_recovers_same_catalog_object_and_provider_revision_even_zero(self):
        self.channel.update(value=0.0, min=0.0, max=0.0)
        original = self.sample()
        self.assertEqual(self.ui.readingFor("one", "external_1"), "0.0 °C")
        with patch.object(controls.time, "monotonic", return_value=20.0):
            self.ui.expire_readings(136)
            revision = self.ui.sensorRevision
            self.events.clear()
            self.ui.receive(dict(original, time=136.0))
        self.assertEqual(self.events, ["data", "sensors"])
        self.assertEqual(self.ui.sensorRevision, revision + 1)
        self.assertEqual(self.ui.readingFor("one", "external_1"), "0.0 °C")
        self.assertEqual(self.row(self.discovered)["value"], "0.0 °C")
        self.assertTrue(self.row(self.discovered)["available"])
        self.assertEqual(self.ui.externalStatus["state"], "ready")
        self.assertNotIn("sample_status", self.ui.readings)
        self.assertEqual(len(self.ui._history), 1)
        self.assertFalse(self.ui.expire_readings(136.5))

    def test_empty_and_under_35_seconds_are_unchanged_future_and_bad_timestamps_expire(self):
        self.assertFalse(self.ui.expire_readings(135))
        self.sample()
        snapshot = copy.deepcopy(self.ui._data)
        self.assertFalse(self.ui.expire_readings(134.999))
        self.assertEqual(self.ui._data, snapshot)
        self.assertEqual(self.events, [])
        for timestamp in (200, None, "bad", float("nan"), float("inf"), True):
            with self.subTest(timestamp=timestamp):
                self.sample(timestamp)
                self.assertTrue(self.ui.expire_readings(136))
                self.assertEqual(self.ui._data["sample_status"]["state"], "stale")
                self.assertEqual(self.row("cpu_temp")["value"], "—")
                self.assertEqual(self.ui.topBarDraftRows()[0]["value"], "—")

    def test_stale_reason_has_priority_over_unsupported_and_diagnostics_show_sampler(self):
        self.sample()
        self.ui.expire_readings(136)
        self.assertEqual(unavailable_reason(self.ui._data, "gpu_fan_percent"), "读数已过期")
        rows = source_rows(self.ui._data)
        self.assertEqual(
            rows[0],
            dict(id="sample", label="Sampler", state="stale", detail="读数已过期", errors=""),
        )
        gpu = next(row for row in rows if row["id"] == "nvml")
        self.assertIn("nvmlDeviceGetFanSpeed", gpu["errors"])
        self.assertIn("status 3", gpu["errors"])
        self.assertEqual(self.cached["diagnostics"][0]["detail"], self.ui.tr("读数已过期"))

    def test_previous_external_error_is_preserved_as_history_not_current_expiry_reason(self):
        self.sample(
            external_status=dict(
                state="error",
                detail="Synthetic collector exited with code 7",
                sensor_count=1,
                available_count=0,
                hardware_count=1,
            )
        )
        self.ui.expire_readings(136)
        status = self.ui.externalStatus
        self.assertEqual(status["state"], "stale")
        self.assertEqual(status["detail"], "读数已过期")
        self.assertEqual(status["last_state"], "error")
        self.assertEqual(status["last_detail"], "Synthetic collector exited with code 7")
        row = next(row for row in source_rows(self.ui._data) if row["id"] == "external")
        self.assertEqual(row["detail"], "读数已过期")
        self.assertIn("previous_state (historical): error", row["errors"])
        self.assertIn(
            "previous_detail (historical): Synthetic collector exited with code 7", row["errors"]
        )

    def test_runtime_timer_uses_controller_invalidation_entry_without_native_runtime(self):
        path = Path(__file__).resolve().parents[1] / "native_runtime.py"
        runtime = next(
            node
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef) and node.name == "Runtime"
        )
        method = next(
            node
            for node in runtime.body
            if isinstance(node, ast.FunctionDef) and node.name == "clear_stale"
        )
        namespace = {}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                str(path),
                "exec",
            ),
            namespace,
        )
        fake = SimpleNamespace(controller=SimpleNamespace(expire_readings=Mock()))
        namespace["clear_stale"](fake)
        fake.controller.expire_readings.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
