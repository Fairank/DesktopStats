"""Retained offscreen editors pause only live work; no hardware/process/native IO."""

import copy
import os
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QObject, Property, QCoreApplication, QEvent, QUrl, Slot
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import (
    QJSValue, QQmlComponent, QQmlEngine, QQmlExpression, qmlContext, qmlRegisterType,
)
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import getCppPointer

import native_controller as controls
from native_card import HardwareCard
from native_surface import MaterialSurface
from settings_backdrop_host import SettingsBackdropHost
from stats_config import DEFAULT

ROOT = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")


class CountedController(controls.Controller):
    def __init__(self):
        self.calls = Counter()
        super().__init__()

    def get_draft(self):
        self.calls["draft"] += 1
        return self._draft
    draft = Property("QVariantMap", get_draft, notify=controls.Controller.draftChanged)

    def get_readings(self):
        self.calls["readings"] += 1
        return self._data
    readings = Property("QVariantMap", get_readings, notify=controls.Controller.dataChanged)

    def get_history(self):
        self.calls["history"] += 1
        return list(self._history)
    history = Property("QVariantList", get_history, notify=controls.Controller.dataChanged)

    def get_revision(self):
        self.calls["revision"] += 1
        return self._sensor_revision
    sensorRevision = Property(int, get_revision, notify=controls.Controller.sensorsChanged)

    @Slot()
    def inspect(self):
        self.calls["inspect"] += 1

    def sensor_rows(self, prefs=None, *, discovered=True):
        self.calls["sensor_rows"] += 1
        return super().sensor_rows(prefs, discovered=discovered)

    @Slot(str, result="QVariantMap")
    def widgetHealth(self, key):
        self.calls["health"] += 1
        return super().widgetHealth(key)

    @Slot(str, str, result=str)
    def readingFor(self, key, metric):
        self.calls["readingFor"] += 1
        return super().readingFor(key, metric)

    @Slot(result="QVariantList")
    def topBarDraftRows(self):
        self.calls["topbar"] += 1
        return super().topBarDraftRows()

    @Slot(str, result="QVariantMap")
    def topBarStylePreviewRow(self, key):
        self.calls["style"] += 1
        return super().topBarStylePreviewRow(key)

    @Slot(str, result="QVariantList")
    def metricRowsFor(self, key):
        self.calls["metric_rows"] += 1
        return super().metricRowsFor(key)


def value(item, name):
    result = item.property(name)
    return result.toVariant() if isinstance(result, QJSValue) else result


class SettingsActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            font = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts" / name
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.host = None
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native IO")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch.object(controls.sensors.Sampler, "__init__", side_effect=AssertionError("No sampler")))
        self.enterContext(patch.object(controls, "save", side_effect=AssertionError("No persistence")))
        config = copy.deepcopy(DEFAULT)
        config.update(autostart=False, history_enabled=False, refresh=2)
        with patch.object(controls, "load", return_value=config):
            self.ui = CountedController()
        self.ui._data = self.sample(20)
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(ROOT / "native/Settings.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        QTest.qWait(15)

    def tearDown(self):
        if self.host is not None:
            self.host.dispose()
            self.host.deleteLater()
            self.host = None
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        self.ui.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.ui.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.native.assert_not_called()
        self.process.assert_not_called()
        self.assertEqual(self.warnings, [])

    def find(self, name):
        found = self.window.findChild(QObject, name)
        self.assertIsNotNone(found, name)
        return found

    def evaluate(self, item, text):
        expression = QQmlExpression(qmlContext(item), item, text)
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return result[0] if isinstance(result, tuple) else result

    def page(self, page):
        self.window.setProperty("page", page)
        QCoreApplication.processEvents()

    @staticmethod
    def sample(usage):
        return dict(time=time.time(), cpu_usage=usage, cpu_temp=40, cpu_power=20,
                    gpus={"0": dict(label="Synthetic GPU", gpu_usage=10)},
                    external_revision=usage)

    def deliver(self, usage=80):
        self.ui._reading_notify_at = float("-inf")
        self.ui.receive(self.sample(usage))
        QCoreApplication.processEvents()

    def pause(self, minimized=False):
        if minimized:
            self.window.showMinimized()
        else:
            self.window.hide()
        QCoreApplication.processEvents()
        self.ui.calls.clear()

    def resume(self):
        self.window.showNormal()
        QCoreApplication.processEvents()

    def editor_state(self):
        canvas = self.find("contentLayoutEditor")
        field = self.find("widgetWidthInput")
        inspector = field.parentItem()
        while inspector.metaObject().indexOfProperty("health") < 0:
            inspector = inspector.parentItem()
        editor = inspector.parentItem()
        while editor.metaObject().indexOfProperty("selectedKey") < 0:
            editor = editor.parentItem()
        return dict(canvas=getCppPointer(canvas), zoom=canvas.property("zoom"),
                    selected=value(canvas, "selectedIds"), selected_metric=canvas.property("selectedMetric"),
                    section=editor.property("section"), expanded=editor.property("expandedCanvas"),
                    folds=[inspector.property(name) for name in ("devicesOpen", "positionOpen", "displayOpen")],
                    scroll=self.find("widgetWorkspaceScroll").property("contentItem").property("contentY"),
                    field=field.property("text"), edited=field.property("userEdited"),
                    pending=self.window.property("pendingInput"), draft=copy.deepcopy(self.ui._draft),
                    undo=copy.deepcopy(self.ui._undo_drafts))

    def prepare_editor(self):
        self.ui.changeWidget("cpu", "title", "Draft")
        self.assertTrue(self.ui.dirty)
        self.assertTrue(self.ui.canUndoDraft)
        canvas = self.find("contentLayoutEditor")
        canvas.setProperty("zoom", 1.5)
        self.evaluate(canvas, 'selectedMetric="cpu_usage";selectedIds=["cpu_usage","cpu_temp"]')
        self.evaluate(canvas, 'let p=parent;while(p && p.expandedCanvas===undefined)p=p.parent;p.expandedCanvas=true;p.section="devices"')
        field = self.find("widgetWidthInput")
        field.setProperty("text", "unfinished")
        field.setProperty("userEdited", True)
        self.evaluate(field, 'let p=parent;while(p && p.devicesOpen===undefined)p=p.parent;p.devicesOpen=true;p.positionOpen=true;p.displayOpen=true')
        QCoreApplication.processEvents()
        self.find("widgetWorkspaceScroll").property("contentItem").setProperty("contentY", 35)

    def test_hidden_editor_skips_all_live_projection_and_restores_latest_with_inputs(self):
        self.prepare_editor()
        before = self.editor_state()
        self.pause()
        for usage in (40, 60, 80):
            self.deliver(usage)
        self.assertEqual(self.ui.calls, {})
        self.assertEqual(len(self.ui._history), 3)
        self.resume()
        self.assertEqual(self.editor_state(), before)
        self.assertEqual(value(self.find("contentLayoutEditor"), "previewReadings")["cpu_usage"], 80)

    def test_minimized_editor_retains_state_and_stops_inspection(self):
        self.prepare_editor()
        before = self.editor_state()
        self.pause(minimized=True)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.property("uiActive"))
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.resume()
        self.assertEqual(self.editor_state(), before)
        self.assertEqual(value(self.find("contentLayoutEditor"), "previewReadings")["cpu_usage"], 80)

    def test_hidden_topbar_never_reads_draft_or_projects_style_history(self):
        self.page(3)
        inspector = self.find("topBarSelectedInspector")
        self.assertTrue(inspector.property("visible"))
        self.pause()
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.resume()
        self.assertEqual(value(self.find("topBarSettings"), "rows")[0]["numeric_value"], 80)
        self.assertEqual(value(inspector, "stylePreviewRow")["numeric_value"], 80)

    def test_minimized_group_popup_keeps_pending_input_and_can_confirm_after_resume(self):
        self.page(3)
        inspector = self.find("topBarSelectedInspector")
        self.evaluate(inspector, 'openGroup();groupDraftMetrics=["cpu_usage","cpu_temp"]')
        self.assertTrue(inspector.property("pendingGroupEdits"))
        baseline = value(inspector, "groupBaseline")
        self.pause(minimized=True)
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.assertTrue(inspector.property("groupPopupOpen"))
        self.assertTrue(inspector.property("pendingGroupEdits"))
        self.assertEqual(value(inspector, "groupBaseline"), baseline)
        self.assertEqual(value(inspector, "groupDraftMetrics"), ["cpu_usage", "cpu_temp"])
        self.assertFalse(self.find("topBarDesignSamplesTimer").property("running"))
        self.resume()
        self.assertTrue(inspector.property("groupPopupOpen"))
        self.assertEqual(value(inspector, "stylePreviewRow")["numeric_value"], 80)
        self.evaluate(inspector, "confirmGroup()")
        self.assertFalse(inspector.property("groupPopupOpen"))
        self.assertEqual(self.ui._draft["top_bar"]["items"][0]["prefs"]["metrics"], ["cpu_usage", "cpu_temp"])
        self.assertTrue(self.ui.canUndoDraft)

    def test_minimized_sensor_browser_freezes_list_and_preserves_query_selection_scroll(self):
        self.page(2)
        browser = self.find("sensorBrowser")
        browser.setProperty("query", "cpu")
        listing = self.find("sensorResultsList")
        listing.setProperty("currentIndex", 3)
        listing.setProperty("contentY", 100)
        def state():
            return (browser.property("query"), browser.property("category"), listing.property("currentIndex"),
                    listing.property("contentY"), value(browser, "entries"))
        before = state()
        rows = value(browser, "rows")
        self.pause(minimized=True)
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.assertEqual(state(), before)
        self.assertEqual(value(browser, "rows"), rows)
        self.resume()
        self.assertEqual(state(), before)
        self.assertEqual(next(row for row in value(browser, "rows") if row["id"] == "cpu_usage")["value"], "80 %")

    def test_minimized_metric_gallery_preserves_pending_selection_and_pauses_inspect(self):
        gallery = self.find("widgetGallery")
        self.evaluate(gallery, 'showReadings("cpu");pendingMetrics=["cpu_usage","cpu_power"]')
        listing = self.find("galleryResultsGrid")
        listing.setProperty("currentIndex", 3)
        listing.setProperty("contentY", 120)
        def state():
            return (value(gallery, "pendingMetrics"), gallery.property("query"), gallery.property("category"),
                    listing.property("currentIndex"), listing.property("contentY"), value(gallery,"entries"))
        before = state()
        self.pause(minimized=True)
        self.assertTrue(gallery.property("opened"))
        self.assertFalse(self.find("galleryInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.assertEqual(state(), before)
        self.resume()
        self.assertTrue(gallery.property("opened"))
        self.assertEqual(state(), before)
        self.assertEqual(next(row for row in value(gallery, "liveRows") if row["id"] == "cpu_usage")["value"], "80 %")

    def test_minimized_widget_gallery_freezes_thumbnails_then_updates_once(self):
        gallery = self.find("widgetGallery")
        self.evaluate(gallery, "showWidgets()")
        initial = value(gallery,"previewReadings")
        self.pause(minimized=True)
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.assertEqual(value(gallery,"previewReadings"), initial)
        self.resume()
        self.assertTrue(gallery.property("opened"))
        self.assertEqual(value(gallery,"previewReadings")["cpu_usage"],80)

    def test_minimized_topbar_picker_keeps_filter_and_list_until_fresh_resume(self):
        self.page(3)
        editor = self.find("topBarSettings")
        picker = self.find("topBarMetricPicker")
        query = self.find("topBarMetricSearch")
        choices = self.find("topBarMetricChoices")
        self.evaluate(picker, "open()")
        query.setProperty("text", "cpu")
        choices.setProperty("currentIndex",2)
        choices.setProperty("contentY",20)
        QCoreApplication.processEvents()
        def state():
            return (picker.property("opened"), query.property("text"), choices.property("currentIndex"),
                    choices.property("contentY"), value(picker,"choiceIds"))
        before = state()
        self.pause(minimized=True)
        self.assertFalse(self.find("topBarPickerInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls, {})
        self.resume()
        self.assertEqual(state(),before)
        self.assertEqual(next(row for row in value(editor,"sensorChoices") if row["id"] == "cpu_usage")["value"],"80 %")

    def test_minimized_scene_popup_preserves_proposal_selection_and_confirmation(self):
        popup = self.find("scenePopup")
        # Scene inventory/selection is explicit fake state, never a disk query.
        with patch.object(self.ui,"refreshScenes"):
            self.evaluate(popup,"open()")
        popup.setProperty("selectedId","synthetic_scene")
        popup.setProperty("confirmId","synthetic_scene")
        proposal = dict(config=copy.deepcopy(self.ui._draft),windows=[])
        popup.setProperty("proposal",self.engine.toScriptValue(proposal))
        self.pause(minimized=True)
        self.deliver()
        self.assertEqual(self.ui.calls,{})
        self.assertTrue(popup.property("opened"))
        self.assertEqual(popup.property("selectedId"),"synthetic_scene")
        self.assertEqual(popup.property("confirmId"),"synthetic_scene")
        self.assertEqual(value(popup,"proposal"),proposal)
        self.resume()
        self.assertTrue(popup.property("opened"))
        self.assertEqual(value(popup,"proposal"),proposal)
        self.assertEqual(value(self.find("selectedSceneLivePreview"),"readings")["cpu_usage"],80)

    def test_standalone_components_keep_their_existing_active_defaults(self):
        component = QQmlComponent(self.engine)
        component.setData(b'''import QtQuick
import QtQuick.Window
Window {
 width:900;height:760;visible:false
 TopBarSettings {objectName:"standaloneBar";width:800;active:true}
 SensorBrowser {objectName:"standaloneBrowser";width:800;active:false}
 TopBarItemInspector {objectName:"standaloneInspector";visible:false;item:stats.draft.top_bar.items[0]}
 Gallery {objectName:"standaloneGallery"}
}''',QUrl.fromLocalFile(str(ROOT / "native/ActivityDefaultsFixture.qml")))
        fixture = component.create()
        self.assertIsNotNone(fixture,[error.toString() for error in component.errors()])
        try:
            bar = fixture.findChild(QObject,"standaloneBar")
            browser = fixture.findChild(QObject,"standaloneBrowser")
            inspector = fixture.findChild(QObject,"standaloneInspector")
            gallery = fixture.findChild(QObject,"standaloneGallery")
            self.assertTrue(bar.property("readingsActive"))
            self.assertFalse(browser.property("readingsActive"))
            self.assertFalse(inspector.property("readingsActive"))
            self.assertTrue(gallery.property("readingsActive"))
            bar.setProperty("active",False)
            browser.setProperty("active",True)
            self.assertFalse(bar.property("readingsActive"))
            self.assertTrue(browser.property("readingsActive"))
            self.assertEqual(value(bar,"rows"),[])
            self.assertTrue(value(browser,"rows"))
        finally:
            fixture.destroy()
            fixture.deleteLater()
            component.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def attach_host(self):
        self.window.hide()
        QCoreApplication.processEvents()
        self.host = SettingsBackdropHost(self.window,native=False)
        self.host.show()
        QCoreApplication.processEvents()

    def minimize_host(self):
        self.host.showMinimized()
        QCoreApplication.processEvents()
        self.ui.calls.clear()
        self.assertTrue(self.window.isVisible())
        # Child QQuickWindow remains Windowed: only the host owns minimize state.
        self.assertEqual(self.window.visibility().name,"Windowed")
        self.assertFalse(self.window.property("uiActive"))

    def test_host_minimized_editor_stops_dirty_inspection_without_losing_input(self):
        self.prepare_editor()
        self.attach_host()
        before = self.editor_state()
        self.assertTrue(self.find("settingsInspectTimer").property("running"))
        self.minimize_host()
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls,{})
        self.host.showNormal()
        QCoreApplication.processEvents()
        self.assertEqual(self.editor_state(),before)
        self.assertEqual(value(self.find("contentLayoutEditor"),"previewReadings")["cpu_usage"],80)

    def test_host_minimized_sensor_browser_stops_inspection_and_retains_viewport(self):
        self.attach_host()
        self.page(2)
        browser=self.find("sensorBrowser")
        browser.setProperty("query","cpu")
        listing=self.find("sensorResultsList")
        listing.setProperty("currentIndex",3)
        listing.setProperty("contentY",40)
        QCoreApplication.processEvents()
        def state():
            return (browser.property("query"),listing.property("currentIndex"),listing.property("contentY"),value(browser,"entries"))
        before=state()
        self.assertTrue(self.find("settingsInspectTimer").property("running"))
        self.minimize_host()
        self.assertTrue(browser.property("active"))
        self.assertFalse(browser.property("readingsActive"))
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls,{})
        self.assertEqual(state(),before)
        self.host.showNormal()
        QCoreApplication.processEvents()
        self.assertEqual(state(),before)
        self.assertEqual(next(row for row in value(browser,"rows") if row["id"]=="cpu_usage")["value"],"80 %")

    def test_host_minimized_group_popup_retains_draft_and_refreshes_latest_on_restore(self):
        self.ui.changeWidget("cpu","title","Draft")
        self.attach_host()
        self.page(3)
        inspector=self.find("topBarSelectedInspector")
        self.evaluate(inspector,'openGroup();groupDraftMetrics=["cpu_usage","cpu_temp"]')
        baseline=value(inspector,"groupBaseline")
        self.minimize_host()
        self.assertTrue(self.find("topBarSettings").property("active"))
        self.assertFalse(self.find("topBarSettings").property("readingsActive"))
        self.assertFalse(self.find("settingsInspectTimer").property("running"))
        self.deliver()
        self.assertEqual(self.ui.calls,{})
        self.assertTrue(inspector.property("groupPopupOpen"))
        self.assertTrue(inspector.property("pendingGroupEdits"))
        self.assertEqual(value(inspector,"groupBaseline"),baseline)
        self.assertEqual(value(inspector,"groupDraftMetrics"),["cpu_usage","cpu_temp"])
        self.host.showNormal()
        QCoreApplication.processEvents()
        self.assertTrue(inspector.property("groupPopupOpen"))
        self.assertEqual(value(inspector,"stylePreviewRow")["numeric_value"],80)
        self.evaluate(inspector,"confirmGroup()")
        self.assertFalse(inspector.property("groupPopupOpen"))
        self.assertEqual(self.ui._draft["top_bar"]["items"][0]["prefs"]["metrics"],["cpu_usage","cpu_temp"])

    def test_disposed_minimized_host_resets_computation_state_for_parentless_fallback(self):
        self.attach_host()
        self.host.showMinimized()
        QCoreApplication.processEvents()
        self.assertTrue(self.window.property("hostMinimized"))
        self.host.dispose()
        self.assertIsNone(self.window.parent())
        self.assertFalse(self.window.isVisible())
        self.assertIs(self.window.property("hostMinimized"),False)
        # State signals after disposal must not address the detached client.
        self.host.windowStateChanged.emit(self.host.windowState())
        self.host.deleteLater()
        self.host=None
        self.window.showNormal()
        QCoreApplication.processEvents()
        self.assertTrue(self.window.property("uiActive"))
        self.deliver()
        self.assertEqual(value(self.find("contentLayoutEditor"),"previewReadings")["cpu_usage"],80)


if __name__ == "__main__":
    unittest.main()
