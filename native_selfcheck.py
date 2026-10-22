"""Isolated bundle health check: no tray, IPC, sensors, migration or native desktop."""

import copy
import json
import os
import time
from pathlib import Path


def run(output):
    location = os.environ.get("DESKTOP_STATS_DATA")
    if not location or not Path(location).is_absolute():
        raise ValueError("Self-check requires an explicitly isolated DESKTOP_STATS_DATA directory")
    base = Path(location).resolve()
    output = Path(output).resolve()
    if output.suffix.lower() != ".json" or not output.is_relative_to(base) or output.exists():
        raise ValueError("Use a new report path inside the isolated self-check data directory")
    base.mkdir(parents=True, exist_ok=True)
    if any(base.iterdir()):
        raise ValueError("Self-check refuses an existing application profile")
    output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        QSG_RENDER_LOOP="basic",
        QT_QUICK_CONTROLS_STYLE="Basic",
    )
    report = {
        "ok": False,
        "checks": [],
        "hardware": False,
        "native_composition": False,
        "installed_app_ipc": False,
        "foreground_windows": False,
    }
    try:
        _check(report, output)
        report["ok"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return 0 if report["ok"] else 1


def _check(report, output):
    from PySide6.QtCore import (
        QBuffer,
        QCoreApplication,
        QEvent,
        QIODevice,
        QLibraryInfo,
        Qt,
        QUrl,
        qVersion,
    )
    from PySide6.QtGui import QFontDatabase, QImage, QPainter
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, qmlRegisterType
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtWidgets import QApplication

    from material_policy import render_policy
    from native_card import HardwareCard
    from native_controller import Controller
    from native_layout import windows
    from native_surface import MaterialSurface
    from product_version import VERSION
    from stats_config import ASSETS, DEFAULT
    from top_bar_runtime import BarViewState

    plugins = [Path(path) for path in QCoreApplication.libraryPaths()]
    plugins.append(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)))
    plugins.append(ASSETS / "PySide6/plugins")
    if not any((path / "platforms/qoffscreen.dll").is_file() for path in plugins):
        raise RuntimeError("Missing offscreen Qt plugin; refusing to start a different platform")
    QQuickWindow.setDefaultAlphaBuffer(True)
    app = QApplication([])
    assert app.platformName() == "offscreen", "Refusing a native desktop platform"
    app.setQuitOnLastWindowClosed(False)
    font_directory = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("msyh.ttc", "msyhbd.ttc", "SegUIVar.ttf", "segoeui.ttf"):
        path = font_directory / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    assert QFontDatabase.families(), "No real fonts available for the offscreen render"
    report.update(
        version=VERSION,
        qt=qVersion(),
        platform=app.platformName(),
        font_families=len(QFontDatabase.families()),
    )
    for name in ("assets/icon.ico", "assets/icon.png", "locales.txt"):
        assert (ASSETS / name).is_file(), f"Missing bundled asset: {name}"
    report["checks"].append("assets")
    qmlRegisterType(HardwareCard, "DesktopStats", 1, 0, "HardwareCard")
    qmlRegisterType(MaterialSurface, "DesktopStats", 1, 0, "MaterialSurface")
    engine, controller = QQmlApplicationEngine(), Controller()
    warnings, objects, components = [], [], []
    engine.warnings.connect(lambda items: warnings.extend(item.toString() for item in items))
    engine.rootContext().setContextProperty("stats", controller)
    bar_state = BarViewState(engine, "self-check")
    bar_state._config = copy.deepcopy(DEFAULT)
    try:
        for filename in (
            "Settings.qml", "DesktopWidget.qml", "Details.qml", "TopBar.qml", "TopBarDetails.qml"
        ):
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(ASSETS / "native" / filename)))
            components.append(component)
            assert not component.isError(), "; ".join(
                error.toString() for error in component.errors()
            )
            initial = {}
            if filename in ("TopBar.qml", "TopBarDetails.qml"):
                initial["barState"] = bar_state
            if filename == "DesktopWidget.qml":
                spec = windows(DEFAULT)[0]
                spec["material_policy"] = render_policy(DEFAULT, spec)
                initial["spec"] = spec
            window = component.createWithInitialProperties(initial)
            assert window is not None, f"Could not create bundled {filename}"
            objects.append(window)
            assert not window.isVisible(), "Self-check must not show even an offscreen window"
            if filename == "DesktopWidget.qml":
                scene = window.contentItem()
                names = [child.objectName() for child in scene.childItems()]
                report["widget_scene_children"] = names
                assert "moveHandle" in names and "resizeHandle" in names, (
                    "Widget input handles must belong to the actual window scene"
                )
            report["checks"].append(filename)
        config = copy.deepcopy(DEFAULT)
        card = HardwareCard()
        card.setWidth(168)
        card.setHeight(168)
        card.set_key("cpu")
        card.set_config(config)
        card.set_data({"time": time.time(), "cpu_temp": 65, "cpu_usage": 21})
        image = QImage(168, 168, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            card.paint(painter)
        finally:
            painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert image.save(buffer, "PNG"), "Could not encode bundle-render evidence"
        with output.with_suffix(".png").open("xb") as file:
            file.write(bytes(buffer.data()))
        report["checks"].append("native-card-render")
        QCoreApplication.processEvents()
    finally:
        for item in [*objects, *components, engine]:
            item.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    report["qml_warnings"] = warnings
    assert not warnings, "; ".join(warnings)
