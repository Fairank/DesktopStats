"""Independent transport/lifecycle audit with fake processes and in-memory pipes only."""

import copy
import importlib
import io
import json
import os
import queue
import subprocess
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import external_engine as transport
from external_sensor import PROVIDER, parse_snapshot


def fixture(value=0, *, stamp=1000.0, sensor_type="Power"):
    return dict(schema=1, provider=PROVIDER, version="0.9.6", timestamp=stamp,
                hardware=[dict(id="/fixture", name="Synthetic", type="Battery", parent_id=None)],
                sensors=[dict(id="/fixture/power/0", name="Fixture Power", hardware_id="/fixture",
                              hardware_name="Synthetic", hardware_type="Battery", type=sensor_type,
                              unit="W" if sensor_type == "Power" else "RPM", value=value,
                              min=None, max=None)])


def line(value=0, **kwargs):
    return (json.dumps(fixture(value, **kwargs)) + "\n").encode("utf-8")


class MemoryPipe:
    def __init__(self, chunks=()):
        self.chunks = queue.Queue()
        self.closed = False
        for chunk in chunks:
            self.chunks.put(chunk)

    def readline(self, limit=-1):
        chunk = self.chunks.get()
        return b"" if chunk is None else chunk[:limit] if limit >= 0 else chunk

    def read(self, limit=-1):
        return self.readline(limit)

    def finish(self):
        self.chunks.put(None)

    def close(self):
        self.closed = True
        self.finish()


class MemoryProcess:
    def __init__(self, chunks=()):
        self.stdout = MemoryPipe(chunks)
        self.stderr = MemoryPipe()
        self.stdin = Mock()
        self.stdin.write.side_effect = self._stop_input
        self.returncode = None
        self.finished = threading.Event()
        self.terminated = False
        self.killed = False

    def _stop_input(self, value):
        if value == b"stop\n":
            self.finish(0)
        return len(value)

    def finish(self, code):
        self.returncode = code
        self.finished.set()
        self.stdout.finish()
        self.stderr.finish()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self.finished.wait(timeout):
            raise subprocess.TimeoutExpired("in-memory collector", timeout)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.finish(-15)

    def kill(self):
        self.killed = True
        self.finish(-9)


class ExternalTransportTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(transport.subprocess, "Popen",
                                  side_effect=AssertionError("No real collector may start in tests"))
        self.popen = self.guard.start()
        self.addCleanup(self.guard.stop)
        self.engine = transport.ExternalEngine()
        self.addCleanup(self.engine.close)
        self.clock = dict(mono=10.0, wall=1000.0)
        for name, key in (("monotonic", "mono"), ("time", "wall")):
            replacement = patch.object(transport.time, name, side_effect=lambda key=key: self.clock[key])
            replacement.start()
            self.addCleanup(replacement.stop)

    def accepted(self, value=0):
        self.engine._accept(line(value), self.engine._generation)

    def fake_path(self):
        path = Mock()
        path.is_file.return_value = True
        path.__str__ = Mock(return_value="C:/private-fixture/collector.exe")
        path.parent = Path("C:/private-fixture")
        return path

    def test_idle_and_closed_engines_never_start_a_process_or_thread(self):
        self.assertEqual(self.engine.read()["external_status"]["state"], "idle")
        self.assertIsNone(self.engine._thread)
        self.engine.close()
        self.engine.read(active=True)
        self.assertIsNone(self.engine._thread)
        self.popen.assert_not_called()

    def test_hundred_hz_reads_share_snapshot_and_only_start_one_worker(self):
        started = threading.Event()
        def passive_worker():
            started.set()
            self.engine._stop.wait()
        with patch.object(self.engine, "_run", side_effect=passive_worker) as worker:
            self.engine.read(active=True)
            self.assertTrue(started.wait(1))
            with patch.object(transport, "parse_snapshot", wraps=parse_snapshot) as parser:
                self.accepted(0)
                previous = None
                for _ in range(100):
                    current = self.engine.read(active=True)
                    rows = current["external_sensors"]
                    if previous is not None:
                        self.assertIs(rows, previous)
                    self.assertEqual(rows["/fixture/power/0"]["value"], 0.0)
                    self.assertEqual(current["external_status"]["available_count"], 1)
                    previous = rows
                    self.clock["mono"] += 0.01
                    self.clock["wall"] += 0.01
                self.assertEqual(parser.call_count, 1)
            self.engine.close()
            worker.assert_called_once()
        self.popen.assert_not_called()

    def test_stale_and_disconnected_snapshots_keep_labels_but_never_old_values_or_zero(self):
        self.accepted(25)
        self.assertEqual(self.engine.read()["external_sensors"]["/fixture/power/0"]["value"], 25)
        self.clock["mono"] += transport.FRESH_SECONDS + 0.01
        stale = self.engine.read()
        row = stale["external_sensors"]["/fixture/power/0"]
        self.assertIsNone(row["value"])
        self.assertFalse(row["available"])
        self.assertEqual(row["name"], "Fixture Power")
        self.assertEqual(stale["external_status"]["state"], "stale")
        self.assertEqual(stale["external_status"]["available_count"], 0)
        self.accepted(0)
        self.engine._state("error", "synthetic disconnect")
        self.assertIsNone(self.engine.read()["external_sensors"]["/fixture/power/0"]["value"])

    def test_wall_clock_jump_alone_invalidates_a_monotonic_fresh_snapshot(self):
        self.accepted(7)
        for delta in (-100, 100):
            self.clock["wall"] = 1000 + delta
            with self.subTest(delta=delta):
                result = self.engine.read()
                self.assertIsNone(result["external_sensors"]["/fixture/power/0"]["value"])
                self.assertEqual(result["external_status"]["available_count"], 0)

    def test_rescan_and_shutdown_reject_late_old_generation_packets(self):
        self.engine._generation = 2
        self.engine._accept(line(10), 1)
        self.assertIsNone(self.engine._snapshot)
        self.engine._accept(line(20), 2)
        prior = self.engine._snapshot
        self.engine.close()
        self.engine._accept(line(30), 2)
        self.assertIs(self.engine._snapshot, prior)
        self.assertIsNone(self.engine.read()["external_sensors"]["/fixture/power/0"]["value"])

    def test_invalid_partial_oversize_duplicate_and_noncurrent_packets_fail_reader(self):
        duplicate = fixture()
        duplicate["sensors"].append(copy.deepcopy(duplicate["sensors"][0]))
        invalid = (b"diagnostic text\n", b"\xff\n", b"{}", b"[1]\n",
                   b"x" * (transport.MAX_LINE + 1) + b"\n",
                   (json.dumps(duplicate) + "\n").encode(), line(stamp=2000),
                   b"[" * 2000 + b"]" * 2000 + b"\n")
        for packet in invalid:
            with self.subTest(size=len(packet), prefix=packet[:20]):
                done, failed = threading.Event(), threading.Event()
                self.engine._consume(io.BytesIO(packet), self.engine._generation, done, failed)
                self.assertTrue(done.is_set())
                self.assertTrue(failed.is_set())
                self.assertIsNone(self.engine._snapshot)

    def test_graceful_shutdown_only_writes_to_and_waits_for_the_owned_process(self):
        process = MemoryProcess()
        transport.ExternalEngine._shutdown(process)
        process.stdin.write.assert_called_once_with(b"stop\n")
        process.stdin.close.assert_called_once()
        self.assertEqual(process.returncode, 0)
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)

    def test_shutdown_escalates_only_its_owned_process_after_timeouts(self):
        for timeout_count in (1, 2):
            with self.subTest(timeout_count=timeout_count):
                process = Mock()
                process.poll.return_value = None
                process.wait.side_effect = [subprocess.TimeoutExpired("fake", 1)] * timeout_count + [0]
                transport.ExternalEngine._shutdown(process)
                process.terminate.assert_called_once()
                self.assertEqual(process.kill.call_count, timeout_count - 1)
                timeouts = [call.kwargs["timeout"] for call in process.wait.call_args_list]
                self.assertEqual(len(timeouts), timeout_count + 1)
                self.assertTrue(all(0 < timeout <= 1.2 for timeout in timeouts))
                self.assertLess(sum(timeouts), 4.0)

    def test_missing_fixed_helper_does_not_fall_back_to_path_or_a_shell(self):
        path = self.fake_path()
        path.is_file.return_value = False
        with patch.object(transport, "collector_path", return_value=path):
            self.assertFalse(self.engine._session(0))
        self.assertEqual(self.engine.read()["external_status"]["state"], "missing")
        self.popen.assert_not_called()

    def test_real_worker_lifecycle_uses_only_fake_process_and_closes_all_memory_pipes(self):
        process = MemoryProcess((line(0),))
        spawned = threading.Event()
        def factory(*args, **kwargs):
            spawned.set()
            return process
        self.popen.side_effect = factory
        with patch.object(transport, "collector_path", return_value=self.fake_path()):
            self.engine.read(active=True)
            self.assertTrue(spawned.wait(1))
            for _ in range(100):
                if self.engine.read()["external_status"]["state"] == "ready":
                    break
                threading.Event().wait(0.005)
            self.assertEqual(self.engine.read()["external_status"]["state"], "ready")
            self.engine.close()
        self.assertFalse(self.engine._thread.is_alive())
        self.assertEqual(process.returncode, 0)
        self.assertTrue(process.stdout.closed and process.stderr.closed)
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0], ["C:/private-fixture/collector.exe", "--interval", "1"])
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["creationflags"], getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertNotIn("runas", str(args).lower())

    def test_bad_packet_session_invalidates_readings_and_releases_owned_process(self):
        process = MemoryProcess((b"bad json\n",))
        self.popen.side_effect = lambda *args, **kwargs: process
        self.engine._active_until = 1000
        with patch.object(transport, "collector_path", return_value=self.fake_path()):
            self.assertFalse(self.engine._session(0))
        self.assertEqual(self.engine.read()["external_status"]["state"], "error")
        self.assertEqual(process.returncode, 0)
        self.assertTrue(process.stdout.closed and process.stderr.closed)

    def test_unexpected_eof_keeps_last_sample_unavailable_after_process_exit(self):
        process = MemoryProcess((line(42),))
        process.finish(0)
        self.popen.side_effect = lambda *args, **kwargs: process
        self.engine._active_until = 1000
        with patch.object(transport, "collector_path", return_value=self.fake_path()):
            self.engine._session(0)
        result = self.engine.read()
        self.assertEqual(result["external_status"]["state"], "error")
        self.assertEqual(result["external_status"]["available_count"], 0)
        self.assertTrue(all(row["value"] is None for row in result["external_sensors"].values()))
        self.assertTrue(process.stdout.closed and process.stderr.closed)

    def test_late_old_session_packet_and_cleanup_cannot_overwrite_new_same_generation_session(self):
        old = object()
        self.engine._session_token = old
        self.engine._accept(line(10), self.engine._generation, old)
        self.engine._retire(old)
        current = object()
        self.engine._session_token = current
        self.engine._accept(line(20), self.engine._generation, current)
        prior = self.engine._snapshot
        self.engine._accept(line(99), self.engine._generation, old)
        self.engine._retire(old)
        self.assertIs(self.engine._snapshot, prior)
        result = self.engine.read()
        self.assertEqual(result["external_status"]["state"], "ready")
        self.assertEqual(result["external_sensors"]["/fixture/power/0"]["value"], 20)

    def test_buffered_packet_arriving_after_exit_cannot_restore_ready_state(self):
        release = threading.Event()
        class DelayedPipe(MemoryPipe):
            def readline(self, limit=-1):
                release.wait(1)
                return super().readline(limit)
        process = MemoryProcess()
        process.stdout = DelayedPipe((line(42),))
        process.finish(0)
        self.popen.side_effect = lambda *args, **kwargs: process
        self.engine._active_until = 1000
        original = self.engine._state
        def state(state, detail):
            original(state, detail)
            if state == "error":
                release.set()
        try:
            with (
                patch.object(transport, "collector_path", return_value=self.fake_path()),
                patch.object(self.engine, "_state", side_effect=state),
            ):
                self.engine._session(0)
            result = self.engine.read()
            self.assertEqual(result["external_status"]["state"], "error")
            self.assertEqual(result["external_status"]["available_count"], 0)
            self.assertTrue(all(row["value"] is None for row in result["external_sensors"].values()))
        finally:
            release.set()
            process.finish(0)

    def test_startup_timeout_stops_owned_process_without_a_real_time_wait(self):
        process = MemoryProcess()
        self.popen.side_effect = lambda *args, **kwargs: process
        self.engine._active_until = 1000
        wake = Mock()
        wake.wait.side_effect = lambda _: self.clock.update(mono=self.clock["mono"] + 10)
        self.engine._wake = wake
        with patch.object(transport, "collector_path", return_value=self.fake_path()):
            self.assertFalse(self.engine._session(0))
        self.assertEqual(self.engine.read()["external_status"]["state"], "stale")
        self.assertEqual(process.returncode, 0)
        self.assertTrue(process.stdout.closed and process.stderr.closed)

    def test_session_closes_streams_even_if_process_shutdown_raises(self):
        process = MemoryProcess()
        self.popen.side_effect = lambda *args, **kwargs: process
        try:
            with (
                patch.object(transport, "collector_path", return_value=self.fake_path()),
                patch.object(self.engine, "_wanted", return_value=False),
                patch.object(self.engine, "_shutdown", side_effect=OSError("synthetic termination failure")),
            ):
                with self.assertRaises(OSError):
                    self.engine._session(0)
            self.assertTrue(process.stdout.closed and process.stderr.closed)
        finally:
            process.finish(0)

    def test_denied_cleanup_does_not_spawn_a_second_process_over_an_outstanding_one(self):
        process = Mock()
        process.poll.return_value = None
        self.engine._process = process
        self.engine._active_until = 1000
        wake = Mock()
        waits = []
        def wait(timeout):
            waits.append(timeout)
            if len(waits) == 3:
                self.engine._stop.set()
        wake.wait.side_effect = wait
        self.engine._wake = wake
        with patch.object(self.engine, "_session") as session:
            self.engine._run()
        session.assert_not_called()
        self.popen.assert_not_called()
        self.assertEqual(self.engine.read()["external_status"]["state"], "error")

    def test_close_reports_error_while_owned_process_or_worker_is_unfinished(self):
        for live_thread, live_process in ((True, False), (False, True)):
            with self.subTest(live_thread=live_thread, live_process=live_process):
                thread, process = Mock(), Mock()
                thread.is_alive.return_value = live_thread
                process.poll.return_value = None if live_process else 0
                self.engine._thread, self.engine._process = thread, process
                self.engine.close()
                status = self.engine.read()["external_status"]
                self.assertEqual(status["state"], "error")
                self.assertIn("尚未结束", status["detail"])


class ExternalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = Path(__file__).resolve().parents[1] / "qa-private/redesign08/external-transport-temp"
        directory.mkdir(parents=True, exist_ok=True)
        cls.profile = tempfile.TemporaryDirectory(dir=directory)
        with patch.dict(os.environ, {"DESKTOP_STATS_DATA": cls.profile.name, "QT_QPA_PLATFORM": "offscreen"}):
            cls.controls = importlib.import_module("native_controller")
            cls.sensors = importlib.import_module("sensors")
            cls.settings = importlib.import_module("stats_config")
            cls.catalog = importlib.import_module("widget_catalog")

    @classmethod
    def tearDownClass(cls):
        cls.profile.cleanup()

    def setUp(self):
        self.guard = patch.object(transport.subprocess, "Popen",
                                  side_effect=AssertionError("No real helper may start"))
        self.popen = self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_external_display_name_is_literal_and_not_a_localization_key(self):
        prefs = self.catalog.from_template("custom")
        prefs.update(content=["external_1"], sensor_bindings={"external_1": dict(
            provider=PROVIDER, sensor_id="/fixture/power/0", sensor_type="Power",
            name="内存", hardware_name="Synthetic")})
        config = self.settings.validate(dict(version=7, language="de", widgets={"one": prefs},
                                            widget_order=["one"]))
        with patch.object(self.controls, "load", return_value=config):
            controller = self.controls.Controller()
        self.assertEqual(controller.metricInfoFor("one", "external_1")["label"], "内存")

    def test_unsaved_binding_previews_current_value_then_revert_removes_it(self):
        config = self.settings.validate(dict(version=7, widgets={"one": self.catalog.from_template("custom")},
                                            widget_order=["one"]))
        with patch.object(self.controls, "load", return_value=copy.deepcopy(config)):
            controller = self.controls.Controller()
        rows = parse_snapshot(fixture(0))["sensors"]
        controller.receive(dict(time=1000, external_catalog=rows, external_sensors={},
                                external_revision=(1, True), external_status={"state": "ready"}))
        discovered = next(row for row in controller.metricRowsFor("one") if row["id"].startswith("lhm:"))
        self.assertNotIn("external_1", [row["id"] for row in controller.sensorRows])
        controller.addMetric("one", discovered["id"])
        self.assertIn("external_1", controller._draft["widgets"]["one"]["content"])
        self.assertNotIn("external_1", controller._saved["widgets"]["one"]["content"])
        self.assertEqual(controller.unitFor("one", "external_1"), "W")
        self.assertNotEqual(controller.readingFor("one", "external_1"), "—")
        self.assertEqual(len(controller._data["external_sensors"]), 1)
        controller.revert()
        self.assertEqual(controller._draft, config)
        self.assertEqual(controller._data["external_sensors"], {})
        self.popen.assert_not_called()

    def test_sampler_filters_desktop_rows_but_retains_full_draft_discovery_catalog(self):
        rows = parse_snapshot(fixture(0))["sensors"]
        extra = dict(next(iter(rows.values())), id="/unbound/fan/0", type="Fan", unit="RPM", value=1200)
        rows[extra["id"]] = extra
        prefs = self.catalog.from_template("custom")
        prefs.update(content=["external_1"], sensor_bindings={"external_1": dict(
            provider=PROVIDER, sensor_id="/fixture/power/0", sensor_type="Power",
            name="Fixture Power", hardware_name="Synthetic")})
        config = self.settings.validate(dict(version=7, widgets={"one": prefs}, widget_order=["one"], refresh=0.01))
        sampler = object.__new__(self.sensors.Sampler)
        sampler.__dict__.update(cpu="Synthetic", cores=4, threads=8, first=False, _closed=False,
                                asus=None, nvidia=None, nvml_retry=float("inf"),
                                battery=Mock(read=Mock(return_value={})),
                                storage=Mock(read=Mock(return_value={"storages": {}, "storage_status": {"state": "idle"}})),
                                activity=Mock(read=Mock(return_value={})),
                                cpu_power=Mock(), cooling=SimpleNamespace(sample_times={}))
        sampler.external = Mock()
        sampler.external.read.side_effect = lambda *args: dict(external_sensors=rows,
            external_revision=(1, True), external_status={"state": "ready"})
        ram = SimpleNamespace(percent=20, used=10, total=100, available=90)
        swap = SimpleNamespace(percent=0, used=0)
        with ExitStack() as stack:
            for target, value in (("load", config), ("hwinfo_registry", {}),
                                  ("psutil.cpu_percent", 1), ("psutil.sensors_battery", None),
                                  ("psutil.virtual_memory", ram), ("psutil.swap_memory", swap)):
                stack.enter_context(patch(f"sensors.{target}", return_value=value))
            stack.enter_context(patch.object(self.sensors, "INSPECT_UNTIL", 0))
            for _ in range(100):
                data = sampler.sample()
                self.assertIs(data["external_catalog"], rows)
                self.assertEqual(set(data["external_sensors"]), {"/fixture/power/0"})
                self.assertEqual(data["external_sensors"]["/fixture/power/0"]["value"], 0)
        self.assertEqual(sampler.external.read.call_count, 100)
        self.assertTrue(all(call.args[0] is True for call in sampler.external.read.call_args_list))
        self.popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
