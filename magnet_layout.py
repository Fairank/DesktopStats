"""Deterministic desktop spacing in logical pixels; no window or input calls."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    legal: bool
    snapped: bool = False
    normal: tuple[int, int] = (0, 0)


def separated(rect, others, gap=0):
    x, y, width, height = rect
    return all(
        x + width + gap <= ox or ox + ow + gap <= x or y + height + gap <= oy or oy + oh + gap <= y
        for ox, oy, ow, oh in others
    )


def contained(rect, areas):
    x, y, width, height = rect
    return not areas or any(
        ax <= x and ay <= y and x + width <= ax + aw and y + height <= ay + ah
        for ax, ay, aw, ah in areas
    )


def settle(rect, others, areas, gap=12, snap=18, fallback=None):
    """Move only the released rectangle to a nearby legal, bounded position.

    Edge-coordinate candidates cover every free rectangular cell. If no legal
    cell can hold the widget, retain a legal drag origin when provided; never
    move the other widgets or silently reduce the requested spacing.
    """
    values = (*rect, gap, snap, *(n for item in [*others, *areas] for n in item))
    if not all(type(n) in (int, float) and isfinite(n) for n in values):
        raise ValueError("Non-finite desktop geometry")
    x, y, width, height = map(round, rect)
    if width <= 0 or height <= 0 or gap < 0 or snap < 0:
        raise ValueError("Invalid desktop geometry")
    others = [tuple(map(round, item)) for item in others]
    areas = [tuple(map(round, item)) for item in areas]
    original = (x, y, width, height)

    def valid(px, py):
        box = (px, py, width, height)
        return contained(box, areas) and separated(box, others, gap)

    if valid(x, y):
        near = []
        for ox, oy, ow, oh in others:
            if y < oy + oh and oy < y + height:
                for px, direction in ((ox - width - gap, -1), (ox + ow + gap, 1)):
                    if abs(px - x) <= snap and valid(px, y):
                        near.append(((px - x) ** 2, px, y, (direction, 0)))
            if x < ox + ow and ox < x + width:
                for py, direction in ((oy - height - gap, -1), (oy + oh + gap, 1)):
                    if abs(py - y) <= snap and valid(x, py):
                        near.append(((py - y) ** 2, x, py, (0, direction)))
        if near:
            _, px, py, normal = min(near)
            return Placement(px, py, True, True, normal)
        return Placement(x, y, True)

    candidates = set()
    for ax, ay, aw, ah in areas or [(x - 100000, y - 100000, 200000, 200000)]:
        if width > aw or height > ah:
            continue

        def clamp_x(value):
            return max(ax, min(round(value), ax + aw - width))

        def clamp_y(value):
            return max(ay, min(round(value), ay + ah - height))

        xs = {clamp_x(x), ax, ax + aw - width}
        ys = {clamp_y(y), ay, ay + ah - height}
        for ox, oy, ow, oh in others:
            xs.update(map(clamp_x, (ox - width - gap, ox + ow + gap, ox, ox + ow - width)))
            ys.update(map(clamp_y, (oy - height - gap, oy + oh + gap, oy, oy + oh - height)))
        candidates.update((px, py) for px in xs for py in ys if valid(px, py))
    if candidates:
        px, py = min(candidates, key=lambda p: ((p[0] - x) ** 2 + (p[1] - y) ** 2, p[1], p[0]))
        dx, dy = px - x, py - y
        normal = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
        return Placement(px, py, True, True, normal)
    if fallback is not None and valid(*fallback):
        return Placement(*map(round, fallback), True)
    # Impossible packing is reported, rather than claiming the gap was met.
    if areas:
        ax, ay, aw, ah = min(areas, key=lambda a: (a[0] - x) ** 2 + (a[1] - y) ** 2)
        return Placement(
            max(ax, min(x, ax + max(0, aw - width))),
            max(ay, min(y, ay + max(0, ah - height))),
            False,
        )
    return Placement(original[0], original[1], False)
