"""Fake-clock scheduling only; never imports Qt/native or creates a window."""

import json
import unittest
from dataclasses import FrozenInstanceError, replace

from settings_material_lifecycle import SettingsMaterialLifecycle

GOOD = dict(material="desktop-acrylic", status="configured-unverified", backdrop_result=0,
            backdrop_type=3, compositing_verified=False)
FAILED = dict(material="solid", status="fallback", fallback_reason="frame-extension-failed",
              frame_result=-2147467259, compositing_verified=False)


class Clock:
    def __init__(self):
        self.now = 100.

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SettingsMaterialLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.life = SettingsMaterialLifecycle(clock=self.clock)

    def context(self, **overrides):
        values = dict(handle=123, visible=True, window_state="normal", policy="allowed")
        values.update(overrides)
        return self.life.update_context(**values)

    def due(self, delay=.15):
        self.clock.advance(delay)
        request = self.life.take_due()
        self.assertIsNotNone(request)
        return request

    def test_no_window_context_means_no_timer_or_action(self):
        self.assertIsNone(self.life.next_delay_ms())
        self.assertIsNone(self.life.take_due())
        self.assertFalse(self.life.notify("shown"))

    def test_show_and_activation_burst_coalesce_on_trailing_150ms(self):
        self.context()
        self.assertEqual(self.life.next_delay_ms(), 150)
        self.clock.advance(.1)
        self.life.notify("shown")
        self.life.notify("activated")
        self.assertEqual(self.life.next_delay_ms(), 150)
        self.clock.advance(.149)
        self.assertIsNone(self.life.take_due())
        request = self.due(.001)
        self.assertIn("activated", request.reasons)
        self.assertIn("shown", request.reasons)
        self.assertEqual(self.life.metadata()["applies_total"], 1)
        self.assertIsNone(self.life.take_due())

    def test_request_is_immutable_and_one_inflight(self):
        self.context()
        request = self.due()
        with self.assertRaises(FrozenInstanceError):
            request.handle = 456
        self.assertIsNone(self.life.next_delay_ms())
        self.assertIsNone(self.life.take_due())
        self.assertFalse(self.life.complete(replace(request), GOOD))
        self.assertTrue(self.life.complete(request, GOOD))
        self.assertFalse(self.life.complete(request, GOOD))

    def test_success_stops_and_never_claims_rendered_verification(self):
        self.context()
        request = self.due()
        self.life.complete(request, {**GOOD, "compositing_verified": True})
        self.assertEqual(self.life.metadata()["state"], "configured_unverified")
        self.assertFalse(self.life.metadata()["compositing_verified"])
        self.assertFalse(self.life.metadata()["last_report"]["compositing_verified"])
        self.clock.advance(1000)
        self.assertIsNone(self.life.take_due())
        self.assertIsNone(self.life.next_delay_ms())

    def test_failure_retries_250ms_then_1s_then_exhausts(self):
        self.context()
        first = self.due()
        self.life.complete(first, FAILED)
        self.assertEqual(self.life.next_delay_ms(), 250)
        second = self.due(.25)
        self.assertEqual(second.attempt, 2)
        self.life.complete(second, FAILED)
        self.assertEqual(self.life.next_delay_ms(), 1000)
        third = self.due(1)
        self.assertEqual(third.attempt, 3)
        self.life.complete(third, FAILED)
        self.assertEqual(self.life.metadata()["state"], "exhausted")
        self.assertIsNone(self.life.next_delay_ms())
        self.clock.advance(100)
        self.assertIsNone(self.life.take_due())
        self.assertEqual(self.life.metadata()["last_report"]["frame_result"], -2147467259)

    def test_success_on_retry_stops_budget_early(self):
        self.context()
        self.life.complete(self.due(), FAILED)
        self.life.complete(self.due(.25), GOOD)
        self.assertIsNone(self.life.next_delay_ms())
        self.assertEqual(self.life.metadata()["applies_total"], 2)

    def test_event_during_backoff_does_not_reset_or_accelerate_budget(self):
        self.context()
        self.life.complete(self.due(), FAILED)
        self.clock.advance(.1)
        self.assertTrue(self.life.notify("deactivated"))
        self.assertEqual(self.life.next_delay_ms(), 150)
        second = self.due(.15)
        self.assertEqual(second.attempt, 2)
        self.assertIn("deactivated", second.reasons)
        self.assertIn("retry", second.reasons)

    def test_reentrant_events_during_apply_do_not_create_a_loop(self):
        self.context()
        request = self.due()
        for event in self.life.EVENTS:
            self.assertFalse(self.life.notify(event))
        self.life.complete(request, GOOD)
        self.assertIsNone(self.life.next_delay_ms())

    def test_move_sample_and_ordinary_resize_are_noops(self):
        self.context()
        self.life.complete(self.due(), GOOD)
        for _ in range(100):
            for event in ("moved", "resize", "sample", "reading", "unknown"):
                self.assertFalse(self.life.notify(event))
            self.assertFalse(self.context())
        self.assertIsNone(self.life.next_delay_ms())
        self.assertEqual(self.life.metadata()["applies_total"], 1)

    def test_only_changed_window_state_schedules_resize_recovery(self):
        self.context()
        self.life.complete(self.due(), GOOD)
        self.context(window_state="maximized")
        request = self.due()
        self.assertIn("window_state_changed", request.reasons)
        self.life.complete(request, GOOD)
        self.assertFalse(self.context(window_state="maximized"))
        self.assertIsNone(self.life.next_delay_ms())

    def test_hidden_cancels_pending_and_show_starts_fresh_episode(self):
        self.context()
        self.context(visible=False)
        self.clock.advance(10)
        self.assertIsNone(self.life.take_due())
        self.assertIsNone(self.life.next_delay_ms())
        self.assertFalse(self.life.notify("activated"))
        self.context()
        self.assertEqual(self.due().attempt, 1)

    def test_minimized_cancels_retry_and_restore_does_not_reuse_token(self):
        self.context()
        first = self.due()
        self.life.complete(first, FAILED)
        self.context(window_state="minimized")
        self.assertIsNone(self.life.next_delay_ms())
        self.assertFalse(self.life.complete(first, GOOD))
        self.context()
        self.assertEqual(self.due().attempt, 1)

    def test_hide_during_apply_rejects_report(self):
        self.context()
        first = self.due()
        self.context(visible=False)
        self.assertFalse(self.life.complete(first, GOOD))
        self.assertEqual(self.life.metadata()["last_report"], {})

    def test_handle_destroyed_and_recreated_rejects_old_request(self):
        self.context()
        first = self.due()
        self.context(handle=0)
        self.assertIsNone(self.life.next_delay_ms())
        self.context(handle=456)
        self.assertFalse(self.life.complete(first, GOOD))
        second = self.due()
        self.assertEqual(second.handle, 456)
        self.assertGreater(second.generation, first.generation)
        self.assertTrue(self.life.complete(second, GOOD))

    def test_same_hwnd_reuse_after_destroy_has_new_generation(self):
        self.context()
        first = self.due()
        self.context(handle=0)
        self.context(handle=123)
        self.assertFalse(self.life.complete(first, GOOD))
        self.assertGreater(self.due().generation, first.generation)

    def test_historical_report_remains_bound_to_its_old_handle_and_generation(self):
        self.context()
        first = self.due()
        self.life.complete(first, FAILED)
        self.context(handle=456)
        second = self.due()
        metadata = self.life.metadata()
        self.assertEqual(metadata['last_request']['token'], second.token)
        self.assertEqual(metadata['last_report_token'], first.token)
        self.assertEqual(metadata['last_report_handle'], 123)
        self.assertEqual(metadata['last_report_generation'], first.generation)
        self.life.complete(second, GOOD)
        self.assertEqual(self.life.metadata()['last_report_handle'], 456)

    def test_unconfirmed_or_fallback_report_never_counts_as_success(self):
        for overrides in (dict(backdrop_type=1), dict(backdrop_result=-1), dict(status='fallback'), dict(material='solid')):
            with self.subTest(overrides=overrides):
                self.setUp()
                self.context()
                self.life.complete(self.due(), {**GOOD, **overrides})
                self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_known_disabled_policy_clears_once_without_retry(self):
        self.context(policy="disabled")
        request = self.due()
        self.assertEqual(request.policy, "disabled")
        self.life.complete(request, FAILED)
        self.assertEqual(self.life.metadata()["state"], "policy_disabled")
        self.assertIsNone(self.life.next_delay_ms())
        for event in self.life.EVENTS:
            self.assertFalse(self.life.notify(event))

    def test_disabled_then_allowed_starts_new_episode(self):
        self.context(policy="disabled")
        self.life.complete(self.due(), FAILED)
        self.context(policy="allowed")
        self.life.complete(self.due(), GOOD)
        self.assertEqual(self.life.metadata()["state"], "configured_unverified")

    def test_query_unknown_is_not_misclassified_as_explicit_policy_disable(self):
        self.context(policy="unknown")
        self.life.complete(self.due(), dict(material="solid", fallback_reason="transparency-disabled"))
        self.assertEqual(self.life.metadata()["state"], "retry_wait")
        self.assertEqual(self.life.next_delay_ms(), 250)

    def test_unsupported_or_intentionally_disabled_request_has_no_retry(self):
        for reason in ("unsupported-windows", "material-disabled"):
            with self.subTest(reason=reason):
                self.setUp()
                self.context()
                self.life.complete(self.due(), dict(material="solid", fallback_reason=reason))
                self.assertEqual(self.life.metadata()["state"], "unavailable")
                self.assertIsNone(self.life.next_delay_ms())

    def test_inactive_notification_does_not_claim_policy_failure(self):
        self.context()
        self.life.complete(self.due(), GOOD)
        self.life.notify("deactivated")
        request = self.due()
        self.assertEqual(request.policy, "allowed")
        self.life.complete(request, GOOD)
        self.assertEqual(self.life.metadata()["state"], "configured_unverified")

    def test_later_real_lifecycle_event_can_restart_exhausted_episode(self):
        self.context()
        for index, delay in enumerate((.15, .25, 1)):
            self.life.complete(self.due(delay), FAILED)
        self.assertEqual(self.life.metadata()["state"], "exhausted")
        self.life.notify("composition_changed")
        self.assertEqual(self.due().attempt, 1)

    def test_metadata_is_bounded_detached_json_without_arbitrary_payload(self):
        self.context()
        report = dict(FAILED, backend_error="x" * 10000, screenshot="not allowed", nested={"arbitrary": True}, renderer="Fake")
        self.life.complete(self.due(), report)
        snapshot = self.life.metadata()
        self.assertEqual(len(snapshot["last_report"]["backend_error"]), 512)
        self.assertNotIn("screenshot", snapshot["last_report"])
        self.assertNotIn("nested", snapshot["last_report"])
        self.assertEqual(snapshot["last_report"]["renderer"], "Fake")
        json.dumps(snapshot)
        snapshot["last_report"]["backend_error"] = "changed"
        self.assertEqual(len(self.life.metadata()["last_report"]["backend_error"]), 512)

    def test_close_cancels_pending_and_rejects_inflight_or_new_events(self):
        self.context()
        request = self.due()
        self.life.close()
        self.life.close()
        self.assertFalse(self.life.complete(request, GOOD))
        self.assertFalse(self.context(handle=456))
        self.assertFalse(self.life.notify("shown"))
        self.assertIsNone(self.life.next_delay_ms())
        self.assertIsNone(self.life.take_due())
        self.assertEqual(self.life.metadata()["state"], "closed")

    def test_invalid_context_or_scheduler_options_fail_explicitly(self):
        for options in (dict(debounce_ms=-1), dict(debounce_ms=float("nan")), dict(retry_delays=(0,)), dict(retry_delays=(float("inf"),)), dict(retry_delays=(1,) * 9)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                SettingsMaterialLifecycle(**options)
        for context in (dict(handle=True), dict(handle=-1), dict(visible=1), dict(policy="off"), dict(window_state="fullscreen")):
            with self.subTest(context=context), self.assertRaises(ValueError):
                self.context(**context)

    def test_empty_retry_budget_still_attempts_once(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, retry_delays=())
        self.context()
        self.life.complete(self.due(), FAILED)
        self.assertEqual(self.life.metadata()["state"], "exhausted")
        self.assertIsNone(self.life.next_delay_ms())

    def test_explicit_request_is_immediate_but_cannot_override_pause_or_inflight(self):
        self.assertFalse(self.life.request_now())
        self.context()
        self.assertTrue(self.life.request_now('apply'))
        self.assertEqual(self.life.next_delay_ms(), 0)
        request = self.life.take_due()
        self.assertEqual(request.reasons, ('explicit:apply',))
        self.assertFalse(self.life.request_now('nested'))
        self.life.complete(request, GOOD)
        self.context(visible=False)
        self.assertFalse(self.life.request_now('show'))

    def test_explicit_disabled_cleanup_has_no_retry(self):
        self.context(policy='disabled')
        self.life.request_now('apply')
        self.life.complete(self.life.take_due(), FAILED)
        self.assertEqual(self.life.metadata()['state'], 'policy_disabled')
        self.assertIsNone(self.life.next_delay_ms())

    def test_invalid_completion_report_does_not_consume_current_request(self):
        self.context()
        request = self.due()
        with self.assertRaises(ValueError):
            self.life.complete(request, None)
        self.assertTrue(self.life.complete(request, GOOD))

    def test_unready_visible_surface_never_consumes_native_retry_budget(self):
        self.context(render_ready=False)
        self.assertEqual(self.life.metadata()['state'], 'waiting_for_render')
        self.assertFalse(self.life.request_now('first-show'))
        self.assertFalse(self.life.notify('graphics_ready'))
        self.clock.advance(10)
        self.assertIsNone(self.life.take_due())
        self.assertIsNone(self.life.next_delay_ms())
        self.assertEqual(self.life.metadata()['applies_total'], 0)
        self.context(render_ready=True)
        request = self.due()
        self.assertEqual(request.attempt, 1)
        self.assertIn('render_ready_changed', request.reasons)

    def test_render_invalidation_rejects_inflight_success_and_waits_for_new_frame(self):
        self.context()
        first = self.due()
        self.context(render_ready=False)
        self.assertFalse(self.life.complete(first, GOOD))
        self.assertIsNone(self.life.take_due())
        self.context(render_ready=True)
        second = self.due()
        self.assertGreater(second.generation, first.generation)
        self.assertEqual(second.attempt, 1)

    def test_disabled_policy_can_clear_before_first_frame_without_enabling_material(self):
        self.context(render_ready=False, policy='disabled')
        request = self.due()
        self.assertEqual(request.policy, 'disabled')
        self.life.complete(request, FAILED)
        self.assertEqual(self.life.metadata()['state'], 'policy_disabled')
        self.context(render_ready=False, policy='allowed')
        self.assertEqual(self.life.metadata()['state'], 'waiting_for_render')
        self.assertIsNone(self.life.next_delay_ms())

    def test_render_ready_requires_boolean_and_repeated_same_value_does_not_restart(self):
        with self.assertRaises(ValueError):
            self.context(render_ready=1)
        self.context(render_ready=True)
        self.life.complete(self.due(), GOOD)
        for _ in range(30):
            self.assertFalse(self.context(render_ready=True))
        self.assertIsNone(self.life.next_delay_ms())

    def test_system_blur_success_uses_its_exact_native_bool_contract(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
        self.context()
        report = dict(material='system-blur', blur_configured=True, bool_result=1,
                      status='configured-unverified', coating_translucent=True, last_error=0)
        self.life.complete(self.due(), report)
        self.assertEqual(self.life.metadata()['state'], 'configured_unverified')
        self.assertEqual(self.life.metadata()['backend'], 'system-blur')
        self.assertIsNone(self.life.next_delay_ms())
        for key in ('blur_configured', 'bool_result', 'coating_translucent', 'last_error'):
            self.assertEqual(self.life.metadata()['last_report'][key], report[key])

    def test_system_blur_never_accepts_dwm_report_as_its_own_success(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
        self.context()
        self.life.complete(self.due(), GOOD)
        self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_system_blur_requires_all_success_fields_and_raw_bool_type(self):
        base = dict(material='system-blur', blur_configured=True, bool_result=1, status='configured-unverified')
        for changes in (dict(material='translucent'), dict(blur_configured=1), dict(blur_configured=False),
                        dict(bool_result=0), dict(bool_result=None), dict(bool_result='1'),
                        dict(bool_result=.1), dict(status='fallback')):
            with self.subTest(changes=changes):
                self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
                self.context()
                self.life.complete(self.due(), {**base, **changes})
                self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_system_blur_successful_off_request_is_terminal_even_noop(self):
        for value in (1, None):
            with self.subTest(value=value):
                self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
                self.context()
                self.life.complete(self.due(), dict(material='translucent', blur_configured=False,
                    bool_result=value, ok=True, status='no-blur', fallback_reason='material-disabled', blur_may_remain=False))
                self.assertEqual(self.life.metadata()['state'], 'unavailable')
                self.assertIsNone(self.life.next_delay_ms())

    def test_system_blur_clear_failure_retries_instead_of_terminal_off(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
        self.context()
        self.life.complete(self.due(), dict(material='translucent', blur_configured=False, bool_result=0,
            ok=False, status='cleanup-failed', fallback_reason='material-disabled', blur_may_remain=True))
        self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_system_blur_failed_disabled_cleanup_is_bounded_and_can_recover(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
        self.context(policy='disabled')
        self.life.complete(self.due(), dict(material='solid', blur_configured=False, bool_result=0,
            ok=False, status='cleanup-failed', fallback_reason='accent-clear-failed', blur_may_remain=True))
        self.assertEqual(self.life.metadata()['state'], 'retry_wait')
        self.assertEqual(self.life.next_delay_ms(), 250)
        self.life.complete(self.due(.25), dict(material='solid', blur_configured=False, bool_result=1,
            ok=True, status='fallback', fallback_reason='high-contrast', blur_may_remain=False))
        self.assertEqual(self.life.metadata()['state'], 'policy_disabled')
        self.assertIsNone(self.life.next_delay_ms())

    def test_system_blur_disabled_policy_never_accepts_accidental_enable_as_clear(self):
        self.life = SettingsMaterialLifecycle(clock=self.clock, backend='system-blur')
        self.context(policy='disabled')
        self.life.complete(self.due(), dict(material='system-blur', blur_configured=True, bool_result=1,
            status='configured-unverified', blur_may_remain=True))
        self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_default_acrylic_does_not_accept_compatibility_blur_report(self):
        self.context()
        self.life.complete(self.due(), dict(material='system-blur', blur_configured=True,
                                         bool_result=1, status='configured-unverified'))
        self.assertEqual(self.life.metadata()['backend'], 'desktop-acrylic')
        self.assertEqual(self.life.metadata()['state'], 'retry_wait')

    def test_invalid_backend_fails_before_scheduling(self):
        for backend in ('acrylic', None, 1):
            with self.subTest(backend=backend), self.assertRaises(ValueError):
                SettingsMaterialLifecycle(backend=backend)


if __name__ == "__main__":
    unittest.main()
