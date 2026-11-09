"""Synthetic firmware records only. No native or user hardware access."""
import unittest
import ctypes
from types import SimpleNamespace
from unittest.mock import patch

import memory_identity as identity


def record(*, part=b"CMK32GX4M2E3200C16", maker=b"Corsair", form=9, size=8192):
    row = bytearray(0x1b)
    row[0:2] = bytes((17, len(row)))
    row[0x0c:0x0e] = size.to_bytes(2, "little")
    row[0x0e], row[0x17], row[0x18], row[0x19], row[0x1a] = form, 1, 2, 3, 4
    return bytes(row) + b"\0".join((maker, b"SERIAL-NEVER-RETAIN", b"ASSET-PRIVATE", part)) + b"\0\0"


def raw(*records):
    table = b"".join(records) + b"\x7f\x04\x00\x00\x00\x00"
    return b"\0\x03\x09\0" + len(table).to_bytes(4, "little") + table


class MemoryIdentityTests(unittest.TestCase):
    def tearDown(self):
        identity._identity_once.cache_clear()

    def test_only_identity_fields_survive_and_form_factors_are_not_guessed(self):
        data = raw(record(), record(part=b"SODIMM-PART", form=13), record(part=b"soldered", form=11))
        result = identity.parse_smbios(data)
        self.assertEqual(result, (("Corsair", "CMK32GX4M2E3200C16", "dimm"),
                                  ("Corsair", "SODIMM-PART", "sodimm"), ("Corsair", "soldered", "unknown")))
        self.assertNotIn("SERIAL", repr(result))
        self.assertNotIn("ASSET", repr(result))

    def test_empty_slots_and_placeholders_do_not_invent_product_identities(self):
        self.assertEqual(identity.parse_smbios(raw(record(size=0), record(part=b"Unknown", maker=b"Not Specified"))),
                         (("", "", "dimm"),))

    def test_truncation_invalid_lengths_and_device_limit_fail_closed(self):
        data = raw(record())
        for candidate in (None, b"", data[:-1], data+b"extra", data[:8]+b"\x11\x03\0\0\0\0",
                          raw(*[record() for _ in range(65)])):
            self.assertEqual(identity.parse_smbios(candidate), ())
        no_terminator = bytearray(data)
        no_terminator[-2:] = b"xx"
        self.assertEqual(identity.parse_smbios(bytes(no_terminator)), ())

    def test_success_and_failure_are_cached_without_retaining_mutable_maps(self):
        with patch.object(identity, "_read_raw_table", return_value=raw(record())) as read:
            first = identity.modules()
            first[0]["part_number"] = "changed"
            self.assertEqual(identity.modules()[0]["part_number"], "CMK32GX4M2E3200C16")
            self.assertEqual(read.call_count, 1)
        identity._identity_once.cache_clear()
        with patch.object(identity, "_read_raw_table", side_effect=OSError("unavailable")) as read:
            self.assertEqual(identity.modules(), [])
            self.assertEqual(identity.modules(), [])
            self.assertEqual(read.call_count, 1)

    def test_only_modern_topbar_with_ram_requests_one_shot_identity(self):
        bar = dict(enabled=True, hardware_icon_style="soft", items=[dict(metric="ram_percent", prefs={})])
        self.assertTrue(identity.requested(dict(top_bar=bar)))
        self.assertTrue(identity.requested(dict(top_bar=dict(bar, hardware_icon_style="cartoon"))))
        self.assertTrue(identity.requested(dict(top_bar=dict(bar, hardware_icon_style="sketch"))))
        for patch_value in (dict(enabled=False), dict(hardware_icon_style="classic"),
                            dict(items=[dict(metric="vram_percent", prefs={})]), dict(items=[])):
            self.assertFalse(identity.requested(dict(top_bar=dict(bar, **patch_value))))

    def test_native_snapshot_uses_only_size_and_data_calls_then_reuses_cache(self):
        payload = raw(record())
        class Query:
            def __init__(self): self.calls = []
            def __call__(self, provider, table, buffer, size):
                self.calls.append((provider, table, size))
                if buffer is None:
                    return len(payload)
                ctypes.memmove(buffer, payload, len(payload))
                return len(payload)
        query = Query()
        with patch.object(identity.sys, "platform", "win32"), \
             patch.object(identity.c, "WinDLL", return_value=SimpleNamespace(GetSystemFirmwareTable=query)) as library:
            for _ in range(100): self.assertEqual(len(identity.modules()), 1)
            library.assert_called_once_with("kernel32", use_last_error=True)
        self.assertEqual(query.calls, [(int.from_bytes(b"RSMB", "big"), 0, 0),
                                       (int.from_bytes(b"RSMB", "big"), 0, len(payload))])

    def test_oversized_snapshot_does_not_allocate_or_retry(self):
        from unittest.mock import Mock
        query = Mock(return_value=identity.MAX_BYTES + 1)
        with patch.object(identity.sys, "platform", "win32"), \
             patch.object(identity.c, "WinDLL", return_value=SimpleNamespace(GetSystemFirmwareTable=query)), \
             patch.object(identity.c, "create_string_buffer", side_effect=AssertionError("No large allocation")):
            self.assertEqual(identity.modules(), [])
            self.assertEqual(identity.modules(), [])
            query.assert_called_once()


if __name__ == "__main__":
    unittest.main()
