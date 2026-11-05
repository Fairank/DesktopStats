"""Native ABI/buffer fixtures and Activity rates without loading Windows APIs."""

import ctypes as c
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import network_snapshot as net
from activity_sensors import Activity


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class FakeLibrary:
    def __init__(self):
        self.members = [(3, "Adapter A", "Synthetic A", 3003), (4, "适配器 B", "Synthetic B", 4004)]
        self.values = {3: (2**40, 2**41), 4: (1000, 2000)}
        self.oper, self.admin, self.guids = {}, {}, {}
        self.fault, self.errors = "", {}
        self.gaa_calls, self.table_calls, self.legacy_calls, self.frees = 0, 0, 0, []
        self.gaa_resize, self.legacy_resize = 0, 0
        self.flags = []
        self.gaa_sizes, self.legacy_sizes = [], []
        self.owned = []
        self.GetAdaptersAddresses = Function(self.gaa)
        self.GetIfTable2 = Function(self.table)
        self.FreeMibTable = Function(lambda pointer: self.frees.append(pointer.value))
        self.GetIfTable = Function(self.legacy)

    @staticmethod
    def size(pointer, value):
        c.cast(pointer, c.POINTER(net.U32))[0] = value

    @staticmethod
    def wide(row, field, text):
        data = text.encode("utf-16-le", errors="surrogatepass") + b"\0\0"
        c.memmove(c.addressof(row) + getattr(type(row), field).offset, data, len(data))

    def gaa(self, family, flags, reserved, buffer, size):
        self.gaa_calls += 1
        self.flags.append(flags)
        self.gaa_sizes.append(0 if buffer is None else len(buffer))
        if not self.members:
            return 232
        phase = "gaa_probe" if buffer is None else "gaa_data"
        if phase in self.errors:
            return self.errors[phase]
        if buffer is None:
            self.size(size, net.MAX_BUFFER + 1 if self.fault == "gaa_oversize" else 4096)
            return 111
        if self.gaa_resize:
            self.gaa_resize -= 1
            self.size(size, len(buffer) * 2)
            return 111
        required = len(self.members) * c.sizeof(net.AdapterPrefix) + sum(
            len(text.encode("utf-16-le", errors="surrogatepass")) + 2
            for _index, name, description, _luid in self.members for text in (name, description))
        if required > len(buffer):
            self.size(size, required)
            return 111
        start, end = c.addressof(buffer), c.addressof(buffer) + len(buffer)
        position = len(self.members) * c.sizeof(net.AdapterPrefix)
        for at, (index, name, description, luid) in enumerate(self.members):
            row = net.AdapterPrefix.from_buffer(buffer, at * c.sizeof(net.AdapterPrefix))
            row.length, row.index, row.luid = c.sizeof(net.AdapterPrefix), index, luid
            row.next = start + (at + 1) * c.sizeof(net.AdapterPrefix) if at + 1 < len(self.members) else None
            for field, text in (("friendly_name", name), ("description", description)):
                data = text.encode("utf-16-le", errors="surrogatepass") + b"\0\0"
                setattr(row, field, start + position)
                c.memmove(start + position, data, len(data))
                position += len(data)
        first = net.AdapterPrefix.from_buffer(buffer)
        if self.fault == "gaa_short_length":
            first.length = 8
        elif self.fault == "gaa_long_length":
            first.length = len(buffer) + 1
        elif self.fault == "gaa_cycle":
            first.next = start
        elif self.fault == "gaa_next_outside":
            first.next = end + 8
        elif self.fault == "gaa_next_unaligned":
            first.next = start + 1
        elif self.fault == "gaa_name_outside":
            first.friendly_name = end + 2
        elif self.fault == "gaa_description_outside":
            first.description = start - 2
        elif self.fault == "gaa_unterminated":
            first.friendly_name = end - 514
            c.memmove(first.friendly_name, b"A\0" * 257, 514)
        elif self.fault == "gaa_zero_luid":
            first.luid = 0
        self.size(size, 8 if self.fault == "gaa_short_used" else position)
        return 0

    def table(self, pointer):
        self.table_calls += 1
        if self.fault == "table_null":
            c.cast(pointer, c.POINTER(c.c_void_p))[0] = None
            return 0
        members = self.members[:-1] if self.fault == "table_missing" else self.members
        buffer = c.create_string_buffer(net.InterfaceTable.rows.offset + len(members) * c.sizeof(net.InterfaceRow))
        self.owned.append(buffer)
        net.U32.from_buffer(buffer).value = net.MAX_INTERFACES + 1 if self.fault == "table_count" else len(members)
        for at, (index, name, description, luid) in enumerate(members):
            row = net.InterfaceRow.from_buffer(buffer, net.InterfaceTable.rows.offset + at * c.sizeof(net.InterfaceRow))
            row.index = members[0][0] if self.fault == "table_duplicate" else index
            row.luid = luid + 1 if self.fault == "luid_mismatch" else luid
            row.guid.a = self.guids.get(index, index)
            self.wide(row, "alias", name + " changed" if self.fault == "alias_mismatch" else name)
            self.wide(row, "description", description)
            row.in_octets, row.out_octets = self.values[index]
            if self.fault == "table_unterminated":
                c.memmove(c.addressof(row) + net.InterfaceRow.alias.offset, b"A\0" * 257, 514)
        c.cast(pointer, c.POINTER(c.c_void_p))[0] = c.addressof(buffer)
        return self.errors.get("table", 0)

    def legacy(self, buffer, size, ordered):
        self.legacy_calls += 1
        self.legacy_sizes.append(0 if buffer is None else len(buffer))
        phase = "legacy_probe" if buffer is None else "legacy_data"
        if phase in self.errors:
            return self.errors[phase]
        members = self.members[:-1] if self.fault == "legacy_missing" else self.members
        required = net.LegacyTable.rows.offset + len(members) * c.sizeof(net.LegacyRow)
        if buffer is None:
            self.size(size, required)
            return 122
        if self.legacy_resize:
            self.legacy_resize -= 1
            self.size(size, len(buffer) + c.sizeof(net.LegacyRow))
            return 122
        if required > len(buffer):
            self.size(size, required)
            return 122
        net.U32.from_buffer(buffer).value = len(members)
        for at, (index, _name, description, _luid) in enumerate(members):
            row = net.LegacyRow.from_buffer(buffer, net.LegacyTable.rows.offset + at * c.sizeof(net.LegacyRow))
            row.index = members[0][0] if self.fault == "legacy_duplicate" else index
            row.oper, row.admin = self.oper.get(index, 5), self.admin.get(index, 1)
            text = members[0][2] if self.fault == "legacy_description_duplicate" else description
            raw = text.encode("ascii", errors="replace")
            row.description_length = 257 if self.fault == "legacy_description_length" else len(raw)
            c.memmove(c.addressof(row) + net.LegacyRow.description.offset, raw, len(raw))
        self.size(size, 2 if self.fault == "legacy_short_used" else required)
        return 0


def reader(fake, *, clock=None):
    return net.NetworkSnapshot(api_factory=lambda: net.NativeNetworkApi(library=fake), environ={}, clock=clock)


class SnapshotAbiTests(unittest.TestCase):
    def test_reviewed_x64_abi_and_pointer_types(self):
        self.assertEqual(c.sizeof(net.Guid), 16)
        self.assertEqual((c.sizeof(net.InterfaceRow), net.InterfaceTable.rows.offset), (1352, 8))
        self.assertEqual((net.InterfaceRow.in_octets.offset, net.InterfaceRow.out_octets.offset), (1208, 1280))
        self.assertEqual((c.sizeof(net.LegacyRow), net.LegacyTable.rows.offset, net.LegacyRow.oper.offset), (860, 4, 544))
        self.assertEqual((net.AdapterPrefix.friendly_name.offset, net.AdapterPrefix.luid.offset), (72, 224))
        self.assertIs(dict(net.AdapterPrefix._fields_)["friendly_name"], c.c_void_p)

    def test_lazy_construction_disabled_first_read_and_unavailable_are_session_fallbacks(self):
        factory, env = Mock(side_effect=AssertionError("No native initialization")), {}
        with patch("ctypes.WinDLL", side_effect=AssertionError("No DLL")), patch.object(threading.Thread, "start", side_effect=AssertionError("No worker")):
            snapshot = net.NetworkSnapshot(api_factory=factory, environ=env)
            factory.assert_not_called()
            env[net.DISABLED] = "1"
            self.assertIsNone(snapshot.read())
            env.clear()
            self.assertIsNone(snapshot.read())
        factory.assert_not_called()
        missing = Mock(side_effect=net.NativeUnavailable)
        snapshot = net.NetworkSnapshot(api_factory=missing, environ={})
        self.assertIsNone(snapshot.read())
        self.assertIsNone(snapshot.read())
        missing.assert_called_once()
        with self.assertRaises(net.NativeUnavailable):
            net.NativeNetworkApi(library=SimpleNamespace())

    def test_real_initialization_error_is_not_permanent_or_silently_fallback(self):
        fake = FakeLibrary()
        factory = Mock(side_effect=[net.SnapshotError(net.SNAPSHOT_API, 5), net.NativeNetworkApi(library=fake)])
        snapshot = net.NetworkSnapshot(api_factory=factory, environ={})
        with self.assertRaises(net.SnapshotError) as error:
            snapshot.read()
        self.assertEqual(error.exception.winerror, 5)
        self.assertEqual(snapshot.read()["Adapter A"].bytes_recv, 2**40)
        self.assertEqual(factory.call_count, 2)

    def test_names_order_uint64_and_exact_legacy_connected_operational_rule(self):
        fake = FakeLibrary()
        fake.oper = {3: 4, 4: 5}
        snapshot = reader(fake)
        result = snapshot.read()
        self.assertEqual(list(result), ["Adapter A", "适配器 B"])
        self.assertEqual((result["Adapter A"].bytes_recv, result["Adapter A"].bytes_sent), (2**40, 2**41))
        self.assertTrue(all(row.isup for row in result.values()))
        self.assertEqual(fake.flags, [15, 15])
        self.assertEqual(len(fake.frees), 1)
        fake.admin[3] = 2
        fake.oper[4] = 3
        self.assertFalse(any(row.isup for row in snapshot.read().values()))
        self.assertEqual(len(fake.frees), 2)

    def test_success_null_oversize_duplicate_parse_and_missing_join_are_os_errors(self):
        cases = {
            "gaa_oversize": "GetAdaptersAddresses", "gaa_short_used": "GetAdaptersAddresses",
            "gaa_short_length": "GetAdaptersAddresses", "gaa_long_length": "GetAdaptersAddresses",
            "gaa_cycle": "GetAdaptersAddresses", "gaa_next_outside": "GetAdaptersAddresses",
            "gaa_next_unaligned": "GetAdaptersAddresses", "gaa_name_outside": "GetAdaptersAddresses",
            "gaa_description_outside": "GetAdaptersAddresses", "gaa_unterminated": "GetAdaptersAddresses",
            "gaa_zero_luid": "GetAdaptersAddresses", "table_null": "GetIfTable2",
            "table_count": "GetIfTable2", "table_duplicate": "GetIfTable2",
            "table_unterminated": "GetIfTable2", "legacy_short_used": "GetIfTable",
            "legacy_duplicate": "GetIfTable", "legacy_description_length": "GetIfTable",
            "table_missing": net.SNAPSHOT_API, "legacy_missing": net.SNAPSHOT_API,
            "luid_mismatch": net.SNAPSHOT_API,
        }
        for fault, api in cases.items():
            with self.subTest(fault=fault):
                fake = FakeLibrary()
                fake.fault = fault
                with self.assertRaises(net.SnapshotError) as error:
                    reader(fake).read()
                self.assertEqual((error.exception.api, error.exception.winerror), (api, 13))
                expected_free = 0 if fault.startswith("gaa_") or fault == "table_null" else 1
                self.assertEqual(len(fake.frees), expected_free)

    def test_duplicate_gaa_index_is_invalid_not_an_ambiguity_fallback(self):
        fake = FakeLibrary()
        fake.members[1] = (3, "Other name", "Other description", 3003)
        with self.assertRaises(net.SnapshotError):
            reader(fake).read()
        self.assertEqual(fake.table_calls, 0)

    def test_member_limit_before_dereferencing_more_nodes(self):
        with patch.object(net, "MAX_INTERFACES", 1):
            with self.assertRaises(net.SnapshotError):
                reader(FakeLibrary()).read()

    def test_api_return_codes_and_success_owned_buffer_release(self):
        for stage, api, code in (("gaa_probe", "GetAdaptersAddresses", 5), ("gaa_data", "GetAdaptersAddresses", 87),
                                 ("table", "GetIfTable2", 50), ("legacy_probe", "GetIfTable", 5),
                                 ("legacy_data", "GetIfTable", 87)):
            with self.subTest(stage=stage):
                fake = FakeLibrary()
                fake.errors[stage] = code
                with self.assertRaises(net.SnapshotError) as error:
                    reader(fake).read()
                self.assertEqual((error.exception.api, error.exception.winerror), (api, code))
                # An error output from Table2 is not an owned successful buffer.
                self.assertEqual(len(fake.frees), 1 if stage.startswith("legacy") else 0)

    def test_resize_retry_is_bounded_and_empty_adapter_result_is_success(self):
        fake = FakeLibrary()
        fake.gaa_resize = fake.legacy_resize = 1
        self.assertEqual(len(reader(fake).read()), 2)
        self.assertEqual((fake.gaa_calls, fake.legacy_calls, len(fake.frees)), (3, 3, 1))
        for attr, code in (("gaa_resize", 111), ("legacy_resize", 122)):
            fake = FakeLibrary()
            setattr(fake, attr, 10)
            with self.assertRaises(net.SnapshotError) as error:
                reader(fake).read()
            self.assertEqual(error.exception.winerror, code)
        fake = FakeLibrary()
        fake.members = []
        self.assertEqual(reader(fake).read(), {})
        self.assertEqual(fake.table_calls, 0)

    def test_successful_size_hints_skip_only_probes_and_read_fresh_topology_counters_and_state(self):
        fake = FakeLibrary()
        snapshot = reader(fake)
        first = snapshot.read()
        fake.values[3] = (2**40 + 1234, 2**41 + 5678)
        fake.admin[3] = 2
        second = snapshot.read()
        self.assertEqual(fake.gaa_sizes.count(0), 1)
        self.assertEqual(fake.legacy_sizes.count(0), 1)
        self.assertEqual((fake.gaa_calls, fake.legacy_calls, fake.table_calls), (3, 3, 2))
        self.assertEqual(second["Adapter A"].bytes_recv, first["Adapter A"].bytes_recv + 1234)
        self.assertFalse(second["Adapter A"].isup)

        fake.members.append((5, "New adapter", "New description", 5005))
        fake.values[5] = (10, 20)
        third = snapshot.read()
        self.assertEqual(list(third), ["Adapter A", "适配器 B", "New adapter"])
        self.assertEqual((fake.gaa_calls, fake.legacy_calls, fake.table_calls), (5, 5, 3))
        self.assertGreater(fake.gaa_sizes[-1], fake.gaa_sizes[-2])
        self.assertGreater(fake.legacy_sizes[-1], fake.legacy_sizes[-2])
        self.assertEqual(fake.gaa_sizes.count(0), 1)
        self.assertEqual(fake.legacy_sizes.count(0), 1)

        fake.members = []
        self.assertEqual(snapshot.read(), {})
        self.assertEqual(fake.table_calls, 3)
        fake.members = [(5, "Renamed adapter", "New description", 5005)]
        self.assertEqual(list(snapshot.read()), ["Renamed adapter"])
        self.assertEqual(fake.table_calls, 4)
        self.assertEqual(len(fake.frees), 4)

    def test_cached_size_queries_keep_error_and_bounded_resize_contracts(self):
        for phase, code, api in (("gaa_data", 5, "GetAdaptersAddresses"),
                                 ("legacy_data", 87, "GetIfTable")):
            with self.subTest(phase=phase):
                fake = FakeLibrary()
                snapshot = reader(fake)
                snapshot.read()
                fake.errors[phase] = code
                with self.assertRaises(net.SnapshotError) as error:
                    snapshot.read()
                self.assertEqual((error.exception.api, error.exception.winerror), (api, code))
                fake.errors.clear()
                self.assertEqual(len(snapshot.read()), 2)
                self.assertEqual(fake.gaa_sizes.count(0), 1)
                self.assertEqual(fake.legacy_sizes.count(0), 1)
        for attr, code in (("gaa_resize", 111), ("legacy_resize", 122)):
            with self.subTest(attr=attr):
                fake = FakeLibrary()
                snapshot = reader(fake)
                snapshot.read()
                setattr(fake, attr, 10)
                with self.assertRaises(net.SnapshotError) as error:
                    snapshot.read()
                self.assertEqual(error.exception.winerror, code)
                self.assertLessEqual(fake.gaa_calls, 5)
                self.assertLessEqual(fake.legacy_calls, 5)

    def test_cached_capacity_does_not_allow_invalid_growth_sizes_or_poison_recovery(self):
        for method, code, position, api_name in (("gaa", 111, 4, "GetAdaptersAddresses"),
                                                ("legacy", 122, 1, "GetIfTable")):
            for invalid_size in (0, 1, net.MAX_BUFFER + 1):
                with self.subTest(method=method, invalid_size=invalid_size):
                    fake = FakeLibrary()
                    api = net.NativeNetworkApi(library=fake)
                    api.read()
                    original = getattr(api, method)

                    def invalid_growth(*args):
                        FakeLibrary.size(args[position], invalid_size)
                        return code

                    setattr(api, method, Function(invalid_growth))
                    with self.assertRaises(net.SnapshotError) as error:
                        api.read()
                    self.assertEqual((error.exception.api, error.exception.winerror), (api_name, 13))
                    setattr(api, method, original)
                    self.assertEqual(len(api.read()), 2)

    def test_identity_ambiguity_falls_back_before_unnecessary_queries_and_retries_after_60s(self):
        for mode in ("description", "alias", "non_ascii", "alias_mismatch", "legacy_description_duplicate"):
            with self.subTest(mode=mode):
                fake, now = FakeLibrary(), [0.0]
                if mode == "description":
                    fake.members[1] = (4, "Other", "Synthetic A", 4004)
                elif mode == "alias":
                    fake.members[1] = (4, "Adapter A", "Synthetic B", 4004)
                elif mode == "non_ascii":
                    fake.members[1] = (4, "Other", "非ASCII描述", 4004)
                else:
                    fake.fault = mode
                snapshot = reader(fake, clock=lambda: now[0])
                self.assertIsNone(snapshot.read())
                calls = fake.gaa_calls
                if mode in ("description", "alias", "non_ascii"):
                    self.assertEqual(fake.table_calls, 0)
                self.assertIsNone(snapshot.read())
                self.assertEqual(fake.gaa_calls, calls)
                now[0] = 60
                self.assertIsNone(snapshot.read())
                self.assertGreater(fake.gaa_calls, calls)


class ActivityNativeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fake, self.now = FakeLibrary(), 10.0
        self.snapshot = reader(self.fake, clock=lambda: self.now)
        self.activity = Activity(network_reader=self.snapshot)
        self.clock = patch("activity_sensors.time.monotonic", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.old_io = self.enterContext(patch("activity_sensors.psutil.net_io_counters", side_effect=AssertionError("No old query")))
        self.old_status = self.enterContext(patch("activity_sensors.psutil.net_if_stats", side_effect=AssertionError("No old query")))

    def sample(self):
        self.now += 2
        return self.activity.read({"network"})

    def test_no_demand_is_lazy_and_failure_clears_rates_with_specific_diagnostics(self):
        idle = self.activity.read(set())
        self.assertEqual(self.fake.gaa_calls, 0)
        self.assertEqual(idle["provider_status"]["network"], dict(state="not_requested", requested=False))
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "warming_up")
        self.fake.values[3] = (2**40 + 2_000_000, 2**41 + 4_000_000)
        self.assertEqual(self.sample()["net_download"], 1)
        self.fake.errors["table"] = 5
        failed = self.sample()
        self.assertEqual(failed["networks"], {})
        self.assertIsNone(failed["network_active"])
        self.assertNotIn("net_download", failed)
        self.assertEqual(failed["provider_status"]["network"]["error"],
                         dict(api="GetIfTable2", reason="OSError", errno=5, winerror=5))
        self.fake.errors.clear()
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "warming_up")
        self.activity.read(set())
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "warming_up")
        self.old_io.assert_not_called()
        self.old_status.assert_not_called()

    def test_remove_rename_disconnect_counter_reset_and_same_name_replacement_rewarm(self):
        self.fake.members = [self.fake.members[0]]
        for change in ("counter_reset", "rename", "remove", "disconnect", "luid", "guid"):
            with self.subTest(change=change):
                self.fake.members = [(3, "Adapter A", "Synthetic A", 3003)]
                self.fake.values[3] = (5000, 6000)
                self.fake.oper.clear()
                self.fake.guids.clear()
                self.activity = Activity(network_reader=self.snapshot)
                self.sample()
                self.fake.values[3] = (2_005_000, 2_006_000)
                self.assertEqual(self.sample()["net_download"], 1)
                if change == "counter_reset":
                    self.fake.values[3] = (1, 2)
                elif change == "rename":
                    self.fake.members = [(3, "Renamed", "Synthetic A", 3003)]
                elif change in ("remove", "disconnect"):
                    if change == "remove":
                        self.fake.members = []
                    else:
                        self.fake.oper[3] = 0
                    self.assertEqual(self.sample()["provider_status"]["network"]["state"], "no_devices")
                    self.fake.members = [(3, "Adapter A", "Synthetic A", 3003)]
                    self.fake.oper.clear()
                elif change == "luid":
                    self.fake.members = [(3, "Adapter A", "Synthetic A", 9009)]
                    self.fake.values[3] = (2**50, 2**51)
                else:
                    self.fake.guids[3] = 9009
                    self.fake.values[3] = (2**50, 2**51)
                reading = self.sample()
                self.assertEqual(reading["provider_status"]["network"]["state"], "warming_up")
                self.assertIsNone(reading["net_download"])

    def test_ambiguity_cooldown_keeps_fallback_live_and_backend_switch_rewarms(self):
        self.sample()
        self.fake.fault = "alias_mismatch"
        self.old_io.side_effect = None
        self.old_status.side_effect = None
        self.old_io.return_value = {"Adapter A": SimpleNamespace(bytes_recv=100, bytes_sent=200)}
        self.old_status.return_value = {"Adapter A": SimpleNamespace(isup=True)}
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "warming_up")
        native_calls = self.fake.gaa_calls
        self.old_io.return_value = {"Adapter A": SimpleNamespace(bytes_recv=2_000_100, bytes_sent=4_000_200)}
        self.assertEqual(self.sample()["net_upload"], 2)
        self.assertEqual(self.fake.gaa_calls, native_calls)
        self.old_status.return_value = {"Adapter A": SimpleNamespace(isup=False)}
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "no_devices")
        self.assertEqual(self.old_io.call_count, 3)
        self.fake.fault = ""
        self.now += 60
        self.assertEqual(self.sample()["provider_status"]["network"]["state"], "warming_up")

    def test_bad_injected_reading_is_a_local_os_error_instead_of_sampler_failure(self):
        bad = SimpleNamespace(read=lambda: {"Adapter": SimpleNamespace(bytes_recv=float("nan"), bytes_sent=10, isup=True)})
        result = Activity(network_reader=bad).read({"network"})
        self.assertEqual(result["provider_status"]["network"]["state"], "query_failed")
        self.assertEqual(result["provider_status"]["network"]["error"]["api"], net.SNAPSHOT_API)
        self.assertEqual(result["provider_status"]["network"]["error"]["winerror"], 13)


if __name__ == "__main__":
    unittest.main()
