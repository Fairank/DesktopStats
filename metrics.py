"""Typed reading registry, device selection, dependencies and truthful availability."""

import math

from external_sensor import EXTERNAL_SLOTS, binding_meta, sensor_binding


def reading(
    label, source, unit, digits=0, maximum=100, kind="line", category=None, scope=None, note=""
):
    return dict(
        label=label,
        source=source,
        unit=unit,
        digits=digits,
        maximum=maximum,
        kind=kind,
        category=category or source,
        scope=scope,
        note=note,
    )


METRICS = {
    "cpu_temp": reading("CPU 温度", "cpu", "°C", maximum=125, category="power"),
    "cpu_usage": reading("CPU 使用率", "cpu", "%"),
    "cpu_frequency": reading("CPU 频率", "cpu", "GHz", 2, 8),
    "cpu_cores": reading("物理核心", "cpu", "", maximum=256),
    "cpu_threads": reading("逻辑处理器", "cpu", "", maximum=512),
    "cpu_power": reading("CPU 封装功率", "cpu", "W", 1, 200, category="power"),
    "gpu_temp": reading("GPU 温度", "gpu", "°C", maximum=125, category="power", scope="gpus"),
    "gpu_usage": reading("GPU 使用率", "gpu", "%", scope="gpus"),
    "gpu_power": reading("GPU 功率", "gpu", "W", 1, 300, category="power", scope="gpus"),
    "gpu_asic_power": reading("GPU 芯片功率", "hwinfo", "W", 1, 300, category="power",
                              note="HWiNFO 导出的芯片功率，与板卡功率范围不同。"),
    "gpu_clock": reading("GPU 核心频率", "gpu", "MHz", maximum=4000, scope="gpus"),
    "gpu_memory_clock": reading("显存频率", "gpu", "MHz", maximum=12000, scope="gpus"),
    "gpu_fan_percent": reading("GPU 风扇", "gpu", "%", scope="gpus"),
    "cpu_fan_rpm": reading("CPU 风扇转速", "cooling", "RPM", maximum=12000, category="cooling",
                           note="机身散热风扇的实际转速；需厂商转速传感器。"),
    "gpu_fan_rpm": reading("GPU 风扇转速", "cooling", "RPM", maximum=12000, category="cooling",
                           note="机身 GPU 侧散热风扇转速，不是风扇目标百分比。"),
    "system_fan_rpm": reading("系统风扇转速", "cooling", "RPM", maximum=12000, category="cooling",
                              note="需要设备实际提供第三风扇转速。"),
    "ram_percent": reading("内存占用率", "memory", "%", kind="bar"),
    "ram_used_gb": reading("已用内存", "memory", "GB", 1, 128),
    "ram_available_gb": reading("可用内存", "memory", "GB", 1, 128),
    "ram_total_gb": reading("总内存", "memory", "GB", 1, 128),
    "swap_percent": reading("分页文件占用率", "memory", "%", kind="bar"),
    "swap_used_gb": reading("已用分页文件", "memory", "GB", 1, 128),
    "vram_gb": reading("已用显存", "gpu", "GB", 1, 24, scope="gpus"),
    "vram_total_gb": reading("总显存", "gpu", "GB", 1, 24, scope="gpus"),
    "vram_percent": reading("显存占用率", "gpu", "%", kind="bar", scope="gpus"),
    "battery_percent": reading("电池电量", "battery", "%", kind="bar"),
    "battery_watts": reading("电池充放电", "battery", "W", 1, 100, category="power"),
    "battery_charge_watts": reading(
        "电池充电输入",
        "battery",
        "W",
        1,
        100,
        category="power",
        note="电池侧输入，不是充电器输入。",
    ),
    "battery_discharge_watts": reading(
        "电池放电输出",
        "battery",
        "W",
        1,
        100,
        category="power",
        note="电池侧输出，不等于整机功耗。",
    ),
    "voltage": reading("电池电压", "hwinfo", "V", 2, 25, category="battery"),
    "battery_remaining_wh": reading("剩余能量", "battery", "Wh", 1, 120),
    "battery_time_minutes": reading(
        "预计剩余时间",
        "battery",
        "min",
        maximum=900,
        note="由 Windows 提供；充电或无法预测时不显示。",
    ),
    "adapter_input_watts": reading(
        "充电器输入", "hwinfo", "W", 1, 400, category="power", note="需要独立的输入功率传感器。"
    ),
    "system_power": reading(
        "整机功耗",
        "hwinfo",
        "W",
        1,
        400,
        category="power",
        note="需要整机功率传感器，不由其他功率相加。",
    ),
    "net_download": reading("下载速度", "network", "MB/s", 2, 100, scope="networks"),
    "net_upload": reading("上传速度", "network", "MB/s", 2, 100, scope="networks"),
    "net_received_gb": reading(
        "累计接收",
        "network",
        "GB",
        2,
        1000,
        scope="networks",
        note="网卡计数器累计值；重启或重置网卡后会变化。",
    ),
    "net_sent_gb": reading(
        "累计发送",
        "network",
        "GB",
        2,
        1000,
        scope="networks",
        note="网卡计数器累计值；重启或重置网卡后会变化。",
    ),
    "disk_read": reading("磁盘读取", "disk", "MB/s", 2, 500, scope="disks"),
    "disk_write": reading("磁盘写入", "disk", "MB/s", 2, 500, scope="disks"),
    "disk_percent": reading("磁盘占用率", "disk", "%", kind="bar", scope="volumes"),
    "disk_used_gb": reading("已用空间", "disk", "GB", 1, 2048, scope="volumes"),
    "disk_free_gb": reading("可用空间", "disk", "GB", 1, 2048, scope="volumes"),
    "disk_total_gb": reading("磁盘容量", "disk", "GB", 1, 2048, scope="volumes"),
    "storage_temp": reading("NVMe 温度", "storage", "°C", maximum=100, category="disk", scope="storages", note="来自 Windows NVMe 健康日志的复合温度。"),
    "storage_spare_percent": reading("NVMe 备用容量", "storage", "%", maximum=100, category="disk", scope="storages", note="可用备用空间比例，不是磁盘剩余容量。"),
    "storage_wear_percent": reading("NVMe 寿命已用", "storage", "%", maximum=255, category="disk", scope="storages", note="厂商估计的已用寿命，可超过 100%；不是磁盘占用率。"),
}
METRICS.update((slot, binding_meta(slot)) for slot in EXTERNAL_SLOTS)
SCOPE_FIELDS = {
    "networks": "network_target",
    "disks": "disk_target",
    "volumes": "volume_target",
    "gpus": "gpu_target",
    "storages": "storage_target",
}


def numeric(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def metric_info(key, preferences=None):
    return binding_meta(key, preferences) if key in EXTERNAL_SLOTS else METRICS[key]


def metric_value(data, key, preferences=None):
    if key in EXTERNAL_SLOTS:
        binding = sensor_binding(key, preferences)
        rows = data.get("external_sensors")
        if binding is None or not isinstance(rows, dict):
            return None
        row = rows.get(binding["sensor_id"])
        unit = metric_info(key, preferences)["unit"]
        if (
            not isinstance(row, dict)
            or row.get("type") != binding["sensor_type"]
            or row.get("id", binding["sensor_id"]) != binding["sensor_id"]
            or row.get("unit", unit) != unit
            or row.get("available") is False
        ):
            return None
        value = row.get("value")
        return value if numeric(value) else None
    meta = metric_info(key, preferences)
    scope = meta.get("scope")
    if scope and preferences:
        target = preferences.get(SCOPE_FIELDS[scope])
        special = {"networks": "auto", "disks": "all", "volumes": "system", "gpus": "0", "storages": "0"}[scope]
        # Explicit disconnected/removed devices stay unavailable; never silently change them.
        if target and target != special:
            value = data.get(scope, {}).get(target, {}).get(key)
            return value if numeric(value) else None
        if scope in ("gpus", "storages") and scope in data:
            value = data[scope].get(target or special, {}).get(key)
            return value if numeric(value) else None
    if key == "vram_percent":
        total, used = data.get("vram_total_gb"), data.get("vram_gb")
        return used / total * 100 if numeric(total) and total > 0 and numeric(used) else None
    value = data.get(key)
    return value if numeric(value) else None


def display_value(data, key, preferences=None):
    prefs = preferences or {}
    value = metric_value(data, key, prefs)
    meta = metric_info(key, prefs)
    unit, digits = meta["unit"], meta["digits"]
    if unit == "°C" and prefs.get("temperature_unit") == "F":
        unit, value = "°F", value * 9 / 5 + 32 if numeric(value) else None
    if key in ("net_download", "net_upload") and prefs.get("network_unit") == "Mbps":
        unit, value = "Mbps", value * 8 if numeric(value) else None
    if prefs.get("precision", "auto") != "auto":
        digits = int(prefs["precision"])
    return value, unit, digits


def variable(key):
    return "Metric" + "".join(part.title() for part in key.split("_"))


def required_sources(config):
    needed = set()
    if config.get("top_bar", {}).get("enabled"):
        needed.update(METRICS[item["metric"]]["source"] for item in config["top_bar"]["items"])
    if not config.get("visible", True):
        return needed
    for key in config.get("widget_order", config["widgets"]):
        prefs = config["widgets"][key]
        if not prefs["enabled"]:
            continue
        if prefs.get("content"):
            needed.update(METRICS[item]["source"] for item in prefs["content"])
        else:
            kind = prefs.get("kind", key)
            needed.add("gpu" if kind == "vram" else "battery" if kind == "power" else kind)
    return needed
