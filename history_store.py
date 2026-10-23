"""Local, bounded sensor history; no hardware, UI or preference access.

``record`` accepts the sampler's canonical values, never formatted display units.
Call it on the sampling worker: at most one SQLite transaction per monotonic
second is attempted, regardless of the sampling rate. A short in-memory tail is
included in queries. Seconds are retained for one hour and minute rollups for
seven days; rollups retain raw observation counts, sums and extrema.
"""

import hashlib
import math
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from metrics import METRICS, numeric

PERIODS = {"10m": 600, "1h": 3600, "24h": 86400}
RETENTION = 7 * 86400
SECOND_RETENTION = 3600
DEFAULT_METRICS = (
    "cpu_usage", "cpu_temp", "cpu_power", "cpu_frequency", "ram_percent",
    "ram_used_gb", "battery_percent", "battery_watts", "battery_charge_watts",
    "battery_discharge_watts", "cpu_fan_rpm", "gpu_fan_rpm", "system_fan_rpm",
    "adapter_input_watts", "system_power",
)
DEFAULT_SCOPES = ("gpus", "networks")
SCOPES = ("gpus", "networks", "disks", "volumes", "storages")
MAX_DEVICES_PER_SAMPLE = 32
_COLUMNS = "resolution,second,metric,scope,device,unit,total,count,low,peak,missing,last,last_at"
_CREATE = """CREATE TABLE IF NOT EXISTS sensor_history (
    resolution INTEGER NOT NULL, second INTEGER NOT NULL, metric TEXT NOT NULL,
    scope TEXT NOT NULL, device TEXT NOT NULL, unit TEXT NOT NULL,
    total REAL NOT NULL, count INTEGER NOT NULL, low REAL, peak REAL,
    missing INTEGER NOT NULL, last REAL, last_at REAL,
    PRIMARY KEY (resolution,metric,scope,device,unit,second)
) WITHOUT ROWID"""
_UPSERT = f"""INSERT INTO sensor_history ({_COLUMNS}) VALUES ({','.join('?' * 13)})
ON CONFLICT (resolution,metric,scope,device,unit,second) DO UPDATE SET
 total=total+excluded.total, count=count+excluded.count,
 low=CASE WHEN low IS NULL THEN excluded.low WHEN excluded.low IS NULL THEN low
          ELSE min(low,excluded.low) END,
 peak=CASE WHEN peak IS NULL THEN excluded.peak WHEN excluded.peak IS NULL THEN peak
           ELSE max(peak,excluded.peak) END,
 missing=missing+excluded.missing,
 last=CASE WHEN excluded.last_at >= coalesce(last_at,-1) THEN excluded.last ELSE last END,
 last_at=CASE WHEN excluded.last_at IS NULL THEN last_at WHEN last_at IS NULL THEN excluded.last_at
              ELSE max(last_at,excluded.last_at) END"""


def device_key(scope, identifier):
    """Opaque stable identity; labels, adapter names and addresses never reach disk."""
    if scope not in SCOPES or type(identifier) not in (str, int):
        raise ValueError("History requires an explicit supported device identity")
    value = str(identifier)
    if not value or len(value) > 4096:
        raise ValueError("Invalid history device identity")
    return hashlib.sha256((scope + "\0" + value).encode("utf-8")).hexdigest()


@dataclass
class _Bucket:
    total: float = 0.0
    count: int = 0
    low: float | None = None
    peak: float | None = None
    missing: int = 0
    last: float | None = None
    last_at: float | None = None

    def add(self, value, timestamp):
        if not numeric(value):
            self.missing += 1
            return
        self.total += value
        self.count += 1
        self.low = value if self.low is None else min(self.low, value)
        self.peak = value if self.peak is None else max(self.peak, value)
        if self.last_at is None or timestamp >= self.last_at:
            self.last, self.last_at = value, timestamp

    def merge(self, other):
        self.total += other.total
        self.count += other.count
        self.missing += other.missing
        if other.low is not None:
            self.low = other.low if self.low is None else min(self.low, other.low)
        if other.peak is not None:
            self.peak = other.peak if self.peak is None else max(self.peak, other.peak)
        if other.last_at is not None and (self.last_at is None or other.last_at >= self.last_at):
            self.last, self.last_at = other.last, other.last_at

    def values(self):
        return (self.total, self.count, self.low, self.peak, self.missing, self.last, self.last_at)

    def result(self):
        return dict(mean=self.total / self.count if self.count else None,
                    peak=self.peak, minimum=self.low, count=self.count,
                    missing_count=self.missing, latest=self.last, latest_time=self.last_at)


class HistoryStore:
    """One local database, lazily opened, safe for a worker and query thread.

    Expected filesystem/SQLite failures return an unavailable status and retain a
    bounded pending batch for retry. No exception messages or reading labels are
    persisted. Programming errors remain visible to the caller.
    """

    def __init__(self, path, *, metrics=DEFAULT_METRICS, scopes=DEFAULT_SCOPES,
                 clock=time.monotonic, wall_clock=time.time, max_pending=8192):
        self.path = Path(path)
        if str(self.path).startswith(("\\\\", "//")):
            raise ValueError("History must use a local file")
        if not 32 <= max_pending <= 65536:
            raise ValueError("Invalid history buffer size")
        self.metrics = tuple(dict.fromkeys(metrics))
        self.scopes = tuple(dict.fromkeys(scopes))
        if any(key not in METRICS or METRICS[key].get("scope") or key.startswith("external_")
               for key in self.metrics) or any(scope not in SCOPES for scope in self.scopes):
            raise ValueError("Unsupported history selection")
        self._scoped = {scope: tuple(key for key, meta in METRICS.items()
                                    if meta.get("scope") == scope) for scope in self.scopes}
        self._clock, self._wall = clock, wall_clock
        self._lock = threading.RLock()
        self._pending = OrderedDict()
        self._source_times = OrderedDict()
        self._source_clock = None
        self._max_pending = max_pending
        self._connection = None
        self._read_connection = None
        self._read_discard_pending = False
        self._query_lock = threading.Lock()
        self._schema_ready = False
        self._next_write = float("-inf")
        self._last_cleanup = float("-inf")
        self._closed = False
        self._failures = OrderedDict()
        self._ready_detail = "Local history is up to date"
        self._status = dict(state="idle", detail="History has not been written yet",
                            error="", api="", errorcode=None, write_transactions=0,
                            failure_count=0, dropped_buckets=0)

    @property
    def status(self):
        with self._lock:
            return dict(self._status, pending_buckets=len(self._pending), closed=self._closed)

    def _connect(self):
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=.02, check_same_thread=False)
            try:
                connection.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                connection.close()
                raise
            self._connection = connection
        return self._connection

    def _failure(self, error, api):
        code = next((value for name in ("sqlite_errorcode", "winerror", "errno")
                     if type(value := getattr(error, name, None)) is int), None)
        self._failures[api] = dict(error=type(error).__name__, api=api, errorcode=code)
        self._failures.move_to_end(api)
        self._status["failure_count"] += 1
        self._refresh_status()
        # The reader owns a separate connection. Its failures must not keep
        # extending the retry gate of a healthy sampling-worker connection.
        if api != "sqlite3.history.read":
            self._next_write = max(self._next_write, self._clock() + 5)

    def _refresh_status(self):
        if self._failures:
            self._status.update(state="unavailable", detail="Local history storage is unavailable",
                                **next(reversed(self._failures.values())))
        else:
            self._status.update(state="ready", detail=self._ready_detail,
                                error="", api="", errorcode=None)

    def _recover(self, api, detail=None):
        self._failures.pop(api, None)
        if detail is not None:
            self._ready_detail = detail
        self._refresh_status()

    def _observe_clock(self, wall):
        now = self._clock()
        previous = self._source_clock
        self._source_clock = now, wall
        if previous is not None:
            elapsed = now - previous[0]
            if elapsed < 0 or wall - previous[1] < elapsed - 2:
                # Provider timestamps are UTC wall times. A system clock
                # correction starts a new de-duplication epoch; an ordinary
                # delayed sample does not, because the clock itself advanced.
                self._source_times.clear()

    def _close_reader(self):
        connection = self._read_connection
        if connection is not None:
            connection.close()
        self._read_connection = None
        self._read_discard_pending = False

    def _finish_read(self, error=None):
        """End one snapshot; a damaged reader must be closed before reuse."""
        connection = self._read_connection
        if connection is not None:
            try:
                connection.rollback()
            except (OSError, sqlite3.Error) as cleanup_error:
                if error is None:
                    error = cleanup_error
        if error is not None:
            self._read_discard_pending = connection is not None
            try:
                self._close_reader()
            except (OSError, sqlite3.Error):
                # Retain exactly this reference for a later close retry. The
                # original read error takes precedence over cleanup failures.
                pass
            self._failure(error, "sqlite3.history.read")
            return False
        self._recover("sqlite3.history.read")
        return True

    def _add(self, metric, value, timestamp, scope="", identifier=""):
        unit = METRICS[metric]["unit"]
        token = device_key(scope, identifier) if scope else ""
        for resolution, retention in ((1, SECOND_RETENTION), (60, RETENTION)):
            if timestamp < self._wall() - retention:
                continue
            second = math.floor(timestamp / resolution) * resolution
            key = (resolution, second, metric, scope, token, unit)
            if key not in self._pending:
                self._pending[key] = _Bucket()
            self._pending[key].add(value, timestamp)
        while len(self._pending) > self._max_pending:
            self._pending.popitem(last=False)
            self._status["dropped_buckets"] += 1

    def _observe(self, metric, row, sample_time, scope="", identifier=""):
        if metric not in row:
            return
        timestamp = sample_time
        source_times = row.get("metric_timestamps")
        source_time = source_times.get(metric) if isinstance(source_times, dict) else None
        if numeric(source_time) and numeric(row.get(metric)):
            # A cached provider reading is one observation, at its source time.
            # Repeated 100 Hz deliveries cannot turn it into 100 fresh samples.
            if source_time > sample_time + 1 or source_time < self._wall() - RETENTION:
                self._add(metric, None, sample_time, scope, identifier)
                return
            identity = (metric, scope, str(identifier))
            if source_time <= self._source_times.get(identity, float("-inf")):
                return
            self._source_times[identity] = source_time
            self._source_times.move_to_end(identity)
            while len(self._source_times) > 4096:
                self._source_times.popitem(last=False)
            timestamp = source_time
        self._add(metric, row.get(metric), timestamp, scope, identifier)

    def record(self, sample):
        """Aggregate a canonical sampler dictionary; return False if not accepted.

        Missing scoped devices are never replaced by a flat/default-device value.
        Omitted or invalid readings remain gaps; actual zero readings are valid.
        """
        if not isinstance(sample, dict) or not numeric(sample.get("time")):
            return False
        timestamp = sample["time"]
        wall = self._wall()
        if timestamp < wall - RETENTION or timestamp > wall + 5:
            return False
        with self._lock:
            if self._closed:
                return False
            self._observe_clock(wall)
            for metric in self.metrics:
                self._observe(metric, sample, timestamp)
            for scope in self.scopes:
                devices = sample.get(scope)
                if not isinstance(devices, dict):
                    continue
                for index, (identifier, row) in enumerate(devices.items()):
                    if index >= MAX_DEVICES_PER_SAMPLE:
                        break
                    if not isinstance(row, dict) or type(identifier) not in (str, int):
                        continue
                    if not str(identifier) or len(str(identifier)) > 4096:
                        continue
                    for metric in self._scoped[scope]:
                        self._observe(metric, row, timestamp, scope, identifier)
            self.flush()
            return True

    def flush(self, *, _final=False):
        """Flush one bounded batch if due; retries and explicit calls share a gate."""
        with self._lock:
            now = self._clock()
            if self._closed or not self._pending or (not _final and now < self._next_write):
                return False
            self._next_write = now + 1
            wall = self._wall()
            for key in list(self._pending):
                retention = SECOND_RETENTION if key[0] == 1 else RETENTION
                if key[1] + key[0] <= wall - retention:
                    del self._pending[key]
            if not self._pending:
                return False
            try:
                connection = self._connect()
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if not self._schema_ready:
                        connection.execute(_CREATE)
                        connection.execute("CREATE INDEX IF NOT EXISTS sensor_history_expiry "
                                           "ON sensor_history(resolution,second)")
                    connection.executemany(_UPSERT, [key + bucket.values()
                                                    for key, bucket in self._pending.items()])
                    if now - self._last_cleanup >= 3600:
                        connection.execute("DELETE FROM sensor_history WHERE resolution=1 AND second<?",
                                           (math.floor(wall - SECOND_RETENTION),))
                        connection.execute("DELETE FROM sensor_history WHERE resolution=60 AND second<?",
                                           (math.floor((wall - RETENTION) / 60) * 60,))
                self._schema_ready = True
                self._last_cleanup = now if now - self._last_cleanup >= 3600 else self._last_cleanup
                self._pending.clear()
                self._status["write_transactions"] += 1
                self._recover("sqlite3.history.write", "Local history is up to date")
                return True
            except (OSError, sqlite3.Error) as error:
                self._failure(error, "sqlite3.history.write")
                return False

    def query(self, metric, period="10m", *, scope="", device_id="", unit=None,
              end=None, points=240):
        """Return a bounded, uniform UTC axis, gap buckets and exact raw statistics.

        ``end`` is exclusive, rounded up to the source resolution. Empty bins have
        ``mean=None`` and ``gap=True``; interpolation and last-value filling are
        deliberately absent. Values remain in their canonical registry unit.
        Multi-point aggregation uses a fixed UTC epoch grid for each period and
        point budget, with clipped partial edge bins. One edge-bin allowance can
        make the grid slightly coarser than dividing duration by the budget.
        A one-point query is the exact full-window aggregate.
        ``read_ok`` describes this query's completeness independently of the
        global status, which can retain a failed write or explicit clear.
        """
        if metric not in METRICS or metric.startswith("external_") or period not in PERIODS:
            raise ValueError("Unsupported history series or period")
        if type(points) is not int or not 1 <= points <= 720:
            raise ValueError("Invalid history point limit")
        expected_scope = METRICS[metric].get("scope") or ""
        if scope != expected_scope:
            raise ValueError("History device scope must be explicit")
        token = device_key(scope, device_id) if scope else ""
        canonical = METRICS[metric]["unit"]
        if unit is not None and unit != canonical:
            raise ValueError("History units cannot be mixed")
        resolution = 60 if period == "24h" else 1
        until = self._wall() if end is None else end
        if not numeric(until) or until < 0:
            raise ValueError("Invalid history end time")
        until = math.ceil(until / resolution) * resolution
        duration = PERIODS[period]
        start = until - duration
        if points >= duration // resolution:
            step = resolution
        else:
            step = math.ceil(duration / (max(1, points - 1) * resolution)) * resolution
        grid_start = start if points == 1 else math.floor(start / step) * step
        bins = [_Bucket() for _ in range(math.ceil((until - grid_start) / step))]
        summary = _Bucket()
        rows = []
        read_ok = True
        # Start the reader's WAL snapshot and copy the unwritten tail under the
        # same short lock. Fetch/aggregate outside it, so a long history query
        # cannot stall the sampling worker or count a just-flushed batch twice.
        with self._query_lock:
            cursor = None
            with self._lock:
                if self._closed:
                    raise RuntimeError("History store is closed")
                try:
                    if self._read_discard_pending:
                        self._close_reader()
                    if self.path.exists():
                        if self._read_connection is None:
                            self._read_connection = sqlite3.connect(
                                self.path, timeout=.02, check_same_thread=False)
                            self._read_connection.execute("PRAGMA query_only=ON")
                        self._read_connection.execute("BEGIN")
                        cursor = self._read_connection.execute(
                            "SELECT second,total,count,low,peak,missing,last,last_at FROM sensor_history "
                            "WHERE resolution=? AND metric=? AND scope=? AND device=? AND unit=? "
                            "AND second>=? AND second<? ORDER BY second",
                            (resolution, metric, scope, token, canonical,
                             max(start, self._wall() - (RETENTION if resolution == 60
                                                       else SECOND_RETENTION)), until))
                except (OSError, sqlite3.Error) as error:
                    read_ok = False
                    if self._read_discard_pending:
                        self._failure(error, "sqlite3.history.read")
                    else:
                        self._finish_read(error)
                    cursor = None
                tail = [(key[1], *bucket.values()) for key, bucket in self._pending.items()
                        if key[0] == resolution and key[2:] == (metric, scope, token, canonical)
                        and max(start, self._wall() - (RETENTION if resolution == 60
                                                      else SECOND_RETENTION)) <= key[1] < until]
            if cursor is not None:
                read_error = None
                try:
                    rows = cursor.fetchall()
                except (OSError, sqlite3.Error) as error:
                    read_error = error
                with self._lock:
                    read_ok = self._finish_read(read_error)
                    if not read_ok:
                        rows = []
            rows.extend(tail)
            state = self.status
        for row in rows:
            second, *values = row
            bucket = _Bucket(*values)
            bins[int((second - grid_start) // step)].merge(bucket)
            summary.merge(bucket)
        result = []
        for index, bucket in enumerate(bins):
            second = grid_start + index * step
            result.append(dict(time=max(start, second), end=min(second + step, until), gap=bucket.count == 0,
                               **bucket.result()))
        return dict(metric=metric, scope=scope, device=token, unit=canonical, period=period,
                    start=start, end=until, resolution=step, points=result,
                    summary=summary.result(), status=state, read_ok=read_ok)

    def clear(self):
        """Explicitly clear all history, atomically with the in-memory tail.

        User-requested deletion is exempt from normal write cadence. A failed
        transaction leaves both persisted history and the pending tail intact.
        It never changes sampling selection, preferences or database schema.
        """
        with self._query_lock, self._lock:
            if self._closed:
                return False
            try:
                connection = self._connect()
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(_CREATE)
                    connection.execute("CREATE INDEX IF NOT EXISTS sensor_history_expiry "
                                       "ON sensor_history(resolution,second)")
                    connection.execute("DELETE FROM sensor_history")
                self._pending.clear()
                self._source_times.clear()
                self._source_clock = None
                self._schema_ready = True
                self._last_cleanup = self._clock()
                self._next_write = self._clock() + 1
                self._status["write_transactions"] += 1
                # This committed transaction proves the writer is usable,
                # while leaving independent reader failures visible.
                self._failures.pop("sqlite3.history.write", None)
                self._recover("sqlite3.history.clear", "Local history has been cleared")
                return True
            except (OSError, sqlite3.Error) as error:
                self._failure(error, "sqlite3.history.clear")
                return False

    def close(self):
        """Finish one explicit final batch, then reject records and queries.

        Shutdown is the sole exception to the normal one-transaction/second gate,
        so a successful shutdown does not discard the final partial second.
        """
        with self._query_lock, self._lock:
            if not self._closed:
                self.flush(_final=True)
            self._closed = True
            for name in ("_connection", "_read_connection"):
                connection = getattr(self, name)
                if connection is not None:
                    try:
                        connection.close()
                    except sqlite3.Error as error:
                        self._failure(error, "sqlite3.history.close")
                    else:
                        setattr(self, name, None)
