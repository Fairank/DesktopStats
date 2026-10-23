"""Synthetic history recovery boundaries; no hardware, preferences, or Qt."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from history_store import HistoryStore

BASE = 1_700_000_040


def sql_error(code):
    error = sqlite3.OperationalError("synthetic private database detail must not be displayed")
    error.sqlite_errorcode = code
    return error


class FaultyReader:
    def __init__(self, connection, *, read_error=None, fetch_error=None, rollback_error=None, close_failures=0):
        self.connection = connection
        self.read_error = read_error
        self.fetch_error = fetch_error
        self.rollback_error = rollback_error
        self.close_failures = close_failures
        self.close_calls = 0

    def execute(self, sql, *parameters):
        if sql.startswith("SELECT") and self.read_error is not None:
            raise self.read_error
        cursor = self.connection.execute(sql, *parameters)
        if sql.startswith("SELECT") and self.fetch_error is not None:
            error = self.fetch_error

            class FailedCursor:
                def fetchall(inner):
                    raise error

            return FailedCursor()
        return cursor

    def rollback(self):
        if self.rollback_error is not None:
            raise self.rollback_error
        return self.connection.rollback()

    def close(self):
        self.close_calls += 1
        if self.close_calls <= self.close_failures:
            raise sql_error(sqlite3.SQLITE_IOERR)
        return self.connection.close()


class HistoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="history-recovery-")
        self.path = Path(self.directory.name) / "history.sqlite3"
        self.now = 0.0
        self.wall = float(BASE)
        self.stores = []
        self.store = self.make_store()

    def tearDown(self):
        for store in self.stores:
            store.close()
            store.close()  # Retry a synthetic one-off cleanup failure, if any.
        self.directory.cleanup()

    def make_store(self, **options):
        store = HistoryStore(self.path, clock=lambda: self.now,
                             wall_clock=lambda: self.wall, **options)
        self.stores.append(store)
        return store

    def test_existing_history_is_ready_after_reopening_without_a_new_sample(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.close()
        reopened = self.make_store()
        result = reopened.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(result["summary"]["count"], 1)
        self.assertEqual(result["summary"]["mean"], 20)
        self.assertEqual(result["status"]["state"], "ready",
                         "Paused recording must still report readable persisted history as ready")

    def test_read_ok_distinguishes_complete_empty_or_pending_history_from_a_failed_writer(self):
        empty = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertTrue(empty["read_ok"])
        self.assertEqual(empty["summary"]["count"], 0)
        self.assertEqual(empty["status"]["state"], "idle")
        with patch.object(self.store, "_connect", side_effect=OSError(28, "synthetic full disk")):
            self.store.record(dict(time=self.wall, cpu_usage=0))
        pending = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertTrue(pending["read_ok"])
        self.assertEqual(pending["summary"]["count"], 1)
        self.assertEqual(pending["summary"]["mean"], 0)
        self.assertEqual(pending["status"]["api"], "sqlite3.history.write")
        self.assertEqual(pending["status"]["state"], "unavailable")

    def test_successful_read_recovers_a_transient_read_error_without_a_new_write(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = self.store._read_connection

        class FailingOnceReader:
            failed = False

            def execute(inner, sql, *parameters):
                if sql.startswith("SELECT") and not inner.failed:
                    inner.failed = True
                    error = sqlite3.OperationalError("synthetic transient reader contention")
                    error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                    raise error
                return reader.execute(sql, *parameters)

            def rollback(inner):
                return reader.rollback()

            def close(inner):
                return reader.close()

        self.store._read_connection = FailingOnceReader()
        failed = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(failed["summary"]["count"], 0)
        self.assertFalse(failed["read_ok"])
        self.assertEqual(failed["status"]["api"], "sqlite3.history.read")
        self.assertEqual(failed["status"]["errorcode"], sqlite3.SQLITE_BUSY)
        recovered = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(recovered["summary"]["count"], 1)
        self.assertTrue(recovered["read_ok"])
        self.assertEqual(recovered["status"]["state"], "ready")
        self.assertEqual(recovered["status"]["error"], "")
        self.assertEqual(recovered["status"]["api"], "")
        self.assertEqual(self.store.status["write_transactions"], 1,
                         "A successful read must not manufacture a write just to recover its status")
        reader = self.store._read_connection
        self.store._read_connection = FailingOnceReader()
        failed_again = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(failed_again["status"]["state"], "unavailable")
        self.assertEqual(failed_again["status"]["failure_count"], 2)
        self.assertEqual(self.store.query("cpu_usage", end=self.wall + 1)
                         ["status"]["state"], "ready")

    def test_select_and_rollback_failure_preserve_the_original_error_and_rebuild_the_reader(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = FaultyReader(self.store._read_connection,
                             read_error=sql_error(sqlite3.SQLITE_BUSY),
                             rollback_error=sql_error(sqlite3.SQLITE_IOERR))
        self.store._read_connection = reader
        failed = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(failed["summary"]["count"], 0)
        self.assertFalse(failed["read_ok"])
        self.assertEqual(failed["status"]["api"], "sqlite3.history.read")
        self.assertEqual(failed["status"]["errorcode"], sqlite3.SQLITE_BUSY)
        self.assertNotIn("private", str(failed["status"]))
        self.assertEqual(reader.close_calls, 1)
        recovered = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(recovered["summary"]["count"], 1)
        self.assertTrue(recovered["read_ok"])
        self.assertEqual(recovered["status"]["state"], "ready")
        self.assertIsNot(self.store._read_connection, reader)

    def test_rollback_failure_after_fetch_returns_safe_error_and_rebuilds_reader(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = FaultyReader(self.store._read_connection,
                             rollback_error=sql_error(sqlite3.SQLITE_IOERR))
        self.store._read_connection = reader
        failed = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(failed["summary"]["count"], 0)
        self.assertFalse(failed["read_ok"])
        self.assertEqual(failed["status"]["errorcode"], sqlite3.SQLITE_IOERR)
        self.assertEqual(reader.close_calls, 1)
        recovered = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(recovered["summary"]["count"], 1)
        self.assertTrue(recovered["read_ok"])
        self.assertEqual(recovered["status"]["state"], "ready")

    def test_fetch_failure_does_not_reuse_partial_rows_and_rebuilds_reader(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = FaultyReader(self.store._read_connection,
                             fetch_error=sql_error(sqlite3.SQLITE_IOERR))
        self.store._read_connection = reader
        failed = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertFalse(failed["read_ok"])
        self.assertEqual(failed["summary"]["count"], 0)
        self.assertEqual(failed["status"]["errorcode"], sqlite3.SQLITE_IOERR)
        self.assertEqual(reader.close_calls, 1)
        recovered = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertTrue(recovered["read_ok"])
        self.assertEqual(recovered["summary"]["count"], 1)

    def test_reader_cleanup_retries_keep_one_reference_and_do_not_open_more_connections(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = FaultyReader(self.store._read_connection,
                             read_error=sql_error(sqlite3.SQLITE_BUSY), close_failures=3)
        self.store._read_connection = reader
        connect = sqlite3.connect
        with patch("history_store.sqlite3.connect", wraps=connect) as reopened:
            for attempts in range(1, 4):
                failed = self.store.query("cpu_usage", end=self.wall + 1)
                self.assertFalse(failed["read_ok"])
                self.assertIs(self.store._read_connection, reader)
                self.assertEqual(reader.close_calls, attempts)
                self.assertEqual(reopened.call_count, 0)
            recovered = self.store.query("cpu_usage", end=self.wall + 1)
            self.assertTrue(recovered["read_ok"])
            self.assertEqual(recovered["summary"]["count"], 1)
            self.assertEqual(reopened.call_count, 1)
            self.assertEqual(reader.close_calls, 4)

    def test_failed_reader_close_retains_one_reference_until_retry_succeeds(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        reader = FaultyReader(self.store._read_connection,
                             read_error=sql_error(sqlite3.SQLITE_BUSY),
                             rollback_error=sql_error(sqlite3.SQLITE_IOERR), close_failures=1)
        self.store._read_connection = reader
        failed = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(failed["status"]["errorcode"], sqlite3.SQLITE_BUSY)
        self.assertFalse(failed["read_ok"])
        self.assertIs(self.store._read_connection, reader)
        self.assertEqual(reader.close_calls, 1)
        recovered = self.store.query("cpu_usage", end=self.wall + 1)
        self.assertEqual(reader.close_calls, 2)
        self.assertIsNot(self.store._read_connection, reader)
        self.assertEqual(recovered["summary"]["count"], 1)
        self.assertTrue(recovered["read_ok"])
        self.assertEqual(recovered["status"]["state"], "ready")

    def test_successful_read_does_not_hide_a_failed_write_or_user_clear(self):
        for operation in ("write", "clear"):
            with self.subTest(operation=operation):
                store = self.make_store()
                store.record(dict(time=self.wall, cpu_usage=20))
                store.query("cpu_usage", end=self.wall + 1)
                error = PermissionError(13, "synthetic private path must not be displayed")
                with patch.object(store, "_connect", side_effect=error):
                    if operation == "clear":
                        self.assertFalse(store.clear())
                    else:
                        self.now += 1
                        self.wall += 1
                        store.record(dict(time=self.wall, cpu_usage=30))
                # A read failure occurs after the write/clear fault, so the
                # current display fault alone cannot preserve the older one.
                reader = store._read_connection

                class FailingOnceReader:
                    failed = False

                    def execute(inner, sql, *parameters):
                        if sql.startswith("SELECT") and not inner.failed:
                            inner.failed = True
                            raise sqlite3.OperationalError("synthetic reader contention")
                        return reader.execute(sql, *parameters)

                    def rollback(inner):
                        return reader.rollback()

                    def close(inner):
                        return reader.close()

                store._read_connection = FailingOnceReader()
                self.assertEqual(store.query("cpu_usage", end=self.wall + 1)
                                 ["status"]["api"], "sqlite3.history.read")
                recovered = store.query("cpu_usage", end=self.wall + 1)
                self.assertGreater(recovered["summary"]["count"], 0)
                self.assertTrue(recovered["read_ok"],
                                "Existing readable history survives an independent write/clear error")
                self.assertEqual(recovered["status"]["state"], "unavailable")
                self.assertEqual(recovered["status"]["api"], f"sqlite3.history.{operation}")
                self.assertEqual(recovered["status"]["errorcode"], 13)
                self.assertNotIn("private", str(recovered["status"]))
                if operation == "clear":
                    self.assertTrue(store.clear())
                else:
                    self.now += 5
                    self.wall += 5
                    self.assertTrue(store.flush())
                self.assertEqual(store.status["state"], "ready")
                store.close()

    def test_fresh_provider_reading_after_wall_clock_rollback_is_not_a_duplicate(self):
        self.store.record(dict(time=self.wall, cpu_fan_rpm=1000,
                               metric_timestamps={"cpu_fan_rpm": self.wall}))
        # The cooling provider deliberately invalidates its cache on a wall
        # clock jump, then returns a fresh value at the new wall time. The
        # monotonic clock continues forward, as on a system time correction.
        self.now = 1.0
        self.wall -= 120
        self.store.record(dict(time=self.wall, cpu_fan_rpm=2000,
                               metric_timestamps={"cpu_fan_rpm": self.wall}))
        result = self.store.query("cpu_fan_rpm", end=self.wall + 1)
        self.assertEqual(result["summary"]["count"], 1)
        self.assertEqual(result["summary"]["latest"], 2000)
        self.assertEqual(result["summary"]["latest_time"], self.wall)
        # Re-delivery of this new cached observation is still only one sample.
        self.now += .1
        self.wall += .1
        self.store.record(dict(time=self.wall, cpu_fan_rpm=2000,
                               metric_timestamps={"cpu_fan_rpm": self.wall - .1}))
        self.assertEqual(self.store.query("cpu_fan_rpm", end=self.wall + 1)
                         ["summary"]["count"], 1)

    def test_committed_clear_can_recover_a_write_failure_without_claiming_a_failed_read_is_healthy(self):
        self.store.record(dict(time=self.wall, cpu_usage=20))
        self.store.query("cpu_usage", end=self.wall + 1)
        self.now = 1
        self.wall += 1
        with patch.object(self.store, "_connect", side_effect=OSError(28, "synthetic disk full")):
            self.store.record(dict(time=self.wall, cpu_usage=30))
        self.assertEqual(self.store.status["api"], "sqlite3.history.write")
        self.assertTrue(self.store.clear())
        self.assertEqual(self.store.status["state"], "ready")
        self.assertEqual(self.store.query("cpu_usage", end=self.wall + 1)["summary"]["count"], 0)
        reader = self.store._read_connection

        class FailedReader:
            def execute(inner, sql, *parameters):
                if sql.startswith("SELECT"):
                    raise sqlite3.OperationalError("synthetic reader failure")
                return reader.execute(sql, *parameters)

            def rollback(inner):
                return reader.rollback()

            def close(inner):
                return reader.close()

        self.store._read_connection = FailedReader()
        self.store.query("cpu_usage", end=self.wall + 1)
        # A successful clear is a writer proof, not evidence that a failed
        # independent reader connection recovered.
        self.assertTrue(self.store.clear())
        self.assertEqual(self.store.status["api"], "sqlite3.history.read")

    def test_late_samples_and_minor_clock_jitter_do_not_reset_source_deduplication(self):
        self.now = 4
        self.wall = BASE + 4
        self.store.record(dict(time=self.wall, cpu_fan_rpm=2000,
                               metric_timestamps={"cpu_fan_rpm": self.wall}))
        self.now = 5
        self.wall = BASE + 5
        # The source/sample timestamp is old, but the real clocks advanced.
        self.store.record(dict(time=BASE + 1, cpu_fan_rpm=1000,
                               metric_timestamps={"cpu_fan_rpm": BASE + 1}))
        self.store.record(dict(time=self.wall, cpu_fan_rpm=2000,
                               metric_timestamps={"cpu_fan_rpm": BASE + 4}))
        self.now += .1
        self.wall -= .1
        self.store.record(dict(time=self.wall, cpu_fan_rpm=2000,
                               metric_timestamps={"cpu_fan_rpm": BASE + 4}))
        result = self.store.query("cpu_fan_rpm", end=BASE + 6)
        self.assertEqual(result["summary"]["count"], 1)
        self.assertEqual(result["summary"]["latest"], 2000)

    def test_clock_epoch_keeps_future_source_filter_and_normal_transaction_rate(self):
        for index in range(200):
            self.now = index / 100
            self.wall = BASE + self.now - (120 if index >= 100 else 0)
            self.store.record(dict(time=self.wall, cpu_fan_rpm=index,
                                   metric_timestamps={"cpu_fan_rpm": self.wall}))
        self.assertEqual(self.store.status["write_transactions"], 2)
        # A cached value from the old clock epoch is now in the future; it is
        # invalid rather than an observation which may reset the new epoch.
        self.store.record(dict(time=self.wall, cpu_fan_rpm=9999,
                               metric_timestamps={"cpu_fan_rpm": BASE}))
        result = self.store.query("cpu_fan_rpm", end=self.wall + .01)
        self.assertEqual(result["summary"]["count"], 100)
        self.assertEqual(result["summary"]["peak"], 199)
        self.assertEqual(result["summary"]["missing_count"], 1)

    def test_clock_epochs_do_not_grow_device_deduplication_or_outage_buffer_without_bound(self):
        store = self.make_store(max_pending=32)
        with patch.object(store, "_connect", side_effect=OSError(28, "synthetic full disk")):
            for group in range(140):
                devices = {f"synthetic-{group * 32 + index}": {
                    "net_download": index,
                    "metric_timestamps": {"net_download": self.wall}}
                    for index in range(32)}
                store.record(dict(time=self.wall, networks=devices))
            self.assertLessEqual(len(store._source_times), 4096)
            self.assertLessEqual(store.status["pending_buckets"], 32)
            self.assertGreater(store.status["dropped_buckets"], 0)
            self.now += 1
            self.wall -= 120
            store.record(dict(time=self.wall, networks={"after-reset": {
                "net_download": 0, "metric_timestamps": {"net_download": self.wall}}}))
            self.assertEqual(len(store._source_times), 1)
            self.assertLessEqual(store.status["pending_buckets"], 32)

    def test_read_errors_do_not_indefinitely_postpone_healthy_writer_transactions(self):
        self.store.record(dict(time=self.wall, cpu_usage=0))
        self.store.query("cpu_usage", end=self.wall + 1)
        self.store._read_connection = FaultyReader(self.store._read_connection,
                                                   read_error=sql_error(sqlite3.SQLITE_BUSY))
        connect = sqlite3.connect

        def failed_reader(*arguments, **options):
            return FaultyReader(connect(*arguments, **options), read_error=sql_error(sqlite3.SQLITE_BUSY))

        # The UI queries every two seconds while the healthy worker continues
        # delivering data. A read error must not move the writer's retry gate.
        with patch("history_store.sqlite3.connect", side_effect=failed_reader):
            for second in range(1, 13):
                self.now = float(second)
                self.wall = BASE + second
                if second % 2:
                    self.store.query("cpu_usage", end=self.wall + 1)
                self.store.record(dict(time=self.wall, cpu_usage=second))
        self.assertEqual(self.store.status["failure_count"], 6)
        with closing(sqlite3.connect(self.path)) as database:
            persisted = database.execute(
                "SELECT sum(count) FROM sensor_history WHERE resolution=1 AND metric='cpu_usage'"
            ).fetchone()[0]
        self.assertEqual(persisted, 13,
                         "Repeated reader failures must not leave healthy new samples only in memory")

    def test_requerying_the_same_observations_keeps_epoch_bucket_timestamps_and_statistics(self):
        for offset, value in ((1, 10), (2, 20), (4, 40), (7, 70)):
            self.now = float(offset)
            self.wall = BASE + offset
            self.store.record(dict(time=self.wall, cpu_usage=value))
        self.wall = BASE + 11
        first = self.store.query("cpu_usage", end=BASE + 10, points=240)
        second = self.store.query("cpu_usage", end=BASE + 11, points=240)
        def observed(result):
            return {point["time"]: point for point in result["points"] if not point["gap"]}

        self.assertEqual(first["resolution"], 3)
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(observed(first), observed(second),
                         "An unchanged recorded sample must not change bucket identity or mean on every UI refresh")
        self.assertEqual(first["summary"]["count"], 4)
        self.assertEqual(first["summary"]["mean"], 35)
        self.assertEqual(first["summary"]["peak"], 70)

    def test_epoch_grid_keeps_the_real_window_point_budget_and_clipped_edge_bins(self):
        for period, duration in (("10m", 600), ("1h", 3600), ("24h", 86400)):
            for budget in (1, 2, 3, 10, 200, 240, 600, 720):
                steps = set()
                for shift in (0, .1, 1, 2, 59, 60, 61):
                    with self.subTest(period=period, budget=budget, shift=shift):
                        result = self.store.query("cpu_usage", period, end=BASE + shift, points=budget)
                        self.assertEqual(result["end"] - result["start"], duration)
                        self.assertGreater(len(result["points"]), 0)
                        self.assertLessEqual(len(result["points"]), budget)
                        self.assertEqual(result["points"][0]["time"], result["start"])
                        self.assertEqual(result["points"][-1]["end"], result["end"])
                        self.assertTrue(all(result["start"] <= point["time"] < point["end"] <= result["end"]
                                            for point in result["points"]))
                        self.assertTrue(all(a["end"] == b["time"] for a, b in zip(
                            result["points"], result["points"][1:])))
                        self.assertTrue(all(point["gap"] for point in result["points"]))
                        if budget > 1:
                            self.assertTrue(all(point["time"] % result["resolution"] == 0
                                                for point in result["points"][1:]))
                        steps.add(result["resolution"])
                self.assertEqual(len(steps), 1, "Resolution cannot change as the same window advances")

    def test_partial_edges_do_not_mix_outside_observations_and_keep_zero_gaps_extrema(self):
        until = BASE + 10
        start = until - 600
        self.wall = float(until + 1)
        for timestamp, value in ((start - 1, 999), (start, 0), (start + 1, 10),
                                 (start + 3, None), (until - 1, 100), (until, 999)):
            self.store.record(dict(time=timestamp, cpu_usage=value))
        for points in (1, 2, 200, 240, 600):
            result = self.store.query("cpu_usage", end=until, points=points)
            self.assertEqual(result["summary"]["count"], 3)
            self.assertEqual(result["summary"]["missing_count"], 1)
            self.assertEqual(result["summary"]["minimum"], 0)
            self.assertEqual(result["summary"]["peak"], 100)
            self.assertEqual(result["summary"]["latest"], 100)
            self.assertEqual(result["summary"]["latest_time"], until - 1)
            self.assertAlmostEqual(result["summary"]["mean"], 110 / 3)
            self.assertEqual(sum(point["count"] for point in result["points"]), 3)
            self.assertEqual(sum(point["missing_count"] for point in result["points"]), 1)
            self.assertEqual(result["points"][0]["minimum"], 0)
            self.assertEqual(result["points"][-1]["peak"], 100)
            if points > 2:
                self.assertTrue(any(point["gap"] for point in result["points"]))


if __name__ == "__main__":
    unittest.main()
