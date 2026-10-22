"""Accepted settings colors reused through QImage painting, never a live window."""

import copy
import os
import re
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from native_card import HardwareCard
from native_surface import MaterialSurface
from skin_styles import GLASS_DEFAULTS, palette
from stats_config import DEFAULT

THEME = Path(__file__).resolve().parents[1] / "native/Theme.qml"


def theme_pair(name, digits=8, seen=()):
    if name in seen:
        raise AssertionError("Cyclic theme token: " + name)
    line = re.search(r"readonly property color " + name + r":([^\n]+)", THEME.read_text(encoding="utf-8"))
    if line is None:
        raise AssertionError("Accepted settings token is missing: " + name)
    value = line.group(1).strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return theme_pair(value, digits, (*seen, name))
    colors = re.findall(r"#[0-9a-fA-F]{" + str(digits) + r"}\b", value)[:2]
    if len(colors) != 2:
        raise AssertionError("Two explicit theme colors required: " + name)
    return colors


def render_item(item):
    image = QImage(160, 160, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    try:
        item.paint(painter)
    finally:
        painter.end()
    return image


class MainWindowPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_glass_exactly_matches_accepted_settings_tokens(self):
        self.assertEqual(GLASS_DEFAULTS["glass_transparency"], 50)
        for dark in (False, True):
            colors = palette("glass", dark, transparency=50)
            index = 0 if dark else 1
            self.assertEqual(colors["top"], theme_pair("windowTop")[index])
            self.assertEqual(colors["bottom"], theme_pair("windowBottom")[index])
            self.assertEqual(colors["ink"], theme_pair("ink", 6)[index])
            self.assertEqual(colors["muted"], theme_pair("muted", 6)[index])
            self.assertEqual(colors["edge_top"], theme_pair("line")[index])
            self.assertEqual(colors["edge_bottom"], theme_pair("line")[index])
            self.assertEqual(palette("glass", dark), colors)

    def test_continuous_alpha_has_exact_endpoints_and_settings_midpoint(self):
        for dark in (False, True):
            for stop in ("top", "bottom"):
                values = [QColor(palette("glass", dark, transparency=step / 20)[stop]).alpha()
                          for step in range(2001)]
                anchor = QColor(theme_pair("windowTop" if stop == "top" else "windowBottom")[0 if dark else 1]).alpha()
                self.assertEqual((values[0], values[1000], values[-1]), (255, anchor, 0))
                self.assertTrue(all(0 <= one - two <= 1 for one, two in zip(values, values[1:])))
                self.assertEqual(len(set(values)), 256)
                self.assertLessEqual(abs(values[500] - (255 + anchor) / 2), .5)
                self.assertLessEqual(abs(values[1500] - anchor / 2), .5)

    def test_background_slider_keeps_rgb_foreground_and_corner_contract(self):
        for dark in (False, True):
            baseline = palette("glass", dark, transparency=50, curvature=37.5)
            for value in (0, 12.375, 49.95, 50.05, 88.125, 100):
                colors = palette("glass", dark, transparency=value, curvature=37.5)
                self.assertEqual(colors["radius"], 15)
                for key in ("ink", "muted", "edge_top", "edge_bottom"):
                    self.assertEqual(colors[key], baseline[key])
                self.assertEqual(QColor(colors["ink"]).alpha(), 255)
                self.assertEqual(QColor(colors["muted"]).alpha(), 255)
                for stop in ("top", "bottom"):
                    self.assertEqual(colors[stop][3:], baseline[stop][3:])

    def test_other_glass_skins_keep_their_existing_colors_and_response(self):
        expected = {
            ("frost", False): ("#a8f9fbfd", "#a8f6f8fa"),
            ("frost", True): ("#a8262b32", "#a823282f"),
            ("tint", False): ("#6bb9d9ff", "#6bb6d6ff"),
            ("tint", True): ("#6b20416e", "#6b1d3e6b"),
        }
        for (skin, dark), stops in expected.items():
            colors = palette(skin, dark, transparency=50, curvature=37.5)
            self.assertEqual((colors["top"], colors["bottom"]), stops)
            self.assertEqual(colors["radius"], 15)
        for skin in ("graphite", "minimal", "card"):
            for dark in (False, True):
                self.assertEqual(palette(skin, dark, transparency=0, curvature=0),
                                 palette(skin, dark, transparency=100, curvature=100))

    def make_items(self, dark, transparency, title=False):
        config = copy.deepcopy(DEFAULT)
        config.update(skin="glass", theme="dark" if dark else "light",
                      glass_transparency=transparency, glass_curvature=50)
        config["widgets"]["cpu"].update(skin=None, content=["cpu_usage"], presentation="hero",
                                        show_title=title, chart=False)
        surface = MaterialSurface()
        surface.setWidth(160)
        surface.setHeight(160)
        surface.set_config(config)
        surface.set_frosted(True)
        card = HardwareCard()
        card.setWidth(160)
        card.setHeight(160)
        card.setProperty("moduleKey", "cpu")
        card.setProperty("config", config)
        card.setProperty("readings", {"time": time.time(), "cpu_usage": 42.0})
        card.setProperty("frosted", True)
        card.setProperty("surface", True)
        return surface, card

    def test_real_card_and_shared_surface_paint_one_matching_coating(self):
        for dark in (False, True):
            for value in (0, 37.5, 50, 75, 100):
                surface, card = self.make_items(dark, value)
                face, content = render_item(surface), render_item(card)
                self.assertEqual(content.pixelColor(80, 150), face.pixelColor(80, 150))
                colors = palette("glass", dark, transparency=value)
                lo, hi = sorted(QColor(colors[stop]).alpha() for stop in ("top", "bottom"))
                self.assertTrue(lo <= face.pixelColor(80, 80).alpha() <= hi)
                self.assertEqual(face.pixelColor(0, 0).alpha(), 0)

    def test_clear_coating_does_not_fade_titles_or_numbers(self):
        for dark in (False, True):
            surface, card = self.make_items(dark, 100, title=True)
            self.assertEqual(render_item(surface).pixelColor(80, 80).alpha(), 0)
            image = render_item(card)
            self.assertGreater(sum(image.pixelColor(x, y).alpha() == 255
                                   for x in range(160) for y in range(160)), 50)
            self.assertEqual(image.pixelColor(80, 150).alpha(), 0)


if __name__ == "__main__":
    unittest.main()
