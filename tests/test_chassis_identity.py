"""Synthetic read-only SMBIOS contracts; never read real hardware in tests."""

import ctypes
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import chassis_catalog as catalog
import chassis_identity as identity


def structure(kind, size, fields, strings):
    data = bytearray(size)
    data[0:2] = bytes((kind, size))
    for position, value in fields.items():
        if isinstance(value, bytes):
            data[position:position + len(value)] = value
        else:
            data[position] = value
    return bytes(data) + b"\0".join(strings) + b"\0\0"


def system(maker=b"ASUS", product=b"System Product Name"):
    return structure(1, 0x1b, {4: 1, 5: 2, 6: 3, 7: 4, 8: b"PRIVATE-UUID12345", 0x19: 5, 0x1a: 6},
                     (maker, product, b"System Version", b"PRIVATE-SYSTEM-SERIAL", b"SKU", b"System Family"))


def baseboard(board_type=10):
    return structure(2, 0x0f, {4: 1, 5: 2, 6: 3, 7: 4, 8: 5, 0x0d: board_type},
                     (b"ASUSTeK COMPUTER INC.", b"ROG STRIX Z790-A GAMING WIFI D4", b"PRIVATE-BOARD-VERSION",
                      b"PRIVATE-BOARD-SERIAL", b"PRIVATE-ASSET"))


def enclosure(maker=b"Chassis Manufacturer", version=b"Default string", sku=b"SKU", count=0, width=0, lock=True):
    sku_position = 0x15 + count * width
    return structure(3, sku_position + 1,
                     {4: 1, 5: 3 | (0x80 if lock else 0), 6: 2, 7: 3, 8: 4,
                      0x13: count, 0x14: width, sku_position: 5},
                     (maker, version, b"PRIVATE-CHASSIS-SERIAL", b"PRIVATE-ASSET", sku))


def raw(*records):
    table = b"".join(records) + b"\x7f\x04\0\0\0\0"
    return b"\0\x03\x09\0" + len(table).to_bytes(4, "little") + table


class ChassisIdentityTests(unittest.TestCase):
    def tearDown(self):
        identity._identity_once.cache_clear()

    def test_import_performs_no_native_calls(self):
        with patch.object(ctypes, "WinDLL", side_effect=AssertionError("import must be lazy")) as native:
            importlib.reload(identity)
            native.assert_not_called()

    def test_only_whitelisted_identity_fields_survive(self):
        with patch.object(identity, "_read_raw_table", return_value=raw(system(), baseboard(), enclosure())):
            result = identity.snapshot()
        self.assertEqual(result["system"], dict(manufacturer="ASUS", product="", version="", sku="", family=""))
        self.assertEqual(result["enclosures"], [dict(manufacturer="", version="", sku="", type=3)])
        self.assertEqual(result["baseboards"], [dict(manufacturer="ASUSTeK COMPUTER INC.",
                                                  product="ROG STRIX Z790-A GAMING WIFI D4", board_type=10)])
        self.assertNotIn("PRIVATE", repr(result))
        self.assertEqual(set(result), {"state", "source", "system", "enclosures", "baseboards"})

    def test_variable_position_chassis_sku_and_lock_bit(self):
        result = identity.parse_smbios(raw(enclosure(b"Example OEM", b"Example case", b"CASE-123", count=2, width=3)))
        self.assertEqual(result[1], (("Example OEM", "Example case", "CASE-123", 3),))

    def test_legacy_type3_without_sku_is_valid(self):
        record = structure(3, 9, {4: 1, 5: 0x83, 6: 2, 7: 3},
                           (b"Legacy OEM", b"Legacy enclosure", b"PRIVATE-SERIAL"))
        self.assertEqual(identity.parse_smbios(raw(record))[1], (("Legacy OEM", "Legacy enclosure", "", 3),))

    def test_module_boards_are_not_motherboards(self):
        self.assertEqual(identity.parse_smbios(raw(baseboard(board_type=9)))[2], ())

    def test_invalid_structure_lengths_bounds_and_counts_fail_closed(self):
        good = raw(system(), enclosure())
        bad_component_array = bytearray(enclosure(count=1, width=3))
        bad_component_array[0x14] = 1
        out_of_bounds_array = bytearray(enclosure())
        out_of_bounds_array[0x13:0x15] = bytes((255, 255))
        malformed = (None, b"", good[:-1], good + b"x", raw(system(), system()),
                     raw(structure(3, 8, {}, (b"invalid",))), raw(bytes(bad_component_array)),
                     raw(bytes(out_of_bounds_array)), raw(*[enclosure() for _ in range(17)]),
                     raw(*[baseboard() for _ in range(17)]), raw(*[b"\x7e\x04\0\0\0\0"] * 4096))
        for candidate in malformed:
            with self.subTest(length=len(candidate) if candidate is not None else None):
                self.assertIsNone(identity.parse_smbios(candidate))

    def test_placeholder_normalization_is_bounded(self):
        self.assertEqual(identity._clean(b"  SystemProductName  "), "")
        self.assertEqual(identity._clean(b"\tTo Be Filled By O.E.M.\n"), "")
        self.assertEqual(identity._clean("ＡＳＵＳ".encode()), "ASUS")
        self.assertLessEqual(len(identity._clean(b"A" * 5000)), 128)

    def test_success_and_failure_cached_with_detached_results(self):
        with patch.object(identity, "_read_raw_table", return_value=raw(system(), baseboard(), enclosure())) as read:
            first = identity.snapshot()
            first["system"]["manufacturer"] = "changed"
            first["baseboards"].clear()
            first["enclosures"][0]["type"] = 99
            second = identity.snapshot()
            self.assertEqual(second["system"]["manufacturer"], "ASUS")
            self.assertEqual(len(second["baseboards"]), 1)
            self.assertEqual(second["enclosures"][0]["type"], 3)
            read.assert_called_once()
        identity._identity_once.cache_clear()
        with patch.object(identity, "_read_raw_table", side_effect=OSError("unavailable")) as read:
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            read.assert_called_once()

    def test_native_read_performs_two_calls_only_and_no_privileged_interface(self):
        payload = raw(system(), enclosure())
        class Query:
            def __init__(self):
                self.calls = []
            def __call__(self, provider, table, buffer, size):
                self.calls.append((provider, table, size))
                if buffer is None:
                    return len(payload)
                ctypes.memmove(buffer, payload, len(payload))
                return len(payload)
        query = Query()
        with patch.object(identity.sys, "platform", "win32"), \
             patch.object(identity.c, "WinDLL", return_value=SimpleNamespace(GetSystemFirmwareTable=query)) as native:
            for _ in range(20):
                self.assertEqual(identity.snapshot()["state"], "available")
            native.assert_called_once_with("kernel32", use_last_error=True)
        self.assertEqual(query.calls, [(int.from_bytes(b"RSMB", "big"), 0, 0),
                                       (int.from_bytes(b"RSMB", "big"), 0, len(payload))])

    def test_oversized_snapshot_never_allocated_or_retried(self):
        query = Mock(return_value=identity.MAX_BYTES + 1)
        with patch.object(identity.sys, "platform", "win32"), \
             patch.object(identity.c, "WinDLL", return_value=SimpleNamespace(GetSystemFirmwareTable=query)), \
             patch.object(identity.c, "create_string_buffer", side_effect=AssertionError("oversized allocation")):
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            query.assert_called_once()

    def test_changed_snapshot_size_fails_without_retry(self):
        query = Mock(side_effect=[32, 31])
        with patch.object(identity.sys, "platform", "win32"), \
             patch.object(identity.c, "WinDLL", return_value=SimpleNamespace(GetSystemFirmwareTable=query)):
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            self.assertEqual(identity.snapshot()["state"], "unavailable")
        self.assertEqual(query.call_count, 2)

    def test_non_windows_does_not_load_kernel32(self):
        with patch.object(identity.sys, "platform", "linux"), patch.object(identity.c, "WinDLL") as native:
            self.assertEqual(identity.snapshot()["state"], "unavailable")
            native.assert_not_called()

    def test_asus_motherboard_and_system_never_choose_a_case(self):
        with patch.object(identity, "_read_raw_table", return_value=raw(system(), baseboard(), enclosure())):
            result = identity.identify()
        self.assertEqual(result["state"], "unidentified")
        self.assertIsNone(result["model"])
        self.assertEqual(result["reason"], "retail_model_not_reported")

    def test_manual_selection_is_explicit_and_invalid_saved_id_is_safe(self):
        firmware = dict(state="unavailable", enclosures=[])
        chosen = identity.identify(firmware, "hyte-y60")
        self.assertEqual(chosen["state"], "manual")
        self.assertEqual(chosen["model"]["id"], "hyte-y60")
        self.assertIs(chosen["firmware"], firmware)
        for invalid in ("old-unavailable-case", "../hyte-y60", "x" * 65, ["hyte-y60"]):
            result = identity.identify(firmware, invalid)
            self.assertEqual(result["state"], "unidentified")
            self.assertIsNone(result["model"])
            self.assertEqual(result["reason"], "invalid_manual_selection")

    def test_only_verified_exact_enclosure_can_auto_match_and_conflicts_stay_unknown(self):
        registry = (("Verified OEM", "CASE-A", "hyte-y60", "https://hyte.com/store/y60/cs-hyte-y60-b"),
                    ("Verified OEM", "CASE-B", "hyte-y70", "https://hyte.com/store/y70/cs-hyte-y70-b"))
        firmware = dict(state="available", enclosures=[dict(manufacturer="Verified OEM", version="CASE-A")])
        with patch.object(catalog, "_FIRMWARE_IDENTITIES", registry):
            self.assertEqual(identity.identify(firmware)["state"], "automatic")
            firmware["enclosures"].append(dict(manufacturer="Verified OEM", sku="CASE-B"))
            self.assertEqual(identity.identify(firmware)["reason"], "ambiguous_enclosure_identity")
            firmware["enclosures"] = None
            self.assertEqual(identity.identify(firmware)["state"], "unidentified")


if __name__ == "__main__":
    unittest.main()
