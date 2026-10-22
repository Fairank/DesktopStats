"""Independently exercise customization through Qt's actual event handlers.

The default, and only supported platform, is offscreen. The profile is isolated,
hardware sampling and Windows composition calls are stubbed, and QCursor is not
read. No installed process, foreground window, system mouse or clipboard is used.
Passing this audit establishes editor/menu persistence and Qt painting behavior;
it does not establish that DWM really blurs the desktop. That needs a separately
authorized, visible compositor check while the user is idle.
"""

# Project/Qt imports must follow the isolated, noninteractive environment.
# ruff: noqa: E402

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
import traceback
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROFILE = ROOT / "qa-private" / f"customization-profile-{os.getpid()}"
os.environ["DESKTOP_STATS_DATA"] = str(PROFILE)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QSG_RENDER_LOOP"] = "basic"

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontInfo,
    QImage,
    QPainter,
    QRawFont,
    QWheelEvent,
)
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

import native_runtime
from native_card import HardwareCard
from native_controller import Controller
from skin_styles import GLASS_SKINS, SKINS, effective_skin
from stats_config import DEFAULT, load, save, validate
from widget_catalog import from_template


class LocalCursor:
    """Popup coordinates in the synthetic offscreen screen, not the OS cursor."""

    @staticmethod
    def pos():
        return QPoint(120, 100)


def load_system_fonts():
    """Read system font files into this Qt process, without installing fonts.

    The offscreen Windows platform may start with an empty font database. A
    nonempty database alone is insufficient: check the actual family selected
    and its own glyph table, so a fallback/tofu rendering cannot pass this audit.
    """
    directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    result = dict(
        familiesBefore=len(QFontDatabase.families()),
        scope="process-local QFontDatabase.addApplicationFont; no font installation",
        loaded={},
        missingFiles=[],
        checks=[],
    )
    for filename in (
        "msyh.ttc",
        "msyhbd.ttc",
        "SegUIVar.ttf",
        "segoeui.ttf",
        "seguisb.ttf",
        "msjh.ttc",
        "msjhbd.ttc",
        "YuGothR.ttc",
        "YuGothB.ttc",
        "malgun.ttf",
        "malgunbd.ttf",
    ):
        path = directory / filename
        if not path.is_file():
            result["missingFiles"].append(filename)
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        result["loaded"][filename] = QFontDatabase.applicationFontFamilies(font_id)
    result["familiesAfter"] = len(QFontDatabase.families())
    for family, characters in (
        ("Microsoft YaHei UI", "系统温度功耗充电内存"),
        ("Segoe UI", "CPU0123456789°CW%"),
        ("Segoe UI Variable", "CPU0123456789°CW%"),
        ("Microsoft JhengHei UI", "系統溫度記憶體"),
        ("Yu Gothic", "温度電力システム"),
        ("Yu Gothic UI", "温度電力システム"),
        ("Malgun Gothic", "온도전력배터리"),
    ):
        font = QFont(family, 12)
        resolved = QFontInfo(font).family()
        raw = QRawFont.fromFont(font)
        glyphs = list(raw.glyphIndexesForString(characters))
        passed = (
            resolved == family
            and raw.isValid()
            and raw.familyName() == family
            and len(glyphs) == len(characters)
            and all(glyphs)
        )
        result["checks"].append(
            dict(
                family=family,
                resolved=resolved,
                rawFamily=raw.familyName(),
                characters=characters,
                glyphIndexes=glyphs,
                passed=bool(passed),
            )
        )
    result["passed"] = result["familiesAfter"] > 0 and all(
        check["passed"] for check in result["checks"]
    )
    return result


def descendants(node):
    queue, result, seen = [node], [], set()
    while queue:
        item = queue.pop()
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        result.append(item)
        queue.extend(item.children())
        if hasattr(item, "childItems"):
            queue.extend(item.childItems())
    return result


def fixture():
    config = copy.deepcopy(DEFAULT)
    target, peer = from_template("custom"), from_template("gpu")
    for prefs, metric in ((target, "cpu_usage"), (peer, "gpu_usage")):
        prefs.update(
            title="",
            content=[metric],
            chart=False,
            presentation="hero",
            skin=None,
            grouped=True,
            show_title=True,
            size=None,
        )
    config.update(
        language="en",
        theme="light",
        skin="card",
        mode="separate",
        size=112,
        autostart=False,
        visible=True,
        locked=False,
        widgets={"w_target": target, "w_peer": peer},
        widget_order=["w_target", "w_peer"],
    )
    return validate(config)


class Audit:
    def __init__(self, runtime, report, transparency_policy):
        self.runtime, self.controller, self.report = runtime, runtime.controller, report
        self.transparency_policy = transparency_policy
        self.window = runtime.settings
        self.frames = 0
        self.menu_requests = []
        self.settings_requests = []
        self.context_source = None
        runtime.controller.menuRequested.connect(self.menu_requests.append)
        runtime.controller.settingsRequested.connect(self.settings_requests.append)
        self.window.frameSwapped.connect(self.frame_rendered)

    def frame_rendered(self):
        self.frames += 1

    def settle(self):
        """Let real event delivery, animations, bindings and a rendered frame finish."""
        before = self.frames
        self.window.update()
        for _ in range(60):
            QTest.qWait(20)
            if self.frames > before:
                QTest.qWait(135)
                return
        raise AssertionError("Offscreen Qt settings did not render a frame")

    def find(self, name, parent=None):
        root = parent if parent is not None else self.window.contentItem()
        found = [item for item in descendants(root) if item.objectName() == name]
        assert len(found) == 1, f"Expected exactly one {name}, found {len(found)}"
        return found[0]

    def require(self, condition, message, **details):
        self.report["checks"].append(dict(name=message, passed=bool(condition), **details))
        assert condition, message

    def run(self, name, callback):
        try:
            # Each workflow starts from the same independently saved fixture;
            # a failing local override must not produce unrelated later failures.
            self.controller.edit(fixture())
            self.controller.apply()
            self.window.selectWidget("w_target")
            self.settle()
            callback()
        except Exception:
            self.report["failures"].append(dict(case=name, traceback=traceback.format_exc()))
            menu = getattr(self.runtime, "context_menu", None)
            if menu is not None:
                menu.close()
            self.controller.revert()
            QTest.qWait(50)

    @staticmethod
    def flickable_for(item):
        parent = item.parentItem()
        fallback = None
        while parent is not None:
            if parent.metaObject().indexOfProperty("contentY") >= 0:
                fallback = parent
                # The inline inspector keeps a natural-height ScrollView to
                # preserve its controls. Its content does not scroll; the
                # enclosing component workspace is the clipping viewport.
                if parent.property("contentHeight") > parent.height() + 1:
                    return parent
            parent = parent.parentItem()
        return fallback

    def click(self, item):
        self.require(
            item.isVisible() and item.isEnabled(),
            "Click target visible and enabled",
            objectName=item.objectName(),
        )
        viewport = self.flickable_for(item)
        if viewport is not None:
            # Use real local wheel events to reveal controls, never assign contentY.
            for _ in range(35):
                point = item.mapToItem(viewport, QPointF(item.width() / 2, item.height() / 2))
                if 2 <= point.y() <= viewport.height() - 2:
                    break
                # The center may contain the precise-layout canvas, which
                # correctly owns wheel pan/zoom. Use the outer page's visible
                # margin to scroll the page rather than that nested canvas.
                position = viewport.mapToScene(QPointF(8, viewport.height() / 2))
                delta = -360 if point.y() > viewport.height() else 360
                wheel = QWheelEvent(
                    position,
                    position,
                    QPoint(),
                    QPoint(0, delta),
                    Qt.NoButton,
                    Qt.NoModifier,
                    Qt.NoScrollPhase,
                    False,
                )
                wheel.setTimestamp(round(time.monotonic() * 1000))
                QCoreApplication.sendEvent(self.window, wheel)
                QTest.qWait(170)
            # A wheel-triggered scroll can outlive the first visible frame.
            # Wait for actual motion to stop before this separate user click;
            # never retry a missed click or assign focus/contentY to pass it.
            for _ in range(100):
                if not viewport.property("moving"):
                    break
                QTest.qWait(20)
            QTest.qWait(120)
            point = item.mapToItem(viewport, QPointF(item.width() / 2, item.height() / 2))
            self.require(
                0 <= point.y() <= viewport.height(),
                "Click target in its scroll viewport",
                objectName=item.objectName(),
                y=point.y(),
                viewport=viewport.height(),
            )
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
        self.require(
            0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height(),
            "Click target in settings bounds",
            objectName=item.objectName(),
        )
        # QTest sends local Qt events to an offscreen window; it never moves a physical cursor.
        QTest.mouseMove(self.window, point.toPoint())
        QTest.qWait(25)
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        QTest.qWait(30)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
        self.settle()

    def apply(self):
        self.click(self.find("applyButton"))
        self.require(
            self.controller._draft == self.controller._saved, "Apply commits current draft"
        )
        self.require(load() == self.controller._saved, "Apply persists the same configuration")

    def select_global(self, skin):
        saved_before = copy.deepcopy(self.controller._saved)
        self.click(self.find("nav_0"))
        picker = self.find("globalSkinPicker")
        if not picker.isVisible():
            self.click(self.find("desktopDefaultsToggle"))
        picker = self.find("globalSkinPicker")
        self.open_skin_picker(picker)
        self.click(self.find("skinOption_" + skin, picker))
        self.require(
            self.controller._draft["skin"] == skin, "Global thumbnail changes draft", skin=skin
        )
        self.require(
            self.controller._saved == saved_before,
            "Global thumbnail leaves saved settings unchanged before Apply",
        )
        self.apply()

    def select_widget(self, skin):
        saved_before = copy.deepcopy(self.controller._saved)
        self.window.selectWidget("w_target")
        self.settle()
        self.inline_style_ready()
        picker = self.find("widgetSkinPicker")
        self.open_skin_picker(picker)
        self.click(self.find("skinOption_" + (skin or "global"), picker))
        self.require(
            self.controller._draft["widgets"]["w_target"]["skin"] == skin,
            "Local thumbnail changes draft",
            skin=skin,
        )
        self.require(
            self.controller._saved == saved_before,
            "Local thumbnail leaves saved settings unchanged before Apply",
        )
        self.apply()

    def open_skin_picker(self, picker):
        """Open the actual compact chooser; options are intentionally lazy."""
        self.click(self.find("skinPickerChangeButton", picker))
        popup = self.find("skinPickerPopup", picker)
        self.require(popup.property("opened"), "Compact skin summary opens its chooser")

    def inline_style_ready(self):
        """Check the common page instead of clicking a removed inspector tab."""
        picker = self.find("widgetSkinPicker")
        self.require(
            self.window.property("page") == 0 and picker.isVisible() and picker.isEnabled(),
            "Selected widget exposes its skin controls on the common page",
        )
        self.require(
            all(
                self.find(name).isVisible() and self.find(name).isEnabled()
                for name in ("showTitleToggle", "widgetWidthInput", "widgetHeightInput")
            ),
            "Title and dimensions remain available beside the inline skin workflow",
        )
        apply = self.find("applyButton")
        point = apply.mapToScene(QPointF(apply.width() / 2, apply.height() / 2))
        self.require(
            apply.isVisible() and apply.isEnabled()
            and 0 <= point.x() < self.window.width()
            and 0 <= point.y() < self.window.height()
            and not any(
                item.objectName() == "widgetInspectorDrawer" and item.property("visible")
                for item in descendants(self.window.contentItem())
            ),
            "The single fixed Apply remains reachable without an inspector drawer",
        )

    def material(self, skin):
        config = self.controller._saved
        self.require(
            effective_skin(config, "w_target") == skin,
            "Effective skin resolves correctly",
            skin=skin,
        )
        material = self.runtime.composition["w_target"]
        request = next(
            entry
            for entry in reversed(self.report["widgetMaterialRequests"])
            if entry["report"] is material
        )
        self.require(
            type(request["enabled"]) is bool and request["enabled"] == (skin in GLASS_SKINS),
            "Runtime requests alpha coating only for glass skins",
            skin=skin,
            requested=request["enabled"],
            simulated=True,
        )
        self.require(
            material["coating_translucent"]
            is (skin in GLASS_SKINS and self.transparency_policy["enabled"]),
            "Widget alpha report honors skin and transparency policy",
            skin=skin,
            policyEnabled=self.transparency_policy["enabled"],
        )
        self.require(
            material["blur_configured"] is False,
            "Widget alpha report does not claim system blur",
        )
        self.require(
            material["compositing_verified"] is False,
            "Widget alpha report does not claim rendered verification",
        )

    def painted(self, name, *, coating=True):
        """Read actual HardwareCard painter output, independent of palette internals."""
        card = HardwareCard()
        card.setWidth(168)
        card.setHeight(168)
        card.setProperty("moduleKey", "w_target")
        card.setProperty("config", copy.deepcopy(self.controller._saved))
        card.setProperty("readings", dict(time=time.time(), cpu_usage=37.0, gpu_usage=21.0))
        card.setProperty("frosted", coating)
        image = QImage(168, 168, QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor("transparent"))
        painter = QPainter(image)
        try:
            card.paint(painter)
        finally:
            painter.end()
        path = ROOT / "qa-private" / f"customization-{name}.png"
        image.save(str(path))
        # Hero/no-chart fixture leaves these inner lower-body positions blank.
        alphas = [image.pixelColor(x, 145).alpha() for x in (30, 58, 83, 110, 135)]
        record = dict(
            name=name,
            path=str(path),
            backgroundAlphas=alphas,
            sha256=hashlib.sha256(bytes(image.constBits())).hexdigest(),
        )
        self.report["paintings"].append(record)
        card.deleteLater()
        return record

    def inheritance(self):
        self.material("card")
        self.select_global("glass")
        self.material("glass")
        self.select_widget("card")
        self.material("card")
        self.select_global("frost")
        self.material("card")
        self.require(
            self.controller._saved["skin"] == "frost",
            "Global skin remains independent of local override",
        )
        self.select_widget(None)
        self.material("frost")
        self.select_widget("glass")
        self.select_global("card")
        self.material("glass")
        saved_before = copy.deepcopy(self.controller._saved)
        self.click(self.find("useGlobalSkinButton"))
        self.require(
            all(prefs["skin"] is None for prefs in self.controller._draft["widgets"].values()),
            "Use global skin clears local overrides in draft",
        )
        self.require(
            self.controller._saved == saved_before,
            "Use global skin leaves saved overrides unchanged before Apply",
        )
        self.apply()
        self.material("card")

    def all_skins(self):
        self.require(
            set(SKINS) == {"glass", "frost", "tint", "card", "graphite", "minimal"},
            "Six expected skin identifiers are available",
        )
        hashes = []
        for skin in ("glass", "frost", "tint", "card", "graphite", "minimal"):
            self.select_global(skin)
            self.material(skin)
            record = self.painted(skin)
            hashes.append(record["sha256"])
            alpha = max(record["backgroundAlphas"])
            if skin in GLASS_SKINS:
                self.require(
                    0 < alpha < 220,
                    "Glass painter retains background transparency",
                    skin=skin,
                    alpha=alpha,
                )
            elif skin == "minimal":
                self.require(
                    alpha == 0,
                    "Minimal painter leaves blank background fully transparent",
                    alpha=alpha,
                )
            else:
                self.require(
                    alpha >= 240, "Solid painter has an opaque background", skin=skin, alpha=alpha
                )
        self.require(len(set(hashes)) == 6, "Six skins produce distinct actual paintings")
        self.select_global("glass")
        saved_before = copy.deepcopy(self.controller._saved)
        self.transparency_policy["enabled"] = False
        try:
            self.runtime.keep_below()
            self.settle()
            self.material("glass")
            self.require(
                self.runtime.composition["w_target"]["coating_allowed"] is False,
                "Disabled transparency policy denies widget alpha coating",
            )
            cards = [
                item
                for item in descendants(self.runtime.widgets["w_target"].contentItem())
                if isinstance(item, HardwareCard)
            ]
            self.require(
                len(cards) == 1 and cards[0].property("frosted") is False,
                "Actual widget card follows disabled transparency policy",
            )
            fallback = self.painted("policy-disabled", coating=False)
            self.require(
                min(fallback["backgroundAlphas"]) >= 240,
                "Disabled transparency policy has a readable solid painted fallback",
            )
            self.require(
                self.controller._saved == saved_before,
                "Transparency policy changes do not alter saved widget preferences",
            )
        finally:
            self.transparency_policy["enabled"] = True
            self.runtime.keep_below()
            self.settle()
        self.material("glass")

    def title(self):
        self.select_global("card")
        self.window.selectWidget("w_target")
        self.settle()
        self.inline_style_ready()
        toggle = self.find("showTitleToggle")
        self.require(toggle.property("checked") is True, "Title switch reflects default true")
        before = self.painted("title-on")
        self.click(toggle)
        self.require(
            self.controller._draft["widgets"]["w_target"]["show_title"] is False,
            "Actual title switch changes draft",
        )
        self.require(
            self.controller._saved["widgets"]["w_target"]["show_title"] is True,
            "Title change is pending until Apply",
        )
        self.apply()
        after = self.painted("title-off")
        self.require(
            before["sha256"] != after["sha256"], "Title switch changes actual card painting"
        )
        self.click(self.find("showTitleToggle"))
        self.apply()
        restored = self.painted("title-restored")
        self.require(
            restored["sha256"] == before["sha256"], "Re-enabling title restores identical painting"
        )

    def open_context(self, window, point):
        # Two independent context gestures must not become a platform double
        # click. This wait does not manipulate the OS cursor or foreground.
        QTest.qWait(QApplication.doubleClickInterval() + 80)
        self.context_source = window
        before = len(self.menu_requests)
        settings_before = len(self.settings_requests)
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, point)
        QTest.qWait(120)
        menu = getattr(self.runtime, "context_menu", None)
        self.require(
            isinstance(menu, QMenu) and menu.isVisible(),
            "Actual widget right-click opens its menu",
            requests=self.menu_requests[before:],
            settingsRequests=self.settings_requests[settings_before:],
            windowVisible=window.isVisible(),
        )
        self.require(
            all(not area["pressed"] for area in self.pressed_areas(window)),
            "Context menu opens only after the widget releases its mouse gesture",
            areas=self.pressed_areas(window),
        )
        return menu

    @staticmethod
    def pressed_areas(window):
        return [
            dict(name=item.objectName(), pressed=bool(item.property("pressed")))
            for item in descendants(window.contentItem())
            if item.metaObject().indexOfProperty("pressedButtons") >= 0
        ]

    def click_menu(self, menu, names):
        """Open submenus and activate actual QAction geometries with local Qt events."""
        current = menu
        retained_actions = []
        for index, name in enumerate(names):
            actions = current.actions()
            retained_actions.append(actions)
            action = next(
                (
                    action
                    for action in actions
                    if action.objectName() == name
                    or (action.menu() is not None and action.menu().objectName() == name)
                ),
                None,
            )
            self.require(action is not None, "Context action exists", action=name)
            self.require(action.isEnabled(), "Context action enabled", action=name)
            if index == len(names) - 1:
                QTest.mouseClick(
                    current, Qt.LeftButton, Qt.NoModifier, current.actionGeometry(action).center()
                )
            else:
                QTest.mouseClick(
                    current, Qt.LeftButton, Qt.NoModifier, current.actionGeometry(action).center()
                )
                QTest.qWait(100)
                child = action.menu()
                self.require(
                    child is not None and child.isVisible(),
                    "Context submenu opens by mouse",
                    action=name,
                )
                current = child
        QTest.qWait(120)
        if self.context_source is not None:
            self.require(
                all(not area["pressed"] for area in self.pressed_areas(self.context_source)),
                "Closing the context menu leaves no pressed widget mouse area",
                areas=self.pressed_areas(self.context_source),
            )
        self.settle()

    def quick_actions(self):
        self.controller.changeWidget("w_peer", "title", "Pending")
        before = copy.deepcopy(self.controller._saved)
        pending = copy.deepcopy(self.controller._draft)
        window = self.runtime.widgets["w_target"]
        point = QPoint(window.width() // 2, window.height() // 2)
        menu = self.open_context(window, point)
        self.click_menu(menu, ["menu_skin", "skin_glass"])
        expected = copy.deepcopy(before)
        expected["widgets"]["w_target"]["skin"] = "glass"
        expected_pending = copy.deepcopy(pending)
        expected_pending["widgets"]["w_target"]["skin"] = "glass"
        self.require(
            self.controller._saved == expected, "Quick skin saves only the selected property"
        )
        self.require(
            self.controller._draft == expected_pending,
            "Quick skin retains every unrelated pending draft",
        )
        self.require(load() == expected, "Quick skin persists only the selected property")
        menu = self.open_context(window, point)
        self.click_menu(menu, ["show_title"])
        expected["widgets"]["w_target"]["show_title"] = False
        expected_pending["widgets"]["w_target"]["show_title"] = False
        self.require(self.controller._saved == expected, "Quick title saves only title visibility")
        self.require(
            self.controller._draft == expected_pending, "Quick title retains pending edits"
        )
        self.controller.revert()

    def group_context(self):
        self.controller.change("mode", "combined")
        self.controller.apply()
        self.settle()
        group = self.runtime.widgets["group"]
        # The panel's outer gutter requests the combined menu; its cells request
        # their own per-widget menus, which must not affect their neighbors.
        menu = self.open_context(group, QPoint(4, 4))
        children = [action.menu() for action in menu.actions() if action.menu() is not None]
        self.require(len(children) == 2, "Combined menu includes both untitled members")
        self.require(
            all(child.isWindow() and child.windowType() == Qt.Popup for child in children),
            "Combined member menus retain Qt.Popup window type",
            flags=[int(child.windowFlags()) for child in children],
        )
        self.require(
            all(child.title() for child in children),
            "Combined menu gives untitled members a readable label",
        )
        cell = group.property("spec")["cells"][0]
        before = copy.deepcopy(self.controller._saved)
        self.click_menu(menu, ["widgetContextMenu", "menu_skin", "skin_graphite"])
        expected = copy.deepcopy(before)
        expected["widgets"][cell["key"]]["skin"] = "graphite"
        self.require(
            self.controller._saved == expected,
            "Combined panel member submenu changes only that member",
        )
        point = QPoint(round(cell["x"] + cell["width"] / 2), round(cell["y"] + cell["height"] / 2))
        before = copy.deepcopy(self.controller._saved)
        menu = self.open_context(group, point)
        self.click_menu(menu, ["show_title"])
        expected = copy.deepcopy(before)
        expected["widgets"][cell["key"]]["show_title"] = not before["widgets"][cell["key"]][
            "show_title"
        ]
        self.require(
            self.controller._saved == expected,
            "Combined cell context action changes only that member",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "qa-private/customization-qa-report.json"
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=("inheritance", "six-skins", "title", "quick-actions", "combined-context"),
        help="Run only selected workflows; the default runs all workflows.",
    )
    args = parser.parse_args()
    report = dict(
        platform="offscreen",
        selectedCases=args.case or "all",
        profile=str(PROFILE),
        checks=[],
        failures=[],
        qmlWarnings=[],
        paintings=[],
        nativeComposition="Settings composition simulated; widget alpha policy simulated; widget system blur is not configured or verified",
        widgetMaterialRequests=[],
        isolation=dict(
            hardwareSampling=False,
            windowsCompositionCalls=False,
            desktopZOrderCalls=False,
            installedAppIpc=False,
            systemTray=False,
            systemCursor=False,
            clipboard=False,
            foregroundActivation=False,
        ),
        source={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "native_runtime.py",
                "native_platform.py",
                "desktop_placement.py",
                "product_version.py",
                "native_controller.py",
                "configuration_scopes.py",
                "presets.py",
                "external_sensor.py",
                "native_card.py",
                "skin_styles.py",
                "native/Settings.qml",
                "native/SamplingControl.qml",
                "native/WindowChrome.qml",
                "native/Appearance.qml",
                "native/WidgetEditor.qml",
                "native/WidgetInspector.qml",
                "native/ContentCanvas.qml",
                "native/ContentLayoutEditor.qml",
                "native/Check.qml",
                "native/OptionTabs.qml",
                "native/SkinPicker.qml",
                "native/ValueSlider.qml",
                "native/Theme.qml",
                "native/DesktopWidget.qml",
                "native/Preview.qml",
                "native/WidgetPreview.qml",
                "native/Gallery.qml",
                "native/FrostedBackdrop.qml",
                "native_surface.py",
                "material_policy.py",
                "card_layout.py",
                "responsive_layout.py",
                "layout_assist.py",
                "localization.py",
                "locales.txt",
                "tools/verify_customization.py",
            )
        },
    )
    save(fixture())
    QQuickWindow.setDefaultAlphaBuffer(True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    assert app.platformName() == "offscreen", "Refusing to create foreground/native test windows"
    report["fonts"] = load_system_fonts()
    if not report["fonts"]["passed"]:
        report["failures"].append(dict(case="fonts", details=report["fonts"]["checks"]))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(dict(failures=report["failures"], report=str(args.report))))
        return 1
    with ExitStack() as stack:
        transparency_policy = {"enabled": True}
        original_warnings = native_runtime.Runtime.qml_warnings

        def record_warnings(runtime, warnings):
            report["qmlWarnings"].extend(warning.toString() for warning in warnings)
            original_warnings(runtime, warnings)

        stack.enter_context(patch.object(native_runtime.Runtime, "qml_warnings", record_warnings))
        stack.enter_context(patch.object(Controller, "start", return_value=None))
        stack.enter_context(patch.object(Controller, "inspect", return_value=None))
        stack.enter_context(
            patch.object(
                native_runtime,
                "transparency_enabled",
                side_effect=lambda: transparency_policy["enabled"],
            )
        )
        stack.enter_context(patch.object(native_runtime, "desktop_level", return_value=None))
        stack.enter_context(patch.object(native_runtime, "animations_enabled", return_value=False))
        stack.enter_context(patch.object(native_runtime, "QCursor", LocalCursor))

        def simulated_glass(hwnd, dark=False, enabled=True):
            return dict(
                material="desktop-acrylic" if enabled else "solid",
                enabled=enabled,
                simulated=True,
                dark=dark,
                native_observed=False,
            )

        def simulated_widget_material(enabled=True):
            allowed = transparency_policy["enabled"]
            translucent = bool(enabled and allowed)
            result = dict(
                coating_allowed=allowed,
                coating_translucent=translucent,
                material="translucent" if translucent else "solid",
                blur_configured=False,
                compositing_verified=False,
                status="translucent" if translucent else "fallback",
            )
            if not translucent:
                result["fallback_reason"] = (
                    "transparency-disabled" if enabled else "material-disabled"
                )
            report["widgetMaterialRequests"].append(dict(enabled=enabled, report=result))
            return result

        stack.enter_context(patch.object(native_runtime, "glass", simulated_glass))
        stack.enter_context(
            patch.object(native_runtime, "widget_material", simulated_widget_material)
        )
        runtime = native_runtime.Runtime(app, background=True, headless=True)
        runtime.headless = False
        runtime.apply(False)
        runtime.floor_timer.stop()
        runtime.stale_timer.stop()
        runtime.settings.resize(1160, 790)
        runtime.settings.show()

        audit = Audit(runtime, report, transparency_policy)

        def execute():
            try:
                audit.settle()
                for name, callback in (
                    ("inheritance", audit.inheritance),
                    ("six-skins", audit.all_skins),
                    ("title", audit.title),
                    ("quick-actions", audit.quick_actions),
                    ("combined-context", audit.group_context),
                ):
                    if not args.case or name in args.case:
                        audit.run(name, callback)
                if report["qmlWarnings"]:
                    report["failures"].append(dict(case="qml", warnings=report["qmlWarnings"]))
            except Exception:
                report["failures"].append(dict(case="setup", traceback=traceback.format_exc()))
            finally:
                runtime.shutdown()
                runtime.settings.hide()
                app.quit()

        QTimer.singleShot(250, execute)
        app.exec()
        # Destroy QML before its context Controller; otherwise Python's shutdown
        # order can emit misleading `stats is null` diagnostics after the audit.
        for window in [*runtime.widgets.values(), runtime.settings]:
            window.deleteLater()
        runtime.widgets.clear()
        runtime.component.deleteLater()
        runtime.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report["sourceAfter"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in report["source"]
    }
    report["sourceStable"] = report["source"] == report["sourceAfter"]
    if not report["sourceStable"]:
        report["failures"].append(dict(case="source", error="Source changed during the audit"))
    report["passed"] = sum(item["passed"] for item in report["checks"])
    report["total"] = len(report["checks"])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            dict(
                passed=report["passed"],
                total=report["total"],
                failures=report["failures"],
                report=str(args.report),
                platform=app.platformName(),
            ),
            ensure_ascii=False,
        )
    )
    return int(bool(report["failures"]))


if __name__ == "__main__":
    raise SystemExit(main())
