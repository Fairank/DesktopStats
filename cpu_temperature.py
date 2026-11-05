"""Read the fixed ASUS CPU channel from an explicitly launched local bridge.

The ordinary app never activates privileged COM, requests elevation or starts a
helper. It reads 64 bytes of shared memory, at most once per two seconds. The
bridge retains one service connection and a verified CPU index, obtains a new
sensor view on each read, and stops with its bound application process.
This is the ASUS CPU channel, not a claim about a package/core temperature.

The raw tenths-Celsius convention for sensor 0x06030012 is also documented by
the original client implementation at:
https://github.com/fjorge9-arch/gmk104-aura/blob/6809c252a14abf656874d443d5b10979a196d2f9/python/gmk104aura/cpu_temp.py
No third-party implementation code is copied here.
"""

import ctypes as c
import math
import os
import struct
import time
from ctypes import wintypes as w

SOURCE = "ASUS COM · CPU"
API = "ASUS CPU shared memory"
MAGIC = 0x54435344
SENSOR_ID = 0x06030012
SIZE = 64
INTERVAL = 2.0
FRESH_SECONDS = 8.0


def is_requested(config):
    bar = config.get("top_bar", {})
    if bar.get("enabled") and any(
        item["metric"] == "cpu_temp" or "cpu_temp" in item.get("prefs", {}).get("metrics", [])
        for item in bar.get("items", [])
    ):
        return True
    if not config.get("visible", True):
        return False
    for key, prefs in config.get("widgets", {}).items():
        if not prefs.get("enabled"):
            continue
        content = prefs.get("content")
        if content:
            if "cpu_temp" in content:
                return True
        elif prefs.get("kind", key) == "cpu" and (
            prefs.get("primary") == "temp" or prefs.get("secondary") == "temp"
        ):
            return True
    return False


def _current_sid(kernel):
    security = c.WinDLL("advapi32.dll", use_last_error=True)
    security.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
    security.OpenProcessToken.restype = w.BOOL
    security.GetTokenInformation.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
    security.GetTokenInformation.restype = w.BOOL
    security.ConvertSidToStringSidW.argtypes = [c.c_void_p, c.POINTER(w.LPWSTR)]
    security.ConvertSidToStringSidW.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    token, length, text = w.HANDLE(), w.DWORD(), w.LPWSTR()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)):
        raise c.WinError(c.get_last_error())
    try:
        security.GetTokenInformation(token, 1, None, 0, c.byref(length))
        if not 0 < length.value <= 4096:
            raise OSError("Invalid token information length")
        buffer = c.create_string_buffer(length.value)
        if not security.GetTokenInformation(token, 1, buffer, length, c.byref(length)):
            raise c.WinError(c.get_last_error())
        sid = c.cast(buffer, c.POINTER(c.c_void_p)).contents.value
        if not security.ConvertSidToStringSidW(sid, c.byref(text)):
            raise c.WinError(c.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(c.cast(text, c.c_void_p))
    finally:
        kernel.CloseHandle(token)


class _Mapping:
    def __init__(self, app_pid):
        self.kernel = c.WinDLL("kernel32.dll", use_last_error=True)
        self.kernel.OpenFileMappingW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
        self.kernel.OpenFileMappingW.restype = w.HANDLE
        self.kernel.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]
        self.kernel.MapViewOfFile.restype = c.c_void_p
        self.kernel.UnmapViewOfFile.argtypes = [c.c_void_p]
        self.kernel.UnmapViewOfFile.restype = w.BOOL
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.kernel.CloseHandle.restype = w.BOOL
        self.name = "Local\\DesktopStats.CpuTemperature." + _current_sid(self.kernel) + "." + str(app_pid)
        self.handle = self.view = None

    def read(self):
        if self.view is None:
            self.handle = self.kernel.OpenFileMappingW(4, False, self.name)  # FILE_MAP_READ only.
            if not self.handle:
                raise c.WinError(c.get_last_error())
            self.view = self.kernel.MapViewOfFile(self.handle, 4, 0, 0, SIZE)
            if not self.view:
                error = c.get_last_error()
                self.close()
                raise c.WinError(error)
        for _ in range(3):
            first = c.string_at(self.view, SIZE)
            second = c.string_at(self.view, SIZE)
            sequence = struct.unpack_from("<I", first, 8)[0]
            if sequence % 2 == 0 and first == second:
                return first
        raise ValueError("Shared temperature snapshot is being written")

    def close(self):
        if self.view:
            self.kernel.UnmapViewOfFile(self.view)
        if self.handle:
            self.kernel.CloseHandle(self.handle)
        self.view = self.handle = None


class AsusCpuTemperature:
    def __init__(self, *, api=None, app_pid=None, clock=None, wall_clock=None, enabled=None):
        self.app_pid = os.getpid() if app_pid is None else app_pid
        self._api = api
        self._clock = clock or time.monotonic
        self._wall = wall_clock or time.time
        self._enabled = (os.environ.get("DESKTOP_STATS_CPU_BRIDGE_DISABLED") != "1"
                         if enabled is None else bool(enabled))
        self._next = 0.0
        self._last_clock = None
        self._cached = {}
        self._sample_time = None
        self._closed = False
        self.state = "idle"
        self.error = {}

    @property
    def sample_time(self):
        return self._sample_time

    def _discard(self):
        self._cached = {}
        self._sample_time = None

    def _release(self):
        if self._api is not None:
            self._api.close()

    def _failure(self, state, error=None):
        self._discard()
        self.state = state
        self.error = error or {}

    def status(self, requested):
        detail = {
            "idle": "仅按需读取已获授权的 CPU 温度桥接。",
            "missing": "CPU 温度桥接尚未运行；程序不会自动请求管理员权限。",
            "ready": "每两秒读取 ASUS CPU 缓存；时间为成功 getter 的观察时间。",
            "stale": "CPU 温度快照已过期或时钟改变，已清除读数。",
            "unavailable": "ASUS CPU 温度接口本轮未提供有效读数。",
            "warming_up": "CPU 温度桥接正在连接已有 ASUS 服务。",
            "closed": "CPU 温度桥接已关闭。",
            "invalid_value": "CPU 温度快照身份、格式或数值无效，已拒绝。",
            "query_failed": "CPU 温度共享内存读取失败；其他采样继续。",
        }.get(self.state, "本轮没有可验证的 CPU 温度。")
        return dict(state=self.state, requested=bool(requested), api=API, detail=detail,
                    error=dict(self.error))

    def read(self, requested=True):
        if self._closed:
            return {}
        if not requested or not self._enabled:
            self._discard()
            self._release()
            self._next = 0
            self.state, self.error = "idle", {}
            return {}
        now, wall = self._clock(), self._wall()
        if self._last_clock is not None and now < self._last_clock:
            self._discard()
            self._next = 0
        self._last_clock = now
        if self._sample_time is not None and not 0 <= wall - self._sample_time <= FRESH_SECONDS:
            self._failure("stale")
            self._release()
            self._next = 0
        if now < self._next:
            return dict(self._cached)
        self._next = now + INTERVAL
        try:
            if self._api is None:
                self._api = _Mapping(self.app_pid)
            payload = self._api.read()
            if type(payload) is not bytes or len(payload) != SIZE:
                raise ValueError("Unexpected temperature snapshot size")
            magic, schema, seq, state, helper_pid, sensor_id, raw, result, timestamp, app_pid = struct.unpack_from(
                "<7IiqI", payload
            )
            if (magic != MAGIC or schema != 1 or seq % 2 or not helper_pid
                    or sensor_id != SENSOR_ID or app_pid != self.app_pid or any(payload[44:])):
                raise ValueError("Unexpected temperature snapshot identity")
            if state != 1:
                self._failure({0: "warming_up", 2: "unavailable", 3: "closed"}.get(state, "invalid_value"),
                              dict(api=API, status_code=result) if result else None)
                if state == 3:
                    self._release()
                return {}
            source_time = timestamp / 1000
            observed_wall = self._wall()  # A writer can publish during the memory read.
            if not math.isfinite(source_time) or not 0 <= observed_wall - source_time <= FRESH_SECONDS:
                self._failure("stale")
                self._release()
                return {}
            if result or not 0 < raw < 1250:
                raise ValueError("Invalid ASUS CPU temperature")
            self._sample_time = source_time
            self.state, self.error = "ready", {}
            self._cached = dict(cpu_temp=raw / 10.0, cpu_temp_source=SOURCE)
        except OSError as error:
            code = getattr(error, "winerror", None)
            facts = dict(api=API, type=type(error).__name__)
            if type(code) is int:
                facts["winerror"] = code
            self._failure("missing" if code == 2 else "query_failed", facts)
            self._release()
            if code != 2:
                self._next = now + 60
        except ValueError:
            self._failure("invalid_value")
            self._release()
        return dict(self._cached)

    def close(self):
        self._closed = True
        self._discard()
        self._release()
        self.state = "closed"
