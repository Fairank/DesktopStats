"""Real Settings mouse/key selections through scoped save to fake dual-screen AppBar.

All windows are offscreen. No native APIs, collectors, profile IO or installation.
"""

import copy
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import native_controller as controls
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT
from top_bar_layout import PixelRect
from top_bar_runtime import TopBarManager

if __package__:
    from .test_top_bar_runtime import Adapter, Application, Screen, Window
else:
    from test_top_bar_runtime import Adapter, Application, Screen, Window

QQuickStyle.setStyle("Basic")
FIRST, SECOND = r"\\.\DISPLAY1", r"\\.\DISPLAY2"


class TopBarMonitorSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "No Windows desktop UI"
        cls.root = Path(__file__).resolve().parents[1]
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            path = Path("C:/Windows/Fonts") / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.addCleanup(patch.stopall)
        self.native = patch("ctypes.WinDLL", side_effect=AssertionError("No native API")).start()
        self.process = patch("subprocess.Popen", side_effect=AssertionError("No processes")).start()
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.ui.set_motion_enabled(False)
        self.inventory = [
            dict(id="TL140ADXP02-0", label="TL140ADXP02-0", native_id=FIRST, primary=True,
                 x=0, y=0, width=1463, height=914),
            dict(id="Mi Monitor", label="Mi Monitor", native_id=SECOND, primary=False,
                 x=0, y=-1440, width=2048, height=1152),
        ]
        self.ui.set_screen_inventory(self.inventory)
        self.first = Screen("TL140ADXP02-0", PixelRect(0, 0, 2560, 1600), dpi=168,
                            native_id=FIRST, handle=18)
        self.second = Screen("Mi Monitor", PixelRect(0, -1800, 2560, -360), dpi=120,
                             native_id=SECOND, handle=19)
        self.fake_app = Application([self.first, self.second])
        self.adapter = Adapter()
        self.runtime = SimpleNamespace(app=self.fake_app, controller=self.ui, headless=True,
                                       show_settings=lambda *_: None)
        self.manager = TopBarManager(self.runtime, adapter=self.adapter, window_factory=Window)
        self.ui.topBarApplyRequested.connect(lambda: self.manager.apply(self.ui.saved))
        self.save = patch.object(controls, "save").start()
        self.engine = QQmlApplicationEngine()
        self.engine.setOutputWarningsToStandardError(False)
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(e.toString() for e in rows))
        self.engine.load(QUrl.fromLocalFile(str(self.root / "native/Settings.qml")))
        self.assertTrue(self.engine.rootObjects(), self.warnings)
        self.window = self.engine.rootObjects()[0]
        self.window.resize(1024, 700)
        self.window.setProperty("page", 3)
        self.window.show()  # Asserted offscreen only; no native desktop window.
        QTest.qWait(35)
        self.find("topBarSettings").setProperty("barOptionsOpen", True)
        QTest.qWait(20)

    def tearDown(self):
        self.manager.close()
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.engine.deleteLater()
        self.ui.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def find(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail("Missing control " + name)

    def reveal(self, item):
        # Config changes and font/layout polish can update contentHeight on
        # separate turns. Recompute the scroll target after those updates;
        # never click an old scene coordinate outside the visible viewport.
        for _ in range(25):
            parent = item.parentItem()
            while parent:
                if parent.property("contentY") is not None:
                    point = item.mapToItem(parent, QPointF(0, 0))
                    target = parent.property("contentY")
                    if point.y() < 8:
                        target += point.y() - 8
                    elif point.y() + item.height() > parent.height() - 8:
                        target += point.y() + item.height() - parent.height() + 8
                    parent.setProperty("contentY", max(0, min(
                        max(0, parent.property("contentHeight") - parent.height()), target)))
                parent = parent.parentItem()
            QTest.qWait(10)
            point = item.mapToScene(item.boundingRect().center())
            if 0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height():
                return

    def click(self, name):
        item = self.find(name)
        self.reveal(item)
        self.assertTrue(item.isVisible(), name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        self.assertTrue(0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height(),
                        (name, point, self.window.size()))
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(20)

    def mode(self, key):
        self.click("topBarMonitorChoice")
        QTest.keyClick(self.window, Qt.Key_Home)
        for _ in range({"primary": 0, "all": 1, "selected": 2}[key]):
            QTest.keyClick(self.window, Qt.Key_Down)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(20)
        self.assertEqual(self.ui.draft["top_bar"]["monitor_mode"], key)

    def test_actual_second_monitor_mouse_selection_saves_and_creates_only_secondary_host(self):
        self.ui.changeTopBar("enabled", True)
        self.ui.change("refresh", .35)
        self.ui.changeWidget("cpu", "title", "Draft desk")
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "Draft desk")
        saved = copy.deepcopy(self.ui.saved)
        self.mode("selected")
        self.click("topBarScreen_" + SECOND)
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [SECOND])
        self.assertEqual(self.ui.saved, saved)
        self.click("applyButton")
        self.assertEqual(self.ui.saved["top_bar"]["screens"], [SECOND])
        self.assertEqual(self.ui.saved["top_bar"]["monitor_mode"], "selected")
        self.assertEqual(self.ui.saved["refresh"], saved["refresh"])
        self.assertEqual(self.ui.draft["refresh"], .35)
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], "Draft desk")
        self.assertEqual(list(self.manager.hosts), [SECOND])
        self.assertIs(self.manager.hosts[SECOND].screen, self.second)
        self.assertEqual(self.manager.hosts[SECOND].binding.dpi, 120)
        self.assertLess(self.manager.hosts[SECOND].rect.top, 0)
        self.assertEqual(self.save.call_count, 1)

    def test_actual_checkbox_keyboard_toggle_remains_reachable_and_undoable(self):
        self.mode("selected")
        item = self.find("topBarScreen_" + SECOND)
        self.reveal(item)
        item.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(20)
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [SECOND])
        self.assertTrue(self.find("topBarScreen_" + SECOND).hasActiveFocus())
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(20)
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [])
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [SECOND])
        self.save.assert_not_called()

    def test_primary_all_and_selected_preserve_the_exact_native_selection(self):
        self.ui.changeTopBar("enabled", True)
        self.mode("selected")
        self.click("topBarScreen_" + SECOND)
        for mode, expected in (("all", {FIRST, SECOND}), ("primary", {FIRST}), ("selected", {SECOND})):
            self.mode(mode)
            self.click("applyButton")
            self.assertEqual(set(self.manager.hosts), expected)
            self.assertEqual(self.ui.saved["top_bar"]["screens"], [SECOND])

    def test_same_friendly_names_are_disambiguated_and_still_select_second(self):
        self.inventory[0]["label"] = self.inventory[1]["label"] = "Same model"
        self.first._name = self.second._name = "Same model"
        self.ui.set_screen_inventory(self.inventory)
        self.mode("selected")
        self.assertEqual(len(self.ui.topBarScreenChoices), 2)
        self.assertIn(FIRST, self.find("topBarScreen_" + FIRST).property("text"))
        self.assertIn(SECOND, self.find("topBarScreen_" + SECOND).property("text"))
        self.click("topBarScreen_" + SECOND)
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [SECOND])

    def test_legacy_javascript_array_boundary_is_converted_before_validate_and_undo(self):
        component = QQmlComponent(self.engine)
        code = 'import QtQml\nQtObject { function choose() { stats.changeTopBar("screens", %s) } }' % json.dumps([SECOND])
        component.setData(code.encode(), QUrl())
        obj = component.create()
        self.assertIsNotNone(obj, [e.toString() for e in component.errors()])
        try:
            obj.choose()
            self.assertEqual(self.ui.draft["top_bar"]["screens"], [SECOND])
            self.assertTrue(self.ui.undoDraft())
            self.assertEqual(self.ui.draft["top_bar"]["screens"], [])
        finally:
            obj.deleteLater()
            component.deleteLater()

    def test_typed_selection_rejects_unknown_ids_but_preserves_offline_choice(self):
        before = copy.deepcopy(self.ui.draft)
        self.assertFalse(self.ui.setTopBarScreenSelected("Mi Monitor", True))
        self.assertFalse(self.ui.setTopBarScreenSelected("unknown", True))
        self.assertEqual(self.ui.draft, before)
        self.assertTrue(self.ui.setTopBarScreenSelected(SECOND, True))
        self.ui.set_screen_inventory(self.inventory[:1])
        self.assertTrue(any(row["id"] == SECOND for row in self.ui.topBarScreenChoices))
        self.assertTrue(self.ui.setTopBarScreenSelected(SECOND, False))
        self.assertEqual(self.ui.draft["top_bar"]["screens"], [])


if __name__ == "__main__":
    unittest.main()
