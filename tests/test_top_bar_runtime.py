"""Fake AppBar integration and offscreen QML; no Windows APIs or sensor collectors."""

import copy
import ctypes as c
import math
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMetaObject, QObject, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QWheelEvent
from PySide6.QtQml import QQmlEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from appbar_platform import WINDOW_GENERATION_PROPERTY, AppBarError, AppBarResult
from native_surface import MaterialSurface
from top_bar_layout import PixelRect
from top_bar_runtime import (
    ABN_FULLSCREENAPP,
    ABN_POSCHANGED,
    OVERFLOW,
    BarMaterial,
    BarViewState,
    Binding,
    MonitorInfo,
    ScreenIdentity,
    TopBarManager,
    WindowPreparationError,
    WindowsTopBarAdapter,
)

QQuickStyle.setStyle("Basic")


def config(enabled=True, mode="primary", screens=()):
    return dict(
        theme="light",
        language="en",
        skin="glass",
        opacity=94,
        glass_transparency=60,
        glass_curvature=50,
        top_bar=dict(
            enabled=enabled,
            monitor_mode=mode,
            screens=list(screens),
            height=32,
            items=[dict(id=f"b_{i}", metric="cpu_usage", prefs={}) for i in range(6)],
        ),
    )


def rows(count=6):
    return [
        dict(
            id=f"b_{i}",
            metric="cpu_usage",
            label="CPU usage",
            value=f"{20 + i}%",
            unit="%",
            available=True,
            source="Artificial fixture",
            reason="",
            hardware_name="Fake CPU",
            related=[
                dict(label="Temperature", value="65°C", source="Artificial fixture", reason="")
            ],
            history=[10, 20, None, 30],
        )
        for i in range(count)
    ]


class BarStateInitializationTests(unittest.TestCase):
    def test_spacing_is_ready_before_any_manager_layout_or_self_check_qml(self):
        parent = QObject()
        state = BarViewState(parent, "unlaid-out-self-check")
        self.assertEqual(state.spacing, 12.0)
        self.assertEqual(state.config, {})


class BarMaterialTests(unittest.TestCase):
    """No native execution: backend, sealed generation and Qt bridge are fake."""

    def setUp(self):
        self.backend, self.validate, self.bridge = Mock(), Mock(), Mock()
        self.binding = SimpleNamespace(hwnd=123, token=object())
        self.material = BarMaterial(self.backend, self.validate)
        self.material.bridge = self.bridge
        self.material.bind(self.binding)
        self.backend.clear.return_value = dict(ok=True, cleanup_complete=True)
        self.backend.close.return_value = dict(ok=True, complete=True)

    def test_permission_is_not_enough_and_only_success_configures_coating(self):
        for ok, configured, allowed, expected in (
            (False, False, True, False), (True, False, True, False),
            (True, True, False, False), (True, True, True, True)
        ):
            with self.subTest(ok=ok, configured=configured, allowed=allowed):
                self.backend.apply.return_value = dict(
                    ok=ok, blur_configured=configured, coating_allowed=allowed,
                    material="translucent", blur_may_remain=not ok)
                report = self.material.apply(123, True, {"state": "allowed"})
                self.assertEqual(report["coating_translucent"], expected)
                self.assertFalse(report["compositing_verified"])
                if not expected:
                    self.assertEqual(report["material"], "solid")

    def test_current_generation_is_checked_before_every_material_write(self):
        self.backend.apply.return_value = dict(ok=True, blur_configured=True, coating_allowed=True)
        with self.assertRaises(AppBarError):
            self.material.apply(999, True, {"state": "allowed"})
        self.backend.apply.assert_not_called()
        self.validate.side_effect = AppBarError("generation changed")
        with self.assertRaises(AppBarError):
            self.material.apply(123, True, {"state": "allowed"})
        self.backend.apply.assert_not_called()
        self.validate.assert_called_once_with(self.binding.token)

    def test_close_clears_bridge_then_backend_and_incomplete_cleanup_is_not_success(self):
        events = []
        self.bridge.close.side_effect = lambda: events.append("bridge")
        self.backend.close.side_effect = lambda: events.append("backend") or dict(ok=False, complete=False)
        with self.assertRaisesRegex(AppBarError, "cleanup is incomplete"):
            self.material.close()
        self.assertEqual(events, ["bridge", "backend"])
        self.bridge.deleteLater.assert_not_called()
        self.backend.close.side_effect = lambda: dict(ok=True, complete=True)
        self.material.close()
        self.material.deleteLater()
        self.bridge.deleteLater.assert_called_once()

    def test_release_never_calls_native_for_an_unattempted_hidden_surface(self):
        self.assertTrue(self.material.clear(123)["cleanup_complete"])
        self.backend.clear.assert_not_called()
        self.validate.assert_not_called()

    def test_failed_release_keeps_attempt_and_generation_guard_for_retry(self):
        self.material.attempted = True
        self.backend.clear.return_value = dict(ok=False, cleanup_complete=False)
        self.assertFalse(self.material.clear(123)["cleanup_complete"])
        self.assertTrue(self.material.attempted)
        self.backend.close.return_value = dict(ok=False, complete=False)
        with self.assertRaises(AppBarError):
            self.material.close()
        self.assertTrue(self.material.attempted)
        self.backend.clear.return_value = dict(ok=True, cleanup_complete=True)
        self.material.clear(123)
        self.assertFalse(self.material.attempted)

    def test_unknown_or_disabled_skin_cannot_inherit_a_successful_old_coating(self):
        self.backend.apply.return_value = dict(ok=True, blur_configured=False, coating_allowed=False)
        result = self.material.apply(123, False, {"state": "unknown"})
        self.assertFalse(result["coating_translucent"])
        self.assertEqual(result["material"], "solid")


class Controller(QObject):
    dataChanged = Signal()

    def __init__(self):
        super().__init__()
        self.rows, self.calls, self.status = rows(), 0, {}

    def topBarRows(self):
        self.calls += 1
        return copy.deepcopy(self.rows)

    def set_top_bar_status(self, report):
        self.status = copy.deepcopy(report)

    def tr(self, text):
        return text


class Screen:
    def __init__(self, name, physical, dpi=96, native_id=None, handle=18):
        self._name, self.physical, self.dpi = name, physical, dpi
        self.native_id, self.native_handle = native_id or name, handle

    def name(self):
        return self._name

    def nativeInterface(self):
        return SimpleNamespace(handle=lambda: self.native_handle)

    def availableGeometry(self):
        return self.geometry()

    def geometry(self):
        return QRect(
            self.physical.left,
            self.physical.top,
            round(self.physical.width * 96 / self.dpi),
            round(self.physical.height * 96 / self.dpi),
        )


class Application:
    def __init__(self, screens):
        self._screens = screens

    def screens(self):
        return self._screens[:]

    def primaryScreen(self):
        return self._screens[0] if self._screens else None

    def platformName(self):
        return "offscreen"


class Window:
    def __init__(self, kind, state, screen, pinned):
        self.kind, self.state, self.screen, self.pinned = kind, state, screen, pinned
        self.visible, self.deleted, self.activated = False, False, 0
        self._width, self._height = (800, 32) if kind == "bar" else (320, 240)

    def width(self):
        return self._width

    def height(self):
        return self._height

    def deleteLater(self):
        self.deleted = True


class Session:
    def __init__(self, adapter, binding):
        self.adapter, self.binding, self.active = adapter, binding, False
        self._dpi = binding.dpi
        self._fullscreen = False

    def register(self, monitor, *, dpi=96, height_dip=32):
        self.adapter.events.append(("register", self.binding.screen_name, dpi, height_dip))
        if self.adapter.fail_register == self.binding.screen_name:
            return AppBarResult(False, "FAILED", False, None, True, ("fixture failure",))
        self.active, self._dpi = True, dpi
        rect = self.adapter.proposed_band(self.binding, height_dip)
        self.binding.window._width, self.binding.window._height = (
            round(rect.width * 96 / dpi),
            round(rect.height * 96 / dpi),
        )
        return AppBarResult(True, "READY", True, rect, False)

    def relayout(self, monitor, *, dpi=96, height_dip=32):
        self.adapter.events.append(("relayout", self.binding.screen_name))
        return self.register(monitor, dpi=dpi, height_dip=height_dip)

    def shell_recreated(self, epoch):
        self.adapter.events.append(("shell", self.binding.screen_name, epoch))
        return self.register(self.binding.monitor, dpi=self.binding.dpi)

    def fullscreen(self, opened):
        self._fullscreen = opened
        self.adapter.events.append(("fullscreen", self.binding.screen_name, opened))
        return AppBarResult(True, "READY", True, None, False, fullscreen=opened)

    def notify_activation(self, active):
        self.adapter.events.append(("activate_notice", active))
        return AppBarResult(True, "READY", True, None, False)

    def notify_window_position(self):
        self.adapter.events.append(("position_notice", self.binding.screen_name))
        return AppBarResult(True, "READY", True, None, False)

    def close(self):
        self.adapter.events.append(("remove", self.binding.screen_name))
        if self.adapter.fail_close:
            return AppBarResult(False, "FAILED", True, None, False, ("fixture pending cleanup",))
        self.active = False
        return AppBarResult(True, "CLOSED", False, None, True)


class Adapter:
    native = False
    callback_message, taskbar_message = 0xC111, 0xC222

    def __init__(self):
        self.events, self.created = [], []
        self.fail_register, self.fail_close = None, False
        self.coating_calls, self.shows = 0, []
        self.offset = 0

    def screen_identity(self, screen):
        return ScreenIdentity(screen.native_id, screen.native_handle, screen.name())

    def prepare(self, window, screen):
        token = SimpleNamespace(hwnd=100 + len(self.created))
        binding = Binding(
            window,
            token,
            self.screen_identity(screen).native_id,
            screen.physical,
            PixelRect(
                screen.physical.left,
                screen.physical.top + 32,
                screen.physical.right,
                screen.physical.bottom - 40,
            ),
            screen.dpi,
        )
        self.created.append(binding)
        self.events.append(("prepare", window.kind, screen.name()))
        return binding

    def session(self, binding):
        binding.session = Session(self, binding)
        return binding.session

    def snapshot(self, binding):
        binding.monitor, binding.dpi = binding.window.screen.physical, binding.window.screen.dpi
        return binding.monitor, binding.work, binding.dpi

    def proposed_band(self, binding, height):
        rect = binding.monitor
        return PixelRect(
            rect.left,
            rect.top + self.offset,
            rect.right,
            rect.top + self.offset + math.ceil(height * binding.dpi / 96),
        )

    def show(self, binding, *, activate=False):
        if binding.window.kind == "bar":
            assert binding.session.active
        binding.window.visible = True
        binding.window.activated += int(activate)
        self.shows.append((binding.window.kind, activate))

    def hide(self, binding):
        binding.window.visible = False
        self.events.append(("hide", binding.window.kind, binding.screen_name))

    def release(self, binding):
        self.events.append(("release", binding.window.kind, binding.screen_name))

    def place_panel(self, binding, anchor, work, dpi):
        self.events.append(("panel", anchor, work, dpi))

    def coating_allowed(self):
        self.coating_calls += 1
        return True


class TopBarRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = Controller()
        self.a = Screen("DISPLAY1", PixelRect(0, 0, 1920, 1080))
        self.b = Screen("DISPLAY2", PixelRect(-2560, -200, 0, 1240), dpi=144)
        self.app = Application([self.a, self.b])
        self.settings = []
        self.runtime = SimpleNamespace(
            app=self.app,
            controller=self.controller,
            headless=True,
            show_settings=self.settings.append,
        )
        self.adapter = Adapter()
        self.windows = []

        def factory(*args):
            window = Window(*args)
            self.windows.append(window)
            return window

        self.manager = TopBarManager(self.runtime, adapter=self.adapter, window_factory=factory)
        self.addCleanup(self.manager.close)

    def test_disabled_and_default_headless_do_not_create_windows_or_load_native(self):
        self.manager.apply(config(False))
        self.assertEqual(self.windows, [])
        self.assertEqual(self.adapter.events, [])
        self.assertEqual(self.controller.calls, 0)
        other = TopBarManager(self.runtime)
        self.addCleanup(other.close)
        with patch("ctypes.WinDLL", side_effect=AssertionError("native load")):
            other.apply(config(True))
        self.assertEqual(self.controller.status["state"], "unavailable")
        self.assertFalse(other.hosts)

    def test_primary_all_selected_and_missing_screens_preserve_intent(self):
        value = config()
        original = copy.deepcopy(value)
        self.manager.apply(value)
        self.assertEqual(list(self.manager.hosts), ["DISPLAY1"])
        self.assertEqual(self.controller.status["state"], "ready")
        self.assertEqual(value, original)
        self.manager.apply(config(mode="all"))
        self.assertEqual(set(self.manager.hosts), {"DISPLAY1", "DISPLAY2"})
        self.manager.apply(config(mode="selected", screens=["DISPLAY2", "DISCONNECTED"]))
        self.assertEqual(list(self.manager.hosts), ["DISPLAY2"])
        self.assertEqual(self.controller.status["missing_screens"], ["DISCONNECTED"])
        self.app._screens = [self.a]
        self.manager.apply(config(mode="selected", screens=["DISPLAY2", "DISCONNECTED"]))
        self.assertFalse(self.manager.hosts)
        self.assertNotIn("DISPLAY1", self.controller.status["active_screens"])

    def test_duplicate_friendly_names_keep_two_native_targets_and_selected_intent(self):
        self.a._name = self.b._name = "Same friendly panel"
        self.a.native_id, self.a.native_handle = r"\\.\DISPLAY1", 18
        self.b.native_id, self.b.native_handle = r"\\.\DISPLAY2", 19
        self.manager.apply(config(mode="all"))
        self.assertEqual(set(self.manager.hosts), {r"\\.\DISPLAY1", r"\\.\DISPLAY2"})
        self.assertIs(self.manager.hosts[r"\\.\DISPLAY1"].screen, self.a)
        self.assertIs(self.manager.hosts[r"\\.\DISPLAY2"].screen, self.b)
        self.manager.apply(config(mode="selected", screens=[r"\\.\DISPLAY2"]))
        self.assertEqual(list(self.manager.hosts), [r"\\.\DISPLAY2"])
        self.assertIs(self.manager.hosts[r"\\.\DISPLAY2"].screen, self.b)
        self.assertEqual(self.manager.hosts[r"\\.\DISPLAY2"].state.hostId, r"\\.\DISPLAY2")

    def test_unmapped_selected_screen_does_not_fall_back_to_primary(self):
        original = self.adapter.screen_identity

        def identity(screen):
            if screen is self.b:
                raise AppBarError("native interface missing")
            return original(screen)

        self.adapter.screen_identity = identity
        self.manager.apply(config(mode="selected", screens=["DISPLAY2"]))
        self.assertFalse(self.manager.hosts)
        self.assertFalse(self.windows)
        self.assertEqual(self.controller.status["missing_screens"], ["DISPLAY2"])
        self.assertEqual(self.controller.status["state"], "failed")
        self.assertIn("native interface missing", " ".join(self.controller.status["errors"]))

    def test_friendly_name_is_never_accepted_as_a_native_target(self):
        self.b._name = "Mi Monitor"
        self.b.native_id = r"\\.\DISPLAY2"
        self.manager.apply(config(mode="selected", screens=["Mi Monitor"]))
        self.assertFalse(self.manager.hosts)
        self.assertEqual(self.controller.status["missing_screens"], ["Mi Monitor"])

    def test_duplicate_native_identity_is_ambiguous_not_silently_merged(self):
        self.b.native_id = self.a.native_id
        self.manager.apply(config(mode="all"))
        self.assertFalse(self.manager.hosts)
        self.assertFalse(self.windows)
        self.assertEqual(self.controller.status["state"], "failed")
        self.assertIn(
            "ambiguous native screen identity", " ".join(self.controller.status["errors"])
        )

    def test_preparation_identity_change_cannot_register_a_different_screen(self):
        original = self.adapter.prepare

        def prepare(window, screen):
            binding = original(window, screen)
            binding.screen_name = "UNSELECTED"
            return binding

        self.adapter.prepare = prepare
        self.manager.apply(config())
        self.assertFalse(self.manager.hosts)
        self.assertFalse(any(event[0] == "register" for event in self.adapter.events))
        self.assertTrue(self.windows[0].deleted)

    def test_negative_physical_coordinates_and_dpi_are_local_in_qml(self):
        self.manager.apply(config(mode="selected", screens=["DISPLAY2"]))
        host = self.manager.hosts["DISPLAY2"]
        self.assertEqual(host.rect, PixelRect(-2560, -200, 0, -152))
        self.assertEqual(host.state.rows[0]["y"], 0)
        self.assertEqual(host.state.rows[0]["height"], 32)
        self.assertGreaterEqual(host.state.rows[0]["x"], 0)
        self.assertTrue(all(0 <= row["x"] <= 2560 / 1.5 for row in host.state.rows))
        self.assertEqual(self.adapter.shows, [("bar", False)])

    def test_failed_registration_never_shows_or_falls_back_and_other_screen_survives(self):
        self.adapter.fail_register = "DISPLAY2"
        self.manager.apply(config(mode="all"))
        self.assertEqual(list(self.manager.hosts), ["DISPLAY1"])
        failed = next(window for window in self.windows if window.screen is self.b)
        self.assertFalse(failed.visible)
        self.assertTrue(failed.deleted)
        self.assertEqual(self.controller.status["state"], "partial")
        self.assertEqual(self.controller.status["detail"], self.controller.status["reason"])

    def test_notifications_query_without_repeating_reservation_and_shell_rebuild_is_once(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        initial = len([event for event in self.adapter.events if event[0] == "register"])
        for _ in range(20):
            self.manager.native_message(
                host.binding.hwnd, self.adapter.callback_message, ABN_POSCHANGED
            )
        self.manager._refresh()
        self.assertEqual(
            len([event for event in self.adapter.events if event[0] == "register"]), initial
        )
        for _ in range(10):
            self.manager.native_message(host.binding.hwnd, self.adapter.taskbar_message)
        self.manager._refresh()
        self.assertEqual(len([event for event in self.adapter.events if event[0] == "shell"]), 1)
        self.manager.native_message(999999, self.adapter.taskbar_message)
        self.assertFalse(self.manager._shell_pending)

    def test_hover_delay_no_activation_joint_region_close_and_click_pin(self):
        self.manager.apply(config())
        self.manager.hover("DISPLAY1", "b_0")
        self.assertEqual(self.manager._hover_timer.interval(), 350)
        QTest.qWait(250)
        self.assertIsNone(self.manager._panel)
        QTest.qWait(130)
        self.assertIsNotNone(self.manager._panel)
        self.assertFalse(self.adapter.shows[-1][1])
        self.manager.leave()
        QTest.qWait(100)
        self.manager.enter_panel()
        QTest.qWait(190)
        self.assertIsNotNone(self.manager._panel)
        self.manager.click("DISPLAY1", "b_0")
        self.assertTrue(self.manager._panel["pinned"])
        self.assertTrue(self.adapter.shows[-1][1])
        self.manager.hover("DISPLAY1", "b_1")
        self.manager.leave()
        QTest.qWait(270)
        self.assertEqual(self.manager._panel["item"], "b_0")
        self.manager.click("DISPLAY1", "b_0")
        self.assertIsNone(self.manager._panel)

    def test_overflow_details_contains_every_hidden_metric_and_no_duplicate_units(self):
        self.a.physical = PixelRect(0, 0, 500, 800)
        self.controller.rows = rows(24)
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        self.assertGreater(host.state.overflowCount, 0)
        self.assertEqual(len(host.state.rows) + host.state.overflowCount, 24)
        self.manager.click("DISPLAY1", OVERFLOW)
        self.assertEqual([row["id"] for row in host.state.detail["items"]], list(host.overflow_ids))
        self.assertEqual(host.state.rows[0]["value"].count("%"), 1)

    def test_rows_are_shared_and_coalesced_without_registration_or_policy_poll_per_tick(self):
        self.manager.apply(config(mode="all"))
        native_events = len(self.adapter.events)
        policy = self.adapter.coating_calls
        before = self.controller.calls
        for _ in range(20):
            self.controller.dataChanged.emit()
        QTest.qWait(200)  # Allow coarse-timer scheduling under a loaded QA worker.
        self.assertEqual(self.controller.calls, before + 1)
        self.assertEqual(len(self.adapter.events), native_events)
        self.assertEqual(self.adapter.coating_calls, policy)
        self.controller.rows[0]["value"] = "—"
        self.controller.rows[0].update(available=False, reason="Fake sensor unavailable")
        self.manager.update_rows()
        for host in self.manager.hosts.values():
            self.assertEqual(host.state.rows[0]["value"], "—")
            self.assertFalse(host.state.rows[0]["available"])

    def test_pending_cleanup_blocks_duplicate_registration_and_retries_before_delete(self):
        self.manager.apply(config())
        old = self.windows[0]
        self.adapter.fail_close = True
        self.manager.apply(config(False))
        self.assertFalse(old.deleted)
        self.assertTrue(self.manager.retired)
        count = len(self.windows)
        self.manager.apply(config(True))
        self.assertEqual(len(self.windows), count)
        self.assertEqual(self.controller.status["state"], "failed")
        self.adapter.fail_close = False
        self.manager.apply(config(True))
        self.assertTrue(old.deleted)
        self.assertFalse(self.manager.retired)
        self.assertEqual(len(self.manager.hosts), 1)

    def test_fullscreen_closes_details_and_paused_state_waits_for_explicit_resume(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        host = self.manager.hosts["DISPLAY1"]
        self.manager.native_message(
            host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
        )
        self.manager._refresh()
        self.assertIsNone(self.manager._panel)
        self.assertIn(("fullscreen", "DISPLAY1", True), self.adapter.events)
        self.manager.pause()
        self.manager.apply(config())
        self.assertFalse(self.manager.hosts)
        self.manager.focus_details()
        self.assertTrue(self.manager.hosts)
        self.assertTrue(self.manager._panel["pinned"])

    def test_fullscreen_blocks_late_hover_click_focus_and_direct_show_until_exit(self):
        self.manager.apply(config(mode="all"))
        self.manager.click("DISPLAY1", "b_0")
        host = self.manager.hosts["DISPLAY1"]
        self.manager.native_message(
            host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
        )
        self.manager._refresh()
        self.assertTrue(host.session._fullscreen)
        created, shows = len(self.windows), list(self.adapter.shows)
        self.manager.hover("DISPLAY2", "b_1")
        self.assertFalse(self.manager._hover_timer.isActive())
        self.manager._pending_hover = ("DISPLAY2", "b_1")
        self.manager._open_hover()
        self.manager.click("DISPLAY2", "b_1")
        self.manager.focus_details()
        self.manager._show_panel(self.manager.hosts["DISPLAY2"], OVERFLOW, False)
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.adapter.shows, shows)
        self.assertEqual(self.settings, [])
        self.manager.native_message(
            host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 0
        )
        self.manager._refresh()
        self.assertFalse(host.session._fullscreen)
        self.manager.click("DISPLAY2", "b_1")
        self.assertEqual(self.manager._panel["item"], "b_1")

    def test_queued_fullscreen_blocks_other_screen_before_notification_refresh(self):
        self.manager.apply(config(mode="all"))
        host = self.manager.hosts["DISPLAY2"]
        self.manager.native_message(
            host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
        )
        created, shows = len(self.windows), list(self.adapter.shows)
        self.manager.hover("DISPLAY1", "b_0")
        self.assertFalse(self.manager._hover_timer.isActive())
        self.manager.click("DISPLAY1", "b_0")
        self.manager.focus_details()
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.adapter.shows, shows)

    def test_fullscreen_session_is_recorded_before_close_callback_can_reopen(self):
        self.manager.apply(config(mode="all"))
        self.manager.click("DISPLAY1", "b_0")
        old_panel = self.manager._panel
        attempts = []

        def close_and_try_open():
            attempts.append(True)
            self.manager.click("DISPLAY2", "b_1")

        old_panel["material_bridge"] = SimpleNamespace(
            close=close_and_try_open, deleteLater=lambda: None
        )
        created = len(self.windows)
        self.manager.native_message(
            old_panel["host"].binding.hwnd,
            self.adapter.callback_message,
            ABN_FULLSCREENAPP,
            1,
        )
        self.manager._refresh()
        self.assertEqual(attempts, [True])
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.windows), created)
        self.assertFalse(old_panel["window"].visible)

    def test_fullscreen_exit_callback_cannot_open_during_another_screen_enter_batch(self):
        self.manager.apply(config(mode="all"))
        first, second = self.manager.hosts["DISPLAY1"], self.manager.hosts["DISPLAY2"]
        first.session.fullscreen(True)
        fullscreen = first.session.fullscreen

        def exit_and_try_open(opened):
            result = fullscreen(opened)
            if not opened:
                self.manager.click("DISPLAY1", "b_0")
            return result

        first.session.fullscreen = exit_and_try_open
        for host, opened in ((first, False), (second, True)):
            self.manager.native_message(
                host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, int(opened)
            )
        created, shows = len(self.windows), list(self.adapter.shows)
        self.manager._refresh()
        self.assertIsNone(self.manager._panel)
        self.assertEqual(len(self.windows), created)
        self.assertEqual(self.adapter.shows, shows)
        self.assertTrue(second.session._fullscreen)
        self.assertFalse(self.manager._dispatching_fullscreen)

    def test_fullscreen_received_during_panel_position_prevents_first_show(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        position = self.adapter.place_panel

        def position_and_notify(*args):
            position(*args)
            self.manager.native_message(
                host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
            )

        self.adapter.place_panel = position_and_notify
        shows = list(self.adapter.shows)
        self.manager.click("DISPLAY1", "b_0")
        self.assertIsNone(self.manager._panel)
        self.assertEqual(self.adapter.shows, shows)
        self.assertFalse(self.windows[-1].visible)
        self.assertTrue(self.windows[-1].deleted)

    def test_fullscreen_received_inside_show_hides_only_that_panel_immediately(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        show = self.adapter.show

        def show_and_notify(binding, *, activate=False):
            show(binding, activate=activate)
            self.manager.native_message(
                host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
            )

        self.adapter.show = show_and_notify
        self.manager._show_panel(host, "b_0", False)
        self.assertIsNone(self.manager._panel)
        self.assertFalse(self.windows[-1].visible)
        self.assertTrue(self.windows[-1].deleted)
        self.assertEqual(self.manager.retired, [])

    def test_fullscreen_received_during_material_prepare_prevents_first_show(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        material = SimpleNamespace(
            close=Mock(), deleteLater=Mock(),
            prepare_before_show=lambda: self.manager.native_message(
                host.binding.hwnd, self.adapter.callback_message, ABN_FULLSCREENAPP, 1
            ),
        )
        shows = list(self.adapter.shows)
        with patch.object(self.manager, "_material_bridge", return_value=material):
            self.manager.click("DISPLAY1", "b_0")
        self.assertIsNone(self.manager._panel)
        self.assertEqual(self.adapter.shows, shows)
        self.assertTrue(self.windows[-1].deleted)
        material.close.assert_called_once()

    def test_failed_detail_material_close_hides_and_retains_exact_record_until_retry(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        panel = self.manager._panel
        binding, window = panel["binding"], panel["window"]
        material = Mock()
        material.close.side_effect = AppBarError("material cleanup pending")
        panel["material_bridge"] = material
        self.manager.close_panel()
        self.assertFalse(window.visible)
        self.assertFalse(window.deleted)
        self.assertEqual(self.manager.retired, [panel])
        self.assertIs(panel["binding"], binding)
        self.assertIs(panel["material_bridge"], material)
        material.deleteLater.assert_not_called()
        self.assertNotIn(("release", "details", "DISPLAY1"), self.adapter.events)
        material.close.side_effect = None
        self.manager._retry_retired()
        self.assertEqual(self.manager.retired, [])
        self.assertTrue(window.deleted)
        self.assertIsNone(panel["binding"])
        material.deleteLater.assert_called_once()
        self.assertEqual(self.adapter.events.count(("release", "details", "DISPLAY1")), 1)

    def test_failed_panel_hide_still_clears_material_but_never_releases_or_deletes(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        panel = self.manager._panel
        material = Mock()
        panel["material_bridge"] = material
        hide = self.adapter.hide

        def fail_panel_hide(binding):
            if binding is panel["binding"]:
                raise AppBarError("own panel did not hide")
            hide(binding)

        self.adapter.hide = fail_panel_hide
        self.manager.close_panel()
        material.close.assert_called_once()
        self.assertEqual(self.manager.retired, [panel])
        self.assertFalse(panel["window"].deleted)
        self.assertNotIn(("release", "details", "DISPLAY1"), self.adapter.events)
        self.adapter.hide = hide
        self.manager._retry_retired()
        self.assertFalse(panel["window"].visible)
        self.assertTrue(panel["window"].deleted)
        self.assertEqual(self.manager.retired, [])
        material.close.assert_called_once()

    def assert_switch_waits_for_retirement(self, replacement=False):
        self.manager.apply(config(mode="selected", screens=["DISPLAY1"]))
        old = self.manager.hosts["DISPLAY1"]
        created = len(self.adapter.created)
        target = "DISPLAY2"
        if replacement:
            self.app._screens[0] = Screen(
                self.a.name(), self.a.physical, dpi=self.a.dpi,
                native_id="DISPLAY3", handle=19,
            )
            target = "DISPLAY3"
        self.adapter.fail_close = True
        try:
            self.manager.apply(config(mode="selected", screens=[target]))
            self.assertEqual(len(self.adapter.created), created)
            self.assertNotIn(target, self.manager.hosts)
            self.assertIn(old, self.manager.retired)
            self.assertTrue(old.session.active)
            self.assertFalse(old.window.deleted)
            self.assertEqual(self.controller.status["state"], "failed")
        finally:
            self.adapter.fail_close = False
        self.manager.apply(config(mode="selected", screens=[target]))
        self.assertTrue(old.window.deleted)
        self.assertFalse(old.session.active)
        self.assertFalse(self.manager.retired)
        self.assertEqual(list(self.manager.hosts), [target])

    def test_selection_switch_waits_for_previous_screen_cleanup(self):
        self.assert_switch_waits_for_retirement()

    def test_new_native_identity_on_same_panel_waits_for_previous_cleanup(self):
        self.assert_switch_waits_for_retirement(replacement=True)

    def test_failed_first_target_cleanup_blocks_later_target_creation(self):
        self.adapter.fail_register = "DISPLAY1"
        self.adapter.fail_close = True
        try:
            self.manager.apply(config(mode="all"))
            self.assertEqual(len(self.adapter.created), 1)
            self.assertTrue(self.manager.retired)
            self.assertNotIn("DISPLAY2", self.manager.hosts)
            self.assertFalse(any(event[:2] == ("register", "DISPLAY2") for event in self.adapter.events))
        finally:
            self.adapter.fail_register = None
            self.adapter.fail_close = False
        self.manager.apply(config(mode="all"))
        self.assertFalse(self.manager.retired)
        self.assertEqual(set(self.manager.hosts), {"DISPLAY1", "DISPLAY2"})

    def test_shell_and_dpi_change_use_current_physical_monitor_and_requested_height(self):
        value = config()
        value["top_bar"]["height"] = 40
        self.manager.apply(value)
        host = self.manager.hosts["DISPLAY1"]
        self.a.dpi = 134
        self.a.physical = PixelRect(-1800, -300, 0, 900)
        self.manager.native_message(host.binding.hwnd, self.adapter.taskbar_message)
        self.manager._refresh()
        self.assertEqual(host.rect, PixelRect(-1800, -300, 0, -244))
        self.assertEqual(host.applied_dpi, 134)
        self.assertEqual(host.applied_monitor, self.a.physical)
        self.assertEqual(host.state.rows[0]["height"], 56 * 96 / 134)
        self.assertIn(("relayout", "DISPLAY1"), self.adapter.events)

    def test_same_name_new_screen_generation_is_recreated_and_old_is_removed_first(self):
        self.manager.apply(config())
        old = self.manager.hosts["DISPLAY1"]
        self.app._screens[0] = Screen("DISPLAY1", PixelRect(0, 0, 2560, 1440), dpi=144)
        self.manager.apply(config())
        new = self.manager.hosts["DISPLAY1"]
        self.assertIsNot(old, new)
        self.assertTrue(old.window.deleted)
        self.assertEqual(new.binding.dpi, 144)
        event_names = [event[0] for event in self.adapter.events]
        self.assertLess(event_names.index("remove"), len(event_names) - 2)

    def test_stable_row_model_updates_without_resetting_delegates(self):
        self.manager.apply(config())
        model = self.manager.hosts["DISPLAY1"].state.rows
        resets, changes = [], []
        model.modelReset.connect(lambda: resets.append(True))
        model.dataChanged.connect(lambda *args: changes.append(args))
        self.controller.rows[0]["value"] = "93%"
        self.manager.update_rows()
        self.assertIs(self.manager.hosts["DISPLAY1"].state.rows, model)
        self.assertEqual(model[0]["value"], "93%")
        self.assertEqual(resets, [])
        self.assertEqual(len(changes), 1)

    def test_host_created_after_shell_broadcast_is_not_registered_twice(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        self.manager.native_message(host.binding.hwnd, self.adapter.taskbar_message)
        self.app._screens[0] = Screen("DISPLAY1", PixelRect(0, 0, 2560, 1440))
        self.manager.apply(config())
        self.manager._refresh()
        self.assertFalse(any(event[0] == "shell" for event in self.adapter.events))

    def test_disabling_still_closes_all_hosts_when_detail_cleanup_is_pending(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        release = self.adapter.release

        def fail_only_panel(binding):
            if binding.window.kind == "details":
                raise AppBarError("Artificial panel cleanup failure")
            release(binding)

        self.adapter.release = fail_only_panel
        self.manager.close_panel()
        self.assertTrue(self.manager.retired)
        self.manager.apply(config(False))
        self.assertFalse(self.manager.hosts)
        self.assertTrue(self.manager.retired)
        self.assertEqual(self.controller.status["state"], "failed")
        self.assertIn(("remove", "DISPLAY1"), self.adapter.events)
        self.adapter.release = release

    def test_pause_cleanup_failure_is_explicit_and_old_notifications_do_not_rebuild_new_host(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        self.manager.native_message(host.binding.hwnd, self.adapter.taskbar_message)
        self.adapter.fail_close = True
        self.manager.pause()
        self.assertEqual(self.controller.status["state"], "failed")
        self.assertTrue(self.controller.status["detail"])
        self.assertFalse(self.manager._shell_pending)
        self.assertEqual(self.manager._notifications, {})
        self.adapter.fail_close = False
        self.manager.resume()
        shell_count = len([event for event in self.adapter.events if event[0] == "shell"])
        self.manager._refresh()
        self.assertEqual(
            len([event for event in self.adapter.events if event[0] == "shell"]), shell_count
        )


    def test_display_styles_two_groups_and_spacing_share_runtime_rows(self):
        value = config()
        value["top_bar"]["spacing"] = 6
        for item, style in zip(value["top_bar"]["items"],
                               ("value", "icon_value", "trend_value", "label_value", "value", "value")):
            item["prefs"]["style"] = style
        value["top_bar"]["items"][0]["prefs"]["placement"] = "left"
        self.manager.apply(value)
        host = self.manager.hosts["DISPLAY1"]
        rows = {row["id"]: row for row in host.state.rows}
        self.assertEqual(host.state.spacing, 6)
        self.assertEqual(rows["b_0"]["x"], host.state.menuRect["x"]+host.state.menuRect["width"]+6)
        self.assertEqual(rows["b_0"]["placement"], "left")
        self.assertTrue(rows["b_0"]["group_start"])
        self.assertTrue(rows["b_1"]["group_start"])
        self.assertFalse(rows["b_2"]["group_start"])
        self.assertAlmostEqual(rows["b_1"]["width"]-rows["b_0"]["width"], 23, delta=1)
        self.assertAlmostEqual(rows["b_2"]["width"]-rows["b_1"]["width"], 19, delta=1)
        self.assertEqual(rows["b_2"]["icon"], "cpu")
        self.assertTrue(rows["b_2"]["trend_available"])

    def test_unavailable_trend_drops_old_line_without_native_calls(self):
        value = config()
        value["top_bar"]["items"][0]["prefs"]["style"] = "trend_value"
        self.controller.rows[0]["history"] = list(range(60))
        self.manager.apply(value)
        state = self.manager.hosts["DISPLAY1"].state
        self.assertEqual(len(state.rows[0]["trend"]), 40)
        native_calls = len(self.adapter.events)
        self.controller.rows[0].update(available=False, value="—", reason="Synthetic provider failed")
        self.manager.update_rows()
        self.assertEqual(state.rows[0]["trend"], [])
        self.assertEqual(state.rows[0]["trend_points"], [])
        self.assertFalse(state.rows[0]["trend_available"])
        self.assertEqual(len(self.adapter.events), native_calls)

    def test_full_value_measurement_does_not_clip_units_at_old_width_cap(self):
        value = config()
        value["top_bar"]["items"] = value["top_bar"]["items"][:1]
        value["top_bar"]["items"][0]["prefs"]["style"] = "value"
        self.controller.rows = self.controller.rows[:1]
        self.controller.rows[0]["value"] = "123456789012345678901234567890.0 watts"
        self.manager.apply(value)
        row = self.manager.hosts["DISPLAY1"].state.rows[0]
        self.assertGreater(row["width"], 150+12)
        self.assertEqual(row["value"], self.controller.rows[0]["value"])

    def test_medium_value_and_normal_label_measurement_at_overflow_boundary(self):
        """Match the shared QML font weights before deciding a prefix fits."""
        measured_fonts = []

        class Metrics:
            def __init__(self, font):
                self.font = QFont(font)
                measured_fonts.append(self.font)

            def horizontalAdvance(self, text):
                return len(text) * (10 if self.font.weight() == QFont.Weight.Medium else 9)

        value = config()
        value["top_bar"]["items"] = value["top_bar"]["items"][:2]
        for item in value["top_bar"]["items"]:
            item["prefs"]["style"] = "value"
        value["top_bar"]["items"][1]["prefs"]["style"] = "label_value"
        self.controller.rows = self.controller.rows[:2]
        for row in self.controller.rows:
            row["value"] = "8888888888"
        self.a.physical = PixelRect(0, 0, 325, 1080)
        with patch("top_bar_runtime.QFontMetricsF", Metrics):
            self.manager.apply(value)
        host = self.manager.hosts["DISPLAY1"]
        self.assertEqual(measured_fonts[0].pixelSize(), 12)
        self.assertEqual(measured_fonts[0].weight(), QFont.Weight.Medium)
        self.assertEqual(measured_fonts[1].pixelSize(), 11)
        self.assertEqual(measured_fonts[1].weight(), QFont.Weight.Normal)
        self.assertEqual([row["id"] for row in host.state.rows], ["b_0"])
        self.assertEqual(host.overflow_ids, ("b_1",))
        self.assertEqual(host.state.rows[0]["width"], 112)

    def test_numeric_updates_preserve_plan_and_static_state_but_publish_latest(self):
        self.manager.apply(config(mode="all"))
        signals = []
        for host in self.manager.hosts.values():
            host.state.changed.connect(lambda: signals.append("static"))
            host.state._row_model.modelReset.connect(lambda: signals.append("reset"))
        with patch("top_bar_runtime.plan_top_bar", side_effect=AssertionError("unchanged layout")), \
                patch("top_bar_runtime.palette", side_effect=AssertionError("unchanged palette")):
            for step in range(20):
                for row in self.controller.rows:
                    row["value"] = f"{40 + step}%"
                self.manager.update_rows()
        self.assertEqual(signals, [])
        for host in self.manager.hosts.values():
            self.assertEqual(host.state.rows[0]["value"], "59%")

    def test_contiguous_data_changes_emit_one_range_not_one_signal_per_metric(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        signals = []
        host.state._row_model.dataChanged.connect(lambda first, last, roles: signals.append((first.row(), last.row())))
        for row in self.controller.rows:
            row["value"] = "80%"
        self.manager.update_rows()
        self.assertEqual(signals, [(0, 5)])
        self.assertEqual([row["value"] for row in host.state.rows], ["80%"] * 6)

    def test_real_width_growth_invalidates_geometry_without_recreating_host(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        prior = host.state.rows[0]["width"]
        from top_bar_runtime import plan_top_bar
        with patch("top_bar_runtime.plan_top_bar", wraps=plan_top_bar) as planner:
            self.controller.rows[0]["value"] = "12345678901234567890 percent"
            self.manager.update_rows()
            self.assertEqual(planner.call_count, 1)
        self.assertGreater(host.state.rows[0]["width"], prior)
        self.assertIs(self.manager.hosts["DISPLAY1"], host)
        self.assertEqual(len([event for event in self.adapter.events if event[0] == "register"]), 1)

    def test_new_style_measurement_fonts_and_geometry_match_render_contract(self):
        fonts = []

        class Metrics:
            def __init__(self, font):
                fonts.append((font.pixelSize(), font.weight()))

            def horizontalAdvance(self, text):
                return len(text) * 2

        value = config()
        styles = ["bar_value", "ring_value", "graph", "stacked"]
        value["top_bar"]["items"] = value["top_bar"]["items"][:4]
        self.controller.rows = self.controller.rows[:4]
        for item, style in zip(value["top_bar"]["items"], styles):
            item["prefs"]["style"] = style
        with patch("top_bar_runtime.QFontMetricsF", Metrics):
            self.manager.apply(value)
        by_id = {row["id"]: row for row in self.manager.hosts["DISPLAY1"].state.rows}
        self.assertEqual([by_id[f"b_{index}"]["width"] for index in range(4)], [54, 46, 56, 32])
        self.assertEqual(set(fonts), {(12, QFont.Weight.Medium), (9, QFont.Weight.Medium),
                                     (11, QFont.Weight.Medium), (9, QFont.Weight.Normal)})

    def test_font_and_numeric_text_caches_are_bounded_and_dpi_specific(self):
        self.manager.apply(config())
        with patch("top_bar_runtime.QFontMetricsF", side_effect=AssertionError("cached metrics")):
            for index in range(2100):
                self.manager._measure("Segoe UI Variable", 12, QFont.Weight.Medium, str(index), 96, tabular=True)
        self.assertLessEqual(len(self.manager._text_widths), 2048)
        self.manager._measure("Segoe UI Variable", 12, QFont.Weight.Medium, "123", 144)
        self.assertTrue(any(key[-1] == 144 for key in self.manager._font_metrics))

    def test_detail_projection_is_lazy_and_related_updates_do_not_need_base_change(self):
        calls = []
        temperature = ["65°C"]

        def detail(identifier):
            calls.append(identifier)
            result = copy.deepcopy(self.controller.rows[0])
            result["related"][0]["value"] = temperature[0]
            return result

        self.controller.topBarDetailRow = detail
        self.manager.apply(config())
        for step in range(5):
            self.controller.rows[0]["value"] = f"{30 + step}%"
            self.manager.update_rows()
        self.assertEqual(calls, [])
        self.manager.click("DISPLAY1", "b_0")
        self.assertEqual(calls, ["b_0"])
        host = self.manager.hosts["DISPLAY1"]
        notifications = []
        host.state.detailChanged.connect(lambda: notifications.append(True))
        self.manager.update_rows()
        self.assertEqual(notifications, [])
        temperature[0] = "66°C"
        self.manager.update_rows()
        self.assertEqual(host.state.detail["related"][0]["value"], "66°C")
        self.assertEqual(len(notifications), 1)
        self.manager.close_panel()
        count = len(calls)
        self.manager.update_rows()
        self.assertEqual(len(calls), count)

    def test_projected_controller_rows_are_not_formatted_twice(self):
        from top_bar_layout import present_metric
        self.controller.rows = [present_metric(row) for row in self.controller.rows]
        with patch("top_bar_runtime.present_metric", side_effect=AssertionError("double projection")):
            self.manager.apply(config())
            self.controller.rows[0]["value"] = "71%"
            self.manager.update_rows()
        self.assertEqual(self.manager.hosts["DISPLAY1"].state.rows[0]["value"], "71%")

    def test_live_move_forwards_only_valid_ids_and_reports_controller_refusal(self):
        self.manager.apply(config())
        calls = []
        self.controller.placeLiveTopBarMetric = lambda *args: calls.append(args) or True
        state = self.manager.hosts["DISPLAY1"].state
        self.assertTrue(state.moveMetric("b_0", "b_2", "left"))
        self.assertEqual(calls, [("b_0", "b_2", "left")])
        self.assertFalse(state.moveMetric("missing", "b_2", "left"))
        self.assertFalse(state.moveMetric("b_0", "missing", "left"))
        self.assertFalse(state.moveMetric("b_0", "", "center"))
        self.controller.placeLiveTopBarMetric = lambda *unused: False
        self.assertFalse(state.moveMetric("b_0", "", "right"))
        self.assertEqual(config()["top_bar"]["items"][0]["id"], "b_0")

    def test_bar_appearance_override_is_local_and_transparency_does_not_recompose(self):
        value = config()
        value["top_bar"]["appearance"] = dict(follow_global=False, skin="frost", glass_transparency=23)
        self.manager.apply(value)
        host = self.manager.hosts["DISPLAY1"]
        self.assertEqual(host.state.config["skin"], "frost")
        self.assertEqual(host.state.config["glass_transparency"], 23)
        self.assertEqual(value["skin"], "glass")
        events = []
        host.material_bridge = SimpleNamespace(request=events.append, close=lambda: None)
        value["top_bar"]["appearance"]["glass_transparency"] = 80
        self.manager.apply(value)
        self.assertEqual(events, [])
        value["theme"] = "dark"
        self.manager.apply(value)
        self.assertEqual(events, ["preference_changed"])

    def test_material_bridge_is_not_constructed_for_injected_or_headless_clients(self):
        with patch("settings_material_bridge.SettingsMaterialBridge", side_effect=AssertionError("native bridge")):
            self.manager.apply(config())
            self.manager.click("DISPLAY1", "b_0")
        self.assertIsNone(self.manager.hosts["DISPLAY1"].material_bridge)
        self.assertIsNone(self.manager._panel["material_bridge"])

    def test_material_bridge_attaches_before_own_hwnd_prepare_and_closes_before_release(self):
        events = []
        old_prepare, old_release = self.adapter.prepare, self.adapter.release
        self.adapter.prepare = lambda *args: events.append("prepare") or old_prepare(*args)
        self.adapter.release = lambda *args: events.append("release") or old_release(*args)

        def attach(*unused):
            events.append("bridge-start")
            return SimpleNamespace(close=lambda: events.append("bridge-close"), request=lambda reason: None)

        with patch.object(self.manager, "_material_bridge", attach):
            self.manager.apply(config())
            self.manager.click("DISPLAY1", "b_0")
        self.assertEqual(events, ["bridge-start", "prepare", "bridge-start", "prepare"])
        self.manager.close()
        self.assertEqual(events[4:], ["bridge-close", "release", "bridge-close", "release"])

    def test_native_material_composition_uses_local_style_and_explicit_policy_only(self):
        bridges = []

        class Bridge:
            def __init__(self, window, parent, **callbacks):
                self.callbacks = callbacks
                self.started = False
                bridges.append(self)

            def start(self):
                self.started = True

        self.manager.apply(config())
        state = self.manager.hosts["DISPLAY1"].state
        state._config = dict(skin="frost", theme="dark", glass_transparency=77)
        self.manager._injected = False
        self.runtime.headless = False
        self.app.platformName = lambda: "windows"
        validate = Mock()
        self.adapter.backend = SimpleNamespace(validate=validate)
        policy = dict(state="allowed", reason="fake-explicit-policy")
        backend = Mock()
        backend.apply.side_effect = lambda handle, enabled, policy: dict(
            ok=True, coating_allowed=policy["state"] == "allowed",
            blur_configured=enabled and policy["state"] == "allowed")
        backend.clear.return_value = dict(ok=True, cleanup_complete=True)
        with patch("settings_material_bridge.SettingsMaterialBridge", Bridge), \
                patch("native_widget_material.WidgetBlurBackend", return_value=backend):
            material = self.manager._material_bridge(self.windows[0], state)
            bridge = material.bridge
            self.assertTrue(bridge.started)
            self.assertEqual(bridge.callbacks["backend"], "system-blur")
            self.assertIs(bridge.callbacks["wait_for_first_frame"], True)
            self.assertFalse(state.coatingTranslucent)
            material.bind(self.manager.hosts["DISPLAY1"].binding)
            handle = material.binding.hwnd
            report = bridge.callbacks["compose_once"](handle, policy)
            backend.apply.assert_called_once_with(handle, enabled=True, policy=policy)
            self.assertTrue(report["coating_allowed"])
            self.assertTrue(report["coating_translucent"])
            self.assertFalse(report["compositing_verified"])
            state._config["skin"] = "card"
            bridge.callbacks["compose_once"](handle, policy)
            self.assertFalse(backend.apply.call_args.kwargs["enabled"])
            bridge.callbacks["release_surface"](handle)
            backend.clear.assert_called_once_with(handle)
            self.assertEqual(validate.call_count, 3)
        # The live Windows path was injected, not executed. Restore fake runtime
        # identity before test cleanup, so no native event filter is touched.
        self.manager._injected = True
        self.runtime.headless = True
        self.assertEqual(len(bridges), 1)

    def test_status_metadata_reports_own_host_geometry_without_claiming_visual_pass(self):
        self.manager.apply(config(mode="all"))
        report = self.controller.status
        self.assertFalse(report["native_blur_verified"])
        self.assertEqual(len(report["hosts"]), 2)
        for host in report["hosts"]:
            self.assertTrue(host["visible"])
            self.assertGreater(host["width"], 0)
            self.assertEqual(host["height"], 32)
            self.assertGreater(host["visible_metric_count"], 0)
            self.assertEqual(host["material_lifecycle"], {})

    def test_material_bridge_object_is_released_once_even_when_host_cleanup_retries(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        events = []
        host.material_bridge = SimpleNamespace(close=lambda: events.append("close"),
                                               deleteLater=lambda: events.append("delete"))
        self.adapter.fail_close = True
        self.manager._drop("DISPLAY1")
        self.assertEqual(events, ["close", "delete"])
        self.assertIsNone(host.material_bridge)
        self.adapter.fail_close = False
        self.manager._retry_retired()
        self.assertEqual(events, ["close", "delete"])
        self.assertEqual(self.manager.retired, [])

    def test_incomplete_material_cleanup_blocks_replacement_and_preserves_owned_record(self):
        self.manager.apply(config())
        host = self.manager.hosts["DISPLAY1"]
        material = Mock()
        material.close.side_effect = AppBarError("material cleanup is incomplete")
        host.material_bridge = material
        self.manager.apply(config(mode="selected", screens=["DISPLAY2"]))
        self.assertFalse(self.manager.hosts)
        self.assertEqual(self.manager.retired, [host])
        self.assertFalse(host.window.deleted)
        self.assertFalse(any(event[:2] == ("register", "DISPLAY2") for event in self.adapter.events))
        material.close.side_effect = None
        self.manager.apply(config(mode="selected", screens=["DISPLAY2"]))
        self.assertEqual(list(self.manager.hosts), ["DISPLAY2"])
        self.assertTrue(host.window.deleted)

    def test_partial_detail_prepare_retains_one_record_without_reusing_deleted_bridge(self):
        self.manager.apply(config())
        events = []
        bridge = SimpleNamespace(close=lambda: events.append("close"),
                                 deleteLater=lambda: events.append("delete"))
        old_prepare, old_release = self.adapter.prepare, self.adapter.release

        def prepare(window, screen):
            binding = old_prepare(window, screen)
            if window.kind == "details":
                raise WindowPreparationError("preparation cleanup failed", binding)
            return binding

        self.adapter.prepare = prepare
        self.adapter.release = lambda binding: (_ for _ in ()).throw(AppBarError("retry release"))
        with patch.object(self.manager, "_material_bridge", return_value=bridge):
            self.manager.click("DISPLAY1", "b_0")
        self.assertEqual(events, ["close", "delete"])
        self.assertEqual(len(self.manager.retired), 1)
        self.assertIsNone(self.manager.retired[0]["material_bridge"])
        self.adapter.release = old_release
        self.manager._retry_retired()
        self.assertEqual(events, ["close", "delete"])
        self.assertEqual(self.manager.retired, [])

    def test_detail_mask_matches_sixteen_dip_corner_and_reapplies_only_on_size_change(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        panel = self.manager._panel
        panel["window"].setMask = Mock()
        from widget_material_geometry import rounded_mask
        with patch.object(self.manager, "_native_windows", return_value=True), \
                patch("widget_material_geometry.rounded_mask", wraps=rounded_mask) as shape:
            self.manager._position_panel()
            self.manager._position_panel()
            shape.assert_called_once_with(((0, 0, 320, 240, 16),))
            mask = panel["window"].setMask.call_args.args[0]
            self.assertFalse(mask.contains(QPoint(0, 0)))
            self.assertTrue(mask.contains(QPoint(160, 120)))
            panel["window"]._height = 160
            self.manager._queue_panel_geometry()
            self.manager._queue_panel_geometry()
            QTest.qWait(5)
            self.assertEqual(shape.call_count, 2)
            shape.assert_called_with(((0, 0, 320, 160, 16),))
        self.manager._queue_panel_geometry()
        self.manager.close_panel()
        self.assertFalse(self.manager._panel_geometry_timer.isActive())

    def test_injected_detail_windows_never_receive_native_masks(self):
        self.manager.apply(config())
        self.manager.click("DISPLAY1", "b_0")
        panel = self.manager._panel
        panel["window"].setMask = Mock(side_effect=AssertionError("native mask"))
        self.manager._position_panel()
        panel["window"].setMask.assert_not_called()


    def test_rejected_live_move_exposes_reason_then_success_clears_feedback(self):
        self.manager.apply(config())
        state = self.manager.hosts["DISPLAY1"].state
        self.controller.status = "Apply pending bar changes before dragging the live bar."
        self.controller.placeLiveTopBarMetric = lambda *args: False
        self.assertFalse(state.moveMetric("b_0", "b_1", "right"))
        self.assertEqual(state.operationMessage, self.controller.status)
        self.assertTrue(state._operation_timer.isActive())
        self.controller.placeLiveTopBarMetric = lambda *args: True
        self.assertTrue(state.moveMetric("b_0", "b_1", "right"))
        self.assertEqual(state.operationMessage, "")
        self.assertFalse(state._operation_timer.isActive())

    def test_split_units_and_percentage_reserve_keep_positions_stable(self):
        for row in self.controller.rows:
            row.update(number_text="9.00", unit_text="%", number_reserve="100.00", value="9.00 %")
        self.manager.apply(config())
        state = self.manager.hosts["DISPLAY1"].state
        before = [(row["x"], row["width"]) for row in state.rows]
        for row in self.controller.rows:
            row.update(number_text="100.00", value="100.00 %")
        self.manager.update_rows()
        self.assertEqual(before, [(row["x"], row["width"]) for row in state.rows])
        self.assertEqual(state.rows[0]["unit_text"], "%")
        self.assertEqual(state.rows[0]["value"], "100.00 %")


class AdapterBoundaryTests(unittest.TestCase):
    """Exercise the actual ctypes wrapper using only injected Python functions."""

    def setUp(self):
        self.adapter = WindowsTopBarAdapter()
        self.properties, self.released, self.validated = {}, [], []
        self.native_pid, self.native_thread = os.getpid(), 91
        self.native_name, self.foreground = r"\\.\DISPLAY1", 999
        self.visible, self.fail_remove, self.monitor = False, False, 18
        self.native_dpi = 144
        self.window = SimpleNamespace(
            setScreen=lambda screen: None,
            setPosition=lambda *args: None,
            width=lambda: 320,
            height=lambda: 200,
            winId=lambda: 123,
            show=lambda: setattr(self, "visible", True),
            hide=lambda: setattr(self, "visible", False),
            requestActivate=lambda: setattr(self, "foreground", 123),
        )
        self.screen = Screen("TL140ADXP02-0", PixelRect(-1920, -200, 0, 880))

        def owner(hwnd, output):
            self.assertEqual(hwnd, 123)
            output._obj.value = self.native_pid
            return self.native_thread

        def info(handle, output):
            self.assertEqual(handle, self.screen.native_handle)
            result = output._obj
            self.assertEqual(result.cbSize, c.sizeof(MonitorInfo))
            result.szDevice = self.native_name
            for key, value in zip(
                ("left", "top", "right", "bottom"),
                (
                    self.screen.physical.left,
                    self.screen.physical.top,
                    self.screen.physical.right,
                    self.screen.physical.bottom,
                ),
            ):
                setattr(result.rcMonitor, key, value)
                setattr(result.rcWork, key, value)
            return 1

        def set_prop(hwnd, name, value):
            self.assertEqual(name, WINDOW_GENERATION_PROPERTY)
            self.properties[hwnd] = value.value
            return 1

        def remove_prop(hwnd, name):
            self.assertEqual(name, WINDOW_GENERATION_PROPERTY)
            return 0 if self.fail_remove else self.properties.pop(hwnd, 0)

        def retain(hwnd, generation):
            return SimpleNamespace(hwnd=hwnd, generation=generation)

        self.adapter.backend = SimpleNamespace(
            retain_window=retain,
            validate=lambda token: self.validated.append(token),
            release_window=lambda token: self.released.append(token),
            hide=lambda token: setattr(self, "visible", False),
        )
        self.adapter._functions = dict(
            owner=owner,
            thread=lambda: 91,
            get_prop=lambda hwnd, name: self.properties.get(hwnd, 0),
            set_prop=set_prop,
            remove_prop=remove_prop,
            monitor=lambda hwnd, flags: self.monitor,
            monitor_info=info,
            dpi=lambda hwnd: self.native_dpi,
            foreground=lambda: self.foreground,
            visible=lambda hwnd: self.visible,
        )

    def test_physical_monitor_abi_generation_and_release_are_explicit(self):
        self.assertEqual(c.sizeof(MonitorInfo), 104)
        self.assertEqual(MonitorInfo.szDevice.offset, 40)
        with patch("ctypes.WinDLL", side_effect=AssertionError("No native loading")):
            binding = self.adapter.prepare(self.window, self.screen)
            self.assertEqual(binding.monitor, self.screen.physical)
            self.assertEqual(binding.dpi, 144)
            self.assertEqual(binding.screen_name, r"\\.\DISPLAY1")
            self.assertEqual(binding.monitor_handle, 18)
            self.assertIs(binding.screen, self.screen)
            self.assertGreater(binding.token.generation, 0)
            self.adapter.show(binding)
            self.assertEqual(self.foreground, 999)
            self.adapter.hide(binding)
            self.adapter.release(binding)
        self.assertEqual(self.properties, {})
        self.assertEqual(self.released, [binding.token])

    def test_screen_identity_uses_qt_handle_and_native_device_not_friendly_name(self):
        with (
            patch("ctypes.WinDLL", side_effect=AssertionError("No native loading")),
            patch.object(
                self.adapter,
                "_api",
                side_effect=AssertionError("Identity must not initialize window APIs"),
            ),
        ):
            identity = self.adapter.screen_identity(self.screen)
        self.assertEqual(identity, ScreenIdentity(r"\\.\DISPLAY1", 18, "TL140ADXP02-0"))
        self.assertEqual(self.properties, {})
        self.assertFalse(self.validated)

    def test_missing_interface_or_handle_fails_before_touching_any_window(self):
        touches = []
        self.window.setScreen = lambda screen: touches.append("screen")
        self.window.winId = lambda: touches.append("hwnd") or 123
        for screen in (
            SimpleNamespace(name=lambda: "same"),
            SimpleNamespace(name=lambda: "same", nativeInterface=lambda: None),
            Screen("same", self.screen.physical, handle=0),
        ):
            with (
                self.subTest(screen=screen),
                patch("ctypes.WinDLL", side_effect=AssertionError("No native loading")),
            ):
                with self.assertRaisesRegex(AppBarError, "native interface|monitor handle"):
                    self.adapter.prepare(self.window, screen)
        self.assertEqual(touches, [])
        self.assertEqual(self.properties, {})

    def test_snapshot_rechecks_live_qt_handle_and_rejects_wrong_device(self):
        binding = self.adapter.prepare(self.window, self.screen)
        self.screen.native_handle = 19
        self.monitor = 19
        self.adapter.snapshot(binding)
        self.assertEqual(binding.monitor_handle, 19)
        self.monitor = 18
        with self.assertRaisesRegex(AppBarError, "HMONITOR"):
            self.adapter.snapshot(binding)
        self.monitor = 19
        self.native_name = r"\\.\DISPLAY2"
        with self.assertRaisesRegex(AppBarError, "device identity changed"):
            self.adapter.snapshot(binding)

    def test_negative_physical_bounds_and_window_dpi_do_not_use_geometry_matching(self):
        self.screen.physical = PixelRect(-3000, -240, 0, 1560)
        self.screen.dpi = 144
        self.native_dpi = 192
        binding = self.adapter.prepare(self.window, self.screen)
        self.assertEqual(binding.monitor, PixelRect(-3000, -240, 0, 1560))
        self.assertEqual(binding.dpi, 192)
        self.assertEqual(binding.monitor_handle, self.monitor)

    def test_screen_inventory_retains_desktop_id_and_adds_native_id_lazily(self):
        import ast

        path = Path(__file__).resolve().parents[1] / "native_runtime.py"
        runtime = next(
            node
            for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef) and node.name == "Runtime"
        )
        method = next(
            node
            for node in runtime.body
            if isinstance(node, ast.FunctionDef) and node.name == "screen_inventory"
        )
        namespace = {}
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                str(path),
                "exec",
            ),
            namespace,
        )
        fake = SimpleNamespace(
            headless=False,
            app=SimpleNamespace(
                primaryScreen=lambda: self.screen,
                screens=lambda: [self.screen],
                platformName=lambda: "windows",
            ),
            top_bar=SimpleNamespace(adapter=self.adapter),
        )
        with patch("ctypes.WinDLL", side_effect=AssertionError("No native loading")):
            rows = namespace["screen_inventory"](fake)
        self.assertEqual(rows[0]["id"], "TL140ADXP02-0")
        self.assertEqual(rows[0]["native_id"], r"\\.\DISPLAY1")
        fake.headless = True
        with patch.object(
            self.adapter, "screen_identity", side_effect=AssertionError("Headless must stay lazy")
        ):
            rows = namespace["screen_inventory"](fake)
        self.assertEqual(rows[0]["native_id"], "")

    def test_foreign_pid_and_wrong_thread_fail_before_property_or_monitor_calls(self):
        for field, value in (("native_pid", os.getpid() + 1), ("native_thread", 90)):
            old = getattr(self, field)
            setattr(self, field, value)
            with self.assertRaises(AppBarError):
                self.adapter.prepare(self.window, self.screen)
            setattr(self, field, old)
            self.assertEqual(self.properties, {})
            self.assertEqual(self.released, [])

    def test_missing_and_wrong_monitor_remove_only_the_own_generation(self):
        for attribute, value in (("monitor", 0), ("monitor", 19)):
            old = getattr(self, attribute)
            setattr(self, attribute, value)
            with self.assertRaises(AppBarError):
                self.adapter.prepare(self.window, self.screen)
            setattr(self, attribute, old)
            self.assertEqual(self.properties, {})
        self.assertEqual(len(self.released), 2)

    def test_unconfirmed_prepare_cleanup_preserves_the_actual_owned_window(self):
        self.monitor, self.fail_remove = 0, True
        with self.assertRaises(WindowPreparationError) as caught:
            self.adapter.prepare(self.window, self.screen)
        self.assertIs(caught.exception.binding.window, self.window)
        self.assertIn(123, self.properties)
        self.assertEqual(self.released, [])

    def test_nonactivating_show_failure_is_not_reported_as_success(self):
        binding = self.adapter.prepare(self.window, self.screen)
        self.window.show = lambda: setattr(self, "foreground", 123)
        self.visible = True
        with self.assertRaisesRegex(AppBarError, "took focus"):
            self.adapter.show(binding)
        self.assertFalse(self.visible)
        self.foreground = 999
        self.window.show = lambda: None
        with self.assertRaisesRegex(AppBarError, "visible"):
            self.adapter.show(binding)


class QmlAdapter(Adapter):
    """Real offscreen QQuickWindows, fake registration and physical monitor data."""

    def prepare(self, window, screen):
        window.kind = "bar" if window.objectName() == "topBarWindow" else "details"
        window.fixture_screen = screen
        binding = Binding(
            window,
            SimpleNamespace(hwnd=100 + len(self.created)),
            self.screen_identity(screen).native_id,
            screen.physical,
            PixelRect(0, 32, screen.physical.right, screen.physical.bottom - 40),
            screen.dpi,
        )
        self.created.append(binding)
        self.events.append(("prepare", window.kind, screen.name()))
        return binding

    def snapshot(self, binding):
        binding.monitor, binding.dpi = (
            binding.window.fixture_screen.physical,
            binding.window.fixture_screen.dpi,
        )
        return binding.monitor, binding.work, binding.dpi

    def show(self, binding, *, activate=False):
        window = binding.window
        if window.kind == "bar":
            self.assert_active(binding)
            window.resize(window._width, window._height)
        window.show()  # Offscreen Qt only, never an OS AppBar or desktop window.
        if activate:
            window.requestActivate()
        self.shows.append((window.kind, activate))

    @staticmethod
    def assert_active(binding):
        assert binding.session.active

    def hide(self, binding):
        binding.window.hide()
        self.events.append(("hide", binding.window.kind, binding.screen_name))

    def place_panel(self, binding, anchor, work, dpi):
        binding.window.setPosition(20, 50)
        super().place_panel(binding, anchor, work, dpi)


class QmlTopBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        # Windows offscreen Qt can have an empty font database. Read fonts into
        # this process only; no installation or user settings are changed.
        directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            path = directory / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.controller, self.settings, self.warnings = Controller(), [], []
        self.screen = Screen("DISPLAY1", PixelRect(0, 0, 1280, 900))
        self.engine = QQmlEngine()
        self.engine.warnings.connect(
            lambda values: self.warnings.extend(v.toString() for v in values)
        )
        self.runtime = SimpleNamespace(
            app=Application([self.screen]),
            controller=self.controller,
            headless=True,
            show_settings=self.settings.append,
            engine=self.engine,
        )
        self.adapter = QmlAdapter()
        self.manager = TopBarManager(self.runtime, adapter=self.adapter)
        self.manager.apply(config())
        self.host = self.manager.hosts.get("DISPLAY1")
        self.assertIsNotNone(self.host, self.controller.status)
        QTest.qWait(25)

    def tearDown(self):
        self.manager.close()
        QTest.qWait(1)
        self.assertEqual(self.warnings, [])

    def metric(self, item="b_0"):
        return self.visual(self.host.window, "topBarMetric_" + item)

    @staticmethod
    def visual(window, name):
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        return None

    def point(self, item="b_0"):
        metric = self.metric(item)
        self.assertIsNotNone(metric)
        return QPoint(
            round(metric.x() + metric.width() / 2), round(metric.y() + metric.height() / 2)
        )

    def hover_until_open(self, point):
        # Give the real offscreen window a definite enter edge. Qt's coarse
        # 350 ms timer can run late under suite load; wait for the UI result,
        # while the isolated timer tests retain the exact debounce contract.
        QTest.mouseMove(self.host.window, QPoint(-10, -10))
        QTest.mouseMove(self.host.window, point)
        for _ in range(100):
            if self.manager._panel is not None:
                break
            QTest.qWait(10)
        self.assertIsNotNone(self.manager._panel)

    def test_real_hover_stays_stable_under_repeated_readings_and_does_not_activate(self):
        metric = self.metric()
        QTest.mouseMove(self.host.window, self.point())
        for index in range(5):
            self.controller.rows[0]["value"] = f"{70 + index}%"
            self.manager.update_rows()
            QTest.qWait(85)
            self.assertIs(self.metric(), metric, "Live readings rebuilt a hover delegate")
        self.assertIsNotNone(self.manager._panel)
        self.assertFalse(self.manager._panel["pinned"])
        self.assertEqual(self.host.state.detail["value"], "74%")
        self.assertEqual(self.adapter.shows[-1], ("details", False))
        self.assertTrue(
            self.manager._panel["window"].flags() & Qt.WindowType.WindowDoesNotAcceptFocus
        )

    def test_split_units_are_visible_aligned_and_inside_measured_hit_regions(self):
        value = config()
        styles = ["icon_value", "label_value", "value", "trend_value", "bar_value", "stacked"]
        self.screen.physical = PixelRect(0, 0, 1920, 900)
        for item, style, row in zip(value["top_bar"]["items"], styles, self.controller.rows):
            item["prefs"]["style"] = style
            row.update(number_text="1234.5", unit_text="MB/s", number_reserve="999.9", value="1234.5 MB/s")
        self.manager.apply(value)
        self.host = self.manager.hosts["DISPLAY1"]
        QTest.qWait(30)
        for row in self.host.state.rows:
            item = self.metric(row["id"])
            number = item.findChild(QObject, "topBarContentValue")
            unit = item.findChild(QObject, "topBarContentUnit")
            self.assertEqual((number.property("text"), unit.property("text")), ("1234.5", "MB/s"))
            self.assertTrue(unit.isVisible())
            self.assertAlmostEqual(number.y() + number.property("baselineOffset"),
                                   unit.y() + unit.property("baselineOffset"), delta=0.01)
            end = unit.mapToItem(item, QPointF(unit.width(), 0)).x()
            self.assertLessEqual(end, item.width() - 5)
            self.assertGreaterEqual(number.mapToItem(item, QPointF(0, 0)).y(), 0)

    def test_real_click_pin_close_and_edit_use_actual_qml_events(self):
        QTest.mouseClick(
            self.host.window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self.point(),
        )
        QTest.qWait(15)
        self.assertTrue(self.manager._panel["pinned"])
        window = self.manager._panel["window"]
        self.assertFalse(window.flags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.assertEqual(window.findChild(QObject, "topBarDetailValue").property("text"), "20%")
        close = window.findChild(QObject, "topBarDetailsClose")
        local = close.mapToScene(close.boundingRect().center())
        QTest.mouseClick(
            window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local.toPoint()
        )
        QTest.qWait(5)
        self.assertIsNone(self.manager._panel)
        QTest.mouseClick(
            self.host.window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self.point(),
        )
        QTest.qWait(15)
        window = self.manager._panel["window"]
        edit = window.findChild(QObject, "topBarDetailsEdit")
        local = edit.mapToScene(edit.boundingRect().center())
        QTest.mouseClick(
            window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local.toPoint()
        )
        QTest.qWait(5)
        self.assertEqual(self.settings, ["__top_bar__"])
        self.assertIsNone(self.manager._panel)

    def test_actual_bar_to_details_pointer_region_and_keyboard_escape(self):
        self.hover_until_open(self.point())
        window = self.manager._panel["window"]
        QTest.mouseMove(self.host.window, QPoint(-10, -10))
        QTest.qWait(90)
        # The shared offscreen cursor may already be inside the newly shown
        # panel after another test. Establish this window's actual enter edge.
        QTest.mouseMove(window, QPoint(-10, -10))
        QTest.mouseMove(window, QPoint(100, 80))
        QTest.qWait(200)
        self.assertIsNotNone(self.manager._panel)
        QTest.mouseMove(window, QPoint(-10, -10))
        QTest.qWait(280)
        self.assertIsNone(self.manager._panel)
        QTest.mouseClick(
            self.host.window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            self.point(),
        )
        QTest.qWait(20)
        window = self.manager._panel["window"]
        self.assertTrue(window.isActive())
        QTest.keyClick(window, Qt.Key.Key_Escape)
        QTest.qWait(5)
        self.assertIsNone(self.manager._panel)

    def test_right_click_opens_owned_menu_and_settings_action(self):
        with patch("top_bar_runtime.QCursor.pos", return_value=QPoint(40, 40)):
            QTest.mouseClick(
                self.host.window,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
                self.point(),
            )
        QTest.qWait(5)
        menu = self.manager._menu
        self.assertIsNotNone(menu)
        self.assertEqual(len([action for action in menu.actions() if not action.isSeparator()]), 3)
        self.assertEqual(len([action for action in menu.actions() if action.isSeparator()]), 1)
        QTest.keyClick(menu, Qt.Key.Key_Down)
        QTest.keyClick(menu, Qt.Key.Key_Return)
        QTest.qWait(5)
        self.assertEqual(self.settings, ["__top_bar__"])

    def test_real_overflow_has_scrollable_list_and_click_pins_selected_hidden_metric(self):
        self.controller.rows = rows(64)
        self.manager.update_rows()
        QTest.qWait(15)
        overflow = self.host.window.findChild(QObject, "topBarOverflow")
        point = overflow.mapToScene(overflow.boundingRect().center()).toPoint()
        self.hover_until_open(point)
        panel = self.manager._panel
        self.assertIsNotNone(panel)
        self.assertFalse(panel["pinned"])
        window = panel["window"]
        listing = window.findChild(QObject, "topBarOverflowList")
        self.assertEqual(listing.property("count"), self.host.state.overflowCount)
        self.assertGreater(listing.property("contentHeight"), listing.property("height"))
        item = self.host.overflow_ids[0]
        row = self.visual(window, "topBarOverflowRow_" + item)
        self.assertIsNotNone(row)
        point = row.mapToScene(row.boundingRect().center()).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        QTest.qWait(15)
        self.assertEqual(self.manager._panel["item"], item)
        self.assertTrue(self.manager._panel["pinned"])

    def test_overflow_scrolling_is_preserved_during_live_reading_updates(self):
        self.controller.rows = rows(64)
        self.manager.update_rows()
        self.manager.click("DISPLAY1", OVERFLOW)
        QTest.qWait(20)
        window = self.manager._panel["window"]
        listing = window.findChild(QObject, "topBarOverflowList")
        point = listing.mapToScene(listing.boundingRect().center())
        wheel = QWheelEvent(
            point,
            QPointF(point),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(window, wheel)
        QTest.qWait(80)
        QMetaObject.invokeMethod(listing, "cancelFlick")
        scroll = listing.property("contentY")
        self.assertGreater(scroll, 0)
        for index in range(4):
            self.controller.rows[20]["value"] = f"{80 + index}%"
            self.manager.update_rows()
            QTest.qWait(15)
            self.assertEqual(listing.property("contentY"), scroll)


if __name__ == "__main__":
    unittest.main()
