"""Validated, opt-in top bar preferences. Importing performs no native operations."""

import copy
import math
import re
import unicodedata

from external_sensor import EXTERNAL_SLOTS, validate_bindings
from metrics import METRICS
from top_bar_layout import DISPLAY_STYLES
from top_bar_profiles import paired_channels

APPEARANCE_DEFAULTS = dict(follow_global=True, skin="glass", glass_transparency=50.0)


def top_bar_style(config):
    """Resolve bar-only coatings without mutating global/widget preferences."""
    style = {
        key: copy.deepcopy(config[key])
        for key in ("skin", "theme", "language", "opacity", "glass_transparency", "glass_curvature")
        if key in config
    }
    appearance = config.get("top_bar", {}).get("appearance", APPEARANCE_DEFAULTS)
    if not appearance.get("follow_global", True):
        style.update(skin=appearance["skin"], glass_transparency=appearance["glass_transparency"])
    # Bare text is useful on desktop cards, but a reserved menu bar needs a
    # readable material so the entire native band has a visible affordance.
    if style.get("skin") == "minimal":
        style["skin"] = "glass"
    return style


def default_top_bar():
    return dict(
        enabled=False,
        monitor_mode="primary",
        screens=[],
        height=32,
        spacing=12,
        appearance=copy.deepcopy(APPEARANCE_DEFAULTS),
        items=[
            dict(
                id="b_" + metric,
                metric=metric,
                prefs={"sensor_bindings": {}, "placement": "right", "style": "label_value"},
            )
            for metric in (
                "cpu_usage",
                "gpu_usage",
                "ram_percent",
                "cpu_temp",
                "gpu_power",
                "battery_percent",
            )
        ],
    )


def _target(value):
    if (
        not isinstance(value, str)
        or len(value) > 200
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError("不支持的设备或显示器")
    return value


def validate_top_bar(value):
    if not isinstance(value, dict) or set(value) - {
        "enabled",
        "monitor_mode",
        "screens",
        "height",
        "spacing",
        "items",
        "appearance",
    }:
        raise ValueError("顶部栏设置不正确")
    out = default_top_bar()
    if "appearance" in value:
        appearance = value["appearance"]
        if not isinstance(appearance, dict) or set(appearance) - set(APPEARANCE_DEFAULTS):
            raise ValueError("顶部栏材质设置不正确")
        appearance = dict(APPEARANCE_DEFAULTS, **appearance)
        if type(appearance["follow_global"]) is not bool:
            raise ValueError("顶部栏材质开关不正确")
        if appearance["skin"] not in ("glass", "frost", "tint", "card", "graphite"):
            raise ValueError("不支持的顶部栏材质")
        level = appearance["glass_transparency"]
        if type(level) not in (int, float) or not 0 <= level <= 100 or not math.isfinite(level):
            raise ValueError("顶部栏透明度应为 0–100%")
        out["appearance"] = appearance
    if "enabled" in value:
        if type(value["enabled"]) is not bool:
            raise ValueError("顶部栏开关不正确")
        out["enabled"] = value["enabled"]
    if "monitor_mode" in value:
        if value["monitor_mode"] not in ("primary", "all", "selected"):
            raise ValueError("顶部栏显示器设置不正确")
        out["monitor_mode"] = value["monitor_mode"]
    if "height" in value:
        if type(value["height"]) is not int or value["height"] not in (28, 32, 40):
            raise ValueError("顶部栏高度不正确")
        out["height"] = value["height"]
    if "spacing" in value:
        spacing = value["spacing"]
        if type(spacing) not in (int, float) or not 4 <= spacing <= 24:
            raise ValueError("顶部栏间距应为 4–24 px")
        out["spacing"] = spacing
    if "screens" in value:
        screens = value["screens"]
        if not isinstance(screens, list) or len(screens) > 16:
            raise ValueError("顶部栏显示器设置不正确")
        out["screens"] = [_target(screen) for screen in screens]
        if any(not screen for screen in screens) or len(set(screens)) != len(screens):
            raise ValueError("顶部栏显示器设置不正确")
    if "items" not in value:
        return out
    items = value["items"]
    if not isinstance(items, list) or len(items) > 64:
        raise ValueError("顶部栏最多添加 64 项指标")
    out["items"], identifiers = [], set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "metric", "prefs"}:
            raise ValueError("顶部栏指标设置不正确")
        identifier, metric, source = item["id"], item["metric"], item["prefs"]
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"b_[a-z0-9_]{1,46}", identifier)
            or identifier in identifiers
        ):
            raise ValueError("顶部栏指标标识不正确")
        if not isinstance(metric, str) or metric not in METRICS or not isinstance(source, dict):
            raise ValueError("顶部栏指标设置不正确")
        identifiers.add(identifier)
        if source.get('style') in ('duplex', 'duplex_inline') and not paired_channels(metric):
            raise ValueError('该指标没有可配对的双向读数')
        prefs = {}
        for field, options in (
            ("precision", ("auto", "0", "1", "2")),
            ("temperature_unit", ("C", "F")),
            ("network_unit", ("MBps", "Mbps")),
        ):
            if field in source:
                if source[field] not in options:
                    raise ValueError("不支持的顶部栏显示格式")
                prefs[field] = source[field]
        for field, options, default in (
            ("placement", ("left", "right"), "right"),
            ("style", DISPLAY_STYLES, "label_value"),
        ):
            selected = source.get(field, default)
            if selected not in options:
                raise ValueError("不支持的顶部栏显示样式")
            prefs[field] = selected
        for field in (
            "gpu_target",
            "network_target",
            "disk_target",
            "volume_target",
            "storage_target",
        ):
            if field in source:
                prefs[field] = _target(source[field])
        prefs["sensor_bindings"] = validate_bindings(source.get("sensor_bindings", {}))
        if metric in EXTERNAL_SLOTS:
            if set(prefs["sensor_bindings"]) != {metric}:
                raise ValueError("请先绑定外部传感器")
        elif prefs["sensor_bindings"]:
            raise ValueError("顶部栏指标与传感器绑定不一致")
        unknown = set(source) - set(prefs)
        if unknown:
            raise ValueError("不支持的顶部栏指标设置")
        out["items"].append(dict(id=identifier, metric=metric, prefs=copy.deepcopy(prefs)))
    return out
