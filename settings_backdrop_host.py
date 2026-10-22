"""A native raster background host for the existing transparent Quick settings.

WUJI's working presentation separates a GDI-black DWM window from its alpha
foreground. Keep that separation without replacing the QML interface. This is
a Qt native-frame/raster host, not WinForms/WebView2; visible equivalence still
requires validation. No desktop pixels, global window operations or polling.
"""

import ctypes as c
import os
import threading
from ctypes import wintypes as w

from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication, QPlatformSurfaceEvent, QSurface, QSurfaceFormat, QWindow


class _BlackClient:
    """GDI writes only to the exact current own HWND on its GUI thread."""

    def __init__(self):
        self.user = c.WinDLL("user32", use_last_error=True)
        self.gdi = c.WinDLL("gdi32", use_last_error=True)
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        self.user.GetWindowThreadProcessId.restype = w.DWORD
        self.user.GetWindowLongPtrW.argtypes = [w.HWND, c.c_int]
        self.user.GetWindowLongPtrW.restype = c.c_ssize_t
        self.user.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
        self.user.GetClientRect.restype = w.BOOL
        self.user.GetDC.argtypes = [w.HWND]
        self.user.GetDC.restype = w.HDC
        self.user.ReleaseDC.argtypes = [w.HWND, w.HDC]
        self.user.ReleaseDC.restype = c.c_int
        self.user.FillRect.argtypes = [w.HDC, c.POINTER(w.RECT), w.HBRUSH]
        self.user.FillRect.restype = c.c_int
        self.gdi.GetStockObject.argtypes = [c.c_int]
        self.gdi.GetStockObject.restype = w.HGDIOBJ

    def fill(self, handle, valid, dc=0):
        if type(handle) is not int or handle <= 0 or not valid():
            raise RuntimeError("Background surface is not current")
        pid = w.DWORD()
        tid = self.user.GetWindowThreadProcessId(handle, c.byref(pid))
        if pid.value != os.getpid() or tid != threading.get_native_id():
            raise RuntimeError("Background surface must be owned by this GUI thread")
        style = self.user.GetWindowLongPtrW(handle, -20)
        if style & (0x80000 | 0x200000):
            raise RuntimeError("Raster backdrop host cannot be layered or omit redirection")
        rect = w.RECT()
        if not self.user.GetClientRect(handle, c.byref(rect)) or not valid():
            raise RuntimeError("Background surface no longer current")
        acquired = not dc
        dc = dc or self.user.GetDC(handle)
        if not dc:
            raise c.WinError(c.get_last_error())
        try:
            if not valid():
                raise RuntimeError("Background surface replaced before paint")
            # GDI black in a frame extended by DWM leaves zero-alpha background.
            # This is not an opaque black QML rectangle or whole-window opacity.
            if not self.user.FillRect(dc, c.byref(rect), self.gdi.GetStockObject(4)):
                raise c.WinError(c.get_last_error())
        finally:
            if acquired:
                self.user.ReleaseDC(handle, dc)


class _PaintEvents(QAbstractNativeEventFilter):
    def __init__(self, host):
        super().__init__()
        self.host = host

    def nativeEventFilter(self, event_type, message):
        host = self.host
        if not host._disposed and host._handle and event_type == b"windows_generic_MSG":
            try:
                msg = w.MSG.from_address(int(message))
                if int(msg.hWnd or 0) == host._handle and msg.message == 0x0014:
                    if host.paint_background(int(msg.wParam)):
                        return True, 1
            except (ValueError, TypeError, OverflowError, RuntimeError) as error:
                host._record_paint_error(error)
        return False, 0


class SettingsBackdropHost(QWindow):
    """Native caption, geometry and visibility; QML retains state and focus.

    Construct before showing the Quick client. Construction never creates a
    native handle or shows a window. dispose() runs after the material bridge
    has released the current host, before either native window is destroyed.
    """

    paintFailed = Signal(str)

    def __init__(self, client, *, painter=None, native=None):
        super().__init__()
        if client.isVisible() or client.parent() is not None:
            raise ValueError("Settings client must be a hidden, unparented window")
        app = QGuiApplication.instance()
        self._native = app.platformName() == "windows" if native is None else bool(native)
        self._painter = painter
        self._handle = 0
        self._serial = 0
        self._paint_error = ""
        self._paint_count = 0
        self._disposed = False
        self._syncing = False
        self._filter_installed = False
        self._client = client
        self._paint_filter = _PaintEvents(self)
        self.setObjectName("settingsNativeBackdropHost")
        self.setSurfaceType(QSurface.RasterSurface)
        format_ = QSurfaceFormat()
        format_.setAlphaBufferSize(0)
        self.setFormat(format_)
        self.setFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                      | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
                      | Qt.WindowCloseButtonHint)
        self.setTitle(client.title())
        self.setIcon(client.icon())
        self.setMinimumSize(client.minimumSize())
        self.resize(client.size())
        self.widthChanged.connect(self._sync_client_size)
        self.heightChanged.connect(self._sync_client_size)
        try:
            client.setProperty("nativeHosted", True)
            client.setParent(self)
            client.setPosition(0, 0)
            client.resize(self.size())
            client.visibleChanged.connect(self._client_visibility)
            if self._native:
                app.installNativeEventFilter(self._paint_filter)
                self._filter_installed = True
        except Exception:
            self.dispose()
            raise

    def _record_paint_error(self, error):
        message = f"{type(error).__name__}: {error}"[:400]
        if message != self._paint_error:
            self._paint_error = message
            self.paintFailed.emit(message)

    def paint_background(self, dc=0):
        if self._disposed or not self._handle or QThread.currentThread() != self.thread():
            return False
        if not self._native and self._painter is None:
            return False
        handle, serial = self._handle, self._serial

        def valid():
            return not self._disposed and self._handle == handle and self._serial == serial
        try:
            if self._painter is None:
                self._painter = _BlackClient()
            self._painter.fill(handle, valid, dc)
            if not valid():
                return False
            self._paint_count += 1
            self._paint_error = ""
            return True
        except Exception as error:
            self._record_paint_error(error)
            return False

    def _client_visibility(self, visible):
        if not visible and not self._syncing and not self._disposed:
            self.hide()  # Escape/client close must never leave an empty host.

    def _sync_client_size(self, *_):
        if (self._client is not None and not self._disposed and self.width() > 0 and self.height() > 0
                and not self.windowState() & Qt.WindowMinimized):
            self._client.resize(self.size())

    def event(self, event):
        kind = event.type()
        if kind == QEvent.Close and hasattr(self, "_disposed") and not self._disposed:
            event.ignore()
            self.hide()  # Preserve the existing close-to-tray and unsaved draft.
            return True
        if kind == QEvent.PlatformSurface and hasattr(self, "_disposed"):
            if event.surfaceEventType() == QPlatformSurfaceEvent.SurfaceCreated:
                self._handle = int(self.winId())
                self._serial += 1
            else:
                self._handle = 0
                self._serial += 1
        return super().event(event)

    def resizeEvent(self, event):
        # Both are Qt logical sizes. Never apply DPR a second time.
        self._sync_client_size()
        super().resizeEvent(event)

    def exposeEvent(self, event):
        if self.isExposed():
            self.paint_background()
        super().exposeEvent(event)

    def showEvent(self, event):
        self._syncing = True
        try:
            if self._client is not None and not self._disposed:
                self._client.setPosition(0, 0)
                self._client.resize(self.size())
                self._client.show()
        finally:
            self._syncing = False
        super().showEvent(event)

    def hideEvent(self, event):
        self._syncing = True
        try:
            if self._client is not None:
                self._client.hide()
        finally:
            self._syncing = False
        super().hideEvent(event)

    def status(self):
        return dict(kind="native-raster-host", surface_alive=bool(self._handle),
                    surface_serial=self._serial, alpha_bits=self.format().alphaBufferSize(),
                    paint_count=self._paint_count, paint_error=self._paint_error,
                    visual_verified=False, disposed=self._disposed)

    def dispose(self):
        if self._disposed:
            return
        if QThread.currentThread() != self.thread():
            raise RuntimeError("Dispose settings host on its GUI thread")
        self._disposed = True
        errors = []
        app = QGuiApplication.instance()
        if self._filter_installed and app is not None:
            app.removeNativeEventFilter(self._paint_filter)
        self._filter_installed = False
        client, self._client = self._client, None
        if client is not None:
            for action in (
                lambda: client.visibleChanged.disconnect(self._client_visibility),
                client.hide, client.destroy, lambda: client.setParent(None),
            ):
                try:
                    action()
                except RuntimeError as error:
                    errors.append(str(error)[:200])
        try:
            self.hide()
            self.destroy()
        finally:
            self._handle = 0
        if errors:
            self._paint_error = "; ".join(errors)
