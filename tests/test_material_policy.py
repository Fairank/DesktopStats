"""Material boundaries and preview geometry, without native desktop windows."""

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from material_policy import render_policy
from native_controller import Controller
from native_layout import grid_plan, windows
from native_runtime import Runtime
from skin_styles import GLASS_SKINS, SKINS
from stats_config import DEFAULT


class MaterialPolicyTests(unittest.TestCase):
    def config(self, first=None, second=None, global_skin="glass", mode="combined"):
        config = copy.deepcopy(DEFAULT)
        config.update(skin=global_skin, mode=mode, widget_order=["cpu", "gpu"])
        for key, skin in (("cpu", first), ("gpu", second)):
            config["widgets"][key].update(enabled=True, skin=skin, grouped=True)
        return config

    def test_every_global_and_local_single_skin_uses_the_effective_material(self):
        for global_skin in SKINS:
            for local in (None, *SKINS):
                config = self.config(local, None, global_skin, "separate")
                policy = render_policy(config, windows(config)[0])
                self.assertEqual(policy["backdrop"], (local or global_skin) in GLASS_SKINS)
                self.assertIsNone(policy["panel_skin"])
                self.assertTrue(policy["card_surfaces"])

    def test_uniform_group_uses_its_members_material_including_all_minimal(self):
        for global_skin in SKINS:
            for local in SKINS:
                config = self.config(local, local, global_skin)
                policy = render_policy(config, windows(config)[0])
                self.assertEqual(policy["panel_skin"], local)
                self.assertFalse(policy["card_surfaces"])
                self.assertEqual(policy["backdrop"], local in GLASS_SKINS)

    def test_mixed_groups_never_paint_a_global_slab_beneath_their_children(self):
        for first in SKINS:
            for second in SKINS:
                if first == second:
                    continue
                config = self.config(first, second)
                policy = render_policy(config, windows(config)[0])
                self.assertIsNone(policy["panel_skin"])
                self.assertTrue(policy["card_surfaces"])
                mixed_minimal = "minimal" in (first, second) and bool({first, second} & GLASS_SKINS)
                self.assertEqual(
                    policy["fallback_reason"], "mixed-minimal" if mixed_minimal else ""
                )
                self.assertEqual(
                    policy["backdrop"], bool({first, second} & GLASS_SKINS) and not mixed_minimal
                )

    def test_disabled_unrepresented_members_do_not_affect_policy(self):
        config = self.config("minimal", "glass")
        config["widgets"]["gpu"]["enabled"] = False
        policy = render_policy(config, windows(config)[0])
        self.assertEqual(policy["panel_skin"], "minimal")
        self.assertFalse(policy["backdrop"])
        self.assertFalse(render_policy(config, dict(id="group", cells=[]))["card_surfaces"])

    def controller(self, config):
        with patch("native_controller.load", return_value=copy.deepcopy(config)):
            return Controller()

    def test_group_preview_preserves_independent_member_sizes(self):
        config = self.config("card", "card")
        config["widgets"]["cpu"]["size"] = 180
        config["widgets"]["gpu"]["size"] = 76
        controller = self.controller(config)
        self.assertEqual(controller.previewState("cpu")["height"], 270)
        self.assertEqual(controller.previewState("gpu")["height"], 114)

    def test_preview_uses_work_area_fit_and_material_result_without_inventing_blur(self):
        config = self.config("glass", "minimal")
        controller = self.controller(config)
        controller.set_preview_area(320, 240)
        specs, _ = grid_plan(windows(config), 320, 240, config["layout"])
        expected = next(cell for cell in specs[0]["cells"] if cell["key"] == "cpu")
        state = controller.previewState("cpu")
        self.assertEqual((state["width"], state["height"]), (expected["width"], expected["height"]))
        self.assertFalse(state["frosted"])
        self.assertEqual(state["note"], "")
        self.assertTrue(state["coating_translucent"])
        controller.set_window_materials({"group": {"material": "desktop-acrylic"}})
        self.assertFalse(controller.previewState("cpu")["frosted"])
        self.assertEqual(controller.previewState("gpu")["status"], "无底色")
        config["widgets"]["gpu"]["skin"] = "glass"
        controller.edit(config)
        self.assertTrue(controller.previewState("cpu")["frosted"])
        self.assertFalse(controller.previewState("cpu")["compositing_verified"])

    def test_disabled_and_unknown_widget_previews_are_safe(self):
        config = self.config("minimal", "glass")
        config["widgets"]["cpu"]["enabled"] = False
        controller = self.controller(config)
        self.assertEqual(controller.previewState("cpu")["status"], "无底色")
        self.assertFalse(controller.previewState("cpu")["frosted"])
        self.assertEqual(controller.previewState("missing"), {})

    def test_display_change_recomputes_sizes_but_headless_and_shutdown_do_not(self):
        runtime = SimpleNamespace(shutting_down=False, headless=False, apply=Mock())
        Runtime.fit_windows(runtime)
        runtime.apply.assert_called_once_with(False)
        runtime.shutting_down = True
        Runtime.fit_windows(runtime)
        runtime.shutting_down, runtime.headless = False, True
        Runtime.fit_windows(runtime)
        runtime.apply.assert_called_once()

    def test_uniform_tint_preview_exposes_the_shared_panel_slice(self):
        config = self.config("tint", "tint", global_skin="minimal")
        config["widgets"]["cpu"]["size"] = 180
        config["widgets"]["gpu"].update(size=76, form="wide")
        controller = self.controller(config)
        controller.set_preview_area(620, 360)
        controller.set_window_materials(
            {"group": {"material": "desktop-acrylic", "compositing_verified": False}}
        )
        specs, _ = grid_plan(windows(config), 620, 360, config["layout"])
        panel = specs[0]
        for cell in panel["cells"]:
            with self.subTest(widget=cell["key"]):
                state = controller.previewState(cell["key"])
                self.assertEqual(state["panel_skin"], "tint")
                self.assertFalse(state["card_surfaces"])
                self.assertEqual(
                    (state["cell_x"], state["cell_y"], state["width"], state["height"]),
                    (cell["x"], cell["y"], cell["width"], cell["height"]),
                )
                self.assertEqual(
                    (state["panel_width"], state["panel_height"]),
                    (panel["width"], panel["height"]),
                )
                self.assertTrue(state["frosted"])
                self.assertFalse(state["compositing_verified"])

    def test_separate_and_disabled_previews_have_no_shared_panel(self):
        config = self.config("tint", "tint", mode="separate")
        controller = self.controller(config)
        for enabled in (True, False):
            config["widgets"]["cpu"]["enabled"] = enabled
            controller.edit(config)
            state = controller.previewState("cpu")
            self.assertIsNone(state["panel_skin"])
            self.assertTrue(state["card_surfaces"])
            self.assertEqual((state["cell_x"], state["cell_y"]), (0, 0))
            self.assertEqual(
                (state["panel_width"], state["panel_height"]),
                (state["width"], state["height"]),
            )


class RuntimeMaterialCompatibilityTests(unittest.TestCase):
    def runtime_and_window(self):
        controller = SimpleNamespace(
            _draft={"theme": "dark"},
            _saved={"theme": "light"},
            set_material=Mock(),
            set_window_materials=Mock(),
        )
        runtime = SimpleNamespace(controller=controller, composition={})
        window = Mock()
        window.winId.return_value = 123
        window.rendererInterface.return_value.graphicsApi.return_value = SimpleNamespace(
            name="MockDirect3D11"
        )
        return runtime, window

    def test_material_backend_exceptions_keep_the_widget_in_solid_fallback(self):
        for error in (OSError("backend unavailable"), AttributeError("entry point unavailable")):
            with self.subTest(error=type(error).__name__):
                runtime, window = self.runtime_and_window()
                with (
                    patch("native_runtime.widget_material", side_effect=error) as compose,
                    patch("native_runtime.desktop_level") as place,
                    self.assertLogs(level="WARNING"),
                ):
                    Runtime.compose(runtime, window, "cpu", enabled=True)
                report = runtime.composition["cpu"]
                self.assertEqual(report["material"], "solid")
                self.assertFalse(report["compositing_verified"])
                self.assertEqual(report["backend_error"], str(error))
                self.assertEqual(report["renderer"], "MockDirect3D11")
                compose.assert_called_once_with(True)
                place.assert_called_once_with(123)
                window.setProperty.assert_called_once_with("composition", report)
                runtime.controller.set_window_materials.assert_called_once_with(
                    runtime.composition
                )

    def test_settings_fallback_uses_draft_theme_and_does_not_place_desktop_window(self):
        runtime, window = self.runtime_and_window()
        with (
            patch("native_runtime.glass", side_effect=OSError("unavailable")) as compose,
            patch("native_runtime.desktop_level") as place,
            self.assertLogs(level="WARNING"),
        ):
            Runtime.compose(runtime, window, "settings")
        compose.assert_called_once_with(123, True, True)
        place.assert_not_called()
        window.setProperty.assert_not_called()
        runtime.controller.set_material.assert_called_once_with(runtime.composition["settings"])

    def test_desktop_placement_exceptions_do_not_abort_material_delivery(self):
        for error in (OSError("placement unavailable"), AttributeError("entry point unavailable")):
            with self.subTest(error=type(error).__name__):
                runtime, window = self.runtime_and_window()
                report = {"material": "solid", "compositing_verified": False}
                with (
                    patch("native_runtime.widget_material", return_value=report),
                    patch("native_runtime.desktop_level", side_effect=error),
                    self.assertLogs(level="WARNING"),
                ):
                    Runtime.compose(runtime, window, "cpu", enabled=False)
                self.assertEqual(runtime.composition["cpu"]["desktop_level_error"], str(error))
                runtime.controller.set_window_materials.assert_called_once_with(
                    runtime.composition
                )

    def test_programming_errors_are_not_hidden_by_compatibility_fallback(self):
        for error_type in (ValueError, RuntimeError):
            for boundary in ("widget_material", "desktop_level"):
                with self.subTest(error=error_type.__name__, boundary=boundary):
                    runtime, window = self.runtime_and_window()
                    with (
                        patch(
                            "native_runtime.widget_material",
                            return_value={"material": "solid", "compositing_verified": False},
                        ) as compose,
                        patch("native_runtime.desktop_level") as place,
                    ):
                        (compose if boundary == "widget_material" else place).side_effect = error_type(
                            "programming error"
                        )
                        with self.assertRaises(error_type):
                            Runtime.compose(runtime, window, "cpu")

    def watched_runtime(self):
        runtime = SimpleNamespace(watched_screens=set(), fit_windows=Mock())
        runtime.watch_screen = lambda screen: Runtime.watch_screen(runtime, screen)
        return runtime

    def test_screen_watch_is_deduplicated_and_destroyed_screens_are_released(self):
        runtime, screen = self.watched_runtime(), Mock()
        Runtime.watch_screen(runtime, None)
        Runtime.watch_screen(runtime, screen)
        Runtime.watch_screen(runtime, screen)
        self.assertEqual(runtime.watched_screens, {screen})
        screen.availableGeometryChanged.connect.assert_called_once()
        screen.destroyed.connect.assert_called_once()
        geometry_callback = screen.availableGeometryChanged.connect.call_args.args[0]
        geometry_callback(object())
        runtime.fit_windows.assert_called_once()
        screen.destroyed.connect.call_args.args[0](object())
        self.assertEqual(runtime.watched_screens, set())

    def test_added_replacement_screen_receives_its_own_work_area_subscription(self):
        runtime, old, replacement = self.watched_runtime(), Mock(), Mock()
        Runtime.screen_added(runtime, old)
        Runtime.screen_added(runtime, old)
        old.availableGeometryChanged.connect.assert_called_once()
        Runtime.screen_removed(runtime, old)
        self.assertNotIn(old, runtime.watched_screens)
        Runtime.screen_added(runtime, replacement)
        self.assertEqual(runtime.watched_screens, {replacement})
        replacement.availableGeometryChanged.connect.assert_called_once()
        # The old screen may be destroyed after the replacement has been added.
        old.destroyed.connect.call_args.args[0](old)
        self.assertEqual(runtime.watched_screens, {replacement})
        runtime.fit_windows.reset_mock()
        replacement.availableGeometryChanged.connect.call_args.args[0](object())
        runtime.fit_windows.assert_called_once()
