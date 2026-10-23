"""Local-only history regressions; synthetic dictionaries, no hardware or Qt."""

import math
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import history_store as history

BASE = 1_700_000_040  # Aligned to a real UTC minute, independent of test execution time.


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="synthetic-history-")
        self.path = Path(self.directory.name) / "history.sqlite3"
        self.now = 0.0
        self.wall = float(BASE)
        self.stores = []
        self.store = self.make_store()

    def tearDown(self):
        for store in self.stores:
            store.close()
        self.directory.cleanup()

    def make_store(self, **options):
        store = history.HistoryStore(self.path, clock=lambda: self.now,
                                     wall_clock=lambda: self.wall, **options)
        self.stores.append(store)
        return store

    def sample(self, offset=0, **values):
        self.wall = BASE + offset
        self.now = float(offset)
        return dict(time=self.wall, **values)

    def query(self, metric="cpu_usage", *, end=None, **options):
        return self.store.query(metric, end=self.wall + 1 if end is None else end, **options)

    def test_lazy_creation_and_empty_history_has_real_time_gaps(self):
        self.assertFalse(self.path.exists())
        result = self.query(points=600)
        self.assertEqual(result["end"] - result["start"], 600)
        self.assertEqual(len(result["points"]), 600)
        self.assertTrue(all(point["gap"] and point["mean"] is None for point in result["points"]))
        self.assertEqual(result["summary"]["count"], 0)
        self.assertFalse(self.path.exists(), "An empty query must not create a database")

    def test_one_hundred_hz_records_use_at_most_one_normal_transaction_per_second(self):
        for index in range(250):
            self.assertTrue(self.store.record(self.sample(index / 100, cpu_usage=index % 100)))
        self.assertEqual(self.store.status["write_transactions"], 3)
        result = self.query()
        self.assertEqual(result["summary"]["count"], 250)
        self.assertEqual(result["summary"]["peak"], 99)
        self.assertAlmostEqual(result["summary"]["mean"], sum(i % 100 for i in range(250)) / 250)
        for _ in range(20):
            self.assertFalse(self.store.flush())
        self.assertEqual(self.store.status["write_transactions"], 3)

    def test_minute_rollups_preserve_weighted_mean_extrema_and_actual_zero(self):
        for index in range(100):
            self.store.record(self.sample(index / 100, cpu_usage=0))
        self.store.record(self.sample(2, cpu_usage=90))
        for period in ("10m", "1h", "24h"):
            result = self.query(period=period, points=1)
            self.assertEqual(result["summary"]["count"], 101)
            self.assertAlmostEqual(result["summary"]["mean"], 90 / 101)
            self.assertEqual(result["summary"]["minimum"], 0)
            self.assertEqual(result["summary"]["peak"], 90)
            self.assertEqual(result["summary"]["latest"], 90)

    def test_missing_seconds_stay_gaps_without_interpolating_or_carrying_last_value(self):
        self.store.record(self.sample(0, cpu_usage=10))
        self.store.record(self.sample(2, cpu_usage=20))
        result = self.query(points=600, end=BASE + 3)
        self.assertEqual([point["mean"] for point in result["points"][-3:]], [10, None, 20])
        self.assertEqual([point["gap"] for point in result["points"][-3:]], [False, True, False])
        self.assertEqual([point["time"] for point in result["points"][-3:]],
                         [BASE, BASE + 1, BASE + 2])

    def test_none_nonfinite_and_booleans_are_missing_but_zero_and_negative_are_valid(self):
        for index, value in enumerate((None, math.nan, math.inf, True, 0, -2)):
            self.store.record(self.sample(index / 10, battery_watts=value))
        result = self.query("battery_watts")["summary"]
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["missing_count"], 4)
        self.assertEqual(result["mean"], -1)
        self.assertEqual((result["minimum"], result["peak"]), (-2, 0))

    def test_explicit_final_flush_preserves_subsecond_tail_and_close_rejects_records(self):
        self.store.record(self.sample(0, cpu_usage=1))
        self.store.record(self.sample(.1, cpu_usage=3))
        self.assertEqual(self.store.status["write_transactions"], 1)
        self.store.close()
        self.assertEqual(self.store.status["write_transactions"], 2)
        self.assertFalse(self.store.record(self.sample(.2, cpu_usage=99)))
        self.store.close()
        self.assertEqual(self.store.status["write_transactions"], 2)
        reopened = self.make_store()
        result = reopened.query("cpu_usage", end=BASE + 1)["summary"]
        self.assertEqual((result["count"], result["mean"]), (2, 2))

    def test_devices_are_independent_and_flat_active_network_never_crosses_series(self):
        self.store.record(self.sample(0, gpu_usage=99, net_download=99, gpus={
            "0": {"gpu_usage": 0}, "1": {"gpu_usage": 80}}, networks={
            "adapter-a": {"net_download": 1}, "adapter-b": {"net_download": 9}}))
        self.store.record(self.sample(1, net_download=7, networks={
            "adapter-a": {"net_download": 3}}))
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="0")["summary"]["mean"], 0)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="1")["summary"]["mean"], 80)
        result = self.query("net_download", scope="networks", device_id="adapter-a")
        self.assertEqual(result["summary"]["mean"], 2)
        other = self.query("net_download", scope="networks", device_id="adapter-b")
        self.assertEqual(other["summary"]["count"], 1)
        self.assertEqual(other["summary"]["mean"], 9)
        self.assertNotEqual(result["device"], other["device"])
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="removed")["summary"]["count"], 0)

    def test_units_scopes_and_device_identity_cannot_be_silently_changed(self):
        for arguments in (
            dict(metric="gpu_usage"), dict(metric="gpu_usage", scope="gpus"),
            dict(metric="cpu_temp", unit="°F"), dict(metric="net_download", scope="gpus", device_id="0"),
            dict(metric="cpu_usage", period="7d"), dict(metric="cpu_usage", points=0),
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.store.query(**arguments)

    def test_cached_provider_timestamps_are_not_counted_as_fresh_hundred_hz_samples(self):
        for index in range(100):
            self.store.record(self.sample(index / 100, cpu_temp=60,
                                          metric_timestamps={"cpu_temp": BASE}))
        result = self.query("cpu_temp")["summary"]
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["latest_time"], BASE)
        self.store.record(self.sample(1, cpu_temp=None, metric_timestamps={"cpu_temp": BASE}))
        result = self.query("cpu_temp")["summary"]
        self.assertEqual((result["count"], result["missing_count"]), (1, 1))
        self.store.record(self.sample(2, cpu_temp=70, metric_timestamps={"cpu_temp": BASE + 2}))
        self.assertEqual(self.query("cpu_temp")["summary"]["count"], 2)

    def test_sample_time_is_real_wall_time_and_invalid_future_timestamps_do_not_add_data(self):
        self.assertFalse(self.store.record({"time": BASE + 6, "cpu_usage": 99}))
        self.assertFalse(self.store.record({"time": BASE - history.RETENTION - 1, "cpu_usage": 99}))
        self.assertFalse(self.store.record({"time": True, "cpu_usage": 99}))
        self.store.record(self.sample(0, cpu_temp=99, metric_timestamps={"cpu_temp": BASE + 50}))
        self.assertEqual(self.query("cpu_temp")["summary"]["count"], 0)
        self.assertEqual(self.query("cpu_temp")["summary"]["missing_count"], 1)

    def test_default_whitelist_does_not_store_labels_files_network_addresses_or_raw_payloads(self):
        private = "Synthetic private account 10.0.0.8 C:/personal/secret.docx"
        self.store.record(self.sample(0, cpu_usage=5, cpu_name=private, process=private,
                                      path=private, address=private, networks={private: {
                                          "label": private, "address": private, "net_upload": 2}}))
        self.store.close()
        payload = b"".join(path.read_bytes() for path in self.path.parent.iterdir() if path.is_file())
        self.assertNotIn(private.encode(), payload)
        self.assertNotIn(b"10.0.0.8", payload)
        with closing(sqlite3.connect(self.path)) as database:
            devices = database.execute("SELECT DISTINCT device FROM sensor_history WHERE scope='networks'").fetchall()
            self.assertEqual(devices, [(history.device_key("networks", private),)])

    def test_optional_storage_is_recorded_only_when_explicitly_enabled(self):
        sample = self.sample(0, storages={"0": {"storage_temp": 42}})
        self.store.record(sample)
        self.assertEqual(self.query("storage_temp", scope="storages", device_id="0")["summary"]["count"], 0)
        self.store.close()
        enabled = self.make_store(scopes=("storages",))
        enabled.record(sample)
        self.assertEqual(enabled.query("storage_temp", scope="storages", device_id="0",
                                       end=BASE + 1)["summary"]["mean"], 42)

    def test_retention_keeps_minutes_for_seven_days_and_seconds_for_only_one_hour(self):
        self.store.record(self.sample(0, cpu_usage=20))
        self.store.close()
        self.now = 4000
        self.wall = BASE + 4000
        current = self.make_store()
        current.record(dict(time=self.wall, cpu_usage=40))
        with closing(sqlite3.connect(self.path)) as database:
            self.assertEqual(database.execute(
                "SELECT count(*) FROM sensor_history WHERE resolution=1 AND second=?", (BASE,)).fetchone()[0], 0)
            self.assertEqual(database.execute(
                "SELECT count(*) FROM sensor_history WHERE resolution=60 AND second=?", (BASE,)).fetchone()[0], 1)
        self.assertEqual(current.query("cpu_usage", period="24h", end=self.wall + 1)["summary"]["count"], 2)
        self.now += history.RETENTION + 61
        self.wall += history.RETENTION + 61
        current.record(dict(time=self.wall, cpu_usage=60))
        with closing(sqlite3.connect(self.path)) as database:
            self.assertEqual(database.execute(
                "SELECT count(*) FROM sensor_history WHERE second<?", (BASE + 4000,)).fetchone()[0], 0)

    def test_write_failures_are_bounded_safe_and_recover_without_losing_valid_readings(self):
        error = PermissionError(13, "Synthetic private filename must not be exposed", "/private/file")
        with patch.object(self.store, "_connect", side_effect=error) as connect:
            for index in range(1000):
                self.store.record(self.sample(index / 100, cpu_usage=1))
            self.assertEqual(connect.call_count, 2, "100 Hz failure must not retry 100 times a second")
        status = self.store.status
        self.assertEqual(status["state"], "unavailable")
        self.assertEqual(status["errorcode"], 13)
        self.assertNotIn("private", str(status))
        self.assertEqual(self.query()["summary"]["count"], 1000)
        self.now = 10
        self.assertTrue(self.store.flush())
        self.assertEqual(self.store.status["state"], "ready")
        self.assertEqual(self.store.status["error"], "")
        self.assertEqual(self.query()["summary"]["count"], 1000)

    def test_real_sqlite_writer_lock_is_reported_then_recovers_without_duplicate_counts(self):
        self.store.record(self.sample(0, cpu_usage=1))
        other = sqlite3.connect(self.path, timeout=.02)
        other.execute("BEGIN IMMEDIATE")
        try:
            self.store.record(self.sample(.1, cpu_usage=3))
            self.now = 1
            self.assertFalse(self.store.flush())
            self.assertEqual(self.store.status["errorcode"], sqlite3.SQLITE_BUSY)
            self.assertEqual(self.store.status["api"], "sqlite3.history.write")
            self.assertEqual(self.query()["summary"]["count"], 2)
        finally:
            other.rollback()
            other.close()
        self.now = 6
        self.assertTrue(self.store.flush())
        self.assertEqual(self.query()["summary"]["mean"], 2)
        self.assertEqual(self.query()["summary"]["count"], 2)

    def test_database_error_does_not_destroy_existing_file_or_expose_contents(self):
        content = b"Synthetic private content is not a SQLite database"
        self.path.write_bytes(content)
        self.assertTrue(self.store.record(self.sample(0, cpu_usage=10)))
        self.assertEqual(self.path.read_bytes(), content)
        self.assertEqual(self.store.status["state"], "unavailable")
        result = self.query()
        self.assertEqual(result["summary"]["mean"], 10)
        self.assertNotIn("Synthetic", str(result["status"]))

    def test_outage_buffer_is_bounded_and_reports_evictions(self):
        small = self.make_store(max_pending=32)
        with patch.object(small, "_connect", side_effect=OSError(28, "synthetic storage full")):
            for second in range(200):
                self.wall = BASE + second
                self.now = second
                small.record(dict(time=self.wall, cpu_usage=second))
        self.assertLessEqual(small.status["pending_buckets"], 32)
        self.assertGreater(small.status["dropped_buckets"], 0)

    def test_each_sample_has_a_bounded_device_budget(self):
        devices = {str(index): {"gpu_usage": index} for index in range(1000)}
        self.store.record(self.sample(0, gpus=devices))
        with closing(sqlite3.connect(self.path)) as database:
            self.assertEqual(database.execute(
                "SELECT count(DISTINCT device) FROM sensor_history WHERE scope='gpus'"
            ).fetchone()[0], history.MAX_DEVICES_PER_SAMPLE)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="999")["summary"]["count"], 0)

    def test_clear_removes_persisted_and_pending_data_but_new_samples_keep_device_isolation(self):
        self.store.record(self.sample(0, cpu_temp=50, metric_timestamps={"cpu_temp": BASE},
                                      gpus={"0": {"gpu_usage": 10}, "1": {"gpu_usage": 20}}))
        self.store.record(self.sample(.1, cpu_usage=5))
        self.assertGreater(self.store.status["pending_buckets"], 0)
        self.assertTrue(self.store.clear())
        self.assertEqual(self.store.status["pending_buckets"], 0)
        self.assertEqual(self.query("cpu_temp")["summary"]["count"], 0)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="0")["summary"]["count"], 0)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="1")["summary"]["count"], 0)
        # Clearing resets cached source de-duplication, too: the still-current
        # sensor reading may start the new history without waiting for a change.
        self.store.record(self.sample(.2, cpu_temp=60, metric_timestamps={"cpu_temp": BASE},
                                      gpus={"1": {"gpu_usage": 80}}))
        self.assertEqual(self.query("cpu_temp")["summary"]["mean"], 60)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="1")["summary"]["mean"], 80)
        self.assertEqual(self.query("gpu_usage", scope="gpus", device_id="0")["summary"]["count"], 0)

    def test_failed_clear_retains_both_database_and_pending_batch_and_can_be_retried(self):
        self.store.record(self.sample(0, cpu_usage=10))
        self.store.record(self.sample(.1, cpu_usage=20))
        pending = self.store.status["pending_buckets"]
        with patch.object(self.store, "_connect", side_effect=PermissionError(13, "private filename")):
            self.assertFalse(self.store.clear())
        self.assertEqual(self.store.status["pending_buckets"], pending)
        self.assertEqual(self.store.status["api"], "sqlite3.history.clear")
        self.assertEqual(self.query()["summary"]["count"], 2)
        self.assertTrue(self.store.clear(), "Explicit retry must not be blocked by the normal cadence")
        self.assertEqual(self.query()["summary"]["count"], 0)
        self.store.close()
        self.assertFalse(self.store.clear())

    def test_sqlite_clear_transaction_failure_rolls_back_without_discarding_pending(self):
        self.store.record(self.sample(0, cpu_usage=10))
        self.store.record(self.sample(.1, cpu_usage=20))
        pending = self.store.status["pending_buckets"]
        with closing(sqlite3.connect(self.path)) as database:
            database.execute("CREATE TRIGGER synthetic_clear_failure BEFORE DELETE ON sensor_history "
                             "BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
            database.commit()
        self.assertFalse(self.store.clear())
        self.assertEqual(self.store.status["pending_buckets"], pending)
        self.assertEqual(self.query()["summary"]["count"], 2)
        with closing(sqlite3.connect(self.path)) as database:
            self.assertEqual(database.execute(
                "SELECT count FROM sensor_history WHERE resolution=1").fetchone()[0], 1)
            database.execute("DROP TRIGGER synthetic_clear_failure")
            database.commit()
        self.assertTrue(self.store.clear())
        self.assertEqual(self.query()["summary"]["count"], 0)

    def test_concurrent_query_snapshot_does_not_block_writer_or_double_count_pending_tail(self):
        self.store.record(self.sample(0, cpu_usage=1))
        self.store.record(self.sample(.1, cpu_usage=3))
        self.query()  # Open the independent read connection before instrumenting it.
        reader = self.store._read_connection
        reading, release = threading.Event(), threading.Event()

        class WaitingCursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def fetchall(inner):
                reading.set()
                if not release.wait(3):
                    raise AssertionError("Synthetic writer did not finish")
                return inner.cursor.fetchall()

        class WaitingReader:
            def execute(inner, sql, *arguments):
                cursor = reader.execute(sql, *arguments)
                return WaitingCursor(cursor) if sql.startswith("SELECT") else cursor

            def rollback(inner):
                return reader.rollback()

            def close(inner):
                return reader.close()

        self.store._read_connection = WaitingReader()
        results, errors = [], []

        def query():
            try:
                results.append(self.query())
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=query)
        thread.start()
        try:
            self.assertTrue(reading.wait(3))
            self.now = 1
            self.assertTrue(self.store.flush(), "A slow history reader must not hold the worker lock")
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(results[0]["summary"]["count"], 2)
        self.assertEqual(self.query()["summary"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
