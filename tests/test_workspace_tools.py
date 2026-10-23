"""Private workspace actions; no native windows, hardware, installed state or preferences."""

import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import diagnostic_actions as diagnostics
import native_controller as controls
import native_layout
import workspace_scenarios as scenes
import workspace_tools as tools
from history_store import HistoryStore
from stats_config import DEFAULT


class WorkspaceToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Workspace tests require an offscreen application")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="synthetic-workspace-")
        self.root = Path(self.directory.name)
        self.patches = ExitStack()
        self.saved = copy.deepcopy(DEFAULT)
        self.save = self.patches.enter_context(patch.object(tools, "save"))
        self.patches.enter_context(patch.object(controls, "load", return_value=self.saved))
        self.patches.enter_context(patch.object(controls, "save", side_effect=AssertionError("No preference IO")))
        self.patches.enter_context(patch.object(tools, "BASE", self.root))
        self.backend = Mock()
        self.backend.status = dict(state="idle", detail="Synthetic history", error="", api="", errorcode=None)
        self.backend.clear.return_value = True
        self.store_factory = self.patches.enter_context(patch.object(tools, "HistoryStore", return_value=self.backend))
        self.patches.enter_context(patch.object(controls.sensors, "Sampler", side_effect=AssertionError("No hardware")))
        self.dialog = self.patches.enter_context(patch.object(tools.QFileDialog, "getSaveFileName", return_value=("", "")))
        self.ui = controls.Controller()
        self.ui.rescanExternal = Mock()
        self.applied = []
        self.ui.applyRequested.connect(self.applied.append)
        self.ui.set_preview_area(1280, 720)

    def tearDown(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()
        self.patches.close()
        self.directory.cleanup()

    def response(self, *, unavailable=False):
        return dict(unit="%", start=100, end=106, resolution=2,
                    points=[dict(time=100, mean=0, minimum=0, peak=0, gap=False),
                            dict(time=102, mean=None, minimum=None, peak=None, gap=True),
                            dict(time=104, mean=20, minimum=10, peak=30, gap=False)],
                    summary=dict(latest=20, latest_time=104.25, mean=10, peak=20,
                                 minimum=0, count=2, missing_count=1),
                    status=dict(state="unavailable" if unavailable else "ready", detail="Synthetic history"))

    def test_first_scene_listing_and_application_work_without_existing_scene_file(self):
        self.ui.refreshScenes()
        self.assertEqual([row["id"] for row in self.ui.scenes], ["office", "performance", "endurance"])
        self.assertFalse(self.ui.sceneError)
        self.assertTrue(self.ui.applyScene("office"))
        self.save.assert_called_once()
        self.assertEqual(self.applied, [True])
        self.assertEqual(self.ui.appliedSceneId, "office")
        self.assertEqual(scenes.workspace(self.ui._scene_store.prepare("previous", self.ui._saved)),
                         scenes.workspace(self.saved))

    def test_save_scene_saves_draft_workspace_without_applying_preferences_or_starting_hardware(self):
        self.ui._draft["language"] = "en"
        self.ui._draft["refresh"] = .1
        self.ui._draft["widgets"]["cpu"]["content"] = ["cpu_power", "cpu_usage"]
        self.assertTrue(self.ui.saveScene("私有测试场景"))
        self.save.assert_not_called()
        custom = next(row for row in self.ui.scenes if row.get("custom"))
        prepared = self.ui._scene_store.prepare(custom["id"], self.ui._saved)
        self.assertEqual(prepared["widgets"]["cpu"]["content"], ["cpu_power", "cpu_usage"])
        self.assertEqual(prepared["language"], self.saved["language"])
        self.assertEqual(prepared["refresh"], self.saved["refresh"])
        self.ui.rescanExternal.assert_not_called()
        self.store_factory.assert_not_called()

    def test_apply_scene_does_not_commit_or_erase_unrelated_pending_preferences(self):
        self.ui._draft.update(language="en", refresh=.25, autostart=True, history_enabled=False)
        self.ui._undo_drafts.append(copy.deepcopy(self.saved))
        self.assertTrue(self.ui.applyScene("performance"))
        committed = self.save.call_args.args[0]
        for field in ("language", "refresh", "autostart", "history_enabled"):
            self.assertEqual(committed[field], self.saved[field])
        self.assertEqual(self.ui._draft["language"], "en")
        self.assertEqual(self.ui._draft["refresh"], .25)
        self.assertTrue(self.ui._draft["autostart"])
        self.assertFalse(self.ui._draft["history_enabled"])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(scenes.workspace(self.ui._draft), scenes.workspace(self.ui._saved))

    def test_capacity_failure_does_not_save_or_replace_recovery_scene(self):
        self.ui.set_preview_area(180, 100)
        before = copy.deepcopy(self.ui._saved)
        self.assertFalse(self.ui.applyScene("office"))
        self.save.assert_not_called()
        self.assertEqual(self.ui._saved, before)
        self.assertFalse(self.ui._scene_store.path.exists())
        self.assertFalse(self.applied)

    def test_preference_save_failure_preserves_existing_recovery_scene_bytes(self):
        historical = scenes.builtin("endurance", self.saved)
        self.ui._scene_store.remember_previous(historical)
        prior = self.ui._scene_store.path.read_bytes()
        saved, draft = copy.deepcopy(self.ui._saved), copy.deepcopy(self.ui._draft)
        self.save.side_effect = PermissionError("synthetic save denied")
        self.assertFalse(self.ui.applyScene("office"))
        self.assertEqual(self.ui._scene_store.path.read_bytes(), prior)
        self.assertEqual(self.ui._saved, saved)
        self.assertEqual(self.ui._draft, draft)
        self.assertFalse(self.applied)

    def test_atomic_scene_replace_failure_keeps_original_and_does_not_apply_config(self):
        self.ui._scene_store.save("保留原场景", self.saved)
        prior = self.ui._scene_store.path.read_bytes()
        replace = Path.replace

        def denied(path, target):
            if Path(target) == self.ui._scene_store.path:
                raise PermissionError("Synthetic scene replacement denied")
            return replace(path, target)

        with patch.object(Path, "replace", denied):
            self.assertFalse(self.ui.saveScene("另一个场景"))
        self.assertEqual(self.ui._scene_store.path.read_bytes(), prior)
        self.assertEqual(list(self.root.glob(".scene-*.tmp")), [])
        self.save.assert_not_called()

    def test_history_recording_changes_only_saved_single_field_and_undo_cannot_revive_it(self):
        self.ui._draft.update(language="en", refresh=.25)
        self.ui._undo_drafts = [copy.deepcopy(self.saved)]
        self.ui._redo_drafts = [copy.deepcopy(self.saved)]
        self.assertTrue(self.ui.setHistoryRecording(False))
        expected = copy.deepcopy(self.saved)
        expected["history_enabled"] = False
        self.assertEqual(self.save.call_args.args[0], expected)
        self.assertFalse(self.ui.historyRecording)
        self.assertEqual(self.ui._draft["language"], "en")
        self.assertEqual(self.ui._draft["refresh"], .25)
        for value in self.ui._undo_drafts + self.ui._redo_drafts:
            self.assertFalse(value["history_enabled"])
        self.assertTrue(self.ui.undoDraft())
        self.assertFalse(self.ui._draft["history_enabled"])
        self.assertFalse(self.ui.historyRecording)

    def test_failed_history_setting_save_preserves_saved_draft_and_history_stacks(self):
        self.ui._draft["language"] = "en"
        self.ui._undo_drafts = [copy.deepcopy(self.saved)]
        before = copy.deepcopy((self.ui._saved, self.ui._draft, self.ui._undo_drafts))
        self.save.side_effect = OSError("Synthetic preference file unavailable")
        self.assertFalse(self.ui.setHistoryRecording(False))
        self.assertEqual((self.ui._saved, self.ui._draft, self.ui._undo_drafts), before)

    def test_history_pause_skips_backend_and_resume_records_samples(self):
        self.ui._saved["history_enabled"] = False
        self.ui._record_history(dict(time=100, cpu_usage=0))
        self.store_factory.assert_not_called()
        self.ui._saved["history_enabled"] = True
        self.ui._record_history(dict(time=101, cpu_usage=0))
        self.backend.record.assert_called_once_with(dict(time=101, cpu_usage=0))

    def test_history_query_uses_explicit_device_and_maps_gap_without_losing_zero(self):
        self.ui._devices = dict(gpus={"1": dict(label="Synthetic GPU")})
        self.ui._data = dict(gpus={"1": dict(gpu_usage=0)})
        choices = self.ui.historyMetricChoices
        choice = next(row for row in choices if row["scope"] == "gpus" and row["label"] == "GPU 使用率")
        self.assertTrue(choice["available"])
        self.backend.query.return_value = self.response()
        result = self.ui.historyQuery(choice["id"], "1h")
        self.backend.query.assert_called_once_with("gpu_usage", "1h", scope="gpus", device_id="1")
        self.assertEqual(result["points"], [dict(timestamp=100, value=0, minimum=0, peak=0), None,
                                            dict(timestamp=104, value=20, minimum=10, peak=30)])
        self.assertEqual((result["count"], result["mean"], result["coverage"]), (2, 10, 2 / 3))
        self.assertEqual(result["state"], "ready")

    def test_disconnected_history_device_keeps_identity_and_never_switches_to_auto(self):
        self.ui._devices = dict(networks={"synthetic-nic": dict(label="Synthetic Network")})
        choice = next(row for row in self.ui.historyMetricChoices
                      if row["scope"] == "networks" and row["label"] == "下载速度")
        self.ui._devices = {}
        self.ui.historyMetricChoices
        self.backend.query.return_value = self.response(unavailable=True)
        result = self.ui.historyQuery(choice["id"], "10m")
        self.backend.query.assert_called_once_with("net_download", "10m", scope="networks", device_id="synthetic-nic")
        self.assertEqual(result["state"], "error")

    def test_history_latest_time_is_the_provider_observation_time_without_a_ui_clock_substitute(self):
        choice = next(row for row in self.ui.historyMetricChoices if row["label"] == "CPU 使用率")
        response = self.response()
        self.backend.query.return_value = response
        result = self.ui.historyQuery(choice["id"], "10m")
        self.assertEqual(result["latest_time"], 104.25)
        del response["summary"]["latest_time"]
        self.assertIsNone(self.ui.historyQuery(choice["id"], "10m")["latest_time"])

    def test_backend_english_details_are_localized_in_status_and_query_without_mutating_backend(self):
        choice = next(row for row in self.ui.historyMetricChoices if row["label"] == "CPU 使用率")
        details = (
            ("idle", "History has not been written yet", "等待第一批历史记录。",
             "Waiting for the first history records."),
            ("unavailable", "Local history storage is unavailable",
             "本地历史存储不可用，请检查文件访问和磁盘空间。",
             "Local history storage is unavailable. Check file access and disk space."),
            ("ready", "Local history is up to date", "最近的历史记录已保存到本机。",
             "Recent history has been saved on this computer."),
            ("ready", "Local history has been cleared", "本机历史记录已清空。",
             "History on this computer has been cleared."),
        )
        for language, index in (("zh-CN", 2), ("en", 3)):
            self.ui._draft["language"] = language
            for row in details:
                state, raw = row[:2]
                with self.subTest(language=language, state=state, raw=raw):
                    self.backend.status = dict(state=state, detail=raw, error="PermissionError",
                                               api="sqlite3.history.write", errorcode=13)
                    response = self.response(unavailable=state == "unavailable")
                    response["status"] = dict(self.backend.status)
                    self.backend.query.return_value = response
                    status = self.ui.historyStatus
                    query = self.ui.historyQuery(choice["id"], "10m")
                    self.assertEqual(status["detail"], row[index])
                    self.assertEqual(query["detail"], row[index])
                    self.assertEqual(status["errorcode"], 13)
                    self.assertEqual(self.backend.status["detail"], raw)
                    if state == "unavailable":
                        self.assertEqual(query["state"], "error")
        self.save.assert_not_called()

    def test_unknown_history_query_and_failed_clear_are_explicit(self):
        self.assertEqual(self.ui.historyQuery("missing", "10m")["state"], "error")
        self.backend.query.assert_not_called()
        self.backend.clear.return_value = False
        self.assertFalse(self.ui.clearHistory())
        self.backend.clear.assert_called_once_with()

    def test_diagnostic_check_waits_for_a_new_sample_and_timeout_is_explicit(self):
        with patch.object(tools.time, "time", return_value=200):
            self.ui.checkSources()
        self.ui.rescanExternal.assert_called_once_with()
        self.assertEqual(self.ui.diagnosticCheck["state"], "checking")
        self.ui._workspace_sample_received(dict(time=199))
        self.assertEqual(self.ui.diagnosticCheck["state"], "checking")
        self.ui._diagnostic_timeout()
        self.assertEqual(self.ui.diagnosticCheck["state"], "waiting")

    def test_late_diagnostic_timeout_cannot_replace_a_successful_refresh(self):
        with patch.object(tools.time, "time", return_value=200):
            self.ui.checkSources()
        self.ui._workspace_sample_received(dict(time=201))
        self.assertEqual(self.ui.diagnosticCheck["state"], "updated")
        self.ui._diagnostic_timeout()
        self.assertEqual(self.ui.diagnosticCheck["state"], "updated")

    def test_safe_diagnostics_keeps_codes_and_known_api_but_removes_arbitrary_private_strings(self):
        private = "alice 10.0.0.8"
        payload = dict(time=100, cpu_usage=99, device_id=private, provider_status={
            "network": dict(state="query_failed", reason=private, api=private, type=private,
                            error=dict(api="psutil.net_io_counters", errno=13, message=private)),
            "nvml": dict(state="waiting_retry", reason="initialization_failed",
                         error=dict(api="nvmlInit_v2", status_code=3, type="OSError")),
        })
        report = diagnostics.safe_report(payload, "synthetic-version")
        self.assertNotIn(private, json.dumps(report))
        self.assertEqual(report["sources"]["network"]["error"]["errno"], 13)
        self.assertEqual(report["sources"]["network"]["error"]["api"], "psutil.net_io_counters")
        self.assertEqual(report["sources"]["nvml"]["reason"], "initialization_failed")
        self.assertNotIn("cpu_usage", report)

    def test_diagnostic_export_is_private_and_io_failure_does_not_report_success(self):
        self.ui._data = dict(time=100, cpu_usage=99, networks={"private-adapter": {"label": "private-adapter"}},
                             provider_status={"battery": dict(state="no_battery", ntstatus=0)})
        path = self.root / "synthetic-diagnostics.json"
        self.assertTrue(self.ui.exportDiagnosticsPath(path))
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("private-adapter", json.dumps(report))
        self.assertNotIn("cpu_usage", report)
        prior = path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("Synthetic file unavailable")):
            self.assertFalse(self.ui.exportDiagnosticsPath(path))
        self.assertEqual(path.read_bytes(), prior)
        self.assertFalse(list(self.root.glob(".diagnostics-*.tmp")))
        self.dialog.assert_not_called()

    def test_failed_scene_rollback_retains_exact_recovery_copy_and_reports_incomplete_restore(self):
        self.ui._scene_store.remember_previous(scenes.builtin("endurance", self.saved))
        original = self.ui._scene_store.path.read_bytes()
        self.save.side_effect = OSError("Synthetic preference save denied")
        replace = Path.replace

        def fail_restore(path, target):
            if path.name.startswith(".scene-recovery-"):
                raise PermissionError("Synthetic restore denied")
            return replace(path, target)

        with patch.object(Path, "replace", fail_restore):
            self.assertFalse(self.ui.applyScene("office"))
        retained = list(self.root.glob(".scene-recovery-*.json"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_bytes(), original)
        self.assertIn("恢复未完成", self.ui.sceneError)
        self.assertEqual(self.ui._saved, self.saved)
        self.assertFalse(self.applied)

    def test_builtin_widget_positions_round_trip_through_existing_position_reader(self):
        for identifier in ("office", "performance", "endurance"):
            config = scenes.builtin(identifier, self.saved)
            positions = {spec["id"]: [100 + i * 40, 70 + i * 10]
                         for i, spec in enumerate(native_layout.windows(config))}
            path = self.root / (identifier + "-positions.json")
            path.write_text(json.dumps(positions), encoding="utf-8")
            self.assertEqual(native_layout.read_positions(path), positions)

    def test_scene_preview_has_real_windows_and_never_mutates_or_saves_settings(self):
        before = copy.deepcopy((self.ui._saved, self.ui._draft, self.ui._undo_drafts))
        result = self.ui.scenePreview("performance")
        self.assertEqual(len(result["windows"]), 2)
        self.assertEqual({row["id"] for row in result["windows"]}, {"w_scene_cpu", "w_scene_gpu"})
        self.assertEqual((self.ui._saved, self.ui._draft, self.ui._undo_drafts), before)
        self.assertFalse(self.ui._scene_store.path.exists())
        self.save.assert_not_called()
        self.ui.rescanExternal.assert_not_called()
        self.store_factory.assert_not_called()
        self.assertEqual(self.ui.scenePreview("unknown"), {})
        self.assertTrue(self.ui.sceneError)
        self.assertEqual((self.ui._saved, self.ui._draft, self.ui._undo_drafts), before)

    def test_scene_thumbnails_use_actual_widget_tiles_and_quantity_icons(self):
        self.ui.refreshScenes()
        performance = next(row for row in self.ui.scenes if row["id"] == "performance")
        self.assertEqual(performance["preview"]["widget_count"], 2)
        self.assertEqual(len(performance["preview"]["tiles"]), 2)
        self.assertEqual([len(row["metrics"]) for row in performance["preview"]["tiles"]], [3, 3])
        self.assertEqual(performance["preview"]["tiles"][0]["metrics"][0]["icon"], "temperature")
        choices = self.ui.historyMetricChoices
        self.assertEqual(next(row["icon"] for row in choices if row["label"] == "CPU 风扇转速"), "fan")
        self.assertEqual(next(row["icon"] for row in choices if row["label"] == "CPU 频率"), "frequency")
        self.assertEqual(next(row["icon"] for row in choices if row["label"] == "CPU 封装功率"), "power")

    def test_ui_history_bins_keep_a_single_spike_among_many_low_observations(self):
        clock = {"time": 0.0}
        base = 1_700_000_040
        backend = HistoryStore(self.root / "synthetic-history.sqlite3", clock=lambda: clock["time"],
                               wall_clock=lambda: base + clock["time"])
        self.ui._history_backend = backend
        for index in range(1000):
            clock["time"] = index / 1000
            backend.record(dict(time=base + clock["time"], cpu_usage=100 if index == 500 else 0))
        choice = next(row for row in self.ui.historyMetricChoices if row["label"] == "CPU 使用率")
        result = self.ui.historyQuery(choice["id"], "10m")
        observed = [point for point in result["points"] if point is not None]
        self.assertEqual(result["peak"], 100)
        self.assertEqual(result["count"], 1000)
        self.assertAlmostEqual(result["mean"], .1)
        self.assertEqual(max(point["peak"] for point in observed), 100)
        self.assertEqual(min(point["minimum"] for point in observed), 0)

    def test_open_history_resolves_network_auto_once_and_preserves_explicit_device(self):
        requested = []
        self.ui.settingsRequested.connect(requested.append)
        self.ui._data = dict(network_active="nic-a")
        route = self.ui.openHistoryMetric("net_download", dict(network_target="auto"))
        selected = self.ui._history_choices[route.split(":", 1)[1]]
        self.assertEqual(selected, ("net_download", "networks", "nic-a"))
        self.ui._data["network_active"] = "nic-b"
        self.backend.query.return_value = self.response()
        self.ui.historyQuery(route.split(":", 1)[1], "10m")
        self.backend.query.assert_called_with("net_download", "10m", scope="networks", device_id="nic-a")
        explicit = self.ui.openHistoryMetric("gpu_usage", dict(gpu_target="1"))
        self.assertEqual(self.ui._history_choices[explicit.split(":", 1)[1]], ("gpu_usage", "gpus", "1"))
        self.ui._data = {}
        self.assertEqual(self.ui.openHistoryMetric("net_download", dict(network_target="auto")), "__history__")
        self.assertEqual(self.ui.openHistoryMetric("external_1"), "__history__")
        self.assertEqual(self.ui.openHistoryMetric("storage_temp"), "__history__")
        self.assertEqual(requested[-1], "__history__")

    def test_worker_closes_only_backend_without_stopping_qt_timer(self):
        self.ui._store()
        with patch.object(self.ui._diagnostic_timer, "stop") as timer:
            self.ui.close_history_backend()
        self.backend.close.assert_called_once_with()
        timer.assert_not_called()

    def test_normal_no_battery_card_is_not_reported_as_permission_failure(self):
        rows = diagnostics.cards(dict(provider_status={"battery": dict(state="no_battery", ntstatus=0)}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["badge"], "无电池")
        self.assertTrue(rows[0]["healthy"])


if __name__ == "__main__":
    unittest.main()
