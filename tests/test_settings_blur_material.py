"""Current settings backend lifecycle; fake API and guarded identity only."""
import unittest
from unittest.mock import Mock

from settings_blur_material import SettingsBlurMaterial


class SettingsBlurMaterialTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.apply.return_value = dict(material="system-blur", status="configured-unverified",
            coating_allowed=True, coating_translucent=True, blur_configured=True, bool_result=1, ok=True)
        self.backend.clear.return_value = dict(ok=True, cleanup_complete=True, blur_may_remain=False)
        self.backend.close.return_value = dict(ok=True)
        self.clearer = Mock(return_value=dict(ok=True))
        self.material = SettingsBlurMaterial(self.backend, self.clearer)
        self.generation = 1

    def apply(self, generation=1):
        return self.material.apply(123, dict(state="allowed"), surface_id=generation,
                                   valid=lambda: self.generation == generation)

    def release(self, generation=1):
        return self.material.clear(123, surface_id=generation, valid=lambda: self.generation == generation)

    def test_same_surface_prepares_once_and_reports_only_unverified_blur(self):
        first = self.apply()
        self.apply()
        self.assertEqual(self.clearer.call_count, 1)
        self.assertEqual(self.backend.apply.call_count, 2)
        self.assertEqual(first["status"], "configured-unverified")
        self.assertTrue(first["activation_independent"])

    def test_release_requires_current_serial_even_for_reused_handle(self):
        self.apply()
        self.generation = 2
        self.assertFalse(self.release()["ok"])
        self.backend.clear.assert_not_called()
        self.assertEqual(self.apply(2)["fallback_reason"], "settings-previous-surface-cleanup-failed")
        self.assertEqual(self.backend.apply.call_count, 1)

    def test_new_surface_after_successful_release_must_prepare_again(self):
        self.apply()
        self.assertTrue(self.release()["ok"])
        self.generation = 2
        self.assertTrue(self.apply(2)["blur_configured"])
        self.assertEqual(self.clearer.call_count, 2)

    def test_clearer_reentrant_release_recreation_never_applies_new_surface(self):
        def recreate(handle):
            self.release()
            self.generation = 2
            return dict(ok=True)
        self.clearer.side_effect = recreate
        self.assertEqual(self.apply()["fallback_reason"], "settings-surface-not-current")
        self.backend.apply.assert_not_called()

    def test_failed_cleanup_blocks_reused_integer_without_new_native_calls(self):
        self.apply()
        self.backend.clear.return_value = dict(ok=False, cleanup_complete=False, blur_may_remain=True)
        self.release()
        self.generation = 2
        self.assertFalse(self.apply(2)["coating_allowed"])
        self.assertEqual(self.clearer.call_count, 1)
        self.assertEqual(self.backend.apply.call_count, 1)

    def test_clearer_exception_is_diagnosed_and_does_not_enable_blur(self):
        self.clearer.side_effect = OSError("synthetic unavailable")
        result = self.apply()
        self.assertEqual(result["fallback_reason"], "settings-backdrop-clear-exception")
        self.assertFalse(result["coating_translucent"])
        self.backend.apply.assert_not_called()

    def test_closed_backend_never_prepares_or_applies(self):
        self.material.close()
        self.assertEqual(self.apply()["fallback_reason"], "settings-backend-closed")
        self.clearer.assert_not_called()
        self.backend.apply.assert_not_called()

    def test_policy_unknown_delegates_cleanup_without_preparing_dwm(self):
        self.material.apply(123, dict(state="unknown"), surface_id=1, valid=lambda: True)
        self.clearer.assert_not_called()
        self.backend.apply.assert_called_once_with(123, enabled=True, policy=dict(state="unknown"))
