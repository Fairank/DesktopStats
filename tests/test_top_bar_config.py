"""Opt-in bars, typed bindings, draft transactions and truthful source explanations."""

import copy
import unittest
from unittest.mock import patch

import native_controller as controls
from external_sensor import PROVIDER, parse_snapshot
from metrics import required_sources
from sensor_diagnostics import source_rows, unavailable_reason
from stats_config import DEFAULT, validate
from top_bar_config import default_top_bar, validate_top_bar


class TopBarConfigTests(unittest.TestCase):
    def test_legacy_preferences_keep_desktop_and_do_not_enable_bar(self):
        legacy = copy.deepcopy(DEFAULT)
        legacy.pop("top_bar")
        result = validate(legacy)
        self.assertFalse(result["top_bar"]["enabled"])
        self.assertEqual(result["widgets"], legacy["widgets"])
        self.assertEqual(result["widget_order"], legacy["widget_order"])
        self.assertEqual(validate(result), result)

    def test_bar_collects_sources_even_when_desktop_widgets_hidden(self):
        config = copy.deepcopy(DEFAULT)
        config["visible"] = False
        self.assertEqual(required_sources(config), set())
        config["top_bar"]["enabled"] = True
        self.assertEqual(required_sources(config), {"cpu", "gpu", "memory", "battery"})

    def test_limits_and_invalid_preferences_are_rejected(self):
        for changes in (
            {"enabled": 1},
            {"height": 31},
            {"height": 32.0},
            {"screens": ["x", "x"]},
            {"screens": [""]},
            {"screens": ["x\n"]},
            {"monitor_mode": "overlay"},
            {"unknown": True},
            {"items": default_top_bar()["items"] * 11},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_top_bar(dict(default_top_bar(), **changes))

    def test_duplicate_metrics_can_target_distinct_devices_with_stable_ids(self):
        value = default_top_bar()
        value["items"] = [
            dict(id="b_a", metric="gpu_power", prefs={"gpu_target": "0"}),
            dict(id="b_b", metric="gpu_power", prefs={"gpu_target": "1"}),
        ]
        self.assertEqual(len(validate_top_bar(value)["items"]), 2)
        value["items"][1]["id"] = "b_a"
        with self.assertRaises(ValueError):
            validate_top_bar(value)

    def test_external_binding_is_exact_not_a_name_or_gpu_index_guess(self):
        value = default_top_bar()
        binding = dict(
            provider=PROVIDER,
            sensor_id="/amdgpu/0/power/0",
            sensor_type="Power",
            name="Power",
            hardware_name="iGPU",
        )
        value["items"] = [
            dict(
                id="b_custom",
                metric="external_1",
                prefs={"sensor_bindings": {"external_1": binding}},
            )
        ]
        self.assertEqual(
            validate_top_bar(value)["items"][0]["prefs"]["sensor_bindings"]["external_1"], binding
        )
        value["items"][0]["metric"] = "gpu_power"
        with self.assertRaises(ValueError):
            validate_top_bar(value)


class TopBarControllerTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()

    def test_add_reorder_remove_is_draft_only_and_undoable(self):
        original = copy.deepcopy(self.ui._saved)
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.addTopBarMetric("cpu_power"))
            identifier = self.ui._draft["top_bar"]["items"][-1]["id"]
            self.ui.moveTopBarMetric(identifier, -1)
            self.assertEqual(self.ui._draft["top_bar"]["items"][-2]["id"], identifier)
            self.ui.removeTopBarMetric(identifier)
            self.assertEqual(len(self.ui._draft["top_bar"]["items"]), 6)
            self.ui.undoDraft()
            self.assertEqual(len(self.ui._draft["top_bar"]["items"]), 7)
            save.assert_not_called()
        self.assertEqual(self.ui._saved, original)

    def test_saved_rows_use_saved_targets_and_zero_is_not_unavailable(self):
        self.ui._data = {"time": 100, "gpus": {"0": {"gpu_power": 0.0}, "1": {"gpu_power": 24.5}}}
        identifier = self.ui._saved["top_bar"]["items"][4]["id"]
        self.ui.changeTopBarItem(identifier, "gpu_target", "1")
        with patch.object(controls.time, "time", return_value=101):
            live = self.ui.topBarRows()[4]
            draft = self.ui.topBarDraftRows()[4]
        self.assertTrue(live["available"])
        self.assertEqual(live["value"], "0.0 W")
        self.assertEqual(draft["value"], "24.5 W")
        with patch.object(controls.time, "time", return_value=200):
            self.assertFalse(self.ui.topBarRows()[4]["available"])

    def test_bar_binding_survives_inventory_optimization(self):
        row = dict(
            id="/amdgpu/0/power/0",
            type="Power",
            name="Chip",
            hardware_name="iGPU",
            hardware_type="GpuAmd",
            unit="W",
            value=4.2,
            available=True,
        )
        self.ui._external_rows = {row["id"]: row}
        self.ui._discovered_ids = {"lhm:example": row["id"]}
        self.assertTrue(self.ui.addTopBarMetric("lhm:example"))
        self.assertIn(row["id"], self.ui._data["external_sensors"])
        with patch.object(controls, "save"):
            self.ui.apply()
        self.assertEqual(self.ui._saved["top_bar"]["items"][-1]["metric"], "external_1")

    def test_disconnected_monitor_is_kept_as_explicit_choice(self):
        self.ui.changeTopBar("screens", ["disconnected-display"])
        self.assertEqual(self.ui.topBarScreenChoices[0]["id"], "disconnected-display")

    def test_top_bar_choices_use_native_ids_and_disambiguate_duplicate_friendly_labels(self):
        self.ui.set_screen_inventory(
            [
                dict(
                    id="Same panel",
                    label="Same panel",
                    native_id=r"\\.\DISPLAY1",
                    primary=True,
                    x=0,
                    y=0,
                    width=1920,
                    height=1080,
                ),
                dict(
                    id="Same panel",
                    label="Same panel",
                    native_id=r"\\.\DISPLAY2",
                    primary=False,
                    x=-2560,
                    y=-200,
                    width=2560,
                    height=1440,
                ),
                dict(
                    id="Unmapped",
                    label="Unmapped",
                    native_id="",
                    primary=False,
                    x=1920,
                    y=0,
                    width=1920,
                    height=1080,
                ),
            ]
        )
        rows = self.ui.topBarScreenChoices
        self.assertEqual([row["id"] for row in rows], [r"\\.\DISPLAY1", r"\\.\DISPLAY2"])
        self.assertNotEqual(rows[0]["label"], rows[1]["label"])
        self.assertTrue(
            all("Same panel" in row["label"] and row["id"] in row["label"] for row in rows)
        )
        # Ordinary desktop screen IDs retain their old contract.
        self.assertEqual(
            [row["id"] for row in self.ui.screenChoices],
            ["", "Same panel", "Same panel", "Unmapped"],
        )
        self.ui.changeTopBar("screens", ["Same panel"])
        offline = next(row for row in self.ui.topBarScreenChoices if row["id"] == "Same panel")
        self.assertIn(self.ui.tr("未连接"), offline["label"])

    def test_saved_bar_language_does_not_change_with_unapplied_editor_language(self):
        original = self.ui.topBarRows()[0]["label"]
        self.ui.change("language", "en")
        self.assertEqual(self.ui.topBarRows()[0]["label"], original)
        self.assertEqual(self.ui.topBarDraftRows()[0]["label"], "CPU usage")


class DiagnosticTests(unittest.TestCase):
    def test_collector_diagnostic_counts_are_preserved_and_bounded(self):
        payload = dict(
            schema=1,
            provider=PROVIDER,
            version="0.9.6",
            timestamp=1000,
            hardware=[],
            sensors=[],
            update_errors=3,
            skipped_types=2,
            truncated=1,
        )
        result = parse_snapshot(payload)
        self.assertEqual(
            [result[key] for key in ("update_errors", "skipped_types", "truncated")], [3, 2, 1]
        )
        for invalid in (True, -1, 1_000_001, float("nan"), "3"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_snapshot(dict(payload, update_errors=invalid))

    def test_nvml_exact_status_is_explained_not_inferred_from_null(self):
        data = {
            "gpus": {
                "0": {
                    "channel_status": {
                        "gpu_fan_percent": dict(
                            state="query_failed",
                            api="nvmlDeviceGetFanSpeed",
                            status_code=3,
                            status_text="Not Supported",
                        )
                    }
                }
            }
        }
        reason = unavailable_reason(data, "gpu_fan_percent")
        self.assertIn("明确", reason)
        self.assertIn("status 3", reason)
        self.assertIn("尚无有效读数", unavailable_reason({}, "gpu_fan_percent"))

    def test_absent_hwinfo_export_is_not_reported_as_permission_failure(self):
        data = {
            "provider_status": {
                "hwinfo": dict(
                    state="export_absent",
                    exports=[dict(hive="HKCU", state="query_failed", error=dict(winerror=2))],
                )
            }
        }
        reason = unavailable_reason(data, "system_power")
        self.assertIn("不存在", reason)
        self.assertIn("不是权限", reason)
        self.assertIn("Win32 2", source_rows(data)[0]["errors"])

    def test_present_null_external_channel_does_not_claim_unsupported(self):
        prefs = {
            "sensor_bindings": {
                "external_1": dict(
                    provider=PROVIDER,
                    sensor_id="/x",
                    sensor_type="Power",
                    name="Power",
                    hardware_name="Test",
                )
            }
        }
        data = {"external_sensors": {"/x": dict(type="Power", unit="W", value=None)}}
        self.assertIn("采集库本轮返回空值", unavailable_reason(data, "external_1", prefs))


if __name__ == "__main__":
    unittest.main()
