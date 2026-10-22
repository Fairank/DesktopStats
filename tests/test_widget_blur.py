"""Pure injected API tests; no Qt, native DLL or actual window is required."""

import ctypes as c
import importlib.util
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import native_widget_material as material

HANDLE = 0x123456789ABCDE if c.sizeof(c.c_void_p) == 8 else 0xABCDE


class FakeAPI:
    def __init__(self):
        self.thread = threading.main_thread().native_id
        self.pid = os.getpid()
        self.live = True
        self.calls, self.queries, self.responses = [], [], []

    def is_window(self, hwnd):
        self.queries.append(("live", hwnd))
        return self.live

    def owner(self, hwnd):
        self.queries.append(("owner", hwnd))
        return self.thread, self.pid

    def set_blur(self, hwnd, enabled):
        self.calls.append((hwnd, enabled))
        response = self.responses.pop(0) if self.responses else (1, 0)
        if isinstance(response, Exception):
            raise response
        return response


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class FakeDLL:
    def __init__(self):
        self.calls = []
        self.IsWindow = Function(lambda hwnd: hwnd.value == HANDLE)
        self.GetWindowThreadProcessId = Function(self.owner)
        self.SetWindowCompositionAttribute = Function(self.request)

    def owner(self, hwnd, pointer):
        c.cast(pointer, c.POINTER(material.DWORD)).contents.value = os.getpid()
        return threading.get_native_id()

    def request(self, hwnd, pointer):
        data = c.cast(pointer, c.POINTER(material._CompositionData)).contents
        policy = c.cast(data.data, c.POINTER(material._AccentPolicy)).contents
        self.calls.append(
            (
                hwnd.value,
                data.attribute,
                data.size,
                policy.state,
                policy.flags,
                policy.gradient,
                policy.animation,
                c.get_last_error(),
            )
        )
        c.set_last_error(87)
        return 1


class WidgetBlurTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(c, "WinDLL", side_effect=AssertionError("Real DLL is forbidden"))
        self.dll_guard = guard.start()
        self.addCleanup(guard.stop)
        self.api = FakeAPI()
        self.backend = material.WidgetBlurBackend(self.api)

    def test_import_constructor_and_empty_close_do_not_load_dll(self):
        spec = importlib.util.spec_from_file_location(
            "isolated_widget_blur", Path(material.__file__)
        )
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        self.assertTrue(fresh.WidgetBlurBackend().close()["complete"])
        self.dll_guard.assert_not_called()

    def test_factory_is_lazy_and_created_once(self):
        factory = Mock(return_value=self.api)
        backend = material.WidgetBlurBackend(api_factory=factory)
        factory.assert_not_called()
        self.assertFalse(backend.apply(0, policy="allowed")["ok"])
        factory.assert_not_called()
        self.assertTrue(backend.apply(HANDLE, policy="allowed")["ok"])
        self.assertTrue(backend.apply(HANDLE, policy="allowed")["ok"])
        backend.clear(HANDLE)
        backend.close()
        factory.assert_called_once()

    def test_64_bit_structures_and_win_bool_signature(self):
        self.assertEqual(c.sizeof(material.HWND), c.sizeof(c.c_void_p))
        self.assertEqual(c.sizeof(material.BOOL), 4)
        self.assertEqual(c.sizeof(material.SIZE_T), c.sizeof(c.c_void_p))
        self.assertEqual(c.sizeof(material._AccentPolicy), 16)
        self.assertEqual(material._CompositionData.data.offset, c.sizeof(c.c_void_p))
        self.assertEqual(material._CompositionData.size.offset, 2 * c.sizeof(c.c_void_p))
        self.assertEqual(c.sizeof(material._CompositionData), 3 * c.sizeof(c.c_void_p))
        dll = FakeDLL()
        loader = Mock(return_value=dll)
        api = material._CtypesBlurAPI(loader)
        loader.assert_called_once_with("user32", use_last_error=True)
        self.assertEqual(
            dll.SetWindowCompositionAttribute.argtypes,
            [material.HWND, c.POINTER(material._CompositionData)],
        )
        self.assertIs(dll.SetWindowCompositionAttribute.restype, material.BOOL)
        self.assertTrue(api.is_window(HANDLE))
        self.assertEqual(api.owner(HANDLE), (threading.get_native_id(), os.getpid()))
        c.set_last_error(5)
        self.assertEqual(api.set_blur(HANDLE, True), (1, 87))
        self.assertEqual(api.set_blur(HANDLE, False), (1, 87))
        self.assertEqual(
            dll.calls, [(HANDLE, 19, 16, 3, 0, 0, 0, 0), (HANDLE, 19, 16, 0, 0, 0, 0, 0)]
        )
        with self.assertRaises(ValueError):
            api.set_blur(HANDLE, 4)
        self.dll_guard.assert_not_called()

    def test_configured_report_is_not_compositing_proof(self):
        report = self.backend.apply(HANDLE, policy={"state": "allowed", "reason": "allowed"})
        self.assertTrue(report["ok"])
        self.assertEqual(report["material"], "system-blur")
        self.assertEqual(report["status"], "configured-unverified")
        self.assertTrue(report["blur_configured"])
        self.assertTrue(report["coating_allowed"])
        self.assertTrue(report["coating_translucent"])
        self.assertFalse(report["compositing_verified"])
        self.assertEqual(report["bool_result"], 1)
        self.assertEqual(report["last_error"], 0)
        self.assertEqual(self.api.calls, [(HANDLE, True)])

    def test_no_acrylic_mode_is_exposed(self):
        with self.assertRaises(TypeError):
            self.backend.apply(HANDLE, policy="allowed", mode="acrylic")
        self.assertEqual(self.api.calls, [])

    def test_policy_disabled_unknown_none_or_invalid_clears_old_blur(self):
        for policy in ("disabled", "unknown", None, "ALLOWED", True, [], {"state": True}):
            with self.subTest(policy=policy):
                self.backend.apply(HANDLE, policy="allowed")
                result = self.backend.apply(HANDLE, policy=policy)
                self.assertEqual(self.api.calls[-1], (HANDLE, False))
                self.assertFalse(result["blur_configured"])
                self.assertFalse(result["coating_allowed"])
                self.assertFalse(result["coating_translucent"])
                self.assertEqual(result["material"], "solid")
                self.assertFalse(result["compositing_verified"])

    def test_default_unknown_policy_never_requests_new_blur(self):
        result = self.backend.apply(HANDLE)
        self.assertTrue(result["cleanup"]["noop"])
        self.assertEqual(result["policy"]["state"], "unknown")
        self.assertEqual(result["fallback_reason"], "transparency-policy-unavailable")
        self.assertEqual(self.api.calls, [])

    def test_explicit_accessibility_reason_is_preserved(self):
        result = self.backend.apply(HANDLE, policy={"state": "disabled", "reason": "high-contrast"})
        self.assertEqual(result["fallback_reason"], "high-contrast")
        self.assertFalse(result["coating_allowed"])

    def test_enabled_false_removes_only_our_previous_effect(self):
        self.backend.apply(HANDLE, policy="allowed")
        report = self.backend.apply(HANDLE, False, "allowed")
        self.assertTrue(report["ok"])
        self.assertEqual(self.api.calls, [(HANDLE, True), (HANDLE, False)])
        self.assertEqual(report["status"], "no-blur")
        self.assertTrue(report["coating_allowed"])
        self.assertFalse(report["coating_translucent"])
        self.assertFalse(report["blur_configured"])
        self.assertEqual(report["fallback_reason"], "material-disabled")

    def test_invalid_enabled_is_rejected_after_safe_cleanup(self):
        for enabled in (1, 0, None, "yes", []):
            with self.subTest(enabled=enabled):
                self.backend.apply(HANDLE, policy="allowed")
                report = self.backend.apply(HANDLE, enabled, "allowed")
                self.assertFalse(report["ok"])
                self.assertEqual(report["fallback_reason"], "invalid-enabled")
                self.assertEqual(self.api.calls[-1], (HANDLE, False))
                self.assertFalse(report["coating_translucent"])

    def test_request_false_preserves_bool_and_error_with_alpha_fallback(self):
        self.api.responses = [(0, 5), (1, 0)]
        report = self.backend.apply(HANDLE, policy="allowed")
        self.assertFalse(report["ok"])
        self.assertEqual(report["bool_result"], 0)
        self.assertEqual(report["last_error"], 5)
        self.assertEqual(report["fallback_reason"], "accent-request-failed")
        self.assertEqual(report["material"], "translucent")
        self.assertTrue(report["coating_translucent"])
        self.assertFalse(report["blur_configured"])
        self.assertTrue(report["cleanup"]["cleanup_complete"])
        self.assertFalse(report["blur_may_remain"])

    def test_request_exception_preserves_winerror_and_attempts_cleanup(self):
        error = OSError("synthetic request failure")
        error.winerror = 50
        self.api.responses = [error, (1, 0)]
        report = self.backend.apply(HANDLE, policy="allowed")
        self.assertEqual(report["last_error"], 50)
        self.assertEqual(report["fallback_reason"], "accent-request-exception")
        self.assertTrue(report["cleanup"]["ok"])

    def test_api_loader_failure_preserves_allowed_alpha_without_false_success(self):
        backend = material.WidgetBlurBackend(api_factory=Mock(side_effect=OSError("not supported")))
        result = backend.apply(HANDLE, policy="allowed")
        self.assertFalse(result["ok"])
        self.assertEqual(result["fallback_reason"], "native-api-unavailable")
        self.assertEqual(result["material"], "translucent")
        self.assertFalse(result["blur_configured"])
        self.assertTrue(result["coating_translucent"])
        self.assertTrue(backend.close()["complete"])

    def test_failed_policy_cleanup_does_not_claim_previous_blur_is_removed(self):
        self.backend.apply(HANDLE, policy="allowed")
        self.api.responses = [(0, 87)]
        report = self.backend.apply(HANDLE, policy="disabled")
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "cleanup-failed")
        self.assertEqual(report["fallback_reason"], "accent-clear-failed")
        self.assertEqual(report["last_error"], 87)
        self.assertTrue(report["blur_may_remain"])
        self.assertFalse(report["coating_translucent"])
        self.assertTrue(self.backend.close()["complete"])

    def test_close_retries_failed_clear_then_is_idempotent(self):
        self.api.responses = [(0, 5), (0, 87), OSError("synthetic clear failure"), (1, 0)]
        self.backend.apply(HANDLE, policy="allowed")
        report = self.backend.close()
        self.assertFalse(report["complete"])
        self.assertTrue(report["blur_may_remain"])
        self.assertTrue(self.backend.close()["complete"])
        count = len(self.api.calls)
        self.assertTrue(self.backend.close()["complete"])
        self.assertEqual(len(self.api.calls), count)

    def test_closed_backend_does_not_request_new_blur_or_hide_pending_failure(self):
        self.backend.apply(HANDLE, policy="allowed")
        self.api.responses = [(0, 5)]
        self.backend.close()
        count = len(self.api.calls)
        result = self.backend.apply(HANDLE, policy="allowed")
        self.assertFalse(result["ok"])
        self.assertEqual(result["fallback_reason"], "backend-closed")
        self.assertTrue(result["blur_may_remain"])
        self.assertEqual(len(self.api.calls), count)

    def test_invalid_handles_never_query_adapter(self):
        for hwnd in (0, -1, True, False, None, "123", 1.0, 1 << (8 * c.sizeof(material.HWND))):
            with self.subTest(hwnd=hwnd):
                result = self.backend.apply(hwnd, policy="allowed")
                self.assertEqual(result["fallback_reason"], "invalid-window-handle")
        self.assertEqual(self.api.queries, [])
        self.assertEqual(self.api.calls, [])

    def test_foreign_thread_and_dead_handle_are_rejected(self):
        for problem, reason in (
            ("pid", "window-not-owned"),
            ("thread", "window-not-gui-thread"),
            ("dead", "window-not-live"),
        ):
            with self.subTest(problem=problem):
                api = FakeAPI()
                if problem == "pid":
                    api.pid += 1
                elif problem == "thread":
                    api.thread += 1
                else:
                    api.live = False
                backend = material.WidgetBlurBackend(api)
                self.assertEqual(backend.apply(HANDLE, policy="allowed")["fallback_reason"], reason)
                self.assertFalse(backend.clear(HANDLE)["ok"])
                self.assertEqual(api.calls, [])

    def test_calling_worker_thread_cannot_query_or_write_window(self):
        result = []
        thread = threading.Thread(
            target=lambda: result.append(self.backend.apply(HANDLE, policy="allowed"))
        )
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]["fallback_reason"], "requires-gui-thread")
        self.assertEqual(self.api.queries, [])
        self.assertEqual(self.api.calls, [])

    def test_owner_is_rechecked_before_set_and_failed_cleanup(self):
        owned = (self.api.thread, self.api.pid)
        self.api.owner = Mock(
            side_effect=[owned, (owned[0], owned[1] + 1), (owned[0], owned[1] + 1)]
        )
        result = self.backend.apply(HANDLE, policy="allowed")
        self.assertFalse(result["ok"])
        self.assertTrue(result["blur_may_remain"])
        self.assertFalse(result["cleanup"]["ok"])
        self.assertEqual(self.api.calls, [])

    def test_clear_only_touched_handle_then_destroy_does_not_need_new_native_calls(self):
        self.backend.apply(HANDLE, policy="allowed")
        self.assertTrue(self.backend.clear(HANDLE + 1)["noop"])
        self.assertTrue(self.backend.clear(HANDLE)["cleanup_complete"])
        self.api.live = False
        self.assertTrue(self.backend.close()["complete"])
        self.assertEqual(self.api.calls, [(HANDLE, True), (HANDLE, False)])

    def test_lost_identity_during_close_never_writes_foreign_window(self):
        self.backend.apply(HANDLE, policy="allowed")
        self.api.pid += 1
        result = self.backend.close()
        self.assertFalse(result["complete"])
        self.assertEqual(result["pending"], [HANDLE])
        self.assertEqual(self.api.calls, [(HANDLE, True)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
