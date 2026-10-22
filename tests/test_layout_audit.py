"""Independent 0.9 layout regressions; no native windows, IPC or sampling.

Pure planners and isolated Controller objects use mocked persistence. Unbound
Runtime methods run against plain fake objects, never an actual Runtime.
"""

import copy
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/layout-audit-unit-profile"),
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect

from desktop_placement import desktop_plan
from magnet_layout import separated
from native_controller import Controller
from native_layout import LayoutCapacityError, windows
from native_runtime import Runtime
from responsive_layout import responsive_plan
from stats_config import DEFAULT, validate
from widget_catalog import from_template, widget_defaults


def isolated_controller(config=None):
    with patch("native_controller.load", return_value=copy.deepcopy(config or DEFAULT)):
        return Controller()


METRICS = ["cpu_temp", "cpu_usage", "cpu_power", "gpu_temp", "gpu_usage", "gpu_power"]
OBSERVATIONS = []


def screen(id="primary", x=0, width=1000, height=600, primary=True):
    return dict(id=id, primary=primary, x=x, y=0, width=width, height=height)


def config_for(widgets, **options):
    result = copy.deepcopy(DEFAULT)
    result.update(widgets=copy.deepcopy(widgets), widget_order=list(widgets), **options)
    return validate(result)


def custom(**options):
    result = widget_defaults("custom")
    result.update(
        content=METRICS,
        form="free",
        width=900,
        height=200,
        layout_mode="horizontal",
        show_title=False,
    )
    result.update(options)
    return result


def validate_drawn_cells(config, specs):
    for spec in specs:
        for cell in spec["cells"]:
            prefs = config["widgets"][cell["key"]]
            content = Controller._content_for(prefs)
            responsive_plan(cell["width"], cell["height"], content, prefs)


class IndependentGeometryTests(unittest.TestCase):
    def test_group_fitting_never_accepts_widths_that_hide_every_reading(self):
        config = config_for({"w_a": custom(), "w_b": custom()}, mode="combined")
        try:
            specs, _ = desktop_plan(config, [screen()])
        except LayoutCapacityError:
            return  # Readable content cannot fit; a clear rejection is correct.
        validate_drawn_cells(config, specs)

    def test_narrow_monitor_bar_grows_height_to_preserve_every_reading(self):
        config = config_for({"w_bar": from_template("status_bar")})
        specs, points = desktop_plan(config, [screen(width=800)])
        validate_drawn_cells(config, specs)
        self.assertEqual((specs[0]["width"], specs[0]["height"]), (776, 76))
        self.assertEqual(points["w_bar"][1], 8)

    def test_undocked_bar_retains_its_window_in_combined_mode(self):
        config = config_for(
            {"w_a": from_template("cpu"), "w_bar": from_template("status_bar")}, mode="combined"
        )
        self.assertIn("w_bar", [spec["id"] for spec in windows(config)])
        config["widgets"]["w_bar"]["dock"] = "free"
        self.assertIn("w_bar", [spec["id"] for spec in windows(config)])

    def test_global_row_and_column_layouts_produce_the_selected_direction(self):
        base = config_for(
            {
                "w_a": from_template("custom"),
                "w_b": from_template("custom"),
                "w_c": from_template("custom"),
            }
        )
        layouts = {}
        for direction in ("row", "column"):
            base["layout"] = direction
            _, points = desktop_plan(base, [screen(width=1200, height=900)], rearrange=True)
            layouts[direction] = list(points.values())
        self.assertEqual(len({point[1] for point in layouts["row"]}), 1)
        self.assertEqual(len({point[0] for point in layouts["column"]}), 1)
        self.assertNotEqual(layouts["row"], layouts["column"])

    def test_saved_config_cannot_make_initial_window_planning_raise(self):
        prefs = widget_defaults("custom")
        prefs.update(
            content=["cpu_usage"],
            form="free",
            width=200,
            height=40,
            layout_mode="manual",
            show_title=False,
            metric_positions={"cpu_usage": dict(x=0, y=0, width=0.001, height=1)},
        )
        raw = copy.deepcopy(DEFAULT)
        raw.update(widgets={"w_a": prefs}, widget_order=["w_a"])
        try:
            normalized = validate(raw)
        except ValueError:
            return
        # Runtime.apply invokes windows() through desktop_plan before showing.
        # Controller.preview_windows also calls windows outside its try block.
        windows(normalized)


class IsolatedControllerTests(unittest.TestCase):
    def test_migration_and_json_roundtrip_preserve_dormant_instances_and_old_geometry(self):
        before = config_for({"w_a": from_template("cpu"), "w_dormant": from_template("custom")})
        before["version"] = 6
        before["widget_order"] = ["w_a"]
        before["widgets"]["w_a"].update(title="Retained", temperature_unit="F", size=112)
        before["widgets"]["w_dormant"].update(enabled=False, title="Dormant")
        new_fields = (
            "width",
            "height",
            "layout_mode",
            "columns",
            "metric_positions",
            "dock",
            "layer",
            "screen_target",
        )
        for prefs in before["widgets"].values():
            for field in new_fields:
                prefs.pop(field, None)
        expected_widgets = copy.deepcopy(before["widgets"])
        migrated = validate(before)
        self.assertEqual(migrated["version"], 8)
        self.assertEqual(migrated["widget_order"], ["w_a"])
        for key, prefs in expected_widgets.items():
            for field, value in prefs.items():
                self.assertEqual(migrated["widgets"][key][field], value, (key, field))
        self.assertEqual(
            (windows(migrated)[0]["width"], windows(migrated)[0]["height"]), (168, 168)
        )
        import json

        self.assertEqual(validate(json.loads(json.dumps(migrated))), migrated)

    def test_capacity_preflight_matches_the_actual_rearrange_request(self):
        wide = custom()
        wide["height"] = 400
        before = config_for({"w_a": wide})
        after = config_for({"w_a": wide, "w_b": wide})
        screens = [
            screen("p", width=1280, height=720),
            screen("s", x=1280, width=1280, height=720, primary=False),
        ]
        positions = {"w_a": [1400, 100]}
        controller = isolated_controller()
        controller._saved, controller._draft = before, after
        controller.set_screen_inventory(screens, positions)
        outcomes = []

        def requested(rearrange):
            try:
                desktop_plan(controller._saved, screens, positions, rearrange)
                outcomes.append({"ok": True, "rearrange": rearrange})
            except ValueError as error:
                outcomes.append({"ok": False, "rearrange": rearrange, "error": str(error)})

        controller.applyRequested.connect(requested)
        with patch("native_controller.save") as saved, patch("native_controller.set_autostart"):
            controller.apply()
        OBSERVATIONS.append(
            dict(
                case="capacity_commit",
                saved=saved.called,
                outcomes=outcomes,
                status=controller.status,
            )
        )
        self.assertFalse(
            saved.called and any(not row["ok"] for row in outcomes),
            "Preferences were saved although the actual requested rearrangement fails",
        )

    def test_quick_show_title_never_persists_an_unrenderable_manual_widget(self):
        prefs = widget_defaults("custom")
        prefs.update(
            content=["cpu_usage"],
            form="free",
            width=200,
            height=2160,
            layout_mode="manual",
            show_title=False,
            metric_positions={"cpu_usage": dict(x=0, y=0, width=1, height=0.014)},
        )
        initial = config_for({"w_a": prefs})
        windows(initial)  # Valid readable starting state.
        controller = isolated_controller()
        controller._saved, controller._draft = initial, copy.deepcopy(initial)
        with patch("native_controller.save") as saved:
            accepted = controller.quickWidget("w_a", "show_title", True)
        OBSERVATIONS.append(
            dict(
                case="quick_title", accepted=accepted, saved=saved.called, status=controller.status
            )
        )
        if accepted:
            windows(controller._saved)

    def test_resizing_keeps_unrelated_pending_title_language_and_content(self):
        initial = config_for({"w_a": from_template("cpu")})
        controller = isolated_controller()
        controller._saved, controller._draft = initial, copy.deepcopy(initial)
        controller._draft["language"] = "de"
        controller._draft["widgets"]["w_a"]["title"] = "Pending"
        controller._draft["widgets"]["w_a"]["content"] = ["cpu_usage", "cpu_power"]
        with patch("native_controller.save"):
            self.assertTrue(controller.resizeWindow("w_a", 600, 100))
        self.assertEqual(controller._draft["language"], "de")
        self.assertEqual(controller._draft["widgets"]["w_a"]["title"], "Pending")
        self.assertEqual(controller._draft["widgets"]["w_a"]["content"], ["cpu_usage", "cpu_power"])
        self.assertNotEqual(controller._saved["widgets"]["w_a"]["title"], "Pending")

    def test_desktop_movement_updates_preflight_memory_before_delayed_disk_save(self):
        initial = config_for({"w_a": from_template("custom")})
        controller = isolated_controller(initial)
        screens = [
            screen("p", width=1280, height=720),
            screen("s", x=1280, width=1280, height=720, primary=False),
        ]
        positions = {"w_a": [1400, 100]}
        controller.set_screen_inventory(screens, positions)
        fake = SimpleNamespace(
            widgets={"w_a": object()},
            shutting_down=False,
            controller=controller,
            positions=copy.deepcopy(positions),
            screen_inventory=lambda: screens,
            position_timer=SimpleNamespace(start=Mock()),
        )
        Runtime.position(fake, "w_a", 100, 100)
        self.assertEqual(
            controller._preview_positions["w_a"],
            [100, 100],
            "A fast Apply must preflight the actual current monitor",
        )
        fake.position_timer.start.assert_called_once()

    def test_quick_shape_resets_explicit_strip_geometry_atomically(self):
        initial = config_for({"w_a": from_template("status_bar")})
        controller = isolated_controller(initial)
        with patch("native_controller.save"):
            self.assertTrue(controller.quickWidget("w_a", "form", "square"))
        prefs = controller._saved["widgets"]["w_a"]
        self.assertEqual(
            (prefs["form"], prefs["width"], prefs["height"], prefs["layout_mode"], prefs["dock"]),
            ("square", None, None, "auto", "free"),
        )
        self.assertEqual(
            windows(controller._saved)[0]["width"], windows(controller._saved)[0]["height"]
        )

    def test_manual_reorder_moves_visual_slots_and_remove_preserves_remaining_positions(self):
        prefs = widget_defaults("custom")
        prefs.update(
            content=["cpu_usage", "gpu_usage"],
            form="free",
            width=600,
            height=120,
            layout_mode="manual",
            show_title=False,
            metric_positions={
                "cpu_usage": dict(x=0, y=0, width=0.4, height=1),
                "gpu_usage": dict(x=0.6, y=0, width=0.4, height=1),
            },
        )
        initial = config_for({"w_a": prefs})
        controller = isolated_controller(initial)
        previous = copy.deepcopy(controller._draft["widgets"]["w_a"]["metric_positions"])
        drawn_before = {
            row["id"]: row["x"]
            for row in controller.widgetContentLayout("w_a", 600, 120)["readings"]
        }
        self.assertTrue(controller.reorderMetric("w_a", 0, 1))
        # Manual ordering is a visual action: the new first metric occupies the
        # previous first slot. Keeping rectangles attached to IDs made the
        # editor's move arrows report success without moving anything on screen.
        moved = {
            "gpu_usage": previous["cpu_usage"],
            "cpu_usage": previous["gpu_usage"],
        }
        self.assertEqual(controller._draft["widgets"]["w_a"]["content"], ["gpu_usage", "cpu_usage"])
        self.assertEqual(controller._draft["widgets"]["w_a"]["metric_positions"], moved)
        drawn_after = {
            row["id"]: row["x"]
            for row in controller.widgetContentLayout("w_a", 600, 120)["readings"]
        }
        self.assertEqual(drawn_after["gpu_usage"], drawn_before["cpu_usage"])
        self.assertEqual(drawn_after["cpu_usage"], drawn_before["gpu_usage"])
        controller.removeMetric("w_a", 0)
        self.assertEqual(
            controller._draft["widgets"]["w_a"]["metric_positions"],
            {"cpu_usage": moved["cpu_usage"]},
        )


class MonitorAndLifecycleTests(unittest.TestCase):
    def test_explicit_monitor_target_wins_and_missing_target_is_retained(self):
        config = config_for({"w_a": from_template("custom")})
        screens = [
            screen("p", width=1200, height=800),
            screen("s", x=-1200, width=1200, height=800, primary=False),
        ]
        config["widgets"]["w_a"]["screen_target"] = "s"
        specs, _ = desktop_plan(config, screens, {"w_a": [100, 100]})
        self.assertEqual(specs[0]["screen_id"], "s")
        config["widgets"]["w_a"]["screen_target"] = "currently-disconnected-display"
        before = copy.deepcopy(config)
        specs, _ = desktop_plan(config, screens)
        self.assertEqual(specs[0]["screen_id"], "p")
        self.assertEqual(
            config, before, "A temporary fallback must not rewrite the selected display identity"
        )

    def test_undock_refusal_or_window_replacement_is_safe(self):
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                point = SimpleNamespace(x=lambda: 10, y=lambda: 8)
                fake = SimpleNamespace(
                    widgets={"w_bar": point},
                    shutting_down=False,
                    controller=SimpleNamespace(_saved={"locked": False}),
                    _spec_by_id={"w_bar": {"dock": "top"}},
                    cancel_motion=Mock(),
                    drag_origins={},
                )

                def quick(key, field, value):
                    if replacement:
                        fake.widgets.pop(key)
                    return replacement

                fake.controller.quickWidget = quick
                Runtime.begin_move(fake, "w_bar")
                self.assertEqual(fake.drag_origins, {})


class FakeArrangementTest(unittest.TestCase):
    def test_magnet_gap_survives_docked_bar_being_added_after_saved_window(self):
        config = config_for(
            {"w_a": from_template("custom"), "w_bar": from_template("status_bar")},
            magnet_enabled=True,
            magnet_gap=12,
        )
        screens = [screen(width=1000, height=700)]
        positions = {"w_a": [100, 12]}
        specs, _ = desktop_plan(config, screens, positions)
        # No Runtime instance, QObject window or timer is constructed. This
        # exercises only arrange's real ordering with explicitly fake objects.
        fake_windows = {}
        for spec in specs:
            point = {"x": 0, "y": 0}
            fake_windows[spec["id"]] = SimpleNamespace(
                setPosition=lambda x, y, p=point: p.update(x=x, y=y), point=point
            )
        rectangle = QRect(0, 0, 1000, 700)
        fake_screen = SimpleNamespace(availableGeometry=lambda: rectangle)
        fake = SimpleNamespace(
            app=SimpleNamespace(primaryScreen=lambda: fake_screen, screens=lambda: [fake_screen]),
            controller=SimpleNamespace(_saved=config, set_status=Mock()),
            positions=copy.deepcopy(positions),
            screen_inventory=lambda: screens,
            widgets=fake_windows,
            position_timer=SimpleNamespace(start=Mock()),
        )
        Runtime.arrange(fake, specs, False)
        rectangles = []
        for spec in specs:
            x, y = fake.positions[spec["id"]]
            rect = (x, y, spec["width"], spec["height"])
            self.assertTrue(
                separated(rect, rectangles, 12),
                "Saved floating window overlaps a later docked bar while repulsion is enabled",
            )
            rectangles.append(rect)


if __name__ == "__main__":
    unittest.main()
