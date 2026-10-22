"""Owned raster Acrylic presenter for the existing Quick detail content.

Like Settings, the DWM background belongs to a non-layered raster HWND while
Quick paints transparent foreground content in its child. No capture or global
window operations. Creation stays hidden until the manager retains its token.
"""

import ctypes as c
import os
import sys
import threading

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QRegion

from settings_acrylic_material import SettingsAcrylicMaterial
from settings_backdrop_host import SettingsBackdropHost


class _CornerAPI:
    """Lazy, own-window DWM preference; construction never loads a DLL."""

    def __init__(self):
        self._user = self._dwm = None

    @staticmethod
    def build():
        return sys.getwindowsversion().build if sys.platform == "win32" else 0

    def _load(self):
        if self._user is None:
            user = c.WinDLL("user32", use_last_error=True)
            dwm = c.WinDLL("dwmapi", use_last_error=True)
            user.IsWindow.argtypes, user.IsWindow.restype = [c.c_void_p], c.c_int
            user.GetWindowThreadProcessId.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
            user.GetWindowThreadProcessId.restype = c.c_uint32
            user.GetWindowLongPtrW.argtypes = [c.c_void_p, c.c_int]
            user.GetWindowLongPtrW.restype = c.c_ssize_t
            dwm.DwmSetWindowAttribute.argtypes = [
                c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32,
            ]
            dwm.DwmSetWindowAttribute.restype = c.c_int32
            self._user, self._dwm = user, dwm

    def is_window(self, handle):
        self._load()
        return bool(self._user.IsWindow(handle))

    def owner(self, handle):
        self._load()
        process = c.c_uint32()
        thread = self._user.GetWindowThreadProcessId(handle, c.byref(process))
        return int(thread), process.value

    def extended_style(self, handle):
        self._load()
        c.set_last_error(0)
        value = int(self._user.GetWindowLongPtrW(handle, -20))
        if not value and c.get_last_error():
            raise c.WinError(c.get_last_error())
        return value

    def round(self, handle):
        self._load()
        preference = c.c_int32(2)  # DWMWCP_ROUND; system chooses the AA radius.
        return int(self._dwm.DwmSetWindowAttribute(handle, 33, c.byref(preference), c.sizeof(preference)))


class TopBarBackdropHost(SettingsBackdropHost):
    def __init__(self, client, *, pinned, close_panel, native=None, painter=None, corner_api=None):
        super().__init__(client, native=native, painter=painter)
        self._corner_api, self._corner_identity = corner_api, None
        self._corner_report = dict(status="not-requested", configured=False, visual_verified=False)
        self._close_panel = close_panel
        self._content_resize = False
        self._content_timer = QTimer(self)
        self._content_timer.setSingleShot(True)
        self._content_timer.timeout.connect(self._sync_content_size)
        self.setObjectName("topBarDetailsBackdropHost")
        # Keep Qt's window state consistent with the adapter's native topmost
        # placement, including subsequent native frame changes.
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if not pinned:
            flags |= Qt.WindowDoesNotAcceptFocus
        self.setFlags(flags)
        client.widthChanged.connect(self._content_size_changed)
        client.heightChanged.connect(self._content_size_changed)

    @property
    def quick_client(self):
        return self._client

    def configure_native_corners(self, handle, *, valid):
        """Prefer DWM AA on this retained Raster HWND; failure keeps mask fallback.

        A window region prevents DWM rounding, so remove it before requesting
        the preference. HRESULT success is only a configured hint, not visual
        confirmation. The manager restores its old mask after a failed request.
        """
        if threading.get_native_id() != threading.main_thread().native_id:
            return False
        identity = (handle, self._serial)

        def current():
            def same():
                return (not self._disposed and type(handle) is int and handle > 0
                        and self._handle == handle and self._serial == identity[1])
            return same() and valid() is not False and same()

        try:
            if (not callable(valid) or not current() or self.format().alphaBufferSize() != 0
                    or not self._native and self._corner_api is None):
                return False
            if self._corner_identity == identity:
                return self._corner_report.get("configured") is True
            self._client.setProperty("nativeRounded", False)
            if not current():
                return False
            api = self._corner_api or _CornerAPI()
            if api.build() < 22000:
                self._corner_report = dict(status="unsupported", configured=False, visual_verified=False)
                self._corner_identity = identity
                return False
            self._corner_api = api
            if (not current() or not api.is_window(handle) or not current()
                    or api.owner(handle) != (threading.get_native_id(), os.getpid()) or not current()
                    or api.extended_style(handle) & 0x80000 or not current()):
                return False
            self.setMask(QRegion())
            if not current():
                return False
            result = api.round(handle)
            if not current():
                return False
            configured = type(result) is int and result == 0
            self._corner_report = dict(status="configured-unverified" if configured else "fallback",
                                       configured=configured, hresult=result,
                                       surface_serial=identity[1], visual_verified=False)
            self._corner_identity = identity
            self._client.setProperty("nativeRounded", configured)
            return current() and configured
        except Exception as error:
            self._corner_report = dict(status="fallback", configured=False, visual_verified=False,
                                       error=(type(error).__name__ + ": " + str(error))[:240])
            return False

    def status(self):
        return dict(super().status(), corners=dict(getattr(self, "_corner_report", {})))

    def _content_size_changed(self, *_):
        if not self._disposed and not self._content_resize:
            # A Qt resize emits width/height separately. Read their final pair
            # after both signals, rather than restoring the old other axis.
            self._content_timer.start(0)

    def _sync_content_size(self):
        if self._disposed or self._client is None or self._content_resize:
            return
        self._content_resize = True
        try:
            if (self._client.width() > 0 and self._client.height() > 0
                    and self.size() != self._client.size()):
                self.resize(self._client.size())
        finally:
            self._content_resize = False

    def event(self, event):
        if (event.type() == QEvent.Close and hasattr(self, "_close_panel")
                and not self._disposed):
            event.ignore()
            self._close_panel()
            return True
        return super().event(event)

    def dispose(self):
        if hasattr(self, "_content_timer"):
            self._content_timer.stop()
        super().dispose()


class DetailAcrylicBackend:
    """WUJI-style DWM Acrylic on the owned black Raster presentation host."""

    def __init__(self, host, *, validate, api=None):
        self.host, self.validate = host, validate
        self.backend = SettingsAcrylicMaterial(api=api)
        self._identity = None

    def _guard(self, handle, serial):
        try:
            self.validate(handle)
            status = self.host.status()
            return bool(not status["disposed"] and status["surface_alive"]
                        and status["surface_serial"] == serial
                        and self.host._handle == handle)
        except (RuntimeError, ValueError):
            return False

    def apply(self, handle, *, enabled, policy):
        serial = self.host.status()["surface_serial"]
        def guard():
            return self._guard(handle, serial)
        if not guard():
            raise RuntimeError("Detail Acrylic requires its retained current raster surface")
        self._identity = handle, serial
        if enabled:
            result = self.backend.apply(handle, policy, surface_id=serial, valid=guard)
            if result.get("blur_configured") and not self.host.paint_background():
                cleanup = self.backend.clear(handle, surface_id=serial, valid=guard)
                return dict(result, ok=False, material="solid", coating_allowed=False, coating_translucent=False,
                            blur_configured=False, blur_may_remain=not cleanup.get("cleanup_complete"),
                            fallback_reason="raster-background-unavailable")
            return result
        result = self.backend.clear(handle, surface_id=serial, valid=guard)
        return dict(result, coating_allowed=False, coating_translucent=False,
                    blur_configured=False, material="solid",
                    fallback_reason="material-disabled" if result.get("ok") and result.get("cleanup_complete")
                    else result.get("fallback_reason", "native-cleanup-failed"))

    def clear(self, handle):
        if self._identity is None:
            return dict(ok=True, cleanup_complete=True, noop=True)
        original, serial = self._identity
        if handle != original:
            raise RuntimeError("Cannot clear a replacement detail surface")
        return self.backend.clear(handle, surface_id=serial,
                                  valid=lambda: self._guard(handle, serial))

    def close(self):
        return self.backend.close()
