"""Explain only observed source failures; absence alone never proves unsupported hardware."""

from itertools import islice

from external_sensor import sensor_binding
from metrics import SCOPE_FIELDS, metric_info


def export_has_problem(export, state):
    """An available VSB hive does not require a second, optional hive to exist."""
    error = export.get("error")
    if export.get("state") in ("available", "export_absent") and not error:
        return False
    if (state == "available" and export.get("state") == "export_absent"
            and isinstance(error, dict)
            and (error.get("type") == "FileNotFoundError" or error.get("winerror") == 2)):
        return False
    return True


def reading_source(data, metric, prefs=None):
    prefs = prefs or {}
    source = metric_info(metric, prefs)["source"]
    if source == "gpu":
        target = prefs.get("gpu_target", "0")
        return (
            data.get("gpus", {}).get(target, {}).get("gpu_source")
            or (data.get("gpu_source") if target == "0" else None)
            or "NVIDIA NVML"
        )
    if metric in data.get("metric_sources", {}):
        return data["metric_sources"][metric]
    if metric == "cpu_temp":
        return data.get("cpu_temp_source", "ASUS ACPI")
    if metric == "cpu_power":
        return data.get("cpu_power_source", "Windows Energy Meter")
    if source == "storage":
        return "Windows NVMe health"
    return {"hwinfo": "HWiNFO VSB", "cooling": "ASUS ACPI", "external": "LibreHardwareMonitor"}.get(
        source, "Windows"
    )


def error_text(error):
    if not isinstance(error, dict):
        return ""
    facts = []
    for field, label in (
        ("api", "API"),
        ("endpoint", "endpoint"),
        ("label", ""),
        ("sensor", ""),
        ("winerror", "Win32"),
        ("errno", "errno"),
        ("ntstatus", "NTSTATUS"),
        ("status_code", "status"),
        ("status_text", ""),
        ("reason", ""),
        ("raw", "raw"),
        ("returned_bytes", "bytes"),
        ("message", ""),
    ):
        if error.get(field) is not None:
            value = (
                hex(error[field] & 0xFFFFFFFF)
                if field == "ntstatus" and type(error[field]) is int
                else str(error[field])[:240]
            )
            facts.append((label + " " if label else "") + value)
    nested = error.get("error")
    if isinstance(nested, dict):
        facts.extend(
            ("Win32 " if key == "winerror" else "") + str(nested[key])[:240]
            for key in ("winerror", "message")
            if key in nested
        )
    return " · ".join(facts)[:700]


def unavailable_reason(data, metric, prefs=None):
    """Pure formatting, no probing, permissions guesses, or hardware unsupported inference."""
    if data.get("sample_status", {}).get("state") == "stale":
        return "读数已过期"
    prefs = prefs or {}
    meta = metric_info(metric, prefs)
    provider = data.get("provider_status", {})
    scope = meta.get("scope")
    target = prefs.get(SCOPE_FIELDS.get(scope))
    activity = (
        provider.get("volumes" if scope == "volumes" else meta["source"], {})
        if meta["source"] in ("network", "disk")
        else {}
    )
    activity_error = activity.get("error")
    if scope == "volumes":
        volume = data.get("volume_system") if target in (None, "system") else target
        activity_error = activity_error or activity.get("device_errors", {}).get(volume)
    # A failed enumeration cannot prove that the saved device was disconnected.
    if activity_error:
        return "Windows 活动查询失败，将自动重试。" + error_text(activity_error)
    if (
        target
        and target not in ("0", "auto", "all", "system")
        and scope in data
        and target not in data[scope]
    ):
        return "所选设备未连接：" + target
    if meta["source"] == "external":
        binding = sensor_binding(metric, prefs)
        if not binding:
            return "此指标尚未绑定具体传感器。"
        status = data.get("external_status", {})
        rows = data.get("external_sensors", {})
        row = rows.get(binding["sensor_id"])
        if status.get("state") not in (None, "ready", "empty"):
            return status.get("detail") or "扩展采集器尚未返回本轮数据。"
        if not row:
            return "本轮扩展清单中没有所选传感器；保留原绑定，未自动换成其他设备。"
        if row.get("type") != binding["sensor_type"] or row.get("unit") != meta["unit"]:
            return "传感器类型或单位与保存的绑定不符；已拒绝混用。"
        return "已识别传感器，但采集库本轮返回空值；尚不能确定硬件原因。"
    if meta["source"] == "gpu":
        device = data.get("gpus", {}).get(target or "0", data)
        status = device.get("device_status", {})
        if status and status.get("state") != "available":
            return "NVML 此设备句柄查询未成功，将自动重试。" + error_text(status)
        channel = device.get("channel_status", {}).get(metric, {})
        if channel:
            detail = error_text(channel)
            if channel.get("state") == "entrypoint_missing":
                return "当前 NVML 库没有此查询入口。" + detail
            if channel.get("status_code") == 3:
                return "NVML 明确返回此查询不支持。" + detail
            if channel.get("state") != "available":
                return "NVML 此通道查询未成功。" + detail
        status = provider.get("nvml", {})
        if status.get("requested") is False:
            return "当前未请求显卡采样；打开传感器页或添加此指标后采样。"
        if status.get("error"):
            return "显卡来源暂未连接，将自动重试。" + error_text(status["error"])
        return "显卡通道尚无有效读数；需要通道返回码，不能据此认定硬件不支持。"
    if metric == "cpu_power":
        state = data.get("cpu_power_state")
        if state == "warming_up":
            return "功率计需要两次采样，正在建立基线。"
        detail = data.get("cpu_power_error", "")
        return "Windows Energy Meter 尚无有效采样。" + (
            " " + str(detail)[:300] if detail else "尚无具体错误，不能判断为权限不足。"
        )
    if metric == "cpu_temp" or meta["source"] == "cooling":
        if metric == "system_fan_rpm":
            return "内置 ASUS 读取只接入 CPU/GPU 两路机身风扇；第三风扇需从已发现的扩展传感器绑定。"
        endpoint = {
            "cpu_temp": "0x00120094",
            "cpu_fan_rpm": "0x00110013",
            "gpu_fan_rpm": "0x00110014",
        }.get(metric)
        status = provider.get("asus", {})
        channel = status.get("channel_errors", {}).get(endpoint, {}) or status.get(
            "channel_status", {}
        ).get(metric, {})
        if channel:
            return "ASUS " + endpoint + " 查询未产生有效读数。" + error_text(channel)
        if status.get("error"):
            return "ASUS 设备接口暂未连接，将自动重试。" + error_text(status["error"])
        if status.get("requested") is False:
            return "当前未请求温度/风扇采样；添加此指标或打开传感器页后采样。"
        return "厂商接口本轮尚无有效读数；未判定为硬件不支持。"
    if meta["source"] == "hwinfo":
        status = provider.get("hwinfo", data.get("hwinfo_status", {}))
        detail = status.get("detail") or error_text(status.get("error"))
        if status.get("state") == "export_absent":
            return "HWiNFO VSB 导出键不存在；尚未获得此导出通道，不是权限错误。" + (
                " " + detail if detail else ""
            )
        if status:
            return detail or "HWiNFO 已检查，但此项没有有效导出值；查看来源诊断。"
        return "尚未获得此项 HWiNFO 导出证据；不能由 CPU/GPU 功率相加或电池功率推算。"
    if meta["source"] == "battery":
        if data.get("battery_present") is False:
            return "Windows 本轮明确报告未发现电池。"
        if metric == "battery_time_minutes" and data.get("charging"):
            return "电池正在充电，Windows 此时未给出放电剩余时间。"
        status = data.get("battery_status", {})
        if status.get("error"):
            return "Windows 电池接口查询失败，将自动重试。" + error_text(status["error"])
        if status.get("ntstatus"):
            return "Windows 电池接口失败，NTSTATUS " + hex(status["ntstatus"] & 0xFFFFFFFF)
        return "Windows 电池接口本轮没有提供此值；不能当作 0 W 或充电器输入。"
    if meta["source"] == "storage":
        target = prefs.get("storage_target", "0")
        row = data.get("storages", {}).get(target, {})
        status = data.get("storage_status", {})
        if status.get("state") == "stale":
            return status.get("detail", "NVMe 健康读数已过期。")
        if row.get("winerror"):
            return "Windows 只读 NVMe 查询失败。" + error_text(row)
        if row.get("reason"):
            return "NVMe 响应未通过校验。" + error_text(row)
        if metric in row.get("channel_reasons", {}):
            return "NVMe 已返回此通道，但数值未通过校验：" + row["channel_reasons"][metric]
        return status.get("detail") or "添加 NVMe 指标后按需读取；尚无此设备有效健康日志。"
    if meta["source"] in ("network", "disk"):
        if activity.get("state") == "no_devices":
            return "Windows 本轮查询成功，但没有符合条件的活动设备。"
        if activity.get("state") == "warming_up" and scope != "volumes":
            return "速率需要两次连续采样，正在建立计数器基线。"
        return "Windows 活动来源本轮没有提供此值；查看来源诊断，未判定为权限不足或硬件不支持。"
    return "本轮尚无有效读数；未获得可证明权限不足或硬件不支持的错误。"


def source_rows(data):
    rows = []
    sample = data.get("sample_status", {})
    if sample.get("state") == "stale":
        rows.append(
            dict(id="sample", label="Sampler", state="stale", detail="读数已过期", errors="")
        )
    for identifier, status in data.get("provider_status", {}).items():
        errors = []
        if identifier == "nvml":
            for device_id, device in list(data.get("gpus", {}).items())[:16]:
                state = device.get("device_status", {})
                if state and state.get("state") != "available":
                    errors.append("GPU " + device_id + " · " + error_text(state))
                for metric, channel in device.get("channel_status", {}).items():
                    if channel.get("state") != "available":
                        errors.append(
                            "GPU " + device_id + " · " + metric + " · " + error_text(channel)
                        )
        if status.get("error"):
            errors.append(error_text(status["error"]))
        if status.get("cleanup_error"):
            errors.append("Cleanup · " + error_text(status["cleanup_error"]))
        for error in list(status.get("device_errors", {}).values())[:32]:
            errors.append(error_text(error))
        for channel in list(status.get("channel_status", {}).values())[:32]:
            if channel.get("state") != "available":
                errors.append(error_text(channel))
        for export in status.get("exports", [])[:4]:
            if not export_has_problem(export, status.get("state")):
                continue
            errors.append(
                " · ".join(
                    filter(
                        None,
                        (export.get("hive"), export.get("state"), error_text(export.get("error"))),
                    )
                )
            )
        channels = status.get("channel_errors", [])
        channels = islice(channels.values(), 32) if isinstance(channels, dict) else (
            channels[:32] if isinstance(channels, list) else ())
        for channel in channels:
            errors.append(error_text(channel))
        if identifier == "hwinfo":
            detail = {
                "export_absent": "VSB 导出键不存在；不是拒绝访问。",
                "future_timestamp": "导出时间在未来，已拒绝作为新读数。",
                "stale": "导出数据已过期。",
                "parse_error": "存在导出，但部分数值格式不明确或无效。",
                "no_supported_channels": "导出存在，未匹配内置映射；可从扩展清单按设备绑定。",
            }.get(status.get("state"), status.get("detail", ""))
        else:
            detail = status.get("detail") or status.get("reason", "")
            if identifier == "battery" and not detail:
                detail = {
                    "ready": "Windows 电池接口本轮查询成功。",
                    "no_battery": "Windows 本轮查询成功，未发现电池。",
                    "query_failed": "本轮 Windows 电池查询失败；将自动重试。",
                    "waiting_retry": "Windows 电池来源正在等待重试。",
                }.get(status.get("state"), "")
            if identifier in ("network", "disk", "volumes") and not detail:
                detail = {
                    "query_failed": "本轮 Windows 活动查询失败；将自动重试。",
                    "partial": "部分卷本轮查询失败；其它卷继续更新。",
                    "warming_up": "正在建立连续采样的速率基线。",
                    "no_devices": "本轮查询成功，但没有符合条件的活动设备。",
                }.get(status.get("state"), "")
        rows.append(
            dict(
                id=identifier,
                label={
                    "asus": "ASUS ACPI",
                    "nvml": "NVIDIA NVML",
                    "battery": "Windows 电池接口",
                    "hwinfo": "HWiNFO VSB",
                    "network": "Windows 网络计数器",
                    "disk": "Windows 磁盘计数器",
                    "volumes": "Windows 卷容量",
                }.get(identifier, identifier),
                state=status.get("state", "unknown"),
                detail=detail,
                errors="\n".join(filter(None, errors))[:4000],
            )
        )
    extended = data.get("external_status")
    if extended:
        errors = [
            f"{field}: {extended[field]}"
            for field in ("update_errors", "skipped_types", "truncated", "rejected_count")
            if extended.get(field)
        ]
        if extended.get("state") == "stale" and extended.get("last_state"):
            errors.append("previous_state (historical): " + str(extended["last_state"])[:64])
            if extended.get("last_detail"):
                errors.append("previous_detail (historical): " + str(extended["last_detail"])[:700])
        rows.append(
            dict(
                id="external",
                label="LibreHardwareMonitor",
                state=extended.get("state", "unknown"),
                detail=extended.get("detail", ""),
                errors="\n".join(errors),
            )
        )
    if "storage_status" in data:
        status = data["storage_status"]
        rows.append(
            dict(
                id="storage",
                label="Windows NVMe health",
                state=status.get("state", "unknown"),
                detail=status.get("detail", ""),
                errors="\n".join(
                    "PhysicalDrive" + identifier + " · " + error_text(row)
                    for identifier, row in data.get("storages", {}).items()
                    if row.get("state") != "available"
                ),
            )
        )
    return rows
