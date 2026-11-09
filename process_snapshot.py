"""One bounded Windows process snapshot, with no per-process handles.

The Windows x64 SYSTEM_PROCESS_INFORMATION prefix supplies process name,
creation time, CPU times and working set together. One query avoids repeating
psutil's protected-process fallbacks for every PID. No command line, account or
executable path is requested. Native/schema errors remain explicit failures.

API: https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation
Layout reference: https://github.com/winsiderss/phnt/blob/master/ntexapi.h
The x64 prefix ends with six LARGE_INTEGER I/O counters. ReadTransferCount at
232 and WriteTransferCount at 240 are process-wide bytes, not physical-disk
attribution. They are decoded only when explicitly requested by the same worker.
"""

import ctypes as c
import struct

_CLASS = 5  # SystemProcessInformation; read only.
_HEADER = 256  # Windows x64 prefix, followed by variable thread/name data.
_INITIAL = 256 * 1024
_MAXIMUM = 64 * 1024 * 1024
_MAX_ATTEMPTS = 4
_EPOCH = 116444736000000000
_TICKS = 10000000
_RESIZE = frozenset((0xC0000004, 0xC0000023, 0x80000005))


class SnapshotError(OSError):
    api = "NtQuerySystemInformation"

    def __init__(self, status, reason="Native process snapshot unavailable"):
        self.code = f"0x{status & 0xFFFFFFFF:08x}"
        super().__init__(f"{self.api}: {self.code}; {reason}")


class WindowsProcessSnapshot:
    """Lazy native binding and reusable buffer, owned by one sampler worker."""

    def __init__(self, *, query=None):
        self.query = query
        self.buffer = None

    def _bind(self):
        if c.sizeof(c.c_void_p) != 8:
            raise SnapshotError(0xC00000BB, "Windows x64 snapshot layout required")
        if self.query is None:
            self.library = c.WinDLL("ntdll", use_last_error=True)
            self.query = self.library.NtQuerySystemInformation
            self.query.argtypes = [c.c_uint32, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32)]
            self.query.restype = c.c_int32

    def read(self, *, include_io=False):
        self._bind()
        if self.buffer is None:
            self.buffer = c.create_string_buffer(_INITIAL)
        for _attempt in range(_MAX_ATTEMPTS):
            capacity = len(self.buffer)
            returned = c.c_uint32()
            status = self.query(_CLASS, self.buffer, capacity, c.byref(returned)) & 0xFFFFFFFF
            if status in _RESIZE:
                needed = max(returned.value + 65536, capacity * 2)
                if needed > _MAXIMUM:
                    raise SnapshotError(status, "Native snapshot exceeds the bounded buffer")
                self.buffer = c.create_string_buffer(needed)
                continue
            if status:
                raise SnapshotError(status)
            if not _HEADER <= returned.value <= capacity:
                raise SnapshotError(0xC000000D, "Invalid native return length")
            return self._decode(returned.value, include_io=include_io)
        raise SnapshotError(status, "Native snapshot kept changing during bounded retries")

    def _decode(self, used, *, include_io=False):
        buffer = self.buffer
        address = c.addressof(buffer)
        rows, skipped, offset, count = [], 0, 0, 0
        while True:
            count += 1
            if count > 65536 or offset + _HEADER > used:
                raise SnapshotError(0xC000000D, "Invalid process record boundary")
            next_offset = struct.unpack_from("<I", buffer, offset)[0]
            if next_offset and (
                next_offset < _HEADER or next_offset % 8 or offset + next_offset > used
            ):
                raise SnapshotError(0xC000000D, "Invalid next process offset")
            created, user, kernel = struct.unpack_from("<qqq", buffer, offset + 32)
            length, maximum = struct.unpack_from("<HH", buffer, offset + 56)
            pointer = struct.unpack_from("<Q", buffer, offset + 64)[0]
            pid = struct.unpack_from("<Q", buffer, offset + 80)[0]
            working_set = struct.unpack_from("<Q", buffer, offset + 144)[0]
            if user < 0 or kernel < 0 or created < 0 or 0 < created < _EPOCH:
                raise SnapshotError(0xC000000D, "Invalid process time counters")
            if length % 2 or maximum % 2 or length > maximum:
                raise SnapshotError(0xC000000D, "Invalid process name length")
            if length:
                if not address <= pointer or pointer + maximum > address + used:
                    raise SnapshotError(0xC000000D, "Process name pointer is outside the snapshot")
                try:
                    name = c.string_at(pointer, length).decode("utf-16-le")
                except UnicodeDecodeError as error:
                    raise SnapshotError(0xC000000D, "Invalid process name encoding") from error
                if "\0" in name:
                    raise SnapshotError(0xC000000D, "Invalid process name terminator")
                name = name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].strip()[:180]
            else:
                name = "System" if pid == 4 else ""
            if pid:
                if name:
                    row = dict(
                            pid=pid,
                            name=name,
                            started=(created - _EPOCH) / _TICKS if created else 0.0,
                            cpu_seconds=(user + kernel) / _TICKS,
                            memory_bytes=working_set,
                        )
                    if include_io:
                        read_bytes, write_bytes = struct.unpack_from('<qq', buffer, offset + 232)
                        # Invalid signed counters do not fabricate zero I/O or
                        # discard otherwise usable CPU/memory observations.
                        if read_bytes >= 0 and write_bytes >= 0:
                            row.update(io_read_bytes=read_bytes, io_write_bytes=write_bytes)
                    rows.append(row)
                else:
                    skipped += 1
            if not next_offset:
                return dict(rows=rows, skipped=skipped)
            offset += next_offset
