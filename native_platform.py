"""Windows composition for our own native windows; no screen capture or drivers."""

import ctypes as c
import sys
import winreg
from ctypes import wintypes as w


class Margins(c.Structure):
    _fields_ = [(name, c.c_int) for name in ("left", "right", "top", "bottom")]


def _system_parameters():
    query = c.WinDLL("user32", use_last_error=True).SystemParametersInfoW
    query.argtypes = [w.UINT, w.UINT, c.c_void_p, w.UINT]
    query.restype = w.BOOL
    return query


def animations_enabled():
    """Read the client's animation preference; unavailable policy means no motion."""
    # SPI_GETCLIENTAREAANIMATION, not its adjacent SPI_SET* counterpart.
    enabled = w.BOOL()
    try:
        return bool(_system_parameters()(0x1042, 0, c.byref(enabled), 0) and enabled.value)
    except (OSError, AttributeError):
        return False


def transparency_policy():
    """Distinguish an explicit accessibility choice from an unreadable policy."""

    class HighContrast(c.Structure):
        _fields_ = [("size", w.UINT), ("flags", w.DWORD), ("scheme", w.LPWSTR)]

    contrast = HighContrast()
    contrast.size = c.sizeof(contrast)
    try:
        if not _system_parameters()(0x42, contrast.size, c.byref(contrast), 0):
            return {"state": "unknown", "reason": "accessibility-query-failed", "winerror": c.get_last_error()}
        if contrast.flags & 1:
            return {"state": "disabled", "reason": "high-contrast"}
    except (OSError, AttributeError) as error:
        return {"state": "unknown", "reason": "accessibility-query-unavailable", "error": str(error)[:240], "winerror": getattr(error, "winerror", None)}
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value = winreg.QueryValueEx(key, "EnableTransparency")[0]
            if type(value) is not int or value not in (0, 1):
                return {"state": "unknown", "reason": "transparency-preference-invalid"}
            return {"state": "allowed" if value == 1 else "disabled", "reason": "allowed" if value == 1 else "transparency-disabled"}
    except (OSError, AttributeError) as error:
        return {"state": "unknown", "reason": "transparency-preference-unreadable", "error": str(error)[:240], "winerror": getattr(error, "winerror", None)}


def transparency_enabled():
    """Fail closed without misreporting a query failure as a user preference."""
    return transparency_policy()["state"] == "allowed"


def widget_material(enabled=True):
    """Describe policy-allowed alpha coating for the legacy widget window.

    This function takes no HWND and configures no compositor or blur backend.
    A translucent result allows the painter to honor its continuous background
    alpha; it does not verify rendered transparency or system blur. Accessibility
    and transparency policy can force a readable solid coating. Settings retain
    their separate, explicitly unverified glass() composition request.
    """
    allowed = transparency_enabled()
    translucent = bool(enabled and allowed)
    report = {
        "coating_allowed": allowed,
        "coating_translucent": translucent,
        "material": "translucent" if translucent else "solid",
        "blur_configured": False,
        "compositing_verified": False,
        "status": "translucent" if translucent else "fallback",
    }
    if not translucent:
        report["fallback_reason"] = (
            "transparency-disabled" if enabled else "material-disabled"
        )
    return report


def _clear_backdrop(dwm, hwnd, report):
    """Best-effort removal after partial setup; no callbacks or native allocations."""
    try:
        value = c.c_int(1)  # DWMSBT_NONE
        setter = dwm.DwmSetWindowAttribute
        setter.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
        setter.restype = c.c_long
        report["cleanup_backdrop_result"] = setter(hwnd, 38, c.byref(value), c.sizeof(value))
    except (OSError, AttributeError) as error:
        report["cleanup_backdrop_error"] = str(error)
    try:
        margins = Margins(0, 0, 0, 0)
        extend = dwm.DwmExtendFrameIntoClientArea
        extend.argtypes = [w.HWND, c.POINTER(Margins)]
        extend.restype = c.c_long
        report["cleanup_frame_result"] = extend(hwnd, c.byref(margins))
    except (OSError, AttributeError) as error:
        report["cleanup_frame_error"] = str(error)


def refresh_owned_frame(hwnd):
    """Invalidate only our GUI-thread frame, without resizing or activating it.

    DWM's extended client frame must be recalculated independently of a user
    resize. This is a native frame notification, not a synthetic geometry change
    or a claim that an accepted backdrop has been visually verified.
    """
    report = {"frame_refresh_result": False}
    try:
        user = c.WinDLL("user32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
        user.GetWindowThreadProcessId.restype = w.DWORD
        kernel.GetCurrentProcessId.argtypes = []
        kernel.GetCurrentProcessId.restype = w.DWORD
        kernel.GetCurrentThreadId.argtypes = []
        kernel.GetCurrentThreadId.restype = w.DWORD
        def owned_here():
            owner = w.DWORD()
            thread = user.GetWindowThreadProcessId(hwnd, c.byref(owner))
            return bool(thread and owner.value == kernel.GetCurrentProcessId()
                        and thread == kernel.GetCurrentThreadId())
        if not owned_here():
            report["frame_refresh_error"] = "not-owned-gui-thread"
            return report
        user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
        user.SetWindowPos.restype = w.BOOL
        # NO{SIZE,MOVE,ZORDER,ACTIVATE,OWNERZORDER} | FRAMECHANGED.
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020 | 0x0200
        report["frame_refresh_result"] = bool(user.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags))
        if not report["frame_refresh_result"]:
            report["frame_refresh_winerror"] = c.get_last_error()
            return report
        # FRAMECHANGED dispatches synchronously; teardown/recreation can run
        # inside it. Never send a later repaint to a stale or recycled HWND.
        if not owned_here():
            report["frame_refresh_error"] = "owner-changed-during-refresh"
            return report
        user.RedrawWindow.argtypes = [w.HWND, c.c_void_p, w.HRGN, w.UINT]
        user.RedrawWindow.restype = w.BOOL
        # Queue invalidation; no synchronous paint, erase, capture, or focus.
        report["frame_redraw_result"] = bool(user.RedrawWindow(hwnd, None, None, 0x0401))
    except (OSError, AttributeError) as error:
        report["frame_refresh_error"] = str(error)[:512]
    return report


def glass(hwnd, dark=False, enabled=True, *, policy=None):
    """Request Desktop Acrylic. A configured attribute is not rendered proof."""
    report = {
        "material": "solid",
        "build": sys.getwindowsversion().build,
        "compositing_verified": False,
        "status": "fallback",
    }
    if report["build"] < 22621:
        report["fallback_reason"] = "unsupported-windows"
        return report
    dwm = None
    try:
        dwm = c.WinDLL("dwmapi")
        set_attr = dwm.DwmSetWindowAttribute
        set_attr.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
        set_attr.restype = c.c_long
        dwm.DwmExtendFrameIntoClientArea.argtypes = [w.HWND, c.POINTER(Margins)]
        dwm.DwmExtendFrameIntoClientArea.restype = c.c_long
        dwm.DwmGetWindowAttribute.argtypes = [w.HWND, w.DWORD, c.c_void_p, w.DWORD]
        dwm.DwmGetWindowAttribute.restype = c.c_long
        for attribute, value in ((20, int(dark)), (33, 2), (34, 0xFFFFFFFE)):
            number = c.c_int(value) if value < 0x80000000 else w.DWORD(value)
            report[f"attribute_{attribute}_result"] = set_attr(
                hwnd, attribute, c.byref(number), c.sizeof(number)
            )
        allowed = enabled and (policy.get("state") == "allowed" if policy is not None else transparency_enabled())
        if policy is not None:
            report["policy"] = dict(policy)
        if not allowed:
            report["fallback_reason"] = (policy.get("reason", "transparency-policy-unavailable") if policy is not None else "transparency-disabled") if enabled else "material-disabled"
        # This is a GDI redirection-bitmap candidate, not a Qt DirectComposition
        # switch. Its impact on the accelerated swap chain remains unverified.
        if allowed and report["build"] >= 26100:
            alpha = c.c_int(1)
            report["redirection_alpha_result"] = set_attr(hwnd, 39, c.byref(alpha), c.sizeof(alpha))
        margins = Margins(*((-1,) * 4 if allowed else (0,) * 4))
        report["frame_result"] = dwm.DwmExtendFrameIntoClientArea(hwnd, c.byref(margins))
        if allowed and report["frame_result"] != 0:
            allowed = False
            report["fallback_reason"] = "frame-extension-failed"
            _clear_backdrop(dwm, hwnd, report)
        value = c.c_int(3 if allowed else 1)
        report["backdrop_result"] = set_attr(hwnd, 38, c.byref(value), c.sizeof(value))
        confirmed = c.c_int()
        report["backdrop_read_result"] = dwm.DwmGetWindowAttribute(
            hwnd, 38, c.byref(confirmed), c.sizeof(confirmed)
        )
        if report["backdrop_read_result"] == 0:
            report["backdrop_type"] = confirmed.value
        if allowed:
            if report["backdrop_result"] == 0 and report.get("backdrop_type") == 3:
                report.update(material="desktop-acrylic", status="configured-unverified")
                report.update(refresh_owned_frame(hwnd))
            else:
                report["fallback_reason"] = "backdrop-unconfirmed"
                # Stop a partially configured backdrop before painting solid fallback.
                _clear_backdrop(dwm, hwnd, report)
        user = c.WinDLL("user32")
        user.GetWindowLongPtrW.argtypes = [w.HWND, c.c_int]
        user.GetWindowLongPtrW.restype = c.c_ssize_t
        report["layered"] = bool(user.GetWindowLongPtrW(hwnd, -20) & 0x80000)
    except (OSError, AttributeError) as error:
        report.update(
            material="solid",
            status="fallback",
            fallback_reason="native-api-unavailable",
            backend_error=str(error),
        )
        if dwm is not None:
            _clear_backdrop(dwm, hwnd, report)
    return report


def desktop_level(hwnd):
    """A non-activating desktop tool window, below ordinary application windows."""
    user = c.WinDLL("user32", use_last_error=True)
    user.GetWindowLongPtrW.argtypes = [w.HWND, c.c_int]
    user.GetWindowLongPtrW.restype = c.c_ssize_t
    user.SetWindowLongPtrW.argtypes = [w.HWND, c.c_int, c.c_ssize_t]
    user.SetWindowLongPtrW.restype = c.c_ssize_t
    style = user.GetWindowLongPtrW(hwnd, -20)
    user.SetWindowLongPtrW(hwnd, -20, (style | 0x08000080) & ~0x40000)
    user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
    user.SetWindowPos(hwnd, w.HWND(1), 0, 0, 0, 0, 0x0013)  # bottom, no activate/move/resize


def desktop_below(hwnd):
    """Check this window's position relative to the shell, without reading content."""
    user = c.WinDLL("user32")
    user.GetWindow.argtypes = [w.HWND, w.UINT]
    user.GetWindow.restype = w.HWND
    user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    current = user.GetWindow(hwnd, 2)
    for _ in range(2000):
        if not current:
            return False
        name = c.create_unicode_buffer(128)
        user.GetClassNameW(current, name, 128)
        if name.value in ("Progman", "WorkerW"):
            return True
        current = user.GetWindow(current, 2)
    return False


def pinned_level(hwnd):
    """Explicit user-selected topmost level for this owned nonactivating widget."""
    user = c.WinDLL("user32",use_last_error=True)
    user.SetWindowPos.argtypes = [w.HWND,w.HWND,c.c_int,c.c_int,c.c_int,c.c_int,w.UINT]
    user.SetWindowPos.restype = w.BOOL
    if not user.SetWindowPos(hwnd,w.HWND(-1),0,0,0,0,0x0013):
        raise c.WinError(c.get_last_error())
