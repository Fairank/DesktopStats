"""Canonical discovery formatting remains separate from validated widget bindings."""

import copy
import hashlib
import math
import time
import unittest
from unittest.mock import patch

from external_sensor import (
    PROVIDER,
    SENSOR_TYPES,
    inventory_display,
    parse_snapshot,
    sensor_binding,
    validate_bindings,
)
from metrics import metric_value


def channel(sensor_type="Temperature", **values):
    row = dict(
        id="/Opaque/ Channel β ",
        type=sensor_type,
        unit=SENSOR_TYPES[sensor_type]["unit"],
        name=" 原始 Channel 名 β ",
        hardware_name=" Main Board α ",
        hardware_id="/board",
        hardware_type="SuperIO",
        value=12.3456,
        available=True,
        min=None,
        max=None,
    )
    row.update(values)
    return row


class InventoryDisplayTests(unittest.TestCase):
    def test_all_thirteen_types_use_canonical_units_and_display_precision(self):
        expected = {
            "Temperature": ("12.3", "°C"),
            "Fan": ("12", "RPM"),
            "Voltage": ("12.346", "V"),
            "Current": ("12.346", "A"),
            "Power": ("12.3", "W"),
            "Clock": ("12.3", "MHz"),
            "Load": ("12.3", "%"),
            "Data": ("12.3", "GB"),
            "SmallData": ("12.3", "MB"),
            "Throughput": ("12", "B/s"),
            "Level": ("12.3", "%"),
            "Energy": ("12.35", "Wh"),
            "Factor": ("12.346", ""),
        }
        self.assertEqual(set(expected), set(SENSOR_TYPES))
        for sensor_type, result in expected.items():
            with self.subTest(sensor_type=sensor_type):
                row = channel(sensor_type)
                self.assertEqual(inventory_display(row["id"], row), result)

    def test_parser_normalizes_energy_once_and_discovery_does_not_rescale_throughput(self):
        rows = []
        for sensor_type, value in (("Energy", 24500), ("Throughput", 123456)):
            row = channel(sensor_type, id="/board/" + sensor_type, value=value)
            row["unit"] = SENSOR_TYPES[sensor_type]["raw_unit"]
            rows.append(row)
        payload = dict(
            schema=1,
            provider=PROVIDER,
            version="0.9.6",
            timestamp=time.time(),
            hardware=[dict(id="/board", name="Board", type="SuperIO", parent_id=None)],
            sensors=rows,
        )
        parsed = parse_snapshot(payload)["sensors"]
        self.assertEqual(
            inventory_display("/board/Energy", parsed["/board/Energy"]), ("24.50", "Wh")
        )
        self.assertEqual(
            inventory_display("/board/Throughput", parsed["/board/Throughput"]), ("123456", "B/s")
        )
        self.assertEqual(
            inventory_display("/board/Energy", dict(parsed["/board/Energy"], unit="mWh")),
            ("—", "Wh"),
        )

    def test_zero_is_available_and_false_availability_remains_unavailable(self):
        for sensor_type in SENSOR_TYPES:
            with self.subTest(sensor_type=sensor_type):
                row = channel(sensor_type, value=0)
                text, unit = inventory_display(row["id"], row)
                self.assertEqual(float(text), 0)
                self.assertEqual(unit, SENSOR_TYPES[sensor_type]["unit"])
                self.assertEqual(
                    inventory_display(row["id"], dict(row, available=False)), ("—", unit)
                )

    def test_non_numeric_boolean_nan_infinity_and_huge_integer_are_not_numbers(self):
        for value in (None, True, False, "0", [], {}, math.nan, math.inf, -math.inf, 10**1000):
            with self.subTest(value=repr(value)):
                row = channel(value=value)
                self.assertEqual(inventory_display(row["id"], row), ("—", "°C"))

    def test_exact_identifier_and_canonical_unit_are_required_without_normalization(self):
        row = channel()
        self.assertEqual(inventory_display(row["id"].strip(), row), ("—", "°C"))
        self.assertEqual(inventory_display(row["id"].lower(), row), ("—", "°C"))
        for identifier in (None, False, 42, "", "/different"):
            with self.subTest(identifier=identifier):
                self.assertEqual(inventory_display(identifier, row), ("—", "°C"))
        for mutation in ({"id": "/different"}, {"unit": "°F"}, {"unit": "W"}, {"unit": None}):
            with self.subTest(mutation=mutation):
                self.assertEqual(inventory_display(row["id"], dict(row, **mutation)), ("—", "°C"))

    def test_unsupported_types_and_bad_shapes_fail_closed(self):
        row = channel()
        for bad in (
            None,
            True,
            [],
            "row",
            {},
            dict(row, type="Control"),
            dict(row, type="Unknown"),
            dict(row, type=True),
            dict(row, type=[]),
        ):
            with self.subTest(bad=bad):
                self.assertEqual(inventory_display(row["id"], bad), ("—", ""))

    def test_fahrenheit_and_precision_are_display_preferences_only(self):
        row = channel(value=40)
        source = copy.deepcopy(row)
        prefs = dict(temperature_unit="F", precision="2")
        self.assertEqual(inventory_display(row["id"], row, prefs), ("104.00", "°F"))
        self.assertEqual(inventory_display(row["id"], dict(row, value=0), prefs), ("32.00", "°F"))
        self.assertEqual(
            inventory_display(row["id"], dict(row, available=False), prefs), ("—", "°F")
        )
        self.assertEqual(inventory_display(row["id"], row, dict(precision="0")), ("40", "°C"))
        self.assertEqual(row, source)
        self.assertEqual(prefs, dict(temperature_unit="F", precision="2"))

    def test_overflow_after_temperature_conversion_is_unavailable_without_raising(self):
        for value in (1e308, -1e308, 10**308, -(10**308)):
            with self.subTest(value=value):
                row = channel(value=value)
                self.assertEqual(
                    inventory_display(row["id"], row, dict(temperature_unit="F")), ("—", "°F")
                )

    def test_missing_or_non_mapping_preferences_keep_canonical_display(self):
        row = channel()
        for prefs in (None, [], True, "F"):
            with self.subTest(prefs=prefs):
                self.assertEqual(inventory_display(row["id"], row, prefs), ("12.3", "°C"))

    def test_formatter_does_not_mutate_source_names_or_authorize_a_binding(self):
        row = channel()
        original = copy.deepcopy(row)
        self.assertEqual(inventory_display(row["id"], row), ("12.3", "°C"))
        self.assertEqual(row, original)
        self.assertIsNone(sensor_binding("external_1", row))
        with self.assertRaises(ValueError):
            validate_bindings({"external_1": row})
        valid = dict(
            provider=PROVIDER,
            sensor_id=row["id"],
            sensor_type=row["type"],
            name=row["name"],
            hardware_name=row["hardware_name"],
        )
        prefs = dict(sensor_bindings={"external_1": valid})
        self.assertEqual(sensor_binding("external_1", prefs), valid)
        self.assertEqual(
            metric_value(dict(external_sensors={row["id"]: row}), "external_1", prefs), row["value"]
        )
        self.assertIsNone(
            metric_value(
                dict(external_sensors={row["id"]: dict(row, unit="W")}), "external_1", prefs
            )
        )

    def test_discovered_controller_rows_keep_exact_names_ids_and_selected_binding_separate(self):
        import native_controller as controls
        from stats_config import DEFAULT, validate
        from widget_catalog import from_template

        cfg = copy.deepcopy(DEFAULT)
        prefs = from_template("custom")
        prefs.update(content=["cpu_usage"], width=300, height=160, form="free", show_title=False)
        cfg.update(widgets={"w_a": prefs}, widget_order=["w_a"], language="de", mode="separate")
        with patch.object(controls, "load", return_value=validate(cfg)):
            ui = controls.Controller()
        row = channel()
        ui.receive(dict(time=time.time(), external_catalog={row["id"]: row}, external_revision=1))
        identifier = "lhm:" + hashlib.sha256(row["id"].encode()).hexdigest()
        discovered = next(item for item in ui.metricRowsFor("w_a") if item["id"] == identifier)
        self.assertEqual(discovered["label"], row["name"])
        self.assertEqual(discovered["hardware_name"], row["hardware_name"])
        self.assertEqual(discovered["unit"], "°C")
        self.assertTrue(ui.addMetrics("w_a", [identifier]))
        binding = ui.draft["widgets"]["w_a"]["sensor_bindings"]["external_1"]
        self.assertEqual(binding["sensor_id"], row["id"])
        self.assertEqual(binding["name"], row["name"])
        self.assertEqual(binding["hardware_name"], row["hardware_name"])
        self.assertEqual(ui.readingFor("w_a", "external_1"), "12.3 °C")
        self.assertNotIn(identifier, [item["id"] for item in ui.metricRowsFor("w_a")])


if __name__ == "__main__":
    unittest.main()
