"""Native vector skins; every coordinate and font is rendered at the display DPI."""

import ctypes as c
import math
import winreg
from pathlib import Path

from localization import translate
from metrics import METRICS, variable
from stats_config import BASE, MODULES, ORDER

ROOT = BASE / "skin/DesktopStats"


def display_scale():
    try:
        scale = c.windll.shcore.GetScaleFactorForDevice(0) / 100
        if 1 <= scale <= 5:
            return scale
    except (OSError, AttributeError):
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics") as k:
            return winreg.QueryValueEx(k, "AppliedDPI")[0] / 96
    except OSError:
        return 1


def skin_path():
    path = c.create_unicode_buffer(32768)
    if c.windll.shell32.SHGetFolderPathW(None, 5, None, 0, path):
        raise OSError("Documents folder unavailable")
    return Path(path.value) / "Rainmeter/Skins/DesktopStats"


PRIMARY = {
    "cpu": {"temp": "#CpuTemp#°C", "usage": "#CpuUsage#"},
    "gpu": {"temp": "#GpuTemp#°C", "usage": "#GpuUsage#", "power": "#GpuPower#"},
    "memory": {"percent": "#MemoryPct#", "used": "#MemoryUsed# GB"},
    "vram": {"used": "#VramNumber# GB", "percent": "#VramPercent#"},
    "battery": {"percent": "#BatteryPct#", "voltage": "#BatteryVoltage#"},
    "power": {"watts": "#PowerNumber# W", "voltage": "#BatteryVoltage#"},
}
SECONDARY = {
    "cpu": {
        "usage": "#CpuUsage# 使用率",
        "temp": "#CpuTemp#°C",
        "cores": "#CpuCores# 核 / #CpuThreads# 线程",
    },
    "gpu": {
        "usage_power": "#GpuUsage# · #GpuPower#",
        "usage": "#GpuUsage# 使用率",
        "power": "#GpuPower#",
        "vram": "显存 #Vram#",
    },
    "memory": {"capacity": "#MemoryDetail#", "available": "可用 #MemoryAvailable#"},
    "vram": {"capacity": "共 #VramTotal#"},
    "battery": {"state": "#BatteryStateCN#", "power": "#BatteryPower#"},
    "power": {"state": "#PowerStateCN#", "battery": "电池 #BatteryPct#"},
}
BAR = {
    "cpu": "CpuBar",
    "gpu": "GpuBar",
    "memory": "MemoryBar",
    "vram": "VramBar",
    "battery": "BatteryBar",
    "power": "PowerBar",
}
DEFAULTVARS = dict(
    CpuTemp="--",
    CpuUsage="--",
    CpuBar=0,
    CpuCores="--",
    CpuThreads="--",
    GpuTemp="--",
    GpuUsage="--",
    GpuBar=0,
    GpuPower="--",
    MemoryPct="--",
    MemoryBar=0,
    MemoryDetail="--",
    MemoryAvailable="--",
    MemoryUsed="--",
    Vram="--",
    VramTotal="--",
    VramNumber="--",
    VramPercent="--",
    VramBar=0,
    BatteryPct="--",
    BatteryBar=0,
    BatteryPower="--",
    BatteryVoltage="--",
    PowerNumber="--",
    PowerBar=0,
    PowerState=3,
    BatteryStateCN="等待数据",
    PowerStateCN="等待数据",
    SensorFresh=0,
)
DEFAULTVARS.update({variable(key): "--" for key in METRICS})
DEFAULTVARS.update({variable(key) + "Bar": 0 for key in METRICS})


def rgb(hexc):
    return ",".join(str(int(hexc[i : i + 2], 16)) for i in (1, 3, 5))


class Skin:
    def __init__(self, config):
        self.config = config
        self.tr = lambda value: translate(value, config["language"])
        self.dark = config["theme"] == "dark"
        self.fg = "247,249,252" if self.dark else "28,32,40"
        self.muted = "170,183,201" if self.dark else "94,105,122"
        self.parts = [
            """[Rainmeter]
Update=1000
AccurateText=1
DynamicWindowSize=1
BackgroundMode=2
SolidColor=0,0,0,1
OnRefreshAction=[!ZPos -2]
ContextTitle=组件设置
ContextAction=["http://127.0.0.1:8776/"]

[Metadata]
Name=Desktop Stats
Version=3.0
Information=Native vector desktop widgets. Click to configure.

[Variables]
DataFile="""
            + str(BASE / "state.txt")
            + "\n"
            + "DataInterval="
            + str(config["refresh"])
            + "\n"
            + "".join(f"{k}={self.tr(v)}\n" for k, v in DEFAULTVARS.items())
            + """
[NativeData]
Measure=WebParser
URL=file://#DataFile#
RegExp=(?s)^(.*)$
StringIndex=1
CodePage=65001
UpdateRate=#DataInterval#
LogSubstringErrors=0

[ReadLocal]
Measure=Script
ScriptFile=#ROOTCONFIGPATH#@Resources\\ReadSensors.lua

[PowerStatus]
Measure=Calc
Formula=#PowerState#
DynamicVariables=1
IfCondition=#PowerState#=0
IfTrueAction=[!SetVariable BatteryStateCN "已接电 · 未充电"][!SetVariable PowerStateCN "已接电"]
IfCondition2=#PowerState#=1
IfTrueAction2=[!SetVariable BatteryStateCN "正在充电"][!SetVariable PowerStateCN "充电中"]
IfCondition3=#PowerState#=2
IfTrueAction3=[!SetVariable BatteryStateCN "电池供电"][!SetVariable PowerStateCN "放电中"]
IfCondition4=#PowerState#=3
IfTrueAction4=[!SetVariable BatteryStateCN "等待数据"][!SetVariable PowerStateCN "等待数据"]
"""
        ]
        self.parts[0] = self.parts[0].replace(
            "ContextTitle=组件设置", "ContextTitle=" + self.tr("组件设置")
        )
        for label in (
            "已接电 · 未充电",
            "已接电",
            "正在充电",
            "充电中",
            "电池供电",
            "放电中",
            "等待数据",
        ):
            self.parts[0] = self.parts[0].replace('"' + label + '"', '"' + self.tr(label) + '"')

    def section(self, name, values):
        self.parts.append("\n[" + name + "]\n" + "".join(f"{k}={v}\n" for k, v in values.items()))

    def shape(self, name, commands, extra=None):
        values = {"Meter": "Shape"}
        values.update({("Shape" + (str(i) if i > 1 else "")): v for i, v in enumerate(commands, 1)})
        values.update(extra or {})
        self.section(name, values)

    def surface(self, width, height, scale, style=None, name="Surface", x=0, y=0, inner=False):
        style = style or self.config["skin"]
        factor = {"card": 1, "glass": 0.63, "minimal": 0.13}[style]
        a = round(255 * self.config["opacity"] / 100 * factor)
        fill = "28,33,42" if self.dark else "247,250,254"
        radius = 20 * scale
        commands = []
        if style != "minimal" and not inner:
            commands.append(
                f"Rectangle {x + 5 * scale:.2f},{y + 7 * scale:.2f},{width:.2f},{height:.2f},{radius:.2f} | Fill Color 12,26,48,13 | StrokeWidth 0"
            )
        border = 0 if style == "minimal" else 45 if self.dark else 195 if style == "glass" else 160
        commands.append(
            f"Rectangle {x + 6 * scale:.2f},{y + 5 * scale:.2f},{width:.2f},{height:.2f},{radius:.2f} | Fill Color {fill},{a} | StrokeWidth {0.7 * scale:.2f} | Stroke Color 255,255,255,{border}"
        )
        self.shape(name, commands)

    def text(self, name, x, y, value, size, scale, color=None, extra=None):
        values = {
            "Meter": "String",
            "FontFace": "Segoe UI",
            "FontSize": round(size * scale, 3),
            "FontColor": (color or self.fg) + ",255",
            "AntiAlias": 1,
            "DynamicVariables": 1,
            "X": round(x, 2),
            "Y": round(y, 2),
            "Text": value,
        }
        values.update(extra or {})
        self.section(name, values)

    def icon(self, key, x, y, s, color):
        def rect(a, b, width, height, r=1):
            return f"Rectangle {x + a * s:.2f},{y + b * s:.2f},{width * s:.2f},{height * s:.2f},{r * s:.2f} | Fill Color 0,0,0,0 | Stroke Color {color},255 | StrokeWidth {1.35 * s:.2f}"

        def line(a, b, d, e):
            return f"Line {x + a * s:.2f},{y + b * s:.2f},{x + d * s:.2f},{y + e * s:.2f} | Stroke Color {color},255 | StrokeWidth {1.25 * s:.2f}"

        if key == "battery":
            commands = [rect(0, 3, 14, 10, 2), line(16, 6, 16, 10), rect(3, 6, 7, 4, 0.6)]
        elif key == "power":
            commands = [
                line(10, 0, 2, 9),
                line(2, 9, 8, 9),
                line(8, 9, 6, 17),
                line(6, 17, 15, 6),
                line(15, 6, 9, 6),
                line(9, 6, 10, 0),
            ]
        elif key == "memory":
            commands = [
                rect(0, 4, 17, 10, 2),
                line(4, 7, 4, 11),
                line(8, 7, 8, 11),
                line(12, 7, 12, 11),
                line(3, 14, 3, 17),
                line(8, 14, 8, 17),
                line(13, 14, 13, 17),
            ]
        else:
            commands = [rect(3, 3, 12, 12, 2), rect(6.5, 6.5, 5, 5, 1)]
            for a in (5, 9, 13):
                commands.extend(
                    [line(a, 0, a, 3), line(a, 15, a, 18), line(0, a, 3, a), line(15, a, 18, a)]
                )
        self.shape(key + "Icon", commands)

    def tile(self, key, prefs, x, y, s):
        color = rgb(MODULES[key]["color"])
        style = prefs.get("skin") or self.config["skin"]
        self.icon(key, x + 13 * s, y + 12 * s, s * 0.72, color)
        label = prefs.get("title") or self.tr("充放电" if key == "power" else MODULES[key]["label"])
        self.text(
            key + "Label",
            x + 32 * s,
            y + 11 * s,
            label,
            8,
            s,
            color if style == "minimal" else None,
            extra={"W": round(68 * s, 2), "H": round(17 * s, 2), "ClipString": 2},
        )
        content = prefs.get("content")
        if content and len(content) > 2:
            for i, metric in enumerate(content):
                meta = METRICS[metric]
                self.text(
                    key + "MetricLabel" + str(i),
                    x + 13 * s,
                    y + (36 + 14 * i) * s,
                    self.tr(meta["label"]),
                    7,
                    s,
                    self.muted,
                    extra={"W": round(49 * s, 2), "H": round(14 * s, 2), "ClipString": 2},
                )
                self.text(
                    key + "MetricValue" + str(i),
                    x + 100 * s,
                    y + (35 + 14 * i) * s,
                    "#"
                    + variable(metric)
                    + "#"
                    + ("" if meta["unit"] == "%" else " ")
                    + meta["unit"],
                    8.2,
                    s,
                    extra={"StringAlign": "Right"},
                )
        else:
            value = PRIMARY[key][prefs["primary"]]
            secondary = self.tr(SECONDARY[key].get(prefs["secondary"], ""))
            if content:
                first = METRICS[content[0]]
                value = (
                    "#"
                    + variable(content[0])
                    + "#"
                    + ("" if first["unit"] == "%" else " ")
                    + first["unit"]
                )
                secondary = self.tr(first["label"])
                if len(content) == 2:
                    second = METRICS[content[1]]
                    secondary = (
                        self.tr(second["label"])
                        + " #"
                        + variable(content[1])
                        + "#"
                        + ("" if second["unit"] == "%" else " ")
                        + second["unit"]
                    )
            self.text(
                key + "Value",
                x + 12 * s,
                y + 31 * s,
                value,
                24,
                s,
                extra={"InlinePattern": "°C| GB| W| V", "InlineSetting": f"Size | {10 * s:.3f}"},
            )
            self.text(
                key + "Secondary",
                x + 13 * s,
                y + 75 * s,
                secondary,
                7.4,
                s,
                self.muted,
                extra={"W": round(88 * s, 2), "H": round(16 * s, 2), "ClipString": 2},
            )
        bar = variable(content[0]) + "Bar" if content else BAR[key]
        maximum = METRICS[content[0]]["maximum"] if content else 50 if key == "power" else 100
        kind = (
            METRICS[content[0]]["kind"]
            if content
            else "line"
            if key in ("cpu", "gpu", "power")
            else "bar"
        )
        # Missing samples draw as zero; the displayed reading stays '--'.
        self.section(
            key + "Measure",
            {
                "Measure": "Calc",
                "Formula": "#" + bar + "#",
                "MinValue": 0,
                "MaxValue": maximum,
                "DynamicVariables": 1,
            },
        )
        if prefs["chart"]:
            if kind == "line":
                self.section(
                    key + "Chart",
                    {
                        "Meter": "Line",
                        "MeasureName": key + "Measure",
                        "X": round(x + 13 * s, 2),
                        "Y": round(y + 94 * s, 2),
                        "W": round(86 * s, 2),
                        "H": round(10 * s, 2),
                        "LineCount": 1,
                        "LineColor": color + ",230",
                        "LineWidth": round(1.25 * s, 2),
                        "AntiAlias": 1,
                        "AutoScale": 0,
                    },
                )
            else:
                self.section(
                    key + "Chart",
                    {
                        "Meter": "Bar",
                        "MeasureName": key + "Measure",
                        "X": round(x + 13 * s, 2),
                        "Y": round(y + 98 * s, 2),
                        "W": round(86 * s, 2),
                        "H": round(3 * s, 2),
                        "BarColor": color + ",220",
                        "SolidColor": color + ",30",
                        "BarOrientation": "Horizontal",
                    },
                )
        self.shape(
            key + "Hit",
            [
                f"Rectangle {x:.2f},{y:.2f},{112 * s:.2f},{112 * s:.2f},{18 * s:.2f} | Fill Color 0,0,0,1 | StrokeWidth 0"
            ],
            {
                "LeftMouseUpAction": f'["http://127.0.0.1:8776/?widget={key}"]',
                "ToolTipText": label + self.tr(" · 点击设置 · 拖动调整位置"),
            },
        )

    def write(self, folder):
        target = ROOT / folder / "Widget.ini"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(self.parts), encoding="utf-16")


def build(config):
    resources = ROOT / "@Resources"
    resources.mkdir(parents=True, exist_ok=True)
    stale_keys = ",".join(
        "'" + key + "'"
        for key in DEFAULTVARS
        if key not in ("PowerState", "BatteryStateCN", "PowerStateCN", "SensorFresh")
    )
    (resources / "ReadSensors.lua").write_text(
        r"""function Update()
    -- Rainmeter's native reader handles Unicode Windows paths; Lua 5.1 io.open
    -- uses the ANSI filesystem API and fails for UTF-8 paths on many systems.
    local reader = SKIN:GetMeasure('NativeData')
    local text = reader and reader:GetStringValue() or ''
    local epoch = 0
    for key,value in text:gmatch('([^=\r\n]+)=([^\r\n]*)') do
        SKIN:Bang('!SetVariable', key, value)
        if key == 'SampleEpoch' then epoch = tonumber(value) or 0 end
    end
    if os.time()-epoch > 35 or epoch-os.time() > 5 then
        for _,key in ipairs({$STALE_KEYS$}) do
            SKIN:Bang('!SetVariable', key, key:match('Bar$') and '0' or '--')
        end
        SKIN:Bang('!SetVariable','PowerState','3')
        return 0
    end
    return 1
end
""".replace("$STALE_KEYS$", stale_keys),
        encoding="ascii",
    )
    dpi = display_scale()
    enabled = [k for k in ORDER if config["visible"] and config["widgets"][k]["enabled"]]
    grouped = [
        k
        for k in enabled
        if config["mode"] == "combined"
        or (config["mode"] == "mixed" and config["widgets"][k]["grouped"])
    ]
    active = []
    for key in ORDER:
        prefs = config["widgets"][key]
        s = (prefs["size"] or config["size"]) / 112 * dpi
        panel = Skin(config)
        panel.surface(112 * s, 112 * s, s, style=prefs.get("skin"))
        panel.tile(key, prefs, 6 * s, 5 * s, s)
        panel.write(key)
        if key in enabled and key not in grouped:
            active.append(
                dict(
                    id=key,
                    config="DesktopStats\\" + key,
                    width=math.ceil(124 * s),
                    height=math.ceil(124 * s),
                )
            )
    if grouped:
        cols = min(config["group_columns"], len(grouped))
        rows = math.ceil(len(grouped) / cols)
        sizes = [(config["widgets"][k]["size"] or config["size"]) * dpi for k in grouped]
        widths = [max(sizes[i] for i in range(j, len(grouped), cols)) for j in range(cols)]
        heights = [max(sizes[i : i + cols]) for i in range(0, len(grouped), cols)]
        gap = 4 * dpi
        pad = 6 * dpi
        width = sum(widths) + (cols - 1) * gap
        height = sum(heights) + (rows - 1) * gap
        panel = Skin(config)
        panel.surface(width, height, dpi)
        for i, key in enumerate(grouped):
            col, row = i % cols, i // cols
            x = pad + sum(widths[:col]) + col * gap
            y = 5 * dpi + sum(heights[:row]) + row * gap
            s = sizes[i] / 112
            prefs = config["widgets"][key]
            if prefs.get("skin") and prefs["skin"] != config["skin"]:
                panel.surface(
                    108 * s,
                    108 * s,
                    s,
                    style=prefs["skin"],
                    name=key + "Surface",
                    x=x - 4 * s,
                    y=y - 3 * s,
                    inner=True,
                )
            panel.tile(key, prefs, x, y, s)
        panel.write("Group")
        active.insert(
            0,
            dict(
                id="Group",
                config="DesktopStats\\Group",
                width=math.ceil(width + pad * 2),
                height=math.ceil(height + pad * 2),
            ),
        )
    return active
