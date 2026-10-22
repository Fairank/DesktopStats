"""NVMe decoding, exact targets and bounded child transport with synthetic data only."""

import copy
import json
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from metrics import metric_value, required_sources
from stats_config import DEFAULT
from storage_sensor import FIELDS, SOURCE, StorageHealth, decode_health, parse_reply, worker_main


def response(kelvin=303, spare=100, wear=2):
    raw = bytearray(560)
    struct.pack_into("<12I", raw, 0, 48, 48, 3, 2, 2, 0, 40, 512, 0, 0, 0, 0)
    struct.pack_into("<H", raw, 49, kelvin)
    raw[51], raw[53] = spare, wear
    return bytes(raw)


def reply(**changes):
    row = dict(
        label="Not trusted",
        source=SOURCE,
        state="available",
        storage_temp=29.85,
        storage_spare_percent=100,
        storage_wear_percent=0,
    )
    return dict(
        schema=1,
        provider=SOURCE,
        timestamp=time.time(),
        state="ready",
        storages={"0": dict(row, **changes)},
    )


class StorageDecodeTests(unittest.TestCase):
    def test_correct_kelvin_offset_and_endurance_above_100(self):
        values = decode_health(response(wear=255))
        self.assertAlmostEqual(values["storage_temp"], 29.85)
        self.assertEqual(values["storage_wear_percent"], 255)
        self.assertEqual(values["storage_spare_percent"], 100)

    def test_invalid_sentinels_do_not_destroy_independent_values(self):
        for kelvin in (0, 65535):
            value = decode_health(response(kelvin=kelvin, spare=255, wear=0))
            self.assertIsNone(value["storage_temp"])
            self.assertIsNone(value["storage_spare_percent"])
            self.assertEqual(value["storage_wear_percent"], 0)

    def test_short_wrong_protocol_and_out_of_bounds_descriptor_rejected(self):
        for raw in (b"", response()[:559], b"x" * 560):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                decode_health(raw)
        data = bytearray(response())
        struct.pack_into("<I", data, 24, 2048)
        with self.assertRaises(ValueError):
            decode_health(bytes(data))

    def test_snapshot_numbers_and_clock_are_validated(self):
        self.assertEqual(parse_reply(reply())["storages"]["0"]["label"], "PhysicalDrive0")
        for changes in (
            {"storage_temp": True},
            {"storage_temp": float("nan")},
            {"storage_spare_percent": 101},
            {"storage_wear_percent": 256},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_reply(reply(**changes))
        with self.assertRaises(ValueError):
            parse_reply(dict(reply(), timestamp=time.time() + 30))

    def test_failed_query_never_reuses_reported_old_number(self):
        value = parse_reply(reply(state="query_failed", winerror=5))
        self.assertEqual(value["storages"]["0"]["winerror"], 5)
        self.assertTrue(all(value["storages"]["0"][field] is None for field in FIELDS))

    def test_selected_disk_does_not_fall_back_to_zero_and_valid_zero_survives(self):
        data = parse_reply(reply())
        self.assertEqual(metric_value(data, "storage_wear_percent", {"storage_target": "0"}), 0)
        self.assertIsNone(metric_value(data, "storage_temp", {"storage_target": "1"}))
        config = copy.deepcopy(DEFAULT)
        config["widgets"]["cpu"]["content"] = ["storage_temp"]
        self.assertIn("storage", required_sources(config))


class StorageTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = StorageHealth(Path(self.temp.name))
        self.addCleanup(self.engine.close)
        self.native = patch(
            "storage_sensor.c.WinDLL", side_effect=AssertionError("No native calls")
        )
        self.native.start()
        self.addCleanup(self.native.stop)

    def test_default_is_inert(self):
        with (
            patch("storage_sensor.threading.Thread.start") as start,
            patch("storage_sensor.subprocess.Popen") as spawn,
        ):
            self.assertEqual(self.engine.read()["storages"], {})
            start.assert_not_called()
            spawn.assert_not_called()

    def test_worker_reply_is_under_isolated_profile_and_not_stdout(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0

        def spawn(command, **options):
            self.assertEqual(options["creationflags"], subprocess.CREATE_NO_WINDOW)
            self.assertFalse(options["shell"])
            self.assertEqual(command[-2], "--storage-read")
            output = Path(command[-1])
            self.assertTrue(output.is_relative_to(self.engine.base / "storage-probes"))
            output.write_text(json.dumps(reply()), encoding="utf-8")
            return process

        with patch("storage_sensor.subprocess.Popen", side_effect=spawn):
            self.engine._query()
        self.assertEqual(self.engine.read()["storages"]["0"]["storage_wear_percent"], 0)
        process.wait.assert_called_once_with(timeout=3)
        process.kill.assert_not_called()

    def test_timeout_kills_only_retained_child_and_clears_snapshot(self):
        self.engine._snapshot = reply()
        process = Mock(returncode=-9)
        process.poll.side_effect = [None, -9]
        process.wait.side_effect = [subprocess.TimeoutExpired("own-child", 3), -9]
        with patch("storage_sensor.subprocess.Popen", return_value=process):
            self.engine._query()
        process.kill.assert_called_once_with()
        self.assertEqual(self.engine.read()["storages"], {})
        self.assertIn("timed out", self.engine.read()["storage_status"]["detail"])

    def test_clock_reversal_or_old_receipt_cannot_keep_readings(self):
        self.engine._snapshot = parse_reply(reply())
        self.engine._received = 100
        for stamp in (90, 109):
            with patch("storage_sensor.time.monotonic", return_value=stamp):
                data = self.engine.read()
                self.assertIsNone(data["storages"]["0"]["storage_temp"])
                self.assertEqual(data["storage_status"]["state"], "stale")

    def test_worker_rejects_unrelated_destination_before_native_query(self):
        with (
            patch("stats_config.BASE", Path(self.temp.name)),
            patch("storage_sensor.read_native") as native,
        ):
            self.assertEqual(worker_main(str(Path(self.temp.name) / "unrelated.json")), 2)
            native.assert_not_called()

    def test_closed_provider_never_starts_query_or_keeps_values(self):
        self.engine._snapshot = parse_reply(reply())
        self.engine._received = time.monotonic()
        self.engine.close()
        with patch("storage_sensor.subprocess.Popen") as spawn:
            self.engine._query()
            data = self.engine.read(True)
        spawn.assert_not_called()
        self.assertEqual(data["storage_status"]["state"], "closed")
        self.assertIsNone(data["storages"]["0"]["storage_temp"])

    def test_failed_kill_keeps_ownership_and_blocks_next_spawn_until_recovered(self):
        process = Mock(returncode=None)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("own-child", 3)
        process.kill.side_effect = PermissionError("Synthetic kill failure")
        with patch("storage_sensor.subprocess.Popen", return_value=process) as spawn:
            self.engine._query()
            self.assertIs(self.engine._process, process)
            self.assertEqual(self.engine.read()["storage_status"]["state"], "cleanup_pending")
            self.engine._query()
            self.assertEqual(spawn.call_count, 1)
            self.assertFalse(self.engine.close())
        process.poll.return_value = 0
        self.assertTrue(self.engine.close())
        self.assertIsNone(self.engine._process)
        self.assertIsNone(self.engine._folder)

    def test_close_does_not_claim_success_while_thread_is_alive(self):
        worker = Mock()
        worker.is_alive.return_value = True
        self.engine._thread = worker
        self.assertFalse(self.engine.close())
        self.assertEqual(self.engine.read()["storage_status"]["state"], "closing")
        worker.is_alive.return_value = False
        self.assertTrue(self.engine.close())


if __name__ == "__main__":
    unittest.main()
