"""Native-only regressions: editing, imports, layout and unavailable readings."""

import copy
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/native-unit-data")
)

from PySide6.QtCore import QRect

import installer
import native_controller as controls
from metrics import required_sources
from native_card import formatted, primary_metric, secondary
from native_layout import constrain, fit, read_positions, windows
from stats_config import DEFAULT, ORDER, validate


class NativeEditTests(unittest.TestCase):
    def setUp(self):
        self.initial = copy.deepcopy(DEFAULT)
        self.loader = patch.object(controls, "load", return_value=self.initial)
        self.loader.start()
        self.ui = controls.Controller()

    def tearDown(self):
        self.loader.stop()

    def test_cross_hardware_readings_survive_commit(self):
        self.ui.contentMode("cpu", "custom")
        self.ui.addMetric("cpu", "gpu_power")
        self.ui.addMetric("cpu", "battery_watts")
        self.ui.moveMetric("cpu", 2, -1)
        self.ui.changeWidget("cpu", "title", "工作台")
        self.ui.changeWidget("gpu", "enabled", False)
        self.assertIn("gpu", required_sources(self.ui._draft))
        with patch.object(controls, "save") as write:
            self.ui.apply()
        stored = write.call_args.args[0]
        self.assertEqual(
            stored["widgets"]["cpu"]["content"], ["cpu_temp", "battery_watts", "gpu_power"]
        )
        self.assertEqual(stored["widgets"]["cpu"]["title"], "工作台")
        self.assertFalse(self.ui.dirty)

    def test_duplicate_and_seventh_metric_cannot_enter_card(self):
        self.ui.contentMode("cpu", "custom")
        for metric in (
            "cpu_temp",
            "gpu_temp",
            "ram_percent",
            "battery_percent",
            "battery_watts",
            "gpu_power",
            "net_download",
        ):
            self.ui.addMetric("cpu", metric)
        self.assertEqual(
            self.ui._draft["widgets"]["cpu"]["content"],
            [
                "cpu_temp",
                "gpu_temp",
                "ram_percent",
                "battery_percent",
                "battery_watts",
                "gpu_power",
            ],
        )
        for _ in range(6):
            self.ui.removeMetric("cpu", 0)
        self.assertEqual(len(self.ui._draft["widgets"]["cpu"]["content"]), 1)

    def test_failed_save_rolls_back_startup_change_and_preserves_saved_settings(self):
        self.ui.change("autostart", True)
        with (
            patch.object(controls, "save", side_effect=OSError("test")),
            patch.object(controls, "set_autostart") as startup,
            self.assertLogs(level="ERROR"),
        ):
            self.ui.apply()
        self.assertEqual([call.args[0] for call in startup.call_args_list], [True, False])
        self.assertEqual(self.ui._saved, self.initial)
        self.assertTrue(self.ui.dirty)

    def test_apply_and_arrange_saves_once_and_emits_one_successful_layout_request(self):
        requested, saved = [], []
        self.ui.applyRequested.connect(requested.append)
        self.ui.savedChanged.connect(lambda: saved.append(True))
        self.ui.change("refresh", 0.05)
        with patch.object(controls, "save") as write:
            self.ui.rearrange()
        write.assert_called_once()
        self.assertEqual(requested, [True])
        self.assertEqual(saved, [True])
        self.assertEqual(self.ui._saved["refresh"], 0.05)
        self.assertFalse(self.ui.dirty)

    def test_failed_apply_and_arrange_preserves_layout_and_unsaved_edits(self):
        requested, saved = [], []
        self.ui.applyRequested.connect(requested.append)
        self.ui.savedChanged.connect(lambda: saved.append(True))
        self.ui.change("refresh", 0.05)
        with (
            patch.object(controls, "save", side_effect=OSError("test save failure")),
            self.assertLogs(level="ERROR"),
        ):
            self.ui.rearrange()
        self.assertEqual(requested, [])
        self.assertEqual(saved, [])
        self.assertEqual(self.ui._saved, self.initial)
        self.assertEqual(self.ui._draft["refresh"], 0.05)
        self.assertTrue(self.ui.dirty)

    def test_sampling_loop_uses_only_successfully_applied_refresh_intervals(self):
        controller = self.ui
        phases = []

        class FakeStop:
            def __init__(self):
                self.stopped = False
                self.intervals = []
                self.errors = []

            def is_set(self):
                return self.stopped

            def set(self):
                self.stopped = True

            def wait(self, interval):
                self.intervals.append(interval)
                try:
                    stage = len(self.intervals)
                    if stage == 1:
                        controller.change("refresh", 0.01)
                    elif stage == 2:
                        controller.apply()
                    elif stage == 3:
                        controller.change("refresh", 5)
                        controller.apply()
                    else:
                        self.set()
                    phases.append((controller._saved["refresh"], controller._draft["refresh"]))
                except Exception as error:
                    self.errors.append(error)
                    self.set()
                return self.stopped

        stop = FakeStop()
        controller.stop = stop
        readings = [{"sequence": index} for index in range(4)]
        provider = Mock(spec=["sample", "write", "close"])
        provider.sample.side_effect = readings
        with (
            patch.object(controls.sensors, "Sampler", return_value=provider) as sampler,
            patch.object(controls, "save", side_effect=[None, OSError("test save failed")]) as save,
            patch.object(controls, "set_autostart") as startup,
            self.assertLogs(level="ERROR") as errors,
        ):
            try:
                controller.start()
                controller.thread.join(timeout=2)
            finally:
                stop.set()
                if controller.thread:
                    controller.thread.join(timeout=2)
            self.assertFalse(controller.thread.is_alive(), "sampling thread did not stop")
            sampler.assert_called_once_with()
            startup.assert_not_called()
            self.assertEqual([entry.args[0]["refresh"] for entry in save.call_args_list], [0.01, 5])

        self.assertEqual(stop.errors, [])
        self.assertEqual(stop.intervals, [2, 2, 0.01, 0.01])
        self.assertEqual(phases, [(2, 0.01), (0.01, 0.01), (0.01, 5), (0.01, 5)])
        self.assertEqual(provider.sample.call_count, 4)
        self.assertEqual(provider.write.call_args_list, [call(reading) for reading in readings])
        provider.close.assert_called_once_with()
        self.assertEqual(controller._saved["refresh"], 0.01)
        self.assertEqual(controller._draft["refresh"], 5)
        self.assertTrue(controller.dirty)
        self.assertEqual(len(errors.output), 1)
        self.assertIn("Native settings commit failed", errors.output[0])

    def test_invalid_import_leaves_current_draft_and_saved_values_intact(self):
        original = copy.deepcopy(self.ui._draft)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"size": -5}), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.ui.import_path(path)
        self.assertEqual(self.ui._draft, original)
        self.assertEqual(self.ui._saved, self.initial)

    def test_qml_integer_slider_values_are_validated_without_loosening_bool_types(self):
        self.ui.change("size", 117.0)
        self.ui.changeWidget("cpu", "size", 123.0)
        self.assertEqual(self.ui._draft["size"], 117)
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["size"], 123)
        self.ui.change("size", True)
        self.assertEqual(self.ui._draft["size"], 117)

    def test_language_switch_never_translates_user_titles(self):
        self.ui.changeWidget("cpu", "title", "系统状态")
        self.ui.change("language", "ja")
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["title"], "系统状态")
        self.assertEqual(self.ui.catalog["modules"][2]["label"], "メモリ")

    def test_revert_restores_all_unsaved_edits(self):
        self.ui.changeWidget("cpu", "skin", "minimal")
        self.ui.change("language", "es")
        self.ui.revert()
        self.assertEqual(self.ui._draft, self.initial)


class NativeRefreshValidationTests(unittest.TestCase):
    def test_integer_and_centisecond_intervals_survive_json_round_trip(self):
        for interval in (
            0.01,
            0.02,
            0.05,
            0.1,
            0.29,
            0.57,
            0.99,
            1,
            1.0,
            1.25,
            2,
            2.0,
            4.99,
            5,
            5.0,
        ):
            with self.subTest(interval=interval):
                config = validate({"version": 6, "refresh": interval})
                self.assertEqual(config["version"], 8)
                self.assertIn(type(config["refresh"]), (int, float))
                self.assertEqual(config["refresh"], interval)
                self.assertEqual(validate(json.loads(json.dumps(config))), config)

    def test_default_interval_remains_two_seconds(self):
        self.assertEqual(DEFAULT["refresh"], 2)
        self.assertEqual(DEFAULT["version"], 8)
        for version in (4, 5, 6):
            with self.subTest(version=version):
                config = validate({"version": version})
                self.assertEqual(config["version"], 8)
                self.assertEqual(config["refresh"], 2)

    def test_old_ten_second_interval_is_clamped_without_losing_other_preferences(self):
        for version in (4, 5):
            for interval in (2, 5, 10, 10.0):
                with self.subTest(version=version, interval=interval):
                    widget = dict(
                        title="迁移保留", skin="minimal", size=123, show_title=False, enabled=False
                    )
                    preferences = dict(
                        language="ja", theme="dark", skin="glass", opacity=76, size=120
                    )
                    original = dict(
                        version=version, refresh=interval, widgets={"cpu": widget}, **preferences
                    )
                    snapshot = copy.deepcopy(original)
                    config = validate(original)
                    self.assertEqual(config["version"], 8)
                    self.assertEqual(config["refresh"], min(interval, 5))
                    self.assertEqual({key: config[key] for key in preferences}, preferences)
                    self.assertEqual({key: config["widgets"]["cpu"][key] for key in widget}, widget)
                    self.assertEqual(validate(json.loads(json.dumps(config))), config)
                    self.assertEqual(original, snapshot)

    def test_version_five_migration_retains_custom_instances_and_six_metrics(self):
        metrics = [
            "cpu_temp",
            "gpu_temp",
            "ram_percent",
            "battery_percent",
            "battery_watts",
            "gpu_power",
        ]
        config = validate(
            {
                "version": 5,
                "refresh": 10,
                "widget_order": ["workbench"],
                "widgets": {"workbench": {"kind": "cpu", "content": metrics, "title": "工作台"}},
            }
        )
        self.assertEqual(config["version"], 8)
        self.assertEqual(config["refresh"], 5)
        self.assertEqual(config["widget_order"], ["workbench"])
        self.assertEqual(list(config["widgets"]), ["workbench"])
        self.assertEqual(config["widgets"]["workbench"]["content"], metrics)
        self.assertEqual(config["widgets"]["workbench"]["title"], "工作台")

    def test_invalid_refresh_values_do_not_gain_rounding_or_boolean_coercion(self):
        for value in (
            True,
            False,
            0.009,
            5.01,
            10,
            10.0,
            1.234,
            1.001,
            0,
            -0.01,
            -1,
            100,
            None,
            "1",
            "2",
            [],
            {},
            math.nan,
            math.inf,
            -math.inf,
        ):
            with self.subTest(value=repr(value), kind=type(value).__name__):
                with self.assertRaises(ValueError):
                    validate({"version": 6, "refresh": value})


class NativeLayoutTests(unittest.TestCase):
    def test_large_vertical_group_fits_on_small_monitor_without_changing_preferences(self):
        config = validate({"size": 180, "mode": "combined", "group_columns": 1})
        original = windows(config)[0]
        adjusted = constrain(original, 1000, 720)
        self.assertLessEqual(adjusted["height"], 684)
        self.assertEqual(len(adjusted["cells"]), len(original["cells"]))
        self.assertGreater(original["height"], 1000)

    def test_uninstall_manifest_cannot_select_files_outside_its_install_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "install-manifest.json").write_text(
                json.dumps(
                    ["_internal/QtCore.dll", "../../outside.txt", str(root.parent / "outside.txt")]
                ),
                encoding="utf-8",
            )
            with patch.object(installer, "DIRECTORY", root):
                self.assertEqual(installer.owned_files(), [root / "_internal/QtCore.dll"])

    def test_every_mode_displays_each_enabled_widget_exactly_once(self):
        for mode in ("separate", "combined", "mixed"):
            config = validate({"mode": mode})
            expected = [key for key in ORDER if config["widgets"][key]["enabled"]]
            actual = [cell["key"] for window in windows(config) for cell in window["cells"]]
            self.assertCountEqual(actual, expected)
            self.assertEqual(len(actual), len(set(actual)))

    def test_individual_size_and_global_size_remain_independent(self):
        config = validate({"size": 100, "widgets": {"cpu": {"size": 140}}})
        sizes = {window["id"]: window["width"] for window in windows(config)}
        self.assertEqual(sizes["cpu"], 210)
        self.assertEqual(sizes["gpu"], 150)

    def test_group_cells_fit_inside_their_native_window(self):
        for count in (1, 2, 3):
            config = validate({"mode": "combined", "group_columns": count})
            window = windows(config)[0]
            for cell in window["cells"]:
                self.assertLessEqual(cell["x"] + cell["width"], window["width"])
                self.assertLessEqual(cell["y"] + cell["height"], window["height"])

    def test_removed_monitor_position_returns_to_primary_work_area(self):
        screen = QRect(0, 0, 1280, 720)
        self.assertEqual(fit(2400, 700, 168, 168, [screen]), (1112, 552))
        self.assertEqual(fit(-900, -400, 168, 168, [screen]), (0, 0))

    def test_bad_or_nonfinite_saved_positions_cannot_hide_a_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "positions.json"
            path.write_text('{"cpu":[NaN,0],"gpu":[35,50],"unknown":[0,0]}', encoding="utf-8")
            self.assertEqual(read_positions(path), {"gpu": [35, 50]})
            path.write_text("[]", encoding="utf-8")
            self.assertEqual(read_positions(path), {})


class NativeReadingTests(unittest.TestCase):
    def test_missing_nan_and_zero_have_different_meanings(self):
        self.assertEqual(formatted({}, "battery_watts"), ("—", "W"))
        self.assertEqual(formatted({"battery_watts": math.nan}, "battery_watts"), ("—", "W"))
        self.assertEqual(formatted({"battery_watts": 0}, "battery_watts"), ("0.0", "W"))

    def test_vram_is_derived_from_actual_capacity(self):
        self.assertEqual(formatted({"vram_gb": 3, "vram_total_gb": 8}, "vram_percent"), ("38", "%"))
        self.assertEqual(formatted({"vram_gb": 3}, "vram_percent"), ("—", "%"))

    def test_idle_ac_battery_does_not_say_discharging(self):
        data = {
            "battery_present": True,
            "power_online": True,
            "discharging": True,
            "battery_watts": 0,
        }
        text = secondary(data, "battery", DEFAULT["widgets"]["battery"], lambda value: value)
        self.assertEqual(text, "已连接电源")

    def test_every_hardware_preset_resolves_to_a_supported_native_metric(self):
        for key in ORDER:
            self.assertIn(primary_metric(key, DEFAULT["widgets"][key]), controls.METRICS)


if __name__ == "__main__":
    unittest.main()
