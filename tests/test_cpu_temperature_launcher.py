"""Consent/session safety with fake DLLs, private files and offscreen signals."""

import copy
import ctypes as c
import hashlib
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cpu_temperature_launcher as startup
from configuration_scopes import PREFERENCE_FIELDS, merge_scope, scope_dirty
from fullscreen_guard import WindowState
from stats_config import DEFAULT, validate

WALL = 1_700_000_000.0


def config():
    value = copy.deepcopy(DEFAULT)
    value[startup.PREFERENCE] = True
    value["widgets"]["cpu"].update(enabled=True, primary="temp")
    return value


class FakeApi:
    def __init__(self):
        self.calls = []
        self.result = dict(launched=True, error=0)
        self.error = None
        self.on_verify = None

    def verify_process(self, expected, pid):
        self.calls.append(("process", expected, pid))
        if self.error:
            raise self.error
        if self.on_verify:
            self.on_verify()

    @contextmanager
    def verified_helper(self, helper, digest):
        self.calls.append(("locked", helper, digest))
        try:
            yield
        finally:
            self.calls.append(("unlocked",))

    def launch(self, helper, pid):
        self.calls.append(("launch", helper, pid))
        return self.result

    def close(self):
        self.calls.append(("close",))


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native calls")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.local = Path(tempfile.gettempdir()) / "synthetic-startup-local"
        self.executable = self.local / "Programs/DesktopStats/DesktopStats.exe"
        self.api = FakeApi()
        self.factory = Mock(return_value=self.api)
        self.options = dict(platform="win32", frozen=True, executable=self.executable,
                            environ={"LOCALAPPDATA": str(self.local)}, app_pid=731,
                            api_factory=self.factory, wall_clock=lambda: WALL)
        self.launcher = startup.CpuTemperatureLauncher(**self.options)
        self.data = dict(time=WALL)

    def tearDown(self):
        self.native.assert_not_called()
        self.process.assert_not_called()

    def update(self, **kwargs):
        return self.launcher.update(config(), self.data, fullscreen=kwargs.get("fullscreen", False))

    def test_constructor_does_not_load_native_or_read_files(self):
        with patch.object(Path, "open", side_effect=AssertionError("No files")):
            startup.CpuTemperatureLauncher(**self.options)
        self.factory.assert_not_called()

    def test_launch_uses_fixed_helper_digest_and_bound_pid_exactly_once(self):
        self.assertEqual(self.update()["state"], "launched")
        for _ in range(30):
            self.update()
        helper = self.executable.parent / startup.HELPER_RELATIVE
        self.assertEqual(self.api.calls, [
            ("process", self.executable, 731), ("locked", helper, startup.HELPER_SHA256),
            ("launch", helper, 731), ("unlocked",),
        ])
        self.assertTrue(self.launcher.status()["attempted"])
        self.factory.assert_called_once_with()

    def test_restarting_app_creates_new_single_prompt_budget(self):
        self.update()
        self.launcher.close()
        self.launcher = startup.CpuTemperatureLauncher(**self.options)
        self.update()
        self.assertEqual(sum(row[0] == "launch" for row in self.api.calls), 2)

    def test_successful_launch_tracks_fresh_cached_temperature_without_any_new_native_work(self):
        self.assertEqual(self.update()["state"], "launched")
        calls = list(self.api.calls)
        foreground = Mock(side_effect=AssertionError("Post-consent samples must not query foreground"))
        self.data.update(cpu_temp=61.0, metric_timestamps={"cpu_temp": WALL - 1})
        for _ in range(30):
            self.assertEqual(self.update(fullscreen=foreground),
                             dict(state="ready", reason="existing_temperature", attempted=True, error=0))
        self.assertEqual(self.api.calls, calls)
        self.factory.assert_called_once_with()
        foreground.assert_not_called()

    def test_post_launch_ready_waiting_and_recovery_use_sample_timestamp_not_new_frame_time(self):
        now = [WALL]
        self.launcher = startup.CpuTemperatureLauncher(**(self.options | {"wall_clock": lambda: now[0]}))
        self.assertEqual(self.update()["state"], "launched")
        calls = list(self.api.calls)
        foreground = Mock(side_effect=AssertionError("No foreground reads after consent"))
        self.data.update(cpu_temp=62.0, metric_timestamps={"cpu_temp": now[0]})
        self.assertEqual(self.update(fullscreen=foreground)["state"], "ready")
        now[0] += startup.FRESH_SECONDS + .01
        # A fresh overall frame cannot make its expired temperature fresh.
        self.data["time"] = now[0]
        self.assertEqual(self.update(fullscreen=foreground),
                         dict(state="launched", reason="awaiting_sensor", attempted=True, error=0))
        self.data.update(cpu_temp=None, metric_timestamps={"cpu_temp": now[0]})
        self.assertEqual(self.update(fullscreen=foreground)["reason"], "awaiting_sensor")
        self.data.update(cpu_temp=63.0, metric_timestamps={"cpu_temp": now[0]})
        self.assertEqual(self.update(fullscreen=foreground)["state"], "ready")
        self.assertEqual(self.api.calls, calls)
        self.factory.assert_called_once_with()
        foreground.assert_not_called()
        self.launcher.close()
        self.assertEqual(self.update(fullscreen=foreground)["state"], "closed")
        self.assertEqual(self.api.calls, calls + [("close",)])

    def test_post_launch_invalid_samples_do_not_report_ready_or_relaunch(self):
        self.update()
        calls = list(self.api.calls)
        foreground = Mock(side_effect=AssertionError("No post-launch foreground reads"))
        for value, stamp in ((False, WALL), (0, WALL), (125, WALL), (float("nan"), WALL),
                             (float("inf"), WALL), (60, WALL - 8.1), (60, WALL + 1),
                             (60, None)):
            with self.subTest(value=value, timestamp=stamp):
                self.data.update(cpu_temp=value, metric_timestamps={"cpu_temp": stamp})
                self.assertEqual(self.update(fullscreen=foreground),
                                 dict(state="launched", reason="awaiting_sensor", attempted=True, error=0))
        self.assertEqual(self.api.calls, calls)
        self.factory.assert_called_once_with()
        foreground.assert_not_called()

    def test_terminal_cancel_or_failure_is_not_replaced_by_a_later_fresh_reading(self):
        fresh = dict(time=WALL, cpu_temp=60, metric_timestamps={"cpu_temp": WALL})
        foreground = Mock(side_effect=AssertionError("Terminal failures must not query foreground"))
        for result in (dict(launched=False, error=1223), dict(launched=False, error=5)):
            with self.subTest(result=result):
                api = FakeApi()
                api.result = result
                factory = Mock(return_value=api)
                launcher = startup.CpuTemperatureLauncher(**(self.options | {"api_factory": factory}))
                terminal = launcher.update(config(), dict(time=WALL), fullscreen=False)
                calls = list(api.calls)
                self.assertEqual(launcher.update(config(), fresh, fullscreen=foreground), terminal)
                self.assertEqual(api.calls, calls)
                factory.assert_called_once_with()
        foreground.assert_not_called()

    def test_cancel_does_not_retry_even_after_new_samples_and_preference_toggle(self):
        self.api.result = dict(launched=False, error=1223)
        self.assertEqual(self.update()["state"], "cancelled")
        disabled = config() | {startup.PREFERENCE: False}
        self.launcher.update(disabled, self.data, fullscreen=False)
        for _ in range(50):
            self.update()
        self.assertEqual(sum(row[0] == "launch" for row in self.api.calls), 1)

    def test_failed_launch_does_not_retry(self):
        self.api.result = dict(launched=False, error=5)
        self.assertEqual(self.update(), dict(state="failed", reason="elevation", attempted=True, error=5))
        self.update()
        self.assertEqual(sum(row[0] == "launch" for row in self.api.calls), 1)

    def test_unknown_and_fullscreen_defer_without_consuming_attempt(self):
        for state in (True, None, True, None):
            result = self.update(fullscreen=state)
            self.assertEqual(result["state"], "deferred")
            self.assertFalse(result["attempted"])
        self.factory.assert_not_called()
        self.assertEqual(self.update()["state"], "launched")

    def test_healthy_bridge_or_other_provider_suppresses_consent(self):
        for source in ("ASUS COM · CPU", "HWiNFO"):
            self.data.update(cpu_temp=60.0, metric_timestamps={"cpu_temp": WALL - 2}, cpu_temp_source=source)
            self.assertEqual(self.update()["state"], "ready")
        self.factory.assert_not_called()
        self.data["cpu_temp"] = None
        self.assertEqual(self.update()["state"], "launched")

    def test_stale_false_infinite_or_invalid_temperature_never_counts_as_ready(self):
        for value, stamp in ((False, WALL), (0, WALL), (125, WALL), (float("nan"), WALL),
                             (float("inf"), WALL), (60, WALL - 8.1), (60, WALL + 1)):
            self.assertFalse(startup.temperature_ready(dict(cpu_temp=value, time=stamp), WALL))
        self.assertTrue(startup.temperature_ready(dict(cpu_temp=60, time=WALL), WALL))

    def test_headless_source_nonwindows_test_profile_and_disabled_reader_never_load_api(self):
        overrides = [dict(headless=True), dict(frozen=False), dict(platform="linux"),
                     dict(environ={"LOCALAPPDATA": str(self.local), "DESKTOP_STATS_DATA": "private"}),
                     dict(environ={"LOCALAPPDATA": str(self.local), "DESKTOP_STATS_CPU_BRIDGE_DISABLED": "1"})]
        for values in overrides:
            launcher = startup.CpuTemperatureLauncher(**(self.options | values))
            self.assertEqual(launcher.update(config(), self.data, fullscreen=False)["state"], "disabled")
        self.factory.assert_not_called()

    def test_default_off_and_no_temperature_demand_do_not_query_foreground(self):
        foreground = Mock(side_effect=AssertionError("No foreground reads"))
        self.launcher.update(DEFAULT, self.data, fullscreen=foreground)
        value = config()
        value["visible"], value["top_bar"]["enabled"] = False, False
        self.assertEqual(self.launcher.update(value, self.data, fullscreen=foreground)["state"], "idle")
        self.data["cpu_temp"] = 60
        self.launcher.update(config(), self.data, fullscreen=foreground)
        foreground.assert_not_called()
        self.factory.assert_not_called()

    def test_wrong_installed_path_and_absent_localappdata_are_blocked_before_native(self):
        for override in (dict(executable=self.executable.with_name("Other.exe")), dict(environ={})):
            launcher = startup.CpuTemperatureLauncher(**(self.options | override))
            self.assertEqual(launcher.update(config(), self.data, fullscreen=False)["state"], "blocked")
        self.factory.assert_not_called()

    def test_verification_failure_is_terminal_without_attempting_consent(self):
        self.api.error = ValueError("wrong current process or helper")
        self.assertEqual(self.update()["reason"], "verification")
        self.assertFalse(self.launcher.status()["attempted"])
        self.update()
        self.assertEqual(len(self.api.calls), 1)

    def test_shutdown_during_preflight_cleans_lock_and_prevents_consent(self):
        self.api.on_verify = self.launcher.close
        self.assertEqual(self.update()["state"], "closed")
        self.assertFalse(any(row[0] == "launch" for row in self.api.calls))
        self.assertIn(("unlocked",), self.api.calls)

    def test_closed_instance_ignores_all_future_samples(self):
        self.launcher.close()
        self.assertEqual(self.update()["state"], "closed")
        self.factory.assert_not_called()

    def test_reentrant_shutdown_during_consent_does_not_replace_closed_status(self):
        def launch(helper, pid):
            self.launcher.close()
            return dict(launched=True, error=0)
        self.api.launch = launch
        self.assertEqual(self.update()["state"], "closed")
        self.assertEqual(self.api.calls[-2:], [("unlocked",), ("close",)])
        self.assertTrue(self.launcher.status()["attempted"])

    def test_preference_strict_default_and_scope(self):
        self.assertIs(DEFAULT[startup.PREFERENCE], False)
        self.assertIs(validate({})[startup.PREFERENCE], False)
        self.assertIn(startup.PREFERENCE, PREFERENCE_FIELDS)
        for value in (1, 0, "true", None, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate({startup.PREFERENCE: value})
        source = validate(DEFAULT | {startup.PREFERENCE: True})
        self.assertTrue(scope_dirty(DEFAULT, source, "preferences"))
        self.assertFalse(scope_dirty(DEFAULT, source, "desktop"))
        self.assertIs(merge_scope(DEFAULT, source, "topbar")[startup.PREFERENCE], False)
        self.assertIs(merge_scope(DEFAULT, source, "preferences")[startup.PREFERENCE], True)


class ForegroundTests(unittest.TestCase):
    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native calls")))

    def test_fullscreen_and_unknown_guard_never_fall_through(self):
        factory = Mock(side_effect=AssertionError("No extra native API"))
        manager = SimpleNamespace(_fullscreen_active=lambda: True)
        self.assertIs(startup.foreground_fullscreen(manager, api_factory=factory), True)
        manager = SimpleNamespace(_fullscreen_active=lambda: False, _fullscreen_guard=SimpleNamespace(
            _known=False, failure=None), _read_foreground_visibility=lambda: None)
        self.assertIsNone(startup.foreground_fullscreen(manager, api_factory=factory))
        manager._fullscreen_guard._known = True
        manager._fullscreen_guard_error = "ReadFailed"
        self.assertIsNone(startup.foreground_fullscreen(manager, api_factory=factory))
        factory.assert_not_called()

    def test_read_only_query_desktop_window_and_game(self):
        state = WindowState(7, (10, 20, 1010, 720), (0, 0, 1920, 1080))
        api = SimpleNamespace(foreground=lambda: 7, window=lambda hwnd: state)
        self.assertIs(startup.foreground_fullscreen(api_factory=lambda: api), False)
        state = WindowState(7, (0, 0, 1920, 1080), (0, 0, 1920, 1080))
        self.assertIs(startup.foreground_fullscreen(api_factory=lambda: api), True)
        state = WindowState(7, desktop=True)
        self.assertIs(startup.foreground_fullscreen(api_factory=lambda: api), False)
        state = None
        self.assertIsNone(startup.foreground_fullscreen(api_factory=lambda: api))

    def test_guard_observed_game_still_defers_with_own_settings_foreground(self):
        factory = Mock(side_effect=AssertionError("No foreground override"))
        manager = SimpleNamespace(_fullscreen_active=lambda: False, _fullscreen_guard=SimpleNamespace(
            _known=True, failure=None), _read_foreground_visibility=lambda: None,
            _foreground_hidden_screens={"DISPLAY2"})
        self.assertTrue(startup.foreground_fullscreen(manager, api_factory=factory))
        factory.assert_not_called()

    def test_own_window_needs_existing_known_guard_to_rule_out_a_game_behind_it(self):
        api = SimpleNamespace(foreground=lambda: 7, window=lambda hwnd: WindowState(7, own_process=True))
        self.assertIsNone(startup.foreground_fullscreen(api_factory=lambda: api))
        manager = SimpleNamespace(_fullscreen_active=lambda: False, _fullscreen_guard=SimpleNamespace(
            _known=True, failure=None), _read_foreground_visibility=lambda: None,
            _foreground_hidden_screens=set())
        self.assertIs(startup.foreground_fullscreen(manager, api_factory=lambda: api), False)

    def test_native_failure_null_hidden_cloaked_or_unmeasurable_foreground_defers(self):
        for state in (None, WindowState(7, visible=False), WindowState(7, minimized=True),
                      WindowState(7, cloaked=True), WindowState(7)):
            api = SimpleNamespace(foreground=lambda: 7, window=lambda hwnd: state)
            self.assertIsNone(startup.foreground_fullscreen(api_factory=lambda: api))
        self.assertIsNone(startup.foreground_fullscreen(api_factory=Mock(side_effect=OSError())))
        self.native.assert_not_called()


class Function:
    def __init__(self, invoke):
        self.invoke = invoke

    def __call__(self, *args):
        return self.invoke(*args)


class Dlls:
    """No WinDLL, Shell or process exists; every native boundary is a callable."""
    def __init__(self, executable, helper):
        self.executable, self.helper = executable, helper
        self.pid, self.close_fail, self.closed = 731, False, []
        self.payload, self.position = b"synthetic signed-off helper fixture", 0
        self.success, self.error, self.process, self.com_result = True, 0, 99, 0
        self.co_enter = self.co_exit = 0
        self.shell_info = self.open_args = None
        self.final = str(helper)
        self.read_fail = False
        self.kernel = SimpleNamespace(**{name: Function(fn) for name, fn in dict(
            GetCurrentProcessId=lambda: self.pid, GetModuleFileNameW=self.module_name,
            CreateFileW=self.open, GetFinalPathNameByHandleW=self.final_name,
            ReadFile=self.read, CloseHandle=self.close,
        ).items()})
        self.shell = SimpleNamespace(ShellExecuteExW=Function(self.execute))
        self.ole = SimpleNamespace(CoInitializeEx=Function(self.co_initialize),
                                   CoUninitialize=Function(self.co_uninitialize))

    def loader(self, name, **kwargs):
        return {"kernel32": self.kernel, "shell32": self.shell, "ole32": self.ole}[name]

    def module_name(self, module, buffer, length):
        buffer.value = str(self.executable)
        return len(buffer.value)

    def open(self, *args):
        self.open_args = args
        return 55

    def final_name(self, handle, buffer, size, flags):
        buffer.value = "\\\\?\\" + self.final
        return len(buffer.value)

    def read(self, handle, buffer, size, count, overlapped):
        payload = self.payload[self.position:self.position + size]
        self.position += len(payload)
        c.memmove(buffer, payload, len(payload))
        count._obj.value = len(payload)
        return not self.read_fail

    def close(self, handle):
        self.closed.append(handle)
        return not self.close_fail

    def execute(self, pointer):
        info = pointer._obj
        self.shell_info = {key: getattr(info, key) for key, _kind in info._fields_}
        info.hProcess = self.process
        return self.success

    def co_initialize(self, reserved, flags):
        self.co_enter += 1
        self.co_flags = flags
        return self.com_result

    def co_uninitialize(self):
        self.co_exit += 1


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No real DLL")))
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix="temperature-launcher-"))
        self.exe, self.helper = Path(directory) / "DesktopStats.exe", Path(directory) / "Bridge.exe"
        self.exe.write_bytes(b"synthetic exe")
        self.helper.write_bytes(b"synthetic helper")
        self.dlls = Dlls(self.exe, self.helper)
        self.api = startup._NativeApi(loader=self.dlls.loader, last_error=lambda: self.dlls.error)
        self.digest = hashlib.sha256(self.dlls.payload).hexdigest()

    def test_shell_structure_verb_hide_pid_flags_com_and_process_cleanup(self):
        result = self.api.launch(self.helper, 731)
        self.assertEqual(result, dict(launched=True, error=0))
        info = self.dlls.shell_info
        self.assertEqual(c.sizeof(startup._ShellExecuteInfo), 112 if c.sizeof(c.c_void_p) == 8 else 60)
        self.assertEqual(info["cbSize"], c.sizeof(startup._ShellExecuteInfo))
        self.assertEqual(info["fMask"], 0x540)
        self.assertEqual((info["lpVerb"], info["lpFile"], info["lpParameters"], info["nShow"]),
                         ("runas", str(self.helper), "--app-pid 731", 0))
        self.assertEqual(info["lpDirectory"], str(self.helper.parent))
        self.assertIsNone(info["hwnd"])
        self.assertEqual((self.dlls.co_enter, self.dlls.co_exit, self.dlls.co_flags), (1, 1, 6))
        self.assertEqual(self.dlls.closed, [99])
        self.assertFalse(self.api._handles)

    def test_cancellation_preserves_native_error_and_balances_com(self):
        self.dlls.success, self.dlls.error, self.dlls.process = False, 1223, None
        self.assertEqual(self.api.launch(self.helper, 731), dict(launched=False, error=1223))
        self.assertEqual(self.dlls.co_exit, 1)
        self.assertFalse(self.dlls.closed)

    def test_shell_exception_still_closes_handle_and_uninitializes_com(self):
        def fail(pointer):
            pointer._obj.hProcess = 99
            raise OSError("synthetic Shell failure")
        self.dlls.shell.ShellExecuteExW.invoke = fail
        with self.assertRaises(OSError):
            self.api.launch(self.helper, 731)
        self.assertEqual(self.dlls.closed, [99])
        self.assertEqual(self.dlls.co_exit, 1)

    def test_com_already_initialized_balances_and_failed_com_never_calls_shell(self):
        self.dlls.com_result = 1
        self.api.launch(self.helper, 731)
        self.assertEqual(self.dlls.co_exit, 1)
        self.dlls.com_result, self.dlls.shell_info = -1, None
        with self.assertRaises(OSError):
            self.api.launch(self.helper, 731)
        self.assertIsNone(self.dlls.shell_info)
        self.assertEqual(self.dlls.co_exit, 1)

    def test_verified_helper_locked_during_launch_then_closed(self):
        with self.api.verified_helper(self.helper, self.digest):
            self.assertEqual(self.dlls.closed, [])
            self.assertEqual(self.dlls.open_args[:3], (str(self.helper), 0x80000000, 1))
            self.assertEqual(self.dlls.open_args[4:6], (3, 0x80))
            self.api.launch(self.helper, 731)
        self.assertEqual(self.dlls.closed, [99, 55])
        self.assertFalse(self.api._handles)

    def test_bad_hash_wrong_final_path_oversize_and_read_error_close_file(self):
        for case in ("digest", "path", "size", "read"):
            with self.subTest(case=case):
                self.dlls.position, self.dlls.closed, self.dlls.final = 0, [], str(self.helper)
                self.dlls.payload, self.dlls.read_fail = b"synthetic signed-off helper fixture", False
                if case == "path":
                    self.dlls.final = str(self.helper.with_name("Other.exe"))
                elif case == "size":
                    self.dlls.payload = b"x" * (1024 * 1024 + 1)
                elif case == "read":
                    self.dlls.read_fail = True
                with self.assertRaises((OSError, ValueError)):
                    with self.api.verified_helper(self.helper, "0" * 64 if case == "digest" else self.digest):
                        self.fail("Unverified helper must never launch")
                self.assertEqual(self.dlls.closed, [55])
                self.assertFalse(self.api._handles)

    def test_current_os_process_path_pid_and_plain_file_must_match(self):
        self.api.verify_process(self.exe, 731)
        for expected, pid in ((self.helper, 731), (self.exe, 732)):
            with self.assertRaises(ValueError):
                self.api.verify_process(expected, pid)
        self.exe.unlink()
        with self.assertRaises(ValueError):
            self.api.verify_process(self.exe, 731)

    def test_reparse_component_is_rejected(self):
        real = Path.lstat
        def lstat(path, *args, **kwargs):
            if path == self.helper.parent:
                return SimpleNamespace(st_file_attributes=0x400)
            return real(path, *args, **kwargs)
        with patch.object(Path, "lstat", lstat), self.assertRaises(ValueError):
            startup._plain_path(self.helper)

    def test_failed_handle_cleanup_is_retained_for_shutdown_retry(self):
        self.dlls.close_fail = True
        with self.assertRaises(OSError):
            self.api.launch(self.helper, 731)
        self.assertEqual(self.api._handles, {99})
        self.assertEqual(self.dlls.co_exit, 1)
        self.dlls.close_fail = False
        self.api.close()
        self.assertFalse(self.api._handles)
        self.assertEqual(self.dlls.closed, [99, 99])


class RuntimeSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtQuickControls2 import QQuickStyle
        from PySide6.QtWidgets import QApplication
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise AssertionError("Temperature integration must remain offscreen")

    def setUp(self):
        import native_controller
        import native_runtime
        self.runtime_module = native_runtime
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No true UAC/native calls")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch.object(native_controller, "load", return_value=config()))
        self.enterContext(patch.object(native_controller.Controller, "start", lambda *args, **kwargs: None))
        self.enterContext(patch.object(native_runtime, "read_positions", return_value={}))
        self.enterContext(patch.object(native_runtime, "transparency_enabled", return_value=False))
        self.enterContext(patch.object(native_runtime.Runtime, "save_positions", lambda *args: None))
        self.enterContext(patch.object(native_runtime, "CONFIG", SimpleNamespace(exists=lambda: True)))
        self.runtime = native_runtime.Runtime(self.app, background=True, headless=True)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.runtime.shutdown()
        self.runtime.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.native.assert_not_called()

    def test_real_runtime_existing_signal_headless_never_prompts(self):
        self.runtime.controller._data = dict(time=WALL)
        self.runtime.controller.dataChanged.emit()
        self.assertEqual(self.runtime.cpu_temperature_launcher.status()["state"], "disabled")

    def test_signal_defer_resume_cancel_no_repeat_shutdown(self):
        api = FakeApi()
        api.result = dict(launched=False, error=1223)
        local = Path(tempfile.gettempdir()) / "synthetic-runtime-startup"
        self.runtime.cpu_temperature_launcher = startup.CpuTemperatureLauncher(
            platform="win32", frozen=True, executable=local / "Programs/DesktopStats/DesktopStats.exe",
            environ={"LOCALAPPDATA": str(local)}, app_pid=731, api_factory=lambda: api,
            wall_clock=lambda: WALL,
        )
        guard = self.enterContext(patch.object(self.runtime_module, "foreground_fullscreen", return_value=True))
        self.runtime.controller._data = dict(time=WALL)
        self.runtime.controller.dataChanged.emit()
        self.assertEqual(self.runtime.cpu_temperature_launcher.status()["state"], "deferred")
        self.assertFalse(api.calls)
        guard.return_value = False
        self.runtime.controller.dataChanged.emit()
        self.assertEqual(self.runtime.cpu_temperature_launcher.status()["state"], "cancelled")
        for _ in range(4):
            self.runtime.controller.dataChanged.emit()
        self.assertEqual(guard.call_count, 2)
        self.assertEqual(sum(row[0] == "launch" for row in api.calls), 1)
        self.runtime.shutdown()
        self.runtime.controller.dataChanged.emit()
        self.assertEqual(self.runtime.cpu_temperature_launcher.status()["state"], "closed")
        self.assertIn(("close",), api.calls)

    def consent_fixture(self, outcome=None):
        api = FakeApi()
        if outcome is not None:
            api.result = outcome
        local = Path(tempfile.gettempdir()) / "synthetic-recovery-startup"
        self.runtime.cpu_temperature_launcher = startup.CpuTemperatureLauncher(
            platform="win32", frozen=True, executable=local / "Programs/DesktopStats/DesktopStats.exe",
            environ={"LOCALAPPDATA": str(local)}, app_pid=731, api_factory=lambda: api,
            wall_clock=lambda: WALL,
        )
        self.enterContext(patch.object(self.runtime_module, "foreground_fullscreen", return_value=False))
        self.runtime.controller._data = dict(time=WALL)
        events = dict(bar=[], settings=[], widget=[])
        self.runtime.top_bar.refresh_materials = events["bar"].append
        self.runtime.settings_material = SimpleNamespace(request=events["settings"].append, close=lambda: None)
        self.runtime.widgets["probe"] = SimpleNamespace(hide=lambda: None)
        self.runtime.widget_materials["probe"] = SimpleNamespace(request=events["widget"].append, close=lambda: None)
        return api, events

    def test_consent_success_cancel_and_failure_queue_one_recovery_on_next_turn(self):
        for outcome in (dict(launched=True, error=0), dict(launched=False, error=1223),
                        dict(launched=False, error=5)):
            with self.subTest(outcome=outcome):
                _api, events = self.consent_fixture(outcome)
                self.runtime.controller.dataChanged.emit()
                self.assertEqual(events, dict(bar=[], settings=[], widget=[]))
                self.app.processEvents()
                self.assertEqual(events, {key: ["composition_changed"] for key in events})
                for _ in range(10):
                    self.runtime.controller.dataChanged.emit()
                self.app.processEvents()
                self.assertEqual(events, {key: ["composition_changed"] for key in events})

    def test_post_launch_freshness_changes_do_not_queue_more_consent_or_material_recovery(self):
        api, events = self.consent_fixture()
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, {key: ["composition_changed"] for key in events})
        calls = list(api.calls)
        with patch.object(self.runtime_module, "foreground_fullscreen",
                          side_effect=AssertionError("No post-consent foreground queries")):
            for stamp, expected in ((WALL, "ready"), (WALL - startup.FRESH_SECONDS - .1, "launched"),
                                    (WALL, "ready")):
                self.runtime.controller._data.update(cpu_temp=64, metric_timestamps={"cpu_temp": stamp})
                self.runtime.controller.dataChanged.emit()
                self.assertEqual(self.runtime.cpu_temperature_launcher.status()["state"], expected)
            self.app.processEvents()
        self.assertEqual(api.calls, calls)
        self.assertEqual(events, {key: ["composition_changed"] for key in events})

    def test_healthy_deferred_and_source_sessions_never_queue_recovery(self):
        _api, events = self.consent_fixture()
        self.runtime.controller._data["cpu_temp"] = 47.0
        self.runtime.controller.dataChanged.emit()
        self.runtime.controller._data["cpu_temp"] = None
        with patch.object(self.runtime_module, "foreground_fullscreen", return_value=True):
            self.runtime.controller.dataChanged.emit()
        with patch.object(self.runtime_module, "foreground_fullscreen", return_value=None):
            self.runtime.controller.dataChanged.emit()
        self.runtime.cpu_temperature_launcher = startup.CpuTemperatureLauncher()
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, dict(bar=[], settings=[], widget=[]))

    def test_shutdown_before_queued_recovery_drops_every_request(self):
        _api, events = self.consent_fixture()
        self.runtime.controller.dataChanged.emit()
        self.runtime.shutdown()
        self.app.processEvents()
        self.assertEqual(events, dict(bar=[], settings=[], widget=[]))

    def test_replaced_manager_or_launcher_before_next_turn_drops_old_recovery(self):
        for owner in ("top_bar", "cpu_temperature_launcher"):
            with self.subTest(owner=owner):
                _api, events = self.consent_fixture()
                original = getattr(self.runtime, owner)
                self.runtime.controller.dataChanged.emit()
                setattr(self.runtime, owner, SimpleNamespace())
                self.app.processEvents()
                setattr(self.runtime, owner, original)
                self.assertEqual(events, dict(bar=[], settings=[], widget=[]))

    def test_shutdown_or_manager_replacement_inside_consent_does_not_queue(self):
        api, events = self.consent_fixture()
        original_bar = self.runtime.top_bar

        def launch(_helper, _pid):
            self.runtime.top_bar = SimpleNamespace()
            return dict(launched=True, error=0)

        api.launch = launch
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.runtime.top_bar = original_bar
        self.assertEqual(events, dict(bar=[], settings=[], widget=[]))
        api, events = self.consent_fixture()

        def shutdown(_helper, _pid):
            self.runtime.shutdown()
            return dict(launched=False, error=1223)

        api.launch = shutdown
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, dict(bar=[], settings=[], widget=[]))

    def test_nested_sample_during_consent_still_queues_only_once(self):
        api, events = self.consent_fixture()

        def nested(_helper, _pid):
            self.runtime.controller.dataChanged.emit()
            return dict(launched=True, error=0)

        api.launch = nested
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, {key: ["composition_changed"] for key in events})

    def test_bar_refresh_reentrant_shutdown_skips_remaining_materials(self):
        _api, events = self.consent_fixture()

        def close(reason):
            events["bar"].append(reason)
            self.runtime.shutdown()

        self.runtime.top_bar.refresh_materials = close
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, dict(bar=["composition_changed"], settings=[], widget=[]))

    def test_replaced_settings_and_widget_during_bar_refresh_skip_stale_bridges(self):
        _api, events = self.consent_fixture()
        fresh = []

        def replace(reason):
            events["bar"].append(reason)
            self.runtime.settings_material = SimpleNamespace(request=fresh.append, close=lambda: None)
            self.runtime.widgets["probe"] = SimpleNamespace(hide=lambda: None)
            self.runtime.widget_materials["probe"] = SimpleNamespace(request=fresh.append, close=lambda: None)

        self.runtime.top_bar.refresh_materials = replace
        self.runtime.controller.dataChanged.emit()
        self.app.processEvents()
        self.assertEqual(events, dict(bar=["composition_changed"], settings=[], widget=[]))
        self.assertEqual(fresh, [])


if __name__ == "__main__":
    unittest.main()
