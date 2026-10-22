"""Read-only NVMe health, isolated from the sampler by a bounded owned child.

Only IOCTL_STORAGE_QUERY_PROPERTY with the fixed NVMe health log is sent on a
zero-access metadata handle. No read/write, pass-through or settings API exists.
The child runs before Qt/IPC and writes one exclusive reply in its owned folder.
"""

import ctypes as c
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SOURCE = "Windows NVMe health"
FIELDS = ("storage_temp", "storage_spare_percent", "storage_wear_percent")


def decode_health(raw):
    if not isinstance(raw, bytes) or len(raw) < 48:
        raise ValueError("short_descriptor")
    header = struct.unpack_from("<12I", raw)
    version, size, protocol, kind = header[:4]
    offset, length = header[6:8]
    if (
        version != 48
        or size != 48
        or protocol != 3
        or kind != 2
        or offset < 40
        or length < 512
        or 8 + offset + length > len(raw)
    ):
        raise ValueError("invalid_protocol_descriptor")
    log = raw[8 + offset : 8 + offset + 512]
    kelvin = int.from_bytes(log[1:3], "little")
    # Kelvin 0/FFFF are invalid; avoid showing corrupt sentinels as temperatures.
    return dict(
        storage_temp=kelvin - 273.15 if 223 <= kelvin <= 473 else None,
        storage_spare_percent=log[3] if log[3] <= 100 else None,
        storage_wear_percent=log[5],  # NVMe explicitly permits >100% wear.
        channel_reasons={
            **({"storage_temp": "invalid_temperature_kelvin"} if not 223 <= kelvin <= 473 else {}),
            **({"storage_spare_percent": "spare_out_of_range"} if log[3] > 100 else {}),
        },
    )


def read_native():
    lib = c.WinDLL("kernel32", use_last_error=True)
    lib.QueryDosDeviceW.argtypes, lib.QueryDosDeviceW.restype = (
        [c.c_wchar_p, c.POINTER(c.c_wchar), c.c_uint32],
        c.c_uint32,
    )
    lib.CreateFileW.argtypes = [
        c.c_wchar_p,
        c.c_uint32,
        c.c_uint32,
        c.c_void_p,
        c.c_uint32,
        c.c_uint32,
        c.c_void_p,
    ]
    lib.CreateFileW.restype = c.c_void_p
    lib.CloseHandle.argtypes, lib.CloseHandle.restype = [c.c_void_p], c.c_int32
    lib.DeviceIoControl.argtypes = [
        c.c_void_p,
        c.c_uint32,
        c.c_void_p,
        c.c_uint32,
        c.c_void_p,
        c.c_uint32,
        c.POINTER(c.c_uint32),
        c.c_void_p,
    ]
    lib.DeviceIoControl.restype = c.c_int32
    size = 4096
    while True:
        names = c.create_unicode_buffer(size)
        used = lib.QueryDosDeviceW(None, names, size)
        error = c.get_last_error() if not used else 0
        if used or error != 122 or size >= 65536:
            break
        size *= 2
    if not used:
        return dict(state="query_failed", api="QueryDosDeviceW", winerror=error, storages={})
    disks = sorted(
        (
            name
            for name in names[:used].split("\0")
            if re.fullmatch(r"PhysicalDrive[0-9]{1,3}", name)
        ),
        key=lambda name: int(name[13:]),
    )[:16]
    rows = {}
    for name in disks:
        row = dict(label=name, source=SOURCE, state="query_failed", api="CreateFileW(metadata)")
        rows[name[13:]] = row
        handle = lib.CreateFileW("\\\\.\\" + name, 0, 3, None, 3, 0, None)
        if handle in (None, c.c_void_p(-1).value):
            row["winerror"] = c.get_last_error()
            continue
        try:
            buffer = c.create_string_buffer(560)
            struct.pack_into("<12I", buffer, 0, 50, 0, 3, 2, 2, 0, 40, 512, 0, 0, 0, 0)
            count = c.c_uint32()
            ok = lib.DeviceIoControl(
                handle, 0x002D1400, buffer, 560, buffer, 560, c.byref(count), None
            )
            error = c.get_last_error() if not ok else 0
            row.update(
                api="IOCTL_STORAGE_QUERY_PROPERTY(NVMe health)",
                winerror=error,
                returned_bytes=count.value,
            )
            if ok:
                try:
                    row.update(decode_health(buffer.raw[: min(count.value, 560)]))
                    row["state"] = "available"
                except ValueError as error:
                    row.update(state="invalid_value", reason=str(error))
        finally:
            if not lib.CloseHandle(handle):
                row["close_error"] = c.get_last_error()
    return dict(
        state="ready" if any(row["state"] == "available" for row in rows.values()) else "no_values",
        storages=rows,
    )


def worker_main(output):
    from stats_config import BASE

    output = Path(output)
    root = (BASE / "storage-probes").resolve()
    if (
        not output.is_absolute()
        or output.name != "reply.json"
        or not output.resolve().is_relative_to(root)
        or not output.parent.is_dir()
    ):
        return 2
    try:
        result = dict(read_native(), schema=1, timestamp=time.time(), provider=SOURCE)
    except Exception as error:
        result = dict(
            schema=1,
            timestamp=time.time(),
            provider=SOURCE,
            state="error",
            storages={},
            error=type(error).__name__ + ": " + str(error)[:300],
        )
    with output.open("x", encoding="utf-8") as file:
        json.dump(result, file)
    return 0


def parse_reply(payload):
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema")) is not int
        or payload["schema"] != 1
        or payload.get("provider") != SOURCE
    ):
        raise ValueError("invalid_storage_reply")
    if payload.get("state") not in ("ready", "no_values", "error", "query_failed"):
        raise ValueError("invalid_storage_state")
    stamp, rows = payload.get("timestamp"), payload.get("storages")
    if (
        type(stamp) not in (int, float)
        or not math.isfinite(stamp)
        or not -0.001 <= time.time() - stamp <= 8
    ):
        raise ValueError("stale_storage_reply")
    if not isinstance(rows, dict) or len(rows) > 16:
        raise ValueError("invalid_storage_list")
    result = {}
    for identifier, raw in rows.items():
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[0-9]{1,3}", identifier)
            or not isinstance(raw, dict)
        ):
            raise ValueError("invalid_storage_identifier")
        row = {field: raw.get(field) for field in FIELDS}
        for field, value in row.items():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError("invalid_storage_number")
        if row["storage_temp"] is not None and not -51 <= row["storage_temp"] <= 200:
            raise ValueError("invalid_storage_temperature")
        if (
            row["storage_spare_percent"] is not None
            and not 0 <= row["storage_spare_percent"] <= 100
        ):
            raise ValueError("invalid_storage_spare")
        if row["storage_wear_percent"] is not None and not 0 <= row["storage_wear_percent"] <= 255:
            raise ValueError("invalid_storage_wear")
        if raw.get("state") not in ("available", "query_failed", "invalid_value"):
            raise ValueError("invalid_storage_channel_state")
        for key in ("state", "api", "reason"):
            if key in raw and isinstance(raw[key], str):
                row[key] = raw[key][:160]
        if type(raw.get("winerror")) is int:
            row["winerror"] = raw["winerror"]
        reasons = raw.get("channel_reasons", {})
        if not isinstance(reasons, dict) or set(reasons) - set(FIELDS):
            raise ValueError("invalid_storage_channel_reasons")
        row["channel_reasons"] = {key: str(value)[:120] for key, value in reasons.items()}
        if type(raw.get("close_error")) is int:
            row["close_error"] = raw["close_error"]
        row.update(label="PhysicalDrive" + identifier, source=SOURCE)
        if raw.get("state") != "available":
            row.update(dict.fromkeys(FIELDS))
        result[identifier] = row
    return dict(payload, storages=result)


class StorageHealth:
    """One lazy worker; at most one owned 3-second query process every 5 seconds."""

    def __init__(self, base):
        self.base = Path(base)
        self._lock, self._stop, self._wake = threading.Lock(), threading.Event(), threading.Event()
        self._thread = self._process = self._snapshot = self._folder = None
        self._closed = False
        self._received = self._active_until = 0.0
        self._status = {"state": "idle", "detail": "添加 NVMe 指标后按需读取健康信息。"}

    def read(self, active=False):
        now = time.monotonic()
        with self._lock:
            if active and not self._stop.is_set():
                self._active_until = now + 8
                if self._thread is None:
                    self._thread = threading.Thread(
                        target=self._run, name="storage-health", daemon=True
                    )
                    self._thread.start()
                self._wake.set()
            snapshot, received, status = self._snapshot, self._received, dict(self._status)
        fresh = (
            not self._stop.is_set()
            and bool(snapshot)
            and 0 <= now - received < 8
            and -0.001 <= time.time() - snapshot["timestamp"] < 8
        )
        rows = snapshot["storages"] if snapshot else {}
        if not fresh:
            rows = {key: dict(row, **dict.fromkeys(FIELDS)) for key, row in rows.items()}
            if snapshot:
                status.update(state="stale", detail="NVMe 健康信息已过期，未继续显示旧值。")
        if self._stop.is_set():
            status.update(
                state="closed"
                if self._closed
                else "cleanup_pending"
                if status.get("state") == "cleanup_pending"
                else "closing",
                detail="NVMe 健康查询已关闭。"
                if self._closed
                else status.get("detail", "正在关闭 NVMe 健康查询。"),
            )
        return dict(storages=rows, storage_status=status)

    def _run(self):
        due = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            with self._lock:
                wanted = now < self._active_until
            if wanted and now >= due:
                self._query()
                due = time.monotonic() + 5
            self._wake.wait(0.25)
            self._wake.clear()

    def _retire_owned(self):
        """Never throw away an owned process/folder or permit another on failed cleanup."""
        with self._lock:
            process, folder = self._process, self._folder
        try:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=1)
                if process.poll() is None:
                    raise TimeoutError("Own storage worker has not exited")
                with self._lock:
                    if self._process is process:
                        self._process = None
            if folder is not None:
                root = (self.base / "storage-probes").resolve()
                target = Path(folder).resolve()
                if target.parent != root or not target.name.startswith("owned-"):
                    raise ValueError("Refusing cleanup outside own storage probe folder")
                try:
                    shutil.rmtree(target)
                except FileNotFoundError:
                    pass
                with self._lock:
                    if self._folder == folder:
                        self._folder = None
            return True
        except Exception as error:
            with self._lock:
                self._snapshot = None
                self._status = dict(
                    state="cleanup_pending",
                    detail="NVMe 子进程清理尚未完成："
                    + type(error).__name__
                    + ": "
                    + str(error)[:240],
                )
            return False

    def _query(self):
        if not self._retire_owned() or self._stop.is_set():
            return
        process = None
        try:
            root = self.base / "storage-probes"
            root.mkdir(parents=True, exist_ok=True)
            folder = tempfile.mkdtemp(prefix="owned-", dir=root)
            with self._lock:
                self._folder = folder
            reply = Path(folder) / "reply.json"
            command = [sys.executable]
            if not getattr(sys, "frozen", False):
                command.append(str(Path(__file__).with_name("app.py")))
            command.extend(["--storage-read", str(reply)])
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                shell=False,
            )
            with self._lock:
                self._process = process
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                raise TimeoutError("NVMe health worker timed out")
            if process.returncode != 0 or not reply.is_file() or reply.stat().st_size > 65536:
                raise ValueError("invalid_storage_worker_result; exit=" + str(process.returncode))
            payload = parse_reply(json.loads(reply.read_text(encoding="utf-8")))
            with self._lock:
                if not self._stop.is_set():
                    self._snapshot, self._received = payload, time.monotonic()
                    self._status = dict(
                        state=payload["state"],
                        detail=payload.get("error", "Windows NVMe 只读健康查询。"),
                    )
        except Exception as error:
            with self._lock:
                self._snapshot = None
                self._status = dict(
                    state="error", detail=type(error).__name__ + ": " + str(error)[:300]
                )
        finally:
            self._retire_owned()

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=4.5)
            if self._thread.is_alive():
                with self._lock:
                    self._status = dict(
                        state="closing", detail="NVMe 采集线程尚未退出；保留子进程所有权。"
                    )
                return False
        if not self._retire_owned():
            return False
        self._closed = True
        return True
