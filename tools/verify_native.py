"""Render our own native windows and record composition/interaction evidence."""

import faulthandler
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
os.environ["DESKTOP_STATS_DATA"] = str(ROOT / "qa-private/native-qa-data")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QSG_RENDER_LOOP"] = "basic"
faulthandler.enable()
faulthandler.dump_traceback_later(20, repeat=True)

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, qInstallMessageHandler
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from localization import LANGUAGES
from native_runtime import Runtime
from presets import catalogue
from stats_config import save

config = catalogue()["overview"]["config"]
save(config)
QQuickWindow.setDefaultAlphaBuffer(True)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
runtime = Runtime(app)
result = [0]
warnings = []


def qt_message(kind, context, message):
    if (
        "Error" in message
        or "is not defined" in message
        or "Unable to assign" in message
        or "Cannot" in message
    ):
        warnings.append(message)


qInstallMessageHandler(qt_message)


def capture():
    try:
        runtime.diagnose(ROOT / "qa-private/native-first.json")
        print("composition", runtime.composition)
        assert runtime.settings.isVisible()
        assert runtime.controller._data.get("time")
        for language in LANGUAGES:
            runtime.controller.change("language", language)
            QTest.qWait(20)
            for item in runtime.settings.findChildren(QObject):
                if item.metaObject().indexOfProperty("valueRole") >= 0 and item.property("count"):
                    assert item.property("currentIndex") >= 0, (language, item.property("value"))
        runtime.controller.change("language", "zh-CN")
        runtime.controller.changeWidget("gpu", "enabled", True)
        runtime.controller.changeWidget("cpu", "size", 117.0)
        button = runtime.settings.findChild(QObject, "applyButton")
        center = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
        QTest.mouseClick(
            runtime.settings, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center
        )
        QTest.qWait(120)
        assert not runtime.controller.dirty, runtime.controller.status
        assert len(runtime.widgets) == 2
        assert runtime.controller._saved["widgets"]["cpu"]["size"] == 117
        before_hide = runtime.controller._saved["widgets"].copy()
        runtime.controller.quick("visible")
        assert not runtime.widgets
        runtime.controller.quick("visible")
        assert len(runtime.widgets) == 2
        assert runtime.controller._saved["widgets"] == before_hide
        runtime.controller.preset("compact")
        runtime.controller.change("opacity", 72)
        runtime.controller.apply()
        runtime.settings.setProperty("page", 1)
        QTest.qWait(180)
        runtime.diagnose(ROOT / "qa-private/native-appearance.json")
        runtime.controller.change("theme", "dark")
        runtime.controller.change("language", "en")
        runtime.controller.apply()
        QTest.qWait(180)
        runtime.diagnose(ROOT / "qa-private/native-dark.json")
        runtime.settings.resize(940, 640)
        runtime.settings.setProperty("page", 0)
        QTest.qWait(180)
        runtime.diagnose(ROOT / "qa-private/native-small.json")
        assert all(
            item["above_desktop"]
            for item in __import__("json")
            .loads((ROOT / "qa-private/native-small.json").read_text(encoding="utf-8"))["windows"]
            .values()
        )
        runtime.settings.resize(720, 540)
        QTest.qWait(140)
        assert runtime.settings.property("previewWidth") == 0
        runtime.diagnose(ROOT / "qa-private/native-compact-window.json")
        runtime.controller.preset("detailed")
        runtime.controller.apply()
        QTest.qWait(140)
        assert set(runtime.widgets) == {"group"}
        runtime.diagnose(ROOT / "qa-private/native-group.json")
        runtime.controller.change("mode", "mixed")
        runtime.controller.apply()
        QTest.qWait(140)
        assert len(runtime.widgets) == 4
        runtime.settings.close()
        assert not runtime.settings.isVisible()
        assert runtime.widgets
        runtime.show_settings("gpu")
        assert runtime.settings.isVisible()
        assert runtime.settings.property("selectedKey") == "gpu"
        assert not warnings, warnings
        print(
            "Native workflows: 8 languages, real Apply click, hide/restore, sizes, presets, combined/mixed, dark mode, resize, close/reopen: PASS"
        )
    except Exception:
        traceback.print_exc()
        result[0] = 1
    finally:
        app.quit()


QTimer.singleShot(3500, capture)
app.exec()
raise SystemExit(result[0])
