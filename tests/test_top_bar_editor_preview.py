"""Selected-only style history and direct menu semantics; no hardware/native IO."""

import copy
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import native_controller as controls
from native_surface import MaterialSurface
from stats_config import DEFAULT
from top_bar_runtime import TopBarManager

QQuickStyle.setStyle("Basic")


class TopBarEditorPreviewTests(unittest.TestCase):
    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.now = time.time()
        self.ui._data = dict(time=self.now, cpu_usage=0, cpu_temp=68, net_download=2)
        self.ui._history.extend(dict(time=self.now, cpu_usage=value, cpu_temp=value,
                                     net_download=value) for value in (0, None, 20, 30))
        self.first = self.ui._draft["top_bar"]["items"][0]

    def test_selected_candidate_has_true_history_before_selecting_trend_style(self):
        before = copy.deepcopy(self.ui._draft)
        regular = self.ui.topBarDraftRows()[0]
        selected = self.ui.topBarStylePreviewRow(self.first["id"])
        self.assertEqual(regular["history"], [])
        self.assertEqual(selected["history"], [0, None, 20, 30])
        self.assertTrue(selected["trend_available"])
        self.assertIsNone(selected["trend_points"][1])
        self.assertEqual(selected["related"], [])
        self.assertEqual(selected["numeric_value"], 0)
        self.assertEqual(self.ui._draft, before)
        self.assertFalse(self.ui.canUndoDraft)

    def test_selected_projection_is_one_item_not_sixty_four_history_copies(self):
        self.ui._draft["top_bar"]["items"] = [
            dict(id=f"b_{i}", metric="cpu_usage", prefs=dict(style="label_value"))
            for i in range(64)
        ]
        with patch.object(controls, "display_value", wraps=controls.display_value) as project:
            selected = self.ui.topBarStylePreviewRow("b_63")
        self.assertEqual(selected["id"], "b_63")
        self.assertEqual(project.call_count, 1 + len(self.ui._history))
        self.assertEqual(selected["related"], [])
        with patch.object(controls, "display_value", wraps=controls.display_value) as project:
            rows = self.ui.topBarDraftRows()
        self.assertEqual(project.call_count, 64)
        self.assertTrue(all(row["history"] == [] for row in rows))

    def test_invalid_selection_does_not_walk_history(self):
        with patch.object(controls, "display_value", wraps=controls.display_value) as project:
            for key in ("missing", "", None, True):
                self.assertEqual(self.ui.topBarStylePreviewRow(key), {})
        project.assert_not_called()

    def test_selected_history_uses_draft_units_and_precision(self):
        item = next(row for row in self.ui._draft["top_bar"]["items"] if row["metric"] == "cpu_temp")
        item["prefs"].update(temperature_unit="F", precision="2")
        row = self.ui.topBarStylePreviewRow(item["id"])
        self.assertEqual(row["number_text"], "154.40")
        self.assertEqual(row["unit_text"], "°F")
        self.assertEqual(row["value"], "154.40 °F")
        self.assertEqual(row["history"], [32, None, 68, 86])
        self.assertEqual(row["number_reserve"], "999.9")
        self.assertNotIn("temperature_unit", next(
            x for x in self.ui._saved["top_bar"]["items"] if x["id"] == item["id"])["prefs"])

    def test_split_reading_keeps_complete_legacy_value_and_percent_reserve(self):
        self.first["prefs"]["precision"] = "2"
        row = self.ui.topBarDraftRows()[0]
        self.assertEqual((row["number_text"], row["unit_text"], row["value"]), ("0.00", "%", "0.00 %"))
        self.assertEqual(row["number_reserve"], "100.00")
        self.first["prefs"]["precision"] = "auto"
        self.assertEqual(self.ui.topBarDraftRows()[0]["number_reserve"], "100")

    def test_missing_and_stale_data_do_not_create_trends_or_detached_units(self):
        self.ui._data["cpu_usage"] = None
        row = self.ui.topBarStylePreviewRow(self.first["id"])
        self.assertEqual((row["number_text"], row["unit_text"], row["value"]), ("—", "", "—"))
        self.assertFalse(row["trend_available"])
        self.assertEqual(row["trend_points"], [])
        self.ui._data.update(cpu_usage=50, time=self.now - 40)
        row = self.ui.topBarStylePreviewRow(self.first["id"])
        self.assertEqual(row["number_text"], "—")
        self.assertFalse(row["trend_available"])


class TopBarMenuDisableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"

    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.addCleanup(self.ui.close)
        self.ui._saved["top_bar"]["enabled"] = True
        self.ui._draft = copy.deepcopy(self.ui._saved)
        runtime = SimpleNamespace(app=self.app, controller=self.ui, headless=True)
        self.manager = TopBarManager(runtime)
        self.addCleanup(self.manager.close)
        self.manager.hosts["own-test"] = SimpleNamespace(state=SimpleNamespace(tr=lambda text: text))
        self.manager.close_panel = Mock()

    def menu_action(self):
        # Build the actual owned QAction/QMenu without a popup or native window.
        with patch("top_bar_runtime.QMenu.popup", new=lambda *_: None):
            self.manager.menu("own-test")
        self.manager.hosts.clear()  # No fake host enters production disposal.
        action = next(a for a in self.manager._menu.actions() if a.objectName() == "topBarDisable")
        self.assertFalse(action.text().endswith("…"))
        return action

    def test_disable_action_only_commits_enabled_without_opening_settings(self):
        self.ui.changeTopBar("height", 40)
        self.ui.change("size", 150)
        self.manager.runtime.show_settings = Mock()
        with patch.object(controls, "save") as save:
            self.menu_action().trigger()
        self.assertEqual(save.call_count, 1)
        self.assertFalse(self.ui._saved["top_bar"]["enabled"])
        self.assertFalse(self.ui._draft["top_bar"]["enabled"])
        self.assertEqual(self.ui._saved["top_bar"]["height"], 32)
        self.assertEqual(self.ui._draft["top_bar"]["height"], 40)
        self.assertEqual(self.ui._draft["size"], 150)
        self.manager.runtime.show_settings.assert_not_called()

    def test_failed_disable_keeps_enabled_and_pending_work(self):
        self.ui.changeTopBar("height", 40)
        before = copy.deepcopy((self.ui._saved, self.ui._draft))
        with patch.object(controls, "save", side_effect=OSError("fake save rejected")):
            self.menu_action().trigger()
        self.assertEqual((self.ui._saved, self.ui._draft), before)
        self.assertTrue(self.ui._saved["top_bar"]["enabled"])


class QmlTopBarEditorPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"
        cls.root = Path(__file__).resolve().parents[1]
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        with patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)):
            self.ui = controls.Controller()
        self.ui.change("language", "de")
        self.now = time.time()
        self.ui._data = dict(time=self.now, cpu_usage=27)
        self.ui._history.extend(dict(time=self.now, cpu_usage=n) for n in (0, 20, None, 30, 40))
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(lambda values: self.warnings.extend(v.toString() for v in values))
        self.component = QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Window
import "../../native"
Window {
 id:scene
 width:760; height:1100; visible:false
 color:stats.theme === "dark" ? "#1d2128" : "#f6f8fb"
 property real inspectorWidth:280
 TopBarPreviewStrip {
  objectName:"qaPreview"; x:16; y:12; width:scene.width-32
  rows:{const revision=stats.sensorRevision; const draft=stats.draft; return stats.topBarDraftRows()}
 }
 TopBarItemInspector {
  objectName:"qaInspector"; x:16; y:100; width:scene.inspectorWidth
  item:stats.draft.top_bar.items[0]
  row:{const revision=stats.sensorRevision; const draft=stats.draft; return stats.topBarDraftRows()[0]}
 }
}''', QUrl.fromLocalFile(str(self.root / "qa-private/redesign22/editor-preview-fixture.qml")))
        self.assertFalse(self.component.isError(), [e.toString() for e in self.component.errors()])
        self.window = self.component.create()
        self.assertIsNotNone(self.window)
        self.window.show()  # Asserted offscreen, never a native visible window.
        QTest.qWait(25)

    def tearDown(self):
        self.window.hide()
        self.window.destroy()
        self.window.deleteLater()
        self.component.deleteLater()
        self.engine.deleteLater()
        self.ui.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(self.warnings, [])

    def find(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail("Missing visual item " + name)

    def open_gallery(self):
        """Open the lazy, same-page chooser through its actual mouse target."""
        inspector = self.find("qaInspector")
        if not inspector.property("galleryOpen"):
            chooser = self.find("topBarStyleChooser")
            point = chooser.mapToScene(chooser.boundingRect().center()).toPoint()
            QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        gallery = self.find("topBarStyleGallery")
        deadline = time.monotonic() + 0.25
        while not gallery.property("item") and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(inspector.property("galleryOpen"))
        self.assertIsNotNone(gallery.property("item"))

    def test_real_candidates_have_history_and_click_keeps_scoped_draft(self):
        self.open_gallery()
        sample = self.find("topBarStyleSample_trend_value")
        self.assertTrue(sample.property("row").toVariant()["trend_available"])
        tile = self.find("topBarStyle_graph")
        point = tile.mapToScene(tile.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(5)
        self.assertFalse(self.find("qaInspector").property("galleryOpen"))
        self.assertEqual(self.ui._draft["top_bar"]["items"][0]["prefs"]["style"], "graph")
        self.assertEqual(self.ui._saved["top_bar"]["items"][0]["prefs"]["style"], "label_value")
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui._draft["top_bar"]["items"][0]["prefs"]["style"], "label_value")

    def test_all_eight_candidates_are_real_mouse_targets(self):
        for style in ("label_value", "value", "icon_value", "trend_value", "bar_value", "ring_value", "graph", "stacked"):
            self.open_gallery()
            tile = self.find("topBarStyle_" + style)
            point = tile.mapToScene(tile.boundingRect().center()).toPoint()
            self.assertTrue(self.window.geometry().size().width() > point.x() >= 0)
            self.assertTrue(self.window.geometry().size().height() > point.y() >= 0)
            QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(5)
            self.assertFalse(self.find("qaInspector").property("galleryOpen"))
            self.assertEqual(self.ui._draft["top_bar"]["items"][0]["prefs"]["style"], style)
        self.assertEqual(self.ui._saved["top_bar"]["items"][0]["prefs"]["style"], "label_value")

    def test_narrow_and_wide_samples_keep_real_size_and_complete_value(self):
        inspector = self.find("qaInspector")
        for width in (280, 472, 620):
            self.window.setProperty("inspectorWidth", width)
            QTest.qWait(10)
            self.assertEqual(inspector.width(), width)
            self.open_gallery()
            for style in ("label_value", "value", "icon_value", "trend_value", "bar_value", "ring_value", "graph", "stacked"):
                sample = self.find("topBarStyleSample_" + style)
                self.assertEqual(sample.scale(), 1, (width, style))
                origin = sample.mapToItem(inspector, 0, 0)
                self.assertGreaterEqual(origin.x(), -1, (width, style))
                self.assertLessEqual(origin.x() + sample.width(), width + 1, (width, style))
                self.assertEqual(sample.property("row").toVariant()["value"], "27 %")

    def test_preview_content_uses_six_dip_left_padding(self):
        first = self.ui._draft["top_bar"]["items"][0]
        self.ui.changeTopBarItem(first["id"], "style", "value")
        QTest.qWait(10)
        metric = self.find("topBarPreviewMetric_" + first["id"])
        pending = list(metric.childItems())
        value = None
        while pending:
            child = pending.pop()
            if child.objectName() == "topBarContentValue":
                value = child
                break
            pending.extend(child.childItems())
        self.assertIsNotNone(value)
        content = value.parentItem()
        self.assertAlmostEqual(content.mapToItem(metric, 0, 0).x(), 6, places=5)

    def external_temperature(self):
        sensor_id = "/qa22/temperature/0"
        channel = dict(id=sensor_id, type="Temperature", unit="°C", value=68, available=True)
        self.ui._external_rows[sensor_id] = channel
        self.ui._data["external_sensors"] = {sensor_id: channel}
        draft = copy.deepcopy(self.ui._draft)
        first = draft["top_bar"]["items"][0]
        first["metric"] = "external_1"
        first["prefs"].update(precision="2", temperature_unit="F", sensor_bindings={
            "external_1": dict(provider="LibreHardwareMonitor", sensor_id=sensor_id,
                               sensor_type="Temperature", name="GPU Memory Junction Temperature",
                               hardware_name="Synthetic GPU")})
        self.assertTrue(self.ui.edit(draft))
        QTest.qWait(15)

    def test_long_external_label_and_fahrenheit_keep_true_type_size_and_unit(self):
        self.external_temperature()
        inspector = self.find("qaInspector")
        for width in (280, 472, 620):
            self.window.setProperty("inspectorWidth", width)
            QTest.qWait(10)
            self.assertEqual(inspector.width(), width)
            self.open_gallery()
            for style in ("label_value", "value", "icon_value", "trend_value", "graph", "stacked"):
                sample = self.find("topBarStyleSample_" + style)
                self.assertEqual(sample.scale(), 1, (width, style))
                origin = sample.mapToItem(inspector, 0, 0)
                self.assertGreaterEqual(origin.x(), -1, (width, style))
                self.assertLessEqual(origin.x() + sample.width(), width + 1, (width, style))
                self.assertEqual(sample.property("row").toVariant()["value"], "154.40 °F")


if __name__ == "__main__":
    unittest.main()
