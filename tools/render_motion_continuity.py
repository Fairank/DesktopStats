"""Render synthetic, owned offscreen QML demonstrations; no desktop capture.

Requires requirements-artwork.txt in addition to the normal development runtime.
The reproducible 20 fps GIF is a visual reference, not a native frame-rate or
Windows blur benchmark. It uses actual controller projection and QML effects.
"""

import argparse
import copy
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
QML = """import QtQuick
import "../native" as Product
Window {
 id:scene;width:980;height:476;visible:false
 property bool dark:false
 property int sampleNumber:1
 property var readings:[]
 readonly property color ink:dark?"#f4f6f9":"#202833"
 readonly property color muted:dark?"#aab6c7":"#657286"
 color:dark?"#20242b":"#f5f7fb"
 Text {x:24;y:18;text:"Live hardware motion";font.family:"Segoe UI";font.pixelSize:21;font.weight:Font.DemiBold;color:scene.ink}
 Text {x:24;y:50;text:"Synthetic readings: 1 s  |  Sample #"+scene.sampleNumber+"  |  Motion continues between updates";font.family:"Segoe UI";font.pixelSize:12;color:scene.muted}
 Repeater {
  model:["CPU · load / heat / power","GPU · load / heat / power","Memory · occupancy",
    "Network · download / upload","Disk · read / write","Battery · charging",
    "Fan · rotation","Temperature · column + warmth","Storage · capacity"]
  Rectangle {
   id:card;required property int index;required property string modelData
   readonly property var reading:scene.readings[index] || ({})
   x:24+(index%3)*316;y:84+Math.floor(index/3)*116;width:300;height:102;radius:13
   color:scene.dark?"#292f38":"#ffffff";border.width:1;border.color:scene.dark?"#39424e":"#e0e6ef"
   Text {x:14;y:14;width:230;text:card.modelData;textFormat:Text.PlainText;font.family:"Segoe UI";font.pixelSize:12;font.weight:Font.Medium;color:scene.muted}
   Product.MetricIcon {
    x:250;y:10;width:36;height:36
    name:card.reading.icon || "sensors";metric:card.reading.metric || "";ink:scene.ink
    hardwareState:card.reading.hardware_state || ({});automaticEffect:card.reading.auto_effect || ""
    effect:card.reading.icon_effect || "off";level:card.reading.effect_level===undefined?null:card.reading.effect_level
    available:card.reading.available===true && Number.isFinite(card.reading.numeric_value)
    motionEnabled:true;intensity:.65;speed:1
   }
   Product.TopBarGroupContent {
    x:14;y:59;width:implicitWidth;height:implicitHeight;row:card.reading
    ink:scene.ink;muted:scene.muted;fontFamily:"Segoe UI";motionEnabled:true
   }
  }
 }
 Text {x:24;y:449;text:"Actual QML: 18 / 11 DIP readouts + 36 DIP detail · synthetic inputs · 65% strength · 1× speed · decorative feedback";font.family:"Segoe UI";font.pixelSize:11;color:scene.muted}
}"""


def projected_sample(index):
    return dict(
        time=time.time(),
        cpu_usage=[42, 78, 59, 91][index],
        cpu_temp=[75, 105, 87, 112][index],
        cpu_power=[75, 150, 105, 175][index],
        cpu_fan_rpm=[3600, 6200, 4800, 7600][index],
        ram_percent=[55, 78, 66, 84][index],
        gpu_usage=[35, 82, 56, 90][index],
        gpu_temp=[63, 92, 76, 99][index],
        gpu_power=[65, 225, 130, 260][index],
        net_download=[12, 65, 28, 80][index],
        net_upload=[5, 24, 12, 40][index],
        disk_read=[65, 280, 110, 360][index],
        disk_write=[30, 110, 65, 180][index],
        battery_percent=68,
        battery_charge_watts=[18, 35, 24, 42][index],
        battery_discharge_watts=0,
        disk_percent=[42, 43, 44, 45][index],
    )


def configuration(default):
    value = copy.deepcopy(default)
    metrics = (
        "cpu_usage",
        "gpu_usage",
        "ram_percent",
        "net_download",
        "disk_read",
        "battery_percent",
        "cpu_fan_rpm",
        "cpu_temp",
        "disk_percent",
    )
    items = []
    for metric in metrics:
        prefs = dict(style="icon_value", icon_effect="auto", effect_intensity=0.65)
        if metric in ("cpu_usage", "gpu_usage"):
            prefix = metric.split("_")[0]
            prefs["metrics"] = [metric, prefix + "_temp", prefix + "_power"]
        elif metric in ("net_download", "disk_read"):
            prefs["style"] = "duplex_inline"
        items.append(dict(id="b_demo_" + metric, metric=metric, prefs=prefs))
    value.update(language="en", autostart=False)
    value["top_bar"]["items"] = items
    return value


def render(destination, scratch, *, overwrite=False):
    os.environ.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        QSG_RENDER_LOOP="basic",
        QML_DISABLE_DISK_CACHE="1",
        QT_SCALE_FACTOR="1",
        DESKTOP_STATS_DATA=str(scratch / "profile"),
        TEMP=str(scratch),
        TMP=str(scratch),
    )
    sys.path.insert(0, str(ROOT))
    from PIL import Image
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl
    from PySide6.QtGui import QFont, QFontDatabase, QImage
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from shiboken6 import getCppPointer

    from native_controller import Controller
    from stats_config import DEFAULT, validate

    app = QApplication([])
    if app.platformName() != "offscreen":
        raise RuntimeError("This renderer only supports owned offscreen windows")
    for name in ("segoeui.ttf", "seguisb.ttf"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI"))
    source_paths = [
        "native/MetricIcon.qml",
        "native/MetricEffectClock.js",
        "native/TopBarMetricContent.qml",
        "native/TopBarGroupContent.qml",
        "native_controller.py",
        "top_bar_feedback.py",
    ]
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    sources = {name: digest(ROOT / name) for name in source_paths}
    reports = []
    with patch("native_controller.load", return_value=validate(configuration(DEFAULT))):
        controller = Controller()
    controller.set_motion_enabled(True)
    controller.receive(projected_sample(0))
    for dark in (False, True):
        output = destination / (
            "motion-continuity-dark.gif" if dark else "motion-continuity-light.gif"
        )
        if output.exists() and not overwrite:
            raise FileExistsError(output)
        engine = QQmlEngine()
        warnings = []
        engine.warnings.connect(
            lambda errors: warnings.extend(error.toString() for error in errors)
        )
        component = QQmlComponent(engine)
        component.setData(QML.encode(), QUrl.fromLocalFile(str(ROOT / "tools/motion-scene.qml")))
        window = component.createWithInitialProperties(
            dict(dark=dark, readings=controller.topBarRows())
        )
        if not isinstance(window, QQuickWindow):
            raise RuntimeError([error.toString() for error in component.errors()])
        window.show()
        QTest.qWait(100)

        def icons():
            pending, found = [window.contentItem()], []
            while pending:
                item = pending.pop()
                if item.metaObject().indexOfProperty("clockSubscription") >= 0:
                    found.append(item)
                pending.extend(item.childItems())
            return found

        def stop_clock():
            from PySide6.QtCore import QObject

            for clock in window.findChildren(QObject, "metricIconAnimation"):
                clock.stop()

        def evaluate(icon, expression):
            value = QQmlExpression(qmlContext(icon), icon, expression)
            value.evaluate()
            if value.hasError():
                raise RuntimeError(value.error().toString())

        stop_clock()
        retained = {getCppPointer(icon)[0] for icon in icons()}
        for icon in icons():
            icon.setProperty("previousTick", 2000)
            for phase in (
                "phase",
                "loadPhase",
                "thermalArcPhase",
                "energyPhase",
                "spinPhase",
                "inboundPhase",
                "outboundPhase",
            ):
                icon.setProperty(phase, 0)
        frames = []
        for frame in range(80):
            stop_clock()
            if frame % 20 == 0:
                controller.receive(projected_sample(frame // 20))
                window.setProperty("sampleNumber", frame // 20 + 1)
                window.setProperty("readings", controller.topBarRows())
                app.processEvents()
                if {getCppPointer(icon)[0] for icon in icons()} != retained:
                    raise AssertionError("A new sample recreated an icon in the published demo")
            stop_clock()
            for icon in icons():
                evaluate(icon, f"advanceClock({2050 + 50 * frame})")
            window.requestUpdate()
            window.grabWindow()
            app.processEvents()
            image = window.grabWindow().convertToFormat(QImage.Format_RGBA8888)
            frames.append(
                Image.frombytes(
                    "RGBA", (image.width(), image.height()), bytes(image.constBits())
                ).convert("RGB")
            )
        if warnings:
            raise RuntimeError(warnings)
        # One palette spans several burst moments, so color does not shimmer
        # because of independent per-frame GIF quantization.
        palette_samples = Image.new("RGB", (980, 476 * 8))
        for index, frame in enumerate(frames[::10]):
            palette_samples.paste(frame, (0, index * 476))
        palette = palette_samples.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
        encoded[0].save(
            output,
            save_all=True,
            append_images=encoded[1:],
            duration=50,
            loop=0,
            disposal=2,
            optimize=False,
        )
        reports.append(
            dict(
                file=output.name,
                sha256=digest(output),
                bytes=output.stat().st_size,
                frames=len(frames),
                duration_ms=4000,
                retained_icon_count=len(retained),
                no_sample_recreated_icon=True,
            )
        )
        window.hide()
        window.destroy()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    controller.close()
    assert sources == {name: digest(ROOT / name) for name in source_paths}
    return dict(
        ok=True,
        synthetic=True,
        native_or_desktop_capture=False,
        sample_interval_seconds=1,
        deterministic_presentation_step_ms=50,
        strength=0.65,
        speed=1,
        source_sha256=sources,
        outputs=reports,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    def forbid(*args, **kwargs):
        raise AssertionError("Hardware, native composition and process launch are forbidden")

    # These guards apply to Python-side product APIs; Qt itself uses offscreen
    # QPA and never creates a desktop AppBar or captures another window.
    with tempfile.TemporaryDirectory(prefix=".motion-render-", dir=destination) as temporary:
        scratch = Path(temporary).resolve()
        if not scratch.is_relative_to(destination) or scratch == destination:
            raise ValueError("Temporary rendering directory escaped the selected output")
        with (
            patch.object(ctypes, "WinDLL", forbid, create=True),
            patch.object(subprocess, "Popen", forbid),
        ):
            result = render(destination, scratch, overwrite=args.overwrite)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
