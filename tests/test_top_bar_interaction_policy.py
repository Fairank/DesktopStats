"""User detail intent remains usable after Shell fullscreen ordering notices.

Only the real coordinator/Qt timers and fake owned surfaces are used. No QML
rendering, native calls, sensors, installed process or user profile is involved.
"""

import time
import unittest

import test_top_bar_runtime as fixtures
from PySide6.QtTest import QTest


class TopBarInteractionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TopBarRuntimeTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.TopBarRuntimeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.manager = self.fixture.manager
        self.adapter = self.fixture.adapter
        self.manager.apply(fixtures.config(mode="all"))
        self.assertEqual(set(self.manager.hosts), {"DISPLAY1", "DISPLAY2"})
        self.assertTrue(all(host.window.isVisible() for host in self.manager.hosts.values()))

    def notice(self, display, opened=True, *, refresh=True):
        host = self.manager.hosts[display]
        self.manager.native_message(
            host.binding.hwnd, self.adapter.callback_message,
            fixtures.ABN_FULLSCREENAPP, int(opened),
        )
        if refresh:
            self.manager._refresh()

    def assert_open(self, display="DISPLAY1", item="b_0", *, pinned=True):
        panel = self.manager._panel
        self.assertIsNotNone(panel, self.manager.detail_diagnostics())
        self.assertIs(panel["host"], self.manager.hosts[display])
        self.assertEqual(panel["item"], item)
        self.assertEqual(panel["pinned"], pinned)
        self.assertTrue(self.manager._panel_visible(panel))
        self.assertFalse(panel["window"].deleted)
        return panel

    def wait_for_panel(self):
        deadline = time.monotonic() + 1.0
        while self.manager._panel is None and time.monotonic() < deadline:
            QTest.qWait(10)

    def test_click_on_visible_bar_is_allowed_with_same_screen_fullscreen_state(self):
        self.notice("DISPLAY1")
        self.assertTrue(self.manager.hosts["DISPLAY1"].session._fullscreen)
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        self.assert_open()
        self.assertIn(("fullscreen", "DISPLAY1", True), self.adapter.events)

    def test_click_on_visible_bar_is_allowed_with_other_screen_fullscreen_state(self):
        self.notice("DISPLAY2")
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        self.assert_open()
        self.assertTrue(self.manager.hosts["DISPLAY2"].session._fullscreen)

    def test_explicit_focus_action_is_allowed_when_both_sessions_report_fullscreen(self):
        self.notice("DISPLAY1")
        self.notice("DISPLAY2")
        self.manager.focus_details()
        self.assert_open()
        self.assertEqual(self.fixture.settings, [])

    def test_fresh_pointer_hover_can_open_after_fullscreen_notice(self):
        self.notice("DISPLAY1")
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_1")
        self.assertTrue(self.manager._hover_timer.isActive())
        self.wait_for_panel()
        self.assert_open(item="b_1", pinned=False)

    def test_queued_other_screen_notice_does_not_veto_new_user_click(self):
        self.notice("DISPLAY2", refresh=False)
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        panel = self.assert_open()
        self.manager._refresh()
        self.assertIs(self.manager._panel, panel)
        self.assert_open()

    def test_enter_cancels_old_automatic_hover_without_opening_then_accepts_new_hover(self):
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_0")
        self.assertTrue(self.manager._hover_timer.isActive())
        self.notice("DISPLAY1")
        self.assertIsNone(self.manager._pending_hover)
        self.assertFalse(self.manager._hover_timer.isActive())
        QTest.qWait(420)
        self.assertIsNone(self.manager._panel)
        self.assertEqual([window.kind for window in self.fixture.windows], ["bar", "bar"])
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_1")
        self.wait_for_panel()
        self.assert_open(item="b_1", pinned=False)

    def test_queued_enter_cancels_older_hover_before_coalesced_refresh(self):
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_0")
        self.assertTrue(self.manager._hover_timer.isActive())
        self.notice("DISPLAY1", refresh=False)
        self.assertIsNone(self.manager._pending_hover)
        self.assertFalse(self.manager._hover_timer.isActive())
        self.manager._refresh()
        QTest.qWait(420)
        self.assertIsNone(self.manager._panel)
        self.assertEqual([window.kind for window in self.fixture.windows], ["bar", "bar"])

    def test_fresh_hover_after_queued_enter_survives_that_older_notice_refresh(self):
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_0")
        self.notice("DISPLAY1", refresh=False)
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_1")
        self.manager._refresh()
        self.assertEqual(self.manager._pending_hover, ("DISPLAY1", "b_1"))
        self.assertTrue(self.manager._hover_timer.isActive())
        self.wait_for_panel()
        self.assert_open(item="b_1", pinned=False)

    def test_other_screen_enter_preserves_existing_user_pinned_detail(self):
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        panel = self.assert_open()
        self.notice("DISPLAY2")
        QTest.qWait(280)
        self.assertIs(self.manager._panel, panel)
        self.assert_open()
        self.assertTrue(self.manager.hosts["DISPLAY2"].session._fullscreen)

    def test_notice_during_explicit_panel_placement_preserves_user_request(self):
        place = self.adapter.place_panel
        notified = False

        def place_and_notify(*args):
            nonlocal notified
            place(*args)
            if not notified:
                notified = True
                self.notice("DISPLAY2", refresh=False)

        self.adapter.place_panel = place_and_notify
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        panel = self.assert_open()
        self.assertTrue(notified)
        QTest.qWait(280)
        self.assertIs(self.manager._panel, panel)
        self.assert_open()

    def test_pinned_detail_is_not_retargeted_by_a_later_hover(self):
        self.manager.hosts["DISPLAY1"].state.clickMetric("b_0")
        panel = self.assert_open()
        self.manager.hosts["DISPLAY2"].session.fullscreen(True)
        self.manager.hosts["DISPLAY2"].state.hoverMetric("b_1")
        QTest.qWait(420)
        self.assertIs(self.manager._panel, panel)
        self.assert_open()
        self.assertFalse(self.manager._hover_timer.isActive())

    def test_repeated_same_host_enter_keeps_new_hover_pending_and_new_hover_panel(self):
        self.notice("DISPLAY1")
        self.manager.hosts["DISPLAY1"].state.hoverMetric("b_1")
        self.assertEqual(self.manager._pending_hover, ("DISPLAY1", "b_1"))
        sequence = self.manager._detail_serial
        self.notice("DISPLAY1", refresh=False)
        self.assertEqual(self.manager._pending_hover, ("DISPLAY1", "b_1"))
        self.assertTrue(self.manager._hover_timer.isActive())
        self.assertEqual(self.manager._detail_serial, sequence)
        self.manager._refresh()
        self.wait_for_panel()
        panel = self.assert_open(item="b_1", pinned=False)
        for _ in range(3):
            self.notice("DISPLAY1")
        QTest.qWait(280)
        self.assertIs(self.manager._panel, panel)
        self.assert_open(item="b_1", pinned=False)

    def test_multiscreen_enter_exit_and_position_updates_keep_click_and_hover_usable(self):
        self.notice("DISPLAY1")
        self.notice("DISPLAY2")
        flags = ((True, True), (True, False), (False, True), (True, True))
        for index, (first, second) in enumerate(flags):
            with self.subTest(first=first, second=second):
                self.notice("DISPLAY1", first, refresh=False)
                self.notice("DISPLAY2", second, refresh=False)
                for host in self.manager.hosts.values():
                    self.manager.native_message(
                        host.binding.hwnd, self.adapter.callback_message, fixtures.ABN_POSCHANGED, 0,
                    )
                self.manager._refresh()
                self.assertEqual(self.manager.hosts["DISPLAY1"].session._fullscreen, first)
                self.assertEqual(self.manager.hosts["DISPLAY2"].session._fullscreen, second)
                display = "DISPLAY1" if index % 2 == 0 else "DISPLAY2"
                state = self.manager.hosts[display].state
                state.clickMetric("b_0")
                self.assert_open(display)
                self.manager.close_panel()
                state.hoverMetric("b_1")
                self.wait_for_panel()
                self.assert_open(display, "b_1", pinned=False)
                self.manager.close_panel()

    def test_closed_or_paused_manager_is_not_reopened_by_bar_input(self):
        self.manager.pause()
        self.manager.click("DISPLAY1", "b_0")
        self.manager.hover("DISPLAY1", "b_0")
        self.assertIsNone(self.manager._panel)
        self.assertFalse(self.manager.hosts)
        self.manager.close()
        self.manager.focus_details()
        self.assertIsNone(self.manager._panel)
        self.assertFalse(self.manager.hosts)
        self.assertEqual(self.fixture.settings, [])

    def test_inflight_hover_enter_clears_only_its_own_detail_publication(self):
        for stage in ("constructor", "emit", "emit_replacement"):
            with self.subTest(stage=stage):
                fixture = fixtures.TopBarRuntimeTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                manager = fixture.manager
                manager.apply(fixtures.config(mode="all"))
                host = manager.hosts["DISPLAY1"]
                fired = False
                original_make = manager._make_window

                def cancel_hover():
                    nonlocal fired
                    if fired:
                        return
                    fired = True
                    manager.native_message(
                        host.binding.hwnd, fixture.adapter.callback_message,
                        fixtures.ABN_FULLSCREENAPP, 1,
                    )
                    if stage == "emit_replacement":
                        manager.click("DISPLAY1", "b_1")

                def make_and_cancel(*args):
                    window = original_make(*args)
                    cancel_hover()
                    return window

                if stage == "constructor":
                    manager._make_window = make_and_cancel
                else:
                    host.state.detailChanged.connect(cancel_hover)
                try:
                    manager._show_panel(host, "b_0", False)
                finally:
                    manager._make_window = original_make

                self.assertTrue(fired)
                details = [window for window in fixture.windows if window.kind == "details"]
                if stage == "emit_replacement":
                    panel = manager._panel
                    self.assertIsNotNone(panel, manager.detail_diagnostics())
                    self.assertTrue(panel["pinned"])
                    self.assertEqual(panel["item"], "b_1")
                    self.assertEqual(host.state._detail["id"], "b_1")
                    self.assertEqual(host.state._detail["mode"], "pinned")
                    self.assertTrue(manager._panel_visible(panel))
                    self.assertEqual(len(details), 1)
                    QTest.qWait(10)
                    self.assertIs(manager._panel, panel)
                    self.assertEqual(host.state._detail["id"], "b_1")
                else:
                    self.assertIsNone(manager._panel)
                    self.assertEqual(host.state._detail, {})
                    self.assertEqual(len(details), int(stage == "constructor"))
                    self.assertTrue(all(window.deleted for window in details))
                self.assertEqual(manager.retired, [])
                manager.close()

    def test_duplicate_enter_during_drained_batch_preserves_fresh_hover(self):
        self.notice("DISPLAY2", refresh=False)
        self.manager.hover("DISPLAY2", "b_1")
        sequence = self.manager._detail_serial
        original_sync = self.manager._sync_host
        notified = False

        def sync_and_repeat_notice(host, **options):
            nonlocal notified
            if host is self.manager.hosts["DISPLAY1"] and not notified:
                notified = True
                self.notice("DISPLAY2", refresh=False)
            return original_sync(host, **options)

        self.manager._sync_host = sync_and_repeat_notice
        try:
            self.manager._refresh()
        finally:
            self.manager._sync_host = original_sync

        self.assertTrue(notified)
        self.assertEqual(self.manager._detail_serial, sequence)
        self.assertEqual(self.manager._pending_hover, ("DISPLAY2", "b_1"))
        self.assertTrue(self.manager._hover_timer.isActive())
        self.assertTrue(self.manager.hosts["DISPLAY2"].session._fullscreen)
        self.wait_for_panel()
        self.assert_open("DISPLAY2", "b_1", pinned=False)


if __name__ == "__main__":
    unittest.main()
