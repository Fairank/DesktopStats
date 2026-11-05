"""Event-driven, read-only fullscreen avoidance; no Qt or native work on import.

Create/start/close on the GUI thread, whose Windows message loop delivers the
OUTOFCONTEXT WinEvents. The notification only requests a caller-owned queued
refresh. ``blocked`` accepts native screen IDs and physical-pixel monitor bounds.
No window enumeration, timer, window title, process name or foreign write occurs.

References: Microsoft Learn SetWinEventHook, UnhookWinEvent, Event Constants,
GetWindowRect, DWMWINDOWATTRIBUTE and MONITORINFO.
"""

from __future__ import annotations

import ctypes as c
import os
import sys
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND = 0x0017
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
EVENT_OBJECT_CLOAKED = 0x8017
EVENT_OBJECT_UNCLOAKED = 0x8018
EVENTS = (
    EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND,
    EVENT_OBJECT_DESTROY, EVENT_OBJECT_SHOW, EVENT_OBJECT_HIDE,
    EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_CLOAKED, EVENT_OBJECT_UNCLOAKED,
)
_FAILED_CLOSE_RETAINERS = []  # Keep C callback pointers alive if native unhook fails.
_MAX_TRACKED = 32


class FullscreenQueryError(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowState:
    """Fake/native adapter result; rectangles use (left, top, right, bottom)."""

    hwnd: int
    rect: object = None
    monitor_rect: object = None
    visible: bool = True
    minimized: bool = False
    cloaked: bool = False
    desktop: bool = False
    own_process: bool = False
    identity: tuple = ()


@dataclass(frozen=True)
class _Tracked:
    state: WindowState
    suppressed: frozenset = frozenset()


def _rect(value):
    if isinstance(value, Mapping):
        result = tuple(value[key] for key in ("left", "top", "right", "bottom"))
    elif isinstance(value, (tuple, list)) and len(value) == 4:
        result = tuple(value)
    else:
        result = tuple(getattr(value, key) for key in ("left", "top", "right", "bottom"))
    if any(type(v) is not int for v in result) or result[2] <= result[0] or result[3] <= result[1]:
        raise FullscreenQueryError("Invalid physical-pixel rectangle")
    return result


def _covers(window, monitor):
    return (window[0] <= monitor[0] and window[1] <= monitor[1]
            and window[2] >= monitor[2] and window[3] >= monitor[3])


def _intersection(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1]))


class FullscreenGuard:
    """A bounded observation cache with explicit native lifecycle.

    ``api_factory`` returns an adapter with install(callback)->handles,
    uninstall(handle)->bool, foreground()->HWND|None, window(HWND)->WindowState|None,
    and optional is_own_window(HWND)->bool/release_callback(). None from window
    means destroyed; query failures must raise. No background worker is started.
    """

    def __init__(self, on_change, *, environ=None, api_factory=None):
        self._notify = on_change
        self._environ = os.environ if environ is None else environ
        self._factory = api_factory
        self._api = None
        self._handles = []
        self._thread = None
        self._started = False
        self._closed = False
        self._disabled = False
        self._hook_failed = False
        self._dirty = True
        self._known = False
        self._monitors = {}
        self._attempt_monitors = {}
        self._cached = frozenset()
        self._last_blocked = frozenset()
        self._tracked = OrderedDict()
        self._foreground_hwnd = None
        self.failure = None

    @property
    def closed(self):
        return self._closed

    def start(self):
        if self._closed or self._started:
            return
        self._started = True
        self._thread = threading.get_ident()
        self._disabled = (self._environ.get("DESKTOP_STATS_FULLSCREEN_GUARD_DISABLED") == "1"
                          or (sys.platform != "win32" and self._factory is None))
        if self._disabled:
            return
        try:
            self._api = (self._factory or _NativeApi)()
            self._handles = list(self._api.install(self._event))
            if not self._handles or any(not handle for handle in self._handles):
                raise FullscreenQueryError("No WinEvent hooks were installed")
        except Exception as exc:
            self._handles = list(getattr(exc, "handles", self._handles))
            self._hook_failed = True
            self.failure = f"Fullscreen hooks unavailable: {exc}"

    def invalidate(self):
        """Mark dirty for a caller-owned AppBar/display/DPI notification."""
        if not self._closed:
            self._dirty = True

    def _event(self, event, hwnd, object_id=0, child_id=0):
        if self._closed or event not in EVENTS:
            return
        if event != EVENT_SYSTEM_FOREGROUND:
            if not hwnd or object_id != 0 or child_id != 0:
                return
            if (self._foreground_hwnd is not None and hwnd != self._foreground_hwnd
                    and hwnd not in self._tracked):
                return
            try:
                own = getattr(self._api, "is_own_window", None)
                if own is not None and own(hwnd):
                    return
            except Exception:
                pass  # Let the queued query apply its conservative error policy.
        self._dirty = True
        try:
            if self._notify is not None:
                self._notify()
        except Exception as exc:
            # Exceptions must not escape through a native callback boundary.
            self.failure = f"Fullscreen refresh notification failed: {exc}"

    def _fallback(self, monitors):
        if not self._known or self._hook_failed:
            return frozenset(monitors)
        changed = {key for key, value in monitors.items() if self._monitors.get(key) != value}
        return frozenset((set(self._last_blocked) & monitors.keys()) | changed)

    @staticmethod
    def _coverage(state, monitors):
        if state is None or not state.visible or state.minimized or state.cloaked:
            return frozenset()
        if state.desktop or state.own_process:
            return frozenset()
        bounds = _rect(state.rect)
        return frozenset(key for key, value in monitors.items() if _covers(bounds, value))

    @staticmethod
    def _foreground_monitor(state, monitors):
        if state.monitor_rect is not None:
            native = _rect(state.monitor_rect)
            matches = {key for key, value in monitors.items() if value == native}
            if matches:
                return matches
        if state.rect is None or not monitors:
            return set()
        bounds = _rect(state.rect)
        key = max(monitors, key=lambda name: _intersection(bounds, monitors[name]))
        return {key} if _intersection(bounds, monitors[key]) > 0 else set()

    @staticmethod
    def _related_foreground(foreground, game):
        # Use identity facts already read by the native adapter. A game's
        # dialog may be windowed while its validated fullscreen owner remains.
        front, prior = foreground.identity, game.identity
        if not (isinstance(front, tuple) and len(front) >= 4
                and isinstance(prior, tuple) and len(prior) >= 4):
            return False
        if any(type(pid) is not int or pid <= 0 for pid in (front[0], prior[0])):
            return False
        owner = front[3]
        return (front[0] == prior[0]
                or type(owner) is int and owner > 0 and owner == game.hwnd)

    def blocked(self, monitors):
        if self._closed:
            return frozenset()
        self.start()
        if self._disabled:
            return frozenset()
        try:
            current = {key: _rect(value) for key, value in monitors.items()}
        except Exception as exc:
            self.failure = f"Fullscreen monitor query failed: {exc}"
            return self._fallback(dict.fromkeys(monitors))
        if not current:
            return frozenset()
        if self._hook_failed:
            return frozenset(current)
        if not self._dirty and current == self._attempt_monitors:
            return self._cached
        if threading.get_ident() != self._thread:
            self.failure = "Fullscreen queries must run on the hook owner thread"
            return self._fallback(current)
        self._dirty = False
        self._attempt_monitors = current
        try:
            hwnd = self._api.foreground()
            if not hwnd:
                raise FullscreenQueryError("Foreground window is temporarily unavailable")
            self._foreground_hwnd = hwnd
            foreground = self._api.window(hwnd)
            if foreground is None:
                raise FullscreenQueryError("Foreground window disappeared during query")
            tracked = OrderedDict()
            if not foreground.desktop:
                for handle, old in self._tracked.items():
                    state = foreground if handle == hwnd else self._api.window(handle)
                    if state is None or (old.state.identity and state.identity != old.state.identity):
                        continue
                    if self._coverage(state, current) - old.suppressed:
                        tracked[handle] = _Tracked(state, old.suppressed)
                coverage = self._coverage(foreground, current)
                if coverage:
                    tracked.pop(hwnd, None)
                    tracked[hwnd] = _Tracked(foreground)
                else:
                    # A normal foreground on this display restores that display,
                    # while an observed game on another display stays protected.
                    active = self._foreground_monitor(foreground, current)
                    for handle, item in list(tracked.items()):
                        if self._related_foreground(foreground, item.state):
                            continue
                        suppressed = item.suppressed | active
                        if self._coverage(item.state, current) - suppressed:
                            tracked[handle] = _Tracked(item.state, frozenset(suppressed))
                        else:
                            del tracked[handle]
            while len(tracked) > _MAX_TRACKED:
                tracked.popitem(last=False)
            result = set()
            for item in tracked.values():
                result.update(self._coverage(item.state, current) - item.suppressed)
            self._tracked = tracked
            self._last_blocked = frozenset(result)
            self._cached = self._last_blocked
            self._monitors = current
            self._known = True
            self.failure = None
            return self._last_blocked
        except Exception as exc:
            self.failure = f"Fullscreen window query failed: {exc}"
            self._cached = self._fallback(current)
            return self._cached

    def close(self):
        self._closed = True
        self._notify = None
        if not self._handles:
            release = getattr(self._api, "release_callback", None)
            if release is not None:
                release()
            self._tracked.clear()
            self.failure = None
            return True
        if threading.get_ident() != self._thread:
            self.failure = "Fullscreen hooks must be removed on their owner thread"
            if self._api not in _FAILED_CLOSE_RETAINERS:
                _FAILED_CLOSE_RETAINERS.append(self._api)
            return False
        remaining = []
        for handle in self._handles:
            try:
                if not self._api.uninstall(handle):
                    remaining.append(handle)
            except Exception:
                remaining.append(handle)
        self._handles = remaining
        if remaining:
            self.failure = "Fullscreen hook cleanup is incomplete"
            if self._api not in _FAILED_CLOSE_RETAINERS:
                _FAILED_CLOSE_RETAINERS.append(self._api)
            return False
        release = getattr(self._api, "release_callback", None)
        if release is not None:
            release()
        if self._api in _FAILED_CLOSE_RETAINERS:
            _FAILED_CLOSE_RETAINERS.remove(self._api)
        self._tracked.clear()
        self.failure = None
        return True


class RECT(c.Structure):
    _fields_ = [(name, c.c_int32) for name in ("left", "top", "right", "bottom")]


class MONITORINFO(c.Structure):
    _fields_ = [("cbSize", c.c_uint32), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", c.c_uint32)]


class _NativeApi:
    """Lazy ctypes adapter. Every foreign-window operation below is read-only."""

    def __init__(self, *, dll_loader=None):
        loader = dll_loader or c.WinDLL
        self.user = loader("user32", use_last_error=True)
        self.dwm = loader("dwmapi", use_last_error=True)
        self._callback = None
        self._hooks = []
        p, d, i, b = c.c_void_p, c.c_uint32, c.c_int32, c.c_int32
        self._callback_type = getattr(c, "WINFUNCTYPE", c.CFUNCTYPE)(
            None, p, d, p, i, i, d, d)
        signatures = (
            (self.user, "SetWinEventHook", p, [d, d, p, self._callback_type, d, d, d]),
            (self.user, "UnhookWinEvent", b, [p]),
            (self.user, "GetForegroundWindow", p, []),
            (self.user, "IsWindow", b, [p]),
            (self.user, "IsWindowVisible", b, [p]),
            (self.user, "IsIconic", b, [p]),
            (self.user, "GetWindowThreadProcessId", d, [p, c.POINTER(d)]),
            (self.user, "GetClassNameW", i, [p, c.c_wchar_p, i]),
            (self.user, "GetWindow", p, [p, d]),
            (self.user, "GetWindowRect", b, [p, c.POINTER(RECT)]),
            (self.user, "MonitorFromWindow", p, [p, d]),
            (self.user, "GetMonitorInfoW", b, [p, c.POINTER(MONITORINFO)]),
            (self.dwm, "DwmGetWindowAttribute", i, [p, d, p, d]),
        )
        for library, name, result, arguments in signatures:
            function = getattr(library, name)
            function.restype, function.argtypes = result, arguments
        self._dpi_context = getattr(self.user, "SetThreadDpiAwarenessContext", None)
        if self._dpi_context is not None:
            self._dpi_context.restype, self._dpi_context.argtypes = p, [p]

    def install(self, callback):
        def receive(_hook, event, hwnd, object_id, child_id, _thread, _time):
            try:
                callback(event, hwnd, object_id, child_id)
            except Exception:
                pass

        self._callback = self._callback_type(receive)
        try:
            for event in EVENTS:
                # OUTOFCONTEXT is zero. Foreground events include our own process.
                handle = self.user.SetWinEventHook(event, event, None, self._callback, 0, 0, 0)
                if not handle:
                    raise FullscreenQueryError("SetWinEventHook failed")
                self._hooks.append(handle)
        except Exception as exc:
            remaining = []
            for old in self._hooks:
                try:
                    if not self.user.UnhookWinEvent(old):
                        remaining.append(old)
                except Exception:
                    remaining.append(old)
            self._hooks = remaining
            error = FullscreenQueryError(f"SetWinEventHook failed: {exc}")
            error.handles = list(remaining)
            raise error from exc
        return list(self._hooks)

    def uninstall(self, handle):
        success = bool(self.user.UnhookWinEvent(handle))
        if success and handle in self._hooks:
            self._hooks.remove(handle)
        return success

    def release_callback(self):
        if not self._hooks:
            self._callback = None

    def foreground(self):
        return self.user.GetForegroundWindow()

    def is_own_window(self, hwnd):
        pid = c.c_uint32()
        return bool(self.user.GetWindowThreadProcessId(hwnd, c.byref(pid))
                    and pid.value == os.getpid())

    def window(self, hwnd):
        if not self.user.IsWindow(hwnd):
            return None
        pid = c.c_uint32()
        thread = self.user.GetWindowThreadProcessId(hwnd, c.byref(pid))
        name = c.create_unicode_buffer(256)
        if not thread or not self.user.GetClassNameW(hwnd, name, len(name)):
            raise FullscreenQueryError("Window identity is unavailable")
        owner = self.user.GetWindow(hwnd, 4) or 0  # GW_OWNER; never alter it.
        visible = bool(self.user.IsWindowVisible(hwnd))
        minimized = bool(self.user.IsIconic(hwnd))
        identity = (pid.value, thread, name.value, owner)
        desktop = name.value in {"Progman", "WorkerW"}
        own = pid.value == os.getpid()
        if desktop:
            return WindowState(hwnd, desktop=True, own_process=own, identity=identity)
        if not visible or minimized:
            return WindowState(hwnd, visible=visible, minimized=minimized,
                               desktop=desktop, own_process=own, identity=identity)
        cloaked = c.c_uint32()
        if self.dwm.DwmGetWindowAttribute(hwnd, 14, c.byref(cloaked), c.sizeof(cloaked)) < 0:
            raise FullscreenQueryError("Window cloak state is unavailable")
        if cloaked.value:
            return WindowState(hwnd, cloaked=True, desktop=desktop,
                               own_process=own, identity=identity)
        previous = None
        if self._dpi_context is not None:
            previous = self._dpi_context(c.c_void_p(-4))  # PER_MONITOR_AWARE_V2
            if not previous:
                raise FullscreenQueryError("Physical-pixel query context is unavailable")
        try:
            bounds = RECT()
            if self.dwm.DwmGetWindowAttribute(hwnd, 9, c.byref(bounds), c.sizeof(bounds)) < 0:
                if not self.user.GetWindowRect(hwnd, c.byref(bounds)):
                    raise FullscreenQueryError("Window bounds are unavailable")
            monitor = self.user.MonitorFromWindow(hwnd, 2)  # DEFAULTTONEAREST
            info = MONITORINFO()
            info.cbSize = c.sizeof(info)
            if not monitor or not self.user.GetMonitorInfoW(monitor, c.byref(info)):
                raise FullscreenQueryError("Window monitor is unavailable")
            return WindowState(hwnd, _rect(bounds), _rect(info.rcMonitor), desktop=desktop,
                               own_process=own, identity=identity)
        finally:
            if previous:
                self._dpi_context(previous)
