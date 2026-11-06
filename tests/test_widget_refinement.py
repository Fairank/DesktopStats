"""Default widget hierarchy and invisible resizing; owned offscreen surfaces only."""
import copy
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import Property, QCoreApplication, QEvent, QObject, QPoint, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtTest import QTest

from card_layout import plan
from native_card import HardwareCard, formatted
from native_surface import MaterialSurface
from responsive_layout import default_summary, responsive_plan
from stats_config import DEFAULT
from tests import test_card_layout as fixture
from widget_catalog import from_template

ROOT = Path(__file__).resolve().parents[1]


class WidgetSummaryTests(unittest.TestCase):
    setUpClass = classmethod(fixture.CardLayoutTests.setUpClass.__func__)

    def test_default_templates_get_one_primary_and_complete_support_slots(self):
        for template in ("cpu", "gpu", "memory", "battery", "storage"):
            prefs = from_template(template)
            metrics = prefs["content"]
            self.assertTrue(default_summary(prefs, metrics))
            legacy = plan(328, 3, summary=True)
            primary, *support = legacy.readings
            self.assertGreater(primary.size, max(item.size for item in support))
            self.assertLess(primary.box.right, support[0].box.x)
            self.assertEqual(primary.box.y, support[0].box.y)
            self.assertGreater(support[1].box.y, support[0].box.bottom)
            prefs.update(form="free", width=184, height=300)
            before = copy.deepcopy(prefs)
            layout = responsive_plan(184, 300, metrics, prefs)
            self.assertEqual(prefs, before)
            self.assertEqual([item.metric for item in layout.readings], metrics)
            self.assertGreater(layout.readings[0].size, layout.readings[1].size)
            self.assertLess(layout.readings[0].box.bottom, layout.readings[1].box.y)
            self.assertEqual(layout.readings[1].box.y, layout.readings[2].box.y)
            self.assertGreaterEqual(layout.body.y, layout.title.bottom + 8)

    def test_custom_content_and_explicit_layouts_keep_existing_geometry(self):
        for field, value in (("layout_mode", "manual"), ("layout_mode", "grid"),
                             ("layout_mode", "vertical"), ("presentation", "list"),
                             ("presentation", "ring"), ("form", "bar")):
            prefs = from_template("cpu")
            prefs[field] = value
            self.assertFalse(default_summary(prefs, prefs["content"]))
        prefs = from_template("cpu")
        changed = list(reversed(prefs["content"]))
        self.assertFalse(default_summary(prefs, changed))
        prefs.update(form="free", width=344, height=168, content=changed)
        layout = responsive_plan(344, 168, changed, prefs)
        self.assertEqual([item.metric for item in layout.readings], changed)
        self.assertEqual(len(layout.readings), 3)
        self.assertGreater(layout.readings[1].box.x, layout.readings[0].box.x)

    def test_actual_painter_preserves_values_units_and_hit_targets_in_both_themes(self):
        data = dict(time=time.time(), cpu_usage=42, cpu_temp=68, cpu_frequency=4.8,
                    gpu_usage=65, gpu_temp=61, gpu_power=227, ram_percent=62,
                    ram_used_gb=31.7, ram_available_gb=19.5, ram_total_gb=64,
                    battery_percent=74, battery_time_minutes=163, battery_remaining_wh=57.2,
                    disk_percent=62, disk_used_gb=300, disk_free_gb=500)
        for language in ("zh-CN", "de", "ja"):
            for theme in ("light", "dark"):
                for template in ("cpu", "gpu", "memory", "battery", "storage"):
                    for width, height, form in ((236, 114, "wide"), (344, 168, "wide"),
                                                (184, 300, "free"), (344, 168, "free"),
                                                (170, 148, "free"), (148, 148, "free")):
                        with self.subTest(language=language, theme=theme, template=template,
                                          width=width, height=height, form=form):
                            prefs = from_template(template)
                            prefs["form"] = form
                            if form == "free":
                                prefs.update(width=width, height=height)
                            config = copy.deepcopy(DEFAULT)
                            config.update(widgets={"proof": prefs}, widget_order=["proof"],
                                          language=language, theme=theme, skin="card")
                            card = HardwareCard()
                            card.setWidth(width); card.setHeight(height)
                            card.set_config(config); card.set_key("proof"); card.set_data(data)
                            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
                            image.fill(Qt.transparent)
                            painter = QPainter(image); measured = fixture.MeasuringPainter(painter)
                            card.paint(measured); painter.end()
                            expected = [part for metric in prefs["content"]
                                        for part in formatted(data, metric, prefs)]
                            self.assertEqual([run["text"] for run in measured.runs], expected)
                            self.assertFalse(measured.overflows, measured.overflows)
                            self.assertTrue(all(item["glyph_fits"] for item in measured.labels), measured.labels)
                            layout, scale, _ = card._hit_layout()
                            for reading in layout.readings:
                                box = reading.box
                                self.assertEqual(card.metricAt((box.x+box.width/2)*scale,
                                                               (box.y+box.height/2)*scale), reading.index)
                            self.assertEqual(card.metricAt(0, 0), -1)
                            self.assertEqual(image.pixelColor(width-1, height-1).alpha(), 0)


class WidgetFixture(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.config = copy.deepcopy(DEFAULT)
        self.config.update(locked=False, widgets={"cpu": from_template("cpu")}, widget_order=["cpu"])
        self.resizes = []

    saved = Property("QVariantMap", lambda self: self.config, notify=changed)
    readings = Property("QVariantMap", lambda self: dict(time=time.time(), cpu_usage=42), notify=changed)
    history = Property("QVariantList", lambda self: [], notify=changed)

    @Slot(str, result=str)
    def tr(self, value):
        return value

    @Slot(str, result="QVariantMap")
    @Slot(str, float, result="QVariantMap")
    def resizeLimits(self, key, width=184):
        return dict(min_width=148, min_height=148, max_width=600, max_height=600)

    @Slot(str, float, float, result=bool)
    def resizeWindow(self, key, width, height):
        self.resizes.append((key, width, height))
        return True


class WidgetCornerTests(unittest.TestCase):
    setUpClass = classmethod(fixture.CardLayoutTests.setUpClass.__func__)

    def test_resize_hotspot_is_invisible_but_dragging_still_resizes(self):
        with patch("ctypes.WinDLL", side_effect=AssertionError("No native API")), \
             patch("subprocess.Popen", side_effect=AssertionError("No process")):
            qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
            qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
            ui = WidgetFixture(); engine = QQmlEngine(); warnings = []
            engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
            engine.rootContext().setContextProperty("stats", ui)
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT/"native/DesktopWidget.qml")))
            spec = dict(id="proof", width=184, height=184,
                        cells=[dict(key="cpu", x=0, y=0, width=184, height=184)])
            window = component.createWithInitialProperties(dict(spec=spec))
            self.assertIsNotNone(window, component.errorString())
            try:
                window.show(); QTest.qWait(30)
                handle = window.findChild(QObject, "resizeHandle")
                self.assertIsNotNone(handle)
                self.assertEqual((handle.width(), handle.height()), (26, 26))
                self.assertTrue(handle.isVisible())
                self.assertEqual(handle.property("cursorShape"), Qt.SizeFDiagCursor)
                self.assertEqual(handle.childItems(), [], "Resize hotspot must draw no corner marks")
                QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, QPoint(171, 171))
                self.assertTrue(window.property("resizing"))
                QTest.mouseMove(window, QPoint(205, 195), 20)
                QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, QPoint(205, 195))
                self.assertFalse(window.property("resizing"))
                self.assertEqual(ui.resizes, [("proof", 218.0, 208.0)])
                self.assertEqual((window.width(), window.height()), (218, 208))
                ui.config["locked"] = True; ui.changed.emit(); self.app.processEvents()
                self.assertFalse(handle.isVisible())
            finally:
                window.hide(); window.destroy(); window.deleteLater()
                component.deleteLater(); engine.deleteLater(); ui.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
            self.assertEqual(warnings, [])
