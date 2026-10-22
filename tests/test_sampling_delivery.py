"""Healthy samples survive optional diagnostic-export failures; no hardware IO."""

import copy
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import native_controller as controls
from stats_config import DEFAULT


class SamplingDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Sampling regressions must not open a desktop UI")

    def setUp(self):
        config = copy.deepcopy(DEFAULT)
        config["refresh"] = .01
        with patch.object(controls, "load", return_value=config):
            self.ui = controls.Controller()
        self.now = 10.0
        self.sequence = 0
        self.delivered = []
        self.ui.sampleReady.connect(lambda reading: self.delivered.append(reading["sequence"]))
        self.sampler = SimpleNamespace(sample=Mock(side_effect=self.sample), write=Mock(), close=Mock())

    def tearDown(self):
        self.ui.close()
        self.ui.deleteLater()
        self.app.processEvents()

    def sample(self):
        value = dict(time=time.time(), cpu_usage=self.sequence % 100, sequence=self.sequence)
        self.sequence += 1
        return value

    def run_sampling(self, count, export):
        case = self

        class Stop:
            stopped = False
            iterations = 0

            def is_set(self):
                return self.stopped

            def set(self):
                self.stopped = True

            def wait(self, interval):
                self.iterations += 1
                case.now = round(case.now + interval, 6)
                if self.iterations >= count:
                    self.stopped = True
                return self.stopped

        self.ui.stop = Stop()
        self.sampler.write.side_effect = export
        with (
            patch.object(controls.sensors, "Sampler", return_value=self.sampler),
            patch.object(controls.time, "monotonic", side_effect=lambda: self.now),
            patch.object(controls.logging, "exception") as errors,
            patch.object(controls.logging, "info") as recovery,
            patch.object(controls, "save", side_effect=AssertionError("No settings persistence")),
        ):
            self.ui.start()
            self.ui.thread.join(timeout=3)
            self.assertFalse(self.ui.thread.is_alive(), "Synthetic sampling must finish")
            self.app.processEvents()
        self.sampler.close.assert_called_once_with()
        return errors, recovery

    def test_persistent_export_denial_does_not_drop_samples_or_flood_logs(self):
        def denied(_reading):
            raise PermissionError("Synthetic diagnostic file locked")

        errors, _ = self.run_sampling(200, denied)
        self.assertEqual(self.delivered, list(range(200)))
        self.assertEqual([row["sequence"] for row in self.ui._history], list(range(160, 200)))
        self.assertEqual(self.ui.readings["sequence"], 199)
        self.assertLessEqual(self.sampler.write.call_count, 2, "Failed exports need a retry cooldown")
        errors.assert_called_once()

    def test_export_recovers_without_restarting_or_replaying_old_data(self):
        written = []

        def locked_then_ready(reading):
            if self.now < 10.5:
                raise OSError("Synthetic disk temporarily unavailable")
            written.append(reading["sequence"])

        errors, recovery = self.run_sampling(180, locked_then_ready)
        self.assertEqual(self.delivered, list(range(180)))
        self.assertTrue(written, "Export must retry after the file becomes writable")
        self.assertGreaterEqual(written[0], 50)
        self.assertEqual(written[-1], 179)
        self.assertEqual([row["sequence"] for row in self.ui._history], list(range(140, 180)))
        errors.assert_called_once()
        recovery.assert_called_once()

    def test_healthy_exports_keep_every_successful_sample_in_order(self):
        written = []
        errors, recovery = self.run_sampling(25, lambda reading: written.append(reading["sequence"]))
        self.assertEqual(self.delivered, list(range(25)))
        self.assertEqual(written, list(range(25)))
        self.assertEqual([row["sequence"] for row in self.ui._history], list(range(25)))
        errors.assert_not_called()
        recovery.assert_not_called()

    def test_a_later_export_outage_is_reported_and_recovers_again(self):
        written = []

        def intermittent(reading):
            if self.now < 10.1 or 11.2 <= self.now < 11.3:
                raise PermissionError("Synthetic intermittent export lock")
            written.append(reading["sequence"])

        errors, recovery = self.run_sampling(300, intermittent)
        self.assertEqual(self.delivered, list(range(300)))
        self.assertEqual(errors.call_count, 2)
        self.assertEqual(recovery.call_count, 2)
        self.assertEqual(written[-1], 299)

    def test_sensor_failure_does_not_publish_or_export_the_previous_sample(self):
        def sometimes_unavailable():
            sequence = self.sequence
            self.sequence += 1
            if sequence == 1:
                raise OSError("Synthetic provider unavailable for one sample")
            return dict(time=time.time(), cpu_usage=sequence, sequence=sequence)

        self.sampler.sample.side_effect = sometimes_unavailable
        written = []
        errors, recovery = self.run_sampling(3, lambda reading: written.append(reading["sequence"]))
        self.assertEqual(self.delivered, [0, 2])
        self.assertEqual(written, [0, 2])
        self.assertEqual([row["sequence"] for row in self.ui._history], [0, 2])
        errors.assert_called_once_with("Sensor sampling failed")
        recovery.assert_not_called()


if __name__ == "__main__":
    unittest.main()
