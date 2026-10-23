"""Actionable explanations and deliberately small, non-personal diagnostic exports."""
import math
from itertools import islice

from metrics import METRICS
from sensor_diagnostics import export_has_problem, source_rows

GOOD = {"ready", "connected", "available", "no_battery", "not_requested", "idle"}
STATES = GOOD | {
    "waiting_retry", "warming_up", "stale", "export_absent", "invalid_timestamp",
    "future_timestamp", "no_supported_channels", "parse_error", "empty", "no_values",
    "error", "closed", "cleanup_pending", "closing", "partial", "no_devices", "query_failed",
    "failed", "unavailable", "starting", "missing", "invalid_value", "entrypoint_missing",
}
REASONS = {
    "initialization_failed", "initialization_error", "read_failed", "no_values", "not_requested",
    "handle_lost", "cleanup_pending", "entrypoint_missing", "null_device_handle",
    "zero_total_memory", "presence_missing", "temperature_out_of_range", "unknown_flags",
    "rpm_out_of_range", "ioctl_failed", "invalid_response_length", "export_changed_during_read",
    "OSError", "PermissionError", "FileNotFoundError", "RuntimeError", "QueryError", "psutil.Error",
}
ERROR_TYPES = {
    "OSError", "PermissionError", "FileNotFoundError", "RuntimeError", "AttributeError",
    "ValueError", "TypeError", "ProviderApiError", "ProviderCleanupPending", "QueryError",
    "psutil.Error", "OperationalError", "DatabaseError", "IntegrityError",
}
APIS = {
    "Nvidia", "Nvidia.read", "AsusTemperature", "AsusTemperature.read", "DeviceIoControl",
    "DeviceIoControl/DSTS", "CreateFileW", "QueryDosDeviceW", "CreateFileW(metadata)",
    "IOCTL_STORAGE_QUERY_PROPERTY(NVMe health)", "HWiNFO VSB registry query",
    "winreg.OpenKey", "winreg.QueryInfoKey", "winreg.EnumValue",
    "CallNtPowerInformation(SystemBatteryState)", "LoadLibraryW(PowrProf.dll)",
    "psutil.net_io_counters", "psutil.net_if_stats", "psutil.disk_io_counters",
    "psutil.disk_partitions", "psutil.disk_usage",
    "nvmlInit_v2", "nvmlShutdown", "nvmlDeviceGetCount_v2", "nvmlDeviceGetHandleByIndex_v2",
    "nvmlDeviceGetName", "nvmlDeviceGetTemperature", "nvmlDeviceGetUtilizationRates",
    "nvmlDeviceGetPowerUsage", "nvmlDeviceGetMemoryInfo", "nvmlDeviceGetClockInfo",
    "nvmlDeviceGetFanSpeed", "nvmlErrorString",
}
MAX_FAILURES = 64
_ASUS_METRICS = {"0x00120094": "cpu_temp", "0x00110013": "cpu_fan_rpm", "0x00110014": "gpu_fan_rpm"}


def cards(data):
    result = []
    for row in source_rows(data):
        state = row["state"]
        status = data.get("provider_status", {}).get(row["id"], {})
        if row["id"] == "external":
            status = data.get("external_status", {})
        if row["id"] == "storage":
            status = data.get("storage_status", {})
        has_error = bool(row["errors"])
        healthy = state in GOOD and not has_error
        badge = "正常" if healthy else "部分可用" if state in GOOD and has_error else "待检查"
        if state == "no_battery":
            badge = "无电池"
        elif state in ("not_requested", "idle"):
            badge = "按需读取"
        elif state == "waiting_retry":
            badge = "等待重试"
        elif state == "warming_up":
            badge = "建立基线"
        elif state == "stale":
            badge = "读数过期"
        elif state == "export_absent":
            badge = "未发现导出"
        hint = "本轮接口正常返回。"
        if has_error or not healthy:
            hint = "重新检查后仍缺测，可导出接口状态用于排查；不会把缺测当作零。"
        if row["id"] == "hwinfo" and state == "export_absent":
            hint = "检查 HWiNFO 是否正在提供 VSB 导出；当前未发现相应注册表键。"
        elif state == "waiting_retry":
            hint = "等待来源的重试间隔结束后自动恢复检查，其他正常来源继续更新。"
        elif state == "no_battery":
            hint = "Windows 明确报告没有电池，这不是权限错误。"
        elif state in ("idle", "not_requested"):
            hint = "添加对应指标或重新检查时，才按需请求该来源。"
        elif state == "warming_up":
            hint = "速率需要两次连续读数；不会使用中断前的旧基线。"
        retry = status.get("retry_in_seconds", 0)
        retry = max(0, min(86400, retry)) if (
            type(retry) in (int, float) and math.isfinite(retry)) else 0
        result.append(dict(row, badge=badge, healthy=healthy, hint=hint, retry_seconds=retry))
    return result


def safe_report(data, version):
    """No raw samples, device IDs, adapter names, paths or exception messages."""
    def facts(value):
        if not isinstance(value, dict):
            return {}
        result = {}
        # Field names alone are not a privacy boundary: arbitrary reason/API
        # strings can contain hostnames, adapter labels or exception messages.
        # Export only the app's known machine codes and fixed API spellings.
        for key, allowed in (("api", APIS), ("state", STATES), ("reason", REASONS), ("type", ERROR_TYPES)):
            item = value.get(key)
            if isinstance(item, str) and item in allowed:
                result[key] = item
        for key in ("winerror", "errno", "ntstatus", "status_code"):
            item = value.get(key)
            if type(item) is int and -(2**63) <= item < 2**64:
                result[key] = item
        for field in ("error", "cleanup_error"):
            if field in value:
                result[field] = facts(value[field])
        return result

    def children(value, limit=32):
        if isinstance(value, dict):
            return islice(value.items(), limit)
        if isinstance(value, list):
            return (("", row) for row in islice(value, limit))
        return ()

    def source_facts(identifier, value):
        result = facts(value)
        failures = []
        truncated = False

        def append(row, metric=""):
            nonlocal truncated
            safe = facts(row)
            if not safe:
                return
            if (row.get("state") in GOOD and not row.get("error") and not row.get("cleanup_error")
                    and not any(type(row.get(key)) is int and row[key] != 0
                                for key in ("winerror", "errno", "ntstatus", "status_code"))):
                return
            if isinstance(metric, str) and metric in METRICS:
                safe["metric"] = metric
            if len(failures) < MAX_FAILURES:
                failures.append(safe)
            else:
                truncated = True

        if isinstance(value, dict):
            for field in ("device_errors", "channel_errors", "channel_status", "exports"):
                for key, row in children(value.get(field), 4 if field == "exports" else 32):
                    if field == "exports" and isinstance(row, dict) and not export_has_problem(row, value.get("state")):
                        continue
                    metric = _ASUS_METRICS.get(key, key) if identifier == "asus" else key
                    append(row, metric if field in ("channel_errors", "channel_status") else "")
        if identifier == "nvml":
            # Device mapping keys and names are deliberately never copied.
            for _, device in children(data.get("gpus"), 16):
                if not isinstance(device, dict):
                    continue
                append(device.get("device_status"))
                for metric, row in children(device.get("channel_status")):
                    append(row, metric)
        elif identifier == "storage_status":
            for _, device in children(data.get("storages")):
                append(device)
        if failures:
            result["failures"] = failures
        if truncated:
            result["failures_truncated"] = True
        return result

    sources = {str(key): source_facts(key, value) for key, value in data.get("provider_status", {}).items()
               if key in {"nvml", "asus", "hwinfo", "network", "disk", "volumes", "battery"}}
    for field in ("external_status", "storage_status", "battery_status", "sample_status"):
        if isinstance(data.get(field), dict):
            sources[field] = source_facts(field, data[field])
    timestamp = data.get("time")
    return dict(format=1, application="Desktop Stats", version=version,
                sample_time=timestamp if type(timestamp) in (int, float) and math.isfinite(timestamp) else None,
                sources=sources,
                privacy="No raw readings, device identifiers, local paths or exception messages.")
