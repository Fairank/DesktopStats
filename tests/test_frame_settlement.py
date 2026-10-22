"""Finite post-present recovery and nonactivating frame refresh, fake Win32 only."""
import unittest
from unittest.mock import MagicMock, patch

import native_platform as platform
from settings_material_lifecycle import SettingsMaterialLifecycle


class FrameSettlementTests(unittest.TestCase):
    def test_refresh_validates_process_and_thread_then_never_moves_or_focuses(self):
        user, kernel = MagicMock(), MagicMock()
        kernel.GetCurrentProcessId.return_value = 100
        kernel.GetCurrentThreadId.return_value = 200
        def owner(hwnd, output):
            output._obj.value = 100
            return 200
        user.GetWindowThreadProcessId.side_effect = owner
        user.SetWindowPos.return_value = 1
        user.RedrawWindow.return_value = 1
        with patch.object(platform.c, "WinDLL", side_effect=lambda name, **kw: user if name == "user32" else kernel):
            report = platform.refresh_owned_frame(123)
            self.assertTrue(report["frame_refresh_result"])
            user.SetWindowPos.assert_called_once_with(123, None, 0, 0, 0, 0, 0x237)
            user.RedrawWindow.assert_called_once_with(123, None, None, 0x401)
            user.SetWindowPos.reset_mock()
            user.RedrawWindow.reset_mock()
            kernel.GetCurrentThreadId.return_value = 201
            self.assertEqual(platform.refresh_owned_frame(123)["frame_refresh_error"], "not-owned-gui-thread")
            user.SetWindowPos.assert_not_called()
            user.RedrawWindow.assert_not_called()
            kernel.GetCurrentThreadId.return_value = 200
            kernel.GetCurrentProcessId.return_value = 101
            self.assertEqual(platform.refresh_owned_frame(123)["frame_refresh_error"], "not-owned-gui-thread")
            user.SetWindowPos.assert_not_called()

    def test_settlement_shares_finite_attempt_budget_and_hide_cancels(self):
        now = [100.]
        life = SettingsMaterialLifecycle(clock=lambda: now[0], settle_delay=.25)
        life.update_context(handle=123, visible=True, policy="allowed")
        now[0] += .15
        good = dict(material="desktop-acrylic", backdrop_result=0, backdrop_type=3)
        life.complete(life.take_due(), good)
        self.assertEqual(life.metadata()["state"], "settle_wait")
        now[0] += .25
        life.complete(life.take_due(), good)
        self.assertEqual(life.metadata()["state"], "configured_unverified")
        self.assertIsNone(life.next_delay_ms())
        self.assertEqual(life.metadata()["applies_total"], 2)
        life.notify("composition_changed")
        now[0] += .15
        life.complete(life.take_due(), good)
        life.update_context(handle=123, visible=False, policy="allowed")
        now[0] += 20
        self.assertIsNone(life.take_due())
        self.assertFalse(life.metadata()["compositing_verified"])

    def test_reentrant_native_refresh_cannot_redraw_a_changed_owner(self):
        user, kernel = MagicMock(), MagicMock()
        kernel.GetCurrentProcessId.return_value = 100
        kernel.GetCurrentThreadId.return_value = 200
        owner_pid = [100]
        def owner(hwnd, output):
            output._obj.value = owner_pid[0]
            return 200
        user.GetWindowThreadProcessId.side_effect = owner
        def refresh(*args):
            owner_pid[0] = 101
            return 1
        user.SetWindowPos.side_effect = refresh
        with patch.object(platform.c, "WinDLL", side_effect=lambda name, **kw: user if name == "user32" else kernel):
            result = platform.refresh_owned_frame(123)
        self.assertEqual(result["frame_refresh_error"], "owner-changed-during-refresh")
        user.RedrawWindow.assert_not_called()

    def test_settle_failure_gets_only_remaining_attempt(self):
        now = [100.]
        life = SettingsMaterialLifecycle(clock=lambda: now[0], settle_delay=.25)
        life.update_context(handle=123, visible=True, policy="allowed")
        now[0] += .15
        life.complete(life.take_due(), dict(material="desktop-acrylic", backdrop_result=0, backdrop_type=3))
        now[0] += .25
        life.complete(life.take_due(), dict(material="solid", status="fallback"))
        now[0] += 1
        life.complete(life.take_due(), dict(material="solid", status="fallback"))
        self.assertEqual(life.metadata()["applies_total"], 3)
        self.assertEqual(life.metadata()["state"], "exhausted")
        self.assertIsNone(life.next_delay_ms())
