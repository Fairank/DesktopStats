"""Lazy, bounded Shell process identity; no polling or window-content access.

TaskbarCreated also occurs on same-process primary-display DPI changes. Callers
may invalidate old observations only when two known (PID, creation FILETIME)
identities differ. Unknown never means a new Shell.
"""

import ctypes as c
import sys


class _FileTime(c.Structure):
    _fields_ = [("low", c.c_uint32), ("high", c.c_uint32)]


class _CtypesShellAPI:
    def __init__(self):
        user = c.WinDLL("user32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        self._shell = user.GetShellWindow
        self._shell.argtypes, self._shell.restype = [], c.c_void_p
        self._owner = user.GetWindowThreadProcessId
        self._owner.argtypes, self._owner.restype = [c.c_void_p, c.POINTER(c.c_uint32)], c.c_uint32
        self._open = kernel.OpenProcess
        self._open.argtypes, self._open.restype = [c.c_uint32, c.c_int32, c.c_uint32], c.c_void_p
        self._times = kernel.GetProcessTimes
        self._times.argtypes = [c.c_void_p, *([c.POINTER(_FileTime)] * 4)]
        self._times.restype = c.c_int32
        self._close = kernel.CloseHandle
        self._close.argtypes, self._close.restype = [c.c_void_p], c.c_int32

    def shell_window(self):
        return int(self._shell() or 0)

    def owner_pid(self, window):
        pid = c.c_uint32()
        return pid.value if self._owner(window, c.byref(pid)) else 0

    def open_process(self, pid):
        return int(self._open(0x1000, False, pid) or 0)  # PROCESS_QUERY_LIMITED_INFORMATION

    def creation_time(self, handle):
        created, exited, kernel, user = (_FileTime() for _ in range(4))
        if not self._times(handle, c.byref(created), c.byref(exited), c.byref(kernel), c.byref(user)):
            return None
        return (created.high << 32) | created.low

    def close_handle(self, handle):
        return bool(self._close(handle))


class ShellIdentityReader:
    """read() -> (pid, creation FILETIME) or None; constructor loads no DLL.

    The optional API is a pure-test boundary. Every read obtains fresh metadata,
    rechecks the Shell window/PID and closes its one limited-query handle.
    """

    def __init__(self, api=None):
        self._api = api

    def read(self):
        handle, result = None, None
        try:
            if self._api is None:
                if sys.platform != "win32":
                    return None
                self._api = _CtypesShellAPI()
            api = self._api
            window = api.shell_window()
            if type(window) is not int or window <= 0:
                return None
            pid = api.owner_pid(window)
            if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
                return None
            handle = api.open_process(pid)
            if type(handle) is not int or handle <= 0:
                handle = None
                return None
            created = api.creation_time(handle)
            if (type(created) is int and 0 < created <= 0xFFFFFFFFFFFFFFFF
                    and api.shell_window() == window and api.owner_pid(window) == pid):
                result = pid, created
        except (OSError, RuntimeError, ValueError, TypeError, OverflowError, AttributeError):
            result = None
        finally:
            if handle is not None:
                try:
                    if self._api.close_handle(handle) is not True:
                        result = None
                except (OSError, RuntimeError, ValueError, TypeError, OverflowError, AttributeError):
                    result = None
        return result
