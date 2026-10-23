"""Discoverable actions and transactional group edits using owned offscreen Qt."""

import copy
import math
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign36/profile")
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlComponent
from PySide6.QtTest import QTest

from tests import test_top_bar_groups_qml as groups

ROOT = Path(__file__).resolve().parents[1]


class TopBarActionUiTests(unittest.TestCase):
    setUpClass = classmethod(groups.GroupQmlTests.setUpClass.__func__)
    setUp = groups.GroupQmlTests.setUp
    tearDown = groups.GroupQmlTests.tearDown
    item = groups.GroupQmlTests.item
    click = groups.GroupQmlTests.click
    resize = groups.GroupQmlTests.resize
    wheel = groups.GroupQmlTests.wheel
    evaluate = groups.GroupQmlTests.evaluate
    item_config = groups.GroupQmlTests.item_config
    open_group = groups.GroupQmlTests.open_group
    staged = groups.GroupQmlTests.staged
    preset = groups.GroupQmlTests.preset
    choose = groups.GroupQmlTests.choose

    def test_confirm_commits_once_and_apply_keeps_other_scope_pending(self):
        self.ui.change("refresh", 0.5)
        before = copy.deepcopy(self.ui._draft)
        self.open_group()
        with patch.object(self.ui, "edit", wraps=self.ui.edit) as edit:
            self.preset()
            self.click("topBarGroupUp_cpu_power")
            self.assertEqual(edit.call_count, 0)
            self.assertEqual(self.ui._draft, before)
            self.click("topBarGroupConfirm")
            self.assertEqual(edit.call_count, 1)
        self.assertEqual(
            self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_power", "cpu_temp"]
        )
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertNotIn("metrics", self.ui._saved["top_bar"]["items"][0]["prefs"])
        self.click("applyButton")
        self.assertEqual(self.ui._saved["top_bar"], self.ui._draft["top_bar"])
        self.assertEqual(self.ui._draft["refresh"], 0.5)
        self.assertNotEqual(self.ui._saved["refresh"], 0.5)
        self.assertEqual(self.save.call_count, 1)

    def test_cancel_button_discards_every_local_edit(self):
        before = copy.deepcopy(self.ui._draft)
        self.open_group()
        with patch.object(self.ui, "edit", wraps=self.ui.edit) as edit:
            self.preset()
            self.click("topBarGroupRemove_cpu_temp")
            self.click("topBarGroupCancel")
            self.assertEqual(edit.call_count, 0)
        self.assertEqual(self.ui._draft, before)
        self.open_group()
        self.assertEqual(self.staged(), ["cpu_usage"])
        self.click("topBarGroupCancel")

    def test_escape_and_outside_close_discard_without_activating_underlying_controls(self):
        for outside in (False, True):
            with self.subTest(outside=outside):
                before = copy.deepcopy(self.ui._draft)
                self.open_group()
                self.preset()
                with patch.object(self.ui, "edit", wraps=self.ui.edit) as edit:
                    if outside:
                        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, QPoint(20, 150))
                    else:
                        QTest.keyClick(self.window, Qt.Key_Escape)
                    QTest.qWait(40)
                    self.assertEqual(edit.call_count, 0)
                self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
                self.assertEqual(self.window.property("page"), 3)
                self.assertTrue(self.window.isVisible())
                self.assertEqual(self.ui._draft, before)

    def test_hidden_window_discards_local_edits_before_reopening(self):
        before = copy.deepcopy(self.ui._draft)
        self.open_group()
        self.preset()
        self.window.hide()
        QTest.qWait(40)
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertFalse(self.item("topBarSettings").property("pendingGroupEdits"))
        self.assertEqual(self.ui._draft, before)
        self.window.show()
        QTest.qWait(40)
        self.open_group()
        self.assertEqual(self.staged(), ["cpu_usage"])
        self.click("topBarGroupCancel")

    def test_switching_item_discards_old_member_buffer(self):
        before = copy.deepcopy(self.ui._draft)
        self.open_group()
        self.preset()
        editor = self.item("topBarSettings")
        editor.setProperty("selectedItem", "b_gpu_usage")
        QTest.qWait(40)
        self.assertFalse(editor.property("groupPopupOpen"))
        self.assertEqual(self.ui._draft, before)
        self.click("topBarGroupButton")
        self.assertEqual(self.staged(), ["gpu_usage"])
        self.click("topBarGroupCancel")

    def test_failed_confirmation_retains_input_and_retry_is_atomic(self):
        before = copy.deepcopy(self.ui._draft)
        self.open_group()
        self.preset()
        with patch.object(self.ui, "edit", return_value=False) as edit:
            self.click("topBarGroupConfirm")
            self.assertEqual(edit.call_count, 1)
        self.assertTrue(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertEqual(self.staged(), ["cpu_usage", "cpu_temp", "cpu_power"])
        self.assertTrue(self.item("topBarGroupError").isVisible())
        self.assertEqual(self.ui._draft, before)
        with patch.object(self.ui, "edit", wraps=self.ui.edit) as edit:
            self.click("topBarGroupConfirm")
            self.assertEqual(edit.call_count, 1)
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertEqual(
            self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_temp", "cpu_power"]
        )

    def test_external_same_item_change_is_not_silently_overwritten(self):
        self.open_group()
        self.preset()
        self.ui.setTopBarGroupMetrics("b_cpu_usage", ["cpu_usage", "cpu_frequency"])
        QTest.qWait(30)
        self.assertEqual(self.staged(), ["cpu_usage", "cpu_temp", "cpu_power"])
        with patch.object(self.ui, "edit", wraps=self.ui.edit) as edit:
            self.click("topBarGroupConfirm")
            self.assertEqual(edit.call_count, 0)
        self.assertTrue(self.item("topBarGroupError").isVisible())
        self.assertTrue(self.item("topBarSettings").property("groupPopupOpen"))
        self.assertEqual(self.item_config()["prefs"]["metrics"], ["cpu_usage", "cpu_frequency"])
        self.click("topBarGroupCancel")
        self.open_group()
        self.assertEqual(self.staged(), ["cpu_usage", "cpu_frequency"])
        self.click("topBarGroupCancel")

    def test_pending_group_edits_are_visible_to_the_settings_safety_contract(self):
        self.assertFalse(self.ui.dirty)
        self.open_group()
        self.assertFalse(self.item("topBarSettings").property("pendingGroupEdits"))
        self.preset()
        self.assertFalse(self.ui.dirty)
        self.assertTrue(self.item("topBarSettings").property("pendingGroupEdits"))
        self.assertTrue(self.window.property("pendingEdits"))
        self.click("topBarGroupCancel")
        self.assertFalse(self.window.property("pendingEdits"))

    def test_each_row_has_bounded_adjust_and_delete_and_can_undo_removal(self):
        self.resize(740, 700)
        self.click("nav_3")
        for identifier in ("b_cpu_usage", "b_gpu_usage"):
            card = self.item("topBarItem_" + identifier)
            for action in ("Adjust", "Delete"):
                button = self.item("topBarItem" + action + "_" + identifier)
                self.assertTrue(button.isVisible())
                self.assertTrue(button.property("outlined"))
                left = button.mapToItem(card, QPointF())
                self.assertGreaterEqual(left.x(), 0)
                self.assertLessEqual(left.x() + button.width(), card.width() + 0.1)
                self.assertLessEqual(left.y() + button.height(), card.height() + 0.1)
        self.click("topBarItemAdjust_b_gpu_usage")
        self.assertEqual(self.item("topBarSettings").property("selectedItem"), "b_gpu_usage")
        # Scroll back to the row after the narrow inspector reveal.
        scroll = self.item("topBarSettingsScroll")
        for _ in range(10):
            target = self.item("topBarItemDelete_b_gpu_usage")
            if 0 < target.mapToItem(scroll, target.boundingRect().center()).y() < scroll.height():
                break
            self.wheel(scroll, 240)
        scroll.property("contentItem").cancelFlick()
        QTest.qWait(30)
        self.click("topBarItemDelete_b_gpu_usage")
        self.assertFalse(
            any(row["id"] == "b_gpu_usage" for row in self.ui._draft["top_bar"]["items"])
        )
        QTest.keyClick(self.window, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(40)
        self.assertTrue(
            any(row["id"] == "b_gpu_usage" for row in self.ui._draft["top_bar"]["items"])
        )
        self.save.assert_not_called()

    def test_narrow_confirmation_footer_is_visible_and_keyboard_operable(self):
        self.resize(740, 600)
        self.open_group()
        self.preset()
        self.choose("topBarGroupAdd", 0)
        for name in ("topBarGroupCancel", "topBarGroupConfirm"):
            button = self.item(name)
            point = button.mapToScene(QPointF())
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y() + button.height(), self.window.height())
        confirm = self.item("topBarGroupConfirm")
        confirm.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.qWait(40)
        self.assertEqual(len(self.item_config()["prefs"]["metrics"]), 4)
        self.assertFalse(self.item("topBarSettings").property("groupPopupOpen"))

    def test_quiet_button_has_a_real_edge_and_distinct_hover_disabled_and_focus(self):
        component = QQmlComponent(self.engine)
        component.setData(
            b"""import QtQuick
import QtQuick.Controls
import "../../native" as Product
Window {width:360;height:180;color:"white"
Product.ActionButton {id:quiet;objectName:"quietSample";x:30;y:30;width:180;text:"Secondary";quiet:true}
Product.ActionButton {objectName:"disabledSample";x:30;y:90;width:180;text:"Secondary";quiet:true;enabled:false}}
""",
            QUrl.fromLocalFile(str(ROOT / "qa-private/redesign36/button-proof.qml")),
        )
        self.assertFalse(component.isError(), [error.toString() for error in component.errors()])
        window = component.create()
        self.assertIsNotNone(window)
        try:
            window.show()
            QTest.qWait(60)
            quiet = window.findChild(groups.bars.QObject, "quietSample")
            disabled = window.findChild(groups.bars.QObject, "disabledSample")
            dpr = window.devicePixelRatio()

            def color(image, x, y):
                return image.pixelColor(round(x * dpr), round(y * dpr))

            QTest.mouseMove(window, QPoint(340, 160))
            QTest.qWait(20)
            image = window.grabWindow()
            self.assertEqual(image.width(), round(window.width() * dpr))
            self.assertEqual(image.height(), round(window.height() * dpr))
            # Fractional-DPR rasterization snaps the 1-DIP edge inside its
            # first two logical pixels; the outermost physical pixel may be
            # uncovered. Inspect that bounded edge strip, not one boundary.
            edge = [
                image.pixelColor(x, round(47 * dpr)).rgba()
                for x in range(math.floor(30 * dpr), math.ceil(32 * dpr))
            ]
            self.assertTrue(any(pixel != color(image, 25, 47).rgba() for pixel in edge))
            quiet_idle = color(image, 42, 47)
            disabled_idle = color(image, 42, 107)
            QTest.mouseMove(window, QPoint(42, 47))
            QTest.qWait(30)
            image = window.grabWindow()
            self.assertNotEqual(color(image, 42, 47).rgba(), quiet_idle.rgba())
            self.assertNotEqual(color(image, 42, 47).rgba(), disabled_idle.rgba())
            self.assertFalse(disabled.isEnabled())
            quiet.forceActiveFocus()
            QTest.qWait(25)
            self.assertTrue(quiet.hasActiveFocus())
            self.assertTrue(quiet.property("background").isVisible())
        finally:
            window.hide()
            window.destroy()
            window.deleteLater()
            component.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_icon_effect_choice_defaults_off_and_retains_pending_preference_scope(self):
        self.ui.change("refresh", 0.5)
        self.click("nav_3")
        self.assertEqual(self.item("topBarSelectedInspector").property("selectedEffect"), "off")
        self.choose("topBarIconEffect", 1)
        self.assertEqual(self.item_config()["prefs"]["icon_effect"], "auto")
        self.assertNotIn("icon_effect", self.ui._saved["top_bar"]["items"][0]["prefs"])
        self.assertEqual(self.ui._draft["refresh"], 0.5)
        self.save.assert_not_called()

    def test_electrical_power_and_voltage_offer_the_flow_effect(self):
        self.click("nav_3")
        for metric in ("gpu_power", "voltage"):
            with self.subTest(metric=metric):
                if metric == "voltage":
                    self.assertTrue(self.ui.addTopBarMetric(metric))
                    identifier = self.ui._draft["top_bar"]["items"][-1]["id"]
                    QTest.qWait(35)  # Let the inserted delegate receive its real layout.
                else:
                    identifier = "b_gpu_power"
                target = self.item("topBarItemAdjust_" + identifier)
                scroll = self.item("topBarSettingsScroll")
                for _ in range(12):
                    local = target.mapToItem(scroll, target.boundingRect().center())
                    if 12 <= local.y() <= scroll.height() - 12:
                        break
                    self.wheel(scroll, -120 if local.y() > scroll.height() - 12 else 120)
                scroll.property("contentItem").cancelFlick()
                QTest.qWait(35)
                self.click("topBarItemAdjust_" + identifier)
                self.assertEqual(self.item("topBarSettings").property("selectedItem"), identifier)
                options = groups.variant(
                    self.item("topBarSelectedInspector").property("effectOptions")
                )
                index = next(index for index, row in enumerate(options) if row["id"] == "flow")
                self.choose("topBarIconEffect", index)
                self.assertEqual(self.item_config(identifier)["prefs"]["icon_effect"], "flow")
        self.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
