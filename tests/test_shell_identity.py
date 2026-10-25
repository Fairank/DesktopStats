"""Only injected Shell metadata APIs; no GUI, real processes or native calls."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from shell_identity import ShellIdentityReader


class FakeAPI:
    def __init__(self):
        self.windows = [101, 101]
        self.pids = [42, 42]
        self.created = 132000000000000001
        self.handle = 77
        self.close_ok = True
        self.calls = []
        self.failure = None

    def shell_window(self):
        self.calls.append("shell_window")
        return self.windows.pop(0)

    def owner_pid(self, window):
        self.calls.append(("owner_pid", window))
        return self.pids.pop(0)

    def open_process(self, pid):
        self.calls.append(("open_process", pid))
        return self.handle

    def creation_time(self, handle):
        self.calls.append(("creation_time", handle))
        if self.failure:
            raise self.failure
        return self.created

    def close_handle(self, handle):
        self.calls.append(("close_handle", handle))
        return self.close_ok


class ShellIdentityTests(unittest.TestCase):
    def test_construction_is_lazy_and_nonwindows_read_does_not_load_dll(self):
        with patch("shell_identity._CtypesShellAPI", side_effect=AssertionError("Native forbidden")) as api:
            reader = ShellIdentityReader()
            api.assert_not_called()
            with patch("shell_identity.sys.platform", "linux"):
                self.assertIsNone(reader.read())
            api.assert_not_called()

    def test_stable_shell_returns_exact_pid_and_64_bit_creation_then_closes(self):
        api = FakeAPI()
        self.assertEqual(ShellIdentityReader(api).read(), (42, 132000000000000001))
        self.assertEqual(api.calls, ["shell_window", ("owner_pid", 101), ("open_process", 42),
            ("creation_time", 77), "shell_window", ("owner_pid", 101), ("close_handle", 77)])

    def test_ctypes_protocol_uses_only_limited_process_metadata_and_closes(self):
        def owner(window, pid):
            self.assertEqual(window, 101)
            pid._obj.value = 42
            return 19

        def times(handle, created, exited, kernel, user):
            self.assertEqual(handle, 77)
            created._obj.low, created._obj.high = 0x12345678, 0x1ABCDEF0
            return 1

        user = SimpleNamespace(GetShellWindow=Mock(return_value=101),
                               GetWindowThreadProcessId=Mock(side_effect=owner))
        kernel = SimpleNamespace(OpenProcess=Mock(return_value=77), GetProcessTimes=Mock(side_effect=times),
                                 CloseHandle=Mock(return_value=1))
        with patch("shell_identity.sys.platform", "win32"), patch(
                "shell_identity.c.WinDLL", side_effect=[user, kernel], create=True) as loader:
            reader = ShellIdentityReader()
            loader.assert_not_called()
            self.assertEqual(reader.read(), (42, 0x1ABCDEF012345678))
            self.assertEqual([call.args[0] for call in loader.call_args_list], ["user32", "kernel32"])
        kernel.OpenProcess.assert_called_once_with(0x1000, False, 42)
        kernel.CloseHandle.assert_called_once_with(77)
        self.assertEqual(user.GetShellWindow.call_count, 2)
        self.assertEqual(user.GetWindowThreadProcessId.call_count, 2)

    def test_changed_window_or_pid_during_read_is_unknown_and_closes_handle(self):
        for field, values in (("windows", [101, 202]), ("pids", [42, 43])):
            with self.subTest(field=field):
                api = FakeAPI()
                setattr(api, field, values)
                self.assertIsNone(ShellIdentityReader(api).read())
                self.assertEqual(api.calls[-1], ("close_handle", 77))

    def test_same_pid_with_different_process_birth_is_a_different_identity(self):
        first, second = FakeAPI(), FakeAPI()
        second.created += 1
        self.assertNotEqual(ShellIdentityReader(first).read(), ShellIdentityReader(second).read())

    def test_each_read_is_fresh_rather_than_a_cached_shell_observation(self):
        api = FakeAPI()
        reader = ShellIdentityReader(api)
        first = reader.read()
        api.windows, api.pids, api.created = [303, 303], [43, 43], api.created + 10
        second = reader.read()
        self.assertEqual(first[0], 42)
        self.assertEqual(second, (43, first[1] + 10))
        self.assertEqual(api.calls.count(("close_handle", 77)), 2)

    def test_unavailable_shell_or_pid_never_opens_a_process(self):
        for field, values in (("windows", [0]), ("windows", [None]), ("windows", [True]),
                              ("pids", [0]), ("pids", [-1]), ("pids", [True])):
            with self.subTest(field=field, values=values):
                api = FakeAPI()
                setattr(api, field, values)
                self.assertIsNone(ShellIdentityReader(api).read())
                self.assertFalse(any(isinstance(call, tuple) and call[0] == "open_process" for call in api.calls))

    def test_denied_open_and_bad_birth_return_unknown_without_adopting_data(self):
        api = FakeAPI()
        api.handle = 0
        self.assertIsNone(ShellIdentityReader(api).read())
        self.assertFalse(any(isinstance(call, tuple) and call[0] == "close_handle" for call in api.calls))
        for created in (None, 0, -1, True, 2**64):
            with self.subTest(created=created):
                api = FakeAPI()
                api.created = created
                self.assertIsNone(ShellIdentityReader(api).read())
                self.assertEqual(api.calls[-1], ("close_handle", 77))

    def test_failure_after_open_always_attempts_close_and_is_unknown(self):
        for failure in (PermissionError("denied"), OSError("timing unavailable"), RuntimeError("gone")):
            with self.subTest(failure=failure):
                api = FakeAPI()
                api.failure = failure
                self.assertIsNone(ShellIdentityReader(api).read())
                self.assertEqual(api.calls[-1], ("close_handle", 77))
        api = FakeAPI()
        api.close_ok = False
        self.assertIsNone(ShellIdentityReader(api).read())
        self.assertEqual(api.calls[-1], ("close_handle", 77))
        api = FakeAPI()
        with patch.object(api, "close_handle", side_effect=OSError("close failed")) as close:
            self.assertIsNone(ShellIdentityReader(api).read())
        close.assert_called_once_with(77)


if __name__ == "__main__":
    unittest.main()
