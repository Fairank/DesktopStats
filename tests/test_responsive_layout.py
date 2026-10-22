"""Two-dimensional pure plans and actual-DIP painter tests; no shown windows."""

import copy
import math
import os
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/redesign09/responsive-unit-profile"),
)

from responsive_layout import (
    ResponsiveLayoutError,
    dimensions,
    is_responsive,
    metric_rects,
    minimum_dimensions,
    responsive_plan,
)
from stats_config import DEFAULT
from widget_catalog import widget_defaults

CONTENT = [
    "cpu_temp",
    "cpu_usage",
    "cpu_power",
    "gpu_fan_rpm",
    "battery_charge_watts",
    "net_download",
]


def configuration(width=900, height=40, count=6, mode="auto", title=False):
    config = copy.deepcopy(DEFAULT)
    prefs = widget_defaults("custom")
    prefs.update(
        content=CONTENT[:count],
        form="bar",
        width=width,
        height=height,
        layout_mode=mode,
        columns=2,
        metric_positions={},
        show_title=title,
    )
    config.update(widgets={"test": prefs}, widget_order=["test"])
    return config, prefs


def placements(metrics):
    columns = min(3, len(metrics))
    rows = math.ceil(len(metrics) / columns)
    return {
        metric: dict(
            x=index % columns / columns,
            y=index // columns / rows,
            width=1 / columns,
            height=1 / rows,
        )
        for index, metric in enumerate(metrics)
    }


class ResponsiveLayoutTests(unittest.TestCase):
    def test_legacy_null_geometry_remains_unchanged(self):
        for form in ("square", "wide"):
            config, prefs = configuration()
            prefs.update(width=None, height=None, form=form, layout_mode="auto", size=76)
            self.assertFalse(is_responsive(prefs))
            self.assertEqual(
                dimensions(config, "test"), (272, 132) if form == "wide" else (132, 132)
            )
            prefs["content"] = CONTENT[:3]
            self.assertEqual(
                dimensions(config, "test"), (236, 114) if form == "wide" else (114, 114)
            )

    def test_bar_has_fixed_readable_actual_dip_sizes_and_narrow_request_reflows(self):
        config, prefs = configuration()
        self.assertEqual(minimum_dimensions(prefs), (148, 38))
        self.assertEqual(dimensions(config, "test"), (900, 40))
        prefs["width"] = 320
        original = copy.deepcopy(prefs)
        self.assertEqual(dimensions(config, "test"), (320, 114))
        self.assertEqual(prefs, original, "Effective dimensions must not rewrite user requests")
        prefs["show_title"] = True
        self.assertEqual(dimensions(config, "test"), (320, 136))
        with self.assertRaises(ResponsiveLayoutError):
            responsive_plan(320, 40, CONTENT, prefs)

    def test_every_mode_and_dimension_preserves_all_bounded_nonoverlapping_slots(self):
        for count in range(1, 7):
            for mode in ("auto", "horizontal", "vertical", "grid"):
                for width in (320, 900, 1400):
                    for height in (40, 56, 132, 300):
                        for title in (False, True):
                            with self.subTest(
                                count=count, mode=mode, width=width, height=height, title=title
                            ):
                                config, prefs = configuration(width, height, count, mode, title)
                                w, h = dimensions(config, "test")
                                layout = responsive_plan(w, h, prefs["content"], prefs)
                                self.assertEqual(
                                    [r.index for r in layout.readings], list(range(count))
                                )
                                for reading in layout.readings:
                                    box = reading.box
                                    self.assertGreaterEqual(box.x, layout.body.x - 0.01)
                                    self.assertGreaterEqual(box.y, layout.body.y - 0.01)
                                    self.assertLessEqual(box.right, layout.body.right + 0.01)
                                    self.assertLessEqual(box.bottom, layout.body.bottom + 0.01)
                                    self.assertGreaterEqual(box.width, 128 - 0.01)
                                    self.assertGreaterEqual(box.height, 30 - 0.01)
                                for index, a in enumerate(layout.readings):
                                    for b in layout.readings[index + 1 :]:
                                        self.assertFalse(
                                            min(a.box.right, b.box.right)
                                            > max(a.box.x, b.box.x) + 0.01
                                            and min(a.box.bottom, b.box.bottom)
                                            > max(a.box.y, b.box.y) + 0.01
                                        )

    def test_manual_rectangles_are_normalized_against_exact_shared_body_and_metric_ids(self):
        config, prefs = configuration(900, 132, mode="manual", title=True)
        prefs["metric_positions"] = placements(CONTENT)
        layout = responsive_plan(*dimensions(config, "test"), CONTENT, prefs)
        original = metric_rects(layout, CONTENT)
        self.assertEqual([row["id"] for row in metric_rects(layout)], CONTENT)
        reversed_metrics = list(reversed(CONTENT))
        reordered = metric_rects(
            responsive_plan(900, 132, reversed_metrics, prefs), reversed_metrics
        )
        self.assertEqual(
            {r["metric"]: (r["x"], r["y"], r["width"], r["height"]) for r in original},
            {r["metric"]: (r["x"], r["y"], r["width"], r["height"]) for r in reordered},
        )
        self.assertEqual(original[0]["x"], layout.body.x)
        self.assertEqual(original[0]["y"], layout.body.y)
        self.assertAlmostEqual(original[0]["width"], layout.body.width / 3)
        self.assertAlmostEqual(original[0]["height"], layout.body.height / 2)

    def test_manual_partial_overlap_and_invalid_geometry_are_explicit_errors(self):
        _, prefs = configuration(900, 132, mode="manual")
        for positions in (
            {},
            {CONTENT[0]: dict(x=0, y=0, width=1, height=1)},
            {m: dict(x=0, y=0, width=1, height=1) for m in CONTENT},
            {m: dict(x=0, y=0, width=math.nan, height=1) for m in CONTENT},
        ):
            prefs["metric_positions"] = positions
            with self.assertRaises(ResponsiveLayoutError):
                responsive_plan(900, 132, CONTENT, prefs)

    def test_large_regular_single_channel_preserves_ring_bar_core_and_history_regions(self):
        config, prefs = configuration(320, 300, count=1)
        for presentation, field in (
            ("ring", "ring"),
            ("bar", "chart"),
            ("cores", "cores"),
            ("auto", "chart"),
        ):
            prefs.update(presentation=presentation, chart=True)
            layout = responsive_plan(320, 300, prefs["content"], prefs)
            self.assertIsNotNone(getattr(layout, field))


class ResponsivePainterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_card_layout import CardLayoutTests

        CardLayoutTests.setUpClass()

    @staticmethod
    def render(config, data, dpr=1):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        from test_card_layout import MeasuringPainter

        from native_card import HardwareCard

        width, height = dimensions(config, "test")
        image = QImage(
            math.ceil(width * dpr), math.ceil(height * dpr), QImage.Format_ARGB32_Premultiplied
        )
        image.setDevicePixelRatio(dpr)
        image.fill(Qt.GlobalColor.transparent)
        card = HardwareCard()
        card.setWidth(width)
        card.setHeight(height)
        card.set_config(config)
        card.set_key("test")
        card.set_data(data)
        painter = QPainter(image)
        measured = MeasuringPainter(painter)
        card.paint(measured)
        painter.end()
        return image, card, measured

    def test_real_fonts_fixed_dip_sizes_all_values_units_hit_targets_and_both_themes(self):
        from native_card import formatted

        data = dict(
            time=time.time(),
            cpu_temp=85,
            cpu_usage=100,
            cpu_power=0,
            gpu_fan_rpm=5600,
            battery_charge_watts=12.3,
            net_download=1234.56,
        )
        for language in ("zh-CN", "de"):
            for theme in ("light", "dark"):
                for width in (320, 900, 1400):
                    for height in (40, 56, 132, 300):
                        for dpr in (1, 1.75):
                            with self.subTest(
                                language=language, theme=theme, width=width, height=height, dpr=dpr
                            ):
                                config, prefs = configuration(width, height)
                                config.update(language=language, theme=theme, skin="card")
                                prefs["temperature_unit"] = "F"
                                _, card, drawn = self.render(config, data, dpr)
                                self.assertFalse(drawn.overflows, drawn.overflows)
                                expected = [
                                    part
                                    for metric in CONTENT
                                    for part in formatted(data, metric, prefs)
                                ]
                                self.assertEqual([run["text"] for run in drawn.runs], expected)
                                for index, run in enumerate(drawn.runs):
                                    self.assertGreaterEqual(
                                        run["font"], 12 if index % 2 == 0 else 9
                                    )
                                for label in drawn.labels:
                                    self.assertGreaterEqual(label["font"], 10)
                                    self.assertTrue(label["glyph_fits"], label)
                                layout = responsive_plan(
                                    card.width(), card.height(), CONTENT, prefs
                                )
                                for reading in layout.readings:
                                    box = reading.box
                                    self.assertEqual(
                                        card.metricAt(
                                            box.x + box.width / 2, box.y + box.height / 2
                                        ),
                                        reading.index,
                                    )
                                self.assertEqual(card.metricAt(0, 0), -1)
                                first = layout.readings[0].box
                                self.assertEqual(
                                    card.metricAt(first.right + 4, first.y + first.height / 2), -1
                                )

    def test_external_full_literal_name_and_units_survive_compact_label_and_missing_data(self):
        name = "CPU 温度 – Präzisionslüfter Sensor / very long literal hardware label"
        config, prefs = configuration(148, 40, count=1)
        prefs["content"] = ["external_1"]
        prefs["sensor_bindings"] = {
            "external_1": dict(
                provider="LibreHardwareMonitor",
                sensor_id="/fan/0",
                sensor_type="Fan",
                name=name,
                hardware_name="Exact device",
            )
        }
        config["language"] = "de"
        for value in (0, 5600, None):
            data = dict(
                time=time.time(),
                external_sensors={"/fan/0": dict(type="Fan", id="/fan/0", unit="RPM", value=value)},
            )
            _, card, drawn = self.render(config, data)
            layout = responsive_plan(card.width(), card.height(), prefs["content"], prefs)
            box = layout.readings[0].box
            self.assertEqual(card.metricLabelAt(box.x + 1, box.y + 1), name)
            self.assertFalse(drawn.overflows)
            self.assertTrue(any("…" in item["text"] for item in drawn.labels))
            self.assertEqual(
                [r["text"] for r in drawn.runs], [str(value), "RPM"] if value is not None else ["—"]
            )

    def test_manual_hit_targets_follow_ids_and_titles_and_gaps_are_not_metrics(self):
        config, prefs = configuration(900, 132, mode="manual", title=True)
        prefs["metric_positions"] = placements(CONTENT)
        _, card, _ = self.render(config, dict(time=time.time()))
        layout = responsive_plan(card.width(), card.height(), CONTENT, prefs)
        self.assertEqual(card.metricAt(layout.title.x + 1, layout.title.y + 1), -1)
        self.assertEqual(card.metricAt(float("nan"), 0), -1)
        for index, reading in enumerate(layout.readings):
            box = reading.box
            self.assertEqual(card.metricAt(box.x + box.width / 2, box.y + box.height / 2), index)

    def test_six_external_literal_labels_keep_zero_fahrenheit_rpm_and_all_units(self):
        from native_card import formatted

        config, prefs = configuration(320, 40)
        slots = [f"external_{index}" for index in range(1, 7)]
        types = ("Power", "Fan", "Temperature", "Voltage", "Current", "Load")
        units = ("W", "RPM", "°C", "V", "A", "%")
        values = (0, 5600, 0, 12.345, -1.25, 100)
        names = [
            f"CPU 温度 literal Präzisionssensor / port {index} – original name, not UI translation"
            for index in range(6)
        ]
        prefs.update(
            content=slots,
            temperature_unit="F",
            sensor_bindings={
                slot: dict(
                    provider="LibreHardwareMonitor",
                    sensor_id=f"/test/{index}",
                    sensor_type=types[index],
                    name=names[index],
                    hardware_name="Literal hardware",
                )
                for index, slot in enumerate(slots)
            },
        )
        config["language"] = "de"
        data = dict(
            time=time.time(),
            external_sensors={
                f"/test/{index}": dict(
                    type=types[index], id=f"/test/{index}", unit=units[index], value=values[index]
                )
                for index in range(6)
            },
        )
        _, card, drawn = self.render(config, data)
        self.assertEqual(
            [run["text"] for run in drawn.runs],
            [part for slot in slots for part in formatted(data, slot, prefs)],
        )
        self.assertFalse(drawn.overflows, drawn.overflows)
        layout = responsive_plan(card.width(), card.height(), slots, prefs)
        for reading in layout.readings:
            box = reading.box
            self.assertEqual(
                card.metricLabelAt(box.x + box.width / 2, box.y + box.height / 2),
                names[reading.index],
            )


if __name__ == "__main__":
    unittest.main()
