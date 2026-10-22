"""Only owned offscreen QWindows, fake composition/policy, no native API calls."""

import ctypes
import os
import threading
import unittest
from ctypes import wintypes
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread, Signal
from PySide6.QtGui import QExposeEvent, QRegion, QWindow
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from settings_material_bridge import SettingsMaterialBridge

GOOD = dict(material="desktop-acrylic", status="configured-unverified", backdrop_result=0,
            backdrop_type=3, compositing_verified=False)
FAILED = dict(material="solid", status="fallback", fallback_reason="frame-extension-failed")


class Clock:
    now = 100.

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class OffscreenWindow(QWindow):
    sceneGraphInitialized = Signal()

    def __init__(self):
        super().__init__()
        self.winid_calls = 0

    def winId(self):
        self.winid_calls += 1
        return super().winId()


class ControlledQuickSurface(OffscreenWindow):
    """Owned offscreen surface, independently controlled renderer milestones."""

    frameSwapped = Signal()
    sceneGraphInvalidated = Signal()

    def __init__(self):
        super().__init__()
        self.exposed = False
        self.initialized = False
        self.update_calls = 0

    def isSceneGraphInitialized(self):
        return self.initialized

    def isExposed(self):
        return self.exposed

    def update(self):
        self.update_calls += 1


class SettingsMaterialBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "No real Windows desktop tests"

    def setUp(self):
        self.clock = Clock()
        self.window = OffscreenWindow()
        self.compose = Mock(return_value=dict(GOOD))
        self.policy = Mock(return_value=dict(state="allowed", reason="allowed"))
        self.publish = Mock()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
                                             policy_reader=self.policy, publish=self.publish,
                                             clock=self.clock)
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def show(self):
        self.window.show()  # Asserted offscreen; never a visible Windows window.
        self.app.processEvents()
        self.assertGreater(self.bridge.status()["handle"], 0)

    def due(self, seconds=.15):
        self.clock.advance(seconds)
        self.bridge._on_timeout()

    def test_start_on_hidden_window_never_forces_native_handle_or_composition(self):
        self.assertEqual(self.window.winid_calls, 0)
        self.assertEqual(self.bridge.status()["handle"], 0)
        self.assertFalse(self.bridge.status()["native_filter_installed"])
        self.assertIsNone(self.bridge.compose_now())
        self.assertFalse(self.bridge.status()["timer_active"])
        self.assertEqual(self.window.winid_calls, 0)
        self.compose.assert_not_called()

    def test_owned_show_activate_events_coalesce_to_one_call(self):
        self.show()
        self.clock.advance(.1)
        QCoreApplication.sendEvent(self.window, QEvent(QEvent.WindowActivate))
        QCoreApplication.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
        self.compose.assert_not_called()
        self.due()
        self.compose.assert_called_once()
        self.publish.assert_called_once()
        self.assertFalse(self.bridge.status()["timer_active"])
        self.assertFalse(self.publish.call_args.args[0]["compositing_verified"])

    def test_compose_now_passes_one_exact_policy_snapshot_and_publishes_metadata(self):
        self.show()
        self.policy.return_value = dict(state="allowed", reason="allowed", winerror=0)
        before = self.policy.call_count
        report = self.bridge.compose_now("apply")
        self.assertEqual(self.policy.call_count, before + 1)
        self.assertEqual(self.compose.call_args.args, (self.bridge.status()["handle"], self.policy.return_value))
        self.assertEqual(report["policy"]["winerror"], 0)
        self.assertEqual(report["lifecycle"]["state"], "configured_unverified")
        self.assertEqual(report["lifecycle"]["last_request"]["reasons"], ["explicit:apply"])

    def test_hide_drops_pending_timer_and_show_starts_fresh(self):
        self.show()
        self.window.hide()
        self.app.processEvents()
        self.assertFalse(self.bridge.status()["timer_active"])
        self.due(10)
        self.compose.assert_not_called()
        self.show()
        self.due()
        self.compose.assert_called_once()

    def test_minimize_suspends_and_restore_reschedules(self):
        self.show()
        self.window.setWindowState(Qt.WindowMinimized)
        self.app.processEvents()
        self.assertEqual(self.bridge.status()["window_state"], "minimized")
        self.assertFalse(self.bridge.status()["timer_active"])
        self.due(10)
        self.compose.assert_not_called()
        self.window.setWindowState(Qt.WindowNoState)
        self.app.processEvents()
        self.due()
        self.compose.assert_called_once()

    def test_destroy_during_callback_cannot_publish_old_hwnd_result(self):
        self.show()
        previous = self.bridge.status()["generation"]

        def destroy(_handle, _policy):
            self.window.destroy()
            return dict(GOOD)

        self.compose.side_effect = destroy
        self.assertIsNone(self.bridge.compose_now())
        self.publish.assert_not_called()
        self.assertEqual(self.bridge.status()["handle"], 0)
        self.assertGreater(self.bridge.status()["generation"], previous)
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_recreated_native_surface_gets_new_generation(self):
        self.show()
        first = self.bridge.compose_now()
        self.window.destroy()
        self.show()
        self.due()
        last = self.publish.call_args.args[0]
        self.assertGreater(last["lifecycle"]["generation"], first["lifecycle"]["generation"])
        self.assertEqual(self.compose.call_count, 2)

    def test_exception_recovery_is_bounded_and_same_policy_poll_does_not_restart(self):
        self.show()
        self.compose.side_effect = OSError("Synthetic backend failure")
        self.bridge.compose_now()
        self.assertEqual(self.bridge.status()["state"], "retry_wait")
        self.due(.25)
        self.due(1)
        self.assertEqual(self.compose.call_count, 3)
        self.assertEqual(self.bridge.status()["state"], "exhausted")
        for _ in range(20):
            self.assertFalse(self.bridge.refresh_policy())
        self.due(100)
        self.assertEqual(self.compose.call_count, 3)
        self.assertFalse(self.bridge.status()["timer_active"])
        self.assertIn("Synthetic backend failure", self.bridge.status()["last_report"]["backend_error"])

    def test_disabled_policy_cleanup_once_and_reenable_restores(self):
        self.show()
        self.bridge.compose_now()
        self.policy.return_value = dict(state="disabled", reason="high-contrast")
        self.compose.return_value = dict(FAILED)
        self.assertTrue(self.bridge.refresh_policy())
        self.due()
        self.assertEqual(self.bridge.status()["state"], "policy_disabled")
        self.assertFalse(self.bridge.request("activated"))
        self.assertFalse(self.bridge.status()["timer_active"])
        self.policy.return_value = dict(state="allowed", reason="allowed")
        self.compose.return_value = dict(GOOD)
        self.bridge.refresh_policy()
        self.due()
        self.assertEqual(self.bridge.status()["state"], "configured_unverified")

    def test_unknown_policy_read_is_reported_and_can_recover(self):
        self.show()
        self.policy.side_effect = OSError("Synthetic policy failure")
        self.compose.return_value = dict(FAILED)
        report = self.bridge.compose_now()
        self.assertEqual(report["policy"]["state"], "unknown")
        self.assertIn("Synthetic policy failure", report["policy"]["error"])
        self.assertEqual(self.bridge.status()["state"], "retry_wait")
        self.policy.side_effect = None
        self.compose.return_value = dict(GOOD)
        self.bridge.refresh_policy()
        self.due()
        self.assertEqual(self.bridge.status()["state"], "configured_unverified")

    def test_regular_resize_move_and_unknown_events_do_not_read_policy_or_apply(self):
        self.show()
        self.bridge.compose_now()
        calls = self.policy.call_count
        for _ in range(20):
            self.window.resize(400, 300)
            for reason in ("move", "resize", "sample"):
                self.assertFalse(self.bridge.request(reason))
        self.app.processEvents()
        self.assertEqual(self.policy.call_count, calls)
        self.assertEqual(self.compose.call_count, 1)
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_native_notification_is_own_hwnd_only_and_never_consumed(self):
        self.show()
        self.bridge.compose_now()
        msg = wintypes.MSG()
        msg.hWnd = self.bridge.status()["handle"] + 100
        msg.message = 0x031A
        self.assertEqual(self.bridge._native.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)), (False, 0))
        self.assertFalse(self.bridge.status()["timer_active"])
        msg.hWnd = self.bridge.status()["handle"]
        self.assertEqual(self.bridge._native.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg)), (False, 0))
        self.assertTrue(self.bridge.status()["timer_active"])
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge._native.nativeEventFilter(b"windows_generic_MSG", 0), (False, 0))

    def test_queued_graphics_signal_returns_to_gui_thread(self):
        self.show()
        self.bridge.compose_now()
        threads = []
        self.policy.side_effect = lambda: (threads.append(QThread.currentThread()), dict(state="allowed"))[1]
        worker = threading.Thread(target=self.window.sceneGraphInitialized.emit)
        worker.start()
        worker.join()
        self.assertEqual(threads, [])
        self.app.processEvents()
        self.assertEqual(threads, [self.window.thread()])
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_close_disconnects_late_events_and_cancels_timer(self):
        self.show()
        self.bridge.close()
        self.bridge.close()
        self.window.sceneGraphInitialized.emit()
        QCoreApplication.sendEvent(self.window, QEvent(QEvent.WindowActivate))
        self.app.processEvents()
        self.assertFalse(self.bridge.request("shown"))
        self.assertFalse(self.bridge.refresh_policy())
        self.assertIsNone(self.bridge.compose_now())
        self.compose.assert_not_called()
        self.assertEqual(self.bridge.status()["state"], "closed")
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_reentrant_material_notifications_do_not_schedule_feedback_loop(self):
        self.show()

        def compose(_handle, _policy):
            self.bridge.request('composition_changed')
            self.bridge.compose_now('nested')
            return dict(GOOD)

        self.compose.side_effect = compose
        self.bridge.compose_now()
        self.assertEqual(self.compose.call_count, 1)
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_publish_failure_is_bounded_diagnostic_and_not_native_retry(self):
        self.show()
        self.publish.side_effect = RuntimeError('Synthetic publication failure')
        with self.assertLogs(level='WARNING'):
            result = self.bridge.compose_now()
        self.assertIsNotNone(result)
        self.assertIn('Synthetic publication failure', self.bridge.status()['publish_error'])
        self.assertFalse(self.bridge.status()['timer_active'])
        self.assertEqual(self.compose.call_count, 1)

    def test_real_single_shot_timer_offscreen_executes_once(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
                                             policy_reader=self.policy, publish=self.publish)
        self.bridge.start()
        self.show()
        for _ in range(35):
            if self.compose.called:
                break
            QTest.qWait(10)
        self.compose.assert_called_once()
        self.publish.assert_called_once()
        QTest.qWait(200)
        self.compose.assert_called_once()

    def system_bridge(self, release=None):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            backend='system-blur', release_surface=release)
        self.bridge.start()

    def test_system_backend_configured_once_without_dwm_retry(self):
        self.system_bridge()
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified', coating_translucent=True)
        self.show()
        result = self.bridge.compose_now()
        self.assertEqual(result['lifecycle']['backend'], 'system-blur')
        self.assertEqual(result['lifecycle']['state'], 'configured_unverified')
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_precreated_hidden_surface_is_adopted_on_show_without_hidden_probe(self):
        self.bridge.close()
        existing = int(self.window.winId())  # Own offscreen surface, deliberately before bridge start.
        calls_before_start = self.window.winid_calls
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified')
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock, backend='system-blur')
        self.bridge.start()
        self.assertFalse(self.window.isVisible())
        self.assertEqual(self.window.winid_calls, calls_before_start)
        self.assertEqual(self.bridge.status()['handle'], 0)
        self.show()
        self.assertEqual(self.bridge.status()['handle'], existing)
        self.due()
        self.compose.assert_called_once_with(existing, self.policy.return_value)
        self.assertEqual(self.bridge.status()['state'], 'configured_unverified')

    def test_repeated_hide_show_of_same_surface_does_not_duplicate_release(self):
        release = Mock(return_value=dict(ok=True, noop=True, cleanup_complete=True))
        self.system_bridge(release)
        self.show()
        first_handle = self.bridge.status()['handle']
        self.window.hide()
        self.show()
        self.assertEqual(self.bridge.status()['handle'], first_handle)
        self.bridge.close()
        self.window.destroy()
        self.assertEqual(release.call_count, 1)

    def test_release_runs_before_handle_clear_and_invalidates_inflight_report(self):
        released = []

        def release(handle):
            released.append(handle)
            self.assertEqual(self.bridge._handle, handle)
            self.assertFalse(self.bridge.status()['in_flight'])
            self.assertIsNone(self.bridge.compose_now('reentrant-release'))
            return dict(ok=True, bool_result=1, cleanup_complete=True)

        self.system_bridge(release)
        self.show()
        handle = self.bridge.status()['handle']
        self.compose.side_effect = lambda *_: (self.window.destroy(), dict(GOOD))[1]
        self.assertIsNone(self.bridge.compose_now())
        self.assertEqual(released, [handle])
        self.assertEqual(self.bridge.status()['handle'], 0)
        self.assertEqual(self.bridge.status()['release_count'], 1)
        self.publish.assert_not_called()
        self.bridge.close()
        self.assertEqual(released, [handle])

    def test_close_releases_once_after_cancellation_and_preserves_return_report(self):
        release = Mock()

        def clear(handle):
            self.assertTrue(self.bridge.status()['closed'])
            self.assertFalse(self.bridge.status()['timer_active'])
            return dict(ok=False, bool_result=0, last_error=5, blur_may_remain=True, status='cleanup-failed')

        release.side_effect = clear
        self.system_bridge(release)
        self.show()
        handle = self.bridge.status()['handle']
        self.bridge.close()
        self.bridge.close()
        self.window.destroy()
        release.assert_called_once_with(handle)
        self.assertEqual(self.bridge.status()['release_report']['last_error'], 5)
        self.assertTrue(self.bridge.status()['release_report']['blur_may_remain'])

    def test_release_exception_does_not_skip_timer_or_filter_cleanup(self):
        release = Mock(side_effect=RuntimeError('x' * 3000))
        self.system_bridge(release)
        self.show()
        app = Mock()
        self.bridge._native_installed = True  # Simulated registration, never installed in Windows.
        with patch('settings_material_bridge.QGuiApplication.instance', return_value=app), \
             patch.object(self.window, 'removeEventFilter', wraps=self.window.removeEventFilter) as remove, \
             self.assertLogs(level='WARNING'):
            self.bridge.close()
        app.removeNativeEventFilter.assert_called_once_with(self.bridge._native)
        remove.assert_called_once_with(self.bridge)
        self.assertEqual(len(self.bridge.status()['release_error']), 512)
        self.assertFalse(self.bridge.status()['native_filter_installed'])
        self.assertFalse(self.bridge.status()['timer_active'])
        self.window.destroy()
        self.assertEqual(release.call_count, 1)

    def test_recreated_surface_can_release_again_even_if_windows_reuses_handle(self):
        release = Mock(return_value=dict(ok=True, noop=True, cleanup_complete=True))
        self.system_bridge(release)
        self.show()
        self.window.destroy()
        self.show()
        self.window.destroy()
        self.assertEqual(release.call_count, 2)
        self.assertEqual(self.bridge.status()['release_count'], 2)

    def test_qobject_destroy_notification_never_looks_up_or_clears_stale_handle(self):
        release = Mock()
        self.system_bridge(release)
        self.show()
        winid_calls = self.window.winid_calls
        # Simulate the final notification after an already missing native
        # surface. It is too late for native cleanup; never recreate the HWND.
        self.bridge._window_destroyed()
        self.assertEqual(self.window.winid_calls, winid_calls)
        release.assert_not_called()
        self.assertEqual(self.bridge.status()['handle'], 0)
        self.assertTrue(self.bridge.status()['closed'])

    def test_never_shown_window_has_no_surface_to_release(self):
        release = Mock()
        self.system_bridge(release)
        self.bridge.close()
        release.assert_not_called()
        self.assertEqual(self.window.winid_calls, 0)

    def test_release_callback_must_be_callable(self):
        with self.assertRaises(ValueError):
            SettingsMaterialBridge(self.window, compose_once=self.compose, policy_reader=self.policy,
                publish=self.publish, release_surface=True)


class FirstFrameMaterialBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == 'offscreen', 'No real Windows desktop tests'

    def setUp(self):
        self.clock = Clock()
        self.window = ControlledQuickSurface()
        self.window.resize(420, 280)
        self.compose = Mock(return_value=dict(GOOD))
        self.policy = Mock(return_value=dict(state='allowed', reason='allowed'))
        self.publish = Mock()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock)
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def pump(self):
        for _ in range(4):
            self.app.processEvents()

    def due(self, seconds=.15):
        self.clock.advance(seconds)
        self.bridge._on_timeout()

    def show_exposed(self):
        self.window.show()
        self.pump()
        self.window.exposed = True
        QCoreApplication.sendEvent(self.window, QExposeEvent(QRegion()))
        self.pump()

    def submit_frame(self):
        self.window.initialized = True
        self.window.sceneGraphInitialized.emit()
        self.window.frameSwapped.emit()
        self.pump()

    def test_show_hwnd_and_scenegraph_success_are_not_first_frame_readiness(self):
        self.window.show()
        self.pump()
        self.assertGreater(self.bridge.status()['handle'], 0)
        self.assertIsNone(self.bridge.compose_now('first-show'))
        self.window.initialized = True
        self.window.sceneGraphInitialized.emit()
        self.pump()
        self.due(20)
        self.compose.assert_not_called()
        self.assertEqual(self.bridge.status()['state'], 'waiting_for_render')
        self.assertEqual(self.bridge.status()['applies_total'], 0)
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_first_exposed_frame_and_bounded_settlement_need_no_resize_or_focus(self):
        self.show_exposed()
        original = self.window.geometry()
        self.window.initialized = True
        self.window.sceneGraphInitialized.emit()
        self.pump()
        self.due(10)
        self.compose.assert_not_called()
        self.window.frameSwapped.emit()
        self.pump()
        self.assertTrue(self.bridge.status()['first_frame_observed'])
        self.assertTrue(self.bridge.status()['render_ready'])
        self.compose.assert_not_called()
        self.due()
        self.compose.assert_called_once()
        self.assertEqual(self.window.geometry(), original)
        self.assertEqual(self.bridge.status()['state'], 'settle_wait')
        self.assertFalse(self.publish.call_args.args[0]['compositing_verified'])
        self.assertEqual(self.window.update_calls, 2)
        self.due(.25)
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge.status()['state'], 'configured_unverified')
        self.assertFalse(self.bridge.status()['timer_active'])
        self.assertEqual(self.window.geometry(), original)
        self.assertIn('render_settle', self.publish.call_args.args[0]['lifecycle']['last_request']['reasons'])

    def test_frame_notice_while_graphics_uninitialized_is_not_reused_on_initialization(self):
        self.show_exposed()
        self.window.frameSwapped.emit()
        self.pump()
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.window.initialized = True
        self.window.sceneGraphInitialized.emit()
        self.pump()
        self.due(5)
        self.compose.assert_not_called()
        self.window.frameSwapped.emit()
        self.pump()
        self.due()
        self.compose.assert_called_once()

    def test_every_frame_and_repeat_expose_do_not_become_material_polling(self):
        self.show_exposed()
        self.submit_frame()
        self.due()
        before = self.policy.call_count
        for _ in range(100):
            self.window.frameSwapped.emit()
            QCoreApplication.sendEvent(self.window, QExposeEvent(QRegion()))
        self.pump()
        self.due(20)
        self.assertEqual(self.compose.call_count, 2)  # Initial + one settlement.
        # One deliberate due() context check; no policy IO for 100 frames.
        self.assertEqual(self.policy.call_count, before + 1)
        self.assertEqual(self.window.update_calls, 2)
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_settlement_frame_request_reentrant_hide_rejects_old_publication(self):
        self.show_exposed()
        self.submit_frame()
        self.window.update = self.window.hide
        self.due()
        self.publish.assert_not_called()
        self.assertEqual(self.bridge.status()['state'], 'paused')
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_settlement_frame_request_error_keeps_finite_timer_armed(self):
        self.show_exposed()
        self.submit_frame()
        self.window.update = Mock(side_effect=RuntimeError('surface unavailable'))
        self.due()
        self.assertTrue(self.bridge.status()['timer_active'])
        self.assertEqual(self.publish.call_args.args[0]['render_update_error'], 'surface unavailable')
        self.due(.25)
        self.assertEqual(self.compose.call_count, 2)
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_unexposed_restore_requires_new_frame_even_with_same_hwnd(self):
        self.show_exposed()
        self.submit_frame()
        self.due()
        handle = self.bridge.status()['handle']
        self.window.exposed = False
        QCoreApplication.sendEvent(self.window, QExposeEvent(QRegion()))
        self.due(5)
        self.assertEqual(self.bridge.status()['state'], 'waiting_for_render')
        self.window.exposed = True
        QCoreApplication.sendEvent(self.window, QExposeEvent(QRegion()))
        self.due(5)
        self.compose.assert_called_once()
        self.submit_frame()
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge.status()['handle'], handle)
        self.assertEqual(self.window.update_calls, 4)

    def test_minimize_restore_drops_old_frame_notice_and_waits_again(self):
        self.show_exposed()
        self.submit_frame()
        self.due()
        previous = self.bridge.status()['render_epoch']
        self.window.setWindowState(Qt.WindowMinimized)
        self.pump()
        self.window.setWindowState(Qt.WindowNoState)
        self.pump()
        self.bridge._render_event(previous, 'first_frame')
        self.due(5)
        self.compose.assert_called_once()
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.submit_frame()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_queued_pre_hide_frame_cannot_enable_new_show(self):
        self.show_exposed()
        self.window.initialized = True
        self.window.frameSwapped.emit()  # Queued GUI delivery deliberately delayed.
        old_epoch = self.bridge.status()['render_epoch']
        self.window.hide()
        self.window.show()
        self.pump()
        self.assertGreater(self.bridge.status()['render_epoch'], old_epoch)
        self.due(5)
        self.compose.assert_not_called()
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.submit_frame()
        self.due()
        self.compose.assert_called_once()

    def test_graphics_invalidation_cancels_pending_and_needs_new_scene_frame(self):
        self.show_exposed()
        self.submit_frame()
        self.due()
        self.window.initialized = False
        self.window.sceneGraphInvalidated.emit()
        self.pump()
        self.assertFalse(self.bridge.status()['render_ready'])
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.due(5)
        self.compose.assert_called_once()
        self.submit_frame()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_failed_native_request_keeps_existing_three_attempt_budget_after_frame(self):
        self.show_exposed()
        self.submit_frame()
        self.compose.return_value = dict(FAILED)
        for delay in (.15, .25, 1):
            self.due(delay)
            self.window.frameSwapped.emit()
            self.pump()
        self.assertEqual(self.compose.call_count, 3)
        self.assertEqual(self.bridge.status()['state'], 'exhausted')
        self.due(100)
        self.assertEqual(self.compose.call_count, 3)
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_render_thread_emits_queued_metadata_and_never_native_or_policy_calls(self):
        self.show_exposed()
        self.window.initialized = True
        before = self.policy.call_count
        worker = threading.Thread(target=self.window.frameSwapped.emit)
        worker.start()
        worker.join()
        self.compose.assert_not_called()
        self.assertEqual(self.policy.call_count, before)
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.pump()
        self.assertTrue(self.bridge.status()['first_frame_observed'])
        threads = []
        self.compose.side_effect = lambda *_: (threads.append(QThread.currentThread()), dict(GOOD))[1]
        self.due()
        self.assertEqual(threads, [self.window.thread()])

    def test_policy_disabled_clears_before_frame_and_reenable_waits_for_frame(self):
        self.show_exposed()
        self.policy.return_value = dict(state='disabled', reason='high-contrast')
        self.compose.return_value = dict(FAILED)
        result = self.bridge.compose_now('policy-cleanup')
        self.assertEqual(result['lifecycle']['state'], 'policy_disabled')
        self.policy.return_value = dict(state='allowed')
        self.bridge.refresh_policy()
        self.due(5)
        self.compose.assert_called_once()
        self.compose.return_value = dict(GOOD)
        self.submit_frame()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_close_drops_late_render_signals_without_lookup_or_call(self):
        self.show_exposed()
        self.window.initialized = True
        self.window.frameSwapped.emit()
        self.bridge.close()
        calls = self.window.winid_calls
        self.pump()
        self.window.sceneGraphInitialized.emit()
        self.window.sceneGraphInvalidated.emit()
        self.window.frameSwapped.emit()
        self.pump()
        self.assertEqual(self.window.winid_calls, calls)
        self.compose.assert_not_called()
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_system_blur_quick_surface_keeps_immediate_contract(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock, backend='system-blur')
        self.bridge.start()
        self.window.show()
        self.pump()
        self.assertFalse(self.bridge.status()['render_gate'])
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified')
        self.assertIsNotNone(self.bridge.compose_now())
        self.compose.assert_called_once()

    def test_actual_offscreen_quick_first_show_waits_for_submitted_frame(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        self.window = QQuickWindow()
        self.window.resize(420, 280)
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock)
        self.bridge.start()
        self.window.show()
        # show() has created the surface, but the GUI/render loop has not run.
        self.assertIsNone(self.bridge.compose_now('show-before-frame'))
        self.compose.assert_not_called()
        for _ in range(100):
            self.pump()
            if self.bridge.status()['render_ready']:
                break
            QTest.qWait(5)
        self.assertTrue(self.bridge.status()['render_ready'])
        self.assertTrue(self.window.isSceneGraphInitialized())
        self.assertTrue(self.bridge.status()['first_frame_observed'])
        self.due()
        self.compose.assert_called_once()
        self.assertFalse(self.publish.call_args.args[0]['compositing_verified'])

    def test_system_blur_explicit_gate_waits_for_first_frame_and_preserves_policy_snapshot(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            backend='system-blur', wait_for_first_frame=True)
        self.bridge.start()
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified')
        self.show_exposed()
        self.window.initialized = True
        self.window.sceneGraphInitialized.emit()
        self.pump()
        self.assertIsNone(self.bridge.compose_now('show'))
        self.due(5)
        self.compose.assert_not_called()
        self.assertEqual(self.bridge.status()['state'], 'waiting_for_render')
        self.window.frameSwapped.emit()
        self.pump()
        self.due()
        self.compose.assert_called_once_with(self.bridge.status()['handle'], self.policy.return_value)
        self.assertEqual(self.bridge.status()['backend'], 'system-blur')
        self.assertTrue(self.bridge.status()['render_gate'])
        self.assertEqual(self.bridge.status()['state'], 'configured_unverified')

    def test_system_blur_explicit_gate_drops_pre_hide_frame_epoch(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            backend='system-blur', wait_for_first_frame=True)
        self.bridge.start()
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified')
        self.show_exposed()
        self.window.initialized = True
        self.window.frameSwapped.emit()
        self.window.hide()
        self.window.show()
        self.pump()
        self.due(5)
        self.compose.assert_not_called()
        self.assertFalse(self.bridge.status()['first_frame_observed'])
        self.submit_frame()
        self.due()
        self.compose.assert_called_once()

    def test_explicit_gate_requires_boolean_and_actual_quick_capabilities(self):
        for invalid in ('true', 1, 0, [], {}):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                SettingsMaterialBridge(self.window, compose_once=self.compose,
                    policy_reader=self.policy, publish=self.publish, wait_for_first_frame=invalid)
        plain = OffscreenWindow()
        try:
            with self.assertRaisesRegex(ValueError, 'requires a Quick window'):
                SettingsMaterialBridge(plain, compose_once=self.compose,
                    policy_reader=self.policy, publish=self.publish, wait_for_first_frame=True)
        finally:
            plain.destroy()
            plain.deleteLater()

    def test_explicit_false_preserves_immediate_contract_even_for_quick_acrylic(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            wait_for_first_frame=False)
        self.bridge.start()
        self.window.show()
        self.pump()
        self.assertFalse(self.bridge.status()['render_gate'])
        self.assertIsNotNone(self.bridge.compose_now())
        self.compose.assert_called_once()

    def test_actual_quick_system_blur_opt_in_waits_for_real_submitted_frame(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        self.window = QQuickWindow()
        self.window.resize(420, 280)
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            backend='system-blur', wait_for_first_frame=True)
        self.bridge.start()
        self.compose.return_value = dict(material='system-blur', blur_configured=True,
            bool_result=1, status='configured-unverified')
        self.window.show()
        self.assertIsNone(self.bridge.compose_now('first-show'))
        self.compose.assert_not_called()
        for _ in range(100):
            self.pump()
            if self.bridge.status()['render_ready']:
                break
            QTest.qWait(5)
        self.assertTrue(self.bridge.status()['render_ready'])
        self.due()
        self.compose.assert_called_once()
        self.assertFalse(self.publish.call_args.args[0]['compositing_verified'])

    def test_actual_quick_hide_restore_waits_for_fresh_frame_without_resize(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        self.window = QQuickWindow()
        self.window.resize(420, 280)
        self.window.setPersistentGraphics(False)
        self.window.setPersistentSceneGraph(False)
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock)
        self.bridge.start()
        for restored in (False, True):
            self.window.show()
            original = self.window.geometry()  # QPA may place an initially unpositioned window during show().
            self.assertIsNone(self.bridge.compose_now('restore' if restored else 'show'))
            for _ in range(100):
                self.pump()
                if self.bridge.status()['render_ready']:
                    break
                QTest.qWait(5)
            self.assertTrue(self.bridge.status()['render_ready'])
            self.due()
            self.assertEqual(self.compose.call_count, 2 if restored else 1)
            self.assertEqual(self.window.geometry(), original)
            if not restored:
                self.window.hide()
                self.pump()
                self.assertFalse(self.bridge.status()['first_frame_observed'])
                self.assertFalse(self.bridge.status()['timer_active'])
                self.due(5)
                self.compose.assert_called_once()

    def test_attach_after_actual_quick_first_frame_requests_one_fresh_frame(self):
        self.bridge.close()
        self.window.destroy()
        self.window.deleteLater()
        self.window = QQuickWindow()
        self.window.resize(420, 280)
        frames = []
        self.window.frameSwapped.connect(lambda: frames.append(True))
        self.window.show()
        for _ in range(100):
            self.pump()
            if frames:
                break
            QTest.qWait(5)
        self.assertTrue(frames)
        self.bridge = SettingsMaterialBridge(self.window, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock)
        self.bridge.start()
        self.assertIsNone(self.bridge.compose_now('attach-after-frame'))
        self.compose.assert_not_called()
        before = len(frames)
        for _ in range(100):
            self.pump()
            if self.bridge.status()['render_ready']:
                break
            QTest.qWait(5)
        self.assertGreater(len(frames), before)
        self.assertTrue(self.bridge.status()['render_ready'])
        self.due()
        self.compose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
