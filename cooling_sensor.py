"""Read-only ASUS fan status with bounded, successful-value caching.

Only CPU/GPU DSTS endpoints are enabled. These values are measured hundred-RPM
units, not fan duty percentages or target speeds. The shared ATKACPI handle is
owned by AsusTemperature in sensors.py; this helper never opens/closes hardware.

Protocol facts independently checked against upstream Linux asus-wmi.h and
asus-wmi.c, and G-Helper's ASUS endpoint declarations. No GPL implementation is
copied here. Unrecognised hardware/flags/ranges remain unavailable.
"""

import math
import time
from types import MappingProxyType

SOURCE = "ASUS ACPI"
FAN_ENDPOINTS = MappingProxyType({"cpu_fan_rpm": 0x00110013, "gpu_fan_rpm": 0x00110014})
PRESENCE_BIT = 0x00010000
POLL_SECONDS = .5
MAX_RPM = 12_000


def decode_asus_fan(raw):
    """Decode supported DSTS status; stopped (0 RPM) differs from unsupported."""
    if type(raw) is not int or not 0 <= raw <= 0xFFFFFFFF:
        return None
    # Presence, user and BIOS flags are the documented upper DSTS bits. Unknown
    # high bits may encode an error and are not accepted as a plausible speed.
    if not raw & PRESENCE_BIT or raw & ~0x0007FFFF:
        return None
    rpm = (raw & 0xFFFF) * 100
    return rpm if 0 <= rpm <= MAX_RPM else None


class AsusFans:
    """Single-sampler-thread provider; each enabled endpoint is polled <=2 Hz.

    Failed attempts still advance the throttle, but only successful readings
    are cached. Clock reversal, invalid clocks, wall/monotonic divergence and
    long gaps discard cached values. A clock reversal establishes a new throttle
    baseline before any next I/O. close() only invalidates this helper.
    """

    def __init__(self, read_status=None, *, clock=None, wall_clock=None):
        self._read_status = read_status if callable(read_status) else None
        self._clock = clock or time.monotonic
        self._wall_clock = wall_clock or time.time
        self._attempt_at = {}
        self._values = {}
        self._sample_times = {}
        self._last_clock = None
        self._clock_fault = False
        self._closed = False
        self._generation = 0
        self.state = "unavailable"

    @property
    def sample_times(self):
        return dict(self._sample_times)

    def _clear_values(self):
        self._values.clear()
        self._sample_times.clear()
        self._generation += 1

    def _observe_clock(self):
        now, wall = self._clock(), self._wall_clock()
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (now, wall)) or now < 0:
            self._clear_values()
            self._last_clock = None
            self._clock_fault = True
            self.state = "clock_reset"
            return None
        previous = self._last_clock
        self._last_clock = now, wall
        if self._clock_fault or previous is not None and now < previous[0]:
            self._clear_values()
            self._attempt_at = dict.fromkeys(FAN_ENDPOINTS, now)
            self._clock_fault = False
            self.state = "clock_reset"
            return None
        if previous is not None:
            elapsed, wall_elapsed = now - previous[0], wall - previous[1]
            if elapsed > 30 or abs(wall_elapsed - elapsed) > 2:
                # Do not erase valid monotonic throttle timestamps on a wall
                # clock jump; that could otherwise permit an extra rapid I/O.
                self._clear_values()
        return now, wall

    def read(self):
        if self._closed or self._read_status is None:
            return {}
        result = {}
        for key, endpoint in FAN_ENDPOINTS.items():
            generation = self._generation
            clock = self._observe_clock()
            if clock is None:
                return {}
            if self._generation != generation:
                result.clear()
            now, wall = clock
            previous = self._attempt_at.get(key)
            if previous is not None and 0 <= now - previous < POLL_SECONDS:
                if key in self._values:
                    result[key] = self._values[key]
                continue
            self._attempt_at[key] = now
            try:
                rpm = decode_asus_fan(self._read_status(endpoint))
            except (OSError, AttributeError, TypeError, ValueError):
                rpm = None
            if rpm is None:
                self._values.pop(key, None)
                self._sample_times.pop(key, None)
                continue
            self._values[key] = result[key] = rpm
            self._sample_times[key] = wall
        self.state = "ready" if result else "unavailable"
        return result

    def close(self):
        self._closed = True
        self._clear_values()
        self._attempt_at.clear()
        self._last_clock = None
        self.state = "closed"
