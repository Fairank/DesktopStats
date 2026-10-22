"""One vector surface implementation for individual and combined widgets."""

from math import hypot

from PySide6.QtCore import Property, QRectF, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtQuick import QQuickPaintedItem

from skin_styles import effective_skin, glass_options, palette


def paint_surface(painter, width, height, colors, radius=None):
    """One rounded coating and one physical-pixel light edge; no grey frame."""
    if colors["transparent"] or width <= 0 or height <= 0:
        return
    transform = painter.worldTransform()
    pixels_per_unit = max(
        hypot(transform.m11(), transform.m12()),
        hypot(transform.m21(), transform.m22()),
        0.01,
    ) * max(painter.device().devicePixelRatioF(), 0.01)
    stroke = min(1 / pixels_per_unit, min(width, height) / 4)
    inset = stroke / 2
    corner = min(colors.get("radius", 18) if radius is None else radius, width / 2, height / 2)
    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0, QColor(colors["top"]))
    gradient.setColorAt(1, QColor(colors["bottom"]))
    edge = QLinearGradient(0, 0, 0, height)
    edge.setColorAt(0, QColor(colors.get("edge_top", colors["border"])))
    edge.setColorAt(1, QColor(colors.get("edge_bottom", colors["border"])))
    painter.save()
    painter.setBrush(gradient)
    painter.setPen(QPen(edge, stroke))
    painter.drawRoundedRect(
        QRectF(inset, inset, width - stroke, height - stroke),
        max(0, corner - inset), max(0, corner - inset),
    )
    painter.restore()


class MaterialSurface(QQuickPaintedItem):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = {}
        self._frosted = True
        self._radius = -1.0
        self.setAntialiasing(True)
        self.setOpaquePainting(False)

    def set_config(self, value):
        self._config = value or {}
        self.changed.emit()
        self.update()

    config = Property("QVariantMap", lambda self: self._config, set_config, notify=changed)

    def set_frosted(self, value):
        self._frosted = value
        self.changed.emit()
        self.update()

    frosted = Property(bool, lambda self: self._frosted, set_frosted, notify=changed)

    def set_radius(self, value):
        self._radius = max(-1.0, value)
        self.changed.emit()
        self.update()

    cornerRadius = Property(float, lambda self: self._radius, set_radius, notify=changed)

    def paint(self, painter):
        if self.width() <= 0 or self.height() <= 0:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        colors = palette(
            effective_skin(self._config),
            self._config.get("theme") == "dark",
            self._config.get("opacity", 94),
            frosted=self._frosted,
            **glass_options(self._config),
        )
        paint_surface(painter, self.width(), self.height(), colors, None if self._radius < 0 else self._radius)
