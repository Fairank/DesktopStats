"""Fullscreen avoidance contracts. Every native boundary is fake."""

import ctypes as c
import dataclasses
import importlib
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import fullscreen_guard as guard_module
from fullscreen_guard import FullscreenGuard, WindowState
from top_bar_layout import PixelRect

A = PixelRect(0, 0, 2560, 1440)
B = PixelRect(-1920, -200, 0, 880)
MONITORS = {"native-A": A, "native-B": B}


class FakeApi:
    def __init__(self):
        self.active = 1
        self.windows = {1: WindowState(1, A, A, identity=(123, 4, "Game", 0))}
        self.callback = None
        self.installs = []
        self.uninstalls = []
        self.reads = []
        self.foreground_error = None
        self.window_error = None
        self.install_error = False
        self.failed_unhooks = set()
        self.released = False
        self.own = set()

    def install(self, callback):
        if self.install_error:
            raise OSError("hook error")
        self.callback = callback
        self.installs = list(range(100, 100 + len(guard_module.EVENTS)))
        return self.installs

    def uninstall(self, handle):
        self.uninstalls.append((handle, threading.get_ident()))
        return handle not in self.failed_unhooks

    def release_callback(self):
        self.released = True

    def foreground(self):
        self.reads.append("foreground")
        if self.foreground_error:
            raise self.foreground_error
        return self.active

    def window(self, hwnd):
        self.reads.append(hwnd)
        if self.window_error:
            raise self.window_error
        return self.windows.get(hwnd)

    def is_own_window(self, hwnd):
        return hwnd in self.own

    def emit(self, event=guard_module.EVENT_SYSTEM_FOREGROUND, hwnd=None, obj=0, child=0):
        self.callback(event, self.active if hwnd is None else hwnd, obj, child)


class FullscreenGuardTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.changes = []
        self.guard = FullscreenGuard(lambda: self.changes.append(True), environ={},
                                     api_factory=lambda: self.api)
        self.addCleanup(self.guard.close)

    def test_constructor_and_import_are_inert_and_start_is_idempotent(self):
        with patch.object(guard_module, "_NativeApi", side_effect=AssertionError("native")):
            importlib.reload(guard_module)
            lazy = guard_module.FullscreenGuard(lambda: None, environ={})
            self.assertIsNone(lazy._api)
        self.assertEqual(self.api.installs, [])
        self.assertEqual(self.api.reads, [])
        self.guard.start()
        self.guard.start()
        self.assertEqual(len(self.api.installs), len(guard_module.EVENTS))
        self.assertEqual(self.api.reads, [])

    def test_startup_already_fullscreen_is_detected_without_an_event(self):
        self.guard.start()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.assertEqual(self.changes, [])

    def test_optout_and_unsupported_never_create_native_adapter(self):
        for platform, env in (("win32", {"DESKTOP_STATS_FULLSCREEN_GUARD_DISABLED": "1"}),
                              ("linux", {})):
            with self.subTest(platform=platform), patch.object(guard_module.sys, "platform", platform):
                with patch.object(guard_module, "_NativeApi", side_effect=AssertionError("native")):
                    guard = FullscreenGuard(lambda: None, environ=env)
                    guard.start()
                    self.assertEqual(guard.blocked(MONITORS), set())
                    self.assertTrue(guard.close())

    def test_foreground_exact_cover_and_windowed_transition(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[1] = WindowState(1, (0, 0, 2560, 1439), A)
        self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE)
        self.assertEqual(self.guard.blocked(MONITORS), set())
        self.assertEqual(len(self.changes), 1)

    def test_negative_origin_and_fullspan_cover_all_contained_monitors(self):
        self.api.windows[1] = WindowState(1, B, B)
        self.assertEqual(self.guard.blocked(MONITORS), {"native-B"})
        self.api.windows[1] = WindowState(1, (-1920, -200, 2560, 1440), A)
        self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE)
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))

    def test_work_area_maximized_window_is_not_fullscreen(self):
        self.api.windows[1] = WindowState(1, (0, 32, 2560, 1400), A)
        self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_different_monitor_focus_retains_observed_game_then_same_monitor_clears(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[2] = WindowState(2, (-1800, 0, -500, 700), B)
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[2] = WindowState(2, (100, 100, 1500, 1000), A)
        self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE)
        self.assertEqual(self.guard.blocked(MONITORS), set())
        self.api.windows[2] = WindowState(2, (-1800, 0, -500, 700), B)
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set())
        self.api.active = 1
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})

    def test_fullspan_retains_other_screen_when_normal_window_covers_one(self):
        self.api.windows[1] = WindowState(1, (-1920, -200, 2560, 1440), A)
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.api.windows[2] = WindowState(2, (100, 100, 1500, 1000), A)
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-B"})

    def test_same_process_popup_keeps_visible_fullscreen_game_protected(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[2] = WindowState(
            2, (500, 300, 1400, 900), A, identity=(123, 77, "GameDialog", 0))
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})

    def test_owned_popup_keeps_visible_fullscreen_game_protected_across_processes(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[2] = WindowState(
            2, (500, 300, 1400, 900), A, identity=(456, 77, "OwnedDialog", 1))
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})

    def test_unrelated_process_normal_foreground_still_restores_same_monitor(self):
        self.guard.blocked(MONITORS)
        self.api.windows[2] = WindowState(
            2, (500, 300, 1400, 900), A, identity=(456, 77, "OtherApp", 0))
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_related_popup_does_not_preserve_invalid_or_no_longer_fullscreen_game(self):
        original = self.api.windows[1]
        changes = ({"rect": (0, 32, 2560, 1400)}, {"visible": False},
                   {"minimized": True}, {"cloaked": True},
                   {"identity": (999, 4, "ReusedGameHandle", 0)}, None)
        for change in changes:
            with self.subTest(change=change):
                self.api.active = 1
                self.api.windows[1] = original
                self.guard.invalidate()
                self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
                self.api.windows[2] = WindowState(
                    2, (500, 300, 1400, 900), A, identity=(123, 77, "GameDialog", 1))
                self.api.active = 2
                if change is None:
                    del self.api.windows[1]
                else:
                    self.api.windows[1] = dataclasses.replace(original, **change)
                self.api.emit()
                self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_popup_relation_is_per_game_across_two_monitors(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.windows[3] = WindowState(3, B, B, identity=(789, 9, "OtherGame", 0))
        self.api.active = 3
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.api.windows[2] = WindowState(
            2, (500, 300, 1400, 900), A, identity=(123, 77, "GameDialog", 1))
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.api.windows[2] = dataclasses.replace(
            self.api.windows[2], rect=(-1800, 0, -500, 700), monitor_rect=B)
        self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE)
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})

    def test_related_popup_keeps_prior_fullspan_suppression_on_other_monitor(self):
        self.api.windows[1] = dataclasses.replace(
            self.api.windows[1], rect=(-1920, -200, 2560, 1440))
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.api.windows[2] = WindowState(
            2, (500, 300, 1400, 900), A, identity=(456, 77, "OtherApp", 0))
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-B"})
        self.api.windows[3] = WindowState(
            3, (-1800, 0, -500, 700), B, identity=(123, 55, "GameDialog", 1))
        self.api.active = 3
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-B"})
        self.assertEqual(self.guard._tracked[1].suppressed, {"native-A"})

    def test_missing_or_invalid_relation_identity_does_not_guess_a_popup(self):
        for identity in ((), (123,), (0, 77, "Unknown", 0),
                         (-1, 77, "Unknown", 0), (True, 77, "Unknown", 0),
                         (456, 77, "Unknown", 0)):
            with self.subTest(identity=identity):
                self.api.active = 1
                self.guard.invalidate()
                self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
                self.api.windows[2] = WindowState(
                    2, (500, 300, 1400, 900), A, identity=identity)
                self.api.active = 2
                self.api.emit()
                self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_desktop_foreground_clears_all_observed_games(self):
        self.guard.blocked(MONITORS)
        self.api.windows[2] = WindowState(2, B, B, desktop=True)
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_destroy_hidden_minimize_and_cloak_remove_tracked_game(self):
        for change in (None, {"visible": False}, {"minimized": True}, {"cloaked": True}):
            with self.subTest(change=change):
                self.api.active = 1
                self.api.windows[1] = WindowState(1, A, A)
                self.guard.invalidate()
                self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
                self.api.windows[2] = WindowState(2, (-1800, 0, -500, 700), B)
                self.api.active = 2
                if change is None:
                    del self.api.windows[1]
                else:
                    self.api.windows[1] = dataclasses.replace(self.api.windows[1], **change)
                self.api.emit(guard_module.EVENT_OBJECT_HIDE, hwnd=1)
                self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_show_restore_and_uncloak_trigger_fresh_read(self):
        for event in (guard_module.EVENT_OBJECT_SHOW, guard_module.EVENT_SYSTEM_MINIMIZEEND,
                      guard_module.EVENT_OBJECT_UNCLOAKED):
            with self.subTest(event=event):
                self.api.windows[1] = WindowState(1, (100, 100, 500, 500), A)
                self.guard.invalidate()
                self.assertEqual(self.guard.blocked(MONITORS), set())
                self.api.windows[1] = WindowState(1, A, A)
                self.api.emit(event)
                self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})

    def test_null_or_query_failure_is_conservative_then_recovers_on_event(self):
        self.api.active = None
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.assertIn("unavailable", self.guard.failure)
        self.api.active = 1
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.api.window_error = OSError("query failed")
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        self.assertIn("query failed", self.guard.failure)
        self.api.window_error = None
        self.api.windows[1] = WindowState(1, (100, 100, 500, 500), A)
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set())
        self.assertIsNone(self.guard.failure)

    def test_install_failure_blocks_all_and_reports_failure(self):
        self.api.install_error = True
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.assertIn("hooks unavailable", self.guard.failure)
        self.assertEqual(self.api.reads, [])

    def test_no_poll_repeated_reads_and_events_only_request_caller_refresh(self):
        self.guard.blocked(MONITORS)
        count = len(self.api.reads)
        for _ in range(25):
            self.guard.blocked(MONITORS)
        self.assertEqual(len(self.api.reads), count)
        for _ in range(25):
            self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE)
        self.assertEqual(len(self.api.reads), count)
        self.assertEqual(len(self.changes), 25)
        self.guard.blocked(MONITORS)
        self.assertGreater(len(self.api.reads), count)

    def test_unknown_startup_does_not_retry_without_event_or_invalidation(self):
        self.api.active = None
        self.guard.blocked(MONITORS)
        count = len(self.api.reads)
        for _ in range(25):
            self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.assertEqual(len(self.api.reads), count)

    def test_object_noise_and_own_events_are_filtered_but_own_foreground_is_observed(self):
        self.guard.start()
        for kwargs in ({"obj": -4}, {"child": 1}, {"hwnd": 0}):
            self.api.emit(guard_module.EVENT_OBJECT_LOCATIONCHANGE, **kwargs)
        self.api.own.add(1)
        self.api.emit(guard_module.EVENT_OBJECT_SHOW)
        self.assertEqual(self.changes, [])
        self.api.emit()
        self.assertEqual(self.changes, [True])

    def test_unrelated_background_events_are_ignored_but_old_tracked_game_is_observed(self):
        self.guard.blocked(MONITORS)
        count = len(self.api.reads)
        for event in (guard_module.EVENT_OBJECT_LOCATIONCHANGE, guard_module.EVENT_OBJECT_SHOW,
                      guard_module.EVENT_OBJECT_HIDE):
            self.api.emit(event, hwnd=999)
        self.assertEqual(self.changes, [])
        self.guard.blocked(MONITORS)
        self.assertEqual(len(self.api.reads), count)
        self.api.windows[2] = WindowState(2, (-1800, 0, -500, 700), B)
        self.api.active = 2
        self.api.emit()
        self.guard.blocked(MONITORS)
        self.api.windows[1] = dataclasses.replace(self.api.windows[1], minimized=True)
        self.api.emit(guard_module.EVENT_SYSTEM_MINIMIZESTART, hwnd=1)
        self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_dpi_geometry_and_hotplug_recompute_physical_monitor_mapping(self):
        self.assertEqual(self.guard.blocked(MONITORS), {"native-A"})
        larger = {"native-A": PixelRect(0, 0, 3840, 2160)}
        self.assertEqual(self.guard.blocked(larger), set())
        self.api.windows[1] = WindowState(1, larger["native-A"], larger["native-A"])
        self.guard.invalidate()
        self.assertEqual(self.guard.blocked(larger), {"native-A"})
        self.api.windows[1] = WindowState(1, B, B)
        self.assertEqual(self.guard.blocked({"renamed-native": B}), {"renamed-native"})
        self.assertEqual(self.guard.blocked({}), set())

    def test_new_or_changed_monitor_is_hidden_during_query_failure(self):
        self.guard.blocked({"native-A": A})
        self.api.foreground_error = OSError("display transition")
        self.assertEqual(self.guard.blocked(MONITORS), set(MONITORS))
        self.assertEqual(self.guard.blocked({"native-B": B}), {"native-B"})

    def test_reused_handle_identity_cannot_retain_old_fullscreen_observation(self):
        self.guard.blocked(MONITORS)
        self.api.windows[1] = WindowState(1, A, A, identity=(999, 5, "Other", 0))
        self.api.windows[2] = WindowState(2, (-1800, 0, -500, 700), B)
        self.api.active = 2
        self.api.emit()
        self.assertEqual(self.guard.blocked(MONITORS), set())

    def test_tracking_is_bounded_without_window_enumeration(self):
        monitors = {}
        for number in range(40):
            rect = (number * 100, 0, number * 100 + 100, 100)
            monitors[str(number)] = rect
            self.api.windows[number + 1] = WindowState(number + 1, rect, rect)
            self.api.active = number + 1
            self.guard.invalidate()
            self.guard.blocked(monitors)
        self.assertLessEqual(len(self.guard._tracked), 32)

    def test_close_unhooks_on_owner_thread_and_suppresses_late_callbacks_and_reads(self):
        self.guard.blocked(MONITORS)
        callback = self.api.callback
        count = len(self.api.reads)
        self.assertTrue(self.guard.close())
        self.assertTrue(self.guard.closed)
        callback(guard_module.EVENT_SYSTEM_FOREGROUND, 1)
        self.assertEqual(self.guard.blocked(MONITORS), set())
        self.assertEqual(self.api.reads[count:], [])
        self.assertEqual(self.changes, [])
        self.assertTrue(self.api.released)
        self.assertTrue(all(tid == threading.get_ident() for _, tid in self.api.uninstalls))
        self.assertTrue(self.guard.close())

    def test_failed_unhook_retains_callback_and_can_be_retried(self):
        self.guard.start()
        self.api.failed_unhooks.add(self.api.installs[0])
        self.assertFalse(self.guard.close())
        self.assertFalse(self.api.released)
        self.assertIn(self.api, guard_module._FAILED_CLOSE_RETAINERS)
        self.api.emit()
        self.assertEqual(self.changes, [])
        self.api.failed_unhooks.clear()
        self.assertTrue(self.guard.close())
        self.assertTrue(self.api.released)
        self.assertNotIn(self.api, guard_module._FAILED_CLOSE_RETAINERS)

    def test_wrong_thread_close_closes_gate_but_defers_unhook_to_owner(self):
        self.guard.start()
        result = []
        worker = threading.Thread(target=lambda: result.append(self.guard.close()))
        worker.start()
        worker.join()
        self.assertEqual(result, [False])
        self.assertEqual(self.api.uninstalls, [])
        self.api.emit()
        self.assertEqual(self.changes, [])
        self.assertTrue(self.guard.close())

    def test_wrong_thread_read_retains_last_blocked_without_native_queries(self):
        self.guard.blocked(MONITORS)
        self.guard.invalidate()
        count = len(self.api.reads)
        result = []
        worker = threading.Thread(target=lambda: result.append(self.guard.blocked(MONITORS)))
        worker.start()
        worker.join()
        self.assertEqual(result, [{"native-A"}])
        self.assertEqual(len(self.api.reads), count)


class Function:
    def __init__(self, effect):
        self.effect = effect

    def __call__(self, *args):
        return self.effect(*args)


class NativeBoundaryTests(unittest.TestCase):
    def fake_native(self):
        calls = []

        def hook(*args):
            calls.append(("hook", args))
            return len(calls)

        def rectangle(_hwnd, _attribute, output, _size):
            if _attribute == 14:
                output._obj.value = 0
            else:
                output._obj.left, output._obj.top = -1920, -200
                output._obj.right, output._obj.bottom = 0, 880
            return 0

        def identity(_hwnd, output):
            output._obj.value = os.getpid() + 1
            return 77

        def name(_hwnd, output, _size):
            output.value = "GameWindow"
            return len(output.value)

        def monitor(_handle, output):
            info = output._obj
            self.assertEqual(info.cbSize, 40)
            info.rcMonitor.left, info.rcMonitor.top = -1920, -200
            info.rcMonitor.right, info.rcMonitor.bottom = 0, 880
            return 1

        def context(value):
            calls.append(("dpi", value.value if isinstance(value, c.c_void_p) else value))
            return 1234

        user = SimpleNamespace(**{key: Function(value) for key, value in {
            "SetWinEventHook": hook, "UnhookWinEvent": lambda value: 1,
            "GetForegroundWindow": lambda: 101, "IsWindow": lambda hwnd: 1,
            "IsWindowVisible": lambda hwnd: 1, "IsIconic": lambda hwnd: 0,
            "GetWindowThreadProcessId": identity, "GetClassNameW": name,
            "GetWindow": lambda hwnd, which: 0,
            "GetWindowRect": lambda hwnd, output: 0,
            "MonitorFromWindow": lambda hwnd, flags: 3, "GetMonitorInfoW": monitor,
            "SetThreadDpiAwarenessContext": context,
        }.items()})
        dwm = SimpleNamespace(DwmGetWindowAttribute=Function(rectangle))
        api = guard_module._NativeApi(dll_loader=lambda name, **options: {
            "user32": user, "dwmapi": dwm}[name])
        return api, calls

    def test_exact_event_hooks_zero_flags_pointer_width_and_retained_callback(self):
        api, calls = self.fake_native()
        notifications = []
        handles = api.install(lambda *args: notifications.append(args))
        self.assertEqual(len(handles), len(guard_module.EVENTS))
        for _, args in calls:
            self.assertEqual(args[0], args[1])
            self.assertIn(args[0], guard_module.EVENTS)
            self.assertIsNone(args[2])
            self.assertEqual(args[4:], (0, 0, 0))
        self.assertIs(api.user.SetWinEventHook.restype, c.c_void_p)
        self.assertEqual(c.sizeof(guard_module.RECT), 16)
        self.assertEqual(c.sizeof(guard_module.MONITORINFO), 40)
        api._callback(1, guard_module.EVENT_SYSTEM_FOREGROUND, 101, 0, 0, 77, 1)
        self.assertEqual(notifications, [(guard_module.EVENT_SYSTEM_FOREGROUND, 101, 0, 0)])
        for handle in handles:
            self.assertTrue(api.uninstall(handle))
        api.release_callback()
        self.assertIsNone(api._callback)

    def test_native_physical_bounds_restore_dpi_context_on_success_and_failure(self):
        api, calls = self.fake_native()
        state = api.window(101)
        self.assertEqual(state.rect, (-1920, -200, 0, 880))
        self.assertEqual(state.monitor_rect, state.rect)
        self.assertEqual([call for call in calls if call[0] == "dpi"],
                         [("dpi", -4 % (1 << (c.sizeof(c.c_void_p) * 8))), ("dpi", 1234)])
        calls.clear()
        api.user.GetMonitorInfoW.effect = lambda *_: 0
        with self.assertRaises(guard_module.FullscreenQueryError):
            api.window(101)
        self.assertEqual(calls[-1], ("dpi", 1234))

    def test_partial_hook_install_failure_unhooks_previous_handles(self):
        api, _ = self.fake_native()
        values = iter((101, 102, 0))
        api.user.SetWinEventHook.effect = lambda *_: next(values)
        unhooked = []
        api.user.UnhookWinEvent.effect = lambda handle: unhooked.append(handle) or 1
        with self.assertRaises(guard_module.FullscreenQueryError) as raised:
            api.install(lambda *_: None)
        self.assertEqual(unhooked, [101, 102])
        self.assertEqual(raised.exception.handles, [])

    def test_failed_partial_install_cleanup_is_retained_for_guard_close_retry(self):
        api, _ = self.fake_native()
        values = iter((101, 102, 0))
        api.user.SetWinEventHook.effect = lambda *_: next(values)
        api.user.UnhookWinEvent.effect = lambda handle: int(handle != 101)
        guard = FullscreenGuard(lambda: None, environ={}, api_factory=lambda: api)
        self.assertEqual(guard.blocked(MONITORS), set(MONITORS))
        self.assertEqual(guard._handles, [101])
        self.assertFalse(guard.close())
        self.assertIsNotNone(api._callback)
        api.user.UnhookWinEvent.effect = lambda _: 1
        self.assertTrue(guard.close())
        self.assertIsNone(api._callback)
        self.assertIsNone(guard.failure)

    def test_dwm_bounds_failure_falls_back_inside_same_physical_pixel_context(self):
        api, calls = self.fake_native()
        original = api.dwm.DwmGetWindowAttribute.effect
        api.dwm.DwmGetWindowAttribute.effect = lambda hwnd, attribute, output, size: (
            -1 if attribute == 9 else original(hwnd, attribute, output, size))

        def fallback(_hwnd, output):
            self.assertEqual(calls[-1][0], "dpi")
            output._obj.left, output._obj.top = -1920, -200
            output._obj.right, output._obj.bottom = 0, 880
            return 1

        api.user.GetWindowRect.effect = fallback
        self.assertEqual(api.window(101).rect, (-1920, -200, 0, 880))
        self.assertEqual(calls[-1], ("dpi", 1234))

    def test_native_desktop_does_not_require_dwm_frame_bounds(self):
        api, calls = self.fake_native()

        def desktop(_hwnd, output, _size):
            output.value = "WorkerW"
            return len(output.value)

        api.user.GetClassNameW.effect = desktop
        api.dwm.DwmGetWindowAttribute.effect = lambda *_: self.fail("desktop has no frame")
        self.assertTrue(api.window(101).desktop)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
