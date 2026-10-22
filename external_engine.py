"""Owned, bounded background transport for the bundled sensor collector.

Only the app's fixed helper path is executable. No GUI, listening socket, shell,
elevation or driver setup is involved. A stalled or invalid helper cannot block
the sampler or preserve stale values. Discovery runs independently of UI cadence.
"""

import json
import subprocess
import threading
import time
from pathlib import Path

from external_sensor import PROVIDER, parse_snapshot

MAX_LINE = 2 * 1024 * 1024
FRESH_SECONDS = 8.0
START_SECONDS = 20.0


def collector_path():
    # In a frozen app __file__ is inside _internal, beside bundled collector/.
    root = Path(__file__).resolve().parent / "collector"
    packaged = root / "DesktopStats.Collector.exe"
    return packaged if packaged.is_file() else root / "runtime" / "DesktopStats.Collector.exe"


class ExternalEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._active_until = 0.0
        self._rescan = None
        self._generation = 0
        self._snapshot = None
        self._received_at = None
        self._status = "idle"
        self._detail = "扩展采集器按需运行"
        self._revision = 0
        self._unavailable_cache = None
        self._process = None
        self._session_token = None

    def _state(self, state, detail):
        with self._lock:
            if (state, detail) != (self._status, self._detail):
                self._status, self._detail = state, detail
                self._revision += 1

    def read(self, active=False, rescan=0):
        """Non-blocking snapshot. Returned rows must be treated as immutable."""
        now = time.monotonic()
        with self._lock:
            if self._stop.is_set():
                active = False
            if active:
                self._active_until = now + 8.0  # UI sampling may itself be 5 s.
                if self._rescan != rescan:
                    self._rescan = rescan
                    self._generation += 1
                    self._received_at = None
                    self._status, self._detail = "starting", "正在识别扩展传感器"
                    self._revision += 1
                    self._wake.set()
                if self._thread is None:
                    self._thread = threading.Thread(
                        target=self._run, name="extended-sensor-engine", daemon=True
                    )
                    self._thread.start()
            snapshot, received = self._snapshot, self._received_at
            state, detail, revision = self._status, self._detail, self._revision
        # Check both clocks: suspend/resume or an adjusted wall clock cannot make
        # a fresh UI refresh pass off an old provider sample as a current reading.
        fresh = (
            snapshot is not None
            and received is not None
            and 0 <= now - received <= FRESH_SECONDS
            and abs(time.time() - snapshot["timestamp"]) <= FRESH_SECONDS
        )
        fresh = fresh and state in ("ready", "empty") and not self._stop.is_set()
        rows = snapshot["sensors"] if snapshot else {}
        if not fresh and rows:
            with self._lock:
                if self._unavailable_cache is None or self._unavailable_cache[0] is not snapshot:
                    self._unavailable_cache = (
                        snapshot,
                        {key: dict(row, value=None, available=False) for key, row in rows.items()},
                    )
                rows = self._unavailable_cache[1]
            if state in ("ready", "empty"):
                state, detail = "stale", "扩展传感器读数已过期"
        available = sum(row.get("available", False) for row in rows.values())
        return {
            "external_sensors": rows,
            "external_revision": (revision, bool(fresh)),
            "external_status": dict(
                state=state,
                detail=detail,
                sensor_count=len(rows),
                available_count=available,
                hardware_count=len(snapshot["hardware"]) if snapshot else 0,
                version=snapshot["version"] if snapshot else "0.9.6",
                updated_at=snapshot["timestamp"] if snapshot else None,
                provider=PROVIDER,
                **{field: snapshot.get(field, 0) if snapshot else 0
                   for field in ("skipped_types", "update_errors", "truncated", "rejected_count")},
            ),
        }

    def _wanted(self, generation=None):
        with self._lock:
            return (
                not self._stop.is_set()
                and time.monotonic() < self._active_until
                and (generation is None or generation == self._generation)
            )

    def _accept(self, line, generation, token=None):
        # decode strictly, reject arbitrary diagnostics or malformed/oversize JSON
        payload = json.loads(line.decode("utf-8"))
        snapshot = parse_snapshot(payload)
        if abs(time.time() - snapshot["timestamp"]) > FRESH_SECONDS:
            raise ValueError("Collector timestamp is not current")
        with self._lock:
            if (
                generation != self._generation
                or self._stop.is_set()
                or token is not self._session_token
            ):
                return
            self._snapshot = snapshot
            self._received_at = time.monotonic()
            self._status = "ready" if snapshot["sensors"] else "empty"
            self._detail = (
                "已连接扩展传感器" if snapshot["sensors"] else "此采集模式未发现支持的传感器"
            )
            self._revision += 1

    def _consume(self, stream, generation, done, failed, token=None):
        try:
            while not self._stop.is_set():
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE or not line.endswith(b"\n"):
                    raise ValueError("Collector line limit")
                self._accept(line, generation, token)
        except (ValueError, TypeError, OSError, UnicodeError, RecursionError):
            failed.set()
        finally:
            stream.close()
            done.set()

    @staticmethod
    def _drain(stream):
        # Never accumulate provider diagnostics or print hardware identifiers.
        try:
            while stream.read(4096):
                pass
        except OSError:
            pass
        finally:
            stream.close()

    @staticmethod
    def _shutdown(process):
        try:
            if process.poll() is None:
                process.stdin.write(b"stop\n")
                process.stdin.flush()
        except (OSError, ValueError, BrokenPipeError):
            pass
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass
        try:
            process.wait(timeout=0.75)
        except subprocess.TimeoutExpired:
            # This Popen is the only process we terminate. No PID/name search.
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.5)

    def _session(self, generation):
        path = collector_path()
        if not path.is_file():
            self._state("missing", "扩展采集器尚未安装")
            return False
        self._state("starting", "正在识别扩展传感器")
        # NO_WINDOW also applies when the main app is frozen with no console.
        process = subprocess.Popen(
            [str(path), "--interval", "1"],
            cwd=str(path.parent),
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._lock:
            self._process = process
            token = self._session_token = object()
            self._received_at = None
        done, failed = threading.Event(), threading.Event()
        reader = threading.Thread(
            target=self._consume,
            args=(process.stdout, generation, done, failed, token),
            daemon=True,
        )
        errors = threading.Thread(target=self._drain, args=(process.stderr,), daemon=True)
        started = time.monotonic()
        healthy = False
        try:
            reader.start()
            errors.start()
            while self._wanted(generation):
                with self._lock:
                    received = self._received_at
                elapsed = time.monotonic() - started
                current = received is not None and received >= started
                healthy = healthy or current
                if done.is_set() or failed.is_set() or process.poll() is not None:
                    self._retire(token)
                    self._state("error", "扩展采集器已停止，可重新扫描")
                    break
                if (
                    current
                    and time.monotonic() - received > FRESH_SECONDS
                    or not current
                    and elapsed > START_SECONDS
                ):
                    self._retire(token)
                    self._state("stale", "扩展采集器响应超时")
                    break
                self._wake.wait(0.2)
                self._wake.clear()
        finally:
            self._retire(token)
            try:
                self._shutdown(process)
            except (OSError, subprocess.SubprocessError):
                # Retry only our own handle after an exceptional cleanup failure.
                # Preserve the original error for the supervisor/status; never
                # start another collector while this process is still alive.
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=0.5)
                except (OSError, subprocess.SubprocessError):
                    pass
                raise
            finally:
                for thread, stream in ((reader, process.stdout), (errors, process.stderr)):
                    if thread.ident is not None:
                        thread.join(timeout=0.25)
                    # A blocked BufferedReader.close can itself wait on read's
                    # lock. That thread owns closing its stream in its finally.
                    if not thread.is_alive():
                        stream.close()
                with self._lock:
                    if process.poll() is not None:
                        self._process = None
        return healthy

    def _retire(self, token):
        # A reader may still hold a complete buffered line after the process
        # exits. Invalidate that session before status/cleanup, including retries
        # that use the same user rescan generation.
        with self._lock:
            if self._session_token is token:
                self._session_token = None
                self._received_at = None
                self._revision += 1

    def _run(self):
        failures = 0
        retry_at = 0.0
        seen = -1
        while not self._stop.is_set():
            with self._lock:
                generation = self._generation
                outstanding = self._process
            if outstanding is not None:
                if outstanding.poll() is None:
                    self._state("error", "扩展采集器尚未结束")
                    self._wake.wait(0.5)
                    self._wake.clear()
                    continue
                with self._lock:
                    self._process = None
            if generation != seen:
                failures, retry_at, seen = 0, 0.0, generation
            if not self._wanted():
                self._state("idle", "扩展采集器按需运行")
            elif time.monotonic() >= retry_at:
                try:
                    healthy = self._session(generation)
                    failures = 1 if healthy else min(failures + 1, 5)
                except (OSError, subprocess.SubprocessError, ValueError):
                    self._state("error", "无法启动扩展采集器，可重新扫描")
                    failures = min(failures + 1, 5)
                retry_at = time.monotonic() + min(60, 2**failures)
                continue
            self._wake.wait(0.5)
            self._wake.clear()

    def close(self):
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=4.0)
        with self._lock:
            process = self._process
        unfinished = (
            thread is not None
            and thread.is_alive()
            or process is not None
            and process.poll() is None
        )
        self._state(
            "error" if unfinished else "idle",
            "扩展采集器尚未结束" if unfinished else "扩展采集器已停止",
        )
