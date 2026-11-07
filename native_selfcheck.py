"""Isolated bundle health check: no tray, IPC, sensors, migration or native desktop."""

import copy
import json
import os
import sys
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
    from PySide6.QtGui import QFontDatabase, QImage, QPainter, QWindow
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
            "Settings.qml", "DesktopWidget.qml", "Details.qml", "TopBar.qml", "TopBarDetails.qml",
            "AssemblyPage.qml", "AssemblyClock.qml",
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
            if isinstance(window,QWindow):
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
        # Exercise the optional geometry and profile adapter without a GL
        # context, Windows inventory, sensor sampling or an assembly window.
        from assembly_spec import build_spec
        from assembly_profiles import bake_profiles
        from assembly_geometry import build_scene
        from PySide6 import QtOpenGL,QtOpenGLWidgets
        assembly=build_spec(dict(cpu_name="Intel Core i7-13700KF",gpus={"0":dict(gpu_name="RTX 5090")}),
                            copy.deepcopy(DEFAULT),dict(state="unavailable"),[])
        scene=build_scene(bake_profiles(assembly,engine))
        assert scene.meshes,"Missing optional assembly geometry"
        report["assembly_meshes"]=len(scene.meshes)
        report["checks"].append("assembly-geometry-no-graphics")
        from chassis_catalog import coverage
        from top_bar_config import HARDWARE_ICON_STYLES
        report["assembly_cases"]=coverage()["cases"]
        report["assembly_styles"]=len(HARDWARE_ICON_STYLES)
        assert report["assembly_cases"]>=64 and report["assembly_styles"]==13
        for style in HARDWARE_ICON_STYLES:
            styled=copy.deepcopy(assembly);styled['visual_style']=style
            result=build_scene(styled)
            assert result.dimensions==scene.dimensions and result.metadata['visual_style']==style
        report["checks"].append("assembly-style-catalog-no-graphics")
        from assembly_effects import SelectionEffect,policies
        assert len(policies())==13 and len({row['kind'] for row in policies()})==13
        for policy in policies():
            effect=SelectionEffect();assert effect.start(policy['style'],'gpu')
            for _ in range(26):effect.advance(34.)
            assert not effect.active and effect.sample()['amount']==0.
        assert scene.metadata.get('detail_level')=='balanced'
        assert scene.triangle_count<=40000
        report['assembly_effects']=13
        report["checks"].append("assembly-finite-effects-no-graphics")
        from assembly_parts import choices,reference_preset
        catalog=choices()
        assert len(catalog['gpus'])>=148 and len(catalog['memory'])>=28
        assert len(catalog['boards'])>=17 and len(catalog['coolers'])>=27 and len(catalog['fans'])>=27
        reference=copy.deepcopy(DEFAULT)
        reference['assembly']=reference_preset(reference['assembly'],'air')
        reference['assembly']['part_styles']={'case':'notebook_color','gpu':'miniature','fans:front:0':'notebook_line'}
        reference_spec=build_spec(dict(cpu_name='Intel Core i7-13700KF',gpus={'0':dict(gpu_name='RTX 5090')}),
                                 reference,dict(state='unavailable'),[])
        assembled=build_scene(bake_profiles(reference_spec,engine))
        assert assembled.metadata['canvas_style']=='notebook_color'
        assert assembled.metadata['part_style_map']['gpu']=='miniature'
        assert assembled.metadata['part_style_map']['fans:front:0']=='notebook_line'
        assert assembled.metadata['cooling']['parts'] and assembled.metadata['auxiliary']['parts']
        report['assembly_catalog_counts']={key:len(value) for key,value in catalog.items() if key in ('gpus','memory','boards','coolers','fans','psus','storage','expansion')}
        report["checks"].append("assembly-reference-parts-and-mixed-styles-no-graphics")
        from hardware_packs import PackStore
        pack_store=PackStore(output.parent/'unused-hardware-packs')
        report['hardware_pack_state']=pack_store.memory_status()
        assert report['hardware_pack_state']['packs']==0
        assert report['hardware_pack_state']['persistent_meshes']==0
        assert report['hardware_pack_state']['background_workers']==0
        assert 'cpu_catalog' not in sys.modules,'Optional authoring catalog loaded in base runtime'
        assert assembly['cpu']['appearance']['cpu_package']['model_id']=='intel-13700kf'
        assert scene.metadata['cpu_package']['available']
        report['checks'].append('optional-pack-lazy-runtime-and-base-cpu-no-graphics')
        assert 'accessory_art' not in sys.modules,'Dormant accessory gallery loaded its artwork'
        from accessory_art import choices as accessory_choices,art as accessory_art,clear_cache,cache_info
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer
        accessory_catalog=accessory_choices()
        report['accessory_catalog_counts']={key:len(rows) for key,rows in accessory_catalog.items()}
        assert report['accessory_catalog_counts']==dict(cases=64,coolers=42,psus=21,fans=38)
        for kind,key in (('case','cases'),('cooler','coolers'),('psu','psus'),('fan','fans')):
            for style in ('miniature','notebook_line'):
                artwork=accessory_art(kind,accessory_catalog[key][0]['id'],style)
                svg=QSvgRenderer(QByteArray(artwork['svg'].encode('utf8')))
                assert svg.isValid(),(kind,style)
                sample=QImage(120,100,QImage.Format_ARGB32_Premultiplied);sample.fill(Qt.transparent)
                paint=QPainter(sample)
                try:svg.render(paint)
                finally:paint.end()
                assert any(sample.pixelColor(x,50).alpha()>0 for x in range(120)),(kind,style)
        clear_cache();assert cache_info()['entries']==0
        report['checks'].append('accessory-svg-catalog-render-and-release-no-graphics')
        QCoreApplication.processEvents()
    finally:
        for item in [*objects, *components, engine]:
            item.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    report["qml_warnings"] = warnings
    assert not warnings, "; ".join(warnings)
