"""Synthetic external sensor schemas and units; no hardware, UI or transport access."""

import copy
import math
import unittest

from external_sensor import (
    EXTERNAL_SLOTS,
    MAX_HARDWARE,
    MAX_SENSORS,
    MAX_TIMESTAMP,
    PROVIDER,
    SENSOR_TYPES,
    binding_meta,
    parse_snapshot,
    sensor_binding,
    validate_bindings,
)
from metrics import METRICS, display_value, metric_info, metric_value, numeric, required_sources


def binding(sensor_id="/gpu/0/fan/0", sensor_type="Fan", name="Case Fan", hardware="GPU 0"):
    return dict(provider=PROVIDER, sensor_id=sensor_id, sensor_type=sensor_type,
                name=name, hardware_name=hardware)


def snapshot(sensor_type="Fan", value=1234, *, sensor_id="/gpu/0/fan/0", unit=None):
    return dict(
        schema=1,
        provider=PROVIDER,
        version="0.9.6",
        timestamp=1792468800.125,
        hardware=[dict(id="/gpu/0", name="GPU 0", type="GpuNvidia", parent_id=None)],
        sensors=[dict(
            id=sensor_id,
            name="Case Fan",
            hardware_id="/gpu/0",
            hardware_name="GPU 0",
            hardware_type="GpuNvidia",
            type=sensor_type,
            unit=SENSOR_TYPES[sensor_type]["raw_unit"] if unit is None else unit,
            value=value,
            min=None,
            max=None,
        )],
    )


class ExternalBindingTests(unittest.TestCase):
    def test_six_slots_and_explicit_units_are_fixed(self):
        self.assertEqual(EXTERNAL_SLOTS, tuple(f"external_{n}" for n in range(1, 7)))
        expected = dict(Temperature="°C", Fan="RPM", Voltage="V", Current="A", Power="W",
                        Clock="MHz", Load="%", Data="GB", SmallData="MB", Throughput="B/s",
                        Level="%", Energy="Wh", Factor="")
        self.assertEqual({key: spec["unit"] for key, spec in SENSOR_TYPES.items()}, expected)
        self.assertEqual(SENSOR_TYPES["Energy"]["raw_unit"], "mWh")
        self.assertNotIn("Control", SENSOR_TYPES)

    def test_canonical_binding_preserves_exact_identifier_and_is_independent(self):
        source = {"external_1": binding("/GPU/0/ Fan ", name=" 风扇 ")}
        original = copy.deepcopy(source)
        result = validate_bindings(source)
        self.assertEqual(result, original)
        result["external_1"]["name"] = "Changed"
        self.assertEqual(source, original)

    def test_all_slots_are_per_widget_not_a_global_identifier_registry(self):
        prefs = dict(sensor_bindings={slot: binding(f"/fan/{n}")
                                     for n, slot in enumerate(EXTERNAL_SLOTS)})
        self.assertEqual(len(validate_bindings(prefs["sensor_bindings"])), 6)
        for slot in EXTERNAL_SLOTS:
            self.assertEqual(binding_meta(slot, prefs)["label"], "Case Fan")
        self.assertEqual(len([key for key in METRICS if key.startswith("external_")]), 6)

    def test_duplicate_ids_in_different_slots_are_rejected_even_if_types_differ(self):
        with self.assertRaises(ValueError):
            validate_bindings({"external_1": binding(),
                               "external_2": binding(sensor_type="Power")})

    def test_bad_shapes_fields_providers_and_types_are_rejected(self):
        bad_bindings = [None, [], True, {"external_7": binding()}, {"cpu_usage": binding()},
                        {1: binding()}, {"external_1": None}]
        for source in bad_bindings:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    validate_bindings(source)
        for field, value in (("provider", "Other"), ("provider", True),
                             ("sensor_type", "Control"), ("sensor_type", "Unknown"),
                             ("sensor_type", []), ("sensor_id", None), ("name", "")):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    validate_bindings({"external_1": dict(binding(), **{field: value})})
        extra = dict(binding(), unit="W", maximum=1, digits=6, kind="bar")
        with self.assertRaises(ValueError):
            validate_bindings({"external_1": extra})
        missing = binding()
        missing.pop("hardware_name")
        with self.assertRaises(ValueError):
            validate_bindings({"external_1": missing})

    def test_text_limits_and_control_characters_are_enforced_without_path_interpretation(self):
        valid = binding("i" * 512, name="名" * 128, hardware="设" * 128)
        self.assertEqual(validate_bindings({"external_1": valid})["external_1"], valid)
        for field, length in (("sensor_id", 512), ("name", 128), ("hardware_name", 128)):
            for value in ("x" * (length + 1), "A\nB", "A\x00B", "A\u200eB", "A\ud800B"):
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ValueError):
                        validate_bindings({"external_1": dict(binding(), **{field: value})})
        opaque = binding("../../run.cmd", hardware="")
        self.assertEqual(validate_bindings({"external_1": opaque})["external_1"], opaque)

    def test_meta_is_derived_from_type_and_missing_bindings_are_safe(self):
        for sensor_type, spec in SENSOR_TYPES.items():
            with self.subTest(sensor_type=sensor_type):
                prefs = dict(sensor_bindings={"external_1": binding(sensor_type=sensor_type)})
                meta = binding_meta("external_1", prefs)
                self.assertEqual(meta["label"], "Case Fan")
                self.assertIn(PROVIDER, meta["note"])
                self.assertIn("GPU 0", meta["note"])
                self.assertEqual((meta["source"], meta["category"], meta["scope"]),
                                 ("external", "advanced", None))
                for field in ("unit", "digits", "maximum", "kind"):
                    self.assertEqual(meta[field], spec[field])
                meta["unit"] = "Corrupt"
                self.assertNotEqual(SENSOR_TYPES[sensor_type]["unit"], "Corrupt")
        for prefs in (None, {}, dict(sensor_bindings=None), dict(sensor_bindings={"external_1": {}})):
            self.assertIsNone(sensor_binding("external_1", prefs))
            self.assertEqual(binding_meta("external_1", prefs)["label"], "未绑定传感器")
            self.assertEqual(binding_meta("external_1", prefs)["unit"], "")


class ExternalSnapshotTests(unittest.TestCase):
    def test_all_whitelisted_types_normalize_with_correct_units_and_energy_scale(self):
        for sensor_type, spec in SENSOR_TYPES.items():
            with self.subTest(sensor_type=sensor_type):
                source = snapshot(sensor_type, 12345)
                source["sensors"][0].update(min=1000, max=15000)
                original = copy.deepcopy(source)
                result = parse_snapshot(source)
                row = result["sensors"]["/gpu/0/fan/0"]
                scale = 1000 if sensor_type == "Energy" else 1
                self.assertEqual((row["value"], row["min"], row["max"]),
                                 (12345 / scale, 1000 / scale, 15000 / scale))
                self.assertEqual(row["unit"], spec["unit"])
                self.assertTrue(row["available"])
                self.assertEqual(result["rejected_count"], 0)
                self.assertIs(type(result["timestamp"]), float)
                self.assertEqual(source, original)

    def test_genuine_none_is_unavailable_and_zero_is_a_real_reading(self):
        for value, available in ((None, False), (0, True), (-12.5, True)):
            with self.subTest(value=value):
                result = parse_snapshot(snapshot("Temperature", value))
                row = result["sensors"]["/gpu/0/fan/0"]
                self.assertEqual(row["value"], value)
                self.assertEqual(row["available"], available)
                self.assertEqual(result["rejected_count"], 0)

    def test_invalid_numeric_cells_become_missing_and_count_once_per_row(self):
        for value in (True, False, "0", "NaN", [], {}, math.nan, math.inf, -math.inf, 10**1000):
            with self.subTest(value=repr(value)):
                source = snapshot(value=value)
                source["sensors"][0].update(min=value, max=value)
                result = parse_snapshot(source)
                row = result["sensors"]["/gpu/0/fan/0"]
                self.assertIsNone(row["value"])
                self.assertIsNone(row["min"])
                self.assertIsNone(row["max"])
                self.assertFalse(row["available"])
                self.assertEqual(result["rejected_count"], 1)

    def test_bad_descriptors_units_and_control_target_are_skipped_and_counted(self):
        mutations = (("type", "Control"), ("type", "Unknown"), ("type", []), ("unit", "%"),
                     ("unit", 0), ("name", "bad\nname"), ("name", "x" * 129),
                     ("hardware_type", "x" * 65), ("hardware_id", "/removed"))
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                source = snapshot()
                source["sensors"][0][field] = value
                result = parse_snapshot(source)
                self.assertEqual(result["sensors"], {})
                self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(parse_snapshot(snapshot("Energy", 1200, unit="Wh"))["sensors"], {})

    def test_duplicate_sensor_and_hardware_ids_reject_whole_snapshot(self):
        source = snapshot()
        source["sensors"].append(dict(source["sensors"][0], type="Control"))
        with self.assertRaises(ValueError):
            parse_snapshot(source)
        source = snapshot()
        source["hardware"].append(dict(source["hardware"][0], name="Different"))
        with self.assertRaises(ValueError):
            parse_snapshot(source)

    def test_bad_header_is_rejected_instead_of_turning_into_an_empty_healthy_reading(self):
        changes = (("schema", True), ("schema", 1.0), ("schema", 2), ("provider", "Other"),
                   ("version", None), ("version", "v" * 65), ("timestamp", True),
                   ("timestamp", -1), ("timestamp", MAX_TIMESTAMP + 1),
                   ("timestamp", math.inf), ("timestamp", math.nan), ("timestamp", "1"),
                   ("hardware", {}), ("sensors", {}), ("sensors", None))
        for field, value in changes:
            with self.subTest(field=field, value=repr(value)):
                with self.assertRaises(ValueError):
                    parse_snapshot(dict(snapshot(), **{field: value}))
        for value in (None, [], "{}", b"{}", True):
            with self.assertRaises(ValueError):
                parse_snapshot(value)

    def test_bounded_lists_accept_limit_and_reject_one_over(self):
        source = snapshot()
        row = source["sensors"][0]
        source["sensors"] = [dict(row, id=f"/fan/{index}") for index in range(MAX_SENSORS)]
        self.assertEqual(len(parse_snapshot(source)["sensors"]), MAX_SENSORS)
        source["sensors"].append(dict(row, id="/one-more"))
        with self.assertRaises(ValueError):
            parse_snapshot(source)
        source = snapshot()
        row = source["hardware"][0]
        source["hardware"] = [dict(row, id=f"/hardware/{index}")
                              for index in range(MAX_HARDWARE + 1)]
        with self.assertRaises(ValueError):
            parse_snapshot(source)

    def test_hardware_rejection_and_unknown_fields_are_explicit(self):
        source = snapshot()
        source["hardware"][0]["name"] = "bad\x00name"
        result = parse_snapshot(source)
        self.assertEqual(result["hardware"], [])
        self.assertEqual(result["sensors"], {})
        self.assertEqual(result["rejected_count"], 2)
        source = snapshot()
        source["execute"] = "ignored.exe"
        source["sensors"][0]["execute"] = "ignored.exe"
        result = parse_snapshot(source)
        self.assertNotIn("execute", result)
        self.assertNotIn("execute", result["sensors"]["/gpu/0/fan/0"])


class ExternalMetricTests(unittest.TestCase):
    def prefs(self, sensor_id="/gpu/0/fan/0", sensor_type="Fan"):
        return dict(sensor_bindings={"external_1": binding(sensor_id, sensor_type)})

    def test_dynamic_slot_metadata_and_values_do_not_change_global_registry(self):
        original = copy.deepcopy(METRICS)
        first = self.prefs("/gpu/0/fan/0", "Fan")
        second = self.prefs("/cpu/0/temp/0", "Temperature")
        data = dict(external_sensors={
            "/gpu/0/fan/0": dict(type="Fan", unit="RPM", value=0),
            "/cpu/0/temp/0": dict(type="Temperature", unit="°C", value=37.25),
        })
        self.assertEqual(metric_value(data, "external_1", first), 0)
        self.assertEqual(metric_value(data, "external_1", second), 37.25)
        self.assertEqual(metric_info("external_1", first)["unit"], "RPM")
        self.assertEqual(metric_info("external_1", second)["unit"], "°C")
        self.assertEqual(METRICS, original)

    def test_removed_changed_or_mismatched_rows_never_bind_a_different_channel(self):
        prefs = self.prefs()
        for rows in ({}, None, [], {"/other": dict(type="Fan", value=1500)},
                     {"/gpu/0/fan/0": dict(type="Control", value=50)},
                     {"/gpu/0/fan/0": dict(type="Fan", unit="W", value=50)},
                     {"/gpu/0/fan/0": dict(type="Fan", id="/other", value=50)},
                     {"/gpu/0/fan/0": dict(type="Fan", value=50, available=False)}):
            with self.subTest(rows=rows):
                self.assertIsNone(metric_value(dict(external_1=999, external_sensors=rows),
                                               "external_1", prefs))

    def test_external_numbers_must_be_finite_and_not_boolean(self):
        for value in (None, True, False, "0", math.nan, math.inf, -math.inf, 10**1000):
            with self.subTest(value=repr(value)):
                data = dict(external_sensors={"/gpu/0/fan/0": dict(type="Fan", value=value)})
                self.assertIsNone(metric_value(data, "external_1", self.prefs()))
        self.assertFalse(numeric(10**1000))

    def test_missing_binding_cannot_appear_available_from_a_slot_named_value(self):
        data = dict(external_1=15, external_sensors={"/gpu/0/fan/0": dict(type="Fan", value=1200)})
        self.assertIsNone(metric_value(data, "external_1"))
        self.assertEqual(display_value(data, "external_1"), (None, "", 0))

    def test_display_converts_temperature_and_uses_canonical_energy_units(self):
        energy = parse_snapshot(snapshot("Energy", 12345))
        self.assertEqual(display_value(dict(external_sensors=energy["sensors"]), "external_1",
                                       self.prefs(sensor_type="Energy")), (12.345, "Wh", 2))
        temperature = parse_snapshot(snapshot("Temperature", 25))
        prefs = dict(self.prefs(sensor_type="Temperature"), temperature_unit="F", precision="2")
        self.assertEqual(display_value(dict(external_sensors=temperature["sensors"]), "external_1",
                                       prefs), (77.0, "°F", 2))
        self.assertEqual(display_value({"cpu_temp": 25}, "cpu_temp", {"temperature_unit": "F"}),
                         (77.0, "°F", 0))
        self.assertIs(metric_info("cpu_temp"), METRICS["cpu_temp"])

    def test_throughput_stays_bytes_per_second_not_network_megabits(self):
        data = parse_snapshot(snapshot("Throughput", 4096))
        prefs = dict(self.prefs(sensor_type="Throughput"), network_unit="Mbps")
        self.assertEqual(display_value(dict(external_sensors=data["sensors"]), "external_1", prefs),
                         (4096.0, "B/s", 0))

    def test_dependencies_include_external_only_for_enabled_visible_content(self):
        prefs = dict(self.prefs(), enabled=True, kind="custom", content=["cpu_usage", "external_1"])
        config = dict(visible=True, widget_order=["one"], widgets={"one": prefs})
        self.assertEqual(required_sources(config), {"cpu", "external"})
        config["widgets"]["one"]["enabled"] = False
        self.assertEqual(required_sources(config), set())
        config["widgets"]["one"]["enabled"] = True
        config["visible"] = False
        self.assertEqual(required_sources(config), set())


if __name__ == "__main__":
    unittest.main()
