"""Hardware-icon versions: strict schema, scoped drafts and synthetic offscreen UI."""
import copy
import json
import logging
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import getCppPointer

from configuration_scopes import merge_scope, rebase_saved_changes
from localization import LANGUAGES, MESSAGES
from stats_config import DEFAULT, validate
from top_bar_config import HARDWARE_ICON_STYLES, default_top_bar, validate_top_bar
from tests import test_top_bar_groups_qml as fixture


class HardwareIconSchemaTests(unittest.TestCase):
    def test_old_preferences_default_to_classic_and_keep_existing_layout_and_effect_choices(self):
        old = copy.deepcopy(DEFAULT)
        old["top_bar"].pop("hardware_icon_style", None)
        old["top_bar"]["items"][0]["prefs"].update(style="icon_value", icon_effect="auto")
        old["top_bar"]["spacing"] = 9.5
        before = copy.deepcopy(old)
        result = validate(old)
        self.assertEqual(result["top_bar"]["hardware_icon_style"], "classic")
        normalized_bar = dict(result["top_bar"])
        normalized_bar.pop("hardware_icon_style")
        self.assertEqual(normalized_bar, before["top_bar"])
        self.assertEqual(result["widgets"], before["widgets"])
        self.assertEqual(result["widget_order"], before["widget_order"])
        self.assertEqual(old, before)
        self.assertEqual(default_top_bar()["hardware_icon_style"], "classic")

    def test_all_seven_styles_roundtrip_as_topbar_fields_without_changing_material_or_metrics(self):
        self.assertEqual(HARDWARE_ICON_STYLES, ("cartoon", "notebook_smile", "notebook_color", "notebook_line", "classic", "outline", "solid", "miniature", "soft", "sketch"))
        for style in HARDWARE_ICON_STYLES:
            with self.subTest(style=style):
                config = copy.deepcopy(DEFAULT)
                config["top_bar"]["hardware_icon_style"] = style
                result = validate(json.loads(json.dumps(config)))
                self.assertEqual(result["top_bar"]["hardware_icon_style"], style)
                self.assertEqual(validate(result), result)
                self.assertEqual(result["top_bar"]["items"], DEFAULT["top_bar"]["items"])
                self.assertEqual(result["top_bar"]["appearance"], DEFAULT["top_bar"]["appearance"])
                self.assertEqual(result["widgets"], DEFAULT["widgets"])

    def test_invalid_types_and_values_are_rejected_instead_of_resetting_a_choice(self):
        for invalid in (None, True, False, 0, 1, 1.0, [], {}, ("classic",), "", "Classic", "outline ", "unknown"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_top_bar(dict(default_top_bar(), hardware_icon_style=invalid))

    def test_scoped_merge_and_rebase_keep_the_icon_choice_and_unrelated_pending_work(self):
        saved, draft = copy.deepcopy(DEFAULT), copy.deepcopy(DEFAULT)
        draft["top_bar"]["hardware_icon_style"] = "miniature"
        draft["widgets"]["cpu"]["title"] = "Pending"
        draft["refresh"] = .75
        applied = merge_scope(saved, draft, "topbar")
        self.assertEqual(applied["top_bar"]["hardware_icon_style"], "miniature")
        self.assertEqual(applied["refresh"], saved["refresh"])
        self.assertEqual(applied["widgets"], saved["widgets"])
        other_scope = merge_scope(saved, draft, "preferences")
        self.assertEqual(other_scope["top_bar"]["hardware_icon_style"], "classic")
        after_quick_action = copy.deepcopy(saved)
        after_quick_action["top_bar"]["enabled"] = True
        rebased = rebase_saved_changes(draft, saved, after_quick_action)
        self.assertTrue(rebased["top_bar"]["enabled"])
        self.assertEqual(rebased["top_bar"]["hardware_icon_style"], "miniature")
        self.assertEqual(rebased["widgets"]["cpu"]["title"], "Pending")

    def test_control_labels_and_note_are_available_in_all_eight_languages(self):
        keys = ("硬件图标", "经典通用", "结构线稿", "精简实物", "微型实物", "柔和双色", "可爱卡通", "手绘线稿", "随手线条", "手涂淡彩", "笑脸手绘", "1 · 原版", "2 · 可爱笑脸", "3 · 彩色手绘", "4 · 纯线条",
                "切换外观版本，自动匹配规则和读数保持一致。")
        self.assertEqual(len(LANGUAGES), 8)
        for language in LANGUAGES.keys() - {"zh-CN"}:
            for key in keys:
                self.assertTrue(MESSAGES[language][key], (language, key))

    def test_controller_edits_only_topbar_draft_and_rejects_invalid_inputs_without_saving(self):
        import native_controller as controls
        with (patch("ctypes.WinDLL", side_effect=AssertionError("No native API")) as native,
              patch("subprocess.Popen", side_effect=AssertionError("No process")) as process,
              patch.object(controls, "load", return_value=copy.deepcopy(DEFAULT)),
              patch.object(controls, "save") as save):
            controller = controls.Controller()
            try:
                saved = copy.deepcopy(controller._saved)
                for style in HARDWARE_ICON_STYLES:
                    controller.changeTopBar("hardware_icon_style", style)
                    self.assertEqual(controller._draft["top_bar"]["hardware_icon_style"], style)
                    self.assertEqual(controller._saved, saved)
                before = copy.deepcopy(controller._draft)
                for invalid in (None, 1, True, [], "unknown"):
                    controller.changeTopBar("hardware_icon_style", invalid)
                    self.assertEqual(controller._draft, before)
                self.assertEqual(controller.scopeDirty, dict(desktop=False, preferences=False, topbar=True))
                save.assert_not_called()
            finally:
                controller.close()
            native.assert_not_called()
            process.assert_not_called()

    def test_live_style_command_commits_only_the_style_without_discarding_cached_temperature(self):
        import native_controller as controls
        from PySide6.QtWidgets import QApplication
        from tests import test_installer_audit as ipc_fixture

        application = QApplication.instance() or QApplication([])
        source = validate(copy.deepcopy(DEFAULT))
        source["top_bar"]["hardware_icon_style"] = "cartoon"
        expected = copy.deepcopy(source)
        expected["top_bar"]["hardware_icon_style"] = "miniature"
        now = time.time()
        readings = dict(time=now, cpu_temp=63.0, cpu_temp_source="Synthetic authorized CPU cache",
                        metric_timestamps={"cpu_temp": now}, external_sensors={})
        before = copy.deepcopy(readings)
        with (patch("ctypes.WinDLL", side_effect=AssertionError("No native API")) as native,
              patch("subprocess.Popen", side_effect=AssertionError("No process")) as process,
              patch("threading.Thread.start", side_effect=AssertionError("No worker")),
              patch.object(controls, "load", return_value=source),
              patch.object(controls, "save") as save):
            controller = controls.Controller()
            try:
                controller._data = readings
                applied = QSignalSpy(controller.topBarApplyRequested)
                ipc_fixture.LocalServerCleanQuitAuditTests.setUpClass()
                timer = SimpleNamespace(singleShot=Mock(side_effect=AssertionError("No queued restart")))
                logger = Mock(spec=logging)
                namespace = dict(json=json, os=SimpleNamespace(getpid=lambda: 7007),
                                 logging=logger, QTimer=timer)
                exec(compile(ipc_fixture.LocalServerCleanQuitAuditTests.method,
                             "<actual LocalServer.read; actual Controller; fake socket>", "exec"), namespace)
                runtime = SimpleNamespace(
                    controller=controller,
                    settings=SimpleNamespace(property=lambda name: False),
                    show_settings=Mock(side_effect=AssertionError("No settings window")),
                )
                server = SimpleNamespace(runtime=runtime, application=SimpleNamespace(quit=Mock()))
                client = ipc_fixture.FakeClient(dict(command="hardware_icon_style", style="miniature",
                                                    expected_pid=7007))
                namespace["read"](server, client)
                self.assertEqual(json.loads(client.output),
                                 dict(ok=True, pid=7007, hardware_icon_style="miniature"))
                self.assertTrue(client.disconnected)
                save.assert_called_once_with(expected)
                self.assertEqual(controller.saved, expected)
                self.assertEqual(controller.draft, expected)
                self.assertFalse(controller.dirty)
                self.assertEqual(applied.count(), 1)
                self.assertIs(controller._data, readings)
                self.assertEqual(controller._data, before)
                self.assertIsNone(controller.thread)
                timer.singleShot.assert_not_called()
                server.application.quit.assert_not_called()
                runtime.show_settings.assert_not_called()
                logger.exception.assert_not_called()
            finally:
                controller.close()
            native.assert_not_called()
            process.assert_not_called()


class HardwareIconPreferenceUiTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GroupQmlTests.setUpClass.__func__)
    setUp = fixture.GroupQmlTests.setUp
    tearDown = fixture.GroupQmlTests.tearDown
    item = fixture.GroupQmlTests.item
    click = fixture.GroupQmlTests.click
    resize = fixture.GroupQmlTests.resize
    evaluate = fixture.GroupQmlTests.evaluate

    def show_choice(self):
        self.click("nav_3")
        self.click("topBarAppearanceTab")
        return self.item("topBarHardwareIconChoice")

    def choose(self, index):
        choice = self.item("topBarHardwareIconChoice")
        choice.forceActiveFocus()
        QTest.keyClick(self.window, Qt.Key_Space)
        QTest.keyClick(self.window, Qt.Key_Home)
        for _ in range(index):
            QTest.keyClick(self.window, Qt.Key_Down)
        QTest.keyClick(self.window, Qt.Key_Return)
        QTest.qWait(20)

    def test_keyboard_selection_reuses_one_main_preview_and_does_not_save_or_change_matching_inputs(self):
        self.resize(960, 700)
        choice = self.show_choice()
        self.assertEqual(choice.property("value"), "classic")
        self.assertEqual(choice.property("count"), len(HARDWARE_ICON_STYLES))
        preview = getCppPointer(self.item("topBarMainPreview"))[0]
        before = copy.deepcopy(self.ui._draft)
        saved = copy.deepcopy(self.ui._saved)
        for index, style in enumerate(HARDWARE_ICON_STYLES):
            self.choose(index)
            expected = copy.deepcopy(before)
            expected["top_bar"]["hardware_icon_style"] = style
            self.assertEqual(self.ui._draft, expected)
            self.assertEqual(self.ui._saved, saved)
            self.assertEqual(getCppPointer(self.item("topBarMainPreview"))[0], preview)
            rows = fixture.variant(self.item("topBarMainPreview").property("rows"))
            self.assertTrue(rows)
            self.assertEqual(rows[0]["hardware_appearance"]["icon_set"], style)
        self.save.assert_not_called()

    def test_narrow_choice_is_discoverable_and_scoped_apply_and_revert_preserve_other_drafts(self):
        self.resize(720, 600)
        choice = self.show_choice()
        setting = self.item("topBarHardwareIconSetting")
        self.assertTrue(setting.isVisible() and choice.isVisible())
        self.assertGreaterEqual(choice.width(), 150)
        point = choice.mapToScene(choice.boundingRect().center())
        self.assertGreaterEqual(point.x(), 0)
        self.assertLess(point.x(), self.window.width())
        self.ui.change("refresh", .75)
        self.ui.changeWidget("cpu", "title", "Pending")
        self.choose(HARDWARE_ICON_STYLES.index("outline"))
        self.click("applyButton")
        self.assertEqual(self.ui._saved["top_bar"]["hardware_icon_style"], "outline")
        self.assertEqual(self.ui._saved["refresh"], DEFAULT["refresh"])
        self.assertEqual(self.ui._draft["refresh"], .75)
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["title"], "Pending")
        self.assertEqual(self.save.call_count, 1)
        self.choose(HARDWARE_ICON_STYLES.index("soft"))
        self.click("revertButton")
        self.assertEqual(self.ui._draft["top_bar"]["hardware_icon_style"], "outline")
        self.assertEqual(self.ui._draft["refresh"], .75)
        self.assertEqual(self.ui._draft["widgets"]["cpu"]["title"], "Pending")
        self.click("topBarContentTab")
        QCoreApplication.processEvents()
        self.assertFalse(setting.isVisible())


if __name__ == "__main__":
    unittest.main()
