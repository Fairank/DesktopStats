"""Render real HardwareGlyph QML offscreen, with synthetic appearances only.

No desktop window, sampler, subprocess, native API, profile read or application
restart. The contact sheet shows literal 18px icons beside 32px and 64px views.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

QML = '''import QtQuick
import "../native" as Product
Window {
    id:scene;visible:false;width:1440;height:84+Math.ceil(variants.length/2)*144+56;color:"#e7ebf1"
    property var variants:[]
    property string catalogTitle:"Hardware appearances · 原创硬件外观"
    property string catalogNote:"18px actual size · 32px · 64px / Static vectors · simplified families"
    Text {x:24;y:17;text:scene.catalogTitle;font.family:"Microsoft YaHei UI"
        font.pixelSize:20;font.weight:Font.DemiBold;color:"#202833"}
    Text {x:24;y:49;text:scene.catalogNote
        font.family:"Segoe UI";font.pixelSize:12;color:"#5e6b7d"}
    Repeater {
        model:2
        Rectangle {
            id:theme;required property int index
            readonly property bool dark:index===1
            readonly property color ink:dark?"#e8edf4":"#303a48"
            readonly property color muted:dark?"#a1aebf":"#68768a"
            x:8+index*716;y:84;width:708;height:Math.ceil(scene.variants.length/2)*144+48;radius:16
            color:dark?"#1c222b":"#f5f7fa"
            Text {x:16;y:13;text:theme.dark?"DARK / 深色":"LIGHT / 浅色";font.family:"Segoe UI"
                font.pixelSize:11;font.weight:Font.DemiBold;color:theme.muted}
            Repeater {
                model:scene.variants
                Rectangle {
                    id:card;required property int index;required property var modelData
                    x:12+(index%2)*348;y:40+Math.floor(index/2)*144;width:336;height:132;radius:12
                    color:theme.dark?"#252d38":"#ffffff"
                    border.width:1;border.color:theme.dark?"#394350":"#dfe5ed"
                    Text {x:14;y:12;width:308;text:card.modelData.label;textFormat:Text.PlainText
                        elide:Text.ElideRight
                        font.family:"Microsoft YaHei UI";font.pixelSize:12;font.weight:Font.Medium;color:theme.ink}
                    Text {x:14;y:31;width:308;text:card.modelData.note;textFormat:Text.PlainText
                        font.family:"Microsoft YaHei UI";font.pixelSize:10;color:theme.muted}
                    Repeater {
                        model:[64,32,18]
                        Item {
                            id:sample;required property int index;required property int modelData
                            x:[20,130,220][index];y:50;width:78;height:76
                            Product.HardwareGlyph {
                                objectName:"glyph_"+theme.index+"_"+card.index+"_"+sample.modelData
                                x:0;y:(64-height)/2;width:sample.modelData;height:sample.modelData
                                appearance:card.modelData.appearance;ink:theme.ink
                            }
                            Text {x:0;y:64;text:sample.modelData+"px";font.family:"Segoe UI";font.pixelSize:9;color:theme.muted}
                        }
                    }
                }
            }
        }
    }
}'''


def variants(catalog):
    sys.path.insert(0, str(ROOT))
    from hardware_appearance import CATALOG, appearance_for

    if catalog == "models":
        result = []
        for row in CATALOG:
            appearance = appearance_for(row[1], row[-1][0])
            assert appearance["confidence"] == "model" and appearance["id"] == row[0]
            note = "已确认型号 · " + (f"{appearance['fan_count']} 风扇" if row[1] == "gpu" else "已知 CPU 封装")
            result.append(dict(label=appearance["label"], note=note, appearance=appearance))
        return result

    from hardware_series import SERIES_CATALOG
    result = []
    for row in SERIES_CATALOG:
        appearance = appearance_for("gpu", row["board_vendor"] + " " + row["aliases"][0] + " unidentified GPU")
        assert appearance["series_id"] == row["id"] and appearance["fan_count"] is None
        assert appearance["style"] == "gpu_neutral"
        result.append(dict(label=row["label"] + " · 系列示意",
                           note=" / ".join(row["features"]) + " · 未确认风扇",
                           source_url=row["source_url"], appearance=appearance))
    return result


def render(destination, scratch, catalog):
    os.environ.update(DESKTOP_STATS_DATA=str(scratch / "profile"), QT_QPA_PLATFORM="offscreen",
                      QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic",
                      QT_QUICK_CONTROLS_STYLE="Basic", QML_DISABLE_DISK_CACHE="1",
                      QT_SCALE_FACTOR="1", QT_AUTO_SCREEN_SCALE_FACTOR="0", TEMP=str(scratch), TMP=str(scratch))
    from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPointF, QUrl
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "offscreen", "Catalog must never open native desktop windows"
    for name in ("segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    engine = QQmlEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    component = QQmlComponent(engine)
    component.setData(QML.encode("utf-8"), QUrl.fromLocalFile(str(ROOT / "tools/hardware-catalog.qml")))
    if component.isError():
        raise RuntimeError("; ".join(error.toString() for error in component.errors()))
    cases = variants(catalog)
    title = "Confirmed hardware models · 已确认型号" if catalog == "models" else "GPU cooler families · 系列外观示意"
    note = "18px actual size · 32px · 64px / " + ("Exact catalog identities; simplified physical layouts" if catalog == "models"
                                                else "Family cues only; fan counts UNKNOWN, no fan circles")
    window = component.createWithInitialProperties(dict(variants=cases, catalogTitle=title, catalogNote=note))
    assert isinstance(window, QQuickWindow), [error.toString() for error in component.errors()]
    try:
        window.show()  # Offscreen platform asserted above; never a desktop window.
        QTest.qWait(100)
        app.processEvents()
        visual = {}
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName():
                visual[item.objectName()] = item
            pending.extend(item.childItems())
        rows = []
        for theme in range(2):
            for index, case in enumerate(cases):
                for size in (18, 32, 64):
                    glyph = visual.get(f"glyph_{theme}_{index}_{size}")
                    assert glyph is not None, (theme, index, size, list(visual), warnings)
                    image = glyph.findChild(QObject, "hardwareGlyphImage")
                    assert image is not None
                    status = QQmlExpression(qmlContext(image), image, "Number(status)").evaluate()
                    status = status[0] if isinstance(status, tuple) else status
                    assert status == 1, (case["label"], status, warnings)
                    point = glyph.mapToScene(QPointF(0, 0))
                    rows.append(dict(label=case["label"], theme="dark" if theme else "light", size=size,
                                     x=point.x(), y=point.y(), geometry_key=glyph.property("geometryKey")))
        assert not warnings, warnings
        image = window.grabWindow()
        assert not image.isNull() and image.width() == 1440 and image.devicePixelRatio() == 1
        assert image.save(str(destination))
        destination.with_suffix(".json").write_text(json.dumps(dict(
            platform=app.platformName(), rendering="software/offscreen", image=str(destination),
            width=image.width(), height=image.height(), literal_18px=True, warnings=warnings,
            variants=cases, glyphs=rows), ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        window.hide()
        window.destroy()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return dict(output=str(destination), variants=len(cases), glyphs=len(rows), warnings=len(warnings))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa-private/hardware-catalog.png")
    parser.add_argument("--catalog", choices=("models", "series"), default="models")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists() and not args.overwrite:
        parser.error("Use --overwrite to replace the previous generated contact sheet")
    destination.parent.mkdir(parents=True, exist_ok=True)
    private = ROOT / "qa-private/hardware-catalog-scratch"
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as scratch, \
         patch.object(ctypes, "WinDLL", side_effect=AssertionError("No native API")), \
         patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess")), \
         patch("threading.Thread.start", side_effect=AssertionError("No worker threads")):
        result = render(destination, Path(scratch), args.catalog)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
