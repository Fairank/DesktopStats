"""Read the Windows aggregate battery state without PowerShell or administrator rights."""

import ctypes as c


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
        self.lib = c.WinDLL("PowrProf.dll")
        self.lib.CallNtPowerInformation.argtypes = [
            c.c_int,
            c.c_void_p,
            c.c_uint32,
            c.c_void_p,
            c.c_uint32,
        ]
        self.lib.CallNtPowerInformation.restype = c.c_int32

    def read(self):
        state = SystemBatteryState()
        status = self.lib.CallNtPowerInformation(5, None, 0, c.byref(state), c.sizeof(state))
        result = decode(state) if status == 0 else {}
        result["battery_status"] = {"api": "CallNtPowerInformation(SystemBatteryState)", "ntstatus": int(status)}
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
