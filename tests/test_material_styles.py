"""Coating/readability contracts; QImage only, never touches desktop composition."""

import math
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from native_surface import MaterialSurface, paint_surface
from skin_styles import GLASS_DEFAULTS, GLASS_SKINS, SKINS, glass_options, palette


def luminance(color):
    values = [getattr(color, channel)() / 255 for channel in ("red", "green", "blue")]
    values = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values
    ]
    return sum(value * weight for value, weight in zip(values, (0.2126, 0.7152, 0.0722)))


def contrast(one, two):
    values = sorted((luminance(one), luminance(two)))
    return (values[1] + 0.05) / (values[0] + 0.05)


class RecordingPainter:
    def __init__(self, painter):
        self.painter = painter
        self.pen_widths = []

    def __getattr__(self, name):
        return getattr(self.painter, name)

    def setPen(self, pen):
        self.pen_widths.append(pen.widthF())
        self.painter.setPen(pen)


class MaterialStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_material_surface_consumes_continuous_config_in_its_actual_paint(self):
        for skin in GLASS_SKINS:
            for frosted in (False, True):
                for transparency in (0, 37.5, 100):
                    for curvature in (0, 37.5, 100):
                        config = dict(
                            skin=skin, glass_transparency=transparency, glass_curvature=curvature
                        )
                        image = QImage(80, 80, QImage.Format_ARGB32_Premultiplied)
                        image.fill(Qt.transparent)
                        surface = MaterialSurface()
                        surface.setWidth(80)
                        surface.setHeight(80)
                        surface.set_config(config)
                        surface.set_frosted(frosted)
                        painter = QPainter(image)
                        surface.paint(painter)
                        painter.end()
                        colors = palette(skin, frosted=frosted, **glass_options(config))
                        top, bottom = (QColor(colors[stop]).alpha() for stop in ("top", "bottom"))
                        expected = top + (bottom - top) * (40.5 / 80)
                        self.assertLessEqual(abs(image.pixelColor(40, 40).alpha() - expected), 1)

    def test_glass_options_inherit_each_field_and_keep_fractional_zero(self):
        self.assertEqual(GLASS_DEFAULTS, {"glass_transparency": 50.0, "glass_curvature": 50.0})
        self.assertEqual(glass_options({}), {"transparency": 50.0, "curvature": 50.0})
        config = dict(
            glass_transparency=37.5,
            glass_curvature=72.125,
            widgets={
                "a": dict(glass_transparency=0.0, glass_curvature=None),
                "b": dict(glass_transparency=None, glass_curvature=12.75),
            },
        )
        self.assertEqual(glass_options(config, "a"), {"transparency": 0.0, "curvature": 72.125})
        self.assertEqual(glass_options(config, "b"), {"transparency": 37.5, "curvature": 12.75})
        self.assertEqual(
            glass_options(config, "missing"), {"transparency": 37.5, "curvature": 72.125}
        )

    def test_glass_options_bad_values_cannot_generate_nonfinite_geometry(self):
        for value in (float("nan"), float("inf"), True, "37.5", 10**1000):
            self.assertEqual(
                glass_options(dict(glass_transparency=value, glass_curvature=value)),
                {"transparency": 50.0, "curvature": 50.0},
            )
            self.assertEqual(
                glass_options(
                    dict(glass_transparency=37.5, widgets={"a": dict(glass_transparency=value)}),
                    "a",
                )["transparency"],
                37.5,
            )

    def test_continuous_transparency_has_strict_endpoints_and_no_presets(self):
        for dark in (False, True):
            for skin in GLASS_SKINS:
                alpha = [
                    QColor(palette(skin, dark, transparency=value / 2)["bottom"]).alpha()
                    for value in range(201)
                ]
                self.assertEqual(alpha[0], 255)
                self.assertEqual(alpha[-1], 0)
                self.assertTrue(all(one >= two for one, two in zip(alpha, alpha[1:])))
                self.assertGreater(len(set(alpha)), 100)
                self.assertNotEqual(
                    palette(skin, dark, transparency=37.5)["bottom"],
                    palette(skin, dark, transparency=0)["bottom"],
                )
                self.assertNotEqual(
                    palette(skin, dark, transparency=37.5)["bottom"],
                    palette(skin, dark, transparency=100)["bottom"],
                )

    def test_glass_controls_do_not_change_non_glass_skins(self):
        for skin in ("card", "graphite", "minimal"):
            for dark in (False, True):
                baseline = palette(skin, dark)
                for transparency in (0, 37.5, 100):
                    for curvature in (0, 37.5, 100):
                        self.assertEqual(
                            palette(skin, dark, transparency=transparency, curvature=curvature),
                            baseline,
                        )

    def test_fallback_keeps_readable_coating_but_can_keep_glass_corner_shape(self):
        for skin in GLASS_SKINS:
            for transparency in (0, 37.5, 100):
                colors = palette(skin, frosted=False, transparency=transparency, curvature=37.5)
                self.assertEqual(QColor(colors["bottom"]).alpha(), 255)
                self.assertEqual(QColor(colors["top"]).alpha(), 255)
                self.assertEqual(colors["radius"], 15.0)

    def test_curvature_changes_actual_corner_coverage_without_padding(self):
        for dpr in (1, 1.25, 1.5, 1.75, 2):
            counts = []
            for curvature in (0, 37.5, 100):
                image = QImage(round(80 * dpr), round(80 * dpr), QImage.Format_ARGB32_Premultiplied)
                image.setDevicePixelRatio(dpr)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                painter.setRenderHint(QPainter.Antialiasing)
                paint_surface(
                    painter, 80, 80, palette("glass", transparency=0, curvature=curvature)
                )
                painter.end()
                counts.append(
                    sum(
                        image.pixelColor(x, y).alpha() > 200
                        for x in range(image.width())
                        for y in range(image.height())
                    )
                )
                self.assertGreater(image.pixelColor(image.width() // 2, 0).alpha(), 100)
                self.assertGreater(image.pixelColor(0, image.height() // 2).alpha(), 100)
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertGreater(counts[0], counts[1])
            self.assertGreater(counts[1], counts[2])

    def test_frost_and_tint_keep_their_existing_coating_depth_separation(self):
        for dark in (False, True):
            for level in (45, 94, 100):
                alpha = {
                    skin: QColor(palette(skin, dark, level)["bottom"]).alpha()
                    for skin in ("frost", "tint")
                }
                self.assertGreaterEqual(alpha["frost"] - alpha["tint"], 40)

    def test_solid_fallbacks_remain_readable_and_distinct(self):
        for dark in (False, True):
            coatings = [palette(skin, dark, frosted=False) for skin in GLASS_SKINS]
            self.assertEqual(len({item["bottom"] for item in coatings}), 3)
            for skin in SKINS.keys() - {"minimal"}:
                colors = palette(skin, dark, frosted=False)
                face = QColor(colors["bottom"])
                # Include the remaining alpha against both opposite extremes.
                for under in (0, 255):
                    final = QColor(
                        *[
                            round(getattr(face, c)() * face.alphaF() + under * (1 - face.alphaF()))
                            for c in ("red", "green", "blue")
                        ]
                    )
                    self.assertGreaterEqual(contrast(QColor(colors["ink"]), final), 7)
                    self.assertGreaterEqual(contrast(QColor(colors["muted"]), final), 4.5)

    def test_minimal_never_paints_a_surface(self):
        for dark in (False, True):
            for frosted in (False, True):
                image = QImage(80, 80, QImage.Format_ARGB32_Premultiplied)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                paint_surface(painter, 80, 80, palette("minimal", dark, frosted=frosted))
                painter.end()
                self.assertTrue(
                    all(image.pixelColor(x, y).alpha() == 0 for x in range(80) for y in range(80))
                )

    def test_light_edge_is_one_physical_pixel_at_every_supported_dpi(self):
        for dpr in (1, 1.25, 1.5, 1.75, 2):
            for scale in (0.7125, 1, 1.6875):
                image = QImage(
                    math.ceil(168 * dpr), math.ceil(168 * dpr), QImage.Format_ARGB32_Premultiplied
                )
                image.setDevicePixelRatio(dpr)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                painter.scale(scale, scale)
                before = (painter.pen(), painter.brush(), painter.worldTransform())
                recording = RecordingPainter(painter)
                paint_surface(recording, 168 / scale, 168 / scale, palette("glass"))
                self.assertEqual(len(recording.pen_widths), 1)
                self.assertAlmostEqual(recording.pen_widths[0] * scale * dpr, 1)
                self.assertEqual(before, (painter.pen(), painter.brush(), painter.worldTransform()))
                painter.end()
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_bad_optional_accent_cannot_break_a_material(self):
        for accent in (None, "bad", "#oops!!", 123):
            self.assertEqual(palette("tint", accent=accent), palette("tint"))
