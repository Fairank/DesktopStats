"""Exercise the new gallery and drag resize on our own native windows."""

import faulthandler
import json
import os
import sys
import traceback
from pathlib import Path

if __name__ == "__main__" and "--allow-visible-desktop" not in sys.argv:
    raise SystemExit(
        "Visible-window test disabled. Use verify_customization.py for offscreen checks, or --allow-visible-desktop only while the user is idle."
    )

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DESKTOP_STATS_DATA"] = str(ROOT / "qa-private/upgrade-gui-data")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QSG_RENDER_LOOP"] = "basic"
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QTimer, qInstallMessageHandler
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from localization import LANGUAGES
from native_runtime import Runtime
from presets import catalogue
from stats_config import load, save

save(catalogue()["overview"]["config"])
faulthandler.enable()
faulthandler.dump_traceback_later(35)
QQuickWindow.setDefaultAlphaBuffer(True)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
messages = []
qInstallMessageHandler(lambda kind, ctx, message: messages.append(message))
runtime = Runtime(app)
ui = runtime.controller
result = 0


def descendants(node):
    visited = set()
    queue = [node]
    out = []
    while queue:
        item = queue.pop()
        if id(item) in visited:
            continue
        visited.add(id(item))
        out.append(item)
        queue.extend(item.children())
        if hasattr(item, "childItems"):
            queue.extend(item.childItems())
    return out


def find(name):
    return next(
        (item for item in descendants(runtime.settings.contentItem()) if item.objectName() == name),
        None,
    )


def click(item, window=None):
    window = window or runtime.settings
    center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center)
    QTest.qWait(100)


def capture():
    global result
    try:
        settings = runtime.settings
        runtime.diagnose(ROOT / "qa-private/upgrade-settings.json")
        click(settings.findChild(QObject, "addWidgetButton"))
        gallery = settings.findChild(QObject, "widgetGallery")
        assert gallery.property("opened")
        gallery.setProperty("query", "MB/s")
        QTest.qWait(50)
        assert find("galleryItem_network") is not None
        gallery.setProperty("query", "")
        QTest.qWait(300)
        settings.grabWindow().save(str(ROOT / "qa-private/upgrade-gallery.png"))
        gallery.setProperty("query", "network")
        QTest.qWait(100)
        item = find("galleryItem_network")
        assert item is not None
        click(item)
        added = settings.property("selectedKey")
        assert added.startswith("w_")
        assert ui._draft["widgets"][added]["kind"] == "network"
        gallery.showReadings(added)
        QTest.qWait(100)
        metric = find("galleryItem_cpu_usage")
        metric.forceActiveFocus()
        ui.receive(dict(ui._data, cpu_usage=37.5))
        QTest.qWait(50)
        assert settings.activeFocusItem().objectName() == "galleryItem_cpu_usage"
        find("gallerySearch").forceActiveFocus()
        QTest.keyClick(settings, Qt.Key_Down)
        assert settings.activeFocusItem().objectName().startswith("galleryItem_")
        QTest.keyClick(settings, Qt.Key_Escape)
        QTest.qWait(50)
        assert not gallery.property("opened") and settings.isVisible()
        assert settings.findChild(QObject, "addWidgetButton").property("activeFocus")
        ui.changeWidget(added, "size", 100)
        click(settings.findChild(QObject, "applyButton"))
        assert added in runtime.widgets
        before = ui._saved["widgets"][added]["size"]
        window = runtime.widgets[added]
        start = QPoint(window.width() - 18, window.height() - 18)
        end = QPoint(window.width() - 2, window.height() - 2)
        QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(window, end, 150)
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
        QTest.qWait(150)
        assert ui._saved["widgets"][added]["size"] > before, (
            before,
            ui._saved["widgets"][added]["size"],
        )
        assert load()["widgets"][added]["size"] == ui._saved["widgets"][added]["size"]
        ui.changeWidget(added, "title", "网络桌面")
        # This is a real shortcut event while editing the title field.
        title = settings.findChild(QObject, "widgetTitle")
        title.forceActiveFocus()
        QTest.keyClick(settings, Qt.Key_X)
        QTest.keyClick(settings, Qt.Key_S, Qt.ControlModifier)
        QTest.qWait(100)
        assert not ui.dirty
        assert ui._saved["widgets"][added]["title"].upper().endswith("X"), ui._saved["widgets"][
            added
        ]["title"]
        duplicate = ui.duplicateWidget(added)
        ui.moveWidget(duplicate, -1)
        ui.removeWidget(added)
        ui.apply()
        assert added not in runtime.widgets and duplicate in runtime.widgets
        power = ui.addWidget("power")
        ui.apply()
        settings.selectWidget(power)
        QTest.qWait(250)
        runtime.diagnose(ROOT / "qa-private/upgrade-power.json")
        preview = settings.findChild(QObject, "actualSizePreview")
        from PySide6.QtCore import QMetaObject

        QMetaObject.invokeMethod(preview, "open")
        QTest.qWait(100)
        settings.grabWindow().save(str(ROOT / "qa-private/upgrade-actual-size.png"))
        QMetaObject.invokeMethod(preview, "close")
        key = ui.addWidget("overview")
        ui.addMetric(key, "net_download")
        ui.addMetric(key, "disk_read")
        ui.apply()
        settings.selectWidget(key)
        QTest.qWait(250)
        runtime.diagnose(ROOT / "qa-private/upgrade-six.json")
        for lang in LANGUAGES:
            ui.change("language", lang)
            QTest.qWait(15)
        ui.change("language", "en")
        ui.change("theme", "dark")
        ui.apply()
        settings.resize(1020, 700)
        QTest.qWait(100)
        runtime.diagnose(ROOT / "qa-private/upgrade-dark.json")
        settings.resize(720, 560)
        QTest.qWait(100)
        runtime.diagnose(ROOT / "qa-private/upgrade-compact.json")
        ui.change("language", "zh-CN")
        ui.apply()
        settings.resize(1160, 790)
        ui.change("mode", "combined")
        ui.apply()
        QTest.qWait(200)
        group = runtime.widgets["group"]
        old = ui._saved["widgets"][key]["size"] or ui._saved["size"]
        start = QPoint(group.width() - 18, group.height() - 18)
        end = QPoint(group.width() - 2, group.height() - 2)
        QTest.mousePress(group, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(group, end, 150)
        QTest.mouseRelease(group, Qt.LeftButton, Qt.NoModifier, end)
        QTest.qWait(150)
        assert (ui._saved["widgets"][key]["size"] or ui._saved["size"]) > old, (
            old,
            ui._saved["widgets"][key]["size"],
            group.width(),
            group.height(),
        )
        runtime.diagnose(ROOT / "qa-private/upgrade-combined.json")
        for name in list(ui._draft["widget_order"]):
            ui.removeWidget(name)
        ui.apply()
        assert not runtime.widgets and not ui._draft["widget_order"]
        settings.grabWindow().save(str(ROOT / "qa-private/upgrade-empty.png"))
        assert not [
            m
            for m in messages
            if any(x in m for x in ("Error", "Cannot", "Unable", "is not defined", "Binding loop"))
        ], messages
        print(
            "PASS: gallery search/add, real native drag resize, shortcut save, duplicate/reorder/remove, power and six readings, 8 languages, compact/dark, group resize, empty desktop"
        )
    except Exception:
        traceback.print_exc()
        result = 1
        print("Qt messages", json.dumps(messages, ensure_ascii=True))
    finally:
        app.quit()


QTimer.singleShot(3600, capture)
app.exec()
sys.exit(result)
