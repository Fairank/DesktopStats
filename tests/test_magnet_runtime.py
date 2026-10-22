"""Release/animation lifecycle with fake windows, without desktop input or APIs."""

import copy
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/magnet-runtime-unit-data"),
)

from PySide6.QtCore import QObject, QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from magnet_layout import separated
from native_runtime import Runtime
from stats_config import DEFAULT


class Window:
    def __init__(self, x, y):
        self.point = (x, y)
        self.props = {}

    def x(self):
        return self.point[0]

    def y(self):
        return self.point[1]

    def width(self):
        return 100

    def height(self):
        return 100

    def isVisible(self):
        return True

    def setPosition(self, x, y):
        self.point = (x, y)

    def setProperty(self, name, value):
        self.props[name] = value


class MagnetRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.runtime = Runtime.__new__(Runtime)
        QObject.__init__(self.runtime)
        r = self.runtime
        r.app = SimpleNamespace(
            screens=lambda: [SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 800, 600))]
        )
        config = copy.deepcopy(DEFAULT)
        config.update(magnet_enabled=True, magnet_gap=12, magnet_bounce=True)
        r.controller = SimpleNamespace(
            _saved=config, set_status=Mock(), update_preview_position=Mock()
        )
        r.widgets = {"a": Window(20, 100), "b": Window(250, 100)}
        r.motion, r.drag_origins, r.positions = {}, {}, {}
        r.position_timer = Mock()
        r.shutting_down = False

    def tearDown(self):
        for key in list(self.runtime.motion):
            self.runtime.cancel_motion(key)

    def release_over_neighbor(self):
        r = self.runtime
        r.begin_move("a")
        r.widgets["a"].setPosition(235, 100)
        r.end_move("a")

    def test_reduced_motion_lands_without_an_animation_or_moving_the_neighbor(self):
        with patch("native_runtime.animations_enabled", return_value=False):
            self.release_over_neighbor()
        r = self.runtime
        self.assertEqual(r.motion, {})
        self.assertEqual(r.widgets["b"].point, (250, 100))
        self.assertTrue(separated((*r.widgets["a"].point, 100, 100), [(250, 100, 100, 100)], 12))
        self.assertEqual(r.positions["a"], list(r.widgets["a"].point))

    def test_user_disabling_the_bounce_does_not_query_system_motion(self):
        self.runtime.controller._saved["magnet_bounce"] = False
        with patch("native_runtime.animations_enabled") as motion:
            self.release_over_neighbor()
        motion.assert_not_called()
        self.assertEqual(self.runtime.motion, {})

    def test_spring_finishes_at_a_legal_position_and_records_only_its_final_target(self):
        with patch("native_runtime.animations_enabled", return_value=True):
            self.release_over_neighbor()
        r = self.runtime
        self.assertIn("a", r.motion)
        self.assertFalse(r.widgets["a"].props["registered"])
        QTest.qWait(550)
        self.assertEqual(r.motion, {})
        self.assertTrue(r.widgets["a"].props["registered"])
        self.assertEqual(r.positions["a"], list(r.widgets["a"].point))
        self.assertTrue(separated((*r.widgets["a"].point, 100, 100), [(250, 100, 100, 100)], 12))

    def test_grabbing_mid_animation_cancels_old_finish_and_retains_the_new_origin(self):
        with patch("native_runtime.animations_enabled", return_value=True):
            self.release_over_neighbor()
        r = self.runtime
        QTest.qWait(50)
        point = r.widgets["a"].point
        r.begin_move("a")
        self.assertEqual(r.motion, {})
        self.assertEqual(r.drag_origins["a"], point)
        QTest.qWait(500)
        self.assertEqual(r.widgets["a"].point, point)

    def test_duplicate_native_and_qml_release_does_not_start_another_animation(self):
        with patch("native_runtime.animations_enabled", return_value=True):
            self.release_over_neighbor()
            animation = self.runtime.motion["a"]
            self.runtime.end_move("a")
        self.assertIs(self.runtime.motion["a"], animation)

    def test_shutdown_cancellation_records_the_legal_final_target(self):
        with patch("native_runtime.animations_enabled", return_value=True):
            self.release_over_neighbor()
        r = self.runtime
        target = r.motion["a"].property("settle_target")
        r.shutting_down = True
        r.cancel_motion("a", finish=True)
        self.assertEqual(r.widgets["a"].point, tuple(target))
        self.assertEqual(r.positions["a"], target)
        self.assertEqual(r.motion, {})

    def test_locked_widgets_ignore_drag_signals(self):
        self.runtime.controller._saved["locked"] = True
        self.runtime.begin_move("a")
        self.runtime.end_move("a")
        self.assertEqual(self.runtime.drag_origins, {})
        self.assertEqual(self.runtime.widgets["a"].point, (20, 100))


if __name__ == "__main__":
    unittest.main()
