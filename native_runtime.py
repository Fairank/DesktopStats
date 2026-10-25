"""Native desktop windows, tray, settings and local single-instance dispatch."""

import ctypes as c
import json
import logging
import math
import os
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, QVariantAnimation
from PySide6.QtGui import QActionGroup, QCursor, QIcon
from PySide6.QtNetwork import QLocalServer
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, qmlRegisterType
from PySide6.QtWidgets import QSystemTrayIcon

from appearance_preview import project_appearance
from desktop_placement import desktop_plan
from localization import best_language, translate
from magnet_layout import contained, separated, settle
from material_policy import render_policy
from metrics import metric_info
from modern_menu import ModernMenu as QMenu
from modern_menu import set_action_icon
from native_card import HardwareCard, primary_metric
from native_controller import Controller
from native_glass import NativeFrameBridge, widget_flags
from native_ipc import name
from native_layout import (
    LayoutCapacityError,
    fit,
    read_positions,
    write_positions,
)
from native_platform import (
    animations_enabled,
    desktop_below,
    desktop_level,
    glass,
    pinned_level,
    transparency_enabled,
    transparency_policy,
    widget_material,
)
from native_surface import MaterialSurface
from native_widget_material import WidgetBlurBackend
from responsive_layout import ResponsiveLayoutError, is_responsive
from settings_acrylic_material import SettingsAcrylicMaterial
from settings_backdrop_host import SettingsBackdropHost
from settings_blur_material import SettingsBlurMaterial
from settings_material_bridge import SettingsMaterialBridge
from stats_config import ASSETS, CONFIG, MODULES, SKINS, load
from top_bar_runtime import TopBarManager
from widget_catalog import TEMPLATES
from widget_material_geometry import backdrop_shapes, rounded_mask


class Runtime(QObject):
    def __init__(self, application, background=False, headless=False):
        super().__init__()
        self.app = application
        self.headless = headless
        self.positions = read_positions()
        self.widgets = {}
        self.motion = {}
        self.drag_origins = {}
        self.composition = {}
        self.widget_blur = (
            None if headless or application.platformName() != "windows" else WidgetBlurBackend()
        )
        self.widget_materials = {}
        self._widget_appearance_config = {}
        self._widget_native_options = {}
        self._widget_mask_states = {}
        self._widget_mask_pending = set()
        self.widget_mask_timer = QTimer(self)
        self.widget_mask_timer.setSingleShot(True)
        self.widget_mask_timer.setInterval(16)
        self.widget_mask_timer.timeout.connect(self.update_widget_masks)
        self.watched_screens = set()
        self.shutting_down = False
        self.transparency = transparency_enabled()
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.setInterval(450)
        self.position_timer.timeout.connect(self.save_positions)
        self.controller = Controller()
        self.controller.set_motion_enabled(not headless and animations_enabled())
        self.frame_bridge = (
            None
            if headless
            else NativeFrameBridge(
                application, on_enter=self.begin_move, on_exit=self.queue_end_move
            )
        )
        screen = self.app.primaryScreen().availableGeometry()
        self.controller.set_preview_area(screen.width(), screen.height())
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
        self.engine = QQmlApplicationEngine()
        self.engine.warnings.connect(self.qml_warnings)
        self.engine.rootContext().setContextProperty("stats", self.controller)
        self.engine.load(QUrl.fromLocalFile(str(ASSETS / "native/Settings.qml")))
        if not self.engine.rootObjects():
            raise RuntimeError("Native settings could not load")
        self.settings = self.engine.rootObjects()[0]
        self.settings.setIcon(application.windowIcon())
        self.settings_theme = self.controller._draft["theme"]
        self.controller.draftChanged.connect(self.settings_draft_changed)
        self.settings.setPersistentGraphics(True)
        self.settings.setPersistentSceneGraph(True)
        self.settings_host = (SettingsBackdropHost(self.settings)
                              if not headless and application.platformName() == "windows" else None)
        self.settings_blur = (SettingsAcrylicMaterial() if self.settings_host is not None
                              else SettingsBlurMaterial()
                              if not headless and application.platformName() == "windows" else None)
        self.settings_material = None if headless else SettingsMaterialBridge(
            Runtime._settings_window(self), self,
            backend="desktop-acrylic" if self.settings_host is not None else "system-blur",
            frame_source=self.settings if self.settings_host is not None else None,
            allow_hidden_prepare=self.settings_host is not None,
            wait_for_first_frame=True, activation_requests=self.settings_host is not None,
            compose_once=self._settings_material_request,
            policy_reader=transparency_policy,
            publish=self._publish_settings_material,
            release_surface=self._release_settings_surface,
        )
        if self.settings_material:
            self.settings_material.start()
        if self.settings_host:
            self.settings_host.paintFailed.connect(self._settings_paint_failed)
        self.component = QQmlComponent(
            self.engine, QUrl.fromLocalFile(str(ASSETS / "native/DesktopWidget.qml"))
        )
        if self.component.isError():
            raise RuntimeError("; ".join(error.toString() for error in self.component.errors()))
        self.settings.visibleChanged.connect(self.refresh_appearance)
        self.top_bar = TopBarManager(self)
        self.controller.applyRequested.connect(self.apply)
        self.controller.topBarApplyRequested.connect(self.apply_top_bar)
        self.controller.settingsRequested.connect(self.show_settings)
        self.controller.positionChanged.connect(self.position)
        self.controller.moveStarted.connect(self.begin_move)
        self.controller.moveFinished.connect(self.queue_end_move)
        self.controller.menuRequested.connect(self.widget_menu)
        self.controller.windowCloseRequested.connect(self.queue_window_close)
        self.controller.detailsRequested.connect(self.show_details)
        self.controller.quitRequested.connect(self.app.quit)
        self.controller.dataChanged.connect(self.first_reading)
        self.tray = None
        if not headless:
            self.tray = QSystemTrayIcon(QIcon(str(ASSETS / "assets/icon.ico")), self)
            self.tray.setToolTip("Desktop Stats")
            self.tray.activated.connect(
                lambda reason: (
                    self.show_settings("")
                    if reason
                    in (
                        QSystemTrayIcon.ActivationReason.Trigger,
                        QSystemTrayIcon.ActivationReason.DoubleClick,
                    )
                    else None
                )
            )
            self.update_menu()
            self.tray.show()
            self.apply(False)
            if not background:
                QTimer.singleShot(80, lambda: self.show_settings(""))
        self.app.aboutToQuit.connect(self.shutdown)
        self.app.screenAdded.connect(self.screen_added)
        self.app.screenRemoved.connect(self.screen_removed)
        self.app.primaryScreenChanged.connect(lambda *args: self.fit_windows())
        for screen in self.app.screens():
            self.watch_screen(screen)
        self.floor_timer = QTimer(self)
        self.floor_timer.setInterval(4000)
        self.floor_timer.timeout.connect(self.keep_below)
        self.floor_timer.start()
        self.stale_timer = QTimer(self)
        self.stale_timer.setInterval(5000)
        self.stale_timer.timeout.connect(self.clear_stale)
        self.stale_timer.start()
        self.controller.start()

    def qml_warnings(self, warnings):
        for warning in warnings:
            logging.warning("Native interface: %s", warning.toString())

    def settings_draft_changed(self):
        theme = self.controller._draft["theme"]
        if theme != self.settings_theme:
            self.settings_theme = theme
            if self.settings.isVisible():
                self.compose(self.settings, "settings")
        self.refresh_appearance()

    def refresh_appearance(self):
        """Preview coatings on existing windows without committing other edits.

        No window creation, positioning, resizing, flags, sampling or file writes
        occur here. Hiding settings restores the last saved appearance.
        """
        if self.headless or self.shutting_down:
            return
        config = project_appearance(
            self.controller._saved, self.controller._draft, self.settings.isVisible()
        )
        previous = getattr(self, "_appearance_states", {})
        states = {}
        for key, window in self.widgets.items():
            spec = getattr(self, "_spec_by_id", {}).get(key)
            if spec is None:
                continue
            policy = render_policy(config, spec)
            state = (window, config, policy)
            states[key] = state
            if previous.get(key) == state:
                continue
            window.setProperty("appearanceConfig", config)
            window.setProperty("appearancePolicy", policy)
            materials = getattr(self, "widget_materials", {})
            if key in materials:
                self._widget_appearance_config[key] = config
                # Opacity only changes the coating. Curvature only changes its
                # footprint; neither should continuously reconfigure the OS blur.
                options = (policy["backdrop"], config.get("theme"))
                if self._widget_native_options.get(key) != options:
                    self._widget_native_options[key] = options
                    materials[key].request("preference_changed")
                allowed = self.composition.get(key, {}).get("coating_allowed", self.transparency)
                report = dict(self.composition.get(key, {}))
                report.update(coating_allowed=allowed,
                              coating_translucent=allowed and policy["translucent"])
                self.composition[key] = report
                window.setProperty("composition", report)
                self.queue_widget_mask(key)
                continue
            # The alpha permission changes when minimal digits become glass.
            # This is only a painter policy; no native placement or blur calls.
            previous_report = self.composition.get(key, {})
            report = widget_material(policy["translucent"])
            policy_fields = {
                "material", "coating_allowed", "coating_translucent", "blur_configured",
                "compositing_verified", "status", "fallback_reason",
            }
            for field, value in previous_report.items():
                if field not in policy_fields:
                    report.setdefault(field, value)
            self.composition[key] = report
            window.setProperty("composition", report)
        self._appearance_states = states
        self.controller.set_window_materials(self.composition)

    def first_reading(self):
        if CONFIG.exists():
            return
        config = load()
        language = c.create_unicode_buffer(85)
        if c.windll.kernel32.GetUserDefaultLocaleName(language, 85):
            config["language"] = best_language(language.value)
        config["skin"] = "glass"
        data = self.controller._data
        if data.get("cpu_temp") is None:
            config["widgets"]["cpu"].update(primary="usage", secondary="cores")
        if data.get("gpu_temp") is None and data.get("gpu_usage") is None:
            config["widgets"]["gpu"]["enabled"] = False
        if not data.get("battery_present"):
            config["widgets"]["battery"]["enabled"] = False
        self.controller.edit(config)
        self.controller.apply()

    def clear_stale(self):
        self.controller.expire_readings()

    def update_menu(self):
        if not self.tray:
            return
        old = self.tray.contextMenu()
        config = self.controller._saved
        menu = QMenu(theme=config["theme"], language=config["language"])

        def tr(text):
            return translate(text, self.controller._saved["language"])

        action = menu.addAction(tr("组件设置"))
        set_action_icon(action, "layout-grid")
        action.triggered.connect(lambda: self.show_settings(""))
        action = menu.addAction(tr("顶部状态栏设置"))
        set_action_icon(action, "sliders-horizontal")
        action.triggered.connect(self.create_status_bar)
        action = menu.addAction(tr("顶部状态栏详情"))
        set_action_icon(action, "activity")
        action.setEnabled(self.controller._saved.get("top_bar", {}).get("enabled", False))
        action.triggered.connect(lambda: self.top_bar.focus_details())
        menu.addSeparator()
        for field, label in (("visible", "显示桌面组件"), ("locked", "锁定位置")):
            action = menu.addAction(tr(label))
            action.setCheckable(True)
            action.setChecked(self.controller._saved[field])
            action.triggered.connect(
                lambda checked=False, selected=field: self.controller.quick(selected)
            )
        menu.addSeparator()
        action = menu.addAction(tr("退出"))
        set_action_icon(action, "x")
        action.triggered.connect(self.app.quit)
        self.tray.setContextMenu(menu)
        self.tray_menu = menu
        if old:
            old.deleteLater()

    def build_widget_menu(self, key):
        config = self.controller._saved
        menu = QMenu(theme=config["theme"], language=config["language"])
        menu.setObjectName("widgetContextMenu")

        def tr(text):
            return translate(text, config["language"])

        if key == "group":
            action = menu.addAction(tr("组合面板设置"))
            set_action_icon(action, "sliders-horizontal")
            action.triggered.connect(lambda: self.show_settings(""))
            spec = self.widgets[key].property("spec")
            if hasattr(spec, "toVariant"):
                spec = spec.toVariant()
            for cell in spec["cells"]:
                child = self.build_widget_menu(cell["key"])
                prefs = config["widgets"][cell["key"]]
                child.setParent(menu, child.windowFlags())
                child.setTitle(
                    prefs["title"]
                    or tr(TEMPLATES.get(prefs.get("template"), MODULES[prefs["kind"]])["label"])
                )
                menu.addMenu(child)
        elif key in config["widgets"]:
            prefs = config["widgets"][key]
            edit = menu.addAction(tr("编辑内容与布局"))
            edit.setObjectName("edit_widget")
            set_action_icon(edit, "sliders-horizontal")
            edit.triggered.connect(lambda: self.show_settings(key))
            menu.addSeparator()
            title = menu.addAction(tr("显示标题"))
            title.setObjectName("show_title")
            title.setCheckable(True)
            title.setChecked(prefs.get("show_title", True))
            title.triggered.connect(
                lambda checked: self.controller.quickWidget(key, "show_title", checked)
            )

            def choices(label, field, options, current):
                sub = menu.addMenu(tr(label))
                sub.setObjectName("menu_" + field)
                selected_label = next((text for value, text in options if value == current), "")
                sub.menuAction().setProperty("menuHint", tr(selected_label))
                group = QActionGroup(sub)
                group.setExclusive(True)
                for value, text in options:
                    action = sub.addAction(tr(text))
                    action.setObjectName(field + "_" + ("global" if value is None else str(value)))
                    action.setData(value)
                    action.setCheckable(True)
                    action.setChecked(current == value)
                    group.addAction(action)
                    action.triggered.connect(
                        lambda checked=False, selected=value: self.controller.quickWidget(
                            key, field, selected
                        )
                    )
                return sub

            choices("组件皮肤", "skin", [(None, "跟随全局"), *SKINS.items()], prefs["skin"])
            if not is_responsive(prefs):
                choices(
                    "单独尺寸",
                    "size",
                    [
                        (None, "跟随全局"),
                        (76, "小号"),
                        (112, "中号"),
                        (148, "大号"),
                        (180, "特大号"),
                    ],
                    prefs["size"],
                )
            choices(
                "卡片比例",
                "form",
                [("square", "方形"), ("wide", "宽卡片"), ("free", "自由尺寸"), ("bar", "状态条")],
                prefs["form"],
            )
            choices("放置位置", "dock", [("free", "自由放置"), ("top", "屏幕顶部")], prefs["dock"])
            choices(
                "窗口层级",
                "layer",
                [("desktop", "仅在桌面"), ("pinned", "始终置顶")],
                prefs["layer"],
            )
            styles = [("auto", "自动"), ("hero", "大数字"), ("list", "详细列表")]
            first = (prefs.get("content") or [primary_metric(prefs["kind"], prefs)])[0]
            if metric_info(first, prefs)["unit"] == "%":
                styles += [("ring", "圆环"), ("bar", "进度条")]
            if prefs["kind"] == "cpu":
                styles += [("cores", "每核负载")]
            choices("信息样式", "presentation", styles, prefs["presentation"])
            graph = menu.addAction(tr("显示图表"))
            graph.setObjectName("show_chart")
            graph.setCheckable(True)
            graph.setChecked(prefs["chart"])
            graph.setEnabled(
                prefs["presentation"] == "auto" and len(prefs.get("content") or []) <= 2
            )
            graph.triggered.connect(
                lambda checked: self.controller.quickWidget(key, "chart", checked)
            )
            menu.addSeparator()
            hide = menu.addAction(tr("隐藏此组件"))
            hide.setObjectName("hide_widget")
            set_action_icon(hide, "x")
            hide.triggered.connect(lambda: self.controller.quickWidget(key, "enabled", False))
        menu.addSeparator()
        action = menu.addAction(tr("锁定桌面位置"))
        action.setObjectName("lock_all_widgets")
        action.setCheckable(True)
        action.setChecked(self.controller._saved["locked"])
        action.triggered.connect(lambda: self.controller.quick("locked"))
        action = menu.addAction(tr("显示桌面组件"))
        action.setObjectName("show_all_widgets")
        action.setCheckable(True)
        action.setChecked(self.controller._saved["visible"])
        action.triggered.connect(lambda: self.controller.quick("visible"))
        return menu

    def widget_menu(self, key):
        old = getattr(self, "context_menu", None)
        if old:
            old.close()
        menu = self.build_widget_menu(key)
        self.context_menu = menu

        def release():
            if self.context_menu is menu:
                self.context_menu = None
            menu.deleteLater()

        menu.aboutToHide.connect(release)
        menu.popup(QCursor.pos())

    def queue_window_close(self, key):
        """Hide the exact owned window transactionally after its close event."""
        window = self.widgets.get(key)
        if window is None or self.shutting_down:
            return

        def commit():
            if not self.shutting_down and self.widgets.get(key) is window:
                self.controller.hideWindow(key)

        QTimer.singleShot(0, commit)

    def compose(self, window, key, enabled=True):
        bridge = getattr(self, "settings_material", None)
        if key == "settings" and bridge is not None:
            return bridge.compose_now("explicit")
        widget_bridge = getattr(self, "widget_materials", {}).get(key)
        if key != "settings" and widget_bridge is not None:
            report = widget_bridge.compose_now("explicit") or self.composition.get(key, {})
            Runtime._place_widget(self, window, key, report)
            return report
        theme = (
            self.controller._draft["theme"]
            if key == "settings"
            else self.controller._saved["theme"]
        )
        try:
            report = (
                glass(int(window.winId()), theme == "dark", enabled)
                if key == "settings"
                else widget_material(enabled)
            )
        except (OSError, AttributeError) as error:
            logging.warning("Native glass is unavailable; using a solid surface", exc_info=True)
            report = {
                "material": "solid",
                "coating_allowed": False,
                "coating_translucent": False,
                "blur_configured": False,
                "compositing_verified": False,
                "backend_error": str(error),
            }
        report["renderer"] = window.rendererInterface().graphicsApi().name
        bridge = getattr(self, "frame_bridge", None)
        if bridge and key in bridge.reports:
            report["native_frame"] = dict(bridge.reports[key])
        self.composition[key] = report
        if key != "settings":
            window.setProperty("composition", report)
        if key == "settings" or "settings" not in self.composition:
            self.controller.set_material(report)
        if key != "settings":
            Runtime._place_widget(self, window, key, report)
        self.controller.set_window_materials(self.composition)
        return report

    def _place_widget(self, window, key, report):
        try:
            if getattr(self, "_spec_by_id", {}).get(key, {}).get("layer") == "pinned":
                pinned_level(int(window.winId()))
            else:
                desktop_level(int(window.winId()))
        except (OSError, AttributeError) as error:
            logging.warning("Native desktop placement is unavailable", exc_info=True)
            report["desktop_level_error"] = str(error)

    def _widget_material_request(self, key, window, handle, policy):
        config = self._widget_appearance_config.get(key, self.controller._saved)
        spec = self._spec_by_id[key]
        surface = render_policy(config, spec)
        self._widget_native_options[key] = (surface["backdrop"], config.get("theme"))
        if surface["backdrop"] and policy.get("state") == "allowed":
            shapes = backdrop_shapes(config, spec, window.width(), window.height())
            state = (window, shapes)
            if self._widget_mask_states.get(key) != state:
                window.setMask(rounded_mask(shapes))
                self._widget_mask_states[key] = state
        report = self.widget_blur.apply(handle, enabled=surface["backdrop"], policy=policy)
        allowed = policy.get("state") == "allowed"
        # Mixed bare digits keep their unpainted background. Their glass peers
        # retain ordinary alpha without giving the whole group a native backdrop.
        report.update(coating_allowed=allowed,
                      coating_translucent=allowed and surface["translucent"],
                      renderer=window.rendererInterface().graphicsApi().name)
        if surface["fallback_reason"]:
            report["surface_fallback_reason"] = surface["fallback_reason"]
        return report

    def _publish_widget_material(self, key, window, report):
        if self.shutting_down or self.widgets.get(key) is not window:
            return
        self.composition[key] = report
        window.setProperty("composition", report)
        self.controller.set_window_materials(self.composition)
        self.queue_widget_mask(key)

    def _release_widget_surface(self, key, handle):
        result = self.widget_blur.clear(handle)
        if not result.get("ok", False):
            logging.warning("Widget material release failed for %s: %s", key, result)
        self._widget_mask_states.pop(key, None)
        return result

    def ensure_widget_material(self, key, window):
        if key in self.widget_materials or self.widget_blur is None:
            return
        bridge = SettingsMaterialBridge(
            window, self, backend="system-blur",
            compose_once=lambda handle, policy: self._widget_material_request(key, window, handle, policy),
            policy_reader=transparency_policy,
            publish=lambda report: self._publish_widget_material(key, window, report),
            release_surface=lambda handle: self._release_widget_surface(key, handle),
        )
        self.widget_materials[key] = bridge
        window.widthChanged.connect(lambda *_args: self.queue_widget_mask(key))
        window.heightChanged.connect(lambda *_args: self.queue_widget_mask(key))
        bridge.start()

    def queue_widget_mask(self, key):
        if self.shutting_down or key not in self.widgets:
            return
        self._widget_mask_pending.add(key)
        if not self.widget_mask_timer.isActive():
            self.widget_mask_timer.start()

    def update_widget_masks(self):
        keys, self._widget_mask_pending = self._widget_mask_pending, set()
        for key in keys:
            window = self.widgets.get(key)
            spec = getattr(self, "_spec_by_id", {}).get(key)
            if window is None or spec is None or self.shutting_down:
                continue
            config = self._widget_appearance_config.get(key, self.controller._saved)
            report = self.composition.get(key, {})
            if report.get("blur_may_remain") and not report.get("blur_configured"):
                # Failed removal must not expand an old blur to the whole HWND.
                # Keep its last footprint until a bounded retry confirms clear.
                continue
            shapes = (backdrop_shapes(config, spec, window.width(), window.height())
                      if report.get("blur_configured") else ())
            state = (window, shapes)
            if self._widget_mask_states.get(key) == state:
                continue
            window.setMask(rounded_mask(shapes))
            self._widget_mask_states[key] = state

    def _settings_material_request(self, handle, policy):
        """Read/request only; the lifecycle bridge guards publication by generation."""
        context = self.settings_material.status()
        serial = context["surface_serial"]
        epoch = context.get("render_epoch")
        preparation = context.get("preparation_token") if context.get("preparing_hidden") else None
        report = (self.settings_blur.apply(handle, policy, surface_id=serial,
                                          valid=lambda: self._settings_surface_current(
                                              handle, serial, frame_epoch=epoch, preparation_token=preparation))
                  if self.settings_blur is not None
                  else dict(material="solid", status="fallback", fallback_reason="native-platform-unavailable",
                            coating_allowed=False, coating_translucent=False, blur_configured=False,
                            compositing_verified=False))
        host = getattr(self, "settings_host", None)
        if host is not None:
            if report.get("ok") and report.get("coating_translucent") and not host.paint_background():
                cleanup = self.settings_blur.clear(handle, surface_id=serial,
                    valid=lambda: self._settings_surface_current(handle, serial, releasing=True))
                report.update(material="solid", status="fallback", ok=False,
                    coating_allowed=False, coating_translucent=False,
                    fallback_reason="native-background-paint-failed", cleanup=cleanup)
            report["presentation_host"] = host.status()
        report["renderer"] = self.settings.rendererInterface().graphicsApi().name
        return report

    def _settings_window(self):
        """Global native geometry/state; settings remains the Quick editor."""
        return getattr(self, "settings_host", None) or self.settings

    def _settings_paint_failed(self, reason):
        if not self.shutting_down:
            self._publish_settings_material(dict(material="solid", status="fallback", ok=False,
                coating_allowed=False, coating_translucent=False,
                fallback_reason="native-background-paint-failed", backend_error=reason,
                compositing_verified=False))

    def _release_settings_surface(self, handle):
        if self.settings_blur is None:
            return dict(ok=True, noop=True, cleanup_complete=True)
        serial = self.settings_material.status()["surface_serial"]
        result = self.settings_blur.clear(handle, surface_id=serial,
            valid=lambda: self._settings_surface_current(handle, serial, releasing=True))
        if not self.shutting_down:
            self._publish_settings_material(dict(material="solid", status="waiting-for-surface",
                coating_allowed=False, coating_translucent=False, blur_configured=False,
                compositing_verified=False))
        return result

    def _settings_surface_current(self, handle, serial, *, releasing=False, frame_epoch=None,
                                  preparation_token=None):
        bridge = getattr(self, "settings_material", None)
        if bridge is None:
            return False
        context = bridge.status()
        current = (context["surface_alive"] and context["surface_handle"] == handle
                   and context["surface_serial"] == serial)
        window = Runtime._settings_window(self)
        if preparation_token is not None:
            host = getattr(self, "settings_host", None)
            return bool(current and host is window and host is not None
                        and not self.shutting_down and not context["closed"]
                        and not host.status().get("disposed")
                        and context.get("frame_source_alive")
                        and self.settings.parent() is host
                        and bridge.hidden_preparation_current(handle, serial, preparation_token))
        return bool(current and (releasing or not self.shutting_down and not context["closed"]
                                 and context.get("frame_source_alive", True)
                                 and context.get("render_ready", True)
                                 and (frame_epoch is None or context.get("render_epoch") == frame_epoch)
                                 and window.isVisible() and self.settings.isVisible()
                                 and not window.windowState() & Qt.WindowMinimized))

    def _publish_settings_material(self, report):
        self.composition["settings"] = report
        self.controller.set_material(report)
        self.controller.set_window_materials(self.composition)

    def show_settings(self, key=""):
        host = getattr(self, "settings_host", None)
        settings = self.settings

        def current():
            return (not self.shutting_down and self.settings is settings
                    and getattr(self, "settings_host", None) is host
                    and (host is None or not host.status().get("disposed")))

        if not current():
            return  # A queued tray/IPC request must not recreate a released host.
        if key == "__top_bar__":
            self.settings.setProperty("page", 3)
        elif key == "__history__":
            self.settings.setProperty("page", 4)
        elif key.startswith("__history__:"):
            self.settings.selectHistory(key.partition(":")[2])
        elif key:
            self.settings.selectWidget(key)
        if not current():
            return
        self.controller.inspect()
        if not current():
            return
        window = Runtime._settings_window(self)
        available = [screen.availableGeometry() for screen in self.app.screens()]
        if getattr(self, "settings_host", None) is not None:
            # The user's existing Show action may create the native host. Its
            # actual frame margins then keep the caption inside the work area.
            window.create()
            if not current():
                return
            margins = window.frameMargins()
            screen = self.app.primaryScreen().availableGeometry()
            if not window.isVisible():
                window.resize(min(1280, screen.width()-48-margins.left()-margins.right()),
                              min(640, screen.height()-48-margins.top()-margins.bottom()))
                if not current():
                    return
                frame = window.frameGeometry()
                window.setFramePosition(QPoint(screen.x()+(screen.width()-frame.width())//2,
                                               screen.y()+(screen.height()-frame.height())//2))
                if not current():
                    return
            frame = window.frameGeometry()
            x, y = fit(frame.x(), frame.y(), frame.width(), frame.height(), available)
            window.setFramePosition(QPoint(x, y))
            if not current():
                return
        elif not self.settings.isVisible():
            screen = self.app.primaryScreen().availableGeometry()
            self.settings.resize(min(1280, screen.width() - 48), min(640, screen.height() - 48))
            if not current():
                return
            self.settings.setPosition(
                screen.x() + (screen.width() - self.settings.width()) // 2,
                screen.y() + (screen.height() - self.settings.height()) // 2,
            )
            if not current():
                return
        if getattr(self, "settings_host", None) is None:
            x, y = fit(window.x(), window.y(), window.width(), window.height(), available)
            window.setPosition(x, y)
        elif not window.isVisible():
            # Only this explicit own-window Show path prepares the already
            # created Raster owner. The generic Quick first-frame gate stays
            # intact. The bridge also owns cleanup if Show is never reached.
            bridge = self.settings_material
            prepared = bridge.prepare_hidden() if bridge is not None else None
            if (prepared is None or self.shutting_down or self.settings_material is not bridge
                    or getattr(self, "settings_host", None) is not window
                    or bridge.status()["closed"] or window.status().get("disposed")):
                return
        if not current():
            return
        window.showNormal()
        if not current():
            return
        self.compose(self.settings, "settings")
        if not current():
            return
        window.raise_()
        if not current():
            return
        window.requestActivate()

    def apply_top_bar(self):
        """A bar-only commit does not recreate widgets or discard editor drafts."""
        self.top_bar.apply(self.controller._saved)
        self.update_menu()

    def apply(self, rearrange=False):
        if getattr(self, "top_bar", None) is not None:
            self.top_bar.apply(self.controller._saved)
        if self.headless:
            return
        config = self.controller._saved
        self.controller.set_motion_enabled(animations_enabled())
        for key in list(self.motion):
            self.cancel_motion(key)
        self.drag_origins.clear()
        screen = self.app.primaryScreen().availableGeometry()
        screens = self.screen_inventory()
        self.controller.set_preview_area(screen.width(), screen.height())
        self.controller.set_screen_inventory(screens, self.positions)
        try:
            specs, points = desktop_plan(config, screens, self.positions, bool(rearrange))
        except (LayoutCapacityError, ResponsiveLayoutError):
            self.controller.set_status("桌面空间不足，请减少显示的组件或调整布局。")
            return
        self._spec_by_id = {spec["id"]: spec for spec in specs}
        self._planned_points = points
        for spec in specs:
            spec["material_policy"] = render_policy(config, spec)
        active = {spec["id"] for spec in specs}
        for key in list(self.widgets):
            if key not in active:
                window = self.widgets.pop(key)
                window.hide()
                material = self.widget_materials.pop(key, None)
                if material:
                    material.close()
                    material.deleteLater()
                self._widget_appearance_config.pop(key, None)
                self._widget_native_options.pop(key, None)
                self._widget_mask_states.pop(key, None)
                if self.frame_bridge:
                    self.frame_bridge.unregister(window)
                window.deleteLater()
                self.composition.pop(key, None)
        for spec in specs:
            key = spec["id"]
            window = self.widgets.get(key)
            # Keep the known alpha/layered presentation used by minimal digits.
            # DWM type 3 on the nonlayered, nonactivating Quick path was never
            # visually accepted and can replace transparency with a solid tint.
            native_frame = False
            desired_flags = int(widget_flags(native_frame))
            if spec.get("layer") == "pinned":
                from PySide6.QtCore import Qt

                desired_flags = int(
                    (widget_flags(native_frame) & ~Qt.WindowStaysOnBottomHint)
                    | Qt.WindowStaysOnTopHint
                )
            setup_frame = window is None or int(window.flags()) != desired_flags
            if window:
                window.setProperty("registered", False)
                if setup_frame:
                    window.hide()
                    material = self.widget_materials.pop(key, None)
                    if material:
                        material.close()
                        material.deleteLater()
                    if self.frame_bridge:
                        self.frame_bridge.unregister(window)
                    window.setProperty("nativeFlags", desired_flags)
                window.setProperty("spec", spec)
                window.resize(spec["width"], spec["height"])
            else:
                window = self.component.createWithInitialProperties(
                    {"spec": spec, "nativeFlags": desired_flags}
                )
                if not window:
                    raise RuntimeError("Native widget could not load")
                self.widgets[key] = window
            if self.frame_bridge:
                if native_frame and setup_frame and not self.frame_bridge.register(window, key):
                    window.hide()
                    self.frame_bridge.unregister(window)
                    fallback_flags = widget_flags(False)
                    if spec.get("layer") == "pinned":
                        from PySide6.QtCore import Qt

                        fallback_flags = (
                            fallback_flags & ~Qt.WindowStaysOnBottomHint
                        ) | Qt.WindowStaysOnTopHint
                    window.setProperty("nativeFlags", int(fallback_flags))
                self.frame_bridge.watch_moves(window, key)
            # Frame recalculation can change the client dimensions. Apply the
            # requested logical card size again before arranging or showing it.
            window.resize(spec["width"], spec["height"])
            self._widget_appearance_config[key] = config
            self.ensure_widget_material(key, window)
        self.arrange(specs, rearrange)
        for key, window in self.widgets.items():
            window.show()
            spec = window.property("spec")
            if hasattr(spec, "toVariant"):
                spec = spec.toVariant()
            enabled = spec["material_policy"]["translucent"]
            self.compose(window, key, enabled)
            window.setProperty("registered", True)
        if self.settings.isVisible():
            self.compose(self.settings, "settings")
        self._appearance_states = {}
        self.refresh_appearance()
        self.update_menu()

    def arrange(self, specs, rearrange):
        if not specs:
            return
        rectangles = [item.availableGeometry() for item in self.app.screens()]
        config = self.controller._saved
        _, planned = desktop_plan(config, self.screen_inventory(), self.positions, bool(rearrange))
        for spec in specs:
            x, y = planned[spec["id"]]
            x, y = fit(x, y, spec["width"], spec["height"], rectangles)
            self.widgets[spec["id"]].setPosition(x, y)
            self.positions[spec["id"]] = [x, y]
        self.position_timer.start()

    def cancel_motion(self, key, finish=False):
        animation = self.motion.pop(key, None)
        target = animation.property("settle_target") if animation and finish else None
        if animation:
            animation.stop()
            animation.valueChanged.disconnect()
            animation.finished.disconnect()
            animation.deleteLater()
        window = self.widgets.get(key)
        if window:
            if target is not None:
                window.setPosition(*target)
                self.positions[key] = list(target)
            window.setProperty("registered", True)

    def begin_move(self, key):
        if self.shutting_down or key not in self.widgets or self.controller._saved["locked"]:
            return
        if getattr(self, "_spec_by_id", {}).get(key, {}).get("dock") == "top":
            if not self.controller.quickWidget(key, "dock", "free"):
                return
            if key not in self.widgets:
                return
        self.cancel_motion(key)
        window = self.widgets[key]
        self.drag_origins.setdefault(key, (window.x(), window.y()))

    def queue_end_move(self, key):
        QTimer.singleShot(0, lambda: self.end_move(key))

    def end_move(self, key):
        origin = self.drag_origins.pop(key, None)
        if origin is None or self.shutting_down or key not in self.widgets:
            return
        window = self.widgets[key]
        config = self.controller._saved
        areas = [
            (r.x(), r.y(), r.width(), r.height())
            for r in (s.availableGeometry() for s in self.app.screens())
        ]
        others = [
            (w.x(), w.y(), w.width(), w.height())
            for other, w in self.widgets.items()
            if other != key and w.isVisible()
        ]
        if not config["magnet_enabled"]:
            x, y = fit(
                window.x(),
                window.y(),
                window.width(),
                window.height(),
                [s.availableGeometry() for s in self.app.screens()],
            )
            window.setPosition(x, y)
            self.position(key, x, y)
            return
        placed = settle(
            (window.x(), window.y(), window.width(), window.height()),
            others,
            areas,
            gap=config["magnet_gap"],
            fallback=origin,
        )
        if not placed.legal:
            self.controller.set_status("当前工作区空间不足以保持设定间距。")
        animate = (
            config["magnet_bounce"] and placed.legal and placed.snapped and animations_enabled()
        )
        if not animate:
            window.setPosition(placed.x, placed.y)
            self.position(key, placed.x, placed.y)
            return
        start = (window.x(), window.y())
        animation = QVariantAnimation(self)
        animation.setDuration(440)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setProperty("settle_target", [placed.x, placed.y])
        self.motion[key] = animation
        window.setProperty("registered", False)

        def frame(value):
            if self.shutting_down or self.widgets.get(key) is not window:
                return
            t = float(value)
            u = min(1.0, t / 0.58)
            ease = 1 - (1 - u) ** 3
            phase = max(0.0, (t - 0.52) / 0.48)
            bounce = 4 * abs(math.sin(phase * 2 * math.pi)) * math.exp(-2 * phase) if phase else 0
            x = round(start[0] + (placed.x - start[0]) * ease + placed.normal[0] * bounce)
            y = round(start[1] + (placed.y - start[1]) * ease + placed.normal[1] * bounce)
            if u >= 1 and (
                not contained((x, y, window.width(), window.height()), areas)
                or not separated(
                    (x, y, window.width(), window.height()), others, config["magnet_gap"]
                )
            ):
                x, y = placed.x, placed.y
            window.setPosition(x, y)

        def finished():
            if self.motion.get(key) is not animation:
                return
            self.motion.pop(key, None)
            if self.widgets.get(key) is window and not self.shutting_down:
                window.setPosition(placed.x, placed.y)
                window.setProperty("registered", True)
                self.position(key, placed.x, placed.y)
            animation.deleteLater()

        animation.valueChanged.connect(frame)
        animation.finished.connect(finished)
        animation.start()

    def position(self, key, x, y):
        if key in self.widgets and not self.shutting_down:
            self.positions[key] = [x, y]
            self.controller.update_preview_position(key, x, y)
            self.position_timer.start()

    def save_positions(self):
        try:
            write_positions(self.positions)
            if not self.shutting_down:
                self.controller.set_screen_inventory(self.screen_inventory(), self.positions)
        except OSError:
            logging.exception("Desktop position save failed")

    def fit_windows(self):
        if not self.shutting_down and not self.headless:
            # Recompute sizes as well as positions after monitor/work-area changes.
            self.apply(False)

    def watch_screen(self, screen):
        if screen is None or screen in self.watched_screens:
            return
        self.watched_screens.add(screen)
        screen.availableGeometryChanged.connect(lambda *args: self.fit_windows())
        screen.geometryChanged.connect(lambda *args: self.fit_windows())
        screen.logicalDotsPerInchChanged.connect(lambda *args: self.fit_windows())
        screen.destroyed.connect(lambda *args: self.watched_screens.discard(screen))

    def screen_added(self, screen):
        self.watch_screen(screen)
        self.fit_windows()

    def screen_removed(self, screen):
        self.watched_screens.discard(screen)
        self.fit_windows()

    def keep_below(self):
        enabled = transparency_enabled()
        if enabled != self.transparency:
            self.transparency = enabled
            self.apply(False)
        material = getattr(self, "settings_material", None)
        if material:
            # No draw/sampling loop: this only notices a policy transition.
            material.refresh_policy()
        for material in getattr(self, "widget_materials", {}).values():
            material.refresh_policy()
        for key, window in self.widgets.items():
            if window.isVisible():
                if getattr(self, "_spec_by_id", {}).get(key, {}).get("layer") == "pinned":
                    pinned_level(int(window.winId()))
                else:
                    desktop_level(int(window.winId()))

    def screen_inventory(self):
        primary = self.app.primaryScreen()
        result = []
        for screen in self.app.screens():
            area = screen.availableGeometry()
            native_id, native_error = "", ""
            if not getattr(self, "headless", True) and self.app.platformName() == "windows":
                try:
                    native_id = self.top_bar.adapter.screen_identity(screen).native_id
                except Exception as error:
                    native_error = str(error)[:240]
            result.append(
                dict(
                    id=screen.name(),
                    label=screen.name(),
                    native_id=native_id,
                    native_error=native_error,
                    primary=screen == primary,
                    x=area.x(),
                    y=area.y(),
                    width=area.width(),
                    height=area.height(),
                )
            )
        return result

    def create_status_bar(self):
        if self.top_bar.paused:
            self.top_bar.resume()
        self.show_settings("__top_bar__")

    def show_details(self, key, index, x, y):
        if getattr(self, "details", None) is None:
            component = QQmlComponent(
                self.engine, QUrl.fromLocalFile(str(ASSETS / "native/Details.qml"))
            )
            if component.isError():
                logging.error("Details component: %s", [e.toString() for e in component.errors()])
                return
            self.details = component.create()
            self.details_component = component
            if self.details is None:
                return
        self.details.setProperty("widgetKey", key)
        self.details.setProperty("metricIndex", index)
        areas = [screen.availableGeometry() for screen in self.app.screens()]
        px, py = fit(
            round(x - self.details.width() / 2),
            round(y + 8),
            self.details.width(),
            self.details.height(),
            areas,
        )
        self.details.setPosition(px, py)
        self.details.show()
        self.details.requestActivate()

    def diagnose(self, output):
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.isVisible():
            self.settings.grabWindow().save(str(output.with_suffix(".png")))
        report = {
            "version": self.controller.version,
            "windows": {},
            "composition": self.composition,
            "settings_visible": self.settings.isVisible(),
            "sensor_timestamp": self.controller._data.get("time"),
            "readings": {
                key: value
                for key, value in self.controller._data.items()
                if key not in ("cpu_name", "gpu_name")
            },
        }
        for key, window in self.widgets.items():
            report["windows"][key] = {
                "width": window.width(),
                "height": window.height(),
                "x": window.x(),
                "y": window.y(),
                "visible": window.isVisible(),
                "above_desktop": desktop_below(int(window.winId())),
            }
            window.grabWindow().save(str(output.with_name(output.stem + "-" + key + ".png")))
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def shutdown(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        errors = []

        def attempt(label, action):
            try:
                action()
            except Exception as error:
                errors.append((label, error))

        for owner_name, method in (
            ("settings_material", "close"), ("settings_blur", "close"),
            ("settings_host", "dispose"), ("top_bar", "close"),
        ):
            owner = getattr(self, owner_name, None)
            if owner is not None:
                attempt(owner_name, getattr(owner, method))
        for key in list(self.motion):
            attempt("motion " + key, lambda key=key: self.cancel_motion(key, finish=True))
        self.drag_origins.clear()
        for timer_name in ("floor_timer", "stale_timer", "position_timer", "widget_mask_timer"):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                attempt(timer_name, timer.stop)
        attempt("save positions", self.save_positions)
        attempt("controller", self.controller.close)
        for key, window in list(self.widgets.items()):
            attempt("widget " + key, window.hide)
        for key, material in list(self.widget_materials.items()):
            def close_material(key=key, material=material):
                material.close()
                if self.widget_materials.get(key) is material:
                    self.widget_materials.pop(key)

            attempt("widget material " + key, close_material)
        for owner_name, method in (
            ("widget_blur", "close"), ("details", "hide"),
            ("frame_bridge", "close"), ("tray", "hide"),
        ):
            owner = getattr(self, owner_name, None)
            if owner is not None:
                attempt(owner_name, getattr(owner, method))
        if errors:
            original = errors[0][1]
            for label, error in errors[1:]:
                original.add_note("Runtime shutdown also failed (" + label + "): " + str(error))
            raise original


class LocalServer(QLocalServer):
    def __init__(self, application):
        super().__init__()
        self.application = application
        self.runtime = None
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.newConnection.connect(self.accept)
        self.clients = set()

    def start(self):
        return self.listen(name())

    def accept(self):
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            self.clients.add(socket)
            socket.setProperty("buffer", b"")
            socket.readyRead.connect(lambda client=socket: self.read(client))
            socket.disconnected.connect(lambda client=socket: self.discard(client))
            idle = QTimer(socket)
            idle.setSingleShot(True)
            idle.timeout.connect(socket.disconnectFromServer)
            idle.start(5000)
            self.read(socket)

    def discard(self, client):
        self.clients.discard(client)
        client.deleteLater()

    def read(self, client):
        raw = client.property("buffer") or b""
        raw += bytes(client.readAll())
        if len(raw) > 4096:
            client.disconnectFromServer()
            return
        if b"\n" not in raw:
            client.setProperty("buffer", raw)
            return
        response = {"ok": False}
        try:
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("Local command must be a JSON object")
            action = message.get("command")
            if self.runtime and action == "show":
                self.runtime.show_settings("")
                response = {"ok": True}
            elif action == "quit":
                response = {"ok": True}
                QTimer.singleShot(50, self.application.quit)
            elif action == "quit_if_clean":

                def clean():
                    return bool(self.runtime) and not (
                        self.runtime.controller.dirty
                        or bool(self.runtime.settings.property("pendingEdits"))
                    )

                if clean():
                    response = {"ok": True, "quitting": True, "dirty": False, "pid": os.getpid()}

                    def quit_if_still_clean():
                        # The queued turn must not discard input entered after
                        # the response. The installer also confirms termination.
                        if clean():
                            self.application.quit()

                    QTimer.singleShot(0, quit_if_still_clean)
                else:
                    response = {"ok": False, "dirty": True, "reason": "unsaved_changes"}
            elif self.runtime and action == "diagnose" and isinstance(message.get("path"), str):
                self.runtime.diagnose(message["path"])
                response = {"ok": True}
            elif self.runtime and action == "status":
                try:
                    manager = getattr(self.runtime, "top_bar", None)
                    snapshot = getattr(manager, "detail_diagnostics", None)
                    top_bar_details = snapshot() if callable(snapshot) else {
                        "available": False,
                        "errors": [{"scope": "snapshot", "code": "manager_unavailable"}],
                    }
                except Exception:
                    # A deleted Qt wrapper must not hide the basic status used
                    # by the existing exact-identity, clean-exit safeguards.
                    top_bar_details = {
                        "available": False,
                        "errors": [{"scope": "snapshot", "code": "snapshot_failed"}],
                    }
                response = {
                    "ok": True,
                    "version": self.runtime.controller.version,
                    "widgets": len(self.runtime.widgets),
                    "native": True,
                    "settings_visible": Runtime._settings_window(self.runtime).isVisible(),
                    "dirty": self.runtime.controller.dirty
                    or bool(self.runtime.settings.property("pendingEdits")),
                    "pid": os.getpid(),
                    "top_bar": dict(self.runtime.controller._top_bar_status),
                    "top_bar_details": top_bar_details,
                    "settings_material": dict(self.runtime.controller._material),
                    "settings_material_context": (
                        self.runtime.settings_material.status()
                        if getattr(self.runtime, "settings_material", None) is not None else {}
                    ),
                    "widget_materials": {
                        key: {field: report[field] for field in (
                            "material", "status", "blur_configured", "blur_may_remain",
                            "coating_allowed", "coating_translucent", "bool_result", "last_error",
                            "fallback_reason", "surface_fallback_reason", "backend_error",
                            "renderer", "compositing_verified",
                        ) if field in report}
                        for key, report in getattr(self.runtime, "composition", {}).items()
                        if key in self.runtime.widgets
                    },
                    "settings_active": Runtime._settings_window(self.runtime).isActive(),
                    "settings_minimized": bool(Runtime._settings_window(self.runtime).windowState() & Qt.WindowMinimized),
                }
        except (ValueError, TypeError, OSError):
            logging.exception("Local command rejected")
        client.write(json.dumps(response).encode() + b"\n")
        client.flush()
        client.disconnectFromServer()
