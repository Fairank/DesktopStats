"""Native vector cards: compatible legacy scaling and actual-DIP 2-D layouts."""

import time
from math import ceil

from PySide6.QtCore import Property, QPointF, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickPaintedItem

from battery_sensor import power_state
from card_layout import Box, core_boxes, plan
from compact_labels import label_options
from localization import translate
from metrics import display_value, metric_info, metric_value, numeric
from native_surface import paint_surface
from responsive_layout import ResponsiveLayoutError, is_responsive, responsive_plan
from skin_styles import effective_skin, glass_options, palette
from stats_config import DEFAULT, MODULES
from widget_catalog import TEMPLATES


def primary_metric(key, preferences):
    return {
        "cpu": {"temp": "cpu_temp", "usage": "cpu_usage", "frequency": "cpu_frequency"},
        "gpu": {"temp": "gpu_temp", "usage": "gpu_usage", "power": "gpu_power"},
        "memory": {"percent": "ram_percent", "used": "ram_used_gb"},
        "vram": {"used": "vram_gb", "percent": "vram_percent"},
        "battery": {
            "percent": "battery_percent",
            "voltage": "voltage",
            "time": "battery_time_minutes",
        },
        "power": {"watts": "battery_watts", "voltage": "voltage"},
        "network": {"download": "net_download", "upload": "net_upload"},
        "disk": {"read": "disk_read", "write": "disk_write", "percent": "disk_percent"},
        "custom": {"usage": "cpu_usage"},
    }[key][preferences["primary"]]


def formatted(data, metric, prefs=None):
    value, unit, digits = display_value(data, metric, prefs)
    return (f"{value:.{digits}f}" if numeric(value) else "—", unit)


def secondary(data, key, preferences, tr):
    field = preferences["secondary"]

    def text(metric):
        value, unit = formatted(data, metric, preferences)
        return value + (" " + unit if value != "—" else "")

    if field == "none":
        return ""
    if key == "cpu":
        if field == "cores":
            return f"{data.get('cpu_cores', '—')} / {data.get('cpu_threads', '—')} " + tr(
                "核心 / 线程"
            )
        return text("cpu_" + field) + " " + tr("温度" if field == "temp" else "使用率")
    if key == "gpu":
        if field == "usage_power":
            return text("gpu_usage") + "  ·  " + text("gpu_power")
        return text({"usage": "gpu_usage", "power": "gpu_power", "vram": "vram_gb"}[field])
    if key in ("memory", "vram"):
        used = metric_value(data, "ram_used_gb" if key == "memory" else "vram_gb", preferences)
        total = metric_value(
            data, "ram_total_gb" if key == "memory" else "vram_total_gb", preferences
        )
        if field == "available":
            return text("ram_available_gb") + " " + tr("可用容量")
        return f"{used:.1f} / {total:.0f} GB" if numeric(used) and numeric(total) else "— / — GB"
    if field == "battery":
        return text("battery_percent")
    if field == "power":
        return text("battery_watts")
    return tr({0: "已连接电源", 1: "充电中", 2: "放电中", 3: "未提供"}[power_state(data)])


def ui_font(language):
    return {
        "zh-CN": "Microsoft YaHei UI",
        "zh-TW": "Microsoft JhengHei UI",
        "ja": "Yu Gothic UI",
        "ko": "Malgun Gothic",
    }.get(language, "Segoe UI Variable")


class HardwareCard(QQuickPaintedItem):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = DEFAULT
        self._data = {}
        self._history = []
        self._key = "cpu"
        self._surface = True
        self._frosted = True
        self.setAntialiasing(True)
        self.setOpaquePainting(False)

    def set_config(self, value):
        self._config = value or DEFAULT
        self.changed.emit()
        self.update()

    config = Property("QVariantMap", lambda self: self._config, set_config, notify=changed)

    def set_data(self, value):
        self._data = value or {}
        self.changed.emit()
        self.update()

    readings = Property("QVariantMap", lambda self: self._data, set_data, notify=changed)

    def set_history(self, value):
        self._history = value or []
        self.changed.emit()
        self.update()

    history = Property("QVariantList", lambda self: self._history, set_history, notify=changed)

    def set_key(self, value):
        self._key = value
        self.changed.emit()
        self.update()

    moduleKey = Property(str, lambda self: self._key, set_key, notify=changed)

    def set_surface(self, value):
        self._surface = value
        self.changed.emit()
        self.update()

    surface = Property(bool, lambda self: self._surface, set_surface, notify=changed)

    def set_frosted(self, value):
        self._frosted = value
        self.changed.emit()
        self.update()

    frosted = Property(bool, lambda self: self._frosted, set_frosted, notify=changed)

    @staticmethod
    def _content(prefs, kind):
        content = prefs.get("content")
        if not content and kind == "power" and prefs.get("primary") == "watts":
            return ["battery_charge_watts", "battery_discharge_watts"]
        return content or [primary_metric(kind, prefs)]

    def _hit_layout(self):
        prefs = self._config.get("widgets", {}).get(self._key)
        if not prefs or self.width() <= 0 or self.height() <= 0:
            return None, 1, []
        kind = prefs.get("kind", self._key)
        content = self._content(prefs, kind)
        if is_responsive(prefs):
            return responsive_plan(self.width(), self.height(), content, prefs), 1, content
        config = self._config
        data = self._data
        stamp = data.get("time", 0)
        if not numeric(stamp) or not 0 <= time.time() - stamp < 35:
            data = {}
        scale = self.height() / 160
        style = prefs.get("presentation", "auto")
        footer = (
            kind == "power"
            or not prefs.get("content")
            and style != "cores"
            and bool(
                secondary(data, kind, prefs, lambda value: translate(value, config["language"]))
            )
        )
        args = dict(
            style=style,
            show_title=prefs.get("show_title", True),
            chart=bool(prefs["chart"] and style == "auto" and len(content) <= 2),
            footer=footer,
        )
        layout = plan(self.width() / scale, len(content), **args)
        draw = _CardPainter(
            None, config, {"ink": "#000000", "muted": "#666666"}, MODULES[kind]["color"], scale
        )

        def labels(metric):
            info = metric_info(metric, prefs)
            full = (
                info["label"]
                if info["source"] == "external"
                else translate(info["label"], config["language"])
            )
            return label_options(metric, full, config["language"])

        if any(
            draw.needs_space(
                reading,
                *formatted(data, content[reading.index], prefs),
                labels=labels(content[reading.index]),
            )
            for reading in layout.readings
        ):
            layout = plan(self.width() / scale, len(content), compact=True, **args)
        return layout, scale, content

    @Slot(float, float, result=int)
    def metricAt(self, x, y):
        """Hit the same reading slots used by paint, leaving title/margins empty."""
        if not numeric(x) or not numeric(y):
            return -1
        try:
            layout, scale, _ = self._hit_layout()
        except (ResponsiveLayoutError, KeyError, ValueError, TypeError):
            return -1
        if layout is not None:
            for reading in layout.readings:
                box = reading.box
                if (
                    box.x * scale <= x < box.right * scale
                    and box.y * scale <= y < box.bottom * scale
                ):
                    return reading.index
            for box in (layout.chart, layout.cores):
                if (
                    box
                    and box.x * scale <= x < box.right * scale
                    and box.y * scale <= y < box.bottom * scale
                ):
                    return 0
        return -1

    @Slot(float, float, result=str)
    def metricLabelAt(self, x, y):
        """Full literal external name / translated static name for hover details."""
        index = self.metricAt(x, y)
        if index < 0:
            return ""
        prefs = self._config["widgets"][self._key]
        content = self._content(prefs, prefs.get("kind", self._key))
        info = metric_info(content[index], prefs)
        return (
            info["label"]
            if info["source"] == "external"
            else translate(info["label"], self._config["language"])
        )

    def _paint_responsive(self, painter, config, prefs, data, meta, content, colors, metric_label):
        width, height = self.width(), self.height()
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            if self._surface:
                paint_surface(
                    painter, width, height, colors, radius=min(colors.get("radius", 18), height / 2)
                )
            painter.setClipRect(QRectF(1, 1, width - 2, height - 2), Qt.ClipOperation.IntersectClip)
            draw = _CardPainter(painter, config, colors, meta["color"], 1)
            draw.label_min, draw.number_min, draw.unit_min = 10, 12, 9
            try:
                layout = responsive_plan(width, height, content, prefs)
            except ResponsiveLayoutError:
                # Controllers preflight with dimensions(). This is only the
                # explicit transient invalid-resize/error state, not an excuse
                # to silently draw some of the selected channels.
                draw.label(
                    "↔  ↕",
                    Box(4, 4, max(1, width - 8), max(1, height - 8)),
                    12,
                    align=Qt.AlignmentFlag.AlignHCenter,
                )
                return
            if layout.title:
                title = prefs.get("title") or translate(
                    TEMPLATES.get(prefs.get("template"), {}).get("label", meta["label"]),
                    config["language"],
                )
                draw.label(title, layout.title, 11, draw.ink, QFont.Weight.DemiBold)
            for separator in layout.separators:
                color = QColor(draw.muted)
                color.setAlpha(46)
                painter.setPen(QPen(color, 0.7))
                painter.drawLine(
                    QPointF(separator.x, separator.y), QPointF(separator.x, separator.bottom)
                )
            for reading in layout.readings:
                metric = content[reading.index]
                value, unit = formatted(data, metric, prefs)
                labels = label_options(metric, metric_label(metric), config["language"])
                box = reading.box
                if reading.mode == "compact":
                    draw.compact(labels, value, unit, box, reading.size)
                elif reading.mode == "row":
                    draw.responsive_row(labels, value, unit, box, reading.size)
                elif reading.mode == "ring":
                    if draw.label_width(labels, 9) > layout.ring.width * 0.76:
                        diameter = min(32, box.height - 4)
                        draw.arc(
                            Box(box.x, box.y + (box.height - diameter) / 2, diameter, diameter),
                            metric_value(data, metric, prefs),
                            metric_info(metric, prefs)["maximum"],
                        )
                        draw.responsive_stack(
                            labels,
                            value,
                            unit,
                            Box(box.x + diameter + 8, box.y, box.width - diameter - 8, box.height),
                            min(28, reading.size),
                        )
                    else:
                        draw.ring(
                            value,
                            unit,
                            labels,
                            metric_value(data, metric, prefs),
                            box,
                            min(28, reading.size),
                            metric_info(metric, prefs)["maximum"],
                            layout.ring,
                        )
                else:
                    draw.responsive_stack(labels, value, unit, box, reading.size)
            if layout.chart:
                metric = content[0]
                if (
                    prefs.get("presentation") == "bar"
                    or metric_info(metric, prefs)["kind"] == "bar"
                ):
                    draw.bar(
                        layout.chart,
                        metric_value(data, metric, prefs),
                        metric_info(metric, prefs)["maximum"],
                    )
                else:
                    draw.trend(layout.chart, self._history, metric, prefs, bool(data))
            if layout.cores:
                values = data.get("cpu_per_core", [])
                draw.cores(layout.cores, values if isinstance(values, (list, tuple)) else [])
        finally:
            painter.restore()

    def paint(self, painter):
        if self.width() <= 0 or self.height() <= 0:
            return
        config = self._config
        prefs = config.get("widgets", {}).get(self._key)
        if not prefs:
            return
        kind = prefs.get("kind", self._key)
        meta = MODULES[kind]
        data = self._data
        stamp = data.get("time", 0)
        if not numeric(stamp) or not 0 <= time.time() - stamp < 35:
            data = {}
        scale = self.height() / 160
        width = self.width() / scale
        colors = palette(
            effective_skin(config, self._key),
            config["theme"] == "dark",
            config["opacity"],
            meta["color"],
            self._frosted,
            **glass_options(config, self._key),
        )

        def tr(value):
            return translate(value, config["language"])

        def metric_label(metric):
            info = metric_info(metric, prefs)
            return info["label"] if info["source"] == "external" else tr(info["label"])

        content = self._content(prefs, kind)
        style = prefs.get("presentation", "auto")
        footer = ""
        if kind == "power":
            footer = tr({0: "已连接电源", 1: "充电中", 2: "放电中", 3: "未提供"}[power_state(data)])
        elif not prefs.get("content") and style != "cores":
            footer = secondary(data, kind, prefs, tr)
        show_title = prefs.get("show_title", True)
        if is_responsive(prefs):
            self._paint_responsive(
                painter, config, prefs, data, meta, content, colors, metric_label
            )
            return
        layout = plan(
            width,
            len(content),
            style,
            show_title,
            chart=bool(prefs["chart"] and style == "auto" and len(content) <= 2),
            footer=bool(footer),
        )
        values = data.get("cpu_per_core", [])
        values = values if isinstance(values, (list, tuple)) else []
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.scale(scale, scale)
            if self._surface:
                paint_surface(painter, width, 160, colors)
            painter.setClipRect(QRectF(1, 1, width - 2, 158), Qt.ClipOperation.IntersectClip)
            draw = _CardPainter(painter, config, colors, meta["color"], scale)
            if any(
                draw.needs_space(
                    reading,
                    *formatted(data, content[reading.index], prefs),
                    labels=label_options(
                        content[reading.index],
                        metric_label(content[reading.index]),
                        config["language"],
                    ),
                )
                for reading in layout.readings
            ):
                layout = plan(
                    width,
                    len(content),
                    style,
                    show_title,
                    chart=bool(prefs["chart"] and style == "auto" and len(content) <= 2),
                    footer=bool(footer),
                    compact=True,
                )
            if show_title:
                title = prefs.get("title") or tr(
                    TEMPLATES.get(prefs.get("template"), {}).get("label", meta["label"])
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(draw.accent)
                painter.drawEllipse(QRectF(14, 18, 3.5, 3.5))
                badge = style == "cores" and len(content) >= 4
                draw.label(
                    title,
                    Box(24, 10, width - (76 if badge else 38), 21),
                    11,
                    draw.ink,
                    QFont.Weight.DemiBold,
                )
                if badge:
                    draw.label(
                        str(len(values)) if values else "—",
                        Box(width - 44, 10, 30, 21),
                        9,
                        align=Qt.AlignmentFlag.AlignRight,
                    )
            for reading in layout.readings:
                metric = content[reading.index]
                value, unit = formatted(data, metric, prefs)
                label = label_options(metric, metric_label(metric), config["language"])
                if reading.mode == "row":
                    draw.row(label, value, unit, reading.box, reading.size)
                elif reading.mode == "ring":
                    draw.ring(
                        value,
                        unit,
                        label,
                        metric_value(data, metric, prefs),
                        reading.box,
                        reading.size,
                        metric_info(metric, prefs)["maximum"],
                        layout.ring,
                    )
                else:
                    draw.stack(label, value, unit, reading.box, reading.size)
            if layout.ring and layout.readings[0].mode != "ring":
                draw.arc(
                    layout.ring,
                    metric_value(data, content[0], prefs),
                    metric_info(content[0], prefs)["maximum"],
                )
            if layout.chart:
                if style == "bar" or metric_info(content[0], prefs)["kind"] == "bar":
                    draw.bar(
                        layout.chart,
                        metric_value(data, content[0], prefs),
                        metric_info(content[0], prefs)["maximum"],
                    )
                else:
                    draw.trend(layout.chart, self._history, content[0], prefs, bool(data))
            if layout.cores:
                if layout.core_caption:
                    draw.label(
                        tr("逻辑处理器") + " · " + (str(len(values)) if values else "—"),
                        layout.core_caption,
                        9,
                    )
                draw.cores(layout.cores, values)
            if footer and layout.footer:
                draw.label(footer, layout.footer, 9)
        finally:
            painter.restore()


class _CardPainter:
    """Measure before painting; every readout has separate number/unit runs."""

    def __init__(self, painter, config, colors, accent, scale):
        self.painter = painter
        self.family = ui_font(config["language"])
        self.ink = QColor(colors["ink"])
        self.muted = QColor(colors["muted"])
        self.accent = QColor(accent)
        self.scale = scale
        full_size = scale >= 114 / 160 - 0.001
        self.label_min = ceil(9 / scale) if full_size else 9
        self.number_min = ceil(9 / scale) if full_size else 10
        self.unit_min = ceil(8 / scale) if full_size else 8
        self._fonts = {}

    def font(self, size, weight=QFont.Weight.Normal):
        key = (max(1, round(size)), weight)
        if key not in self._fonts:
            font = QFont(self.family)
            font.setPixelSize(key[0])
            font.setWeight(weight)
            self._fonts[key] = font
        return self._fonts[key]

    @staticmethod
    def rect(box):
        return QRectF(box.x, box.y, max(0, box.width), max(0, box.height))

    def label(
        self,
        value,
        box,
        size=10,
        color=None,
        weight=QFont.Weight.Normal,
        align=Qt.AlignmentFlag.AlignLeft,
        elide=True,
    ):
        if box.width <= 0 or box.height <= 0:
            return
        painter = self.painter
        font = self.font(max(size, self.label_min), weight)
        metrics = QFontMetricsF(font)
        value = str(value)
        if elide:
            value = metrics.elidedText(value, Qt.TextElideMode.ElideRight, max(1, box.width))
        ink = metrics.tightBoundingRect(value)
        left = max(0, -ink.left())
        right = max(0, ink.right() - metrics.horizontalAdvance(value))
        text_box = Box(box.x + left, box.y, max(1, box.width - left - right), box.height)
        painter.save()
        painter.setClipRect(self.rect(box), Qt.ClipOperation.IntersectClip)
        painter.setFont(font)
        painter.setPen(color if color is not None else self.muted)
        painter.drawText(self.rect(text_box), align | Qt.AlignmentFlag.AlignVCenter, value)
        painter.restore()

    def metric_label(self, options, box, size=10, align=Qt.AlignmentFlag.AlignLeft):
        """Prefer the complete name, then a reviewed semantic short name.

        A metric is never silently turned into arbitrary prefix + ellipsis.
        Row/stack layout first measures these same fonts and candidate names.
        """
        if isinstance(options, str):
            options = (options,)
        metrics = QFontMetricsF(self.font(max(size, self.label_min)))
        selected = next(
            (value for value in options if self.text_width(metrics, value) <= box.width + 0.01),
            options[-1],
        )
        self.label(selected, box, size, align=align, elide=False)

    def label_width(self, labels, size=10):
        if isinstance(labels, str):
            labels = (labels,)
        metrics = QFontMetricsF(self.font(max(size, self.label_min)))
        return min(self.text_width(metrics, value) for value in labels)

    @staticmethod
    def text_width(metrics, text):
        ink = metrics.tightBoundingRect(text)
        return max(metrics.horizontalAdvance(text), ink.right()) - min(0, ink.left())

    def responsive_label(self, options, box, size, align=Qt.AlignmentFlag.AlignLeft):
        """Short visible label only; metricLabelAt retains the complete name."""
        if isinstance(options, str):
            options = (options,)
        metrics = QFontMetricsF(self.font(max(size, self.label_min)))
        selected = next(
            (text for text in options if self.text_width(metrics, text) <= box.width), options[-1]
        )
        self.label(selected, box, size, elide=True, align=align)

    def responsive_stack(self, labels, value, unit, box, size, align=Qt.AlignmentFlag.AlignLeft):
        label_size = 10 if box.height <= 60 else 11
        label_height = QFontMetricsF(self.font(label_size)).height()
        available = max(12, box.height - label_height - 2)
        measured = self.measure(value, unit, box.width, available, size)
        total = label_height + 2 + measured["height"]
        y = box.y + max(0, (box.height - total) / 2)
        self.responsive_label(labels, Box(box.x, y, box.width, label_height), label_size, align)
        self.readout(
            value,
            unit,
            Box(box.x, y + label_height + 2, box.width, measured["height"]),
            size,
            align=align,
            measured=measured,
        )

    def compact(self, labels, value, unit, box, size):
        # Fixed logical text sizes: flattening a panel never flattens its font.
        self.responsive_stack(labels, value, unit, box, size, Qt.AlignmentFlag.AlignHCenter)

    def responsive_row(self, labels, value, unit, box, size):
        measured = self.measure(value, unit, box.width * 0.56, box.height, size)
        label_width = box.width - measured["width"] - 10
        if self.label_width(labels, 11) > label_width and box.height >= 40:
            self.responsive_stack(labels, value, unit, box, size)
            return
        self.responsive_label(labels, Box(box.x, box.y, max(1, label_width), box.height), 11)
        self.readout(
            value,
            unit,
            Box(box.right - measured["width"], box.y, measured["width"], box.height),
            size,
            Qt.AlignmentFlag.AlignRight,
            measured,
        )

    @staticmethod
    def _compact_numbers(value):
        yield value
        try:
            number = float(value)
        except (ValueError, OverflowError):
            return
        for digits in (3,):
            mantissa, exponent = f"{number:.{digits - 1}e}".split("e")
            mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
            yield mantissa + "e" + str(int(exponent))

    def measure(self, value, unit, width, height, size):
        unit = unit if value != "—" else ""
        initial = max(self.number_min, min(size, height * 0.86))
        minimum = min(initial, self.number_min)
        selected = None
        for number in self._compact_numbers(value):
            current = initial
            while current >= minimum - 0.01:
                number_font = self.font(current, QFont.Weight.DemiBold)
                unit_font = self.font(max(self.unit_min, current * 0.42 + 2))
                number_metrics = QFontMetricsF(number_font)
                unit_metrics = QFontMetricsF(unit_font)
                gap = max(3, current * 0.12) if unit else 0
                advance = number_metrics.horizontalAdvance(number)
                suffix = unit_metrics.horizontalAdvance(unit)
                number_ink = number_metrics.tightBoundingRect(number)
                unit_ink = unit_metrics.tightBoundingRect(unit)
                left = min(0, number_ink.left())
                right = max(advance, number_ink.right())
                top, bottom = number_ink.top(), number_ink.bottom()
                if unit:
                    right = max(right, advance + gap + max(suffix, unit_ink.right()))
                    top, bottom = min(top, unit_ink.top()), max(bottom, unit_ink.bottom())
                selected = dict(
                    value=number,
                    unit=unit,
                    font=number_font,
                    unit_font=unit_font,
                    metrics=number_metrics,
                    unit_metrics=unit_metrics,
                    width=right - left,
                    number_width=advance,
                    gap=gap,
                    left=left,
                    top=top,
                    height=bottom - top,
                )
                if selected["width"] <= width + 0.01 and selected["height"] <= height + 0.5:
                    return selected
                current -= 1
        return selected

    def readout(self, value, unit, box, size, align=Qt.AlignmentFlag.AlignLeft, measured=None):
        if box.width <= 0 or box.height <= 0:
            return
        reading = measured or self.measure(value, unit, box.width, box.height, size)
        if reading is None:
            return
        painter = self.painter
        x = box.x
        if align == Qt.AlignmentFlag.AlignRight:
            x = box.right - reading["width"]
        elif align == Qt.AlignmentFlag.AlignHCenter:
            x += (box.width - reading["width"]) / 2
        x -= reading["left"]
        baseline = box.y + (box.height - reading["height"]) / 2 - reading["top"]
        painter.save()
        painter.setClipRect(self.rect(box), Qt.ClipOperation.IntersectClip)
        painter.setFont(reading["font"])
        painter.setPen(self.ink)
        painter.drawText(QPointF(x, baseline), reading["value"])
        if reading["unit"]:
            painter.setFont(reading["unit_font"])
            painter.setPen(self.muted)
            painter.drawText(
                QPointF(x + reading["number_width"] + reading["gap"], baseline), reading["unit"]
            )
        painter.restore()

    def needs_space(self, reading, value, unit, labels=()):
        if reading.mode == "ring":
            return False
        width, height = reading.box.width, reading.box.height
        if reading.mode == "row":
            width = max(1, width - self.label_width(labels) - 8) if labels else width * 0.80
        else:
            height -= QFontMetricsF(self.font(max(10, self.label_min))).height() + 2
            if labels and self.label_width(labels) > width + 0.01:
                return True
        measured = self.measure(value, unit, width, max(1, height), reading.size)
        return measured["width"] > width + 0.01 or measured["height"] > height + 0.5

    def stack(self, label, value, unit, box, size):
        label_height = QFontMetricsF(self.font(max(10, self.label_min))).height()
        available = max(1, box.height - label_height - 2)
        reading = self.measure(value, unit, box.width, available, size)
        number_height = min(available, reading["height"])
        total = label_height + 2 + number_height
        y = box.y + max(0, (box.height - total) / 2)
        self.metric_label(label, Box(box.x, y, box.width, label_height), 10)
        self.readout(
            value,
            unit,
            Box(box.x, y + label_height + 2, box.width, number_height),
            size,
            measured=reading,
        )

    def row(self, label, value, unit, box, size):
        # Names and readings are measured together. Keep a complete semantic
        # label before fitting the value; wide lists supply full-width rows.
        label_width = self.label_width(label)
        available = max(1, box.width - label_width - 8.5)
        measured = self.measure(value, unit, available, box.height, size)
        label_height = QFontMetricsF(self.font(max(10, self.label_min))).height()
        if (
            measured["width"] > available + 0.01
            and box.height >= label_height + measured["height"] + 2
        ):
            self.stack(label, value, unit, box, size)
            return
        value_width = min(box.width * 0.80, max(measured["width"] + 0.5, 1))
        label_box = Box(box.x, box.y, max(1, box.width - value_width - 8), box.height)
        self.metric_label(label, label_box, 10)
        self.readout(
            value,
            unit,
            Box(box.right - value_width, box.y, value_width, box.height),
            size,
            Qt.AlignmentFlag.AlignRight,
            measured,
        )

    def arc(self, box, current, maximum=100):
        painter = self.painter
        stroke = min(5, box.width * 0.075)
        rect = QRectF(
            box.x + stroke / 2, box.y + stroke / 2, box.width - stroke, box.height - stroke
        )
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(130, 145, 164, 36), stroke))
        painter.drawArc(rect, 0, 360 * 16)
        if numeric(current):
            painter.setPen(
                QPen(self.accent, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            )
            painter.drawArc(rect, 90 * 16, -round(min(1, max(0, current / maximum)) * 360 * 16))
        painter.restore()

    def ring(self, value, unit, label, current, space, size, maximum, box):
        inner_width = box.width * 0.80
        number_height = box.height * 0.40
        number_box = Box(
            box.x + (box.width - inner_width) / 2,
            box.y + box.height * 0.24,
            inner_width,
            number_height,
        )
        measured = self.measure(value, unit, number_box.width, number_box.height, size)
        if (
            measured["width"] > number_box.width + 0.01
            or measured["height"] > number_box.height + 0.5
            or self.label_width(label, 9) > box.width * 0.76 + 0.01
        ):
            diameter = min(32, space.height - 4)
            self.arc(
                Box(space.x, space.y + (space.height - diameter) / 2, diameter, diameter),
                current,
                maximum,
            )
            self.stack(
                label,
                value,
                unit,
                Box(space.x + diameter + 8, space.y, space.width - diameter - 8, space.height),
                size,
            )
            return
        self.arc(box, current, maximum)
        self.readout(value, unit, number_box, size, Qt.AlignmentFlag.AlignHCenter, measured)
        label_height = QFontMetricsF(self.font(max(9, self.label_min))).height()
        self.metric_label(
            label,
            Box(
                box.x + box.width * 0.12, box.y + box.height * 0.62, box.width * 0.76, label_height
            ),
            9,
            align=Qt.AlignmentFlag.AlignHCenter,
        )

    def bar(self, box, current, maximum):
        painter = self.painter
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(130, 145, 164, 32))
        painter.drawRoundedRect(self.rect(box), box.height / 2, box.height / 2)
        if numeric(current):
            painter.setBrush(self.accent)
            filled = Box(box.x, box.y, box.width * min(1, max(0, current / maximum)), box.height)
            painter.drawRoundedRect(self.rect(filled), box.height / 2, box.height / 2)

    def trend(self, box, history, metric, prefs, fresh):
        painter = self.painter
        points = [(index, metric_value(item, metric, prefs)) for index, item in enumerate(history)]
        valid = [value for _, value in points if numeric(value)]
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if len(valid) < 2 or not fresh:
            painter.setPen(QPen(QColor(130, 145, 164, 38), 0.8))
            painter.drawLine(QPointF(box.x, box.bottom - 2), QPointF(box.right, box.bottom - 2))
            return
        magnitude = max(1, max(abs(value) for value in valid))
        normalized = [value / magnitude for value in valid]
        margin = max(
            (max(normalized) - min(normalized)) * 0.12, abs(max(normalized)) * 0.04, 1 / magnitude
        )
        high = max(normalized) + margin
        low = min(normalized) - margin
        if min(normalized) >= 0:
            low = max(0, low)
        path = QPainterPath()
        connected = False
        for index, value in points:
            if not numeric(value):
                connected = False
                continue
            x = box.x + index / max(1, len(points) - 1) * box.width
            y = (
                box.bottom
                - 2
                - (value / magnitude - low) / max(1e-300, high - low) * max(1, box.height - 4)
            )
            if connected:
                path.lineTo(x, y)
            else:
                path.moveTo(x, y)
            connected = True
        painter.save()
        painter.setClipRect(self.rect(box), Qt.ClipOperation.IntersectClip)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                self.accent,
                1.4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(path)
        painter.restore()

    def cores(self, box, values):
        painter = self.painter
        if not values:
            self.label("—", box, 20)
            return
        painter.setPen(Qt.PenStyle.NoPen)
        for cell, value in zip(core_boxes(len(values), box), values):
            radius = min(1.5, cell.width / 3, cell.height / 3)
            painter.setBrush(QColor(130, 145, 164, 30))
            painter.drawRoundedRect(self.rect(cell), radius, radius)
            if numeric(value) and value > 0:
                fill = cell.height * min(1, max(0, value / 100))
                painter.setBrush(self.accent)
                painter.drawRoundedRect(
                    QRectF(cell.x, cell.bottom - fill, cell.width, fill), radius, radius
                )
