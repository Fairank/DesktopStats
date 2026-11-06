"""Lazy exterior diagrams in real details QML; owned offscreen windows only."""

from collections import Counter
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QUrl
from PySide6.QtGui import QWindow
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import getCppPointer

import hardware_appearance as hardware
from tests import test_top_bar_module_qml as fixture

ROOT = Path(__file__).resolve().parents[1]
GPU_ROWS = {row[0]: row for row in hardware.CATALOG if row[1] == "gpu"}


def socket_counts(image):
    source = image.property("source").toString()
    svg = ET.fromstring(unquote(source.split(",", 1)[1]))
    return Counter(node.get("class").split()[1] for node in svg.iter()
                   if node.get("class", "").startswith("hardware-socket "))


class HardwareStructureQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ModuleQmlTests.setUpClass()
        cls.app = fixture.ModuleQmlTests.app
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("Only offscreen hardware-structure tests are allowed")

    def setUp(self):
        self.native = self.enterContext(patch(
            "ctypes.WinDLL", side_effect=AssertionError("No native I/O"), create=True))
        self.process = self.enterContext(patch(
            "subprocess.Popen", side_effect=AssertionError("No process")))
        self.thread = self.enterContext(patch(
            "threading.Thread", side_effect=AssertionError("No Python thread")))
        self.state = fixture.ModuleState()
        self.state.details.update(id="b_gpu", metric="gpu_usage", family="gpu", icon="gpu",
                                  label="GPU 使用率", group_label="显卡", source="Synthetic provider")
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(
            lambda rows: self.warnings.extend(row.toString() for row in rows))
        self.component = self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.hide()
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        self.state.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()
        self.thread.assert_not_called()

    def settle(self):
        self.app.processEvents()
        QTest.qWait(10)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def publish(self, identity, reading=20):
        alias = GPU_ROWS[identity][-1][0]
        appearance = dict(hardware.appearance_for("gpu", alias), icon_set="solid")
        self.assertEqual((appearance["id"], appearance["confidence"]), (identity, "model"))
        # All model facts originate in the public identity projection. Each
        # reading delivers a fresh QVariantMap, as the actual details do.
        self.state.details = dict(copy.deepcopy(self.state.details), hardware_name=alias,
                                  hardware_appearance=appearance, numeric_value=reading,
                                  number_text=str(reading), value=str(reading) + " %")
        self.state.changed.emit()
        self.settle()
        return appearance

    def load(self, identity):
        self.publish(identity)
        self.component = QQmlComponent(
            self.engine, QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
        self.window = self.component.createWithInitialProperties({"barState": self.state})
        self.assertIsNotNone(self.window, [row.toString() for row in self.component.errors()])
        self.window.show()
        self.settle()

    def find(self, name):
        # Repeater delegates belong to the visual tree, which can differ from
        # QObject ownership. Reuse the real-details fixture's visual lookup.
        return fixture.ModuleQmlTests.find(self, name)

    def assert_image_ready(self, image):
        expression = QQmlExpression(qmlContext(image), image, "status === Image.Ready")
        result = expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        self.assertTrue(result[0] if isinstance(result, tuple) else result,
                        "The actual QML Image must be Ready")

    def assert_released(self):
        loader = self.find("topBarHardwareStructureLoader")
        self.assertFalse(loader.property("active"))
        self.assertIsNone(loader.property("item"))
        self.assertIsNone(self.window.findChild(QObject, "topBarHardwareStructureImage"))

    def open_structure(self, view="ports"):
        self.window.setProperty("showMetadata", True)
        self.window.setProperty("hardwareStructureView", view)
        self.settle()
        loader = self.find("topBarHardwareStructureLoader")
        self.assertTrue(loader.property("active"))
        self.assertIsNotNone(loader.property("item"))
        image = self.find("topBarHardwareStructureImage")
        self.assert_image_ready(image)
        self.assertTrue(image.property("source").toString().startswith("data:image/svg+xml;utf8,"))
        return loader, image

    def test_structure_is_lazy_and_fresh_readings_do_not_reload_its_image(self):
        identity = "asus-proart-5080-oc"
        self.load(identity)
        self.assertFalse(self.window.property("showMetadata"))
        self.assert_released()
        self.window.setProperty("showMetadata", True)
        self.settle()
        self.assert_released()
        loader, image = self.open_structure("ports")
        self.assertEqual(socket_counts(image), Counter(displayport=2, hdmi=1, usb_c=1))
        item_pointer = getCppPointer(loader.property("item"))[0]
        image_pointer = getCppPointer(image)[0]
        source = image.property("source")
        changes = QSignalSpy(image.sourceChanged)
        self.assertTrue(changes.isValid())
        for reading in (21, 22, 23):
            self.publish(identity, reading)
            self.assertEqual(self.window.property("hardwareStructureView"), "ports")
            self.assertEqual(getCppPointer(loader.property("item"))[0], item_pointer)
            self.assertEqual(getCppPointer(self.find("topBarHardwareStructureImage"))[0], image_pointer)
            self.assertEqual(image.property("source"), source)
        self.assertEqual(changes.count(), 0)

    def test_hidden_minimized_and_collapsed_details_release_structure_loader(self):
        self.load("asus-proart-5080-oc")
        self.open_structure()
        for pause, resume in (
            (self.window.hide, self.window.showNormal),
            (lambda: self.window.setVisibility(QWindow.Minimized), self.window.showNormal),
            (lambda: self.window.setProperty("hostMinimized", True),
             lambda: self.window.setProperty("hostMinimized", False)),
        ):
            pause()
            self.settle()
            self.assert_released()
            resume()
            self.settle()
            self.assertTrue(self.find("topBarHardwareStructureLoader").property("active"))
            self.assert_image_ready(self.find("topBarHardwareStructureImage"))
        self.window.setProperty("showMetadata", False)
        self.settle()
        self.assertEqual(self.window.property("hardwareStructureView"), "")
        self.assert_released()
        self.window.setProperty("showMetadata", True)
        self.settle()
        self.assert_released()

    def test_power_switch_uses_real_facts_and_unknown_or_slot_power_cannot_claim_sockets(self):
        self.load("powercolor-fighter-7800xt")
        loader, image = self.open_structure("ports")
        self.assertEqual(socket_counts(image), Counter(displayport=3, hdmi=1))
        image_pointer = getCppPointer(image)[0]
        power = self.find("topBarHardwareStructure_power")
        self.assertTrue(power.property("enabled"))
        changes = QSignalSpy(image.sourceChanged)
        self.assertTrue(QMetaObject.invokeMethod(power, "clicked"))
        self.settle()
        self.assertEqual(self.window.property("hardwareStructureView"), "power")
        self.assertEqual(getCppPointer(self.find("topBarHardwareStructureImage"))[0], image_pointer)
        self.assertEqual(socket_counts(image), Counter({"8pin": 2}))
        self.assertEqual(changes.count(), 1)
        self.assertIsNotNone(loader.property("item"))

        unknown = self.publish("msi-gtx1050ti-4gt-lp")
        self.assertIsNone(unknown["board_details"]["power_connectors"])
        self.assert_released()
        self.assertEqual(self.window.property("hardwareStructureView"), "")
        self.assertFalse(self.find("topBarHardwareStructure_power").property("enabled"))

        self.assertTrue(self.find("topBarHardwareStructure_ports").property("enabled"))
        self.assertIn("供电接口待核实", self.find("topBarDetailBoardSockets").property("text"))
        slot_power = self.publish("sapphire-pulse-rx6400-4g-lp")
        self.assertEqual(slot_power["board_details"]["power_connectors"], [])
        self.assert_released()
        self.assertFalse(self.find("topBarHardwareStructure_power").property("enabled"))
        self.assertIn("无需外接供电", self.find("topBarDetailBoardSockets").property("text"))
        _, image = self.open_structure("ports")
        self.assertEqual(socket_counts(image), Counter(hdmi=1, displayport=1))

    def test_rear_accessory_views_are_distinct_and_wrap_in_narrow_details(self):
        self.load('powercolor-red-devil-7800xt-bp')
        self.window.setWidth(360)
        loader,image=self.open_structure('backplate')
        original=image.property('source')
        accessory=self.find('topBarHardwareStructure_accessory')
        self.assertTrue(accessory.property('enabled'))
        self.assertTrue(QMetaObject.invokeMethod(accessory,'clicked'))
        self.settle()
        self.assertEqual(self.window.property('hardwareStructureView'),'accessory')
        self.assertNotEqual(self.find('topBarHardwareStructureImage').property('source'),original)
        self.assert_image_ready(self.find('topBarHardwareStructureImage'))
        views=self.find('topBarHardwareStructureViews')
        self.assertLessEqual(views.property('childrenRect').width(),views.width()+.1)
        self.publish('asus-proart-5080-oc')
        self.assertEqual(self.window.property('hardwareStructureView'),'')
        self.assert_released()


if __name__ == "__main__":
    unittest.main()
