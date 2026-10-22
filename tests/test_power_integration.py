"""Regressions at the registry, dependency and sampler power-source boundaries."""

import copy
import os
import threading
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault(
    "DESKTOP_STATS_DATA",
    str(Path(__file__).resolve().parents[1] / "qa-private/power-integration-data"),
)

import sensors
from energy_sensor import SOURCE
from metrics import required_sources
from native_controller import Controller
from stats_config import DEFAULT


class PowerDependencyTests(unittest.TestCase):
    def test_cpu_package_only_keeps_its_native_provider_active(self):
        config = copy.deepcopy(DEFAULT)
        config["widget_order"] = ["cpu"]
        config["widgets"]["cpu"]["content"] = ["cpu_power"]
        self.assertEqual(required_sources(config), {"cpu"})
        config["widgets"]["cpu"]["enabled"] = False
        self.assertEqual(required_sources(config), set())
        config["widgets"]["cpu"]["enabled"] = True
        config["visible"] = False
        self.assertEqual(required_sources(config), set())


class RegistryPowerTests(unittest.TestCase):
    @staticmethod
    def registry(values, age=0):
        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        entries = list(values.items())
        modified = int((time.time() - age + 11644473600) * 1e7)
        with (
            patch(
                "sensors.winreg.OpenKey",
                side_effect=lambda hive, path: (
                    Key()
                    if hive == sensors.winreg.HKEY_CURRENT_USER
                    else (_ for _ in ()).throw(FileNotFoundError())
                ),
            ),
            patch("sensors.winreg.QueryInfoKey", return_value=(0, len(entries), modified)),
            patch(
                "sensors.winreg.EnumValue",
                side_effect=lambda key, index: (*entries[index], sensors.winreg.REG_SZ),
            ),
        ):
            return sensors.hwinfo_registry()

    def test_standard_four_field_vsb_exports_work_without_unit_extension(self):
        values = {}
        for index, sensor, label, raw in (
            ("0", "CPU [#0] AMD", "CPU Package Power", "42.5"),
            ("1", "ASUS EC", "Adapter Input Power", "91.4"),
            ("2", "ASUS EC", "Total System Power", "87.3"),
        ):
            values.update(
                {
                    "Sensor" + index: sensor,
                    "Label" + index: label,
                    "ValueRaw" + index: raw,
                    "Value" + index: raw + " W",
                }
            )
        data = self.registry(values)
        self.assertEqual(data["cpu_power"], 42.5)
        self.assertEqual(data["adapter_input_watts"], 91.4)
        self.assertEqual(data["system_power"], 87.3)

    def test_explicit_watts_required_instead_of_guessing_from_sensor_name(self):
        for text in ("42.5 mW", "42.5 kW", "42.5", "42.5 W/h", "unavailable", "NaN W"):
            with self.subTest(value=text):
                data = self.registry(
                    {
                        "Sensor0": "CPU [#0] AMD",
                        "Label0": "CPU Package Power",
                        "ValueRaw0": "42.5",
                        "Value0": text,
                    }
                )
                self.assertNotIn("cpu_power", data)

    def test_unit_extension_is_authoritative_when_present(self):
        for unit, expected in (("W", True), (" w ", True), ("mW", False), ("kW", False)):
            with self.subTest(unit=unit):
                self.assertEqual(
                    sensors.hwinfo_watts_unit({"Unit0": unit, "Value0": "42.5 W"}, "0"),
                    expected,
                )

    def test_power_limit_and_stale_exports_are_not_current_package_power(self):
        values = {
            "Sensor0": "CPU [#0] AMD",
            "Label0": "CPU PPT Limit",
            "ValueRaw0": "80",
            "Value0": "80 W",
        }
        self.assertEqual(self.registry(values), {})
        values["Label0"] = "CPU Package Power"
        self.assertEqual(self.registry(values, age=31), {})

    def test_gpu_power_also_requires_an_explicit_watt_unit(self):
        values = {
            "Sensor0": "GPU [#0] NVIDIA",
            "Label0": "GPU Power",
            "ValueRaw0": "900",
            "Value0": "900 mW",
        }
        self.assertNotIn("gpu_power", self.registry(values))
        values.update(ValueRaw0="19.5", Value0="19.5 W")
        self.assertEqual(self.registry(values)["gpu_power"], 19.5)

    def test_asic_and_board_power_have_independent_measurement_scopes(self):
        values={"Sensor0":"GPU [#0] NVIDIA","Label0":"GPU ASIC Power",
                "ValueRaw0":"17.1","Value0":"17.1 W"}
        self.assertEqual(self.registry(values),{"gpu_asic_power":17.1})
        values.update(Sensor1="GPU [#0] NVIDIA",Label1="GPU Power",ValueRaw1="24.2",Value1="24.2 W")
        self.assertEqual(self.registry(values),{"gpu_asic_power":17.1,"gpu_power":24.2})
        values["Value0"]="17.1 mW"
        self.assertEqual(self.registry(values),{"gpu_power":24.2})


class SamplerPowerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.config = copy.deepcopy(DEFAULT)
        self.config["widget_order"] = ["cpu"]
        self.config["widgets"]["cpu"]["content"] = ["cpu_power"]
        self.native = Mock(state="ready")
        self.native.read.return_value = {"cpu_power": 43.2, "cpu_power_source": SOURCE}
        self.asus = Mock()
        self.asus.read.return_value = {"cpu_temp": 80, "cpu_temp_source": "ASUS ACPI"}
        self.battery = Mock()
        self.battery.read.return_value = {"battery_watts": 0.0, "battery_present": True}
        self.activity = Mock()
        self.activity.read.return_value = {}
        self.storage = Mock()
        self.storage.read.return_value = {}
        self.fallback = {}
        patches = {
            "load": lambda: copy.deepcopy(self.config),
            "cpu_name": lambda: "Test CPU",
            "CpuPackagePower": lambda: self.native,
            "AsusTemperature": lambda: self.asus,
            "Battery": lambda: self.battery,
            "Activity": lambda: self.activity,
            "StorageHealth": lambda base: self.storage,
            "hwinfo_registry": lambda cache=None: copy.deepcopy(self.fallback),
            "INSPECT_UNTIL": 0,
            "ExternalEngine": lambda: SimpleNamespace(read=lambda *a: {"external_sensors": {}}, close=lambda: None),
        }
        for name, value in patches.items():
            self.stack.enter_context(patch("sensors." + name, value))
        self.stack.enter_context(patch("sensors.psutil.cpu_count", return_value=8))
        self.stack.enter_context(patch("sensors.psutil.cpu_percent", return_value=25.0))
        self.stack.enter_context(
            patch("sensors.psutil.cpu_freq", return_value=SimpleNamespace(current=4000))
        )
        self.stack.enter_context(patch("sensors.psutil.sensors_battery", return_value=None))
        self.stack.enter_context(
            patch(
                "sensors.psutil.virtual_memory",
                return_value=SimpleNamespace(percent=50, used=2**33, total=2**34, available=2**33),
            )
        )
        self.stack.enter_context(
            patch("sensors.psutil.swap_memory", return_value=SimpleNamespace(percent=0, used=0))
        )
        self.nvidia_factory = self.stack.enter_context(patch("sensors.Nvidia"))
        self.sampler = sensors.Sampler()
        self.addCleanup(self.sampler.close)

    def test_native_package_sample_takes_priority_without_mislabeling(self):
        self.fallback = {"cpu_power": 99.0, "adapter_input_watts": 91.4}
        data = self.sampler.sample()
        self.assertEqual(data["cpu_power"], 43.2)
        self.assertEqual(data["metric_sources"]["cpu_power"], SOURCE)
        self.assertEqual(data["adapter_input_watts"], 91.4)
        self.assertEqual(data["metric_sources"]["adapter_input_watts"], "HWiNFO VSB")
        self.assertEqual(data["battery_watts"], 0.0)
        self.nvidia_factory.assert_not_called()

    def test_native_failure_falls_back_to_hwinfo_with_correct_source(self):
        self.native.read.return_value = {}
        self.native.state = "unavailable"
        self.fallback = {"cpu_power": 39.7}
        data = self.sampler.sample()
        self.assertEqual(data["cpu_power"], 39.7)
        self.assertEqual(data["metric_sources"]["cpu_power"], "HWiNFO VSB")

    def test_unmapped_hwinfo_gpu_is_never_attributed_to_nvml_gpu_zero(self):
        self.config["widget_order"] = ["gpu"]
        self.fallback = {"gpu_power": 14.2, "gpu_temp": 78}
        gpu = self.nvidia_factory.return_value
        gpu.read.return_value = dict(gpu_usage=5, gpu_source="NVIDIA NVML",
                                     gpus={"0": dict(gpu_usage=5, label="Discrete GPU")})
        data = self.sampler.sample()
        self.assertNotIn("gpu_power", data)
        self.assertNotIn("gpu_power", data["gpus"]["0"])
        self.assertIsNone(data["cpu_temp"])
        self.assertNotIn("gpu_power", data["metric_sources"])
        gpu.close()

    def test_failed_new_sample_never_reuses_last_power_or_source(self):
        self.assertEqual(self.sampler.sample()["cpu_power"], 43.2)
        self.native.read.return_value = {}
        self.native.state = "unavailable"
        data = self.sampler.sample()
        self.assertIsNone(data.get("cpu_power"))
        self.assertNotIn("cpu_power", data["metric_sources"])

    def test_no_cpu_dependency_skips_provider_until_sensor_inspection(self):
        self.config["widget_order"] = ["memory"]
        with (
            patch("threading.Thread.start", side_effect=AssertionError("No provider thread")) as start,
            patch("subprocess.Popen", side_effect=AssertionError("No provider process")) as spawn,
        ):
            self.sampler.sample()
            self.native.read.assert_not_called()
            with patch("sensors.INSPECT_UNTIL", time.monotonic() + 8):
                self.sampler.sample()
            self.assertIs(self.sampler.storage, self.storage)
            self.assertEqual(self.storage.read.call_args_list, [call(False), call(True)])
            start.assert_not_called()
            spawn.assert_not_called()
        self.native.read.assert_called_once()

    def test_standalone_run_closes_sources_even_when_wait_fails(self):
        self.sampler.sample = Mock(return_value={})
        self.sampler.write = Mock()
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.side_effect = RuntimeError("Worker cancelled")
        with self.assertRaises(RuntimeError):
            self.sampler.run(stop)
        self.asus.close.assert_called_once()
        self.native.close.assert_called_once()

    def test_optional_counter_failure_keeps_cpu_and_battery_sample(self):
        with (
            patch("sensors.psutil.swap_memory", side_effect=RuntimeError("PDH unavailable")),
            patch("sensors.psutil.virtual_memory", side_effect=OSError("Memory API unavailable")),
            patch("sensors.psutil.sensors_battery", side_effect=OSError("No battery API")),
        ):
            data = self.sampler.sample()
        self.assertEqual(data["cpu_power"], 43.2)
        self.assertEqual(data["battery_watts"], 0.0)
        self.assertIsNone(data["swap_percent"])
        self.assertIsNone(data["ram_used_gb"])
        self.assertIsNone(data["battery_percent"])
        self.assertIn("MemoryDetail=-- / -- GB", sensors.view(data))

    def test_one_cleanup_failure_does_not_leak_other_sources(self):
        self.asus.close.side_effect = OSError("Device already gone")
        stop = Mock()
        stop.is_set.return_value = True
        self.sampler.run(stop)
        self.native.close.assert_called_once()

    def test_native_worker_shutdown_releases_package_counter_after_sampling_error(self):
        entered = threading.Event()

        def fail_sample():
            entered.set()
            raise OSError("Sensor disappeared")

        self.sampler.sample = fail_sample
        self.asus.close.side_effect = OSError("ASUS handle already closed")
        with (
            patch("native_controller.load", return_value=copy.deepcopy(self.config)),
            patch("native_controller.sensors.Sampler", return_value=self.sampler),
            patch("native_controller.logging.exception"),
        ):
            controller = Controller()
            controller.start()
            self.assertTrue(entered.wait(timeout=2), "Worker did not enter sampling")
            controller.close()
        self.assertFalse(controller.thread.is_alive())
        self.native.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
