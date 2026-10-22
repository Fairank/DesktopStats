"""Own offscreen Raster/Quick pairs and fake material APIs; no native calls."""

import os
import threading
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread
from PySide6.QtGui import QExposeEvent, QRegion, QWindow
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from settings_material_bridge import SettingsMaterialBridge

GOOD = dict(
    material="system-blur", status="configured-unverified", ok=True,
    bool_result=1, blur_configured=True, coating_allowed=True,
    coating_translucent=True, compositing_verified=False,
)
DWM = dict(material="desktop-acrylic", status="configured-unverified",
           backdrop_type=3, backdrop_result=0)
CLEARED = dict(material="solid", status="fallback", fallback_reason="material-disabled",
               ok=True, bool_result=1, blur_may_remain=False)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class ControlledRaster(QWindow):
    def __init__(self):
        super().__init__()
        self.exposed = False
        self.winid_calls = 0
        self.update_calls = 0

    def isExposed(self):
        return self.exposed

    def winId(self):
        self.winid_calls += 1
        return super().winId()

    def update(self):
        self.update_calls += 1


class ControlledQuick(QQuickWindow):
    """Actual Quick QObject with explicitly controlled render milestones."""

    def __init__(self):
        super().__init__()
        self.exposed = False
        self.initialized = False
        self.update_calls = 0
        self.winid_calls = 0

    def isExposed(self):
        return self.exposed

    def isSceneGraphInitialized(self):
        return self.initialized

    def update(self):
        self.update_calls += 1

    def winId(self):
        self.winid_calls += 1
        raise AssertionError("Bridge must never query a rendering source handle")


class FrameSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "No Windows-visible test windows"

    def setUp(self):
        self.clock = Clock()
        self.host = ControlledRaster()
        self.host.resize(400, 280)
        self.frame = ControlledQuick()
        self.frame.resize(400, 280)
        self.compose = Mock(return_value=dict(GOOD))
        self.policy = Mock(return_value=dict(state="allowed"))
        self.publish = Mock()
        self.release = Mock(return_value=dict(ok=True, cleanup_complete=True))
        self.bridge = self.make_bridge()
        self.bridge.start()

    def make_bridge(self, **kwargs):
        return SettingsMaterialBridge(
            self.host, frame_source=self.frame, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, clock=self.clock,
            release_surface=self.release, backend=kwargs.pop("backend", "system-blur"),
            **kwargs,
        )

    def tearDown(self):
        self.bridge.close()
        for window in (self.frame, self.host):
            try:
                window.destroy()
                window.deleteLater()
            except RuntimeError:
                pass  # A test deliberately deleted the owned QObject.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def pump(self):
        for _ in range(4):
            self.app.processEvents()

    def expose(self, window, value):
        window.exposed = value
        QCoreApplication.sendEvent(window, QExposeEvent(QRegion()))
        self.pump()

    def show_pair(self):
        self.host.show()  # QPA is asserted offscreen, never a visible Windows HWND.
        self.frame.show()
        self.pump()
        self.expose(self.host, True)
        self.expose(self.frame, True)

    def submit(self):
        self.frame.initialized = True
        self.frame.sceneGraphInitialized.emit()
        self.frame.frameSwapped.emit()
        self.pump()

    def due(self, seconds=.15):
        self.clock.now += seconds
        self.bridge._on_timeout()

    def ready(self):
        self.show_pair()
        self.submit()
        self.assertTrue(self.bridge.status()["render_ready"])

    def test_hidden_pair_start_does_not_create_either_surface(self):
        self.assertEqual(self.host.winid_calls, 0)
        self.assertEqual(self.frame.winid_calls, 0)
        self.assertTrue(self.bridge.status()["render_gate"])
        self.assertFalse(self.bridge.status()["native_filter_installed"])
        self.assertIsNone(self.bridge.compose_now())
        self.compose.assert_not_called()

    def test_actual_quick_is_required_not_an_augmented_plain_window(self):
        with self.assertRaisesRegex(ValueError, "actual QQuickWindow"):
            SettingsMaterialBridge(self.host, frame_source=self.host,
                compose_once=self.compose, policy_reader=self.policy, publish=self.publish)

    def test_separate_source_cannot_disable_first_frame_gate(self):
        with self.assertRaisesRegex(ValueError, "first-frame gating"):
            self.make_bridge(wait_for_first_frame=False)

    def test_plain_native_owner_without_source_retains_legacy_immediate_contract(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.host, compose_once=self.compose,
            policy_reader=self.policy, publish=self.publish, backend="system-blur")
        self.bridge.start()
        self.host.show()
        self.pump()
        self.assertFalse(self.bridge.status()["render_gate"])
        self.assertIsNotNone(self.bridge.compose_now())
        self.compose.assert_called_once()

    def test_host_handle_and_exposure_cannot_replace_client_first_frame(self):
        self.show_pair()
        self.frame.initialized = True
        self.frame.sceneGraphInitialized.emit()
        self.pump()
        self.due(50)
        self.compose.assert_not_called()
        self.assertEqual(self.bridge.status()["applies_total"], 0)
        self.submit()
        self.due()
        self.compose.assert_called_once()
        self.assertEqual(self.compose.call_args.args[0], self.bridge.status()["surface_handle"])
        self.assertEqual(self.frame.winid_calls, 0)
        self.assertEqual(self.host.update_calls, 0)
        self.assertGreater(self.frame.update_calls, 0)

    def test_hidden_native_owner_blocks_even_a_ready_render_source(self):
        self.frame.show()
        self.pump()
        self.expose(self.frame, True)
        self.submit()
        self.policy.return_value = dict(state="disabled")
        self.assertIsNone(self.bridge.compose_now())
        self.assertEqual(self.host.winid_calls, 0)
        self.compose.assert_not_called()

    def test_native_owner_exposure_is_required_independently(self):
        self.show_pair()
        self.expose(self.host, False)
        self.submit()
        self.due(50)
        self.compose.assert_not_called()
        self.expose(self.host, True)
        self.due(50)
        self.compose.assert_not_called()
        self.submit()
        self.due()
        self.compose.assert_called_once()

    def test_render_source_exposure_is_required_independently(self):
        self.show_pair()
        self.expose(self.frame, False)
        self.submit()
        self.due(50)
        self.compose.assert_not_called()
        # Real Quick exposure may automatically submit a fresh frame. Hold its
        # signals only in this controlled fixture to inspect the pre-frame gap.
        self.frame.blockSignals(True)
        self.expose(self.frame, True)
        self.frame.blockSignals(False)
        self.due(50)
        self.compose.assert_not_called()
        self.submit()
        self.due()
        self.compose.assert_called_once()

    def test_client_hide_show_retires_queued_old_first_frame(self):
        self.show_pair()
        self.frame.initialized = True
        self.frame.frameSwapped.emit()
        old = self.bridge.status()["frame_epoch"]
        self.frame.blockSignals(True)
        self.frame.hide()
        self.frame.show()
        self.pump()
        self.frame.blockSignals(False)
        self.assertGreater(self.bridge.status()["frame_epoch"], old)
        self.due(10)
        self.compose.assert_not_called()
        self.assertFalse(self.bridge.status()["first_frame_observed"])
        self.submit()
        self.due()
        self.compose.assert_called_once()

    def test_client_surface_rebuild_preserves_native_owner_and_never_releases_client(self):
        self.ready()
        self.due()
        owner = self.bridge.status()["surface_handle"]
        serial = self.bridge.status()["surface_serial"]
        frame_serial = self.bridge.status()["frame_surface_serial"]
        old = self.bridge.status()["frame_epoch"]
        self.frame.destroy()
        self.frame.initialized = False
        self.pump()
        self.release.assert_not_called()
        self.assertFalse(self.bridge.status()["frame_surface_alive"])
        self.assertEqual(self.bridge.status()["surface_handle"], owner)
        self.frame.show()
        self.pump()
        self.expose(self.frame, True)
        self.bridge._render_event(old, "first_frame")
        self.due(10)
        self.assertEqual(self.compose.call_count, 1)
        self.submit()
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge.status()["surface_serial"], serial)
        self.assertGreater(self.bridge.status()["frame_surface_serial"], frame_serial)
        self.assertEqual(self.frame.winid_calls, 0)

    def test_source_qobject_destruction_fails_closed_but_owner_release_survives(self):
        self.ready()
        self.due()
        owner = self.bridge.status()["surface_handle"]
        self.frame.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.pump()
        status = self.bridge.status()
        self.assertFalse(status["frame_source_alive"])
        self.assertFalse(status["render_ready"])
        self.assertFalse(status["closed"])
        self.assertEqual(status["surface_handle"], owner)
        self.assertIsNone(self.bridge.compose_now())
        self.due(50)
        self.assertEqual(self.compose.call_count, 1)
        self.release.assert_not_called()
        self.bridge.close()
        self.bridge.close()
        self.release.assert_called_once_with(owner)

    def test_host_minimize_restore_needs_current_client_frame(self):
        self.ready()
        self.due()
        old = self.bridge.status()["frame_epoch"]
        self.host.setWindowState(Qt.WindowMinimized)
        self.pump()
        self.assertIsNone(self.bridge.compose_now())
        self.host.setWindowState(Qt.WindowNoState)
        self.pump()
        self.bridge._render_event(old, "first_frame")
        self.due(50)
        self.assertEqual(self.compose.call_count, 1)
        self.submit()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_client_dpi_change_invalidates_epoch_without_changing_host_handle(self):
        self.ready()
        self.due()
        owner = self.bridge.status()["surface_handle"]
        old = self.bridge.status()["frame_epoch"]
        QCoreApplication.sendEvent(self.frame, QEvent(QEvent.DevicePixelRatioChange))
        self.bridge._render_event(old, "first_frame")
        self.due(50)
        self.assertEqual(self.compose.call_count, 1)
        self.assertEqual(self.bridge.status()["surface_handle"], owner)
        self.submit()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_native_callback_reentrant_child_hide_cannot_publish_old_success(self):
        self.ready()
        self.compose.side_effect = lambda *_: (self.frame.hide(), dict(GOOD))[1]
        self.assertIsNone(self.bridge.compose_now())
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_render_invalidation_inside_native_callback_rejects_success_before_gui_notice(self):
        self.ready()
        self.compose.side_effect = lambda *_: (self.frame.sceneGraphInvalidated.emit(), dict(GOOD))[1]
        self.assertIsNone(self.bridge.compose_now())
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["render_ready"])
        self.pump()
        self.compose.side_effect = None
        self.submit()
        self.due()
        self.assertEqual(self.publish.call_count, 1)

    def test_disabled_policy_clears_before_frame_but_reenable_waits_for_current_frame(self):
        self.show_pair()
        self.policy.return_value = dict(state="disabled")
        self.compose.return_value = dict(CLEARED)
        self.assertFalse(self.bridge.status()["first_frame_observed"])
        self.assertIsNotNone(self.bridge.compose_now())
        self.assertEqual(self.compose.call_args.args[1], dict(state="disabled"))
        self.assertEqual(self.bridge.status()["state"], "policy_disabled")
        self.assertFalse(self.bridge.status()["timer_active"])

        self.policy.return_value = dict(state="allowed")
        self.compose.return_value = dict(GOOD)
        self.bridge.refresh_policy()
        self.assertIsNone(self.bridge.compose_now())
        self.due(50)
        self.assertEqual(self.compose.call_count, 1)
        self.submit()
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge.status()["state"], "configured_unverified")

    def test_invalidation_inside_preframe_policy_clear_retires_inflight_request(self):
        self.show_pair()
        self.policy.return_value = dict(state="disabled")
        self.compose.side_effect = lambda *_: (self.frame.sceneGraphInvalidated.emit(), dict(CLEARED))[1]
        self.assertIsNone(self.bridge.compose_now())
        self.assertFalse(self.bridge.status()["in_flight"])
        self.publish.assert_not_called()
        self.pump()
        self.compose.side_effect = None
        self.compose.return_value = dict(CLEARED)
        self.assertIsNotNone(self.bridge.compose_now())
        self.assertEqual(self.bridge.status()["state"], "policy_disabled")
        self.assertEqual(self.publish.call_count, 1)
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_source_destroy_then_owner_surface_destroy_still_releases_known_owner_once(self):
        self.ready()
        self.due()
        owner = self.bridge.status()["surface_handle"]
        owner_queries = self.host.winid_calls
        self.frame.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.host.destroy()
        self.pump()
        self.release.assert_called_once_with(owner)
        self.assertEqual(self.host.winid_calls, owner_queries)
        self.assertEqual(self.bridge.status()["surface_handle"], 0)
        self.assertFalse(self.bridge.status()["timer_active"])
        self.bridge.close()
        self.assertEqual(self.release.call_count, 1)

    def test_render_thread_only_changes_scalar_epoch_then_queues_gui_work(self):
        self.ready()
        before = self.policy.call_count
        epoch = self.bridge.status()["frame_epoch"]
        worker = threading.Thread(target=self.frame.sceneGraphInvalidated.emit)
        worker.start()
        worker.join()
        self.assertEqual(self.policy.call_count, before)
        self.compose.assert_not_called()
        self.assertGreater(self.bridge._render_epoch, epoch)
        self.pump()
        self.assertFalse(self.bridge.status()["render_ready"])
        threads = []
        self.compose.side_effect = lambda *_: (threads.append(QThread.currentThread()), dict(GOOD))[1]
        self.submit()
        self.due()
        self.assertEqual(threads, [self.host.thread()])

    def test_dwm_settlement_updates_only_quick_source_and_is_finite(self):
        self.bridge.close()
        self.compose.return_value = dict(DWM)
        self.bridge = self.make_bridge(backend="desktop-acrylic")
        self.bridge.start()
        self.ready()
        self.due()
        self.assertEqual(self.bridge.status()["state"], "settle_wait")
        self.assertEqual(self.host.update_calls, 0)
        self.assertGreaterEqual(self.frame.update_calls, 2)
        self.due(.25)
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.bridge.status()["state"], "configured_unverified")
        self.assertFalse(self.bridge.status()["timer_active"])

    def test_settlement_update_reentrant_source_hide_cannot_publish_or_keep_retrying(self):
        self.bridge.close()
        self.compose.return_value = dict(DWM)
        self.bridge = self.make_bridge(backend="desktop-acrylic")
        self.bridge.start()
        self.ready()
        self.frame.update = Mock(side_effect=self.frame.hide)
        self.due()
        self.assertEqual(self.compose.call_count, 1)
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["visible"])
        self.assertFalse(self.bridge.status()["in_flight"])
        self.assertFalse(self.bridge.status()["timer_active"])
        self.assertEqual(self.host.update_calls, 0)

    def test_release_callback_exception_does_not_leave_frame_connections_or_timer_live(self):
        self.ready()
        epoch = self.bridge.status()["frame_epoch"]
        self.release.side_effect = RuntimeError("fake release failed")
        with self.assertLogs(level="WARNING"):
            self.bridge.close()
        self.assertIn("fake release failed", self.bridge.status()["release_error"])
        self.assertFalse(self.bridge.status()["timer_active"])
        self.frame.frameSwapped.emit()
        self.frame.sceneGraphInvalidated.emit()
        self.frame.hide()
        self.pump()
        self.assertEqual(self.bridge.status()["frame_epoch"], epoch)
        self.compose.assert_not_called()
        self.bridge.close()
        self.release.assert_called_once()

    def test_close_disconnects_frame_events_and_owner_cleanup_remains_once(self):
        self.ready()
        epoch = self.bridge.status()["frame_epoch"]
        self.bridge.close()
        self.frame.frameSwapped.emit()
        self.frame.hide()
        self.pump()
        self.assertEqual(self.bridge.status()["frame_epoch"], epoch)
        self.compose.assert_not_called()
        self.release.assert_called_once()
        self.assertFalse(self.bridge.status()["frame_source_alive"])

    def test_real_quick_child_frame_arms_raster_owner_without_native_backend(self):
        self.bridge.close()
        child = QQuickWindow()
        child.resize(400, 280)
        child.setParent(self.host)
        self.bridge = SettingsMaterialBridge(
            self.host, frame_source=child, backend="system-blur",
            compose_once=self.compose, policy_reader=self.policy, publish=self.publish,
            clock=self.clock,
        )
        self.bridge.start()
        try:
            self.host.show()
            self.expose(self.host, True)
            child.show()
            for _ in range(40):
                QTest.qWait(10)
                if self.bridge.status()["first_frame_observed"]:
                    break
            self.assertTrue(child.isSceneGraphInitialized())
            self.assertTrue(self.bridge.status()["first_frame_observed"])
            self.assertTrue(self.bridge.status()["render_ready"])
            self.due()
            self.compose.assert_called_once()
            self.assertEqual(self.compose.call_args.args[0], self.bridge.status()["surface_handle"])
            self.assertFalse(self.publish.call_args.args[0]["compositing_verified"])
        finally:
            self.bridge.close()
            child.hide()
            child.destroy()
            child.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
