"""Bar design systems, actual owned QML and fake platform registration only."""

import copy
import hashlib
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign37/profile")
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from tests import test_top_bar_groups_qml as fixture
from tests import test_top_bar_runtime as bars


class TopBarDesignUiTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GroupQmlTests.setUpClass.__func__)
    item = fixture.GroupQmlTests.item
    click = fixture.GroupQmlTests.click
    resize = fixture.GroupQmlTests.resize
    wheel = fixture.GroupQmlTests.wheel
    evaluate = fixture.GroupQmlTests.evaluate

    def setUp(self):
        self.bar_managers = []
        fixture.GroupQmlTests.setUp(self)

    def tearDown(self):
        try:
            for manager in self.bar_managers:
                manager.close()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        finally:
            fixture.GroupQmlTests.tearDown(self)

    def sample_rows(self):
        return fixture.variant(self.item("topBarSettings").property("designExampleRows"))

    def test_three_real_bar_samples_are_visible_without_opening_more_options(self):
        self.resize(1280, 900)
        self.click("nav_3")
        self.assertFalse(self.item("topBarSettings").property("barOptionsOpen"))
        for design in ("classic", "capsule", "instrument"):
            tile = self.item("topBarDesign_" + design)
            sample = self.item("topBarDesignSample_" + design)
            self.assertTrue(tile.isVisible())
            self.assertTrue(sample.property("sampleOnly"))
            self.assertFalse(sample.property("interactivePreview"))
            self.assertEqual(sample.property("barDesign"), design)
            self.assertGreater(sample.height(), 27)
            self.assertGreaterEqual(sample.property("shown"), 1)
            self.assertEqual(sample.property("hiddenCount"), 0)
            self.assertGreater(len(self.sample_rows()), 0)
            point = tile.mapToScene(QPointF())
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y() + tile.height(), self.window.height() - 72)

    def test_clicking_the_real_sample_changes_only_design_and_can_undo(self):
        self.ui.change("refresh", 0.5)
        before = copy.deepcopy(self.ui._draft)
        saved = copy.deepcopy(self.ui._saved)
        self.click("nav_3")
        tile = self.item("topBarDesign_capsule")
        point = tile.mapToScene(QPointF(tile.width() / 2, 20)).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(40)
        expected = copy.deepcopy(before)
        expected["top_bar"]["appearance"]["design"] = "capsule"
        self.assertEqual(self.ui._draft, expected)
        self.assertEqual(self.ui._saved, saved)
        self.assertTrue(self.ui._draft["top_bar"]["appearance"]["follow_global"])
        self.assertEqual(self.item("topBarMainPreview").property("barDesign"), "capsule")
        QTest.keyClick(self.window, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(40)
        self.assertEqual(self.ui._draft, before)
        self.save.assert_not_called()

    def test_keyboard_choice_and_scoped_apply_preserve_other_pending_preferences(self):
        self.ui.change("refresh", 0.5)
        self.click("nav_3")
        self.item("topBarDesign_instrument").forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(35)
        self.assertEqual(self.ui._draft["top_bar"]["appearance"]["design"], "instrument")
        self.click("applyButton")
        self.assertEqual(self.ui._saved["top_bar"]["appearance"]["design"], "instrument")
        self.assertEqual(self.ui._draft["refresh"], 0.5)
        self.assertNotEqual(self.ui._saved["refresh"], 0.5)
        self.assertEqual(self.save.call_count, 1)

    def test_narrow_samples_and_selection_do_not_clip_or_shrink_the_type(self):
        self.resize(740, 700)
        self.click("nav_3")
        tiles = [
            self.item("topBarDesign_" + design) for design in ("classic", "capsule", "instrument")
        ]
        for tile in tiles:
            point = tile.mapToScene(QPointF())
            self.assertGreaterEqual(point.x(), 184)
            self.assertLessEqual(point.x() + tile.width(), self.window.width())
            self.assertGreater(tile.width(), 125)
        for design in ("classic", "capsule", "instrument"):
            sample = self.item("topBarDesignSample_" + design)
            self.assertGreaterEqual(sample.property("shown"), 1)
            self.assertEqual(sample.property("hiddenCount"), 0)
            tile = self.item("topBarDesign_" + design)
            self.assertEqual(tile.height(), 56)
            sample_top = sample.mapToItem(tile, QPointF()).y()
            self.assertGreaterEqual(sample_top, 8)
            self.assertLessEqual(sample_top + sample.height(), tile.height() - 8)
        for design in ("capsule", "instrument", "classic"):
            self.click("topBarDesign_" + design)
            self.assertEqual(self.ui._draft["top_bar"]["appearance"]["design"], design)
            self.assertTrue(self.item("topBarDesign_" + design).property("chosen"))

    def test_unavailable_sample_keeps_a_missing_reading_instead_of_synthetic_zero(self):
        self.ui._data = {}
        self.ui.sensorsChanged.emit()
        self.click("nav_3")
        for row in self.sample_rows():
            self.assertEqual(row["value"], "—")
            self.assertFalse(row["available"])
        self.click("topBarDesign_capsule")
        self.assertEqual(self.item("topBarMainPreview").property("barDesign"), "capsule")
        self.assertFalse(self.ui._saved["top_bar"]["enabled"])

    def test_hidden_samples_stop_and_active_samples_do_not_rebuild_on_each_reading(self):
        self.click("nav_3")
        editor = self.item("topBarSettings")
        before = copy.deepcopy(self.sample_rows())
        timer = self.window.findChild(QObject, "topBarDesignSamplesTimer")
        self.assertTrue(timer.property("running"))
        for index in range(12):
            self.ui.receive(
                dict(self.ui._data, time=time.time(), cpu_usage=60 + index, external_revision=index)
            )
        QTest.qWait(50)
        self.assertEqual(fixture.variant(editor.property("rows"))[0]["value"], "71 %")
        self.assertEqual(self.sample_rows(), before)
        timer.setProperty("interval", 40)
        deadline = time.monotonic() + 1
        while self.sample_rows()[0]["value"] == before[0]["value"] and time.monotonic() < deadline:
            QTest.qWait(15)
        self.assertNotEqual(self.sample_rows()[0]["value"], before[0]["value"])
        timer.setProperty("interval", 2000)
        self.click("nav_1")
        self.assertFalse(timer.property("running"))
        self.assertEqual(self.sample_rows(), [])
        with patch.object(self.ui, "_top_bar_rows", wraps=self.ui._top_bar_rows) as readings:
            self.ui.sensorsChanged.emit()
            QTest.qWait(40)
            self.assertEqual(readings.call_count, 0)
        self.assertFalse(editor.property("active"))

    def make_bar(self, design="classic", height=32, width=1280):
        settings = copy.deepcopy(self.ui._saved)
        settings["top_bar"].update(enabled=True, height=height)
        settings["top_bar"]["appearance"]["design"] = design
        self.ui._saved = copy.deepcopy(settings)
        screen = bars.Screen("DISPLAY1", bars.PixelRect(0, 0, width, 1000))
        runtime = SimpleNamespace(
            app=bars.Application([screen]),
            controller=self.ui,
            headless=True,
            show_settings=lambda _key: None,
            engine=self.engine,
        )
        adapter = bars.QmlAdapter()
        manager = bars.TopBarManager(runtime, adapter=adapter)
        self.bar_managers.append(manager)
        manager.apply(settings)
        QTest.qWait(40)
        return manager, settings, screen, adapter

    def test_all_designs_have_distinct_real_paint_and_identical_native_hit_geometry(self):
        manager, settings, _screen, _adapter = self.make_bar()
        baseline = None
        painted = []
        for design in ("classic", "capsule", "instrument"):
            settings["top_bar"]["appearance"]["design"] = design
            manager.apply(settings)
            QTest.qWait(40)
            host = manager.hosts["DISPLAY1"]
            current = [(row.id, row.rect) for row in host.geometry.items]
            if baseline is None:
                baseline = current
            self.assertEqual(current, baseline)
            self.assertEqual(host.window.property("barDesign"), design)
            QTest.mouseMove(host.window, QPoint(-10, -10))
            QTest.qWait(15)
            image = host.window.grabWindow()
            self.assertFalse(image.isNull())
            painted.append(hashlib.sha256(image.constBits()).hexdigest())
            band = bars.QmlTopBarTests.visual(host.window, "topBarBandChrome")
            self.assertEqual(band.property("design"), design)
            for entry in host.geometry.items:
                chrome = bars.QmlTopBarTests.visual(host.window, "topBarMetricChrome_" + entry.id)
                pane = chrome.findChild(QObject, "topBarChromePane")
                self.assertGreaterEqual(pane.x(), 0)
                self.assertLessEqual(pane.x() + pane.width(), entry.rect.width + 0.1)
                self.assertLessEqual(pane.y() + pane.height(), host.window.height() + 0.1)
        self.assertEqual(len(set(painted)), 3)
        manager.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_capsule_hover_pinned_drag_and_overflow_chrome_share_the_same_system(self):
        manager, settings, screen, _adapter = self.make_bar("capsule", width=800)
        host = manager.hosts["DISPLAY1"]
        first = host.state.rows[0]
        metric = bars.QmlTopBarTests.visual(host.window, "topBarMetric_" + first["id"])
        chrome = bars.QmlTopBarTests.visual(host.window, "topBarMetricChrome_" + first["id"])
        point = metric.mapToScene(metric.boundingRect().center()).toPoint()
        QTest.mouseMove(host.window, point)
        QTest.qWait(30)
        self.assertTrue(chrome.property("hovered"))
        QTest.mouseClick(host.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(30)
        self.assertTrue(chrome.property("pinned"))
        self.assertTrue(manager._panel["pinned"])
        manager.close_panel()
        with patch.object(manager, "move_metric", return_value=True) as commit:
            QTest.mousePress(host.window, Qt.LeftButton, Qt.NoModifier, point)
            QTest.mouseMove(host.window, QPoint(point.x() - 20, point.y()), 20)
            self.assertTrue(chrome.property("dragged"))
            QTest.mouseRelease(
                host.window, Qt.LeftButton, Qt.NoModifier, QPoint(point.x() - 20, point.y())
            )
            self.assertEqual(commit.call_count, 1)
        screen.physical = bars.PixelRect(0, 0, 160, 1000)
        manager.apply(settings)
        QTest.qWait(40)
        host = manager.hosts["DISPLAY1"]
        self.assertGreater(host.state.overflowCount, 0)
        overflow = bars.QmlTopBarTests.visual(host.window, "topBarOverflow")
        overflow_chrome = bars.QmlTopBarTests.visual(host.window, "topBarOverflowChrome")
        self.assertTrue(overflow.isVisible())
        self.assertEqual(overflow_chrome.property("design"), "capsule")
        self.assertEqual(overflow_chrome.property("role"), "overflow")
        point = overflow.mapToScene(overflow.boundingRect().center()).toPoint()
        QTest.mouseClick(host.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(30)
        self.assertEqual(host.state.detail["id"], "__overflow__")
        self.assertTrue(overflow_chrome.property("pinned"))
        manager.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_both_line_styles_fit_28_32_40_without_changing_font_metrics(self):
        manager, settings, _screen, _adapter = self.make_bar("instrument")
        for index, item in enumerate(settings["top_bar"]["items"]):
            item["prefs"]["style"] = "stacked" if index % 2 else "graph"
        self.ui._saved = copy.deepcopy(settings)
        for design in ("classic", "capsule", "instrument"):
            settings["top_bar"]["appearance"]["design"] = design
            for height in (28, 32, 40):
                settings["top_bar"]["height"] = height
                manager.apply(settings)
                QTest.qWait(35)
                host = manager.hosts["DISPLAY1"]
                self.assertEqual(host.window.height(), height)
                for entry in host.geometry.items:
                    metric = bars.QmlTopBarTests.visual(host.window, "topBarMetric_" + entry.id)
                    content = next(
                        child for child in metric.childItems() if child.property("row") is not None
                    )
                    top = content.mapToItem(metric, QPointF()).y()
                    self.assertGreaterEqual(top, -0.1)
                    self.assertLessEqual(top + content.height(), height + 0.1)
                    self.assertEqual(content.property("design"), design)
        manager.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
