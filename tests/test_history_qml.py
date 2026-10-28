"""Actual QML events and owned offscreen painting with synthetic history only."""

import copy
import ctypes
import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QSG_RENDER_LOOP", "basic")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/history-qml-profile"))

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]


def synthetic_history():
    start = 1792663200.0
    values = [9, 13, 12, 16, 61, 87, 72, 28, 22, 25, 23, 68, 71, 74, 70, 74, 18, 15, None, 14,
              92, 45, 31, 29, 68, 69, 66, 67, 52, 24, 13, 12, 14, 15, 40, 82, 47, 20, 18, 21]
    points, raw_values = [], []
    for index, value in enumerate(values):
        if value is None:
            points.append(dict(timestamp=start + index * 15, value=None))
            continue
        low, peak = max(0, value - 1 - index % 5), min(100, value + [2, 5, 1, 11, 7][index % 5])
        middle = (16 * value - low - peak) / 14
        raw_bin = [low] + [middle] * 14 + [peak]
        assert low <= middle <= peak
        raw_values.extend(raw_bin)
        points.append(dict(timestamp=start + index * 15, value=sum(raw_bin) / len(raw_bin), minimum=min(raw_bin), peak=max(raw_bin)))
    return dict(state="ready", metric="cpu_usage", label="CPU 使用率", unit="%", start=start,
                end=start + 600, points=points, latest=raw_values[-1], latest_time=start + 599.0625,
                mean=sum(raw_values) / len(raw_values), peak=max(raw_values), minimum=min(raw_values), count=len(raw_values), missing_count=16,
                coverage=.975, step_seconds=15)


SCENARIOS = [
    dict(id="focus", label="专注工作", description="一条轻盈状态栏，留下完整的工作空间。", icon="grid", accent="#246dcb",
         summary="顶部栏 · 4 项常用指标", preview=dict(kind="bar", metrics=[dict(label="CPU", icon="cpu"), dict(label="内存", icon="memory"), dict(label="电池", icon="battery")])),
    dict(id="performance", label="性能观察", description="温度、功耗与负载放在一起，变化一眼可见。", icon="cpu", accent="#8651b8",
         summary="2 个组件 · 负载与散热", preview=dict(kind="cards", metrics=[dict(label="CPU 使用率", icon="cpu"), dict(label="GPU 功率", icon="gpu"), dict(label="风扇转速", icon="fan")],
             tiles=[dict(label="处理器", icon="cpu", metrics=[dict(label="CPU 使用率", icon="cpu"), dict(label="温度", icon="temperature")]),
                    dict(label="显卡", icon="gpu", metrics=[dict(label="GPU 功率", icon="power"), dict(label="风扇转速", icon="fan")])])),
    dict(id="light", label="轻量桌面", description="只显示最关心的数字，小巧而清楚。", icon="sensors", accent="#187c67",
         summary="2 个组件 · 紧凑数字", preview=dict(kind="compact", metrics=[dict(label="CPU", icon="cpu"), dict(label="内存", icon="memory")]))
]


class HistoryController(QObject):
    changed = Signal()
    historyChanged = Signal()
    historyOptionsChanged = Signal()
    historyRecordingChanged = Signal()

    def __init__(self):
        super().__init__()
        self.mode = "light"
        self.locale = "zh-CN"
        self.recording = True
        self.reject_recording = False
        self.requests = []
        self.actions = []
        self.status_reads = 0
        self.response = synthetic_history()
        self.options = [
            dict(id="cpu:local", label="CPU 使用率", unit="%", device_id="local", scope="cpu", device_label="本机处理器", icon="cpu", available=True),
            dict(id="gpu:0", label="GPU 功率", unit="W", device_id="0", scope="gpus", device_label="Synthetic GPU A", icon="gpu", available=True),
            dict(id="gpu:1", label="GPU 功率", unit="W", device_id="1", scope="gpus", device_label="Synthetic GPU B", icon="gpu", available=False),
        ]
        self.status = dict(state="ready", detail="仅保存在本机 · 此图使用明确的合成样本", recording=True)

    theme = Property(str, lambda self: self.mode, notify=changed)
    language = Property(str, lambda self: self.locale, notify=changed)
    texts = Property("QVariantMap", lambda self: {}, notify=changed)
    material = Property("QVariantMap", lambda self: {}, constant=True)
    motionEnabled = Property(bool, lambda self: False, constant=True)
    historyMetricChoices = Property("QVariantList", lambda self: self.options, notify=historyOptionsChanged)
    @Property("QVariantMap", notify=historyChanged)
    def historyStatus(self):
        self.status_reads += 1
        return self.status
    historyRecording = Property(bool, lambda self: self.recording, notify=historyRecordingChanged)

    @Slot(str, str, result="QVariantMap")
    def historyQuery(self, identifier, period):
        self.requests.append((identifier, period))
        return copy.deepcopy(self.response)

    @Slot(bool)
    def setHistoryRecording(self, value):
        if self.reject_recording:
            self.actions.append(("record_rejected", value))
            return
        self.recording = value
        self.actions.append(("record", value))
        self.historyRecordingChanged.emit()

    @Slot()
    def clearHistory(self):
        self.actions.append(("clear",))
        self.response = dict(state="empty", start=1792663200.0, end=1792663800.0, points=[], count=0)
        self.historyChanged.emit()


class HistoryQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("History tests must not create a native window")
        for filename in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            font = Path("C:/Windows/Fonts") / filename
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        self.native = self.enterContext(patch.object(ctypes, "WinDLL", side_effect=AssertionError("No native DLL")))
        self.process = self.enterContext(patch.object(subprocess, "Popen", side_effect=AssertionError("No process")))
        self.controller = HistoryController()
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.controller)
        self.engine.rootContext().setContextProperty("testScenarios", SCENARIOS)
        self.warnings = []
        self.engine.warnings.connect(lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.window = self.component = None

    def tearDown(self):
        if self.window is not None:
            self.window.hide()
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def load(self, kind="history", width=760, height=720):
        self.component = QQmlComponent(self.engine)
        if kind == "history":
            child = 'Product.HistoryPage {id:page;objectName:"page";anchors.fill:parent;controller:stats}'
        elif kind == "scenarios":
            child = '''ScrollView {anchors.fill:parent;anchors.margins:24;contentWidth:availableWidth;contentHeight:picker.implicitHeight;clip:true;
                Product.ScenarioPicker {id:picker;objectName:"picker";width:parent.width-6;scenarios:testScenarios;selectedId:"focus";
                onPreviewRequested:identifier=>{scene.events=scene.events.concat(["preview:"+identifier]);selectedId=identifier}
                onApplyRequested:identifier=>scene.events=scene.events.concat(["apply:"+identifier])
                onSaveRequested:name=>scene.events=scene.events.concat(["save:"+name])}}'''
        else:
            child = 'Product.TrendChart {id:chart;objectName:"chart";anchors.fill:parent;anchors.margins:16;series:scene.chartSeries;rangeStart:100;rangeEnd:200;unit:"W"}'
        code = '''import QtQuick
import QtQuick.Controls
import "../../native" as Product
Window {id:scene;width:%d;height:%d;visible:false;color:stats.theme==="dark"?"#23272e":"#f6f8fb";
 property var events:[];property var chartSeries:[];
 %s
}''' % (width, height, child)
        self.component.setData(code.encode("utf-8"), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign33/history-fixture.qml")))
        self.window = self.component.create()
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.assertIsInstance(self.window, QQuickWindow)
        self.window.show()
        QTest.qWait(35)
        return self.find("page" if kind == "history" else "picker" if kind == "scenarios" else "chart")

    def find(self, name):
        result = self.window.findChild(QObject, name)
        if result is None:
            queue = [self.window.contentItem()]
            while queue:
                item = queue.pop()
                if item.objectName() == name:
                    return item
                queue.extend(item.childItems())
        self.assertIsNotNone(result, name)
        return result

    def click(self, name):
        item = self.find(name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        self.assertTrue(item.isVisible(), name)
        self.assertTrue(0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height(), (name, point))
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(10)

    def reveal(self, name):
        item = self.find(name)
        scroll = self.find("historyPageScroll")
        flick = scroll.property("contentItem")
        content_item = flick.property("contentItem")
        previous, stable = None, 0
        deadline = time.monotonic() + .5
        while stable < 2 and time.monotonic() < deadline:
            QTest.qWait(16)
            signature = (flick.property("contentHeight"), item.mapToItem(content_item, QPointF(0, item.height())).y(), item.width())
            stable = stable + 1 if signature == previous else 0
            previous = signature
        self.assertGreaterEqual(stable, 2)
        self.assertGreaterEqual(flick.property("contentHeight") + 1, previous[1])
        point = item.mapToScene(item.boundingRect().center())
        current = flick.property("contentY")
        flick.setProperty("contentY", max(0, min(flick.property("contentHeight") - flick.height(), current + point.y() - self.window.height() / 2)))
        QTest.qWait(15)

    def test_history_device_ids_never_substitute_another_gpu(self):
        page = self.load()
        self.assertEqual(self.controller.requests[-1], ("cpu:local", "10m"))
        page.choose("gpu:1")
        self.assertEqual(self.controller.requests[-1], ("gpu:1", "10m"))
        self.assertIn("Synthetic GPU B", self.find("historyDeviceLabel").property("text"))
        self.controller.options = [self.controller.options[0], self.controller.options[1]]
        self.controller.historyOptionsChanged.emit()
        QTest.qWait(10)
        self.assertEqual(page.property("selectedId"), "gpu:1")
        page.refresh()
        self.assertEqual(self.controller.requests[-1][0], "gpu:1")
        self.assertIn("Synthetic GPU B", self.find("historyDeviceLabel").property("text"))

    def test_query_cadence_ignores_sample_signal_burst_and_inactive_page(self):
        page = self.load()
        self.find("historyRefreshTimer").setProperty("interval", 120)
        before = len(self.controller.requests)
        for _ in range(80):
            self.controller.historyChanged.emit()
        QTest.qWait(25)
        self.assertEqual(len(self.controller.requests), before)
        QTest.qWait(140)
        self.assertGreater(len(self.controller.requests), before)
        page.setProperty("active", False)
        before = len(self.controller.requests)
        for _ in range(20):
            self.controller.historyChanged.emit()
        QTest.qWait(150)
        self.assertEqual(len(self.controller.requests), before)

    def test_inactive_hidden_and_minimized_history_do_not_read_store_status(self):
        page = self.load()
        self.assertTrue(page.property("uiActive"))
        self.assertGreater(self.controller.status_reads, 0)
        timer = self.find("historyRefreshTimer")

        def check_quiet():
            QTest.qWait(20)
            before = self.controller.status_reads
            self.controller.requests.clear()
            for _ in range(40):
                self.controller.historyChanged.emit()
            QTest.qWait(35)
            self.assertFalse(page.property("uiActive"))
            self.assertFalse(timer.property("running"))
            self.assertEqual(self.controller.status_reads, before)
            self.assertEqual(self.controller.requests, [])
            self.assertEqual(self.controller.actions, [])

        page.setProperty("active", False)
        check_quiet()
        page.setProperty("period", "1h")
        page.setProperty("active", True)
        QTest.qWait(35)
        self.assertTrue(page.property("uiActive"))
        self.assertEqual(self.controller.requests[-1], ("cpu:local", "1h"))
        self.window.hide()
        check_quiet()
        self.window.show()
        QTest.qWait(35)
        self.assertTrue(page.property("uiActive"))
        self.window.showMinimized()
        check_quiet()
        self.window.showNormal()
        QTest.qWait(35)
        self.assertTrue(page.property("uiActive"))
        self.assertTrue(timer.property("running"))
        self.assertEqual(self.controller.requests[-1], ("cpu:local", "1h"))

    def test_range_toggle_and_recording_use_only_their_explicit_actions(self):
        self.load()
        self.click("historyRange_1h")
        self.assertEqual(self.controller.requests[-1], ("cpu:local", "1h"))
        self.click("historyRecordingToggle")
        self.assertEqual(self.controller.actions, [("record", False)])
        self.assertFalse(self.controller.recording)

    def test_rejected_recording_change_restores_the_committed_switch(self):
        self.load()
        self.controller.reject_recording = True
        self.click("historyRecordingToggle")
        self.assertTrue(self.controller.recording)
        self.assertTrue(self.find("historyRecordingToggle").property("checked"))
        self.assertEqual(self.controller.actions, [("record_rejected", False)])

    def test_percentage_scale_stays_zero_to_one_hundred_across_new_queries(self):
        page = self.load()
        chart = self.find("historyTrendChart")
        self.assertEqual(chart.property("axis").toVariant(), {"low": 0, "high": 100})
        self.controller.response = dict(self.controller.response, points=[dict(timestamp=1792663200, value=2)], latest=2, peak=2, minimum=2, mean=2, count=1)
        page.refresh()
        self.assertEqual(chart.property("axis").toVariant(), {"low": 0, "high": 100})
        self.controller.response = dict(self.controller.response, unit="W", points=[dict(timestamp=1792663200, value=143)], latest=143, peak=143, minimum=143, mean=143)
        page.refresh()
        self.assertEqual(chart.property("axis").toVariant()["high"], 143)

    def test_latest_raw_time_is_distinct_from_last_aggregate_bucket(self):
        page = self.load()
        self.assertEqual(page.property("latestTime"), self.controller.response["latest_time"])
        self.assertNotEqual(page.property("latestTime"), self.controller.response["points"][-1]["timestamp"])
        self.assertEqual(self.find("historyLastSampleTime").property("text"), page.timeText(self.controller.response["latest_time"]))

    def test_clear_requires_separate_confirmation_and_cancel_preserves_data(self):
        self.load(height=600)
        self.reveal("historyClearButton")
        self.click("historyClearButton")
        self.assertEqual(self.controller.actions, [])
        self.reveal("historyCancelClear")
        self.click("historyCancelClear")
        self.assertEqual(self.controller.actions, [])
        self.reveal("historyClearButton")
        self.click("historyClearButton")
        self.reveal("historyConfirmClear")
        self.click("historyConfirmClear")
        self.assertEqual(self.controller.actions, [("clear",)])
        self.assertEqual(self.find("historyLatestValue").property("text"), "—")

    def test_zero_loading_missing_and_error_never_turn_missing_into_zero(self):
        page = self.load(width=400, height=740)
        for response, expected in ((dict(self.controller.response, latest=0), "0"),
                                   (dict(state="empty", points=[]), "—"),
                                   (dict(state="loading", points=[]), "—"),
                                   (dict(state="error", detail="Synthetic query failure", points=[]), "—")):
            self.controller.response = response
            page.refresh()
            QTest.qWait(10)
            self.assertEqual(self.find("historyLatestValue").property("text"), expected)
        self.assertEqual(self.find("historyTrendChart").property("errorText"), "Synthetic query failure")

    def test_actual_plot_does_not_connect_missing_samples(self):
        chart = self.load("chart", width=580, height=300)
        self.window.setProperty("chartSeries", [dict(id="a", label="Power", color="#e32855", unit="W", points=[
            dict(timestamp=100, value=0), dict(timestamp=120, value=100), None,
            dict(timestamp=180, value=0), dict(timestamp=200, value=100)])])
        QTest.qWait(60)
        QTest.mouseMove(self.window, QPoint(3, 3))
        QTest.qWait(10)
        image = self.window.grabWindow()
        self.assertFalse(image.isNull())
        scale = image.width() / self.window.width()
        def pixel(x, y):
            return image.pixelColor(round(x * scale), round(y * scale))
        plot = chart.property("plotRect")
        x_gap = int(chart.x() + plot.x() + plot.width() / 2)
        def colored(color):
            return color.red() > 140 and color.red() > color.green() * 1.6 and color.red() > color.blue() * 1.3
        self.assertFalse(any(colored(pixel(x_gap, int(chart.y() + y))) for y in range(int(plot.y()), int(plot.y() + plot.height()))))
        x_line = int(chart.x() + plot.x() + plot.width() * .9)
        self.assertTrue(any(colored(pixel(x_line, int(chart.y() + y))) for y in range(int(plot.y()), int(plot.y() + plot.height()))))
        background = pixel(2, 2)
        gap = pixel(int(chart.x() + plot.x() + plot.width() * .55), int(chart.y() + plot.y() + plot.height() * .35))
        self.assertLessEqual(max(abs(gap.red() - background.red()), abs(gap.green() - background.green()), abs(gap.blue() - background.blue())), 1)
        area = pixel(int(chart.x() + plot.x() + plot.width() * .1), int(chart.y() + plot.y() + plot.height() * .8))
        self.assertGreater(max(abs(area.red() - background.red()), abs(area.green() - background.green()), abs(area.blue() - background.blue())), 2)

    def test_mouse_and_keyboard_inspection_select_real_nonuniform_timestamps(self):
        chart = self.load("chart", width=440, height=280)
        self.window.setProperty("chartSeries", [dict(id="a", label="Power", unit="W", points=[
            dict(timestamp=100, value=2), dict(timestamp=117, value=7.5), None, dict(timestamp=200, value=1)])])
        QTest.qWait(30)
        plot = chart.property("plotRect")
        point = QPoint(int(chart.x() + plot.x() + .17 * plot.width()), int(chart.y() + plot.y() + plot.height() / 2))
        QTest.mouseMove(self.window, point)
        QTest.qWait(10)
        self.assertEqual(chart.property("hoverTimestamp"), 117)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.keyClick(self.window, Qt.Key_Right)
        self.assertEqual(chart.property("hoverTimestamp"), 200)
        QTest.keyClick(self.window, Qt.Key_Home)
        self.assertEqual(chart.property("hoverTimestamp"), 100)
        QTest.keyClick(self.window, Qt.Key_Escape)
        self.assertNotEqual(chart.property("hoverTimestamp"), chart.property("hoverTimestamp"))

    def test_stationary_pointer_notifications_preserve_keyboard_then_real_motion_resumes_hover(self):
        chart = self.load("chart", width=440, height=280)
        self.window.setProperty("chartSeries", [dict(id="a", unit="W", points=[
            dict(timestamp=100, value=2), dict(timestamp=117, value=7.5),
            dict(timestamp=200, value=1)])])
        self.window.requestActivate()
        QTest.qWait(30)
        plot = chart.property("plotRect")
        point = QPoint(int(chart.x()+plot.x()+.17*plot.width()),
                       int(chart.y()+plot.y()+plot.height()/2))
        QTest.mouseMove(self.window, point)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(10)
        self.assertTrue(self.window.isActive())
        self.assertTrue(chart.hasActiveFocus())
        self.assertEqual(chart.property("hoverTimestamp"), 117)
        QTest.keyClick(self.window, Qt.Key_Home)
        self.assertEqual(chart.property("hoverTimestamp"), 100)
        hover = self.find("trendPlotHover")
        self.assertTrue(QMetaObject.invokeMethod(hover, "pointChanged", Qt.DirectConnection))
        self.assertEqual(chart.property("hoverTimestamp"), 100)
        # Real movement still inspects the nearest actual sample, including gaps.
        target = QPoint(int(chart.x()+plot.x()+.95*plot.width()), point.y())
        QTest.mouseMove(self.window, target)
        QTest.qWait(10)
        self.assertEqual(chart.property("hoverTimestamp"), 200)
        QTest.keyClick(self.window, Qt.Key_Escape)
        self.assertTrue(QMetaObject.invokeMethod(hover, "pointChanged", Qt.DirectConnection))
        self.assertNotEqual(chart.property("hoverTimestamp"), chart.property("hoverTimestamp"))
        QTest.mouseMove(self.window, point)
        QTest.qWait(10)
        self.assertEqual(chart.property("hoverTimestamp"), 117)

    def test_different_units_cannot_claim_a_shared_scale(self):
        chart = self.load("chart")
        self.window.setProperty("chartSeries", [dict(id="a", unit="W", points=[dict(timestamp=100, value=20)]),
                                                dict(id="b", unit="%", points=[dict(timestamp=200, value=90)])])
        QTest.qWait(10)
        self.assertFalse(chart.property("compatibleUnits"))
        self.assertFalse(chart.property("hasData"))

    def test_hover_exposes_only_real_values_and_never_interpolates_missing_peer(self):
        chart = self.load("chart")
        self.window.setProperty("chartSeries", [
            dict(id="a", label="Download", unit="W", points=[dict(timestamp=100, value=2), dict(timestamp=117, value=7.5)]),
            dict(id="b", label="Upload", unit="W", points=[dict(timestamp=100, value=4), dict(timestamp=117, value=None)]),
        ])
        chart.setProperty("hoverTimestamp", 117)
        QTest.qWait(10)
        rows = chart.property("hoverRows").toVariant()
        self.assertEqual([row["value"] for row in rows], ["7.5", "—"])
        self.assertEqual(chart.property("sampleTimes").toVariant(), [100, 117])

    def test_query_bin_extrema_reach_plot_scale_hover_and_actual_range_pixels(self):
        self.controller.response = dict(state="ready", metric="gpu_power", label="GPU 功率", unit="W", start=100, end=200,
            points=[dict(timestamp=100, value=20, minimum=10, peak=80), dict(timestamp=150, value=20, minimum=10, peak=99),
                    dict(timestamp=200, value=20, minimum=10, peak=40)], latest=20, mean=20, minimum=10, peak=99, count=3)
        self.load()
        chart = self.find("historyTrendChart")
        self.assertTrue(chart.property("hasRanges"))
        self.assertEqual(chart.property("axis").toVariant()["high"], 99)
        self.assertTrue(self.find("historyAggregationNote").isVisible())
        QTest.mouseMove(self.window, QPoint(3, 3))
        QTest.qWait(35)
        image = self.window.grabWindow()
        scale = image.width() / self.window.width()
        plot = chart.property("plotRect")
        origin = chart.mapToScene(QPointF(plot.x() + plot.width() / 2, plot.y() + plot.height() * (1 - 90 / 99)))
        colors = [image.pixelColor(round((origin.x() + dx) * scale), round(origin.y() * scale)) for dx in (-1, 0, 1)]
        self.assertTrue(any(color.blue() > color.red() + 15 and color.blue() > color.green() + 8 for color in colors))
        chart.setProperty("hoverTimestamp", 150)
        rows = chart.property("hoverRows").toVariant()
        self.assertEqual(rows[0]["value"], "20")
        self.assertEqual(rows[0]["range"], "10 – 99 W")
        self.assertEqual(chart.property("sampleTimes").toVariant(), [100, 150, 200])

    def test_invalid_extrema_cannot_expand_scale_or_invent_samples(self):
        chart = self.load("chart")
        self.window.setProperty("chartSeries", [dict(id="a", unit="W", points=[
            dict(timestamp=100, value=20, minimum=30, peak=99), dict(timestamp=200, value=21, minimum=None, peak=1000)])])
        self.assertFalse(chart.property("hasRanges"))
        self.assertEqual(chart.property("axis").toVariant()["high"], 21)
        self.assertEqual(chart.property("sampleTimes").toVariant(), [100, 200])

    def test_scenario_preview_apply_and_save_are_distinct_explicit_events(self):
        picker = self.load("scenarios", width=850, height=1000)
        self.click("scenarioPreviewButton_performance")
        self.assertEqual(self.window.property("events").toVariant(), ["preview:performance"])
        self.assertEqual(picker.property("selectedId"), "performance")
        self.click("scenarioApplyButton_performance")
        self.assertEqual(self.window.property("events").toVariant(), ["preview:performance", "apply:performance"])
        name = self.find("scenarioNameInput")
        name.setProperty("text", "  My workspace  ")
        self.click("scenarioSaveButton")
        self.assertEqual(self.window.property("events").toVariant()[-1], "save:My workspace")

    def test_narrow_and_wide_content_stays_within_its_reading_surface(self):
        page = self.load(width=360, height=720)
        for width in (360, 760):
            self.window.setWidth(width)
            QTest.qWait(35)
            for name in ("historyMetricChoice", "historyTrendChart", "historySampleCount", "historyLatestUnit"):
                item = self.find(name)
                position = item.mapToScene(item.boundingRect().topLeft())
                self.assertGreaterEqual(position.x(), 0, name)
                self.assertLessEqual(position.x() + item.width(), width, name)
            chart = self.find("historyTrendChart")
            plot = chart.property("plotRect")
            self.assertGreaterEqual(plot.x(), 40)
            self.assertLessEqual(plot.x() + plot.width(), chart.width())
        self.assertEqual(page.property("period"), "10m")

    def test_scenario_busy_state_disables_actions_without_losing_selection(self):
        picker = self.load("scenarios", width=850, height=1000)
        picker.setProperty("busy", True)
        self.assertFalse(self.find("scenarioApplyButton_focus").property("enabled"))
        self.assertFalse(self.find("scenarioPreviewButton_performance").property("enabled"))
        self.assertEqual(picker.property("selectedId"), "focus")
        self.assertEqual(self.window.property("events").toVariant(), [])

    def test_scenario_thumbnail_uses_actual_widget_tiles_instead_of_metric_count(self):
        self.load("scenarios", width=850, height=1000)
        preview = self.find("scenarioPreview_performance")
        queue, tiles = [preview], []
        while queue:
            item = queue.pop()
            if item.objectName().startswith("scenarioTile_performance_"):
                tiles.append(item)
            queue.extend(item.childItems())
        self.assertEqual(len(tiles), 2)
        self.assertEqual(self.find("scenarioNameInput").property("maximumLength"), 20)


if __name__ == "__main__":
    unittest.main()
