"""Model widgets use sampled identity, one layout and retained motion offscreen."""
import copy
import json
import math
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext, qmlRegisterType
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from native_card import HardwareCard
from native_surface import MaterialSurface
import native_controller as controls
from hardware_appearance import CATALOG, appearance_for
from material_policy import render_policy
from responsive_layout import hardware_model_geometry, responsive_plan, dimensions, ResponsiveLayoutError
from stats_config import DEFAULT, validate
from native_card import formatted
from top_bar_config import HARDWARE_ICON_STYLES
from widget_catalog import from_template

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    config = copy.deepcopy(DEFAULT)
    config["widgets"] = {key: from_template(key + "_model") for key in ("cpu", "gpu")}
    config["widget_order"] = ["cpu", "gpu"]
    return validate(config)


def sample():
    now = time.time()
    gpu = dict(gpu_name="NVIDIA GeForce RTX 5090 Founders Edition", label="GPU 0",
        gpu_usage=66., gpu_temp=58., gpu_power=281., gpu_fan_rpm=1200.,
        gpu_fan_rpm_timestamp=now, gpu_fan_rpm_source="synthetic-current-rpm",
        gpu_fan_rpm_semantics="driver_current_rpm", gpu_fan_rpm_scope="card")
    return dict(time=now, cpu_name="AMD Ryzen 9 9950X", cpu_usage=38.,
        cpu_temp=64., cpu_frequency=5.25, cpu_power=102., gpus={"0":gpu}, gpu_temp=99.)


class ModelGeometryTests(unittest.TestCase):
    def test_templates_keep_old_cards_and_have_transparent_original_models(self):
        self.assertTrue(from_template("cpu")["skinFrame"])
        for kind in ("cpu", "gpu"):
            prefs = from_template(kind + "_model")
            self.assertFalse(prefs["skinFrame"])
            self.assertEqual(prefs["hardware_icon_style"], "miniature")
            self.assertEqual(prefs["presentation"], "hardware")
            self.assertFalse(prefs["grouped"])
            self.assertEqual(len(prefs["content"]), 3)
        self.assertEqual(validate(configuration()), configuration())

    def test_every_size_has_disjoint_art_caption_readings_and_shared_hit_boxes(self):
        for kind in ("cpu", "gpu"):
            prefs = from_template(kind + "_model")
            for width, height in ((220,220),(240,240),(360,360),(520,260)):
                for content in (prefs["content"][:2], prefs["content"]):
                    geometry = hardware_model_geometry(width,height,content,prefs)
                    layout = responsive_plan(width,height,content,prefs)
                    self.assertEqual(tuple(row.box for row in layout.readings), geometry["readings"])
                    self.assertLessEqual(geometry["image"].bottom, geometry["caption"].y)
                    self.assertLessEqual(geometry["caption"].bottom, layout.readings[0].box.y)
                    for box in (geometry["image"], geometry["caption"], *geometry["readings"]):
                        self.assertGreater(box.width,0);self.assertGreater(box.height,0)
                        self.assertGreaterEqual(box.x,0);self.assertGreaterEqual(box.y,0)
                        self.assertLessEqual(box.right,width);self.assertLessEqual(box.bottom,height)
                    if kind=="cpu":self.assertEqual(geometry["image"].width,geometry["image"].height)
                    else:self.assertGreater(geometry["image"].width,geometry["image"].height)

    def test_invalid_model_layout_is_rejected_without_truncating_metrics(self):
        prefs=from_template("cpu_model")
        for content in (["cpu_usage"], ["cpu_usage","cpu_temp","cpu_power","cpu_frequency"]):
            bad=configuration();bad["widgets"]["cpu"]["content"]=content
            with self.assertRaises(ValueError):validate(bad)
        for field,value in (("skinFrame",1),("hardware_icon_style","unknown"),("hardware_model","<svg>"),
                            ("effect_speed",float("nan")),("effect_intensity",2),("layout_mode","manual")):
            bad=configuration();bad["widgets"]["cpu"][field]=value
            with self.assertRaises(ValueError):validate(bad)
        with self.assertRaises(ResponsiveLayoutError):hardware_model_geometry(200,220,prefs["content"],prefs)

    def test_mixed_frameless_group_never_blurs_the_whole_window(self):
        config=configuration();config["skin"]="glass"
        spec=dict(id="group",cells=[dict(key="cpu"),dict(key="gpu")])
        plain=render_policy(config,spec)
        self.assertFalse(plain["backdrop"]);self.assertIsNone(plain["panel_skin"])
        self.assertFalse(plain["card_surfaces"])
        config["widgets"]["gpu"]["skinFrame"]=True
        mixed=render_policy(config,spec)
        self.assertFalse(mixed["backdrop"]);self.assertIsNone(mixed["panel_skin"])
        self.assertTrue(mixed["card_surfaces"])
        self.assertEqual(mixed["fallback_reason"],"mixed-frameless")
        config["widgets"]["cpu"]["skinFrame"]=True
        self.assertTrue(render_policy(config,spec)["backdrop"])


class DesktopHardwareModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        if cls.app.platformName()!="offscreen":raise unittest.SkipTest("offscreen only")
        fonts=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
        for name in ("SegUIVar.ttf","segoeui.ttf","msyh.ttc"):
            if (fonts/name).is_file():QFontDatabase.addApplicationFont(str(fonts/name))
        qmlRegisterType(HardwareCard,"DesktopStats",1,0,"HardwareCard")
        qmlRegisterType(MaterialSurface,"DesktopStats",1,0,"MaterialSurface")

    def setUp(self):
        self.native=self.enterContext(patch("ctypes.WinDLL",side_effect=AssertionError("No native API")))
        self.process=self.enterContext(patch("subprocess.Popen",side_effect=AssertionError("No process")))
        self.enterContext(patch.object(controls,"load",return_value=configuration()))
        self.enterContext(patch.object(controls,"save"))
        self.controller=controls.Controller()
        self.controller._data=sample()
        self.engine=QQmlEngine();self.warnings=[];self.window=None;self.component=None
        self.engine.warnings.connect(lambda rows:self.warnings.extend(row.toString() for row in rows))
        self.engine.rootContext().setContextProperty("stats",self.controller)

    def tearDown(self):
        if self.window is not None:
            self.window.hide();self.window.destroy();self.window.deleteLater()
        if self.component is not None:self.component.deleteLater()
        self.engine.deleteLater();self.controller.close();self.controller.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.app.processEvents()
        self.assertEqual(self.warnings,[])
        self.native.assert_not_called();self.process.assert_not_called()

    def evaluate(self,code):
        expression=QQmlExpression(qmlContext(self.window),self.window,code)
        result=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return result[0] if isinstance(result,tuple) else result

    def find(self,name):
        pending=[self.window.contentItem()]
        while pending:
            item=pending.pop()
            if item.objectName()==name:return item
            pending.extend(item.childItems())
        self.fail(name)

    def load(self,kind="gpu",size=240):
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import "../native" as Product
Window {
 id:scene; width:240; height:240; visible:false; color:"transparent"
 property string moduleKey:"gpu"
 property bool allowed:true
 Product.WidgetPreview {
   anchors.fill:parent;moduleKey:scene.moduleKey;config:stats.draft
   previewInfo:({width:scene.width,height:scene.height,card_surfaces:true})
   readings:stats.readings;modelMotionAllowed:scene.allowed
 }
}''',QUrl.fromLocalFile(str(ROOT/"tests/DesktopHardwareModelFixture.qml")))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[row.toString() for row in self.component.errors()])
        self.window.setProperty("moduleKey",kind);self.window.resize(size,size)
        self.window.show();QTest.qWait(20)

    def test_readonly_snapshots_do_not_start_sampling_and_never_cross_gpu_targets(self):
        before=copy.deepcopy((self.controller._saved,self.controller._draft,self.controller._data))
        state=self.controller.widgetHardwareState("gpu",True)
        self.assertEqual(state["hardware_state"]["fan_speed"]["rpm"],1200.)
        self.assertEqual(state["appearance"]["confidence"],"model")
        self.controller._draft["widgets"]["gpu"]["gpu_target"]="missing"
        missing=self.controller.widgetHardwareState("gpu",True)
        self.assertEqual(missing["name"],"")
        self.assertFalse(missing["available"])
        self.assertFalse(missing["hardware_state"]["fan_speed"]["available"])
        self.assertNotEqual(missing["appearance"]["confidence"],"model")
        self.controller._draft["widgets"]["gpu"]["gpu_target"]="0"
        self.assertEqual(before,(self.controller._saved,self.controller._draft,self.controller._data))
        self.assertIsNone(self.controller.thread)
        self.assertEqual(formatted(self.controller._data,"cpu_temp",self.controller._draft["widgets"]["cpu"])[0],"64")

    def test_real_frame_time_controls_staleness_and_future_timestamps_cannot_wake_motion(self):
        self.controller._data["time"]=time.time()-36
        self.controller._data["timestamp"]=time.time()
        self.assertFalse(self.controller.widgetHardwareState("cpu",True)["available"])
        self.assertFalse(self.controller.widgetHardwareState("gpu",True)["available"])
        self.controller._data["time"]=time.time()+10
        self.assertFalse(self.controller.widgetHardwareState("gpu",True)["available"])

    def test_model_metric_limits_are_atomic_and_keep_two_readings(self):
        before=copy.deepcopy(self.controller._draft)
        self.assertFalse(self.controller.addMetrics("cpu",["cpu_power"]))
        self.assertEqual(before,self.controller._draft)
        self.controller.removeMetric("cpu",2)
        two=copy.deepcopy(self.controller._draft)
        self.assertEqual(len(two["widgets"]["cpu"]["content"]),2)
        self.controller.removeMetric("cpu",1)
        self.assertEqual(two,self.controller._draft)
        self.assertTrue(self.controller.addMetrics("cpu",["cpu_power"]))

    def test_actual_desktop_window_uses_the_runtime_motion_gate_and_saved_identity(self):
        self.component=QQmlComponent(self.engine,QUrl.fromLocalFile(str(ROOT/"native/DesktopWidget.qml")))
        spec=dict(id="gpu",width=240,height=240,cells=[dict(key="gpu",x=0,y=0,width=240,height=240)],
                  material_policy=render_policy(self.controller._saved,dict(id="gpu",cells=[dict(key="gpu")])))
        self.window=self.component.createWithInitialProperties(dict(spec=spec))
        self.assertIsNotNone(self.window,[e.toString() for e in self.component.errors()])
        self.window.show();QTest.qWait(20)
        icon=self.find("desktopHardwareModelIcon")
        self.assertFalse(icon.property("animationRunning"))
        self.window.setProperty("modelMotionAllowed",True);self.app.processEvents()
        self.assertTrue(icon.property("gpuFanMotionActive"))
        self.controller._draft["widgets"]["gpu"]["gpu_target"]="missing"
        self.controller.dataChanged.emit();self.app.processEvents()
        self.assertTrue(icon.property("gpuFanMotionActive"))
        self.window.setProperty("modelMotionAllowed",False);self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertIsNone(self.controller.thread)

    def test_actual_editor_has_frame_style_choices_and_preserves_two_metric_floor(self):
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Controls
import "../native" as Product
ApplicationWindow {
 width:1100;height:850;visible:false
 Product.WidgetEditor {anchors.fill:parent;selectedKey:"gpu";active:true}
}''',QUrl.fromLocalFile(str(ROOT/"tests/ModelWidgetEditorFixture.qml")))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[e.toString() for e in self.component.errors()])
        self.window.show();QTest.qWait(40)
        self.assertFalse(self.find("widgetSkinFrame").property("checked"))
        self.assertEqual(self.find("widgetHardwareStyle").property("value"),"miniature")
        self.assertFalse(self.find("manualLayoutToggle").isVisible())
        self.assertTrue(self.find("desktopHardwareModelIcon").isVisible())
        self.controller.removeMetric("gpu",2);self.app.processEvents()
        self.assertFalse(self.find("metricListRemove_gpu_temp").property("enabled"))
        self.assertIsNone(self.controller.thread)

    def test_actual_gallery_model_thumbnails_use_retained_art_without_motion_or_sampling(self):
        self.component=QQmlComponent(self.engine)
        self.component.setData(b'''import QtQuick
import QtQuick.Controls
import "../native" as Product
ApplicationWindow {
 width:1100;height:850;visible:false
 Product.Gallery {id:gallery;objectName:"modelGallery";readingsActive:false;query:"hardware model"}
 function openGallery(){gallery.open();gallery.query="";gallery.category="cpu"}
}''',QUrl.fromLocalFile(str(ROOT/"tests/ModelWidgetGalleryFixture.qml")))
        self.window=self.component.create()
        self.assertIsNotNone(self.window,[e.toString() for e in self.component.errors()])
        self.window.show();self.evaluate("openGallery()");QTest.qWait(80)
        model=self.find("desktopHardwareModelIcon")
        self.assertFalse(model.property("motionEnabled"))
        self.assertTrue(model.property("modelMode"))
        self.assertTrue(model.property("hasHardwareAppearance"))
        self.assertIsNone(self.controller.thread)

    def test_gpu_target_changes_clear_only_the_manual_model_and_saved_stays_unchanged(self):
        self.controller._draft["widgets"]["gpu"]["hardware_model"]="synthetic-choice"
        saved=copy.deepcopy(self.controller._saved)
        self.controller.changeWidget("gpu","gpu_target","1")
        self.assertEqual(self.controller._draft["widgets"]["gpu"]["hardware_model"],"")
        self.assertEqual(self.controller._saved,saved)

    def test_actual_qml_has_large_separate_art_and_readings_at_both_sizes(self):
        self.load("gpu")
        for size in (240,360):
            self.window.resize(size,size);self.app.processEvents()
            icon=self.find("desktopHardwareModelIcon")
            self.assertGreater(icon.width(),size*.8)
            self.assertLess(icon.height(),size*.7)
            card=self.find("desktopHardwareModel").parentItem().parentItem()
            geometry=hardware_model_geometry(size,size,["gpu_usage","gpu_temp","gpu_power"],self.controller._draft["widgets"]["gpu"])
            self.assertEqual(card.metricAt(geometry["image"].x+3,geometry["image"].y+3),-1)
            for index,box in enumerate(geometry["readings"]):
                self.assertEqual(card.metricAt(box.x+box.width/2,box.y+box.height/2),index)
            self.assertFalse(self.window.grabWindow().isNull())
            self.assertEqual(self.window.grabWindow().pixelColor(0,0).alpha(),0)
            pixels=self.window.grabWindow();box=geometry["image"]
            self.assertGreater(sum(pixels.pixelColor(x,y).alpha()>0
                for x in range(math.ceil(box.x),int(box.right),4)
                for y in range(math.ceil(box.y),int(box.bottom),4)),20)

    def test_all_thirteen_actual_qml_styles_rotate_known_fans_and_old_classic_stays_generic(self):
        self.load("gpu")
        for style in HARDWARE_ICON_STYLES:
            self.controller.changeWidget("gpu","hardware_icon_style",style)
            self.app.processEvents()
            icon=self.find("desktopHardwareModelIcon")
            self.assertTrue(icon.property("gpuFanMotionActive"),style)
            glyph=self.find("metricHardwareGlyphLoader").property("item")
            self.assertFalse(glyph.property("classic"),style)
            layers=glyph.property("fanLayerData")
            layers=layers.toVariant() if hasattr(layers,"toVariant") else layers
            self.assertEqual(len(layers["rotors"]),2,style)
        self.controller.changeWidget("gpu","hardware_icon_style","classic")
        self.app.processEvents()
        icon=self.find("desktopHardwareModelIcon")
        icon.setProperty("modelMode",False);self.app.processEvents()
        self.assertFalse(icon.property("hasHardwareAppearance"))
        self.assertIsNone(self.find("metricHardwareGlyphLoader").property("item"))

    def test_cpu_effects_reuse_real_channels_and_missing_temperature_stays_missing(self):
        self.load("cpu")
        icon=self.find("desktopHardwareModelIcon")
        self.assertTrue(icon.property("animationRunning"))
        self.assertIsNotNone(self.find("metricIconProcessorWarmth").property("item"))
        self.controller._data["cpu_temp"]=None
        self.controller.dataChanged.emit();self.app.processEvents()
        self.assertIsNone(icon.property("thermalTarget"))
        self.assertTrue(icon.property("animationRunning"))
        self.window.setProperty("allowed",False);self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))

    def test_motion_stops_when_hidden_disallowed_or_rpm_expires_and_svg_stays_retained(self):
        self.load("gpu")
        icon=self.find("desktopHardwareModelIcon")
        self.assertTrue(icon.property("gpuFanMotionActive"))
        glyph=self.find("metricHardwareGlyphLoader").property("item")
        source=glyph.property("svgSource").toString()
        phase=icon.property("gpuFanPhase");QTest.qWait(70)
        self.assertNotEqual(icon.property("gpuFanPhase"),phase)
        self.assertEqual(glyph.property("svgSource").toString(),source)
        self.window.setProperty("allowed",False);self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertIsNone(icon.property("clockSubscription"))
        self.window.setProperty("allowed",True);self.app.processEvents()
        self.controller._data["gpus"]["0"]["gpu_fan_rpm_timestamp"]=time.time()-4
        self.controller.dataChanged.emit();self.app.processEvents()
        self.assertFalse(icon.property("gpuFanMotionActive"))
        self.window.hide();self.app.processEvents()
        self.assertFalse(icon.property("animationRunning"))
        self.assertIsNone(self.controller.thread)

    def test_model_styles_keep_all_reviewed_gpu_fan_counts_and_cpu_identity(self):
        self.load("gpu")
        # Evaluating the production JS avoids allocating thousands of image items.
        component=QQmlComponent(self.engine)
        component.setData(b'''import QtQuick
import "../native/HardwareShapes.js" as Shapes
QtObject { function inspect(appearance) {
 const key=Shapes.key(Object.assign({},appearance,{model_mode:true}),"#303a48")
 const layers=Shapes.layers(key)
 return {key:key,source:Shapes.source(key),rotors:layers.rotors}
}}''',QUrl.fromLocalFile(str(ROOT/"tests/ModelShapesProbe.qml")))
        probe=component.create();self.assertIsNotNone(probe,[e.toString() for e in component.errors()])
        try:
            for row in CATALOG:
                if row[1]!="gpu":continue
                appearance=appearance_for("gpu",row[-1][0])
                expected=appearance.get("visible_fan_count")
                if expected is None:expected=appearance.get("fan_count")
                expected=expected if appearance["style"] in ("gpu_axial","gpu_blower","gpu_hybrid") and expected in (1,2,3) else 0
                for style in HARDWARE_ICON_STYLES:
                    expression=QQmlExpression(qmlContext(probe),probe,"inspect("+json.dumps(dict(appearance,icon_set=style))+")")
                    result=expression.evaluate();result=result[0] if isinstance(result,tuple) else result
                    self.assertFalse(expression.hasError(),expression.error().toString())
                    result=result.toVariant() if hasattr(result,"toVariant") else result
                    keyed_count = -1 if appearance["style"] == "gpu_neutral" else 0 if appearance["style"] == "gpu_integrated" else (
                        appearance.get("visible_fan_count") if appearance.get("visible_fan_count") is not None else appearance.get("fan_count"))
                    self.assertEqual(int(result["key"].split("|")[4]),keyed_count if keyed_count is not None else -1,(row[0],style))
                    # Source-unknown blades retain a static opening/cap in the
                    # notebook styles. Never invent vanes to obtain motion.
                    self.assertLessEqual(len(result["rotors"]),expected,(row[0],style))
                    if row[0] == "nvidia-founders-rtx5090-32g":
                        self.assertEqual(len(result["rotors"]),expected,(row[0],style))
                        if style in ("notebook_color","notebook_line","notebook_smile"):
                            from urllib.parse import unquote
                            self.assertIn("hardware-notebook-fe-xbrace",unquote(result["source"]))
                    for rotor in result["rotors"]:
                        self.assertTrue(all(math.isfinite(rotor[key]) for key in ("cx","cy","radius","direction")))
                        self.assertGreater(rotor["radius"],0)
                    if style in ("classic","outline"):
                        self.assertIn("|model_"+style,result["key"])
                        self.assertIn(row[0],result["key"])
            for name in ("AMD Ryzen 9 9950X","Intel Core i7-13700KF"):
                appearance=appearance_for("cpu",name)
                for style in HARDWARE_ICON_STYLES:
                    expression=QQmlExpression(qmlContext(probe),probe,"inspect("+json.dumps(dict(appearance,icon_set=style))+")")
                    result=expression.evaluate();result=result[0] if isinstance(result,tuple) else result
                    result=result.toVariant() if hasattr(result,"toVariant") else result
                    self.assertIn(appearance["id"],result["key"])
                    self.assertEqual(result["rotors"],[])
        finally:
            probe.deleteLater();component.deleteLater()


if __name__=="__main__":unittest.main()
