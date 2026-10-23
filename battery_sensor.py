"""Read the Windows aggregate battery state without PowerShell or administrator rights."""

import ctypes as c
import time

BATTERY_API = "CallNtPowerInformation(SystemBatteryState)"
BATTERY_RETRY_SECONDS = 60.0


class SystemBatteryState(c.Structure):
    _fields_ = [
        ("online", c.c_ubyte),
        ("present", c.c_ubyte),
        ("charging", c.c_ubyte),
        ("discharging", c.c_ubyte),
        ("spare", c.c_ubyte * 3),
        ("tag", c.c_ubyte),
        ("capacity", c.c_uint32),
        ("remaining", c.c_uint32),
        ("rate", c.c_uint32),
        ("estimated_time", c.c_uint32),
        ("alert1", c.c_uint32),
        ("alert2", c.c_uint32),
    ]


def decode(state):
    rate = c.c_int32(state.rate).value
    watts = None if not state.present or state.rate == 0x80000000 else abs(rate) / 1000
    # Direction is part of the measurement, not inferred from AC being plugged in.
    charge = discharge = None
    if watts is not None:
        if watts == 0:
            charge = discharge = 0.0
        elif state.charging and not state.discharging:
            charge, discharge = watts, 0.0
        elif state.discharging and not state.charging:
            charge, discharge = 0.0, watts
    remaining = state.remaining
    seconds = state.estimated_time
    return dict(
        battery_present=bool(state.present),
        power_online=bool(state.online),
        charging=bool(state.charging),
        discharging=bool(state.discharging),
        battery_watts=watts,
        battery_charge_watts=charge,
        battery_discharge_watts=discharge,
        battery_remaining_wh=remaining / 1000
        if state.present and 0 <= remaining < 0x80000000
        else None,
        battery_time_minutes=seconds / 60
        if state.present and not state.charging and 0 < seconds < 0x80000000
        else None,
    )


class Battery:
    def __init__(self):
        # One optional source must not prevent the sampler from starting.
        self.lib = None
        self._retry_at = 0.0
        self._status = dict(api=BATTERY_API, state="idle", ntstatus=None)

    @staticmethod
    def _open():
        lib = c.WinDLL("PowrProf.dll")
        lib.CallNtPowerInformation.argtypes = [
            c.c_int,
            c.c_void_p,
            c.c_uint32,
            c.c_void_p,
            c.c_uint32,
        ]
        lib.CallNtPowerInformation.restype = c.c_int32
        return lib

    def _failure(self, now, api, error=None, ntstatus=None):
        facts = dict(api=api)
        if error is not None:
            facts["reason"] = (
                "entrypoint_missing" if isinstance(error, AttributeError) else "OSError"
            )
            for field in ("errno", "winerror"):
                value = getattr(error, field, None)
                if type(value) is int and -(2**31) <= value < 2**32:
                    facts[field] = value
        if ntstatus is not None:
            facts["ntstatus"] = ntstatus
        self.lib = None
        self._retry_at = now + BATTERY_RETRY_SECONDS
        self._status = dict(api=api, state="query_failed", ntstatus=ntstatus, error=facts)
        return dict(battery_status=dict(self._status, retry_in_seconds=BATTERY_RETRY_SECONDS))

    def read(self):
        now = time.monotonic()
        if now < self._retry_at:
            return dict(
                battery_status=dict(
                    self._status, state="waiting_retry", retry_in_seconds=self._retry_at - now
                )
            )
        state = SystemBatteryState()
        api = "LoadLibraryW(PowrProf.dll)" if self.lib is None else BATTERY_API
        try:
            if self.lib is None:
                try:
                    self.lib = self._open()
                except AttributeError as error:
                    return self._failure(now, BATTERY_API, error)
            api = BATTERY_API
            status = int(
                self.lib.CallNtPowerInformation(5, None, 0, c.byref(state), c.sizeof(state))
            )
        except OSError as error:
            return self._failure(now, api, error)
        if status != 0:
            return self._failure(now, BATTERY_API, ntstatus=status)
        self._status = dict(
            api=BATTERY_API, state="ready" if state.present else "no_battery", ntstatus=0
        )
        result = decode(state)
        result["battery_status"] = dict(self._status, retry_in_seconds=0.0)
        return result


def power_state(data):
    """UI state: retain raw firmware flags, but don't label AC + zero watts as flow."""
    if not data.get("battery_present"):
        return 3
    if data.get("power_online") and data.get("battery_watts") == 0:
        return 0
    if data.get("charging"):
        return 1
    if data.get("discharging"):
        return 2
    return 0 if data.get("power_online") else 3
