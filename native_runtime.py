"""Native desktop windows, tray, settings and local single-instance dispatch."""

import ctypes as c
import json
import logging
import math
import os
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, QUrl, QVariantAnimation
from PySide6.QtGui import QActionGroup, QCursor, QIcon
from PySide6.QtNetwork import QLocalServer
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, qmlRegisterType
from PySide6.QtWidgets import QSystemTrayIcon

from appearance_preview import project_appearance, project_top_bar_appearance
from cpu_temperature_launcher import CpuTemperatureLauncher, foreground_fullscreen
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
from raster_blur_material import ThinRasterAcrylicMaterial
from responsive_layout import ResponsiveLayoutError, is_responsive
from settings_backdrop_host import SettingsBackdropHost
from settings_blur_material import SettingsBlurMaterial
from settings_material_bridge import SettingsMaterialBridge
from stats_config import ASSETS, CONFIG, MODULES, PROFILE_PATHS, SKINS, load
from secondary_mode055 import active as secondary_active, display_name as session_display_name, target_native_id as secondary_target, status as session_status, screen_native_id as secondary_screen_id
from top_bar_runtime import TopBarManager
from widget_catalog import TEMPLATES
from widget_material_geometry import backdrop_shapes, rounded_mask


_input_desktop_api = None


def _desktop_session_ready():
    """Read input-desktop identity only; never switch desktops or request rights.

    Default + UOI_IO positively identifies our interactive input desktop. Lock,
    secure consent, inaccessible/disconnected or unknown state stays disallowed.
    https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-openinputdesktop
    https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getuserobjectinformationw
    """
    global _input_desktop_api
    if os.name != 'nt':return None
    try:
        if _input_desktop_api is None:
            user=c.WinDLL('user32',use_last_error=True)
            signatures=((user.OpenInputDesktop,c.c_void_p,[c.c_uint32,c.c_int32,c.c_uint32]),
                        (user.GetUserObjectInformationW,c.c_int32,[c.c_void_p,c.c_int32,c.c_void_p,c.c_uint32,c.POINTER(c.c_uint32)]),
                        (user.CloseDesktop,c.c_int32,[c.c_void_p]))
            for function,result,args in signatures:function.restype=result;function.argtypes=args
            _input_desktop_api=user
        user=_input_desktop_api;handle=user.OpenInputDesktop(0,False,1)  # DESKTOP_READOBJECTS
        if not handle:return None
        result=None
        try:
            name=c.create_unicode_buffer(256);needed=c.c_uint32();receives=c.c_int32()
            if (user.GetUserObjectInformationW(handle,2,name,c.sizeof(name),c.byref(needed))
                    and user.GetUserObjectInformationW(handle,6,c.byref(receives),c.sizeof(receives),c.byref(needed))):
                result=name.value.casefold()=='default' and bool(receives.value)
        finally:
            if not user.CloseDesktop(handle):result=None
        return result
    except (OSError,AttributeError,TypeError,ValueError):return None


class _DesktopAwareTopBarManager(TopBarManager):
    """Extend the one existing event guard to models, without changing bar hosts.

    A disabled/paused bar still has no AppBar hosts. Only its existing queued
    WinEvent refresh and guard remain while a visible hardware model needs them.
    The guard's normal shutdown still releases all native hooks on application
    exit or after the last model and bar host have gone. No second guard/timer.
    """
    def _model_monitors(self):
        return {**getattr(self.runtime,'_model_guard_monitors',{}),
                **getattr(self.runtime,'_assembly_guard_monitors',{}),
                **getattr(self.runtime,'_reference_import_monitors',{}),
                **getattr(self.runtime,'_secondary_guard_monitors',{})}

    def _queue_foreground_visibility(self):
        if self._model_monitors():
            if not self.closed and self._fullscreen_guard is not None and not self._foreground_timer.isActive():
                self._foreground_timer.start()
        else:super()._queue_foreground_visibility()

    def _read_foreground_visibility(self):
        if not self._model_monitors():return super()._read_foreground_visibility()
        if self._fullscreen_guard is None:
            self._foreground_hidden_screens=frozenset();return
        monitors={name:host.binding.monitor for name,host in self.hosts.items()
                  if not host.closing and host.binding is not None}
        monitors.update(self._model_monitors())
        try:
            guard=self._fullscreen_guard
            blocked=guard.blocked(monitors)
            self._foreground_hidden_screens=frozenset(monitors) if getattr(guard,'failure',None) else blocked
            self._fullscreen_guard_error=None
        except Exception as error:
            self._fullscreen_guard_error=type(error).__name__
            self._foreground_hidden_screens=frozenset(monitors)

    def _foreground_visibility_changed(self):
        if self.closed:return
        if self.paused and self._model_monitors():self._read_foreground_visibility()
        else:super()._foreground_visibility_changed()
        Runtime.refresh_model_motion(self.runtime,query=False)

    def _stop_fullscreen_guard(self):
        guard=self._fullscreen_guard
        if (not self.closed and not getattr(self.runtime,'shutting_down',False)
                and self._model_monitors() and guard is not None and not guard.closed):return
        super()._stop_fullscreen_guard()


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
        self._assembly_window = None
        self._model_guard_monitors = {}
        self._model_guard_hidden = {}
        self._assembly_guard_monitors = {}
        self._model_monitor_cache = {}
        self._model_motion_refreshing = False
        self._assembly_guard_hidden = False
        self.controller.assemblyViewRequested.connect(self.open_assembly_view)
        self.controller.referenceModelImportRequested.connect(self.import_reference_model)
        self.controller.set_motion_enabled(not headless and animations_enabled())
        self.frame_bridge = (
            None
            if headless
            else NativeFrameBridge(
                application, on_enter=self.begin_move, on_exit=self.queue_end_move
            )
        )
        screen = Runtime._placement_screen(self).availableGeometry()
        self.controller.set_preview_area(screen.width(), screen.height())
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
        self.engine = QQmlApplicationEngine()
        self.engine.warnings.connect(self.qml_warnings)
        self.engine.rootContext().setContextProperty("stats", self.controller)
        # A background top bar does not need the hidden settings object tree.
        # Keep the engine/context shared; load the editor on its first Show.
        self.settings = None
        self.settings_host = None
        self.settings_blur = None
        self.settings_material = None
        self._settings_loading = False
        self.settings_theme = self.controller._draft["theme"]
        self.controller.draftChanged.connect(self.settings_draft_changed)
        # The top bar has its own component. Compile desktop cards only when
        # a real card is first created; keep one reusable component thereafter.
        self.component = None
        if secondary_active():
            from secondary_top_bar055 import create_secondary_top_bar
            self.top_bar = create_secondary_top_bar(self, manager_class=_DesktopAwareTopBarManager,
                target_native_id=secondary_target(), gap_dip=6, desktop_ready=_desktop_session_ready)
        else:
            self.top_bar = _DesktopAwareTopBarManager(self)
        self.controller.motionChanged.connect(lambda:Runtime.refresh_model_motion(self))
        self.app.applicationStateChanged.connect(lambda *_:Runtime.refresh_model_motion(self))
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
        self.cpu_temperature_launcher = CpuTemperatureLauncher(
            headless=headless or application.platformName() != "windows"
        )
        self.controller.dataChanged.connect(self.maybe_start_cpu_temperature)
        self.tray = None
        if not headless:
            self.tray = QSystemTrayIcon(QIcon(str(ASSETS / "assets/icon.ico")), self)
            self.tray.setToolTip(session_display_name())
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
        self.controller.start(diagnostic_exports=self.headless)

    def qml_warnings(self, warnings):
        for warning in warnings:
            logging.warning("Native interface: %s", warning.toString())

    def _secondary_screen(self):
        wanted=secondary_target()
        if not secondary_active()or not wanted:return None
        matches=[screen for screen in self.app.screens()if secondary_screen_id(screen).casefold()==wanted.casefold()]
        return matches[0]if len(matches)==1 else None

    def _allowed_screens(self):
        if not secondary_active():return list(self.app.screens())
        target=Runtime._secondary_screen(self)
        return [target]if target is not None else[]

    def _placement_screen(self):
        return Runtime._secondary_screen(self)if secondary_active()else self.app.primaryScreen()

    def _secondary_admitted(self,*,query=True):
        if not secondary_active():return True
        try:
            target=Runtime._secondary_screen(self)
            if target is None or _desktop_session_ready()is not True:return False
            identifier,rect=Runtime._model_screen_fact(self,target)
            self._secondary_guard_monitors={identifier:rect}
            bar=self.top_bar;bar._ensure_fullscreen_guard()
            if query:bar._read_foreground_visibility()
            guard=getattr(bar,'_fullscreen_guard',None)
            return bool(guard is not None and getattr(guard,'_known',False)is True
                and not getattr(guard,'closed',True)and not getattr(guard,'failure',None)
                and not getattr(bar,'_fullscreen_guard_error',None)
                and identifier not in getattr(bar,'_foreground_hidden_screens',()))
        except(AttributeError,RuntimeError,TypeError,ValueError,OSError):return False

    def _secondary_window_context(self,window):
        if not Runtime._secondary_admitted(self):return None
        target=Runtime._secondary_screen(self)
        if target is None:return None
        adapter=self.top_bar.adapter
        identity=adapter.screen_identity(target)
        info=adapter._monitor_info(identity.monitor_handle)
        work=info.rcWork
        # Authorize pending placement into the confirmed target work area.
        # A hidden native owner can initially belong to another monitor; the
        # separate Show gate still requires its actual native target and bounds.
        return dict(admitted=True,native_id=identity.native_id,
            work=tuple(int(getattr(work,key))for key in('left','top','right','bottom')))

    def register_secondary_window(self,window):
        if not secondary_active():return True
        if self.shutting_down or self.headless or self.app.platformName()!='windows':return False
        target=Runtime._secondary_screen(self)
        if target is None or _desktop_session_ready()is not True:return False
        owner=window
        if callable(getattr(window,'windowHandle',None)):
            window.setWindowFlag(Qt.WindowDoesNotAcceptFocus,True)
            window.setAttribute(Qt.WA_ShowWithoutActivating,True)
            window.winId()  # Explicit own hidden QWidget; never a foreign HWND.
            owner=window.windowHandle()
        if owner is None:return False
        top=getattr(owner,'isTopLevel',None)
        if callable(top)and top()is False:return True
        owner.setFlag(Qt.WindowDoesNotAcceptFocus,True)
        owner.setScreen(target)
        guard=getattr(self,'_secondary_window_guard',None)
        if guard is None:
            from secondary_window_guard055 import create_secondary_window_guard
            guard=create_secondary_window_guard(self.app,lambda item:Runtime._secondary_window_context(self,item))
            self._secondary_window_guard=guard
        if not guard.watch(owner):return False
        owner.create()  # Hidden first setup is allowed before adapter.prepare.
        if not guard.bind(owner,int(owner.winId())):
            owner.hide();return False
        return True

    def _secondary_window_admitted(self,window):
        if not secondary_active():return True
        owner=window.windowHandle()if callable(getattr(window,'windowHandle',None))else window
        guard=getattr(self,'_secondary_window_guard',None)
        return bool(owner is not None and guard is not None and guard.allowed(owner))

    def _close_secondary_window_guard(self):
        guard=getattr(self,'_secondary_window_guard',None)
        if guard is None:return
        result=guard.close()
        if not result.get('complete'):raise RuntimeError('V2 window protection cleanup incomplete: '+str(result.get('errors')))
        self._secondary_window_guard=None

    def _secondary_refresh_panels(self):
        if not secondary_active()or getattr(self,'_secondary_refreshing',False):return
        self._secondary_refreshing=True
        try:
            allowed=Runtime._secondary_admitted(self,query=False)
            hidden=getattr(self,'_secondary_hidden_widgets',{})
            for key,window in tuple(getattr(self,'widgets',{}).items()):
                if not allowed and window.isVisible():
                    hidden[key]=window;window.hide()
                elif allowed and hidden.get(key)is window:
                    if Runtime._secondary_window_admitted(self,window):
                        window.show();window.lower()
                        if Runtime._secondary_window_admitted(self,window):hidden.pop(key,None)
                        else:window.hide()
            self._secondary_hidden_widgets=hidden
            # Settings/details are not automatically reopened after a game;
            # a new explicit request rechecks the exact target and desktop.
            if not allowed:
                for window in(getattr(self,'details',None),Runtime._settings_window(self)):
                    if window is not None and window.isVisible():window.hide()
            else:
                for window in(getattr(self,'details',None),Runtime._settings_window(self)):
                    if (window is not None and window.isVisible()
                            and not Runtime._secondary_window_admitted(self,window)):window.hide()
        except(RuntimeError,AttributeError,TypeError):pass
        finally:self._secondary_refreshing=False

    def ensure_settings(self):
        """Create the editor once, preserving its draft and existing glass lifecycle."""
        if self.shutting_down or self._settings_loading:
            return None
        if self.settings is not None:
            return self.settings
        self._settings_loading = True
        roots = tuple(self.engine.rootObjects())

        def discard():
            for owner_name, method in (("settings_material", "close"), ("settings_blur", "close"),
                                       ("settings_host", "dispose")):
                owner = getattr(self, owner_name, None)
                if owner is not None:
                    try:
                        getattr(owner, method)()
                    except Exception:
                        logging.exception("Could not release incomplete settings: %s", owner_name)
                    else:
                        if secondary_active() and owner_name in ("settings_material", "settings_host"):
                            try:
                                owner.deleteLater()
                            except Exception:
                                logging.exception("Could not delete incomplete secondary settings: %s", owner_name)
                setattr(self, owner_name, None)
            for root in self.engine.rootObjects():
                if root not in roots:
                    root.deleteLater()
            self.settings = None

        def cancelled():
            if not self.shutting_down:
                return False
            discard()
            return True

        try:
            self.engine.load(QUrl.fromLocalFile(str(ASSETS / "native/Settings.qml")))
            created = [root for root in self.engine.rootObjects() if root not in roots]
            if cancelled():
                return None
            settings = next((root for root in created if root.objectName() == "settingsWindow"), None)
            if settings is None:
                raise RuntimeError("Native settings could not load")
            self.settings = settings
            settings.setIcon(self.app.windowIcon())
            if cancelled():
                return None
            self.settings_theme = self.controller._draft["theme"]
            settings.setPersistentGraphics(True)
            settings.setPersistentSceneGraph(True)
            if cancelled():
                return None
            self.settings_host = (SettingsBackdropHost(settings)
                if not self.headless and self.app.platformName() == "windows" else None)
            if secondary_active():
                settings.setTitle(session_display_name())
                target=Runtime._secondary_screen(self)
                if target is None:raise RuntimeError('Second-version target screen unavailable')
                settings.setScreen(target)
                settings.setFlag(Qt.WindowDoesNotAcceptFocus,True)
                if self.settings_host is not None:
                    self.settings_host.setTitle(session_display_name())
                    self.settings_host.setScreen(target)
                    self.settings_host.setFlag(Qt.WindowDoesNotAcceptFocus,True)
            if cancelled():
                return None
            self.settings_blur = (ThinRasterAcrylicMaterial(paint_background=self.settings_host.paint_background)
                if self.settings_host is not None else SettingsBlurMaterial()
                if not self.headless and self.app.platformName() == "windows" else None)
            if cancelled():
                return None
            self.settings_material = None if self.headless else SettingsMaterialBridge(
                Runtime._settings_window(self), self, backend="system-blur",
                frame_source=settings if self.settings_host is not None else None,
                allow_hidden_prepare=self.settings_host is not None,
                wait_for_first_frame=True, activation_requests=self.settings_host is not None and not secondary_active(),
                compose_once=self._settings_material_request, policy_reader=transparency_policy,
                publish=self._publish_settings_material, release_surface=self._release_settings_surface)
            if cancelled():
                return None
            settings.visibleChanged.connect(self.refresh_appearance)
            if self.settings_host:
                self.settings_host.paintFailed.connect(self._settings_paint_failed)
            if self.settings_material:
                self.settings_material.start()
            if secondary_active():
                # The material bridge must observe the first hidden native
                # surface; registration may create it before hidden prepare.
                if not Runtime.register_secondary_window(self,Runtime._settings_window(self)):
                    raise RuntimeError('Second-version settings bounds protection unavailable')
            if cancelled():
                return None
            return settings
        except Exception:
            discard()
            raise
        finally:
            self._settings_loading = False

    def _settings_visible(self):
        settings = getattr(self, "settings", None)
        return settings is not None and settings.isVisible()

    def _settings_pending(self):
        settings = getattr(self, "settings", None)
        return settings is not None and bool(settings.property("pendingEdits"))

    def _settings_window_state(self):
        window = Runtime._settings_window(self)
        return dict(settings_loaded=getattr(self, "settings", None) is not None,
                    settings_visible=window is not None and window.isVisible(),
                    settings_active=window is not None and window.isActive(),
                    settings_minimized=bool(window is not None and window.windowState() & Qt.WindowMinimized))

    def settings_draft_changed(self):
        theme = self.controller._draft["theme"]
        if theme != self.settings_theme:
            self.settings_theme = theme
            if Runtime._settings_visible(self):
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
            self.controller._saved, self.controller._draft, Runtime._settings_visible(self)
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
        bar = getattr(self, "top_bar", None)
        if bar is not None:
            active = Runtime._settings_visible(self)
            bar.preview_appearance(project_top_bar_appearance(
                self.controller._saved, self.controller._draft, active
            ), active=active)

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
        inspector=getattr(self,"_assembly_window",None)
        if inspector is not None:
            inspector.update_readings()

    def maybe_start_cpu_temperature(self):
        if self.shutting_down:
            return
        launcher = getattr(self, "cpu_temperature_launcher", None)
        if launcher is not None:
            attempted = launcher.status().get("attempted") is True
            bar = getattr(self, "top_bar", None)
            result = launcher.update(
                self.controller._saved, self.controller._data,
                fullscreen=lambda: foreground_fullscreen(getattr(self, "top_bar", None),
                                                        desktop_ready=_desktop_session_ready),
            )
            if (not attempted and result.get("attempted") is True and not self.shutting_down
                    and getattr(self, "cpu_temperature_launcher", None) is launcher
                    and getattr(self, "top_bar", None) is bar):
                # Returning from consent can invalidate accepted compositor
                # state. Queue once, then reuse the bridges' existing debounce
                # and current-surface/visibility gates; never apply native blur
                # in the sensor callback or start another polling loop.
                QTimer.singleShot(0, lambda: Runtime._refresh_after_temperature_consent(self, launcher, bar))

    def _refresh_after_temperature_consent(self, launcher, bar):
        def current():
            return (not self.shutting_down
                    and getattr(self, "cpu_temperature_launcher", None) is launcher
                    and getattr(self, "top_bar", None) is bar)

        if not current():
            return
        settings = getattr(self, "settings_material", None)
        widgets = tuple((key, self.widgets.get(key), material)
                        for key, material in getattr(self, "widget_materials", {}).items())
        if bar is not None:
            bar.refresh_materials("composition_changed")
        if not current():
            return
        if settings is not None and getattr(self, "settings_material", None) is settings:
            settings.request("composition_changed")
        for key, window, material in widgets:
            if not current():
                return
            if (window is not None and self.widgets.get(key) is window
                    and self.widget_materials.get(key) is material):
                material.request("composition_changed")

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
        action = menu.addAction(tr("桌面 3D 检视"))
        action.setObjectName("openAssemblyDesktop")
        set_action_icon(action, "gpu")
        action.triggered.connect(self.controller.openAssemblyView)
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
        host = getattr(self, "settings_host", None)
        # A native callback may synchronously change the selected theme. Replay
        # only the latest target once in this transaction, then use the existing
        # finite recovery budget if it changes again; never add a polling timer.
        for attempt in range(2):
            caption = {"caption_theme": self.controller.theme} if host is not None else {}
            report = (self.settings_blur.apply(handle, policy, surface_id=serial, **caption,
                valid=lambda: self._settings_surface_current(
                    handle, serial, frame_epoch=epoch, preparation_token=preparation))
                if self.settings_blur is not None
                else dict(material="solid", status="fallback", fallback_reason="native-platform-unavailable",
                    coating_allowed=False, coating_translucent=False, blur_configured=False,
                    compositing_verified=False))
            if (not report.get("ok") or not report.get("caption_configured")
                    or caption["caption_theme"] == self.controller.theme):
                break
            if attempt == 1:
                cleanup = self.settings_blur.clear(handle, surface_id=serial,
                    valid=lambda: self._settings_surface_current(handle, serial, releasing=True))
                report.update(material="solid", status="fallback", ok=False,
                    coating_allowed=False, coating_translucent=False, blur_configured=False,
                    caption_configured=False, caption_visual_verified=False,
                    blur_may_remain=cleanup.get("blur_may_remain", True),
                    cleanup_complete=cleanup.get("cleanup_complete", False),
                    fallback_reason="caption-theme-changed-during-request", cleanup=cleanup)
        if host is not None:
            if (report.get("ok") and report.get("coating_translucent")
                    and not report.get("background_paint_completed") and not host.paint_background()):
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
        if self.shutting_down or getattr(self, "_settings_loading", False):
            return
        if secondary_active() and not Runtime._secondary_admitted(self):
            return
        if getattr(self, "settings", None) is None:
            try:
                if Runtime.ensure_settings(self) is None:
                    return
            except Exception:
                logging.exception("Native settings could not open")
                self.controller.set_status("无法打开设置", error=True)
                return
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
        window = Runtime._settings_window(self)
        available = [screen.availableGeometry() for screen in Runtime._allowed_screens(self)]
        if getattr(self, "settings_host", None) is not None:
            # The user's existing Show action may create the native host. Its
            # actual frame margins then keep the caption inside the work area.
            window.create()
            if not current():
                return
            margins = window.frameMargins()
            screen = Runtime._placement_screen(self).availableGeometry()
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
            screen = Runtime._placement_screen(self).availableGeometry()
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
        if secondary_active() and not Runtime._secondary_window_admitted(self,window):return
        window.showNormal()
        if secondary_active() and not Runtime._secondary_window_admitted(self,window):
            window.hide();return
        if not current():
            return
        self.compose(self.settings, "settings")
        if not current():
            return
        if not secondary_active():window.raise_()
        if not current():
            return
        if not secondary_active():window.requestActivate()

    def desktop_widget_component(self):
        if self.component is None:
            component = QQmlComponent(
                self.engine, QUrl.fromLocalFile(str(ASSETS / "native/DesktopWidget.qml"))
            )
            if component.isError():
                raise RuntimeError("; ".join(error.toString() for error in component.errors()))
            self.component = component
        return self.component

    def apply_top_bar(self):
        """A bar-only commit does not recreate widgets or discard editor drafts."""
        self.top_bar.apply(self.controller._saved)
        Runtime.refresh_model_motion(self)
        self.update_menu()

    def apply(self, rearrange=False):
        if getattr(self, "top_bar", None) is not None:
            self.top_bar.apply(self.controller._saved)
        if self.headless:
            return
        if secondary_active() and not Runtime._secondary_admitted(self):
            Runtime._secondary_refresh_panels(self)
            return
        config = self.controller._saved
        self.controller.set_motion_enabled(animations_enabled())
        for key in list(self.motion):
            self.cancel_motion(key)
        self.drag_origins.clear()
        screen = Runtime._placement_screen(self).availableGeometry()
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
                desired_flags = int(
                    (widget_flags(native_frame) & ~Qt.WindowStaysOnBottomHint)
                    | Qt.WindowStaysOnTopHint
                )
            if secondary_active():desired_flags|=int(Qt.WindowDoesNotAcceptFocus)
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
                window = self.desktop_widget_component().createWithInitialProperties(
                    {"spec": spec, "nativeFlags": desired_flags}
                )
                if not window:
                    raise RuntimeError("Native widget could not load")
                self.widgets[key] = window
                if secondary_active():
                    window.setTitle(session_display_name()+' · 小组件')
                window.installEventFilter(self)
                for signal in (window.visibleChanged,window.visibilityChanged,window.screenChanged):
                    signal.connect(lambda *_:Runtime.refresh_model_motion(self))
            if secondary_active()and not Runtime.register_secondary_window(self,window):
                window.hide()
                raise RuntimeError('Second-version widget bounds protection unavailable')
            if self.frame_bridge:
                if native_frame and setup_frame and not self.frame_bridge.register(window, key):
                    window.hide()
                    self.frame_bridge.unregister(window)
                    fallback_flags = widget_flags(False)
                    if spec.get("layer") == "pinned":
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
        # A pinned hardware model must be admitted before its first Show, not
        # briefly published over a game and hidden by a later exposure event.
        model_windows=Runtime._admit_model_windows(self)
        for key, window in self.widgets.items():
            if secondary_active() and not Runtime._secondary_window_admitted(self,window):
                window.hide();continue
            if key not in model_windows:window.show()
            elif not window.isVisible():continue
            if secondary_active() and not Runtime._secondary_window_admitted(self,window):
                window.hide();continue
            spec = window.property("spec")
            if hasattr(spec, "toVariant"):
                spec = spec.toVariant()
            enabled = spec["material_policy"]["translucent"]
            self.compose(window, key, enabled)
            window.setProperty("registered", True)
        if Runtime._settings_visible(self):
            self.compose(self.settings, "settings")
        self._appearance_states = {}
        self.refresh_appearance()
        Runtime.refresh_model_motion(self)
        self.update_menu()

    def arrange(self, specs, rearrange):
        if not specs:
            return
        rectangles = [item.availableGeometry() for item in Runtime._allowed_screens(self)]
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
            for r in (s.availableGeometry() for s in Runtime._allowed_screens(self))
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
                [s.availableGeometry() for s in Runtime._allowed_screens(self)],
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
        self._model_monitor_cache = {}
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
        Runtime.refresh_model_motion(self)

    def eventFilter(self,watched,event):
        if (event.type() in (QEvent.Expose,QEvent.Show,QEvent.Hide,QEvent.WindowStateChange)
                and (any(window is watched for window in self.widgets.values())
                     or getattr(self,'_assembly_window',None) is watched)):
            Runtime.refresh_model_motion(self)
        return super().eventFilter(watched,event)

    def _model_screen_fact(self,screen):
        cache=getattr(self,'_model_monitor_cache',{})
        if screen in cache:return cache[screen]
        if screen is None:raise ValueError('Model screen is unavailable')
        adapter=self.top_bar.adapter;identity=adapter.screen_identity(screen)
        identifier=identity.native_id
        if type(identifier) is not str or not identifier:raise ValueError('Model monitor identity is unavailable')
        bounds=adapter._monitor_info(identity.monitor_handle).rcMonitor
        rect=tuple(getattr(bounds,key) for key in ('left','top','right','bottom'))
        if any(type(value) is not int for value in rect) or rect[2]<=rect[0] or rect[3]<=rect[1]:
            raise ValueError('Model monitor bounds are unavailable')
        cache[screen]=(identifier,rect);self._model_monitor_cache=cache
        return cache[screen]

    def _has_hardware_model(self,key,window):
        try:
            spec=window.property('spec')
            if hasattr(spec,'toVariant'):spec=spec.toVariant()
            config=getattr(self,'_widget_appearance_config',{}).get(key,self.controller._saved)
            return any(config.get('widgets',{}).get(cell.get('key'),{}).get('presentation')=='hardware'
                       for cell in (spec or {}).get('cells',()) if isinstance(cell,dict))
        except (AttributeError,RuntimeError,TypeError,ValueError):return False

    def _admit_model_windows(self):
        hidden=getattr(self,'_model_guard_hidden',{})
        self._model_guard_hidden=hidden;models=set()
        for key,window in self.widgets.items():
            if Runtime._has_hardware_model(self,key,window):models.add(key);hidden[key]=window
        Runtime.refresh_model_motion(self)
        return models

    def refresh_model_motion(self,*,query=True):
        """Reuse WinEvents/window signals/the existing floor tick; no new poller."""
        if getattr(self,'_model_motion_refreshing',False):return
        self._model_motion_refreshing=True
        try:
            candidates=[];monitors={}
            hidden=getattr(self,'_model_guard_hidden',{})
            hidden={key:window for key,window in hidden.items() if self.widgets.get(key) is window}
            self._model_guard_hidden=hidden
            stopped=getattr(self,'shutting_down',False) or getattr(self,'headless',True)
            for key,window in tuple(getattr(self,'widgets',{}).items()):
                hardware=False;identifier=None
                try:
                    hardware=Runtime._has_hardware_model(self,key,window)
                    exposed=(not stopped and (hardware or hidden.get(key) is window)
                             and (hidden.get(key) is window or window.isVisible() is True and window.isExposed() is True)
                             and not bool(window.windowState()&Qt.WindowMinimized))
                    if exposed:
                        identifier,rect=Runtime._model_screen_fact(self,window.screen());monitors[identifier]=rect
                except (AttributeError,RuntimeError,TypeError,ValueError):pass
                candidates.append((key,window,identifier,hardware))
            self._model_guard_monitors=monitors
            assembly=getattr(self,'_assembly_window',None)
            if assembly is not None and hasattr(assembly,'screen'):
                try:
                    identifier,rect=Runtime._model_screen_fact(self,assembly.screen())
                    self._assembly_guard_monitors={identifier:rect}
                except (AttributeError,RuntimeError,TypeError,ValueError):self._assembly_guard_monitors={}
            dialog=getattr(self,'_reference_file_dialog',None)
            if dialog is not None:
                try:
                    identifier,rect=Runtime._model_screen_fact(self,dialog.screen())
                    self._reference_import_monitors={identifier:rect}
                except (AttributeError,RuntimeError,TypeError,ValueError):self._reference_import_monitors={}
            bar=getattr(self,'top_bar',None)
            all_monitors={**monitors,**getattr(self,'_assembly_guard_monitors',{}),
                          **getattr(self,'_reference_import_monitors',{})}
            if bar is not None:
                if all_monitors and not stopped:bar._ensure_fullscreen_guard()
                elif not getattr(bar,'hosts',{}):bar._stop_fullscreen_guard()
            guard=getattr(bar,'_fullscreen_guard',None)
            if query and all_monitors and guard is not None:bar._read_foreground_visibility()
            known=(guard is not None and getattr(guard,'_known',False) is True
                   and not getattr(guard,'closed',True)
                   and not getattr(guard,'failure',None) and not getattr(bar,'_fullscreen_guard_error',None))
            session=bool(all_monitors) and _desktop_session_ready() is True
            for key,window,identifier,hardware in candidates:
                if self.widgets.get(key) is not window:continue
                safe=bool(session and known and identifier in monitors
                          and identifier not in getattr(bar,'_foreground_hidden_screens',()))
                if (not safe and hardware and window.isVisible() is True
                        and not bool(window.windowState()&Qt.WindowMinimized)):
                    hidden[key]=window;window.hide()
                elif safe and hidden.get(key) is window:
                    if window.isVisible() is not True:window.show();window.lower()
                    if window.isExposed() is True:hidden.pop(key,None)
                allowed=bool(hardware and safe and window.isVisible() is True and window.isExposed() is True)
                if window.property('modelMotionAllowed') is not allowed:window.setProperty('modelMotionAllowed',allowed)
            Runtime._update_assembly_motion(self,known,session,bar)
            Runtime._update_reference_import_guard(self,known,session,bar)
            Runtime._secondary_refresh_panels(self)
        except Exception:
            # Any query/identity failure leaves every owned model quiet.
            for key,window in tuple(getattr(self,'widgets',{}).items()):
                try:
                    window.setProperty('modelMotionAllowed',False)
                    if (Runtime._has_hardware_model(self,key,window) and window.isVisible() is True
                            and not bool(window.windowState()&Qt.WindowMinimized)):
                        self._model_guard_hidden[key]=window;window.hide()
                except RuntimeError:pass
            Runtime._update_assembly_motion(self,False,False,getattr(self,'top_bar',None))
            Runtime._update_reference_import_guard(self,False,False,getattr(self,'top_bar',None))
            Runtime._secondary_refresh_panels(self)
        finally:self._model_motion_refreshing=False

    def _update_assembly_motion(self,known,session,bar):
        window=getattr(self,'_assembly_window',None)
        if window is None:return
        identifiers=getattr(self,'_assembly_guard_monitors',{})
        safe=bool(known and session and identifiers
                  and not set(identifiers)&set(getattr(bar,'_foreground_hidden_screens',())))
        if secondary_active()and not Runtime._secondary_window_admitted(self,window):safe=False
        desktop=getattr(window,'window_mode',None)=='desktop'
        guarded=secondary_active()or desktop or getattr(window,'window_mode',None)=='reference'
        minimized=window.isMinimized() is True
        if guarded and not safe and window.isVisible() is True and not minimized:
            self._assembly_guard_hidden=True;window.hide()
        elif guarded and safe and getattr(self,'_assembly_guard_hidden',False) and not minimized:
            self._assembly_guard_hidden=False
            window.setAttribute(Qt.WA_ShowWithoutActivating,True);window.showNormal();window.lower()
        allowed=bool(safe and window.isVisible() is True and not minimized
                     and not getattr(self,'shutting_down',False))
        if window.property('modelMotionAllowed') is not allowed:window.setProperty('modelMotionAllowed',allowed)
        if not allowed:
            window._clock_active(False)
            window.viewport.set_motion_enabled(False)
        if getattr(window,'window_mode',None)!='reference':window.update_readings()

    def _update_reference_import_guard(self,known,session,bar):
        dialog=getattr(self,'_reference_file_dialog',None)
        if dialog is None:return
        monitors=getattr(self,'_reference_import_monitors',{})
        safe=bool(known and session and monitors
                  and not set(monitors)&set(getattr(bar,'_foreground_hidden_screens',())))
        if secondary_active()and not Runtime._secondary_window_admitted(self,dialog):safe=False
        if not safe:
            try:dialog.reject()
            except RuntimeError:
                self._reference_file_dialog=None;self._reference_import_monitors={}

    def screen_inventory(self):
        primary = self.app.primaryScreen()
        result = []
        for screen in Runtime._allowed_screens(self):
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
        if secondary_active() and not Runtime._secondary_admitted(self):return
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
        if secondary_active():
            target=Runtime._secondary_screen(self)
            if target is None:return
            self.details.setScreen(target);self.details.setTitle(session_display_name()+' · 详情')
            self.details.setFlag(Qt.WindowDoesNotAcceptFocus,True)
            if not Runtime.register_secondary_window(self,self.details):return
        self.details.setProperty("widgetKey", key)
        self.details.setProperty("metricIndex", index)
        areas = [screen.availableGeometry() for screen in Runtime._allowed_screens(self)]
        px, py = fit(
            round(x - self.details.width() / 2),
            round(y + 8),
            self.details.width(),
            self.details.height(),
            areas,
        )
        self.details.setPosition(px, py)
        if secondary_active() and not Runtime._secondary_window_admitted(self,self.details):return
        self.details.show()
        if secondary_active() and not Runtime._secondary_window_admitted(self,self.details):
            self.details.hide();return
        if not secondary_active():self.details.requestActivate()

    def _assembly_target_allowed(self,target):
        """Use the same screen-aware guard before creating/showing an own view."""
        if secondary_active() and target is not Runtime._secondary_screen(self):return False
        identifier,rect=Runtime._model_screen_fact(self,target)
        self._assembly_guard_monitors={identifier:rect}
        bar=self.top_bar;bar._ensure_fullscreen_guard();bar._read_foreground_visibility()
        guard=getattr(bar,'_fullscreen_guard',None)
        return (guard is not None and getattr(guard,'_known',False) is True
                and not getattr(guard,'closed',True)
                and not getattr(guard,'failure',None) and not getattr(bar,'_fullscreen_guard_error',None)
                and identifier not in getattr(bar,'_foreground_hidden_screens',()))

    def import_reference_model(self):
        """Open an owned, screen-bound chooser only after an explicit request."""
        if self.headless or self.shutting_down:return
        if getattr(self,'_reference_file_dialog',None) is not None:return
        previous=getattr(self,'_assembly_guard_monitors',{}).copy()
        dialog=None
        try:
            from assembly_config import target_screen
            target=target_screen(Runtime._allowed_screens(self),self.controller.saved.get('top_bar',{}),
                Runtime._placement_screen(self),lambda screen:self.top_bar.adapter.screen_identity(screen).native_id)
            if (target is None or _desktop_session_ready() is not True
                    or not Runtime._assembly_target_allowed(self,target)):
                self.controller.set_status('所选屏幕当前不适合打开模型。',error=True)
                return
            from PySide6.QtWidgets import QDialog,QFileDialog
            # Runtime owns this chooser. A replaced model window must not
            # destroy the chooser halfway through its fileSelected signal.
            dialog=QFileDialog(None,self.controller.tr('载入开源三维模型'))
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog,True)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilter('DesktopStats open references (*.zip)')
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setAttribute(Qt.WA_DeleteOnClose,True)
            dialog.setAttribute(Qt.WA_ShowWithoutActivating,secondary_active()or foreground_fullscreen() is not False)
            if secondary_active():
                dialog.setWindowFlag(Qt.WindowDoesNotAcceptFocus,True)
                dialog.setWindowTitle(session_display_name()+' · 导入模型')
            area=target.availableGeometry()
            width=min(760,max(280,area.width()-48));height=min(520,max(240,area.height()-48))
            dialog.resize(width,height)
            dialog.winId();dialog.windowHandle().setScreen(target)
            if secondary_active()and not Runtime.register_secondary_window(self,dialog):
                dialog.reject();return
            dialog.move(area.x()+max(0,(area.width()-width)//2),area.y()+max(0,(area.height()-height)//2))
            identifier,rect=Runtime._model_screen_fact(self,target)
            self._reference_file_dialog=dialog;self._reference_import_monitors={identifier:rect}
            chosen=[]
            def selected(path):
                if self._reference_file_dialog is not dialog:return
                if type(path) is str:chosen[:]=[path]
            def finished(result):
                owns=getattr(self,'_reference_file_dialog',None) is dialog
                if owns:self._reference_file_dialog=None;self._reference_import_monitors={}
                try:
                    # finished(Accepted) is delivered after the chooser hides;
                    # fileSelected itself is emitted while it is still open.
                    if owns and result==QDialog.DialogCode.Accepted and chosen:
                        Runtime.open_reference_view(self,chosen[0])
                finally:Runtime.refresh_model_motion(self,query=False)
            dialog.fileSelected.connect(selected);dialog.finished.connect(finished)
            dialog.windowHandle().screenChanged.connect(lambda *_:Runtime.refresh_model_motion(self))
            if (_desktop_session_ready() is not True or not Runtime._assembly_target_allowed(self,target)
                    or secondary_active()and not Runtime._secondary_window_admitted(self,dialog)):
                dialog.reject();return
            dialog.open()
        except Exception:
            if dialog is not None:dialog.close()
            logging.exception('Open reference chooser could not open')
            self.controller.set_status('无法打开模型选择器。',error=True)
        finally:
            self._assembly_guard_monitors=previous
            Runtime.refresh_model_motion(self)

    def open_reference_view(self,path):
        if type(path) is not str or not path or len(path)>32767:return
        Runtime.open_assembly_view(self,dict(reference_package=path,options={'window_mode':'reference'}))

    def open_assembly_view(self, specification):
        """A user-requested native viewer, kept on the selected bar screen."""
        if self.headless or self.shutting_down:
            return
        window = None
        previous_monitors=getattr(self,'_assembly_guard_monitors',{}).copy()
        admitted=False
        try:
            configured = self.controller.saved.get("top_bar", {})
            from assembly_config import target_screen
            target = target_screen(Runtime._allowed_screens(self),configured,Runtime._placement_screen(self),
                lambda screen:self.top_bar.adapter.screen_identity(screen).native_id)
            if target is None:
                self.controller.set_status("所选屏幕不可用", error=True)
                return
            if _desktop_session_ready() is not True:
                self.controller.set_status("桌面当前不可交互，暂不打开三维检视。",error=True)
                return
            if not Runtime._assembly_target_allowed(self,target):
                self.controller.set_status("此屏幕正在运行全屏应用，暂不打开三维检视。",error=True)
                return
            options=specification.get('options',{})
            mode=options.get('window_mode','inspect') if isinstance(options,dict) else 'inspect'
            mode=mode if type(mode) is str and mode in ('inspect','desktop','reference') else 'inspect'
            if mode=='reference' and (type(specification.get('reference_package')) is not str
                    or not specification['reference_package']):return
            current = self._assembly_window
            current_mode=getattr(current,'window_mode','inspect')
            if type(current_mode) is not str:current_mode='inspect'
            if current is not None and (current_mode!=mode or mode=='reference'):
                current.close()
                if self._assembly_window is current:self._assembly_window=None
                current=None;previous_monitors={}
            if current is not None:
                current.synchronize(specification)
                window = current
            elif mode=='reference':
                from open_reference_models054 import load_reference
                from open_reference_window054 import OpenReferenceWindow
                model=load_reference(Path(specification['reference_package']))
                window=OpenReferenceWindow(model,self.controller)
            else:
                from assembly_window import create_assembly_window
                window = create_assembly_window(self.controller, self.engine, specification)
            area = target.availableGeometry()
            minimum_width = min(280,max(1,area.width())) if mode=='desktop' else min(760,max(320,area.width()))
            minimum_height = min(300,max(1,area.height())) if mode=='desktop' else min(520,max(240,area.height()))
            window.setMinimumSize(minimum_width, minimum_height)
            width = min(420,max(minimum_width,area.width()-32)) if mode=='desktop' else min(1080,max(minimum_width,area.width()-64))
            height = min(480,max(minimum_height,area.height()-32)) if mode=='desktop' else min(800,max(minimum_height,area.height()-64))
            window.resize(width, height)
            if secondary_active():
                window.setWindowFlag(Qt.WindowDoesNotAcceptFocus,True)
                window.setWindowTitle(session_display_name()+' · 整机检视')
            window.winId()
            window.windowHandle().setScreen(target)
            if secondary_active()and not Runtime.register_secondary_window(self,window):
                window.close();return
            window.move(area.x() + max(0, (area.width() - width) // 2),
                        area.y() + max(0, (area.height() - height) // 2))
            if current is None:
                self._assembly_window = window
                window.installEventFilter(self)
                window.windowHandle().screenChanged.connect(lambda *_:Runtime.refresh_model_motion(self))
                def closed(owner=window):
                    if self._assembly_window is owner:
                        self._assembly_window=None;self._assembly_guard_monitors={};self._assembly_guard_hidden=False
                        Runtime.refresh_model_motion(self)
                window.closed.connect(closed)
            # A queued foreground/secure-desktop change during profile baking
            # must be checked again before publishing the newly built surface.
            if (_desktop_session_ready() is not True or not Runtime._assembly_target_allowed(self,target)
                    or secondary_active()and not Runtime._secondary_window_admitted(self,window)):
                window.close();previous_monitors={};return
            admitted=True
            activate = not secondary_active() and mode in ('inspect','reference') and foreground_fullscreen() is False
            window.setAttribute(Qt.WA_ShowWithoutActivating,not activate)
            window.showNormal()
            if secondary_active()and not Runtime._secondary_window_admitted(self,window):
                window.hide()
            if mode=='desktop':window.lower()
            elif activate:
                window.raise_();window.activateWindow()
        except Exception:
            if window is not None:
                window.close()
                if self._assembly_window is None:previous_monitors={}
            logging.exception("Assembly view could not open")
            self.controller.set_status("无法打开三维视图", error=True)
        finally:
            if not admitted:self._assembly_guard_monitors=previous_monitors
            Runtime.refresh_model_motion(self)

    def diagnose(self, output):
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if Runtime._settings_visible(self):
            self.settings.grabWindow().save(str(output.with_suffix(".png")))
        report = {
            "version": self.controller.version,
            "application_mode": session_status(),
            "windows": {},
            "composition": self.composition,
            "settings_visible": Runtime._settings_visible(self),
            "sensor_timestamp": self.controller._data.get("time"),
            "cpu_temperature_startup": (
                self.cpu_temperature_launcher.status()
                if getattr(self, "cpu_temperature_launcher", None) is not None else {}
            ),
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
            ("_reference_file_dialog", "reject"),
            ("_assembly_window", "close"),
            ("cpu_temperature_launcher", "close"),
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
        attempt("secondary window protection",lambda:Runtime._close_secondary_window_guard(self))
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
                        or Runtime._settings_pending(self.runtime)
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
            elif self.runtime and action == "hardware_icon_style":
                from top_bar_config import HARDWARE_ICON_STYLES

                selected, expected = message.get("style"), message.get("expected_pid")
                controller = self.runtime.controller
                if type(expected) is not int or expected != os.getpid():
                    response = {"ok": False, "reason": "instance_changed"}
                elif not isinstance(selected, str) or selected not in HARDWARE_ICON_STYLES:
                    response = {"ok": False, "reason": "invalid_style"}
                elif (controller.dirty or getattr(controller, "replacementPending", False)
                      or Runtime._settings_pending(self.runtime)):
                    response = {"ok": False, "dirty": True, "reason": "unsaved_changes"}
                else:
                    # One allowlisted preference uses the existing scoped save;
                    # sampling, temperature helper and application PID survive.
                    controller.changeTopBar("hardware_icon_style", selected)
                    applied = (controller.applyTopBar()
                               and controller.saved["top_bar"]["hardware_icon_style"] == selected)
                    if not applied:
                        controller.revertTopBarDraft()
                    response = {"ok": bool(applied), "pid": os.getpid(),
                                "hardware_icon_style": selected if applied else None}
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
                    "application_mode": session_status(),
                    "version": self.runtime.controller.version,
                    "widgets": len(self.runtime.widgets),
                    "native": True,
                    "profile": PROFILE_PATHS.status(),
                    "motion_enabled": bool(self.runtime.controller.motionEnabled),
                    "top_bar_configuration": [
                        {key: item[key] for key in ("id", "metric")} | {
                            "style": item["prefs"]["style"],
                            "icon_effect": item["prefs"].get("icon_effect", "off"),
                            "metrics": item["prefs"].get("metrics", [item["metric"]]),
                        }
                        for item in self.runtime.controller._saved["top_bar"]["items"]
                    ],
                    **Runtime._settings_window_state(self.runtime),
                    "dirty": self.runtime.controller.dirty
                    or Runtime._settings_pending(self.runtime),
                    "pid": os.getpid(),
                    "top_bar": dict(self.runtime.controller._top_bar_status),
                    "top_bar_details": top_bar_details,
                    "cpu_temperature_startup": (
                        self.runtime.cpu_temperature_launcher.status()
                        if getattr(self.runtime, "cpu_temperature_launcher", None) is not None else {}
                    ),
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
                }
        except (ValueError, TypeError, OSError):
            logging.exception("Local command rejected")
        client.write(json.dumps(response).encode() + b"\n")
        client.flush()
        client.disconnectFromServer()
