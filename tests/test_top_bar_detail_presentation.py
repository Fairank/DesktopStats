"""Detail-first-presentation contracts with fake windows/native backend only.

These exercise the real material factory and Manager call order. No QML
window is created or shown, no AppBar registered and no sensor/IPC is used.
"""

import copy
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from appbar_platform import AppBarError
from top_bar_runtime import OVERFLOW, TopBarManager

if __package__:
    from . import test_top_bar_runtime as fixture
else:
    import test_top_bar_runtime as fixture


class DetailWindow(fixture.Window):
    def __init__(self, *args):
        super().__init__(*args)
        self.widthChanged, self.heightChanged = Mock(), Mock()
        self.setMask = Mock()
        self.binding, self.surface_serial = None, 1
        self.released = False

    def isVisible(self):
        return self.visible


class DetailAdapter(fixture.Adapter):
    def __init__(self):
        super().__init__()
        self.timeline, self.before_show = [], []
        self.invalid_tokens = set()
        self.backend = SimpleNamespace(validate=self.validate)

    def validate(self, token):
        binding = next((b for b in self.created if b.token is token), None)
        if binding is None or id(token) in self.invalid_tokens or binding.window.released:
            raise AppBarError("Artificial own generation is not current")

    def prepare(self, window, screen):
        binding = super().prepare(window, screen)
        binding.token.generation = len(self.created)
        window.binding = binding
        self.timeline.append(("prepare", window.kind, binding.hwnd))
        return binding

    def place_panel(self, binding, *args):
        self.timeline.append(("position", binding.hwnd))
        return super().place_panel(binding, *args)

    def show(self, binding, *, activate=False):
        if binding.window.kind == "details":
            state = binding.window.state
            self.before_show.append(
                dict(
                    coating=state.detailCoatingTranslucent,
                    report=copy.deepcopy(state.materialReports.get("details", {})),
                    binding=binding,
                    was_visible=binding.window.visible,
                )
            )
            self.timeline.append(("show", binding.hwnd))
        return super().show(binding, activate=activate)

    def release(self, binding):
        self.timeline.append(("release", binding.hwnd))
        binding.window.released = True
        return super().release(binding)


class DetailBackend:
    def __init__(self, owner):
        self.owner, self.succeed = owner, True
        self.calls, self.clears = [], []
        self.hook, self.closed = None, False
        self.close_calls = 0

    def apply(self, handle, *, enabled, policy):
        binding = next(b for b in self.owner.adapter.created if b.hwnd == handle)
        self.owner.adapter.timeline.append(("apply", handle, binding.window.visible))
        self.calls.append((handle, enabled, copy.deepcopy(policy)))
        if self.hook:
            self.hook()
        allowed = policy.get("state") == "allowed"
        configured = self.succeed and enabled and allowed
        return dict(
            ok=self.succeed,
            material="system-blur" if configured else "solid",
            coating_allowed=allowed,
            blur_configured=configured,
            blur_may_remain=False,
            bool_result=1 if self.succeed else 0,
            status="configured-unverified" if configured else "fallback",
            fallback_reason="" if configured else "artificial-fallback",
            compositing_verified=False,
        )

    def clear(self, handle):
        self.clears.append(handle)
        self.owner.adapter.timeline.append(("clear", handle))
        return dict(ok=True, cleanup_complete=True)

    def close(self):
        self.close_calls += 1
        self.closed = True
        return dict(ok=True, complete=True)


class DetailBridge:
    """Controlled lifecycle callbacks; no GUI window/native/timer operations."""

    def __init__(self, window, parent, **callbacks):
        self.window, self.callbacks = window, callbacks
        self.closed, self.started, self.deleted = False, False, False
        self.reasons = []

    def start(self):
        self.started = True

    def status(self):
        binding = self.window.binding
        return dict(
            closed=self.closed,
            started=self.started,
            surface_alive=binding is not None,
            surface_handle=binding.hwnd if binding else 0,
            surface_serial=self.window.surface_serial,
            last_request=dict(reasons=list(self.reasons)),
            render_ready=self.window.visible,
            render_gate=True,
            first_frame_observed=self.window.visible,
        )

    def request(self, reason):
        if self.closed:
            return False
        self.reasons = [reason]
        report = self.callbacks["compose_once"](
            self.window.binding.hwnd, self.callbacks["policy_reader"]()
        )
        if report is not None:
            self.callbacks["publish"](report)
        return report

    def close(self):
        if not self.closed:
            self.closed = True
            if self.window.binding is not None:
                self.callbacks["release_surface"](self.window.binding.hwnd)

    def deleteLater(self):
        self.deleted = True


class TopBarDetailPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        if cls.qt.platformName() != "offscreen":
            raise RuntimeError("This suite must run on offscreen Qt only")

    def setUp(self):
        native = self.enterContext(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native DLL"))
        )
        process = self.enterContext(
            patch("subprocess.Popen", side_effect=AssertionError("No subprocess"))
        )
        # Run after manager cleanup, before restoring the guards. A swallowed
        # forbidden request must fail the test too, not just return fallback.
        self.addCleanup(lambda: self.assertEqual(native.call_count, 0))
        self.addCleanup(lambda: self.assertEqual(process.call_count, 0))
        self.controller = fixture.Controller()
        self.a = fixture.Screen("DISPLAY1", fixture.PixelRect(0, 0, 1920, 1080))
        self.b = fixture.Screen("DISPLAY2", fixture.PixelRect(-2560, -200, 0, 1240), dpi=144)
        self.app = fixture.Application([self.a, self.b])
        self.runtime = SimpleNamespace(
            app=self.app, controller=self.controller, headless=True, show_settings=lambda _key: None
        )
        self.adapter, self.windows, self.backends = DetailAdapter(), [], []
        self.policy = dict(state="allowed", reason="synthetic")

        def window_factory(*args):
            window = DetailWindow(*args)
            self.windows.append(window)
            return window

        self.manager = TopBarManager(
            self.runtime, adapter=self.adapter, window_factory=window_factory
        )
        self.manager.apply(fixture.config(mode="all"))
        self.enterContext(patch.object(self.manager, "_native_windows", return_value=True))
        self.enterContext(patch("settings_material_bridge.SettingsMaterialBridge", DetailBridge))
        self.enterContext(
            patch("native_platform.transparency_policy", new=lambda: copy.deepcopy(self.policy))
        )

        def backend_factory():
            backend = DetailBackend(self)
            self.backends.append(backend)
            return backend

        self.enterContext(patch("native_widget_material.WidgetBlurBackend", new=backend_factory))
        self.addCleanup(self.manager.close)

    def open_panel(self, host="DISPLAY1", item="b_0", pinned=False):
        self.manager._show_panel(self.manager.hosts[host], item, pinned)
        self.assertIsNotNone(self.manager._panel)
        return self.manager._panel

    def test_successful_material_and_coating_are_ready_before_first_show(self):
        panel = self.open_panel()
        snapshot = self.adapter.before_show[-1]
        self.assertTrue(snapshot["coating"])
        self.assertTrue(snapshot["report"]["blur_configured"])
        self.assertFalse(snapshot["report"]["compositing_verified"])
        self.assertFalse(snapshot["was_visible"])
        handle = panel["binding"].hwnd
        timeline = self.adapter.timeline
        self.assertLess(
            timeline.index(("position", handle)), timeline.index(("apply", handle, False))
        )
        self.assertLess(timeline.index(("apply", handle, False)), timeline.index(("show", handle)))

    def test_unbound_material_cannot_issue_any_native_request(self):
        host = self.manager.hosts["DISPLAY1"]
        window = DetailWindow("details", host.state, self.a, False)
        material = self.manager._material_bridge(window, host.state, "details")
        self.addCleanup(material.close)
        with self.assertRaises(AppBarError):
            material.prepare_before_show()
        self.assertFalse(self.backends[-1].calls)

    def test_first_frame_shown_and_activation_events_reuse_success(self):
        panel = self.open_panel()
        material, backend = panel["material_bridge"], self.backends[-1]
        for reason in (
            "shown",
            "graphics_ready",
            "first_frame",
            "exposed",
            "activated",
            "deactivated",
            "retry",
        ):
            material.bridge.request(reason)
        self.assertEqual(len(backend.calls), 1)
        self.assertTrue(panel["host"].state.detailCoatingTranslucent)

    def test_initial_failure_remains_solid_during_automatic_bootstrap_retry(self):
        factory = self.manager._material_bridge

        def failing_factory(*args):
            result = factory(*args)
            self.backends[-1].succeed = False
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=failing_factory):
            panel = self.open_panel()
        backend = self.backends[-1]
        self.assertFalse(self.adapter.before_show[-1]["coating"])
        backend.succeed = True
        for reason in ("shown", "graphics_ready", "first_frame", "exposed", "activated", "retry"):
            panel["material_bridge"].bridge.request(reason)
        self.assertEqual(len(backend.calls), 1)
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)

    def test_known_disabled_and_unknown_policy_start_and_remain_solid(self):
        for state in ("disabled", "unknown"):
            with self.subTest(policy=state):
                self.policy["state"] = state
                panel = self.open_panel()
                self.assertFalse(self.adapter.before_show[-1]["coating"])
                panel["material_bridge"].bridge.request("first_frame")
                self.assertFalse(panel["host"].state.detailCoatingTranslucent)
                self.manager.close_panel()

    def test_same_panel_metric_change_does_not_prepare_or_reapply_material(self):
        panel = self.open_panel()
        window, backend = panel["window"], self.backends[-1]
        count = len(self.adapter.created)
        other = self.open_panel(item="b_1")
        self.assertIs(other["window"], window)
        self.assertEqual(len(self.adapter.created), count)
        self.assertEqual(len(backend.calls), 1)
        self.assertTrue(self.adapter.before_show[-1]["coating"])

    def test_hover_to_pinned_and_other_monitor_get_separate_prepared_generations(self):
        one = self.open_panel()
        two = self.open_panel(pinned=True)
        three = self.open_panel("DISPLAY2", pinned=False)
        self.assertEqual(len({id(p["window"]) for p in (one, two, three)}), 3)
        self.assertEqual(len(self.backends), 3)
        self.assertTrue(one["window"].deleted)
        self.assertTrue(two["window"].deleted)
        for backend, snapshot in zip(self.backends, self.adapter.before_show):
            self.assertEqual(len(backend.calls), 1)
            self.assertTrue(snapshot["coating"])
        self.assertEqual(three["binding"].dpi, 144)

    def test_overflow_panel_uses_identical_hidden_material_preparation(self):
        host = self.manager.hosts["DISPLAY1"]
        host.overflow_ids = ("b_0", "b_1")
        host.state._overflow = dict(x=400, y=0, width=40, height=32)
        panel = self.open_panel(item=OVERFLOW)
        self.assertTrue(panel["host"].state.detail["overflow"])
        self.assertTrue(self.adapter.before_show[-1]["coating"])
        self.assertEqual(len(self.backends[-1].calls), 1)

    def test_genuine_preference_recovery_can_reconfigure_initial_failed_material(self):
        factory = self.manager._material_bridge

        def failing_factory(*args):
            result = factory(*args)
            self.backends[-1].succeed = False
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=failing_factory):
            panel = self.open_panel()
        material, backend = panel["material_bridge"], self.backends[-1]
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)
        backend.succeed = True
        for reason in (
            "theme_changed",
            "composition_changed",
            "power_changed",
            "display_changed",
            "system_preferences",
            "preference_changed",
        ):
            before = len(backend.calls)
            material.bridge.request(reason)
            self.assertEqual(len(backend.calls), before + 1, reason)
            self.assertTrue(panel["host"].state.detailCoatingTranslucent)

    def test_policy_and_skin_change_invalidate_cached_success(self):
        panel = self.open_panel()
        material, backend = panel["material_bridge"], self.backends[-1]
        self.policy["state"] = "disabled"
        material.bridge.request("first_frame")
        self.assertEqual(len(backend.calls), 2)
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)
        self.policy["state"] = "allowed"
        panel["host"].state._config = dict(panel["host"].state.config, skin="card")
        material.bridge.request("first_frame")
        self.assertEqual(len(backend.calls), 3)
        self.assertFalse(backend.calls[-1][1])
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)

    def test_transient_real_recovery_failure_can_retry_without_bootstrap_snapshot(self):
        panel = self.open_panel()
        material, backend = panel["material_bridge"], self.backends[-1]
        self.assertEqual(len(backend.calls), 1)
        self.assertTrue(panel["host"].state.detailCoatingTranslucent)
        backend.succeed = False
        material.bridge.request("composition_changed")
        self.assertEqual(len(backend.calls), 2)
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)
        backend.succeed = True
        material.bridge.request("retry")
        self.assertEqual(len(backend.calls), 3)
        self.assertTrue(panel["host"].state.detailCoatingTranslucent)

    def test_reentrant_close_during_hidden_apply_never_shows_or_publishes_success(self):
        factory = self.manager._material_bridge

        def closing_factory(*args):
            result = factory(*args)
            self.backends[-1].hook = self.manager.close_panel
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=closing_factory):
            self.manager._show_panel(self.manager.hosts["DISPLAY1"], "b_0", False)
        self.assertIsNone(self.manager._panel)
        self.assertFalse(self.adapter.before_show)
        self.assertFalse(self.manager.hosts["DISPLAY1"].state.detailCoatingTranslucent)
        self.assertEqual(self.backends[-1].close_calls, 1)

    def test_ownership_change_during_hidden_apply_cannot_publish_or_show(self):
        factory = self.manager._material_bridge

        def invalidating_factory(*args):
            result = factory(*args)
            self.backends[-1].hook = lambda: self.adapter.invalid_tokens.add(
                id(result.binding.token)
            )
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=invalidating_factory):
            self.manager._show_panel(self.manager.hosts["DISPLAY1"], "b_0", False)
        self.assertFalse(self.adapter.before_show)
        self.assertFalse(self.manager.hosts["DISPLAY1"].state.detailCoatingTranslucent)
        self.adapter.invalid_tokens.clear()
        self.manager._retry_retired()

    def test_surface_serial_change_during_hidden_apply_cannot_publish_or_show(self):
        factory = self.manager._material_bridge

        def changing_factory(*args):
            result = factory(*args)
            window = result.bridge.window
            self.backends[-1].hook = lambda: setattr(
                window, "surface_serial", window.surface_serial + 1
            )
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=changing_factory):
            self.manager._show_panel(self.manager.hosts["DISPLAY1"], "b_0", False)
        self.assertFalse(self.adapter.before_show)
        self.assertFalse(self.manager.hosts["DISPLAY1"].state.detailCoatingTranslucent)

    def test_closed_panel_cannot_republish_or_prepare_a_cached_success(self):
        panel = self.open_panel()
        material = panel["material_bridge"]
        saved = copy.deepcopy(panel["host"].state.materialReports["details"])
        self.manager.close_panel()
        material.bridge.callbacks["publish"](saved)
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)
        with self.assertRaises(AppBarError):
            material.prepare_before_show()

    def test_incomplete_prepared_material_cleanup_retains_window_and_blocks_replacement(self):
        panel = self.open_panel()
        backend = self.backends[-1]
        backend.clear = Mock(return_value=dict(ok=False, cleanup_complete=False))
        backend.close = Mock(return_value=dict(ok=False, complete=False))
        self.manager.close_panel()
        self.assertIn(panel, self.manager.retired)
        self.assertFalse(panel["window"].deleted)
        self.assertFalse(panel["window"].released)
        count = len(self.adapter.created)
        self.manager._show_panel(self.manager.hosts["DISPLAY2"], "b_0", False)
        self.assertEqual(len(self.adapter.created), count)
        backend.clear.return_value = dict(ok=True, cleanup_complete=True)
        backend.close.return_value = dict(ok=True, complete=True)
        self.manager._retry_retired()
        self.assertFalse(self.manager.retired)
        self.assertTrue(panel["window"].deleted)

    def test_new_failed_pinned_window_does_not_inherit_prior_hover_success(self):
        self.open_panel()
        factory = self.manager._material_bridge

        def failing_factory(*args):
            result = factory(*args)
            self.backends[-1].succeed = False
            return result

        with patch.object(self.manager, "_material_bridge", side_effect=failing_factory):
            panel = self.open_panel(pinned=True)
        self.assertFalse(self.adapter.before_show[-1]["coating"])
        self.assertFalse(self.adapter.before_show[-1]["report"]["ok"])
        self.assertFalse(panel["host"].state.detailCoatingTranslucent)

    def test_bar_composition_keeps_existing_reconfigure_behavior_without_detail_cache(self):
        host = self.manager.hosts["DISPLAY1"]
        material = self.manager._material_bridge(host.window, host.state, "bar")
        self.addCleanup(material.close)
        material.bind(host.binding)
        backend = self.backends[-1]
        for _ in range(2):
            material.bridge.callbacks["compose_once"](host.binding.hwnd, self.policy)
        self.assertEqual(len(backend.calls), 2)

    def test_cleanup_clears_prepared_material_before_releasing_window(self):
        panel = self.open_panel()
        handle, backend = panel["binding"].hwnd, self.backends[-1]
        self.manager.close_panel()
        self.assertIn(handle, backend.clears)
        self.assertLess(
            self.adapter.timeline.index(("clear", handle)),
            self.adapter.timeline.index(("release", handle)),
        )
        self.assertTrue(backend.closed)
        self.assertTrue(panel["window"].deleted)

    def test_reentrant_clear_opening_same_host_keeps_replacement_detail_and_coating(self):
        old_panel = self.open_panel()
        old_backend = self.backends[-1]
        original_clear = old_backend.clear
        opened = False

        def clear_and_open_once(handle):
            nonlocal opened
            result = original_clear(handle)
            if not opened:
                opened = True
                self.manager.click("DISPLAY1", "b_1")
            return result

        with patch.object(old_backend, "clear", side_effect=clear_and_open_once) as clear:
            self.manager.close_panel()
            self.assertEqual(clear.call_count, 1)
        replacement = self.manager._panel
        self.assertIsNotNone(replacement)
        self.assertIsNot(replacement, old_panel)
        self.assertIsNot(replacement["window"], old_panel["window"])
        self.assertTrue(replacement["window"].visible)
        self.assertEqual(replacement["host"].state.detail["id"], "b_1")
        self.assertTrue(replacement["host"].state.detailCoatingTranslucent)
        self.assertTrue(old_panel["window"].deleted)
        self.assertEqual(old_backend.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
