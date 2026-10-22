"""AppBar identity, ABI and lifecycle checks; every native boundary is fake."""

import ctypes as c
import dataclasses
import importlib
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import appbar_platform as bars
from top_bar_layout import PixelRect


class FakeFunction:
    def __init__(self, effect):
        self.effect = effect

    def __call__(self, *args):
        return self.effect(*args)


class FakeWindows:
    """No WinDLL or OS window calls. Supports the exact ctypes wrapper protocol."""

    def __init__(self):
        self.pid, self.tid, self.current_tid = os.getpid(), 77, 77
        self.hwnd, self.generation, self.name = 0x123456, 0x567891, "OwnQtWindowClass"
        self.alive, self.visible, self.registered = True, True, False
        self.fail_message, self.fail_place, self.fail_hide = None, False, False
        self.query_top_offset, self.set_top_offset = 0, 0
        self.after_message = None
        self.calls, self.moves, self.loads = [], [], []
        self.user = SimpleNamespace(
            IsWindow=FakeFunction(lambda _: int(self.alive)),
            IsWindowVisible=FakeFunction(lambda _: int(self.visible)),
            GetWindowThreadProcessId=FakeFunction(self.window_thread),
            GetClassNameW=FakeFunction(self.class_name),
            GetPropW=FakeFunction(self.get_property),
            SetWindowPos=FakeFunction(self.position),
            ShowWindow=FakeFunction(self.show),
        )
        self.shell = SimpleNamespace(SHAppBarMessage=FakeFunction(self.appbar))
        self.kernel = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: self.current_tid))

    def loader(self, name, **options):
        self.loads.append((name, options))
        return {"user32": self.user, "shell32": self.shell, "kernel32": self.kernel}[name]

    def window_thread(self, hwnd, output):
        self.assert_own(hwnd)
        output._obj.value = self.pid
        return self.tid

    def class_name(self, hwnd, output, size):
        self.assert_own(hwnd)
        output.value = self.name
        return len(self.name)

    def get_property(self, hwnd, name):
        self.assert_own(hwnd)
        assert name == bars.WINDOW_GENERATION_PROPERTY
        return self.generation

    def assert_own(self, hwnd):
        assert hwnd == self.hwnd

    def position(self, hwnd, after, x, y, width, height, flags):
        self.assert_own(hwnd)
        assert flags & 0x0010  # Never activate.
        self.moves.append(
            (after.value if isinstance(after, c.c_void_p) else after, x, y, width, height, flags)
        )
        return not self.fail_place

    def show(self, hwnd, command):
        self.assert_own(hwnd)
        assert command == 0
        if not self.fail_hide:
            self.visible = False
        return 0  # Deliberately false: previous visibility is NOT a failure flag.

    def appbar(self, message, pointer):
        data = pointer._obj
        self.assert_own(data.hWnd)
        assert data.cbSize == c.sizeof(bars.APPBARDATA)
        assert data.uEdge == bars.ABE_TOP
        self.calls.append(
            (
                message,
                data.uCallbackMessage,
                data.lParam,
                (data.rc.left, data.rc.top, data.rc.right, data.rc.bottom),
            )
        )
        if message == self.fail_message:
            return 0
        if message == bars.ABM_NEW:
            if self.registered:
                return 0
            self.registered = True
        elif message == bars.ABM_REMOVE:
            self.registered = False
        elif message == bars.ABM_QUERYPOS:
            data.rc.top += self.query_top_offset
        elif message == bars.ABM_SETPOS:
            data.rc.top += self.set_top_offset
            data.rc.bottom += self.set_top_offset
        if self.after_message:
            self.after_message(message)
        return 1


class AppBarTests(unittest.TestCase):
    def setUp(self):
        self.windows = FakeWindows()
        self.backend = bars.NativeAppBarBackend(dll_loader=self.windows.loader)
        self.token = self.backend.retain_window(self.windows.hwnd, self.windows.generation)
        self.session = bars.AppBarSession(self.backend, self.token, 0x8001)
        self.monitor = PixelRect(-1920, -200, 0, 880)

    def test_appbardata_has_windows_pointer_width_layout_and_prototypes(self):
        pointer = c.sizeof(c.c_void_p)
        expected = (48, [0, 8, 16, 20, 24, 40]) if pointer == 8 else (36, [0, 4, 8, 12, 16, 32])
        self.assertEqual(c.sizeof(bars.RECT), 16)
        self.assertEqual(c.sizeof(bars.APPBARDATA), expected[0])
        self.assertEqual(
            [getattr(bars.APPBARDATA, key).offset for key, _ in bars.APPBARDATA._fields_],
            expected[1],
        )
        self.assertIs(self.windows.shell.SHAppBarMessage.restype, c.c_size_t)
        self.assertEqual(
            self.windows.shell.SHAppBarMessage.argtypes, [c.c_uint32, c.POINTER(bars.APPBARDATA)]
        )
        self.assertEqual(self.windows.user.GetPropW.argtypes, [c.c_void_p, c.c_wchar_p])
        self.assertIs(self.windows.user.GetPropW.restype, c.c_void_p)

    def test_foreign_pid_wrong_gui_thread_and_absent_nonce_never_register(self):
        for attribute, value in (("pid", os.getpid() + 1), ("current_tid", 88), ("generation", 0)):
            with self.subTest(attribute=attribute):
                windows = FakeWindows()
                setattr(windows, attribute, value)
                backend = bars.NativeAppBarBackend(dll_loader=windows.loader)
                with self.assertRaises(bars.AppBarError):
                    backend.retain_window(windows.hwnd, 0x567891)
                self.assertEqual(windows.calls, [])

    def test_forged_token_and_changed_pid_thread_class_nonce_are_refused(self):
        with self.assertRaises(bars.AppBarError):
            self.backend.validate(dataclasses.replace(self.token))
        for attribute, changed in (
            ("pid", os.getpid() + 1),
            ("tid", 88),
            ("name", "replacement"),
            ("generation", 0x98765),
            ("alive", False),
        ):
            with self.subTest(attribute=attribute):
                original = getattr(self.windows, attribute)
                setattr(self.windows, attribute, changed)
                with self.assertRaises(bars.AppBarError):
                    self.backend.validate(self.token)
                setattr(self.windows, attribute, original)
        self.assertEqual(self.windows.calls, [])

    def test_reserves_shell_returned_physical_band_and_never_activates(self):
        self.windows.query_top_offset = 40
        self.windows.set_top_offset = 2
        result = self.session.register(self.monitor, dpi=144)
        self.assertTrue(result.ok, result)
        self.assertTrue(result.ready)
        self.assertEqual(result.physical_rect, PixelRect(-1920, -158, 0, -110))
        self.assertEqual([row[0] for row in self.windows.calls], [0, 2, 3])
        self.assertEqual(self.windows.calls[1][3], (-1920, -200, 0, 880))
        self.assertEqual(self.windows.calls[2][3], (-1920, -160, 0, -112))
        self.assertEqual(self.windows.moves[0][1:5], (-1920, -158, 1920, 48))
        self.assertEqual(self.windows.moves[1][0], c.c_void_p(-1).value)
        self.assertTrue(result.registered)
        self.assertFalse(result.cleanup_complete)  # Intentionally active, not yet closed.
        self.assertTrue(self.session.close().cleanup_complete)
        self.assertFalse(self.windows.registered)

    def test_register_constructor_and_import_are_native_inert(self):
        with patch.object(c, "WinDLL", side_effect=AssertionError("Unexpected native load")):
            reloaded = importlib.reload(bars)
            backend = reloaded.NativeAppBarBackend()
            token = reloaded.OwnedWindow(1, os.getpid(), 1, "fake", 1)
            session = reloaded.AppBarSession(backend, token, 0x8001)
            with session:
                pass
            self.assertEqual(session.close().state, "CLOSED")

    def test_duplicate_session_cannot_hide_or_remove_another_lease(self):
        self.assertTrue(self.session.register(self.monitor).ok)
        self.windows.visible = True
        other = bars.AppBarSession(self.backend, self.token, 0x8002)
        result = other.register(self.monitor)
        self.assertFalse(result.ok)
        self.assertTrue(self.windows.visible)
        self.assertTrue(self.windows.registered)
        self.assertNotIn(bars.ABM_REMOVE, [row[0] for row in self.windows.calls])
        self.assertTrue(self.session.close().ok)

    def test_each_acquired_registration_failure_hides_and_removes_in_finally(self):
        for failure in (bars.ABM_QUERYPOS, bars.ABM_SETPOS, "place"):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == "place":
                    self.windows.fail_place = True
                else:
                    self.windows.fail_message = failure
                result = self.session.register(self.monitor)
                self.assertFalse(result.ok)
                self.assertEqual(result.state, "FAILED")
                self.assertFalse(result.registered)
                self.assertTrue(result.cleanup_complete)
                self.assertFalse(self.windows.visible)
                self.assertEqual(self.windows.calls[-1][0], bars.ABM_REMOVE)
                self.assertFalse(any(move[-1] == 0x0013 for move in self.windows.moves))

    def test_new_rejection_never_claims_registered_or_falls_back_to_topmost(self):
        self.windows.fail_message = bars.ABM_NEW
        result = self.session.register(self.monitor)
        self.assertFalse(result.ok)
        self.assertFalse(result)
        self.assertFalse(result.ready)
        self.assertFalse(result.registered)
        self.assertTrue(result.cleanup_complete)
        self.assertEqual(self.windows.moves, [])
        self.assertEqual([row[0] for row in self.windows.calls], [bars.ABM_NEW])

    def test_recycled_hwnd_after_new_is_not_hidden_moved_or_unregistered(self):
        def recycle(message):
            if message == bars.ABM_NEW:
                self.windows.generation += 1

        self.windows.after_message = recycle
        result = self.session.register(self.monitor)
        self.assertFalse(result.ok)
        self.assertTrue(result.registered)
        self.assertFalse(result.cleanup_complete)
        self.assertEqual([row[0] for row in self.windows.calls], [bars.ABM_NEW])
        self.assertEqual(self.windows.moves, [])
        self.assertTrue(self.windows.visible)

    def test_invalid_shell_rect_is_not_placed(self):
        self.windows.query_top_offset = self.monitor.height - 4
        result = self.session.register(self.monitor)
        self.assertFalse(result.ok)
        self.assertTrue(result.cleanup_complete)
        self.assertEqual(self.windows.moves, [])

    def test_remove_failure_stays_pending_and_can_retry(self):
        self.assertTrue(self.session.register(self.monitor).ok)
        self.windows.fail_message = bars.ABM_REMOVE
        failed = self.session.close()
        self.assertFalse(failed.ok)
        self.assertTrue(failed.registered)
        self.assertFalse(failed.cleanup_complete)
        self.windows.fail_message = None
        self.assertTrue(self.session.close().cleanup_complete)

    def test_failed_cleanup_cannot_restore_topmost_and_hide_proof_is_not_reused(self):
        self.assertTrue(self.session.register(self.monitor).ok)
        self.windows.fail_message = bars.ABM_REMOVE
        self.assertFalse(self.session.close().ok)
        move_count = len(self.windows.moves)
        with self.assertRaises(bars.AppBarError):
            self.session.fullscreen(False)
        self.assertEqual(len(self.windows.moves), move_count)
        self.windows.fail_message = None
        self.windows.visible = True  # Caller showed it again; old proof is invalid.
        self.windows.fail_hide = True
        result = self.session.close()
        self.assertFalse(result.registered)
        self.assertFalse(result.cleanup_complete)
        self.windows.fail_hide = False
        self.assertTrue(self.session.close().ok)

    def test_hide_failure_still_unregisters_and_retains_cleanup_for_retry(self):
        self.assertTrue(self.session.register(self.monitor).ok)
        self.windows.fail_hide = True
        failed = self.session.close()
        self.assertFalse(failed.ok)
        self.assertFalse(failed.registered)
        self.assertFalse(failed.cleanup_complete)
        self.assertEqual(self.windows.calls[-1][0], bars.ABM_REMOVE)
        self.windows.fail_hide = False
        self.assertTrue(self.session.close().ok)

    def test_context_exception_always_closes_and_does_not_swallow_original(self):
        with self.assertRaisesRegex(ValueError, "body failure"):
            with self.session:
                self.assertTrue(self.session.register(self.monitor).ok)
                raise ValueError("body failure")
        self.assertEqual(self.windows.calls[-1][0], bars.ABM_REMOVE)
        self.assertTrue(self.session.close().cleanup_complete)

    def test_context_cleanup_error_is_attached_to_original_exception(self):
        with self.assertRaises(ValueError) as caught:
            with self.session:
                self.assertTrue(self.session.register(self.monitor).ok)
                self.windows.fail_message = bars.ABM_REMOVE
                raise ValueError("original")
        self.assertIn("cleanup incomplete", caught.exception.__notes__[0])
        self.windows.fail_message = None
        self.assertTrue(self.session.close().ok)

    def test_notifications_are_deferred_and_relayout_does_not_reregister(self):
        self.windows.after_message = lambda _: self.session.position_notification()
        self.assertTrue(self.session.register(self.monitor).ok)
        self.assertFalse(self.session.needs_relayout)
        self.session.position_notification()
        self.assertTrue(self.session.needs_relayout)
        self.assertTrue(self.session.relayout(dpi=192).ok)
        self.assertEqual([row[0] for row in self.windows.calls].count(bars.ABM_NEW), 1)
        self.assertFalse(self.session.needs_relayout)
        self.assertEqual(self.session._rect.height, 64)

    def test_shell_recreation_reregisters_once_and_fullscreen_yields(self):
        self.assertTrue(self.session.register(self.monitor).ok)
        self.windows.registered = False  # Fake Shell restart; no actual system operation.
        self.assertTrue(self.session.shell_recreated(1).ok)
        count = len(self.windows.calls)
        self.assertTrue(self.session.shell_recreated(1).ok)
        self.assertEqual(len(self.windows.calls), count)
        self.assertTrue(self.session.fullscreen(True).ok)
        self.assertEqual(self.windows.moves[-1][0], 1)
        self.assertTrue(self.session.fullscreen(False).ok)
        self.assertEqual(self.windows.moves[-1][0], c.c_void_p(-1).value)
        self.assertTrue(self.session.notify_activation(True).ok)
        self.assertEqual(self.windows.calls[-1][:3], (bars.ABM_ACTIVATE, 0, 1))
        self.assertTrue(self.session.notify_window_position().ok)
        self.assertEqual(self.windows.calls[-1][0], bars.ABM_WINDOWPOSCHANGED)

    def test_invalid_request_and_cross_thread_call_have_no_new_native_effect(self):
        for kwargs in (
            dict(dpi=True),
            dict(dpi=0),
            dict(height_dip=float("nan")),
            dict(height_dip=129),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(bars.AppBarError):
                self.session.register(self.monitor, **kwargs)
        errors = []

        def attempt():
            try:
                self.session.register(self.monitor)
            except bars.AppBarError as error:
                errors.append(str(error))

        thread = threading.Thread(target=attempt)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.windows.calls, [])


if __name__ == "__main__":
    unittest.main()
