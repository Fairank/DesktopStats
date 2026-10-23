"""Real owned offscreen ComboBox events across history device notifications."""

import copy
import unittest

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from tests import test_history_qml as fixtures


def variant(value):
    return value.toVariant() if hasattr(value, "toVariant") else value


class HistoryOptionsRefreshQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.HistoryQmlTests.setUpClass()

    def setUp(self):
        # Reuse only the renderer/event fixture, not its test methods.
        self.fixture = fixtures.HistoryQmlTests()
        self.fixture.setUp()
        self.observations = []
        self.controller = self.fixture.controller
        self.controller.options = [dict(id="synthetic:" + str(index),
            label="Synthetic metric " + str(index), unit="%", scope="gpus", device_id=str(index),
            device_label="Synthetic device " + str(index), icon="gpu", available=True)
            for index in range(80)]

    def tearDown(self):
        try:
            self.fixture.tearDown()
        finally:
            self.fixture.doCleanups()

    def open_scrolled_choice(self, selected=0):
        self.page = self.fixture.load()
        self.page.choose("synthetic:" + str(selected))
        QTest.qWait(10)
        self.choice = self.fixture.find("historyMetricChoice")
        self.fixture.click("historyMetricChoice")
        # QQuickPopup* has no public PySide converter. Locate its existing
        # QObject child rather than changing product QML just for a test hook.
        popup = next((child for child in self.choice.findChildren(QObject)
                      if child.metaObject().indexOfProperty("opened") >= 0), None)
        self.assertIsNotNone(popup)
        self.assertTrue(popup.property("opened"))
        listing = popup.property("contentItem")
        self.assertGreater(listing.property("contentHeight"), listing.height() + 100)
        point = listing.mapToScene(listing.boundingRect().center())
        QTest.mouseMove(self.fixture.window, point.toPoint())
        for _ in range(3):
            event = QWheelEvent(point, self.fixture.window.mapToGlobal(point.toPoint()),
                QPoint(), QPoint(0, -360), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
            self.fixture.app.sendEvent(self.fixture.window, event)
            QTest.qWait(45)
        QTest.qWait(120)
        self.assertGreater(listing.property("contentY"), 100, "A real popup wheel must scroll")
        return popup, listing

    def test_identical_options_notifications_preserve_open_popup_scroll_selection_and_highlight(self):
        popup, listing = self.open_scrolled_choice(selected=12)
        before = dict(contentY=listing.property("contentY"), current=self.choice.property("currentIndex"),
                      highlight=self.choice.property("highlightedIndex"), selected=self.page.property("selectedId"))
        self.observations.append(dict(phase="before", **before))
        for fresh_containers in (False, True, True):
            with self.subTest(fresh_containers=fresh_containers):
                if fresh_containers:
                    self.controller.options = copy.deepcopy(self.controller.options)
                self.controller.historyOptionsChanged.emit()
                QTest.qWait(40)
                self.observations.append(dict(phase="notification", contentY=listing.property("contentY"),
                    current=self.choice.property("currentIndex"), highlight=self.choice.property("highlightedIndex"),
                    selected=self.page.property("selectedId")))
                self.assertTrue(popup.property("opened"))
                self.assertAlmostEqual(listing.property("contentY"), before["contentY"], delta=1)
                self.assertEqual(self.choice.property("currentIndex"), before["current"])
                self.assertEqual(self.choice.property("highlightedIndex"), before["highlight"])
                self.assertEqual(self.page.property("selectedId"), before["selected"])

    def test_real_device_and_language_label_changes_still_update_choices_and_selected_metadata(self):
        self.open_scrolled_choice()
        self.controller.options[0].update(label="Updated language label", device_label="Updated device label",
                                          available=False)
        self.controller.historyOptionsChanged.emit()
        QTest.qWait(35)
        model = variant(self.choice.property("model"))
        self.assertEqual(model[0]["label"], "Updated language label · Updated device label")
        metadata = variant(self.page.property("selectedMetadata"))
        self.assertEqual(metadata["device_label"], "Updated device label")
        self.assertFalse(metadata["available"])
        self.assertEqual(self.page.property("selectedId"), "synthetic:0")
        new_device = dict(self.controller.options[-1], id="synthetic:new", label="New device metric")
        self.controller.options.append(new_device)
        self.controller.historyOptionsChanged.emit()
        QTest.qWait(35)
        self.assertEqual(self.choice.property("count"), 81)
        self.assertEqual(variant(self.choice.property("model"))[-1]["id"], "synthetic:new")
        self.controller.options = [row for row in self.controller.options if row["id"] != "synthetic:new"]
        self.controller.historyOptionsChanged.emit()
        QTest.qWait(35)
        self.assertEqual(self.choice.property("count"), 80)


if __name__ == "__main__":
    unittest.main()
