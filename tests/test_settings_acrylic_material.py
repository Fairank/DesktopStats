"""Isolated DWM contract tests; no Qt, windows, capture or real native API."""

import ctypes
import os
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from settings_acrylic_material import SettingsAcrylicMaterial, _CtypesAcrylicAPI, _Margins


class FakeAPI:
    def __init__(self):
        self.events = []
        self.windows_build = 26200
        self.pid = os.getpid()
        self.tid = threading.main_thread().native_id
        self.live = True
        self.actual = 1
        self.fail = {}
        self.after = None

    def build(self):
        return self.windows_build

    def is_window(self, _hwnd):
        return self.live

    def owner(self, _hwnd):
        return self.tid, self.pid

    def request(self, entry, default):
        self.events.append(entry)
        selected = self.fail.get(entry[:1] + entry[2:], default)
        if self.after:
            self.after(entry)
        if isinstance(selected, Exception):
            raise selected
        return selected

    def set_backdrop(self, hwnd, value):
        result = self.request(("set", hwnd, value), 0)
        if result == 0:
            self.actual = value
        return result

    def extend_frame(self, hwnd, margins):
        return self.request(("extend", hwnd, margins), 0)

    def get_backdrop(self, hwnd):
        return self.request(("get", hwnd), (0, self.actual))


class SettingsAcrylicTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.material = SettingsAcrylicMaterial(self.api)
        self.generation = 1

    def apply(self, policy=None, serial=1, hwnd=123):
        return self.material.apply(
            hwnd,
            policy or {"state": "allowed"},
            surface_id=serial,
            valid=lambda: self.generation == serial,
        )

    def clear(self, serial=1):
        return self.material.clear(123, surface_id=serial, valid=lambda: self.generation == serial)

    def test_construction_and_empty_close_load_no_dll(self):
        with (
            patch("ctypes.WinDLL", side_effect=AssertionError("no native")),
            patch(
                "settings_acrylic_material._CtypesAcrylicAPI", side_effect=AssertionError("no API")
            ),
        ):
            material = SettingsAcrylicMaterial()
            self.assertTrue(material.close()["cleanup_complete"])

    def test_success_follows_wuji_sequence_and_theme_contract(self):
        report = self.apply()
        self.assertEqual(
            self.api.events, [("set", 123, 3), ("extend", 123, (-1, -1, -1, -1)), ("get", 123)]
        )
        self.assertEqual(report["material"], "desktop-acrylic")
        self.assertEqual(report["status"], "configured-unverified")
        self.assertEqual(
            [report[k] for k in ("backdrop_result", "frame_result", "readback_result")], [0, 0, 0]
        )
        self.assertEqual(report["backdrop_type"], 3)
        self.assertTrue(
            all(
                report[k]
                for k in ("ok", "coating_allowed", "coating_translucent", "blur_configured")
            )
        )
        self.assertFalse(report["compositing_verified"])
        self.assertNotIn("bool_result", report)
        self.assertNotIn("alpha_result", report)

    def test_clear_disables_and_confirms_readback_before_forgetting_identity(self):
        self.apply()
        self.api.events.clear()
        report = self.clear()
        self.assertEqual(
            self.api.events, [("set", 123, 1), ("extend", 123, (0, 0, 0, 0)), ("get", 123)]
        )
        self.assertTrue(report["cleanup_complete"])
        self.assertIsNone(self.material.identity)
        count = len(self.api.events)
        self.assertTrue(self.material.close()["complete"])
        self.assertEqual(len(self.api.events), count)

    def test_policy_off_and_unknown_remove_existing_material(self):
        for state in ("disabled", "unknown"):
            with self.subTest(state=state):
                self.setUp()
                self.apply()
                self.api.events.clear()
                report = self.apply({"state": state})
                self.assertTrue(report["cleanup_complete"])
                self.assertFalse(report["coating_allowed"])
                self.assertFalse(report["coating_translucent"])
                self.assertEqual(self.api.events[0], ("set", 123, 1))

    def test_fresh_policy_off_is_explicit_disable_not_acrylic_enable(self):
        report = self.apply({"state": "disabled"})
        self.assertTrue(report["ok"])
        self.assertEqual([e[2] for e in self.api.events if e[0] == "set"], [1])

    def test_invalid_policy_is_unknown_and_solid(self):
        for policy in (True, "allowed", {"state": True}):
            with self.subTest(policy=policy):
                self.setUp()
                report = self.apply(policy)
                self.assertEqual(report["policy"]["state"], "unknown")
                self.assertFalse(report["coating_translucent"])

    def test_windows10_or_unknown_build_never_mutates(self):
        for value in (19045, 22620, True, None):
            with self.subTest(build=value):
                self.setUp()
                self.api.windows_build = value
                self.assertFalse(self.apply()["ok"])
                self.assertFalse(self.api.events)

    def test_invalid_handle_and_serial_reject_before_loading_api(self):
        factory = Mock(side_effect=AssertionError("must not construct"))
        material = SettingsAcrylicMaterial(api_factory=factory)
        for hwnd in (None, True, 0, -1, 1 << (ctypes.sizeof(ctypes.c_void_p) * 8)):
            report = material.apply(hwnd, {"state": "allowed"}, surface_id=1, valid=lambda: True)
            self.assertFalse(report["ok"])
        for serial in (None, True, 0, -1):
            self.assertFalse(
                material.apply(123, {"state": "allowed"}, surface_id=serial, valid=lambda: True)[
                    "ok"
                ]
            )
        factory.assert_not_called()

    def test_no_foreign_process_or_thread_or_destroyed_window_mutations(self):
        for field, value in (("pid", os.getpid() + 1), ("tid", -1), ("live", False)):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.api, field, value)
                self.assertFalse(self.apply()["ok"])
                self.assertFalse(self.api.events)

    def test_worker_thread_cannot_apply_or_mark_backend_closed(self):
        results = []
        thread = threading.Thread(
            target=lambda: results.extend((self.apply(), self.material.close()))
        )
        thread.start()
        thread.join()
        self.assertFalse(any(r["ok"] for r in results))
        self.assertFalse(self.api.events)
        self.assertFalse(self.material.closed)

    def test_expired_or_throwing_generation_guard_never_loads_api(self):
        factory = Mock(side_effect=AssertionError("must not construct"))
        material = SettingsAcrylicMaterial(api_factory=factory)
        for valid in (lambda: False, lambda: 1, Mock(side_effect=RuntimeError("deleted"))):
            self.assertFalse(
                material.apply(123, {"state": "allowed"}, surface_id=1, valid=valid)["ok"]
            )
        factory.assert_not_called()

    def test_failed_enable_attribute_or_frame_is_cleaned(self):
        for operation in (("set", 3), ("extend", (-1, -1, -1, -1))):
            with self.subTest(operation=operation):
                self.setUp()
                self.api.fail[operation] = -2147467259
                report = self.apply()
                self.assertFalse(report["ok"])
                self.assertFalse(report["coating_translucent"])
                self.assertTrue(report["cleanup"]["cleanup_complete"])
                self.assertIsNone(self.material.identity)
                self.assertIn(("set", 123, 1), self.api.events)

    def test_wrong_or_failed_readback_never_allows_transparency(self):
        for result in ((0, 2), (-1, 3), (0, True)):
            with self.subTest(result=result):
                self.setUp()

                def get(hwnd):
                    self.api.events.append(("get", hwnd))
                    return result if self.api.actual == 3 else (0, self.api.actual)

                self.api.get_backdrop = get
                report = self.apply()
                self.assertFalse(report["coating_translucent"])
                self.assertTrue(report["cleanup"]["cleanup_complete"])

    def test_mutation_exception_still_attempts_safe_clear(self):
        self.api.fail[("set", 3)] = OSError("partial native request")
        report = self.apply()
        self.assertFalse(report["ok"])
        self.assertTrue(report["cleanup"]["cleanup_complete"])
        self.assertIn(("set", 123, 1), self.api.events)

    def test_generation_change_after_first_mutation_prevents_all_later_native_calls(self):
        self.api.after = lambda _e: setattr(self, "generation", 2)
        report = self.apply()
        self.assertEqual(self.api.events, [("set", 123, 3)])
        self.assertFalse(report["coating_translucent"])
        self.assertTrue(report["blur_may_remain"])
        self.assertFalse(self.material.close()["complete"])
        self.assertEqual(self.api.events, [("set", 123, 3)])

    def test_owner_change_after_first_mutation_prevents_all_later_native_calls(self):
        self.api.after = lambda _e: setattr(self.api, "pid", os.getpid() + 1)
        self.assertFalse(self.apply()["ok"])
        self.assertEqual(self.api.events, [("set", 123, 3)])

    def test_generation_change_inside_owner_query_prevents_first_mutation(self):
        def owner(_handle):
            self.generation = 2
            return self.api.tid, self.api.pid

        self.api.owner = owner
        self.assertFalse(self.apply()["ok"])
        self.assertFalse(self.api.events)

    def test_wrong_serial_cannot_redirect_cleanup_or_release_guard(self):
        self.apply()
        original = self.material._alive
        self.generation = 2
        count = len(self.api.events)
        self.assertFalse(self.clear(2)["ok"])
        self.assertIs(self.material._alive, original)
        self.assertFalse(self.apply(serial=2)["ok"])
        self.assertEqual(len(self.api.events), count)

    def test_failed_cleanup_blocks_reapply_but_can_retry_original_surface(self):
        self.apply()
        self.api.fail[("set", 1)] = -1
        self.assertFalse(self.clear()["cleanup_complete"])
        count = len(self.api.events)
        self.assertFalse(self.apply()["ok"])
        self.assertEqual(len(self.api.events), count)
        self.api.fail.clear()
        self.assertTrue(self.clear()["cleanup_complete"])
        self.generation = 2
        self.assertTrue(self.apply(serial=2)["ok"])

    def test_close_failure_retains_retryable_cleanup_and_closed_apply_gate(self):
        self.apply()
        self.api.fail[("extend", (0, 0, 0, 0))] = -1
        self.assertFalse(self.material.close()["complete"])
        self.assertEqual(self.material.identity, (1, 123))
        count = len(self.api.events)
        self.assertFalse(self.apply()["ok"])
        self.assertEqual(len(self.api.events), count)
        self.api.fail.clear()
        self.assertTrue(self.material.close()["complete"])
        self.assertIsNone(self.material.identity)

    def test_reentrant_close_during_native_apply_cancels_and_cleans_same_surface(self):
        def close_once(entry):
            if entry == ("set", 123, 3):
                self.api.after = None
                self.assertFalse(self.material.close()["complete"])

        self.api.after = close_once
        report = self.apply()
        self.assertFalse(report["ok"])
        self.assertFalse(any(e == ("extend", 123, (-1, -1, -1, -1)) for e in self.api.events))
        self.assertTrue(report["cleanup"]["cleanup_complete"])

    def test_reentrant_clear_or_apply_does_not_nest_native_mutations(self):
        nested = []

        def enter(entry):
            if entry == ("set", 123, 3):
                nested.extend((self.clear(), self.apply()))

        self.api.after = enter
        self.assertTrue(self.apply()["ok"])
        self.assertTrue(all(r.get("rejected") for r in nested))
        self.assertEqual(len(self.api.events), 3)

    def test_guard_callback_cannot_reenter_apply_before_transaction_starts(self):
        nested = []

        def valid():
            if not nested:
                nested.append(None)
                nested[0] = self.material.apply(
                    123, {"state": "allowed"}, surface_id=1, valid=lambda: True
                )
            return True

        report = self.material.apply(123, {"state": "allowed"}, surface_id=1, valid=valid)
        self.assertTrue(report["ok"])
        self.assertTrue(nested[0]["rejected"])
        self.assertEqual(len(self.api.events), 3)

    def test_malformed_hresult_is_not_success(self):
        self.api.fail[("set", 3)] = False
        report = self.apply()
        self.assertFalse(report["ok"])
        self.assertFalse(report["coating_translucent"])

    def test_native_factory_error_is_structured_solid_fallback(self):
        material = SettingsAcrylicMaterial(api_factory=Mock(side_effect=OSError("unavailable")))
        report = material.apply(123, {"state": "allowed"}, surface_id=1, valid=lambda: True)
        self.assertFalse(report["ok"])
        self.assertEqual(report["material"], "solid")
        self.assertIn("OSError", report["backend_error"])


class NativeWrapperTests(unittest.TestCase):
    def test_abi_and_exact_attributes_use_only_dwm38(self):
        user, dwm = MagicMock(), MagicMock()

        def dll(name, **_kw):
            return user if name == "user32" else dwm

        dwm.DwmSetWindowAttribute.return_value = 0
        dwm.DwmExtendFrameIntoClientArea.return_value = 0
        records = []

        def set_attr(hwnd, attribute, selected, size):
            records.append(("set", hwnd.value, attribute, selected._obj.value, size))
            return 0

        def extend(hwnd, margins):
            records.append(
                (
                    "extend",
                    hwnd.value,
                    tuple(getattr(margins._obj, k) for k in ("left", "right", "top", "bottom")),
                )
            )
            return 0

        def get_attr(hwnd, attribute, selected, size):
            records.append(("get", hwnd.value, attribute, size))
            selected._obj.value = 3
            return 0

        dwm.DwmSetWindowAttribute.side_effect = set_attr
        dwm.DwmExtendFrameIntoClientArea.side_effect = extend
        dwm.DwmGetWindowAttribute.side_effect = get_attr
        api = _CtypesAcrylicAPI(loader=dll)
        api.set_backdrop(123, 3)
        api.extend_frame(123, (-1, -1, -1, -1))
        self.assertEqual(api.get_backdrop(123), (0, 3))
        self.assertEqual(
            records,
            [("set", 123, 38, 3, 4), ("extend", 123, (-1, -1, -1, -1)), ("get", 123, 38, 4)],
        )
        self.assertEqual(ctypes.sizeof(_Margins), 16)
        self.assertEqual(ctypes.sizeof(dwm.DwmSetWindowAttribute.restype), 4)
        self.assertEqual(ctypes.sizeof(user.GetWindowThreadProcessId.restype), 4)


if __name__ == "__main__":
    unittest.main()
