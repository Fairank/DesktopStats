"""Exceptional workspace interactions, real offscreen Qt events and fake IO."""

import copy
import math
import sqlite3
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtTest import QTest

from history_store import HistoryStore
from tests import test_workspace_ui as fixture


class WorkspaceRecoveryTests(unittest.TestCase):
    setUpClass = classmethod(fixture.IntegratedWorkspaceTests.setUpClass.__func__)
    setUp = fixture.IntegratedWorkspaceTests.setUp
    tearDown = fixture.IntegratedWorkspaceTests.tearDown
    item = fixture.IntegratedWorkspaceTests.item
    click = fixture.IntegratedWorkspaceTests.click
    resize = fixture.IntegratedWorkspaceTests.resize
    wheel = fixture.IntegratedWorkspaceTests.wheel
    settle_scroll = fixture.IntegratedWorkspaceTests.settle_scroll

    def inspect_first_sample(self):
        chart = self.item("historyTrendChart")
        rect = chart.property("plotRect")
        point = chart.mapToScene(QPoint(round(rect.x() + rect.width() / 3),
                                       round(rect.y() + rect.height() / 2))).toPoint()
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.mouseMove(self.window, QPoint(4, 4))
        QTest.qWait(25)
        QTest.keyClick(self.window, Qt.Key_Home)
        inspected = chart.property("hoverTimestamp")
        self.assertTrue(math.isfinite(inspected))
        self.assertTrue(self.item("trendHoverReadout").isVisible())
        return chart, inspected

    def poll_history(self):
        timer = self.window.findChild(QObject, "historyRefreshTimer")
        self.assertIsNotNone(timer)
        timer.setProperty("interval", 75)
        before = self.history.query.call_count
        deadline = time.monotonic() + 1
        while self.history.query.call_count == before and time.monotonic() < deadline:
            QTest.qWait(15)
        self.assertGreater(self.history.query.call_count, before)
        timer.setProperty("interval", 2000)

    def replace_history_response(self, change):
        response = copy.deepcopy(self.history.query.side_effect("cpu_usage", "10m"))
        change(response)
        self.history.query.side_effect = None
        self.history.query.return_value = response

    def select_history_device(self, identifier):
        choices = self.ui.historyMetricChoices
        index = next(index for index, row in enumerate(choices) if row["id"] == identifier)
        self.click("historyMetricChoice")
        QTest.keyClick(self.window, Qt.Key_Home)
        for _ in range(index):
            QTest.keyClick(self.window, Qt.Key_Down)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(35)
        self.assertEqual(self.item("historyPage").property("selectedId"), identifier)

    def test_history_clear_confirmation_does_not_survive_leaving_its_page(self):
        self.resize(740, 960)
        self.click("nav_4")
        self.click("historyClearButton")
        self.assertTrue(self.item("historyPage").property("clearArmed"))
        self.click("nav_1")
        self.assertFalse(self.item("historyPage").property("active"))
        self.click("nav_4")
        self.assertTrue(self.item("historyPage").property("active"))
        self.assertFalse(self.item("historyPage").property("clearArmed"))
        self.history.clear.assert_not_called()
        self.save.assert_not_called()

    def test_background_history_refresh_keeps_the_inspected_real_sample(self):
        self.click("nav_4")
        chart, inspected = self.inspect_first_sample()
        self.poll_history()
        self.assertEqual(chart.property("hoverTimestamp"), inspected)
        self.assertTrue(self.item("trendHoverReadout").isVisible())
        self.save.assert_not_called()

    def test_real_store_rolling_queries_keep_a_real_interior_bucket_and_cursor(self):
        base = 1_700_000_040
        wall, monotonic = [float(base)], [0.0]
        store = HistoryStore(Path(self.folder) / "synthetic-history.sqlite3", metrics=("cpu_usage",),
                             scopes=(), wall_clock=lambda: wall[0], clock=lambda: monotonic[0])
        self.addCleanup(store.close)
        for offset, value in ((1, 10), (2, 20), (4, 40), (7, 70)):
            wall[0], monotonic[0] = base + offset, float(offset)
            self.assertTrue(store.record(dict(time=wall[0], cpu_usage=value)))
        wall[0], monotonic[0] = base + 10, 10.0
        first = store.query("cpu_usage", "10m")
        self.assertEqual(first["resolution"], 3)
        self.ui._history_backend = store
        self.history = store
        self.enterContext(patch.object(store, "query", wraps=store.query))
        self.click("nav_4")
        chart, timestamp = self.inspect_first_sample()
        self.assertIn(timestamp, [point["time"] for point in first["points"] if not point["gap"]])
        old_value = next(point["mean"] for point in first["points"] if point["time"] == timestamp)
        wall[0], monotonic[0] = base + 12, 12.0
        self.poll_history()
        second = store.query("cpu_usage", "10m")
        self.assertEqual(second["end"] - first["end"], 2)
        self.assertEqual(second["resolution"], 3)
        self.assertEqual(second["summary"]["count"], 4)
        self.assertEqual(second["summary"]["mean"], 35)
        self.assertEqual(second["summary"]["peak"], 70)
        self.assertEqual(next(point["mean"] for point in second["points"] if point["time"] == timestamp), old_value)
        self.assertEqual(chart.property("hoverTimestamp"), timestamp)
        rows = chart.property("hoverRows").toVariant()
        self.assertEqual(float(rows[0]["value"]), old_value)
        self.assertEqual(self.item("historyLatestValue").property("text"), "70")
        self.assertTrue(self.item("trendHoverReadout").isVisible())
        self.save.assert_not_called()

    def test_history_clear_confirmation_does_not_survive_hidden_settings(self):
        self.resize(740, 960)
        self.click("nav_4")
        self.click("historyClearButton")
        self.assertTrue(self.item("historyPage").property("clearArmed"))
        self.window.hide()
        QTest.qWait(30)
        self.assertFalse(self.item("historyPage").property("active"))
        self.window.show()
        QTest.qWait(30)
        self.assertFalse(self.item("historyPage").property("clearArmed"))
        self.history.clear.assert_not_called()
        self.save.assert_not_called()

    def test_equal_timestamps_in_a_different_gpu_never_reuse_the_cursor(self):
        self.ui._devices["gpus"]["1"] = dict(label="Synthetic GPU B")
        self.ui.historyOptionsChanged.emit()
        self.click("nav_4")
        ids = {row["device_id"]: row["id"] for row in self.ui.historyMetricChoices
               if row["scope"] == "gpus" and self.ui._history_choices[row["id"]][0] == "gpu_usage"}
        self.select_history_device(ids["0"])
        chart, timestamp = self.inspect_first_sample()
        self.select_history_device(ids["1"])
        result = self.item("historyPage").property("result")
        result = result.toVariant() if hasattr(result, "toVariant") else result
        self.assertTrue(any(point and point["timestamp"] == timestamp
                            for point in result["points"]))
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))
        self.assertFalse(self.item("trendHoverReadout").isVisible())
        self.assertIn("Synthetic GPU B", self.item("historyDeviceLabel").property("text"))

    def test_same_series_with_changed_unit_clears_the_cursor(self):
        self.click("nav_4")
        chart, _ = self.inspect_first_sample()
        self.replace_history_response(lambda response: response.update(unit="W"))
        self.poll_history()
        self.assertEqual(chart.property("unit"), "W")
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))

    def test_missing_inspected_sample_clears_instead_of_snapping_to_a_peer(self):
        self.click("nav_4")
        chart, _ = self.inspect_first_sample()
        self.replace_history_response(lambda response: response["points"][0].update(gap=True))
        self.poll_history()
        self.assertTrue(chart.property("hasData"))
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))
        self.assertFalse(self.item("trendHoverReadout").isVisible())

    def test_removing_one_sample_clears_the_cursor_while_other_data_remains(self):
        self.click("nav_4")
        chart, timestamp = self.inspect_first_sample()
        self.replace_history_response(lambda response: response["points"].pop(0))
        self.poll_history()
        self.assertTrue(chart.property("hasData"))
        times = chart.property("sampleTimes").toVariant()
        self.assertNotIn(timestamp, times)
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))

    def test_kept_cursor_reads_the_new_value_instead_of_a_stale_snapshot(self):
        self.click("nav_4")
        chart, timestamp = self.inspect_first_sample()
        rows = chart.property("hoverRows").toVariant()
        previous = float(rows[0]["value"])

        def update(response):
            for point in response["points"]:
                if not point["gap"]:
                    for field in ("mean", "minimum", "peak"):
                        point[field] += 3
            for field in ("latest", "mean", "minimum", "peak"):
                response["summary"][field] += 3

        self.replace_history_response(update)
        self.poll_history()
        self.assertEqual(chart.property("hoverTimestamp"), timestamp)
        rows = chart.property("hoverRows").toVariant()
        self.assertEqual(float(rows[0]["value"]), previous + 3)

    def test_range_excluding_inspected_sample_clears_the_cursor(self):
        self.click("nav_4")
        chart, timestamp = self.inspect_first_sample()
        self.replace_history_response(lambda response: response.update(start=timestamp + 30))
        self.click("historyRange_1h")
        self.assertEqual(chart.property("rangeStart"), timestamp + 30)
        self.assertTrue(chart.property("hasData"))
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))

    def test_clear_failure_keeps_real_data_and_exposes_the_error(self):
        self.resize(740, 1180)
        self.click("nav_4")
        previous = self.item("historyLatestValue").property("text")
        self.history.clear.return_value = False
        self.click("historyClearButton")
        self.click("historyConfirmClear")
        self.history.clear.assert_called_once_with()
        self.assertEqual(self.item("historyLatestValue").property("text"), previous)
        self.assertIn("未能清空", self.item("saveStateText").property("text"))
        self.save.assert_not_called()

    def test_real_sqlite_clear_failure_keeps_the_curve_and_reports_failed_clear(self):
        base, wall = 1_700_000_040, [1_700_000_040.0]
        store = HistoryStore(Path(self.folder) / "synthetic-clear-failure.sqlite3", metrics=("cpu_usage",),
                             scopes=(), wall_clock=lambda: wall[0], clock=lambda: wall[0]-base)
        self.addCleanup(store.close)
        for offset, value in ((1, 10), (2, 20), (4, 40), (7, 70)):
            wall[0] = base + offset
            self.assertTrue(store.record(dict(time=wall[0], cpu_usage=value)))
        # A real local SQLite transaction rejects DELETE. Queries remain usable;
        # no provider status, QML result or clear return value is substituted.
        with closing(sqlite3.connect(store.path)) as connection:
            connection.execute("""CREATE TRIGGER synthetic_refuse_clear BEFORE DELETE ON sensor_history
                BEGIN SELECT RAISE(ABORT, 'synthetic clear denied'); END""")
            connection.commit()
        wall[0] = base + 10
        self.ui._history_backend = store
        self.resize(740, 1180)
        self.click("nav_4")
        chart = self.item("historyTrendChart")
        self.assertEqual(self.item("historyLatestValue").property("text"), "70")
        self.assertTrue(chart.property("hasData"))
        self.click("historyClearButton")
        self.click("historyConfirmClear")
        self.assertEqual(store.status["state"], "unavailable")
        self.assertEqual(store.status["api"], "sqlite3.history.clear")
        self.assertEqual(self.item("historyLatestValue").property("text"), "70")
        self.assertTrue(chart.property("hasData"))
        self.assertTrue(self.item("trendPlot").isVisible())
        result = self.item("historyPage").property("result")
        result = result.toVariant() if hasattr(result, "toVariant") else result
        self.assertEqual(result["count"], 4)
        self.assertIn("未能清空", self.item("saveStateText").property("text"))
        self.assertEqual(store.query("cpu_usage", "10m")["summary"]["count"], 4)
        self.save.assert_not_called()

    def test_cleared_history_cannot_keep_a_cursor_from_deleted_data(self):
        self.resize(740, 1180)
        self.click("nav_4")
        chart, _ = self.inspect_first_sample()

        def clear():
            self.replace_history_response(lambda response: response.update(
                points=[], summary=dict(latest=None, mean=None, minimum=None, peak=None,
                                        count=0, missing_count=0)))
            return True

        self.history.clear.side_effect = clear
        self.click("historyClearButton")
        self.click("historyConfirmClear")
        self.assertEqual(self.item("historyLatestValue").property("text"), "—")
        self.assertFalse(chart.property("hasData"))
        self.assertTrue(math.isnan(chart.property("hoverTimestamp")))
        self.assertFalse(self.item("trendHoverReadout").isVisible())
        self.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
