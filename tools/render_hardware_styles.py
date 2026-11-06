"""Compare actual icon versions in owned offscreen QML, never on the desktop."""

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
    id:scene; visible:false; width:3236; height:866
    property bool dark:false
    property var cases:[]
    property var styles:[]
    readonly property color ink:dark?"#e8edf4":"#303a48"
    readonly property color muted:dark?"#a1aebf":"#68768a"
    color:dark?"#1c222b":"#eff2f6"
    Text {x:28;y:22;text:"硬件图标 · 十三种外观版本";font.family:"Microsoft YaHei UI"
        font.pixelSize:23;font.weight:Font.DemiBold;color:scene.ink}
    Text {x:28;y:61;text:"放大外观 + 18px 顶部栏实际大小  /  静态矢量，无新增动画或采样"
        font.family:"Microsoft YaHei UI";font.pixelSize:12;color:scene.muted}
    Text {x:28;y:822;text:"结构线稿为上一版保留样式。新方案按已确认型号匹配风扇；未知型号保留中性板卡。"
        font.family:"Microsoft YaHei UI";font.pixelSize:12;color:scene.muted}
    Repeater {
        model:scene.cases
        Text {
            required property int index; required property var modelData
            x:28;y:180+index*126;width:160
            text:modelData.label;textFormat:Text.PlainText
            font.family:"Microsoft YaHei UI";font.pixelSize:12;font.weight:Font.Medium
            color:scene.ink;wrapMode:Text.WordWrap;lineHeight:1.25
        }
    }
    Repeater {
        model:scene.styles
        Item {
            id:column; required property int index; required property var modelData
            x:202+index*232;y:107;width:220;height:688
            Text {x:0;y:0;width:220;text:column.modelData.label;horizontalAlignment:Text.AlignHCenter
                font.family:"Microsoft YaHei UI";font.pixelSize:16;font.weight:Font.DemiBold;color:scene.ink}
            Text {x:0;y:26;width:220;text:column.modelData.note;horizontalAlignment:Text.AlignHCenter
                font.family:"Microsoft YaHei UI";font.pixelSize:10;color:scene.muted}
            Repeater {
                model:scene.cases
                Rectangle {
                    id:cell;required property int index;required property var modelData
                    x:0;y:58+index*126;width:220;height:118;radius:11
                    color:scene.dark?"#252d38":"#ffffff"
                    border.width:1;border.color:scene.dark?"#394350":"#dce3ed"
                    readonly property var chosen:Object.assign({},modelData.appearance,{icon_set:column.modelData.id})
                    Product.HardwareGlyph {
                        objectName:"sample_"+column.index+"_"+cell.index+"_72"
                        x:74;y:4;width:72;height:72;appearance:cell.chosen;ink:scene.ink
                    }
                    Rectangle {
                        x:49;y:84;width:122;height:25;radius:6
                        color:scene.dark?"#303947":"#f0f3f7"
                        Product.HardwareGlyph {
                            objectName:"sample_"+column.index+"_"+cell.index+"_18"
                            x:13;y:3.5;width:18;height:18;appearance:cell.chosen;ink:scene.ink
                        }
                        Text {x:40;y:4;text:cell.modelData.value; font.family:"Segoe UI";font.pixelSize:12
                            font.weight:Font.Medium;color:scene.ink}
                    }
                }
            }
        }
    }
}'''


def render(output, scratch, *, dark=False):
    os.environ.update(DESKTOP_STATS_DATA=str(scratch / "profile"), QT_QPA_PLATFORM="offscreen",
                      QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic", QML_DISABLE_DISK_CACHE="1",
                      QT_SCALE_FACTOR="1", QT_AUTO_SCREEN_SCALE_FACTOR="0", TEMP=str(scratch), TMP=str(scratch))
    sys.path.insert(0, str(ROOT))
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, qmlContext
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from hardware_appearance import appearance_for

    app = QApplication.instance() or QApplication([])
    if app.platformName() != "offscreen":
        raise RuntimeError("This tool only renders owned offscreen windows")
    for name in ("segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    styles = [dict(id=key, label=label, note=note) for key, label, note in (
        ("classic", "经典通用", "原来图标"), ("outline", "结构线稿", "上一版 · 保留可选"),
        ("solid", "精简实物", "实体外壳 / 清晰风扇"), ("miniature", "微型实物", "薄顶边 / 立体厚度"),
        ("soft", "柔和双色", "圆角色块 / 简单可爱"),
        ("cartoon", "可爱卡通", "圆润描边 / 保留型号结构"),
        ("sketch", "手绘线稿", "原线稿 / 保留可选"),
        ("notebook_line", "随手线条", "不齐笔触 / 透明留白"),
        ("notebook_color", "手涂淡彩", "铅笔淡彩 / 保留型号结构"),
        ("notebook_smile", "笑脸手绘", "淡彩表情 / 独立可选"),
        ("sticker", "奶油贴纸", "奶油浅色 / 细描边"),
        ("papercut", "拼色剪纸", "平面拼色 / 简洁面板"),
        ("inkwash", "蓝墨手账", "蓝墨线条 / 淡色笔触"))]
    samples = (
        ("Intel Core i7-13700KF\n长方形顶盖", "cpu", "Intel Core i7-13700KF", "42%"),
        ("ZOTAC SOLO\n单风扇 · 紧凑短卡", "gpu", "ZOTAC GAMING GeForce RTX 4060 8GB SOLO", "36%"),
        ("ASUS Dual\n双风扇 · 中长卡身", "gpu", "DUAL-RTX4060-O8G", "36%"),
        ("ASUS TUF Gaming\n三风扇 · 修长卡身", "gpu", "TUF-RTX4070TIS-O16G-GAMING", "36%"),
        ("未确认整卡型号\n保留中性外观", "gpu", "NVIDIA GeForce RTX 4070", "36%"),
    )
    cases = [dict(label=label, appearance=appearance_for(kind, name), value=value)
             for label, kind, name, value in samples]
    engine, warnings = QQmlEngine(), []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    component = QQmlComponent(engine)
    component.setData(QML.encode(), QUrl.fromLocalFile(str(ROOT / "tools/hardware-styles.qml")))
    window = component.createWithInitialProperties(dict(dark=dark, cases=cases, styles=styles))
    if not isinstance(window, QQuickWindow):
        raise RuntimeError([error.toString() for error in component.errors()])
    try:
        window.show()
        QTest.qWait(100)
        app.processEvents()
        visual, pending = {}, [window.contentItem()]
        while pending:
            item = pending.pop()
            visual[item.objectName()] = item
            pending.extend(item.childItems())
        for column, style in enumerate(styles):
            for row in range(len(cases)):
                for size in (18, 72):
                    glyph = visual[f"sample_{column}_{row}_{size}"]
                    if style["id"] != "classic":
                        ready = QQmlExpression(qmlContext(glyph), glyph, "children[1].status === Image.Ready").evaluate()
                        ready = ready[0] if isinstance(ready, tuple) else ready
                        if not ready:
                            raise RuntimeError(f"Image not ready: {style['id']}/{row}/{size}")
        if warnings:
            raise RuntimeError(warnings)
        capture = window.grabWindow()
        if capture.isNull() or not capture.save(str(output)):
            raise RuntimeError("Could not save comparison image")
        result = dict(image=str(output), theme="dark" if dark else "light", glyphs=len(styles)*len(cases)*2,
                      styles=styles, cases=cases, warnings=warnings, actual_size=18)
        output.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(image=str(output), glyphs=len(styles)*len(cases)*2, warnings=0)
    finally:
        window.hide()
        window.destroy()
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa-private/hardware-icon-styles.png")
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        parser.error("Use --overwrite to replace a generated preview")
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch_root = ROOT / "qa-private/hardware-style-scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_root) as scratch, \
         patch.object(ctypes, "WinDLL", side_effect=AssertionError("No native API")), \
         patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess")), \
         patch("threading.Thread.start", side_effect=AssertionError("No worker threads")):
        print(json.dumps(render(output, Path(scratch), dark=args.dark), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
