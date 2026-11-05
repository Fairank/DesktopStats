"""Single native process snapshot with synthetic bounded Windows x64 buffers."""

import ctypes as c
import importlib
import importlib.util
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

EPOCH = 116444736000000000


class WindowsSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("process_snapshot"), "Bulk process snapshot is missing"
        )
        self.module = importlib.import_module("process_snapshot")
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No real native API")))
        self.enterContext(patch("psutil.pids", side_effect=AssertionError("No per-PID scan")))
        self.enterContext(patch("psutil.Process", side_effect=AssertionError("No process handles")))
        self.calls = []
        self.records = [
            dict(
                pid=4,
                name="",
                created=EPOCH + 10_000_000,
                user=10_000_000,
                kernel=30_000_000,
                memory=2**20,
            ),
            dict(
                pid=42,
                name="Example.exe",
                created=EPOCH + 17_000_000,
                user=25_000_000,
                kernel=5_000_000,
                memory=7 * 2**20,
            ),
        ]
        self.mutate = lambda *_: None

    def write(self, buffer, capacity, returned):
        address = c.addressof(buffer)
        sizes = [
            (256 + len(row["name"].encode("utf-16-le")) + 2 + 7) // 8 * 8 for row in self.records
        ]
        offset = 0
        for index, (row, size) in enumerate(zip(self.records, sizes)):
            name = row["name"].encode("utf-16-le")
            struct.pack_into("<II", buffer, offset, size if index + 1 < len(sizes) else 0, 0)
            struct.pack_into(
                "<qqq", buffer, offset + 32, row["created"], row["user"], row["kernel"]
            )
            struct.pack_into("<HH", buffer, offset + 56, len(name), len(name) + 2 if name else 0)
            struct.pack_into("<Q", buffer, offset + 64, address + offset + 256 if name else 0)
            struct.pack_into("<Q", buffer, offset + 80, row["pid"])
            struct.pack_into("<Q", buffer, offset + 144, row["memory"])
            if name:
                c.memmove(address + offset + 256, name + b"\0\0", len(name) + 2)
            offset += size
        c.cast(returned, c.POINTER(c.c_uint32)).contents.value = offset
        self.mutate(buffer, offset, returned)
        return 0

    def query(self, kind, buffer, capacity, returned):
        self.assertEqual(kind, 5)
        self.calls.append(capacity)
        return self.write(buffer, capacity, returned)

    def reader(self, query=None):
        return self.module.WindowsProcessSnapshot(query=query or self.query)

    def test_one_query_supplies_cpu_memory_names_and_creation_identity(self):
        reader = self.reader()
        self.assertEqual(self.calls, [])
        result = reader.read()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(
            result["rows"],
            [
                dict(pid=4, name="System", started=1.0, cpu_seconds=4.0, memory_bytes=2**20),
                dict(
                    pid=42, name="Example.exe", started=1.7, cpu_seconds=3.0, memory_bytes=7 * 2**20
                ),
            ],
        )

    def test_unicode_basename_is_returned_without_executable_path(self):
        self.records[1]["name"] = r"C:\Private\软件.exe"
        self.assertEqual(self.reader().read()["rows"][1]["name"], "软件.exe")

    def test_pid_zero_is_not_ranked_and_missing_other_names_mark_coverage(self):
        self.records[0]["pid"] = 0
        self.records[1]["name"] = ""
        report = self.reader().read()
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["skipped"], 1)

    def test_buffer_growth_retries_once_and_reuses_the_successful_capacity(self):
        def query(kind, buffer, capacity, returned):
            self.assertEqual(kind, 5)
            self.calls.append(capacity)
            if len(self.calls) == 1:
                c.cast(returned, c.POINTER(c.c_uint32)).contents.value = 2 * 2**20
                return 0xC0000004
            return self.write(buffer, capacity, returned)

        reader = self.reader(query)
        self.assertEqual(len(reader.read()["rows"]), 2)
        self.assertEqual(len(reader.read()["rows"]), 2)
        self.assertEqual(len(self.calls), 3)
        self.assertGreaterEqual(self.calls[1], 2 * 2**20)
        self.assertEqual(self.calls[1], self.calls[2])

    def test_continually_growing_snapshot_has_bounded_retries(self):
        def query(kind, buffer, capacity, returned):
            self.calls.append(capacity)
            c.cast(returned, c.POINTER(c.c_uint32)).contents.value = capacity + 1024
            return 0xC0000004

        with self.assertRaises(self.module.SnapshotError):
            self.reader(query).read()
        self.assertLessEqual(len(self.calls), 4)

    def test_unreasonable_required_size_is_not_allocated(self):
        def query(kind, buffer, capacity, returned):
            self.calls.append(capacity)
            c.cast(returned, c.POINTER(c.c_uint32)).contents.value = 2**31
            return 0xC0000004

        with self.assertRaises(self.module.SnapshotError):
            self.reader(query).read()
        self.assertEqual(len(self.calls), 1)

    def test_native_error_preserves_api_and_status_without_per_pid_fallback(self):
        def query(*args):
            return 0xC0000022

        with self.assertRaises(self.module.SnapshotError) as caught:
            self.reader(query).read()
        self.assertEqual(caught.exception.api, "NtQuerySystemInformation")
        self.assertEqual(caught.exception.code, "0xc0000022")

    def test_record_offsets_cannot_overlap_headers_or_leave_the_returned_buffer(self):
        for value in (8, 257, 2**20):
            with self.subTest(offset=value):
                self.mutate = lambda buffer, used, returned: struct.pack_into(
                    "<I", buffer, 0, value
                )
                with self.assertRaises(self.module.SnapshotError):
                    self.reader().read()

    def test_name_pointer_must_be_inside_our_returned_buffer(self):
        self.mutate = lambda buffer, used, returned: struct.pack_into("<Q", buffer, 64, 1)
        self.records[0]["name"] = "System"
        with self.assertRaises(self.module.SnapshotError):
            self.reader().read()

    def test_utf16_length_and_capacity_are_validated_before_reading(self):
        for length, maximum in ((3, 8), (10, 8), (2, 65534)):
            with self.subTest(length=length, maximum=maximum):
                self.records[0]["name"] = "System"
                self.mutate = lambda buffer, used, returned: struct.pack_into(
                    "<HH", buffer, 56, length, maximum
                )
                with self.assertRaises(self.module.SnapshotError):
                    self.reader().read()

    def test_negative_cpu_times_are_not_turned_into_usage(self):
        self.records[1]["kernel"] = -1
        with self.assertRaises(self.module.SnapshotError):
            self.reader().read()

    def test_success_must_return_a_bounded_complete_header(self):
        for size in (0, 32, 2**30):
            with self.subTest(returned=size):
                self.mutate = lambda buffer, used, returned: c.cast(
                    returned, c.POINTER(c.c_uint32)
                ).__setitem__(0, size)
                with self.assertRaises(self.module.SnapshotError):
                    self.reader().read()


class SourceDispatchTests(unittest.TestCase):
    def test_windows_source_uses_bulk_rows_without_opening_process_handles(self):
        self.assertIsNotNone(
            importlib.util.find_spec("process_snapshot"), "Bulk process source is missing"
        )
        import process_snapshot
        import process_usage

        fake = SimpleNamespace(
            read=lambda: dict(
                rows=[
                    dict(
                        pid=42, name="Example.exe", started=1.0, cpu_seconds=3.0, memory_bytes=2**20
                    )
                ],
                skipped=2,
            )
        )
        with (
            patch.object(process_snapshot, "WindowsProcessSnapshot", return_value=fake),
            patch("process_usage.sys.platform", "win32"),
            patch("psutil.pids", side_effect=AssertionError("No per PID scan")),
            patch("psutil.Process", side_effect=AssertionError("No process handle")),
            patch("psutil.cpu_count", return_value=16),
            patch("psutil.virtual_memory", return_value=SimpleNamespace(total=32 * 2**30)),
        ):
            result = process_usage.ProcessSource().snapshot({"cpu", "memory"})
        self.assertEqual(result["rows"][0]["cpu_seconds"], 3.0)
        self.assertEqual(result["denied"], {})
        self.assertEqual(result["unidentified_count"], 2)
        self.assertEqual(result["logical_cpus"], 16)
        self.assertEqual(result["total_memory"], 32 * 2**30)


if __name__ == "__main__":
    unittest.main()
