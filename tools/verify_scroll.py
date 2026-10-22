"""Exercise gallery scrolling with real wheel events on our own native Qt window.

No installed instance, hardware sampler, preference commit, or IPC is used.
Use --qml-root to compare a frozen release's QML with current source. A failure
in any scenario produces a nonzero exit code; contentY is never set by this test.
"""

# Qt and project modules must load after the isolated data/style environment.
# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DESKTOP_STATS_DATA"] = str(ROOT / "qa-private/scroll-gui-data")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QSG_RENDER_LOOP"] = "basic"

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QWheelEvent
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from native_card import HardwareCard
from native_controller import Controller


def descendants(node):
    queue, result, seen = [node], [], set()
    while queue:
        item = queue.pop()
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        result.append(item)
        queue.extend(item.children())
        if hasattr(item, "childItems"):
            queue.extend(item.childItems())
    return result


def variant(value):
    return value.toVariant() if hasattr(value, "toVariant") else value


def number(item, field):
    value = item.property(field)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else 0.0


class ScrollAudit:
    def __init__(self, window, controller, report):
        self.window, self.controller, self.report = window, controller, report
        self.gallery = window.findChild(QObject, "widgetGallery")
        assert self.gallery is not None, "Gallery popup not found"
        self.key = controller.addWidget("custom")
        assert self.key, "Could not create isolated draft widget"
        window.selectWidget(self.key)
        self.fixture = dict(time=time.time(), cpu_usage=18.0, cpu_temp=65.0, gpu_usage=12.0)
        controller.receive(self.fixture)
        self.frames = 0
        window.frameSwapped.connect(self.frame_rendered)

    def frame_rendered(self):
        self.frames += 1

    def wait_for_layout(self):
        """Require an actual rendered frame after changing popup/window geometry."""
        assert self.window.isExposed(), "The isolated native test window is not exposed"
        before = self.frames
        self.window.update()
        for _ in range(100):
            QTest.qWait(20)
            if self.frames > before:
                QTest.qWait(30)
                return
        raise AssertionError("No native Qt frame was rendered after a layout change")

    def find(self, name):
        return next(
            (item for item in descendants(self.window.contentItem()) if item.objectName() == name),
            None,
        )

    def check(self, case, name, condition, **details):
        case["checks"].append(dict(name=name, passed=bool(condition), **details))
        if not condition:
            self.report["failures"].append(case["name"] + ": " + name)

    @staticmethod
    def state(viewport):
        origin = number(viewport, "originY")
        content = number(viewport, "contentHeight")
        height = number(viewport, "height")
        return dict(
            contentY=number(viewport, "contentY"),
            originY=origin,
            contentHeight=content,
            viewportHeight=height,
            viewportWidth=number(viewport, "width"),
            maximumY=origin + max(0.0, content - height),
        )

    @staticmethod
    def visible_rect(item, viewport):
        point = item.mapToItem(viewport, QPointF(0, 0))
        return dict(x=point.x(), y=point.y(), width=item.width(), height=item.height())

    def fully_visible(self, item, viewport):
        rect = self.visible_rect(item, viewport)
        return (
            rect["x"] >= -2
            and rect["y"] >= -2
            and rect["x"] + rect["width"] <= viewport.width() + 2
            and rect["y"] + rect["height"] <= viewport.height() + 2
        )

    def wheel(self, viewport, delta, item=None):
        """Send a real QWheelEvent; do not call flick(), scrollTo(), or setContentY()."""
        if item is None:
            position = viewport.mapToScene(QPointF(viewport.width() * 0.5, viewport.height() * 0.5))
        else:
            rect = self.visible_rect(item, viewport)
            left, top = max(2.0, rect["x"]), max(2.0, rect["y"])
            right = min(viewport.width() - 2, rect["x"] + rect["width"])
            bottom = min(viewport.height() - 2, rect["y"] + rect["height"])
            assert right > left and bottom > top, "Wheel target card is outside the viewport"
            position = viewport.mapToScene(QPointF((left + right) / 2, (top + bottom) / 2))
        QTest.mouseMove(self.window, position.toPoint())
        event = QWheelEvent(
            position,
            QPointF(self.window.mapToGlobal(position.toPoint())),
            QPoint(),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        event.setTimestamp(round(time.monotonic() * 1000))
        delivered = QCoreApplication.sendEvent(self.window, event)
        QTest.qWait(160)
        # Observe real kinetic/bounds-return completion; never move the viewport.
        previous, stable = number(viewport, "contentY"), 0
        for _ in range(60):
            QTest.qWait(20)
            current = number(viewport, "contentY")
            stable = stable + 1 if abs(current - previous) < 0.1 else 0
            previous = current
            if stable >= 4:
                break
        return dict(delivered=bool(delivered), accepted=event.isAccepted())

    def wheel_to(self, viewport, bottom):
        for count in range(1, 101):
            state = self.state(viewport)
            target = state["maximumY"] if bottom else state["originY"]
            if abs(state["contentY"] - target) <= 2:
                return count - 1
            self.wheel(viewport, -480 if bottom else 480)
        return 100

    def run_case(self, mode, width, height):
        name = f"{mode}-{width}x{height}"
        case = dict(name=name, checks=[])
        self.report["cases"].append(case)
        try:
            self.gallery.close()
            self.window.resize(width, height)
            QTest.qWait(80)
            self.wait_for_layout()
            if mode == "metric":
                self.gallery.showReadings(self.key)
            else:
                self.gallery.showWidgets()
            QTest.qWait(220)
            self.wait_for_layout()
            body = self.gallery.property("contentItem")
            viewports = [
                item
                for item in descendants(body)
                if item.metaObject().indexOfProperty("contentY") >= 0
            ]
            assert len(viewports) == 1, f"Expected one gallery viewport, found {len(viewports)}"
            viewport = viewports[0]
            entries = variant(self.gallery.property("entries"))
            assert len(entries) >= 10, "The full gallery must have enough entries to overflow"
            first = self.find("galleryItem_" + entries[0]["id"])
            last = self.find("galleryItem_" + entries[-1]["id"])
            assert first is not None and last is not None, "First/last result not present"
            case["entryCount"] = len(entries)
            case["renderedFrames"] = self.frames
            # Reopening may legitimately remember scroll position. Establish the
            # initial top using real wheel input, never a contentY assignment.
            case["opening"] = self.state(viewport)
            case["setupWheelEvents"] = self.wheel_to(viewport, False)
            case["initial"] = initial = self.state(viewport)
            self.check(
                case,
                "real wheel input establishes the initial top",
                abs(initial["contentY"] - initial["originY"]) <= 2,
                state=initial,
            )
            self.check(
                case,
                "viewport has actual scroll extent",
                initial["maximumY"] - initial["originY"] > 20,
                state=initial,
            )
            self.check(
                case,
                "last card starts outside the visible viewport",
                not self.fully_visible(last, viewport),
            )
            extent = viewport.mapToScene(QPointF(viewport.width(), viewport.height()))
            self.check(
                case,
                "viewport fits inside settings content",
                extent.y() <= self.window.height() + 2,
                bottom=extent.y(),
                windowHeight=self.window.height(),
            )

            event = self.wheel(viewport, -120, first)
            after = self.state(viewport)
            self.check(
                case,
                "wheel over a result card scrolls down",
                after["contentY"] > initial["contentY"] + 1,
                before=initial["contentY"],
                after=after["contentY"],
                event=event,
            )
            event = self.wheel(viewport, 120)
            up = self.state(viewport)
            self.check(
                case,
                "wheel up reverses the scroll",
                up["contentY"] < after["contentY"] - 1,
                before=after["contentY"],
                after=up["contentY"],
                event=event,
            )

            events = self.wheel_to(viewport, True)
            bottom = self.state(viewport)
            case["bottom"] = bottom
            self.check(
                case,
                "wheel can reach the actual bottom",
                bottom["contentY"] > initial["originY"] + 20
                and abs(bottom["contentY"] - bottom["maximumY"]) <= 2,
                state=bottom,
                wheelEvents=events,
            )
            self.check(
                case,
                "last result is fully visible at bottom",
                self.fully_visible(last, viewport),
                rectangle=self.visible_rect(last, viewport),
            )

            self.fixture.update(time=time.time(), cpu_usage=self.fixture["cpu_usage"] + 1)
            self.controller.receive(dict(self.fixture))
            QTest.qWait(160)
            refreshed = self.state(viewport)
            self.check(
                case,
                "sampling does not reset the scroll position",
                abs(refreshed["contentY"] - bottom["contentY"]) <= 1,
                before=bottom["contentY"],
                after=refreshed["contentY"],
            )

            events = self.wheel_to(viewport, False)
            top = self.state(viewport)
            self.check(
                case,
                "wheel can return to the top",
                abs(top["contentY"] - top["originY"]) <= 2,
                state=top,
                wheelEvents=events,
            )
            self.check(
                case,
                "first result is visible after scrolling up",
                self.fully_visible(first, viewport),
            )

            search = self.find("gallerySearch")
            assert search is not None, "Gallery search not found"
            position = search.mapToScene(QPointF(search.width() / 2, search.height() / 2))
            QTest.mouseClick(
                self.window,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                position.toPoint(),
            )
            QTest.keyClick(self.window, Qt.Key.Key_Down)
            for _ in range(len(entries) - 1):
                QTest.keyClick(self.window, Qt.Key.Key_Right)
                QTest.qWait(2)
            QTest.qWait(160)
            focused = self.window.activeFocusItem()
            self.check(
                case,
                "keyboard navigation can select the final result",
                focused is not None and focused.objectName() == last.objectName(),
                focused=focused.objectName() if focused else None,
                expected=last.objectName(),
            )
            self.check(
                case,
                "keyboard selection reveals the offscreen result",
                self.fully_visible(last, viewport),
                state=self.state(viewport),
                rectangle=self.visible_rect(last, viewport),
            )
        except Exception:
            case["exception"] = traceback.format_exc()
            self.report["failures"].append(name + ": exception")
        finally:
            self.gallery.close()
            QTest.qWait(30)
        print(
            f"{name}: {sum(c['passed'] for c in case['checks'])}/{len(case['checks'])} checks",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qml-root", type=Path, default=ROOT / "native")
    parser.add_argument("--report", type=Path, default=ROOT / "qa-private/scroll-qa-report.json")
    parser.add_argument("--allow-visible-desktop", action="store_true")
    args = parser.parse_args()
    if not args.allow_visible_desktop:
        parser.error(
            "Visible-window tests are disabled by default; use verify_customization.py offscreen, or explicitly allow visible tests while the user is idle."
        )
    qml_root = args.qml_root.resolve()
    assert (qml_root / "Settings.qml").is_file(), "Missing Settings.qml"
    report = dict(
        qmlRoot=str(qml_root),
        pythonController=str(ROOT / "native_controller.py"),
        wheelEvent="QWheelEvent sent to the test's own QQuickWindow",
        inputManipulation="No contentY assignment, flick(), scrollbar drag, or scrollTo()",
        sources={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [qml_root / "Gallery.qml", qml_root / "Settings.qml", Path(__file__)]
        },
        cases=[],
        failures=[],
    )
    QQuickWindow.setDefaultAlphaBuffer(True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    controller = Controller()
    qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
    engine = QQmlApplicationEngine()
    messages = []
    engine.warnings.connect(
        lambda warnings: messages.extend(warning.toString() for warning in warnings)
    )
    engine.rootContext().setContextProperty("stats", controller)
    engine.load(QUrl.fromLocalFile(str(qml_root / "Settings.qml")))
    assert engine.rootObjects(), "Settings failed to load"
    window = engine.rootObjects()[0]
    window.setTitle("Desktop Stats — isolated scroll verification")
    window.show()
    window.requestActivate()

    def exercise():
        try:
            assert QTest.qWaitForWindowExposed(window, 3000), "Native test window was not exposed"
            audit = ScrollAudit(window, controller, report)
            for width, height in [(1160, 790), (720, 560)]:
                for mode in ("widget", "metric"):
                    audit.run_case(mode, width, height)
        except Exception:
            report["exception"] = traceback.format_exc()
            report["failures"].append("Native test setup failed")
        finally:
            controller.close()
            window.hide()
            app.quit()

    # Qt Quick must run inside the real application event loop so geometry is
    # polished/rendered between inputs. qWait before app.exec() is insufficient.
    QTimer.singleShot(300, exercise)
    app.exec()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    report["qmlWarnings"] = messages
    if messages:
        report["failures"].append("QML warnings were emitted")
    report["passed"] = not report["failures"]
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            dict(passed=report["passed"], failures=report["failures"], report=str(report_path)),
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
