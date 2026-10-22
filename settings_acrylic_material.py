"""Owned-window DWM Acrylic requests; no Qt, WCA, capture or visual claims.

The presenter must supply a live GUI-thread HWND and a surface-generation guard.
This adapter only requests attribute38/type3, extends the frame, and reads back
the type. It cannot establish whether the presenter's pixels expose that frame.
DLL loading is lazy. An injected API supports isolated tests without Windows.
"""

import ctypes as c
import os
import sys
import threading

HWND, DWORD, HRESULT = c.c_void_p, c.c_uint32, c.c_int32


class _Margins(c.Structure):
    _fields_ = [(name, c.c_int32) for name in ("left", "right", "top", "bottom")]


class _CtypesAcrylicAPI:
    def __init__(self, loader=None):
        load = loader or c.WinDLL
        self.user = load("user32", use_last_error=True)
        self.dwm = load("dwmapi", use_last_error=True)
        self.user.IsWindow.argtypes, self.user.IsWindow.restype = [HWND], c.c_int32
        self.user.GetWindowThreadProcessId.argtypes = [HWND, c.POINTER(DWORD)]
        self.user.GetWindowThreadProcessId.restype = DWORD
        for name in ("DwmSetWindowAttribute", "DwmGetWindowAttribute"):
            method = getattr(self.dwm, name)
            method.argtypes, method.restype = [HWND, DWORD, c.c_void_p, DWORD], HRESULT
        self.dwm.DwmExtendFrameIntoClientArea.argtypes = [HWND, c.POINTER(_Margins)]
        self.dwm.DwmExtendFrameIntoClientArea.restype = HRESULT

    def build(self):
        return sys.getwindowsversion().build

    def is_window(self, hwnd):
        return bool(self.user.IsWindow(HWND(hwnd)))

    def owner(self, hwnd):
        process = DWORD()
        thread = self.user.GetWindowThreadProcessId(HWND(hwnd), c.byref(process))
        return int(thread), process.value

    def set_backdrop(self, hwnd, value):
        selected = c.c_int32(value)
        return int(self.dwm.DwmSetWindowAttribute(HWND(hwnd), 38, c.byref(selected), 4))

    def extend_frame(self, hwnd, margins):
        value = _Margins(*margins)
        return int(self.dwm.DwmExtendFrameIntoClientArea(HWND(hwnd), c.byref(value)))

    def get_backdrop(self, hwnd):
        value = c.c_int32()
        result = self.dwm.DwmGetWindowAttribute(HWND(hwnd), 38, c.byref(value), 4)
        return int(result), value.value


class _Rejected(Exception):
    pass


def _policy(value):
    state = value.get("state") if isinstance(value, dict) else "unknown"
    if type(state) is not str or state not in ("allowed", "disabled", "unknown"):
        state = "unknown"
    reason = value.get("reason") if isinstance(value, dict) else None
    if not isinstance(reason, str) or not reason:
        reason = {
            "allowed": "allowed",
            "disabled": "transparency-disabled",
            "unknown": "transparency-policy-unavailable",
        }[state]
    return dict(state=state, reason=reason[:240])


class SettingsAcrylicMaterial:
    """api: build/is_window/owner/set_backdrop/extend_frame/get_backdrop.

    Surface IDs are positive integer serials, not HWNDs. Failed cleanup retains
    the old identity and guard; close/clear may retry it, never a replacement.
    close blocks future apply even if its first cleanup attempt fails.
    """

    def __init__(self, api=None, *, api_factory=None):
        self._api = api
        self._factory = api_factory if api_factory is not None else _CtypesAcrylicAPI
        self._gui_thread = threading.main_thread().native_id
        self.identity = None
        self.closed = False
        self.prepared = False
        self.cleanup_failed = False
        self._alive = None
        self._pending = False
        self._busy = False
        self._mutations = 0

    @staticmethod
    def _valid(guard):
        try:
            return callable(guard) and guard() is True
        except Exception:
            return False

    def _report(self, hwnd=None, policy=None, reason=""):
        return dict(
            hwnd=hwnd if type(hwnd) is int else None,
            material="solid",
            status="fallback",
            policy=_policy(policy),
            ok=False,
            coating_allowed=False,
            coating_translucent=False,
            blur_configured=False,
            blur_may_remain=self._pending,
            compositing_verified=False,
            backdrop_result=None,
            frame_result=None,
            readback_result=None,
            backdrop_type=None,
            fallback_reason=reason,
        )

    def _input(self, hwnd, serial, valid):
        if threading.get_native_id() != self._gui_thread:
            raise _Rejected("requires-gui-thread")
        if type(hwnd) is not int or not 0 < hwnd < 1 << (c.sizeof(HWND) * 8):
            raise _Rejected("invalid-window-handle")
        if type(serial) is not int or serial <= 0:
            raise _Rejected("invalid-surface-id")
        if not self._valid(valid):
            raise _Rejected("settings-surface-not-current")

    def _guard(self, identity, valid, *, releasing=False, unclaimed=False):
        serial, hwnd = identity
        self._input(hwnd, serial, valid)
        if self.closed and not releasing:
            raise _Rejected("settings-backend-closed")
        if self.identity != identity and not (unclaimed and self.identity is None):
            raise _Rejected("settings-surface-not-current")
        if self._api is None:
            self._api = self._factory()
        build = self._api.build()
        if type(build) is not int or build < 22621:
            raise _Rejected("desktop-acrylic-unsupported")
        if not self._api.is_window(hwnd):
            raise _Rejected("window-not-live")
        thread, process = self._api.owner(hwnd)
        if type(process) is not int or process != os.getpid():
            raise _Rejected("window-not-owned")
        if type(thread) is not int or thread != self._gui_thread:
            raise _Rejected("window-not-gui-thread")
        # API loading/ownership callbacks may reenter surface destruction.
        self._input(hwnd, serial, valid)
        if (self.closed and not releasing) or (
            self.identity != identity and not (unclaimed and self.identity is None)
        ):
            raise _Rejected("settings-surface-not-current")

    @staticmethod
    def _hr(value):
        if type(value) is not int or not -(1 << 31) <= value < 1 << 32:
            raise ValueError("Invalid native HRESULT")
        return value

    def _call(self, identity, valid, name, *args, releasing=False):
        self._guard(identity, valid, releasing=releasing)
        if name != "get_backdrop":
            self._pending = True  # A failing/raising mutation may still touch DWM.
            self._mutations += 1
        value = getattr(self._api, name)(identity[1], *args)
        self._guard(identity, valid, releasing=releasing)
        return value

    @staticmethod
    def _error(report, error):
        report.update(
            ok=False,
            status="fallback",
            material="solid",
            coating_allowed=False,
            coating_translucent=False,
            blur_configured=False,
            fallback_reason=str(error)
            if isinstance(error, _Rejected)
            else "desktop-acrylic-api-error",
        )
        if isinstance(error, _Rejected):
            report["rejected"] = True
        else:
            report["backend_error"] = f"{type(error).__name__}: {error}"[:500]

    def _clear_current(self, identity, valid):
        report = self._report(identity[1])
        report.update(status="cleanup-failed", cleanup_complete=False)
        try:
            # Continue best-effort cleanup after an HRESULT/exception failure,
            # but never continue after ownership or generation rejection.
            for name, args, field in (
                ("set_backdrop", (1,), "backdrop_result"),
                ("extend_frame", ((0, 0, 0, 0),), "frame_result"),
            ):
                try:
                    report[field] = self._hr(
                        self._call(identity, valid, name, *args, releasing=True)
                    )
                except _Rejected:
                    raise
                except Exception as error:
                    report.setdefault("backend_error", f"{type(error).__name__}: {error}"[:500])
            read_hr, actual = self._call(identity, valid, "get_backdrop", releasing=True)
            report.update(readback_result=self._hr(read_hr), backdrop_type=actual)
            complete = (
                all(
                    report[name] == 0
                    for name in ("backdrop_result", "frame_result", "readback_result")
                )
                and type(actual) is int
                and actual == 1
            )
            if complete:
                self.identity = None
                self._alive = None
                self._pending = False
                self.prepared = False
                self.cleanup_failed = False
                report.update(
                    ok=True,
                    status="no-blur",
                    cleanup_complete=True,
                    blur_may_remain=False,
                    fallback_reason="",
                )
            else:
                report["fallback_reason"] = "desktop-acrylic-clear-failed"
        except Exception as error:
            self._error(report, error)
            report["status"] = "cleanup-failed"
        if not report["cleanup_complete"]:
            self.cleanup_failed = True
            report["blur_may_remain"] = self._pending
        return report

    def apply(self, hwnd, policy, *, surface_id, valid):
        report = self._report(hwnd, policy)
        if self.closed:
            report["fallback_reason"] = "settings-backend-closed"
            return report
        if self._busy:
            report.update(rejected=True, fallback_reason="settings-native-operation-in-progress")
            return report
        identity = (surface_id, hwnd)
        mutations_before = self._mutations
        self._busy = True
        try:
            self._input(hwnd, surface_id, valid)
            if self.identity is not None and self.identity != identity:
                raise _Rejected("settings-surface-not-released")
            if self.cleanup_failed:
                raise _Rejected("settings-previous-surface-cleanup-failed")
            self._guard(identity, valid, unclaimed=True)
            self.identity, self._alive = identity, valid
            if report["policy"]["state"] != "allowed":
                cleanup = self._clear_current(identity, valid)
                report.update(
                    cleanup=cleanup,
                    ok=cleanup["ok"],
                    cleanup_complete=cleanup["cleanup_complete"],
                    blur_may_remain=cleanup["blur_may_remain"],
                    fallback_reason=report["policy"]["reason"],
                )
                return report
            report["backdrop_result"] = self._hr(self._call(identity, valid, "set_backdrop", 3))
            if report["backdrop_result"] != 0:
                raise RuntimeError("Backdrop request failed")
            report["frame_result"] = self._hr(
                self._call(identity, valid, "extend_frame", (-1, -1, -1, -1))
            )
            if report["frame_result"] != 0:
                raise RuntimeError("Frame request failed")
            read_hr, actual = self._call(identity, valid, "get_backdrop")
            report.update(readback_result=self._hr(read_hr), backdrop_type=actual)
            if read_hr != 0 or type(actual) is not int or actual != 3:
                raise RuntimeError("Backdrop readback mismatch")
            self.prepared = True
            report.update(
                ok=True,
                material="desktop-acrylic",
                status="configured-unverified",
                coating_allowed=True,
                coating_translucent=True,
                blur_configured=True,
                blur_may_remain=False,
                fallback_reason="",
                inactive_appearance="system-managed",
            )
        except Exception as error:
            self._error(report, error)
            if self.identity == identity and self._mutations > mutations_before:
                report["cleanup"] = self._clear_current(identity, valid)
                report["blur_may_remain"] = self._pending
        finally:
            self._busy = False
        return report

    def clear(self, hwnd, *, surface_id, valid):
        report = self._report(hwnd)
        if self._busy:
            return dict(
                report,
                rejected=True,
                cleanup_complete=False,
                fallback_reason="settings-native-operation-in-progress",
            )
        self._busy = True
        try:
            self._input(hwnd, surface_id, valid)
            if self.identity is None:
                return dict(
                    report,
                    ok=True,
                    noop=True,
                    status="no-blur",
                    cleanup_complete=True,
                    fallback_reason="",
                )
            if self.identity != (surface_id, hwnd):
                raise _Rejected("settings-release-surface-not-current")
            self._alive = valid
            return self._clear_current(self.identity, valid)
        except Exception as error:
            self._error(report, error)
            report["cleanup_complete"] = False
            if self._pending:
                self.cleanup_failed = True
            return report
        finally:
            self._busy = False

    def close(self):
        report = self._report(self.identity[1] if self.identity else None)
        if threading.get_native_id() != self._gui_thread:
            return dict(
                report,
                cleanup_complete=False,
                complete=False,
                fallback_reason="requires-gui-thread",
            )
        self.closed = True
        if self._busy:
            return dict(
                report,
                cleanup_complete=False,
                complete=False,
                fallback_reason="settings-native-operation-in-progress",
            )
        if self.identity is None:
            return dict(
                report,
                ok=True,
                noop=True,
                cleanup_complete=True,
                complete=True,
                status="no-blur",
                fallback_reason="",
            )
        self._busy = True
        try:
            result = self._clear_current(self.identity, self._alive)
            return dict(result, complete=result["cleanup_complete"])
        finally:
            self._busy = False
