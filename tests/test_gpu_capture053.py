"""Mock-only production capture/cache/consumer controls; no real hardware.

Only the real repository provider is imported. The sensors consumer class is read from
its actual AST without importing sensors/config, loading DLLs or constructing
NVML. Every driver call and provider clock is a test-owned fake.
"""
import ast
import copy
import ctypes as c
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def no_native(*args, **kwargs):
    raise AssertionError("Real driver/native/process operation is forbidden")


class FakeClock:
    def __init__(self):
        self.now, self.wall_offset = 100., 1000.
        self.mono_calls = self.wall_calls = 0

    def monotonic(self):
        self.mono_calls += 1
        return self.now

    def time(self):
        self.wall_calls += 1
        return self.now + self.wall_offset


class FakeDriver:
    def __init__(self, clock):
        self.clock = clock
        self.mapping = {(1, 0): 901, (2, 0): 902}
        self.calls, self.enumerations, self.closes = [], 0, 0
        self.failure, self.partial = None, False

    def devices(self):
        self.enumerations += 1
        return dict(self.mapping)

    def reading(self, handle):
        self.calls.append(handle)
        self.clock.now += .125
        if self.failure is not None:
            raise self.failure
        fans = [dict(index=0, cooler_id=7, rpm=1200, state="available"),
                dict(index=1, cooler_id=19, rpm=None if self.partial else 1800,
                     state="invalid_value" if self.partial else "available")]
        return dict(rpm=1200 if self.partial else 1500, fans=fans,
                    api="NvAPI_GPU_ClientFanCoolersGetStatus", source="NVIDIA driver current fan RPM",
                    semantics="driver_current_rpm", private_api=True,
                    state="partial" if self.partial else "available", aggregate="mean_valid_cooler_channels")

    def close(self):
        self.closes += 1


class CaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "gpu_fan_sensor.py"
        spec = importlib.util.spec_from_file_location("tested_production_gpu_capture053", path)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        # Class/ctypes declarations are pure; any incidental DLL load fails.
        with patch.object(c, "CDLL", side_effect=no_native), patch.object(c, "WinDLL", side_effect=no_native):
            spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(cls.module.__name__, None)

    def setUp(self):
        self.clock = FakeClock()
        self.clock_patch = patch.object(self.module, "time", self.clock)
        self.clock_patch.start(); self.addCleanup(self.clock_patch.stop)
        for name in ("CDLL", "WinDLL"):
            guard = patch.object(c, name, side_effect=no_native)
            guard.start(); self.addCleanup(guard.stop)
        self.driver = FakeDriver(self.clock)
        self.tach = self.module.Tachometer(lambda: self.driver)
        self.addCleanup(self.tach.close)

    def test_cache_preserves_real_completion_wall_sequence_and_query_count(self):
        original = self.tach.read((0, 1, 0))
        stamp = copy.deepcopy(original["status"])
        self.assertEqual(stamp["capture_monotonic"], 100.125)
        self.assertEqual(stamp["timestamp"], 1100.125)
        self.assertEqual(stamp["capture_sequence"], 1)
        self.assertIs(type(stamp["provider_epoch"]), int)
        self.assertEqual(self.clock.mono_calls, 2)  # existing read-start/cache-end calls only
        self.assertEqual(self.driver.calls, [901])
        self.assertTrue(all(row["capture_monotonic"] == 100.125 and row["capture_sequence"] == 1
                            and row["provider_epoch"] == stamp["provider_epoch"] for row in original["fans"]))
        original["status"]["capture_sequence"] = 999
        original["fans"][0]["cooler_id"] = 999
        self.clock.now, self.clock.wall_offset = 100.5, 900.
        cached = self.tach.read((0, 1, 0))
        self.assertEqual(cached["status"], stamp)
        self.assertEqual(cached["fans"][0]["cooler_id"], 7)
        self.assertEqual(self.driver.calls, [901])
        self.assertEqual(self.clock.mono_calls, 3)
        self.assertEqual(self.clock.wall_calls, 1)  # no _result/wall refresh on hit
        self.clock.now = 101.125
        new = self.tach.read((0, 1, 0))
        self.assertEqual(new["status"]["capture_monotonic"], 101.25)
        self.assertEqual(new["status"]["capture_sequence"], 2)
        self.assertEqual(new["status"]["provider_epoch"], stamp["provider_epoch"])
        self.assertEqual(new["status"]["timestamp"], 1001.25)  # legacy wall may correct backwards
        self.assertEqual(self.clock.mono_calls, 5)
        self.assertEqual(self.driver.calls, [901, 901])

    def test_each_device_invalidation_eviction_and_recreated_owner_get_new_epoch(self):
        first = self.tach.read((0, 1, 0))["status"]
        other = self.tach.read((0, 2, 0))["status"]
        self.assertNotEqual(first["provider_epoch"], other["provider_epoch"])
        self.assertEqual(other["capture_sequence"], 1)
        self.tach.invalidate()
        self.assertFalse(self.tach._cache)
        self.assertFalse(self.tach._capture_state)
        replacement = self.tach.read((0, 1, 0))["status"]
        self.assertNotEqual(replacement["provider_epoch"], first["provider_epoch"])
        self.assertEqual(replacement["capture_sequence"], 1)
        new_owner = self.module.Tachometer(lambda: self.driver)
        self.addCleanup(new_owner.close)
        self.assertNotEqual(new_owner.read((0, 1, 0))["status"]["provider_epoch"], replacement["provider_epoch"])
        self.tach.invalidate()
        self.driver.mapping = {(index, 0): index + 100 for index in range(17)}
        epochs = {}
        for index in range(17):
            epochs[index] = self.tach.read((0, index, 0))["status"]["provider_epoch"]
        self.assertEqual(len(self.tach._cache), 16)
        self.assertEqual(len(self.tach._capture_state), 16)
        self.assertNotEqual(self.tach.read((0, 0, 0))["status"]["provider_epoch"], epochs[0])

    def test_failure_partial_unknown_and_cooler_id_semantics_never_make_new_capture(self):
        success = self.tach.read((0, 1, 0))["status"]
        self.clock.now += 1.
        self.driver.failure = self.module.NvapiError(self.module.CURRENT_API, -1)
        failed = self.tach.read((0, 1, 0))
        self.assertIsNone(failed["rpm"])
        self.assertIsNone(failed["status"]["capture_monotonic"])
        self.assertIsNone(failed["status"]["capture_sequence"])
        self.assertEqual(failed["status"]["provider_epoch"], success["provider_epoch"])
        self.clock.now += 4.999
        self.driver.failure = None
        self.assertIsNone(self.tach.read((0, 1, 0))["rpm"])
        self.assertEqual(len(self.driver.calls), 2)
        self.clock.now += .001
        recovered = self.tach.read((0, 1, 0))
        self.assertEqual(recovered["status"]["capture_sequence"], 2)  # failure did not consume sequence
        self.clock.now += 1.
        self.driver.partial = True
        partial = self.tach.read((0, 1, 0))
        self.assertEqual(partial["status"]["state"], "partial")
        self.assertEqual(partial["rpm"], 1200)
        self.assertIsNone(partial["status"]["capture_monotonic"])
        self.assertIsNone(partial["status"]["capture_sequence"])
        self.assertEqual([r["cooler_id"] for r in partial["fans"]], [7, 19])
        self.assertEqual([r["rpm"] for r in partial["fans"]], [1200, None])
        self.assertTrue(all(r["scope"] == "cooler_channel" and r["capture_sequence"] is None for r in partial["fans"]))
        calls = len(self.driver.calls)
        for identity in (None, (1, 1, 0), (0, True, 0), (0, 255, 31)):
            unknown = self.tach.read(identity)
            self.assertIsNone(unknown["rpm"])
            self.assertIsNone(unknown["status"]["capture_monotonic"])
            self.assertIsNone(unknown["status"]["capture_sequence"])
        self.assertEqual(len(self.driver.calls), calls)
        self.tach.close()
        closed = self.tach.read((0, 1, 0))
        self.assertEqual(closed["status"]["state"], "closed")
        self.assertIsNone(closed["status"]["capture_monotonic"])
        self.assertFalse(self.tach._capture_state)

    def test_actual_consumer_fields_cache_handle_swap_and_no_flat_chassis_leak(self):
        path = ROOT / "sensors.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        selected = [row for row in tree.body if isinstance(row, ast.ClassDef) and row.name in ("NvidiaPciInfo", "Nvidia")
                    or isinstance(row, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GPU_CARD_TACH_FIELDS" for t in row.targets)]
        ns = dict(c=c, time=self.clock, NVML_RETRY_SECONDS=5., NVML_GPU_TARGETS=frozenset(str(i) for i in range(16)),
                  GpuTachometer=lambda: self.tach)
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), ns)
        source = ns["Nvidia"].__new__(ns["Nvidia"])
        source.handles, source.device_status, source._device_retry_at = {"0": 11}, {}, {}
        calls = []
        def query(channels, key, api, arguments, unit, handle, output):
            calls.append((api, handle))
            self.assertEqual(api, "nvmlDeviceGetPciInfo_v3")
            output._obj.domain, output._obj.bus, output._obj.device = (0, 1 if handle == 11 else 2, 0)
            channels[key] = dict(state="available", api=api, source="synthetic")
            return True
        source._query = query
        def read_device(handle):
            result = dict(gpu_name="Synthetic", gpu_source="mock", channel_status={})
            source._read_fan_rpm(handle, result["channel_status"], result)
            return result
        source.read_device = read_device
        source.request_fan_rpm(())
        self.assertNotIn("gpu_fans", source.read()["gpus"]["0"])
        self.assertFalse(calls)
        self.assertFalse(self.driver.calls)
        source.request_fan_rpm({"0"})
        data = source.read(); card = data["gpus"]["0"]
        capture_fields = ("gpu_fan_rpm_capture_monotonic", "gpu_fan_rpm_capture_sequence", "gpu_fan_rpm_provider_epoch")
        self.assertTrue(set(capture_fields) <= ns["GPU_CARD_TACH_FIELDS"])
        self.assertTrue(all(k in card and k not in data for k in capture_fields))
        self.assertEqual(card["gpu_fan_rpm_capture_sequence"], 1)
        self.assertEqual(card["gpu_fan_rpm_capture_monotonic"], 100.125)
        self.assertTrue(all(row["cooler_id"] in (7, 19) and row["provider_epoch"] == card["gpu_fan_rpm_provider_epoch"]
                            for row in card["gpu_fans"]))
        self.assertNotIn("gpu_fan_rpm", data["channel_status"])
        self.assertEqual(source.read()["gpus"]["0"]["gpu_fan_rpm_capture_sequence"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.driver.calls, [901])
        source.handles["0"] = 22
        replaced = source.read()["gpus"]["0"]
        self.assertNotEqual(replaced["gpu_fan_rpm_provider_epoch"], card["gpu_fan_rpm_provider_epoch"])
        self.assertEqual(replaced["gpu_fan_rpm_capture_sequence"], 1)
        self.assertEqual(self.driver.calls, [901, 902])


if __name__ == "__main__":
    unittest.main()
