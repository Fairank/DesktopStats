"""DPI-independent native widget layout and resilient desktop positions."""

import json
import math
from copy import deepcopy
from pathlib import Path

from responsive_layout import dimensions, is_responsive, minimum_dimensions
from stats_config import BASE, ORDER, valid_id

POSITIONS = BASE / "positions.json"


class LayoutCapacityError(ValueError):
    """The work area cannot fit selected cards at their readable size."""


def dense_floor(spec):
    floors = spec.get("minimum_edges", {})
    return max(
        (floors.get(cell["key"], 0) / cell["height"] for cell in spec.get("cells", [])), default=0
    )


def minimum_size(config, key):
    """Five or six readings need more room than a three-channel mini card."""
    return 88 if len(config["widgets"][key].get("content") or []) >= 5 else 76


def effective_size(config, key):
    return max(minimum_size(config, key), config["widgets"][key].get("size") or config["size"])


def edge(config, key):
    return round(effective_size(config, key) * 1.5)


def windows(config):
    enabled = [
        key for key in config.get("widget_order", ORDER) if config["widgets"][key]["enabled"]
    ]
    mode = config["mode"]
    grouped = [
        key
        for key in enabled
        if (mode == "combined" or (mode == "mixed" and config["widgets"][key]["grouped"]))
        and config["widgets"][key].get("dock", "free") == "free"
        and config["widgets"][key].get("form") != "bar"
        and config["widgets"][key].get("layer", "desktop") == "desktop"
        and not config["widgets"][key].get("screen_target")
    ]
    result = []
    if grouped:
        columns = min(config["group_columns"], len(grouped))
        sizes = [dimensions(config, key) for key in grouped]
        widths, heights = [size[0] for size in sizes], [size[1] for size in sizes]
        column_widths = [max(widths[i::columns]) for i in range(columns)]
        row_heights = [max(heights[i : i + columns]) for i in range(0, len(grouped), columns)]
        cells = [
            dict(
                key=key,
                x=12 + sum(column_widths[: i % columns]) + i % columns * 8,
                y=12 + sum(row_heights[: i // columns]) + i // columns * 8,
                width=widths[i],
                height=heights[i],
            )
            for i, key in enumerate(grouped)
        ]
        result.append(
            dict(
                id="group",
                width=24 + sum(column_widths) + (columns - 1) * 8,
                height=24 + sum(row_heights) + (len(row_heights) - 1) * 8,
                cells=cells,
                columns=columns,
            )
        )
    for key in enabled:
        if key not in grouped:
            width, height = dimensions(config, key)
            prefs = config["widgets"][key]
            result.append(
                dict(
                    id=key,
                    width=width,
                    height=height,
                    cells=[dict(key=key, x=0, y=0, width=width, height=height)],
                    dock=prefs.get("dock", "free"),
                    layer=prefs.get("layer", "desktop"),
                    screen_target=prefs.get("screen_target", ""),
                )
            )
    for spec in result:
        spec["minimum_edges"] = {
            cell["key"]: minimum_dimensions(config["widgets"][cell["key"]], cell["width"])[1]
            for cell in spec["cells"]
        }
        spec["responsive"] = any(
            is_responsive(config["widgets"][cell["key"]]) for cell in spec["cells"]
        )
        spec["preferences"] = {
            cell["key"]: deepcopy(config["widgets"][cell["key"]]) for cell in spec["cells"]
        }
    return result


def read_positions(path=POSITIONS):
    try:
        if Path(path).stat().st_size > 65536:
            return {}
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return {
            key: [int(n) for n in point]
            for key, point in value.items()
            if (key in ORDER + ["group", "settings"] or (valid_id(key) and key.startswith("w_")))
            and isinstance(point, list)
            and len(point) == 2
            and all(type(n) in (float, int) and math.isfinite(n) and abs(n) < 100000 for n in point)
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def constrain(spec, width, height):
    if spec.get("responsive") and len(spec.get("cells", [])) == 1:
        result = deepcopy(spec)
        cell = result["cells"][0]
        prefs = result["preferences"][cell["key"]]
        new_width = min(cell["width"], max(80, int(width - 36)))
        minimum_width, minimum_height = minimum_dimensions(prefs, new_width)
        if new_width < minimum_width or minimum_height > height - 36:
            raise LayoutCapacityError("Work area cannot fit the responsive content")
        new_height = max(minimum_height, min(cell["height"], int(height - 36)))
        cell.update(width=new_width, height=new_height)
        result.update(width=new_width, height=new_height)
        result["minimum_edges"][cell["key"]] = minimum_height
        return result
    ratio = min(1, max(1, width - 36) / spec["width"], max(1, height - 36) / spec["height"])
    if ratio + 1e-9 < dense_floor(spec):
        raise LayoutCapacityError("Dense card would be smaller than its readable minimum")
    if ratio >= 1:
        return spec
    result = deepcopy(spec)
    for item in [result, *result["cells"]]:
        for key in ("x", "y", "width", "height"):
            if key in item:
                item[key] = round(item[key] * ratio)
    for cell in result["cells"]:
        prefs = result.get("preferences", {}).get(cell["key"])
        if prefs and is_responsive(prefs):
            minimum_width, minimum_height = minimum_dimensions(prefs, cell["width"])
            if cell["width"] < minimum_width or cell["height"] < minimum_height:
                raise LayoutCapacityError("Group would hide responsive content at this size")
    return result


def grid_plan(specs, width, height, layout="grid", gap=10):
    """Pack variable-size cards without overlaps; wrap/fit to the work area."""
    if not specs:
        return [], []
    desired = 1 if layout == "column" else len(specs) if layout == "row" else 2
    candidates = []
    for columns in range(1, len(specs) + 1):
        column_widths = [max(item["width"] for item in specs[i::columns]) for i in range(columns)]
        rows = math.ceil(len(specs) / columns)
        row_heights = [
            max(item["height"] for item in specs[i * columns : (i + 1) * columns])
            for i in range(rows)
        ]
        ratio = min(
            1,
            max(1, width - 50 - gap * (columns - 1)) / sum(column_widths),
            max(1, height - 52 - gap * (rows - 1)) / sum(row_heights),
        )
        candidates.append((ratio, -abs(columns - desired), columns, column_widths, row_heights))
    ratio, _, columns, column_widths, row_heights = max(
        candidates, key=lambda item: (item[0], item[1])
    )
    if ratio + 1e-9 < max(dense_floor(spec) for spec in specs):
        raise LayoutCapacityError("Work area cannot fit all selected dense widgets")
    arranged = [
        constrain(item, item["width"] * ratio + 36, item["height"] * ratio + 36) for item in specs
    ]
    column_widths = [max(item["width"] for item in arranged[i::columns]) for i in range(columns)]
    row_heights = [
        max(item["height"] for item in arranged[i * columns : (i + 1) * columns])
        for i in range(math.ceil(len(specs) / columns))
    ]
    origin = width - sum(column_widths) - gap * (columns - 1) - 24
    points = [
        (
            round(origin + sum(column_widths[: i % columns]) + gap * (i % columns)),
            round(26 + sum(row_heights[: i // columns]) + gap * (i // columns)),
        )
        for i in range(len(specs))
    ]
    return arranged, points


def write_positions(value):
    temporary = POSITIONS.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(POSITIONS)


def fit(x, y, width, height, available):
    """Keep windows on an existing monitor when displays or DPI change."""
    if not available:
        return int(x), int(y)
    screen = next(
        (rect for rect in available if rect.contains(int(x + width / 2), int(y + height / 2))),
        available[0],
    )
    return (
        max(screen.x(), min(int(x), screen.right() - width + 1)),
        max(screen.y(), min(int(y), screen.bottom() - height + 1)),
    )
