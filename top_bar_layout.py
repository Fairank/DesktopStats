"""Pure physical-pixel geometry for a fixed, single-row desktop top bar.

Callers measure text in DIPs. This module never measures fonts, reads monitor
state, or imports a windowing API. All rounding is local to the monitor origin.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import ceil, isfinite

from external_sensor import EXTERNAL_SLOTS, sensor_binding

_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1
_MAX_ITEMS = 64
DISPLAY_STYLES = ("label_value", "value", "icon_value", "trend_value",
                  "bar_value", "ring_value", "graph", "stacked", "duplex", "duplex_inline")
PLACEMENTS = ("left", "right")


def metric_icon(metric: str, preferences=None) -> str:
    """Show the measured quantity before its hardware family; local vectors only."""
    if metric in EXTERNAL_SLOTS:
        binding = sensor_binding(metric, preferences)
        return {
            'Temperature': 'temperature', 'Fan': 'fan', 'Noise': 'noise', 'Voltage': 'voltage',
            'Current': 'voltage', 'Power': 'power', 'Clock': 'frequency',
            'Load': 'grid', 'Level': 'grid',
        }.get(binding['sensor_type'] if binding else '', 'sensors')
    parts = str(metric).strip().casefold().split("_")
    words = set(parts)
    for quantities, icon in (
        (("noise", "sound", "acoustic", "db", "dba"), "noise"),
        (("temp", "temperature", "thermal"), "temperature"),
        (("voltage", "volt", "volts", "current", "amperage"), "voltage"),
        (("power", "watt", "watts", "tdp"), "power"),
        (("frequency", "freq", "clock", "hz", "mhz", "ghz"), "frequency"),
        (("fan", "rpm"), "fan"),
        (("time", "duration", "uptime"), "time"),
    ):
        if words.intersection(quantities):
            return icon
    family = parts[0]
    if family in ("net", "network"):
        if words.intersection(("download", "received", "receive", "rx", "ingress")):
            return "download"
        if words.intersection(("upload", "sent", "send", "tx", "egress")):
            return "upload"
        return "network"
    if family in ("disk", "volume", "storage"):
        if "read" in words:
            return "disk_read"
        if "write" in words:
            return "disk_write"
        return "disk"
    if family in ("ram", "swap", "vram", "memory"):
        return "memory"
    if family in ("cpu", "gpu", "battery"):
        return family
    return "sensors"


def scalar_feedback_mode(metric, preferences):
    """Use the validated sensor type, never free-form names or guessed direction."""
    if metric not in EXTERNAL_SLOTS:
        return ''
    binding = sensor_binding(metric, preferences)
    return {
        'Temperature': 'heat', 'Fan': 'spin', 'Noise': 'off', 'Voltage': 'flow',
        'Current': 'flow', 'Power': 'flow', 'Clock': 'pulse',
        'Load': 'pulse', 'Level': 'pulse', 'Throughput': 'pulse',
    }.get(binding['sensor_type'] if binding else '', 'off')


def present_metric(row: Mapping, prefs: Mapping | None = None) -> dict:
    """Return a display row and bounded, gap-preserving qualitative trend.

    History is already projected into this item's display units by the shared
    controller. This helper neither parses formatted strings nor samples or
    retains hardware values. An unavailable current reading suppresses history.
    Points use validated sample timestamps when present; otherwise the x-axis
    describes sample order and does not imply a fixed time window.
    """
    prefs = prefs or {}
    style = prefs.get("style", "label_value")
    placement = prefs.get("placement", "right")
    if style not in DISPLAY_STYLES or placement not in PLACEMENTS:
        raise LayoutError("invalid metric display style or placement")
    history = row.get("history", [])
    if not isinstance(history, (list, tuple)) or row.get("available") is not True:
        history = []
    values: list[float | None] = []
    for sample in history[-40:]:
        number = None
        if type(sample) in (int, float):
            try:
                candidate = float(sample)
            except (OverflowError, ValueError):
                pass
            else:
                if isfinite(candidate):
                    number = candidate
        values.append(number)
    finite = [value for value in values if value is not None]
    bounded_percent = row.get('unit') == '%' and row.get('gauge_supported') is not False
    low = (0.0 if bounded_percent else min(finite)) if finite else None
    high = (100.0 if bounded_percent else max(finite)) if finite else None
    times = row.get('history_times', ())
    times = list(times[-40:]) if isinstance(times, (list, tuple)) else []
    time_axis = (len(times) == len(values) and len(times) >= 2
                 and all(type(t) in (int, float) and isfinite(t) for t in times)
                 and all(b >= a for a, b in zip(times, times[1:]))
                 and times[-1] > times[0] and isfinite(times[-1]-times[0]))
    elapsed = float(times[-1]-times[0]) if time_axis else None
    points = []
    for index, value in enumerate(values):
        if value is None:
            points.append(None)
            continue
        x = (times[index]-times[0])/elapsed if time_axis else index/max(1, len(values)-1)
        if low == high:
            y = 0.5
        else:
            span = high - low
            if isfinite(span):
                y = (high - value) / span
            else:
                # Avoid overflow for opposite, extreme finite endpoints.
                span = high / 2 - low / 2
                y = (high / 2 - value / 2) / span
            y = min(1.0, max(0.0, y))
        points.append(dict(x=x, y=y))
    available = any(
        values[index] is not None and values[index - 1] is not None
        for index in range(1, len(values))
    )
    number = row.get("numeric_value")
    gauge = None
    if (row.get("available") is True and row.get("unit") == "%"
            and row.get('gauge_supported') is not False and type(number) in (int, float)):
        try:
            candidate = float(number)
            if isfinite(candidate) and 0 <= candidate <= 100:
                gauge = candidate / 100
        except (OverflowError, ValueError):
            pass
    pairs = row.get('paired_rows', [])[:2] if style in ('duplex', 'duplex_inline') else []
    paired_value = '  '.join(('↓ ' if channel.get('direction') in ('download', 'read', 'charge') else '↑ ')
                             + str(channel.get('value', '—')) for channel in pairs)
    return dict(
        row,
        value=paired_value or row.get('value', '—'),
        available=any(channel.get('available') is True for channel in pairs) if pairs else row.get('available', False),
        style=style,
        placement=placement,
        icon=metric_icon(row.get("metric", ""), prefs),
        auto_effect=scalar_feedback_mode(row.get("metric", ""), prefs),
        trend=values,
        trend_points=points,
        trend_available=available,
        trend_min=low,
        trend_max=high,
        history_min=min(finite) if finite else None,
        history_max=max(finite) if finite else None,
        history_mean=sum(v/len(finite) for v in finite) if finite else None,
        history_elapsed_s=elapsed,
        history_started_at=times[0] if time_axis else None,
        history_ended_at=times[-1] if time_axis else None,
        history_axis='time' if time_axis else 'samples',
        gauge_available=gauge is not None,
        gauge_fraction=gauge,
    )


class LayoutError(ValueError):
    """A layout input is invalid or the requested bar cannot fit."""


@dataclass(frozen=True)
class PixelRect:
    """A signed-32-bit physical RECT with nonnegative, C-int-sized extents."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        for name in ("left", "top", "right", "bottom"):
            value = getattr(self, name)
            if type(value) is not int or not _INT_MIN <= value <= _INT_MAX:
                raise LayoutError(f"{name} must be a signed-32-bit integer")
        if not 0 <= self.width <= _INT_MAX or not 0 <= self.height <= _INT_MAX:
            raise LayoutError("rectangle extents must be nonnegative and fit a C int")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class MetricItem:
    """A stable metric ID and the caller's measured text ink width in DIPs."""

    id: str
    measured_width_dip: float
    placement: str = "right"


@dataclass(frozen=True)
class PlacedItem:
    id: str
    rect: PixelRect


@dataclass(frozen=True)
class BarPlan:
    """Desired bar bounds and full-height hit regions in physical pixels."""

    bounds: PixelRect
    menu_hit: PixelRect
    items: tuple[PlacedItem, ...]
    overflow_hit: PixelRect | None
    overflow_ids: tuple[str, ...]
    dpi: int
    height_dip: float

    @property
    def desired_bounds(self) -> PixelRect:
        return self.bounds


def _dip(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise LayoutError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise LayoutError(f"{name} must be a finite number") from exc
    if not isfinite(result) or result < 0 or (positive and result == 0):
        qualifier = "positive" if positive else "nonnegative"
        raise LayoutError(f"{name} must be finite and {qualifier}")
    return result


def _pixels(dip: float, dpi: int, name: str) -> int:
    scaled = dip * dpi / 96
    if not isfinite(scaled) or scaled > _INT_MAX:
        raise LayoutError(f"{name} in physical pixels must fit a C int")
    return ceil(scaled)


def plan_top_bar(
    bounds: PixelRect,
    dpi: int = 96,
    items: Sequence[MetricItem] = (),
    height_dip: float = 32,
    padding_dip: float = 8,
    gap_dip: float = 12,
    menu_width_dip: float = 24,
    item_padding_dip: float = 6,
    overflow_widths_dip: Mapping[int, float] | None = None,
) -> BarPlan:
    """Place the longest fitting metric prefix and a trailing ``+N`` hit region.

    ``bounds`` is the monitor's physical rectangle. The desired bar uses its
    full width and top edge, with a default height of 32 DIPs. An explicit
    height from 16 through 128 DIPs supports other density settings without
    introducing a second row. Menu and metric hit
    regions span the bar height; each is at least that height wide. A measured
    metric or overflow ink width receives ``item_padding_dip`` on *each* side.
    Unmeasured overflow labels use 36 DIPs of ink width. Outer padding and gaps
    are rounded upward independently, as are each control's complete widths.

    The menu stays at the left padding. Left metrics follow the menu; right
    metrics and the single overflow control align with the right padding.
    Each side retains its original relative order, and the output items retain
    the original array order. No metric is skipped to fit a later one. An
    error is raised if the menu and required overflow label cannot both fit;
    text is never compressed, clipped, or moved to another row.
    """
    if not isinstance(bounds, PixelRect):
        raise LayoutError("bounds must be a PixelRect")
    if bounds.width == 0 or bounds.height == 0:
        raise LayoutError("monitor bounds must have positive width and height")
    if type(dpi) is not int or not 48 <= dpi <= 768:
        raise LayoutError("dpi must be an integer between 48 and 768")

    height = _dip(height_dip, "height_dip", positive=True)
    if not 16 <= height <= 128:
        raise LayoutError("height_dip must be between 16 and 128")
    padding = _dip(padding_dip, "padding_dip")
    gap = _dip(gap_dip, "gap_dip")
    menu_width = _dip(menu_width_dip, "menu_width_dip", positive=True)
    item_padding = _dip(item_padding_dip, "item_padding_dip")
    height_px = _pixels(height, dpi, "height_dip")
    padding_px = _pixels(padding, dpi, "padding_dip")
    gap_px = _pixels(gap, dpi, "gap_dip")
    menu_px = max(height_px, _pixels(menu_width, dpi, "menu_width_dip"))
    _pixels(2 * item_padding, dpi, "item padding")
    if height_px > bounds.height:
        raise LayoutError("the requested bar height does not fit the monitor")
    if menu_px + 2 * padding_px > bounds.width:
        raise LayoutError("monitor is too narrow for the menu and outer padding")

    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise LayoutError("items must be a sequence of MetricItem values")
    if len(items) > _MAX_ITEMS:
        raise LayoutError("at most 64 metric items are supported")
    metrics = tuple(items)
    if len(metrics) > _MAX_ITEMS:
        raise LayoutError("at most 64 metric items are supported")
    ids: set[str] = set()
    widths: list[int] = []
    for item in metrics:
        if not isinstance(item, MetricItem):
            raise LayoutError("items must contain only MetricItem values")
        if type(item.id) is not str or not item.id.strip() or item.id in ids:
            raise LayoutError("metric IDs must be unique, nonempty strings")
        if item.placement not in ("left", "right"):
            raise LayoutError("metric placement must be left or right")
        ids.add(item.id)
        ink = _dip(item.measured_width_dip, f"metric {item.id!r} width")
        widths.append(max(height_px, _pixels(ink + 2 * item_padding, dpi, "item width")))

    overflow_widths: dict[int, int] = {}
    if overflow_widths_dip is not None:
        if not isinstance(overflow_widths_dip, Mapping):
            raise LayoutError("overflow_widths_dip must be a mapping")
        if len(overflow_widths_dip) > _MAX_ITEMS:
            raise LayoutError("at most 64 overflow measurements are supported")
        for count, measured_width in overflow_widths_dip.items():
            if type(count) is not int or not 1 <= count <= _MAX_ITEMS:
                raise LayoutError("overflow measurement keys must be integers from 1 to 64")
            ink = _dip(measured_width, f"overflow +{count} width")
            overflow_widths[count] = max(
                height_px, _pixels(ink + 2 * item_padding, dpi, "overflow width")
            )

    bar = PixelRect(bounds.left, bounds.top, bounds.right, bounds.top + height_px)
    menu = PixelRect(
        bounds.left + padding_px,
        bar.top,
        bounds.left + padding_px + menu_px,
        bar.bottom,
    )
    if not metrics:
        return BarPlan(bar, menu, (), None, (), dpi, height)

    available = bar.right - padding_px - menu.right - gap_px
    prefix_widths = [0]
    for width in widths:
        prefix_widths.append(prefix_widths[-1] + width)
    visible_count = len(metrics)
    group_width = prefix_widths[-1] + gap_px * (len(metrics) - 1)
    overflow_px = None
    if group_width > available:
        default_overflow = max(
            height_px, _pixels(36 + 2 * item_padding, dpi, "default overflow width")
        )
        for visible_count in range(len(metrics) - 1, -1, -1):
            hidden_count = len(metrics) - visible_count
            candidate_overflow = overflow_widths.get(hidden_count, default_overflow)
            candidate_width = (
                prefix_widths[visible_count] + gap_px * visible_count + candidate_overflow
            )
            if candidate_width <= available:
                group_width = candidate_width
                overflow_px = candidate_overflow
                break
        else:
            raise LayoutError("monitor is too narrow for the menu and required overflow label")

    visible = tuple(zip(metrics[:visible_count], widths[:visible_count]))
    left = [(item, width) for item, width in visible if item.placement == "left"]
    right = [(item, width) for item, width in visible if item.placement == "right"]
    right_count = len(right) + int(overflow_px is not None)
    right_width = (
        sum(width for _item, width in right)
        + (overflow_px or 0)
        + gap_px * max(0, right_count - 1)
    )
    boxes: dict[str, PixelRect] = {}
    cursor = menu.right + gap_px
    for item, width in left:
        boxes[item.id] = PixelRect(cursor, bar.top, cursor + width, bar.bottom)
        cursor += width + gap_px
    cursor = bar.right - padding_px - right_width
    for item, width in right:
        boxes[item.id] = PixelRect(cursor, bar.top, cursor + width, bar.bottom)
        cursor += width + gap_px
    placed = tuple(PlacedItem(item.id, boxes[item.id]) for item, _width in visible)
    overflow_hit = (
        PixelRect(cursor, bar.top, cursor + overflow_px, bar.bottom)
        if overflow_px is not None
        else None
    )
    return BarPlan(
        bar,
        menu,
        placed,
        overflow_hit,
        tuple(item.id for item in metrics[visible_count:]),
        dpi,
        height,
    )
