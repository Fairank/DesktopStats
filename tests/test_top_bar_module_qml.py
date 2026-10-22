"""Real QML module/skin interactions; owned offscreen windows and synthetic IO."""

import base64
import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QFontDatabase, QImage, QPainter, QWheelEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from localization import MESSAGES, translate
from native_surface import MaterialSurface
from skin_styles import SKINS
from stats_config import DEFAULT

ROOT = Path(__file__).resolve().parents[1]


class ModuleState(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.locale, self.mode = "zh-CN", "light"
        self.preferences = copy.deepcopy(DEFAULT)
        self.preferences["language"] = self.locale
        self.preferences["top_bar"]["items"] = [dict(id="b_cpu", metric="cpu_usage", prefs={"style": "label_value"})]
        self.row = dict(id="b_cpu", metric="cpu_usage", label="CPU 使用率", value="0 %", number_text="0",
                        unit_text="%", unit="%", available=True, numeric_value=0, style="label_value",
                        trend_available=True, trend_points=[dict(x=0, y=.8), None, dict(x=.6, y=.5), dict(x=1, y=.2)],
                        history=[0, None, 20, 30], related=[], group_label="处理器")
        self.details = copy.deepcopy(self.row)
        self.actions = []

    draft = Property("QVariantMap", lambda self: self.preferences, notify=changed)
    config = Property("QVariantMap", lambda self: dict(self.preferences, theme=self.mode, language=self.locale), notify=changed)
    previewRow = Property("QVariantMap", lambda self: self.row, notify=changed)
    detail = Property("QVariantMap", lambda self: self.details, notify=changed)
    language = Property(str, lambda self: self.locale, notify=changed)
    theme = Property(str, lambda self: self.mode, notify=changed)
    texts = Property("QVariantMap", lambda self: MESSAGES[self.locale], notify=changed)
    material = Property("QVariantMap", lambda self: {}, constant=True)
    motionEnabled = Property(bool, lambda self: False, constant=True)
    sensorRevision = Property(int, lambda self: 1, constant=True)
    devices = Property("QVariantMap", lambda self: {"networks": {"wifi": {"label": "Synthetic Wi-Fi adapter"}}}, constant=True)
    previewWindows = Property("QVariantList", lambda self: [], constant=True)
    coatingAllowed = Property(bool, lambda self: False, constant=True)
    catalog = Property("QVariantMap", lambda self: {"skins": [dict(id=key, label=translate(value, self.locale)) for key, value in SKINS.items()]}, notify=changed)
    ink = Property(str, lambda self: "#f5f6f8" if self.mode == "dark" else "#202833", notify=changed)
    muted = Property(str, lambda self: "#b8bdc7" if self.mode == "dark" else "#566272", notify=changed)
    fontFamily = Property(str, lambda self: "Microsoft YaHei UI" if self.locale == "zh-CN" else "Segoe UI Variable", notify=changed)
    panelMaximumHeight = Property(float, lambda self: 640.0, constant=True)
    detailCoatingTranslucent = Property(bool, lambda self: False, constant=True)
    overflowRows = Property("QVariantList", lambda self: [], constant=True)

    @Slot(str, result=str)
    def tr(self, text):
        return translate(text, self.locale)

    @Slot(str, result="QVariantMap")
    def previewState(self, _key):
        return dict(coating_translucent=False, blur_configured=False)

    @Slot(str, str, result="QVariantMap")
    def metricInfoFor(self, _key, metric):
        return dict(scope="networks" if metric.startswith("net_") else "", unit=self.row["unit"])

    @Slot(str, result="QVariantMap")
    def topBarStylePreviewRow(self, _identifier):
        return copy.deepcopy(self.row)

    @Slot(str, str, "QVariant")
    def changeTopBarItem(self, identifier, field, value):
        self.actions.append((identifier, field, value))
        self.preferences["top_bar"]["items"][0]["prefs"][field] = value
        if field == "style":
            self.row["style"] = value
        self.changed.emit()

    @Slot(str, str, str)
    def placeTopBarMetric(self, identifier, before, placement):
        self.actions.append((identifier, before, placement))

    @Slot(str)
    def removeTopBarMetric(self, identifier):
        self.actions.append(("remove", identifier))

    @Slot()
    def closePanel(self):
        self.actions.append("close")

    @Slot()
    def openSettings(self):
        self.actions.append("edit")

    @Slot()
    def enterPanel(self):
        pass

    @Slot()
    def leavePanel(self):
        pass

    @Slot(str)
    def clickMetric(self, identifier):
        self.actions.append(identifier)


class ModuleQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != "offscreen":
            raise RuntimeError("No visible native tests")
        for name in ("SegUIVar.ttf", "segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
            path = Path("C:/Windows/Fonts") / name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
        qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")

    def setUp(self):
        self.native = self.enterContext(patch("ctypes.WinDLL", side_effect=AssertionError("No native API")))
        self.process = self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("No process")))
        self.state = ModuleState()
        self.engine = QQmlEngine()
        self.warnings = []
        self.engine.warnings.connect(lambda errors: self.warnings.extend(item.toString() for item in errors))
        self.engine.rootContext().setContextProperty("stats", self.state)
        self.window = self.component = None

    def tearDown(self):
        if self.window is not None:
            self.window.hide()
            self.window.destroy()
            self.window.deleteLater()
        if self.component is not None:
            self.component.deleteLater()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(self.warnings, [])
        self.native.assert_not_called()
        self.process.assert_not_called()

    def load(self, kind):
        self.component = QQmlComponent(self.engine)
        if kind == "details":
            self.component.loadUrl(QUrl.fromLocalFile(str(ROOT / "native/TopBarDetails.qml")))
            self.window = self.component.createWithInitialProperties({"barState": self.state})
        else:
            if kind == "inspector":
                child = '''Product.TopBarItemInspector { objectName:"inspector"; x:16;y:16;width:scene.panelWidth;
                item:stats.draft.top_bar.items[0];row:stats.previewRow }'''
            elif kind == "inspector_scroll":
                child = '''ScrollView {id:outer;objectName:"outerInspectorScroll";x:16;y:16;
                    width:scene.panelWidth;height:scene.height-32;contentWidth:availableWidth;contentHeight:inspected.implicitHeight;clip:true;
                    Product.TopBarItemInspector {id:inspected;objectName:"inspector";width:outer.availableWidth;
                        item:stats.draft.top_bar.items[0];row:stats.previewRow;
                        onRevealRequested:target=>{const flick=outer.contentItem;const top=target.mapToItem(inspected,0,0).y;const bottom=top+target.height;let next=flick.contentY;if(top<next+8)next=top-8;else if(bottom>next+flick.height-8)next=bottom-flick.height+8;flick.contentY=Math.max(0,Math.min(Math.max(0,flick.contentHeight-flick.height),next))}} }'''
            elif kind == "metric":
                child = '''Product.TopBarMetricContent {objectName:"metricPreview";x:16;y:16;
                    width:implicitWidth;height:implicitHeight;row:stats.previewRow;
                    reserveValueWidth:scene.reserveValue;ink:stats.ink;muted:stats.muted;fontFamily:stats.fontFamily}'''
            else:
                child = '''
                Product.SkinPicker { objectName:"picker";x:16;y:16;width:scene.width-32;
                    compact:scene.compactSkin;allowGlobal:true;widgetKey:"cpu";value:scene.selectedSkin;
                    onPicked:selected=>scene.selectedSkin=selected }'''
            code = '''import QtQuick
import QtQuick.Controls
import "../../native" as Product
Window { id:scene; width:700;height:760;visible:false;color:stats.theme==="dark"?"#20242b":"#f6f8fb";
 property real panelWidth:280;property bool compactSkin:false;property string selectedSkin:"global";property bool reserveValue:false;
 Shortcut {sequence:"Escape";onActivated:scene.hide()}
 ''' + child + "\n}"
            self.component.setData(code.encode(), QUrl.fromLocalFile(str(ROOT / "qa-private/redesign29/module-fixture.qml")))
            self.window = self.component.create()
        self.assertIsNotNone(self.window, [error.toString() for error in self.component.errors()])
        self.window.show()  # QPA platform is asserted offscreen before creation.
        QTest.qWait(30)

    def find(self, name):
        result = self.window.findChild(QObject, name)
        if result is None:
            pending = [self.window.contentItem()]
            while pending:
                item = pending.pop()
                if item.objectName() == name:
                    return item
                pending.extend(item.childItems())
        self.assertIsNotNone(result, name)
        return result

    def click(self, name):
        item = self.find(name)
        self.assertTrue(item.isVisible(), name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        self.assertTrue(0 <= point.x() < self.window.width() and 0 <= point.y() < self.window.height(), name)
        QTest.mouseClick(self.window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(10)

    def open_styles(self):
        if not self.find("inspector").property("galleryOpen"):
            self.click("topBarStyleChooser")
        self.assertIsNotNone(self.find("topBarDisplayStyle"))
        for _ in range(20):
            if self.find("topBarStyleGallery").height() > 1:
                break
            QTest.qWait(10)
        self.assertGreater(self.find("topBarStyleGallery").height(), 1)
        QTest.qWait(30)  # Finish the one-shot container reveal before input.

    def publish(self):
        self.state.changed.emit()
        QTest.qWait(20)

    def proof(self, name):
        directory = os.environ.get("DESKTOP_STATS_QA_PROOF")
        if directory:
            target = Path(directory).resolve()
            self.assertTrue(target.is_relative_to(ROOT / "qa-private"))
            target.mkdir(parents=True, exist_ok=True)
            self.window.requestUpdate()
            QTest.qWait(40)  # A settled static proof, never a first-frame claim.
            self.assertTrue(self.window.grabWindow().save(str(target / (name + ".png"))))

    def test_single_zero_keeps_split_unit_and_full_legacy_value(self):
        self.load("details")
        self.assertEqual(self.find("topBarDetailValue").property("text"), "0")
        self.assertEqual(self.find("topBarDetailUnit").property("text"), "%")
        self.state.details = dict(self.state.details, value="20%")
        del self.state.details["number_text"]
        self.publish()
        self.assertEqual(self.find("topBarDetailValue").property("text"), "20%")

    def pair(self):
        self.state.details.update(label="下载速度", group_label="网络", history_samples=4, hardware_name="Synthetic Wi-Fi adapter",
            paired_rows=[dict(label="下载", direction="download", number_text="0.00", unit_text="MB/s", value="0.00 MB/s", available=True,
                              trend_available=True, trend_points=[dict(x=0, y=.85), dict(x=.3, y=.4), None, dict(x=.7, y=.6), dict(x=1, y=.2)]),
                         dict(label="上传", direction="upload", number_text="999.99", unit_text="MB/s", value="999.99 MB/s", available=True,
                              trend_available=True, trend_points=[dict(x=0, y=.25), dict(x=.3, y=.55), dict(x=.7, y=.7), dict(x=1, y=.5)])])

    def test_duplex_zero_missing_and_units_are_not_duplicated(self):
        self.pair()
        self.state.details["paired_rows"][1]["available"] = False
        self.load("details")
        self.assertFalse(self.find("topBarDetailValue").isVisible())
        self.assertEqual(self.find("topBarPairValue_0").property("text"), "0.00")
        self.assertEqual(self.find("topBarPairUnit_0").property("text"), "MB/s")
        self.assertEqual(self.find("topBarPairValue_1").property("text"), "—")
        self.assertEqual(self.find("topBarPairUnit_1").property("text"), "")

    def test_duplex_geometry_and_complete_units_in_both_languages_and_themes(self):
        self.pair()
        self.load("details")
        for locale, mode in (("zh-CN", "light"), ("de", "dark")):
            self.state.locale, self.state.mode = locale, mode
            self.state.details.update(label=translate("下载速度", locale), group_label=translate("网络", locale))
            for row, label in zip(self.state.details["paired_rows"], ("下载速度", "上传速度"), strict=True):
                row["label"] = translate(label, locale)
            self.publish()
            for index in range(2):
                item = self.find("topBarPairUnit_" + str(index))
                self.assertEqual(item.property("text"), "MB/s")
                edge = item.mapToScene(QPointF(item.width(), 0)).x()
                self.assertLessEqual(edge, self.window.width() - 15)
            if mode == "dark":
                frame = self.window.grabWindow()
                self.assertLess(frame.pixelColor(round(310 * frame.devicePixelRatio()), round(110 * frame.devicePixelRatio())).value(), 120)
            self.proof("module-duplex-" + locale + "-" + mode)

    def test_duplex_histories_are_per_direction_and_missing_or_gaps_are_not_invented(self):
        self.pair()
        self.state.details["trend_available"] = False
        self.load("details")
        chart = self.find("topBarDetailTrend")
        self.assertTrue(chart.isVisible())
        self.assertEqual(self.find("topBarPairTrendLabel_0").property("text"), "下载")
        self.assertEqual(self.find("topBarPairTrendLabel_1").property("text"), "上传")
        self.state.details["paired_rows"][0]["available"] = False
        self.publish()
        self.assertTrue(chart.isVisible())
        self.state.details["paired_rows"][1]["available"] = False
        self.publish()
        self.assertFalse(chart.isVisible())
        self.state.details["paired_rows"][0].update(available=True, trend_points=[dict(x=0, y=.4), None, dict(x=1, y=.7)])
        self.publish()
        self.assertFalse(chart.isVisible(), "Disconnected isolated points are not a readable trend")

    def test_explicit_group_keeps_eight_related_readings_and_real_sample_count(self):
        self.state.details.update(group_label="图形处理器", history_samples=4,
            related=[dict(label="读数" + str(i), value=str(i) + " W", available=True) for i in range(8)])
        self.load("details")
        self.assertEqual(self.find("topBarRelatedTitle").property("text"), "图形处理器")
        self.assertTrue(self.find("topBarRelated_7").isVisible())
        self.assertEqual(self.find("topBarDetailHistoryCount").property("text").split()[0], "4")
        plot = self.find("topBarDetailTrend")
        self.assertGreaterEqual(plot.width(), 230)
        for index in range(3):
            axis = self.find("topBarTrendAxis_" + str(index))
            self.assertGreaterEqual(axis.x(), plot.x() + plot.width() + 7.9)
            self.assertLessEqual(axis.mapToScene(QPointF(axis.width(), 0)).x(), self.window.width() - 15)
            self.assertTrue(axis.property("text"))
            self.assertGreaterEqual(axis.width(), axis.implicitWidth())
        self.state.details["available"] = False
        self.publish()
        self.assertFalse(self.find("topBarDetailTrend").isVisible())

    def test_detail_axes_summaries_and_elapsed_use_real_pair_history(self):
        self.pair()
        self.state.details.update(unit="MB/s", history_samples=4, history_elapsed_s=7.5)
        down, up = self.state.details["paired_rows"]
        down.update(number_text="3.00", trend=[1, None, 2, 3], unit="MB/s", trend_minimum=0, trend_maximum=3)
        up.update(number_text="0.00", trend=[0, .5, .2, 0], unit="MB/s", trend_minimum=0, trend_maximum=3)
        self.load("details")
        self.assertEqual(self.find("topBarTrendAxis_0").property("text"), "3")
        self.assertEqual(self.find("topBarTrendAxis_2").property("text"), "0")
        self.assertEqual(self.find("topBarDetailHistoryCount").property("text"), "4 次采样")
        self.assertEqual(self.find("topBarDetailHistoryElapsed").property("text"), "7.5 s")
        self.assertEqual(self.find("topBarHistorySummaryValue_0").property("text"), "3.00 MB/s")
        self.assertEqual(self.find("topBarHistorySummaryValue_1").property("text"), "0.50 MB/s")
        self.state.details["history_elapsed_s"] = None
        self.publish()
        self.assertFalse(self.find("topBarDetailHistoryElapsed").isVisible(), "No invented fixed duration")
        self.window.setProperty("nativeRounded", True)
        self.assertEqual(self.find("topBarDetailsMaterialSurface").property("cornerRadius"), 0)
        self.window.setProperty("nativeRounded", False)
        self.assertEqual(self.find("topBarDetailsMaterialSurface").property("cornerRadius"), 16)

    def test_detail_source_footer_remains_scrollable_and_clickable_in_short_window(self):
        self.state.details.update(hardware_name="0", source="Synthetic NVML",
            related=[dict(label="Reading " + str(i), value=str(i) + " W", available=True) for i in range(8)])
        self.load("details")
        self.window.resize(320, 280)
        QTest.qWait(20)
        scroll = self.find("topBarDetailScroll")
        self.assertGreater(scroll.property("contentHeight"), scroll.height())
        point = scroll.mapToScene(scroll.boundingRect().center())
        wheel = QWheelEvent(point, point, QPoint(0, 0), QPoint(0, -360), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        self.app.sendEvent(self.window, wheel)
        QTest.qWait(40)
        self.assertGreater(scroll.property("contentY"), 0)
        QMetaObject.invokeMethod(scroll, "cancelFlick")
        scroll.setProperty("contentY", scroll.property("contentHeight") - scroll.height())
        QTest.qWait(20)
        self.assertEqual(self.find("topBarDetailMetadataSummary").property("text"), "设备与来源")
        self.assertFalse(self.find("topBarDetailDeviceName").isVisible(), "Do not headline a bare provider index")
        self.click("topBarDetailMetadataToggle")
        self.assertTrue(self.window.property("showMetadata"))
        scroll.setProperty("contentY", scroll.property("contentHeight") - scroll.height())
        QTest.qWait(20)
        source = self.find("topBarDetailSource")
        self.assertTrue(source.isVisible())
        self.assertEqual(source.property("text"), "Synthetic NVML")
        self.assertLessEqual(source.mapToScene(QPointF(0, source.height())).y(), self.window.height()-15)

    def test_capacity_requires_complete_real_values_and_keeps_zero(self):
        self.state.details.update(label="内存占用率", capacity_summary=dict(label="内存已用", used_text="0.0 GB", total_text="32.0 GB", fraction=0))
        self.load("details")
        capacity = self.find("topBarDetailCapacity")
        self.assertTrue(capacity.isVisible())
        self.assertEqual(self.find("topBarDetailCapacityValue").property("text"), "0.0 GB / 32.0 GB")
        self.assertEqual(self.find("topBarDetailCapacityFill").width(), 0)
        self.state.details["capacity_summary"].update(used_text="21.0 GB", fraction=21 / 32)
        self.state.details.update(number_text="65.6", value="65.6 %")
        self.publish()
        fill = self.find("topBarDetailCapacityFill")
        self.assertAlmostEqual(fill.width() / fill.parentItem().width(), 21 / 32)
        self.proof("module-capacity-real-values")
        for invalid in ({}, dict(used_text="21.0 GB", fraction=.6), dict(used_text="", total_text="32.0 GB", fraction=0),
                        dict(used_text="21.0 GB", total_text="32.0 GB", fraction=1.1)):
            self.state.details["capacity_summary"] = invalid
            self.publish()
            self.assertFalse(capacity.isVisible())

    def test_all_eight_styles_remain_real_mouse_targets_with_canonical_samples(self):
        self.load("inspector")
        for style in ("label_value", "value", "icon_value", "trend_value", "bar_value", "ring_value", "graph", "stacked"):
            self.open_styles()
            self.assertEqual(self.find("topBarStyleSample_" + style).scale(), 1)
            before = len(self.state.actions)
            self.click("topBarStyle_" + style)
            self.assertEqual(self.state.actions[-1], ("b_cpu", "style", style))
            self.assertEqual(len(self.state.actions), before + 1)
            self.assertFalse(self.find("inspector").property("galleryOpen"))
            self.assertTrue(self.find("topBarStyleChooser").hasActiveFocus())
        self.assertFalse(self.window.findChild(QObject, "topBarStyle_duplex"))

    def test_duplex_is_capability_gated_and_narrow_formats_do_not_push_out(self):
        self.pair()
        self.state.row.update(self.state.details)
        self.state.row.update(metric="net_download", label="下载速度", group_label="网络", unit="MB/s", pair_supported=True,
                              value="0.00 MB/s", number_text="0.00", unit_text="MB/s")
        self.state.preferences["top_bar"]["items"][0]["metric"] = "net_download"
        self.load("inspector")
        self.window.resize(312, 760)
        QTest.qWait(20)
        self.open_styles()
        self.click("topBarStyle_duplex")
        self.assertEqual(self.state.actions[-1], ("b_cpu", "style", "duplex"))
        self.open_styles()
        self.click("topBarStyle_duplex_inline")
        self.assertEqual(self.state.actions[-1], ("b_cpu", "style", "duplex_inline"))
        for name in ("topBarPlacement", "topBarPrecision", "topBarNetworkUnit", "topBarDevice"):
            item = self.find(name)
            point = item.mapToItem(self.find("inspector"), QPointF(item.width(), 0))
            self.assertLessEqual(point.x(), 281, name)
        placement_y = self.find("topBarPlacement").mapToScene(QPointF()).y()
        precision_y = self.find("topBarPrecision").mapToScene(QPointF()).y()
        self.assertGreater(placement_y, precision_y)
        self.window.resize(312, round(self.find("inspector").implicitHeight() + 32))
        QTest.qWait(20)
        self.proof("module-inspector-network-280")

    def assert_pair_content_geometry(self):
        metric = self.find("metricPreview")
        first, second = self.find("topBarPair_0"), self.find("topBarPair_1")
        for index, line in enumerate((first, second)):
            point = line.mapToItem(metric, QPointF(line.width(), line.height()))
            self.assertLessEqual(point.x(), metric.width() + .1)
            self.assertLessEqual(point.y(), metric.height() + .1)
            expected = self.state.row["paired_rows"][index]
            self.assertEqual(self.find("topBarPairNumber_" + str(index)).property("text"), expected["number_text"])
            if expected["unit_text"]:
                unit = next(item for item in line.childItems() if item.property("text") == expected["unit_text"])
                self.assertGreaterEqual(unit.width() + .1, unit.implicitWidth())
                self.assertLessEqual(unit.x() + unit.width(), line.width() + .1)
        if self.state.row["style"] == "duplex_inline":
            self.assertAlmostEqual(first.y(), second.y())
            self.assertGreaterEqual(second.x(), first.x() + first.width() + 11.9)
        else:
            self.assertAlmostEqual(first.x(), second.x())
            self.assertGreaterEqual(second.y(), first.y() + first.height())
        expected_dpr = os.environ.get("DESKTOP_STATS_QA_EXPECT_DPR")
        if expected_dpr:
            self.assertAlmostEqual(self.window.devicePixelRatio(), float(expected_dpr))

    def test_duplex_content_zero_missing_and_inline_units_fit(self):
        self.pair()
        self.state.row.update(self.state.details)
        self.load("metric")
        self.window.resize(450, 80)
        for style in ("duplex", "duplex_inline"):
            for available in (True, False):
                self.state.row["style"] = style
                self.state.row["paired_rows"][1].update(available=available, number_text="999.99" if available else "—", unit_text="MB/s" if available else "")
                self.publish()
                self.assert_pair_content_geometry()
                if available:
                    self.proof("metric-" + style + "-dpr" + str(self.window.devicePixelRatio()))

    def test_duplex_reserved_geometry_in_preview_is_bounded(self):
        self.pair()
        self.state.row.update(self.state.details)
        for row in self.state.row["paired_rows"]:
            row.update(number_text="0.00", value="0.00 MB/s")
        self.load("metric")
        self.window.setProperty("reserveValue", True)
        for style in ("duplex", "duplex_inline"):
            self.state.row["style"] = style
            self.publish()
            self.assert_pair_content_geometry()

    def test_gauges_use_capability_not_percent_unit_alone(self):
        self.state.row.update(unit="%", gauge_supported=False)
        self.load("inspector")
        self.open_styles()
        self.assertFalse(self.window.findChild(QObject, "topBarStyle_bar_value"))
        self.assertFalse(self.window.findChild(QObject, "topBarStyle_ring_value"))
        self.assertTrue(self.find("topBarStyle_value").isVisible())

    def test_six_skin_miniatures_have_production_coatings_and_clear_readings(self):
        self.load("skin")
        self.window.resize(700, 540)
        QTest.qWait(20)
        for mode in ("light", "dark"):
            self.state.mode = mode
            self.publish()
            for skin in SKINS:
                self.assertTrue(self.find("skinOption_" + skin).isVisible())
                surface = self.find("skinSampleSurface_" + skin)
                self.assertTrue(surface.property("frosted"))
                self.assertEqual(surface.property("config")["skin"], skin)
                self.assertEqual(self.find("skinSampleReading_" + skin).property("text"), "68")
                self.assertEqual(self.find("skinSampleSecondarySurface_" + skin).property("config")["skin"], skin)
                self.assertTrue(self.find("skinDescription_" + skin).property("text"))
                self.assertGreaterEqual(self.find("skinSampleReading_" + skin).property("font").pixelSize(), 20)
            frame = self.window.grabWindow()
            colors = set()
            for skin in SKINS:
                surface = self.find("skinSampleSurface_" + skin)
                point = surface.mapToScene(QPointF(surface.width() - 14, surface.height() / 2)) * frame.devicePixelRatio()
                colors.add(frame.pixelColor(round(point.x()), round(point.y())).rgba())
            self.assertEqual(len(colors), 6, "All six actual coatings must differ on the same controlled backing")
            backgrounds = {str(self.find("skinSampleScene_" + skin).property("source")) for skin in SKINS}
            self.assertEqual(len(backgrounds), 1, "Compare every coating on exactly the same desktop scene")
            self.proof("skin-six-materials-" + mode)
        for skin in SKINS:
            self.click("skinOption_" + skin)
            self.assertEqual(self.window.property("selectedSkin"), skin)
        self.click("skinOption_global")
        self.assertEqual(self.window.property("selectedSkin"), "global")

    def test_skin_preview_keeps_continuous_and_inherited_preferences(self):
        self.load("skin")
        for value in (0.0, 25.1, 50.0, 75.9, 100.0):
            self.state.preferences["glass_transparency"] = value
            self.publish()
            self.assertAlmostEqual(self.find("skinSampleSurface_glass").property("config")["glass_transparency"], value)
        self.state.preferences["widgets"]["cpu"]["glass_transparency"] = 12.3
        self.publish()
        self.assertAlmostEqual(self.find("skinSampleSurface_glass").property("config")["glass_transparency"], 12.3)
        self.state.preferences["widgets"]["cpu"]["glass_transparency"] = None
        self.publish()
        self.assertEqual(self.find("skinSampleSurface_glass").property("config")["glass_transparency"], 100)

    def test_skin_scene_has_true_rounded_corners_without_svg_clip_support(self):
        self.load("skin")
        source = self.find("skinSampleScene_glass").property("source").toString()
        svg = base64.b64decode(source.split(",", 1)[1]).replace(b'clip-path="url(#c)"', b"")
        image = QImage(320, 190, QImage.Format_RGBA8888)
        image.fill(0)
        painter = QPainter(image)
        try:
            QSvgRenderer(svg).render(painter)
        finally:
            painter.end()
        self.assertEqual([image.pixelColor(x,y).alpha() for x,y in [(0,0),(319,0),(0,189),(319,189)]], [0,0,0,0])
        self.assertEqual(image.pixelColor(160,95).alpha(), 255)

    def test_skin_popup_escape_keeps_window_and_small_popup_scrolls(self):
        self.load("skin")
        self.window.setProperty("compactSkin", True)
        self.window.resize(420, 330)
        QTest.qWait(20)
        self.click("skinPickerChangeButton")
        popup = self.find("skinPickerPopup")
        self.assertTrue(popup.property("opened"))
        self.proof("skin-popup-small")
        scroll = self.find("skinPickerOptionsScroll")
        flick = scroll.property("contentItem")
        before = flick.property("contentY")
        point = scroll.mapToScene(scroll.boundingRect().center())
        event = QWheelEvent(point, point, QPoint(0, 0), QPoint(0, -360), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
        self.app.sendEvent(self.window, event)
        QTest.qWait(40)
        self.assertGreater(flick.property("contentY"), before)
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(20)
        self.assertFalse(popup.property("opened"))
        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.find("skinPickerChangeButton").hasActiveFocus())

    def test_style_gallery_is_fixed_and_vertical_wheel_reaches_outer_scroll(self):
        self.load("inspector_scroll")
        self.window.resize(312, 500)
        self.publish()
        self.open_styles()
        outer = self.find("outerInspectorScroll").property("contentItem")
        for _ in range(20):
            if outer.property("contentHeight") > outer.height():
                break
            QTest.qWait(10)
        self.assertGreater(outer.property("contentHeight"), outer.height())
        heights = {self.find("topBarStyle_" + style).height() for style in ("label_value", "value", "icon_value", "trend_value", "bar_value", "ring_value", "graph", "stacked")}
        self.assertEqual(len(heights), 1)
        before = outer.property("contentY")
        sample = self.find("topBarStyleSample_label_value")
        point = sample.mapToScene(sample.boundingRect().center())
        QTest.mouseMove(self.window, point.toPoint())
        positions=[before]
        for _ in range(3):
            QTest.wheelEvent(self.window, point, QPoint(0, -120))
            QTest.qWait(30)
            positions.append(outer.property("contentY"))
        self.assertGreater(outer.property("contentY"), before, dict(positions=positions,point=(point.x(),point.y()),height=outer.height(),content_height=outer.property("contentHeight"),interactive=outer.property("interactive")))

    def test_compact_gallery_is_lazy_escape_cancels_and_new_item_resets(self):
        self.load("inspector")
        self.assertIsNone(self.window.findChild(QObject, "topBarDisplayStyle"))
        self.open_styles()
        self.assertEqual(self.state.actions, [])
        QTest.keyClick(self.window, Qt.Key_Escape)
        QTest.qWait(20)
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.find("inspector").property("galleryOpen"))
        self.assertTrue(self.find("topBarStyleChooser").hasActiveFocus())
        self.assertIsNone(self.window.findChild(QObject, "topBarDisplayStyle"))
        self.assertEqual(self.state.actions, [])
        self.open_styles()
        self.state.preferences["top_bar"]["items"][0]["id"] = "b_other"
        self.state.row["id"] = "b_other"
        self.publish()
        self.assertFalse(self.find("inspector").property("galleryOpen"))

    def test_open_gallery_reveals_focused_later_style_in_short_outer_view(self):
        self.state.preferences["top_bar"]["items"][0]["prefs"]["style"]="ring_value"
        self.load("inspector_scroll")
        self.window.resize(312,380)
        self.open_styles()
        QTest.qWait(50)
        tile=self.find("topBarStyle_ring_value")
        self.assertTrue(tile.hasActiveFocus())
        top=tile.mapToScene(QPointF()).y()
        bottom=tile.mapToScene(QPointF(0,tile.height())).y()
        self.assertGreaterEqual(top,15)
        self.assertLessEqual(bottom,self.window.height()-15)

    def test_legacy_nonrecommended_gauge_keeps_label_and_saved_style(self):
        self.state.row.update(metric="storage_wear_percent",unit="%",gauge_supported=False)
        self.state.preferences["top_bar"]["items"][0]["prefs"]["style"] = "ring_value"
        self.load("inspector")
        self.assertEqual(self.find("inspector").property("selectedStyleLabel"), translate("圆环与数值","zh-CN"))
        self.assertEqual(self.state.preferences["top_bar"]["items"][0]["prefs"]["style"], "ring_value")
        self.assertEqual(self.state.actions, [])
        self.open_styles()
        self.assertIsNone(self.window.findChild(QObject, "topBarStyle_ring_value"))

    def test_compact_controls_fit_336_and_pair_title_uses_module(self):
        self.pair()
        self.state.row.update(self.state.details)
        self.state.row.update(metric="net_download",unit="MB/s",pair_supported=True)
        self.state.preferences["top_bar"]["items"][0].update(metric="net_download",prefs={"style":"duplex"})
        self.load("inspector")
        inspector = self.find("inspector")
        self.assertEqual(self.find("topBarInspectorTitle").property("text"), "网络")
        for width,locale in ((336,"zh-CN"),(280,"de")):
            self.state.locale=locale
            self.window.setProperty("panelWidth",width)
            self.publish()
            control_lefts=[]
            for name in ("topBarStyleChooser","topBarPrecision","topBarNetworkUnit","topBarPlacement","topBarDevice"):
                item=self.find(name)
                self.assertTrue(item.isVisible())
                control_lefts.append(round(item.mapToItem(inspector,QPointF()).x(),1))
                self.assertLessEqual(item.mapToItem(inspector,QPointF(item.width(),0)).x(),width-11)
            self.assertEqual(len(set(control_lefts)),1)
            if width==336:
                self.assertLessEqual(inspector.implicitHeight(),480)
        self.assertFalse(inspector.property("sourceOpen"))
        self.click("topBarInspectorSourceToggle")
        self.assertTrue(inspector.property("sourceOpen"))

    def test_long_current_style_is_unscaled_and_horizontally_accessible(self):
        self.pair()
        self.state.row.update(self.state.details)
        self.state.row.update(metric="net_download", unit="MB/s", pair_supported=True)
        self.state.preferences["top_bar"]["items"][0].update(metric="net_download", prefs={"style":"duplex_inline"})
        for row in self.state.row["paired_rows"]:
            row.update(number_text="123456789012.34", value="123456789012.34 MB/s")
        self.load("inspector")
        view = self.find("topBarCurrentStylePreview")
        flick = view
        sample = self.find("topBarCurrentStyleSample")
        self.assertEqual(sample.scale(), 1)
        self.assertGreater(flick.property("contentWidth"), view.width())
        bar = self.find("topBarCurrentStyleSampleScrollBar")
        self.assertTrue(bar.isVisible())
        start = bar.mapToScene(QPointF(bar.width() * bar.property("size") / 2, bar.height() / 2)).toPoint()
        end = bar.mapToScene(QPointF(bar.width() - 2, bar.height() / 2)).toPoint()
        QTest.mousePress(self.window, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(self.window, end, 30)
        QTest.mouseRelease(self.window, Qt.LeftButton, Qt.NoModifier, end)
        QTest.qWait(20)
        self.assertGreater(flick.property("contentX"), 0)
        self.assertEqual(sample.property("pairRows").toVariant()[1]["unit_text"], "MB/s")


if __name__ == "__main__":
    unittest.main()
