"""Opt-in, once-per-session elevation of the fixed installed ASUS reader.

No native work, process launch, polling or file access occurs on import or
construction. Call update from the GUI's existing sensor update, then close at
shutdown. The bridge itself remains bound to this app PID and exits with it.

Win32 contract:
https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-shellexecuteinfow
"""

from __future__ import annotations

import ctypes as c
import hashlib
import logging
import math
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from cpu_temperature import FRESH_SECONDS, is_requested

PREFERENCE = "cpu_temperature_prompt_on_start"
HELPER_SHA256 = "09a329fe88294a017fb7db39ed123ad27312ab889b09d473dd5c0dfe8e1708ac"
HELPER_RELATIVE = Path("_internal/cpu-temperature/AsusCpuTemperatureBridge.exe")
_LOG = logging.getLogger("DesktopStats.temperature_startup")
_LOG.setLevel(logging.INFO)


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def temperature_ready(data, now):
    value = data.get("cpu_temp")
    stamp = data.get("metric_timestamps", {}).get("cpu_temp", data.get("time"))
    return (type(value) in (int, float) and math.isfinite(value) and 0 < value < 125
            and type(stamp) in (int, float) and math.isfinite(stamp)
            and 0 <= now - stamp <= FRESH_SECONDS)


class CpuTemperatureLauncher:
    def __init__(self, *, headless=False, platform=None, frozen=None, executable=None,
                 environ=None, app_pid=None, api_factory=None, wall_clock=None):
        self._headless = headless
        self._platform = sys.platform if platform is None else platform
        self._frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        self._executable = Path(sys.executable if executable is None else executable)
        self._environ = os.environ if environ is None else environ
        self._pid = os.getpid() if app_pid is None else app_pid
        self._factory = api_factory or _NativeApi
        self._wall = wall_clock or time.time
        self._api = None
        self._closed = self._terminal = self._attempted = self._updating = False
        self._state, self._reason, self._error = "idle", "", 0

    def _set(self, state, reason="", error=0):
        previous = (self._state, self._reason, self._error)
        self._state, self._reason, self._error = state, reason, error
        if previous != (state, reason, error):
            _LOG.info("CPU temperature startup state=%s reason=%s error=%s", state, reason, error)
        return self.status()

    def status(self):
        return dict(state=self._state, reason=self._reason, attempted=self._attempted,
                    error=self._error)

    def update(self, config, data, *, fullscreen=None):
        if self._closed or self._terminal or self._updating:
            return self.status()
        if (self._headless or self._platform != "win32" or not self._frozen
                or self._environ.get("DESKTOP_STATS_CPU_BRIDGE_DISABLED") == "1"
                or self._environ.get("DESKTOP_STATS_DATA")):
            return self._set("disabled", "unsupported_session")
        if config.get(PREFERENCE) is not True:
            return self._set("disabled", "preference_off")
        if not is_requested(config):
            return self._set("idle", "temperature_not_requested")
        if temperature_ready(data, self._wall()):
            return self._set("ready", "existing_temperature")
        local = self._environ.get("LOCALAPPDATA")
        expected = Path(local) / "Programs/DesktopStats/DesktopStats.exe" if local else None
        if expected is None or not expected.is_absolute() or not _same_path(self._executable, expected):
            self._terminal = True
            return self._set("blocked", "installed_identity")
        fullscreen = fullscreen() if callable(fullscreen) else fullscreen
        if fullscreen is not False:
            return self._set("deferred", "fullscreen" if fullscreen is True else "foreground_unknown")
        helper = expected.parent / HELPER_RELATIVE
        self._updating = True
        try:
            if self._api is None:
                self._api = self._factory()
            self._api.verify_process(expected, self._pid)
            with self._api.verified_helper(helper, HELPER_SHA256):
                # Preflight can be reentered by a caller-owned shutdown.
                if self._closed:
                    return self.status()
                self._attempted = self._terminal = True
                result = self._api.launch(helper, self._pid)
                if self._closed:
                    return self.status()
                error = result.get("error", 0)
                return self._set("launched" if result.get("launched") else
                                 "cancelled" if error == 1223 else "failed",
                                 "awaiting_sensor" if result.get("launched") else "elevation", error)
        except (OSError, ValueError, RuntimeError) as error:
            self._terminal = True
            if not self._closed:
                return self._set("failed", "verification" if not self._attempted else "launch",
                                 getattr(error, "winerror", None) or getattr(error, "errno", None) or 0)
            return self.status()
        finally:
            self._updating = False
            if self._closed and self._api is not None:
                self._api.close()

    def close(self):
        self._closed = True
        if self._api is not None and not self._updating:
            self._api.close()
        self._set("closed")


def foreground_fullscreen(manager=None, *, api_factory=None):
    """Use existing observations first, otherwise one read-only foreground query.

    No hooks, window enumeration, timer or process-name query is installed.
    Unknown native state deliberately defers the consent dialog.
    """
    try:
        observed = False
        if manager is not None:
            if manager._fullscreen_active():
                return True
            guard = getattr(manager, "_fullscreen_guard", None)
            if guard is not None:
                manager._read_foreground_visibility()
                if (getattr(manager, "_fullscreen_guard_error", None)
                        or getattr(guard, "failure", None) or not getattr(guard, "_known", False)):
                    return None
                if getattr(manager, "_foreground_hidden_screens", ()):
                    return True
                observed = True
        from fullscreen_guard import _NativeApi as ForegroundApi, _covers, _rect
        api = (api_factory or ForegroundApi)()
        hwnd = api.foreground()
        state = api.window(hwnd) if hwnd else None
        if state is None:
            return None
        if state.desktop:
            return False
        if not state.visible or state.minimized or state.cloaked:
            return None
        if state.own_process:
            return False if observed else None
        return _covers(_rect(state.rect), _rect(state.monitor_rect))
    except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
        return None


class _ShellExecuteInfo(c.Structure):
    _fields_ = [("cbSize", c.c_uint32), ("fMask", c.c_uint32), ("hwnd", c.c_void_p),
                ("lpVerb", c.c_wchar_p), ("lpFile", c.c_wchar_p),
                ("lpParameters", c.c_wchar_p), ("lpDirectory", c.c_wchar_p),
                ("nShow", c.c_int32), ("hInstApp", c.c_void_p), ("lpIDList", c.c_void_p),
                ("lpClass", c.c_wchar_p), ("hkeyClass", c.c_void_p),
                ("dwHotKey", c.c_uint32), ("hIcon", c.c_void_p), ("hProcess", c.c_void_p)]


class _NativeApi:
    """Lazy Win32 calls; a locked, hashed helper stays fixed through consent."""
    def __init__(self, *, loader=None, last_error=None):
        loader = loader or c.WinDLL
        self._error = last_error or c.get_last_error
        self.kernel = loader("kernel32", use_last_error=True)
        self.shell = loader("shell32", use_last_error=True)
        self.ole = loader("ole32", use_last_error=True)
        p, d, b = c.c_void_p, c.c_uint32, c.c_int32
        for lib, name, result, args in (
            (self.kernel, "GetCurrentProcessId", d, []),
            (self.kernel, "GetModuleFileNameW", d, [p, c.c_wchar_p, d]),
            (self.kernel, "CreateFileW", p, [c.c_wchar_p, d, d, p, d, d, p]),
            (self.kernel, "GetFinalPathNameByHandleW", d, [p, c.c_wchar_p, d, d]),
            (self.kernel, "ReadFile", b, [p, p, d, c.POINTER(d), p]),
            (self.kernel, "CloseHandle", b, [p]),
            (self.shell, "ShellExecuteExW", b, [c.POINTER(_ShellExecuteInfo)]),
            (self.ole, "CoInitializeEx", c.c_int32, [p, d]),
            (self.ole, "CoUninitialize", None, []),
        ):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
        self._handles = set()

    def _close(self, handle):
        if self.kernel.CloseHandle(handle):
            self._handles.discard(handle)
        else:
            raise c.WinError(self._error())

    def verify_process(self, expected, pid):
        value = c.create_unicode_buffer(32768)
        size = self.kernel.GetModuleFileNameW(None, value, len(value))
        if (not 0 < size < len(value) or self.kernel.GetCurrentProcessId() != pid
                or not _same_path(value.value, expected)):
            raise ValueError("Current installed process identity is invalid")
        _plain_path(expected)

    @contextmanager
    def verified_helper(self, path, expected_digest):
        _plain_path(path)
        # Deny write/delete sharing until ShellExecuteEx has completed. No
        # mutable helper arguments or externally configured executable exist.
        handle = self.kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
        if handle in (None, 0, c.c_void_p(-1).value):
            raise c.WinError(self._error())
        self._handles.add(handle)
        try:
            final = c.create_unicode_buffer(32768)
            size = self.kernel.GetFinalPathNameByHandleW(handle, final, len(final), 0)
            if not 0 < size < len(final) or not _same_path(final.value.removeprefix("\\\\?\\"), path):
                raise ValueError("Helper file identity is invalid")
            digest, buffer, total = hashlib.sha256(), c.create_string_buffer(65536), 0
            while True:
                count = c.c_uint32()
                if not self.kernel.ReadFile(handle, buffer, len(buffer), c.byref(count), None):
                    raise c.WinError(self._error())
                if not count.value:
                    break
                total += count.value
                if total > 1024 * 1024:
                    raise ValueError("Unexpected helper size")
                digest.update(buffer.raw[:count.value])
            if digest.hexdigest() != expected_digest:
                raise ValueError("Helper digest is invalid")
            yield
        finally:
            self._close(handle)

    def launch(self, helper, pid):
        result = self.ole.CoInitializeEx(None, 6)  # STA | DISABLE_OLE1DDE
        if result < 0:
            raise OSError("Shell COM apartment is unavailable")
        info = _ShellExecuteInfo()
        info.cbSize, info.fMask = c.sizeof(info), 0x40 | 0x100 | 0x400
        info.lpVerb, info.lpFile = "runas", str(helper)
        info.lpParameters, info.lpDirectory, info.nShow = "--app-pid " + str(pid), str(helper.parent), 0
        try:
            launched = bool(self.shell.ShellExecuteExW(c.byref(info)))
            error = 0 if launched else self._error()
            return dict(launched=launched, error=error)
        finally:
            try:
                if info.hProcess:
                    self._handles.add(info.hProcess)
                    self._close(info.hProcess)
            finally:
                self.ole.CoUninitialize()

    def close(self):
        for handle in tuple(self._handles):
            self._close(handle)


def _plain_path(path):
    if not path.is_file() or not _same_path(path.resolve(strict=True), path):
        raise ValueError("Installed file path is invalid")
    for item in (path, *path.parents):
        if getattr(item.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Reparse paths are not accepted")
