"""Actual compact process card and top-bar detail, owned offscreen QML only."""

import copy
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

import native_controller as controls
import process_usage
from stats_config import DEFAULT, validate
from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]


class ProcessCardQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app

    def setUp(self):
        self.assertTrue(
            (ROOT / "native/ProcessUsageCard.qml").is_file(), "The software ranking card is missing"
        )
        self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.enterContext(patch("threading.Thread.start", side_effect=AssertionError("No worker")))
        self.monitors = []
        owner = self

        class Monitor:
            def __init__(self, callback):
                self.callback, self.generation, self.targets = callback, 0, {}
                owner.monitors.append(self)

            def set_targets(self, targets):
                if self.targets != targets:
                    self.targets = copy.deepcopy(targets)
                    self.generation += 1
                return self.generation

            def close(self):
                pass

        self.enterContext(patch.object(process_usage, "ProcessUsageMonitor", Monitor))
        with patch.object(controls, "load", return_value=validate(copy.deepcopy(DEFAULT))):
            self.ui = controls.Controller()
        self.ui._process_sampling_enabled = True  # Running lifecycle with the injected collector.
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("stats", self.ui)
        self.warnings = []
        self.engine.warnings.connect(
            lambda errors: self.warnings.extend(e.toString() for e in errors)
        )
        self.component = self.window = None

    def tearDown(self):
        if not hasattr(self, "ui"):
            return
        if self.window is not None:
            self.window.hide()
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.ui.close()
        self.assertEqual(self.warnings, [])

    def load(self, top_bar=False, widget=False):
        self.component = QQmlComponent(self.engine)
        if widget:
            self.component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/Details.qml")))
            self.window = self.component.createWithInitialProperties(
                {"widgetKey": self.ui._saved["widget_order"][0]}
            )
        elif top_bar:
            self.state = fixture.ModuleState()
            self.state.details.update(
                metric="cpu_usage", family="cpu", hardware_name="Synthetic CPU"
            )
            self.component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
            self.window = self.component.createWithInitialProperties({"barState": self.state})
        else:
            self.component.setData(
                b"""import QtQuick
import "../../native" as Product
Window { id:scene; width:336; height:400; visible:false
Product.ProcessUsageCard { x:16; y:16; width:304; provider:stats; active:scene.visible
metric:"cpu_usage"; hardwareName:"Synthetic CPU" }
}""",
                QUrl.fromLocalFile(str(ROOT / "qa-private/redesign50/process-card-test.qml")),
            )
            self.window = self.component.create()
        self.assertIsNotNone(self.window, [e.toString() for e in self.component.errors()])
        self.card = self.window.findChild(QObject, "processUsageCard")
        self.assertIsNotNone(self.card)

    def publish(self, n=5):
        monitor = self.monitors[-1]
        token = next(iter(monitor.targets))
        rows = [
            dict(
                name=("<Reader & Editor>.exe" if i == 0 else f"App{i}.exe"),
                value=50.0 - i * 5.0,
                fraction=(50.0 - i * 5.0) / 100,
                process_count=i + 1,
            )
            for i in range(n)
        ]
        monitor.callback(
            monitor.generation,
            {
                token: dict(
                    kind="cpu",
                    state="ready",
                    rows=rows,
                    unit="%",
                    denied_count=0,
                    timestamp=time.time(),
                    reason_code="",
                )
            },
        )
        QTest.qWait(20)

    def find(self, name):
        pending = [self.window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail(name + " missing from actual visual tree")

    def test_hidden_card_never_subscribes_and_shown_card_releases_on_hide(self):
        self.load()
        self.assertEqual(self.monitors, [])
        self.window.show()
        QTest.qWait(20)
        self.assertEqual(len(self.monitors[-1].targets), 1)
        self.publish()
        self.window.hide()
        QTest.qWait(10)
        self.assertEqual(self.monitors[-1].targets, {})

    def test_five_rows_remain_legible_and_plain_text_at_native_panel_width(self):
        self.load()
        self.window.show()
        self.publish(7)
        self.assertEqual(self.card.property("displayedCount"), 5)
        label = self.find("processSoftwareName0")
        self.assertEqual(label.property("text"), "<Reader & Editor>.exe")
        self.assertGreater(label.property("width"), 80)
        self.assertEqual(self.find("processSoftwareValue0").property("text"), "50 %")
        self.assertGreater(self.card.property("implicitHeight"), 160)

    def test_value_updates_retain_row_delegates_and_rank_order(self):
        self.load()
        self.window.show()
        self.publish()
        before = self.find("processSoftwareName0")
        self.publish()
        self.assertIs(self.find("processSoftwareName0"), before)
        self.assertEqual(self.card.property("displayedCount"), 5)

    def test_top_bar_detail_owns_the_same_demand_only_section(self):
        self.load(top_bar=True)
        self.assertEqual(self.monitors, [])
        self.window.show()
        self.publish()
        self.assertEqual(self.card.property("displayedCount"), 5)
        self.assertTrue(self.find("processSoftwareName4").property("visible"))
        self.window.hide()
        QTest.qWait(10)
        self.assertEqual(self.monitors[-1].targets, {})

    def test_widget_hardware_detail_has_a_scrolling_process_section(self):
        self.load(widget=True)
        self.window.show()
        self.publish()
        self.assertEqual(self.card.property("displayedCount"), 5)
        self.assertLessEqual(self.window.height(), 600)
        self.assertGreater(self.find("widgetDetailScroll").property("contentHeight"), 0)

    def test_minimized_native_detail_host_releases_process_demand_without_hiding_client(self):
        self.load(top_bar=True)
        self.window.show()
        self.publish()
        previous = self.card.property("lease")
        self.assertTrue(previous)
        self.assertTrue(self.window.setProperty("hostMinimized", True))
        QTest.qWait(10)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.monitors[-1].targets, {})
        self.assertEqual(self.card.property("lease"), "")
        self.assertTrue(self.window.setProperty("hostMinimized", False))
        QTest.qWait(10)
        self.assertTrue(self.monitors[-1].targets)
        self.assertNotEqual(self.card.property("lease"), previous)

    def test_foreground_game_guard_closes_actual_qml_detail_and_releases_software_demand(self):
        from tests import test_top_bar_runtime as bar_fixture

        config = validate(copy.deepcopy(DEFAULT) | {"top_bar": bar_fixture.config()["top_bar"]})
        self.ui._saved, self.ui._draft = config, copy.deepcopy(config)
        screen = bar_fixture.Screen("DISPLAY1", bar_fixture.PixelRect(0, 0, 1280, 900))
        guards = []

        def guard_factory(changed):
            guard = bar_fixture.ForegroundGuardFixture(changed)
            guards.append(guard)
            return guard

        runtime = SimpleNamespace(app=bar_fixture.Application([screen]), controller=self.ui,
                                  engine=self.engine, headless=True, show_settings=lambda _: None)
        manager = bar_fixture.TopBarManager(runtime, adapter=bar_fixture.QmlAdapter(),
                                            fullscreen_guard_factory=guard_factory)
        try:
            manager.apply(config)
            manager.click("DISPLAY1", "b_0")
            for _ in range(200):
                if manager._panel is not None and self.monitors:
                    break
                QTest.qWait(10)
            self.assertIsNotNone(manager._panel)
            self.assertTrue(self.monitors[-1].targets)
            guards[0].hidden = {"DISPLAY1"}
            guards[0].changed()
            QTest.qWait(20)
            self.assertIsNone(manager._panel)
            self.assertEqual(self.monitors[-1].targets, {})
            self.assertFalse(manager.hosts["DISPLAY1"].window.isVisible())
        finally:
            manager.close()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.app.processEvents()

    def test_detail_compiles_from_only_the_exported_native_assets(self):
        from tools.export_source import collect_paths

        temporary = tempfile.TemporaryDirectory(prefix="exported-detail-", dir=ROOT / "qa-private")
        self.addCleanup(temporary.cleanup)
        stage = Path(temporary.name)
        for name in collect_paths(ROOT):
            if name.startswith(("native/", "assets/")):
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
        self.component = QQmlComponent(self.engine)
        self.component.loadUrl(QUrl.fromLocalFile(str(stage / "native/TopBarDetails.qml")))
        self.assertTrue(self.component.isReady(), [e.toString() for e in self.component.errors()])


if __name__ == "__main__":
    unittest.main()
