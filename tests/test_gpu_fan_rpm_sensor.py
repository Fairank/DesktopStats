"""Physical tachometer demand/caching/identity boundaries; no real driver calls."""
import ctypes as c
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DESKTOP_STATS_DATA", str(
    Path(__file__).resolve().parents[1] / "qa-private/gpu-fan-rpm-test-data"))

import gpu_fan_sensor as fan
import sensors


def fail_io(*args, **kwargs):
    raise AssertionError("Unexpected driver, process or worker operation")


class Function:
    def __init__(self, function): self.function = function
    def __call__(self, *args): return self.function(*args)


class FakeNvapi:
    def __init__(self):
        self.mapping = {(1, 0): 901, (2, 0): 902}
        self.values = {901: 1400, 902: 0}
        self.reads, self.enumerations, self.closes = [], 0, 0
        self.discovery_error = None

    def devices(self):
        self.enumerations += 1
        if self.discovery_error:
            raise self.discovery_error
        return dict(self.mapping)

    def rpm(self, handle):
        self.reads.append(handle)
        value = self.values[handle]
        if isinstance(value, Exception):
            raise value
        return value

    def close(self): self.closes += 1


class FakeNvml:
    def __init__(self):
        self.calls = []
        self.pci = {11: (0, 1, 0), 22: (0, 2, 0)}
        self.pci_error = 0
        for api in ("nvmlDeviceGetName", "nvmlDeviceGetTemperature", "nvmlDeviceGetUtilizationRates",
                    "nvmlDeviceGetPowerUsage", "nvmlDeviceGetMemoryInfo", "nvmlDeviceGetClockInfo",
                    "nvmlDeviceGetFanSpeed", "nvmlDeviceGetPciInfo_v3"):
            setattr(self, api, Function(lambda *args, api=api: self.query(api, *args)))
        self.nvmlShutdown = Function(lambda: self.calls.append(("nvmlShutdown", None)) or 0)

    def query(self, api, handle, *args):
        token = sensors.Nvidia._handle_token(handle)
        self.calls.append((api, token))
        if api == "nvmlDeviceGetPciInfo_v3":
            if self.pci_error:
                return self.pci_error
            args[0]._obj.domain, args[0]._obj.bus, args[0]._obj.device = self.pci[token]
        elif api == "nvmlDeviceGetName":
            args[0].value = b"Synthetic NVIDIA GPU"
        elif api == "nvmlDeviceGetMemoryInfo":
            args[0]._obj.total, args[0]._obj.used = 8 * 1024**3, 1024**3
        elif api == "nvmlDeviceGetUtilizationRates":
            args[0]._obj.gpu = 23
        else:
            args[-1]._obj.value = 50
        return 0


def nvml_source():
    source = sensors.Nvidia.__new__(sensors.Nvidia)
    source.lib, source.name = FakeNvml(), "Synthetic GPU"
    source.handles, source.device_status, source._device_retry_at = {"0": 11, "1": 22}, {}, {}
    return source


class NoHardwareCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ("sensors.c.CDLL", "sensors.c.WinDLL", "subprocess.Popen", "threading.Thread.start"):
            self.stack.enter_context(patch(target, side_effect=fail_io))
        self.now = 100.0
        self.stack.enter_context(patch("gpu_fan_sensor.time.monotonic", side_effect=lambda: self.now))
        self.stack.enter_context(patch("gpu_fan_sensor.time.time", side_effect=lambda: self.now + 1000))


class DemandTests(NoHardwareCase):
    def config(self, style="solid", effect="auto", metric="gpu_usage", target=None):
        prefs = dict(icon_effect=effect)
        if target is not None:
            prefs["gpu_target"] = target
        return dict(top_bar=dict(enabled=True, hardware_icon_style=style,
                                 items=[dict(metric=metric, prefs=prefs)]))

    def test_only_enabled_modern_automatic_gpu_icons_request_selected_target(self):
        for style in ("solid", "miniature", "soft", "cartoon", "sketch"):
            self.assertEqual(sensors.gpu_fan_rpm_targets(self.config(style)), {"0"})
            self.assertEqual(sensors.gpu_fan_rpm_targets(self.config(style, target="1")), {"1"})
        for style in ("classic", "outline"):
            self.assertFalse(sensors.gpu_fan_rpm_targets(self.config(style)))
        for effect in ("off", "spin", "heat", "flow"):
            self.assertFalse(sensors.gpu_fan_rpm_targets(self.config(effect=effect)))
        for metric in ("cpu_usage", "ram_percent", "gpu_fan_rpm", "external_temperature", "gpu_temp",
                       "gpu_power", "gpu_clock", "gpu_memory_clock", "gpu_fan_percent", "vram_percent"):
            self.assertFalse(sensors.gpu_fan_rpm_targets(self.config(metric=metric)))
        config = self.config()
        config["top_bar"]["enabled"] = False
        self.assertFalse(sensors.gpu_fan_rpm_targets(config))

    def test_only_primary_visible_gpu_glyph_requests_no_vram_or_group_child_demand(self):
        config = self.config(metric="vram_percent", target="1")
        config["top_bar"]["items"] += [dict(metric="cpu_usage", prefs=dict(
            icon_effect="auto", metrics=["gpu_power", "gpu_temp"], gpu_target="1"))]
        self.assertFalse(sensors.gpu_fan_rpm_targets(config))
        config["top_bar"]["items"].append(dict(metric="gpu_usage", prefs=dict(
            icon_effect="auto", metrics=["cpu_usage"], gpu_target="1")))
        self.assertEqual(sensors.gpu_fan_rpm_targets(config), {"1"})
        config["top_bar"]["items"].append(dict(metric="gpu_usage", prefs=dict(
            icon_effect="auto", gpu_target="1")))
        self.assertEqual(sensors.gpu_fan_rpm_targets(config), {"1"})
        for bad in ("16", "GPU 1", "-1", 1):
            self.assertFalse(sensors.gpu_fan_rpm_targets(self.config(target=bad)))


class TachometerTests(NoHardwareCase):
    def setUp(self):
        super().setUp()
        self.api = FakeNvapi()
        self.factory = Mock(return_value=self.api)
        self.tach = fan.Tachometer(self.factory)
        self.addCleanup(self.tach.close)

    def test_lazy_initialization_unique_pci_join_and_single_card_channel(self):
        self.factory.assert_not_called()
        self.assertEqual(self.tach.read((0, 2, 0))["rpm"], 0)
        self.assertEqual(self.api.reads, [902])  # Deliberately not enumeration index 0/1.
        self.assertEqual(self.tach.read((0, 1, 0))["rpm"], 1400)
        self.assertEqual(self.api.enumerations, 1)
        self.factory.assert_called_once_with()

    def test_one_second_cache_preserves_timestamp_and_returns_fresh_diagnostics(self):
        original = self.tach.read((0, 1, 0))
        stamp = original["status"]["timestamp"]
        original["status"]["semantics"] = "changed by caller"
        self.now += .999
        cached = self.tach.read((0, 1, 0))
        self.assertEqual(cached["status"]["semantics"], "measured")
        self.assertEqual(cached["status"]["timestamp"], stamp)
        self.assertEqual(self.api.reads, [901])
        self.now += .001
        self.tach.read((0, 1, 0))
        self.assertEqual(self.api.reads, [901, 901])

    def test_transient_failure_invalidates_old_value_and_retries_only_after_backoff(self):
        self.assertEqual(self.tach.read((0, 1, 0))["rpm"], 1400)
        self.now += 1
        self.api.values[901] = fan.NvapiError(fan.API, -1)
        failed = self.tach.read((0, 1, 0))
        self.assertIsNone(failed["rpm"])
        self.assertEqual(failed["status"]["status_code"], -1)
        self.api.values[901] = 1800
        self.now += 4.999
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.assertEqual(len(self.api.reads), 2)
        self.now += .001
        self.assertEqual(self.tach.read((0, 1, 0))["rpm"], 1800)

    def test_unsupported_channel_is_not_retried_and_does_not_poison_other_gpu(self):
        self.api.values[901] = fan.NvapiError(fan.API, -104)
        self.assertEqual(self.tach.read((0, 1, 0))["status"]["state"], "unsupported")
        self.now += 100
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.assertEqual(self.api.reads, [901])
        self.assertEqual(self.tach.read((0, 2, 0))["rpm"], 0)

    def test_invalidated_handle_discards_all_native_handles_and_reenumerates_after_backoff(self):
        self.tach.read((0, 1, 0))
        self.now += 1
        self.api.values[901] = fan.NvapiError(fan.API, -10)
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.assertIsNone(self.tach.read((0, 2, 0))["rpm"])
        self.assertEqual(self.api.enumerations, 1)
        self.api.mapping[(1, 0)] = 999
        self.api.values[999] = 1900
        self.now += 5
        self.assertEqual(self.tach.read((0, 1, 0))["rpm"], 1900)
        self.assertEqual(self.api.enumerations, 2)

    def test_missing_ambiguous_and_nonzero_domain_are_never_assigned_another_gpu(self):
        for bad in (None, (0, 0), (1, 1, 0), (0, 256, 0), (0, 1, 32), (0, True, 0)):
            self.assertIsNone(self.tach.read(bad)["rpm"])
        self.factory.assert_not_called()
        self.api.mapping[(1, 0)] = None
        for identity in ((0, 1, 0), (0, 3, 0)):
            self.assertEqual(self.tach.read(identity)["status"]["state"], "identity_unavailable")
        self.assertFalse(self.api.reads)

    def test_optional_library_and_entrypoint_failures_are_nonfatal_and_cached(self):
        for error, state in ((OSError("missing"), "dll_unavailable"),
                             (AttributeError("missing"), "entrypoint_missing")):
            factory = Mock(side_effect=error)
            tach = fan.Tachometer(factory)
            self.assertEqual(tach.read((0, 1, 0))["status"]["state"], state)
            self.now += 100
            tach.read((0, 1, 0))
            factory.assert_called_once_with()
            tach.close()

    def test_discovery_error_backs_off_and_uint_sentinel_is_not_a_reading(self):
        self.api.discovery_error = OSError("transient enumeration error")
        self.assertEqual(self.tach.read((0, 1, 0))["status"]["state"], "query_failed")
        self.api.discovery_error = None
        self.now += 4
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.now += 1
        self.api.values[901] = 0xFFFFFFFF
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.assertEqual(self.api.enumerations, 2)

    def test_cache_bound_and_close_prevent_further_driver_calls(self):
        self.api.mapping = {(index, 0): index + 100 for index in range(17)}
        self.api.values = {index + 100: index for index in range(17)}
        for index in range(17):
            self.tach.read((0, index, 0))
        self.assertEqual(len(self.tach._cache), 16)
        self.tach.close()
        self.assertEqual(self.api.closes, 1)
        self.assertEqual(self.tach.read((0, 1, 0))["status"]["state"], "closed")
        self.assertFalse(self.tach._cache)


class NvidiaIntegrationTests(NoHardwareCase):
    def setUp(self):
        super().setUp()
        self.source = nvml_source()
        self.api = FakeNvapi()
        self.tach = fan.Tachometer(lambda: self.api)
        self.factory = self.stack.enter_context(patch("sensors.GpuTachometer", return_value=self.tach))
        self.addCleanup(self.source.close)

    def pci_calls(self):
        return [handle for api, handle in self.source.lib.calls if api == "nvmlDeviceGetPciInfo_v3"]

    def test_default_read_and_direct_read_device_do_not_add_queries(self):
        self.source.read_device(11)
        data = self.source.read()
        self.assertFalse(self.pci_calls())
        self.factory.assert_not_called()
        self.assertNotIn("gpu_fan_rpm", data["gpus"]["0"])
        self.assertEqual(sum(api == "nvmlDeviceGetFanSpeed" for api, _ in self.source.lib.calls), 3)

    def test_selected_gpu_metadata_zero_and_no_flat_chassis_overwrite(self):
        self.source.request_fan_rpm({"1"})
        data = self.source.read()
        self.assertEqual(self.pci_calls(), [22])
        self.assertNotIn("gpu_fan_rpm", data["gpus"]["0"])
        row = data["gpus"]["1"]
        self.assertEqual(row["gpu_fan_rpm"], 0)
        self.assertEqual(row["gpu_fan_rpm_semantics"], "measured")
        self.assertEqual(row["gpu_fan_rpm_scope"], "card")
        self.assertEqual(row["gpu_fan_rpm_timestamp"], 1100)
        self.assertEqual(row["gpu_fans"], [])
        self.assertEqual(row["channel_status"]["gpu_fan_rpm"]["state"], "available")
        self.source.request_fan_rpm({"0"})
        data = self.source.read()
        self.assertEqual(data["gpus"]["0"]["gpu_fan_rpm"], 1400)
        for key in ("gpu_fan_rpm", "gpu_fans", "gpu_fan_rpm_source", "gpu_fan_rpm_timestamp"):
            self.assertNotIn(key, data)
        self.assertNotIn("gpu_fan_rpm", data["channel_status"])

    def test_demand_off_is_immediate_and_cache_is_one_second_per_gpu(self):
        self.source.request_fan_rpm({"1"})
        self.source.read()
        for _ in range(10):
            self.now += .09
            self.source.read()
        self.assertEqual(self.api.reads, [902])
        self.assertEqual(self.pci_calls(), [22])
        self.source.request_fan_rpm(())
        self.now += 10
        self.assertNotIn("gpu_fans", self.source.read()["gpus"]["1"])
        self.assertEqual(self.api.reads, [902])

    def test_nvml_pci_missing_entrypoint_is_cached_without_initializing_nvapi(self):
        del self.source.lib.nvmlDeviceGetPciInfo_v3
        self.source.request_fan_rpm({"0"})
        for _ in range(3):
            data = self.source.read()
            self.now += 100
            self.assertEqual(data["gpus"]["0"]["channel_status"]["gpu_fan_rpm"]["state"],
                             "entrypoint_missing")
        self.factory.assert_not_called()

    def test_pci_failure_backs_off_and_other_native_fields_remain_available(self):
        self.source.lib.pci_error = 999
        self.source.request_fan_rpm({"0"})
        row = self.source.read()["gpus"]["0"]
        self.assertEqual(row["gpu_usage"], 23)
        self.assertNotIn("gpu_fan_rpm", row)
        self.source.lib.pci_error = 0
        self.now += 4
        self.source.read()
        self.assertEqual(self.pci_calls(), [11])
        self.now += 1
        self.assertEqual(self.source.read()["gpus"]["0"]["gpu_fan_rpm"], 1400)
        self.assertEqual(self.pci_calls(), [11, 11])

    def test_removed_or_replaced_handle_invalidates_identity_and_cached_value(self):
        self.source.request_fan_rpm({"0"})
        self.source.read()
        self.source.lib.pci[33] = (0, 2, 0)
        self.source.handles["0"] = 33
        self.assertEqual(self.source.read()["gpus"]["0"]["gpu_fan_rpm"], 0)
        self.assertEqual(self.api.enumerations, 2)
        del self.source.handles["0"]
        self.source.read()
        self.assertFalse(self.source._fan_pci)

    def test_nonzero_pci_domain_refuses_match_and_close_clears_owner_caches(self):
        self.source.lib.pci[11] = (1, 1, 0)
        self.source.request_fan_rpm({"0"})
        self.assertNotIn("gpu_fan_rpm", self.source.read()["gpus"]["0"])
        self.factory.assert_not_called()
        self.source.close()
        self.assertFalse(self.source._fan_pci)
        self.assertFalse(self.source._fan_targets)

    def test_failed_nvapi_unload_retains_its_dll_owner_and_retries_without_double_nvml_shutdown(self):
        self.source.request_fan_rpm({"0"})
        self.source.read()
        self.api.close = Mock(side_effect=[RuntimeError("temporary unload failure"), None])
        with self.assertRaises(RuntimeError):
            self.source.close()
        self.assertIs(self.source._fan_tachometer, self.tach)
        self.assertIs(self.tach._backend, self.api)
        self.assertEqual(self.tach.read((0, 1, 0))["status"]["state"], "closed")
        self.source.close()
        self.assertIsNone(self.source._fan_tachometer)
        self.assertEqual(self.api.close.call_count, 2)
        self.assertEqual(sum(api == "nvmlShutdown" for api, _ in self.source.lib.calls), 1)


class NativeContractTests(NoHardwareCase):
    def test_native_enumeration_rejects_duplicate_null_and_invalid_addresses(self):
        backend = fan._Nvapi.__new__(fan._Nvapi)
        descriptors = [(123, 1, 0), (456, 1, 0)]
        def call(api, *args):
            if api == "NvAPI_EnumPhysicalGPUs":
                args[1]._obj.value = len(descriptors)
                for index, (handle, _, _) in enumerate(descriptors):
                    args[0][index] = handle
            else:
                descriptor = next(row for row in descriptors if row[0] == args[0])
                args[1]._obj.value = descriptor[1 if api.endswith("BusId") else 2]
        backend._call = call
        self.assertEqual(backend.devices(), {(1, 0): None})
        for invalid in ((0, 1, 0), (123, 256, 0), (123, 1, 32)):
            descriptors[:] = [invalid]
            with self.assertRaises(ValueError):
                backend.devices()

    def test_ctypes_layout_and_readonly_query_interface_whitelist(self):
        self.assertEqual(c.sizeof(sensors.NvidiaPciInfo), 68)
        self.assertEqual(sensors.NvidiaPciInfo.domain.offset, 16)
        self.assertEqual(sensors.NvidiaPciInfo.busId.offset, 36)
        callbacks, calls = [], []
        uint_pointer = c.POINTER(c.c_uint32)
        def bind(code, arguments, implementation):
            callback = c.CFUNCTYPE(c.c_int, *arguments)(implementation)
            callbacks.append(callback)  # Strong lifetime for fake native function pointers.
            return code, c.cast(callback, c.c_void_p).value
        def enumerate_gpus(handles, count):
            handles[0], count[0] = 123, 1
            return 0
        def scalar(value):
            return lambda handle, output: output.__setitem__(0, value) or 0
        functions = dict((
            bind(0x0150E828, (), lambda: calls.append("init") or 0),
            bind(0xD22BDD7E, (), lambda: calls.append("unload") or 0),
            bind(0xE5AC921F, (c.POINTER(c.c_void_p), uint_pointer), enumerate_gpus),
            bind(0x1BE0B8E5, (c.c_void_p, uint_pointer), scalar(2)),
            bind(0x2A0A350F, (c.c_void_p, uint_pointer), scalar(0)),
            bind(0x5F608315, (c.c_void_p, uint_pointer), scalar(1700)),
        ))
        queried = []
        dll = SimpleNamespace(nvapi_QueryInterface=Function(
            lambda code: queried.append(code) or functions.get(code)))
        with patch("gpu_fan_sensor.c.CDLL", return_value=dll) as load:
            backend = fan._Nvapi()
        self.assertEqual(Path(load.call_args.args[0]).parent.name.casefold(), "system32")
        self.assertEqual(set(queried), set(functions) | {0x35AED5E8})
        self.assertEqual(backend.devices(), {(2, 0): 123})
        self.assertEqual(backend.rpm(123), 1700)
        backend.close()
        backend.close()
        self.assertEqual(calls, ["init", "unload"])


class CurrentDriverFanTests(NoHardwareCase):
    def backend(self, rows=((7, 1200), (19, 1800))):
        backend = fan._Nvapi.__new__(fan._Nvapi)
        backend._coolers_unavailable = set()
        backend._functions = {fan.CURRENT_API: True}
        self.rows, self.calls, self.private_error = rows, [], None
        def call(api, *args):
            self.calls.append(api)
            if api == fan.CURRENT_API:
                if self.private_error:
                    raise self.private_error
                status = args[1]._obj
                self.assertEqual(status.version, 0x106A8)
                self.assertFalse(status.count)
                self.assertEqual(list(status.reserved), [0] * 4)
                status.count = len(self.rows)
                for index, (cooler_id, rpm) in enumerate(self.rows[:32]):
                    status.items[index].cooler_id, status.items[index].current_rpm = cooler_id, rpm
            elif api == fan.API:
                args[1]._obj.value = 900
        backend._call = call
        return backend

    def test_private_v1_abi_matches_lhm_and_one_group_read_returns_mean_and_driver_ids(self):
        self.assertEqual(c.sizeof(fan.FanCoolerStatusItem), 52)
        self.assertEqual(fan.FanCoolerStatusItem.current_rpm.offset, 4)
        self.assertEqual(c.sizeof(fan.FanCoolersStatus), 1704)
        self.assertEqual(fan.FanCoolersStatus.items.offset, 40)
        backend = self.backend()
        reading = backend.reading(999)
        self.assertEqual(self.calls, [fan.CURRENT_API])
        self.assertEqual(reading["rpm"], 1500)
        self.assertEqual([row["cooler_id"] for row in reading["fans"]], [7, 19])
        self.assertEqual(reading["semantics"], "driver_current_rpm")
        self.assertTrue(reading["private_api"])
        self.assertEqual(reading["aggregate"], "mean_valid_cooler_channels")

    def test_optional_private_entrypoint_absent_uses_only_tachometer(self):
        backend = self.backend()
        backend._functions = {}
        self.assertEqual(backend.reading(999)["rpm"], 900)
        self.assertEqual(self.calls, [fan.API])

    def test_unsupported_or_incompatible_private_api_is_tried_once_per_handle(self):
        for code in (-104, -3, -9):
            backend = self.backend()
            self.private_error = fan.NvapiError(fan.CURRENT_API, code)
            for _ in range(3):
                reading = backend.reading(999)
                self.assertEqual(reading["rpm"], 900)
                self.assertEqual(reading["fans"], [])
                self.assertEqual(reading["semantics"], "measured")
            self.assertEqual(self.calls.count(fan.CURRENT_API), 1)
            self.assertEqual(self.calls.count(fan.API), 3)

    def test_zero_and_partial_channels_are_not_filled_or_claimed_as_physical_fans(self):
        backend = self.backend(((3, 0), (8, 0xFFFFFFFF)))
        tach = fan.Tachometer(lambda: backend)
        backend.devices = lambda: {(1, 0): 999}
        reading = tach.read((0, 1, 0))
        self.assertEqual(reading["rpm"], 0)
        self.assertEqual(reading["status"]["state"], "partial")
        self.assertEqual([row["rpm"] for row in reading["fans"]], [0, None])
        self.assertEqual([row["cooler_id"] for row in reading["fans"]], [3, 8])
        self.assertTrue(all(row["scope"] == "cooler_channel" for row in reading["fans"]))
        self.assertTrue(all(row["timestamp"] == 1100 for row in reading["fans"]))

    def test_bad_count_ambiguous_ids_and_all_invalid_values_fail_without_legacy_extra_query(self):
        for rows in (tuple((index, 1000) for index in range(9)),
                     ((2, 1000), (2, 1200)), ((3, 0xFFFFFFFF),)):
            backend = self.backend(rows)
            backend.devices = lambda: {(1, 0): 999}
            reading = fan.Tachometer(lambda: backend).read((0, 1, 0))
            self.assertIsNone(reading["rpm"])
            self.assertEqual(reading["status"]["state"], "invalid_value")
            self.assertEqual(reading["status"]["api"], fan.CURRENT_API)
            self.assertEqual(self.calls, [fan.CURRENT_API])

    def test_private_transient_failure_has_own_source_and_backoff_without_tach_double_read(self):
        backend = self.backend()
        backend.devices = lambda: {(1, 0): 999}
        tach = fan.Tachometer(lambda: backend)
        self.private_error = fan.NvapiError(fan.CURRENT_API, -1)
        reading = tach.read((0, 1, 0))
        self.assertIsNone(reading["rpm"])
        self.assertEqual(reading["status"]["semantics"], "driver_current_rpm")
        self.assertTrue(reading["status"]["private_api"])
        self.now += 4.9
        tach.read((0, 1, 0))
        self.assertEqual(self.calls, [fan.CURRENT_API])
        self.now += .1
        self.private_error = None
        self.assertEqual(tach.read((0, 1, 0))["rpm"], 1500)
        self.assertEqual(self.calls, [fan.CURRENT_API, fan.CURRENT_API])

    def test_current_driver_rows_use_same_one_second_cache(self):
        backend = self.backend()
        backend.devices = lambda: {(1, 0): 999}
        tach = fan.Tachometer(lambda: backend)
        first = tach.read((0, 1, 0))
        self.now += .99
        first["fans"][0]["rpm"] = -100
        self.assertEqual(tach.read((0, 1, 0))["fans"][0]["rpm"], 1200)
        self.assertEqual(self.calls, [fan.CURRENT_API])
        self.now += .01
        tach.read((0, 1, 0))
        self.assertEqual(self.calls, [fan.CURRENT_API, fan.CURRENT_API])


class SamplerDemandTests(NoHardwareCase):
    def test_committed_config_enables_and_disables_selected_card_without_extra_worker(self):
        config = dict(refresh=2, visible=False, widgets={}, top_bar=dict(
            enabled=True, hardware_icon_style="soft", items=[dict(
                metric="gpu_usage", prefs=dict(icon_effect="auto", gpu_target="1"))]))
        source, api = nvml_source(), FakeNvapi()
        sampler = sensors.Sampler.__new__(sensors.Sampler)
        sampler.__dict__.update(
            _closed=False, first=False, cpu="Synthetic CPU", cores=8, threads=16,
            config_provider=lambda: config, asus=None, nvidia=source,
            nvml_retry=0, nvml_status=dict(state="connected"), _nvml_cleanup=None,
            _retry_nvidia_cleanup=Mock(),
            external=SimpleNamespace(read=lambda *args: dict(external_sensors={})),
            cooling=SimpleNamespace(sample_times={}),
            cpu_thermal=SimpleNamespace(read=lambda **kwargs: {}, status=lambda requested: {}),
            storage=SimpleNamespace(read=lambda requested: {}),
            activity=SimpleNamespace(read=lambda *args: dict(provider_status={})),
            battery=SimpleNamespace(read=lambda: {}))
        self.stack.enter_context(patch("sensors.GpuTachometer", return_value=fan.Tachometer(lambda: api)))
        self.stack.enter_context(patch("sensors.hwinfo_registry", return_value={}))
        for name, value in dict(cpu_percent=12, sensors_battery=None,
                virtual_memory=SimpleNamespace(percent=20, used=20, total=100, available=80),
                swap_memory=SimpleNamespace(percent=0, used=0)).items():
            self.stack.enter_context(patch("sensors.psutil." + name, return_value=value))
        self.stack.enter_context(patch("sensors.INSPECT_UNTIL", 0))
        first = sampler.sample()
        self.assertEqual(first["gpus"]["1"]["gpu_fan_rpm"], 0)
        self.assertEqual(first["cpu_usage"], 12)
        self.assertEqual(api.reads, [902])
        config["top_bar"]["hardware_icon_style"] = "classic"
        self.now += 3
        second = sampler.sample()
        self.assertNotIn("gpu_fan_rpm", second["gpus"]["1"])
        self.assertEqual(api.reads, [902])
        source.close()


if __name__ == "__main__":
    unittest.main()
