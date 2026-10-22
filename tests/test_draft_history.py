"""Editor undo transactions never change saved desktop state implicitly."""

import copy
import math
import unittest
from unittest.mock import patch

import native_controller as controls
from stats_config import DEFAULT
from widget_catalog import from_template


class DraftHistoryTests(unittest.TestCase):
    def setUp(self):
        value = copy.deepcopy(DEFAULT)
        value.update(widgets={"w_edit": from_template("status_bar")}, widget_order=["w_edit"])
        with patch.object(controls, "load", return_value=value):
            self.ui = controls.Controller()
        self.original = copy.deepcopy(self.ui._draft)

    def test_one_gesture_undo_redo_preserves_saved_desktop(self):
        self.assertTrue(self.ui.setWidgetDimensions("w_edit", 760, 140))
        edited = copy.deepcopy(self.ui._draft)
        self.assertTrue(self.ui.canUndoDraft)
        with patch.object(controls, "save") as save:
            self.assertTrue(self.ui.undoDraft())
            self.assertEqual(self.ui._draft, self.original)
            self.assertEqual(self.ui._saved, self.original)
            self.assertTrue(self.ui.redoDraft())
            self.assertEqual(self.ui._draft, edited)
            save.assert_not_called()

    def test_rejected_and_noop_operations_do_not_add_history(self):
        self.assertFalse(self.ui.setWidgetDimensions("w_edit", math.nan, 40))
        self.assertTrue(self.ui.edit(copy.deepcopy(self.ui._draft)))
        self.assertFalse(self.ui.canUndoDraft)

    def test_continuous_title_typing_is_one_transaction(self):
        with patch.object(controls.time, "monotonic", side_effect=[1, 1.2, 1.4]):
            for text in ("A", "AB", "ABC"):
                self.ui.changeWidget("w_edit", "title", text)
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, self.original)
        self.assertFalse(self.ui.canUndoDraft)
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui._draft["widgets"]["w_edit"]["title"], "ABC")

    def test_new_operation_after_undo_discards_redo_branch(self):
        self.ui.setWidgetDimensions("w_edit", 700, 100)
        self.ui.undoDraft()
        self.ui.changeWidget("w_edit", "show_title", True)
        self.assertFalse(self.ui.canRedoDraft)
        self.assertFalse(self.ui.redoDraft())

    def test_commit_creates_a_saved_history_boundary(self):
        self.ui.setWidgetDimensions("w_edit", 700, 100)
        with patch.object(controls, "save"), patch.object(controls, "set_autostart"):
            self.ui.apply()
        self.assertFalse(self.ui.canUndoDraft)
        self.assertFalse(self.ui.canRedoDraft)
        self.assertEqual(self.ui._saved, self.ui._draft)

    def test_quick_desktop_action_preserves_draft_but_prevents_stale_undo(self):
        self.ui.changeWidget("w_edit", "title", "Draft")
        with patch.object(controls, "save"):
            self.assertTrue(self.ui.quickWidget("w_edit", "layer", "pinned"))
        self.assertEqual(self.ui._draft["widgets"]["w_edit"]["title"], "Draft")
        self.assertEqual(self.ui._draft["widgets"]["w_edit"]["layer"], "pinned")
        self.assertFalse(self.ui.canUndoDraft)

    def test_removed_widget_and_its_bindings_restore_together(self):
        self.ui.removeWidget("w_edit")
        self.assertFalse(self.ui._draft["widget_order"])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft, self.original)


if __name__ == "__main__":
    unittest.main()
