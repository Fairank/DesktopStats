"""Glass preference schema/transactions, using private files and no system windows."""

import copy
import importlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class GlassPreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = Path(__file__).resolve().parents[1] / "qa-private/redesign08/config-temp"
        cls.test_root.mkdir(parents=True, exist_ok=True)
        cls.import_profile = tempfile.TemporaryDirectory(dir=cls.test_root)
        with patch.dict(
            os.environ,
            {"DESKTOP_STATS_DATA": cls.import_profile.name, "QT_QPA_PLATFORM": "offscreen"},
        ):
            cls.settings = importlib.import_module("stats_config")
            cls.catalog = importlib.import_module("widget_catalog")
            cls.controls = importlib.import_module("native_controller")
        cls.fields = ("glass_transparency", "glass_curvature")

    @classmethod
    def tearDownClass(cls):
        cls.import_profile.cleanup()

    def setUp(self):
        self.profile = tempfile.TemporaryDirectory(dir=self.test_root)
        self.addCleanup(self.profile.cleanup)
        self.base = Path(self.profile.name)
        for name, value in (
            ("BASE", self.base),
            ("CONFIG", self.base / "preferences.json"),
            ("BACKUP", self.base / "preferences.backup.json"),
        ):
            replacement = patch.object(self.settings, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def controller(self, config=None):
        value = self.settings.validate(config or copy.deepcopy(self.settings.DEFAULT))
        with patch.object(self.controls, "load", return_value=value):
            return self.controls.Controller()

    def rich_v6(self):
        widget = self.catalog.from_template("power")
        widget.update(
            enabled=False,
            content=["cpu_power", "gpu_power", "battery_discharge_watts"],
            title="自定功率",
            show_title=False,
            size=107,
            skin="minimal",
            grouped=True,
            presentation="list",
            form="wide",
            precision="2",
            temperature_unit="F",
            network_unit="Mbps",
            network_target="Wi-Fi",
            disk_target="disk-2",
            volume_target="D:",
            gpu_target="1",
        )
        for field in self.fields:
            widget.pop(field)
        return dict(
            version=6,
            theme="dark",
            language="de",
            skin="tint",
            opacity=76,
            size=120,
            mode="mixed",
            layout="row",
            group_columns=3,
            locked=True,
            visible=False,
            autostart=False,
            refresh=0.15,
            magnet_enabled=True,
            magnet_gap=23,
            magnet_bounce=False,
            reflow_on_resize=False,
            widgets={"my_power": widget},
            widget_order=["my_power"],
        )

    def test_new_defaults_are_float_and_widget_fields_inherit(self):
        self.assertEqual(self.catalog.GLASS_DEFAULTS, dict.fromkeys(self.fields, 50.0))
        self.assertEqual(self.settings.DEFAULT["version"], 8)
        self.assertNotIn("glass_refraction", self.settings.DEFAULT)
        for field in self.fields:
            self.assertIs(type(self.settings.DEFAULT[field]), float)
            for prefs in self.settings.DEFAULT["widgets"].values():
                self.assertIsNone(prefs[field])
                self.assertNotIn("glass_refraction", prefs)

    def test_every_supported_version_fills_new_defaults_without_mutating_input(self):
        for version in range(1, 8):
            with self.subTest(version=version):
                source = dict(version=version, opacity=83, theme="dark", language="ja")
                original = copy.deepcopy(source)
                migrated = self.settings.validate(source)
                self.assertEqual(migrated["version"], 8)
                self.assertEqual(migrated["opacity"], 83)
                self.assertEqual((migrated["theme"], migrated["language"]), ("dark", "ja"))
                for field in self.fields:
                    self.assertEqual(migrated[field], 50.0)
                    self.assertIs(type(migrated[field]), float)
                    self.assertTrue(all(p[field] is None for p in migrated["widgets"].values()))
                self.assertEqual(source, original)
                self.assertEqual(self.settings.validate(migrated), migrated)

    def test_unsupported_schema_numbers_are_rejected(self):
        for version in (0, 9, -1, True, False, 8.0, "8", None):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    self.settings.validate({"version": version})

    def test_global_continuous_values_are_not_quantized(self):
        for field in self.fields:
            for value in (0, 0.0, 0.000001, 12.34567890123, 37.25, 99.999999, 100, 100.0):
                with self.subTest(field=field, value=value):
                    config = self.settings.validate({"version": 7, field: value})
                    self.assertIs(type(config[field]), float)
                    self.assertEqual(config[field], float(value))
                    self.assertEqual(self.settings.validate(json.loads(json.dumps(config))), config)

    def test_invalid_globals_are_rejected_instead_of_coerced_or_clamped(self):
        invalid = (
            None, True, False, "0", "37.25", "100", "NaN", [], {},
            -0.000001, 100.000001, -1, 101, 10**1000, math.nan, math.inf, -math.inf,
        )
        for field in self.fields:
            for value in invalid:
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ValueError):
                        self.settings.validate({"version": 7, field: value})

    def test_local_null_and_continuous_override_are_distinct(self):
        for field in self.fields:
            for value in (None, 0, 0.000001, 37.25, 100):
                with self.subTest(field=field, value=value):
                    source = dict(
                        version=7,
                        widgets={"one": dict(kind="custom", **{field: value})},
                        widget_order=["one"],
                        **{field: 63.75},
                    )
                    config = self.settings.validate(source)
                    self.assertEqual(config[field], 63.75)
                    local = config["widgets"]["one"][field]
                    if value is None:
                        self.assertIsNone(local)
                    else:
                        self.assertEqual(local, float(value))
                        self.assertIs(type(local), float)
                    self.assertEqual(self.settings.validate(json.loads(json.dumps(config))), config)

    def test_invalid_local_override_rejects_entire_config(self):
        for field in self.fields:
            for value in (True, False, "37.25", [], {}, -0.01, 100.01, math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ValueError):
                        self.settings.validate(dict(
                            version=7,
                            widgets={"one": dict(kind="custom", **{field: value})},
                            widget_order=["one"],
                        ))

    def test_v6_migration_preserves_instance_identity_and_all_existing_preferences(self):
        original = self.rich_v6()
        snapshot = copy.deepcopy(original)
        migrated = self.settings.validate(original)
        self.assertEqual(migrated["version"], 8)
        self.assertEqual(migrated["widget_order"], ["my_power"])
        self.assertEqual(list(migrated["widgets"]), ["my_power"])
        for field, value in original.items():
            if field not in ("version", "widgets"):
                self.assertEqual(migrated[field], value)
        for field, value in original["widgets"]["my_power"].items():
            self.assertEqual(migrated["widgets"]["my_power"][field], value)
        for field in self.fields:
            self.assertEqual(migrated[field], 50.0)
            self.assertIsNone(migrated["widgets"]["my_power"][field])
        self.assertEqual(original, snapshot)
        self.assertEqual(self.settings.validate(migrated), migrated)

    def test_legacy_widget_fields_and_disabled_state_survive_upgrade(self):
        for version in range(1, 5):
            with self.subTest(version=version):
                prefs = dict(title="迁移保留", show_title=False, enabled=False, size=123,
                             skin="minimal", content=["cpu_usage", "gpu_power"])
                result = self.settings.validate(dict(version=version, widgets={"cpu": prefs}))
                self.assertEqual({key: result["widgets"]["cpu"][key] for key in prefs}, prefs)
                self.assertNotIn("cpu", result["widget_order"])
                self.assertTrue(all(result["widgets"]["cpu"][f] is None for f in self.fields))

    def test_all_defaults_and_templates_define_independent_inherited_fields(self):
        for kind in self.catalog.MODULES:
            with self.subTest(kind=kind):
                prefs = self.catalog.widget_defaults(kind)
                self.assertTrue(all(prefs[field] is None for field in self.fields))
        for template in self.catalog.TEMPLATES:
            with self.subTest(template=template):
                first = self.catalog.from_template(template)
                second = self.catalog.from_template(template)
                self.assertTrue(all(first[field] is None for field in self.fields))
                first["content"].clear()
                first["glass_transparency"] = 37.25
                self.assertTrue(second["content"])
                self.assertIsNone(second["glass_transparency"])
                config = self.settings.validate(dict(
                    version=7, widgets={"created": second}, widget_order=["created"]
                ))
                self.assertEqual(config["widgets"]["created"], second)

    def test_loading_v6_does_not_write_until_save_and_backup_is_validated(self):
        old = self.rich_v6()
        raw = json.dumps(old, ensure_ascii=False)
        self.settings.CONFIG.write_text(raw, encoding="utf-8")
        migrated = self.settings.load()
        self.assertEqual(self.settings.CONFIG.read_text(encoding="utf-8"), raw)
        self.assertFalse(self.settings.BACKUP.exists())
        migrated.update(glass_transparency=37.25, glass_curvature=0)
        migrated["widgets"]["my_power"].update(glass_transparency=100, glass_curvature=37.25)
        self.settings.save(migrated)
        saved = self.settings.load()
        self.assertEqual(saved, self.settings.validate(migrated))
        self.assertEqual(json.loads(self.settings.CONFIG.read_text(encoding="utf-8")), saved)
        backup = json.loads(self.settings.BACKUP.read_text(encoding="utf-8"))
        self.assertEqual(backup, self.settings.validate(old))
        self.assertEqual(backup["version"], 8)
        self.assertIs(type(saved["glass_curvature"]), float)

    def test_invalid_save_leaves_primary_and_backup_unchanged(self):
        self.settings.save(self.settings.DEFAULT)
        config = copy.deepcopy(self.settings.DEFAULT)
        config["glass_transparency"] = 37.25
        self.settings.save(config)
        before = (self.settings.CONFIG.read_bytes(), self.settings.BACKUP.read_bytes())
        for field in self.fields:
            for value in (math.nan, True, -1, "37.25"):
                with self.subTest(field=field, value=repr(value)):
                    invalid = copy.deepcopy(config)
                    invalid[field] = value
                    with self.assertRaises(ValueError):
                        self.settings.save(invalid)
                    self.assertEqual(
                        (self.settings.CONFIG.read_bytes(), self.settings.BACKUP.read_bytes()), before
                    )

    def test_invalid_primary_recovers_validated_backup_with_inheritance_intact(self):
        backup = self.rich_v6()
        self.settings.BACKUP.write_text(json.dumps(backup), encoding="utf-8")
        broken = dict(version=7, glass_transparency=True)
        self.settings.CONFIG.write_text(json.dumps(broken), encoding="utf-8")
        self.assertEqual(self.settings.load(), self.settings.validate(backup))

    def test_new_and_duplicated_instances_keep_new_fields_and_identity(self):
        controller = self.controller()
        controller.change("glass_transparency", 37.25)
        created = controller.addWidget("network")
        self.assertTrue(created)
        self.assertTrue(all(controller._draft["widgets"][created][f] is None for f in self.fields))
        controller.changeWidget(created, "title", "独立网络")
        controller.changeWidget(created, "glass_transparency", 0)
        controller.changeWidget(created, "glass_curvature", 37.25)
        duplicate = controller.duplicateWidget(created)
        self.assertTrue(duplicate)
        self.assertNotEqual(created, duplicate)
        self.assertEqual(controller._draft["widgets"][created], controller._draft["widgets"][duplicate])
        controller.changeWidget(duplicate, "glass_transparency", None)
        self.assertEqual(controller._draft["widgets"][created]["glass_transparency"], 0.0)
        self.assertIsNone(controller._draft["widgets"][duplicate]["glass_transparency"])
        with patch.object(self.controls, "save") as save:
            controller.apply()
        self.assertEqual(save.call_args.args[0]["widget_order"][-2:], [created, duplicate])
        self.assertEqual(save.call_args.args[0]["widgets"][created]["title"], "独立网络")

    def test_controller_fractional_changes_wait_for_apply_and_revert_restores_inheritance(self):
        controller = self.controller()
        original = copy.deepcopy(controller._saved)
        for field in self.fields:
            controller.change(field, 37.25)
            controller.changeWidget("cpu", field, 0)
            self.assertEqual(controller._draft[field], 37.25)
            self.assertEqual(controller._draft["widgets"]["cpu"][field], 0.0)
        self.assertEqual(controller._saved, original)
        self.assertTrue(controller.dirty)
        controller.revert()
        self.assertEqual(controller._draft, original)
        self.assertTrue(all(controller._draft["widgets"]["cpu"][f] is None for f in self.fields))

    def test_invalid_controller_edits_preserve_previous_draft_and_saved_values(self):
        controller = self.controller()
        controller.change("glass_transparency", 37.25)
        controller.changeWidget("cpu", "glass_curvature", 0)
        draft = copy.deepcopy(controller._draft)
        saved = copy.deepcopy(controller._saved)
        for field in self.fields:
            for value in (True, "37.25", -0.01, 100.01, math.nan, math.inf):
                with self.subTest(field=field, value=repr(value)):
                    controller.change(field, value)
                    controller.changeWidget("cpu", field, value)
                    self.assertEqual(controller._draft, draft)
                    self.assertEqual(controller._saved, saved)

    def test_import_and_export_use_validation_and_preserve_fractional_values(self):
        controller = self.controller()
        source = self.rich_v6()
        source.update(glass_transparency=37.25, glass_curvature=0)
        source["widgets"]["my_power"].update(glass_transparency=None, glass_curvature=100)
        imported = self.base / "import.json"
        imported.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8-sig")
        controller.import_path(imported)
        self.assertEqual(controller._draft, self.settings.validate(source))
        self.assertNotIn("my_power", controller._saved["widgets"])
        exported = self.base / "export.json"
        with patch.object(self.controls.QFileDialog, "getSaveFileName",
                          return_value=(str(exported), "JSON (*.json)")):
            controller.exportSettings()
        content = json.loads(exported.read_text(encoding="utf-8"))
        self.assertEqual(content, controller._draft)
        self.assertEqual(content["version"], 8)
        with patch.object(self.controls, "set_autostart") as startup:
            controller.apply()
        startup.assert_not_called()
        self.assertEqual(self.settings.load(), content)

    def test_invalid_glass_import_does_not_change_current_state(self):
        controller = self.controller()
        initial = copy.deepcopy(controller._draft)
        for field in self.fields:
            for value in (True, "37.25", -1, 101, math.inf):
                with self.subTest(field=field, value=repr(value)):
                    imported = self.base / "invalid-import.json"
                    imported.write_text(json.dumps(dict(version=7, **{field: value})), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        controller.import_path(imported)
                    self.assertEqual(controller._draft, initial)
                    self.assertEqual(controller._saved, initial)

    def test_failed_glass_commit_keeps_saved_state_and_pending_overrides(self):
        controller = self.controller()
        saved = copy.deepcopy(controller._saved)
        controller.change("glass_transparency", 37.25)
        controller.changeWidget("cpu", "glass_curvature", 0)
        pending = copy.deepcopy(controller._draft)
        calls = []
        controller.applyRequested.connect(calls.append)
        with (
            patch.object(self.controls, "save", side_effect=OSError("private test failure")),
            self.assertLogs(level="ERROR"),
        ):
            controller.apply()
        self.assertEqual(controller._saved, saved)
        self.assertEqual(controller._draft, pending)
        self.assertTrue(controller.dirty)
        self.assertEqual(calls, [])
        self.assertEqual(controller.status, "未能保存，请重试")


if __name__ == "__main__":
    unittest.main()
