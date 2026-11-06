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
    id:scene;visible:false;width:1440;height:84+Math.ceil(variants.length/2)*rowHeight+56;color:"#e7ebf1"
    property var variants:[]
    property var sampleSizes:[64,32,18]
    property var sampleXs:[20,130,220]
    readonly property int rowHeight:sampleSizes[0]>64?232:144
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
            x:8+index*716;y:84;width:708;height:Math.ceil(scene.variants.length/2)*scene.rowHeight+48;radius:16
            color:dark?"#1c222b":"#f5f7fa"
            Text {x:16;y:13;text:theme.dark?"DARK / 深色":"LIGHT / 浅色";font.family:"Segoe UI"
                font.pixelSize:11;font.weight:Font.DemiBold;color:theme.muted}
            Repeater {
                model:scene.variants
                Rectangle {
                    id:card;required property int index;required property var modelData
                    x:12+(index%2)*348;y:40+Math.floor(index/2)*scene.rowHeight;width:336;height:scene.rowHeight-12;radius:12
                    color:theme.dark?"#252d38":"#ffffff"
                    border.width:1;border.color:theme.dark?"#394350":"#dfe5ed"
                    Text {x:14;y:12;width:308;text:card.modelData.label;textFormat:Text.PlainText
                        elide:Text.ElideRight
                        font.family:"Microsoft YaHei UI";font.pixelSize:12;font.weight:Font.Medium;color:theme.ink}
                    Text {x:14;y:31;width:308;text:card.modelData.note;textFormat:Text.PlainText
                        elide:Text.ElideRight
                        font.family:"Microsoft YaHei UI";font.pixelSize:10;color:theme.muted}
                    Repeater {
                        model:scene.sampleSizes
                        Item {
                            id:sample;required property int index;required property int modelData
                            x:scene.sampleXs[index];y:scene.sampleSizes[0]>64?64:50
                            width:Math.max(78,sample.modelData);height:scene.sampleSizes[0]+18
                            Product.HardwareGlyph {
                                objectName:"glyph_"+theme.index+"_"+card.index+"_"+sample.modelData
                                x:0;y:(scene.sampleSizes[0]-height)/2;width:sample.modelData;height:sample.modelData
                                appearance:card.modelData.appearance;ink:theme.ink
                            }
                            Text {x:0;y:scene.sampleSizes[0]+6;text:sample.modelData+"px";font.family:"Segoe UI";font.pixelSize:9;color:theme.muted}
                        }
                    }
                }
            }
        }
    }
}'''


OVERVIEW_QML = '''import QtQuick
import "../native" as Product
Window {
    id:scene;visible:false;width:1440;height:84+Math.ceil(variants.length/4)*196+24;color:"#e7ebf1"
    property var variants:[]
    property var sampleSizes:[64,32,18]
    property var sampleXs:[6,82,122]
    property string catalogTitle:"Board brands · 品牌代表型号"
    property string catalogNote:"64 / 32 / literal 18px · Light + dark · Confirmed models; simplified illustrations"
    Text {x:24;y:17;text:scene.catalogTitle;font.family:"Microsoft YaHei UI"
        font.pixelSize:20;font.weight:Font.DemiBold;color:"#202833"}
    Text {x:24;y:49;text:scene.catalogNote;font.family:"Segoe UI";font.pixelSize:12;color:"#5e6b7d"}
    Repeater {
        model:scene.variants
        Rectangle {
            id:card;required property int index;required property var modelData
            x:24+(index%4)*354;y:84+Math.floor(index/4)*196;width:336;height:184;radius:12
            color:"#ffffff";border.width:1;border.color:"#d9e1e9"
            Text {x:12;y:10;width:312;text:card.modelData.label;textFormat:Text.PlainText
                elide:Text.ElideRight;font.family:"Microsoft YaHei UI";font.pixelSize:12
                font.weight:Font.DemiBold;color:"#26323f"}
            Text {x:12;y:29;width:312;height:30
                text:card.modelData.model_label || card.modelData.appearance.label;textFormat:Text.PlainText
                wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight
                font.family:"Microsoft YaHei UI";font.pixelSize:10;color:"#526274"}
            Text {x:12;y:63;width:312;text:card.modelData.note;textFormat:Text.PlainText
                elide:Text.ElideRight;font.family:"Microsoft YaHei UI";font.pixelSize:10;color:"#526274"}
            Repeater {
                model:2
                Rectangle {
                    id:theme;required property int index
                    readonly property bool dark:index===1
                    readonly property color ink:dark?"#e8edf4":"#303a48"
                    x:12+index*158;y:84;width:154;height:88;radius:7
                    color:dark?"#1c222b":"#f0f4f8"
                    Text {x:6;y:2;text:theme.dark?"DARK":"LIGHT";font.family:"Segoe UI"
                        font.pixelSize:7;color:theme.dark?"#a1aebf":"#68768a"}
                    Repeater {
                        model:scene.sampleSizes
                        Product.HardwareGlyph {
                            required property int index;required property int modelData
                            objectName:"glyph_"+theme.index+"_"+card.index+"_"+modelData
                            x:scene.sampleXs[index];y:12+(64-height)/2;width:modelData;height:modelData
                            appearance:card.modelData.appearance;ink:theme.ink
                        }
                    }
                }
            }
        }
    }
}'''


def fan_note(appearance):
    """Describe physical and displayed fans without filling an unknown total."""
    if appearance.get("kind") != "gpu":
        return "已知 CPU 封装"
    total = appearance.get("fan_count")
    visible = appearance.get("visible_fan_count", total)
    total = total if type(total) is int and total >= 0 else None
    visible = visible if type(visible) is int and visible >= 0 else None
    if total is None and visible is None:
        return "风扇总数及正面布局未确认"
    if total is None:
        return f"总数未确认 · 图示正面 {visible} 扇"
    if visible is None:
        return f"物理共 {total} 扇 · 正面布局未确认"
    if total == visible == 0:
        return "无物理风扇"
    if total == visible:
        return f"物理 {total} 扇 · 均在正面"
    return f"物理共 {total} 扇 · 图示正面 {visible} 扇"


def variants(catalog, icon_set="outline"):
    sys.path.insert(0, str(ROOT))
    from hardware_appearance import CATALOG, appearance_for

    if catalog == "memory":
        from memory_appearance import CATALOG as MEMORY_MODELS, SERIES_CATALOG as MEMORY_SERIES, appearance_for_memory
        by_series = {row["id"]: row for row in MEMORY_SERIES}
        result = []
        for model in MEMORY_MODELS:
            appearance = appearance_for_memory(model=model["aliases"][0])
            appearance["icon_set"] = icon_set
            row = by_series[appearance["series_id"]]
            result.append(dict(label=row["label"], model_label=appearance["label"],
                               note=" / ".join(appearance["features"]), source_url=appearance["source_url"], appearance=appearance))
        return result

    if catalog == "models":
        result = []
        for row in CATALOG:
            appearance = appearance_for(row[1], row[-1][0])
            assert appearance["confidence"] == "model" and appearance["id"] == row[0]
            appearance["icon_set"] = icon_set
            note = "已确认型号 · " + fan_note(appearance)
            result.append(dict(label=appearance["label"], note=note, appearance=appearance))
        return result

    from hardware_series import SERIES_CATALOG
    result = []
    models = {}
    if catalog in ("series_models", "brands", "series"):
        for model in CATALOG:
            appearance = appearance_for(model[1], model[-1][0])
            if model[1] == "gpu" and appearance["series_id"]:
                models.setdefault(appearance["series_id"], appearance)
    if catalog == "brands":
        # Select real reviewed identities, including the asymmetric and optional
        # layouts that a uniform three-fan overview would conceal. A preference
        # is only a fixture choice, not an identification rule or recommendation.
        preferred = {
            "asus":"asus_astral", "msi":"msi_expert", "gigabyte":"gigabyte_aorus",
            "zotac":"zotac_solo", "sapphire":"sapphire_nitro", "powercolor":"powercolor_red_devil",
            "asrock":"asrock_taichi", "xfx":"xfx_merc", "pny":"pny_xlr8", "evga":"evga_ftw3",
            "leadtek":"leadtek_hurricane", "palit":"palit_gamerock", "gainward":"gainward_phantom",
            "galax":"galax_sg", "inno3d":"inno3d_ichill_x4", "colorful":"colorful_advanced",
            "maxsun":"maxsun_icraft", "yeston":"yeston_sakura", "biostar":"biostar_radeon",
            "nvidia":"nvidia_founders", "amd":"amd_reference", "intel":"intel_limited",
        }
        brands = dict.fromkeys(row["board_vendor"] for row in SERIES_CATALOG)
        for brand in brands:
            choices = [row for row in SERIES_CATALOG if row["board_vendor"] == brand and row["id"] in models]
            if not choices:
                raise ValueError(f"No confirmed model for board brand {brand}")
            row = next((row for row in choices if row["id"] == preferred.get(brand)), choices[0])
            appearance = dict(models[row["id"]], icon_set=icon_set)
            note = fan_note(appearance) + (" · 历史系列" if appearance.get("legacy") else "")
            result.append(dict(label=row["label"], model_label=appearance["label"], note=note,
                               source_url=appearance["source_url"], appearance=appearance))
        return result
    for row in SERIES_CATALOG:
        if catalog == "series_models":
            appearance = dict(models[row["id"]], icon_set=icon_set)
            assert appearance["confidence"] == "model"
            result.append(dict(label=row["label"], note=fan_note(appearance)+" · "+appearance["label"],
                               model_label=appearance["label"],
                               source_url=appearance["source_url"], appearance=appearance))
            continue
        if not row["aliases"]:
            appearance = dict(models[row["id"]], fan_count=None, visible_fan_count=None, style="gpu_neutral", confidence="series")
        else:
            appearance = appearance_for("gpu", row["board_vendor"] + " " + row["aliases"][0] + " unidentified GPU")
        assert appearance["series_id"] == row["id"] and appearance["fan_count"] is None
        assert appearance["style"] == "gpu_neutral"
        appearance["icon_set"] = icon_set
        result.append(dict(label=row["label"] + " · 系列示意",
                           note=" / ".join(row["features"]) + " · 未确认风扇",
                           source_url=row["source_url"], appearance=appearance))
    return result


def render(destination, scratch, catalog, icon_set="outline", compact=False):
    # Keep Qt's offscreen font search bounded; load the four named fonts below.
    # An empty private directory also avoids its unrelated missing-font warning.
    font_directory = scratch / "fonts"
    font_directory.mkdir(exist_ok=True)
    os.environ.update(DESKTOP_STATS_DATA=str(scratch / "profile"), QT_QPA_PLATFORM="offscreen",
                      QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic",
                      QT_QUICK_CONTROLS_STYLE="Basic", QML_DISABLE_DISK_CACHE="1",
                      QT_QPA_FONTDIR=str(font_directory),
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
    compact = compact or catalog in ("brands", "memory")
    component.setData((OVERVIEW_QML if compact else QML).encode("utf-8"),
                      QUrl.fromLocalFile(str(ROOT / "tools/hardware-catalog.qml")))
    if component.isError():
        raise RuntimeError("; ".join(error.toString() for error in component.errors()))
    cases = variants(catalog, icon_set)
    title = (f"{len(cases)} memory designs · {len(cases)} 内存条代表设计" if catalog == "memory" else
             f"{len(cases)} board brands · {len(cases)} 品牌代表型号" if catalog == "brands" else
             "Confirmed hardware models · 已确认型号" if catalog == "models" else
             "Individual cooler series · 逐系列外观" if catalog == "series_models" else "GPU cooler families · 系列外观示意")
    note = ("64 / 32 / literal 18px · Light + dark / " if compact else
            "18px actual size · 40px · 128px / " if catalog == "series_models" else "18px actual size · 32px · 64px / ") + ("Exact catalog identities; simplified physical layouts" if catalog in ("models", "series_models", "brands")
                                                else "Verified module form; enclosure details are static" if catalog == "memory"
                                                else "Family cues only; fan counts UNKNOWN, no fan circles")
    sizes = [128, 40, 18] if catalog == "series_models" and not compact else [64, 32, 18]
    window = component.createWithInitialProperties(dict(variants=cases, catalogTitle=title, catalogNote=note,
                                                       sampleSizes=sizes,
                                                       sampleXs=[6,82,122] if compact else
                                                       [14,180,270] if catalog == "series_models" else [20,130,220]))
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
                for size in sizes:
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
            width=image.width(), height=image.height(), literal_18px=True, compact=compact, warnings=warnings,
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
    parser.add_argument("--catalog", choices=("models", "series", "series_models", "brands", "memory"), default="models")
    parser.add_argument("--icon-set", choices=("outline", "solid", "miniature", "soft"), default="outline")
    parser.add_argument("--compact", action="store_true", help="Four-column cards with both themes and full model labels")
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
        result = render(destination, Path(scratch), args.catalog, args.icon_set, args.compact)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
