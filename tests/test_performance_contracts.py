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


class VolumeDemandTests(unittest.TestCase):
    def test_io_only_bar_does_not_request_volume_capacity(self):
        from metrics import required_sources
        config = dict(visible=False, widgets={}, top_bar=dict(enabled=True, items=[
            dict(metric="disk_read", prefs=dict(style="duplex_inline"))]))
        self.assertEqual(required_sources(config), {"disk"})
        config["top_bar"]["items"][0]["metric"] = "disk_percent"
        self.assertEqual(required_sources(config), {"disk", "volumes"})

    def test_visible_capacity_widgets_and_legacy_percent_still_request_volumes(self):
        from metrics import required_sources
        widget = dict(enabled=True, kind="disk", content=None, primary="percent")
        config = dict(widgets={"disk": widget}, widget_order=["disk"])
        self.assertIn("volumes", required_sources(config))
        widget.update(primary="read", content=["disk_free_gb"])
        self.assertIn("volumes", required_sources(config))
        widget["enabled"] = False
        self.assertEqual(required_sources(config), set())

    def test_unrequested_volume_is_not_reported_as_a_disconnected_drive(self):
        from sensor_diagnostics import unavailable_reason
        reason = unavailable_reason(dict(volumes={}, provider_status=dict(
            volumes=dict(state="not_requested", requested=False))), "disk_percent", {"volume_target": "X:/"})
        self.assertIn("未请求", reason)
        self.assertNotIn("未连接", reason)


class WidgetHistoryQmlTests(unittest.TestCase):
    """Exercise real QML history consumers with a counted real controller getter."""

    @classmethod
    def setUpClass(cls):
        import os
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtQml import qmlRegisterType
        from PySide6.QtWidgets import QApplication

        from native_card import HardwareCard
        from native_surface import MaterialSurface

        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Widget history tests require offscreen QPA")
        directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            if (directory / name).is_file():
                QFontDatabase.addApplicationFont(str(directory / name))
        qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        from PySide6.QtCore import Property
        from PySide6.QtQml import QQmlEngine

        class CountedController(controls.Controller):
            history_reads = 0

            def get_history(self):
                self.history_reads += 1
                return list(self._history)

            history = Property("QVariantList", get_history, notify=controls.Controller.dataChanged)

        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.write = self.enterContext(patch.object(controls, "save"))
        self.enterContext(patch.object(controls, "set_autostart"))
        initial = copy.deepcopy(DEFAULT)
        initial["widgets"]["cpu"]["chart"] = False
        initial["widgets"]["gpu"]["chart"] = False
        with patch.object(controls, "load", return_value=initial):
            self.ui = CountedController()
        self.ui.receive(dict(time=time.time(), cpu_usage=20, cpu_temp=60, gpu_temp=55))
        self.ui.history_reads = 0
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(
            lambda values: self.warnings.extend(value.toString() for value in values)
        )
        self.window = self.component = None

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent

        self.ui.close()
        if self.window is not None:
            self.assertFalse(self.window.isVisible())
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])

    def load(self, canvas=False):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent

        from stats_config import ASSETS

        self.component = QQmlComponent(self.engine)
        if canvas:
            self.component.setData(b'''import QtQuick
import "." as Product
Window {visible:false;width:900;height:500
 Product.ContentCanvas {objectName:"historyCanvas";anchors.fill:parent;widgetKey:"cpu";active:true}
}''', QUrl.fromLocalFile(str(ASSETS / "native/WidgetHistoryFixture.qml")))
            self.window = self.component.create()
        else:
            self.component.loadUrl(QUrl.fromLocalFile(str(ASSETS / "native/DesktopWidget.qml")))
            spec = dict(id="history-fixture", width=336, height=168, cells=[
                dict(key="cpu", x=0, y=0, width=168, height=168),
                dict(key="gpu", x=168, y=0, width=168, height=168),
            ])
            self.window = self.component.createWithInitialProperties(dict(spec=spec))
        self.assertIsNotNone(self.window, self.component.errorString())
        self.app.processEvents()
        self.assertFalse(self.window.isVisible())

    def items(self):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(item.childItems())

    def card(self, key="cpu"):
        from native_card import HardwareCard

        return next(item for item in self.items()
                    if isinstance(item, HardwareCard) and item.property("moduleKey") == key)

    def canvas(self):
        return next(item for item in self.items() if item.objectName() == "historyCanvas")

    def sample(self, value):
        self.ui._reading_notify_at = float("-inf")
        self.ui.receive(dict(time=time.time(), cpu_usage=value, cpu_temp=60, gpu_temp=55))
        self.app.processEvents()

    def test_desktop_chart_off_skips_history_getter_but_keeps_fresh_readings(self):
        self.load()
        self.assertEqual(self.ui.history_reads, 0)
        for value in range(10):
            self.sample(value)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("readings")["cpu_usage"], 9)
        self.assertEqual(self.card().property("history"), [])
        self.assertEqual(self.card("gpu").property("history"), [])

    def test_desktop_uses_saved_chart_flag_and_restores_latest_history_on_commit(self):
        self.load()
        self.ui.changeWidget("cpu", "chart", True)
        self.sample(31)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history"), [])
        self.assertTrue(self.ui.applyDesktop())
        self.app.processEvents()
        self.assertGreater(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history")[-1]["cpu_usage"], 31)
        self.assertEqual(self.card("gpu").property("history"), [])
        self.ui.changeWidget("cpu", "chart", False)
        self.assertTrue(self.ui.applyDesktop())
        self.app.processEvents()
        self.assertEqual(self.card().property("history"), [])
        self.ui.history_reads = 0
        self.sample(47)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("readings")["cpu_usage"], 47)

    def test_desktop_appearance_config_gates_each_card_without_modifying_saved_flags(self):
        self.load()
        preview = copy.deepcopy(self.ui.saved)
        preview["widgets"]["gpu"]["chart"] = True
        self.window.setProperty("appearanceConfig", preview)
        self.app.processEvents()
        self.assertEqual(self.card().property("history"), [])
        self.assertEqual(self.card("gpu").property("history")[-1]["cpu_usage"], 20)
        self.assertFalse(self.ui.saved["widgets"]["gpu"]["chart"])
        self.window.setProperty("appearanceConfig", None)
        self.app.processEvents()
        self.ui.history_reads = 0
        self.sample(63)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card("gpu").property("history"), [])

    def test_desktop_legacy_missing_or_nonboolean_chart_flag_keeps_history_enabled(self):
        self.load()
        for flag in (None, 0, "false", "missing"):
            with self.subTest(flag=flag):
                preview = copy.deepcopy(self.ui.saved)
                if flag == "missing":
                    preview["widgets"]["cpu"].pop("chart")
                else:
                    preview["widgets"]["cpu"]["chart"] = flag
                self.ui.history_reads = 0
                self.window.setProperty("appearanceConfig", preview)
                self.app.processEvents()
                self.assertGreater(self.ui.history_reads, 0)
                self.assertEqual(self.card().property("history")[-1]["cpu_usage"], 20)

    def test_canvas_chart_toggle_refreshes_history_without_waiting_for_another_sample(self):
        self.load(canvas=True)
        self.assertEqual(self.ui.history_reads, 0)
        self.ui.changeWidget("cpu", "chart", True)
        self.app.processEvents()
        self.assertGreater(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history")[-1]["cpu_usage"], 20)
        self.assertFalse(self.ui.saved["widgets"]["cpu"]["chart"])
        self.ui.changeWidget("cpu", "chart", False)
        self.app.processEvents()
        self.assertEqual(self.card().property("history"), [])
        self.ui.history_reads = 0
        self.sample(77)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.canvas().property("previewReadings")["cpu_usage"], 77)

    def test_canvas_inactive_and_resizing_keep_history_frozen_then_resume_fresh(self):
        self.load(canvas=True)
        canvas = self.canvas()
        canvas.setProperty("resizing", True)
        self.ui.changeWidget("cpu", "chart", True)
        self.sample(40)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history"), [])
        canvas.setProperty("resizing", False)
        self.app.processEvents()
        self.assertGreater(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history")[-1]["cpu_usage"], 40)
        frozen = self.card().property("history")
        canvas.setProperty("active", False)
        self.ui.history_reads = 0
        self.sample(81)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history"), frozen)
        canvas.setProperty("active", True)
        self.app.processEvents()
        self.assertEqual(self.card().property("history")[-1]["cpu_usage"], 81)

    def test_canvas_module_switch_uses_its_own_draft_chart_flag_and_current_history(self):
        self.ui.changeWidget("gpu", "chart", True)
        self.load(canvas=True)
        self.assertEqual(self.ui.history_reads, 0)
        self.canvas().setProperty("widgetKey", "gpu")
        self.app.processEvents()
        self.assertGreater(self.ui.history_reads, 0)
        self.assertEqual(self.card("gpu").property("history")[-1]["cpu_usage"], 20)
        self.canvas().setProperty("widgetKey", "cpu")
        self.app.processEvents()
        self.ui.history_reads = 0
        self.sample(92)
        self.assertEqual(self.ui.history_reads, 0)
        self.assertEqual(self.card().property("history"), [])


class PreviewInspectionDemandTests(unittest.TestCase):
    """Only readings missing from the saved runtime warm discovery for previews."""

    def setUp(self):
        self.configuration("cpu_usage", "cpu_temp")
        for name in ("save", "set_autostart"):
            guard = patch.object(controls, name, side_effect=AssertionError("No persistence"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(controls.sensors, "Sampler", side_effect=AssertionError("No hardware"))
        guard.start()
        self.addCleanup(guard.stop)

    def configuration(self, *metrics):
        config = copy.deepcopy(DEFAULT)
        config["visible"] = False
        for prefs in config["widgets"].values():
            prefs["enabled"] = False
        config["top_bar"].update(enabled=bool(metrics), items=[
            dict(id=f"b_test_{index}", metric=metric, prefs={})
            for index, metric in enumerate(metrics)
        ])
        with patch.object(controls, "load", return_value=validate(config)):
            self.ui = controls.Controller()

    @staticmethod
    def binding(identifier):
        return dict(provider=PROVIDER, sensor_id=identifier, sensor_type="Temperature",
                    name="Synthetic temperature", hardware_name="Synthetic board")

    def test_cosmetic_edits_and_preferences_need_no_extra_hardware(self):
        self.ui.changeWidget("cpu", "title", "Pending title")
        self.ui.change("theme", "dark")
        self.ui.changeTopBar("spacing", 12)
        before = copy.deepcopy((self.ui.saved, self.ui.draft, self.ui._undo_drafts))
        for scope, key in (("desktop", "cpu"), ("topbar", ""), ("preferences", "cpu"),
                           ("history", "gpu"), ("unknown", ""), ("desktop", "missing")):
            self.assertFalse(self.ui.previewNeedsInspection(scope, key), (scope, key))
        self.assertEqual((self.ui.saved, self.ui.draft, self.ui._undo_drafts), before)

    def test_disabled_selected_preview_adds_only_its_own_demand(self):
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "gpu"))
        self.assertFalse(self.ui.saved["widgets"]["gpu"]["enabled"])
        self.assertFalse(self.ui.draft["widgets"]["gpu"]["enabled"])
        self.assertFalse(self.ui.saved["visible"])
        self.ui.changeWidget("gpu", "title", "Offscreen edit")
        self.ui.changeWidget("power", "content", ["storage_temp"])
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.assertFalse(self.ui.previewNeedsInspection("topbar", ""))

    def test_cpu_temperature_is_explicit_even_when_cpu_family_is_already_active(self):
        self.configuration("cpu_usage")
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.ui._draft["widgets"]["cpu"].update(primary="frequency", secondary="usage")
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.ui._draft["top_bar"]["items"].append(
            dict(id="b_extra_temperature", metric="cpu_temp", prefs={}))
        self.assertTrue(self.ui.previewNeedsInspection("topbar", ""))

    def test_disabled_bar_still_previews_its_items_without_becoming_enabled(self):
        self.configuration("cpu_usage")
        self.ui._draft["top_bar"].update(enabled=False, items=[
            dict(id="b_gpu_preview", metric="gpu_usage", prefs={})])
        self.assertTrue(self.ui.previewNeedsInspection("topbar", ""))
        self.assertFalse(self.ui.draft["top_bar"]["enabled"])
        self.ui._draft["widgets"]["cpu"].update(primary="usage", secondary="frequency")
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))

    def test_capacity_preview_adds_volumes_without_changing_throughput_demand(self):
        self.configuration("disk_read")
        self.ui._draft["widgets"]["cpu"]["content"] = ["disk_read"]
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.ui._draft["widgets"]["cpu"]["content"] = ["disk_free_gb"]
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "cpu"))

    def test_new_external_binding_keeps_fresh_catalog_discovery(self):
        self.configuration("cpu_usage")
        old = self.binding("/synthetic/old")
        self.ui._saved["top_bar"]["items"][0]["metric"] = "external_1"
        self.ui._saved["top_bar"]["items"][0]["prefs"]["sensor_bindings"] = {"external_1": old}
        prefs = self.ui._draft["widgets"]["cpu"]
        prefs.update(content=["external_1"], sensor_bindings={"external_1": dict(old)})
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))
        prefs["sensor_bindings"]["external_1"] = self.binding("/synthetic/new")
        before = copy.deepcopy((self.ui.saved, self.ui.draft))
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.assertEqual((self.ui.saved, self.ui.draft), before)
        self.assertEqual(self.ui._data, {})

    def test_dormant_saved_binding_does_not_count_as_active_runtime_demand(self):
        self.configuration("cpu_usage")
        active = self.binding("/synthetic/active")
        dormant = self.binding("/synthetic/dormant")
        item = self.ui._saved["top_bar"]["items"][0]
        item.update(metric="external_1", prefs={"sensor_bindings": {"external_1": active}})
        self.ui._saved["widgets"]["cpu"].update(content=["external_1"],
            sensor_bindings={"external_1": dormant}, enabled=False)
        self.ui._draft["widgets"]["cpu"] = copy.deepcopy(self.ui._saved["widgets"]["cpu"])
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "cpu"))
        self.assertFalse(self.ui.saved["widgets"]["cpu"]["enabled"])
        self.ui._saved["widgets"]["cpu"]["enabled"] = True
        self.assertTrue(self.ui.previewNeedsInspection("desktop", "cpu"))  # Desktop still hidden.
        self.ui._saved["visible"] = True
        self.assertFalse(self.ui.previewNeedsInspection("desktop", "cpu"))


if __name__ == "__main__":
    unittest.main()
