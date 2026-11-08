"""Finite recovery of prepared materials on real offscreen Qt transitions.

The composition/policy callbacks are fake. No Windows API, renderer capture,
sensor, visible window or application Runtime is initialized.
"""

import unittest

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QExposeEvent, QRegion

import test_settings_hidden_preparation as fixtures
from settings_material_bridge import SettingsMaterialBridge


class MaterialRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.HiddenPreparationTests.setUpClass()

    def setUp(self):
        self.f = fixtures.HiddenPreparationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.addCleanup(self.f.tearDown)

    def prepare(self):
        f = self.f
        f.use_blur_bridge()
        f.compose.return_value = dict(fixtures.GOOD, material="system-blur", bool_result=1)
        f.create()
        f.bridge.prepare_hidden()
        f.ready()
        f.due()
        self.assertEqual(f.compose.call_count, 1)
        self.assertTrue(f.bridge.status()["hidden_prepared"])

    def submit(self):
        self.f.frame.frameSwapped.emit()
        self.f.pump()
        self.f.due()

    def assert_waits_for_fresh_frame(self, previous_epoch, calls):
        f = self.f
        self.assertGreater(f.bridge.status()["frame_epoch"], previous_epoch)
        self.assertFalse(f.bridge.status()["hidden_prepared"])
        f.bridge._render_event(previous_epoch, "first_frame")
        f.due(50)
        self.assertEqual(f.compose.call_count, calls)

    def test_child_dpi_and_screen_change_retire_adoption_and_keep_same_owner(self):
        self.prepare()
        f = self.f
        owner = f.bridge.status()["surface_handle"]
        winid_calls = f.host.winid_calls
        for index, kind in enumerate((QEvent.DevicePixelRatioChange, QEvent.ScreenChangeInternal), 1):
            previous = f.bridge.status()["frame_epoch"]
            QCoreApplication.sendEvent(f.frame, QEvent(kind))
            self.assert_waits_for_fresh_frame(previous, index)
            self.submit()
            self.assertEqual(f.compose.call_count, index + 1)
            self.assertIn("display_changed", f.bridge.status()["last_request"]["reasons"])
            self.assertEqual(f.bridge.status()["surface_handle"], owner)
        self.assertEqual(f.host.winid_calls, winid_calls)
        self.assertEqual(f.frame.winid_calls, 0)

    def test_native_owner_dpi_and_screen_events_also_reach_the_render_gate(self):
        self.prepare()
        f = self.f
        for index, kind in enumerate((QEvent.DevicePixelRatioChange, QEvent.ScreenChangeInternal), 1):
            previous = f.bridge.status()["frame_epoch"]
            QCoreApplication.sendEvent(f.host, QEvent(kind))
            self.assert_waits_for_fresh_frame(previous, index)
            self.submit()
            self.assertEqual(f.compose.call_count, index + 1)
            self.assertIn("display_changed", f.bridge.status()["last_request"]["reasons"])

    def test_actual_owner_and_client_exposure_loss_recover_after_a_fresh_frame(self):
        self.prepare()
        f = self.f
        for calls, window in enumerate((f.host, f.frame), 1):
            previous = f.bridge.status()["frame_epoch"]
            window.exposed = False
            # Deliver the actual filter event without letting QQuickWindow's
            # default Expose handler independently submit an automatic frame.
            f.bridge.eventFilter(window, QExposeEvent(QRegion()))
            f.pump()
            self.assertIsNone(f.bridge.compose_now())
            self.assertFalse(f.bridge.status()["timer_active"])
            window.exposed = True
            f.bridge.eventFilter(window, QExposeEvent(QRegion()))
            f.pump()
            self.assert_waits_for_fresh_frame(previous, calls)
            self.submit()
            self.assertEqual(f.compose.call_count, calls + 1)
            self.assertIn("composition_changed", f.bridge.status()["last_request"]["reasons"])

    def test_minimize_restore_retires_old_preparation_without_native_work_while_minimized(self):
        self.prepare()
        f = self.f
        previous = f.bridge.status()["frame_epoch"]
        f.host.setWindowState(Qt.WindowMinimized)
        f.pump()
        self.assertFalse(f.bridge.status()["hidden_prepared"])
        self.assertIsNone(f.bridge.compose_now())
        f.due(50)
        self.assertEqual(f.compose.call_count, 1)
        f.host.setWindowState(Qt.WindowNoState)
        f.pump()
        self.assert_waits_for_fresh_frame(previous, 1)
        self.submit()
        self.assertEqual(f.compose.call_count, 2)

    def test_repeated_expose_frames_and_unchanged_state_do_not_reapply(self):
        self.prepare()
        f = self.f
        for _ in range(40):
            QCoreApplication.sendEvent(f.host, QExposeEvent(QRegion()))
            QCoreApplication.sendEvent(f.frame, QExposeEvent(QRegion()))
            QCoreApplication.sendEvent(f.host, QEvent(QEvent.WindowStateChange))
            f.frame.frameSwapped.emit()
            f.pump()
            f.due()
        self.assertEqual(f.compose.call_count, 1)
        self.assertTrue(f.bridge.status()["hidden_prepared"])

    def test_dpi_burst_coalesces_and_failed_recovery_has_a_finite_retry_budget(self):
        self.prepare()
        f = self.f
        f.compose.return_value = dict(fixtures.FAILED)
        for _ in range(20):
            QCoreApplication.sendEvent(f.frame, QEvent(QEvent.DevicePixelRatioChange))
            QCoreApplication.sendEvent(f.host, QEvent(QEvent.ScreenChangeInternal))
        f.due(50)
        self.assertEqual(f.compose.call_count, 1)
        self.submit()
        self.assertEqual(f.compose.call_count, 2)
        f.due(.25)
        self.assertEqual(f.compose.call_count, 3)
        f.due(1.0)
        self.assertEqual(f.compose.call_count, 4)
        self.assertEqual(f.bridge.status()["state"], "exhausted")
        f.due(50)
        self.assertEqual(f.compose.call_count, 4)
        self.assertFalse(f.bridge.status()["timer_active"])

    def test_real_dpi_change_can_recover_a_failed_opening_but_first_frames_cannot(self):
        f = self.f
        f.prepare_failed_blur_opening()
        f.due()
        f.due(1.5)
        self.assertEqual(f.compose.call_count, 1)
        self.assertFalse(f.publish.call_args.args[0]["coating_translucent"])
        QCoreApplication.sendEvent(f.host, QEvent(QEvent.DevicePixelRatioChange))
        f.due(50)
        self.assertEqual(f.compose.call_count, 1)
        self.submit()
        self.assertEqual(f.compose.call_count, 2)
        self.assertTrue(f.publish.call_args.args[0]["coating_translucent"])

    def test_recovery_reason_crosses_first_frame_gate_for_a_callers_prepared_cache(self):
        f = self.f
        f.use_blur_bridge()
        actual = []
        prepared = []
        def compose(handle, policy):
            reasons = (f.bridge.status().get("last_request") or {}).get("reasons", ())
            if not prepared or {"display_changed", "composition_changed"}.intersection(reasons):
                actual.append(tuple(reasons))
                prepared[:] = [dict(fixtures.GOOD, material="system-blur", bool_result=1)]
            return dict(prepared[0])
        # The existing detail presenter has a second caller-owned bootstrap
        # cache. It must receive a real recovery reason, not just first_frame.
        f.bridge._compose_once = compose
        f.create()
        f.bridge.prepare_hidden()
        f.ready()
        f.due()
        self.assertEqual(len(actual), 1)
        QCoreApplication.sendEvent(f.frame, QEvent(QEvent.DevicePixelRatioChange))
        self.submit()
        self.assertEqual(len(actual), 2)
        self.assertIn("display_changed", actual[-1])
        f.frame.sceneGraphInvalidated.emit()
        f.pump()
        self.submit()
        self.assertEqual(len(actual), 3)
        self.assertIn("composition_changed", actual[-1])

    def test_close_or_hide_during_recovery_cannot_publish_or_apply_a_stale_frame(self):
        self.prepare()
        f = self.f
        previous = f.bridge.status()["frame_epoch"]
        QCoreApplication.sendEvent(f.frame, QEvent(QEvent.DevicePixelRatioChange))
        f.host.hide()
        f.frame.hide()
        f.pump()
        f.bridge._render_event(previous, "first_frame")
        f.due(50)
        self.assertEqual(f.compose.call_count, 1)
        f.bridge.close()
        reports = f.publish.call_count
        f.bridge._render_event(f.bridge._render_epoch, "first_frame")
        f.frame.frameSwapped.emit()
        f.due(50)
        self.assertEqual(f.publish.call_count, reports)
        self.assertEqual(f.compose.call_count, 1)
        self.assertFalse(f.bridge.status()["timer_active"])

    def test_legacy_non_frame_client_coalesces_owner_display_change_without_render_polling(self):
        f = self.f
        f.bridge.close()
        f.compose.return_value = dict(fixtures.GOOD, material="system-blur", bool_result=1)
        f.bridge = SettingsMaterialBridge(f.host, backend="system-blur", compose_once=f.compose,
                                         policy_reader=f.policy, publish=f.publish, clock=f.clock)
        f.bridge.start()
        f.host.show()
        f.pump()
        f.due()
        self.assertEqual(f.compose.call_count, 1)
        for _ in range(20):
            QCoreApplication.sendEvent(f.host, QEvent(QEvent.DevicePixelRatioChange))
        f.due()
        self.assertEqual(f.compose.call_count, 2)
        self.assertIn("display_changed", f.bridge.status()["last_request"]["reasons"])
        f.due(50)
        self.assertEqual(f.compose.call_count, 2)
        self.assertFalse(f.bridge.status()["timer_active"])

    def test_non_frame_dpi_inside_native_callback_rejects_stale_result_and_recovers_once(self):
        f = self.f
        f.bridge.close()
        calls = []
        def compose(handle, policy):
            calls.append(handle)
            if len(calls) == 1:
                QCoreApplication.sendEvent(f.host, QEvent(QEvent.DevicePixelRatioChange))
            return dict(fixtures.GOOD, material="system-blur", bool_result=1)
        f.bridge = SettingsMaterialBridge(f.host, backend="system-blur", compose_once=compose,
                                         policy_reader=f.policy, publish=f.publish, clock=f.clock)
        f.bridge.start()
        f.host.show()
        f.pump()
        self.assertIsNone(f.bridge.compose_now("initial"))
        f.publish.assert_not_called()
        self.assertEqual(len(calls), 1)
        f.due(.14)
        self.assertEqual(len(calls), 1)
        f.due(.01)
        self.assertEqual(len(calls), 2)
        f.publish.assert_called_once()
        self.assertEqual(calls[0], calls[1])
        self.assertIn("display_changed", f.bridge.status()["last_request"]["reasons"])
        f.due(50)
        self.assertEqual(len(calls), 2)
        self.assertFalse(f.bridge.status()["timer_active"])


if __name__ == "__main__":
    unittest.main()
