"""Fake-only Raster blur ownership, ordering and recovery; no native windows."""

import ctypes
import os
import threading
import unittest
from unittest.mock import Mock, patch

from raster_blur_material import RasterBlurMaterial


class FakeDwm:
    def __init__(self, events):
        self.events = events
        self.pid, self.tid = os.getpid(), threading.main_thread().native_id
        self.live, self.actual, self.windows_build = True, 1, 26200
        self.fail, self.after = {}, None

    def build(self):
        return self.windows_build

    def is_window(self, _handle):
        return self.live

    def owner(self, _handle):
        return self.tid, self.pid

    def request(self, entry, default):
        self.events.append(entry)
        selected = self.fail.get(entry[0:1] + entry[2:], default)
        if self.after:
            self.after(entry)
        if isinstance(selected, Exception):
            raise selected
        return selected

    def set_backdrop(self, handle, value):
        result = self.request(("dwm", handle, value), 0)
        if result == 0:
            self.actual = value
        return result

    def extend_frame(self, handle, margins):
        return self.request(("frame", handle, margins), 0)

    def get_backdrop(self, handle):
        return self.request(("readback", handle), (0, self.actual))


class FakeAccent:
    def __init__(self, events):
        self.events, self.fail, self.after = events, {}, None

    def set_blur(self, handle, enabled):
        entry = ("accent", handle, enabled)
        self.events.append(entry)
        selected = self.fail.get(enabled, (1, 0))
        if self.after:
            self.after(entry)
        if isinstance(selected, Exception):
            raise selected
        return selected


class RasterBlurTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.dwm, self.accent = FakeDwm(self.events), FakeAccent(self.events)
        self.generation = 1
        self.paint_result = True
        self.paint_hook = None
        self.material = self.make(paint=True)
        self.loader = patch.object(ctypes, "WinDLL", side_effect=AssertionError("No native API"))
        self.no_native = self.loader.start()
        self.addCleanup(self.loader.stop)

    def tearDown(self):
        self.no_native.assert_not_called()

    def paint(self):
        self.events.append(("paint",))
        if self.paint_hook:
            self.paint_hook()
        return self.paint_result

    def make(self, *, paint=False):
        return RasterBlurMaterial(self.dwm, self.accent,
                                  paint_background=self.paint if paint else None)

    def valid(self):
        return self.generation == 1

    def apply(self, *, handle=123, serial=1, policy=None, valid=None):
        return self.material.apply(handle, policy or {"state": "allowed"},
                                   surface_id=serial, valid=valid or self.valid)

    def clear(self, *, handle=123, serial=1, valid=None):
        return self.material.clear(handle, surface_id=serial, valid=valid or self.valid)

    @staticmethod
    def clear_sequence():
        return [("accent", 123, False), ("dwm", 123, 1),
                ("frame", 123, (0, 0, 0, 0)), ("readback", 123)]

    def test_construction_and_empty_close_do_not_load_apis(self):
        with (patch("settings_acrylic_material._CtypesAcrylicAPI") as dwm,
              patch("raster_blur_material._CtypesBlurAPI") as accent):
            adapter = RasterBlurMaterial()
            self.assertTrue(adapter.close()["complete"])
            dwm.assert_not_called()
            accent.assert_not_called()

    def test_success_uses_exact_proven_b_order_and_no_visual_claim(self):
        report = self.apply()
        self.assertEqual(self.events, [
            ("dwm", 123, 1), ("frame", 123, (-1, -1, -1, -1)),
            ("readback", 123), ("accent", 123, True), ("paint",)])
        self.assertEqual(self.material.identity, (1, 123))
        self.assertTrue(self.material.prepared)
        self.assertEqual(report["material"], "system-blur")
        self.assertEqual(report["status"], "configured-unverified")
        self.assertEqual((report["backdrop_type"], report["accent_state"]), (1, 3))
        self.assertEqual(report["bool_result"], 1)
        self.assertEqual(report["frame_margins"], [-1] * 4)
        for key in ("ok", "blur_configured", "coating_allowed", "coating_translucent",
                    "background_paint_completed"):
            self.assertTrue(report[key], key)
        self.assertFalse(report["compositing_verified"])

    def test_external_painter_remains_explicit_for_existing_host_callers(self):
        self.material = self.make()
        report = self.apply()
        self.assertTrue(report["ok"])
        self.assertTrue(report["background_paint_external"])
        self.assertNotIn("background_paint_completed", report)
        self.assertNotIn(("paint",), self.events)

    def test_noncallable_painter_rejected_without_api(self):
        with self.assertRaises(TypeError):
            RasterBlurMaterial(self.dwm, self.accent, paint_background=True)
        self.assertEqual(self.events, [])

    def test_clear_confirms_wca0_dwmnone_frame0_readback_before_forgetting(self):
        self.apply()
        self.events.clear()
        report = self.clear()
        self.assertEqual(self.events, self.clear_sequence())
        self.assertTrue(report["ok"] and report["cleanup_complete"])
        self.assertIsNone(self.material.identity)
        self.assertFalse(self.material.prepared or self.material.cleanup_failed)

    def test_close_is_idempotent_and_prevents_future_enable(self):
        self.apply()
        self.events.clear()
        self.assertTrue(self.material.close()["complete"])
        self.assertEqual(self.events, self.clear_sequence())
        self.events.clear()
        self.assertTrue(self.material.close()["complete"])
        self.assertFalse(self.apply()["ok"])
        self.assertEqual(self.events, [])

    def test_disabled_and_unknown_policy_remove_all_state_without_paint(self):
        for policy in ({"state": "disabled", "reason": "user-setting"},
                       {"state": "unknown"}, {}, {"state": "not-valid"}):
            with self.subTest(policy=policy):
                self.material = self.make(paint=True)
                self.apply()
                self.events.clear()
                result = self.material.apply(123, policy, surface_id=1, valid=self.valid)
                self.assertEqual(self.events, self.clear_sequence())
                self.assertTrue(result["ok"] and result["cleanup_complete"])
                self.assertFalse(result["blur_configured"] or result["coating_translucent"])
                self.assertIsNone(self.material.identity)

    def test_failed_apply_at_each_native_step_clears_and_never_paints(self):
        scenarios = (("dwm", 1), ("frame", (-1, -1, -1, -1)),
                     ("readback",), ("accent", True))
        for key in scenarios:
            with self.subTest(key=key):
                self.material = self.make(paint=True)
                self.dwm.fail.clear()
                self.accent.fail.clear()
                if key[0] == "accent":
                    self.accent.fail[True] = (0, 5)
                elif key[0] == "readback":
                    # First read fails; cleanup read can still confirm removal.
                    calls = []

                    def read(handle):
                        self.events.append(("readback", handle))
                        calls.append(1)
                        return (1, 3) if len(calls) == 1 else (0, 1)

                    self.dwm.get_backdrop = read
                else:
                    # DWMnone is also used during cleanup, so reset after first.
                    original = self.dwm.request
                    seen = []

                    def request(entry, default):
                        if not seen and entry[0:1] + entry[2:] == key:
                            seen.append(1)
                            self.events.append(entry)
                            return 1
                        return original(entry, default)

                    self.dwm.request = request
                self.events.clear()
                report = self.apply()
                self.assertFalse(report["ok"] or report["coating_translucent"])
                self.assertNotIn(("paint",), self.events)
                self.assertEqual(self.events[-4:], self.clear_sequence())
                self.assertTrue(report["cleanup"]["cleanup_complete"])
                self.assertIsNone(self.material.identity)
                # Each iteration uses fresh API objects.
                self.dwm, self.accent = FakeDwm(self.events), FakeAccent(self.events)

    def test_failed_paint_clears_the_exact_same_surface(self):
        self.paint_result = False
        report = self.apply()
        self.assertFalse(report["ok"])
        self.assertIn(("paint",), self.events)
        self.assertEqual(self.events[-4:], self.clear_sequence())
        self.assertTrue(report["cleanup"]["cleanup_complete"])

    def test_raising_paint_clears_and_bounds_error_text(self):
        self.paint_hook = Mock(side_effect=RuntimeError("x" * 1000))
        report = self.apply()
        self.assertFalse(report["ok"])
        self.assertLessEqual(len(report["backend_error"]), 500)
        self.assertEqual(self.events[-4:], self.clear_sequence())

    def test_accent_clear_failure_retains_identity_until_retry(self):
        self.apply()
        self.events.clear()
        self.accent.fail[False] = (0, 5)
        result = self.clear()
        self.assertEqual(self.events, self.clear_sequence())
        self.assertFalse(result["cleanup_complete"])
        self.assertTrue(result["blur_may_remain"] and self.material.cleanup_failed)
        self.assertEqual(self.material.identity, (1, 123))
        self.events.clear()
        self.assertFalse(self.apply()["ok"])
        self.assertEqual(self.events, [])
        self.accent.fail.clear()
        self.assertTrue(self.clear()["cleanup_complete"])
        self.assertIsNone(self.material.identity)

    def test_each_dwm_cleanup_failure_retains_and_can_retry(self):
        for key, failure in ((('dwm', 1), 5), (('frame', (0, 0, 0, 0)), 5),
                             (('readback',), (0, 3))):
            with self.subTest(key=key):
                self.material = self.make(paint=True)
                self.apply()
                self.dwm.fail[key] = failure
                self.events.clear()
                result = self.clear()
                self.assertEqual(self.events, self.clear_sequence())
                self.assertFalse(result["cleanup_complete"])
                self.assertEqual(self.material.identity, (1, 123))
                self.dwm.fail.clear()
                self.assertTrue(self.material.close()["complete"])

    def test_cleanup_exceptions_continue_best_effort_without_forgetting_identity(self):
        self.apply()
        self.accent.fail[False] = OSError("failed WCA")
        self.dwm.fail[("dwm", 1)] = OSError("failed DWM")
        self.events.clear()
        result = self.clear()
        self.assertEqual(self.events, self.clear_sequence())
        self.assertFalse(result["cleanup_complete"])
        self.assertEqual(self.material.identity, (1, 123))
        self.assertIn("failed WCA", result["backend_error"])
        self.accent.fail.clear()
        self.dwm.fail.clear()
        self.assertTrue(self.clear()["cleanup_complete"])

    def test_disabled_policy_can_retry_failed_cleanup_without_enabling(self):
        self.apply()
        self.accent.fail[False] = (0, 5)
        self.assertFalse(self.clear()["cleanup_complete"])
        self.accent.fail.clear()
        self.events.clear()
        report = self.apply(policy={"state": "disabled"})
        self.assertTrue(report["cleanup_complete"])
        self.assertEqual(self.events, self.clear_sequence())

    def test_replacement_handle_and_serial_cannot_clear_or_enable_old_identity(self):
        self.apply()
        self.events.clear()
        for args in (dict(handle=456), dict(serial=2)):
            with self.subTest(args=args):
                self.assertFalse(self.apply(**args)["ok"])
                self.assertFalse(self.clear(**args)["ok"])
        self.assertEqual(self.events, [])
        self.assertEqual(self.material.identity, (1, 123))

    def test_surface_change_during_each_step_prevents_later_native_requests(self):
        for step in ("dwm", "frame", "readback", "accent", "paint"):
            with self.subTest(step=step):
                self.generation = 1
                self.events.clear()
                self.dwm, self.accent = FakeDwm(self.events), FakeAccent(self.events)
                self.material = self.make(paint=True)

                def changed(entry):
                    if entry[0] == step:
                        self.generation = 2

                self.dwm.after = self.accent.after = changed
                self.paint_hook = lambda: changed(("paint",))
                report = self.apply()
                self.assertFalse(report["ok"] or report["coating_translucent"])
                self.assertEqual(self.events[-1][0], step)
                self.assertEqual(self.material.identity, (1, 123))
                self.assertFalse(report["cleanup"]["cleanup_complete"])
                self.events.clear()
                self.assertFalse(self.material.close()["complete"])
                self.assertEqual(self.events, [])

    def test_owner_change_after_native_call_prevents_any_followup_or_replacement_clear(self):
        def change(_entry):
            self.dwm.pid = os.getpid() + 1

        self.dwm.after = change
        result = self.apply()
        self.assertFalse(result["ok"])
        self.assertEqual(self.events, [("dwm", 123, 1)])
        self.assertFalse(result["cleanup"]["cleanup_complete"])

    def test_close_reentry_at_wca_cannot_publish_success_and_cleans_after_unwind(self):
        returned = []
        self.accent.after = lambda entry: returned.append(self.material.close()) if entry[2] else None
        result = self.apply()
        self.assertFalse(result["ok"] or result["coating_translucent"])
        self.assertFalse(returned[0]["complete"])
        self.assertTrue(self.material.closed)
        self.assertEqual(self.events[-4:], self.clear_sequence())
        self.assertTrue(self.material.close()["complete"])

    def test_close_reentry_at_paint_cannot_publish_success(self):
        self.paint_hook = lambda: self.material.close()
        result = self.apply()
        self.assertFalse(result["ok"])
        self.assertEqual(self.events[-4:], self.clear_sequence())
        self.assertTrue(result["cleanup"]["cleanup_complete"])

    def test_nested_apply_and_clear_are_rejected_without_extra_native_mutation(self):
        nested = []

        def reenter(entry):
            if entry[0] == "readback":
                nested.extend((self.apply(), self.clear()))

        self.dwm.after = reenter
        self.assertTrue(self.apply()["ok"])
        self.assertEqual(len(nested), 2)
        self.assertTrue(all(row["rejected"] for row in nested))
        self.assertEqual(len(self.events), 5)

    def test_worker_cannot_use_or_close_material_or_load_any_api(self):
        result = []
        thread = threading.Thread(target=lambda: result.extend((self.apply(), self.clear(),
                                                                self.material.close())))
        thread.start()
        thread.join()
        self.assertEqual(len(result), 3)
        self.assertTrue(all(row["fallback_reason"] == "requires-gui-thread" for row in result))
        self.assertEqual(self.events, [])
        self.assertFalse(self.material.closed)

    def test_invalid_input_and_unowned_or_unsupported_windows_do_not_mutate(self):
        for handle, serial, valid in ((0, 1, self.valid), (True, 1, self.valid),
                                      (123, 0, self.valid), (123, True, self.valid),
                                      (123, 1, lambda: 1), (123, 1, lambda: False)):
            with self.subTest(handle=handle, serial=serial):
                self.assertFalse(self.apply(handle=handle, serial=serial, valid=valid)["ok"])
        for attribute, value in (("pid", os.getpid() + 1), ("tid", self.dwm.tid + 1),
                                 ("live", False), ("windows_build", 22000)):
            with self.subTest(attribute=attribute):
                old = getattr(self.dwm, attribute)
                setattr(self.dwm, attribute, value)
                self.assertFalse(self.apply()["ok"])
                setattr(self.dwm, attribute, old)
        self.assertEqual(self.events, [])

    def test_lazy_accent_factory_failure_cleans_dwm_without_claiming_success(self):
        self.material = RasterBlurMaterial(self.dwm)
        with patch("raster_blur_material._CtypesBlurAPI", side_effect=OSError("missing entrypoint")):
            result = self.apply()
        self.assertFalse(result["ok"] or result["coating_translucent"])
        self.assertEqual(self.events[-3:], self.clear_sequence()[1:])
        self.assertFalse(result["cleanup"]["cleanup_complete"])
        self.assertEqual(self.material.identity, (1, 123))

    def test_invalid_wca_results_do_not_enable_coating(self):
        for value in ((True, 0), (1, -1), (1 << 31, 0), (1,), [1, 0], None):
            with self.subTest(value=value):
                self.material = self.make(paint=True)
                self.accent.fail[True] = value
                result = self.apply()
                self.assertFalse(result["ok"] or result["coating_translucent"])
                self.assertTrue(result["cleanup"]["cleanup_complete"])


if __name__ == "__main__":
    unittest.main()
