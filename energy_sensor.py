"""Read one Windows EMI CPU package counter through the native, read-only PDH API.

The Energy Meter ``Power`` counter is expressed in milliwatts. Only the exact
RAPL package-0 channel is used: core channels, ``_Total``, battery discharge and
power limits are not substitutes for package power or whole-system input.
No helper process, administrator privileges or additional driver is required.
Machines without this Windows-provided channel remain unsupported.

References:
https://learn.microsoft.com/windows/win32/api/pdh/nf-pdh-pdhaddenglishcounterw
https://learn.microsoft.com/windows/win32/api/pdh/nf-pdh-pdhgetformattedcountervalue
https://raw.githubusercontent.com/seerge/g-helper/main/app/HardwareControl.cs
"""

import ctypes as c
import math
import time
from ctypes import wintypes as w

COUNTER_PATH = r"\Energy Meter(RAPL_Package0_PKG)\Power"
SOURCE = "Windows Energy Meter · RAPL package 0"


class _FormattedValue(c.Structure):
    _fields_ = [("status", w.DWORD), ("value", c.c_double)]


class _Pdh:
    """Small API wrapper; a query owns its counter and always closes on failure."""

    def __init__(self):
        self.lib = c.WinDLL("pdh.dll")
        handle = c.c_void_p
        self.lib.PdhOpenQueryW.argtypes = [w.LPCWSTR, c.c_size_t, c.POINTER(handle)]
        self.lib.PdhAddEnglishCounterW.argtypes = [
            handle,
            w.LPCWSTR,
            c.c_size_t,
            c.POINTER(handle),
        ]
        self.lib.PdhCollectQueryData.argtypes = [handle]
        self.lib.PdhGetFormattedCounterValue.argtypes = [
            handle,
            w.DWORD,
            c.POINTER(w.DWORD),
            c.POINTER(_FormattedValue),
        ]
        self.lib.PdhCloseQuery.argtypes = [handle]
        for name in (
            "PdhOpenQueryW",
            "PdhAddEnglishCounterW",
            "PdhCollectQueryData",
            "PdhGetFormattedCounterValue",
            "PdhCloseQuery",
        ):
            getattr(self.lib, name).restype = w.LONG

    @staticmethod
    def _check(status):
        if status:
            raise OSError(f"PDH status 0x{status & 0xFFFFFFFF:08x}")

    def open(self):
        query, counter = c.c_void_p(), c.c_void_p()
        self._check(self.lib.PdhOpenQueryW(None, 0, c.byref(query)))
        try:
            self._check(self.lib.PdhAddEnglishCounterW(query, COUNTER_PATH, 0, c.byref(counter)))
        except OSError:
            self.close(query)
            raise
        return query, counter

    def collect(self, query):
        self._check(self.lib.PdhCollectQueryData(query))

    def value(self, counter):
        value = _FormattedValue()
        # PDH_FMT_DOUBLE | PDH_FMT_NOCAP100. Counter values are not percentages.
        self._check(self.lib.PdhGetFormattedCounterValue(counter, 0x8200, None, c.byref(value)))
        if value.status not in (0, 1):  # VALID_DATA / NEW_DATA
            raise OSError(f"PDH sample status 0x{value.status:08x}")
        return value.value

    def close(self, query):
        self.lib.PdhCloseQuery(query)


class CpuPackagePower:
    """Nonblocking double-sampled package power with bounded retries.

    ``read()`` returns a fresh ``cpu_power`` in watts plus its source, or an empty
    dict while warming up, unavailable or closed. A failed counter is retried
    after ``retry_seconds``; a sample interval over 30 seconds starts a new
    baseline so sleep/resume and hidden widgets cannot produce a long average.
    Fast requests may explicitly reuse a successful value for under 50 ms;
    warmup, errors, resets and closure always clear that short-lived cache.
    The object is intended to be owned and called by one sampler thread.
    """

    def __init__(self, *, api=None, clock=None, wall_clock=None, retry_seconds=60):
        self._api = api
        self._clock = clock or time.monotonic
        self._wall_clock = wall_clock or time.time
        self._retry_seconds = max(1.0, float(retry_seconds))
        self._query = self._counter = None
        self._last_sample = None
        self._last_value = None
        self._sample_time = None
        self._retry_at = 0.0
        self._closed = False
        self.state = "warming_up"
        self.last_error = ""

    @property
    def sample_time(self):
        """UTC time of the successful native observation, unchanged by cache hits."""
        return self._sample_time

    def _release(self):
        if self._query is not None:
            try:
                self._api.close(self._query)
            except (OSError, AttributeError):
                pass
        self._query = self._counter = None
        self._last_sample = None
        self._last_value = None
        self._sample_time = None

    def read(self, *, allow_cached=False):
        if self._closed:
            return {}
        now = self._clock()
        if now < self._retry_at:
            return {}
        try:
            if self._api is None:
                self._api = _Pdh()
            if self._query is None:
                self._query, self._counter = self._api.open()
                self._api.collect(self._query)
                self._last_sample = now
                self.state = "warming_up"
                self.last_error = ""
                return {}
            elapsed = now - self._last_sample
            if 0 <= elapsed < 0.05:
                if allow_cached and self.state == "ready" and self._last_value is not None:
                    return dict(self._last_value)
                return {}
            self._api.collect(self._query)
            self._last_sample = now
            if elapsed < 0 or elapsed > 30:
                self.state = "warming_up"
                self._last_value = None
                self._sample_time = None
                return {}
            milliwatts = self._api.value(self._counter)
            if not math.isfinite(milliwatts) or not 0 <= milliwatts <= 2_000_000:
                raise ValueError("Invalid CPU package power sample")
            sample_time = self._wall_clock()
            if (type(sample_time) not in (int, float) or not math.isfinite(sample_time)
                    or sample_time < 0):
                raise ValueError("Invalid CPU package observation time")
            self.state = "ready"
            self.last_error = ""
            self._sample_time = sample_time
            self._last_value = {"cpu_power": milliwatts / 1000, "cpu_power_source": SOURCE}
            return dict(self._last_value)
        except (OSError, AttributeError, ValueError, TypeError) as error:
            self._release()
            self._retry_at = now + self._retry_seconds
            self.state = "unavailable"
            self.last_error = str(error)
            return {}

    def close(self):
        """Release the query once; subsequent reads never reopen it."""
        self._closed = True
        self._release()
        self.state = "closed"
