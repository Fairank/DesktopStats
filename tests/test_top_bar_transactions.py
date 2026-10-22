"""Bar actions are section transactions and never submit another editor's draft."""

import copy
import unittest
from unittest.mock import patch

import native_controller as controls
from stats_config import DEFAULT


class TopBarTransactionTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.calls = []
        self.ui.topBarApplyRequested.connect(lambda: self.calls.append("bar"))
        self.ui.applyRequested.connect(lambda value: self.calls.append("desktop"))

    def test_enable_only_saves_enabled_and_preserves_other_pending_work(self):
        self.ui.change("refresh", .25)
        self.ui.changeTopBar("height", 40)
        saved = copy.deepcopy(self.ui._saved)
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.setTopBarEnabled(True))
        self.assertEqual(self.ui._saved["refresh"], saved["refresh"])
        self.assertEqual(self.ui._draft["refresh"], .25)
        self.assertTrue(self.ui._saved["top_bar"]["enabled"])
        self.assertEqual(self.ui._saved["top_bar"]["height"], saved["top_bar"]["height"])
        self.assertEqual(self.ui._draft["top_bar"]["height"], 40)
        self.assertEqual(save.call_count, 1)
        self.assertEqual(self.calls, ["bar"])
        self.assertTrue(self.ui.dirty)

    def test_disable_only_saves_off_and_retains_pending_bar_arrangement(self):
        self.ui._saved["top_bar"]["enabled"] = True
        self.ui._draft = copy.deepcopy(self.ui._saved)
        self.ui.changeTopBar("height", 40)
        self.ui.change("size", 150)
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.setTopBarEnabled(False))
        self.assertFalse(self.ui._saved["top_bar"]["enabled"])
        self.assertFalse(self.ui._draft["top_bar"]["enabled"])
        self.assertEqual(self.ui._saved["top_bar"]["height"], 32)
        self.assertEqual(self.ui._draft["top_bar"]["height"], 40)
        self.assertEqual(self.ui._draft["size"], 150)
        self.assertEqual(self.calls, ["bar"])

    def test_apply_keeps_disabled_bar_disabled_and_preserves_widget_draft(self):
        self.ui.changeWidget("cpu", "show_title", False)
        before = copy.deepcopy(self.ui._saved["widgets"])
        self.ui.changeTopBar("spacing", 18)
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.applyTopBar())
        self.assertFalse(self.ui._saved["top_bar"]["enabled"])
        self.assertEqual(self.ui._saved["top_bar"]["spacing"], 18)
        self.assertEqual(self.ui._saved["widgets"], before)
        self.assertFalse(self.ui._draft["widgets"]["cpu"]["show_title"])

    def test_failed_save_leaves_both_states_and_runtime_untouched(self):
        self.ui.changeTopBar("height", 40)
        saved, draft = copy.deepcopy(self.ui._saved), copy.deepcopy(self.ui._draft)
        with patch.object(controls, "save", side_effect=OSError("fixture")):
            self.assertFalse(self.ui.setTopBarEnabled(True))
        self.assertEqual((self.ui._saved, self.ui._draft), (saved, draft))
        self.assertEqual(self.calls, [])

    def test_revert_bar_preserves_widget_draft_and_unrelated_undo_redo(self):
        self.ui.changeWidget("cpu", "show_title", False)
        self.ui.changeTopBar("height", 40)
        self.ui.change("refresh", .25)
        self.ui.undoDraft()  # Leave an unrelated edit in redo as well.
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.revertTopBarDraft())
        save.assert_not_called()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ui._draft["top_bar"], self.ui._saved["top_bar"])
        self.assertFalse(self.ui._draft["widgets"]["cpu"]["show_title"])
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui._draft["refresh"], .25)
        self.assertEqual(self.ui._draft["top_bar"], self.ui._saved["top_bar"])
        self.assertTrue(self.ui.undoDraft())
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, self.ui._saved)
        self.assertFalse(self.ui.revertTopBarDraft())

    def test_runtime_failure_is_not_overwritten_by_success_footer(self):
        self.ui.topBarApplyRequested.connect(lambda: self.ui.set_top_bar_status(
            {"state": "failed", "reason": "无法创建顶部状态栏。"}))
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.setTopBarEnabled(True))
        self.assertEqual(self.ui._status, "无法创建顶部状态栏。")

    def test_drop_is_one_undo_and_keeps_identifiers(self):
        ids = [item["id"] for item in self.ui._draft["top_bar"]["items"]]
        self.assertTrue(self.ui.placeTopBarMetric(ids[1], "", "left"))
        self.assertEqual(len(self.ui._undo_drafts), 1)
        left = [row["id"] for row in self.ui._draft["top_bar"]["items"] if row["prefs"]["placement"] == "left"]
        self.assertEqual(left, [ids[1]])
        self.assertEqual(set(ids), {row["id"] for row in self.ui._draft["top_bar"]["items"]})
        self.assertTrue(self.ui.placeTopBarMetric(ids[2], ids[1], "left"))
        self.assertEqual([row["id"] for row in self.ui._draft["top_bar"]["items"] if row["prefs"]["placement"] == "left"], [ids[2], ids[1]])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual([row["id"] for row in self.ui._draft["top_bar"]["items"] if row["prefs"]["placement"] == "left"], [ids[1]])

    def test_invalid_drop_has_no_side_effects(self):
        original = copy.deepcopy(self.ui._draft)
        ids = [item["id"] for item in original["top_bar"]["items"]]
        for identifier, before, placement in (("missing", "", "left"), (ids[0], ids[1], "left"), (ids[0], ids[0], "right"), (ids[0], "", "anywhere")):
            self.assertFalse(self.ui.placeTopBarMetric(identifier, before, placement))
            self.assertEqual(self.ui._draft, original)
        self.assertFalse(self.ui.canUndoDraft)


if __name__ == "__main__":
    unittest.main()
