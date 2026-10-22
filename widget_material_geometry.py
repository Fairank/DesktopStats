"""Rounded widget backdrop footprints, matching the existing vector painter.

Coordinates are Qt window logical pixels. QWindow.setMask handles monitor DPI;
no desktop pixels are read and no native window style is changed here.
"""

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QRegion

from material_policy import render_policy
from responsive_layout import is_responsive
from skin_styles import effective_skin, glass_options, palette


def backdrop_shapes(config, spec, width, height):
    """Return only painted rounded footprints; mixed bare digits stay unmasked."""
    if not all(
        type(value) in (int, float) and math.isfinite(value) and value > 0
        for value in (width, height, spec.get("width"), spec.get("height"))
    ):
        return ()
    policy = render_policy(config, spec)
    if not policy["backdrop"]:
        return ()
    dark = config.get("theme") == "dark"

    def radius(skin, options):
        return palette(skin, dark, config.get("opacity", 94), **options)["radius"]

    if policy["panel_skin"]:
        rounded = radius(policy["panel_skin"], policy["panel_options"])
        return ((0, 0, width, height, min(rounded, width / 2, height / 2)),)
    result = []
    sx, sy = width / spec["width"], height / spec["height"]
    for cell in spec.get("cells", []):
        key = cell["key"]
        prefs = config.get("widgets", {}).get(key, {})
        skin = effective_skin(config, key)
        if skin == "minimal":
            continue
        cw, ch = cell["width"] * sx, cell["height"] * sy
        rounded = radius(skin, glass_options(config, key))
        if not is_responsive(prefs):
            rounded *= ch / 160
        result.append((cell["x"] * sx, cell["y"] * sy, cw, ch, min(rounded, cw / 2, ch / 2)))
    return tuple(result)


def rounded_mask(shapes):
    """Empty region removes the native mask; disjoint cards keep clear gaps."""
    region = QRegion()
    for x, y, width, height, radius in shapes:
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, width, height), radius, radius)
        region = region.united(QRegion(path.toFillPolygon().toPolygon()))
    return region
