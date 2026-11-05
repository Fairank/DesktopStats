"""Native network snapshots from bounded synthetic ABI buffers, never live APIs."""

import ctypes as c
import importlib
import importlib.util
import os
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class Call:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class NativeNetworkTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("network_snapshot"), "Bulk native network snapshot is missing"
        )
        self.module = importlib.import_module("network_snapshot")
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No live native API")))
        self.aliases = [
            dict(index=7, luid=700, alias="Synthetic VPN"),
            dict(index=9, luid=900, alias="Synthetic Wi-Fi"),
        ]
        self.rows = [
            dict(index=7, luid=700, oper=1, admin=1),
            dict(index=9, luid=900, oper=1, admin=1),
            dict(index=99, luid=9900, oper=1, admin=1),
        ]
        self.calls, self.freed = [], []
        self.buffers = []
        self.address_error = self.table_error = 0
        self.mutate_address = self.mutate_table = lambda *_: None
        self.api = SimpleNamespace(
            GetAdaptersAddresses=Call(self.addresses),
            GetIfTable2=Call(self.table),
            FreeMibTable=Call(self.free),
        )

    def addresses(self, family, flags, reserved, buffer, size):
        self.calls.append(("addresses", family, flags, c.sizeof(buffer)))
        self.assertEqual((family, flags, reserved), (0, 15, None))
        if self.address_error:
            return self.address_error
        start = c.addressof(buffer)
        offset = len(self.aliases) * 256
        for index, row in enumerate(self.aliases):
            base = index * 256
            raw = row["alias"].encode("utf-16-le") + b"\0\0"
            struct.pack_into(
                "<IIQ",
                buffer,
                base,
                232,
                row["index"],
                start + (index + 1) * 256 if index + 1 < len(self.aliases) else 0,
            )
            struct.pack_into("<Q", buffer, base + 72, start + offset)
            struct.pack_into("<I", buffer, base + 108, row["index"])
            struct.pack_into("<Q", buffer, base + 224, row["luid"])
            c.memmove(start + offset, raw, len(raw))
            offset += len(raw)
        c.cast(size, c.POINTER(c.c_uint32)).contents.value = offset
        self.mutate_address(buffer, offset, size)
        return 0

    def table(self, output):
        self.calls.append(("table",))
        buffer = c.create_string_buffer(8 + len(self.rows) * 1352)
        struct.pack_into("<I", buffer, 0, len(self.rows))
        for index, row in enumerate(self.rows):
            base = 8 + index * 1352
            struct.pack_into("<QI", buffer, base, row["luid"], row["index"])
            struct.pack_into("<I", buffer, base + 12, row.get("guid", 0))
            struct.pack_into("<II", buffer, base + 1156, row["oper"], row["admin"])
            # Sent/received bytes, packet pairs, errors and drops are all distinct.
            for offset, value in {
                1208: row.get("rx", 11),
                1216: 12,
                1224: 13,
                1232: 14,
                1240: 15,
                1280: row.get("tx", 21),
                1288: 22,
                1296: 23,
                1304: 24,
                1312: 25,
            }.items():
                struct.pack_into("<Q", buffer, base + offset, value)
        self.mutate_table(buffer, output)
        self.buffers.append(buffer)
        c.cast(output, c.POINTER(c.c_void_p)).contents.value = c.addressof(buffer)
        return self.table_error

    def free(self, pointer):
        self.freed.append(pointer.value if isinstance(pointer, c.c_void_p) else pointer)

    def source(self):
        return self.module.NativeNetworkSnapshot(api=self.api)

    def test_single_table_fresh_names_exact_counters_and_no_extra_interfaces(self):
        source = self.source()
        first = source.read()
        self.assertEqual(set(first), {"Synthetic VPN", "Synthetic Wi-Fi"})
        self.assertEqual(
            first["Synthetic VPN"],
            dict(
                isup=True,
                identity=(700, bytes(16)),
                bytes_sent=21,
                bytes_recv=11,
                packets_sent=45,
                packets_recv=25,
                errin=15,
                errout=25,
                dropin=14,
                dropout=24,
            ),
        )
        self.aliases[0]["alias"] = "Renamed VPN"
        self.assertIn("Renamed VPN", source.read())
        self.assertNotIn("Synthetic VPN", source.read())
        self.assertEqual(sum(call[0] == "table" for call in self.calls), 3)
        self.assertEqual(len(self.freed), 3)

    def test_up_requires_both_operational_and_admin_up(self):
        self.rows[0]["admin"] = 2
        self.rows[1]["oper"] = 5
        self.assertFalse(any(row["isup"] for row in self.source().read().values()))

    def test_activity_is_lazy_and_failure_or_no_demand_resets_rate_baseline(self):
        from activity_sensors import Activity

        source = self.source()
        activity = Activity(network_reader=source)
        self.assertIsNone(source._buffer)
        self.assertIsNone(source._get_addresses)
        with patch("activity_sensors.time.monotonic", return_value=10):
            self.assertEqual(activity.read(set())["provider_status"]["network"]["state"], "not_requested")
        self.assertFalse(self.calls)
        with patch("activity_sensors.time.monotonic", return_value=11):
            self.assertEqual(activity.read({"network"})["provider_status"]["network"]["state"], "warming_up")
        self.rows[0]["rx"] = 1_000_011
        with patch("activity_sensors.time.monotonic", return_value=12):
            self.assertEqual(activity.read({"network"})["net_download"], 1)
        self.table_error = 5
        with patch("activity_sensors.time.monotonic", return_value=13):
            failed = activity.read({"network"})
        self.assertEqual(failed["networks"], {})
        self.assertEqual(failed["provider_status"]["network"]["error"],
                         dict(api="GetIfTable2", reason="OSError", winerror=5))
        self.table_error = 0
        with patch("activity_sensors.time.monotonic", return_value=14):
            self.assertEqual(activity.read({"network"})["provider_status"]["network"]["state"], "warming_up")
        activity.read(set())
        with patch("activity_sensors.time.monotonic", return_value=15):
            self.assertEqual(activity.read({"network"})["provider_status"]["network"]["state"], "warming_up")

    def test_same_name_luid_or_guid_replacement_and_counter_reset_cannot_reuse_rates(self):
        from activity_sensors import Activity

        for change in ("luid", "guid", "counter_reset", "rename", "remove", "disconnect"):
            with self.subTest(change=change):
                self.aliases = [dict(index=7, luid=700, alias="Synthetic VPN")]
                self.rows = [dict(index=7, luid=700, oper=1, admin=1, rx=11, tx=21)]
                self.address_error = 0
                activity = Activity(network_reader=self.source())
                with patch("activity_sensors.time.monotonic", return_value=10):
                    activity.read({"network"})
                self.rows[0]["rx"] = 1_000_011
                with patch("activity_sensors.time.monotonic", return_value=11):
                    self.assertEqual(activity.read({"network"})["net_download"], 1)
                if change == "luid":
                    self.aliases[0]["luid"] = self.rows[0]["luid"] = 701
                elif change == "guid":
                    self.rows[0]["guid"] = 123
                elif change == "counter_reset":
                    self.rows[0]["rx"] = self.rows[0]["tx"] = 1
                elif change == "rename":
                    self.aliases[0]["alias"] = "Renamed VPN"
                else:
                    if change == "remove":
                        self.address_error = 232
                    else:
                        self.rows[0]["oper"] = 2
                    with patch("activity_sensors.time.monotonic", return_value=12):
                        self.assertEqual(activity.read({"network"})["provider_status"]["network"]["state"], "no_devices")
                    self.address_error, self.rows[0]["oper"] = 0, 1
                with patch("activity_sensors.time.monotonic", return_value=13):
                    fresh = activity.read({"network"})
                self.assertEqual(fresh["provider_status"]["network"]["state"], "warming_up")
                self.assertIsNone(fresh["net_download"])

    def test_ip_membership_order_preserves_initial_auto_selection_when_table_is_reversed(self):
        self.rows.reverse()
        result = self.source().read()
        self.assertEqual(list(result), [row["alias"] for row in self.aliases])
        # The first sample has no rate baseline; automatic selection breaks
        # equal-rate ties by this order, just like psutil's GAA iteration.
        active = {name: row for name, row in result.items() if row["isup"]}
        self.assertEqual(max(active, key=lambda _name: 0), "Synthetic VPN")
        import activity_sensors

        with (
            patch.object(activity_sensors, "_native_network", return_value=self.source()),
            patch(
                "activity_sensors.psutil.net_io_counters", side_effect=AssertionError("No fallback")
            ),
            patch(
                "activity_sensors.psutil.net_if_stats", side_effect=AssertionError("No fallback")
            ),
        ):
            activity = activity_sensors.Activity()
            for timestamp in (10, 11):
                with patch("activity_sensors.time.monotonic", return_value=timestamp):
                    self.assertEqual(activity.read({"network"})["network_active"], "Synthetic VPN")

    def test_luid_join_survives_ipv4_index_zero_and_never_uses_a_foreign_row(self):
        self.aliases[0]["index"] = 0
        self.assertTrue(self.source().read()["Synthetic VPN"]["isup"])
        self.rows[0]["luid"] = 701
        with self.assertRaises(self.module.NetworkSnapshotError) as caught:
            self.source().read()
        self.assertEqual(caught.exception.api, "GetIfTable2")
        self.assertEqual(caught.exception.reason, "InterfaceInventoryChanged")
        self.assertEqual(len(self.freed), 2)

    def test_no_interfaces_is_no_data_without_table_call(self):
        self.address_error = 232
        self.assertEqual(self.source().read(), {})
        self.assertFalse(self.freed)
        self.assertEqual(len(self.calls), 1)

    def test_native_api_codes_and_names_survive_without_slow_fallback(self):
        self.address_error = 5
        with self.assertRaises(self.module.NetworkSnapshotError) as caught:
            self.source().read()
        self.assertEqual(
            (caught.exception.api, caught.exception.winerror), ("GetAdaptersAddresses", 5)
        )
        self.assertFalse(self.freed)
        self.address_error, self.table_error = 0, 8
        with self.assertRaises(self.module.NetworkSnapshotError) as caught:
            self.source().read()
        self.assertEqual((caught.exception.api, caught.exception.winerror), ("GetIfTable2", 8))
        self.assertEqual(len(self.freed), 1)

    def test_bounded_growth_reuses_allocated_buffer(self):
        real = self.api.GetAdaptersAddresses.callback

        def grow(*args):
            if c.sizeof(args[3]) < 32768:
                c.cast(args[4], c.POINTER(c.c_uint32)).contents.value = 32768
                self.calls.append(("grow", c.sizeof(args[3])))
                return 111
            return real(*args)

        self.api.GetAdaptersAddresses.callback = grow
        source = self.source()
        source.read()
        source.read()
        self.assertEqual(sum(item[0] == "grow" for item in self.calls), 1)
        self.assertTrue(all(item[-1] == 32768 for item in self.calls if item[0] == "addresses"))

    def test_growth_limit_and_retry_limit_fail_explicitly(self):
        for returned in (2**31, 0, 200):
            with self.subTest(returned=returned):
                calls = []

                def overflow(*args):
                    calls.append(1)
                    c.cast(args[4], c.POINTER(c.c_uint32)).contents.value = returned
                    return 111

                self.api.GetAdaptersAddresses.callback = overflow
                with self.assertRaises(self.module.NetworkSnapshotError):
                    self.source().read()
                self.assertLessEqual(len(calls), 4)

    def test_bad_adapter_pointers_lengths_cycles_and_aliases_are_rejected(self):
        def unterminated(buffer, used, size):
            start = c.addressof(buffer)
            struct.pack_into("<Q", buffer, 72, start + used - 2)
            c.memmove(start + used - 2, b"A\0", 2)

        mutations = [
            lambda b, u, s: struct.pack_into("<Q", b, 8, c.addressof(b)),
            lambda b, u, s: struct.pack_into("<Q", b, 8, c.addressof(b) + u - 4),
            lambda b, u, s: struct.pack_into("<I", b, 0, 80),
            lambda b, u, s: struct.pack_into("<Q", b, 72, c.addressof(b) + u + 2),
            lambda b, u, s: struct.pack_into("<Q", b, 72, c.addressof(b) + 257),
            lambda b, u, s: struct.pack_into("<Q", b, 224, 0),
            lambda b, u, s: struct.pack_into("<Q", b, 256 + 224, 700),
            unterminated,
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.mutate_address = mutate
                with self.assertRaises(self.module.NetworkSnapshotError) as caught:
                    self.source().read()
                self.assertEqual(caught.exception.api, "GetAdaptersAddresses")

    def test_invalid_returned_adapter_size_is_not_followed(self):
        self.mutate_address = lambda b, u, s: setattr(
            c.cast(s, c.POINTER(c.c_uint32)).contents, "value", c.sizeof(b) + 1
        )
        with self.assertRaises(self.module.NetworkSnapshotError):
            self.source().read()
        self.assertFalse(self.freed)

    def test_table_count_is_bounded_and_memory_is_freed_on_validation_failure(self):
        self.mutate_table = lambda b, o: struct.pack_into("<I", b, 0, 5000)
        with self.assertRaises(self.module.NetworkSnapshotError):
            self.source().read()
        self.assertEqual(len(self.freed), 1)

    def test_unsupported_abi_does_not_call_native(self):
        with patch.object(self.module, "POINTER_BYTES", 4):
            with self.assertRaises(self.module.NetworkSnapshotError):
                self.source().read()
        self.assertFalse(self.calls)


class NativeActivityTests(unittest.TestCase):
    def test_disabled_default_backend_does_not_load_native_and_fallback_stays_fresh(self):
        import activity_sensors

        with (patch.dict(os.environ, {"DESKTOP_STATS_NETWORK_SNAPSHOT_DISABLED": "1"}),
              patch("ctypes.WinDLL", side_effect=AssertionError("No native API")),
              patch("activity_sensors.psutil.net_io_counters", return_value={}) as counters,
              patch("activity_sensors.psutil.net_if_stats", return_value={}) as states):
            activity = activity_sensors.Activity()
            self.assertFalse(activity._network_initialized)
            activity.read(set())
            counters.assert_not_called()
            activity.read({"network"})
            activity.read({"network"})
            self.assertEqual((counters.call_count, states.call_count), (2, 2))

    def test_bad_injected_reading_reports_local_safe_error(self):
        from activity_sensors import Activity

        source = SimpleNamespace(read=lambda: {"Adapter": dict(bytes_recv=float("nan"), bytes_sent=1, isup=True)})
        result = Activity(network_reader=source).read({"network"})
        self.assertEqual(result["provider_status"]["network"]["state"], "query_failed")
        self.assertEqual(result["provider_status"]["network"]["error"],
                         dict(api="Windows network snapshot", reason="OSError", winerror=13))

    def test_provider_error_cannot_override_api_or_reason_with_private_text(self):
        import activity_sensors

        error = OSError("PRIVATE_INTERFACE_SECRET")
        error.api, error.reason = "C:/PRIVATE/SECRET", "PRIVATE_ADAPTER_NAME"
        failure = activity_sensors._QueryFailure("psutil.net_io_counters", error)
        self.assertEqual(failure.facts, dict(api="psutil.net_io_counters", reason="OSError"))

    def test_native_inventory_change_publishes_observed_cause(self):
        self.assertIsNotNone(
            importlib.util.find_spec("network_snapshot"), "Bulk native network snapshot is missing"
        )
        module = importlib.import_module("network_snapshot")
        import activity_sensors

        error = module.NetworkSnapshotError("GetIfTable2", reason="InterfaceInventoryChanged")
        failure = activity_sensors._QueryFailure("GetIfTable2", error)
        self.assertEqual(failure.facts, dict(api="GetIfTable2", reason="InterfaceInventoryChanged"))

    def test_native_data_uses_current_states_and_failure_resets_rate_baseline(self):
        self.assertIsNotNone(
            importlib.util.find_spec("network_snapshot"), "Bulk native network snapshot is missing"
        )
        module = importlib.import_module("network_snapshot")
        import activity_sensors

        state = {"value": 100, "error": None}

        def read():
            if state["error"]:
                raise state["error"]
            return {
                "Synthetic VPN": dict(
                    isup=True, bytes_recv=state["value"], bytes_sent=2 * state["value"]
                )
            }

        with (
            patch.object(
                activity_sensors, "_native_network", return_value=SimpleNamespace(read=read)
            ),
            patch(
                "activity_sensors.psutil.net_io_counters",
                side_effect=AssertionError("No slow fallback"),
            ),
            patch(
                "activity_sensors.psutil.net_if_stats",
                side_effect=AssertionError("No slow fallback"),
            ),
        ):
            source = activity_sensors.Activity()
            with patch("activity_sensors.time.monotonic", return_value=10):
                self.assertEqual(
                    source.read({"network"})["provider_status"]["network"]["state"], "warming_up"
                )
            state["value"] = 1000100
            with patch("activity_sensors.time.monotonic", return_value=11):
                result = source.read({"network"})
                self.assertEqual((result["net_download"], result["net_upload"]), (1, 2))
            state["error"] = module.NetworkSnapshotError("GetIfTable2", 5)
            with patch("activity_sensors.time.monotonic", return_value=12):
                result = source.read({"network"})
                self.assertEqual(
                    result["provider_status"]["network"]["error"],
                    dict(api="GetIfTable2", reason="OSError", winerror=5),
                )
                self.assertEqual(result["networks"], {})
                self.assertIsNone(result["network_active"])
            state["error"] = None
            with patch("activity_sensors.time.monotonic", return_value=13):
                self.assertEqual(
                    source.read({"network"})["provider_status"]["network"]["state"], "warming_up"
                )


if __name__ == "__main__":
    unittest.main()
