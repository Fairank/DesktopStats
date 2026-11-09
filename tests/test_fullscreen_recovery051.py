"""Transient visibility-query recovery without CPU consent, Qt timers or DLLs."""

import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from fullscreen_guard import FullscreenGuard, WindowState
from top_bar_runtime import TopBarManager

import test_cpu_temperature_recovery051 as fixtures


class Timer:
    def __init__(self):
        self.active = False
        self.starts = 0

    def isActive(self):
        return self.active

    def start(self):
        self.active = True
        self.starts += 1

    def stop(self):
        self.active = False


class ForegroundRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No Windows API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch("threading.Thread.start", side_effect=AssertionError("No thread")))
        self.now = 10.
        self.api = fixtures.ForegroundApi()
        self.guard = FullscreenGuard(lambda: None, environ={}, api_factory=lambda: self.api,
                                     clock=lambda: self.now)
        self.addCleanup(self.guard.close)

    def test_caller_retry_marks_only_failed_queries_dirty_without_native_work(self):
        self.api.error = OSError("Synthetic foreground transition")
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), set(fixtures.MONITORS))
        queries = self.api.queries
        self.api.error = None
        for _ in range(50):
            self.assertFalse(self.guard.retry_failed_query())
            self.guard.blocked(fixtures.MONITORS)
        self.assertEqual(self.api.queries, queries)
        self.now += 2.
        self.assertTrue(self.guard.retry_failed_query())
        self.assertFalse(self.guard.retry_failed_query())  # Already queued/dirty.
        self.assertEqual(self.api.queries, queries)
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), set())
        self.assertIsNone(self.guard.failure)
        self.assertEqual(self.api.installs, 1)

    def test_exponential_retry_frequency_is_bounded_and_healthy_cache_stops_checks(self):
        self.api.error = OSError("Synthetic ongoing query failure")
        self.guard.blocked(fixtures.MONITORS)
        for delay in (2., 4., 8., 16., 30., 30.):
            queries = self.api.queries
            self.now += delay - .01
            for _ in range(30):
                self.assertFalse(self.guard.retry_failed_query())
            self.assertEqual(self.api.queries, queries)
            self.now += .01
            self.assertTrue(self.guard.retry_failed_query())
            self.assertEqual(self.api.queries, queries)
            self.guard.blocked(fixtures.MONITORS)
        self.api.error = None
        self.now += 30.
        self.assertTrue(self.guard.retry_failed_query())
        self.guard.blocked(fixtures.MONITORS)
        self.guard._clock = lambda: (_ for _ in ()).throw(AssertionError("Healthy cache needs no retry clock"))
        for _ in range(100):
            self.assertFalse(self.guard.retry_failed_query())

    def test_failed_refresh_keeps_game_on_other_display_until_a_safe_observation(self):
        self.api.windows[1] = WindowState(1, fixtures.A, fixtures.A,
                                        identity=(77, 1, "synthetic-game", 0))
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), {"A"})
        self.guard.invalidate()
        self.api.error = OSError("Synthetic foreground transition")
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), {"A"})
        self.api.error = None
        self.api.windows[2] = WindowState(2, (-1800, 20, -200, 900), fixtures.B,
                                        identity=(88, 2, "synthetic-window", 0))
        self.api.active = 2
        self.now += 2.
        self.assertTrue(self.guard.retry_failed_query())
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), {"A"})
        self.assertIn(1, self.guard._tracked)
        self.assertEqual(self.api.installs, 1)

    def test_hook_failure_never_reinstalls_or_retries_window_queries(self):
        self.guard.close()
        api = fixtures.ForegroundApi()
        def unavailable(callback):
            api.installs += 1
            raise OSError("Synthetic hook unavailable")
        api.install = unavailable
        self.guard = FullscreenGuard(lambda: None, environ={}, api_factory=lambda: api,
                                     clock=lambda: self.now)
        self.addCleanup(self.guard.close)
        self.assertEqual(self.guard.blocked(fixtures.MONITORS), set(fixtures.MONITORS))
        for _ in range(100):
            self.now += 30.
            self.assertFalse(self.guard.retry_failed_query())
        self.assertEqual(api.installs, 1)
        self.assertEqual(api.queries, 0)

    def test_clock_rollback_and_invalid_values_do_not_bypass_fail_closed_delay(self):
        self.api.error = OSError("Synthetic foreground transition")
        self.guard.blocked(fixtures.MONITORS)
        for value in (None, True, float("nan"), float("inf")):
            self.now = value
            self.assertFalse(self.guard.retry_failed_query())
        self.now = 3.
        self.assertFalse(self.guard.retry_failed_query())
        self.now = 4.99
        self.assertFalse(self.guard.retry_failed_query())
        self.now = 5.
        self.assertTrue(self.guard.retry_failed_query())
        self.assertEqual(self.api.queries, 1)

    def manager(self):
        m = NS(closed=False, paused=False, _fullscreen_guard=self.guard,
               _foreground_timer=Timer(), _rows_timer=Timer(),
               _foreground_hidden_screens=frozenset(), _fullscreen_guard_error=None,
               hosts={k: NS(closing=False, binding=NS(monitor=v), foreground_hidden=False,
                            state=NS(_host_id=k), material_bridge=None) for k, v in fixtures.MONITORS.items()})
        m._queue_foreground_visibility = lambda: TopBarManager._queue_foreground_visibility(m)
        m._read_foreground_visibility = lambda: TopBarManager._read_foreground_visibility(m)
        m.shown, m.hidden, m.recovered = [], [], []
        m.adapter = NS(show=lambda binding, **kw: m.shown.append(binding),
                       hide=lambda binding: m.hidden.append(binding))
        m._pending_hover = m._detail_request_host = m._panel = m._menu_host_id = None
        m._errors = []
        m._reported_status = ("active", "", ())
        m._status = lambda *args: None
        m._apply_host_visibility = lambda host, **kw: TopBarManager._apply_host_visibility(m, host, **kw)
        for host in m.hosts.values():
            host.material_bridge = NS(request=lambda reason: m.recovered.append(reason))
        return m

    def test_real_manager_reading_entry_recovers_hidden_bar_without_temperature_launcher(self):
        m = self.manager()
        shown, hidden, recovered = m.shown, m.hidden, m.recovered
        self.api.error = OSError("Synthetic transient read")
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, set(fixtures.MONITORS))
        self.assertEqual(len(hidden), 2)
        self.assertFalse(shown)
        self.api.error = None
        for _ in range(40):
            TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 0)
        self.assertEqual(self.api.queries, 1)
        self.now += 2.
        TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 1)
        self.assertEqual(self.api.queries, 1, "A reading signal only queues; it never queries windows")
        m._foreground_timer.stop()
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, set())
        self.assertIsNone(self.guard.failure)
        self.assertEqual(len(shown), 2)
        self.assertEqual(recovered, ["composition_changed", "composition_changed"])
        for _ in range(40):
            TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 1)
        self.assertEqual(self.api.queries, 2)

    def test_known_safe_desktop_cannot_authorize_visibility_after_query_failure(self):
        m = self.manager()
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, set())
        self.api.error = OSError("Synthetic query failed after a safe desktop")
        self.guard.invalidate()
        TopBarManager._foreground_visibility_changed(m)
        self.assertIsNotNone(self.guard.failure)
        self.assertEqual(self.guard._cached, set(), "Do not overwrite the guard's retained observation")
        self.assertEqual(m._foreground_hidden_screens, set(fixtures.MONITORS))
        self.assertEqual(len(m.hidden), 2)
        self.assertFalse(m.shown)
        self.api.error = None
        self.now += 2.
        TopBarManager.queue_rows(m)
        m._foreground_timer.stop()
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, set())
        self.assertEqual(len(m.shown), 2)
        self.assertEqual(m.recovered, ["composition_changed", "composition_changed"])
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(len(m.shown), 2)
        self.assertEqual(len(m.recovered), 2)

    def test_known_game_query_failure_hides_all_then_only_healthy_other_display_restores(self):
        m = self.manager()
        self.api.windows[1] = WindowState(1, fixtures.A, fixtures.A,
                                        identity=(77, 1, "synthetic-game", 0))
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, {"A"})
        self.api.error = OSError("Synthetic query failed while game is tracked")
        self.guard.invalidate()
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, set(fixtures.MONITORS))
        self.assertEqual(self.guard._cached, {"A"})
        self.assertIn(1, self.guard._tracked)
        self.api.error = None
        self.api.windows[2] = WindowState(2, (-1800, 20, -200, 900), fixtures.B,
                                        identity=(88, 2, "synthetic-window", 0))
        self.api.active = 2
        self.now += 2.
        TopBarManager.queue_rows(m)
        m._foreground_timer.stop()
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(m._foreground_hidden_screens, {"A"})
        self.assertIn(1, self.guard._tracked)
        self.assertEqual(m.shown, [m.hosts["B"].binding])
        self.assertEqual(m.recovered, ["composition_changed"])
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(len(m.shown), 1)

    def test_model_runtime_consumer_hides_every_current_target_on_cached_safe_query_failure(self):
        from native_runtime import _DesktopAwareTopBarManager
        m = self.manager()
        m.hosts = {}
        m._model_monitors = lambda: fixtures.MONITORS
        read = lambda: _DesktopAwareTopBarManager._read_foreground_visibility(m)
        read()
        self.assertEqual(m._foreground_hidden_screens, set())
        self.api.error = OSError("Synthetic model-target query failed")
        self.guard.invalidate()
        read()
        self.assertEqual(m._foreground_hidden_screens, set(fixtures.MONITORS))
        self.assertEqual(self.guard._cached, set())
        self.api.error = None
        self.now += 2.
        self.assertTrue(self.guard.retry_failed_query())
        read()
        self.assertEqual(m._foreground_hidden_screens, set())
        self.assertIsNone(self.guard.failure)

    def test_invalid_window_schema_fails_closed_and_disabled_or_closed_manager_never_shows(self):
        m = self.manager()
        TopBarManager._foreground_visibility_changed(m)
        self.api.windows[1] = WindowState(1, (0, 0, "invalid", 1000), fixtures.A)
        self.guard.invalidate()
        TopBarManager._foreground_visibility_changed(m)
        self.assertIsNotNone(self.guard.failure)
        self.assertEqual(m._foreground_hidden_screens, set(fixtures.MONITORS))
        self.assertEqual(len(m.hidden), 2)
        count = self.api.queries
        m.paused = True
        self.now += 2.
        TopBarManager.queue_rows(m)
        TopBarManager._foreground_visibility_changed(m)
        self.assertEqual(self.api.queries, count)
        self.assertFalse(m.shown)
        self.guard.close()
        m._fullscreen_guard = None
        m.hosts = {}
        TopBarManager.queue_rows(m)
        m.closed = True
        TopBarManager._foreground_visibility_changed(m)
        self.assertFalse(m.shown)
        self.assertFalse(m.recovered)

    def test_paused_or_closed_manager_does_not_queue_native_refresh_and_close_cancels_retry(self):
        m = self.manager()
        self.api.error = OSError("Synthetic read failure")
        m._read_foreground_visibility()
        self.now += 2.
        m.paused = True
        TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 0)
        m.closed = True
        self.guard.close()
        self.now += 100.
        TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 0)
        self.assertFalse(self.guard.retry_failed_query())
        self.assertEqual(self.api.queries, 1)

    def test_existing_model_only_guard_uses_its_existing_virtual_queue_while_bar_is_paused(self):
        from native_runtime import _DesktopAwareTopBarManager
        m = self.manager()
        m.paused = True
        m.hosts = {}
        m._model_monitors = lambda: fixtures.MONITORS
        m._queue_foreground_visibility = lambda: _DesktopAwareTopBarManager._queue_foreground_visibility(m)
        self.api.error = OSError("Synthetic model guard read failure")
        self.guard.blocked(fixtures.MONITORS)
        self.now += 2.
        TopBarManager.queue_rows(m)
        self.assertEqual(m._foreground_timer.starts, 1)
        self.assertEqual(m._rows_timer.starts, 0)
        self.assertEqual(self.api.queries, 1)


if __name__ == "__main__":
    unittest.main()
