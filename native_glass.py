"""A native-frame candidate for owned Qt Quick widgets, without window activation.

Qt 6.10's frameless alpha path is layered; keeping native styles avoids that
path. PyQt-Frameless-Window's PySide6 fix for issue 206 also changes its Qt
6.10 flags to NoTitleBarBackgroundHint. That QWidget evidence is not visual
verification of our QQuickWindow composition:
https://github.com/zhiyiYo/PyQt-Frameless-Window/issues/206

The application native-event filter handles documented Win32 frame messages.
Shiboken message pointers can have a zero buffer length despite a valid address;
treating their truth value as pointer validity previously skipped every message.
That was a pointer-reading bug, not an unavailable Qt native-event filter. There is no WndProc replacement, activation spoof, or capture.
"""

import ctypes as c
import logging
import os
import sys
import weakref
from ctypes import wintypes as w
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, Qt

from native_platform import transparency_enabled

WM_NCCALCSIZE = 0x0083
WM_NCDESTROY = 0x0082
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
WS_CHILD = 0x40000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINMAX = 0x00030000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
FRAME_RECALCULATE = 0x0037  # NOSIZE | NOMOVE | NOZORDER | NOACTIVATE | FRAMECHANGED


def native_frame_supported(platform_name):
    """Whether the native-frame candidate may be attempted, not whether it blurs."""
    if platform_name != "windows" or not hasattr(Qt, "NoTitleBarBackgroundHint"):
        return False
    try:
        return sys.getwindowsversion().build >= 22621 and transparency_enabled()
    except (OSError, AttributeError):
        return False


def widget_flags(native=True):
    """Build flags before creating a hidden widget's HWND; never patch its style."""
    flags = Qt.Tool | Qt.WindowStaysOnBottomHint | Qt.WindowDoesNotAcceptFocus
    if native:
        # DesktopWidget also sets a finite maximum size before HWND creation.
        # Without it Qt 6.10 adds MAXIMIZEBOX/SYSMENU even with CustomizeWindowHint.
        return flags | Qt.CustomizeWindowHint | Qt.NoTitleBarBackgroundHint
    return flags | Qt.FramelessWindowHint


class _WindowApi:
    def __init__(self):
        user = c.WinDLL("user32", use_last_error=True)
        user.IsWindow.argtypes = [w.HWND]
        user.IsWindow.restype = w.BOOL
        user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        user.GetWindowThreadProcessId.restype = w.DWORD
        user.GetWindowLongPtrW.argtypes = [w.HWND, c.c_int]
        user.GetWindowLongPtrW.restype = c.c_ssize_t
        user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
        user.SetWindowPos.restype = w.BOOL
        user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
        user.GetWindowRect.restype = w.BOOL
        user.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
        user.GetClientRect.restype = w.BOOL
        self.user = user

    def owned_thread(self, hwnd):
        if not self.user.IsWindow(hwnd):
            return 0
        process = w.DWORD()
        thread = self.user.GetWindowThreadProcessId(hwnd, c.byref(process))
        return int(thread) if thread and process.value == os.getpid() else 0

    def valid_styles(self, hwnd):
        style = self.user.GetWindowLongPtrW(hwnd, -16)
        extended = self.user.GetWindowLongPtrW(hwnd, -20)
        return (
            not style & WS_CHILD
            and not style & (WS_CAPTION | WS_SYSMENU | WS_MINMAX)
            and not extended & WS_EX_LAYERED
            and bool(extended & WS_EX_NOACTIVATE)
            and bool(extended & WS_EX_TOOLWINDOW)
        )

    def recalculate(self, hwnd):
        return bool(self.user.SetWindowPos(hwnd, None, 0, 0, 0, 0, FRAME_RECALCULATE))

    def frame_geometry(self, hwnd):
        outer, client = w.RECT(), w.RECT()
        if not self.user.GetWindowRect(hwnd, c.byref(outer)) or not self.user.GetClientRect(
            hwnd, c.byref(client)
        ):
            return None
        sizes = (
            (outer.right - outer.left, outer.bottom - outer.top),
            (client.right - client.left, client.bottom - client.top),
        )
        return sizes if all(length > 0 for size in sizes for length in size) else None


@dataclass
class _Registration:
    key: str
    window: weakref.ReferenceType
    thread: int
    destroyed: object
    frame_enabled: bool = False
    moving: bool = False


class NativeFrameBridge(QAbstractNativeEventFilter):
    """Remove only registered widget frames while preserving Qt's native style.

    The caller creates a hidden QQuickWindow with widget_flags(), registers it,
    then applies its normal DWM request and geometry. On failure the caller
    keeps it hidden, unregisters it, and restores widget_flags(False). Call
    unregister before changing flags or deleting windows, and close at shutdown.
    Callbacks run inside native dispatch; queue geometry changes for the next
    event-loop turn. This class never moves, resizes, activates, or shows a window.
    """

    def __init__(self, application, on_enter=None, on_exit=None):
        super().__init__()
        self.application = application
        self.on_enter = on_enter
        self.on_exit = on_exit
        self.reports = {}
        self.last_error = ""
        self._windows = {}
        self._api = None
        self._closed = False
        self._installed = application.platformName() == "windows"
        if self._installed:
            application.installNativeEventFilter(self)

    def _failure(self, key, reason, frame_failure=False):
        self.last_error = reason
        restore_error = self.reports.get(key, {}).get("restore_error")
        self.reports[key] = {
            "native_frame": False,
            "status": "fallback",
            "reason": reason,
            "compositing_verified": False,
        }
        if restore_error:
            self.reports[key]["restore_error"] = restore_error
        if frame_failure:
            self.reports[key]["frame_fallback_reason"] = reason
        return False

    def register(self, window, key):
        return self._track(window, key, frame_enabled=True)

    def watch_moves(self, window, key):
        """Observe legacy widgets' native drag boundaries without changing a frame."""
        return self._track(window, key, frame_enabled=False)

    def _track(self, window, key, frame_enabled):
        def failure(reason):
            return self._failure(key, reason, frame_failure=frame_enabled)

        if self._closed:
            return failure("bridge-closed")
        if not isinstance(key, str) or not key or key == "settings":
            return self._failure(str(key), "widget-key-required", frame_failure=frame_enabled)
        if not self._installed:
            return failure("windows-qpa-required")
        if frame_enabled and not native_frame_supported(self.application.platformName()):
            self.unregister(window)
            return failure("native-frame-policy-disabled")
        hwnd = 0
        registered = False
        try:
            # winId creates no visible window; the caller must still keep it hidden.
            if frame_enabled and window.flags() & Qt.FramelessWindowHint:
                self.unregister(window)
                return failure("frameless-flags-incompatible")
            hwnd = int(window.winId())
            if not hwnd or hwnd < 0 or hwnd >= 1 << (c.sizeof(w.HWND) * 8):
                return failure("invalid-window-handle")
            current = self._windows.get(hwnd)
            if current:
                if current.key != key or current.window() is not window:
                    return failure("window-already-registered")
                registered = True
            if frame_enabled and (not current or not current.frame_enabled) and window.isVisible():
                return failure("window-must-be-hidden")
            if not current and any(record.key == key for record in self._windows.values()):
                return failure("widget-already-registered")
            if self._api is None:
                self._api = _WindowApi()
            thread = self._api.owned_thread(hwnd)
            if not thread:
                self.unregister(window, restore_frame=False)
                return failure("window-not-owned")
            if frame_enabled and not self._api.valid_styles(hwnd):
                self.unregister(window)
                return failure("window-style-incompatible")
            if current and (not frame_enabled or current.frame_enabled):
                if frame_enabled and not self._confirm_frame(hwnd, current):
                    return False
                self.last_error = ""
                return True

            def destroyed(*args):
                record = self._windows.get(hwnd)
                if record is not None and record.destroyed is destroyed:
                    self._remove(hwnd, destroyed=True)

            if current:
                record = current
                record.frame_enabled = True
            else:
                record = _Registration(
                    key, weakref.ref(window), thread, destroyed, frame_enabled=frame_enabled
                )
                window.destroyed.connect(destroyed)
                self._windows[hwnd] = record
            registered = True
            if frame_enabled and not self._api.recalculate(hwnd):
                self.unregister(hwnd)
                return failure("frame-recalculation-failed")
            if self._windows.get(hwnd) is not record:
                return failure("window-destroyed-during-registration")
            if frame_enabled and not self._confirm_frame(hwnd, record):
                return False
            previous = self.reports.get(key, {})
            frame_fallback = (
                previous.get("frame_fallback_reason")
                if previous.get("status") == "fallback"
                else None
            )
            self.reports[key] = {
                "native_frame": frame_enabled,
                "status": "candidate-registered" if frame_enabled else "move-watched",
                "hwnd": hwnd,
                "compositing_verified": False,
            }
            if not frame_enabled and frame_fallback:
                self.reports[key]["frame_fallback_reason"] = frame_fallback
            self.last_error = ""
            return True
        except (OSError, AttributeError, RuntimeError) as error:
            if registered:
                self.unregister(hwnd)
            return failure(str(error))

    def _confirm_frame(self, hwnd, record):
        geometry = self._api.frame_geometry(hwnd)
        if (
            geometry is None
            or any(length <= 0 for size in geometry for length in size)
            or geometry[0] != geometry[1]
        ):
            self.unregister(hwnd)
            return self._failure(
                record.key,
                "frame-geometry-unavailable" if geometry is None else "frame-client-mismatch",
                frame_failure=True,
            )
        return True

    def _remove(self, hwnd, destroyed=False):
        record = self._windows.pop(hwnd, None)
        if record is None:
            return None
        window = record.window()
        if not destroyed:
            if window is not None:
                try:
                    window.destroyed.disconnect(record.destroyed)
                except (RuntimeError, TypeError):
                    pass  # QObject destruction may already have removed the connection.
        self.reports[record.key] = {
            "native_frame": False,
            "status": "released",
            "compositing_verified": False,
        }
        return record

    def unregister(self, window_or_hwnd, restore_frame=True):
        if type(window_or_hwnd) is int:
            hwnd = window_or_hwnd
        else:
            hwnd = next(
                (key for key, record in self._windows.items() if record.window() is window_or_hwnd),
                0,
            )
        record = self._remove(hwnd)
        if record is None:
            return False
        # Remove the allowlist entry before recalculating, so the ordinary Qt/
        # Windows NCCALCSIZE path restores the original native frame.
        if restore_frame and record.frame_enabled and self._api is not None:
            try:
                if self._api.owned_thread(hwnd) == record.thread:
                    if not self._api.recalculate(hwnd):
                        self.last_error = "frame-restore-failed"
                        self.reports[record.key]["restore_error"] = self.last_error
            except (OSError, AttributeError) as error:
                self.last_error = str(error)
                self.reports[record.key]["restore_error"] = str(error)
        return True

    def close(self):
        if self._closed:
            return
        self._closed = True
        for hwnd in list(self._windows):
            self.unregister(hwnd)
        if self._installed:
            self.application.removeNativeEventFilter(self)

    def _dispatch(self, hwnd, message):
        record = self._windows.get(hwnd)
        if self._closed or record is None:
            return False, 0
        if message == WM_NCDESTROY:
            self._remove(hwnd, destroyed=True)
            return False, 0
        if message not in (WM_NCCALCSIZE, WM_ENTERSIZEMOVE, WM_EXITSIZEMOVE):
            return False, 0
        try:
            owned = self._api is not None and self._api.owned_thread(hwnd) == record.thread
        except (OSError, AttributeError):
            owned = False
        if not owned:
            self._remove(hwnd, destroyed=True)
            self._failure(record.key, "window-identity-lost", frame_failure=record.frame_enabled)
            return False, 0
        if message == WM_NCCALCSIZE:
            # Leaving Windows' proposed outer rectangle intact and returning 0
            # makes the client occupy it; no pointer writes or NC activation.
            return record.frame_enabled, 0
        if message in (WM_ENTERSIZEMOVE, WM_EXITSIZEMOVE):
            moving = message == WM_ENTERSIZEMOVE
            if record.moving != moving:
                record.moving = moving
                callback = self.on_enter if moving else self.on_exit
                if callback is not None:
                    try:
                        callback(record.key)
                    except Exception:
                        logging.exception("Native widget move notification failed")
        return False, 0

    def nativeEventFilter(self, event_type, message):
        if self._closed or bytes(event_type) != b"windows_generic_MSG":
            return False, 0
        # Shiboken VoidPtr's truth value reflects its declared buffer size, not
        # its address. Native messages may be size-zero yet point to a valid MSG.
        address = int(message) if message is not None else 0
        if not address:
            return False, 0
        native = w.MSG.from_address(address)
        hwnd = int(native.hWnd or 0)
        return self._dispatch(hwnd, native.message)
