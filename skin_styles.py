"""Shared material palette for desktop windows and their native previews."""

import math

from widget_catalog import GLASS_DEFAULTS

SKINS = {
    "glass": "清透玻璃",
    "frost": "柔雾玻璃",
    "tint": "柔彩玻璃",
    "card": "经典卡片",
    "graphite": "石墨黑",
    "minimal": "极简数字",
}
GLASS_SKINS = frozenset(("glass", "frost", "tint"))


def effective_skin(config, key=None):
    prefs = config.get("widgets", {}).get(key, {})
    return prefs.get("skin") or config.get("skin", "glass")


def _percentage(value, default=50.0):
    if type(value) not in (int, float):
        return default
    try:
        number = float(value)
    except OverflowError:
        return default
    return max(0.0, min(100.0, number)) if math.isfinite(number) else default


def glass_options(config, key=None):
    """Resolve per-field widget overrides without importing preference state."""
    prefs = config.get("widgets", {}).get(key, {})
    result = {}
    for option in ("transparency", "curvature"):
        name = "glass_" + option
        global_value = _percentage(config.get(name, GLASS_DEFAULTS[name]), GLASS_DEFAULTS[name])
        value = prefs.get(name)
        result[option] = global_value if value is None else _percentage(value, global_value)
    return result


def _main_window_alpha(transparency, anchor):
    """Continuous coating alpha with the accepted settings appearance at 50%."""
    value = _percentage(transparency)
    if value <= 50:
        return round(255 + (anchor - 255) * value / 50)
    return round(anchor * (100 - value) / 50)


def palette(skin, dark=False, opacity=94, accent="#2884ff", frosted=True, *, transparency=None, curvature=None):
    """ARGB coatings, not proof that the compositor has blurred a window.

    ``frosted`` selects a translucent coating or the readable solid fallback.
    Native verification belongs to the material report. Minimal paints nothing.
    """
    dark = dark or skin == "graphite"
    ink, muted = ("#f4f6f9", "#b8c2cf") if dark else ("#202833", "#566272")
    level = max(45, min(100, opacity))
    rgb = (24, 29, 37) if dark else (249, 252, 255)
    if skin == "glass":
        alpha = 194 if dark else 158
    elif skin == "frost":
        alpha = round(92 + level * 0.82)
        rgb = (35, 40, 47) if dark else (246, 248, 250)
    elif skin == "tint":
        alpha = round(48 + level * 0.64)
        try:
            color = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5))
            if len(accent) != 7:
                raise ValueError
        except (TypeError, ValueError):
            color = (40, 132, 255)
        weight = 0.32 if frosted else 0.12
        rgb = tuple(round(a * (1 - weight) + b * weight) for a, b in zip(rgb, color))
    elif skin == "minimal":
        alpha = 0
    else:
        alpha = 250
    if skin in GLASS_SKINS and not frosted:
        alpha = 255
    if skin == "graphite":
        rgb = (29, 33, 40)

    radius = 18.0
    if skin in GLASS_SKINS:
        if frosted and transparency is not None and skin != "glass":
            transmission = _percentage(transparency) / 100
            # A continuous material response with opaque/clear shared endpoints.
            response = {"frost": .6, "tint": 1.25}[skin]
            alpha = round(255 * (1 - transmission) ** response)
        if curvature is not None:
            radius = 6 + _percentage(curvature) * .24

    def argb(alpha, components):
        return "#" + f"{alpha:02x}" + "".join(f"{c:02x}" for c in components)

    transparent = skin == "minimal"
    edge_top = "#45ffffff" if dark else "#a8ffffff"
    edge_bottom = "#18ffffff" if dark else "#1a172b42"
    top_alpha = alpha
    top_rgb = tuple(min(255, c + 3) for c in rgb)
    if skin == "glass":
        # Reuse Theme.qml's accepted window/ink/line colors. This is an alpha
        # coating only; no compositor, blur, window opacity or second surface.
        top_rgb = rgb = (36, 36, 38) if dark else (255, 255, 255)
        ink, muted = ("#f5f6f8", "#b8bdc7") if dark else ("#1f242b", "#303945")
        edge_top = edge_bottom = "#1cffffff" if dark else "#13000000"
        if frosted:
            value = GLASS_DEFAULTS["glass_transparency"] if transparency is None else transparency
            top_alpha = alpha = _main_window_alpha(value, 214 if dark else 163)
    return {
        "top": argb(top_alpha, top_rgb),
        "bottom": argb(alpha, rgb),
        "border": "#00000000" if transparent else edge_top,
        "edge_top": "#00000000" if transparent else edge_top,
        "edge_bottom": "#00000000" if transparent else edge_bottom,
        "radius": radius,
        "ink": ink,
        "muted": muted,
        "transparent": transparent,
    }
