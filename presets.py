"""Opinionated starting layouts; users can edit every field after choosing one."""

from copy import deepcopy

from stats_config import DEFAULT, validate

CATALOG_INFO = {
    "compact": dict(label="经典桌面", description="五块迷你卡片"),
    "overview": dict(label="单块总览", description="四项指标，一块玻璃"),
    "detailed": dict(label="详细监测", description="六类硬件组合面板"),
    "light": dict(label="轻量桌面", description="精简内容，不主动读取独显"),
}


def catalogue():
    compact = deepcopy(DEFAULT)
    overview = deepcopy(DEFAULT)
    for widget in overview["widgets"].values():
        widget["enabled"] = False
    overview.update(size=112, skin="glass")
    overview["widgets"]["cpu"].update(
        enabled=True,
        title="系统状态",
        content=["cpu_temp", "gpu_temp", "ram_percent", "battery_watts"],
    )
    detailed = deepcopy(DEFAULT)
    detailed.update(mode="combined", size=112, group_columns=3)
    detailed["widget_order"] = list(detailed["widgets"])
    for widget in detailed["widgets"].values():
        widget["enabled"] = True
    light = deepcopy(DEFAULT)
    light.update(skin="minimal", refresh=5)
    light["widgets"]["cpu"].update(primary="usage", secondary="cores")
    light["widgets"]["gpu"]["enabled"] = False
    light["widgets"]["power"]["enabled"] = False
    for config in (compact, overview, detailed, light):
        config["widget_order"] = [
            key for key, prefs in config["widgets"].items() if prefs["enabled"]
        ]
    configurations = dict(compact=compact, overview=overview, detailed=detailed, light=light)
    return {
        key: dict(CATALOG_INFO[key], config=validate(config))
        for key, config in configurations.items()
    }
