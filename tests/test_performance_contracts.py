"""Cheap catalog reads retain correct labels, notification and draft boundaries."""

import copy
import hashlib
import time
import unittest
from unittest.mock import Mock, patch

import native_controller as controls
import presets
from external_sensor import PROVIDER
from localization import translate
from stats_config import DEFAULT, validate
from widget_catalog import TEMPLATES, from_template


class PerformanceContractTests(unittest.TestCase):
    def setUp(self):
        value = copy.deepcopy(DEFAULT)
        first = from_template("custom")
        first.update(
            content=["cpu_power", "gpu_power"],
            width=500,
            height=160,
            form="free",
            show_title=False,
            title="",
        )
        second = from_template("cpu")
        value.update(
            widgets={"w_a": first, "w_b": second},
            widget_order=["w_a", "w_b"],
            mode="separate",
            language="zh-CN",
            autostart=False,
        )
        self.initial = validate(value)
        with patch.object(controls, "load", return_value=copy.deepcopy(self.initial)):
            self.ui = controls.Controller()
        self.counts = dict(catalog=0, language=0, sensors=0)
        for name, signal in (
            ("catalog", self.ui.catalogChanged),
            ("language", self.ui.languageChanged),
            ("sensors", self.ui.sensorsChanged),
        ):
            signal.connect(
                lambda selected=name: self.counts.__setitem__(selected, self.counts[selected] + 1)
            )
        for name in ("save", "set_autostart"):
            guard = patch.object(
                controls, name, side_effect=AssertionError("Unexpected persistence: " + name)
            )
            guard.start()
            self.addCleanup(guard.stop)

    def instance(self, key="w_a"):
        return next(row for row in self.ui.catalog["instances"] if row["id"] == key)

    def reset_counts(self):
        self.counts.update(catalog=0, language=0, sensors=0)

    @staticmethod
    def channel(identifier="/synthetic/fan/case", **options):
        row = dict(
            id=identifier,
            name="Case Fan 原名 β",
            hardware_name="Synthetic board",
            hardware_id="/synthetic",
            hardware_type="SuperIO",
            type="Fan",
            unit="RPM",
            value=2400,
            available=True,
            min=None,
            max=None,
        )
        row.update(options)
        return row

    def discover(self, row):
        self.ui.receive(
            dict(
                time=time.time(),
                cpu_temp=40,
                net_download=1,
                external_catalog={row["id"]: row},
                external_revision=1,
            )
        )
        return "lhm:" + hashlib.sha256(row["id"].encode()).hexdigest()

    def test_catalog_reads_do_not_build_or_validate_preset_configs(self):
        with (
            patch.object(
                controls, "catalogue", side_effect=AssertionError("Unrelated preset work")
            ),
            patch.object(
                presets, "validate", side_effect=AssertionError("Unrelated template validation")
            ),
            patch.object(self.ui, "_build_catalog", wraps=self.ui._build_catalog) as build,
        ):
            first = self.ui.catalog
            for _ in range(30):
                self.assertEqual(self.ui.catalog, first)
            self.assertEqual(build.call_count, 1)
        self.assertEqual({row["id"] for row in first["presets"]}, set(presets.CATALOG_INFO))
        self.assertTrue(all("config" not in entry for entry in presets.CATALOG_INFO.values()))

    def test_repeated_live_values_do_not_deepcopy_unchanged_device_inventory(self):
        sample = dict(time=1.0, cpu_usage=20,
                      gpus={"gpu0": {"label": "Synthetic GPU", "gpu_usage": 10}},
                      networks={"nic0": {"label": "Synthetic Network", "net_download": 1}})
        self.ui.receive(sample)
        inventory = self.ui._devices
        notifications = []
        self.ui.devicesChanged.connect(lambda: notifications.append(True))
        original = copy.deepcopy
        with patch.object(controls.copy, "deepcopy", wraps=original) as deep:
            for index in range(80):
                self.ui.receive(dict(sample, time=index + 2.0, cpu_usage=index))
            inventory_copies = [call for call in deep.call_args_list
                                if call.args and call.args[0] is inventory]
        self.assertEqual(inventory_copies, [])
        self.assertIs(self.ui._devices, inventory)
        self.assertEqual(notifications, [])
        self.assertEqual(self.ui._data["cpu_usage"], 79)
        self.assertEqual(self.ui._history[-1]["cpu_usage"], 79)
        self.ui.receive(dict(time=83.0, gpus={"gpu0": {"label": "Renamed GPU"}}))
        self.assertEqual(self.ui._devices["gpus"]["gpu0"]["label"], "Renamed GPU")
        self.assertIs(self.ui._devices["networks"], inventory["networks"])
        self.assertEqual(inventory["gpus"]["gpu0"]["label"], "Synthetic GPU")
        self.ui.receive(dict(time=84.0, gpus={}))
        self.assertEqual(self.ui._devices["gpus"], {})
        self.assertEqual(len(notifications), 2)

    def test_unrelated_style_geometry_and_device_edits_do_not_notify_catalog_or_language(self):
        before = copy.deepcopy(self.ui.catalog)
        with patch.object(self.ui, "_build_catalog", wraps=self.ui._build_catalog) as build:
            for field, value in (
                ("skin", "graphite"),
                ("glass_transparency", 31.2),
                ("precision", "2"),
                ("gpu_target", "disconnected"),
            ):
                self.ui.changeWidget("w_a", field, value)
                self.assertEqual(self.ui.draft["widgets"]["w_a"][field], value)
            self.assertTrue(self.ui.setWidgetDimensions("w_a", 540, 180))
            self.ui.change("glass_transparency", 62.5)
            self.assertEqual(self.ui.catalog, before)
            build.assert_not_called()
        self.assertEqual(self.counts, dict(catalog=0, language=0, sensors=0))
        self.assertEqual(self.ui.saved, self.initial)

    def test_title_sidebar_updates_and_roundtrips_through_undo_redo(self):
        before = self.instance()["label"]
        self.ui.changeWidget("w_a", "title", "Power Board")
        self.assertEqual(self.instance()["label"], "Power Board")
        self.assertEqual(self.counts, dict(catalog=1, language=0, sensors=0))
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.instance()["label"], before)
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.instance()["label"], "Power Board")
        self.assertEqual(self.counts, dict(catalog=3, language=0, sensors=0))
        self.assertEqual(self.ui.saved, self.initial)

    def test_language_updates_all_catalog_labels_and_only_notifies_on_actual_change(self):
        self.ui.catalog
        self.ui.change("language", "en")
        self.assertEqual(self.ui.language, "en")
        self.assertEqual(self.instance()["label"], translate(TEMPLATES["custom"]["label"], "en"))
        self.assertEqual(self.ui.texts, controls.MESSAGES["en"])
        self.assertEqual(self.counts, dict(catalog=1, language=1, sensors=1))
        self.ui.change("language", "en")
        self.assertEqual(self.counts, dict(catalog=1, language=1, sensors=1))
        self.assertTrue(self.ui.undoDraft())
        self.assertEqual(self.ui.language, "zh-CN")
        self.assertEqual(self.instance()["label"], TEMPLATES["custom"]["label"])
        self.assertTrue(self.ui.redoDraft())
        self.assertEqual(self.ui.language, "en")
        self.assertEqual(self.counts, dict(catalog=3, language=3, sensors=3))

    def test_catalog_order_add_remove_and_undo_are_current(self):
        self.ui.catalog
        self.ui.moveWidget("w_b", -1)
        self.assertEqual([row["id"] for row in self.ui.catalog["instances"]], ["w_b", "w_a"])
        new_key = self.ui.addWidget("memory")
        self.assertTrue(new_key)
        self.assertIn(new_key, [row["id"] for row in self.ui.catalog["instances"]])
        self.ui.removeWidget(new_key)
        self.assertNotIn(new_key, [row["id"] for row in self.ui.catalog["instances"]])
        self.assertTrue(self.ui.undoDraft())
        self.assertIn(new_key, [row["id"] for row in self.ui.catalog["instances"]])

    def test_external_binding_name_and_hardware_rename_invalidate_sidebar_without_translation(self):
        row = self.channel()
        discovered = self.discover(row)
        self.assertTrue(self.ui.addMetrics("w_a", [discovered]))
        self.assertIn(row["name"], self.instance()["subtitle"])
        self.ui.change("language", "de")
        self.assertIn(row["name"], self.instance()["subtitle"])
        value = copy.deepcopy(self.ui.draft)
        binding = value["widgets"]["w_a"]["sensor_bindings"]["external_1"]
        binding.update(name="Original Name 新 β", hardware_name="Synthetic board 2")
        self.reset_counts()
        self.assertTrue(self.ui.edit(value))
        self.assertIn("Original Name 新 β", self.instance()["subtitle"])
        self.assertEqual(
            self.ui.metricInfoFor("w_a", "external_1")["hardware_name"], "Synthetic board 2"
        )
        self.assertEqual(self.counts, dict(catalog=1, language=0, sensors=0))
        self.assertEqual(binding["sensor_id"], row["id"])
        self.assertEqual(binding["provider"], PROVIDER)
        self.assertTrue(self.ui.undoDraft())
        self.assertIn(row["name"], self.instance()["subtitle"])
        self.assertTrue(self.ui.redoDraft())
        self.assertIn("Original Name 新 β", self.instance()["subtitle"])

    def test_unit_precision_and_binding_rows_refresh_without_catalog_notification(self):
        row = self.channel("/synthetic/temperature", type="Temperature", unit="°C", value=40)
        self.discover(row)
        self.ui.catalog
        self.reset_counts()
        self.ui.changeWidget("w_a", "temperature_unit", "F")
        self.ui.changeWidget("w_a", "precision", "2")
        rows = self.ui.metricRowsFor("w_a")
        builtin = next(item for item in rows if item["id"] == "cpu_temp")
        discovered = next(item for item in rows if item.get("provider") == PROVIDER)
        self.assertEqual(builtin["value"], "104.00 °F")
        self.assertEqual(discovered["value"], "104.00 °F")
        self.assertEqual(discovered["label"], row["name"])
        self.assertEqual(self.counts, dict(catalog=0, language=0, sensors=0))

    def test_quick_widget_enabled_updates_sidebar_and_preserves_unrelated_pending_title(self):
        self.ui.changeWidget("w_a", "title", "Draft title")
        self.reset_counts()
        with patch.object(controls, "save", Mock()):
            self.assertTrue(self.ui.quickWidget("w_a", "enabled", False))
        self.assertFalse(self.instance()["enabled"])
        self.assertEqual(self.instance()["label"], "Draft title")
        self.assertEqual(self.ui.saved["widgets"]["w_a"]["title"], "")
        self.assertEqual(self.counts, dict(catalog=1, language=0, sensors=0))
        self.assertTrue(self.ui.dirty)

    def test_quick_style_and_global_toggle_do_not_invalidate_metadata_or_erase_draft(self):
        self.ui.changeWidget("w_a", "title", "Draft title")
        self.ui.catalog
        self.reset_counts()
        with patch.object(controls, "save", Mock()):
            self.assertTrue(self.ui.quickWidget("w_a", "skin", "graphite"))
            self.ui.quick("visible")
        self.assertEqual(self.instance()["label"], "Draft title")
        self.assertEqual(self.counts, dict(catalog=0, language=0, sensors=0))
        self.assertEqual(self.ui.saved["widgets"]["w_a"]["title"], "")
        self.assertTrue(self.ui.dirty)

    def test_geometry_resize_preserves_pending_metadata_without_catalog_notification(self):
        self.ui.changeWidget("w_a", "title", "Pending")
        self.ui.catalog
        self.reset_counts()
        with patch.object(controls, "save", Mock()):
            self.assertTrue(self.ui.resizeWindow("w_a", 550, 190))
        self.assertEqual(self.instance()["label"], "Pending")
        self.assertEqual(self.counts, dict(catalog=0, language=0, sensors=0))
        self.assertTrue(self.ui.dirty)

    def test_invalid_metadata_edit_does_not_invalidate_existing_catalog(self):
        before = copy.deepcopy(self.ui.catalog)
        self.ui.changeWidget("w_a", "title", "x" * 13)
        self.assertEqual(self.ui.catalog, before)
        self.assertEqual(self.counts, dict(catalog=0, language=0, sensors=0))
        self.assertEqual(self.ui.draft, self.initial)

    def test_explicit_presets_return_fresh_configs_and_do_not_pollute_defaults(self):
        original = copy.deepcopy(DEFAULT)
        one, two = presets.catalogue(), presets.catalogue()
        self.assertEqual(set(one), set(presets.CATALOG_INFO))
        for key, metadata in presets.CATALOG_INFO.items():
            self.assertEqual(
                {field: one[key][field] for field in ("label", "description")}, metadata
            )
        one["overview"]["config"]["widgets"]["cpu"]["title"] = "Changed"
        self.assertEqual(two["overview"]["config"]["widgets"]["cpu"]["title"], "系统状态")
        self.ui.change("language", "en")
        self.ui.change("autostart", True)
        self.ui.preset("overview")
        self.assertEqual(self.ui.draft["language"], "en")
        self.assertTrue(self.ui.draft["autostart"])
        self.assertEqual(self.ui.draft["widgets"]["cpu"]["title"], translate("系统状态", "en"))
        self.assertEqual(
            presets.catalogue()["overview"]["config"]["widgets"]["cpu"]["title"], "系统状态"
        )
        self.assertEqual(DEFAULT, original)
        self.assertEqual(self.ui.saved, self.initial)


if __name__ == "__main__":
    unittest.main()
