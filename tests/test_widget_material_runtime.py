"""Synthetic runtime/bridge regressions; no Runtime init, native API or persistence."""

import copy
import os
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault(
    "DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign16")
)

from PySide6.QtCore import QCoreApplication, QEvent, QRect
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication

import native_runtime
from native_runtime import Runtime
from native_surface import paint_surface
from settings_material_bridge import SettingsMaterialBridge
from skin_styles import glass_options, palette
from stats_config import DEFAULT
from widget_material_geometry import backdrop_shapes

GOOD = dict(
    material="system-blur",
    status="configured-unverified",
    blur_configured=True,
    bool_result=1,
    last_error=0,
    ok=True,
    coating_allowed=True,
    coating_translucent=True,
    compositing_verified=False,
)


class Window:
    def __init__(self, spec, events=None):
        self.spec = spec
        self.events = events if events is not None else []
        self.props = {"spec": spec}
        self.flag_value = 0
        self.visible = True
        self.widthChanged = SimpleNamespace(connect=Mock())
        self.heightChanged = SimpleNamespace(connect=Mock())
        self.hide = Mock(side_effect=lambda: self.events.append("hide"))
        self.deleteLater = Mock(side_effect=lambda: self.events.append("delete"))
        self.show = Mock()
        self.setMask = Mock()

    def width(self):
        return self.spec["width"]

    def height(self):
        return self.spec["height"]

    def winId(self):
        return 51

    def flags(self):
        return self.flag_value

    def isVisible(self):
        return self.visible

    def property(self, name):
        return self.props.get(name)

    def setProperty(self, name, value):
        self.props[name] = value
        if name == "spec":
            self.spec = value
        if name == "nativeFlags":
            self.flag_value = value
            self.events.append("flags")

    def resize(self, *_args):
        pass

    def rendererInterface(self):
        return SimpleNamespace(graphicsApi=lambda: SimpleNamespace(name="Software"))


class WidgetRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "Only offscreen tests are permitted"

    def setUp(self):
        for target in (
            "ctypes.WinDLL",
            "subprocess.Popen",
            "native_controller.save",
            "native_controller.set_autostart",
            "native_runtime.write_positions",
        ):
            guard = patch(target, side_effect=AssertionError("No native, process or persistence"))
            forbidden = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(forbidden.assert_not_called)

    def runtime(self, grouped=False):
        config = copy.deepcopy(DEFAULT)
        config.update(skin="glass", mode="combined" if grouped else "separate", theme="light")
        for key in ("cpu", "gpu"):
            config["widgets"][key].update(skin=None, glass_curvature=None, glass_transparency=None)
        key = "group" if grouped else "cpu"
        cells = [dict(key="cpu", x=0, y=0, width=220, height=166)]
        if grouped:
            cells.append(dict(key="gpu", x=232, y=0, width=220, height=166))
        spec = dict(id=key, width=452 if grouped else 220, height=166, cells=cells)
        window = Window(spec)
        bridge = Mock()
        r = SimpleNamespace(
            headless=False,
            shutting_down=False,
            settings=Mock(),
            controller=SimpleNamespace(
                _saved=config,
                _draft=copy.deepcopy(config),
                set_window_materials=Mock(),
                set_material=Mock(),
                set_motion_enabled=Mock(),
                set_preview_area=Mock(),
                set_screen_inventory=Mock(),
                set_status=Mock(),
                close=Mock(),
            ),
            widgets={key: window},
            _spec_by_id={key: spec},
            composition={
                key: dict(GOOD),
                "settings": {"material": "desktop-acrylic", "backdrop_type": 3},
            },
            widget_materials={key: bridge},
            widget_blur=Mock(),
            transparency=True,
            _widget_appearance_config={key: config},
            _widget_native_options={key: (True, "light")},
            _widget_mask_states={},
            _widget_mask_pending=set(),
            widget_mask_timer=Mock(),
            _appearance_states={},
            positions={},
            motion={},
            drag_origins={},
            top_bar=None,
            frame_bridge=Mock(),
            floor_timer=Mock(),
            stale_timer=Mock(),
            position_timer=Mock(),
            save_positions=Mock(),
            cancel_motion=Mock(),
            arrange=Mock(),
            update_menu=Mock(),
            compose=Mock(),
            refresh_appearance=Mock(),
            ensure_widget_material=Mock(),
            screen_inventory=Mock(return_value=[]),
            tray=None,
            details=None,
            settings_material=None,
        )
        r.settings.isVisible.return_value = False
        r.widget_mask_timer.isActive.return_value = False
        r.queue_widget_mask = MethodType(Runtime.queue_widget_mask, r)
        r.widget_blur.apply.side_effect = lambda *_a, **_k: dict(GOOD)
        r.widget_blur.clear.return_value = {"ok": True, "cleanup_complete": True, "bool_result": 1}
        r.widget_blur.close.return_value = {"complete": True}
        area = QRect(0, 0, 1280, 720)
        r.app = SimpleNamespace(
            primaryScreen=lambda: SimpleNamespace(availableGeometry=lambda: area)
        )
        return r, key, window, spec

    def test_refresh_keeps_system_blur_report_and_changes_only_coating_or_mask(self):
        r, key, window, _ = self.runtime()
        r.controller._saved.update(glass_transparency=37.25, glass_curvature=70.5)
        original = copy.deepcopy(r.composition["settings"])
        with patch.object(
            native_runtime, "widget_material", side_effect=AssertionError("Alpha overwrite")
        ):
            Runtime.refresh_appearance(r)
        self.assertEqual(r.composition[key]["material"], "system-blur")
        self.assertTrue(r.composition[key]["blur_configured"])
        self.assertEqual(r.composition[key]["bool_result"], 1)
        self.assertEqual(r.composition["settings"], original)
        r.controller.set_material.assert_not_called()
        r.widget_materials[key].request.assert_not_called()
        self.assertIn(key, r._widget_mask_pending)
        self.assertEqual(window.property("appearanceConfig")["glass_curvature"], 70.5)

    def test_mixed_minimal_requests_clear_keeps_alpha_and_settings_separate(self):
        r, key, window, _ = self.runtime(True)
        r.controller._saved["widgets"]["gpu"]["skin"] = "minimal"
        r.widget_blur.apply.side_effect = None
        r.widget_blur.apply.return_value = dict(
            ok=True,
            material="solid",
            status="no-blur",
            blur_configured=False,
            blur_may_remain=False,
            bool_result=1,
            fallback_reason="material-disabled",
        )
        policy = {"state": "allowed", "reason": "allowed"}
        report = Runtime._widget_material_request(r, key, window, 51, policy)
        r.widget_blur.apply.assert_called_once_with(51, enabled=False, policy=policy)
        self.assertFalse(report["blur_configured"])
        self.assertTrue(report["coating_translucent"])
        self.assertEqual(report["fallback_reason"], "material-disabled")
        self.assertEqual(report["surface_fallback_reason"], "mixed-minimal")
        Runtime._publish_widget_material(r, key, window, report)
        r.controller.set_material.assert_not_called()
        self.assertEqual(r.composition["settings"]["material"], "desktop-acrylic")

    def test_failed_mixed_clear_preserves_native_reason_and_never_expands_mask(self):
        r, key, window, spec = self.runtime(True)
        previous = backdrop_shapes(r.controller._saved, spec, window.width(), window.height())
        r._widget_mask_states[key] = (window, previous)
        r.controller._saved["widgets"]["gpu"]["skin"] = "minimal"
        r.widget_blur.apply.side_effect = None
        r.widget_blur.apply.return_value = dict(
            ok=False,
            material="solid",
            status="cleanup-failed",
            blur_configured=False,
            blur_may_remain=True,
            last_error=5,
            fallback_reason="accent-clear-failed",
        )
        report = Runtime._widget_material_request(r, key, window, 51, {"state": "allowed"})
        self.assertEqual(report["fallback_reason"], "accent-clear-failed")
        r.composition[key] = report
        r._widget_mask_pending.add(key)
        Runtime.update_widget_masks(r)
        window.setMask.assert_not_called()
        self.assertEqual(r._widget_mask_states[key], (window, previous))

    def test_publish_rejects_replaced_window_and_shutdown(self):
        r, key, window, spec = self.runtime()
        before = copy.deepcopy(r.composition)
        Runtime._publish_widget_material(r, key, Window(spec), dict(GOOD))
        r.shutting_down = True
        Runtime._publish_widget_material(r, key, window, dict(GOOD))
        self.assertEqual(r.composition, before)
        r.controller.set_window_materials.assert_not_called()

    def test_release_returns_backend_cleanup_diagnostics(self):
        r, key, _, _ = self.runtime()
        expected = dict(ok=False, last_error=87, cleanup_complete=False, blur_may_remain=True)
        r.widget_blur.clear.return_value = expected
        with self.assertLogs(level="WARNING"):
            result = Runtime._release_widget_surface(r, key, 51)
        self.assertEqual(result, expected)

    def test_mask_uses_current_size_caches_and_clears_after_confirmed_removal(self):
        r, key, window, _ = self.runtime()
        events = []
        window.setMask.side_effect = lambda _mask: events.append("mask")
        r.widget_blur.apply.side_effect = lambda *_args, **_kwargs: (
            events.append("blur") or dict(GOOD)
        )
        Runtime._widget_material_request(r, key, window, 51, {"state": "allowed"})
        self.assertEqual(events, ["mask", "blur"], "Clip must precede enabling whole-HWND blur")
        r._widget_mask_pending.add(key)
        Runtime.update_widget_masks(r)
        region = window.setMask.call_args.args[0]
        self.assertEqual(region.boundingRect(), QRect(0, 0, 220, 166))
        r._widget_mask_pending.add(key)
        Runtime.update_widget_masks(r)
        self.assertEqual(window.setMask.call_count, 1)
        r.composition[key].update(blur_configured=False, blur_may_remain=False)
        r._widget_mask_pending.add(key)
        Runtime.update_widget_masks(r)
        self.assertTrue(window.setMask.call_args.args[0].isEmpty())

    def test_geometry_corner_matches_current_vector_painter_at_legacy_and_responsive_sizes(self):
        r, _, _, spec = self.runtime()
        config = r.controller._saved
        for responsive in (False, True):
            config["widgets"]["cpu"].update(
                width=220 if responsive else None,
                height=166 if responsive else None,
                form="free" if responsive else "square",
                layout_mode="auto",
            )
            for curvature in (0, 37.25, 100):
                config["glass_curvature"] = curvature
                for height in (166, 320):
                    scale = 1 if responsive else height / 160
                    color = palette(
                        "glass", False, config["opacity"], **glass_options(config, "cpu")
                    )
                    painter = Mock()
                    painter.worldTransform.return_value = SimpleNamespace(
                        m11=lambda: scale, m12=lambda: 0, m21=lambda: 0, m22=lambda: scale
                    )
                    painter.device.return_value.devicePixelRatioF.return_value = 1
                    paint_surface(painter, 360 / scale, height / scale, color)
                    rect, radius, _ = painter.drawRoundedRect.call_args.args
                    outer_radius = (radius + rect.x()) * scale
                    shape = backdrop_shapes(config, spec, 360, height)[0]
                    self.assertAlmostEqual(shape[4], outer_radius)

    def test_removal_and_flag_change_close_material_before_delete_or_flags(self):
        for remove in (True, False):
            with self.subTest(remove=remove):
                r, key, window, spec = self.runtime()
                events = window.events
                r.widget_materials[key].close.side_effect = lambda: (
                    events.append("bridge-close"),
                    r.widget_blur.clear(51),
                )
                r.widget_blur.clear.side_effect = lambda _h: (
                    events.append("blur-clear") or {"ok": True}
                )
                r.frame_bridge.unregister.side_effect = lambda _w: events.append("unregister")
                specs = [] if remove else [spec]
                with (
                    patch.object(native_runtime, "desktop_plan", return_value=(specs, {})),
                    patch.object(native_runtime, "animations_enabled", return_value=False),
                ):
                    Runtime.apply(r)
                self.assertLess(events.index("bridge-close"), events.index("blur-clear"))
                self.assertLess(events.index("blur-clear"), events.index("unregister"))
                self.assertLess(
                    events.index("blur-clear"), events.index("delete" if remove else "flags")
                )

    def test_shutdown_handles_optional_none_and_releases_surfaces_before_backend(self):
        for optional in (False, True):
            with self.subTest(optional=optional):
                r, key, window, _ = self.runtime()
                events = window.events
                r.widget_materials[key].close.side_effect = lambda: events.append("bridge-close")
                r.widget_blur.close.side_effect = lambda: events.append("backend-close")
                if optional:
                    r.headless = True
                    r.widget_materials = {}
                    r.widget_blur = None
                    r.frame_bridge = None
                Runtime.shutdown(r)
                self.assertTrue(r.shutting_down)
                r.controller.close.assert_called_once()
                r.widget_mask_timer.stop.assert_called_once()
                if not optional:
                    self.assertLess(events.index("hide"), events.index("bridge-close"))
                    self.assertLess(events.index("bridge-close"), events.index("backend-close"))

    def test_precreated_hidden_surface_is_adopted_on_show_and_released_on_close(self):
        window = QWindow()
        handle = int(window.winId())  # Emulates watch_moves before material binding.
        compose = Mock(return_value=dict(GOOD))
        release = Mock(return_value={"ok": True, "cleanup_complete": True})
        bridge = SettingsMaterialBridge(
            window,
            backend="system-blur",
            compose_once=compose,
            policy_reader=lambda: {"state": "allowed"},
            publish=Mock(),
            release_surface=release,
        )
        try:
            bridge.start()
            window.show()  # Asserted offscreen; no Windows native window.
            self.app.processEvents()
            self.assertEqual(bridge.status()["handle"], handle)
            bridge.compose_now()
            compose.assert_called_once()
            bridge.close()
            release.assert_called_once_with(handle)
        finally:
            bridge.close()
            window.destroy()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main(verbosity=2)
