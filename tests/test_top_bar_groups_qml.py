"""Native group controls and keyboard recovery, owned offscreen Qt only."""

import copy
import json
import math
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/redesign35/test-profile"),
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtTest import QTest

from tests import test_top_bar_runtime as bars
from tests import test_workspace_ui as fixture
from tests import test_workspace_ui_recovery as recovery


def variant(value):
    return value.toVariant() if hasattr(value, "toVariant") else value


class GroupQmlTests(unittest.TestCase):
    setUpClass = classmethod(fixture.IntegratedWorkspaceTests.setUpClass.__func__)
    setUp = fixture.IntegratedWorkspaceTests.setUp
    tearDown = fixture.IntegratedWorkspaceTests.tearDown
    item = fixture.IntegratedWorkspaceTests.item
    click = fixture.IntegratedWorkspaceTests.click
    resize = fixture.IntegratedWorkspaceTests.resize
    wheel = fixture.IntegratedWorkspaceTests.wheel
    inspect_first_sample = recovery.WorkspaceRecoveryTests.inspect_first_sample

    def evaluate(self, item, code):
        expression = QQmlExpression(qmlContext(item), item, code)
        value = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        return value[0] if isinstance(value, tuple) else value

    def rows(self):
        return self.ui.topBarDraftRows()

    def item_config(self, identifier="b_cpu_usage"):
        return next(item for item in self.ui._draft["top_bar"]["items"] if item["id"] == identifier)

    def open_group(self, identifier="b_cpu_usage"):
        self.click("nav_3")
        editor = self.item("topBarSettings")
        scroll = self.item("topBarSettingsScroll")
        target = self.item("topBarItem_" + identifier)
        for _ in range(12):
            local = target.mapToItem(scroll, target.boundingRect().center())
            if 12 <= local.y() <= scroll.height() - 12:
                break
            self.wheel(scroll, -120 if local.y() > scroll.height() - 12 else 120)
        scroll.property("contentItem").cancelFlick()
        QTest.qWait(35)
        self.click("topBarItem_" + identifier)
        self.assertEqual(editor.property("selectedItem"), identifier)
        self.click("topBarGroupButton")
        self.assertTrue(editor.property("groupPopupOpen"))

    def preset(self):
        self.click("topBarGroupPreset")
        self.assertEqual(
            self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_temp", "cpu_power"]
        )

    def close_group(self):
        self.click("topBarGroupClose")
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))

    def choose(self, name, index):
        self.click(name)
        QTest.keyClick(self.window, Qt.Key_Home)
        for _ in range(index):
            QTest.keyClick(self.window, Qt.Key_Down)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(40)

    def test_preset_and_primary_lock_use_one_real_draft_transaction(self):
        saved = copy.deepcopy(self.ui._saved)
        self.ui.change("refresh", 0.5)
        self.open_group()
        self.preset()
        for action in ("Up", "Down", "Remove"):
            self.assertFalse(self.item("topBarGroup" + action + "_cpu_usage").isVisible())
        self.assertFalse(self.item("topBarGroupUp_cpu_temp").isEnabled())
        self.assertEqual(self.ui._saved, saved)
        self.assertEqual(self.ui._draft["refresh"], 0.5)
        self.preset()  # A legal no-op must not display an error or add undo.
        self.assertFalse(self.item("topBarGroupError").isVisible())
        self.close_group()
        QTest.keyClick(self.window, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(35)
        self.assertNotIn("metrics", self.item_config()["prefs"])
        self.assertEqual(self.ui._draft["refresh"], 0.5)
        self.save.assert_not_called()

    def test_extra_members_reorder_delete_and_add_with_real_mouse_and_keys(self):
        self.open_group()
        self.preset()
        self.click("topBarGroupUp_cpu_power")
        self.assertEqual(
            self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_power", "cpu_temp"]
        )
        self.click("topBarGroupRemove_cpu_power")
        self.assertEqual(self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_temp"])
        self.choose("topBarGroupAdd", 0)
        self.assertEqual(
            self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_temp", "cpu_power"]
        )
        self.click("topBarGroupRemove_cpu_power")
        self.click("topBarGroupRemove_cpu_temp")
        self.assertNotIn("metrics", self.item_config()["prefs"])
        self.assertEqual(
            variant(self.item("topBarSelectedInspector").property("groupMetrics")), ["cpu_usage"]
        )

    def test_four_member_cap_and_escape_keep_the_settings_open(self):
        self.open_group()
        self.preset()
        self.choose("topBarGroupAdd", 0)
        self.assertEqual(len(self.item_config()["prefs"]["metrics"]), 4)
        self.assertFalse(self.item("topBarGroupAdd").isVisible())
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(50)
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertTrue(self.window.isVisible())
        self.assertEqual(len(self.item_config()["prefs"]["metrics"]), 4)

    def test_group_dialog_is_closed_when_its_page_is_hidden(self):
        self.open_group()
        self.preset()
        # A parent navigation action is permitted while an overlay owns focus.
        self.window.setProperty("page", 4)
        QTest.qWait(35)
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertTrue(self.window.isVisible())
        self.assertEqual(len(self.item_config()["prefs"]["metrics"]), 3)

    def test_selected_gpu_and_temperature_unit_are_shared_by_every_member(self):
        self.ui._devices["gpus"]["1"] = dict(label="Second synthetic GPU")
        self.ui._data["gpus"]["1"] = dict(
            label="Second synthetic GPU", gpu_usage=81, gpu_temp=71, gpu_power=96.5
        )
        self.ui.sensorsChanged.emit()
        self.open_group("b_gpu_usage")
        self.click("topBarGroupPreset")
        self.assertEqual(
            self.item_config("b_gpu_usage")["prefs"]["metrics"],
            ["gpu_usage", "gpu_temp", "gpu_power"],
        )
        self.close_group()
        self.choose("topBarDevice", 1)
        self.choose("topBarTemperatureUnit", 1)
        row = next(row for row in self.rows() if row["id"] == "b_gpu_usage")
        self.assertEqual(
            [member["metric"] for member in row["group_rows"]],
            ["gpu_usage", "gpu_temp", "gpu_power"],
        )
        self.assertEqual(
            [member["value"] for member in row["group_rows"]], ["81 %", "160 °F", "96.5 W"]
        )
        self.assertTrue(
            all("Second synthetic GPU" in member["hardware_name"] for member in row["group_rows"])
        )
        self.save.assert_not_called()

    def test_vram_primary_preset_stays_in_the_gpu_family(self):
        self.assertTrue(self.ui.addTopBarMetric("vram_gb"))
        identifier = self.ui._draft["top_bar"]["items"][-1]["id"]
        self.open_group(identifier)
        self.click("topBarGroupPreset")
        self.assertEqual(
            self.item_config(identifier)["prefs"]["metrics"],
            ["vram_gb", "gpu_usage", "gpu_temp", "gpu_power"],
        )

    def test_group_filters_inapplicable_styles_but_keeps_original_single_styles(self):
        self.open_group()
        self.preset()
        self.close_group()
        styles = variant(self.item("topBarSelectedInspector").property("displayStyles"))
        self.assertEqual(
            {row["id"] for row in styles},
            {"label_value", "value", "icon_value", "stacked", "trend_value", "graph"},
        )
        self.assertTrue(self.item("topBarTemperatureUnit").isVisible())
        self.open_group()
        self.click("topBarGroupRemove_cpu_power")
        self.click("topBarGroupRemove_cpu_temp")
        self.close_group()
        styles = variant(self.item("topBarSelectedInspector").property("displayStyles"))
        self.assertIn("bar_value", {row["id"] for row in styles})
        self.assertIn("ring_value", {row["id"] for row in styles})

    def test_wrapper_width_is_sum_of_nonrecursive_leaves_and_shrinks_on_remove(self):
        self.open_group()
        self.preset()
        self.close_group()
        wrapper = self.item("topBarCurrentStyleSample")
        leaves = [child for child in wrapper.childItems() if child.isVisible()]
        self.assertEqual(len(leaves), 1)
        members = [
            child
            for child in leaves[0].childItems()
            if child.objectName().startswith("topBarGroupMember_")
        ]
        self.assertEqual(len(members), 3)
        self.assertAlmostEqual(
            wrapper.implicitWidth(),
            sum(member.implicitWidth() for member in members) + 20,
            delta=0.01,
        )
        self.assertTrue(
            all(not variant(member.property("row")).get("group_rows") for member in members)
        )
        before = wrapper.implicitWidth()
        self.open_group()
        self.click("topBarGroupRemove_cpu_power")
        self.close_group()
        self.assertLess(self.item("topBarCurrentStyleSample").implicitWidth(), before)

    def test_narrow_group_controls_remain_inside_the_actual_popup(self):
        self.resize(740, 640)
        self.open_group()
        self.preset()
        self.choose("topBarGroupAdd", 0)
        for metric in self.item_config()["prefs"]["metrics"]:
            label = self.item("topBarGroupLabel_" + metric)
            point = label.mapToScene(QPointF())
            self.assertGreaterEqual(point.x(), 0)
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.x() + label.width(), self.window.width())
            self.assertLessEqual(point.y() + label.height(), self.window.height())
        self.click("topBarGroupRemove_" + self.item_config()["prefs"]["metrics"][-1])
        self.close_group()
        self.save.assert_not_called()

    def test_first_escape_clears_the_chart_cursor_before_the_second_hides_settings(self):
        self.click("nav_4")
        chart, _timestamp = self.inspect_first_sample()
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(30)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(math.isfinite(chart.property("hoverTimestamp")))
        self.assertFalse(self.item("trendHoverReadout").isVisible())
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(30)
        self.assertFalse(self.window.isVisible())

    def test_choice_keyboard_reveals_highlight_without_hijacking_wheel_position(self):
        self.ui._devices["gpus"] = {
            str(index): dict(label="Synthetic GPU " + str(index)) for index in range(8)
        }
        self.ui.historyOptionsChanged.emit()
        self.click("nav_4")
        choice = self.item("historyMetricChoice")
        self.click("historyMetricChoice")
        for _ in range(16):
            QTest.keyClick(self.window, Qt.Key_Down)
        QTest.qWait(35)
        state = json.loads(
            self.evaluate(
                choice,
                """JSON.stringify((()=>{const list=popup.contentItem,item=list.itemAtIndex(highlightedIndex);return {index:highlightedIndex,y:list.contentY,h:list.height,itemY:item.y,itemH:item.height}})())""",
            )
        )
        self.assertEqual(state["index"], 16)
        self.assertGreater(state["y"], 0)
        self.assertGreaterEqual(state["itemY"], state["y"] - 0.5)
        self.assertLessEqual(state["itemY"] + state["itemH"], state["y"] + state["h"] + 0.5)
        listing = self.evaluate(choice, "popup.contentItem")
        self.wheel(listing, 360)
        listing.cancelFlick()
        QTest.qWait(35)
        before = listing.property("contentY")
        self.assertLess(before, state["y"])
        self.ui.historyOptionsChanged.emit()
        QTest.qWait(35)
        self.assertAlmostEqual(listing.property("contentY"), before, delta=0.5)
        QTest.keyClick(self.window, Qt.Key_End)
        QTest.qWait(35)
        self.assertAlmostEqual(
            listing.property("contentY"),
            listing.property("contentHeight") - listing.height(),
            delta=0.5,
        )
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(35)
        self.assertEqual(
            self.item("historyPage").property("selectedId"), self.ui.historyMetricChoices[-1]["id"]
        )

    def test_actual_bar_group_drag_and_hover_use_one_parent_identity(self):
        self.ui.setTopBarGroupMetrics("b_cpu_usage", ["cpu_usage", "cpu_temp", "cpu_power"])
        config = copy.deepcopy(self.ui._draft)
        config["top_bar"]["enabled"] = True
        controller = bars.Controller()
        controller.rows = copy.deepcopy(self.rows())
        screen = bars.Screen("DISPLAY1", bars.PixelRect(0, 0, 1920, 1000))
        runtime = SimpleNamespace(
            app=bars.Application([screen]),
            controller=controller,
            headless=True,
            show_settings=lambda _key: None,
            engine=self.engine,
        )
        adapter = bars.QmlAdapter()
        manager = bars.TopBarManager(runtime, adapter=adapter)
        try:
            manager.apply(config)
            QTest.qWait(40)
            host = manager.hosts["DISPLAY1"]
            metric = bars.QmlTopBarTests.visual(host.window, "topBarMetric_b_cpu_usage")
            self.assertIsNotNone(metric)
            members = []
            pending = [metric]
            while pending:
                child = pending.pop()
                if child.objectName().startswith("topBarGroupMember_"):
                    members.append(child)
                pending.extend(child.childItems())
            self.assertEqual(len(members), 3)
            point = metric.mapToScene(QPointF(metric.width() / 2, metric.height() / 2)).toPoint()
            QTest.mouseMove(host.window, QPoint(-10, -10))
            QTest.mouseMove(host.window, point)
            deadline = time.monotonic() + 1.2
            while manager._panel is None and time.monotonic() < deadline:
                QTest.qWait(15)
            self.assertIsNotNone(manager._panel)
            self.assertEqual(host.state.detail["id"], "b_cpu_usage")
            panel = manager._panel["window"]
            for member in controller.rows[0]["group_rows"]:
                value = bars.QmlTopBarTests.visual(panel, "topBarGroupDetail_" + member["metric"])
                self.assertEqual(value.property("text"), member["value"])
            self.assertFalse(panel.findChild(bars.QObject, "topBarDetailValue").isVisible())
            manager.close_panel()
            with patch.object(manager, "move_metric", return_value=True) as move:
                QTest.mousePress(host.window, Qt.LeftButton, Qt.NoModifier, point)
                QTest.mouseMove(host.window, QPoint(point.x() - 80, point.y()), 30)
                QTest.mouseRelease(
                    host.window, Qt.LeftButton, Qt.NoModifier, QPoint(point.x() - 80, point.y())
                )
                QTest.qWait(35)
                self.assertEqual(move.call_count, 1)
                self.assertEqual(move.call_args.args[0], "b_cpu_usage")
        finally:
            manager.close()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
