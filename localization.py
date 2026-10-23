"""Offline UI translations. English is the fallback for less common messages."""

import copy
import re
from pathlib import Path

LANGUAGES = {
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}


def dictionaries():
    path = Path(__file__).with_name("locales.txt")
    out = {key: {} for key in LANGUAGES}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("//"):
            continue
        values = line.split("|")
        if len(values) != 8:
            raise ValueError("Translation row needs eight columns: " + values[0])
        source = values[0]
        for code, value in zip(list(LANGUAGES)[1:], values[1:]):
            out[code][source] = value or values[2]
    return out


MESSAGES = dictionaries()
FALLBACK = {
    "组合指标": "Grouped readings",
    "主指标": "Primary",
    "添加同组指标": "Add a reading to this group",
    "同一组可显示 1–4 项指标，一起拖动并查看详情。": "Show 1–4 readings together. Drag the whole group or open its details.",
    "使用率 · 温度 · 功耗": "Usage · temperature · power",
    "组合未更新，请重试。": "Could not update this group. Try again.",
    "设置分类": "Settings sections",
    "充放电功率表示电池侧的实时功率，未充电时可为 0 W。充电器输入和整机功耗尚无读数。CPU 封装功率未取得，不显示推测值。": "Power is measured at the battery and may be 0 W while plugged in. Charger input, total system power, and CPU package power are not estimated.",
    "设置格式不正确": "Invalid settings format",
    "不支持的设置: ": "Unsupported setting: ",
    "设置超出范围: ": "Setting out of range: ",
    "更新频率不正确": "Invalid refresh interval",
    "开关设置不正确: ": "Invalid switch: ",
    "组件设置不正确": "Invalid widget settings",
    "组件开关不正确": "Invalid widget switch",
    "不支持的数据项": "Unsupported reading",
    "组件尺寸超出范围": "Widget size out of range",
    "不支持的组件皮肤": "Unsupported widget skin",
    "标题最多 12 个字，请勿使用控制字符或 # [ ] =": "Use up to 12 characters; avoid control characters and # [ ] =",
    "自由内容请选择 1–4 项指标": "Choose 1–4 readings for custom contents",
    "不支持的自由内容指标": "Unsupported custom reading",
    "组件内容不能重复": "Readings cannot be duplicated",
    "Rainmeter 尚未安装": "Install Rainmeter first",
    "桌面组件暂时无法应用，请重试": "Could not apply the widgets. Try again.",
    "应用失败，请重试。原有设置仍已保留。": "Could not apply. Your saved settings were kept.",
    "操作未完成，请在组件设置中重试。": "Open widget settings to try again.",
    "本机端口 8776 被其他程序占用，请关闭冲突程序后重试。": "Port 8776 is in use. Close the conflicting app and try again.",
    "启动失败，详细信息已保存在本机 DesktopStats 日志中。": "Startup failed. Details are in the local DesktopStats log.",
}
for code in LANGUAGES:
    if code != "zh-CN":
        for key, value in FALLBACK.items():
            MESSAGES[code].setdefault(key, value)
SORTED_KEYS = sorted(MESSAGES["en"], key=len, reverse=True)
PATTERN = re.compile("|".join(re.escape(key) for key in SORTED_KEYS))


def translate(value, language="zh-CN"):
    if not isinstance(value, str) or language == "zh-CN":
        return value
    messages = MESSAGES.get(language, MESSAGES["en"])
    if value in messages:
        return messages[value]
    return PATTERN.sub(lambda match: messages[match.group()], value)


def best_language(locale_name):
    name = locale_name.lower().replace("_", "-")
    if name.startswith("zh"):
        return "zh-TW" if any(part in name for part in ("tw", "hk", "mo", "hant")) else "zh-CN"
    prefix = name.split("-")[0]
    return prefix if prefix in LANGUAGES else "en"


def metadata(language, modules, metrics, skins, presets):
    def walk(value):
        if isinstance(value, str):
            return translate(value, language)
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value

    result = dict(
        messages=MESSAGES.get(language, {}),
        modules=walk(modules),
        metrics=walk(metrics),
        skins=walk(skins),
        presets=copy.deepcopy(presets),
    )
    for preset in result["presets"].values():
        preset["label"] = translate(preset["label"], language)
        preset["description"] = translate(preset["description"], language)
        preset["config"]["language"] = language
        for widget in preset["config"]["widgets"].values():
            if widget["title"] == "系统状态":
                widget["title"] = translate("系统状态", language)
    return result
