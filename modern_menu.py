"""Compact native QMenu presentation; QAction and keyboard behavior stay Qt's.

No capture, native DLL, delayed backdrop or global application style is used.
Each menu owns its Fusion proxy style. SVGs are the pinned local Lucide assets.
"""

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QLineF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QMenu, QProxyStyle, QStyle, QStyleOptionMenuItem

_ICONS = Path(__file__).resolve().parent / "assets" / "lucide" / "icons"
_THEMES = {
    "light": dict(bg="#fbfbfc", ink="#202124", muted="#62666d", disabled="#92969e",
                  line="#e2e4e8", border="#d8dbe1", hover="#edf0f4", accent="#2363c9",
                  danger="#b3261e", danger_hover="#fcebe9", shadow="#1c2534"),
    "dark": dict(bg="#292a2d", ink="#f1f3f4", muted="#b8bdc5", disabled="#858a93",
                 line="#42454b", border="#4b4e55", hover="#3b3e44", accent="#a8c7fa",
                 danger="#ffb4ab", danger_hover="#533332", shadow="#000000"),
}
_AUTO_ICONS = {
    "edit_widget": "sliders-horizontal", "hide_widget": "x", "topBarDisable": "x",
}
_ICON_NAMES = frozenset(path.stem for path in _ICONS.glob("*.svg"))


def _theme(value):
    return "dark" if value == "dark" else "light"


@lru_cache(maxsize=128)
def lucide_icon(name, theme="light", *, danger=False):
    """Return a 16DIP icon with real 1–3x rasters, never an emoji/system glyph."""
    if not isinstance(name, str) or name not in _ICON_NAMES:
        raise ValueError("A pinned local Lucide icon name is required")
    colors = _THEMES[_theme(theme)]
    source = (_ICONS / (name + ".svg")).read_text(encoding="utf-8")
    icon = QIcon()
    for mode, color in ((QIcon.Mode.Normal, colors["danger"] if danger else colors["muted"]),
                        (QIcon.Mode.Disabled, colors["disabled"])):
        renderer = QSvgRenderer(QByteArray(source.replace("currentColor", color).encode("utf-8")))
        for ratio in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
            edge = round(16 * ratio)
            image = QImage(edge, edge, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, edge, edge))
            painter.end()
            image.setDevicePixelRatio(ratio)
            icon.addPixmap(QPixmap.fromImage(image), mode)
    return icon


@lru_cache(maxsize=128)
def _vector_icon(name, color):
    if name not in _ICON_NAMES:
        raise ValueError("A pinned local Lucide icon name is required")
    source = (_ICONS / (name + ".svg")).read_text(encoding="utf-8")
    return QSvgRenderer(QByteArray(source.replace("currentColor", color).encode("utf-8")))


def _draw_icon(painter, rect, name, colors, *, enabled=True, danger=False):
    color = colors["disabled"] if not enabled else colors["danger"] if danger else colors["muted"]
    _vector_icon(name, color).render(painter, QRectF(rect))


def decorate_action(action, icon=None, *, role=None, theme="light"):
    """Optional semantic hints; never changes text, checked, data or callbacks."""
    if role is not None:
        if role not in ("normal", "primary", "danger"):
            raise ValueError("Menu role must be normal, primary or danger")
        action.setProperty("modernMenuRole", role)
    if icon is not None:
        action.setProperty("modernMenuIcon", icon)
    name = action.property("modernMenuIcon") or _AUTO_ICONS.get(action.objectName())
    if name:
        action.setIcon(lucide_icon(name, _theme(theme),
                                  danger=action.property("modernMenuRole") == "danger"))
    return action


def set_action_icon(action, name, *, role=None, theme=None):
    """Attach a semantic Lucide icon; infer the owning menu's current theme."""
    if theme is None:
        owners = [action.parent(), *action.associatedObjects()]
        menu = next((owner for owner in owners if isinstance(owner, QMenu)), None)
        theme = menu.property("modernMenuTheme") if menu is not None else "light"
    return decorate_action(action, name, role=role, theme=theme)


def _hint(option, widget, action=None):
    if not isinstance(widget, QMenu):
        return ""
    if action is None:
        action = next((item for item in widget.actions()
                       if item.text().split("\t", 1)[0] == option.text.split("\t", 1)[0]), None)
    value = action.property("menuHint") if action is not None else None
    return value if isinstance(value, str) else ""


class _MenuStyle(QProxyStyle):
    def __init__(self, menu, theme):
        super().__init__("Fusion")
        self.setParent(menu)
        self.theme = _theme(theme)

    @property
    def colors(self):
        return _THEMES[self.theme]

    def pixelMetric(self, metric, option=None, widget=None):
        values = {QStyle.PixelMetric.PM_MenuPanelWidth: 5,
                  QStyle.PixelMetric.PM_MenuHMargin: 3,
                  QStyle.PixelMetric.PM_MenuVMargin: 3,
                  QStyle.PixelMetric.PM_SmallIconSize: 16,
                  QStyle.PixelMetric.PM_MenuDesktopFrameWidth: 0,
                  QStyle.PixelMetric.PM_MenuScrollerHeight: 22,
                  QStyle.PixelMetric.PM_SubMenuOverlap: -4}
        if metric in values:
            return values[metric]
        return super().pixelMetric(metric, option, widget)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        values = {QStyle.StyleHint.SH_Menu_MouseTracking: 1,
                  QStyle.StyleHint.SH_Menu_SupportsSections: 1,
                  QStyle.StyleHint.SH_Menu_Scrollable: 1,
                  QStyle.StyleHint.SH_Menu_SubMenuPopupDelay: 150,
                  QStyle.StyleHint.SH_Menu_SpaceActivatesItem: 1,
                  QStyle.StyleHint.SH_Menu_FlashTriggeredItem: 0,
                  QStyle.StyleHint.SH_Menu_AllowActiveAndDisabled: 0}
        if hint in values:
            return values[hint]
        return super().styleHint(hint, option, widget, returnData)

    def sizeFromContents(self, kind, option, contentsSize, widget=None):
        if kind == QStyle.ContentsType.CT_MenuItem and isinstance(option, QStyleOptionMenuItem):
            if option.menuItemType == QStyleOptionMenuItem.MenuItemType.Separator:
                return QSize(120, 27 if option.text else 9)
            # Qt adds the shared shortcut-column width separately. Bound the
            # label, retain the full QAction text/accessibility and tooltip.
            extra = 20 if not option.icon.isNull() and option.checkType != option.CheckType.NotCheckable else 0
            hint = _hint(option, widget)
            padding = 68 if option.menuItemType == option.MenuItemType.SubMenu else 58
            if hint:
                padding += min(116, option.fontMetrics.horizontalAdvance(hint)) + 24
            if "\t" in option.text:
                padding += 24
            return QSize(max(216, min(384, min(contentsSize.width(), 306) + padding + extra)),
                         max(32, option.fontMetrics.height() + 12))
        return super().sizeFromContents(kind, option, contentsSize, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_FrameMenu:
            return  # The antialiased panel owns the only border.
        if element != QStyle.PrimitiveElement.PE_PanelMenu:
            return super().drawPrimitive(element, option, painter, widget)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = QRectF(option.rect).adjusted(4.5, 4.5, -4.5, -4.5)
        for spread, alpha in ((4, 3), (3, 5), (2, 7), (1, 9)):
            shadow = QColor(self.colors["shadow"])
            shadow.setAlpha(alpha if self.theme == "light" else alpha + 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(panel.adjusted(-spread, -spread + .7, spread, spread + .7),
                                    10 + spread, 10 + spread)
        painter.setPen(QPen(QColor(self.colors["border"]), 1))
        painter.setBrush(QColor(self.colors["bg"]))
        painter.drawRoundedRect(panel, 10, 10)
        painter.restore()

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_MenuEmptyArea:
            return
        if element != QStyle.ControlElement.CE_MenuItem or not isinstance(option, QStyleOptionMenuItem):
            return super().drawControl(element, option, painter, widget)
        if option.menuItemType in (option.MenuItemType.Scroller, option.MenuItemType.TearOff):
            return super().drawControl(element, option, painter, widget)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        colors = self.colors
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        selected = enabled and bool(option.state & QStyle.StateFlag.State_Selected)
        action = widget.actionAt(rect.center()) if isinstance(widget, QMenu) else None
        role = action.property("modernMenuRole") if action is not None else "normal"
        font = QFont(option.font)
        if role == "primary" or option.menuItemType == option.MenuItemType.DefaultItem:
            font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        if option.menuItemType == option.MenuItemType.Separator:
            if option.text:
                font.setPixelSize(12)
                font.setWeight(QFont.Weight.Medium)
                painter.setFont(font)
                painter.setPen(QColor(colors["muted"]))
                painter.drawText(rect.adjusted(10, 2, -10, 0), Qt.AlignmentFlag.AlignVCenter,
                                 option.text)
            else:
                painter.setPen(QPen(QColor(colors["line"]), 1))
                y = rect.center().y() + .5
                painter.drawLine(QLineF(rect.left() + 10, y, rect.right() - 10, y))
            painter.restore()
            return
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["danger_hover"] if role == "danger" else colors["hover"]))
            painter.drawRoundedRect(QRectF(rect).adjusted(0, 1, 0, -1), 6, 6)
        ink = colors["disabled"] if not enabled else colors["danger"] if role == "danger" else colors["ink"]
        icon_box = QRect(rect.left() + 10, rect.center().y() - 8, 16, 16)
        trailing = QRect(rect.right() - 24, rect.center().y() - 8, 16, 16)
        def visual(box):
            return QStyle.visualRect(option.direction, rect, box)
        has_icon = not option.icon.isNull()
        checkable = option.checkType != option.CheckType.NotCheckable
        if has_icon:
            icon_name = action.property("modernMenuIcon") if action is not None else None
            if isinstance(icon_name, str) and icon_name in _ICON_NAMES:
                _draw_icon(painter, visual(icon_box), icon_name, colors,
                           enabled=enabled, danger=role == "danger")
            else:
                option.icon.paint(painter, visual(icon_box), Qt.AlignmentFlag.AlignCenter,
                                  QIcon.Mode.Normal if enabled else QIcon.Mode.Disabled)
        if checkable:
            check_box = trailing if has_icon else icon_box
            if option.checkType == option.CheckType.Exclusive:
                painter.setPen(QPen(QColor(colors["disabled"] if not enabled else colors["muted"]), 1.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(visual(check_box)).adjusted(2, 2, -2, -2))
                if option.checked:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(colors["disabled"] if not enabled else colors["accent"]))
                    painter.drawEllipse(QRectF(visual(check_box)).adjusted(5, 5, -5, -5))
            elif option.checked:
                _draw_icon(painter, visual(check_box), "check", colors, enabled=enabled)
        submenu = option.menuItemType == option.MenuItemType.SubMenu
        if submenu:
            painter.save()
            if option.direction == Qt.LayoutDirection.RightToLeft:
                center = visual(trailing).center()
                painter.translate(center)
                painter.scale(-1, 1)
                painter.translate(-center)
            _draw_icon(painter, visual(trailing), "chevron-right", colors, enabled=enabled)
            painter.restore()
        label, _, shortcut = option.text.partition("\t")
        right = 32 if submenu or has_icon and checkable else 12
        hint = _hint(option, widget, action) if submenu and not shortcut else ""
        secondary = shortcut or hint
        if secondary:
            reserve = (max(option.reservedShortcutWidth, QFontMetrics(font).horizontalAdvance(shortcut))
                       if shortcut else min(116, QFontMetrics(font).horizontalAdvance(hint),
                           max(0, rect.width() - 36 - right - 24
                               - QFontMetrics(font).horizontalAdvance(label) - 2)))
            # The operation name wins. Omit a hint that cannot even fit its
            # ellipsis, including its gap, rather than squeeze the main label.
            if shortcut or reserve >= QFontMetrics(font).horizontalAdvance("…"):
                shortcut_box = QRect(rect.right() - right - reserve, rect.top(), reserve, rect.height())
                painter.setPen(QColor(colors["disabled"] if not enabled else colors["muted"]))
                painter.drawText(visual(shortcut_box), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                                 QFontMetrics(font).elidedText(secondary, Qt.TextElideMode.ElideRight, reserve))
                right += reserve + 24
        text_box = visual(rect.adjusted(36, 0, -right, 0))
        painter.setPen(QColor(ink))
        text = QFontMetrics(font).elidedText(label, Qt.TextElideMode.ElideRight, text_box.width())
        mnemonic = (Qt.TextFlag.TextShowMnemonic if self.styleHint(QStyle.StyleHint.SH_UnderlineShortcut,
                    option, widget) else Qt.TextFlag.TextHideMnemonic)
        painter.drawText(text_box, Qt.AlignmentFlag.AlignVCenter | mnemonic, text)
        painter.restore()


def _refresh(menu):
    theme = menu.property("modernMenuTheme") or "light"
    for action in menu.actions():
        decorate_action(action, theme=theme)
        if not action.toolTip() and not action.isSeparator():
            action.setToolTip(action.text().split("\t", 1)[0])
        if action.menu() is not None:
            apply_menu(action.menu(), theme=theme, language=menu.property("modernMenuLanguage"))


def apply_menu(menu, *, theme="light", language="zh-CN"):
    """Style an existing QMenu recursively without replacing its QActions."""
    if not isinstance(menu, QMenu):
        raise TypeError("An existing QMenu is required")
    theme = _theme(theme)
    menu.setProperty("modernMenuTheme", theme)
    menu.setProperty("modernMenuLanguage", language or "zh-CN")
    style = getattr(menu, "_modern_style", None)
    if style is None:
        style = menu._modern_style = _MenuStyle(menu, theme)
        menu.setStyle(style)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.setAutoFillBackground(False)
        menu.aboutToShow.connect(lambda: _refresh(menu))
    style.theme = theme
    menu.setStyleSheet("")
    families = {"zh-CN": "Microsoft YaHei UI", "zh-TW": "Microsoft JhengHei UI",
                "ja": "Yu Gothic UI", "ko": "Malgun Gothic"}
    font = QFont(families.get(language, "Segoe UI Variable"))
    font.setPixelSize(14)
    menu.setFont(font)
    menu.setMinimumWidth(232)
    menu.setToolTipsVisible(True)
    palette = menu.palette()
    for role, color in ((QPalette.ColorRole.Window, style.colors["bg"]),
                        (QPalette.ColorRole.WindowText, style.colors["ink"]),
                        (QPalette.ColorRole.Text, style.colors["ink"]),
                        (QPalette.ColorRole.Highlight, style.colors["hover"]),
                        (QPalette.ColorRole.HighlightedText, style.colors["ink"])):
        palette.setColor(role, QColor(color))
    menu.setPalette(palette)
    _refresh(menu)
    menu.update()
    return menu


style_submenu = apply_menu


class ModernMenu(QMenu):
    def __init__(self, title="", parent=None, *, theme="light", language="zh-CN"):
        super().__init__(title, parent)
        apply_menu(self, theme=theme, language=language)

    def addMenu(self, *args):
        if len(args) == 1 and isinstance(args[0], QMenu):
            child = args[0]
            apply_menu(child, theme=self.property("modernMenuTheme"),
                       language=self.property("modernMenuLanguage"))
            return super().addMenu(child)
        if len(args) == 1 and isinstance(args[0], str):
            icon, title = None, args[0]
        elif len(args) == 2 and isinstance(args[0], (QIcon, QPixmap)) and isinstance(args[1], str):
            icon, title = args
        else:
            return super().addMenu(*args)
        child = ModernMenu(title, self, theme=self.property("modernMenuTheme"),
                           language=self.property("modernMenuLanguage"))
        if icon is not None:
            child.setIcon(icon)
        super().addMenu(child)
        return child
