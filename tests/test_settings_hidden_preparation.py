"""Hidden Raster-owner preparation with actual offscreen Qt and fake DWM.

No production Runtime initialization, native API, IPC, collector or user IO.
"""

import copy
import os
import threading
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QExposeEvent, QRegion, QSurface, QSurfaceFormat
from PySide6.QtWidgets import QApplication

from native_runtime import Runtime
from settings_acrylic_material import SettingsAcrylicMaterial
from settings_backdrop_host import SettingsBackdropHost
from settings_material_bridge import SettingsMaterialBridge

if __package__:
    from .test_settings_acrylic_material import FakeAPI
    from .test_settings_material_frame_source import Clock, ControlledQuick, ControlledRaster
    from .test_settings_material_integration import FakeController
else:
    from test_settings_acrylic_material import FakeAPI
    from test_settings_material_frame_source import Clock, ControlledQuick, ControlledRaster
    from test_settings_material_integration import FakeController


GOOD = dict(material="desktop-acrylic", status="configured-unverified", ok=True,
            backdrop_type=3, backdrop_result=0, frame_result=0, readback_result=0,
            coating_allowed=True, coating_translucent=True, blur_configured=True,
            compositing_verified=False)
FAILED = dict(material="solid", status="fallback", ok=False, coating_allowed=False,
              coating_translucent=False, blur_configured=False, fallback_reason="fake-api-failed")


class HiddenPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen", "Never run a visible native test"

    def setUp(self):
        self.addCleanup(patch.stopall)
        self.dll = patch("ctypes.WinDLL", side_effect=AssertionError("No native API")).start()
        self.spawn = patch("subprocess.Popen", side_effect=AssertionError("No child process")).start()
        self.clock = Clock()
        self.host = ControlledRaster()
        self.host.setSurfaceType(QSurface.RasterSurface)
        format_ = QSurfaceFormat()
        format_.setAlphaBufferSize(0)
        self.host.setFormat(format_)
        self.frame = ControlledQuick()
        self.frame.setParent(self.host)
        self.host.resize(400, 280)
        self.frame.resize(400, 280)
        self.policy = Mock(return_value=dict(state="allowed", reason="allowed"))
        self.compose = Mock(return_value=copy.deepcopy(GOOD))
        self.publish = Mock()
        self.release = Mock(return_value=dict(ok=True, cleanup_complete=True))
        self.bridge = self.make_bridge()
        self.bridge.start()

    def make_bridge(self, **options):
        return SettingsMaterialBridge(self.host, frame_source=self.frame, backend="desktop-acrylic",
            compose_once=self.compose, policy_reader=self.policy, publish=self.publish,
            release_surface=self.release, clock=self.clock, allow_hidden_prepare=True, **options)

    def tearDown(self):
        self.bridge.close()
        for window in (self.frame, self.host):
            try:
                window.destroy()
                window.deleteLater()
            except RuntimeError:
                pass
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.dll.assert_not_called()
        self.spawn.assert_not_called()

    def pump(self):
        for _ in range(4):
            self.app.processEvents()

    def create(self):
        self.host.create()  # Offscreen platform only, no Windows HWND/API.
        self.assertTrue(self.bridge.status()["surface_alive"])

    def ready(self):
        self.host.show()
        self.frame.show()
        self.pump()
        for window in (self.host, self.frame):
            window.exposed = True
            QCoreApplication.sendEvent(window, QExposeEvent(QRegion()))
        self.frame.initialized = True
        self.frame.sceneGraphInitialized.emit()
        self.frame.frameSwapped.emit()
        self.pump()
        self.assertTrue(self.bridge.status()["render_ready"])

    def due(self, seconds=.16):
        self.clock.now += seconds
        self.bridge._on_timeout()

    def test_opt_in_is_strict_and_plain_bridges_remain_hidden(self):
        self.bridge.close()
        options = dict(compose_once=self.compose, policy_reader=self.policy, publish=self.publish)
        for extra in (dict(allow_hidden_prepare="yes"), dict(allow_hidden_prepare=True),
                      dict(allow_hidden_prepare=True, frame_source=self.frame, backend="unsupported")):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                SettingsMaterialBridge(self.host, **options, **extra)
        self.bridge = SettingsMaterialBridge(self.host, **options)
        self.bridge.start()
        self.create()
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertIsNone(self.bridge.compose_now())
        self.compose.assert_not_called()

    def test_never_creates_or_queries_a_missing_owner_or_child_handle(self):
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertEqual(self.host.winid_calls, 0)
        self.assertEqual(self.frame.winid_calls, 0)
        self.compose.assert_not_called()
        self.assertFalse(self.bridge.status()["preparing_hidden"])

    def test_hidden_prepare_publishes_before_show_without_opening_render_gate(self):
        self.create()
        calls = self.host.winid_calls
        result = self.bridge.prepare_hidden()
        self.assertEqual(result["preparation"], "before-show")
        self.assertTrue(result["coating_translucent"])
        self.assertFalse(result["compositing_verified"])
        self.assertFalse(self.host.isVisible())
        self.assertFalse(self.frame.isVisible())
        self.assertFalse(self.bridge.status()["render_ready"])
        self.assertIsNone(self.bridge.compose_now())
        self.assertEqual(self.host.winid_calls, calls)
        self.assertEqual(self.frame.winid_calls, 0)
        self.publish.assert_called_once()
        self.assertTrue(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.bridge.status()["preparing_hidden"])

    def test_expected_first_child_surface_and_first_frame_adopt_success(self):
        self.create()
        self.bridge.prepare_hidden()
        self.ready()
        self.due()
        self.assertEqual(self.compose.call_count, 1)
        self.assertEqual(self.bridge.status()["hidden_adoptions"], 1)
        self.assertEqual(self.publish.call_args.args[0]["preparation"], "adopted-before-show")
        self.due(.26)
        self.assertEqual(self.compose.call_count, 1)
        self.assertEqual(self.bridge.status()["hidden_adoptions"], 2)

    def use_blur_bridge(self):
        self.bridge.close()
        self.bridge = SettingsMaterialBridge(self.host, frame_source=self.frame, backend="system-blur",
            compose_once=self.compose, policy_reader=self.policy, publish=self.publish,
            release_surface=self.release, clock=self.clock, allow_hidden_prepare=True)
        self.bridge.start()

    def test_system_blur_is_prepared_before_show_and_never_delayed_into_glass(self):
        self.use_blur_bridge()
        self.compose.return_value = dict(GOOD, material="system-blur", bool_result=1)
        self.create()
        self.assertTrue(self.bridge.prepare_hidden()["coating_translucent"])
        self.assertTrue(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.host.isVisible())
        self.assertFalse(self.frame.isVisible())
        self.ready()
        self.due()
        self.due(.5)
        self.assertEqual(self.compose.call_count, 1)
        self.assertEqual(self.publish.call_args.args[0]["preparation"], "adopted-before-show")
        self.assertNotEqual(self.bridge.status()["state"], "settle_wait")

    def test_system_blur_does_not_cache_invalid_native_results(self):
        self.use_blur_bridge()
        self.create()
        for value in (0, True, "1", None, 1 << 31):
            with self.subTest(result=value):
                self.compose.return_value = dict(GOOD, material="system-blur", bool_result=value)
                self.bridge.prepare_hidden()
                self.assertFalse(self.bridge.status()["hidden_prepared"])

    def prepare_failed_blur_opening(self):
        self.use_blur_bridge()
        self.create()
        self.compose.return_value = copy.deepcopy(FAILED)
        self.assertFalse(self.bridge.prepare_hidden()["coating_translucent"])
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.assertTrue(self.bridge.status()["hidden_fallback_prepared"])
        self.compose.return_value = dict(GOOD, material="system-blur", bool_result=1)
        self.ready()

    def test_first_failure_remains_fallback_for_first_frames_and_automatic_retries(self):
        self.prepare_failed_blur_opening()
        for seconds in (.16, .26, 1.01):
            self.due(seconds)
        self.assertEqual(self.compose.call_count, 1)
        self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])
        self.assertEqual(self.publish.call_args.args[0]["preparation"], "adopted-before-show-fallback")
        for reason in ("shown", "graphics_ready", "first_frame", "exposed", "activated", "deactivated"):
            self.bridge.request(reason)
            self.due()
            self.assertEqual(self.compose.call_count, 1)
            self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])
        self.assertFalse(self.bridge.compose_now()["coating_translucent"])
        self.assertEqual(self.compose.call_count, 1)

    def test_desktop_acrylic_failure_is_stable_until_real_recovery(self):
        self.create()
        self.compose.return_value = copy.deepcopy(FAILED)
        self.assertFalse(self.bridge.prepare_hidden()["coating_translucent"])
        self.compose.return_value = copy.deepcopy(GOOD)
        self.ready()
        for seconds in (.16, .26, 1.01):
            self.due(seconds)
        self.assertEqual(self.compose.call_count, 1)
        self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])
        self.bridge.request("preference_changed")
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertTrue(self.publish.call_args.args[0]["coating_translucent"])

    def test_failed_opening_real_recovery_reaches_native_and_keeps_retry_budget(self):
        self.prepare_failed_blur_opening()
        self.due()
        self.compose.return_value = copy.deepcopy(FAILED)
        self.bridge.request("composition_changed")
        self.assertFalse(self.bridge.status()["hidden_fallback_prepared"])
        self.due(.26)
        self.assertEqual(self.compose.call_count, 2)
        self.compose.return_value = dict(GOOD, material="system-blur", bool_result=1)
        self.due(.26)
        self.assertEqual(self.compose.call_count, 2)  # Existing finite backoff is not shortened.
        self.due(.76)
        self.assertEqual(self.compose.call_count, 3)
        self.assertTrue(self.publish.call_args.args[0]["coating_translucent"])

    def test_failed_opening_policy_change_can_recover_without_reopening(self):
        self.prepare_failed_blur_opening()
        self.due()
        self.policy.return_value = dict(state="allowed", reason="policy-refreshed")
        self.bridge.refresh_policy()
        self.assertFalse(self.bridge.status()["hidden_fallback_prepared"])
        self.due(.26)
        self.assertEqual(self.compose.call_count, 2)
        self.assertTrue(self.publish.call_args.args[0]["coating_translucent"])

    def test_failed_opening_hide_and_reopen_prepares_a_new_result(self):
        self.prepare_failed_blur_opening()
        self.due()
        self.frame.hide()
        self.host.hide()
        self.pump()
        self.assertFalse(self.bridge.status()["hidden_fallback_prepared"])
        result = self.bridge.prepare_hidden()
        self.assertTrue(result["coating_translucent"])
        self.assertEqual(self.compose.call_count, 2)
        self.ready()
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertTrue(self.publish.call_args.args[0]["coating_translucent"])

    def test_failed_opening_close_cleans_original_surface_and_rejects_late_events(self):
        self.prepare_failed_blur_opening()
        handle = self.bridge.status()["surface_handle"]
        self.bridge.close()
        self.bridge.close()
        self.due()
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertIsNone(self.bridge.compose_now())
        self.assertFalse(self.bridge.request("composition_changed"))
        self.assertFalse(self.bridge.status()["hidden_fallback_prepared"])
        self.assertEqual(self.compose.call_count, 1)
        self.release.assert_called_once_with(handle)

    def test_failed_hidden_surface_replacement_does_not_reuse_prior_fallback(self):
        self.use_blur_bridge()
        self.create()
        self.compose.return_value = copy.deepcopy(FAILED)
        self.bridge.prepare_hidden()
        serial = self.bridge.status()["surface_serial"]
        self.host.destroy()
        self.host.create()
        self.assertGreater(self.bridge.status()["surface_serial"], serial)
        self.assertFalse(self.bridge.status()["hidden_fallback_prepared"])
        self.compose.return_value = dict(GOOD, material="system-blur", bool_result=1)
        self.assertTrue(self.bridge.prepare_hidden()["coating_translucent"])
        self.ready()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_hidden_callback_exception_is_a_stable_opening_fallback(self):
        self.use_blur_bridge()
        self.create()
        self.compose.side_effect = RuntimeError("fake native failure")
        result = self.bridge.prepare_hidden()
        self.assertFalse(result["coating_translucent"])
        self.assertTrue(self.bridge.status()["hidden_fallback_prepared"])
        self.compose.side_effect = None
        self.compose.return_value = dict(GOOD, material="system-blur", bool_result=1)
        self.ready()
        self.due()
        self.assertEqual(self.compose.call_count, 1)
        self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])

    def test_disabled_failed_cleanup_can_retry_without_enabling_coating(self):
        self.use_blur_bridge()
        self.create()
        self.policy.return_value = dict(state="disabled", reason="transparency-disabled")
        self.compose.return_value = dict(FAILED, status="cleanup-failed",
                                         cleanup_complete=False, blur_may_remain=True)
        self.bridge.prepare_hidden()
        self.compose.return_value = dict(FAILED, status="no-blur", ok=True,
                                         cleanup_complete=True, blur_may_remain=False)
        self.ready()
        self.due()
        self.assertEqual(self.compose.call_count, 2)
        self.assertEqual(self.compose.call_args.args[1]["state"], "disabled")
        self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])
        self.assertTrue(self.publish.call_args.args[0]["cleanup_complete"])

    def test_real_recovery_failure_keeps_finite_retry_unfrozen(self):
        self.create()
        self.bridge.prepare_hidden()
        self.ready()
        self.due()
        self.due(.26)  # Complete the original successful finite settlement.
        self.compose.return_value = copy.deepcopy(FAILED)
        self.bridge.request("composition_changed")
        self.due(.26)
        self.assertEqual(self.compose.call_count, 2)
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.compose.return_value = copy.deepcopy(GOOD)
        self.due(.26)
        self.assertEqual(self.compose.call_count, 3)
        self.assertTrue(self.publish.call_args.args[0]["coating_translucent"])

    def test_each_real_preference_event_invalidates_the_prepared_snapshot(self):
        self.create()
        for reason in ("theme_changed", "composition_changed", "power_changed", "display_changed",
                       "system_preferences", "preference_changed"):
            with self.subTest(reason=reason):
                self.assertIsNotNone(self.bridge.prepare_hidden())
                self.bridge.request(reason)
                self.assertFalse(self.bridge.status()["hidden_prepared"])

    def test_policy_disable_and_unknown_never_replay_prepared_glass(self):
        self.create()
        self.bridge.prepare_hidden()
        self.ready()
        self.due()
        for state in ("disabled", "unknown"):
            with self.subTest(state=state):
                self.policy.return_value = dict(state=state)
                self.compose.return_value = copy.deepcopy(FAILED)
                self.bridge.refresh_policy()
                self.due()
                self.assertFalse(self.bridge.status()["hidden_prepared"])
                self.assertEqual(self.compose.call_args.args[1]["state"], state)
                self.assertFalse(self.publish.call_args.args[0]["coating_translucent"])

    def test_real_scene_graph_invalidation_cannot_adopt_old_success(self):
        self.create()
        self.bridge.prepare_hidden()
        self.ready()
        self.frame.sceneGraphInvalidated.emit()
        self.pump()
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.bridge.status()["render_ready"])
        self.frame.frameSwapped.emit()
        self.pump()
        self.due()
        self.assertEqual(self.compose.call_count, 2)

    def test_never_showing_after_prepare_still_releases_original_surface_once(self):
        self.create()
        self.bridge.prepare_hidden()
        handle = self.bridge.status()["surface_handle"]
        self.bridge.close()
        self.bridge.close()
        self.release.assert_called_once_with(handle)
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.bridge.status()["preparing_hidden"])

    def test_queued_render_notice_after_closed_owner_deletion_is_inert(self):
        self.create()
        self.bridge.prepare_hidden()
        self.bridge._render_notice.emit(self.bridge._render_epoch, "first_frame")
        self.bridge.close()
        calls = self.compose.call_count
        self.host.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        with patch("sys.excepthook") as exceptions:
            self.pump()
            self.bridge._render_event(self.bridge._render_epoch, "first_frame")
            self.bridge.close()
            self.assertFalse(self.bridge.request("theme_changed"))
            exceptions.assert_not_called()
        self.assertEqual(self.compose.call_count, calls)
        self.release.assert_called_once()

    def test_reentrant_close_releases_after_busy_native_callback_unwinds(self):
        self.create()
        order = []

        def compose(*_):
            order.append("compose")
            self.bridge.close()
            self.release.assert_not_called()
            order.append("native-unwound")
            return copy.deepcopy(GOOD)

        self.compose.side_effect = compose
        self.release.side_effect = lambda _: order.append("release") or dict(ok=True)
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertEqual(order, ["compose", "native-unwound", "release"])
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["hidden_release_pending"])
        self.assertFalse(self.bridge.status()["preparing_hidden"])

    def test_native_reentry_cannot_publish_stale_owner_or_preference(self):
        self.create()
        self.compose.side_effect = lambda *_: self.bridge.request("theme_changed") or copy.deepcopy(GOOD)
        self.assertIsNone(self.bridge.prepare_hidden())
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["preparing_hidden"])
        self.assertFalse(self.bridge.status()["hidden_prepared"])

    def test_owner_surface_replacement_inside_native_callback_rejects_old_report(self):
        self.create()
        old_serial = self.bridge.status()["surface_serial"]

        def replace(*_):
            self.host.destroy()
            self.host.create()
            return copy.deepcopy(GOOD)

        self.compose.side_effect = replace
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertGreater(self.bridge.status()["surface_serial"], old_serial)
        self.publish.assert_not_called()
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.bridge.status()["preparing_hidden"])

    def test_destroyed_renderer_blocks_prepare_but_not_owner_release(self):
        self.create()
        self.bridge.prepare_hidden()
        self.bridge._frame_source_destroyed()
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.bridge.close()
        self.release.assert_called_once()

    def test_publish_reentry_close_and_failure_do_not_leave_preparing_capability(self):
        self.create()
        self.publish.side_effect = RuntimeError("fake publish")
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(self.bridge.prepare_hidden())
        self.assertFalse(self.bridge.status()["hidden_prepared"])
        self.assertFalse(self.bridge.status()["preparing_hidden"])
        self.publish.side_effect = lambda _: self.bridge.close()
        self.assertIsNone(self.bridge.prepare_hidden())
        self.release.assert_called_once()

    def test_visible_detached_and_minimized_windows_cannot_prepare(self):
        self.create()
        self.frame.setParent(None)
        self.assertIsNone(self.bridge.prepare_hidden())
        self.frame.setParent(self.host)
        self.host.setWindowState(Qt.WindowMinimized)
        self.assertIsNone(self.bridge.prepare_hidden())
        self.host.setWindowState(Qt.WindowNoState)
        self.host.show()
        self.assertIsNone(self.bridge.prepare_hidden())
        self.compose.assert_not_called()

    def test_worker_thread_cannot_prepare_or_use_hidden_native_capability(self):
        errors = []

        def worker():
            for action in (self.bridge.prepare_hidden,
                           lambda: self.bridge.hidden_preparation_current(1, 1, 1)):
                try:
                    action()
                except RuntimeError as error:
                    errors.append(str(error))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(2)
        self.assertEqual(len(errors), 2)
        self.compose.assert_not_called()


class RuntimeHiddenPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"

    def setUp(self):
        self.addCleanup(patch.stopall)
        self.dll = patch("ctypes.WinDLL", side_effect=AssertionError("No native API")).start()
        self.spawn = patch("subprocess.Popen", side_effect=AssertionError("No child process")).start()
        self.runtime = Runtime.__new__(Runtime)
        QObject.__init__(self.runtime)
        self.runtime.settings = ControlledQuick()
        self.painter = Mock()
        self.runtime.settings_host = SettingsBackdropHost(self.runtime.settings, native=False, painter=self.painter)
        self.runtime.shutting_down = False
        self.runtime.headless = True
        self.runtime.composition = {}
        self.runtime.controller = FakeController()
        self.runtime.controller.inspect = Mock()
        self.runtime.app = self.app
        self.runtime.compose = Mock()
        self.api = FakeAPI()
        self.runtime.settings_blur = SettingsAcrylicMaterial(self.api)
        self.policy = Mock(return_value=dict(state="allowed", reason="allowed"))
        self.bridge = SettingsMaterialBridge(self.runtime.settings_host, self.runtime,
            frame_source=self.runtime.settings, backend="desktop-acrylic", allow_hidden_prepare=True,
            compose_once=self.runtime._settings_material_request, policy_reader=self.policy,
            publish=self.runtime._publish_settings_material,
            release_surface=self.runtime._release_settings_surface)
        self.runtime.settings_material = self.bridge
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()
        self.runtime.settings_blur.close()
        self.runtime.settings_host.dispose()
        self.runtime.settings.deleteLater()
        self.runtime.settings_host.deleteLater()
        self.runtime.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.dll.assert_not_called()
        self.spawn.assert_not_called()

    def create(self):
        self.runtime.settings_host.create()
        self.assertTrue(self.bridge.status()["surface_alive"])

    def test_real_runtime_hidden_guard_apply_paint_and_cleanup_without_show(self):
        self.create()
        result = self.bridge.prepare_hidden()
        self.assertTrue(result["coating_translucent"])
        self.assertFalse(result["compositing_verified"])
        self.assertEqual([event[0] for event in self.api.events], ["set", "extend", "get"])
        self.assertGreater(self.painter.fill.call_count, 0)
        self.assertTrue(self.runtime.controller._material["coating_translucent"])
        self.assertFalse(self.runtime.settings_host.isVisible())
        self.bridge.close()
        self.assertEqual(self.api.events[-3:][0][2], 1)
        self.assertIsNone(self.runtime.settings_blur.identity)
        self.assertTrue(self.runtime.settings_blur.close()["complete"])

    def test_hidden_validity_capability_is_not_reusable_after_prepare(self):
        self.create()
        captured = []
        original = self.runtime.settings_blur.apply

        def apply(*args, **kwargs):
            captured.append(kwargs["valid"])
            self.assertTrue(kwargs["valid"]())
            return original(*args, **kwargs)

        self.runtime.settings_blur.apply = apply
        self.bridge.prepare_hidden()
        self.assertFalse(captured[0]())
        self.assertFalse(self.runtime._settings_surface_current(
            self.bridge.status()["surface_handle"], self.bridge.status()["surface_serial"]))

    def test_actual_runtime_show_orders_material_and_paint_before_show(self):
        observed = []
        host = self.runtime.settings_host
        original = host.showNormal

        def show():
            observed.append((self.runtime.controller._material.get("coating_translucent"),
                             self.painter.fill.call_count, host.status()["surface_alive"]))
            return original()

        with patch.object(host, "showNormal", side_effect=show), patch.object(host, "raise_"), \
                patch.object(host, "requestActivate"):
            self.runtime.show_settings()
        self.assertEqual(observed, [(True, 1, True)])
        self.assertTrue(host.isVisible())
        self.runtime.compose.assert_called_once()

    def test_paint_failure_clears_native_before_publishing_solid(self):
        self.create()
        self.painter.fill.side_effect = RuntimeError("fake paint failure")
        result = self.bridge.prepare_hidden()
        self.assertFalse(result["coating_translucent"])
        self.assertEqual(result["fallback_reason"], "native-background-paint-failed")
        self.assertIsNone(self.runtime.settings_blur.identity)
        self.assertFalse(self.bridge.status()["hidden_prepared"])

    def test_real_adapter_reentrant_close_after_native_mutation_cleans_same_owner(self):
        self.create()
        once = []

        def close(entry):
            if entry[0] == "set" and entry[2] == 3 and not once:
                once.append(True)
                self.bridge.close()

        self.api.after = close
        self.assertIsNone(self.bridge.prepare_hidden())
        self.assertTrue(self.bridge.status()["closed"])
        self.assertFalse(self.bridge.status()["hidden_release_pending"])
        self.assertIsNone(self.runtime.settings_blur.identity)
        self.assertEqual(self.api.actual, 1)
        self.assertTrue(self.runtime.settings_blur.close()["complete"])

    def test_preparation_close_reentry_aborts_runtime_show_and_focus_actions(self):
        original = self.bridge._publish

        def publish(report):
            original(report)
            self.bridge.close()

        self.bridge._publish = publish
        host = self.runtime.settings_host
        with patch.object(host, "showNormal") as show, patch.object(host, "raise_") as raise_, \
                patch.object(host, "requestActivate") as activate:
            self.runtime.show_settings()
            show.assert_not_called()
            raise_.assert_not_called()
            activate.assert_not_called()
        self.assertIsNone(self.runtime.settings_blur.identity)


if __name__ == "__main__":
    unittest.main()
