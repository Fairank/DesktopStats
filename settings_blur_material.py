"""Settings material: one owned HWND, compatibility blur, explicit solid fallback.

The normal DWM Desktop Acrylic backdrop can become solid on deactivation. This
host uses the same compatibility blur as the nonactivating menu bar instead.
No visible result is inferred from either API's return code.
"""
import ctypes as c
import os
import sys
import threading
from ctypes import wintypes as w

from native_widget_material import WidgetBlurBackend


def clear_desktop_backdrop(hwnd, *, valid):
    """Remove only our GUI-thread window's previous system backdrop contract."""
    result = dict(ok=False, compositing_verified=False)
    if type(hwnd) is not int or hwnd <= 0 or not SettingsBlurMaterial._valid(valid):
        return dict(result, fallback_reason="settings-surface-not-current")
    try:
        user = c.WinDLL("user32", use_last_error=True)
        user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        user.GetWindowThreadProcessId.restype = w.DWORD
        owner = w.DWORD()
        thread = user.GetWindowThreadProcessId(hwnd, c.byref(owner))
        if (not thread or owner.value != os.getpid()
                or thread != threading.get_native_id()
                or thread != threading.main_thread().native_id):
            return dict(result, fallback_reason="settings-window-not-owned-gui-thread")
        if sys.getwindowsversion().build < 22621:
            return dict(result, ok=True, noop=True)
        dwm = c.WinDLL("dwmapi", use_last_error=True)
        dwm.DwmSetWindowAttribute.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
        dwm.DwmSetWindowAttribute.restype = c.c_long
        none = c.c_int(1)
        if not SettingsBlurMaterial._valid(valid):
            return dict(result, fallback_reason="settings-surface-not-current")
        result["backdrop_result"] = dwm.DwmSetWindowAttribute(hwnd, 38, c.byref(none), c.sizeof(none))
        # Do not extend the frameless alpha client as an opaque native frame.
        class Margins(c.Structure):
            _fields_ = [(name, c.c_int) for name in ("left", "right", "top", "bottom")]
        dwm.DwmExtendFrameIntoClientArea.argtypes = [w.HWND, c.POINTER(Margins)]
        dwm.DwmExtendFrameIntoClientArea.restype = c.c_long
        margins = Margins(0, 0, 0, 0)
        # The first native call can reenter destruction; validate again.
        after = w.DWORD()
        later_thread = user.GetWindowThreadProcessId(hwnd, c.byref(after))
        if later_thread != thread or after.value != owner.value:
            return dict(result, fallback_reason="settings-window-owner-changed")
        if not SettingsBlurMaterial._valid(valid):
            return dict(result, fallback_reason="settings-surface-not-current")
        result["frame_result"] = dwm.DwmExtendFrameIntoClientArea(hwnd, c.byref(margins))
        result["ok"] = result["backdrop_result"] == result["frame_result"] == 0
        if not result["ok"]:
            result["fallback_reason"] = "settings-old-backdrop-clear-failed"
    except (OSError, AttributeError) as error:
        result.update(fallback_reason="settings-backdrop-api-unavailable", backend_error=str(error)[:512])
    return result


class SettingsBlurMaterial:
    def __init__(self, backend=None, clearer=None):
        self.backend = backend if backend is not None else WidgetBlurBackend()
        self.clearer = clearer
        self.identity = None
        self.prepared = False
        self.cleanup_failed = False
        self.closed = False
        self._alive = lambda: False

    @staticmethod
    def _valid(guard):
        try:
            return guard() is True
        except (RuntimeError, AttributeError):
            return False

    @staticmethod
    def _fallback(reason, **extra):
        return dict(material="solid", status="fallback", blur_configured=False,
                    coating_allowed=False, coating_translucent=False,
                    fallback_reason=reason, compositing_verified=False, **extra)

    def apply(self, hwnd, policy, *, surface_id, valid):
        if self.closed:
            return self._fallback("settings-backend-closed")
        identity = (surface_id, hwnd)
        if not self._valid(valid):
            return self._fallback("settings-surface-not-current")
        if self.cleanup_failed:
            return self._fallback("settings-previous-surface-cleanup-failed")
        if self.identity is not None and self.identity != identity:
            return self._fallback("settings-surface-not-released")
        self.identity = identity
        self._alive = valid
        cleanup = None
        if policy.get("state") == "allowed" and not self.prepared:
            try:
                cleanup = (self.clearer(hwnd) if self.clearer is not None
                           else clear_desktop_backdrop(hwnd, valid=valid))
            except (OSError, RuntimeError, AttributeError) as error:
                cleanup = dict(ok=False, fallback_reason="settings-backdrop-clear-exception", backend_error=str(error)[:512])
            if self.identity != identity or not self._valid(valid):
                return self._fallback("settings-surface-not-current")
            if not cleanup.get("ok"):
                cleared = self.backend.clear(hwnd)
                self.cleanup_failed = not cleared.get("ok") or cleared.get("blur_may_remain") is True
                return self._fallback(cleanup.get("fallback_reason", "settings-old-backdrop-clear-failed"),
                            backend_error=cleanup.get("backend_error", ""),
                            old_backdrop_cleanup=cleanup, cleanup=cleared,
                            blur_may_remain=cleared.get("blur_may_remain", False))
            self.prepared = True
        if not self._valid(valid):
            return self._fallback("settings-surface-not-current")
        report = self.backend.apply(hwnd, enabled=True, policy=policy)
        if self.identity != identity or not self._valid(valid):
            return self._fallback("settings-surface-not-current")
        if cleanup is not None:
            report["old_backdrop_cleanup"] = cleanup
        report["activation_independent"] = True
        return report

    def clear(self, hwnd, *, surface_id, valid):
        self._alive = valid
        if self.identity is None:
            return dict(ok=True, noop=True, cleanup_complete=True)
        if self.identity != (surface_id, hwnd) or not self._valid(valid):
            self.cleanup_failed = True
            return dict(ok=False, rejected=True, cleanup_complete=False,
                        fallback_reason="settings-release-surface-not-current")
        report = self.backend.clear(hwnd)
        self.cleanup_failed = not report.get("ok") or report.get("blur_may_remain") is True
        if not self.cleanup_failed:
            self.identity = None
            self.prepared = False
        return report

    def close(self):
        self.closed = True
        if self.identity is not None and not self._valid(self._alive):
            return dict(ok=False, cleanup_complete=False, blur_may_remain=self.cleanup_failed,
                        fallback_reason="settings-release-surface-not-current")
        report = self.backend.close()
        if report.get("ok"):
            self.identity = None
            self.prepared = False
        return report
