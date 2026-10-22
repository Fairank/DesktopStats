"""Own-window compatibility blur; never changes flags, geometry or activation.

Only WCA_ACCENT_POLICY state 3 (no extra tint) and state 0 are used. This is an
undocumented Windows interface, distinct from the settings window's DWM path.
API facts: github.com/zhiyiYo/PyQt-Frameless-Window, windows/window_effect.py.
No Qt, product imports or DLL loading at import/construction. The host supplies
policy and must call clear() before destroying/replacing an HWND. GUI operations
must run on the Python main thread that owns the application's windows.
"""

import ctypes as c
import os
import threading

HWND, BOOL, DWORD, SIZE_T = c.c_void_p, c.c_int32, c.c_uint32, c.c_size_t


class _AccentPolicy(c.Structure):
    _fields_ = [("state", DWORD), ("flags", DWORD), ("gradient", DWORD), ("animation", DWORD)]


class _CompositionData(c.Structure):
    _fields_ = [("attribute", c.c_int32), ("data", c.c_void_p), ("size", SIZE_T)]


class _CtypesBlurAPI:
    def __init__(self, loader=None):
        self.dll = (loader or c.WinDLL)("user32", use_last_error=True)
        self.dll.IsWindow.argtypes, self.dll.IsWindow.restype = [HWND], BOOL
        self.dll.GetWindowThreadProcessId.argtypes = [HWND, c.POINTER(DWORD)]
        self.dll.GetWindowThreadProcessId.restype = DWORD
        self.dll.SetWindowCompositionAttribute.argtypes = [HWND, c.POINTER(_CompositionData)]
        self.dll.SetWindowCompositionAttribute.restype = BOOL

    def is_window(self, hwnd):
        return bool(self.dll.IsWindow(HWND(hwnd)))

    def owner(self, hwnd):
        process = DWORD()
        thread = self.dll.GetWindowThreadProcessId(HWND(hwnd), c.byref(process))
        return int(thread), process.value

    def set_blur(self, hwnd, enabled):
        if type(enabled) is not bool:
            raise ValueError("Blur request requires bool")
        accent = _AccentPolicy(3 if enabled else 0, 0, 0, 0)
        data = _CompositionData(19, c.cast(c.pointer(accent), c.c_void_p), c.sizeof(accent))
        c.set_last_error(0)
        result = self.dll.SetWindowCompositionAttribute(HWND(hwnd), c.byref(data))
        return int(result), c.get_last_error()


class _Rejected(Exception):
    pass


def _policy(value):
    state = value.get("state") if isinstance(value, dict) else value
    if type(state) is not str or state not in ("allowed", "disabled", "unknown"):
        state = "unknown"
    defaults = {
        "allowed": "allowed",
        "disabled": "transparency-disabled",
        "unknown": "transparency-policy-unavailable",
    }
    reason = value.get("reason") if isinstance(value, dict) else None
    return {
        "state": state,
        "reason": reason[:240] if isinstance(reason, str) and reason else defaults[state],
    }


def _report(hwnd, policy=None, enabled=False):
    decision = _policy(policy)
    allowed = decision["state"] == "allowed"
    translucent = allowed and enabled is True
    return dict(
        hwnd=hwnd if type(hwnd) is int else None,
        policy=decision,
        material="translucent" if translucent else "solid",
        status="fallback",
        coating_allowed=allowed,
        coating_translucent=translucent,
        blur_configured=False,
        blur_may_remain=False,
        compositing_verified=False,
        mechanism="undocumented-accent-policy",
        accent_state=0,
        bool_result=None,
        last_error=None,
        ok=False,
    )


class WidgetBlurBackend:
    """api may inject is_window, owner->(tid,pid), set_blur->(BOOL,LastError).

    Failed removal stays pending and close() may be retried. API success reports
    only a configured request, never proof of visible blur. No state 4 is used.
    """

    def __init__(self, api=None, *, api_factory=None):
        self._api = api
        self._factory = api_factory if api_factory is not None else _CtypesBlurAPI
        self._gui_thread = threading.main_thread().native_id
        self._pending = set()
        self._closed = False

    def _guard(self, hwnd):
        if type(hwnd) is not int or not 0 < hwnd < 1 << (c.sizeof(HWND) * 8):
            raise _Rejected("invalid-window-handle")
        if threading.get_native_id() != self._gui_thread:
            raise _Rejected("requires-gui-thread")
        if self._api is None:
            self._api = self._factory()
        if not self._api.is_window(hwnd):
            raise _Rejected("window-not-live")
        thread, process = self._api.owner(hwnd)
        if type(process) is not int or process != os.getpid():
            raise _Rejected("window-not-owned")
        if type(thread) is not int or thread != self._gui_thread:
            raise _Rejected("window-not-gui-thread")

    def _request(self, hwnd, enabled):
        result = dict(ok=False, accent_state=3 if enabled else 0, bool_result=None, last_error=None)
        try:
            self._guard(hwnd)
        except _Rejected as error:
            return dict(result, fallback_reason=str(error), rejected=True)
        except Exception as error:
            return dict(
                result,
                fallback_reason="native-api-unavailable",
                backend_error=f"{type(error).__name__}: {error}"[:500],
            )
        try:
            value, last_error = self._api.set_blur(hwnd, enabled)
            result.update(ok=bool(value), bool_result=int(value), last_error=int(last_error))
            if not result["ok"]:
                result["fallback_reason"] = (
                    "accent-request-failed" if enabled else "accent-clear-failed"
                )
        except Exception as error:
            result.update(
                fallback_reason="accent-request-exception" if enabled else "accent-clear-exception",
                backend_error=f"{type(error).__name__}: {error}"[:500],
            )
            winerror = getattr(error, "winerror", None)
            if type(winerror) is int:
                result["last_error"] = winerror
        return result

    def apply(self, hwnd, enabled=True, policy=None):
        report = _report(hwnd, policy, enabled)
        report["blur_may_remain"] = type(hwnd) is int and hwnd in self._pending
        if type(enabled) is not bool or not enabled or not report["coating_allowed"]:
            cleanup = self.clear(hwnd)
            report.update(
                cleanup=cleanup,
                ok=cleanup["ok"],
                bool_result=cleanup["bool_result"],
                last_error=cleanup["last_error"],
                status="no-blur" if enabled is False else "fallback",
                fallback_reason=(
                    "invalid-enabled"
                    if type(enabled) is not bool
                    else "material-disabled"
                    if not enabled
                    else report["policy"]["reason"]
                ),
            )
            if not cleanup["ok"]:
                report.update(status="cleanup-failed", fallback_reason=cleanup["fallback_reason"])
            if type(enabled) is not bool:
                report.update(ok=False, rejected=True)
            report["blur_may_remain"] = type(hwnd) is int and hwnd in self._pending
            return report
        if self._closed:
            report["fallback_reason"] = "backend-closed"
            return report
        try:
            self._guard(hwnd)
        except _Rejected as error:
            report.update(fallback_reason=str(error), rejected=True)
            return report
        except Exception as error:
            report.update(
                fallback_reason="native-api-unavailable",
                backend_error=f"{type(error).__name__}: {error}"[:500],
            )
            return report
        self._pending.add(hwnd)
        report.update(self._request(hwnd, True))
        if report["ok"]:
            report.update(
                material="system-blur",
                status="configured-unverified",
                blur_configured=True,
                blur_may_remain=False,
            )
        else:
            report["cleanup"] = self.clear(hwnd)
            report["blur_may_remain"] = hwnd in self._pending
        return report

    def clear(self, hwnd):
        report = _report(hwnd)
        try:
            self._guard(hwnd)
        except _Rejected as error:
            report.update(fallback_reason=str(error), rejected=True)
        except Exception as error:
            report.update(
                fallback_reason="native-api-unavailable",
                backend_error=f"{type(error).__name__}: {error}"[:500],
            )
        else:
            if hwnd not in self._pending:
                report.update(ok=True, noop=True)
            else:
                report.update(self._request(hwnd, False))
                if report["ok"]:
                    self._pending.discard(hwnd)
        pending = type(hwnd) is int and hwnd in self._pending
        report.update(
            cleanup_complete=report["ok"] and not pending,
            blur_may_remain=pending,
            status="no-blur" if report["ok"] else "cleanup-failed",
        )
        return report

    def close(self):
        self._closed = True
        results = [self.clear(hwnd) for hwnd in sorted(self._pending)]
        return dict(
            ok=not self._pending,
            complete=not self._pending,
            pending=sorted(self._pending),
            results=results,
            compositing_verified=False,
            blur_configured=False,
            blur_may_remain=bool(self._pending),
        )
