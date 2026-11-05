"""Blocked fake NVML shutdown must not stop unrelated sampling or delivery."""
import copy
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

import sensors
import test_provider_recovery as fixture
import test_sensor_source_isolation as source_fixture

REAL_START = sensors._NvidiaCleanup.start
REAL_THREAD_START = threading.Thread.start


class NvmlCleanupIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        assert cls.app.platformName() == "offscreen"

    def setUp(self):
        self.case = fixture.RecoveryTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.sampler = self.case.sampler
        self.enterContext(patch.object(threading.Thread, "start", REAL_THREAD_START))
        self.enterContext(patch.object(sensors._NvidiaCleanup, "start", REAL_START))
        self.releases = []
        self.addCleanup(self.release_tasks)

    def release_tasks(self):
        for release in self.releases:
            release.set()
        task = getattr(self.sampler, "_nvml_cleanup_task", None)
        if task is not None:
            self.assertTrue(task.done.wait(1), "Fake cleanup failed to finish")
            self.sampler._consume_nvidia_cleanup()

    def blocked_source(self):
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        names = []

        def close():
            names.append(threading.current_thread().name)
            entered.set()
            release.wait()

        source = SimpleNamespace(read=Mock(return_value={}), close=Mock(side_effect=close),
                                 library=object())
        return source, entered, release, names

    def bounded(self, action):
        results, errors = [], []

        def run():
            try:
                results.append(action())
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=run, name="test-sampling-call", daemon=True)
        thread.start()
        thread.join(1)
        self.assertFalse(thread.is_alive(), "Sampler waited for the blocked driver cleanup")
        if errors:
            raise errors[0]
        return results[0]

    def test_blocked_shutdown_keeps_cpu_bridge_temperature_network_and_disk_fresh(self):
        source, entered, release, names = self.blocked_source()
        self.sampler.nvidia = source
        self.case.asus.read.return_value = {}
        self.sampler.cpu_thermal.read = Mock(return_value={"cpu_temp": 48,
                                                         "cpu_temp_source": "Synthetic MMF"})
        self.case.activity.read.return_value = {"net_download": 2, "disk_read": 3}
        first = self.bounded(self.sampler.sample)
        self.assertTrue(entered.wait(1))
        task = self.sampler._nvml_cleanup_task
        self.assertIn(task, sensors._NVML_CLEANUP_RETAINERS)
        self.assertIs(task.source, source)
        self.assertIsNone(self.sampler.nvidia)
        self.assertEqual(first["cpu_temp"], 48)
        for usage in (20, 30, 40):
            self.case.now += 100
            with patch("sensors.psutil.cpu_percent", return_value=usage):
                data = self.bounded(self.sampler.sample)
            self.assertEqual(data["cpu_usage"], usage)
            self.assertEqual(data["cpu_temp"], 48)
            self.assertEqual((data["net_download"], data["disk_read"]), (2, 3))
            self.assertEqual(data["ram_percent"], 20)
            self.assertGreater(data["time"], first["time"])
            self.assertTrue(data["provider_status"]["nvml"]["cleanup_pending"])
            self.assertIs(self.sampler._nvml_cleanup_task, task)
        self.case.gpu_factory.assert_not_called()
        source.read.assert_called_once()
        source.close.assert_called_once()
        self.assertEqual(names, ["nvml-cleanup"])
        release.set()
        self.assertTrue(task.done.wait(1))

    def test_shutdown_returns_without_join_and_retains_owner_until_completion(self):
        source, entered, release, _ = self.blocked_source()
        self.sampler.nvidia = source
        self.assertFalse(self.bounded(self.sampler.close))
        self.assertTrue(entered.wait(1))
        task = self.sampler._nvml_cleanup_task
        self.assertIn(task, sensors._NVML_CLEANUP_RETAINERS)
        self.assertIs(task.source.library, source.library)
        self.assertFalse(self.bounded(self.sampler.close))
        source.close.assert_called_once()
        self.assertEqual(self.sampler.sample(), {})
        release.set()
        self.assertTrue(task.done.wait(1))
        self.assertTrue(self.sampler.close())
        self.assertNotIn(task, sensors._NVML_CLEANUP_RETAINERS)
        self.assertIsNone(self.sampler._nvml_cleanup)

    def test_failed_close_retries_at_backoff_without_overlapping_or_reinitializing(self):
        tasks = []

        def defer(task):
            sensors._NVML_CLEANUP_RETAINERS.add(task)
            tasks.append(task)

        self.enterContext(patch.object(sensors._NvidiaCleanup, "start", defer))
        source = SimpleNamespace(read=Mock(return_value={}), close=Mock(side_effect=[OSError("lost"), None]))
        self.sampler.nvidia = source
        self.sampler.sample()
        source.close.assert_not_called()
        self.case.now = 110
        for _ in range(10):
            self.sampler.sample()
        self.assertEqual(len(tasks), 1)
        tasks[0]._run()
        self.sampler.sample()
        self.assertEqual(self.sampler._nvml_cleanup_retry, 115)
        self.case.now = 114.999
        self.sampler.sample()
        self.assertEqual(len(tasks), 1)
        self.case.now = 115
        self.sampler.sample()
        self.assertEqual(len(tasks), 2)
        self.case.gpu_factory.assert_not_called()
        self.assertNotIn(tasks[0], sensors._NVML_CLEANUP_RETAINERS)
        tasks[1]._run()
        self.assertEqual(self.sampler.sample()["gpu_power"], 0)
        self.assertIsNone(self.sampler._nvml_cleanup)
        self.assertEqual(source.close.call_count, 2)
        self.assertEqual(self.case.gpu_factory.call_count, 1)

    def test_constructor_discovery_failure_also_defers_blocked_shutdown(self):
        source, entered, release, _ = self.blocked_source()
        library = source_fixture.NvmlLibrary()
        library.count_status = 9
        library.nvmlShutdown = source_fixture.Function(source.close)
        with patch("sensors.Nvidia", fixture.REAL_NVIDIA), patch("sensors.c.CDLL", return_value=library):
            data = self.bounded(self.sampler.sample)
            self.case.assert_healthy_other_sources(data)
            self.assertTrue(entered.wait(1))
            self.assertEqual(data["provider_status"]["nvml"]["error"]["api"], "nvmlDeviceGetCount_v2")
            owner = self.sampler._nvml_cleanup
            self.assertIs(owner.lib, library)
            self.assertTrue(owner._initialized)
            self.bounded(self.sampler.sample)
            source.close.assert_called_once()
        release.set()

    def test_controller_delivers_and_records_history_while_cleanup_remains_blocked(self):
        import native_controller as controls
        source, entered, release, _ = self.blocked_source()
        self.sampler.nvidia = source
        config = copy.deepcopy(self.case.sampler.config_provider() if
            callable(getattr(self.sampler, "config_provider", None)) else fixture.DEFAULT)
        config.update(refresh=.01, history_enabled=False)
        with patch.object(controls, "load", return_value=config):
            ui = controls.Controller()
        recorded = []

        def record(data):
            recorded.append(data)
            if len(recorded) == 3:
                ui.stop.set()

        ui._record_history = record
        try:
            with patch.object(controls.sensors, "Sampler", return_value=self.sampler):
                ui.start()
                ui.thread.join(1)
            self.assertFalse(ui.thread.is_alive())
            self.assertTrue(entered.wait(1))
            self.assertEqual(len(recorded), 3)
            self.assertTrue(all(data["cpu_usage"] == 12 for data in recorded))
            self.app.processEvents()
            self.assertEqual(ui._data["cpu_usage"], 12)
            self.assertFalse(self.sampler._nvml_cleanup_task.done.is_set())
            source.close.assert_called_once()
        finally:
            release.set()
            ui.close()
            ui.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
