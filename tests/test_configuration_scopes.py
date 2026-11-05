"""Three-region persistence and explicit global replacement, entirely fake IO."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import native_controller as controls
from configuration_scopes import SCOPE_FIELDS, merge_scope, rebase_saved_changes
from stats_config import DEFAULT


class ConfigurationScopeTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()

    def dirty_all(self):
        self.ui.changeWidget("cpu", "title", "DeskDraft")
        self.ui.change("refresh", 0.35)
        self.ui.changeTopBar("height", 40)
        self.assertEqual(self.ui.scopeDirty, dict(desktop=True, preferences=True, topbar=True))

    def test_partition_covers_all_fields_once_except_schema_version(self):
        seen = set()
        for fields in SCOPE_FIELDS.values():
            self.assertFalse(seen & fields)
            seen |= fields
        self.assertEqual(seen, set(DEFAULT) - {"version"})

    def test_merge_is_pure_and_rejects_unknown_scope(self):
        before, source = copy.deepcopy(DEFAULT), copy.deepcopy(DEFAULT)
        source["top_bar"]["height"] = 40
        result = merge_scope(before, source, "topbar")
        self.assertEqual(result["top_bar"]["height"], 40)
        result["widgets"]["cpu"]["title"] = "Result"
        self.assertEqual(before, DEFAULT)
        self.assertEqual(source["widgets"]["cpu"]["title"], DEFAULT["widgets"]["cpu"]["title"])
        with self.assertRaises(KeyError):
            merge_scope(before, source, "invalid")

    def test_each_region_commit_leaves_other_saved_and_draft_branches(self):
        for scope, method in (
            ("desktop", "applyDesktop"),
            ("preferences", "applyPreferences"),
            ("topbar", "applyTopBar"),
        ):
            with self.subTest(scope=scope):
                self.setUp()
                self.dirty_all()
                saved, draft = copy.deepcopy(self.ui.saved), copy.deepcopy(self.ui.draft)
                expected = merge_scope(saved, draft, scope)
                with patch.object(controls, "save") as save:
                    self.assertTrue(getattr(self.ui, method)())
                save.assert_called_once_with(expected)
                self.assertEqual(self.ui.saved, expected)
                self.assertEqual(self.ui.draft, draft)
                self.assertEqual(self.ui.scopeDirty[scope], False)
                self.assertTrue(self.ui.dirty)

    def test_region_save_failure_is_atomic_for_history_and_all_branches(self):
        self.dirty_all()
        for method in ("applyDesktop", "applyPreferences", "applyTopBar"):
            before = copy.deepcopy(
                (self.ui.saved, self.ui.draft, self.ui._undo_drafts, self.ui._redo_drafts)
            )
            with patch.object(controls, "save", side_effect=OSError("fake read-only")):
                self.assertFalse(getattr(self.ui, method)())
            self.assertEqual(
                (self.ui.saved, self.ui.draft, self.ui._undo_drafts, self.ui._redo_drafts), before
            )

    def test_preferences_failure_rolls_back_autostart_without_committing_desktop(self):
        self.ui.changeWidget("cpu", "title", "Draft")
        self.ui.change("autostart", True)
        saved = copy.deepcopy(self.ui.saved)
        with (
            patch.object(controls, "set_autostart") as autostart,
            patch.object(controls, "save", side_effect=OSError("fake")),
        ):
            self.assertFalse(self.ui.applyPreferences())
        self.assertEqual(autostart.call_args_list, [((True,),), ((False,),)])
        self.assertEqual(self.ui.saved, saved)
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "Draft")

    def test_each_region_revert_keeps_other_drafts_and_their_undo(self):
        for scope, method in (
            ("desktop", "revertDesktopDraft"),
            ("preferences", "revertPreferencesDraft"),
            ("topbar", "revertTopBarDraft"),
        ):
            with self.subTest(scope=scope):
                self.setUp()
                self.dirty_all()
                expected = merge_scope(self.ui.draft, self.ui.saved, scope)
                self.assertTrue(getattr(self.ui, method)())
                self.assertEqual(self.ui.draft, expected)
                self.assertTrue(self.ui.undoDraft())
                self.assertFalse(self.ui.scopeDirty[scope])

    def test_partial_commit_rebases_undo_and_redo_without_resurrecting_saved_region(self):
        self.dirty_all()
        self.assertTrue(self.ui.undoDraft())  # Pending bar edit is now in redo.
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.applyDesktop())
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui.draft["top_bar"]["height"], 40)
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "DeskDraft")
        while self.ui.undoDraft():
            self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "DeskDraft")

    def test_both_bar_switch_directions_only_save_enabled(self):
        self.dirty_all()
        for enabled in (True, False, True):
            before = copy.deepcopy(self.ui.saved)
            with patch.object(controls, "save") as save:
                self.assertTrue(self.ui.setTopBarEnabled(enabled))
            expected = copy.deepcopy(before)
            expected["top_bar"]["enabled"] = enabled
            save.assert_called_once_with(expected)
            self.assertEqual(self.ui.saved, expected)
            self.assertEqual(self.ui.draft["top_bar"]["height"], 40)
            self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "DeskDraft")
            self.assertTrue(self.ui.scopeDirty["topbar"])

    def test_enabled_commit_rebases_history_only_enabled_leaf(self):
        self.dirty_all()
        with patch.object(controls, "save"):
            self.ui.setTopBarEnabled(True)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui.draft["top_bar"]["height"], 32)
        self.assertTrue(self.ui.draft["top_bar"]["enabled"])

    def test_desktop_preset_does_not_edit_preferences_or_bar(self):
        self.dirty_all()
        before = copy.deepcopy(self.ui.draft)
        name = next(iter(controls.catalogue()))
        self.ui.preset(name)
        for scope in ("preferences", "topbar"):
            for key in SCOPE_FIELDS[scope]:
                self.assertEqual(self.ui.draft[key], before[key])

    def backup(self):
        return copy.deepcopy(
            (
                self.ui.draft,
                self.ui._undo_drafts,
                self.ui._redo_drafts,
                self.ui._last_edit_key,
                self.ui._last_edit_time,
            )
        )

    def test_reset_cancel_restores_exact_original_draft_and_history(self):
        self.dirty_all()
        self.ui.undoDraft()
        before = self.backup()
        self.ui.reset()
        self.assertTrue(self.ui.replacementPending)
        self.ui.changeWidget("cpu", "title", "Candidate")
        self.assertTrue(self.ui.cancelReplacement())
        self.assertFalse(self.ui.replacementPending)
        self.assertEqual(self.backup(), before)

    def test_import_cancel_restores_original_draft_and_history(self):
        self.dirty_all()
        before = self.backup()
        candidate = copy.deepcopy(DEFAULT)
        candidate["widgets"]["cpu"]["title"] = "Imported"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            self.ui.import_path(path)
        self.assertTrue(self.ui.replacementPending)
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "Imported")
        self.ui.cancelReplacement()
        self.assertEqual(self.backup(), before)

    def test_invalid_import_never_creates_a_global_preview(self):
        before = self.backup()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text('{"refresh": -1}', encoding="utf-8")
            with self.assertRaises(ValueError):
                self.ui.import_path(path)
        self.assertFalse(self.ui.replacementPending)
        self.assertEqual(self.backup(), before)

    def test_global_preview_blocks_partial_commit_and_partial_revert(self):
        self.dirty_all()
        self.ui.reset()
        before = copy.deepcopy((self.ui.saved, self.ui.draft))
        with patch.object(controls, "save") as save:
            for method in (
                "applyDesktop",
                "applyPreferences",
                "applyTopBar",
                "revertDesktopDraft",
                "revertPreferencesDraft",
                "revertTopBarDraft",
            ):
                self.assertFalse(getattr(self.ui, method)())
            save.assert_not_called()
        self.assertEqual((self.ui.saved, self.ui.draft), before)

    def test_global_save_failure_retains_preview_and_cancel_snapshot(self):
        self.dirty_all()
        before = self.backup()
        self.ui.reset()
        with patch.object(controls, "save", side_effect=OSError("fake")):
            self.assertFalse(self.ui.applyReplacement())
        self.assertTrue(self.ui.replacementPending)
        self.ui.cancelReplacement()
        self.assertEqual(self.backup(), before)

    def test_explicit_global_apply_saves_all_and_exits_preview(self):
        self.dirty_all()
        self.ui.reset()
        self.ui.changeTopBar("height", 40)
        expected = copy.deepcopy(self.ui.draft)
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.applyReplacement())
        save.assert_called_once_with(expected)
        self.assertFalse(self.ui.replacementPending)
        self.assertFalse(self.ui.dirty)
        self.assertFalse(self.ui.applyReplacement())

    def test_cancelling_replacement_preserves_later_saved_quick_action_and_prior_title(self):
        self.ui.changeWidget("cpu", "title", "PriorDraft")
        self.ui.reset()
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.quickWidget("cpu", "skin", "graphite"))
            self.assertTrue(self.ui.setTopBarEnabled(True))
        self.assertTrue(self.ui.cancelReplacement())
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "PriorDraft")
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["skin"], "graphite")
        self.assertTrue(self.ui.draft["top_bar"]["enabled"])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["skin"], "graphite")

    def test_commit_error_is_explicit_and_clears_only_after_next_action(self):
        self.ui.changeWidget("cpu", "title", "Retry")
        with patch.object(controls, "save", side_effect=OSError("fake")):
            self.assertFalse(self.ui.applyDesktop())
        self.assertEqual(self.ui.commitError, self.ui.tr("未能保存，请重试"))
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.applyDesktop())
        self.assertEqual(self.ui.commitError, "")

    def test_recursive_rebase_does_not_mutate_inputs(self):
        base = {"widget": {"skin": "glass", "title": "old"}, "order": ["a", "b"]}
        saved = {"widget": {"skin": "card", "title": "old"}, "order": ["b"]}
        draft = {"widget": {"skin": "glass", "title": "pending"}, "order": ["a", "b"]}
        result = rebase_saved_changes(draft, base, saved)
        self.assertEqual(result, {"widget": {"skin": "card", "title": "pending"}, "order": ["b"]})
        self.assertEqual(draft["widget"]["skin"], "glass")


class UnchangedApplyTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.applied = []
        self.ui.applyRequested.connect(lambda rearrange: self.applied.append(rearrange))
        self.ui.topBarApplyRequested.connect(lambda: self.applied.append("topbar"))

    def test_unchanged_apply_does_not_save_revalidate_layout_or_reapply_windows(self):
        with (
            patch.object(controls, "save") as save,
            patch.object(controls, "set_autostart") as autostart,
            patch.object(self.ui, "layout_error", side_effect=AssertionError("No layout work")),
        ):
            self.assertTrue(self.ui._commit())
            self.assertTrue(self.ui.applyDesktop())
            self.assertTrue(self.ui.applyPreferences())
            self.assertTrue(self.ui.applyTopBar())
        save.assert_not_called()
        autostart.assert_not_called()
        self.assertEqual(self.applied, [])

    def test_scoped_noop_keeps_other_pending_drafts_and_undo(self):
        for method, pending in (("applyDesktop", "preferences"),
                                ("applyPreferences", "desktop"), ("applyTopBar", "desktop")):
            with self.subTest(method=method):
                self.setUp()
                if pending == "preferences":
                    self.ui.change("refresh", .75)
                else:
                    self.ui.changeWidget("cpu", "title", "Keep this draft")
                before = copy.deepcopy((self.ui.saved, self.ui.draft, self.ui._undo_drafts,
                                        self.ui._redo_drafts))
                with patch.object(controls, "save") as save:
                    self.assertTrue(getattr(self.ui, method)())
                save.assert_not_called()
                self.assertEqual((self.ui.saved, self.ui.draft, self.ui._undo_drafts,
                                  self.ui._redo_drafts), before)
                self.assertEqual(self.applied, [])

    def test_explicit_rearrangement_still_runs_for_equal_configuration(self):
        with patch.object(controls, "save") as save, patch.object(self.ui, "layout_error", return_value=""):
            self.assertTrue(self.ui.rearrangeDesktop())
        save.assert_called_once_with(self.ui.saved)
        self.assertEqual(self.applied, [True])

    def test_equal_global_replacement_still_finishes_the_explicit_preview(self):
        self.ui.changeWidget("cpu", "title", "Unapplied draft")
        self.assertTrue(self.ui._stage_replacement(copy.deepcopy(self.ui.saved)))
        self.assertTrue(self.ui.replacementPending)
        self.assertFalse(self.ui.dirty)
        with patch.object(controls, "save") as save, patch.object(self.ui, "layout_error", return_value=""):
            self.assertTrue(self.ui.applyReplacement())
        save.assert_called_once()
        self.assertFalse(self.ui.replacementPending)
        self.assertEqual(self.applied, [False])

    def test_explicit_live_toggle_still_synchronizes_a_different_pending_toggle(self):
        self.ui.changeTopBar("enabled", True)
        self.assertFalse(self.ui.saved["top_bar"]["enabled"])
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.setTopBarEnabled(False))
        save.assert_called_once()
        self.assertFalse(self.ui.draft["top_bar"]["enabled"])
        self.assertEqual(self.applied, ["topbar"])


if __name__ == "__main__":
    unittest.main()
