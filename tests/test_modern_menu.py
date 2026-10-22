"""Real offscreen QMenu input/rendering; never native desktop or capture."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
if Path("C:/Windows/Fonts").is_dir():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QAction, QActionGroup, QFontMetrics, QImage, QPainter, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QStyleOptionMenuItem  # noqa: E402

from modern_menu import ModernMenu, apply_menu, decorate_action, lucide_icon, set_action_icon  # noqa: E402


class ModernMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("These tests must run offscreen")
        cls._quit_on_last_window = cls.app.quitOnLastWindowClosed()
        cls.app.setQuitOnLastWindowClosed(False)

    @classmethod
    def tearDownClass(cls):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        cls.app.processEvents()
        cls.app.setQuitOnLastWindowClosed(cls._quit_on_last_window)

    def setUp(self):
        self.menu = ModernMenu()

    def tearDown(self):
        self.menu.close()
        self.menu.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def show(self):
        self.menu.popup(QPoint(30, 30))
        QTest.qWait(5)

    @staticmethod
    def render(menu, ratio=1):
        menu.ensurePolished()
        menu.resize(menu.sizeHint())
        image = QImage(round(menu.width() * ratio), round(menu.height() * ratio),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            menu.render(painter, QPoint())
        finally:
            painter.end()
        return image

    def test_keeps_qmenu_qaction_overloads_and_callback(self):
        calls = []
        action = self.menu.addAction("打开设置", lambda: calls.append("open"))
        self.assertIsInstance(self.menu, QMenu)
        self.assertIsInstance(action, QAction)
        action.setData({"stable": 7})
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        QTest.keyClick(self.menu, Qt.Key.Key_Return)
        self.assertEqual(calls, ["open"])
        self.assertEqual(action.data(), {"stable": 7})
        self.assertFalse(self.menu.isVisible())

    def test_keyboard_checkbox_toggles_once_without_losing_action(self):
        action = self.menu.addAction("显示标题")
        action.setCheckable(True)
        checks = []
        action.triggered.connect(lambda checked: checks.append(checked))
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        QTest.keyClick(self.menu, Qt.Key.Key_Space)
        self.assertTrue(action.isChecked())
        self.assertEqual(checks, [True])

    def test_disabled_action_is_skipped_and_cannot_trigger(self):
        disabled = self.menu.addAction("未连接的来源")
        disabled.setEnabled(False)
        target = self.menu.addAction("组件设置")
        calls = []
        disabled.triggered.connect(lambda: calls.append("disabled"))
        target.triggered.connect(lambda: calls.append("target"))
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        self.assertIs(self.menu.activeAction(), target)
        QTest.keyClick(self.menu, Qt.Key.Key_Return)
        self.assertEqual(calls, ["target"])

    def test_radio_group_still_enforces_exclusive_selection(self):
        group = QActionGroup(self.menu)
        group.setExclusive(True)
        actions = [self.menu.addAction(text) for text in ("跟随全局", "清透玻璃", "柔雾玻璃")]
        for index, action in enumerate(actions):
            action.setCheckable(True)
            action.setData(index)
            group.addAction(action)
        actions[0].setChecked(True)
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        QTest.keyClick(self.menu, Qt.Key.Key_Return)
        self.assertEqual([action.isChecked() for action in actions], [False, True, False])
        self.assertEqual(actions[1].data(), 1)

    def test_submenu_right_left_escape_follow_native_qmenu(self):
        sub = self.menu.addMenu("组件皮肤")
        sub.addAction("清透玻璃")
        sub.addAction("柔雾玻璃")
        self.assertIsInstance(sub, ModernMenu)
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_Down)
        QTest.keyClick(self.menu, Qt.Key.Key_Right)
        QTest.qWait(5)
        self.assertTrue(sub.isVisible())
        QTest.keyClick(sub, Qt.Key.Key_Escape)
        self.assertFalse(sub.isVisible())
        self.assertTrue(self.menu.isVisible())
        QTest.keyClick(self.menu, Qt.Key.Key_Escape)
        self.assertFalse(self.menu.isVisible())

    def test_mouse_trigger_uses_original_action_geometry(self):
        action = self.menu.addAction("编辑内容与布局")
        calls = []
        action.triggered.connect(lambda: calls.append(1))
        self.show()
        point = self.menu.actionGeometry(action).center()
        QTest.mouseMove(self.menu, point)
        QTest.mouseClick(self.menu, Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(calls, [1])

    def test_existing_submenu_overload_returns_action_and_keeps_its_actions(self):
        sub = QMenu("现有子菜单", self.menu)
        action = sub.addAction("清透玻璃")
        returned = self.menu.addMenu(sub)
        self.assertIs(returned, sub.menuAction())
        self.assertIs(sub.actions()[0], action)
        self.assertEqual(sub.property("modernMenuTheme"), "light")
        self.assertTrue(hasattr(sub, "_modern_style"))

    def test_recursive_theme_update_reuses_owned_styles_and_actions(self):
        sub = self.menu.addMenu("组件皮肤")
        action = sub.addAction("编辑")
        set_action_icon(action, "sliders-horizontal")
        old_style, sub_style = self.menu.style(), sub.style()
        apply_menu(self.menu, theme="dark", language="de")
        self.assertIs(self.menu.style(), old_style)
        self.assertIs(sub.style(), sub_style)
        self.assertEqual(sub.property("modernMenuTheme"), "dark")
        self.assertIs(sub.actions()[0], action)
        self.assertEqual(self.menu.font().pixelSize(), 14)

    def test_proxy_does_not_own_or_replace_global_application_style(self):
        application_style = self.app.style()
        self.assertIsNot(self.menu.style(), application_style)
        self.assertIsNot(self.menu.style().baseStyle(), application_style)
        self.assertIs(self.menu.style().parent(), self.menu)
        self.menu.deleteLater()
        self.app.processEvents()
        self.assertIs(self.app.style(), application_style)
        self.menu = ModernMenu()

    def test_icons_use_pinned_svg_at_fractional_and_high_dpi(self):
        icon = lucide_icon("sliders-horizontal", "dark")
        for ratio in (1, 1.25, 1.75, 2, 3):
            with self.subTest(ratio=ratio):
                pixmap = icon.pixmap(QSize(16, 16), ratio)
                self.assertFalse(pixmap.isNull())
                self.assertAlmostEqual(pixmap.deviceIndependentSize().width(), 16, delta=.1)
                self.assertGreaterEqual(pixmap.width(), round(16 * ratio))
        with self.assertRaises(ValueError):
            lucide_icon("../../foreign")

    def test_semantic_icon_and_role_keep_native_business_fields(self):
        action = self.menu.addAction("隐藏此组件")
        action.setData("cpu")
        action.setCheckable(True)
        action.setChecked(True)
        set_action_icon(action, "trash", role="danger")
        self.assertEqual(action.property("modernMenuRole"), "danger")
        self.assertEqual(action.property("modernMenuIcon"), "trash")
        self.assertFalse(action.icon().isNull())
        self.assertEqual(action.data(), "cpu")
        self.assertTrue(action.isCheckable() and action.isChecked())
        with self.assertRaises(ValueError):
            decorate_action(action, role="unknown")

    def test_menu_hint_is_muted_preview_without_modifying_shortcut_or_data(self):
        sub = self.menu.addMenu("组件皮肤")
        action = sub.menuAction()
        action.setProperty("menuHint", "清透玻璃 / 使用全局透明度设置")
        action.setData({"skin": "unchanged"})
        sub.addAction("清透玻璃")
        image = self.render(self.menu)
        self.assertFalse(image.isNull())
        self.assertTrue(action.shortcut().isEmpty())
        self.assertEqual(action.data(), {"skin": "unchanged"})
        self.assertLess(self.menu.width(), 480)

    def test_bounded_menu_preserves_full_operation_before_secondary_hint(self):
        label = "Window layer for desktop widgets"
        hint = "Desktop only, following the global window arrangement"
        sub = self.menu.addMenu(label)
        sub.menuAction().setProperty("menuHint", hint)
        sub.addAction("Desktop only")
        painted = []
        draw = QPainter.drawText

        def record(painter, *args):
            if args and isinstance(args[-1], str):
                painted.append(args[-1])
            return draw(painter, *args)

        with patch.object(QPainter, "drawText", record):
            self.render(self.menu)
        self.assertLessEqual(self.menu.width(), 400)
        self.assertIn(label, painted)
        self.assertNotIn(hint, painted)
        self.assertEqual(sub.menuAction().text(), label)

    def test_extreme_german_operation_remains_bounded_with_full_tooltip(self):
        label = "Fensterebene und Darstellung aller Desktop-Komponenten konfigurieren"
        sub = self.menu.addMenu(label)
        sub.menuAction().setProperty("menuHint", "Nur auf dem Desktop und unter anderen Fenstern anzeigen")
        sub.addAction("Nur auf Desktop")
        self.show()
        self.assertLessEqual(self.menu.width(), 400)
        self.assertEqual(sub.menuAction().text(), label)
        self.assertEqual(sub.menuAction().toolTip(), label)

    def test_long_chinese_and_german_labels_are_bounded_with_full_accessible_text(self):
        label = "这是一个非常长的中文自定义组件名称与放置设置" * 3
        action = self.menu.addAction(label)
        sub = self.menu.addMenu("Position und Darstellung der Desktop-Komponenten")
        sub.menuAction().setProperty("menuHint", "Automatisch – diesem Bildschirm folgen")
        sub.addAction("跟随全局")
        self.show()
        self.assertLessEqual(self.menu.width(), 520)
        self.assertEqual(action.text(), label)
        self.assertEqual(action.toolTip(), label)
        for item in self.menu.actions():
            self.assertLessEqual(self.menu.actionGeometry(item).right(), self.menu.width() - 5)

    def test_row_density_is_logical_pixels_not_oversized_dialog(self):
        action = self.menu.addAction("组件设置")
        self.render(self.menu)
        rect = self.menu.actionGeometry(action)
        self.assertGreaterEqual(rect.height(), 32)
        self.assertLessEqual(rect.height(), 38)
        self.assertGreaterEqual(self.menu.width(), 232)
        self.assertLess(self.menu.width(), 300)
        self.assertEqual(self.menu.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize), 16)

    def test_rounded_edge_is_transparent_and_antialiased_in_both_themes(self):
        self.menu.addAction("组件设置")
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                apply_menu(self.menu, theme=theme)
                image = self.render(self.menu, ratio=2)
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                self.assertEqual(image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 255)
                alphas = {image.pixelColor(x, y).alpha() for x in range(24) for y in range(24)}
                self.assertTrue(any(0 < alpha < 255 for alpha in alphas))

    def test_shortcuts_and_section_measurement_fit_inside_action_rect(self):
        self.menu.addSection("桌面组件")
        action = self.menu.addAction("组件设置\tCtrl+,")
        action.setShortcutVisibleInContextMenu(True)
        self.render(self.menu)
        option = QStyleOptionMenuItem()
        self.menu.initStyleOption(option, action)
        metrics = QFontMetrics(self.menu.font())
        rect = self.menu.actionGeometry(action)
        self.assertGreater(rect.width(), metrics.horizontalAdvance("组件设置")
                           + metrics.horizontalAdvance("Ctrl+,") + 58)

    def test_mnemonic_uses_original_qaction_accelerator(self):
        first = self.menu.addAction("&Edit content")
        target = self.menu.addAction("&View settings")
        calls = []
        target.triggered.connect(lambda: calls.append("view"))
        first.triggered.connect(lambda: calls.append("edit"))
        self.show()
        QTest.keyClick(self.menu, Qt.Key.Key_V)
        self.assertEqual(calls, ["view"])

    def test_long_menu_uses_native_scroll_wheel_and_end_home_navigation(self):
        actions = [self.menu.addAction(f"传感器选项 {index + 1:02d}") for index in range(80)]
        self.show()
        before = self.menu.actionGeometry(actions[0]).top()
        point = QPointF(self.menu.rect().center())
        event = QWheelEvent(point, QPointF(self.menu.mapToGlobal(point.toPoint())),
                            QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(self.menu, event)
        self.app.processEvents()
        self.assertLess(self.menu.actionGeometry(actions[0]).top(), before)
        QTest.keyClick(self.menu, Qt.Key.Key_End)
        self.assertIs(self.menu.activeAction(), actions[-1])
        self.assertTrue(self.menu.rect().intersects(self.menu.actionGeometry(actions[-1])))
        QTest.keyClick(self.menu, Qt.Key.Key_Home)
        self.assertIs(self.menu.activeAction(), actions[0])
        self.assertTrue(self.menu.rect().intersects(self.menu.actionGeometry(actions[0])))


if __name__ == "__main__":
    unittest.main()
