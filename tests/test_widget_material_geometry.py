"""Real region geometry, synthetic config only; no native windows or capture."""

import copy
import unittest

from PySide6.QtCore import QPoint

from material_policy import render_policy
from native_layout import windows
from skin_styles import glass_options, palette
from stats_config import DEFAULT
from widget_material_geometry import backdrop_shapes, rounded_mask


class GeometryTests(unittest.TestCase):
    def config(self, skin="glass", mode="separate"):
        value = copy.deepcopy(DEFAULT)
        value.update(skin=skin, mode=mode, widget_order=["cpu", "gpu"])
        for key in value["widget_order"]:
            value["widgets"][key].update(enabled=True, skin=None, grouped=True)
        return value

    def test_glass_has_round_corners_and_full_center(self):
        config = self.config()
        spec = windows(config)[0]
        shapes = backdrop_shapes(config, spec, 240, 160)
        region = rounded_mask(shapes)
        self.assertFalse(region.contains(QPoint(0, 0)))
        self.assertTrue(region.contains(QPoint(120, 80)))
        self.assertTrue(region.contains(QPoint(120, 0)))

    def test_non_glass_never_masks_or_blurs(self):
        for skin in ("card", "graphite", "minimal"):
            config = self.config(skin)
            self.assertEqual(backdrop_shapes(config, windows(config)[0], 240, 160), ())

    def test_classic_card_radius_matches_painter_scaling(self):
        config = self.config()
        spec = windows(config)[0]
        for height in (80, 160, 320):
            actual = backdrop_shapes(config, spec, 360, height)[0][4]
            expected = (
                palette("glass", False, transparency=50, curvature=50)["radius"] * height / 160
            )
            self.assertAlmostEqual(actual, expected)

    def test_uniform_group_uses_only_one_panel_footprint(self):
        config = self.config(mode="combined")
        spec = windows(config)[0]
        shapes = backdrop_shapes(config, spec, spec["width"], spec["height"])
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0][4], palette("glass", **glass_options(config))["radius"])

    def test_different_glass_options_leave_group_gaps_clear(self):
        config = self.config(mode="combined")
        config["widgets"]["gpu"]["glass_curvature"] = 90
        spec = windows(config)[0]
        self.assertTrue(render_policy(config, spec)["card_surfaces"])
        shapes = backdrop_shapes(config, spec, spec["width"], spec["height"])
        region = rounded_mask(shapes)
        self.assertEqual(len(shapes), 2)
        self.assertFalse(region.contains(QPoint(0, 0)))
        self.assertFalse(region.contains(QPoint(5, spec["height"] // 2)))

    def test_mixed_minimal_removes_whole_window_footprint(self):
        config = self.config(mode="combined")
        config["widgets"]["gpu"]["skin"] = "minimal"
        spec = windows(config)[0]
        self.assertEqual(backdrop_shapes(config, spec, 500, 240), ())
        self.assertTrue(rounded_mask(()).isEmpty())

    def test_transparency_never_changes_geometry_but_curvature_does(self):
        config = self.config()
        spec = windows(config)[0]
        before = backdrop_shapes(config, spec, 240, 160)
        config["glass_transparency"] = 100
        self.assertEqual(before, backdrop_shapes(config, spec, 240, 160))
        config["glass_curvature"] = 100
        self.assertNotEqual(before, backdrop_shapes(config, spec, 240, 160))

    def test_invalid_dimensions_are_empty(self):
        config = self.config()
        spec = windows(config)[0]
        for size in ((0, 10), (-1, 10), (float("nan"), 10), (10, float("inf"))):
            self.assertEqual(backdrop_shapes(config, spec, *size), ())


if __name__ == "__main__":
    unittest.main()
