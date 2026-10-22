"""Pure actual-DIP widget geometry shared by drawing, hit-testing and editors.

New 2-D layouts never scale a 160-unit canvas. A requested rectangle that cannot
contain all selected readings at readable density is rejected, and dimensions()
computes a legal effective rectangle before a native window is created/resized.
"""

from math import ceil, floor, isfinite

from card_layout import Box, CardLayout, Reading
from card_layout import plan as legacy_plan

CELL_WIDTH = 128
ROW_HEIGHT = 30
GAP = 8
PAD_X = 10
PAD_Y = 4
TITLE_HEIGHT = 22


class ResponsiveLayoutError(ValueError):
    """The requested content rectangle is incomplete or too small."""


def is_responsive(prefs):
    return (
        prefs.get("width") is not None
        or prefs.get("height") is not None
        or prefs.get("form", "square") in ("free", "bar")
        or prefs.get("layout_mode", "auto") != "auto"
    )


def metric_count(prefs):
    selected = prefs.get("content")
    if selected:
        return len(selected)
    return 2 if prefs.get("kind") == "power" and prefs.get("primary") == "watts" else 1


def _mode(prefs):
    mode = prefs.get("layout_mode", "auto")
    if mode not in ("auto", "horizontal", "vertical", "grid", "manual"):
        raise ResponsiveLayoutError("Unsupported content layout")
    return mode


def _columns(width, count, prefs):
    mode = _mode(prefs)
    if mode == "horizontal":
        return count
    if mode == "vertical":
        return 1
    if mode == "grid":
        return max(1, min(count, int(prefs.get("columns", 2))))
    capacity = max(1, min(count, floor((width - 2 * PAD_X + GAP) / (CELL_WIDTH + GAP))))
    # Balance wrapped rows: six readings at a five-cell width use 3+3 rather
    # than leaving one isolated value below a full row of five.
    return ceil(count / ceil(count / capacity))


def _title(prefs):
    return bool(prefs.get("show_title", prefs.get("form") != "bar"))


def _manual_positions(prefs, metrics):
    positions = prefs.get("metric_positions", {})
    if not isinstance(positions, dict) or any(metric not in positions for metric in metrics):
        raise ResponsiveLayoutError("Every selected metric needs a manual position")
    result = []
    for metric in metrics:
        item = positions[metric]
        if not isinstance(item, dict) or any(
            type(item.get(key)) not in (int, float) or not isfinite(item[key])
            for key in ("x", "y", "width", "height")
        ):
            raise ResponsiveLayoutError("Invalid manual metric rectangle")
        x, y, w, h = (item[key] for key in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 + 1e-8 or y + h > 1 + 1e-8:
            raise ResponsiveLayoutError("Manual metric rectangle outside content area")
        result.append((x, y, w, h))
    for index, (x, y, w, h) in enumerate(result):
        if any(
            min(x + w, bx + bw) - max(x, bx) > 1e-8 and min(y + h, by + bh) - max(y, by) > 1e-8
            for bx, by, bw, bh in result[index + 1 :]
        ):
            raise ResponsiveLayoutError("Manual metric rectangles overlap")
    return result


def minimum_dimensions(prefs, width=None):
    """Readable geometry floor; optional width gives an auto-flow height floor.

    Returns a (width, height) pair in DIP. In auto mode narrow widths require
    more rows; callers must pass their candidate width for the matching height.
    """
    if width is not None and (type(width) not in (int, float) or not isfinite(width) or width <= 0):
        raise ResponsiveLayoutError("Invalid candidate width")
    count = max(1, min(6, metric_count(prefs)))
    if not is_responsive(prefs):
        edge = 132 if count >= 5 else 114
        return (edge * 2 + 8 if prefs.get("form") == "wide" else edge, edge)
    title = TITLE_HEIGHT if _title(prefs) else 0
    mode = _mode(prefs)
    if mode == "manual":
        metrics = prefs.get("content") or []
        positions = _manual_positions(prefs, metrics)
        if not positions:
            raise ResponsiveLayoutError("Manual layout needs selected metrics")
        return (
            ceil(2 * PAD_X + max(CELL_WIDTH / item[2] for item in positions) - 1e-8),
            ceil(2 * PAD_Y + title + max(ROW_HEIGHT / item[3] for item in positions) - 1e-8),
        )
    minimum_width = 2 * PAD_X + CELL_WIDTH
    if mode in ("horizontal", "grid", "vertical"):
        columns = _columns(4096, count, prefs)
        minimum_width = 2 * PAD_X + columns * CELL_WIDTH + (columns - 1) * GAP
    # Without a candidate width, report independent edge floors. Auto layouts
    # can use a single row at a sufficiently wide width; treating the smallest
    # width as mandatory here would incorrectly force every bar to 228px high.
    target_width = max(
        minimum_width,
        width if width is not None else 2 * PAD_X + count * CELL_WIDTH + (count - 1) * GAP,
    )
    columns = _columns(target_width, count, prefs)
    rows = ceil(count / columns)
    minimum_height = max(32, 2 * PAD_Y + title + rows * ROW_HEIGHT + (rows - 1) * GAP)
    return ceil(minimum_width), ceil(minimum_height)


def dimensions(config, key):
    """Return effective legal DIP dimensions while preserving saved requests."""
    prefs = config["widgets"][key]
    if not is_responsive(prefs):
        floor_width, floor_height = minimum_dimensions(prefs)
        edge = max(floor_height, round((prefs.get("size") or config.get("size", 112)) * 1.5))
        return (edge * 2 + 8 if prefs.get("form") == "wide" else edge, edge)
    edge = round((prefs.get("size") or config.get("size", 112)) * 1.5)
    defaults = (
        (900, 40)
        if prefs.get("form") == "bar"
        else (edge * 2 + 8, edge)
        if prefs.get("form") in ("free", "wide")
        else (edge, edge)
    )
    requested_width = prefs.get("width") if prefs.get("width") is not None else defaults[0]
    requested_height = prefs.get("height") if prefs.get("height") is not None else defaults[1]
    if (
        type(requested_width) not in (int, float)
        or type(requested_height) not in (int, float)
        or not isfinite(requested_width)
        or not isfinite(requested_height)
    ):
        raise ResponsiveLayoutError("Invalid widget dimensions")
    minimum_width, _ = minimum_dimensions(prefs, requested_width)
    width = max(minimum_width, round(requested_width))
    _, minimum_height = minimum_dimensions(prefs, width)
    height = max(minimum_height, round(requested_height))
    if width > 4096 or height > 2160:
        raise ResponsiveLayoutError("Readable widget exceeds supported dimensions")
    return width, height


def responsive_plan(width, height, metrics, prefs):
    """Return a CardLayout whose Box coordinates are actual widget DIP.

    metrics is the ordered metric-ID sequence (including external slot IDs).
    Manual IDs are never converted to indexes in persisted preferences.
    """
    if (
        type(width) not in (int, float)
        or type(height) not in (int, float)
        or not (isfinite(width) and isfinite(height))
        or width <= 0
        or height <= 0
    ):
        raise ResponsiveLayoutError("Invalid content rectangle")
    metrics = tuple(metrics)
    if not 1 <= len(metrics) <= 6 or len(set(metrics)) != len(metrics):
        raise ResponsiveLayoutError("Choose one to six distinct metrics")
    if not is_responsive(prefs):
        scale = height / 160
        style = prefs.get("presentation", "auto")
        old = legacy_plan(
            width / scale,
            len(metrics),
            style,
            prefs.get("show_title", True),
            chart=bool(prefs.get("chart") and style == "auto" and len(metrics) <= 2),
            footer=prefs.get("kind") == "power"
            or not prefs.get("content")
            and style != "cores"
            and prefs.get("secondary", "none") != "none",
        )

        def box(item):
            return (
                Box(item.x * scale, item.y * scale, item.width * scale, item.height * scale)
                if item
                else None
            )

        return CardLayout(
            box(old.body),
            tuple(
                Reading(r.index, box(r.box), r.mode, r.size * scale, metrics[r.index])
                for r in old.readings
            ),
            chart=box(old.chart),
            ring=box(old.ring),
            cores=box(old.cores),
            core_caption=box(old.core_caption),
            footer=box(old.footer),
        )
    options = dict(prefs, content=list(metrics))
    minimum_width, minimum_height = minimum_dimensions(options, width)
    if width + 0.01 < minimum_width or height + 0.01 < minimum_height:
        raise ResponsiveLayoutError(
            f"Readable content needs at least {minimum_width} × {minimum_height} DIP"
        )
    title_height = TITLE_HEIGHT if _title(prefs) else 0
    body = Box(PAD_X, PAD_Y + title_height, width - 2 * PAD_X, height - 2 * PAD_Y - title_height)
    title = Box(PAD_X, PAD_Y, width - 2 * PAD_X, TITLE_HEIGHT - 2) if title_height else None
    mode = _mode(prefs)
    if mode == "manual":
        boxes = tuple(
            Box(body.x + x * body.width, body.y + y * body.height, w * body.width, h * body.height)
            for x, y, w, h in _manual_positions(prefs, metrics)
        )
    else:
        columns = _columns(width, len(metrics), prefs)
        rows = ceil(len(metrics) / columns)
        cell_height = (body.height - (rows - 1) * GAP) / rows
        flow_boxes = []
        for index in range(len(metrics)):
            row, column = divmod(index, columns)
            row_columns = min(columns, len(metrics) - row * columns) if mode == "auto" else columns
            row_width = (body.width - (row_columns - 1) * GAP) / row_columns
            flow_boxes.append(
                Box(
                    body.x + column * (row_width + GAP),
                    body.y + row * (cell_height + GAP),
                    row_width,
                    cell_height,
                )
            )
        boxes = tuple(flow_boxes)
    chart = ring = cores = None
    presentation = prefs.get("presentation", "auto")
    if mode != "manual" and len(metrics) == 1:
        box = boxes[0]
        if presentation == "ring" and box.height >= 90:
            diameter = min(104, box.width - 8, box.height - 8)
            ring = Box(
                box.x + (box.width - diameter) / 2,
                box.y + (box.height - diameter) / 2,
                diameter,
                diameter,
            )
        elif presentation == "cores" and box.height >= 100:
            boxes = (Box(box.x, box.y, box.width, 50),)
            cores = Box(box.x, box.y + 58, box.width, box.height - 58)
        elif presentation == "bar" and box.height >= 60:
            boxes = (Box(box.x, box.y, box.width, box.height - 14),)
            chart = Box(box.x, box.bottom - 6, box.width, 4)
        elif presentation == "auto" and prefs.get("chart") and box.height >= 100:
            boxes = (Box(box.x, box.y, box.width, box.height - 30),)
            chart = Box(box.x, box.bottom - 22, box.width, 20)
    elif mode != "manual" and presentation == "ring" and boxes[0].height >= 90:
        box = boxes[0]
        diameter = min(84, box.width - 8, box.height - 8)
        ring = Box(
            box.x + (box.width - diameter) / 2,
            box.y + (box.height - diameter) / 2,
            diameter,
            diameter,
        )
    readings = []
    for index, box in enumerate(boxes):
        compact = box.height <= 60
        style = "compact" if compact else "row" if presentation == "list" else "stack"
        if ring is not None and index == 0:
            style = "ring"
        size = (14 if box.height < 38 else 17) if compact else min(36, max(20, box.height * 0.4))
        readings.append(Reading(index, box, style, size, metrics[index]))
    separators = (
        ()
        if mode == "manual"
        else tuple(
            Box(a.right + GAP / 2, a.y + 4, 0, max(0, a.height - 8))
            for a, b in zip(boxes, boxes[1:])
            if abs(a.y - b.y) < 0.01
        )
    )
    return CardLayout(
        body,
        tuple(readings),
        chart=chart,
        ring=ring,
        cores=cores,
        title=title,
        separators=separators,
    )


def metric_rects(layout, metrics=None):
    result = []
    for reading in layout.readings:
        box = reading.box
        identifier = metrics[reading.index] if metrics is not None else reading.metric
        if identifier is None:
            raise ResponsiveLayoutError(
                "Metric IDs are required to serialize an unbound legacy plan"
            )
        item = dict(
            id=identifier,
            metric=identifier,
            index=reading.index,
            x=box.x,
            y=box.y,
            width=box.width,
            height=box.height,
        )
        result.append(item)
    return result
