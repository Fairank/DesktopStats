"""Validated local preferences, with ordered, independent widget instances."""

import copy
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

from external_sensor import EXTERNAL_SLOTS, validate_bindings
from localization import LANGUAGES
from metrics import METRICS
from profile_paths import resolve_profile_paths
from skin_styles import SKINS
from top_bar_config import default_top_bar, validate_top_bar
from widget_catalog import GLASS_DEFAULTS, MODULES, TEMPLATES, from_template, widget_defaults

ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PROFILE_PATHS = resolve_profile_paths()
BASE = PROFILE_PATHS.directory
IPC_PROFILE_KEY = PROFILE_PATHS.ipc_key
BASE.mkdir(parents=True, exist_ok=True)
CONFIG = BASE / "preferences.json"
BACKUP = BASE / "preferences.backup.json"
ORDER = [
    "cpu",
    "gpu",
    "memory",
    "vram",
    "battery",
    "power",
]  # Legacy template keys, not the instance order.
MAX_WIDGETS = 24
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
DEFAULT = dict(
    version=8,
    theme="light",
    language="zh-CN",
    skin="glass",
    opacity=94,
    **GLASS_DEFAULTS,
    size=88,
    mode="separate",
    layout="grid",
    group_columns=2,
    locked=False,
    visible=True,
    autostart=False,
    refresh=2,
    history_enabled=True,
    top_bar=default_top_bar(),
    magnet_enabled=False,
    magnet_gap=12,
    magnet_bounce=True,
    reflow_on_resize=True,
    widget_order=[key for key in ORDER if key != "vram"],
    widgets={
        key: dict(
            from_template("power") if key == "power" else widget_defaults(key),
            enabled=key != "vram",
        )
        for key in ORDER
    },
)


def valid_id(key):
    return (
        isinstance(key, str)
        and ID_PATTERN.fullmatch(key) is not None
        and key not in ("group", "settings")
    )


def _glass_value(value, field, *, inherit=False):
    if inherit and value is None:
        return None
    if type(value) not in (int, float) or not 0 <= value <= 100 or not math.isfinite(value):
        raise ValueError("设置超出范围: " + field)
    return float(value)


def validate(value):
    if not isinstance(value, dict):
        raise ValueError("设置格式不正确")
    value = copy.deepcopy(value)
    version = value.get("version", 4)
    if type(version) is not int or not 1 <= version <= 8:
        raise ValueError("不支持的设置版本")
    legacy = version < 5
    out = copy.deepcopy(DEFAULT)
    out["top_bar"] = validate_top_bar(value.get("top_bar", out["top_bar"]))
    if value.get("theme") == "glass":
        value["theme"] = "light"
        value.setdefault("skin", "glass")
    for key, options in [
        ("theme", ("light", "dark")),
        ("language", tuple(LANGUAGES)),
        ("skin", tuple(SKINS)),
        ("mode", ("separate", "combined", "mixed")),
        ("layout", ("row", "column", "grid")),
    ]:
        if key in value:
            if not isinstance(value[key], str) or value[key] not in options:
                raise ValueError("不支持的设置: " + key)
            out[key] = value[key]
    for key, lo, hi in [
        ("opacity", 45, 100),
        ("size", 76, 180),
        ("group_columns", 1, 3),
        ("magnet_gap", 0, 64),
    ]:
        if key in value:
            number = value[key]
            if type(number) is not int or not lo <= number <= hi:
                raise ValueError("设置超出范围: " + key)
            out[key] = number
    for key in GLASS_DEFAULTS:
        if key in value:
            out[key] = _glass_value(value[key], key)
    if "refresh" in value:
        interval = value["refresh"]
        if version < 6 and type(interval) in (int, float) and interval == 10:
            interval = 5
        if (
            type(interval) not in (int, float)
            or not math.isfinite(interval)
            or not 0.01 <= interval <= 5
        ):
            raise ValueError("更新频率不正确")
        hundredths = round(interval * 100)
        if not math.isclose(interval * 100, hundredths, rel_tol=0, abs_tol=1e-7):
            raise ValueError("更新频率不正确")
        out["refresh"] = hundredths // 100 if hundredths % 100 == 0 else hundredths / 100
    for key in (
        "locked",
        "visible",
        "autostart",
        "history_enabled",
        "reflow_on_resize",
        "magnet_enabled",
        "magnet_bounce",
    ):
        if key in value:
            if type(value[key]) is not bool:
                raise ValueError("开关设置不正确: " + key)
            out[key] = value[key]
    widgets = value.get("widgets", {})
    if not isinstance(widgets, dict) or len(widgets) > MAX_WIDGETS + len(ORDER):
        raise ValueError("组件设置不正确")
    if legacy:
        widgets = {
            key: dict(dict(widget_defaults(key), enabled=key != "vram"), **widgets.get(key, {}))
            if isinstance(widgets.get(key, {}), dict)
            else widgets[key]
            for key in ORDER
        }
    elif "widgets" not in value:
        widgets = copy.deepcopy(DEFAULT["widgets"])
    out["widgets"] = {}
    for key, source in widgets.items():
        if not valid_id(key) or not isinstance(source, dict):
            raise ValueError("组件设置不正确")
        kind = source.get("kind", key)
        if not isinstance(kind, str) or kind not in MODULES:
            raise ValueError("不支持的组件类型")
        prefs = widget_defaults(kind)
        meta = MODULES[kind]
        for field in ("enabled", "chart", "grouped", "show_title"):
            if field in source:
                if type(source[field]) is not bool:
                    raise ValueError("组件开关不正确")
                prefs[field] = source[field]
        for field in ("primary", "secondary"):
            if field in source:
                if not isinstance(source[field], str) or source[field] not in meta[field]:
                    raise ValueError("不支持的数据项")
                prefs[field] = source[field]
        size = source.get("size")
        if size is not None and (type(size) is not int or not 76 <= size <= 180):
            raise ValueError("组件尺寸超出范围")
        prefs["size"] = size
        skin = source.get("skin")
        if skin is not None and (not isinstance(skin, str) or skin not in SKINS):
            raise ValueError("不支持的组件皮肤")
        prefs["skin"] = skin
        for field in GLASS_DEFAULTS:
            prefs[field] = _glass_value(source.get(field), field, inherit=True)
        prefs["sensor_bindings"] = validate_bindings(source.get("sensor_bindings", {}))
        title = source.get("title", "")
        if (
            not isinstance(title, str)
            or len(title) > 12
            or any(ch in "#[]=" or unicodedata.category(ch).startswith("C") for ch in title)
        ):
            raise ValueError("标题最多 12 个字，请勿使用控制字符或 # [ ] =")
        prefs["title"] = title.strip()
        content = source.get("content")
        if content is not None:
            if not isinstance(content, list) or not 1 <= len(content) <= (4 if legacy else 6):
                raise ValueError("自由内容请选择 1–6 项指标")
            if any(not isinstance(item, str) or item not in METRICS for item in content):
                raise ValueError("不支持的自由内容指标")
            if len(set(content)) != len(content):
                raise ValueError("组件内容不能重复")
            if any(
                item in EXTERNAL_SLOTS and item not in prefs["sensor_bindings"] for item in content
            ):
                raise ValueError("请先绑定外部传感器")
        prefs["content"] = content
        for field, lo, hi in (("width", 80, 4096), ("height", 32, 2160)):
            number = source.get(field)
            if number is not None and (type(number) is not int or not lo <= number <= hi):
                raise ValueError("组件尺寸超出范围")
            prefs[field] = number
        columns = source.get("columns", 2)
        if type(columns) is not int or not 1 <= columns <= 6:
            raise ValueError("布局列数不正确")
        prefs["columns"] = columns
        for field, options in [
            ("presentation", ("auto", "hero", "list", "ring", "bar", "cores")),
            ("form", ("square", "wide", "free", "bar")),
            ("layout_mode", ("auto", "horizontal", "vertical", "grid", "manual")),
            ("dock", ("free", "top")),
            ("layer", ("desktop", "pinned")),
            ("precision", ("auto", "0", "1", "2")),
            ("temperature_unit", ("C", "F")),
            ("network_unit", ("MBps", "Mbps")),
        ]:
            if field in source:
                if not isinstance(source[field], str) or source[field] not in options:
                    raise ValueError("不支持的设置: " + field)
                prefs[field] = source[field]
        positions = source.get("metric_positions", {})
        if not isinstance(positions, dict) or len(positions) > 6:
            raise ValueError("指标位置不正确")
        if any(metric not in (content or []) for metric in positions):
            raise ValueError("指标位置不正确")
        if prefs["layout_mode"] == "manual" and (not content or set(positions) != set(content)):
            raise ValueError("每个指标都需要手动位置")
        normalized = {}
        for metric, rect in positions.items():
            if not isinstance(rect, dict) or set(rect) != {"x", "y", "width", "height"}:
                raise ValueError("指标位置不正确")
            if any(
                type(number) not in (int, float) or not math.isfinite(number)
                for number in rect.values()
            ):
                raise ValueError("指标位置不正确")
            x, y, width, height = (float(rect[field]) for field in ("x", "y", "width", "height"))
            if (
                x < 0
                or y < 0
                or width <= 0
                or height <= 0
                or x + width > 1 + 1e-8
                or y + height > 1 + 1e-8
            ):
                raise ValueError("指标超出内容区")
            normalized[metric] = dict(x=x, y=y, width=width, height=height)
        rects = list(normalized.values())
        for index, rect in enumerate(rects):
            if any(
                min(rect["x"] + rect["width"], other["x"] + other["width"])
                - max(rect["x"], other["x"])
                > 1e-8
                and min(rect["y"] + rect["height"], other["y"] + other["height"])
                - max(rect["y"], other["y"])
                > 1e-8
                for other in rects[index + 1 :]
            ):
                raise ValueError("指标不能重叠")
        prefs["metric_positions"] = normalized
        screen = source.get("screen_target", "")
        if (
            not isinstance(screen, str)
            or len(screen) > 200
            or any(unicodedata.category(ch).startswith("C") for ch in screen)
        ):
            raise ValueError("不支持的显示器")
        prefs["screen_target"] = screen
        for field in ("network_target", "disk_target", "volume_target", "gpu_target", "storage_target"):
            target = source.get(field, prefs[field])
            if (
                not isinstance(target, str)
                or len(target) > 200
                or any(unicodedata.category(ch).startswith("C") for ch in target)
            ):
                raise ValueError("不支持的设备")
            prefs[field] = target
        template = source.get("template", prefs["template"])
        if not isinstance(template, str) or template not in TEMPLATES:
            raise ValueError("不支持的组件模板")
        prefs["template"] = template
        if prefs["presentation"] == "cores" and kind != "cpu":
            raise ValueError("每核负载仅适用于处理器")
        out["widgets"][key] = prefs
    if legacy:
        # Previous versions stored every hardware tab, including unused ones.
        order = [key for key in ORDER if out["widgets"][key]["enabled"]]
    else:
        order = value.get("widget_order", list(out["widgets"]))
    if (
        not isinstance(order, list)
        or len(order) > MAX_WIDGETS
        or any(not valid_id(k) or k not in out["widgets"] for k in order)
        or len(set(order)) != len(order)
    ):
        raise ValueError("组件顺序不正确")
    out["widget_order"] = order
    # Schema-valid normalized rectangles must also fit the renderer's supported
    # readable dimensions, including dormant widgets and title changes.
    from responsive_layout import dimensions

    for key in out["widgets"]:
        dimensions(out, key)
    return out


def load():
    for path in (CONFIG, BACKUP):
        try:
            return validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
    return copy.deepcopy(DEFAULT)


def save(config):
    config = validate(config)
    try:
        prior = validate(json.loads(CONFIG.read_text(encoding="utf-8")))
        temporary = BACKUP.with_suffix(".tmp")
        temporary.write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(BACKUP)
    except (OSError, ValueError, TypeError):
        pass
    temporary = CONFIG.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CONFIG)
