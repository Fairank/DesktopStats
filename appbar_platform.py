"""Explicit, owned-window Windows AppBar foundation; importing changes no system state.

The caller creates/retains its own HWND and stamps WINDOW_GENERATION_PROPERTY
with a nonzero uintptr nonce before retain_window(). HWND destruction, native
event routing and real display/DPI enumeration remain the caller's responsibility.
No automatic listener, GUI, autohide, work-area override or foreign-window API exists.

References: learn.microsoft.com/windows/win32/shell/application-desktop-toolbars
and /windows/win32/api/shellapi/ns-shellapi-appbardata.
"""

from __future__ import annotations

import ctypes as c
import math
import os
import sys
import threading
from dataclasses import dataclass, field

from top_bar_layout import PixelRect

ABM_NEW = 0
ABM_REMOVE = 1
ABM_QUERYPOS = 2
ABM_SETPOS = 3
ABM_ACTIVATE = 6
ABM_WINDOWPOSCHANGED = 9
ABE_TOP = 1
WINDOW_GENERATION_PROPERTY = "DesktopStats.AppBarGeneration"
_MESSAGES = {ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS, ABM_ACTIVATE, ABM_WINDOWPOSCHANGED}


class AppBarError(RuntimeError):
    pass


class RECT(c.Structure):
    _fields_ = [(name, c.c_int32) for name in ("left", "top", "right", "bottom")]


class APPBARDATA(c.Structure):
    # DWORD and LONG remain 32-bit on Win64; HWND and LPARAM are pointer-sized.
    _fields_ = [
        ("cbSize", c.c_uint32),
        ("hWnd", c.c_void_p),
        ("uCallbackMessage", c.c_uint32),
        ("uEdge", c.c_uint32),
        ("rc", RECT),
        ("lParam", c.c_ssize_t),
    ]


@dataclass(frozen=True)
class OwnedWindow:
    hwnd: int
    pid: int
    thread_id: int
    class_name: str
    generation: int
    _seal: object = field(default_factory=object, repr=False, compare=False)


@dataclass(frozen=True)
class AppBarResult:
    ok: bool
    state: str
    registered: bool
    physical_rect: PixelRect | None
    cleanup_complete: bool
    errors: tuple[str, ...] = ()
    fullscreen: bool = False

    @property
    def ready(self):
        return (
            self.ok and self.state == "READY" and self.registered and self.physical_rect is not None
        )

    def __bool__(self):
        return self.ok


def _require(condition, message):
    if not condition:
        raise AppBarError(message)


def _positive_uintptr(value):
    return type(value) is int and 0 < value < 1 << (c.sizeof(c.c_void_p) * 8)


def _rect_inside(rect, bounds):
    return (
        isinstance(rect, PixelRect)
        and rect.width > 0
        and rect.height > 0
        and bounds.left <= rect.left < rect.right <= bounds.right
        and bounds.top <= rect.top < rect.bottom <= bounds.bottom
    )


class NativeAppBarBackend:
    """No DLLs load until an explicitly called window operation.

    A token is accepted only by the backend that retained that exact object.
    All native operations recheck PID, GUI thread, class and generation cookie.
    The caller must unregister before destroying its window or removing the cookie.
    A DLL loader can be injected for ABI/wrapper tests without calling Windows.
    """

    def __init__(self, *, dll_loader=None):
        self._loader = dll_loader
        self._functions = None
        self._retained = {}
        self._claims = {}
        self._registrations = set()

    def _api(self):
        if self._functions is not None:
            return self._functions
        if self._loader is None:
            _require(sys.platform == "win32", "AppBar requires Windows")
            loader = c.WinDLL
        else:
            loader = self._loader
        user = loader("user32", use_last_error=True)
        shell = loader("shell32", use_last_error=True)
        kernel = loader("kernel32", use_last_error=True)
        definitions = {
            "is_window": (user.IsWindow, [c.c_void_p], c.c_int32),
            "is_visible": (user.IsWindowVisible, [c.c_void_p], c.c_int32),
            "window_thread": (
                user.GetWindowThreadProcessId,
                [c.c_void_p, c.POINTER(c.c_uint32)],
                c.c_uint32,
            ),
            "class_name": (
                user.GetClassNameW,
                [c.c_void_p, c.POINTER(c.c_wchar), c.c_int32],
                c.c_int32,
            ),
            "generation": (user.GetPropW, [c.c_void_p, c.c_wchar_p], c.c_void_p),
            "position": (
                user.SetWindowPos,
                [c.c_void_p, c.c_void_p, c.c_int32, c.c_int32, c.c_int32, c.c_int32, c.c_uint32],
                c.c_int32,
            ),
            "show": (user.ShowWindow, [c.c_void_p, c.c_int32], c.c_int32),
            "thread_id": (kernel.GetCurrentThreadId, [], c.c_uint32),
            "appbar": (shell.SHAppBarMessage, [c.c_uint32, c.POINTER(APPBARDATA)], c.c_size_t),
        }
        functions = {}
        for name, (function, args, result) in definitions.items():
            function.argtypes, function.restype = args, result
            functions[name] = function
        self._functions = functions
        return functions

    def _inspect(self, hwnd):
        _require(_positive_uintptr(hwnd), "Invalid HWND")
        api = self._api()
        _require(api["is_window"](hwnd), "Owned HWND no longer exists")
        pid = c.c_uint32()
        thread = int(api["window_thread"](hwnd, c.byref(pid)))
        _require(pid.value == os.getpid() and thread > 0, "HWND is not in this process")
        _require(thread == int(api["thread_id"]()), "AppBar operation requires its GUI thread")
        name = c.create_unicode_buffer(256)
        _require(
            api["class_name"](hwnd, name, len(name)) > 0 and name.value,
            "Cannot verify own window class",
        )
        generation = int(api["generation"](hwnd, WINDOW_GENERATION_PROPERTY) or 0)
        _require(_positive_uintptr(generation), "Own window generation property is absent")
        return pid.value, thread, name.value, generation

    def retain_window(self, hwnd, generation):
        """Explicit native read; nonce property is installed by the owning caller."""
        _require(_positive_uintptr(generation), "Invalid generation nonce")
        pid, thread, name, actual = self._inspect(hwnd)
        _require(actual == generation, "Own window generation changed")
        _require(
            not any(token.hwnd == hwnd for token in self._retained.values()),
            "HWND already retained by this backend",
        )
        token = OwnedWindow(hwnd, pid, thread, name, generation)
        self._retained[token._seal] = token
        return token

    def validate(self, token):
        _require(
            isinstance(token, OwnedWindow) and self._retained.get(token._seal) is token,
            "Window token was not retained by this backend",
        )
        _require(
            self._inspect(token.hwnd)
            == (token.pid, token.thread_id, token.class_name, token.generation),
            "Retained HWND identity/generation changed",
        )

    def claim(self, token, owner):
        self.validate(token)
        _require(
            token._seal not in self._claims or self._claims[token._seal] is owner,
            "Owned HWND already has an AppBar session",
        )
        self._claims[token._seal] = owner

    def release(self, token, owner):
        _require(
            self._claims.get(token._seal) is owner and token._seal not in self._registrations,
            "Cannot release an active or foreign AppBar lease",
        )
        del self._claims[token._seal]

    def release_window(self, token):
        """Pure token cleanup; never removes somebody else's generation property."""
        _require(
            self._retained.get(token._seal) is token
            and token._seal not in self._claims
            and token._seal not in self._registrations,
            "Window still has AppBar resources",
        )
        del self._retained[token._seal]

    def shell_registration_lost(self, token, owner):
        """Call only for a verified Shell-recreated notification, not routine relayout."""
        self.validate(token)
        _require(self._claims.get(token._seal) is owner, "Own lease required")
        self._registrations.discard(token._seal)

    def send(self, token, message, *, callback_message=0, rect=None, lparam=0):
        self.validate(token)
        _require(
            type(message) is int and message in _MESSAGES and token._seal in self._claims,
            "Unsupported/unclaimed AppBar operation",
        )
        _require(
            message == ABM_NEW or token._seal in self._registrations, "AppBar is not registered"
        )
        if message == ABM_NEW:
            _require(
                token._seal not in self._registrations
                and type(callback_message) is int
                and 0x8000 <= callback_message <= 0xFFFF,
                "Invalid/duplicate registration",
            )
        if message in (ABM_QUERYPOS, ABM_SETPOS):
            _require(
                isinstance(rect, PixelRect) and rect.width > 0 and rect.height > 0,
                "A positive physical rectangle is required",
            )
        _require(type(lparam) is int and lparam in (0, 1), "Invalid activation flag")
        data = APPBARDATA()
        data.cbSize, data.hWnd, data.uCallbackMessage = (
            c.sizeof(APPBARDATA),
            token.hwnd,
            callback_message,
        )
        data.uEdge, data.lParam = ABE_TOP, lparam
        if rect is not None:
            data.rc = RECT(rect.left, rect.top, rect.right, rect.bottom)
        returned = self._api()["appbar"](message, c.byref(data))
        _require(bool(returned), "SHAppBarMessage rejected operation " + str(message))
        if message == ABM_NEW:
            self._registrations.add(token._seal)
        elif message == ABM_REMOVE:
            self._registrations.remove(token._seal)
        if message in (ABM_QUERYPOS, ABM_SETPOS):
            return PixelRect(data.rc.left, data.rc.top, data.rc.right, data.rc.bottom)
        return None

    def place(self, token, rect):
        self.validate(token)
        _require(token._seal in self._registrations, "Cannot place an unreserved AppBar")
        flags = 0x0004 | 0x0010  # NOZORDER | NOACTIVATE; no showing or activation.
        _require(
            self._api()["position"](
                token.hwnd, None, rect.left, rect.top, rect.width, rect.height, flags
            ),
            "Owned AppBar positioning failed",
        )

    def set_fullscreen(self, token, opened):
        self.validate(token)
        _require(
            token._seal in self._registrations and type(opened) is bool,
            "Cannot change z-order without an AppBar reservation",
        )
        after = 1 if opened else -1  # HWND_BOTTOM for fullscreen, otherwise HWND_TOPMOST.
        _require(
            self._api()["position"](token.hwnd, c.c_void_p(after), 0, 0, 0, 0, 0x0013),
            "Owned AppBar z-order change failed",
        )

    def hide(self, token):
        self.validate(token)
        api = self._api()
        api["show"](token.hwnd, 0)  # Return is previous visibility, not success.
        self.validate(token)
        _require(not api["is_visible"](token.hwnd), "Owned AppBar did not hide")


class AppBarSession:
    """Injected backend state machine; it does not create windows or register on init.

    register/relayout use physical monitor bounds, not availableGeometry reduced
    by our own reservation. Caller routes native messages; position notifications
    only set needs_relayout so reentrant Shell callbacks cannot recursively reserve.
    READY means reserved/positioned, not shown: the owner shows its window without
    activation only after an ok result (also after a Shell recreation).
    close() must be called in finally, before destroying HWND/cookie. A context
    manager supplies that finally for exceptions but does NOT register on entry.
    cleanup_complete is true only after all owned reservation/visibility is closed.
    """

    def __init__(self, backend, token, callback_message):
        _require(
            type(callback_message) is int and 0x8000 <= callback_message <= 0xFFFF,
            "Application-defined callback message required",
        )
        self.backend, self.token, self.callback_message = backend, token, callback_message
        self._owner, self._thread = object(), threading.get_ident()
        self._claimed = self._registered = self._hidden = self._busy = False
        self._fullscreen = self.needs_relayout = False
        self._monitor = self._rect = None
        self._dpi, self._height_dip, self._shell_epoch = 96, 32, 0
        self._state, self._errors = "IDLE", ()

    def _result(self, ok):
        return AppBarResult(
            ok,
            self._state,
            self._registered,
            self._rect,
            not self._claimed and not self._registered,
            self._errors,
            self._fullscreen,
        )

    def _guard(self):
        _require(threading.get_ident() == self._thread, "Session requires its creating thread")
        _require(not self._busy, "Reentrant AppBar operation must be queued")

    @staticmethod
    def _validate_request(bounds, dpi, height_dip):
        _require(
            isinstance(bounds, PixelRect) and bounds.width > 0 and bounds.height > 0,
            "Positive physical monitor bounds required",
        )
        _require(type(dpi) is int and 48 <= dpi <= 768, "Invalid per-monitor DPI")
        _require(
            type(height_dip) in (int, float)
            and 16 <= height_dip <= 128
            and math.isfinite(height_dip),
            "Invalid bar height",
        )
        height = math.ceil(height_dip * dpi / 96)
        _require(height <= bounds.height, "Monitor cannot fit bar height")
        return height

    def _reserve(self, bounds, dpi, height_dip):
        height = self._validate_request(bounds, dpi, height_dip)
        if not self._claimed:
            self.backend.claim(self.token, self._owner)
            self._claimed = True
        if not self._registered:
            self.backend.send(self.token, ABM_NEW, callback_message=self.callback_message)
            self._registered = True
        self.backend.validate(self.token)
        approved = self.backend.send(self.token, ABM_QUERYPOS, rect=bounds)
        _require(
            _rect_inside(approved, bounds) and approved.height >= height,
            "Shell query returned no usable top band",
        )
        proposed = PixelRect(approved.left, approved.top, approved.right, approved.top + height)
        actual = self.backend.send(self.token, ABM_SETPOS, rect=proposed)
        _require(
            _rect_inside(actual, bounds) and actual.height == height,
            "Shell reservation is outside monitor or changed readable height",
        )
        self._rect = actual
        self.backend.place(self.token, actual)
        self.backend.set_fullscreen(self.token, self._fullscreen)
        self.backend.validate(self.token)
        self._monitor, self._dpi, self._height_dip = bounds, dpi, height_dip
        self._state, self._errors, self.needs_relayout = "READY", (), False
        self._hidden = False
        return self._result(True)

    def register(self, monitor_bounds, *, dpi=96, height_dip=32):
        self._guard()
        # Invalid caller data has no native side effect and leaves an existing bar alone.
        self._validate_request(monitor_bounds, dpi, height_dip)
        self._busy = True
        try:
            return self._reserve(monitor_bounds, dpi, height_dip)
        except Exception as error:
            return self._fail(error)
        finally:
            self._busy = False

    def relayout(self, monitor_bounds=None, *, dpi=None, height_dip=None):
        _require(self._registered, "No AppBar reservation to relayout")
        return self.register(
            monitor_bounds if monitor_bounds is not None else self._monitor,
            dpi=self._dpi if dpi is None else dpi,
            height_dip=self._height_dip if height_dip is None else height_dip,
        )

    def position_notification(self):
        """ABN_POSCHANGED: schedule one relayout on the caller's event loop."""
        _require(threading.get_ident() == self._thread, "Wrong callback thread")
        if self._registered:
            self.needs_relayout = True

    def shell_recreated(self, epoch):
        """Only for a verified new Shell generation. Duplicate epochs are no-ops."""
        self._guard()
        _require(type(epoch) is int and epoch > 0, "Positive Shell generation required")
        if epoch <= self._shell_epoch:
            return self._result(self._state == "READY")
        _require(self._claimed and self._monitor is not None, "No retained AppBar to recreate")
        self._busy = True
        try:
            self.backend.hide(self.token)
            self.backend.shell_registration_lost(self.token, self._owner)
            self._registered = False
            self._shell_epoch = epoch
            return self._reserve(self._monitor, self._dpi, self._height_dip)
        except Exception as error:
            return self._fail(error)
        finally:
            self._busy = False

    def fullscreen(self, opened):
        self._guard()
        _require(type(opened) is bool, "Explicit fullscreen state required")
        self._fullscreen = opened
        if not self._registered:
            return self._result(self._state == "IDLE")
        return self._notification(lambda: self.backend.set_fullscreen(self.token, opened))

    def notify_activation(self, active):
        _require(type(active) is bool, "Explicit activation state required")
        return self._notification(
            lambda: self.backend.send(self.token, ABM_ACTIVATE, lparam=int(active))
        )

    def notify_window_position(self):
        return self._notification(lambda: self.backend.send(self.token, ABM_WINDOWPOSCHANGED))

    def _notification(self, action):
        self._guard()
        _require(self._registered and self._state == "READY", "No ready AppBar for notification")
        self._busy = True
        try:
            action()
            self.backend.validate(self.token)
            return self._result(True)
        except Exception as error:
            return self._fail(error)
        finally:
            self._busy = False

    def _cleanup(self):
        errors = []
        if not self._claimed:
            return errors
        self._hidden = False  # Every attempt needs fresh proof; prior hide is not enough.
        try:
            self.backend.hide(self.token)
            self._hidden = True
        except Exception as error:
            errors.append("hide: " + str(error))
        finally:
            if self._registered:
                try:
                    self.backend.send(self.token, ABM_REMOVE)
                    self._registered = False
                    self._rect = None
                except Exception as error:
                    errors.append("unregister: " + str(error))
        if not self._registered and self._hidden:
            try:
                self.backend.release(self.token, self._owner)
                self._claimed = False
            except Exception as error:
                errors.append("lease release: " + str(error))
        return errors

    def _fail(self, error):
        self._errors = (str(error), *self._cleanup())
        self._state = "FAILED"
        return self._result(False)

    def close(self):
        self._guard()
        self._busy = True
        try:
            errors = tuple(self._cleanup())
            self._state, self._errors, self.needs_relayout = (
                ("FAILED" if errors else "CLOSED"),
                errors,
                False,
            )
            return self._result(not errors and not self._claimed and not self._registered)
        finally:
            self._busy = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        result = self.close()
        if not result.ok and exc is None:
            raise AppBarError("AppBar cleanup incomplete: " + "; ".join(result.errors))
        if not result.ok and exc is not None:
            exc.add_note("AppBar cleanup incomplete: " + "; ".join(result.errors))
        return False
