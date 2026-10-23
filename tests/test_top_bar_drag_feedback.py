"""Owned offscreen pointer gestures, frozen slots and cancellation feedback."""
import copy
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from tests import test_top_bar_runtime as bars


class BarDragFeedbackTests(unittest.TestCase):
    setUpClass = classmethod(bars.QmlTopBarTests.setUpClass.__func__)
    setUp = bars.QmlTopBarTests.setUp
    tearDown = bars.QmlTopBarTests.tearDown
    visual = staticmethod(bars.QmlTopBarTests.visual)
    metric = bars.QmlTopBarTests.metric
    point = bars.QmlTopBarTests.point
    hover_until_open = bars.QmlTopBarTests.hover_until_open

    def start_drag(self):
        point = self.point()
        QTest.mouseMove(self.host.window, QPoint(-10, -10))
        QTest.mousePress(self.host.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.mouseMove(self.host.window, QPoint(point.x()-30, point.y()), 20)
        self.assertTrue(self.host.window.property("dragging"))
        return point

    def test_travelling_copy_tracks_pointer_and_keeps_source_hit_geometry_while_readings_update(self):
        window = self.host.window
        source = self.metric()
        geometry = source.boundingRect(), source.position()
        point = self.start_drag()
        ghost = self.visual(window, "topBarDragPreview")
        self.assertTrue(ghost.isVisible())
        self.assertEqual(ghost.width(), source.width())
        content = next(child for child in source.childItems() if child.property("row") is not None)
        self.assertEqual(content.opacity(), 0)  # No duplicate digits in the vacated slot.
        first_x = ghost.x()
        QTest.mouseMove(window, QPoint(point.x()-70, point.y()), 20)
        self.assertAlmostEqual(ghost.x(), first_x-40, delta=.1)
        self.controller.rows = copy.deepcopy(self.controller.rows)
        self.controller.rows[0]["value"] = "99999%"
        self.manager.update_rows()
        QTest.qWait(20)
        self.assertEqual((source.boundingRect(), source.position()), geometry)
        self.assertEqual(ghost.width(), source.width())
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(-20, point.y()))
        self.assertFalse(ghost.isVisible())
        self.assertFalse(window.property("dragHeld"))

    def test_right_button_cancels_while_left_is_held_without_saving_or_opening_menu(self):
        with patch.object(self.manager, "move_metric") as commit, patch.object(self.manager, "menu") as menu:
            point = self.start_drag()
            location = QPoint(point.x()-30, point.y())
            QTest.mousePress(self.host.window, Qt.RightButton, Qt.NoModifier, location)
            QTest.mouseRelease(self.host.window, Qt.RightButton, Qt.NoModifier, location)
            QTest.mouseRelease(self.host.window, Qt.LeftButton, Qt.NoModifier, location)
            self.assertFalse(self.host.window.property("dragHeld"))
            commit.assert_not_called()
            menu.assert_not_called()

    def test_release_outside_and_resize_cancel_without_saving(self):
        with patch.object(self.manager, "move_metric") as commit:
            point = self.start_drag()
            QTest.mouseMove(self.host.window, QPoint(point.x(), 80), 20)
            self.assertFalse(self.visual(self.host.window, "topBarLiveInsertion").isVisible())
            QTest.mouseRelease(self.host.window, Qt.LeftButton, Qt.NoModifier, QPoint(point.x(), 80))
            commit.assert_not_called()
            self.assertFalse(self.host.window.property("dragging"))
            point = self.start_drag()
            self.host.window.resize(self.host.window.width()-1, self.host.window.height())
            for _ in range(20):  # QWindow resize delivery precedes QML widthChanged.
                if not self.host.window.property("dragging"):
                    break
                QTest.qWait(10)
            self.assertFalse(self.host.window.property("dragging"))
            QTest.mouseRelease(self.host.window, Qt.LeftButton, Qt.NoModifier, point)
            commit.assert_not_called()

    def test_hover_details_marks_active_metric_before_it_is_pinned(self):
        self.hover_until_open(self.point())
        chrome = self.visual(self.host.window, "topBarMetricChrome_b_0")
        self.assertTrue(chrome.property("selected"))
        self.assertFalse(chrome.property("pinned"))
        self.manager.close_panel()
        self.assertFalse(chrome.property("selected"))


if __name__ == "__main__":
    unittest.main()
