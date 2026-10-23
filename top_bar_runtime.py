"""Owned, opt-in AppBar presentation over the existing controller's readings.

No collector, display change, native API or window creation occurs on import or
manager construction. Native calls are lazy and require an explicitly enabled
saved configuration on the Windows platform. Tests inject an entirely fake adapter.
"""

from __future__ import annotations

import copy
import ctypes as c
import math
import os
import secrets
import sys
from collections import OrderedDict
from ctypes import wintypes as w
from dataclasses import dataclass
from types import SimpleNamespace

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QAbstractNativeEventFilter,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QCursor, QFont, QFontMetricsF
from PySide6.QtQml import QQmlComponent

from appbar_platform import (
    ABM_QUERYPOS,
    WINDOW_GENERATION_PROPERTY,
    AppBarError,
    AppBarSession,
    NativeAppBarBackend,
)
from compact_labels import label_options
from modern_menu import ModernMenu as QMenu
from modern_menu import set_action_icon
from native_card import ui_font
from skin_styles import GLASS_SKINS, effective_skin, glass_options, palette
from stats_config import ASSETS
from top_bar_config import top_bar_style
from top_bar_layout import MetricItem, PixelRect, plan_top_bar, present_metric

OVERFLOW = "__overflow__"
WM_ACTIVATE, WM_WINDOWPOSCHANGED, WM_DISPLAYCHANGE = 0x0006, 0x0047, 0x007E
WM_DPICHANGED, WM_NCDESTROY = 0x02E0, 0x0082
ABN_POSCHANGED, ABN_FULLSCREENAPP = 1, 2


class MonitorInfo(c.Structure):
    _fields_ = [
        ("cbSize", c.c_uint32),
        ("rcMonitor", w.RECT),
        ("rcWork", w.RECT),
        ("dwFlags", c.c_uint32),
        ("szDevice", c.c_wchar * 32),
    ]


@dataclass
class Binding:
    window: object
    token: object
    screen_name: str
    monitor: PixelRect
    work: PixelRect
    dpi: int
    monitor_handle: int = 0
    screen: object = None

    @property
    def hwnd(self):
        return self.token.hwnd


@dataclass(frozen=True)
class ScreenIdentity:
    native_id: str
    monitor_handle: int
    friendly_name: str


class WindowPreparationError(AppBarError):
    """Keep an owned HWND alive when its generation cleanup is not confirmed."""

    def __init__(self, message, binding):
        super().__init__(message)
        self.binding = binding


class BarMaterial:
    """One own-window blur backend, retained until its clear is confirmed."""

    def __init__(self, backend, validate):
        self.backend, self._validate = backend, validate
        self.bridge, self.binding = None, None
        self.attempted = False
        self.cleanup = {}
        self.closed = False
        self._prepare_before_show = None
        self.bound_surface = None

    def bind(self, binding):
        self.binding = binding
        status = getattr(self.bridge, "status", None)
        context = status() if callable(status) else None
        self.bound_surface = ((context.get("surface_serial"), context.get("surface_handle"))
                              if isinstance(context, dict) else None)

    def check(self, handle):
        if self.binding is None or handle != self.binding.hwnd:
            raise AppBarError("Top bar material has no current prepared window")
        self._validate(self.binding.token)

    def apply(self, handle, enabled, policy):
        if self.closed:
            raise AppBarError("Top bar material is closed")
        self.check(handle)
        self.attempted = True
        report = self.backend.apply(handle, enabled=enabled, policy=policy)
        report["coating_translucent"] = bool(
            report.get("coating_allowed") and report.get("blur_configured")
            and report.get("ok") and enabled
        )
        if not report["coating_translucent"]:
            report["material"] = "solid"
        report["compositing_verified"] = False
        return report

    def clear(self, handle):
        if not self.attempted:
            return dict(ok=True, cleanup_complete=True, noop=True)
        self.check(handle)
        result = self.backend.clear(handle)
        if result.get("cleanup_complete"):
            self.attempted = False
        return result

    def request(self, reason):
        return self.bridge.request(reason)

    def prepare_before_show(self):
        """Details-only bootstrap, after a hidden HWND has been retained."""
        if self.closed:
            raise AppBarError("Top bar material is closed")
        if self._prepare_before_show is not None:
            return self._prepare_before_show()
        return None

    def status(self):
        return dict(self.bridge.status(), material_cleanup=dict(self.cleanup))

    def close(self):
        self.closed = True
        self.bridge.close()
        if self.attempted:
            self.check(self.binding.hwnd)
        self.cleanup = self.backend.close()
        if not self.cleanup.get("complete") or not self.cleanup.get("ok"):
            raise AppBarError("Own top bar material cleanup is incomplete")
        self.attempted = False

    def deleteLater(self):
        self.bridge.deleteLater()


class WindowsTopBarAdapter:
    """Native calls target only retained own windows; all coordinates here are physical."""

    native = True

    def __init__(self):
        self.backend = NativeAppBarBackend()
        self._functions = None
        self._monitor_info_function = None
        self.callback_message = self.taskbar_message = 0

    def _monitor_info(self, monitor):
        # Inventory resolution must not register AppBar messages or create an
        # HWND. Tests may inject this exact read-only function with the API set.
        function = (self._functions or {}).get("monitor_info")
        if function is None:
            if self._monitor_info_function is None:
                if sys.platform != "win32":
                    raise AppBarError("Windows screen identity is unavailable on this platform")
                function = c.WinDLL("user32", use_last_error=True).GetMonitorInfoW
                function.argtypes = [c.c_void_p, c.POINTER(MonitorInfo)]
                function.restype = c.c_int32
                self._monitor_info_function = function
            function = self._monitor_info_function
        info = MonitorInfo()
        info.cbSize = c.sizeof(MonitorInfo)
        if not function(monitor, c.byref(info)) or not info.szDevice:
            raise AppBarError("Selected Qt screen's native monitor information is unavailable")
        return info

    def screen_identity(self, screen):
        """Map this QScreen's actual HMONITOR, never its label or logical geometry."""
        try:
            interface = screen.nativeInterface()
            monitor = int(interface.handle())
        except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError) as error:
            raise AppBarError(
                "Selected Qt screen's Windows native interface is unavailable"
            ) from error
        if not 0 < monitor < 1 << (c.sizeof(c.c_void_p) * 8):
            raise AppBarError("Selected Qt screen's native monitor handle is unavailable")
        info = self._monitor_info(monitor)
        return ScreenIdentity(info.szDevice, monitor, screen.name())

    def _api(self):
        if self._functions is None:
            if sys.platform != "win32":
                raise AppBarError("Windows AppBar is unavailable on this platform")
            user, kernel = (
                c.WinDLL("user32", use_last_error=True),
                c.WinDLL("kernel32", use_last_error=True),
            )
            definitions = {
                "thread": (kernel.GetCurrentThreadId, [], c.c_uint32),
                "owner": (
                    user.GetWindowThreadProcessId,
                    [c.c_void_p, c.POINTER(c.c_uint32)],
                    c.c_uint32,
                ),
                "get_prop": (user.GetPropW, [c.c_void_p, c.c_wchar_p], c.c_void_p),
                "set_prop": (user.SetPropW, [c.c_void_p, c.c_wchar_p, c.c_void_p], c.c_int32),
                "remove_prop": (user.RemovePropW, [c.c_void_p, c.c_wchar_p], c.c_void_p),
                "monitor": (user.MonitorFromWindow, [c.c_void_p, c.c_uint32], c.c_void_p),
                "monitor_info": (
                    user.GetMonitorInfoW,
                    [c.c_void_p, c.POINTER(MonitorInfo)],
                    c.c_int32,
                ),
                "dpi": (user.GetDpiForWindow, [c.c_void_p], c.c_uint32),
                "visible": (user.IsWindowVisible, [c.c_void_p], c.c_int32),
                "foreground": (user.GetForegroundWindow, [], c.c_void_p),
                "message": (user.RegisterWindowMessageW, [c.c_wchar_p], c.c_uint32),
                "position": (
                    user.SetWindowPos,
                    [
                        c.c_void_p,
                        c.c_void_p,
                        c.c_int32,
                        c.c_int32,
                        c.c_int32,
                        c.c_int32,
                        c.c_uint32,
                    ],
                    c.c_int32,
                ),
            }
            functions = {}
            for key, (function, arguments, result) in definitions.items():
                function.argtypes, function.restype = arguments, result
                functions[key] = function
            self.callback_message = int(functions["message"]("DesktopStats.TopBar.Callback"))
            self.taskbar_message = int(functions["message"]("TaskbarCreated"))
            if (
                not 0xC000 <= self.callback_message <= 0xFFFF
                or not 0xC000 <= self.taskbar_message <= 0xFFFF
            ):
                raise AppBarError("AppBar notification messages could not be registered")
            self._functions = functions
        return self._functions

    def _check_current_window(self, hwnd):
        api = self._api()
        pid = c.c_uint32()
        thread = int(api["owner"](hwnd, c.byref(pid)))
        if pid.value != os.getpid() or not thread or thread != int(api["thread"]()):
            raise AppBarError("Top bar HWND is not on this process's GUI thread")

    def prepare(self, window, screen):
        # Qt handles the initial logical screen placement. Native coordinates
        # below are obtained from that very HWND and checked against its target.
        identity = self.screen_identity(screen)
        window.setScreen(screen)
        center = screen.geometry().center()
        window.setPosition(center.x() - window.width() // 2, center.y() - window.height() // 2)
        hwnd = int(window.winId())
        self._check_current_window(hwnd)
        api = self._api()
        if api["get_prop"](hwnd, WINDOW_GENERATION_PROPERTY):
            raise AppBarError("Own top bar HWND already has a generation cookie")
        nonce = secrets.randbits(c.sizeof(c.c_void_p) * 8 - 1) or 1
        if not api["set_prop"](hwnd, WINDOW_GENERATION_PROPERTY, c.c_void_p(nonce)):
            raise AppBarError("Cannot retain own top bar window generation")
        token = None
        try:
            token = self.backend.retain_window(hwnd, nonce)
            info = self._snapshot(token, identity.native_id, identity.monitor_handle)
            return Binding(
                window, token, identity.native_id, *info, identity.monitor_handle, screen
            )
        except Exception as error:
            try:
                if token is not None:
                    self.backend.validate(token)
                self._check_current_window(hwnd)
                if int(api["get_prop"](hwnd, WINDOW_GENERATION_PROPERTY) or 0) != nonce:
                    raise AppBarError("Own window generation changed during preparation")
                if int(api["remove_prop"](hwnd, WINDOW_GENERATION_PROPERTY) or 0) != nonce:
                    raise AppBarError("Own window preparation cleanup was not confirmed")
                if token is not None:
                    self.backend.release_window(token)
            except Exception as cleanup_error:
                # A failed retain can leave a valid cookie without a sealed token.
                # Preserve this actual own QWindow rather than destroy an unproved
                # generation; retry will fail closed until the process exits.
                retained = token or SimpleNamespace(hwnd=hwnd, generation=nonce)
                binding = Binding(
                    window,
                    retained,
                    identity.native_id,
                    None,
                    None,
                    96,
                    identity.monitor_handle,
                    screen,
                )
                raise WindowPreparationError(
                    f"{error}; cleanup: {cleanup_error}", binding
                ) from error
            raise

    def _snapshot(self, token, screen_name, selected_monitor):
        self.backend.validate(token)
        api = self._api()
        monitor = int(api["monitor"](token.hwnd, 0) or 0)  # No nearest-monitor fallback.
        if not monitor or monitor != selected_monitor:
            raise AppBarError("Owned window HMONITOR does not match the selected Qt screen")
        info = self._monitor_info(monitor)
        if info.szDevice.casefold() != screen_name.casefold():
            raise AppBarError("Owned window monitor does not match the selected display")
        dpi = int(api["dpi"](token.hwnd))
        if not 48 <= dpi <= 768:
            raise AppBarError("Owned window's per-monitor DPI is unavailable")

        def rect(value):
            return PixelRect(value.left, value.top, value.right, value.bottom)

        return rect(info.rcMonitor), rect(info.rcWork), dpi

    def snapshot(self, binding):
        identity = self.screen_identity(binding.screen)
        if identity.native_id.casefold() != binding.screen_name.casefold():
            raise AppBarError("Selected Qt screen's native device identity changed")
        binding.monitor, binding.work, binding.dpi = self._snapshot(
            binding.token, binding.screen_name, identity.monitor_handle
        )
        binding.monitor_handle = identity.monitor_handle
        return binding.monitor, binding.work, binding.dpi

    def session(self, binding):
        return AppBarSession(self.backend, binding.token, self.callback_message)

    def proposed_band(self, binding, height):
        approved = self.backend.send(binding.token, ABM_QUERYPOS, rect=binding.monitor)
        pixels = math.ceil(height * binding.dpi / 96)
        if approved.height < pixels:
            raise AppBarError("Selected display cannot fit the requested top bar")
        return PixelRect(approved.left, approved.top, approved.right, approved.top + pixels)

    def show(self, binding, *, activate=False):
        self.backend.validate(binding.token)
        api = self._api()
        foreground = int(api["foreground"]() or 0)
        binding.window.show()
        self.backend.validate(binding.token)
        if not api["visible"](binding.hwnd):
            raise AppBarError("Owned top bar window did not become visible")
        if (
            not activate
            and foreground != binding.hwnd
            and int(api["foreground"]() or 0) == binding.hwnd
        ):
            self.hide(binding)
            raise AppBarError("Non-activating top bar unexpectedly took focus")
        if activate:
            binding.window.requestActivate()  # Only from a user's click/keyboard action.

    def hide(self, binding):
        self.backend.hide(binding.token)
        binding.window.hide()

    def release(self, binding):
        self.backend.validate(binding.token)
        api = self._api()
        removed = int(api["remove_prop"](binding.hwnd, WINDOW_GENERATION_PROPERTY) or 0)
        if removed != binding.token.generation:
            raise AppBarError("Own window generation removal could not be confirmed")
        self.backend.release_window(binding.token)

    def place_panel(self, binding, anchor, work, dpi):
        self.backend.validate(binding.token)
        scale = dpi / 96
        width = min(math.ceil(binding.window.width() * scale), max(1, work.width - 16))
        height = min(math.ceil(binding.window.height() * scale), max(1, work.height - 16))
        left = min(
            max(anchor.left + (anchor.width - width) // 2, work.left + 8), work.right - width - 8
        )
        top = min(max(anchor.bottom + math.ceil(6 * scale), work.top + 8), work.bottom - height - 8)
        if not self._api()["position"](
            binding.hwnd, c.c_void_p(-1), left, top, width, height, 0x0010
        ):
            raise AppBarError("Owned detail panel positioning failed")

    def coating_allowed(self):
        # Same policy and alpha surface as existing widgets; no new glass backend.
        from native_platform import transparency_enabled

        return transparency_enabled()


class MetricRows(QAbstractListModel):
    """Stable metric delegates: live readings must not restart hover gestures."""

    lengthChanged = Signal()
    READING_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent):
        super().__init__(parent)
        self._values = []

    def roleNames(self):
        return {self.READING_ROLE: b"modelData"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._values)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == self.READING_ROLE and 0 <= index.row() < len(self._values):
            return self._values[index.row()]
        return None

    length = Property(int, lambda self: len(self._values), notify=lengthChanged)

    def update(self, values):
        if [row["id"] for row in values] != [row["id"] for row in self._values]:
            self.beginResetModel()
            self._values = list(values)
            self.endResetModel()
            self.lengthChanged.emit()
            return
        changed = []
        for index, value in enumerate(values):
            if value != self._values[index]:
                self._values[index] = value
                changed.append(index)
        # One notification per contiguous range retains every changed reading
        # without re-creating delegates or dispatching sixty-four Qt signals.
        while changed:
            first = last = changed.pop(0)
            while changed and changed[0] == last + 1:
                last = changed.pop(0)
            self.dataChanged.emit(self.index(first, 0), self.index(last, 0), [self.READING_ROLE])

    # Retain ordinary sequence access for the manager and isolated QA.
    def __getitem__(self, index):
        return self._values[index]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class BarViewState(QObject):
    changed = Signal()
    motionChanged = Signal()
    detailChanged = Signal()
    materialChanged = Signal()
    operationChanged = Signal()

    def __init__(self, manager, host_id):
        super().__init__(manager)
        self.manager, self._host_id = manager, host_id
        self._rows, self._config, self._menu, self._overflow = [], {}, {}, None
        self._row_model = MetricRows(self)
        self._overflow_model = MetricRows(self)
        self._colors = {}
        self._spacing = 12.0
        self._detail, self._coating, self._overflow_count, self._panel_maximum = {}, False, 0, 480.0
        self._policy_allowed, self._material_reports = None, {}
        self._native_material, self._detail_coating = False, False
        self._operation_message = ""
        self._operation_timer = QTimer(self)
        self._operation_timer.setSingleShot(True)
        self._operation_timer.setInterval(3200)
        self._operation_timer.timeout.connect(self._clear_operation)

    hostId = Property(str, lambda self: self._host_id, constant=True)
    motionEnabled = Property(
        bool, lambda self: getattr(getattr(self.manager, 'controller', None), 'motionEnabled', False) is True,
        notify=motionChanged,
    )
    rows = Property(QObject, lambda self: self._row_model, constant=True)
    overflowRows = Property(QObject, lambda self: self._overflow_model, constant=True)
    config = Property("QVariantMap", lambda self: self._config, notify=changed)
    menuRect = Property("QVariantMap", lambda self: self._menu, notify=changed)
    overflowRect = Property("QVariant", lambda self: self._overflow, notify=changed)
    overflowCount = Property(int, lambda self: self._overflow_count, notify=changed)
    spacing = Property(
        float,
        lambda self: self._spacing,
        notify=changed,
    )
    coatingTranslucent = Property(bool, lambda self: self._coating, notify=changed)
    detailCoatingTranslucent = Property(
        bool, lambda self: self._detail_coating if self._native_material else self._coating,
        notify=materialChanged
    )
    ink = Property(str, lambda self: self._colors.get("ink", "#202833"), notify=changed)
    muted = Property(str, lambda self: self._colors.get("muted", "#566272"), notify=changed)
    fontFamily = Property(
        str, lambda self: ui_font(self._config.get("language", "en")), notify=changed
    )
    detail = Property("QVariantMap", lambda self: self._detail, notify=detailChanged)
    pinned = Property(bool, lambda self: self._detail.get("mode") == "pinned", notify=detailChanged)
    panelMaximumHeight = Property(float, lambda self: self._panel_maximum, notify=changed)
    materialReports = Property("QVariantMap", lambda self: self._material_reports, notify=materialChanged)
    operationMessage = Property(str, lambda self: self._operation_message, notify=operationChanged)

    def _clear_operation(self):
        self._operation_timer.stop()
        if self._operation_message:
            self._operation_message = ""
            self.operationChanged.emit()

    @Slot(str)
    def hoverMetric(self, item):
        self.manager.hover(self._host_id, item)

    @Slot()
    def leaveBar(self):
        self.manager.leave()

    @Slot()
    def enterPanel(self):
        self.manager.enter_panel()

    @Slot()
    def leavePanel(self):
        self.manager.leave()

    @Slot(str)
    def clickMetric(self, item):
        self.manager.click(self._host_id, item)

    @Slot(str, str, str, result=bool)
    def moveMetric(self, item, before, placement):
        self._clear_operation()
        moved = self.manager.move_metric(item, before, placement)
        if not moved:
            message = getattr(self.manager.controller, "status", "")
            self._operation_message = message if isinstance(message, str) and message else self.tr("未能保存，请重试")
            self.operationChanged.emit()
            self._operation_timer.start()
        return moved

    @Slot()
    def closePanel(self):
        self.manager.close_panel()

    @Slot()
    def openSettings(self):
        self.manager.open_settings()

    @Slot()
    def openHistory(self):
        self.manager.open_history(self._host_id)

    @Slot()
    def menu(self):
        self.manager.menu(self._host_id)

    @Slot()
    def pause(self):
        self.manager.pause()

    @Slot(str, result=str)
    def tr(self, text):
        from localization import translate

        return translate(text, self._config.get("language", "en"))


@dataclass
class Host:
    screen: object
    state: BarViewState
    window: object
    binding: object = None
    session: object = None
    rect: PixelRect | None = None
    overflow_ids: tuple = ()
    closing: bool = False
    applied_monitor: PixelRect | None = None
    applied_dpi: int | None = None
    applied_height: int | None = None
    shell_epoch: int = 0
    geometry_key: object = None
    geometry: object = None
    material_bridge: object = None


class NativeBarEvents(QAbstractNativeEventFilter):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) != b"windows_generic_MSG" or self.manager.closed:
            return False, 0
        address = int(message) if message is not None else 0
        if address:
            native = w.MSG.from_address(address)
            self.manager.native_message(
                int(native.hWnd or 0), int(native.message), int(native.wParam), int(native.lParam)
            )
        return False, 0  # Qt still handles its own DPI/geometry/activation messages.


class TopBarManager(QObject):
    """One reserved host per selected screen, one optional shared details window."""

    def __init__(self, runtime, *, adapter=None, window_factory=None):
        super().__init__(runtime if isinstance(runtime, QObject) else None)
        self.runtime, self.app, self.controller = runtime, runtime.app, runtime.controller
        self.adapter = adapter if adapter is not None else WindowsTopBarAdapter()
        self._injected = adapter is not None
        self._window_factory = window_factory
        self.hosts, self.retired, self._components = {}, [], {}
        self.closed = self.paused = self._applying = self._closing = False
        self._config, self._rows, self._widths, self._errors = {}, [], {}, []
        self._coating, self._style = False, {}
        self._reported_status = ("disabled", "", ())
        self._font_metrics, self._text_widths, self._short_labels = (
            OrderedDict(), OrderedDict(), OrderedDict()
        )
        self._panel = self._pending_hover = None
        self._notifications, self._shell_pending, self._shell_epoch = {}, False, 0
        self._dispatching_fullscreen = False
        self._filter, self._filter_installed, self._menu = NativeBarEvents(self), False, None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(50)
        self._refresh_timer.timeout.connect(self._refresh)
        self._rows_timer = QTimer(self)
        self._rows_timer.setSingleShot(True)
        self._rows_timer.setInterval(100)
        self._rows_timer.timeout.connect(self._rows_tick)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._open_hover)
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(250)
        self._close_timer.timeout.connect(self.close_panel)
        self._panel_geometry_timer = QTimer(self)
        self._panel_geometry_timer.setSingleShot(True)
        self._panel_geometry_timer.setInterval(0)
        self._panel_geometry_timer.timeout.connect(self._position_panel_safely)
        self.controller.dataChanged.connect(self.queue_rows)
        motion_signal = getattr(self.controller, 'motionChanged', None)
        if motion_signal is not None:
            motion_signal.connect(self._motion_changed)

    @Slot()
    def _motion_changed(self):
        for identifier, host in tuple(self.hosts.items()):
            if self.closed:
                return
            if self.hosts.get(identifier) is host:
                host.state.motionChanged.emit()

    def _status(self, state, reason="", missing=()):
        self._reported_status = (state, reason, tuple(missing))
        hosts = []
        for screen_id, host in list(self.hosts.items())[:16]:
            visible = getattr(host.window, "isVisible", None)
            status = getattr(host.material_bridge, "status", None)
            life = status() if callable(status) else {}
            hosts.append(dict(
                screen_id=screen_id,
                visible=bool(visible() if callable(visible) else getattr(host.window, "visible", False)),
                width=host.window.width(), height=host.window.height(),
                visible_metric_count=len(host.state._rows), overflow_count=len(host.overflow_ids),
                material=dict(host.state._material_reports.get("bar", {})),
                material_lifecycle={key: life[key] for key in (
                    "state", "started", "surface_alive", "render_ready", "render_gate",
                    "first_frame_observed", "exposed", "attempt", "applies_total", "timer_active", "backend"
                ) if key in life},
            ))
        report = dict(
            state=state,
            enabled=bool(self._config.get("top_bar", {}).get("enabled")),
            active_screens=list(self.hosts),
            missing_screens=list(missing),
            reason=reason,
            detail=reason,
            errors=list(self._errors),
            paused=self.paused,
            native_blur_verified=False,
            hosts=hosts,
        )
        self.controller.set_top_bar_status(report)

    def _available(self):
        return self._injected or (
            not self.runtime.headless
            and sys.platform == "win32"
            and self.app.platformName() == "windows"
        )

    def _targets(self, bar):
        screens = self.app.screens()
        mode = bar.get("monitor_mode", "primary")
        if mode == "primary":
            primary = self.app.primaryScreen()
            screens = [primary] if primary is not None else []
        names = set(bar.get("screens", []))
        if mode == "selected" and not names:
            return [], []
        identified, errors, duplicates = {}, [], set()
        for screen in screens:
            try:
                identifier = self.adapter.screen_identity(screen).native_id
                if identifier in identified:
                    duplicates.add(identifier)
                identified[identifier] = screen
            except Exception as error:
                errors.append(screen.name() + ": " + str(error))
        for identifier in duplicates:
            identified.pop(identifier)
            self._errors.append(identifier + ": ambiguous native screen identity")
        missing = sorted(names - set(identified)) if mode == "selected" else []
        if mode != "selected" or missing:
            self._errors.extend(errors)
        return [
            (identifier, screen)
            for identifier, screen in identified.items()
            if mode != "selected" or identifier in names
        ], missing

    def apply(self, config):
        if self.closed or self._applying:
            return
        self._applying = True
        try:
            previous = self._config.get("top_bar")
            self._config = copy.deepcopy(config)
            bar = self._config.get("top_bar", {})
            if previous != bar:
                self.paused = False
                self._widths.clear()
            self._errors = []
            if not bar.get("enabled") or self.paused:
                self._close_hosts()
                self._retry_retired()
                self._status(
                    "failed" if self.retired else "paused" if self.paused else "disabled",
                    "顶部状态栏清理未完成。" if self.retired else "",
                )
                return
            self._retry_retired()
            if self.retired:
                self._status("failed", "顶部状态栏清理未完成。")
                return
            if not self._available():
                self._status("unavailable", "顶部状态栏仅可在 Windows 桌面模式使用。")
                return
            targets, missing = self._targets(bar)
            self._coating = self.adapter.coating_allowed()
            self._style = top_bar_style(config)
            names = {identifier for identifier, screen in targets}
            for name in list(self.hosts):
                if name not in names:
                    self._drop(name)
            if self.retired:
                self._status(
                    "partial" if self.hosts else "failed", "顶部状态栏清理未完成。", missing
                )
                return
            self.update_rows()
            for name, screen in targets:
                if self.closed or self.paused:
                    return
                if self.retired:
                    self._status(
                        "partial" if self.hosts else "failed", "顶部状态栏清理未完成。", missing
                    )
                    return
                host = self.hosts.get(name)
                try:
                    if host is not None and host.screen is not screen:
                        self._drop(name)
                        host = None
                        if self.retired:
                            raise AppBarError("Prior display generation cleanup is incomplete")
                    if host is None:
                        host = self._new_host(screen, name)
                        self.hosts[name] = host
                    self._sync_host(host)
                    if self.closed or self.paused:
                        return
                except Exception as error:
                    if self.closed or self.paused:
                        self._status(
                            "failed" if self.retired else "disabled" if self.closed else "paused",
                            "顶部状态栏清理未完成。" if self.retired else "",
                        )
                        return
                    self._errors.append(name + ": " + str(error))
                    if name in self.hosts:
                        self._drop(name)
                    elif host is not None:
                        self._dispose(host)
            if self.hosts and not self._filter_installed and not self._injected:
                self.app.installNativeEventFilter(self._filter)
                self._filter_installed = True
            state = "ready" if self.hosts else "missing_screen"
            if self._errors:
                state = "partial" if self.hosts else "failed"
            elif missing and self.hosts:
                state = "partial"
            self._status(
                state,
                "无法为部分显示器预留顶部空间。"
                if self._errors
                else "所选显示器未连接。"
                if missing
                else "",
                missing,
            )
        except Exception as error:
            self._errors.append(str(error))
            self._close_hosts()
            self._status("failed", "无法创建顶部状态栏。")
        finally:
            self._applying = False

    def _new_host(self, screen, native_id):
        if self.closed or self.paused:
            raise AppBarError("Top bar stopped before preparing its own window")
        state = BarViewState(self, native_id)
        state._config = self._style
        state._coating = self._coating
        window = self._make_window("bar", state, screen, False)
        # A host created after a pending Shell broadcast is already registered
        # with that new Shell. It must not be registered a second time later.
        host = Host(screen, state, window, shell_epoch=self._shell_epoch + int(self._shell_pending))
        try:
            if self.closed or self.paused:
                raise AppBarError("Top bar stopped while creating its own window")
            host.material_bridge = self._material_bridge(window, state)
            if self.closed or self.paused:
                raise AppBarError("Top bar stopped while creating its material")
            host.binding = self.adapter.prepare(window, screen)
            self._bind_material(host.material_bridge, host.binding)
            if self.closed or self.paused:
                raise AppBarError("Top bar stopped while retaining its own window")
            if host.binding.screen_name.casefold() != native_id.casefold():
                raise AppBarError("Selected native display changed while preparing the top bar")
            host.session = self.adapter.session(host.binding)
            return host
        except Exception as error:
            if isinstance(error, WindowPreparationError):
                host.binding = error.binding
                self._bind_material(host.material_bridge, host.binding)
            self._dispose(host)
            raise

    def _make_window(self, kind, state, screen, pinned):
        if self._window_factory:
            return self._window_factory(kind, state, screen, pinned)
        name = "TopBar.qml" if kind == "bar" else "TopBarDetails.qml"
        if name not in self._components:
            component = QQmlComponent(
                self.runtime.engine, QUrl.fromLocalFile(str(ASSETS / "native" / name))
            )
            if component.isError():
                raise AppBarError("; ".join(error.toString() for error in component.errors()))
            self._components[name] = component
        window = self._components[name].createWithInitialProperties({"barState": state})
        if window is None:
            raise AppBarError("Could not create own top bar window")
        window.setFlag(Qt.WindowType.WindowDoesNotAcceptFocus, not pinned)
        if kind == "bar":
            window.resize(1, 1)
        elif self._native_windows() and not self._injected:
            from top_bar_backdrop_host import TopBarBackdropHost

            window = TopBarBackdropHost(window, pinned=pinned, close_panel=self.close_panel)
        return window

    def _material_bridge(self, window, state, kind="bar"):
        # Injected/offscreen clients cannot opt into native material by merely
        # furnishing a fake HWND. Attach before prepare() creates our HWND.
        if not self._native_windows():
            return None
        from native_platform import transparency_policy
        from native_widget_material import WidgetBlurBackend
        from settings_material_bridge import SettingsMaterialBridge

        quick_client = getattr(window, "quick_client", None)
        raster_details = kind == "details" and quick_client is not None
        material = BarMaterial(WidgetBlurBackend() if not raster_details else None,
                               self.adapter.backend.validate)
        if raster_details:
            from top_bar_backdrop_host import DetailAcrylicBackend

            material.backend = DetailAcrylicBackend(window, validate=material.check)
        state._native_material = True
        if kind == "bar":
            state._policy_allowed = state._coating = False
        else:
            state._detail_coating = False
            state._material_reports = {
                key: value for key, value in state._material_reports.items() if key != "details"
            }
            state.materialChanged.emit()

        prepared = None
        recovery_events = {
            "theme_changed", "composition_changed", "power_changed", "display_changed",
            "system_preferences", "preference_changed",
        }

        def current_details():
            panel = self._panel
            return bool(not self.closed and not material.closed and panel is not None
                        and panel["window"] is window and panel["host"].state is state
                        and panel.get("binding") is material.binding
                        and panel.get("material_bridge") is material)

        def detail_surface():
            if not current_details():
                raise AppBarError("Detail material no longer belongs to the current panel")
            material.check(material.binding.hwnd)
            context = material.bridge.status()
            identity = (context.get("surface_serial"), context.get("surface_handle"))
            if (not context.get("surface_alive") or type(identity[0]) is not int or identity[0] <= 0
                    or identity[1] != material.binding.hwnd or identity != material.bound_surface):
                raise AppBarError("Detail material surface has changed since preparation")
            return identity, context

        def compose(handle, policy):
            nonlocal prepared
            style = state._config
            enabled = effective_skin(style) in GLASS_SKINS
            if kind == "details":
                if material.binding is None or handle != material.binding.hwnd:
                    raise AppBarError("Detail request does not match its retained window")
                surface, context = detail_surface()
                reasons = (context.get("last_request") or {}).get("reasons", ())
                key = (material.binding.token, surface, enabled, dict(policy))
                if prepared is not None and prepared[0] == key and not recovery_events.intersection(reasons):
                    # First-frame/show/activation and automatic retries adopt
                    # the hidden setup; they must not switch a visible fallback
                    # into glass. Real policy/style/system changes may retry.
                    return copy.deepcopy(prepared[1])
                # A genuine recovery/policy change ends bootstrap adoption.
                # Its finite retry episode must reach the backend again.
                prepared = None
            report = material.apply(handle, enabled, policy)
            if kind == "details":
                after, _ = detail_surface()  # Native calls can dispatch surface replacement.
                if after != surface:
                    raise AppBarError("Detail panel changed during material preparation")
                report = dict(report, surface_serial=surface[0],
                              preparation="before-show" if not window.isVisible() else "recovery")
                if not window.isVisible():
                    prepared = key, copy.deepcopy(report)
            return report

        def publish(report):
            if self.closed:
                return
            if kind == "details":
                if not current_details():
                    return
                surface, _ = detail_surface()
                if report.get("surface_serial") != surface[0]:
                    return
            state._material_reports = dict(state._material_reports, **{kind: dict(report)})
            translucent = report.get("coating_translucent") is True
            if kind == "details":
                state._detail_coating = translucent
                state.materialChanged.emit()
            else:
                state.materialChanged.emit()
                if state._policy_allowed != translucent:
                    state._policy_allowed = translucent
                    host = self.hosts.get(state._host_id)
                    if host is not None and not host.closing:
                        self._layout(host)
            if self.hosts.get(state._host_id) is not None:
                self._status(*self._reported_status)

        material.bridge = SettingsMaterialBridge(
            window, self, compose_once=compose, policy_reader=transparency_policy,
            backend="desktop-acrylic" if raster_details else "system-blur",
            publish=publish, release_surface=material.clear,
            wait_for_first_frame=True,
            frame_source=quick_client if raster_details else None,
        )
        material.bridge.start()
        if kind == "details":
            def prepare_before_show():
                if window.isVisible() or not current_details():
                    raise AppBarError("Detail material requires the current hidden panel")
                binding = material.binding
                report = compose(binding.hwnd, transparency_policy())
                publish(report)  # QML sees the final coating before its first paint.
                return report

            material._prepare_before_show = prepare_before_show
        return material

    def _native_windows(self):
        return (not self._injected and not self.runtime.headless and sys.platform == "win32"
                and self.app.platformName() == "windows")

    @staticmethod
    def _bind_material(material, binding):
        bind = getattr(material, "bind", None)
        if callable(bind):
            bind(binding)

    def _sync_host(self, host, *, shell_recreated=False):
        if self.closed or self.paused or host.closing:
            return
        binding = host.binding
        self.adapter.snapshot(binding)
        if self.closed or self.paused or host.closing:
            return
        height = self._config["top_bar"]["height"]
        if shell_recreated:
            result = host.session.shell_recreated(self._shell_epoch)
            if result.ready and (
                host.applied_monitor != binding.monitor
                or host.applied_dpi != binding.dpi
                or host.applied_height != height
            ):
                result = host.session.relayout(binding.monitor, dpi=binding.dpi, height_dip=height)
        elif host.rect is None:
            result = host.session.register(binding.monitor, dpi=binding.dpi, height_dip=height)
        else:
            proposed = self.adapter.proposed_band(binding, height)
            if self.closed or self.paused or host.closing:
                return
            if (
                proposed == host.rect
                and binding.dpi == host.applied_dpi
                and binding.monitor == host.applied_monitor
                and height == host.applied_height
            ):
                self._layout(host)
                return
            result = host.session.relayout(binding.monitor, dpi=binding.dpi, height_dip=height)
        if self.closed or self.paused or host.closing:
            return
        if not result.ready:
            raise AppBarError("; ".join(result.errors) or "AppBar reservation is not ready")
        host.rect = result.physical_rect
        host.shell_epoch = self._shell_epoch + int(self._shell_pending)
        host.applied_monitor, host.applied_dpi, host.applied_height = (
            binding.monitor,
            binding.dpi,
            height,
        )
        self._layout(host)
        if self.closed or self.paused or host.closing:
            return
        self.adapter.show(binding, activate=False)

    @staticmethod
    def _cached(cache, key, create, maximum):
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        value = create()
        cache[key] = value
        if len(cache) > maximum:
            cache.popitem(last=False)
        return value

    def _measure(self, family, size, weight, text, dpi, *, tabular=False):
        key = (family, size, weight, tabular, dpi)

        def metrics():
            font = QFont(family)
            font.setPixelSize(size)
            font.setWeight(weight)
            if tabular:
                font.setFeature(QFont.Tag("tnum"), 1)
            return QFontMetricsF(font)

        measured = self._cached(self._font_metrics, key, metrics, 24)
        return self._cached(
            self._text_widths, (key, text), lambda: measured.horizontalAdvance(text), 2048
        )

    def _content_width(self, row, family, dpi):
        """Measure one unchanged single-reading renderer in logical pixels."""
        style = row['style']
        short = row.get('bar_label') or row['label']
        size = 9 if style == 'graph' else 11 if style in ('stacked', 'duplex') else 12
        split = isinstance(row.get('number_text'), str)
        number = row['number_text'] if split else str(row['value'])
        unit = row.get('unit_text', '') if split else ''
        suffix = 3 + self._measure(
            family, 9 if style in ('graph', 'stacked') else 10,
            QFont.Weight.Normal, unit, dpi,
        ) if unit else 0
        actual = self._measure(family, size, QFont.Weight.Medium, number, dpi, tabular=True) + suffix
        reserve = row.get('number_reserve', '999.9') if split else '999.9 ' + row.get('unit', '')
        stable_value = actual if style == 'graph' else max(
            actual, self._measure(family, size, QFont.Weight.Medium, reserve, dpi, tabular=True) + suffix,
        )
        if style == 'label_value':
            return min(110, self._measure(family, 11, QFont.Weight.Normal, short, dpi)) + 6 + stable_value
        if style == 'stacked':
            return max(min(66, self._measure(family, 9, QFont.Weight.Normal, short, dpi)), stable_value)
        if style == 'graph':
            return max(44, actual)
        if style in ('duplex', 'duplex_inline'):
            widths = [18 + max(
                self._measure(family, 11, QFont.Weight.Medium, str(channel.get('number_text', '—')), dpi, tabular=True),
                self._measure(family, 11, QFont.Weight.Medium, '999.9', dpi, tabular=True),
            ) + (3 + self._measure(family, 9, QFont.Weight.Normal, str(channel.get('unit_text', '')), dpi)
                 if channel.get('unit_text') else 0) for channel in row.get('paired_rows', [])[:2]]
            return (sum(widths) + 12 * max(0, len(widths)-1)
                    if style == 'duplex_inline' else max(widths, default=stable_value))
        return {'value': 0, 'icon_value': 23, 'trend_value': 42,
                'bar_value': 28, 'ring_value': 20}[style] + stable_value

    def _layout(self, host):
        binding, config, rows_snapshot = host.binding, self._config, self._rows

        def current():
            return (not self.closed and not self.paused and not host.closing
                    and self.hosts.get(host.state._host_id) is host
                    and host.binding is binding and binding is not None
                    and self._config is config and self._rows is rows_snapshot)

        if host.rect is None or not current():
            return
        state, rect = host.state, host.rect
        spacing = float(self._config.get("top_bar", {}).get("spacing", 12))
        dpi, scale = host.binding.dpi, host.binding.dpi / 96
        language = self._config.get("language", "en")
        family = ui_font(language)
        items, rows = [], []
        for row in self._rows:
            value = dict(row)
            short = row.get("bar_label") or self._cached(
                self._short_labels, (row["metric"], row["label"], language),
                lambda: label_options(row["metric"], row["label"], language)[-1], 256
            )
            value["bar_label"] = short
            style = row["style"]
            children = row.get('group_rows', []) if row.get('grouped') is True else []
            width = (sum(self._content_width(child, family, dpi) for child in children)
                     + 10 * (len(children)-1)) if children else self._content_width(value, family, dpi)
            members = tuple((child['metric'], child.get('bar_label'), child.get('unit')) for child in children)
            key = (row["id"], style, short, row.get("unit", ""), family, dpi, members)
            self._widths[key] = max(width, self._widths.get(key, 0))
            items.append(MetricItem(row["id"], self._widths[key], row["placement"]))
            rows.append(value)
        # The reservation may be shifted by another AppBar; plan from its exact
        # final rectangle rather than the monitor top or Qt's global coordinates.
        geometry_key = (rect, dpi, self._config["top_bar"]["height"], spacing,
                        tuple((item.id, item.measured_width_dip, item.placement) for item in items))
        geometry_changed = host.geometry_key != geometry_key
        if geometry_changed:
            host.geometry = plan_top_bar(rect, dpi=dpi, items=items,
                                         height_dip=self._config["top_bar"]["height"],
                                         gap_dip=spacing)
            host.geometry_key = geometry_key
        plan = host.geometry

        def relative(box):
            return dict(
                x=(box.left - rect.left) / scale,
                y=(box.top - rect.top) / scale,
                width=box.width / scale,
                height=box.height / scale,
            )

        by_id = {row["id"]: row for row in rows}
        visible, groups = [], set()
        for item in plan.items:
            value = dict(by_id[item.id], **relative(item.rect))
            value["group_start"] = value["placement"] not in groups
            groups.add(value["placement"])
            visible.append(value)
        prior_view = (state._menu, state._overflow, state._overflow_count,
                      state._panel_maximum, state._config, state._coating, state._spacing)
        state._rows, state._menu = visible, relative(plan.menu_hit)
        state._row_model.update(visible)
        if not current():
            return  # Model notifications can synchronously close/reconfigure a host.
        state._overflow = relative(plan.overflow_hit) if plan.overflow_hit else None
        state._overflow_count = len(plan.overflow_ids)
        state._panel_maximum = max(100, min(480, host.binding.work.height / scale - 16))
        state._config = self._style
        state._coating = self._coating if state._policy_allowed is None else state._policy_allowed
        state._spacing = spacing
        host.overflow_ids = plan.overflow_ids
        current_view = (state._menu, state._overflow, state._overflow_count,
                        state._panel_maximum, state._config, state._coating, state._spacing)
        if current_view != prior_view or not state._colors:
            state._colors = palette(effective_skin(self._style), self._style.get("theme") == "dark",
                                    self._style.get("opacity", 94), frosted=state._coating,
                                    **glass_options(self._style))
            state.changed.emit()
        if not current():
            return
        native_changed = any(prior_view[4].get(key) != self._style.get(key)
                             for key in ("skin", "theme"))
        if native_changed:
            if host.material_bridge is not None:
                host.material_bridge.request("preference_changed")
            if not current():
                return
            if self._panel and self._panel["host"] is host:
                bridge = self._panel.get("material_bridge")
                if bridge is not None:
                    bridge.request("preference_changed")
        if geometry_changed and self._panel and self._panel["host"] is host:
            self._position_panel_safely()

    @Slot()
    def queue_rows(self):
        if self.hosts and not self.closed and not self._rows_timer.isActive():
            self._rows_timer.start()

    @Slot()
    def update_rows(self):
        self._rows_timer.stop()
        if not self._config.get("top_bar", {}).get("enabled") or self.paused or self.closed:
            return
        config = self._config
        rows = self.controller.topBarRows()
        if self.closed or self.paused or self._config is not config:
            return
        if (
            not isinstance(rows, list)
            or len(rows) > 64
            or len({row["id"] for row in rows}) != len(rows)
        ):
            raise AppBarError("Controller returned an invalid top bar row list")
        prefs = {item["id"]: item["prefs"] for item in self._config["top_bar"]["items"]}
        # The real Controller already projects each saved row. Legacy injected
        # controllers still receive the same pure formatter once, not twice.
        rows = [row if all(key in row for key in ("style", "placement", "icon", "trend_points"))
                else present_metric(row, prefs.get(row["id"], {})) for row in rows]
        changed = rows != self._rows
        self._rows = rows
        if changed:
            valid = {row["id"] for row in rows} | {OVERFLOW}
            if self._pending_hover and self._pending_hover[1] not in valid:
                self._pending_hover = None
                self._hover_timer.stop()
            if self._panel and self._panel["item"] not in valid:
                self.close_panel()
            for host in tuple(self.hosts.values()):
                if self.closed or self.paused or self._config is not config:
                    return
                if self.hosts.get(host.state._host_id) is not host or host.closing:
                    continue
                self._layout(host)
        if self.closed or self.paused or self._config is not config:
            return
        if self._panel:
            self._detail_data(self._panel["host"], self._panel["item"], self._panel["pinned"])

    def move_metric(self, item, before, placement):
        valid = {row["id"] for row in self._rows}
        if item not in valid or before and before not in valid or placement not in ("left", "right"):
            return False
        move = getattr(self.controller, "placeLiveTopBarMetric", None)
        return bool(move(item, before, placement)) if callable(move) else False

    def _rows_tick(self):
        try:
            self.update_rows()
        except Exception as error:
            if self.closed or self.paused:
                return  # Preserve the deliberate shutdown/pause status.
            self._errors.append("readings: " + str(error))
            self._close_hosts()
            self._status("failed", "无法更新顶部状态栏读数。")

    def _fullscreen_active(self):
        # The panel is shared across displays. Honor the Shell's entering
        # notification immediately, as well as each retained session's state;
        # waiting for the coalesced refresh would allow a late hover to reopen.
        return (self._dispatching_fullscreen
                or any(getattr(host.session, "_fullscreen", False) for host in self.hosts.values())
                or any(flags.get("fullscreen") is True for flags in self._notifications.values()))

    def hover(self, host_id, item):
        if (self.closed or host_id not in self.hosts or self._fullscreen_active()
                or self._panel and self._panel["pinned"]):
            return
        if item != OVERFLOW and not any(row["id"] == item for row in self._rows):
            return
        self._close_timer.stop()
        target = (host_id, item)
        if (
            self._panel
            and self._panel["host"] is self.hosts[host_id]
            and self._panel["item"] == item
        ):
            return
        if target != self._pending_hover:
            self._pending_hover = target
            self._hover_timer.start(80 if self._panel else 350)

    def leave(self):
        self._pending_hover = None
        self._hover_timer.stop()
        if self._panel and not self._panel["pinned"]:
            self._close_timer.start()

    def enter_panel(self):
        self._close_timer.stop()
        self._hover_timer.stop()
        self._pending_hover = None

    def _open_hover(self):
        target, self._pending_hover = self._pending_hover, None
        if target and target[0] in self.hosts:
            self._show_panel(self.hosts[target[0]], target[1], False)

    def click(self, host_id, item):
        host = self.hosts.get(host_id)
        if self.closed or host is None or self._fullscreen_active():
            return
        if (
            self._panel
            and self._panel["host"] is host
            and self._panel["item"] == item
            and self._panel["pinned"]
        ):
            self.close_panel()
        else:
            self._show_panel(host, item, True)

    def _detail_data(self, host, item, pinned):
        if item == OVERFLOW:
            items = [dict(row) for row in self._rows if row["id"] in host.overflow_ids]
            selected = dict(
                id=OVERFLOW,
                label=host.state.tr("更多指标"),
                value="",
                overflow=True,
                items=items,
            )
        else:
            getter = getattr(self.controller, "topBarDetailRow", None)
            selected = getter(item) if callable(getter) else next(
                (dict(row) for row in self._rows if row["id"] == item), None
            )
            if not isinstance(selected, dict) or selected.get("id") != item:
                selected = None
            if selected is None:
                self.close_panel()
                return False
            selected["overflow"] = False
        selected["mode"] = "pinned" if pinned else "hover"
        changed = host.state._detail != selected
        if item == OVERFLOW:
            host.state._overflow_model.update(items)
        if changed:
            host.state._detail = selected
            host.state.detailChanged.emit()
        return True

    def _details_allowed(self, host):
        return (not self.closed and not self.paused and not host.closing
                and self.hosts.get(host.state._host_id) is host
                and host.binding is not None and not self._fullscreen_active())

    def _show_panel(self, host, item, pinned):
        self._hover_timer.stop()
        self._close_timer.stop()
        self._pending_hover = None
        if not self._details_allowed(host):
            return
        if item != OVERFLOW and not any(row["id"] == item for row in self._rows):
            return
        if self._panel and (self._panel["host"] is not host or self._panel["pinned"] != pinned):
            self.close_panel()
            if self._panel is not None:
                return  # A synchronous cleanup callback owns this replacement.
        self._retry_retired()
        if not self._details_allowed(host):
            return
        if self.retired:
            self._status("partial", "顶部状态栏清理未完成。")
            return
        if not self._detail_data(host, item, pinned):
            return
        if not self._details_allowed(host):
            return
        window = bridge = panel = pending = None
        failed = False
        try:
            if self._panel is None:
                window = self._make_window("details", host.state, host.screen, pinned)
                pending = dict(host=host, item=item, pinned=pinned, window=window,
                               binding=None, material_bridge=None)
                if not self._details_allowed(host):
                    return
                bridge = self._material_bridge(window, host.state, "details")
                pending["material_bridge"] = bridge
                if not self._details_allowed(host):
                    return
                # Keep the exact returned lease locally before bind() can emit
                # callbacks or fail. A late record must never revive _panel.
                pending["binding"] = self.adapter.prepare(window, host.screen)
                self._bind_material(bridge, pending["binding"])
                if not self._details_allowed(host) or self._panel is not None:
                    return
                self._panel, pending = pending, None
                if self._native_windows():
                    window.widthChanged.connect(self._queue_panel_geometry)
                    window.heightChanged.connect(self._queue_panel_geometry)
            else:
                self._panel["item"] = item
            panel = self._panel
            self._position_panel()
            if not self._details_allowed(host) or self._panel is not panel:
                if self._panel is panel:
                    self.close_panel()
                return
            if window is not None:
                prepare = getattr(bridge, "prepare_before_show", None)
                if callable(prepare):
                    prepare()
            if not self._details_allowed(host) or self._panel is not panel:
                if self._panel is panel:
                    self.close_panel()
                return
            self.adapter.show(panel["binding"], activate=pinned)
            if not self._details_allowed(host) or self._panel is not panel:
                if self._panel is panel:
                    self.close_panel()
                return
            QTimer.singleShot(0, self._position_panel_safely)
        except Exception as error:
            failed = True
            self._errors.append("details: " + str(error))
            if pending is not None and isinstance(error, WindowPreparationError):
                pending["binding"] = error.binding
                try:
                    self._bind_material(bridge, pending["binding"])
                except Exception as bind_error:
                    self._errors.append("detail binding: " + str(bind_error))
            if panel is not None and self._panel is panel:
                self.close_panel()
        finally:
            if pending is not None:
                self._dispose_panel(pending)
            if self.closed or self.paused:
                self._status(
                    "failed" if self.retired else "disabled" if self.closed else "paused",
                    "顶部状态栏清理未完成。" if self.retired else "",
                )
            elif failed:
                self._status("partial", "无法打开指标详情。")
            elif pending is not None and self.retired:
                self._status("partial" if self.hosts else "failed", "顶部状态栏清理未完成。")

    def _position_panel_safely(self):
        try:
            self._position_panel()
        except Exception as error:
            self._errors.append("details: " + str(error))
            self.close_panel()
            self._status("partial", "无法打开指标详情。")

    @Slot()
    def _queue_panel_geometry(self):
        if self._panel and not self.closed and not self._panel_geometry_timer.isActive():
            self._panel_geometry_timer.start()

    def _position_panel(self):
        if self.closed or not self._panel:
            return
        panel = self._panel
        host, item = panel["host"], panel["item"]
        local = (
            host.state._overflow
            if item == OVERFLOW
            else next((row for row in host.state._rows if row["id"] == item), None)
        )
        if local is None:
            local = host.state._overflow
        if local is None:
            self.close_panel()
            return
        scale = host.binding.dpi / 96
        anchor = PixelRect(
            host.rect.left + round(local["x"] * scale),
            host.rect.top,
            host.rect.left + round((local["x"] + local["width"]) * scale),
            host.rect.bottom,
        )
        self.adapter.place_panel(
            panel["binding"], anchor, host.binding.work, host.binding.dpi
        )
        if self._panel is not panel or self.closed:
            return
        if self._native_windows():
            from widget_material_geometry import rounded_mask

            window, binding = panel["window"], panel["binding"]
            configure_corners = getattr(window, "configure_native_corners", None)

            def current():
                if self.closed or self._panel is not panel or panel.get("binding") is not binding:
                    return False
                self.adapter.backend.validate(binding.token)
                return not self.closed and self._panel is panel and panel.get("binding") is binding

            if callable(configure_corners) and configure_corners(binding.hwnd, valid=current):
                panel["mask_size"] = None
                return
            if self._panel is not panel or self.closed:
                return
            if callable(configure_corners) and window.mask().isEmpty():
                # An unsuccessful native preference may have removed the old
                # region first. Restore fallback even when size is unchanged.
                panel["mask_size"] = None
            size = (window.width(), window.height())
            if panel.get("mask_size") != size:
                width, height = size
                window.setMask(rounded_mask(((0, 0, width, height, min(16, width / 2, height / 2)),)))
                panel["mask_size"] = size

    def close_panel(self):
        self._hover_timer.stop()
        self._close_timer.stop()
        self._panel_geometry_timer.stop()
        self._pending_hover = None
        panel, self._panel = self._panel, None
        if panel:
            self._dispose_panel(panel)
            state = panel["host"].state
            # Native cleanup may synchronously open a replacement on this
            # same host. The old panel must not erase its content/material.
            if self._panel is None or self._panel["host"].state is not state:
                state._detail = {}
                state._detail_coating = False
                state.materialChanged.emit()
                state.detailChanged.emit()

    def _dispose_panel(self, panel):
        hide_error = None
        if panel.get("binding") is not None:
            try:
                # Retain HWND/token/material for retry, but do not leave an
                # unclosed topmost panel covering work if material clear fails.
                self.adapter.hide(panel["binding"])
            except Exception as error:
                hide_error = error
                self._errors.append("detail hide: " + str(error))
        try:
            self._close_material(panel)
            if hide_error is not None:
                raise AppBarError("Own detail panel did not hide") from hide_error
            if panel.get("binding") is not None:
                self.adapter.release(panel["binding"])
                panel["binding"] = None
            client = getattr(panel["window"], "quick_client", None)
            dispose = getattr(panel["window"], "dispose", None)
            if callable(dispose):
                dispose()
                if client is not None:
                    client.deleteLater()
            panel["window"].deleteLater()
        except Exception as error:
            self._errors.append("detail cleanup: " + str(error))
            self.retired.append(panel)

    def open_settings(self):
        if self.closed:
            return
        self.close_panel()
        if self.closed:
            return
        self.runtime.show_settings("__top_bar__")

    def open_history(self, host_id):
        host = self.hosts.get(host_id)
        if self.closed or host is None or host.closing:
            return
        item_id = host.state._detail.get("id")
        item = next((item for item in self._config.get("top_bar", {}).get("items", [])
                     if item["id"] == item_id), None)
        self.close_panel()
        if self.closed or self.hosts.get(host_id) is not host or host.closing:
            return
        callback = getattr(self.controller, "openHistoryMetric", None)
        if item is not None and callable(callback):
            callback(item["metric"], item.get("prefs", {}))
        else:
            self.runtime.show_settings("__history__")

    def focus_details(self):
        """An explicit tray/keyboard action, never invoked by hover/data updates."""
        if self.closed:
            return
        if self.paused:
            self.resume()
        if self._fullscreen_active():
            return
        if self.hosts and self._rows:
            host = next(iter(self.hosts.values()))
            self.click(host.state._host_id, self._rows[0]["id"])
        else:
            self.open_settings()

    def menu(self, host_id):
        host = self.hosts.get(host_id)
        if self.closed or host is None:
            return
        self.close_panel()
        if self.closed or self.hosts.get(host_id) is not host:
            return
        self._close_menu()
        if self.closed or self.hosts.get(host_id) is not host:
            return
        config = self._config or self.controller._saved
        self._menu = QMenu(theme=config.get("theme", "light"), language=config.get("language", "zh-CN"))
        tr = self.hosts[host_id].state.tr
        settings = self._menu.addAction(tr("顶部状态栏设置"), self.open_settings)
        set_action_icon(settings, "sliders-horizontal")
        self._menu.addSeparator()
        self._menu.addAction(tr("暂时隐藏"), self.pause)
        disable = self._menu.addAction(tr("关闭状态栏…").removesuffix("…"))
        disable.setObjectName("topBarDisable")
        set_action_icon(disable, "x")
        disable.triggered.connect(lambda: self.controller.setTopBarEnabled(False))
        self._menu.popup(QCursor.pos())

    def _close_menu(self):
        menu, self._menu = self._menu, None
        if menu is not None:
            menu.close()
            menu.deleteLater()

    def pause(self):
        if self.closed:
            return
        self.paused = True
        self._close_hosts()
        self._status(
            "failed" if self.retired else "paused", "顶部状态栏清理未完成。" if self.retired else ""
        )

    def resume(self):
        if self.closed:
            return
        self.paused = False
        self.apply(self._config)

    def refresh(self):
        if self.hosts and not self.closed and not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def native_message(self, hwnd, message, wparam=0, lparam=0):
        if self.closed:
            return
        host = next((record for record in self.hosts.values() if record.binding.hwnd == hwnd), None)
        if host is None or host.closing:
            return
        flags = self._notifications.setdefault(host.state._host_id, {})
        if message == self.adapter.taskbar_message:
            self._shell_pending = True
        elif message == self.adapter.callback_message:
            if wparam == ABN_POSCHANGED:
                flags["position"] = True
            elif wparam == ABN_FULLSCREENAPP:
                flags["fullscreen"] = bool(lparam)
        elif message == WM_ACTIVATE:
            flags["activation"] = bool(wparam & 0xFFFF)
        elif message == WM_WINDOWPOSCHANGED:
            flags["window_position"] = True
        elif message in (WM_DPICHANGED, WM_DISPLAYCHANGE):
            flags["position"] = True
        elif message == WM_NCDESTROY:
            flags["destroyed"] = True
        else:
            return
        self.refresh()

    def _refresh(self):
        if self.closed:
            return
        notifications, self._notifications = self._notifications, {}
        shell, self._shell_pending = self._shell_pending, False
        previous_fullscreen = self._dispatching_fullscreen
        self._dispatching_fullscreen = previous_fullscreen or any(
            flags.get("fullscreen") is True for flags in notifications.values()
        )
        try:
            if shell:
                self._shell_epoch += 1
            for name, host in list(self.hosts.items()):
                flags = notifications.get(name, {})
                try:
                    if flags.get("destroyed"):
                        raise AppBarError("Owned top bar window was destroyed before unregister")
                    if "fullscreen" in flags:
                        result = host.session.fullscreen(flags["fullscreen"])
                        if flags["fullscreen"]:
                            self.close_panel()
                        if not result.ok:
                            raise AppBarError("Could not update AppBar fullscreen order")
                    if "activation" in flags:
                        if not host.session.notify_activation(flags["activation"]).ok:
                            raise AppBarError("Could not notify AppBar activation")
                    if flags.get("window_position"):
                        if not host.session.notify_window_position().ok:
                            raise AppBarError("Could not notify AppBar window position")
                    self._sync_host(
                        host, shell_recreated=shell and host.shell_epoch < self._shell_epoch
                    )
                except Exception as error:
                    self._errors.append(name + ": " + str(error))
                    self._drop(name)
            if self._errors:
                self._status("partial" if self.hosts else "failed", "无法为部分显示器预留顶部空间。")
        finally:
            self._dispatching_fullscreen = previous_fullscreen

    def _dispose(self, host):
        host.closing = True
        hide_error = None
        if host.binding is not None:
            try:
                # Hide independently of material cleanup. A failed clear must
                # not leave a stale topmost bar covering the user's work.
                self.adapter.hide(host.binding)
            except Exception as error:
                hide_error = error
                self._errors.append(host.state._host_id + " hide: " + str(error))
        try:
            self._close_material(host)
            if hide_error is not None:
                raise AppBarError("Own top bar did not hide") from hide_error
            if host.session is not None:
                result = host.session.close()
                if not result.cleanup_complete:
                    raise AppBarError("; ".join(result.errors) or "AppBar cleanup incomplete")
            if host.binding is not None:
                self.adapter.release(host.binding)
                host.binding = None
            host.window.deleteLater()
            host.state.deleteLater()
        except Exception as error:
            self._errors.append(host.state._host_id + " cleanup: " + str(error))
            self.retired.append(host)  # Keep the actual owned object alive for a retry.

    def _drop(self, name):
        host = self.hosts.pop(name)
        self._notifications.pop(name, None)
        if self._panel and self._panel["host"] is host:
            self.close_panel()
        self._dispose(host)

    def _close_hosts(self):
        self._close_menu()
        self.close_panel()
        self._rows_timer.stop()
        self._refresh_timer.stop()
        self._notifications.clear()
        self._shell_pending = False
        for name in list(self.hosts):
            self._drop(name)

    def _retry_retired(self):
        pending, self.retired = self.retired, []
        for record in pending:
            if isinstance(record, Host):
                self._dispose(record)
            else:
                self._dispose_panel(record)

    @staticmethod
    def _close_material(record):
        bridge = record.material_bridge if isinstance(record, Host) else record.get("material_bridge")
        if bridge is None:
            return
        bridge.close()
        if isinstance(record, Host):
            record.material_bridge = None
        else:
            record["material_bridge"] = None
        delete = getattr(bridge, "deleteLater", None)
        if callable(delete):
            delete()

    def close(self):
        if self._closing or self.closed and not self.retired:
            return
        # Native hide/clear can synchronously dispatch Qt callbacks. Close the
        # admission gate first, while retained leases stay valid for cleanup.
        self.closed = True
        self._closing = True
        try:
            self._close_hosts()
            self._retry_retired()
            if self._filter_installed:
                self.app.removeNativeEventFilter(self._filter)
                self._filter_installed = False
            self._status(
                "failed" if self.retired else "disabled",
                "顶部状态栏清理未完成。" if self.retired else "",
            )
        finally:
            self._closing = False
