"""Demand-only NVIDIA card tachometer, with no polling thread or fan controls.

NvAPI_GPU_GetTachReading is a physical GPU tachometer reading. It exposes one
card-level channel, not an indexed reading for every physical fan. NVML's
GetFanSpeed/GetFanSpeedRPM describe intended speed and are deliberately unused.
Handles are joined by unique PCI bus/device, never by enumeration position.
NvAPI does not expose a PCI domain here, so nonzero domains are not guessed.

ClientFanCoolersGetStatus is an optional PRIVATE driver interface. Its v1 ABI
and CurrentRpm interpretation follow LibreHardwareMonitor v0.9.6's NvApi.cs
and NvidiaGpu.cs, not an NVIDIA public stability guarantee or an independent
physical measurement. Cooler IDs identify driver channels, not front-view fans.
https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/v0.9.6/LibreHardwareMonitorLib/Interop/NvApi.cs
https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/v0.9.6/LibreHardwareMonitorLib/Hardware/Gpu/NvidiaGpu.cs

Official contracts and QueryInterface IDs:
https://docs.nvidia.com/nvapi/group__gpucooler.html
https://docs.nvidia.com/nvapi/group__gpu.html
https://github.com/NVIDIA/nvapi/blob/main/nvapi_interface.h
https://github.com/NVIDIA/nvapi/blob/main/nvapi_lite_common.h
"""

import copy
import ctypes as c
from itertools import count
import os
import time
from pathlib import Path

SOURCE = "NVIDIA NvAPI tachometer"
API = "NvAPI_GPU_GetTachReading"
CURRENT_API = "NvAPI_GPU_ClientFanCoolersGetStatus"
CURRENT_SOURCE = "NVIDIA driver current fan RPM"
INTERVAL = 1.0
RETRY_SECONDS = 5.0
MAX_GPUS = 64  # NVAPI_MAX_PHYSICAL_GPUS; EnumPhysicalGPUs requires this array.
MAX_CACHE = 16  # Same bound as the existing NVML device enumeration.
MAX_FAN_CHANNELS = 8
NOT_SUPPORTED = frozenset((-3, -104))
HANDLE_INVALIDATED = -10
# Process-local logical generations, not a hardware identifier or persisted ID.
# Each joined device slot gets a distinct epoch. A retired/replaced owner or
# invalidated handle can never reuse its old (epoch, sequence) capture identity.
_CAPTURE_EPOCHS = count(1)


class FanCoolerStatusItem(c.Structure):
    _pack_ = 8
    _fields_ = [("cooler_id", c.c_uint32), ("current_rpm", c.c_uint32),
                ("current_min_level", c.c_uint32), ("current_max_level", c.c_uint32),
                ("current_level", c.c_uint32), ("reserved", c.c_uint32 * 8)]


class FanCoolersStatus(c.Structure):
    _pack_ = 8
    _fields_ = [("version", c.c_uint32), ("count", c.c_uint32),
                ("reserved", c.c_uint64 * 4), ("items", FanCoolerStatusItem * 32)]


class NvapiError(RuntimeError):
    def __init__(self, api, code):
        self.api, self.code = api, int(code)
        super().__init__(api + " returned " + str(self.code))


class InvalidFanData(ValueError):
    api = CURRENT_API


class _Nvapi:
    """Small read-only entrypoint whitelist; construction occurs only on demand."""
    def __init__(self):
        name = "nvapi64.dll" if c.sizeof(c.c_void_p) == 8 else "nvapi.dll"
        self.lib = c.CDLL(str(Path(os.environ["WINDIR"]) / "System32" / name))
        query = self.lib.nvapi_QueryInterface
        query.argtypes, query.restype = [c.c_uint32], c.c_void_p
        self._functions = {}
        uint_pointer = c.POINTER(c.c_uint32)
        for api, code, arguments in (
            ("NvAPI_Initialize", 0x0150E828, ()),
            ("NvAPI_Unload", 0xD22BDD7E, ()),
            ("NvAPI_EnumPhysicalGPUs", 0xE5AC921F, (c.POINTER(c.c_void_p), uint_pointer)),
            ("NvAPI_GPU_GetBusId", 0x1BE0B8E5, (c.c_void_p, uint_pointer)),
            ("NvAPI_GPU_GetBusSlotId", 0x2A0A350F, (c.c_void_p, uint_pointer)),
            (API, 0x5F608315, (c.c_void_p, uint_pointer)),
            (CURRENT_API, 0x35AED5E8, (c.c_void_p, c.POINTER(FanCoolersStatus))),
        ):
            address = query(code)
            if not address:
                if api in (API, CURRENT_API):
                    continue
                raise AttributeError(api)
            self._functions[api] = c.CFUNCTYPE(c.c_int, *arguments)(address)
        if not any(api in self._functions for api in (API, CURRENT_API)):
            raise AttributeError("NVIDIA fan RPM entrypoints")
        self._coolers_unavailable = set()
        self._initialized = False
        self._call("NvAPI_Initialize")
        self._initialized = True

    def _call(self, api, *args):
        function = self._functions.get(api)
        if function is None:
            raise AttributeError(api)
        code = int(function(*args))
        if code:
            raise NvapiError(api, code)

    def devices(self):
        getattr(self, "_coolers_unavailable", set()).clear()
        handles, count = (c.c_void_p * MAX_GPUS)(), c.c_uint32()
        self._call("NvAPI_EnumPhysicalGPUs", handles, c.byref(count))
        if not 0 <= count.value <= MAX_GPUS:
            raise ValueError("Invalid physical GPU count")
        result = {}
        for handle in handles[:count.value]:
            if not handle:
                raise ValueError("Null physical GPU handle")
            bus, device = c.c_uint32(), c.c_uint32()
            self._call("NvAPI_GPU_GetBusId", handle, c.byref(bus))
            self._call("NvAPI_GPU_GetBusSlotId", handle, c.byref(device))
            if not (bus.value <= 255 and device.value <= 31):
                raise ValueError("Invalid PCI address")
            # A duplicate address is ambiguous, including multiple PCI domains.
            key = (bus.value, device.value)
            result[key] = None if key in result else handle
        return result

    def rpm(self, handle):
        value = c.c_uint32()
        self._call(API, handle, c.byref(value))
        return value.value

    def reading(self, handle):
        """One grouped current-RPM query; fallback capability is cached per GPU."""
        if CURRENT_API in self._functions and handle not in self._coolers_unavailable:
            status = FanCoolersStatus()
            status.version = c.sizeof(FanCoolersStatus) | (1 << 16)
            try:
                self._call(CURRENT_API, handle, c.byref(status))
            except NvapiError as error:
                if error.code not in NOT_SUPPORTED | {-9}:  # Unsupported v1 ABI.
                    raise
                self._coolers_unavailable.add(handle)
            else:
                if status.count > MAX_FAN_CHANNELS:
                    raise InvalidFanData("Invalid fan channel count")
                if status.count:
                    fans, ids = [], set()
                    for index, item in enumerate(status.items[:status.count]):
                        if item.cooler_id in ids:
                            raise InvalidFanData("Ambiguous cooler IDs")
                        ids.add(item.cooler_id)
                        valid = item.current_rpm != 0xFFFFFFFF
                        fans.append(dict(index=index, cooler_id=item.cooler_id,
                                         rpm=item.current_rpm if valid else None,
                                         state="available" if valid else "invalid_value"))
                    values = [row["rpm"] for row in fans if row["rpm"] is not None]
                    if not values:
                        raise InvalidFanData("No valid current fan RPM channel")
                    return dict(rpm=sum(values) / len(values), fans=fans,
                                api=CURRENT_API, source=CURRENT_SOURCE,
                                semantics="driver_current_rpm", private_api=True,
                                state="available" if len(values) == len(fans) else "partial",
                                aggregate="mean_valid_cooler_channels")
                self._coolers_unavailable.add(handle)
        return dict(rpm=self.rpm(handle), fans=[], api=API, source=SOURCE,
                    semantics="measured", private_api=False, state="available")

    def close(self):
        if self._initialized:
            self._call("NvAPI_Unload")
            self._initialized = False


class Tachometer:
    def __init__(self, backend_factory=None):
        self._factory = backend_factory or _Nvapi
        self._backend = None
        self._devices = None
        self._setup_error = None
        self._setup_retry = 0.0
        self._cache = {}
        self._capture_state = {}
        self._closed = False

    @staticmethod
    def _result(state, *, code=None, api=API, reason="", rpm=None, source=SOURCE,
                semantics="measured", fans=None, private_api=False, aggregate=""):
        status = dict(state=state, api=api, status_code=code, unit="RPM",
                      source=source, semantics=semantics, scope="card", private_api=private_api,
                      timestamp=time.time(), capture_monotonic=None,
                      capture_sequence=None, provider_epoch=None)
        if reason:
            status["reason"] = reason
        if aggregate:
            status["aggregate"] = aggregate
        rows = [dict(row, source=source, semantics=semantics, timestamp=status["timestamp"],
                     scope="cooler_channel") for row in fans or ()]
        return dict(rpm=rpm, status=status, fans=rows)

    def _capture_result(self, result, identity=None, *, completed_at=None, successful=False):
        """Attach existing-query completion, never refresh a cached sample.

        Device identities are already provided by the existing unique PCI join;
        they are not exported. Current private-API cooler IDs keep their driver
        channel semantics and do not become physical/front-view fan identities.
        """
        previous = self._capture_state.get(identity)
        epoch = previous[0] if previous is not None else None
        sequence = None
        if successful:
            epoch, old_sequence = previous if previous is not None else (next(_CAPTURE_EPOCHS), 0)
            sequence = old_sequence + 1
            self._capture_state[identity] = (epoch, sequence)
        status = result["status"]
        status.update(capture_monotonic=completed_at if successful else None,
                      capture_sequence=sequence, provider_epoch=epoch)
        for row in result.get("fans", ()):
            row.update(capture_monotonic=status["capture_monotonic"],
                       capture_sequence=sequence, provider_epoch=epoch)
        return result

    @classmethod
    def _failure(cls, error):
        if isinstance(error, AttributeError):
            return cls._result("entrypoint_missing"), float("inf")
        if isinstance(error, NvapiError):
            permanent = error.code in NOT_SUPPORTED
            return cls._result("unsupported" if permanent else "query_failed",
                               code=error.code, api=error.api,
                               **(dict(source=CURRENT_SOURCE, semantics="driver_current_rpm", private_api=True)
                                  if error.api == CURRENT_API else {})), (
                                   float("inf") if permanent else RETRY_SECONDS)
        if isinstance(error, InvalidFanData):
            return cls._result("invalid_value", api=CURRENT_API, source=CURRENT_SOURCE,
                               semantics="driver_current_rpm", private_api=True), RETRY_SECONDS
        # Do not expose incidental native exception text or paths.
        return cls._result("query_failed"), RETRY_SECONDS

    def invalidate(self):
        """An actual NVML handle change invalidates the native identity join."""
        self._devices = None
        self._cache.clear()
        self._capture_state.clear()
        self._setup_error, self._setup_retry = None, 0.0

    def read(self, identity):
        if self._closed:
            return self._capture_result(self._result("closed"))
        if (not isinstance(identity, tuple) or len(identity) != 3
                or any(type(part) is not int for part in identity)
                or identity[0] != 0 or not 0 <= identity[1] <= 255
                or not 0 <= identity[2] <= 31):
            return self._capture_result(self._result("identity_unavailable"))
        now = time.monotonic()
        cached = self._cache.get(identity)
        if cached is not None and now < cached[0]:
            return copy.deepcopy(cached[1])
        if self._setup_error is not None and now < self._setup_retry:
            return self._capture_result(copy.deepcopy(self._setup_error), identity)
        if self._devices is None:
            try:
                if self._backend is None:
                    try:
                        self._backend = self._factory()
                    except OSError:
                        # A missing optional driver DLL is stable for this owner.
                        self._setup_error = self._result("dll_unavailable")
                        self._setup_retry = float("inf")
                        return self._capture_result(copy.deepcopy(self._setup_error), identity)
                self._devices = self._backend.devices()
            except (NvapiError, OSError, AttributeError, RuntimeError, ValueError) as error:
                self._setup_error, delay = self._failure(error)
                self._setup_retry = time.monotonic() + delay
                return self._capture_result(copy.deepcopy(self._setup_error), identity)
            self._setup_error, self._setup_retry = None, 0.0
        handle = self._devices.get(identity[1:])
        successful_capture = False
        if handle is None:
            result = self._result("identity_unavailable", reason="no_unique_pci_match")
            delay = float("inf")
        else:
            try:
                grouped_read = getattr(self._backend, "reading", None)
                facts = dict(grouped_read(handle)) if callable(grouped_read) else dict(rpm=self._backend.rpm(handle))
                value = facts.pop("rpm")
                # Preserve true zero. UINT_MAX is not a valid tachometer value.
                if type(value) not in (int, float) or not 0 <= value < 0xFFFFFFFF:
                    raise ValueError("Invalid tachometer reading")
                result = self._result(facts.pop("state", "available"), rpm=value, code=0, **facts)
                successful_capture = result["status"]["state"] == "available"
                delay = INTERVAL
            except (NvapiError, OSError, AttributeError, RuntimeError, ValueError) as error:
                result, delay = self._failure(error)
                if isinstance(error, NvapiError) and error.code == HANDLE_INVALIDATED:
                    # Official NvAPI contract: discard all handles and re-enumerate.
                    self.invalidate()
                    self._setup_error, self._setup_retry = result, time.monotonic() + RETRY_SECONDS
        if len(self._cache) >= MAX_CACHE and identity not in self._cache:
            retired = next(iter(self._cache))
            self._cache.pop(retired)
            self._capture_state.pop(retired, None)
        # Reuse the existing cache-completion clock read, not another poll or
        # clock query. It occurs after the actual driver reply and validation.
        completed_at = time.monotonic()
        result = self._capture_result(result, identity, completed_at=completed_at,
                                      successful=successful_capture)
        self._cache[identity] = (completed_at + delay, result)
        return copy.deepcopy(result)

    def close(self):
        self._closed = True
        self._cache.clear()
        self._capture_state.clear()
        self._devices = None
        if self._backend is not None:
            self._backend.close()
            self._backend = None
