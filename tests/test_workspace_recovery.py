"""Workspace recovery invariants with private files and synthetic layouts only."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workspace_scenarios as scenes
from external_sensor import EXTERNAL_SLOTS, PROVIDER
from history_store import HistoryStore
from stats_config import DEFAULT, validate
from tests import test_workspace_tools as fixtures
from widget_catalog import from_template
from workspace_scenarios import SceneStore, workspace


class WorkspaceRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.WorkspaceToolsTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.WorkspaceToolsTests()
        self.fixture.setUp()
        self.ui = self.fixture.ui

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def test_reapplying_current_scene_keeps_recovery_and_does_not_rearrange_desktop(self):
        original = workspace(self.ui._saved)
        self.assertTrue(self.ui.applyScene("office"))
        recovery = self.ui._scene_store.path.read_bytes()
        self.fixture.save.reset_mock()
        self.fixture.applied.clear()
        self.assertTrue(self.ui.applyScene("office"))
        self.assertEqual(self.ui._scene_store.path.read_bytes(), recovery)
        self.assertEqual(workspace(self.ui._scene_store.prepare("previous", self.ui._saved)), original)
        self.fixture.save.assert_not_called()
        self.assertEqual(self.fixture.applied, [])

    def test_reapplying_saved_scene_discards_only_workspace_drafts_without_destroying_recovery(self):
        self.assertTrue(self.ui.applyScene("office"))
        recovery = self.ui._scene_store.path.read_bytes()
        self.ui.changeWidget("w_scene_status", "title", "Pending")
        self.ui.change("refresh", .1)
        self.ui.changeTopBar("height", 40)
        self.fixture.save.reset_mock()
        self.fixture.applied.clear()
        # A custom scene snapshots the saved workspace; unrelated preference
        # edits must survive choosing that same saved workspace again.
        identifier = self.ui._scene_store.save("Saved workspace", self.ui._saved)
        recovery = self.ui._scene_store.path.read_bytes()
        self.assertTrue(self.ui.applyScene(identifier))
        self.assertEqual(workspace(self.ui._draft), workspace(self.ui._saved))
        self.assertEqual(self.ui._draft["refresh"], .1)
        self.assertEqual(self.ui._scene_store.path.read_bytes(), recovery)
        self.fixture.save.assert_not_called()
        self.assertEqual(self.fixture.applied, [])

    def test_restore_previous_does_not_mark_its_now_replaced_recovery_point_as_applied(self):
        self.assertTrue(self.ui.applyScene("office"))
        office = workspace(self.ui._saved)
        self.assertTrue(self.ui.applyScene("endurance"))
        endurance = workspace(self.ui._saved)
        self.assertTrue(self.ui.applyScene("previous"))
        self.assertEqual(workspace(self.ui._saved), office)
        self.assertEqual(workspace(self.ui._scene_store.prepare("previous", self.ui._saved)), endurance)
        self.assertNotEqual(self.ui.appliedSceneId, "previous")
        if self.ui.appliedSceneId:
            self.assertEqual(workspace(self.ui._scene_store.prepare(self.ui.appliedSceneId, self.ui._saved)), office)

    def test_failed_sqlite_clear_keeps_readable_history_and_the_actual_failure_visible(self):
        base = 1_700_000_040
        store = HistoryStore(self.fixture.root / "synthetic-history.sqlite3", metrics=("cpu_usage",),
                             scopes=(), wall_clock=lambda: base + 2, clock=lambda: 1)
        self.ui._history_backend = store
        store.record(dict(time=base + 1, cpu_usage=37))
        connection = sqlite3.connect(store.path)
        try:
            connection.execute("CREATE TRIGGER synthetic_deny_clear BEFORE DELETE ON sensor_history "
                               "BEGIN SELECT RAISE(FAIL, 'synthetic clear denied'); END")
            connection.commit()
        finally:
            connection.close()
        self.assertFalse(self.ui.clearHistory())
        choice = next(row for row in self.ui.historyMetricChoices
                      if self.ui._history_choices[row["id"]][0] == "cpu_usage")
        response = self.ui.historyQuery(choice["id"], "10m")
        self.assertEqual(response["count"], 1)
        self.assertEqual(response["latest"], 37)
        self.assertEqual(response["state"], "ready", "A failed DELETE must not hide a successful read")
        self.assertEqual(self.ui.historyStatus["state"], "unavailable")
        self.assertEqual(self.ui.historyStatus["api"], "sqlite3.history.clear")
        self.assertEqual(self.ui.commitError, self.ui.tr("未能清空历史记录，请重试"))


class SceneStorageLimitTests(unittest.TestCase):
    @staticmethod
    def dense_config():
        config = copy.deepcopy(DEFAULT)
        bindings = {}
        for index, slot in enumerate(EXTERNAL_SLOTS):
            prefix = f"/synthetic/{index}/"
            bindings[slot] = dict(provider=PROVIDER, sensor_id=prefix + "x" * (512 - len(prefix)),
                                  sensor_type="Temperature", name="测" * 128, hardware_name="板" * 128)
        prefs = from_template("custom")
        prefs.update(content=list(EXTERNAL_SLOTS), sensor_bindings=bindings)
        config["widgets"] = {f"w_synthetic_{index}": copy.deepcopy(prefs) for index in range(24)}
        config["widget_order"] = list(config["widgets"])
        config["top_bar"]["items"] = [dict(id=f"b_synthetic_{index}", metric="external_1",
            prefs=dict(sensor_bindings={"external_1": bindings["external_1"]})) for index in range(64)]
        return validate(config)

    def test_eight_valid_dense_utf8_workspaces_all_save_and_remain_readable(self):
        config = self.dense_config()
        with tempfile.TemporaryDirectory(prefix="synthetic-scene-capacity-") as folder:
            store = SceneStore(Path(folder) / "scenes.json")
            for index in range(8):
                identifier = store.save(f"Layout {index}", config)
                self.assertLessEqual(store.path.stat().st_size, scenes.MAX_FILE_BYTES,
                                     "A successful save must respect the reader's UTF-8 byte limit")
                self.assertEqual(workspace(store.prepare(identifier, config)), workspace(config))
            self.assertGreater(store.path.stat().st_size, 1024 * 1024,
                               "Legitimate configured scenes must exercise the old 1 MiB failure")
            self.assertEqual(sum(row.get("custom", False) for row in store.rows(config)), 8)

    def test_oversize_write_uses_utf8_bytes_and_keeps_the_original_readable_file(self):
        config = self.dense_config()
        with tempfile.TemporaryDirectory(prefix="synthetic-scene-budget-") as folder:
            store = SceneStore(Path(folder) / "scenes.json")
            identifier = store.save("Layout", config)
            before = store.path.read_bytes()
            self.assertGreater(len(before), len(before.decode("utf-8")))
            with patch.object(scenes, "MAX_FILE_BYTES", len(before) + 512):
                with self.assertRaisesRegex(ValueError, "场景文件过大"):
                    store.save("Another layout", config)
                self.assertEqual(store.path.read_bytes(), before)
                self.assertEqual(workspace(store.prepare(identifier, config)), workspace(config))


if __name__ == "__main__":
    unittest.main()
