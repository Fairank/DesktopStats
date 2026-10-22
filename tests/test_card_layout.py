"""Readability and bounds of the actual native painter, without desktop windows."""

import copy
import math
import os
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/card-layout-unit-data"),
)

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFontDatabase, QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QApplication

from card_layout import Box, core_boxes, plan
from compact_labels import COMPACT_LABELS, label_options
from localization import LANGUAGES
from native_card import HardwareCard, _CardPainter
from stats_config import DEFAULT
from widget_catalog import widget_defaults

STYLES = ("auto", "hero", "list", "ring", "bar", "cores")
SELECTED = (
    "cpu_usage",
    "gpu_usage",
    "ram_percent",
    "battery_percent",
    "disk_percent",
    "cpu_temp",
)
READINGS = dict(zip(SELECTED, (11, 22, 33, 44, 55, 66)))


class MeasuringPainter:
    """Record real draw calls and glyph bounds before any clipping can hide bugs."""

    def __init__(self, painter):
        self.painter = painter
        self.runs = []
        self.labels = []
        self.paths = []
        self.overflows = []

    def __getattr__(self, name):
        return getattr(self.painter, name)

    def drawText(self, *args):
        if isinstance(args[0], QPointF):
            origin, text = args
            font = self.painter.font()
            bounds = QFontMetricsF(font).tightBoundingRect(text).translated(origin)
            clip = self.painter.clipBoundingRect()
            tolerance = 0.8
            if not clip.adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(bounds):
                self.overflows.append(dict(text=text, bounds=bounds, clip=clip))
            self.runs.append(dict(text=text, baseline=origin.y(), font=font.pixelSize()))
        elif isinstance(args[0], QRectF):
            rect, flags, text = args
            font = self.painter.font()
            metrics = QFontMetricsF(font)
            bounds = metrics.boundingRect(rect, flags, text)
            clip = self.painter.clipBoundingRect()
            x = rect.x()
            if flags & Qt.AlignmentFlag.AlignRight:
                x = rect.right() - metrics.horizontalAdvance(text)
            elif flags & Qt.AlignmentFlag.AlignHCenter:
                x = rect.x() + (rect.width() - metrics.horizontalAdvance(text)) / 2
            glyph_bounds = metrics.tightBoundingRect(text).translated(
                x, bounds.y() + metrics.ascent())
            self.labels.append(dict(
                text=text, font=font.pixelSize(), rect=rect, bounds=bounds, clip=clip,
                advance=metrics.horizontalAdvance(text),
                glyph_bounds=glyph_bounds,
                glyph_fits=clip.adjusted(-.8, -.8, .8, .8).contains(glyph_bounds),
            ))
        return self.painter.drawText(*args)

    def drawPath(self, path):
        self.paths.append(dict(brush=self.painter.brush().style(), bounds=path.boundingRect()))
        return self.painter.drawPath(path)


def render_card(
    size=168,
    wide=False,
    count=6,
    style="auto",
    title=True,
    language="zh-CN",
    readings=None,
    content=None,
    kind="cpu",
    footer=False,
    skin="card",
    theme="light",
    custom_title="",
    history=None,
):
    width = size * 2 + 8 if wide else size
    config = copy.deepcopy(DEFAULT)
    prefs = widget_defaults(kind)
    prefs.update(
        content=list(content or SELECTED[:count]),
        presentation=style,
        show_title=title,
        skin=None,
        title=custom_title,
    )
    if footer:
        prefs["kind"] = "power"
    config.update(
        widgets={"test": prefs},
        widget_order=["test"],
        theme=theme,
        skin=skin,
        language=language,
    )
    values = (
        dict(READINGS, time=time.time(), cpu_per_core=[(index * 17) % 101 for index in range(128)])
        if readings is None
        else readings
    )
    card = HardwareCard()
    card.setWidth(width)
    card.setHeight(size)
    card.set_config(config)
    card.set_key("test")
    card.set_data(values)
    card.set_history(
        history
        if history is not None
        else [dict(values, cpu_usage=index * 3) for index in range(30)]
    )
    image = QImage(width, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    measured = MeasuringPainter(painter)
    card.paint(measured)
    painter.end()
    return image, measured


class CardLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        for file in (
            "msyh.ttc",
            "msyhbd.ttc",
            "msjh.ttc",
            "msjhbd.ttc",
            "segoeui.ttf",
            "SegUIVar.ttf",
            "malgun.ttf",
            "YuGothR.ttc",
        ):
            path = Path("C:/Windows/Fonts") / file
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))

    def assert_inside(self, outer, inner):
        self.assertGreater(inner.width, 0)
        self.assertGreater(inner.height, 0)
        self.assertGreaterEqual(inner.x + 1e-6, outer.x)
        self.assertGreaterEqual(inner.y + 1e-6, outer.y)
        self.assertLessEqual(inner.right - 1e-6, outer.right)
        self.assertLessEqual(inner.bottom - 1e-6, outer.bottom)

    def test_every_style_keeps_all_readings_in_nonoverlapping_bounded_slots(self):
        for style in STYLES:
            for count in range(1, 7):
                for width in (160, 328):
                    for title in (False, True):
                        for footer in (False, True):
                            with self.subTest(
                                style=style, count=count, width=width, title=title, footer=footer
                            ):
                                layout = plan(width, count, style, title, chart=True, footer=footer)
                                self.assertEqual(
                                    [slot.index for slot in layout.readings], list(range(count))
                                )
                                for slot in layout.readings:
                                    self.assert_inside(layout.body, slot.box)
                                for a, first in enumerate(layout.readings):
                                    for second in layout.readings[a + 1 :]:
                                        x = min(first.box.right, second.box.right) - max(
                                            first.box.x, second.box.x
                                        )
                                        y = min(first.box.bottom, second.box.bottom) - max(
                                            first.box.y, second.box.y
                                        )
                                        self.assertTrue(x <= 1e-6 or y <= 1e-6)
                                for decoration in (
                                    layout.chart,
                                    layout.ring,
                                    layout.cores,
                                    layout.core_caption,
                                ):
                                    if decoration:
                                        self.assert_inside(layout.body, decoration)

    def test_large_core_counts_fit_inside_their_actual_grid_without_overlaps(self):
        for count in (1, 2, 8, 16, 32, 64, 128, 192, 256, 512):
            for box in (Box(14, 130, 132, 16), Box(14, 100, 300, 46)):
                cells = core_boxes(count, box)
                self.assertEqual(len(cells), count)
                for index, cell in enumerate(cells):
                    self.assert_inside(box, cell)
                    if index and math.isclose(cell.y, cells[index - 1].y):
                        self.assertGreaterEqual(cell.x, cells[index - 1].right)

    def test_painter_emits_every_selected_number_for_all_presentations(self):
        for style in STYLES:
            for count in range(1, 7):
                for size in (114, 270):
                    for wide in (False, True):
                        for title in (False, True):
                            with self.subTest(
                                style=style, count=count, size=size, wide=wide, title=title
                            ):
                                _, result = render_card(size, wide, count, style, title)
                                numbers = [run["text"] for run in result.runs]
                                for value in list(READINGS.values())[:count]:
                                    self.assertIn(str(value), numbers)
                                self.assertFalse(result.overflows, result.overflows)

    def test_units_use_a_smaller_font_on_the_same_baseline_as_the_number(self):
        for size in (114, 168, 270):
            for style in STYLES:
                _, result = render_card(size=size, count=1, style=style)
                number = next(index for index, run in enumerate(result.runs) if run["text"] == "11")
                value, unit = result.runs[number : number + 2]
                self.assertEqual(unit["text"], "%")
                self.assertEqual(value["baseline"], unit["baseline"])
                self.assertLess(unit["font"], value["font"])

    def test_minimum_wide_power_list_keeps_full_meaning_and_uses_complete_rows(self):
        content = ("cpu_power", "gpu_power", "battery_discharge_watts")
        values = dict(time=time.time(), cpu_power=55.1, gpu_power=30.7,
                      battery_discharge_watts=0, battery_watts=0,
                      battery_present=True, power_online=True)
        expected = {
            "zh-CN": ("CPU 封装功率", "GPU 功率", "电池放电输出"),
            "de": ("CPU-Paketleistung", "GPU-Leist.", "Batterie-Entladeleistung"),
        }
        for language, names in expected.items():
            for title in (False, True):
                _, result = render_card(114, wide=True, style="list", title=title,
                    language=language, readings=values, content=content, kind="power")
                with self.subTest(language=language, title=title):
                    drawn = [label["text"] for label in result.labels]
                    for name in names:
                        self.assertIn(name, drawn)
                    self.assertFalse(any("…" in label for label in drawn))
                    self.assertFalse(result.overflows, result.overflows)
                    self.assertEqual([r["text"] for r in result.runs],
                                     ["55.1", "W", "30.7", "W", "0.0", "W"])
                    for label in result.labels:
                        self.assertLessEqual(label["advance"], label["clip"].width() + .01)
                        self.assertGreaterEqual(label["font"] * 114 / 160, 9)
                        self.assertTrue(label["glyph_fits"], label)
        layout = plan(236 / (114 / 160), 3, "list", True, footer=True)
        self.assertTrue(all(r.box.x == layout.body.x and r.box.width == layout.body.width
                            for r in layout.readings))
        self.assertEqual(len({r.box.y for r in layout.readings}), 3)

    def test_compact_catalogue_has_every_fixed_metric_and_all_eight_languages(self):
        from external_sensor import EXTERNAL_SLOTS
        from metrics import METRICS
        # Discovered channels use their provider's literal name, not a shared
        # label for the generic binding slot (which could misidentify hardware).
        self.assertEqual(set(COMPACT_LABELS), set(METRICS) - set(EXTERNAL_SLOTS))
        for metric, translations in COMPACT_LABELS.items():
            self.assertEqual(set(translations), set(LANGUAGES), metric)
            self.assertTrue(all(text and "…" not in text for text in translations.values()), metric)
        for language in LANGUAGES:
            for slot in EXTERNAL_SLOTS:
                self.assertEqual(label_options(slot, "original 内存", language), ("original 内存",))
            self.assertNotEqual(COMPACT_LABELS["battery_charge_watts"][language],
                                COMPACT_LABELS["battery_discharge_watts"][language])

    def test_three_power_labels_remain_complete_across_all_presentations(self):
        from localization import translate
        from metrics import METRICS
        content = ("cpu_power", "gpu_power", "battery_discharge_watts")
        values = dict(time=time.time(), cpu_power=55.1, gpu_power=30.7,
                      battery_discharge_watts=0, battery_watts=0,
                      battery_present=True, power_online=True)
        for language in LANGUAGES:
            for style in STYLES:
                with self.subTest(language=language, style=style):
                    _, result = render_card(114, wide=True, style=style, language=language,
                        readings=values, content=content, kind="power")
                    labels = {r["text"] for r in result.labels}
                    for metric in content:
                        self.assertTrue(labels.intersection({
                            translate(METRICS[metric]["label"], language),
                            COMPACT_LABELS[metric][language]}), (metric, labels))
                    self.assertFalse(result.overflows, result.overflows)
                    for label in result.labels:
                        self.assertLessEqual(label["advance"], label["clip"].width() + .01,
                                             label)
                        self.assertTrue(label["glyph_fits"], label)

    def test_unit_size_changes_smoothly_across_24_to_25(self):
        image = QImage(240, 160, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        helper = _CardPainter(painter, DEFAULT, {"ink":"#222222", "muted":"#666666"},
                              "#2288ff", 1)
        units = [helper.measure("55.1", "W", 200, 100, size)["unit_font"].pixelSize()
                 for size in (23, 24, 25, 26)]
        painter.end()
        self.assertTrue(all(abs(a-b) <= 1 for a,b in zip(units, units[1:])), units)

    def test_small_wide_power_names_and_numbers_fit_in_all_eight_languages(self):
        from localization import translate
        from metrics import METRICS
        content = ("cpu_power", "gpu_power", "battery_charge_watts",
                   "battery_discharge_watts", "adapter_input_watts", "system_power")
        values = dict(zip(content, (55.1, 30.7, 8.9, 0, 120, 100)))
        values.update(time=time.time(), battery_watts=8.9, battery_present=True,
                      charging=True, power_online=True)
        for language in LANGUAGES:
            for count in range(1, 7):
                with self.subTest(language=language, count=count):
                    _, result = render_card(114, wide=True, style="list", language=language,
                        readings=values, content=content[:count], kind="power")
                    labels = {r["text"] for r in result.labels}
                    for metric in content[:count]:
                        self.assertTrue(labels.intersection({
                            translate(METRICS[metric]["label"], language),
                            COMPACT_LABELS[metric][language]}), (metric, labels))
                    self.assertFalse(result.overflows, result.overflows)
                    for label in result.labels:
                        self.assertLessEqual(label["advance"], label["clip"].width() + .01,
                                             label)
                        self.assertTrue(label["glyph_fits"], label)

    def test_long_numbers_fit_without_losing_leading_digits_in_eight_languages(self):
        content = (
            "cpu_frequency",
            "ram_used_gb",
            "net_received_gb",
            "net_download",
            "voltage",
            "disk_total_gb",
        )
        values = dict(zip(content, (567.891, 1234567.89, 6543210.12, 1234.56, 24.123, 9999999.5)))
        values.update(time=time.time(), cpu_per_core=[50] * 128)
        for language in LANGUAGES:
            for style in STYLES:
                for size in (114, 270):
                    for wide in (False, True):
                        with self.subTest(language=language, style=style, size=size, wide=wide):
                            _, result = render_card(
                                size,
                                wide,
                                style=style,
                                language=language,
                                readings=values,
                                content=content,
                            )
                            self.assertFalse(result.overflows, result.overflows)
                            self.assertEqual(len(result.runs), 12)

    def test_missing_and_stale_values_stay_unavailable_in_every_style(self):
        for style in STYLES:
            for values in (
                {},
                dict(READINGS, time=time.time() - 40),
                dict(READINGS, time=time.time() + 5),
                dict.fromkeys(SELECTED, float("nan")),
            ):
                _, result = render_card(style=style, readings=values)
                self.assertEqual([run["text"] for run in result.runs], ["—"] * 6)

    def test_sparkline_has_no_fill_brush(self):
        _, result = render_card(count=1)
        self.assertEqual(len(result.paths), 1)
        self.assertEqual(result.paths[0]["brush"], Qt.BrushStyle.NoBrush)

    def test_negative_and_extreme_trends_stay_finite_and_inside_plot(self):
        for values in ((-90, -20, None, -60), (-1.7e308, 1.7e308, None, -1e308), (0, 0, None, 0)):
            image = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
            painter = QPainter(image)
            measured = MeasuringPainter(painter)
            helper = _CardPainter(
                measured, DEFAULT, {"ink": "#222222", "muted": "#666666"}, "#2288ff", 1
            )
            box = Box(14, 115, 132, 25)
            helper.trend(
                box, [{"battery_watts": value} for value in values], "battery_watts", {}, True
            )
            painter.end()
            self.assertEqual(len(measured.paths), 1)
            bounds = measured.paths[0]["bounds"]
            self.assertTrue(
                all(
                    math.isfinite(value)
                    for value in (bounds.x(), bounds.y(), bounds.width(), bounds.height())
                )
            )
            self.assertGreaterEqual(bounds.top(), box.y)
            self.assertLessEqual(bounds.bottom(), box.bottom)

    def test_very_long_readout_uses_explicit_scientific_notation(self):
        image = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        helper = _CardPainter(
            painter, DEFAULT, {"ink": "#222222", "muted": "#666666"}, "#2288ff", 114 / 160
        )
        available = (160 - 28) * 0.8
        result = helper.measure("12345678901234567890.00", "MB/s", available, 18, 15)
        painter.end()
        self.assertIn("e", result["value"])
        self.assertLessEqual(result["width"], available)
        self.assertEqual(result["value"], "1.23e19")

    def test_small_ring_moves_long_reading_outside_circle_and_keeps_precision(self):
        values = {"time": time.time(), "cpu_frequency": 567.891, "ram_used_gb": 1234567.89}
        _, result = render_card(
            114, count=2, style="ring", readings=values, content=("cpu_frequency", "ram_used_gb")
        )
        self.assertFalse(result.overflows, result.overflows)
        self.assertIn("567.89", [run["text"] for run in result.runs])


if __name__ == "__main__":
    unittest.main()
