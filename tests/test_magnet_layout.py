"""Independent magnet geometry/configuration checks; no windows or OS input."""

import copy
import json
import os
import random
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from magnet_layout import Placement, contained, separated, settle


def legal_at(point, size, obstacles, areas, gap):
    """Independent axis-aligned clearance oracle, not the production helpers."""
    x, y = point
    width, height = size
    inside = not areas or any(
        x >= ax and y >= ay and x + width <= ax + aw and y + height <= ay + ah
        for ax, ay, aw, ah in areas
    )
    if not inside:
        return False
    for ox, oy, ow, oh in obstacles:
        horizontal_clearance = max(ox - (x + width), x - (ox + ow))
        vertical_clearance = max(oy - (y + height), y - (oy + oh))
        if max(horizontal_clearance, vertical_clearance) < gap:
            return False
    return True


class MagnetGeometryTests(unittest.TestCase):
    def assert_legal(self, placement, size, obstacles, areas, gap):
        self.assertIs(placement.legal, True)
        self.assertIs(type(placement.x), int)
        self.assertIs(type(placement.y), int)
        self.assertTrue(legal_at((placement.x, placement.y), size, obstacles, areas, gap))

    def test_placement_is_an_immutable_value_with_explicit_defaults(self):
        placement = Placement(-30, 12, True)
        self.assertEqual((placement.x, placement.y), (-30, 12))
        self.assertFalse(placement.snapped)
        self.assertEqual(placement.normal, (0, 0))
        with self.assertRaises(FrozenInstanceError):
            placement.x = 99

    def test_separation_accepts_touching_only_when_gap_allows_it(self):
        rect = (0, 0, 10, 10)
        for gap in (0, 12, 64):
            with self.subTest(gap=gap):
                self.assertTrue(separated(rect, [(10 + gap, 0, 20, 10)], gap))
                self.assertTrue(separated(rect, [(0, 10 + gap, 10, 20)], gap))
                self.assertFalse(separated(rect, [(9 + gap, 0, 20, 10)], gap))
        self.assertFalse(separated(rect, [(3, 3, 4, 4)], 0))
        self.assertTrue(separated(rect, [], 64))

    def test_containment_requires_one_complete_workarea_including_negative_origins(self):
        areas = [(-200, -100, 200, 160), (0, 0, 200, 200)]
        self.assertTrue(contained((-200, -100, 200, 160), areas))
        self.assertTrue(contained((0, 0, 200, 200), areas))
        self.assertFalse(contained((-10, 0, 20, 20), areas))
        self.assertFalse(contained((-201, -100, 200, 160), areas))
        self.assertTrue(contained((-999, -999, 1, 1), []))

    def test_overlapping_release_chooses_nearest_legal_edge_for_each_gap(self):
        rect = (215, 130, 40, 30)
        obstacles = [(200, 100, 50, 80)]
        areas = [(0, 0, 500, 300)]
        for gap in (0, 12, 64):
            with self.subTest(gap=gap):
                result = settle(rect, obstacles, areas, gap=gap)
                self.assert_legal(result, rect[2:], obstacles, areas, gap)
                self.assertEqual((result.x, result.y), (250 + gap, 130))
                self.assertTrue(result.snapped)
                self.assertEqual(result.normal, (1, 0))

    def test_multi_obstacle_nearest_result_matches_exhaustive_integer_oracle(self):
        rng = random.Random(7091)
        area = (0, 0, 32, 27)
        for index in range(28):
            width, height = rng.randint(3, 8), rng.randint(3, 8)
            rect = (rng.randint(-5, 34), rng.randint(-5, 29), width, height)
            obstacles = [
                (rng.randint(0, 27), rng.randint(0, 22), rng.randint(2, 10), rng.randint(2, 10))
                for _ in range(rng.randint(1, 4))
            ]
            gap = rng.choice((0, 2, 5))
            possible = [
                (x, y)
                for y in range(area[3] - height + 1)
                for x in range(area[2] - width + 1)
                if legal_at((x, y), (width, height), obstacles, [area], gap)
            ]
            with self.subTest(case=index, rect=rect, obstacles=obstacles, gap=gap):
                result = settle(rect, obstacles, [area], gap=gap, snap=0)
                if not possible:
                    self.assertIs(result.legal, False)
                    continue
                self.assert_legal(result, (width, height), obstacles, [area], gap)
                best_distance = min((x - rect[0]) ** 2 + (y - rect[1]) ** 2 for x, y in possible)
                self.assertEqual(
                    (result.x - rect[0]) ** 2 + (result.y - rect[1]) ** 2, best_distance
                )
                self.assertEqual(result, settle(rect, obstacles, [area], gap=gap, snap=0))

    def test_near_edge_snaps_with_outward_normal_but_far_position_stays(self):
        areas = [(0, 0, 500, 400)]
        obstacles = [(200, 50, 50, 100)]
        near = settle((135, 80, 40, 30), obstacles, areas, gap=12, snap=18)
        self.assertEqual(near, Placement(148, 80, True, True, (-1, 0)))
        far = settle((100, 80, 40, 30), obstacles, areas, gap=12, snap=18)
        self.assertEqual(far, Placement(100, 80, True))
        other_row = settle((135, 220, 40, 30), obstacles, areas, gap=12, snap=18)
        self.assertEqual(other_row, Placement(135, 220, True))
        above = settle((220, 5, 40, 20), obstacles, areas, gap=12, snap=18)
        self.assertEqual(above, Placement(220, 18, True, True, (0, -1)))

    def test_combined_panel_uses_its_full_rectangle(self):
        rect = (310, 150, 320, 170)
        obstacles = [(450, 100, 150, 220)]
        areas = [(0, 0, 900, 500)]
        result = settle(rect, obstacles, areas, gap=12)
        self.assertEqual((result.x, result.y), (118, 150))
        self.assert_legal(result, rect[2:], obstacles, areas, 12)

    def test_multimonitor_negative_coordinates_and_seam_are_bounded(self):
        areas = [(-320, -120, 320, 240), (0, 0, 320, 200)]
        obstacles = [(-180, -40, 50, 80)]
        result = settle((-160, -20, 30, 20), obstacles, areas, gap=12)
        self.assertEqual((result.x, result.y), (-118, -20))
        self.assert_legal(result, (30, 20), obstacles, areas, 12)
        seam = settle((-10, -10, 80, 80), [], areas, gap=12)
        self.assertEqual((seam.x, seam.y), (0, 0))
        self.assert_legal(seam, (80, 80), [], areas, 12)

    def test_outside_workarea_is_clamped_without_moving_obstacles(self):
        rect = (-40, 115, 30, 40)
        obstacles = [(60, 10, 30, 20)]
        areas = [(0, 0, 100, 100)]
        before = copy.deepcopy((rect, obstacles, areas))
        result = settle(rect, obstacles, areas, gap=12)
        self.assertEqual((result.x, result.y), (0, 60))
        self.assert_legal(result, rect[2:], obstacles, areas, 12)
        self.assertEqual((rect, obstacles, areas), before)

    def test_only_original_slot_is_retained_in_an_otherwise_occupied_workarea(self):
        origin = (0, 0)
        rect = (180, 0, 88, 100)
        obstacles = [(100, 0, 200, 100)]
        areas = [(0, 0, 300, 100)]
        self.assertTrue(legal_at(origin, rect[2:], obstacles, areas, 12))
        result = settle(rect, obstacles, areas, gap=12, fallback=origin)
        self.assertEqual((result.x, result.y), origin)
        self.assert_legal(result, rect[2:], obstacles, areas, 12)

    def test_impossible_packing_is_explicit_and_does_not_reduce_the_gap(self):
        areas = [(0, 0, 100, 100)]
        obstacles = [(30, 30, 40, 40)]
        for origin in (None, (0, 0), (-100, -100)):
            with self.subTest(origin=origin):
                result = settle((15, 15, 80, 80), obstacles, areas, gap=12, fallback=origin)
                self.assertIs(result.legal, False)
                self.assertFalse(legal_at((result.x, result.y), (80, 80), obstacles, areas, 12))
        too_large = settle((10, 10, 101, 30), [], areas)
        self.assertIs(too_large.legal, False)

    def test_random_legal_results_really_fit_one_area_and_avoid_every_obstacle(self):
        rng = random.Random(20261020)
        for index in range(160):
            areas = [(-240, -90, 240, 180), (0, 0, 320, 200)]
            rect = (
                rng.randint(-280, 330),
                rng.randint(-120, 230),
                rng.randint(12, 95),
                rng.randint(12, 70),
            )
            obstacles = [
                (
                    rng.randint(-225, 290),
                    rng.randint(-100, 190),
                    rng.randint(10, 85),
                    rng.randint(10, 70),
                )
                for _ in range(rng.randint(0, 14))
            ]
            gap = rng.choice((0, 12, 64))
            untouched = copy.deepcopy((rect, obstacles, areas))
            with self.subTest(case=index, gap=gap):
                result = settle(rect, obstacles, areas, gap=gap, snap=rng.choice((0, 18)))
                self.assertEqual((rect, obstacles, areas), untouched)
                if result.legal:
                    self.assert_legal(result, rect[2:], obstacles, areas, gap)
                if not obstacles:
                    self.assertIs(result.legal, True)

    def test_nonfinite_boolean_and_invalid_primary_geometry_is_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf"), True):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                settle((bad, 0, 10, 10), [], [(0, 0, 100, 100)])
        for rect, gap, snap in [
            ((0, 0, 0, 10), 0, 18),
            ((0, 0, 10, -1), 0, 18),
            ((0, 0, 10, 10), -1, 18),
            ((0, 0, 10, 10), 0, -1),
        ]:
            with self.subTest(rect=rect, gap=gap, snap=snap), self.assertRaises(ValueError):
                settle(rect, [], [(0, 0, 100, 100)], gap=gap, snap=snap)


class MagnetConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Imports define preference paths but create no windows or samplers.
        # Controller.load is separately stubbed for every instance below.
        directory = Path(__file__).resolve().parents[1] / "qa-private/magnet-unit-data"
        with patch.dict(os.environ, {"DESKTOP_STATS_DATA": str(directory)}):
            import native_controller
            import stats_config
        cls.controls = native_controller
        cls.settings = stats_config

    def test_defaults_are_opt_in_twelve_pixel_gap_and_bounce(self):
        for config in (
            self.settings.DEFAULT,
            self.settings.validate({}),
            self.settings.validate({"version": 6}),
        ):
            with self.subTest(version=config["version"]):
                self.assertIs(config["magnet_enabled"], False)
                self.assertEqual(config["magnet_gap"], 12)
                self.assertIs(type(config["magnet_gap"]), int)
                self.assertIs(config["magnet_bounce"], True)

    def test_gap_bounds_and_boolean_types_survive_json_round_trip(self):
        for gap in (0, 12, 64):
            source = dict(version=6, magnet_enabled=True, magnet_gap=gap, magnet_bounce=False)
            with self.subTest(gap=gap):
                config = self.settings.validate(json.loads(json.dumps(source)))
                self.assertIs(config["magnet_enabled"], True)
                self.assertIs(config["magnet_bounce"], False)
                self.assertEqual(config["magnet_gap"], gap)
                self.assertIs(type(config["magnet_gap"]), int)

    def test_import_validation_never_coerces_bool_float_or_out_of_range_gap(self):
        for value in (True, False, 12.0, 12.3, -1, 65, "12", None):
            with self.subTest(gap=value), self.assertRaises(ValueError):
                self.settings.validate({"version": 6, "magnet_gap": value})
        for field in ("magnet_enabled", "magnet_bounce"):
            for value in (0, 1, 0.0, 1.0, "true", None):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.settings.validate({"version": 6, field: value})

    def test_qml_whole_float_gap_is_converted_but_fraction_and_bool_are_rejected(self):
        initial = copy.deepcopy(self.settings.DEFAULT)
        with patch.object(self.controls, "load", return_value=initial):
            ui = self.controls.Controller()
        self.addCleanup(ui.close)
        ui.change("magnet_gap", 7)
        self.assertEqual(ui._draft["magnet_gap"], 7)
        ui.change("magnet_gap", 12.0)
        self.assertEqual(ui._draft["magnet_gap"], 12)
        self.assertIs(type(ui._draft["magnet_gap"]), int)
        valid = copy.deepcopy(ui._draft)
        for bad in (12.3, True, False, -1.0, 65.0, float("nan"), float("inf")):
            with self.subTest(value=bad):
                ui.change("magnet_gap", bad)
                self.assertEqual(ui._draft, valid)
                self.assertEqual(ui._saved, initial)
        for field in ("magnet_enabled", "magnet_bounce"):
            for bad in (0, 1, 0.0, 1.0):
                with self.subTest(field=field, value=bad):
                    ui.change(field, bad)
                    self.assertEqual(ui._draft, valid)

    def test_actual_controller_revert_and_commit_preserve_all_magnet_fields(self):
        initial = copy.deepcopy(self.settings.DEFAULT)
        with patch.object(self.controls, "load", return_value=initial):
            ui = self.controls.Controller()
        self.addCleanup(ui.close)
        ui.change("magnet_enabled", True)
        ui.change("magnet_gap", 64.0)
        ui.change("magnet_bounce", False)
        self.assertEqual(ui._saved, initial)
        ui.revert()
        self.assertEqual(ui._draft, initial)
        ui.change("magnet_enabled", True)
        ui.change("magnet_gap", 0.0)
        ui.change("magnet_bounce", False)
        with (
            patch.object(self.controls, "save") as save_config,
            patch.object(self.controls, "set_autostart") as startup,
        ):
            ui.apply()
        saved = save_config.call_args.args[0]
        self.assertIs(saved["magnet_enabled"], True)
        self.assertEqual(saved["magnet_gap"], 0)
        self.assertIs(type(saved["magnet_gap"]), int)
        self.assertIs(saved["magnet_bounce"], False)
        self.assertEqual(ui._draft, ui._saved)
        startup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
