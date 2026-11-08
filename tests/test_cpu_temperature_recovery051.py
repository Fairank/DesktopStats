"""Restart/deferred-consent recovery with synthetic clocks, windows and memory.

No native DLL, sensor getter, process, timer or application window is started.
These fixtures test recovery policy, never actual temperature availability.
"""

import copy
import struct
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cpu_temperature as thermal
import cpu_temperature_launcher as startup
from fullscreen_guard import FullscreenGuard, WindowState
from stats_config import DEFAULT


WALL = 1_700_000_000.0
A = (0, 0, 2560, 1440)
B = (-1920, 0, 0, 1080)
MONITORS = {"A": A, "B": B}


def config():
    value = copy.deepcopy(DEFAULT)
    value[startup.PREFERENCE] = True
    value["widgets"]["cpu"].update(enabled=True, primary="temp")
    return value


class ForegroundApi:
    def __init__(self):
        self.active = 1
        self.windows = {1: WindowState(1, A, A, desktop=True)}
        self.error = None
        self.installs = self.queries = self.closed = 0

    def install(self, callback):
        self.installs += 1
        return [101]

    def uninstall(self, handle):
        self.closed += 1
        return True

    def foreground(self):
        self.queries += 1
        if self.error:
            raise self.error
        return self.active

    def window(self, hwnd):
        return self.windows.get(hwnd)


class Manager:
    def __init__(self, guard, *, shell=False):
        self._fullscreen_guard = guard
        self._foreground_hidden_screens = frozenset()
        self._fullscreen_guard_error = None
        self.shell = shell

    def _fullscreen_active(self):
        return self.shell

    def _read_foreground_visibility(self):
        self._foreground_hidden_screens = self._fullscreen_guard.blocked(MONITORS)


class ConsentApi:
    def __init__(self):
        self.calls = []
        self.on_verify = None
        self.result = dict(launched=True, error=0)

    def verify_process(self, expected, pid):
        self.calls.append(("process", pid))
        if self.on_verify:
            self.on_verify()

    @contextmanager
    def verified_helper(self, helper, digest):
        self.calls.append(("lock",))
        try:
            yield
        finally:
            self.calls.append(("unlock",))

    def launch(self, helper, pid):
        self.calls.append(("launch", pid))
        return dict(self.result)

    def close(self):
        self.calls.append(("close",))


class NoNativeTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native DLL")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch("threading.Thread.start", side_effect=AssertionError("No worker")))


class GuardRecoveryTests(NoNativeTests):
    def setUp(self):
        super().setUp()
        self.api = ForegroundApi()
        self.guard = FullscreenGuard(lambda: None, environ={}, api_factory=lambda: self.api)
        self.addCleanup(self.guard.close)
        self.manager = Manager(self.guard)

    def observe(self, **kwargs):
        return startup.foreground_fullscreen(self.manager, api_factory=lambda: self.api,
                                            desktop_ready=lambda: True, **kwargs)

    def test_stale_shell_notification_does_not_override_verified_desktop(self):
        self.manager.shell = True
        self.assertIs(self.observe(), False)
        self.assertTrue(self.guard._known)
        self.assertEqual(self.api.installs, 1)
        # The shell notice can remain stuck; recovery needs neither hook restart
        # nor clearing the shared guard's tracked windows.
        self.assertIs(self.observe(), False)
        self.assertEqual(self.api.installs, 1)

    def test_temporary_query_failure_recovers_without_a_new_window_event(self):
        self.api.error = OSError("Synthetic foreground transition")
        self.assertIsNone(self.observe())
        self.assertIsNotNone(self.guard.failure)
        reads = self.api.queries
        self.api.error = None
        # The guard alone correctly retains its conservative cached failure.
        self.guard.blocked(MONITORS)
        self.assertEqual(self.api.queries, reads)
        self.assertIs(self.observe(), False)
        self.assertIsNone(self.guard.failure)
        self.assertEqual(self.api.installs, 1)

    def test_refresh_preserves_a_game_on_the_other_display(self):
        self.api.windows[1] = WindowState(1, A, A, identity=(77, 1, "synthetic-game", 0))
        self.assertIs(self.observe(), True)
        self.api.windows[2] = WindowState(2, (-1800, 50, -300, 900), B,
                                        identity=(88, 2, "synthetic-window", 0))
        self.api.active = 2
        self.manager.shell = True
        self.api.error = OSError("Synthetic transition after an observed game")
        self.assertIsNone(self.observe())
        self.assertIn(1, self.guard._tracked)
        self.api.error = None
        for _ in range(3):
            self.assertIs(self.observe(), True)
            self.assertEqual(self.manager._foreground_hidden_screens, {"A"})
            self.assertIn(1, self.guard._tracked)
        self.assertEqual(self.api.installs, 1)

    def test_unknown_input_desktop_prevents_all_foreground_and_guard_work(self):
        def forbidden():
            raise AssertionError("No foreground work on an unknown input desktop")

        for value in (False, None, 1, "Default"):
            with self.subTest(value=value):
                self.assertIsNone(startup.foreground_fullscreen(
                    self.manager, api_factory=forbidden, desktop_ready=lambda: value))
        def unavailable():
            raise OSError("Synthetic secure desktop transition")
        self.assertIsNone(startup.foreground_fullscreen(
            self.manager, api_factory=forbidden, desktop_ready=unavailable))
        self.assertEqual(self.api.queries, 0)
        self.assertEqual(self.api.installs, 0)


class ConsentRecoveryTests(NoNativeTests):
    def setUp(self):
        super().setUp()
        self.now = 10.0
        self.api = ConsentApi()
        self.local = Path(tempfile.gettempdir()) / "synthetic-recovery051"
        self.fact = True
        self.observations = 0
        self.launcher = self.new_launcher()
        self.addCleanup(self.launcher.close)

    def new_launcher(self, pid=731):
        return startup.CpuTemperatureLauncher(
            platform="win32", frozen=True,
            executable=self.local / "Programs/DesktopStats/DesktopStats.exe",
            environ={"LOCALAPPDATA": str(self.local)}, app_pid=pid,
            api_factory=lambda: self.api, wall_clock=lambda: WALL,
            clock=lambda: self.now)

    def observe(self):
        self.observations += 1
        return self.fact

    def update(self):
        return self.launcher.update(config(), dict(time=WALL), fullscreen=self.observe)

    def test_deferred_callbacks_are_bounded_then_resume_once_after_unlock(self):
        self.assertEqual(self.update()["reason"], "fullscreen")
        for i in range(1, 200):
            self.now = 10.0 + i * .01
            self.update()
        self.assertEqual(self.observations, 1)
        self.assertFalse(self.api.calls)
        self.assertFalse(self.launcher.status()["attempted"])
        self.now = 10.0 + startup.FOREGROUND_RETRY_SECONDS
        self.fact = False
        self.assertEqual(self.update()["state"], "launched")
        self.assertEqual(self.observations, 3)  # Resume plus final consent check.
        calls = list(self.api.calls)
        for i in range(500):
            self.now += .5
            self.update()
        self.assertEqual(self.observations, 3)
        self.assertEqual(self.api.calls, calls)

    def test_throttled_unknown_desktop_can_recover_after_clock_rollback(self):
        self.fact = None
        self.assertEqual(self.update()["reason"], "foreground_unknown")
        self.now = 2.0
        self.fact = False
        self.assertEqual(self.update()["state"], "launched")
        self.assertEqual(self.observations, 3)

    def test_invalid_clock_never_authorizes_or_queries_native_state(self):
        self.fact = False
        for value in (float("nan"), float("inf"), -float("inf"), True, None):
            self.now = value
            self.assertEqual(self.update()["reason"], "foreground_unknown")
        self.assertEqual(self.observations, 0)
        self.assertFalse(self.api.calls)
        self.assertFalse(self.launcher.status()["attempted"])

    def test_failed_foreground_callback_stays_bounded_and_can_recover(self):
        calls = []
        def unavailable():
            calls.append(True)
            raise OSError("Synthetic input desktop transition")
        self.assertEqual(self.launcher.update(config(), dict(time=WALL),
                                             fullscreen=unavailable)["reason"], "foreground_unknown")
        for _ in range(30):
            self.launcher.update(config(), dict(time=WALL), fullscreen=unavailable)
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.api.calls)
        self.fact = False
        self.now += startup.FOREGROUND_RETRY_SECONDS
        self.assertEqual(self.update()["state"], "launched")
        self.assertEqual(self.observations, 2)

    def test_game_or_secure_desktop_arriving_during_preflight_defers_consent(self):
        for arrived in (True, None):
            with self.subTest(arrived=arrived):
                self.api = ConsentApi()
                self.fact = False
                launcher = self.new_launcher()
                self.addCleanup(launcher.close)
                self.api.on_verify = lambda: setattr(self, "fact", arrived)
                result = launcher.update(config(), dict(time=WALL), fullscreen=self.observe)
                self.assertEqual(result["state"], "deferred")
                self.assertFalse(result["attempted"])
                self.assertEqual([row[0] for row in self.api.calls], ["process", "lock", "unlock"])
                self.api.on_verify = None
                self.fact = False
                self.now += startup.FOREGROUND_RETRY_SECONDS
                self.assertEqual(launcher.update(config(), dict(time=WALL),
                                                 fullscreen=self.observe)["state"], "launched")
                self.assertEqual(sum(row[0] == "launch" for row in self.api.calls), 1)

    def test_close_during_initial_or_final_foreground_check_never_launches(self):
        for close_at in (1, 2):
            with self.subTest(close_at=close_at):
                self.api = ConsentApi()
                launcher = self.new_launcher()
                count = 0
                def observe():
                    nonlocal count
                    count += 1
                    if count == close_at:
                        launcher.close()
                    return False
                result = launcher.update(config(), dict(time=WALL), fullscreen=observe)
                self.assertEqual(result["state"], "closed")
                self.assertFalse(result["attempted"])
                self.assertFalse(any(row[0] == "launch" for row in self.api.calls))
                self.assertEqual(launcher.update(config(), {}, fullscreen=observe), result)
                self.assertEqual(count, close_at)

    def test_cancel_is_terminal_but_restarted_pid_gets_its_own_single_consent(self):
        self.api.result = dict(launched=False, error=1223)
        self.fact = False
        self.assertEqual(self.update()["state"], "cancelled")
        self.launcher.close()
        self.launcher = self.new_launcher(pid=742)
        self.api.result = dict(launched=True, error=0)
        self.assertEqual(self.update()["state"], "launched")
        for _ in range(40):
            self.update()
        self.assertEqual([row for row in self.api.calls if row[0] == "launch"],
                         [("launch", 731), ("launch", 742)])

    def test_runtime_passes_input_desktop_gate_and_closes_without_late_consent(self):
        import native_runtime as runtime
        ready = [None]
        api = ForegroundApi()
        obj = SimpleNamespace(shutting_down=False, cpu_temperature_launcher=self.launcher,
                              top_bar=None, controller=SimpleNamespace(_saved=config(), _data=dict(time=WALL)))
        queued = []
        with patch.object(runtime, "_desktop_session_ready", lambda: ready[0]), \
                patch("fullscreen_guard._NativeApi", lambda: api), \
                patch.object(runtime.QTimer, "singleShot", lambda delay, callback: queued.append(callback)):
            runtime.Runtime.maybe_start_cpu_temperature(obj)
            self.assertEqual(self.launcher.status()["reason"], "foreground_unknown")
            self.assertEqual(api.queries, 0)
            ready[0] = True
            self.now += startup.FOREGROUND_RETRY_SECONDS
            runtime.Runtime.maybe_start_cpu_temperature(obj)
            self.assertEqual(self.launcher.status()["state"], "launched")
            self.assertEqual(api.queries, 2)
            self.assertEqual(len(queued), 1)
            obj.shutting_down = True
            runtime.Runtime.maybe_start_cpu_temperature(obj)
            self.assertEqual(len(queued), 1)


class ReaderSessionTests(NoNativeTests):
    def test_closed_or_previous_pid_snapshot_is_rejected_then_current_session_recovers(self):
        clock = [10.0]
        payload = [b""]
        closes = []
        def snapshot(*, state=1, pid=742):
            return struct.pack("<7IiqI20x", thermal.MAGIC, 1, 2, state, 456,
                               thermal.SENSOR_ID, 485 if state == 1 else 0, 0,
                               int(WALL * 1000), pid)
        memory = SimpleNamespace(read=lambda: payload[0], close=lambda: closes.append(True))
        sensor = thermal.AsusCpuTemperature(api=memory, app_pid=742, enabled=True,
                                           clock=lambda: clock[0], wall_clock=lambda: WALL)
        self.addCleanup(sensor.close)
        for fields, state, value in ((dict(state=3), "closed", {}),
                                     (dict(pid=731), "invalid_value", {}),
                                     ({}, "ready", {"cpu_temp": 48.5, "cpu_temp_source": thermal.SOURCE})):
            payload[0] = snapshot(**fields)
            self.assertEqual(sensor.read(), value)
            self.assertEqual(sensor.state, state)
            clock[0] += thermal.INTERVAL
        self.assertTrue(closes)
        sensor.close()
        memory.read = lambda: (_ for _ in ()).throw(AssertionError("No reads after session exit"))
        self.assertEqual(sensor.read(), {})


if __name__ == "__main__":
    unittest.main()
