"""Detail hierarchy and exact-sample interaction in owned offscreen QML only."""
# ruff: noqa: E402 - Fix the private data directory before application imports.

import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(ROOT / "qa-private/redesign38/details-test-profile")
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QUrl,
    Slot,
    qInstallMessageHandler,
)
from PySide6.QtGui import QWheelEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QTest

from tests import test_top_bar_module_qml as module
from tests import test_workspace_ui as font_fixture
from tests.test_top_bar_cpu_effects_qml import cpu_context
from top_bar_layout import present_metric
from top_bar_profiles import align_pair_trends


def variant(value):
    return value.toVariant() if hasattr(value, "toVariant") else value


def network_detail():
    times = [1_700_000_000 + offset for offset in (0, 1.2, 2.5, 4, 6, 8)]
    rows = []
    for metric, label, direction, values in (
        ("net_download", "下载", "download", [1, 2, None, 7, 3, 6.8]),
        ("net_upload", "上传", "upload", [0, 0.2, 0.1, 0.3, None, 1.2]),
    ):
        rows.append(
            present_metric(
                dict(
                    metric=metric,
                    label=label,
                    direction=direction,
                    value=f"{values[-1]:.1f} MB/s",
                    number_text=f"{values[-1]:.1f}",
                    unit_text="MB/s",
                    unit="MB/s",
                    available=True,
                    history=values,
                    history_times=times,
                ),
                {"style": "value"},
            )
        )
    rows = align_pair_trends(rows)
    return dict(
        rows[0],
        id="b_network",
        group_label="网络",
        family="network",
        paired_rows=rows,
        hardware_name="Synthetic Wi-Fi adapter",
        source="Synthetic network provider",
        history_samples=6,
        history_recordable=True,
    )


class DetailsState(module.ModuleState):
    def __init__(self):
        super().__init__()
        self.maximum = 520.0
        self.hidden_rows = []

    panelMaximumHeight = Property(
        float, lambda self: self.maximum, notify=module.ModuleState.changed
    )
    overflowRows = Property(
        "QVariantList", lambda self: self.hidden_rows, notify=module.ModuleState.changed
    )

    @Slot()
    def openHistory(self):
        self.actions.append("history")


class DetailsDesignTests(unittest.TestCase):
    maxDiff = None
    setUpClass = classmethod(font_fixture.IntegratedWorkspaceTests.setUpClass.__func__)

    def setUp(self):
        self.native = self.enterContext(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native API"))
        )
        self.process = self.enterContext(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        self.state = DetailsState()
        self.state.details = network_detail()
        self.messages = []
        self.previous = qInstallMessageHandler(
            lambda kind, context, text: self.messages.append(text)
        )
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.state)
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
        qInstallMessageHandler(self.previous)
        self.native.assert_not_called()
        self.process.assert_not_called()
        self.assertEqual(self.messages, [])

    def load(self, source=None):
        self.component = QQmlComponent(self.engine)
        if source is None:
            self.component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        else:
            self.component.setData(
                source, QUrl.fromLocalFile(str(ROOT / "native/DetailsBaseline.qml"))
            )
        self.window = self.component.createWithInitialProperties({"barState": self.state})
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()
        QTest.qWait(60)

    def find(self, name):
        direct = self.window.findChild(QObject, name)
        if direct is not None:
            return direct
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail(name)

    def publish(self):
        self.state.changed.emit()
        self.app.processEvents()
        QTest.qWait(20)

    def click(self, name):
        item = self.find(name)
        self.assertTrue(item.isVisible())
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(30)

    def chart_point(self, index):
        chart = self.find("topBarDetailTrend")
        slot = variant(self.window.property("chartSlots"))[index]
        return chart.mapToScene(
            QPointF(3 + slot["x"] * (chart.width() - 6), chart.height() / 2)
        ).toPoint()

    def test_cpu_trend_precedes_cores_and_headers_keep_discoverable_edges(self):
        self.state.details = present_metric(
            dict(
                id="b_cpu",
                metric="cpu_usage",
                label="CPU 使用率",
                family="cpu",
                value="42 %",
                number_text="42",
                unit_text="%",
                unit="%",
                available=True,
                history=[10, 65, None, 42],
                history_times=[1, 2, 3, 4],
                cpu_context=cpu_context(24),
                history_recordable=True,
            ),
            {"style": "value"},
        )
        self.load()
        trend = self.find("topBarDetailHistorySection")
        cores = self.find("topBarCpuContext")
        self.assertLess(trend.mapToScene(QPointF()).y(), cores.mapToScene(QPointF()).y())
        self.assertEqual(self.window.property("coreColumns"), 4)
        self.assertEqual(self.find("topBarCpuCoreGrid").property("count"), 24)
        for name in ("topBarDetailsHistory", "topBarDetailsEdit", "topBarDetailsClose"):
            button = self.find(name)
            self.assertEqual(button.height(), 28)
            background = button.property("background")
            self.assertTrue(background.isVisible())
            expression = QQmlExpression(qmlContext(background), background, "border.width")
            self.assertEqual(expression.evaluate()[0], 1)
            self.assertFalse(expression.hasError())

    def test_exact_hover_gap_and_keyboard_cursor_survive_layout_and_same_time_refresh(self):
        self.load()
        chart_area = self.find("topBarDetailChartArea")
        QTest.mouseMove(self.window, self.chart_point(2))
        QTest.qWait(30)
        self.assertEqual(self.window.property("chartCursorIndex"), 2)
        self.assertEqual(self.find("topBarDetailCursorValue_0").property("text"), "—")
        self.assertTrue(self.find("topBarDetailCursorReason").isVisible())
        chart_area.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Right)
        QTest.qWait(20)
        stamp = self.state.details["history_times"][3]
        self.assertAlmostEqual(self.window.property("chartCursorTime"), stamp)
        self.assertEqual(self.find("topBarDetailCursorValue_0").property("text"), "7.0 MB/s")
        self.window.resize(320, self.window.height())
        QTest.qWait(30)
        self.assertAlmostEqual(self.window.property("chartCursorTime"), stamp)
        for row in [self.state.details, *self.state.details["paired_rows"]]:
            for field in ("history", "trend", "history_times", "trend_points"):
                row[field] = row[field][1:]
        self.publish()
        self.assertAlmostEqual(self.window.property("chartCursorTime"), stamp)
        self.assertEqual(self.window.property("chartCursorIndex"), 2)
        QTest.keyClick(self.window, Qt.Key_Escape)
        self.assertEqual(self.window.property("chartCursorIndex"), -1)
        self.assertNotIn("close", self.state.actions)

    def test_cursor_clears_for_device_unit_unavailable_and_untraceable_sample_changes(self):
        self.load()
        area = self.find("topBarDetailChartArea")
        for change in (
            dict(hardware_name="Other synthetic adapter"),
            dict(unit="Mbps"),
            dict(available=False, paired_rows=[]),
        ):
            self.state.details = network_detail()
            self.publish()
            area.forceActiveFocus()
            QTest.keyClick(self.window, Qt.Key_End)
            self.assertGreaterEqual(self.window.property("chartCursorIndex"), 0)
            self.state.details.update(change)
            self.publish()
            self.assertEqual(self.window.property("chartCursorIndex"), -1)
        self.state.details = network_detail()
        for row in [self.state.details, *self.state.details["paired_rows"]]:
            row["history_times"] = []
        self.publish()
        QTest.keyClick(self.window, Qt.Key_Home)
        self.assertEqual(self.window.property("chartCursorIndex"), 0)
        self.state.details["paired_rows"][0]["trend"][0] = 9
        self.publish()
        self.assertEqual(self.window.property("chartCursorIndex"), -1)

    def test_pair_cursor_matches_each_actual_timestamp_and_nonzero_never_becomes_zero(self):
        up = self.state.details["paired_rows"][1]
        for field in ("history", "trend", "history_times", "trend_points"):
            up[field] = up[field][1:]
        up["trend"][-1] = 0.001
        self.load()
        self.find("topBarDetailChartArea").forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_End)
        self.assertEqual(self.find("topBarDetailCursorValue_1").property("text"), "0.001 MB/s")
        down = self.state.details["paired_rows"][0]
        down.update(available=False, trend=[], history=[], history_times=[], trend_points=[])
        self.publish()
        QTest.keyClick(self.window, Qt.Key_End)
        self.assertGreaterEqual(self.window.property("chartCursorIndex"), 0)
        self.assertEqual(self.find("topBarDetailCursorValue_0").property("text"), "—")
        self.assertEqual(self.find("topBarDetailCursorValue_1").property("text"), "0.001 MB/s")

    def test_three_member_primary_spans_a_row_and_four_members_remain_balanced(self):
        self.state.details = dict(
            self.state.details,
            grouped=True,
            paired_rows=[],
            group_rows=[
                dict(metric=metric, label=label, icon=icon, value=value, available=True)
                for metric, label, icon, value in (
                    ("cpu_usage", "使用率", "cpu", "34 %"),
                    ("cpu_temp", "温度", "temperature", "67 °C"),
                    ("cpu_power", "功耗", "power", "21.8 W"),
                )
            ],
        )
        self.load()
        self.window.resize(320, self.window.height())
        QTest.qWait(30)
        primary, temperature, power = [
            self.find("topBarGroupDetail_" + metric)
            for metric in ("cpu_usage", "cpu_temp", "cpu_power")
        ]
        self.assertGreater(primary.width(), temperature.width() * 1.8)
        self.assertAlmostEqual(
            temperature.mapToScene(QPointF()).y(), power.mapToScene(QPointF()).y(), delta=1
        )
        for value in (primary, temperature, power):
            self.assertFalse(value.property("truncated"))
        self.state.details["group_rows"].append(
            dict(
                metric="cpu_frequency",
                label="频率",
                icon="frequency",
                value="3.8 GHz",
                available=True,
            )
        )
        self.publish()
        primary, temperature = [
            self.find("topBarGroupDetail_" + metric) for metric in ("cpu_usage", "cpu_temp")
        ]
        self.assertAlmostEqual(primary.width(), temperature.width(), delta=1)
        self.assertFalse(self.find("topBarGroupDetail_cpu_frequency").property("truncated"))

    def test_short_panel_keeps_source_and_missing_reasons_reachable_with_real_wheel(self):
        self.state.maximum = 280
        self.state.details.update(
            source="Synthetic provider / API 5",
            related=[
                dict(
                    metric="gpu_temp",
                    label="温度",
                    value="—",
                    available=False,
                    reason="Synthetic API access denied",
                ),
                *[
                    dict(label="Reading " + str(index), value=str(index) + " W", available=True)
                    for index in range(8)
                ],
            ],
        )
        self.load()
        scroll = self.find("topBarDetailScroll")
        point = scroll.mapToScene(scroll.boundingRect().center())
        event = QWheelEvent(
            point,
            point,
            QPoint(),
            QPoint(0, -360),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        self.app.sendEvent(self.window, event)
        QTest.qWait(40)
        self.assertGreater(scroll.property("contentY"), 0)
        scroll.cancelFlick()
        scroll.setProperty("contentY", scroll.property("contentHeight") - scroll.height())
        QTest.qWait(20)
        self.click("topBarDetailMetadataToggle")
        self.assertTrue(self.window.property("showMetadata"))
        scroll.setProperty("contentY", scroll.property("contentHeight") - scroll.height())
        QTest.qWait(20)
        source = self.find("topBarDetailSource")
        self.assertEqual(source.property("text"), "Synthetic provider / API 5")
        self.assertLessEqual(
            source.mapToScene(QPointF(0, source.height())).y(), self.window.height() - 15
        )
        self.assertEqual(
            self.find("topBarMissingReason_0").property("text"), "Synthetic API access denied"
        )

    def test_existing_header_actions_and_native_corner_contract_remain(self):
        self.load()
        self.click("topBarDetailsHistory")
        self.click("topBarDetailsEdit")
        self.click("topBarDetailsClose")
        self.assertEqual(self.state.actions, ["history", "edit", "close"])
        self.window.setProperty("nativeRounded", True)
        self.assertEqual(self.find("topBarDetailsMaterialSurface").property("cornerRadius"), 0)
        self.window.setProperty("nativeRounded", False)
        self.assertEqual(self.find("topBarDetailsMaterialSurface").property("cornerRadius"), 16)


if __name__ == "__main__":
    unittest.main()
