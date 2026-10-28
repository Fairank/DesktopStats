"""Pure, bounded LibreHardwareMonitor descriptors; no device or process access."""

import math
import unicodedata

PROVIDER = "LibreHardwareMonitor"
EXTERNAL_SLOTS = tuple(f"external_{index}" for index in range(1, 7))
MAX_SENSORS = 4096
MAX_HARDWARE = 1024
MAX_TIMESTAMP = 253402300799

# Raw units are pinned to LHM v0.9.6 ISensor.cs, not inferred from names.
# https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/v0.9.6/LibreHardwareMonitorLib/Hardware/ISensor.cs
# These maxima are display scales, not sensor limits or value clamps.
SENSOR_TYPES = {
    "Temperature": dict(unit="°C", raw_unit="°C", digits=1, maximum=125, kind="line"),
    "Fan": dict(unit="RPM", raw_unit="RPM", digits=0, maximum=12000, kind="line"),
    "Noise": dict(unit="dBA", raw_unit="dBA", digits=1, maximum=130, kind="line"),
    "Voltage": dict(unit="V", raw_unit="V", digits=3, maximum=25, kind="line"),
    "Current": dict(unit="A", raw_unit="A", digits=3, maximum=100, kind="line"),
    "Power": dict(unit="W", raw_unit="W", digits=1, maximum=400, kind="line"),
    "Clock": dict(unit="MHz", raw_unit="MHz", digits=1, maximum=6000, kind="line"),
    "Load": dict(unit="%", raw_unit="%", digits=1, maximum=100, kind="bar"),
    "Data": dict(unit="GB", raw_unit="GB", digits=1, maximum=2048, kind="line"),
    "SmallData": dict(unit="MB", raw_unit="MB", digits=1, maximum=65536, kind="line"),
    "Throughput": dict(unit="B/s", raw_unit="B/s", digits=0, maximum=1e9, kind="line"),
    "Level": dict(unit="%", raw_unit="%", digits=1, maximum=100, kind="bar"),
    "Energy": dict(unit="Wh", raw_unit="mWh", digits=2, maximum=120, kind="line"),
    "Factor": dict(unit="", raw_unit="", digits=3, maximum=100, kind="line"),
}
_BINDING_FIELDS = frozenset(("provider", "sensor_id", "sensor_type", "name", "hardware_name"))


def _text(value, limit, *, empty=False):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (not empty and not value.strip())
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("硬件传感器文本不正确")
    return value


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _binding(value):
    if not isinstance(value, dict) or set(value) != _BINDING_FIELDS:
        raise ValueError("硬件传感器绑定不正确")
    if value["provider"] != PROVIDER:
        raise ValueError("不支持的传感器来源")
    sensor_type = value["sensor_type"]
    if not isinstance(sensor_type, str) or sensor_type not in SENSOR_TYPES:
        raise ValueError("不支持的传感器类型")
    return dict(
        provider=PROVIDER,
        sensor_id=_text(value["sensor_id"], 512),
        sensor_type=sensor_type,
        name=_text(value["name"], 128),
        hardware_name=_text(value["hardware_name"], 128, empty=True),
    )


def validate_bindings(value):
    """Return canonical per-widget bindings; identifiers remain exact opaque strings."""
    if not isinstance(value, dict) or len(value) > len(EXTERNAL_SLOTS):
        raise ValueError("硬件传感器绑定不正确")
    result, identifiers = {}, set()
    for slot, source in value.items():
        if not isinstance(slot, str) or slot not in EXTERNAL_SLOTS:
            raise ValueError("不支持的外部传感器位置")
        binding = _binding(source)
        if binding["sensor_id"] in identifiers:
            raise ValueError("同一组件不能重复绑定传感器")
        identifiers.add(binding["sensor_id"])
        result[slot] = binding
    return result


def sensor_binding(slot, preferences=None):
    """Unvalidated or missing preferences cannot manufacture a usable channel."""
    if slot not in EXTERNAL_SLOTS or not isinstance(preferences, dict):
        return None
    try:
        return validate_bindings(preferences.get("sensor_bindings", {})).get(slot)
    except ValueError:
        return None


def binding_meta(slot, preferences=None):
    if slot not in EXTERNAL_SLOTS:
        raise ValueError("不支持的外部传感器位置")
    binding = sensor_binding(slot, preferences)
    if binding is None:
        return dict(
            label="未绑定传感器",
            source="external",
            unit="",
            digits=0,
            maximum=100,
            kind="line",
            category="advanced",
            scope=None,
            note="请先选择硬件传感器",
        )
    spec = SENSOR_TYPES[binding["sensor_type"]]
    return dict(
        label=binding["name"],
        source="external",
        unit=spec["unit"],
        digits=spec["digits"],
        maximum=spec["maximum"],
        kind=spec["kind"],
        category="advanced",
        scope=None,
        note=" · ".join(part for part in (PROVIDER, binding["hardware_name"]) if part),
    )


def inventory_display(identifier, channel, preferences=None):
    """Format an already-normalized discovery row without inventing a binding.

    Canonical units, exact identity and numeric/availability checks still apply.
    This does not authorize a row as a saved widget binding.
    """
    if not isinstance(channel, dict) or not isinstance(channel.get("type"), str):
        return "—", ""
    spec = SENSOR_TYPES.get(channel["type"])
    if spec is None:
        return "—", ""
    unit, digits = spec["unit"], spec["digits"]
    value = channel.get("value")
    if (
        not isinstance(identifier, str)
        or not identifier
        or channel.get("id") != identifier
        or channel.get("unit") != unit
        or channel.get("available") is False
        or not _finite(value)
    ):
        value = None
    prefs = preferences if isinstance(preferences, dict) else {}
    if unit == "°C" and prefs.get("temperature_unit") == "F":
        unit = "°F"
        try:
            value = value * 9 / 5 + 32 if value is not None else None
        except OverflowError:
            value = None
    if prefs.get("precision", "auto") != "auto":
        digits = int(prefs["precision"])
    return (f"{value:.{digits}f}" if _finite(value) else "—"), unit


def _unique_ids(rows):
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str):
            continue
        if identifier in seen:
            raise ValueError("硬件传感器标识重复")
        seen.add(identifier)


def parse_snapshot(payload):
    """Normalize a schema-1 dictionary from the bounded stdout transport.

    Headers and duplicate identifiers reject the snapshot. Malformed descriptor rows
    are skipped; malformed numeric cells become None. rejected_count counts affected
    rows, not cells. Genuine None cells are unavailable without being counted as bad.
    Energy input is exclusively mWh, normalized once to Wh for values and extrema.
    This function does not decide freshness; the receiving worker owns that policy.
    """
    if not isinstance(payload, dict):
        raise ValueError("硬件传感器数据格式不正确")
    if type(payload.get("schema")) is not int or payload["schema"] != 1:
        raise ValueError("不支持的硬件传感器数据版本")
    if payload.get("provider") != PROVIDER:
        raise ValueError("不支持的传感器来源")
    version = _text(payload.get("version"), 64)
    diagnostics = {}
    for field in ("skipped_types", "update_errors", "truncated"):
        number = payload.get(field, 0)
        if type(number) is not int or not 0 <= number <= 1_000_000:
            raise ValueError("硬件传感器诊断计数不正确")
        diagnostics[field] = number
    timestamp = payload.get("timestamp")
    if not _finite(timestamp) or not 0 <= timestamp <= MAX_TIMESTAMP:
        raise ValueError("硬件传感器时间不正确")
    hardware_rows, sensor_rows = payload.get("hardware"), payload.get("sensors")
    if (
        not isinstance(hardware_rows, list)
        or len(hardware_rows) > MAX_HARDWARE
        or not isinstance(sensor_rows, list)
        or len(sensor_rows) > MAX_SENSORS
    ):
        raise ValueError("硬件传感器列表不正确")
    _unique_ids(hardware_rows)
    _unique_ids(sensor_rows)
    hardware, hardware_ids, rejected = [], set(), 0
    for row in hardware_rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("硬件描述不正确")
            item = dict(
                id=_text(row.get("id"), 512),
                name=_text(row.get("name"), 128),
                type=_text(row.get("type"), 64),
            )
            parent = row.get("parent_id")
            item["parent_id"] = None if parent is None else _text(parent, 512, empty=True)
        except ValueError:
            rejected += 1
            continue
        hardware.append(item)
        hardware_ids.add(item["id"])
    sensors = {}
    for row in sensor_rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("传感器描述不正确")
            sensor_type = row.get("type")
            if not isinstance(sensor_type, str) or sensor_type not in SENSOR_TYPES:
                raise ValueError("不支持的传感器类型")
            spec = SENSOR_TYPES[sensor_type]
            if row.get("unit") != spec["raw_unit"]:
                raise ValueError("传感器单位不正确")
            item = dict(
                id=_text(row.get("id"), 512),
                name=_text(row.get("name"), 128),
                hardware_id=_text(row.get("hardware_id"), 512),
                hardware_name=_text(row.get("hardware_name"), 128, empty=True),
                hardware_type=_text(row.get("hardware_type"), 64),
                type=sensor_type,
                unit=spec["unit"],
            )
            if item["hardware_id"] not in hardware_ids:
                raise ValueError("传感器所属硬件不存在")
        except ValueError:
            rejected += 1
            continue
        invalid_numeric = False
        for field in ("value", "min", "max"):
            value = row.get(field)
            if value is not None and not _finite(value):
                invalid_numeric = True
                value = None
            elif value is not None:
                value = float(value) / 1000 if sensor_type == "Energy" else float(value)
            item[field] = value
        item["available"] = item["value"] is not None
        if invalid_numeric:
            rejected += 1
        sensors[item["id"]] = item
    return dict(
        schema=1,
        provider=PROVIDER,
        version=version,
        timestamp=float(timestamp),
        hardware=hardware,
        sensors=sensors,
        rejected_count=rejected,
        **diagnostics,
    )
