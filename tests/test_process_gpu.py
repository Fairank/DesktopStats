"""Native GPU attribution boundaries, using only explicit fake PDH/COM APIs."""

import ctypes as c
import importlib
import importlib.util
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class GpuProcessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("process_gpu"), "GPU process counters are missing"
        )
        self.module = importlib.import_module("process_gpu")
        self.now = 0.0
        self.opens = self.collects = self.closes = 0
        self.failed = False
        self.paths = []
        fixture = self

        class Api:
            def open(self, paths):
                fixture.opens += 1
                fixture.paths.append(dict(paths))
                return 12, dict(paths), {}

            def collect(self, query):
                fixture.collects += 1
                if fixture.failed:
                    raise fixture.module.CounterError("PdhCollectQueryData", 0xC0000BB8)

            def values(self, handle):
                suffix = "_eng_0_engtype_3D" if "GPU Engine" in handle else ""
                return [
                    ("pid_42_luid_0x00000000_0x00000123_phys_0" + suffix, 25.0 if suffix else 2**30)
                ]

            def close(self, query):
                fixture.closes += 1

        self.counter = self.module.GpuProcessCounters(
            api=Api(),
            clock=lambda: self.now,
            adapters=lambda: [
                dict(name="Synthetic GPU", luid="00000000_00000123", memory=8 * 2**30)
            ],
        )
        self.addCleanup(self.counter.close)

    def test_counter_instances_keep_pid_adapter_physical_engine_and_real_values(self):
        parse = self.module.parse_counter
        instance = "pid_42_luid_0x00000001_0x00000123_phys_0_eng_2_engtype_Copy"
        self.assertEqual(
            parse(instance, 25.0, "gpu"),
            dict(pid=42, luid="00000001_00000123", engine="0_2_Copy", value=25.0),
        )
        self.assertEqual(
            parse("pid_42_luid_0x00000000_0x00000123_phys_0", 2**30, "vram"),
            dict(pid=42, luid="00000000_00000123", value=2**30),
        )

    def test_malformed_or_nonfinite_native_values_are_omitted(self):
        for name, value in [
            ("bad", 25.0),
            ("pid_0_luid_0x0_0x123_phys_0", 4),
            ("pid_42_luid_0x0_0x123_phys_0", -1),
            ("pid_42_luid_0x0_0x123_phys_0", float("nan")),
            ("pid_42_luid_0x0_0x123_phys_0", True),
        ]:
            self.assertIsNone(self.module.parse_counter(name, value, "vram"))

    def test_gpu_rate_waits_for_two_samples_and_opens_only_requested_counter(self):
        first = self.counter.read({"gpu"})
        self.assertTrue(first["warming"])
        self.now = 2.0
        second = self.counter.read({"gpu"})
        self.assertFalse(second["warming"])
        self.assertEqual(second["gpu"][0]["value"], 25.0)
        self.assertEqual(self.opens, 1)
        self.assertEqual(self.paths, [{"gpu": r"\GPU Engine(*)\Utilization Percentage"}])
        self.assertEqual(self.collects, 2)

    def test_dedicated_vram_uses_memory_counter_without_borrowing_gpu_percentage(self):
        self.counter.read({"vram"})
        self.now = 2.0
        report = self.counter.read({"vram"})
        self.assertEqual(report["vram"][0]["value"], 2**30)
        self.assertEqual(self.paths, [{"vram": r"\GPU Process Memory(*)\Dedicated Usage"}])

    def test_failure_closes_and_retries_after_backoff_without_stale_rows(self):
        self.counter.read({"gpu"})
        self.now = 2.0
        self.failed = True
        failed = self.counter.read({"gpu"})
        self.assertEqual(failed["gpu"], [])
        self.assertEqual(
            failed["errors"]["gpu"], dict(api="PdhCollectQueryData", code="0xc0000bb8")
        )
        self.assertEqual(self.closes, 1)
        self.failed = False
        self.now = 3.0
        self.counter.read({"gpu"})
        self.assertEqual(self.opens, 1)
        self.now = 63.0
        self.assertTrue(self.counter.read({"gpu"})["warming"])
        self.assertEqual(self.opens, 2)

    def test_close_releases_query_once_and_never_reopens(self):
        self.counter.read({"gpu"})
        self.counter.close()
        self.counter.close()
        report = self.counter.read({"gpu"})
        self.assertEqual(self.closes, 1)
        self.assertEqual(self.opens, 1)
        self.assertEqual(report["gpu"], [])

    def test_engine_and_memory_requests_share_one_collection(self):
        self.counter.read({"gpu", "vram"})
        self.now = 2.0
        report = self.counter.read({"gpu", "vram"})
        self.assertEqual(self.opens, 1)
        self.assertEqual(self.collects, 2)
        self.assertEqual(report["gpu"][0]["pid"], 42)
        self.assertEqual(report["vram"][0]["pid"], 42)

    def test_dxgi_releases_both_com_interfaces_on_description_failure(self):
        releases = []

        def factory(iid, result):
            c.cast(result, c.POINTER(c.c_void_p))[0] = c.c_void_p(123)
            return 0

        def method(pointer, index, result, *args):
            if index == 2:
                return lambda this: releases.append(this.value)
            if pointer.value == 123 and index == 12:

                def enumerate_adapter(this, number, output):
                    c.cast(output, c.POINTER(c.c_void_p))[0] = c.c_void_p(456)
                    return 0

                return enumerate_adapter
            if pointer.value == 456 and index == 10:
                return lambda this, desc: 0x80004005
            self.fail("Unexpected COM operation")

        with self.assertRaises(self.module.CounterError):
            self.module.dxgi_adapters(factory=factory, method=method)
        self.assertEqual(releases, [456, 123])

    def test_dxgi_preserves_existing_descriptor_pci_ids_without_extra_queries(self):
        enumerated, described, releases = [], [], []

        def factory(iid, result):
            c.cast(result, c.POINTER(c.c_void_p))[0] = c.c_void_p(123)
            return 0

        def method(pointer, index, result, *args):
            if index == 2:
                return lambda this: releases.append(this.value)
            if pointer.value == 123 and index == 12:
                def enumerate_adapter(this, number, output):
                    enumerated.append(number)
                    if number == 2:
                        return 0x887A0002
                    c.cast(output, c.POINTER(c.c_void_p))[0] = c.c_void_p(456 if number == 0 else 789)
                    return 0
                return enumerate_adapter
            if pointer.value in (456, 789) and index == 10:
                def description(this, output):
                    described.append(this.value)
                    value = c.cast(output, c.POINTER(self.module._Description)).contents
                    value.name = " Synthetic GPU "
                    value.vendor, value.device = 0x1002, 0x73DF
                    value.subsystem, value.revision = 0xE4471043, 0xFFFFFFFF
                    value.dedicated = 8 * 2**30
                    value.luid.high, value.luid.low = -2, 0x123
                    value.flags = 2 if this.value == 789 else 0
                    return 0
                return description
            self.fail("Unexpected COM operation")

        with patch.object(self.module, "adapter_address", return_value=[1, 0, 0]) as address, \
                patch.object(c, "WinDLL", side_effect=AssertionError("No native query")):
            rows = self.module.dxgi_adapters(factory=factory, method=method)
        self.assertEqual(rows, [dict(name="Synthetic GPU", luid="fffffffe_00000123",
            memory=8 * 2**30, pci_address=[1, 0, 0], pci_vendor_id=0x1002,
            pci_device_id=0x73DF, pci_subsystem_id=0xE4471043, pci_revision=0xFFFFFFFF)])
        self.assertTrue(all(type(rows[0][key]) is int for key in (
            "pci_vendor_id", "pci_device_id", "pci_subsystem_id", "pci_revision")))
        address.assert_called_once_with("fffffffe_00000123")
        self.assertEqual((enumerated, described, releases), ([0, 1, 2], [456, 789], [456, 789, 123]))

    def test_adapter_query_failure_obeys_backoff_without_repeating_enumeration(self):
        count = []

        def failed():
            count.append(1)
            raise self.module.CounterError("CreateDXGIFactory1", 0x80004005)

        self.counter.adapter_provider = failed
        self.counter.read({"gpu"})
        self.now = 2.0
        self.counter.read({"gpu"})
        self.assertEqual(len(count), 1)

    def test_adapter_address_reader_closes_native_handle_on_query_failure(self):
        self.assertTrue(
            callable(getattr(self.module, "adapter_address", None)),
            "Physical adapter mapping is missing",
        )
        closed = []

        class Function:
            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        def opened(pointer):
            c.cast(pointer, c.POINTER(self.module._OpenAdapter)).contents.handle = 42
            return 0

        from types import SimpleNamespace

        api = SimpleNamespace(
            D3DKMTOpenAdapterFromLuid=Function(opened),
            D3DKMTQueryAdapterInfo=Function(lambda _: 0xC0000001),
            D3DKMTCloseAdapter=Function(
                lambda pointer: (
                    closed.append(c.cast(pointer, c.POINTER(c.c_uint32)).contents.value) or 0
                )
            ),
        )
        with self.assertRaises(self.module.CounterError):
            self.module.adapter_address("00000000_00000123", lib=api)
        self.assertEqual(closed, [42])

    def pdh_array(self, *, unsafe=False):
        calls = []

        class Function:
            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        def array(handle, format, size, count, buffer):
            self.assertEqual(format, 0x8200)
            calls.append(buffer is not None)
            c.cast(size, c.POINTER(c.c_uint32)).contents.value = 256
            c.cast(count, c.POINTER(c.c_uint32)).contents.value = 1
            if buffer is None:
                return 0x800007D2
            if calls == [False, True]:
                return 0x800007D2  # Native instance set changed after the size query.
            address = c.addressof(buffer)
            text = "pid_42_luid_0x0_0x123_phys_0".encode("utf-16-le") + b"\0\0"
            header = struct.pack("=QI4xd", 1 if unsafe else address + 24, 0, 25.0)
            c.memmove(address, header, len(header))
            c.memmove(address + 24, text, len(text))
            return 0

        functions = {
            name: Function(lambda *_: 0)
            for name in (
                "PdhOpenQueryW",
                "PdhAddEnglishCounterW",
                "PdhCollectQueryData",
                "PdhCloseQuery",
            )
        }
        functions["PdhGetFormattedCounterArrayW"] = Function(array)
        return self.module._Pdh(lib=SimpleNamespace(**functions)), calls

    def test_pdh_array_requeries_buffer_after_instance_race_then_reads_value(self):
        api, calls = self.pdh_array()
        self.assertEqual(api.values(4), [("pid_42_luid_0x0_0x123_phys_0", 25.0)])
        self.assertEqual(calls, [False, True, False, True])

    def test_pdh_array_refuses_a_pointer_outside_its_returned_buffer(self):
        api, _ = self.pdh_array(unsafe=True)
        with self.assertRaises(self.module.CounterError):
            api.values(4)


if __name__ == "__main__":
    unittest.main()
