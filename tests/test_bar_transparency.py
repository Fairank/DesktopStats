"""Actual bar transparency controls and independent drafts, exclusively offscreen."""

import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import native_controller as controls
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT

ROOT = Path(__file__).resolve().parents[1]


class BarTransparencyControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "Never open a Windows test window"
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.save = self.enterContext(patch.object(controls, "save"))
        value = copy.deepcopy(DEFAULT)
        value.update(language="zh-CN", skin="glass", theme="light", glass_transparency=46.125)
        with patch.object(controls, "load", return_value=value):
            self.controller = controls.Controller()
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda values: self.warnings.extend(error.toString() for error in values))
        self.engine.rootContext().setContextProperty("stats", self.controller)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.setProperty("nativeHosted", True)
        self.window.setProperty("page", 3)
        self.window.resize(1100, 960)
        self.window.show()
        QTest.qWait(50)

    def tearDown(self):
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        self.controller.close()
        self.controller.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def find(self, name):
        result = self.window.findChild(QObject, name)
        if result is None:
            pending = [self.window.contentItem()]
            while pending:
                item = pending.pop()
                if item.objectName() == name:
                    return item
                pending.extend(item.childItems())
        self.assertIsNotNone(result, name)
        return result

    def click(self, item, fraction=.5):
        point = item.mapToScene(QPointF(item.width() * fraction, item.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(25)

    def test_slider_is_visible_with_inheritance_and_mouse_edit_only_changes_bar(self):
        options = self.find("topBarSecondarySettings")
        self.assertFalse(options.isVisible())
        slider = self.find("topBarTransparency")
        self.assertTrue(slider.isVisible() and slider.isEnabled())
        self.assertAlmostEqual(slider.property("value"), 46.125)
        original = copy.deepcopy(self.controller._saved)
        self.click(slider, .8)
        appearance = self.controller._draft["top_bar"]["appearance"]
        self.assertFalse(appearance["follow_global"])
        self.assertGreater(appearance["glass_transparency"], 70)
        self.assertEqual(self.controller._draft["glass_transparency"], 46.125)
        self.assertEqual(self.controller._saved, original)
        self.save.assert_not_called()
        self.click(self.find("topBarFollowGlobal"))
        self.assertTrue(self.controller._draft["top_bar"]["appearance"]["follow_global"])
        self.assertAlmostEqual(slider.property("value"), 46.125)

    def test_keyboard_endpoints_and_fractional_value_survive_bar_apply(self):
        slider = self.find("topBarTransparency")
        slider.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_End)
        self.assertEqual(self.controller._draft["top_bar"]["appearance"]["glass_transparency"], 100)
        QTest.keyClick(self.window, Qt.Key_Home)
        self.assertEqual(self.controller._draft["top_bar"]["appearance"]["glass_transparency"], 0)
        self.controller.change("refresh", .25)
        self.controller.changeTopBarAppearance("glass_transparency", 81.125)
        self.assertTrue(self.controller.applyTopBar())
        self.assertEqual(self.controller._saved["top_bar"]["appearance"]["glass_transparency"], 81.125)
        self.assertEqual(self.controller._draft["refresh"], .25)
        self.assertNotEqual(self.controller._saved["refresh"], .25)

    def test_responsive_row_and_non_glass_material_have_no_inoperative_slider(self):
        for width in (760, 1100, 1600):
            self.window.resize(width, 1000)
            for _ in range(40):
                QTest.qWait(10)
                if self.window.property("layoutWidth") == width:
                    break  # The editor deliberately settles after resizing ends.
            QTest.qWait(20)
            slider = self.find("topBarTransparency")
            self.assertTrue(slider.isVisible() and slider.width() > 70)
            left = slider.mapToScene(QPointF(0, 0)).x()
            self.assertGreaterEqual(left, 0)
            self.assertLessEqual(left + slider.width(), self.window.width())
        self.controller.changeTopBarAppearance("skin", "card")
        QTest.qWait(20)
        self.assertFalse(self.find("topBarTransparency").isVisible())
        self.controller.changeTopBarAppearance("skin", "glass")
        QTest.qWait(20)
        self.assertTrue(self.find("topBarTransparency").isVisible())


if __name__ == "__main__":
    unittest.main()
