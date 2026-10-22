"""Native material policy and ABI regressions; every system boundary is mocked."""

import ctypes as c
import os
import unittest
from ctypes import wintypes as w
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

from PySide6.QtCore import QByteArray, Qt
from shiboken6 import VoidPtr

import native_glass as bridge_module
import native_platform as platform


class SystemPreferenceTests(unittest.TestCase):
    def test_animation_preference_uses_only_the_read_only_client_area_query(self):
        for success, enabled, expected in ((1, 1, True), (1, 0, False), (0, 1, False)):
            with self.subTest(success=success, enabled=enabled):
                user = MagicMock()

                def query(action, parameter, output, flags):
                    self.assertEqual((action, parameter, flags), (0x1042, 0, 0))
                    output._obj.value = enabled
                    return success

                user.SystemParametersInfoW.side_effect = query
                with patch.object(platform.c, "WinDLL", return_value=user) as loader:
                    self.assertIs(platform.animations_enabled(), expected)
                loader.assert_called_once_with("user32", use_last_error=True)
                user.SystemParametersInfoW.assert_called_once()

    def test_missing_animation_api_and_policy_read_failures_disable_motion(self):
        for error in (OSError("DLL unavailable"), AttributeError("export unavailable")):
            with self.subTest(error=type(error).__name__):
                with patch.object(platform, "_system_parameters", side_effect=error):
                    self.assertFalse(platform.animations_enabled())

    def test_transparency_requires_successful_accessibility_and_registry_reads(self):
        for success, contrast, setting, expected in (
            (1, 0, 1, True),
            (1, 1, 1, False),
            (0, 0, 1, False),
            (1, 0, 0, False),
            (1, 0, "1", False),
            (1, 0, True, False),
            (1, 0, None, False),
        ):
            with self.subTest(success=success, contrast=contrast, setting=setting):

                def query(action, size, output, flags):
                    self.assertEqual(action, 0x42)
                    self.assertEqual(size, output._obj.size)
                    self.assertEqual(flags, 0)
                    output._obj.flags = contrast
                    return success

                with (
                    patch.object(platform, "_system_parameters", return_value=query),
                    patch.object(platform.winreg, "OpenKey") as open_key,
                    patch.object(platform.winreg, "QueryValueEx", return_value=(setting, 4)),
                ):
                    self.assertIs(platform.transparency_enabled(), expected)
                    if not success or contrast:
                        open_key.assert_not_called()

    def test_missing_transparency_key_does_not_enable_an_unreadable_material(self):
        def query(action, size, output, flags):
            output._obj.flags = 0
            return 1

        with (
            patch.object(platform, "_system_parameters", return_value=query),
            patch.object(platform.winreg, "OpenKey", side_effect=OSError("missing preference")),
        ):
            self.assertFalse(platform.transparency_enabled())
        with patch.object(
            platform, "_system_parameters", side_effect=AttributeError("missing API")
        ):
            self.assertFalse(platform.transparency_enabled())

    def test_preference_helpers_do_not_hide_programming_errors(self):
        for helper in (platform.animations_enabled, platform.transparency_enabled):
            with self.subTest(helper=helper.__name__):
                with patch.object(platform, "_system_parameters", side_effect=ValueError("bug")):
                    with self.assertRaises(ValueError):
                        helper()


class WidgetMaterialTests(unittest.TestCase):
    def test_policy_and_material_enablement_remain_independent_without_native_composition(self):
        for enabled, allowed, translucent, reason in (
            (True, True, True, None),
            (True, False, False, "transparency-disabled"),
            (False, True, False, "material-disabled"),
            (False, False, False, "material-disabled"),
        ):
            with self.subTest(enabled=enabled, allowed=allowed):
                with (
                    patch.object(platform, "transparency_enabled", return_value=allowed) as policy,
                    patch.object(platform.c, "WinDLL", side_effect=AssertionError("No compositor calls")) as loader,
                    patch.object(platform.sys, "getwindowsversion", side_effect=AssertionError("No OS build gate")) as version,
                ):
                    report = platform.widget_material(enabled=enabled)
                policy.assert_called_once_with()
                loader.assert_not_called()
                version.assert_not_called()
                self.assertIs(report["coating_allowed"], allowed)
                self.assertIs(report["coating_translucent"], translucent)
                self.assertEqual(report["material"], "translucent" if translucent else "solid")
                self.assertEqual(report["status"], "translucent" if translucent else "fallback")
                self.assertIs(report["blur_configured"], False)
                self.assertIs(report["compositing_verified"], False)
                if reason is None:
                    self.assertNotIn("fallback_reason", report)
                else:
                    self.assertEqual(report["fallback_reason"], reason)

    def test_default_enables_only_an_alpha_coating_not_a_verified_blur(self):
        with patch.object(platform, "transparency_enabled", return_value=True):
            report = platform.widget_material()
        self.assertEqual(report, {
            "coating_allowed": True,
            "coating_translucent": True,
            "material": "translucent",
            "blur_configured": False,
            "compositing_verified": False,
            "status": "translucent",
        })

    def test_existing_preference_read_failure_stays_fail_closed(self):
        for error in (OSError("preference unavailable"), AttributeError("query unavailable")):
            with self.subTest(error=type(error).__name__):
                with (
                    patch.object(platform, "_system_parameters", side_effect=error),
                    patch.object(platform.c, "WinDLL", side_effect=AssertionError("No compositor calls")) as loader,
                    patch.object(platform.winreg, "OpenKey") as registry,
                ):
                    report = platform.widget_material()
                loader.assert_not_called()
                registry.assert_not_called()
                self.assertIs(report["coating_allowed"], False)
                self.assertIs(report["coating_translucent"], False)
                self.assertEqual(report["material"], "solid")
                self.assertEqual(report["fallback_reason"], "transparency-disabled")
                self.assertIs(report["blur_configured"], False)
                self.assertIs(report["compositing_verified"], False)

    def test_programming_errors_are_not_reclassified_as_policy_fallback(self):
        with patch.object(platform, "transparency_enabled", side_effect=ValueError("bug")):
            with self.assertRaises(ValueError):
                platform.widget_material()


class SystemBackdropTests(unittest.TestCase):
    def setUp(self):
        self.attributes = []
        self.frames = []
        self.dwm = MagicMock()
        self.user = MagicMock()
        self.user.GetWindowLongPtrW.return_value = 0x80000

        def set_attribute(hwnd, attribute, value, size):
            self.attributes.append((hwnd, attribute, value._obj.value, size))
            return 0

        def read_attribute(hwnd, attribute, value, size):
            value._obj.value = 3
            return 0

        def extend_frame(hwnd, margins):
            value = margins._obj
            self.frames.append((value.left, value.right, value.top, value.bottom))
            return 0

        self.dwm.DwmSetWindowAttribute.side_effect = set_attribute
        self.dwm.DwmGetWindowAttribute.side_effect = read_attribute
        self.dwm.DwmExtendFrameIntoClientArea.side_effect = extend_frame
        self.loader = patch.object(
            platform.c,
            "WinDLL",
            side_effect=lambda name, **kwargs: self.dwm if name == "dwmapi" else self.user,
        )
        self.build = patch.object(
            platform.sys, "getwindowsversion", return_value=SimpleNamespace(build=26100)
        )
        self.preference = patch.object(platform, "transparency_enabled", return_value=True)
        for patcher in (self.loader, self.build, self.preference):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_supported_configuration_is_still_visually_unverified(self):
        report = platform.glass(123, dark=True)
        self.assertEqual(report["material"], "desktop-acrylic")
        self.assertEqual(report["status"], "configured-unverified")
        self.assertFalse(report["compositing_verified"])
        self.assertTrue(report["layered"])
        self.assertIn((123, 38, 3, 4), self.attributes)
        self.assertIn((123, 39, 1, 4), self.attributes)
        self.assertEqual(self.frames, [(-1, -1, -1, -1)])
        self.user.SetForegroundWindow.assert_not_called()
        self.user.SetActiveWindow.assert_not_called()
        self.user.SetFocus.assert_not_called()
        self.user.SetWindowLongPtrW.assert_not_called()

    def test_unsupported_windows_never_loads_or_configures_a_native_backend(self):
        platform.sys.getwindowsversion.return_value = SimpleNamespace(build=22000)
        report = platform.glass(123)
        platform.c.WinDLL.assert_not_called()
        self.assertEqual(report["material"], "solid")
        self.assertFalse(report["compositing_verified"])
        self.assertEqual(report["fallback_reason"], "unsupported-windows")

    def test_disabled_policy_removes_backdrop_and_full_client_frame(self):
        for enabled, preference, reason in (
            (False, True, "material-disabled"),
            (True, False, "transparency-disabled"),
        ):
            with self.subTest(enabled=enabled, preference=preference):
                self.attributes.clear()
                self.frames.clear()
                platform.transparency_enabled.return_value = preference
                report = platform.glass(123, enabled=enabled)
                self.assertEqual(report["material"], "solid")
                self.assertEqual(report["fallback_reason"], reason)
                self.assertIn((123, 38, 1, 4), self.attributes)
                self.assertNotIn(39, [attribute for _, attribute, _, _ in self.attributes])
                self.assertEqual(self.frames, [(0, 0, 0, 0)])

    def test_failed_frame_extension_does_not_request_acrylic(self):
        self.dwm.DwmExtendFrameIntoClientArea.side_effect = [-1, 0]
        report = platform.glass(123)
        self.assertEqual(report["material"], "solid")
        self.assertEqual(report["fallback_reason"], "frame-extension-failed")
        self.assertNotIn((123, 38, 3, 4), self.attributes)
        self.assertEqual(report["cleanup_frame_result"], 0)

    def test_unconfirmed_backdrop_is_explicitly_cleared(self):
        self.dwm.DwmGetWindowAttribute.side_effect = lambda *args: -1
        report = platform.glass(123)
        self.assertEqual(report["material"], "solid")
        self.assertFalse(report["compositing_verified"])
        self.assertEqual(report["fallback_reason"], "backdrop-unconfirmed")
        self.assertEqual(self.attributes[-1], (123, 38, 1, 4))
        self.assertEqual(self.frames[-1], (0, 0, 0, 0))

    def test_backend_error_removes_partial_material_and_reports_fallback(self):
        self.user.GetWindowLongPtrW.side_effect = OSError("diagnostic unavailable")
        report = platform.glass(123)
        self.assertEqual(report["material"], "solid")
        self.assertEqual(report["fallback_reason"], "native-api-unavailable")
        self.assertEqual(report["backend_error"], "diagnostic unavailable")
        self.assertEqual(self.attributes[-1], (123, 38, 1, 4))
        self.assertEqual(self.frames[-1], (0, 0, 0, 0))

    def test_missing_backend_and_failed_cleanup_do_not_escape_compatibility_boundary(self):
        platform.c.WinDLL.side_effect = AttributeError("DWM export unavailable")
        report = platform.glass(123)
        self.assertEqual(report["material"], "solid")
        self.assertIn("DWM export unavailable", report["backend_error"])
        platform.c.WinDLL.side_effect = lambda name: self.dwm if name == "dwmapi" else self.user
        self.dwm.DwmSetWindowAttribute.side_effect = OSError("setter failed")
        self.dwm.DwmExtendFrameIntoClientArea.side_effect = AttributeError("frame export missing")
        report = platform.glass(123)
        self.assertEqual(report["cleanup_backdrop_error"], "setter failed")
        self.assertEqual(report["cleanup_frame_error"], "frame export missing")

    def test_backend_programming_errors_are_not_hidden(self):
        self.dwm.DwmSetWindowAttribute.side_effect = ValueError("invalid bridge implementation")
        with self.assertRaises(ValueError):
            platform.glass(123)


class NativeFrameCapabilityTests(unittest.TestCase):
    def test_candidate_is_limited_to_windows_qpa_supported_os_and_allowed_policy(self):
        for qpa, build, preference, expected in (
            ("windows", 22621, True, True),
            ("windows", 26200, False, False),
            ("windows", 22000, True, False),
            ("offscreen", 26200, True, False),
            ("minimal", 26200, True, False),
        ):
            with self.subTest(qpa=qpa, build=build, preference=preference):
                with (
                    patch.object(
                        bridge_module.sys,
                        "getwindowsversion",
                        return_value=SimpleNamespace(build=build),
                    ),
                    patch.object(bridge_module, "transparency_enabled", return_value=preference),
                ):
                    self.assertIs(bridge_module.native_frame_supported(qpa), expected)

    def test_missing_platform_api_means_no_candidate(self):
        with patch.object(
            bridge_module.sys, "getwindowsversion", side_effect=AttributeError("no Windows")
        ):
            self.assertFalse(bridge_module.native_frame_supported("windows"))

    def test_native_flags_keep_nonactivation_and_bottom_but_avoid_frameless(self):
        native = bridge_module.widget_flags()
        legacy = bridge_module.widget_flags(False)
        for flags in (native, legacy):
            self.assertEqual(flags & Qt.WindowType_Mask, Qt.Tool)
            self.assertTrue(flags & Qt.WindowStaysOnBottomHint)
            self.assertTrue(flags & Qt.WindowDoesNotAcceptFocus)
        self.assertFalse(native & Qt.FramelessWindowHint)
        self.assertTrue(native & Qt.CustomizeWindowHint)
        self.assertFalse(native & Qt.WindowTitleHint)
        self.assertTrue(native & Qt.NoTitleBarBackgroundHint)
        self.assertTrue(legacy & Qt.FramelessWindowHint)

    def test_win32_boundary_uses_pointer_sized_handles_and_nonactivating_frame_recalculation(self):
        user = MagicMock()
        user.IsWindow.return_value = 1
        user.SetWindowPos.return_value = 1

        def identity(hwnd, process):
            process._obj.value = os.getpid()
            return 7

        user.GetWindowThreadProcessId.side_effect = identity
        user.GetWindowLongPtrW.side_effect = lambda hwnd, index: 0 if index == -16 else 0x08000080
        with patch.object(bridge_module.c, "WinDLL", return_value=user):
            api = bridge_module._WindowApi()
            hwnd = 0x100000123
            self.assertEqual(api.owned_thread(hwnd), 7)
            self.assertTrue(api.valid_styles(hwnd))
            self.assertTrue(api.recalculate(hwnd))
        self.assertEqual(user.SetWindowPos.argtypes[0], w.HWND)
        self.assertEqual(user.GetWindowLongPtrW.restype, c.c_ssize_t)
        user.SetWindowPos.assert_called_once_with(hwnd, None, 0, 0, 0, 0, 0x0037)
        user.SetForegroundWindow.assert_not_called()
        user.SetFocus.assert_not_called()
        user.SetWindowLongPtrW.assert_not_called()

    def test_win32_adapter_rejects_foreign_and_destroyed_handles(self):
        user = MagicMock()
        user.IsWindow.return_value = 1

        def foreign_identity(hwnd, process):
            process._obj.value = os.getpid() + 1
            return 7

        user.GetWindowThreadProcessId.side_effect = foreign_identity
        with patch.object(bridge_module.c, "WinDLL", return_value=user):
            api = bridge_module._WindowApi()
            self.assertEqual(api.owned_thread(123), 0)
            user.IsWindow.return_value = 0
            user.GetWindowThreadProcessId.reset_mock()
            self.assertEqual(api.owned_thread(123), 0)
            user.GetWindowThreadProcessId.assert_not_called()

    def test_win32_adapter_rejects_layered_child_and_activating_frame_styles(self):
        user = MagicMock()
        with patch.object(bridge_module.c, "WinDLL", return_value=user):
            api = bridge_module._WindowApi()
        for style, extended, expected in (
            (0, 0x08000080, True),
            (0x40000000, 0x08000080, False),
            (0x00C00000, 0x08000080, False),
            (0x00080000, 0x08000080, False),
            (0x00010000, 0x08000080, False),
            (0x00020000, 0x08000080, False),
            (0, 0x08080080, False),
            (0, 0x80, False),
            (0, 0x08000000, False),
        ):
            with self.subTest(style=style, extended=extended):
                user.GetWindowLongPtrW.side_effect = lambda hwnd, index: (
                    style if index == -16 else extended
                )
                self.assertIs(api.valid_styles(123), expected)

    def test_win32_geometry_query_requires_successful_nonempty_rectangles(self):
        user = MagicMock()
        with patch.object(bridge_module.c, "WinDLL", return_value=user):
            api = bridge_module._WindowApi()
        for outer, client, success, expected in (
            ((168, 168), (168, 168), 1, ((168, 168), (168, 168))),
            ((180, 200), (168, 168), 1, ((180, 200), (168, 168))),
            ((0, 0), (0, 0), 1, None),
            ((168, 168), (-1, 168), 1, None),
            ((168, 168), (168, 168), 0, None),
        ):
            with self.subTest(outer=outer, client=client, success=success):

                def read_outer(hwnd, output):
                    output._obj.right, output._obj.bottom = outer
                    return success

                def read_client(hwnd, output):
                    output._obj.right, output._obj.bottom = client
                    return success

                user.GetWindowRect.side_effect = read_outer
                user.GetClientRect.side_effect = read_client
                self.assertEqual(api.frame_geometry(123), expected)


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self):
        for callback in list(self.callbacks):
            callback()


class _Window:
    def __init__(self, hwnd=123, native=True, visible=False):
        self.hwnd = hwnd
        self.window_flags = bridge_module.widget_flags(native)
        self.visible = visible
        self.destroyed = _Signal()

    def winId(self):
        return self.hwnd

    def flags(self):
        return self.window_flags

    def isVisible(self):
        return self.visible


class NativeFrameBridgeTests(unittest.TestCase):
    def setUp(self):
        self.app = Mock()
        self.app.platformName.return_value = "windows"
        self.enter, self.exit = Mock(), Mock()
        self.bridge = bridge_module.NativeFrameBridge(self.app, self.enter, self.exit)
        self.api = Mock(spec=bridge_module._WindowApi)
        self.api.owned_thread.return_value = 7
        self.api.valid_styles.return_value = True
        self.api.recalculate.return_value = True
        self.api.frame_geometry.return_value = ((168, 168), (168, 168))
        self.bridge._api = self.api
        self.policy = patch.object(bridge_module, "native_frame_supported", return_value=True)
        self.policy.start()
        self.addCleanup(self.policy.stop)
        self.addCleanup(self.bridge.close)
        self.window = _Window()

    def test_hidden_native_registration_is_idempotent_and_never_claims_rendered_glass(self):
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        self.window.visible = True
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        self.assertTrue(self.bridge.watch_moves(self.window, "cpu"))
        self.api.recalculate.assert_called_once_with(123)
        self.assertEqual(len(self.window.destroyed.callbacks), 1)
        self.assertTrue(self.bridge.reports["cpu"]["native_frame"])
        self.assertFalse(self.bridge.reports["cpu"]["compositing_verified"])
        self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_NCCALCSIZE), (True, 0))
        self.assertEqual(self.bridge._dispatch(999, bridge_module.WM_NCCALCSIZE), (False, 0))

    def test_move_notifications_are_exact_and_do_not_swallow_the_native_events(self):
        self.bridge.register(self.window, "cpu")
        for message in (
            bridge_module.WM_ENTERSIZEMOVE,
            bridge_module.WM_ENTERSIZEMOVE,
            bridge_module.WM_EXITSIZEMOVE,
            bridge_module.WM_EXITSIZEMOVE,
        ):
            self.assertEqual(self.bridge._dispatch(123, message), (False, 0))
        self.enter.assert_called_once_with("cpu")
        self.exit.assert_called_once_with("cpu")
        self.bridge._dispatch(999, bridge_module.WM_ENTERSIZEMOVE)
        self.enter.assert_called_once()

    def test_legacy_move_watch_allows_layered_visible_windows_without_reframing(self):
        legacy = _Window(native=False, visible=True)
        bridge_module.native_frame_supported.return_value = False
        self.api.valid_styles.return_value = False
        self.assertTrue(self.bridge.watch_moves(legacy, "cpu"))
        self.assertTrue(self.bridge.watch_moves(legacy, "cpu"))
        self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_NCCALCSIZE), (False, 0))
        self.bridge._dispatch(123, bridge_module.WM_ENTERSIZEMOVE)
        self.bridge._dispatch(123, bridge_module.WM_EXITSIZEMOVE)
        self.enter.assert_called_once_with("cpu")
        self.exit.assert_called_once_with("cpu")
        self.assertTrue(self.bridge.unregister(legacy))
        self.api.recalculate.assert_not_called()
        self.api.valid_styles.assert_not_called()
        bridge_module.native_frame_supported.assert_not_called()

    def test_move_watch_can_be_promoted_without_duplicate_destroy_connections(self):
        self.assertTrue(self.bridge.watch_moves(self.window, "cpu"))
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        self.assertEqual(len(self.window.destroyed.callbacks), 1)
        self.api.recalculate.assert_called_once_with(123)
        self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_NCCALCSIZE), (True, 0))

    def test_failed_frame_setup_removes_filter_entry_and_restores_frame(self):
        self.api.recalculate.side_effect = [False, True]
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge._windows, {})
        self.assertEqual(self.window.destroyed.callbacks, [])
        self.assertEqual(self.api.recalculate.call_args_list, [call(123), call(123)])
        self.assertEqual(self.bridge.last_error, "frame-recalculation-failed")
        self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_NCCALCSIZE), (False, 0))

    def test_backend_setup_exception_is_a_clean_fallback(self):
        self.api.recalculate.side_effect = [OSError("frame unavailable"), True]
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge._windows, {})
        self.assertEqual(self.window.destroyed.callbacks, [])
        self.assertEqual(self.bridge.last_error, "frame unavailable")

    def test_foreign_layered_child_or_activating_windows_cannot_register_a_frame(self):
        for owned, styles in ((0, True), (7, False)):
            with self.subTest(owned=owned, styles=styles):
                self.api.owned_thread.return_value = owned
                self.api.valid_styles.return_value = styles
                self.assertFalse(self.bridge.register(self.window, "cpu"))
                self.assertEqual(self.bridge._windows, {})
        self.api.recalculate.assert_not_called()

    def test_visible_native_windows_and_legacy_flags_are_not_reframed(self):
        self.assertFalse(self.bridge.register(_Window(visible=True), "cpu"))
        self.assertFalse(self.bridge.register(_Window(native=False), "gpu"))
        self.assertFalse(self.bridge.register(self.window, "settings"))
        self.api.recalculate.assert_not_called()

    def test_frame_dimensions_must_be_nonempty_and_equal_after_successful_api_call(self):
        for geometry in (None, ((0, 0), (0, 0)), ((-1, 10), (-1, 10)), ((180, 200), (168, 168))):
            with self.subTest(geometry=geometry):
                self.api.frame_geometry.return_value = geometry
                self.assertFalse(self.bridge.register(self.window, "cpu"))
                self.assertEqual(self.bridge._windows, {})
                self.assertEqual(self.window.destroyed.callbacks, [])
                self.assertIn(
                    self.bridge.last_error, ("frame-client-mismatch", "frame-geometry-unavailable")
                )
                self.assertFalse(self.bridge.reports["cpu"]["native_frame"])
        self.assertEqual(self.api.recalculate.call_count, 8)

    def test_idempotent_registration_rechecks_frame_dimensions(self):
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        self.api.frame_geometry.return_value = ((180, 200), (168, 168))
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge.last_error, "frame-client-mismatch")
        self.api.frame_geometry.return_value = ((168, 168), (168, 168))
        self.assertTrue(self.bridge.register(self.window, "cpu"))

    def test_failed_frame_query_restores_without_losing_failure_reason(self):
        self.api.frame_geometry.side_effect = OSError("geometry query failed")
        self.api.recalculate.side_effect = [True, False]
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge.last_error, "geometry query failed")
        self.assertEqual(self.bridge.reports["cpu"]["restore_error"], "frame-restore-failed")
        self.assertEqual(self.bridge._windows, {})

    def test_legacy_move_watch_preserves_frame_failure_but_a_new_frame_success_clears_it(self):
        self.api.frame_geometry.return_value = ((180, 200), (168, 168))
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.window.window_flags = bridge_module.widget_flags(False)
        self.assertTrue(self.bridge.watch_moves(self.window, "cpu"))
        self.assertEqual(self.bridge.reports["cpu"]["status"], "move-watched")
        self.assertEqual(
            self.bridge.reports["cpu"]["frame_fallback_reason"], "frame-client-mismatch"
        )
        self.bridge.unregister(self.window)
        self.window.window_flags = bridge_module.widget_flags(True)
        self.api.frame_geometry.return_value = ((168, 168), (168, 168))
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        self.assertNotIn("frame_fallback_reason", self.bridge.reports["cpu"])

    def test_move_watch_failure_is_not_mislabeled_as_a_frame_fallback(self):
        self.api.owned_thread.return_value = 0
        self.assertFalse(self.bridge.watch_moves(self.window, "cpu"))
        self.api.owned_thread.return_value = 7
        self.assertTrue(self.bridge.watch_moves(self.window, "cpu"))
        self.assertNotIn("frame_fallback_reason", self.bridge.reports["cpu"])

    def test_policy_loss_releases_the_registered_frame(self):
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        bridge_module.native_frame_supported.return_value = False
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge._windows, {})
        self.assertEqual(self.window.destroyed.callbacks, [])
        self.assertFalse(self.bridge.reports["cpu"]["native_frame"])

    def test_destroy_messages_and_qobject_destruction_remove_only_their_own_entry(self):
        self.bridge.register(self.window, "cpu")
        other = _Window(456)
        self.bridge.register(other, "gpu")
        self.api.reset_mock()
        self.bridge._dispatch(123, bridge_module.WM_NCDESTROY)
        self.assertNotIn(123, self.bridge._windows)
        self.assertIn(456, self.bridge._windows)
        other.destroyed.emit()
        self.assertEqual(self.bridge._windows, {})
        self.api.recalculate.assert_not_called()
        self.api.owned_thread.assert_not_called()

    def test_destroy_during_frame_setup_cannot_return_a_successful_registration(self):
        def destroy(hwnd):
            self.window.destroyed.emit()
            return True

        self.api.recalculate.side_effect = destroy
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.assertEqual(self.bridge._windows, {})
        self.assertEqual(self.bridge.last_error, "window-destroyed-during-registration")

    def test_reused_or_foreign_handle_is_not_intercepted_after_identity_loss(self):
        self.bridge.register(self.window, "cpu")
        self.api.owned_thread.return_value = 0
        self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_NCCALCSIZE), (False, 0))
        self.assertEqual(self.bridge._windows, {})
        self.assertEqual(self.bridge.last_error, "window-identity-lost")
        self.api.recalculate.assert_called_once()

    def test_close_and_unregister_are_idempotent_and_restore_only_owned_frames(self):
        self.bridge.register(self.window, "cpu")
        self.assertTrue(self.bridge.unregister(self.window))
        self.assertFalse(self.bridge.unregister(self.window))
        self.assertEqual(self.window.destroyed.callbacks, [])
        self.bridge.close()
        self.bridge.close()
        self.app.installNativeEventFilter.assert_called_once_with(self.bridge)
        self.app.removeNativeEventFilter.assert_called_once_with(self.bridge)
        self.assertFalse(self.bridge.register(self.window, "cpu"))
        self.api.recalculate.assert_has_calls([call(123), call(123)])

    def test_native_message_abi_keeps_full_width_handles_and_ignores_other_qt_surfaces(self):
        self.window.hwnd = 0x100000123
        self.bridge.register(self.window, "cpu")
        message = w.MSG()
        message.hWnd = self.window.hwnd
        message.message = bridge_module.WM_NCCALCSIZE
        self.assertEqual(
            self.bridge.nativeEventFilter(b"windows_generic_MSG", c.addressof(message)), (True, 0)
        )
        self.assertEqual(
            self.bridge.nativeEventFilter(b"windows_dispatcher_MSG", c.addressof(message)),
            (False, 0),
        )
        self.assertEqual(self.bridge.nativeEventFilter(b"windows_generic_MSG", 0), (False, 0))

    def test_native_filter_accepts_valid_zero_sized_shiboken_message_pointers(self):
        self.assertTrue(self.bridge.register(self.window, "cpu"))
        message = w.MSG()
        message.hWnd = self.window.hwnd
        message.message = bridge_module.WM_NCCALCSIZE
        event_type = QByteArray(b"windows_generic_MSG")
        for size in (0, -1):
            pointer = VoidPtr(c.addressof(message), size)
            self.assertNotEqual(int(pointer), 0)
            if size == 0:
                self.assertFalse(bool(pointer))  # A valid address must still be dispatched.
            self.assertEqual(self.bridge.nativeEventFilter(event_type, pointer), (True, 0))
        self.assertEqual(self.bridge.nativeEventFilter(event_type, VoidPtr(0, 0)), (False, 0))
        self.assertEqual(self.bridge.nativeEventFilter(event_type, None), (False, 0))
        pointer = VoidPtr(c.addressof(message), 0)
        for message_code in (
            bridge_module.WM_ENTERSIZEMOVE,
            bridge_module.WM_ENTERSIZEMOVE,
            bridge_module.WM_EXITSIZEMOVE,
            bridge_module.WM_EXITSIZEMOVE,
        ):
            message.message = message_code
            self.assertEqual(self.bridge.nativeEventFilter(event_type, pointer), (False, 0))
        self.enter.assert_called_once_with("cpu")
        self.exit.assert_called_once_with("cpu")

    def test_callback_failure_does_not_escape_qt_native_dispatch(self):
        self.bridge.register(self.window, "cpu")
        self.enter.side_effect = ValueError("callback bug")
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.bridge._dispatch(123, bridge_module.WM_ENTERSIZEMOVE), (False, 0))
        self.bridge._dispatch(123, bridge_module.WM_EXITSIZEMOVE)
        self.exit.assert_called_once_with("cpu")

    def test_offscreen_mode_does_not_install_filter_or_load_system_apis(self):
        app = Mock()
        app.platformName.return_value = "offscreen"
        with patch.object(bridge_module.c, "WinDLL") as loader:
            bridge = bridge_module.NativeFrameBridge(app)
            self.assertFalse(bridge.register(self.window, "cpu"))
            self.assertFalse(bridge.watch_moves(self.window, "cpu"))
            bridge.close()
        app.installNativeEventFilter.assert_not_called()
        app.removeNativeEventFilter.assert_not_called()
        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
