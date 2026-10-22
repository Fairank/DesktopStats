"""Low overhead read-only sensors. Unsupported readings remain unavailable."""

import copy
import ctypes as c
import json
import logging
import math
import os
import re
import struct
import time
import winreg
from ctypes import wintypes as w
from pathlib import Path

import psutil

from activity_sensors import Activity
from battery_sensor import Battery, power_state
from cooling_sensor import FAN_ENDPOINTS, MAX_RPM, PRESENCE_BIT, AsusFans
from cooling_sensor import SOURCE as COOLING_SOURCE
from energy_sensor import CpuPackagePower
from external_engine import ExternalEngine
from metrics import METRICS, metric_value, required_sources, variable
from stats_config import BASE, load
from storage_sensor import StorageHealth

INSPECT_UNTIL = 0
EXTERNAL_RESCAN = 0
ASUS_RETRY_SECONDS = 60.0
NVML_RETRY_SECONDS = 5.0


class ProviderApiError(RuntimeError):
    def __init__(self, api, status):
        self.api, self.status_code = api, int(status)
        super().__init__(f"{api} returned status {status}")


def provider_error(error, api):
    """Bounded diagnostic facts, without guessing why an API failed."""
    result = dict(api=getattr(error, "api", api), type=type(error).__name__,
                  message=str(error)[:240])
    for key in ("winerror", "errno", "status_code"):
        value = getattr(error, key, None)
        if type(value) is int:
            result[key] = value
    return result


def hwinfo_watts_unit(values, index):
    """VSB normally embeds its unit in ValueN; UnitN is an optional extension."""
    unit = str(values.get("Unit" + index, "")).strip().lower()
    if unit:
        return unit == "w"
    return (
        re.fullmatch(
            r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:[eE][+-]?\d+)?\s*W",
            str(values.get("Value" + index, "")).strip(),
            re.IGNORECASE,
        )
        is not None
    )


class AsusTemperature:
    def __init__(self):
        self.needs_reconnect = False
        self.last_error = {}
        self.status_errors = {}
        self.channel_status = {}
        self.lib = c.WinDLL("kernel32", use_last_error=True)
        self.lib.CreateFileW.argtypes = [
            w.LPCWSTR,
            w.DWORD,
            w.DWORD,
            c.c_void_p,
            w.DWORD,
            w.DWORD,
            c.c_void_p,
        ]
        self.lib.CreateFileW.restype = w.HANDLE
        self.lib.DeviceIoControl.argtypes = [
            w.HANDLE,
            w.DWORD,
            c.c_void_p,
            w.DWORD,
            c.c_void_p,
            w.DWORD,
            c.POINTER(w.DWORD),
            c.c_void_p,
        ]
        self.lib.DeviceIoControl.restype = w.BOOL
        self.lib.CloseHandle.argtypes = [w.HANDLE]
        self.lib.CloseHandle.restype = w.BOOL
        self.handle = self.lib.CreateFileW(r"\\.\ATKACPI", 0xC0000000, 3, None, 3, 0x80, None)
        if self.handle in (None, 0, w.HANDLE(-1).value):
            code = c.get_last_error()
            self.handle = None
            error = OSError("ASUS sensor unavailable")
            error.api, error.winerror = "CreateFileW", code
            raise error

    def read_status(self, endpoint):
        """Fixed DSTS reads only; never accepts a method or control operation."""
        if type(endpoint) is not int or endpoint not in (0x00120094, *FAN_ENDPOINTS.values()):
            raise ValueError("Unsupported ASUS status endpoint")
        if self.handle is None or self.needs_reconnect:
            return None
        query = struct.pack("<IIII", 0x53545344, 8, endpoint, 0)
        output, count = c.create_string_buffer(16), w.DWORD()
        c.set_last_error(0)
        success = self.lib.DeviceIoControl(
            self.handle, 0x0022240C, query, len(query), output, 16, c.byref(count), None
        )
        error_code = c.get_last_error() if not success else None
        metric = "cpu_temp" if endpoint == 0x00120094 else next(
            key for key, value in FAN_ENDPOINTS.items() if value == endpoint)
        status = dict(api="DeviceIoControl/DSTS", endpoint=f"0x{endpoint:08x}",
                      state="query_failed", raw=None, returned_bytes=count.value,
                      unit="°C" if metric == "cpu_temp" else "RPM", timestamp=time.time())
        self.channel_status[metric] = status
        if success and 4 <= count.value <= 16:
            raw = struct.unpack("<I", output.raw[:4])[0]
            status.update(raw=raw, state="available")
            reason = ""
            if not raw & PRESENCE_BIT:
                reason = "presence_missing"
            elif metric == "cpu_temp":
                if not 0 < raw - 65536 < 125:
                    reason = "temperature_out_of_range"
            elif raw & ~0x0007FFFF:
                reason = "unknown_flags"
            elif (raw & 0xFFFF) * 100 > MAX_RPM:
                reason = "rpm_out_of_range"
            if reason:
                status.update(state="invalid_value", reason=reason)
                self.status_errors[f"0x{endpoint:08x}"] = dict(status)
            else:
                self.status_errors.pop(f"0x{endpoint:08x}", None)
            return raw
        # Unsupported individual status endpoints must not churn an otherwise
        # healthy shared handle. Only explicit handle/device loss requests a
        # bounded reopen; the sampler owns releasing this handle and fan cache.
        if not success:
            code = error_code
            self.last_error = dict(api="DeviceIoControl", winerror=code,
                                   endpoint=f"0x{endpoint:08x}")
            self.status_errors[f"0x{endpoint:08x}"] = dict(self.last_error)
            status.update(winerror=code, reason="ioctl_failed")
            if code in (6, 1167):
                self.needs_reconnect = True
                status["reason"] = "handle_lost"
        else:
            self.status_errors[f"0x{endpoint:08x}"] = dict(
                api="DeviceIoControl", reason="invalid_response_length", returned_bytes=count.value)
            status.update(state="invalid_value", reason="invalid_response_length")
        return None

    def read(self):
        raw = self.read_status(0x00120094)
        if raw is not None:
            temperature = raw - 65536
            if 0 < temperature < 125:
                return dict(cpu_temp=temperature, cpu_temp_source="ASUS ACPI")
        return {}

    def close(self):
        handle, self.handle = self.handle, None
        if handle is not None:
            self.lib.CloseHandle(handle)


class Util(c.Structure):
    _fields_ = [("gpu", c.c_uint), ("memory", c.c_uint)]


class Memory(c.Structure):
    _fields_ = [("total", c.c_ulonglong), ("free", c.c_ulonglong), ("used", c.c_ulonglong)]


class Nvidia:
    def __init__(self):
        self.lib = c.CDLL(str(Path(os.environ["WINDIR"]) / "System32/nvml.dll"))
        self.handle = c.c_void_p()
        self.lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [c.c_uint, c.POINTER(c.c_void_p)]
        status = self.lib.nvmlInit_v2()
        if status:
            raise ProviderApiError("nvmlInit_v2", status)
        status = self.lib.nvmlDeviceGetHandleByIndex_v2(0, c.byref(self.handle))
        if status:
            self.lib.nvmlShutdown()
            raise ProviderApiError("nvmlDeviceGetHandleByIndex_v2", status)
        count = c.c_uint()
        self.handles = {"0": self.handle}
        if self.lib.nvmlDeviceGetCount_v2(c.byref(count)) == 0:
            for index in range(1, min(count.value, 16)):
                handle = c.c_void_p()
                if self.lib.nvmlDeviceGetHandleByIndex_v2(index, c.byref(handle)) == 0:
                    self.handles[str(index)] = handle
        name = c.create_string_buffer(128)
        self.name = "NVIDIA GPU"
        if self.lib.nvmlDeviceGetName(self.handle, name, 128) == 0:
            self.name = name.value.decode("utf-8", errors="replace")

    def read(self):
        devices = {}
        for key, handle in self.handles.items():
            devices[key] = self.read_device(handle)
        first = devices.get("0", {})
        return dict(first, gpus=devices)

    def read_device(self, handle):
        channels = {}
        result = dict(gpu_name=self.name, gpu_source="NVIDIA NVML", channel_status=channels)
        name = c.create_string_buffer(128)
        if self._query(channels, "gpu_name", "nvmlDeviceGetName", (), "", handle, name, 128):
            result["gpu_name"] = name.value.decode("utf-8", errors="replace")
        result["label"] = result["gpu_name"]
        temp, power = c.c_uint(), c.c_uint()
        usage, memory = Util(), Memory()
        if self._query(channels, "gpu_temp", "nvmlDeviceGetTemperature", (0,), "°C",
                       handle, 0, c.byref(temp)):
            result["gpu_temp"] = temp.value
        if self._query(channels, "gpu_usage", "nvmlDeviceGetUtilizationRates", (), "%",
                       handle, c.byref(usage)):
            result["gpu_usage"] = usage.gpu
        if self._query(channels, "gpu_power", "nvmlDeviceGetPowerUsage", (), "W",
                       handle, c.byref(power)):
            result["gpu_power"] = power.value / 1000
        memory_ok = self._query(channels, "vram_gb", "nvmlDeviceGetMemoryInfo", (), "GB",
                                handle, c.byref(memory))
        channels["vram_total_gb"] = dict(channels["vram_gb"])
        channels["vram_percent"] = dict(channels["vram_gb"], unit="%")
        if memory_ok:
            result.update(vram_gb=memory.used / 1024**3, vram_total_gb=memory.total / 1024**3)
            result["vram_percent"] = memory.used / memory.total * 100 if memory.total else None
            if not memory.total:
                channels["vram_percent"].update(state="invalid_value", reason="zero_total_memory")
        for key, function, args in [
            ("gpu_clock", "nvmlDeviceGetClockInfo", (0,)),
            ("gpu_memory_clock", "nvmlDeviceGetClockInfo", (2,)),
            ("gpu_fan_percent", "nvmlDeviceGetFanSpeed", ()),
        ]:
            value = c.c_uint()
            if self._query(channels, key, function, args, "%" if key == "gpu_fan_percent" else "MHz",
                           handle, *args, c.byref(value)):
                result[key] = value.value
        return result

    def _status_text(self, code):
        if code == 0:
            return "Success"
        cache = getattr(self, "_error_strings", None)
        if cache is None:
            cache = self._error_strings = {}
        if code in cache:
            return cache[code]
        if len(cache) >= 32:
            return ""
        text = ""
        try:
            query = getattr(self.lib, "nvmlErrorString", None)
            if query is not None:
                query.argtypes, query.restype = [c.c_int], c.c_char_p
                raw = query(code)
                if isinstance(raw, bytes):
                    text = raw[:640].decode("utf-8", errors="replace")[:160]
                elif isinstance(raw, str):
                    text = raw[:160]
        except Exception:
            # Diagnostic text is optional and cannot invalidate sensor data.
            pass
        cache[code] = text
        return text

    def _query(self, channels, metric, api, arguments, unit, *call_args):
        status = dict(api=api, arguments=list(arguments), unit=unit,
                      state="entrypoint_missing", status_code=None, status_text="", timestamp=time.time())
        channels[metric] = status
        query = getattr(self.lib, api, None)
        if query is None:
            return False
        try:
            code = int(query(*call_args))
        except (OSError, RuntimeError, AttributeError) as error:
            status.update(state="query_failed", error=provider_error(error, api))
            return False
        status.update(state="available" if code == 0 else "query_failed",
                      status_code=code, status_text=self._status_text(code))
        return code == 0
    def close(self):
        self.lib.nvmlShutdown()


class RegistryReadings(dict):
    """Compatible metric mapping with separate, bounded source diagnostics."""
    def __init__(self):
        super().__init__()
        self.diagnostics = dict(state="export_absent", available_count=0, parse_error_count=0,
                                channel_errors=[], exports=[])
        self.sample_times = {}


def hwinfo_number(raw):
    """Only explicit invariant scalars; never guess comma grouping/decimals."""
    if type(raw) not in (int, float, str):
        raise ValueError("invalid_numeric_type")
    if isinstance(raw, str):
        raw = raw.strip()
        if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw):
            raise ValueError("invalid_numeric_format")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("nonfinite_number")
    return value


def hwinfo_registry(cache=None):
    result = RegistryReadings()
    diagnostics = result.diagnostics
    for hive_name, hive in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        export = dict(hive=hive_name, state="query_failed", updated_at=None)
        diagnostics["exports"].append(export)
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\HWiNFO64\VSB") as key:
                count, values, modified = winreg.QueryInfoKey(key)
                if type(modified) not in (int, float) or not math.isfinite(modified):
                    export["state"] = "invalid_timestamp"
                    continue
                updated = modified / 1e7 - 11644473600
                export["updated_at"] = updated
                age = time.time() - updated
                if updated < 0 or not math.isfinite(age):
                    export["state"] = "invalid_timestamp"
                    continue
                # A 1 ms tolerance only covers FILETIME/float rounding; a future
                # export is not allowed to stay fresh after a clock correction.
                if age < -0.001:
                    export["state"] = "future_timestamp"
                    continue
                if age > 30:
                    export["state"] = "stale"
                    continue
                signature = (count, values, modified)
                cached = cache.get(hive_name) if isinstance(cache, dict) else None
                if cached is not None and cached["signature"] == signature:
                    # Recheck access and FILETIME freshness on every call. Only
                    # unchanged, completely parsed exports can reuse their data.
                    result.update(cached["readings"])
                    result.sample_times.update(dict.fromkeys(cached["readings"], updated))
                    export.update(cached["export"])
                    diagnostics["parse_error_count"] += cached["parse_error_count"]
                    diagnostics["channel_errors"].extend(copy.deepcopy(
                        cached["channel_errors"][:32 - len(diagnostics["channel_errors"])]))
                    continue
                export["state"] = "no_supported_channels"
                vals = {}
                for i in range(values):
                    name, value, _ = winreg.EnumValue(key, i)
                    vals[name] = value
                if winreg.QueryInfoKey(key) != signature:
                    export.update(state="query_failed", error=dict(
                        api="HWiNFO VSB registry query", reason="export_changed_during_read"))
                    if isinstance(cache, dict):
                        cache.pop(hive_name, None)
                    continue
                export_available = 0
                export_parse_errors = 0
                hive_readings = {}
                hive_errors = []
                for name, value in vals.items():
                    if not name.startswith("Label"):
                        continue
                    idx = name[5:]
                    label = str(value).lower()
                    sensor = str(vals.get("Sensor" + idx, "")).lower()
                    try:
                        raw = hwinfo_number(vals.get("ValueRaw" + idx))
                    except (ValueError, TypeError, OverflowError) as error:
                        diagnostics["parse_error_count"] += 1
                        export_parse_errors += 1
                        if len(hive_errors) < 32:
                            hive_errors.append(dict(
                                hive=hive_name, index=idx[:32], label=label[:128], sensor=sensor[:128],
                                state="parse_error", reason=str(error)[:80]))
                        continue
                    matched = False
                    if hwinfo_watts_unit(vals, idx) and 0 <= raw < 2000:
                        if "cpu" in sensor and label in ("cpu package power", "cpu ppt"):
                            hive_readings.update(cpu_power=raw)
                            matched = True
                        if label in (
                            "ac input power",
                            "adapter input power",
                            "charger input power",
                        ):
                            hive_readings["adapter_input_watts"] = raw
                            matched = True
                        if label in ("total system power", "system power consumption"):
                            hive_readings["system_power"] = raw
                            matched = True
                    if (
                        "cpu" in sensor
                        and label in ("cpu (tctl/tdie)", "cpu package", "cpu die (average)")
                        and 0 < raw < 125
                    ):
                        hive_readings.update(cpu_temp=raw, cpu_temp_source="HWiNFO VSB")
                        matched = True
                    if "gpu" in sensor:
                        if label in ("gpu temperature", "gpu core temperature") and 0 < raw < 125:
                            hive_readings.update(gpu_temp=raw, gpu_source="HWiNFO VSB")
                            matched = True
                        elif label in ("gpu core load", "gpu utilization") and 0 <= raw <= 100:
                            hive_readings.update(gpu_usage=raw, gpu_source="HWiNFO VSB")
                            matched = True
                        elif (
                            label in ("gpu power", "gpu asic power")
                            and hwinfo_watts_unit(vals, idx)
                            and 0 <= raw < 2000
                        ):
                            hive_readings["gpu_asic_power" if label == "gpu asic power" else "gpu_power"] = raw
                            matched = True
                    if (
                        "battery" in sensor
                        and label in ("voltage", "battery voltage")
                        and 0 < raw < 100
                    ):
                        hive_readings["voltage"] = raw
                        matched = True
                    export_available += bool(matched)
                export["available_count"] = export_available
                export["parse_error_count"] = export_parse_errors
                export["state"] = "available" if export_available else (
                    "parse_error" if export_parse_errors else "no_supported_channels")
                result.update(hive_readings)
                result.sample_times.update(dict.fromkeys(hive_readings, updated))
                diagnostics["channel_errors"].extend(
                    hive_errors[:32 - len(diagnostics["channel_errors"])])
                if isinstance(cache, dict):
                    cache[hive_name] = dict(
                        signature=signature, readings=dict(hive_readings), export=dict(export),
                        parse_error_count=export_parse_errors,
                        channel_errors=copy.deepcopy(hive_errors),
                    )
        except OSError as error:
            if isinstance(cache, dict):
                cache.pop(hive_name, None)
            export["state"] = "export_absent" if (
                getattr(error, "winerror", None) == 2 or isinstance(error, FileNotFoundError)
            ) else "query_failed"
            export["error"] = provider_error(error, "HWiNFO VSB registry query")
    diagnostics["available_count"] = len(result)
    if result:
        diagnostics["state"] = "available"
    else:
        states = {export["state"] for export in diagnostics["exports"]}
        diagnostics["state"] = next((state for state in (
            "parse_error", "no_supported_channels", "future_timestamp", "stale",
            "invalid_timestamp", "query_failed") if state in states), "export_absent")
    return result


def cpu_name():
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except OSError:
        return "CPU"


def fmt(value, unit="", digits=0):
    return "--" if value is None else f"{value:.{digits}f}{unit}"


def view(data):
    vram_pct = (
        data.get("vram_gb", 0) / data["vram_total_gb"] * 100 if data.get("vram_total_gb") else None
    )
    state = power_state(data)
    result = dict(
        SampleEpoch=str(int(data["time"])),
        PowerState=str(state),
        CpuTemp=fmt(data.get("cpu_temp")),
        CpuUsage=fmt(data["cpu_usage"], "%"),
        CpuBar=fmt(data["cpu_usage"], "", 1),
        CpuCores=str(data["cpu_cores"]),
        CpuThreads=str(data["cpu_threads"]),
        GpuTemp=fmt(data.get("gpu_temp")),
        GpuUsage=fmt(data.get("gpu_usage"), "%"),
        GpuBar=fmt(data.get("gpu_usage") or 0),
        GpuPower=fmt(data.get("gpu_power"), " W", 1),
        MemoryPct=fmt(data["ram_percent"], "%"),
        MemoryBar=fmt(data["ram_percent"], "", 1),
        MemoryUsed=fmt(data["ram_used_gb"], "", 1),
        MemoryTotal=fmt(data["ram_total_gb"], "", 1),
        MemoryDetail=(
            f"{data['ram_used_gb']:.1f} / {data['ram_total_gb']:.1f} GB"
            if all(type(data.get(k)) in (int, float) for k in ("ram_used_gb", "ram_total_gb"))
            else "-- / -- GB"
        ),
        MemoryAvailable=fmt(data["ram_available_gb"], " GB", 1),
        Vram=fmt(data.get("vram_gb"), " GB", 1),
        VramTotal=fmt(data.get("vram_total_gb"), " GB"),
        VramNumber=fmt(data.get("vram_gb"), "", 1),
        VramPercent=fmt(vram_pct, "%"),
        VramBar=fmt(vram_pct or 0, "", 1),
        BatteryPct=fmt(data.get("battery_percent"), "%"),
        BatteryBar=fmt(data.get("battery_percent") or 0),
        BatteryPower=fmt(data.get("battery_watts"), " W", 1),
        BatteryVoltage=fmt(data.get("voltage"), " V", 2),
        PowerNumber=fmt(data.get("battery_watts"), "", 1),
        PowerBar=fmt(data.get("battery_watts") or 0, "", 1),
    )
    result.update(
        {
            variable(key): fmt(metric_value(data, key), digits=meta["digits"])
            for key, meta in METRICS.items()
        }
    )
    result.update(
        {variable(key) + "Bar": fmt(metric_value(data, key) or 0, digits=2) for key in METRICS}
    )
    return "\n".join(k + "=" + v for k, v in result.items()) + "\n"


class Sampler:
    def __init__(self):
        self.cpu = cpu_name()
        self.cores = psutil.cpu_count(logical=False) or 0
        self.threads = psutil.cpu_count() or 0
        self.asus = None
        self.nvidia = None
        self.storage = StorageHealth(BASE)
        self.battery = Battery()
        self.cpu_power = CpuPackagePower()
        self.activity = Activity()
        self.external = ExternalEngine()
        self.nvml_retry = 0
        self.asus_retry = 0
        self.asus_status = dict(state="idle", reason="", error={})
        self.nvml_status = dict(state="idle", reason="", error={})
        self.first = True
        self._hwinfo_cache = {}
        self._closed = False
        try:
            self.asus = AsusTemperature()
            self.asus_status = dict(state="connected", reason="", error={})
        except OSError as error:
            self.asus_retry = time.monotonic() + ASUS_RETRY_SECONDS
            self.asus_status = dict(state="waiting_retry", reason="initialization_failed",
                                    error=provider_error(error, "AsusTemperature"))
        self.cooling = AsusFans(getattr(self.asus, "read_status", None))
        psutil.cpu_percent()
        psutil.cpu_percent(percpu=True)

    def _release_asus(self, reason, error):
        """Invalidate only this provider, including cached pre-loss fan values."""
        source, self.asus = self.asus, None
        previous, self.cooling = self.cooling, AsusFans()
        self.asus_retry = time.monotonic() + ASUS_RETRY_SECONDS
        self.asus_status = dict(state="waiting_retry", reason=reason, error=error)
        channels = getattr(source, "channel_status", None)
        if isinstance(channels, dict):
            self.asus_status["channel_status"] = {key: dict(value) for key, value in channels.items()}
        previous.close()
        if source is not None:
            try:
                source.close()
            except Exception:
                logging.exception("ASUS sensor cleanup failed")

    def _ensure_asus(self):
        if self.asus is not None or time.monotonic() < getattr(self, "asus_retry", 0):
            return
        try:
            source = AsusTemperature()
        except OSError as error:
            self.asus_retry = time.monotonic() + ASUS_RETRY_SECONDS
            self.asus_status = dict(state="waiting_retry", reason="initialization_failed",
                                    error=provider_error(error, "AsusTemperature"))
            return
        previous, self.cooling = self.cooling, AsusFans(getattr(source, "read_status", None))
        self.asus = source
        self.asus_status = dict(state="connected", reason="", error={})
        previous.close()

    def _release_nvidia(self, reason, error=None, retry_seconds=NVML_RETRY_SECONDS):
        source, self.nvidia = self.nvidia, None
        self.nvml_retry = time.monotonic() + retry_seconds
        self.nvml_status = dict(state="waiting_retry" if retry_seconds else "idle",
                                reason=reason, error=error or {})
        if source is not None:
            try:
                source.close()
            except Exception:
                logging.exception("NVML cleanup failed")

    def _provider_status(self, name, requested):
        source = self.asus if name == "asus" else self.nvidia
        status = dict(getattr(self, name + "_status", dict(
            state="connected" if source is not None else "idle", reason="", error={})))
        status["requested"] = bool(requested)
        channel_errors = getattr(source, "status_errors", None)
        if isinstance(channel_errors, dict):
            status["channel_errors"] = {key: dict(value) for key, value in channel_errors.items()}
        channels = getattr(source, "channel_status", None)
        if isinstance(channels, dict):
            status["channel_status"] = {key: dict(value) for key, value in channels.items()}
        deadline = getattr(self, name + "_retry", 0)
        status["retry_in_seconds"] = max(0.0, deadline - time.monotonic()) if (
            status["state"] == "waiting_retry") else 0.0
        return status

    def sample(self):
        if self._closed:
            return {}
        provider = getattr(self, "config_provider", None)
        config = provider() if callable(provider) else load()
        usage = psutil.cpu_percent(interval=0.2 if self.first else None)
        self.first = False
        data = dict(
            time=time.time(),
            cpu_usage=usage,
            cpu_temp=None,
            cpu_name=self.cpu,
            cpu_cores=self.cores,
            cpu_threads=self.threads,
        )
        inspecting = time.monotonic() < INSPECT_UNTIL
        needed = required_sources(config)
        extended = self.external.read("external" in needed or inspecting, EXTERNAL_RESCAN)
        catalog = extended.pop("external_sensors")
        data.update(extended)
        data["external_catalog"] = catalog
        bound_ids = {
            binding["sensor_id"] for prefs in config["widgets"].values()
            for binding in prefs.get("sensor_bindings", {}).values()
        }
        top_bar = config.get("top_bar", {})
        if top_bar.get("enabled"):
            bound_ids.update(
                binding["sensor_id"] for item in top_bar.get("items", [])
                for binding in item.get("prefs", {}).get("sensor_bindings", {}).values())
        data["external_sensors"] = {key: catalog[key] for key in bound_ids if key in catalog}
        cooling, asus_readings = {}, {}
        if "cpu" in needed or "cooling" in needed or inspecting:
            self._ensure_asus()
            try:
                if "cooling" in needed or inspecting:
                    cooling = self.cooling.read()
                if self.asus and ("cpu" in needed or inspecting):
                    asus_readings = self.asus.read()
            except OSError as error:
                cooling, asus_readings = {}, {}
                self._release_asus("read_failed", provider_error(error, "AsusTemperature.read"))
            if self.asus and getattr(self.asus, "needs_reconnect", False) is True:
                cooling, asus_readings = {}, {}
                self._release_asus("handle_lost", dict(self.asus.last_error))
        data.update(cooling)
        if "cpu" in needed or inspecting:
            data.update(self.cpu_power.read(allow_cached=config["refresh"] < 0.05))
            data["cpu_power_state"] = self.cpu_power.state
            error = getattr(self.cpu_power, "last_error", "")
            data["cpu_power_error"] = error if isinstance(error, str) else ""
            data["cpu_per_core"] = psutil.cpu_percent(percpu=True)
            try:
                frequency = psutil.cpu_freq()
                data["cpu_frequency"] = (
                    frequency.current / 1000 if frequency and frequency.current > 0 else None
                )
            except (OSError, RuntimeError, psutil.Error):
                pass
        data.update(asus_readings)
        needs_gpu = "gpu" in needed or inspecting
        if needs_gpu and self.nvidia is None and time.monotonic() >= self.nvml_retry:
            try:
                self.nvidia = Nvidia()
                self.nvml_status = dict(state="connected", reason="", error={})
            except (OSError, RuntimeError, AttributeError) as error:
                self.nvml_retry = time.monotonic() + 60
                self.nvml_status = dict(state="waiting_retry", reason="initialization_failed",
                                        error=provider_error(error, "Nvidia"))
        if not needs_gpu and self.nvidia:
            self._release_nvidia("not_requested", retry_seconds=0)
        if self.nvidia:
            try:
                reading = self.nvidia.read()
            except (OSError, RuntimeError, AttributeError) as error:
                self._release_nvidia("read_failed", provider_error(error, "Nvidia.read"))
            else:
                data.update(reading)
                if not any(
                    device.get(key) is not None
                    for device in [reading, *reading.get("gpus", {}).values()]
                    for key, meta in METRICS.items()
                    if meta["source"] == "gpu"
                ):
                    self._release_nvidia("no_values")
        data["provider_status"] = dict(
            asus=self._provider_status("asus", "cpu" in needed or "cooling" in needed or inspecting),
            nvml=self._provider_status("nvml", needs_gpu),
        )
        extra = hwinfo_registry(getattr(self, "_hwinfo_cache", None))
        diagnostics = getattr(extra, "diagnostics", None)
        if isinstance(diagnostics, dict):
            data["provider_status"]["hwinfo"] = diagnostics
        data["metric_sources"] = {}
        data["metric_timestamps"] = {
            key: timestamp for key, timestamp in self.cooling.sample_times.items() if key in cooling
        }
        data["metric_sources"].update({key: COOLING_SOURCE for key in cooling})
        if data.get("cpu_power") is not None:
            data["metric_sources"]["cpu_power"] = data["cpu_power_source"]
        for key, value in extra.items():
            # VSB labels do not map HWiNFO's GPU numbering to NVML's indices.
            # A GPU [#0] there can be the iGPU while NVML 0 is the dGPU. Use
            # typed external bindings for those channels, never merge by index.
            if key in METRICS and METRICS[key].get("scope") == "gpus":
                continue
            if data.get(key) is None:
                data[key] = value
                data["metric_sources"][key] = "HWiNFO VSB"
                timestamp = getattr(extra, "sample_times", {}).get(key)
                if type(timestamp) in (int, float) and math.isfinite(timestamp):
                    data["metric_timestamps"][key] = timestamp
        data.update(self.battery.read())
        data.update(self.storage.read("storage" in needed or inspecting))
        for metric in ("storage_temp", "storage_spare_percent", "storage_wear_percent"):
            if data.get("storages", {}).get("0", {}).get(metric) is not None:
                data[metric] = data["storages"]["0"][metric]
                data["metric_sources"][metric] = "Windows NVMe health"
        activity = self.activity.read(needed, inspecting)
        data["provider_status"].update(activity.pop("provider_status", {}))
        data.update(activity)
        try:
            battery = psutil.sensors_battery()
            data["battery_percent"] = battery.percent if battery else None
        except (OSError, RuntimeError, psutil.Error):
            data["battery_percent"] = None
        data.update(ram_percent=None, ram_used_gb=None, ram_total_gb=None, ram_available_gb=None)
        try:
            ram = psutil.virtual_memory()
            data.update(
                ram_percent=ram.percent,
                ram_used_gb=ram.used / 1024**3,
                ram_total_gb=ram.total / 1024**3,
                ram_available_gb=ram.available / 1024**3,
            )
        except (OSError, RuntimeError, psutil.Error):
            pass
        data.update(swap_percent=None, swap_used_gb=None)
        try:
            swap = psutil.swap_memory()
            data.update(swap_percent=swap.percent, swap_used_gb=swap.used / 1024**3)
        except (OSError, RuntimeError, psutil.Error):
            pass
        return data

    def write(self, data):
        # Native windows receive samples through signals. Legacy/diagnostic file
        # exports need not rewrite two files 100 times a second.
        now = time.monotonic()
        if 0 <= now - getattr(self, "_last_write_at", float("-inf")) < 0.2:
            return
        for filename, text, encoding in [
            ("state.txt", view(data), "ascii"),
            ("latest.json", json.dumps({key: value for key, value in data.items()
                                       if key != "external_catalog"}), "utf-8"),
        ]:
            temporary = BASE / (filename + ".tmp")
            temporary.write_text(text, encoding=encoding)
            try:
                temporary.replace(BASE / filename)
            except PermissionError:
                pass
        self._last_write_at = now

    def run(self, stop):
        try:
            while not stop.is_set():
                try:
                    self.write(self.sample())
                except Exception:
                    logging.exception("Sensor sample failed")
                stop.wait(load()["refresh"])
        finally:
            self.close()

    def close(self):
        self._closed = True
        getattr(self, "_hwinfo_cache", {}).clear()
        complete = True
        for name in ("storage", "external", "cooling", "asus", "nvidia", "cpu_power"):
            source = getattr(self, name, None)
            if source is not None:
                try:
                    if source.close() is False:
                        complete = False
                        logging.error("Sensor cleanup still pending: %s", name)
                        continue
                except Exception:
                    logging.exception("Sensor cleanup failed: %s", name)
                setattr(self, name, None)
        return complete
