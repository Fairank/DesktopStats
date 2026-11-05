"""Demand leases and real controller projection; no user processes or files."""

import copy
import time
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import native_controller as controls
import process_usage
from stats_config import DEFAULT, validate


class ProcessControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.native = self.enterContext(
            patch("ctypes.WinDLL", side_effect=AssertionError("No native API"))
        )
        self.spawn = self.enterContext(
            patch("subprocess.Popen", side_effect=AssertionError("No process"))
        )
        self.thread = self.enterContext(
            patch("threading.Thread.start", side_effect=AssertionError("No worker"))
        )
        self.config = validate(copy.deepcopy(DEFAULT))
        with patch.object(controls, "load", return_value=self.config):
            self.ui = controls.Controller()
        self.ui._process_sampling_enabled = (
            True  # Running lifecycle; only the process boundary is fake.
        )
        self.addCleanup(self.ui.close)
        self.assertTrue(
            callable(getattr(self.ui, "beginProcessUsage", None)),
            "Detail demand leases are missing",
        )
        self.monitors = []
        fixtures = self

        class Monitor:
            def __init__(self, callback):
                self.callback = callback
                self.generation = 0
                self.targets = {}
                self.closed = False
                fixtures.monitors.append(self)

            def set_targets(self, targets):
                if self.targets != targets:
                    self.generation += 1
                    self.targets = copy.deepcopy(targets)
                return self.generation

            def close(self):
                self.closed = True

        self.enterContext(patch.object(process_usage, "ProcessUsageMonitor", Monitor))

    def deliver(self, token, kind="cpu", value=25.0, generation=None):
        monitor = self.monitors[-1]
        monitor.callback(
            monitor.generation if generation is None else generation,
            {
                token: dict(
                    kind=kind,
                    state="ready",
                    reason_code="",
                    denied_count=0,
                    timestamp=time.time(),
                    unit="%",
                    rows=[dict(name="<Chrome>.exe", value=value, fraction=0.25, process_count=4)],
                )
            },
        )

    def test_opening_cpu_detail_publishes_top_five_without_changing_configuration(self):
        token = self.ui.beginProcessUsage("cpu_temp", "")
        self.assertEqual(self.ui.processUsage(token)["state"], "warming_up")
        self.deliver(token)
        result = self.ui.processUsage(token)
        self.assertEqual(result["rows"][0]["name"], "<Chrome>.exe")
        self.assertEqual(result["rows"][0]["value_text"], "25 %")
        self.assertEqual(result["kind"], "cpu")
        self.assertEqual(result["caption"], "CPU 使用率")
        self.assertEqual(self.ui._saved, self.config)
        self.assertEqual(self.ui._draft, self.config)
        self.assertNotIn("<Chrome>.exe", str(self.ui._data))

    def test_ordinary_readings_and_detail_getters_never_start_process_sampling(self):
        for _ in range(20):
            self.ui.topBarRows()
            self.ui.topBarDetailRow("missing")
            self.assertEqual(self.ui.processUsage("missing"), {})
        self.assertEqual(self.monitors, [])
        self.thread.assert_not_called()
        self.native.assert_not_called()

    def test_unidentified_process_names_are_not_reported_as_permission_failures(self):
        token = self.ui.beginProcessUsage("cpu_usage", "")
        self.deliver(token)
        self.ui._process_results[token].update(unidentified_count=2, state="partial")
        coverage = self.ui.processUsage(token)["coverage"]
        self.assertIn("名称", coverage)
        self.assertIn("2", coverage)
        self.assertNotIn("受保护", coverage)

    def test_replaced_target_discards_late_cpu_reply_and_keeps_gpu_identity(self):
        token = self.ui.beginProcessUsage("cpu_usage", "")
        old = self.monitors[-1].generation
        self.ui.updateProcessUsage(token, "gpu_usage", "GPU B")
        self.deliver(token, generation=old)
        self.assertEqual(self.ui.processUsage(token)["kind"], "gpu")
        self.assertEqual(self.ui.processUsage(token)["rows"], [])
        self.assertEqual(self.monitors[-1].targets[token]["hardware_name"], "GPU B")

    def test_old_card_release_cannot_cancel_replacement_card(self):
        old = self.ui.beginProcessUsage("cpu_usage", "")
        new = self.ui.beginProcessUsage("ram_percent", "")
        self.ui.endProcessUsage(old)
        self.deliver(new, kind="memory", value=256 * 2**20)
        self.assertEqual(self.ui.processUsage(new)["rows"][0]["value_text"], "256 MiB")
        self.ui.endProcessUsage(old)
        self.assertEqual(self.ui.processUsage(new)["rows"][0]["name"], "<Chrome>.exe")
        self.ui.endProcessUsage(new)
        self.assertEqual(self.monitors[-1].targets, {})

    def test_network_without_attribution_explains_reason_without_starting_worker(self):
        token = self.ui.beginProcessUsage("net_download", "Wi-Fi")
        result = self.ui.processUsage(token)
        self.assertEqual(result["state"], "unavailable")
        self.assertEqual(result["reason_code"], "not_attributable")
        self.assertTrue(result["reason"])
        self.assertEqual(result["rows"], [])
        self.assertEqual(self.monitors, [])

    def test_unstarted_or_self_check_controller_does_not_launch_process_queries(self):
        self.ui._process_sampling_enabled = False
        token = self.ui.beginProcessUsage("cpu_usage", "")
        self.assertEqual(self.ui.processUsage(token)["state"], "warming_up")
        self.assertEqual(self.monitors, [])

    def test_expired_report_is_not_presented_as_current_top_five(self):
        token = self.ui.beginProcessUsage("cpu_usage", "")
        self.deliver(token)
        with patch("native_controller.time.time", return_value=time.time() + 20):
            result = self.ui.processUsage(token)
        self.assertEqual(result["state"], "stale")
        self.assertEqual(result["rows"], [])

    def test_closed_controller_ignores_late_reply(self):
        token = self.ui.beginProcessUsage("cpu_usage", "")
        self.ui.close()
        self.deliver(token)
        self.assertEqual(self.ui.processUsage(token), {})
        self.assertTrue(self.monitors[-1].closed)


if __name__ == "__main__":
    unittest.main()
