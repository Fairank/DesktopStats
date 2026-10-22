"""Unreadable Windows policy is distinguishable from a deliberate fallback."""
import unittest
from unittest.mock import patch

import native_platform as platform


class MaterialPolicyDiagnosticsTests(unittest.TestCase):
    def query(self, flags=0, success=1):
        def read(action, size, output, reserved):
            output._obj.flags = flags
            return success
        return read

    def test_accessibility_disabled_and_query_failure_have_different_causes(self):
        with patch.object(platform, "_system_parameters", return_value=self.query(flags=1)):
            self.assertEqual(platform.transparency_policy(), {"state": "disabled", "reason": "high-contrast"})
        with patch.object(platform, "_system_parameters", return_value=self.query(success=0)):
            report = platform.transparency_policy()
        self.assertEqual(report["state"], "unknown")
        self.assertEqual(report["reason"], "accessibility-query-failed")
        self.assertIn("winerror", report)

    def test_registry_failure_keeps_actual_permission_error(self):
        error = PermissionError("fixture access denied")
        error.winerror = 5
        with patch.object(platform, "_system_parameters", return_value=self.query()), patch.object(platform.winreg, "OpenKey", side_effect=error):
            report = platform.transparency_policy()
        self.assertEqual(report["state"], "unknown")
        self.assertEqual(report["reason"], "transparency-preference-unreadable")
        self.assertEqual(report["winerror"], 5)

    def test_preference_disabled_allowed_and_invalid_are_not_conflated(self):
        for value, state in ((0, "disabled"), (1, "allowed"), (True, "unknown"), ("1", "unknown"), (2, "unknown")):
            with self.subTest(value=value), patch.object(platform, "_system_parameters", return_value=self.query()), patch.object(platform.winreg, "OpenKey"), patch.object(platform.winreg, "QueryValueEx", return_value=(value, 4)):
                self.assertEqual(platform.transparency_policy()["state"], state)


if __name__ == "__main__":
    unittest.main()
