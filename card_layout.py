"""Pure, bounded layouts for a 160-unit-high hardware card."""

from dataclasses import dataclass
from math import ceil, sqrt


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height


@dataclass(frozen=True)
class Reading:
    index: int
    box: Box
    mode: str = "stack"
    size: float = 24
    metric: str | None = None


@dataclass(frozen=True)
class CardLayout:
    body: Box
    readings: tuple
    chart: Box | None = None
    ring: Box | None = None
    cores: Box | None = None
    core_caption: Box | None = None
    footer: Box | None = None
    title: Box | None = None
    separators: tuple = ()


def _grid(indices, box, columns, mode="stack", size=24, gap=8, column_gap=None):
    rows = ceil(len(indices) / columns)
    horizontal_gap = gap if column_gap is None else column_gap
    cell_width = (box.width - horizontal_gap * (columns - 1)) / columns
    cell_height = (box.height - gap * (rows - 1)) / rows
    return tuple(
        Reading(
            index,
            Box(
                box.x + position % columns * (cell_width + horizontal_gap),
                box.y + position // columns * (cell_height + gap),
                cell_width,
                cell_height,
            ),
            mode,
            size,
        )
        for position, index in enumerate(indices)
    )


def plan(width, count, style="auto", show_title=True, chart=False, footer=False, compact=False):
    """Keep every selected reading in a non-overlapping content rectangle.

    Dimensions are design units, independent of screen DPI. Small cards use the
    same geometry; the painter measures its real fonts before placing text.
    """
    count = max(1, min(6, count))
    top = 36 if show_title else 14
    bottom = 146 - (16 if footer else 0)
    body = Box(14, top, width - 28, bottom - top)
    foot = Box(14, 133, width - 28, 16) if footer else None
    indices = tuple(range(count))
    wide = width >= 248

    if style == "cores":
        if count == 1:
            metric_height = min(52, body.height * 0.46)
            readings = (Reading(0, Box(body.x, body.y, body.width, metric_height), size=30),)
        else:
            metric_height = min(body.height - 20, count * (24 - count * 1.3))
            readings = _grid(
                indices,
                Box(body.x, body.y, body.width, metric_height),
                2 if wide else 1,
                "row",
                18 if count <= 3 else 15,
                0,
                column_gap=16,
            )
        start = body.y + metric_height + 5
        caption = None
        if (count <= 3 or not show_title) and body.bottom - start >= 32:
            caption = Box(body.x, start, body.width, 16)
            start += 18
        cores = Box(body.x, start, body.width, max(1, body.bottom - start))
        return CardLayout(body, readings, cores=cores, core_caption=caption, footer=foot)

    if style == "list" or (style == "auto" and (count >= 5 or compact and count >= 2)):
        readings = _grid(
            indices,
            body,
            # A list is a reading sequence, not a half-empty dashboard grid.
            # Up to four readings use the full line, so both a meaningful name
            # and the value fit on the smallest 236x114 wide card.
            2 if wide and count >= 5 else 1,
            "row",
            24 if count == 1 else 20 if count <= 3 else 17 if count == 4 else 15,
            0,
            column_gap=16,
        )
        return CardLayout(body, readings, footer=foot)

    if style == "auto" and count in (2, 3, 4):
        chart_box = None
        space = body
        if count == 2 and chart:
            space = Box(body.x, body.y, body.width, body.height - 27)
            chart_box = Box(body.x, body.bottom - 20, body.width, 20)
        if count == 3 and not wide:
            primary_height = space.height * 0.53
            primary = Reading(0, Box(space.x, space.y, space.width, primary_height), size=32)
            support = Box(
                space.x,
                space.y + primary_height + 7,
                space.width,
                space.height - primary_height - 7,
            )
            readings = (primary,) + _grid(
                (1, 2),
                support,
                1 if compact else 2,
                "row" if compact else "stack",
                size=17 if compact else 21,
                gap=0 if compact else 8,
            )
        else:
            columns = 3 if count == 3 else 2 if wide or count == 4 else 1
            readings = _grid(
                indices,
                space,
                columns,
                size=28 if wide else 21 if count == 2 and chart else 25,
                gap=8,
            )
        return CardLayout(body, readings, chart=chart_box, footer=foot)

    # A prominent first reading and a bounded auxiliary area are shared by the
    # hero, ring and bar styles. Density can change, selected data never does.
    if count == 1:
        space = body
        chart_box = None
        if style == "bar":
            space = Box(body.x, body.y, body.width, body.height - 19)
            chart_box = Box(body.x, body.bottom - 9, body.width, 4)
        elif style == "auto" and chart:
            space = Box(body.x, body.y, body.width, body.height - 34)
            chart_box = Box(body.x, body.bottom - 25, body.width, 25)
        if style == "ring":
            diameter = min(104, space.height - 4, space.width - 8)
            ring = Box(
                space.x + (space.width - diameter) / 2,
                space.y + (space.height - diameter) / 2,
                diameter,
                diameter,
            )
            return CardLayout(body, (Reading(0, space, "ring", 27),), ring=ring, footer=foot)
        return CardLayout(body, (Reading(0, space, size=36),), chart=chart_box, footer=foot)

    if count <= 3:
        primary_height = max(body.height - 49, body.height * 0.57)
        support_height = body.height - primary_height - 7
        support = Box(body.x, body.bottom - support_height, body.width, support_height)
        primary_box = Box(body.x, body.y, body.width, primary_height)
        ring = None
        chart_box = None
        mode = "stack"
        if style == "ring":
            diameter = min(primary_height - 2, 84)
            ring = Box(body.x + (body.width - diameter) / 2, body.y, diameter, diameter)
            mode = "ring"
        elif style == "bar":
            chart_box = Box(body.x, primary_box.bottom - 4, body.width, 3)
            primary_box = Box(body.x, body.y, body.width, primary_height - 10)
        readings = (Reading(0, primary_box, mode, 30 if style != "ring" else 23),)
        readings += _grid(
            tuple(range(1, count)),
            support,
            1 if compact else count - 1,
            "row" if compact else "stack",
            size=17 if compact else 21,
            gap=0 if compact else 8,
        )
        return CardLayout(body, readings, chart=chart_box, ring=ring, footer=foot)

    primary_height = max(16, min(40, body.height - (count - 1) * 15.5 - 5))
    primary_box = Box(body.x, body.y, body.width, primary_height)
    ring = None
    chart_box = None
    if style == "ring":
        diameter = min(12 if compact else 32, primary_height - 2)
        ring = Box(
            body.right - diameter, body.y + (primary_height - diameter) / 2, diameter, diameter
        )
        primary_box = Box(body.x, body.y, body.width - diameter - 7, primary_height)
    elif style == "bar":
        chart_box = Box(body.x, primary_box.bottom + 1, body.width, 2)
    support = Box(body.x, body.y + primary_height + 5, body.width, body.height - primary_height - 5)
    readings = (Reading(0, primary_box, "row", 23 if primary_box.height >= 25 else 16),)
    readings += _grid(
        tuple(range(1, count)), support, 2 if wide else 1, "row", 15, 0, column_gap=16
    )
    return CardLayout(body, readings, chart=chart_box, ring=ring, footer=foot)


def core_boxes(count, box):
    """Fit every logical processor, including large counts, inside the plot."""
    if count <= 0 or box.width <= 0 or box.height <= 0:
        return ()
    columns = min(count, max(1, ceil(sqrt(count * box.width / box.height))))
    rows = ceil(count / columns)
    gap = min(2.2, box.width / columns * 0.22, box.height / rows * 0.22)
    cell_width = (box.width - gap * (columns - 1)) / columns
    cell_height = (box.height - gap * (rows - 1)) / rows
    return tuple(
        Box(
            box.x + index % columns * (cell_width + gap),
            box.y + index // columns * (cell_height + gap),
            cell_width,
            cell_height,
        )
        for index in range(count)
    )
