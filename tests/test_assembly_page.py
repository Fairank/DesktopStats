"""Actual assembly settings page, isolated offscreen with synthetic identities."""
import copy
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

import native_controller as controls
from localization import LANGUAGES, MESSAGES
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT

ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = dict(state="available", system=dict(manufacturer="Example"),
                enclosures=[], baseboards=[])


class AssemblyPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "Never open a native test window"
        fonts = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts"
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc",
                     "YuGothM.ttc", "malgun.ttf"):
            font = fonts/name
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch.object(controls, "save"))
        self.snapshot = self.enterContext(patch("chassis_identity.snapshot", return_value=copy.deepcopy(FIRMWARE)))
        self.modules = self.enterContext(patch("memory_identity.modules", return_value=[
            dict(manufacturer="Kingston", part_number="KF560C36BBE-16", form_factor="dimm")]))
        value = copy.deepcopy(DEFAULT)
        value.update(language="zh-CN", theme="light")
        with patch.object(controls, "load", return_value=value):
            self.controller = controls.Controller()
        self.controller._data = dict(cpu_name="Intel Core i7-13700KF", gpus={"0": dict(
            gpu_name="NVIDIA GeForce RTX 5090", gpu_usage=24)})
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.engine.rootContext().setContextProperty("stats", self.controller)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.setProperty("nativeHosted", True)

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
                    result = item
                    break
                pending.extend(item.childItems())
        self.assertIsNotNone(result, name)
        return result

    def click(self, item):
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(25)

    def show_assembly(self, width=1280, height=760):
        self.window.resize(width, height)
        self.window.setProperty("page", 5)
        self.window.show()
        QTest.qWait(80)

    def test_page_is_lazy_and_navigation_selection_tracks_assembly_and_preferences(self):
        self.window.setProperty("page", 5)
        self.app.processEvents()
        self.snapshot.assert_not_called()
        self.show_assembly()
        self.snapshot.assert_called_once()
        self.modules.assert_called_once()
        self.assertTrue(self.controller.assemblySummary["initialized"])
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        selection = self.find("sidebarSelectionSurface")
        for page in (1, 5, 4, 3, 0):
            self.click(self.find("nav_" + str(page)))
            QTest.qWait(230)  # Let the existing sidebar selection transition finish.
            row = self.find("nav_" + str(page))
            self.assertAlmostEqual(selection.y(), row.y(), delta=.01)
        self.snapshot.assert_called_once()
        self.assertNotIn("assembly_viewer", sys.modules)

    def test_case_choice_changes_only_preferences_and_open_is_a_request(self):
        self.show_assembly()
        before = copy.deepcopy(self.controller.saved)
        choice = self.find("assemblyCaseChoice")
        choice.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_End)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(30)
        selected = self.controller.draft["assembly"]["case_model"]
        self.assertTrue(selected)
        self.assertEqual(self.controller.assemblySummary["identity_state"], "manual")
        self.assertEqual(self.controller.saved, before)
        self.assertEqual(self.controller.scopeDirty, dict(desktop=False, preferences=True, topbar=False))
        opened = QSignalSpy(self.controller.assemblyViewRequested)
        button = self.find("openAssemblyViewButton")
        self.assertTrue(button.isEnabled())
        button.clicked.emit()
        self.assertEqual(opened.count(), 1)
        self.assertEqual(opened.at(0)[0]["case"]["id"], selected)
        self.assertNotIn("assembly_viewer", sys.modules)

    def test_widths_and_languages_keep_controls_in_content_and_auto_choice_translated(self):
        self.show_assembly()
        proof = os.environ.get("DESKTOP_STATS_ASSEMBLY_PAGE_PROOF")
        if proof:
            Path(proof).mkdir(parents=True, exist_ok=True)
        sizes = [(1280,760,"zh-CN"),(1280,760,"en")]
        sizes.extend((720,600,language) for language in LANGUAGES)
        for width, height, language in sizes:
            self.controller.change("language", language)
            self.window.resize(width,height)
            for _ in range(60):
                QTest.qWait(10)
                if self.window.property("layoutWidth") == width:
                    break
            QTest.qWait(30)
            self.assertEqual(self.window.property("layoutWidth"),width)
            choice = self.find("assemblyCaseChoice")
            x = choice.mapToScene(QPointF(0,0)).x()
            self.assertGreaterEqual(x, self.window.property("railWidth"))
            self.assertLessEqual(x+choice.width(),width)
            self.assertGreater(choice.width(),300)
            self.assertEqual(choice.property("displayText"), self.controller.tr("自动识别 / 参考机箱"))
            button = self.find("openAssemblyViewButton")
            top = button.mapToScene(QPointF(0,0))
            self.assertGreaterEqual(top.x(),self.window.property("railWidth"))
            self.assertLessEqual(top.x()+button.width(),width)
            self.assertGreaterEqual(top.y(),34)
            self.assertLessEqual(top.y()+button.height(),height-72)
            loader = self.find("assemblyPageLoader")
            pending = [loader.property("item")]
            found_label = None
            while pending:
                item = pending.pop()
                if item.property("text") == self.controller.tr("内存"):
                    found_label = item
                    break
                pending.extend(item.childItems())
            self.assertIsNotNone(found_label)
            self.assertGreaterEqual(found_label.width(),100)
            if proof:
                self.assertTrue(self.window.grabWindow().save(str(Path(proof)/f"assembly-{width}-{language}.png")))

    def test_new_assembly_copy_has_all_eight_language_entries(self):
        keys = set()
        for filename in ("native/AssemblyPage.qml", "assembly_window.py"):
            source = (ROOT/filename).read_text(encoding="utf-8")
            keys.update(re.findall(r'(?:ui\.t|controller\.tr|self\.controller\.tr)\("([^"]+)"\)', source))
        keys.update(("自动识别 / 参考机箱", "参考机箱（未识别）", "处理器未识别", "显卡未识别",
                     "内存型号未识别", "主板布局示意", "整机视图设置格式不正确", "机箱型号设置不正确",
                     "整机视图开关设置不正确"))
        for language in set(LANGUAGES)-{"zh-CN"}:
            for key in keys:
                self.assertTrue(MESSAGES[language].get(key), (language,key))


if __name__ == "__main__":
    unittest.main()
