"""Integrated native workspace pages, owned offscreen windows and fake data only."""
import copy
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QUrl, qInstallMessageHandler
from PySide6.QtGui import QFontDatabase, QWheelEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import getCppPointer

import native_controller as controls
from native_card import HardwareCard
from native_surface import MaterialSurface
from stats_config import DEFAULT
from workspace_scenarios import SceneStore

ROOT = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")


class IntegratedWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QPA offscreen uses FreeType, rather than Windows DirectWrite. Point it
        # at the actual tested UI fonts, not every optional .fon/.ttf on the PC.
        # No warning is filtered: invalid/missing fixture faces must fail here.
        font_root = ROOT / "qa-private/workspace-ui-fonts"
        font_root.mkdir(exist_ok=True)
        font_names = ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "segoeuib.ttf", "msyh.ttc", "msyhbd.ttc")
        for name in font_names:
            font = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts" / name
            if font.is_file():
                shutil.copyfile(font, font_root / name)
        if QApplication.instance() is None:
            cls.enterClassContext(patch.dict(os.environ, {"QT_QPA_FONTDIR": str(font_root)}))
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
        for font in font_root.iterdir():
            assert QFontDatabase.addApplicationFont(str(font)) >= 0, font.name

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.save = self.enterContext(patch("native_controller.save"))
        self.enterContext(patch("workspace_tools.save"))
        self.folder = self.enterContext(tempfile.TemporaryDirectory(dir=ROOT / "qa-private", prefix="workspace-ui-"))
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.ui._scene_store = SceneStore(Path(self.folder) / "scenes.json")
        self.now = time.time()
        self.ui._data = dict(time=self.now, cpu_usage=38, cpu_temp=74, cpu_power=21.8,
                             ram_percent=56, battery_percent=80, battery_watts=0,
                             gpus={"0":dict(gpu_usage=14, gpu_temp=60, gpu_power=11.4)},
                             provider_status=dict(nvml=dict(state="connected", error={}),
                                 battery=dict(state="ready", error={}),
                                 asus=dict(state="waiting_retry", error=dict(api="DeviceIoControl", winerror=5))))
        self.ui._devices = {"gpus":{"0":dict(label="Synthetic GPU")}}
        values = [18, 20, 19, 22, 68, 91, 32, None, 26, 25, 76, 40, 39, 21, 19, 20, 49, 66, 33, 28]
        # Each non-gap bin summarizes eight explicit synthetic samples. Both
        # extrema are real members; the remaining six preserve the exact mean.
        samples = [None if value is None else [value-2, *([value-1/3]*6), value+4]
                   for value in values]
        valid = [value for group in samples if group is not None for value in group]

        def query(metric, period, **kwargs):
            return dict(metric=metric, unit="%", start=self.now-600, end=self.now, resolution=30,
                        points=[dict(time=self.now-600+i*30, end=self.now-570+i*30, gap=value is None,
                                     mean=value, minimum=value-2 if value is not None else None,
                                     peak=value+4 if value is not None else None)
                                for i,value in enumerate(values)],
                        summary=dict(latest=valid[-1], latest_time=self.now-1,
                                     mean=sum(valid)/len(valid), minimum=min(valid),
                                     peak=max(valid), count=len(valid), missing_count=8),
                        status=dict(state="ready",detail="仅本机保存 · 明确的合成测试样本"))
        self.history = Mock(status=dict(state="ready", detail="仅本机保存 · 明确的合成测试样本"))
        self.history.query.side_effect = query
        self.ui._history_backend = self.history
        self.messages = []
        self.previous = qInstallMessageHandler(lambda kind, context, text: self.messages.append(text))
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        self.assertFalse(self.component.isError(), [error.toString() for error in self.component.errors()])
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.setProperty("nativeHosted", True)
        self.window.resize(1180, 760)
        self.window.show()
        QTest.qWait(100)

    def tearDown(self):
        self.ui.close()
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.ui.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        qInstallMessageHandler(self.previous)
        self.native.assert_not_called()
        self.process.assert_not_called()
        self.assertEqual(self.messages, [])

    def item(self, name):
        pending = [self.window.contentItem(), *self.window.findChildren(QQuickItem)]
        visited = set()
        while pending:
            item = pending.pop()
            identity = getCppPointer(item)[0]
            if identity in visited:
                continue
            visited.add(identity)
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail(name)

    def click(self, name):
        item = self.item(name)
        point = item.mapToScene(item.boundingRect().center())
        self.assertTrue(item.isVisible(), name)
        self.assertTrue(item.isEnabled(), name)
        self.assertTrue(0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height(), (name, point))
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
        QTest.qWait(50)

    def sources(self):
        self.click("nav_4")
        self.click("historySourcesButton")
        self.assertEqual(self.window.property("page"), 2)

    def resize(self, width, height):
        self.window.resize(width, height)
        deadline = time.monotonic() + 1
        while self.window.property("resizeInProgress") and time.monotonic() < deadline:
            QTest.qWait(15)
        self.assertFalse(self.window.property("resizeInProgress"))
        QTest.qWait(35)

    def wheel(self, item, angle=-360):
        point = item.mapToScene(item.boundingRect().center())
        QTest.mouseMove(self.window, point.toPoint())
        event = QWheelEvent(point, self.window.mapToGlobal(point.toPoint()), QPoint(), QPoint(0, angle),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        event.setTimestamp(round(time.monotonic() * 1000))
        QCoreApplication.sendEvent(self.window, event)
        QTest.qWait(80)

    def settle_scroll(self, flickable):
        flickable.cancelFlick()
        flickable.returnToBounds()
        deadline = time.monotonic() + 1
        while flickable.property("moving") and time.monotonic() < deadline:
            QTest.qWait(15)
        self.assertFalse(flickable.property("moving"))
        self.assertGreaterEqual(flickable.property("contentY"), -.5)
        self.assertLessEqual(flickable.property("contentY"),
                             max(0, flickable.property("contentHeight") - flickable.height()) + .5)

    def test_history_is_one_click_and_never_saves_other_preferences(self):
        self.ui.change("refresh", .5)
        self.click("nav_4")
        self.assertEqual(self.window.property("page"), 4)
        self.assertTrue(self.item("historyPage").isVisible())
        self.assertTrue(self.item("historyLatestValue").property("text"))
        self.assertFalse(self.item("applyButton").isVisible())
        QTest.keyClick(self.window, Qt.Key_S, Qt.ControlModifier)
        self.save.assert_not_called()
        self.assertEqual(self.ui._saved["refresh"], DEFAULT["refresh"])

    def test_scene_popup_preview_cancel_and_escape_do_not_change_draft(self):
        before = copy.deepcopy(self.ui._draft)
        self.click("openScenesButton")
        self.click("scenarioPreviewButton_performance")
        self.assertTrue(self.item("selectedSceneLivePreview").isVisible())
        proposal = self.item("selectedSceneLivePreview").property("proposal")
        self.assertEqual(len((proposal.toVariant() if hasattr(proposal, "toVariant") else proposal)["windows"]), 2)
        self.assertEqual(self.ui._draft, before)
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(60)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.ui._draft, before)
        self.save.assert_not_called()

    def test_diagnostic_popup_has_actions_and_preserves_details_on_refresh(self):
        self.sources()
        self.click("sourceDiagnosticsButton")
        self.assertTrue(self.item("diagnosticCheckButton").isVisible())
        self.click("diagnosticDetails_asus")
        self.assertIn("asus", self.item("diagnosticsPanel").property("expandedIds").toVariant())
        self.assertTrue(self.item("diagnosticErrorText_asus").isVisible())
        self.ui.diagnosticCheckChanged.emit()
        QTest.qWait(40)
        self.assertTrue(self.item("diagnosticErrorText_asus").isVisible())
        self.assertTrue(self.item("diagnosticCheckButton").isVisible())
        self.click("diagnosticCheckButton")
        self.assertEqual(self.ui.diagnosticCheck["state"], "checking")
        self.assertFalse(self.item("diagnosticCheckButton").isEnabled())
        report = Path(self.folder) / "report.json"
        with patch("workspace_tools.QFileDialog.getSaveFileName", return_value=(str(report), "JSON (*.json)")) as dialog:
            self.click("diagnosticExportButton")
            dialog.assert_called_once()
        self.assertEqual(json.loads(report.read_text())["sources"]["asus"]["error"]["winerror"], 5)

    def test_diagnostic_popup_keyboard_never_applies_preferences_or_hides_settings(self):
        self.ui.change("refresh", .5)
        self.sources()
        self.click("sourceDiagnosticsButton")
        QTest.keyClick(self.window, Qt.Key_S, Qt.ControlModifier)
        self.save.assert_not_called()
        self.assertEqual(self.ui._saved["refresh"], DEFAULT["refresh"])
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(50)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.item("diagnosticCheckButton").isVisible())

    def test_narrow_popup_preview_uses_two_actual_hardware_cards_and_stays_bounded(self):
        self.resize(740, 650)
        self.click("openScenesButton")
        self.click("scenarioPreviewButton_performance")
        preview = self.item("selectedSceneLivePreview")
        self.assertGreater(preview.width(), 230)
        self.assertLessEqual(preview.property("viewScale"), 1)
        pending, widgets = [preview], []
        while pending:
            item = pending.pop()
            if item.objectName().startswith("sceneLiveWidget_"):
                widgets.append(item)
            pending.extend(item.childItems())
        self.assertEqual(len(widgets), 2)
        for item in widgets:
            self.assertTrue(item.isVisible())
            self.assertGreater(item.width(), 60)
            self.assertGreater(item.height(), 60)
            point = item.mapToScene(item.boundingRect().topLeft())
            self.assertGreaterEqual(point.x(), 0)
            self.assertLessEqual(point.x() + item.width(), self.window.width())
        self.assertEqual(self.save.call_count, 0)

    def test_diagnostic_refresh_preserves_reading_position_in_expanded_api_details(self):
        self.resize(740, 600)
        self.ui._data["provider_status"]["asus"]["error"]["message"] = "Synthetic interface detail " * 28
        for name in ("network", "disk", "volumes"):
            self.ui._data["provider_status"][name] = dict(state="waiting_retry", error=dict(api="Synthetic query", winerror=5))
        self.sources()
        self.click("sourceDiagnosticsButton")
        self.click("diagnosticDetails_asus")
        QTest.qWait(40)
        listing = self.item("diagnosticSourcesList")
        self.wheel(listing, -120)
        self.wheel(listing, -120)
        self.settle_scroll(listing)
        before = listing.property("contentY")
        self.assertGreater(before, 0)
        self.assertLess(before, listing.property("contentHeight") - listing.height() - 20)
        self.ui._data["provider_status"]["nvml"]["reason"] = "Synthetic updated source status"
        self.ui.diagnosticCheckChanged.emit()
        QTest.qWait(60)
        self.assertAlmostEqual(listing.property("contentY"), before, delta=1)
        self.assertTrue(self.item("diagnosticErrorText_asus").isVisible())

    def test_custom_scene_remove_requires_confirmation_and_does_not_apply_draft(self):
        self.ui.change("refresh", .5)
        for index in range(8):
            self.ui._scene_store.save("Synthetic scene " + str(index), self.ui._draft)
        self.ui._scene_store.remember_previous(self.ui._saved)
        self.ui.refreshScenes()
        custom = next(row["id"] for row in self.ui.scenes if row.get("custom") and row["id"] != "previous")
        before = copy.deepcopy(self.ui._draft)
        self.click("openScenesButton")
        for protected in ("office", "performance", "endurance", "previous"):
            self.assertFalse(self.item("scenarioRemoveButton_" + protected).isVisible())
        scroll = self.item("scenePickerScroll")
        target = self.item("scenarioRemoveButton_" + custom)
        for _ in range(10):
            local = target.mapToItem(scroll, target.boundingRect().center())
            if 0 <= local.y() < scroll.height()-160:
                break
            self.wheel(scroll, -180)
        self.settle_scroll(scroll.property("contentItem"))
        QTest.qWait(30)
        self.assertTrue(0 <= target.mapToItem(scroll, target.boundingRect().center()).y() < scroll.height()-160)
        self.click("scenarioRemoveButton_" + custom)
        self.assertTrue(any(row["id"] == custom for row in self.ui.scenes))
        self.click("scenarioRemoveCancel_" + custom)
        self.assertTrue(any(row["id"] == custom for row in self.ui.scenes))
        self.click("scenarioRemoveButton_" + custom)
        confirm = self.item("scenarioRemoveConfirm_" + custom)
        self.assertTrue(confirm.property("Accessible.name") or confirm.property("text"))
        confirm.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(60)
        self.assertFalse(any(row["id"] == custom for row in self.ui.scenes))
        self.assertEqual(self.ui._draft, before)
        self.assertEqual(self.ui._saved["refresh"], DEFAULT["refresh"])
        self.save.assert_not_called()
        # Removing one of eight frees a real persisted slot for a replacement.
        self.assertTrue(self.ui.saveScene("Replacement"))


if __name__ == "__main__":
    unittest.main()
