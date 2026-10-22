"""Real Runtime callback/Qt bridge integration; all material APIs are fake.

No production Runtime initialization, collectors, files, IPC, or native window.
QQuickWindow and Theme objects exist exclusively on the asserted offscreen QPA.
"""

import copy
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("DESKTOP_STATS_DATA", str(Path(__file__).resolve().parents[1] / "qa-private/redesign15/integration-profile"))

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, QUrl, Signal
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import native_platform
import native_runtime
from native_runtime import Runtime
from settings_material_bridge import SettingsMaterialBridge
from skin_styles import palette

GOOD = dict(material="system-blur", status="configured-unverified", bool_result=1,
            ok=True, coating_allowed=True, coating_translucent=True, blur_configured=True,
            policy={"state": "allowed", "reason": "allowed"}, compositing_verified=False)
FAILED = dict(material="solid", status="fallback", fallback_reason="frame-extension-failed",
              frame_result=-2147467259, compositing_verified=False)


class FakeController(QObject):
    materialChanged = Signal()
    themeChanged = Signal()

    def __init__(self):
        super().__init__()
        self._draft = {"theme": "light"}
        self._saved = {"theme": "light"}
        self._material = {"material": "solid"}
        self.windows = {}
        self.close = Mock()

    material = Property('QVariantMap', lambda self: self._material, notify=materialChanged)
    theme = Property(str, lambda self: self._draft['theme'], notify=themeChanged)
    language = Property(str, lambda self: 'zh-CN', constant=True)
    texts = Property('QVariantMap', lambda self: {}, constant=True)

    def set_material(self, report):
        self._material = report
        self.materialChanged.emit()

    def set_window_materials(self, report):
        self.windows = copy.deepcopy(report)


class Clock:
    now = 100.

    def __call__(self):
        return self.now


class SettingsMaterialIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == 'offscreen', 'No real native windows'

    def setUp(self):
        self.clock = Clock()
        # Construct only QObject identity, then wire the actual production
        # callbacks. Runtime.__init__ is intentionally excluded: it starts IO.
        self.runtime = Runtime.__new__(Runtime)
        QObject.__init__(self.runtime)
        self.runtime.controller = FakeController()
        self.runtime.settings = QQuickWindow()
        self.runtime.settings.resize(420, 280)
        self.runtime.composition = {}
        self.runtime.widgets = {}
        self.runtime.widget_materials = {}
        self.runtime.widget_blur = None
        self.runtime.widget_mask_timer = Mock()
        self.runtime.transparency = True
        self.runtime.shutting_down = False
        self.runtime.frame_bridge = None
        self.runtime.apply = Mock()
        self.policy = Mock(return_value={"state": "allowed", "reason": "allowed"})
        self.runtime.settings_blur = Mock()
        self.runtime.settings_blur.clear.return_value = dict(ok=True, blur_may_remain=False)
        self.runtime.settings_blur.close.return_value = dict(ok=True)
        self.backend = self.runtime.settings_blur.apply
        self.backend.return_value = copy.deepcopy(GOOD)
        self.bridge = SettingsMaterialBridge(self.runtime.settings, self.runtime,
                                             compose_once=self.runtime._settings_material_request,
                                             policy_reader=self.policy,
                                             publish=self.runtime._publish_settings_material,
                                             clock=self.clock, backend='system-blur',
                                             wait_for_first_frame=True, activation_requests=False,
                                             release_surface=self.runtime._release_settings_surface)
        self.runtime.settings_material = self.bridge
        self.bridge.start()

    def tearDown(self):
        self.bridge.close()
        self.runtime.settings.destroy()
        self.runtime.settings.deleteLater()
        self.runtime.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def show(self):
        self.runtime.settings.show()  # Offscreen only; no native Windows window.
        for _ in range(100):
            self.app.processEvents()
            if self.bridge.status()['render_ready']:
                break
            QTest.qWait(5)
        self.assertTrue(self.bridge.status()['first_frame_observed'])
        self.assertTrue(self.bridge.status()['render_ready'])

    def due(self, seconds):
        self.clock.now += seconds
        self.bridge._on_timeout()

    def test_bridge_parent_and_callbacks_remain_on_runtime_gui_thread(self):
        self.assertIs(self.bridge.parent(), self.runtime)
        self.assertEqual(self.bridge.thread(), self.runtime.settings.thread())
        self.show()
        result = self.runtime.compose(self.runtime.settings, 'settings')
        self.assertEqual(result['renderer'], 'Software')
        self.assertEqual(self.runtime.composition['settings'], result)
        self.assertEqual(self.runtime.controller.material, result)
        self.assertEqual(self.runtime.controller.windows['settings'], result)
        self.assertFalse(result['compositing_verified'])

    def test_hidden_compose_does_not_create_handle_or_native_request(self):
        self.assertEqual(self.bridge.status()['handle'], 0)
        self.assertIsNone(self.runtime.compose(self.runtime.settings, 'settings'))
        self.backend.assert_not_called()
        self.assertEqual(self.runtime.composition, {})

    def test_callback_uses_draft_theme_and_exact_policy_without_early_publication(self):
        self.runtime.controller._draft['theme'] = 'dark'
        policy = {'state': 'allowed', 'reason': 'allowed', 'winerror': 0}
        self.show()
        handle = self.bridge.status()['surface_handle']
        report = self.runtime._settings_material_request(handle, policy)
        self.backend.assert_called_once()
        args, kwargs = self.backend.call_args
        self.assertEqual(args, (handle, policy))
        self.assertEqual(kwargs['surface_id'], self.bridge.status()['surface_serial'])
        self.assertTrue(kwargs['valid']())
        self.assertEqual(report['renderer'], 'Software')
        self.assertEqual(self.runtime.composition, {})
        self.assertEqual(self.runtime.controller.material, {'material': 'solid'})

    def test_actual_runtime_callbacks_automatically_recover_same_policy_failure(self):
        self.show()
        self.backend.side_effect = [copy.deepcopy(FAILED), copy.deepcopy(GOOD)]
        self.runtime.compose(self.runtime.settings, 'settings')
        self.assertEqual(self.runtime.controller.material['material'], 'solid')
        self.due(.25)
        self.assertEqual(self.backend.call_count, 2)
        self.assertEqual(self.runtime.controller.material['material'], 'system-blur')
        self.assertEqual(self.bridge.status()['state'], 'configured_unverified')
        self.assertFalse(self.runtime.controller.material['compositing_verified'])

    def test_destroy_in_native_request_rejects_publication_to_current_runtime(self):
        self.show()

        def destroy(_handle, _policy, **_kwargs):
            self.runtime.settings.destroy()
            return copy.deepcopy(GOOD)

        self.backend.side_effect = destroy
        self.assertIsNone(self.runtime.compose(self.runtime.settings, 'settings'))
        self.assertEqual(self.runtime.controller.material['status'], 'waiting-for-surface')
        self.assertFalse(self.runtime.controller.material['coating_allowed'])

    def test_same_policy_runtime_poll_does_not_restart_exhausted_episode(self):
        self.show()
        self.backend.return_value = copy.deepcopy(FAILED)
        self.runtime.compose(self.runtime.settings, 'settings')
        self.due(.25)
        self.due(1)
        with patch.object(native_runtime, 'transparency_enabled', return_value=True):
            for _ in range(20):
                self.runtime.keep_below()
        self.assertEqual(self.backend.call_count, 3)
        self.runtime.apply.assert_not_called()
        self.assertEqual(self.bridge.status()['state'], 'exhausted')

    def test_policy_transition_via_runtime_poll_schedules_one_main_cleanup(self):
        self.show()
        self.runtime.compose(self.runtime.settings, 'settings')
        self.policy.return_value = {'state': 'disabled', 'reason': 'high-contrast'}
        self.backend.return_value = dict(FAILED, fallback_reason='high-contrast', ok=True,
                                         blur_may_remain=False, bool_result=1)
        with patch.object(native_runtime, 'transparency_enabled', return_value=False):
            self.runtime.keep_below()
        self.runtime.apply.assert_called_once_with(False)
        self.due(.15)
        self.assertEqual(self.runtime.controller.material['policy']['state'], 'disabled')
        self.assertEqual(self.bridge.status()['state'], 'policy_disabled')
        self.assertFalse(self.bridge.status()['timer_active'])

    def test_widget_alpha_report_does_not_replace_settings_blur_request_state(self):
        self.show()
        settings_report = self.runtime.compose(self.runtime.settings, 'settings')
        widget = SimpleNamespace(winId=lambda: 888, setProperty=Mock(),
                                 rendererInterface=lambda: SimpleNamespace(graphicsApi=lambda: SimpleNamespace(name='Software')))
        alpha = dict(material='translucent', coating_translucent=True, blur_configured=False, compositing_verified=False)
        with patch.object(native_runtime, 'widget_material', return_value=alpha), patch.object(native_runtime, 'desktop_level'):
            widget_report = self.runtime.compose(widget, 'cpu')
        self.assertEqual(self.runtime.controller.material, settings_report)
        self.assertEqual(self.runtime.composition['cpu'], widget_report)
        self.assertFalse(widget_report['blur_configured'])
        self.assertNotIn('lifecycle', widget_report)

    def test_shutdown_closes_bridge_before_other_owned_windows(self):
        self.show()
        self.runtime.top_bar = Mock()
        self.runtime.motion = {}
        self.runtime.drag_origins = {}
        self.runtime.floor_timer = Mock()
        self.runtime.stale_timer = Mock()
        self.runtime.position_timer = Mock()
        self.runtime.save_positions = Mock()
        self.runtime.tray = None
        self.runtime.shutdown()
        self.assertEqual(self.bridge.status()['state'], 'closed')
        self.assertIsNone(self.runtime.compose(self.runtime.settings, 'settings'))
        self.backend.assert_not_called()

    def test_theme_translucent_tokens_and_skin_match_but_fallback_remains_opaque(self):
        engine = QQmlEngine()
        engine.rootContext().setContextProperty('stats', self.runtime.controller)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'native/Theme.qml')))
        theme = component.create()
        self.assertIsNotNone(theme)
        self.runtime._publish_settings_material(copy.deepcopy(GOOD))
        self.assertEqual(theme.property('windowTop').alpha(), 163)
        self.assertEqual(theme.property('railTop').alpha(), 82)  # WUJI light chrome coating, 32%.
        self.assertEqual(palette('glass', False, transparency=50)['top'], theme.property('windowTop').name(theme.property('windowTop').NameFormat.HexArgb))
        self.runtime.controller._draft['theme'] = 'dark'
        self.runtime.controller.themeChanged.emit()
        self.assertEqual(theme.property('windowTop').alpha(), 214)
        self.assertEqual(theme.property('railTop').alpha(), 184)  # WUJI dark chrome coating, 72%.
        self.runtime._publish_settings_material(copy.deepcopy(FAILED))
        self.assertEqual(theme.property('windowTop').alpha(), 255)
        theme.deleteLater()
        engine.deleteLater()

    def test_compatibility_blur_does_not_reapply_on_every_activation(self):
        self.show()
        self.runtime.compose(self.runtime.settings, 'settings')
        count = self.backend.call_count
        for _ in range(10):
            QCoreApplication.sendEvent(self.runtime.settings, QEvent(QEvent.WindowDeactivate))
            QCoreApplication.sendEvent(self.runtime.settings, QEvent(QEvent.WindowActivate))
        self.due(2)
        self.assertEqual(self.backend.call_count, count)
        self.assertEqual(self.bridge.status()['state'], 'configured_unverified')

    def test_hidden_window_cannot_pass_apply_guard_but_can_release_own_surface(self):
        self.show()
        self.runtime.compose(self.runtime.settings, 'settings')
        context = self.bridge.status()
        handle, serial = context['surface_handle'], context['surface_serial']
        self.runtime.settings.hide()
        self.assertFalse(self.runtime._settings_surface_current(handle, serial))
        self.assertTrue(self.runtime._settings_surface_current(handle, serial, releasing=True))
        self.assertFalse(self.runtime._settings_surface_current(handle, serial + 1, releasing=True))
        self.assertFalse(self.bridge.status()['window_visible_now'])
        self.assertTrue(self.runtime.controller.material['lifecycle']['visible'])


class StructuredPolicyIntegrationTests(unittest.TestCase):
    def test_query_failure_is_unknown_with_raw_error_and_no_registry_guess(self):
        with patch.object(native_platform, '_system_parameters') as query, patch.object(native_platform.c, 'get_last_error', return_value=5), patch.object(native_platform.winreg, 'OpenKey') as registry:
            query.return_value.return_value = False
            self.assertEqual(native_platform.transparency_policy(), {'state': 'unknown', 'reason': 'accessibility-query-failed', 'winerror': 5})
            registry.assert_not_called()

    def test_optional_glass_policy_is_reused_without_any_second_policy_read(self):
        dwm, user = MagicMock(), MagicMock()
        attributes = []

        def set_attribute(_handle, attr, value, _size):
            attributes.append((attr, value._obj.value))
            return 0

        def read_attribute(_handle, _attr, value, _size):
            value._obj.value = 3
            return 0

        dwm.DwmSetWindowAttribute.side_effect = set_attribute
        dwm.DwmGetWindowAttribute.side_effect = read_attribute
        dwm.DwmExtendFrameIntoClientArea.return_value = 0
        user.GetWindowLongPtrW.return_value = 0
        with patch.object(native_platform.c, 'WinDLL', side_effect=lambda name, **kwargs: dwm if name == 'dwmapi' else user), patch.object(native_platform.sys, 'getwindowsversion', return_value=SimpleNamespace(build=26100)), patch.object(native_platform, 'transparency_enabled', side_effect=AssertionError('No repeated policy query')):
            report = native_platform.glass(123, policy={'state': 'allowed', 'reason': 'allowed'})
        self.assertEqual(report['material'], 'desktop-acrylic')
        self.assertIn((38, 3), attributes)
        self.assertFalse(report['compositing_verified'])


if __name__ == '__main__':
    unittest.main()
