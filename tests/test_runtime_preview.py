"""Regressions for native theme preview and power on battery-free computers."""

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QRect

from desktop_placement import desktop_plan
from magnet_layout import contained, separated, settle
from native_layout import LayoutCapacityError, fit, windows
from native_runtime import Runtime
from stats_config import DEFAULT, validate
from widget_catalog import from_template


class RuntimePreviewTests(unittest.TestCase):
    def test_theme_preview_and_revert_recompose_but_other_edits_do_not(self):
        runtime = SimpleNamespace(
            controller=SimpleNamespace(_draft={"theme": "light"}),
            settings=Mock(),
            settings_theme="light",
            compose=Mock(),
            refresh_appearance=Mock(),
        )
        runtime.settings.isVisible.return_value = True
        Runtime.settings_draft_changed(runtime)
        runtime.compose.assert_not_called()
        runtime.controller._draft["theme"] = "dark"
        Runtime.settings_draft_changed(runtime)
        runtime.controller._draft["title"] = "A title edit"
        Runtime.settings_draft_changed(runtime)
        self.assertEqual(runtime.compose.call_count, 1)
        runtime.controller._draft["theme"] = "light"
        Runtime.settings_draft_changed(runtime)
        self.assertEqual(runtime.compose.call_count, 2)

    def test_first_launch_without_battery_keeps_cpu_gpu_power_visible(self):
        controller = SimpleNamespace(
            _data={"battery_present": False, "cpu_power": 37.1, "gpu_power": 8.2},
            edit=Mock(),
            apply=Mock(),
        )
        with (
            patch("native_runtime.CONFIG") as config_file,
            patch("native_runtime.load", return_value=copy.deepcopy(DEFAULT)),
            patch("native_runtime.c.windll.kernel32.GetUserDefaultLocaleName", return_value=0),
        ):
            config_file.exists.return_value = False
            Runtime.first_reading(SimpleNamespace(controller=controller))
        saved = controller.edit.call_args.args[0]
        self.assertFalse(saved["widgets"]["battery"]["enabled"])
        self.assertTrue(saved["widgets"]["power"]["enabled"])
        self.assertIn("cpu_power", saved["widgets"]["power"]["content"])
        self.assertIn("gpu_power", saved["widgets"]["power"]["content"])

    def test_new_power_defaults_do_not_replace_legacy_customization(self):
        for content in (None, ["battery_watts", "voltage"]):
            old = {"version": 4, "widgets": {"power": {"enabled": False, "content": content}}}
            migrated = validate(old)
            self.assertFalse(migrated["widgets"]["power"]["enabled"])
            self.assertEqual(migrated["widgets"]["power"]["content"], content)
            self.assertNotIn("power", migrated["widget_order"])
        self.assertIn("cpu_power", validate({"version": 5})["widgets"]["power"]["content"])


class SavedDesktopGeometryTests(unittest.TestCase):
    """Restoration shares drag bounds; fresh layouts retain their visual inset."""

    @staticmethod
    def configuration(count=1, **options):
        cfg = copy.deepcopy(DEFAULT)
        cfg.update(
            widgets={f"w_{index}": from_template("custom") for index in range(count)},
            widget_order=[f"w_{index}" for index in range(count)],
            mode="separate",
            autostart=False,
            magnet_enabled=False,
        )
        cfg.update(options)
        return validate(cfg)

    @staticmethod
    def screen(x=0, y=0, width=1200, height=800, name="primary"):
        return dict(id=name, x=x, y=y, width=width, height=height, primary=True)

    def test_saved_legal_positions_use_entire_workarea_on_negative_monitors_too(self):
        cfg = self.configuration()
        spec = windows(cfg)[0]
        for x, y in ((0, 0), (-1200, -200), (400, -900)):
            screen = self.screen(x=x, y=y)
            for point in (
                [x + 5, y + 7],
                [x, y],
                [x + 1200 - spec["width"], y + 800 - spec["height"]],
            ):
                with self.subTest(screen=screen, point=point):
                    saved = {"w_0": point, "dormant": [-9000, -9000]}
                    original = copy.deepcopy((cfg, [screen], saved))
                    actual_specs, actual = desktop_plan(cfg, [screen], saved)
                    self.assertEqual(actual["w_0"], point)
                    self.assertEqual(
                        (actual_specs[0]["width"], actual_specs[0]["height"]),
                        (spec["width"], spec["height"]),
                    )
                    self.assertEqual((cfg, [screen], saved), original)

    def test_saved_near_full_workarea_widget_keeps_legal_size_as_well_as_position(self):
        cfg = self.configuration()
        cfg["widgets"]["w_0"].update(form="free", width=1190, height=780, show_title=False)
        cfg = validate(cfg)
        actual_specs, points = desktop_plan(cfg, [self.screen()], {"w_0": [5, 7]})
        self.assertEqual(points["w_0"], [5, 7])
        # The old constrain allowance reduced this valid 1190-wide window to
        # 1176 even after coordinate clamping was changed to use the full area.
        self.assertEqual((actual_specs[0]["width"], actual_specs[0]["height"]), (1190, 780))

    def test_outside_saved_position_clamps_like_completed_drag_without_extra_inset(self):
        cfg = self.configuration()
        for screen in (self.screen(), self.screen(x=-1200, y=-200)):
            saved = {"w_0": [screen["x"] - 500, screen["y"] + 2000]}
            actual_specs, points = desktop_plan(cfg, [screen], saved)
            spec = actual_specs[0]
            expected = fit(
                *saved["w_0"],
                spec["width"],
                spec["height"],
                [QRect(screen["x"], screen["y"], screen["width"], screen["height"])],
            )
            self.assertEqual(points["w_0"], list(expected))
            self.assertTrue(
                contained(
                    (*points["w_0"], spec["width"], spec["height"]),
                    [(screen["x"], screen["y"], screen["width"], screen["height"])],
                )
            )

    def test_removed_monitor_falls_back_without_rewriting_explicit_target_or_saved_input(self):
        cfg = self.configuration()
        cfg["widgets"]["w_0"]["screen_target"] = "disconnected-negative-display"
        saved = {"w_0": [-1195, -193]}
        original = copy.deepcopy((cfg, saved))
        specs, points = desktop_plan(cfg, [self.screen()], saved)
        self.assertEqual(specs[0]["screen_id"], "primary")
        self.assertEqual(points["w_0"], [0, 0])
        self.assertEqual((cfg, saved), original)

    def test_magnet_does_not_resnap_saved_windows_already_meeting_gap(self):
        cfg = self.configuration(2, magnet_enabled=True, magnet_gap=12)
        width = windows(cfg)[0]["width"]
        saved = {"w_0": [5, 7], "w_1": [5 + width + 12 + 6, 7]}
        # Six extra pixels are within settle's 18-DIP attraction radius. A
        # startup restore is not a new drag release and must not magnetize again.
        with patch(
            "desktop_placement.settle",
            side_effect=AssertionError("Saved legal geometry must not snap"),
        ):
            _, points = desktop_plan(cfg, [self.screen()], saved)
        self.assertEqual(points, saved)

    def test_saved_magnet_conflict_moves_only_conflicting_window_and_keeps_full_bounds(self):
        cfg = self.configuration(2, magnet_enabled=True, magnet_gap=12)
        saved = {"w_0": [5, 7], "w_1": [5, 7]}
        with patch("desktop_placement.settle", wraps=settle) as resolver:
            specs, points = desktop_plan(cfg, [self.screen()], saved)
        self.assertEqual(points["w_0"], [5, 7])
        self.assertNotEqual(points["w_1"], [5, 7])
        self.assertEqual(resolver.call_count, 1)
        by_id = {spec["id"]: spec for spec in specs}
        boxes = {
            key: (*point, by_id[key]["width"], by_id[key]["height"])
            for key, point in points.items()
        }
        self.assertTrue(separated(boxes["w_1"], [boxes["w_0"]], 12))
        self.assertTrue(all(contained(box, [(0, 0, 1200, 800)]) for box in boxes.values()))

    def test_impossible_saved_magnet_conflict_is_explicit_and_inputs_unchanged(self):
        cfg = self.configuration(2, magnet_enabled=True, magnet_gap=12)
        saved = {"w_0": [0, 0], "w_1": [0, 0]}
        original = copy.deepcopy((cfg, saved))
        with self.assertRaises(LayoutCapacityError):
            desktop_plan(cfg, [self.screen(width=260, height=150)], saved)
        self.assertEqual((cfg, saved), original)

    def test_fresh_and_explicit_rearrange_still_use_twelve_pixel_inset(self):
        cfg = self.configuration()
        for origin in ((0, 0), (-1200, -200)):
            screen = self.screen(x=origin[0], y=origin[1])
            for rearrange, saved in ((False, {}), (True, {"w_0": [origin[0] + 5, origin[1] + 7]})):
                with self.subTest(origin=origin, rearrange=rearrange):
                    specs, points = desktop_plan(cfg, [screen], saved, rearrange=rearrange)
                    self.assertTrue(
                        contained(
                            (*points["w_0"], specs[0]["width"], specs[0]["height"]),
                            [(origin[0] + 12, origin[1] + 12, 1176, 776)],
                        )
                    )

    def test_saved_edge_position_stays_when_docked_bar_already_has_clearance(self):
        cfg = self.configuration(magnet_enabled=True, magnet_gap=12)
        cfg["widgets"]["w_bar"] = from_template("status_bar")
        cfg["widget_order"].append("w_bar")
        cfg = validate(cfg)
        _, points = desktop_plan(cfg, [self.screen()], {"w_0": [5, 0]})
        self.assertEqual(points["w_0"], [5, 0])
        self.assertEqual(points["w_bar"], [150, 8])
