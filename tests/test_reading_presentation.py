"""Fast recording must not flood UI bindings or drop the trailing reading."""

import copy
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QElapsedTimer
from PySide6.QtTest import QTest

import native_controller as controls
from stats_config import DEFAULT

APP = QCoreApplication.instance()


class ReadingPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Full discovery already creates QApplication; this file alone needs
        # one as well, so do not install a competing QCoreApplication globally.
        from PySide6.QtWidgets import QApplication
        cls.application = QCoreApplication.instance() or QApplication([])

    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.events = []
        self.ui.dataChanged.connect(lambda: self.events.append(self.ui.readings["cpu_usage"]))

    def test_burst_retains_all_history_and_coalesces_paints_with_trailing_latest(self):
        with patch.object(controls.time, "monotonic", return_value=10):
            for value in range(20):
                self.ui.receive(dict(time=100, cpu_usage=value))
        self.assertEqual(self.events, [0])
        self.assertEqual([row["cpu_usage"] for row in self.ui._history], list(range(20)))
        self.assertEqual(self.ui.readings["cpu_usage"], 19)
        self.assertTrue(self.ui._reading_notify_timer.isActive())
        # Assert eventual trailing delivery, not a scheduler-dependent 65ms
        # wall-clock deadline while the full Qt suite is also draining work.
        deadline = QElapsedTimer()
        deadline.start()
        while len(self.events) < 2 and deadline.elapsed() < 500:
            QTest.qWait(5)
        self.assertEqual(self.events, [0, 19])
        self.assertFalse(self.ui._reading_notify_timer.isActive())

    def test_normal_sampling_remains_immediate_and_close_cancels_trailing_work(self):
        # Freeze each sample's clock rather than depending on an incidental
        # number of calls (other live Qt callbacks can also read monotonic).
        with patch.object(controls.time, "monotonic", return_value=10) as clock:
            self.ui.receive(dict(time=100, cpu_usage=10))
            clock.return_value = 11
            self.ui.receive(dict(time=101, cpu_usage=11))
        self.assertEqual(self.events, [10, 11])
        with patch.object(controls.time, "monotonic", return_value=11):
            self.ui.receive(dict(time=101, cpu_usage=12))
        self.assertTrue(self.ui._reading_notify_timer.isActive())
        self.ui.close()
        QTest.qWait(65)
        self.assertEqual(self.events, [10, 11])


if __name__ == "__main__":
    unittest.main()
