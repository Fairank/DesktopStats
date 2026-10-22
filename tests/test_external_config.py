"""External bindings survive schema/file/edit lifecycles in workspace-only profiles."""

import copy
import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from external_sensor import EXTERNAL_SLOTS, PROVIDER


def bound(sensor_id="/board/fan/0", sensor_type="Fan"):
    return dict(provider=PROVIDER, sensor_id=sensor_id, sensor_type=sensor_type,
                name="Chassis Fan", hardware_name="Mainboard")


class ExternalConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = Path(__file__).resolve().parents[1] / "qa-private/redesign08/external-temp"
        cls.test_root.mkdir(parents=True, exist_ok=True)
        cls.import_profile = tempfile.TemporaryDirectory(dir=cls.test_root)
        with patch.dict(
            os.environ,
            {"DESKTOP_STATS_DATA": cls.import_profile.name, "QT_QPA_PLATFORM": "offscreen"},
        ):
            cls.settings = importlib.import_module("stats_config")
            cls.catalog = importlib.import_module("widget_catalog")
            cls.controls = importlib.import_module("native_controller")

    @classmethod
    def tearDownClass(cls):
        cls.import_profile.cleanup()

    def setUp(self):
        self.profile = tempfile.TemporaryDirectory(dir=self.test_root)
        self.addCleanup(self.profile.cleanup)
        self.base = Path(self.profile.name)
        for name, value in (("BASE", self.base), ("CONFIG", self.base / "preferences.json"),
                            ("BACKUP", self.base / "preferences.backup.json")):
            replacement = patch.object(self.settings, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def config(self):
        prefs = self.catalog.from_template("custom")
        prefs.update(title="混合传感器", form="wide", size=123, skin="tint", show_title=False,
                     glass_transparency=37.25, glass_curvature=0,
                     sensor_bindings={"external_1": bound(),
                                      "external_2": bound("/battery/energy/0", "Energy")},
                     content=["cpu_usage", "external_1", "gpu_temp", "external_2",
                              "ram_percent", "disk_free_gb"])
        return self.settings.validate(dict(version=7, widgets={"workbench": prefs},
                                           widget_order=["workbench"]))

    def controller(self, config=None):
        with patch.object(self.controls, "load", return_value=copy.deepcopy(config or self.config())):
            return self.controls.Controller()

    def test_every_old_version_defaults_bindings_without_changing_identity_or_settings(self):
        for version in range(1, 8):
            with self.subTest(version=version):
                # Versions 1-4 used a hardware-tab map, before independent instances/order.
                widgets = {key: dict(enabled=False) for key in self.settings.ORDER}
                widgets["cpu"] = dict(title="原有组件", size=123, show_title=False,
                                      skin="minimal", content=["cpu_usage"], enabled=True)
                source = dict(version=version, widgets=widgets, widget_order=["cpu"])
                original = copy.deepcopy(source)
                result = self.settings.validate(source)
                self.assertEqual(result["version"], 8)
                self.assertEqual(result["widget_order"], ["cpu"])
                self.assertEqual(result["widgets"]["cpu"]["sensor_bindings"], {})
                for field, value in source["widgets"]["cpu"].items():
                    self.assertEqual(result["widgets"]["cpu"][field], value)
                self.assertEqual(self.settings.validate(result), result)
                self.assertEqual(source, original)

    def test_default_and_every_template_have_independent_empty_bindings(self):
        for prefs in self.settings.DEFAULT["widgets"].values():
            self.assertEqual(prefs["sensor_bindings"], {})
        for template in self.catalog.TEMPLATES:
            with self.subTest(template=template):
                one = self.catalog.from_template(template)
                two = self.catalog.from_template(template)
                one["sensor_bindings"]["external_1"] = bound()
                self.assertEqual(two["sensor_bindings"], {})

    def test_six_mixed_metrics_and_custom_fields_survive_json_validation(self):
        config = self.config()
        original = copy.deepcopy(config)
        result = self.settings.validate(json.loads(json.dumps(config, ensure_ascii=False)))
        self.assertEqual(result, original)
        self.assertEqual(len(result["widgets"]["workbench"]["content"]), 6)
        self.assertEqual(result["widgets"]["workbench"]["glass_curvature"], 0.0)
        self.assertFalse(result["widgets"]["workbench"]["show_title"])

    def test_content_cannot_reference_an_unbound_slot(self):
        config = self.config()
        config["widgets"]["workbench"]["sensor_bindings"].pop("external_1")
        with self.assertRaises(ValueError):
            self.settings.validate(config)
        config = self.config()
        config["widgets"]["workbench"]["content"][-1] = "external_6"
        with self.assertRaises(ValueError):
            self.settings.validate(config)

    def test_bad_binding_rejects_config_even_if_slot_is_not_currently_visible(self):
        config = self.config()
        prefs = config["widgets"]["workbench"]
        prefs.update(content=["cpu_usage"], enabled=False)
        for change in (None, [], {"external_1": dict(bound(), unit="W")},
                       {"external_1": dict(bound(), sensor_type="Control")}):
            with self.subTest(change=change):
                prefs["sensor_bindings"] = change
                with self.assertRaises(ValueError):
                    self.settings.validate(config)

    def test_duplicate_sensor_in_one_widget_is_rejected_but_shared_between_widgets_is_valid(self):
        config = self.config()
        duplicate = copy.deepcopy(config["widgets"]["workbench"])
        config["widgets"]["second"] = duplicate
        config["widget_order"].append("second")
        self.assertEqual(len(self.settings.validate(config)["widgets"]), 2)
        config["widgets"]["second"]["sensor_bindings"]["external_2"] = bound()
        with self.assertRaises(ValueError):
            self.settings.validate(config)

    def test_saved_config_backup_and_fallback_keep_exact_bindings(self):
        first = self.config()
        self.settings.save(first)
        second = copy.deepcopy(first)
        second["widgets"]["workbench"]["sensor_bindings"]["external_1"]["name"] = "Changed"
        self.settings.save(second)
        self.assertEqual(self.settings.load(), second)
        self.assertEqual(json.loads(self.settings.BACKUP.read_text(encoding="utf-8")), first)
        self.settings.CONFIG.write_text("not-json", encoding="utf-8")
        self.assertEqual(self.settings.load(), first)

    def test_illegal_import_does_not_change_existing_draft_or_saved_bindings(self):
        controller = self.controller()
        original = copy.deepcopy(controller._draft)
        bad = self.config()
        bad["widgets"]["workbench"]["sensor_bindings"]["external_1"]["unit"] = "W"
        imported = self.base / "illegal.json"
        imported.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(ValueError):
            controller.import_path(imported)
        self.assertEqual(controller._draft, original)
        self.assertEqual(controller._saved, original)

    def test_new_copy_edit_commit_and_revert_preserve_binding_identity_and_inheritance(self):
        controller = self.controller()
        created = controller.addWidget("custom")
        self.assertTrue(created)
        self.assertEqual(controller._draft["widgets"][created]["sensor_bindings"], {})
        duplicate = controller.duplicateWidget("workbench")
        self.assertTrue(duplicate)
        self.assertEqual(controller._draft["widgets"][duplicate],
                         controller._draft["widgets"]["workbench"])
        updated = copy.deepcopy(controller._draft["widgets"][duplicate]["sensor_bindings"])
        updated["external_1"]["sensor_id"] = "/different/fan/0"
        controller.changeWidget(duplicate, "sensor_bindings", updated)
        self.assertEqual(controller._draft["widgets"]["workbench"]["sensor_bindings"]
                         ["external_1"]["sensor_id"], "/board/fan/0")
        controller.apply()
        self.assertEqual(self.settings.load(), controller._saved)
        controller.changeWidget(duplicate, "sensor_bindings",
                                dict(updated, external_1=bound("/third/fan/0")))
        controller.revert()
        self.assertEqual(controller._draft["widgets"][duplicate]["sensor_bindings"], updated)

    def test_maximum_valid_binding_configuration_exports_and_reimports(self):
        config = copy.deepcopy(self.settings.DEFAULT)
        config["widgets"], config["widget_order"] = {}, []
        for widget_index in range(self.settings.MAX_WIDGETS):
            key = f"w_{widget_index:02}"
            prefs = self.catalog.from_template("custom")
            bindings = {}
            for slot_index, slot in enumerate(EXTERNAL_SLOTS):
                prefix = f"/board/{widget_index}/{slot_index}/"
                bindings[slot] = dict(bound(prefix + "x" * (512 - len(prefix))),
                                      name="名" * 128, hardware_name="设" * 128)
            prefs.update(content=list(EXTERNAL_SLOTS), sensor_bindings=bindings)
            config["widgets"][key] = prefs
            config["widget_order"].append(key)
        config = self.settings.validate(config)
        controller = self.controller(config)
        exported = self.base / "maximum.json"
        with patch.object(self.controls.QFileDialog, "getSaveFileName",
                          return_value=(str(exported), "JSON (*.json)")):
            controller.exportSettings()
        self.assertGreater(exported.stat().st_size, 65536)
        controller.import_path(exported)
        self.assertEqual(controller._draft, config)


if __name__ == "__main__":
    unittest.main()
