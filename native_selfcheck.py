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
        from assembly_gpu_insertion049 import GpuInsertion,insertion_plan
        insertion=insertion_plan(assembled)
        assert insertion['available'],insertion['reason']
        assert 16.<=insertion['distance_mm']<=52.
        motion=GpuInsertion()
        assert motion.start(True)
        for _ in range(32):motion.advance(34.)
        assert motion.progress==1. and not motion.active
        assert motion.start(False)
        for _ in range(32):motion.advance(34.)
        assert motion.progress==0. and not motion.active
        report['gpu_insertion_check']=dict(available=True,distance_mm=insertion['distance_mm'],
            finite_out_and_back=True,scene_rebuilt=False,graphics_context=False)
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
        expected_counts=dict(cases=report['assembly_cases'],**{
            key:sum(bool(row.get('id')) for row in catalog[key]) for key in ('coolers','psus','fans')})
        expected_counts.update({key:0 for key in ('cpu_blocks','loop_pumps','loop_reservoirs','loop_combos','loop_fittings','loop_tubing','gpu_blocks')})
        assert report['accessory_catalog_counts']==expected_counts
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
        # Exercise each bounded data schema in the frozen runtime. These are
        # isolated synthetic fixtures derived from existing references, never
        # imported into the user's library or counted as product coverage.
        import hardware_packs
        from cooling_catalog import get_fan,get_cooler
        from liquid_cooling_catalog044 import get_radiator
        previous_store=hardware_packs._store
        fixture_store=PackStore(output.parent/'self-check-only-model-packs')
        try:
            hardware_packs._store=fixture_store
            getters={'fan':get_fan,'cooler':get_cooler,'radiator':get_radiator}
            base_ids={'fan':'noctua-nf-a12x25-pwm','cooler':'noctua-nh-u12a','radiator':'corsair-xr5-240'}
            for kind,getter in getters.items():
                identity='self-check-'+kind
                reference=getter(base_ids[kind]);reference.update(id=identity,label='Isolated '+kind+' fixture')
                if kind=='fan':
                    selector={key:reference.get(key) for key in ('size_mm','depth_mm','frame','mount_pitch_mm','mount_pitch_verified')}
                    selector['frameless']=reference.get('frameless',False)
                elif kind=='cooler':
                    reference['fan_reference_mm']=120
                    selector=dict(kind=reference['kind'],fan_size_mm=120)
                else:
                    selector={key:reference[key] for key in ('fan_size_mm','fan_count','fan_mount_pitch_mm','fan_mount_pitch_verified')}
                row=dict(id=identity,label=reference['label'],vendor=reference['brand'],series=reference['series'],
                         aliases=[identity],sources=reference['sources'],reference=reference,selector=selector)
                source=output.parent/(identity+'.dspack')
                source.write_bytes(hardware_packs.make_pack(identity,reference['label'],[row],kind=kind))
                fixture_store.install(source)
                assert getter(identity)['id']==identity
                assert len(fixture_store.choices(kind))==1
            assert fixture_store.choices()==[], 'Cooling identities cannot enter CPU matching'
            for kind in ('fan','cooler'):
                artwork=accessory_art(kind,'self-check-'+kind,'notebook_line')
                assert QSvgRenderer(QByteArray(artwork['svg'].encode('utf8'))).isValid()
            from assembly_cooling import add_cooling
            meshes,metadata=add_cooling((),dict(cooling=dict(cpu_cooler='custom-loop-360-reference',
                radiator_model='self-check-radiator',radiator_fan_layout='none',case_fans=[])),
                'eco',dict(cpu=dict(position=(0.,0.,0.),normal=(0.,0.,1.),up=(0.,1.,0.)),case_dimensions=(800.,900.,900.)))
            assert meshes and not metadata['rejected']
            assert any(part.get('model_id')=='self-check-radiator' for part in metadata['parts'])
            for kind in getters:fixture_store.remove('self-check-'+kind)
            assert fixture_store.memory_status()['selected_records']==0
            assert not any(name in sys.modules for name in ('cpu_catalog','cooling_expansion045','liquid_radiator_expansion045'))
            report['checks'].append('optional-cooling-pack-install-render-remove-no-graphics')
            # A synthetic loop reference exercises bundled generators without
            # importing any author catalogs or inferring installed hardware.
            from liquid_pack_schema046 import selector_for
            from liquid_component_runtime046 import get_component as get_loop
            from liquid_geometry046 import build_component
            identity='self-check-loop-block';url='https://example.test/isolated-reference'
            reference=dict(id=identity,label='Isolated synthetic CPU block',brand='Synthetic fixture',series='Self-check',
                part_kind='cpu_block',form='cpu_block',dimensions_mm=dict(width=None,height=None,depth=None),
                reference_envelope_mm=dict(width=80,height=28,depth=80),dimensions_verified=False,
                axis_verified=dict(width=False,height=False,depth=False),sources=[url],notes='Not a retail product.',
                ports_count=2,ports_geometry_complete=True,geometry_family='cpu_armored_square',geometry_features=[],
                supported_sockets=[],socket_support_verified=False,ports=[dict(id='port'+str(i+1),face='top',
                    position_normalized=[x,.5,0],role='connection',thread='G1/4',thread_gender='female',
                    position_verified=False,role_verified=False,source=url) for i,x in enumerate((-.18,.18))])
            row=dict(id=identity,label=reference['label'],vendor=reference['brand'],series=reference['series'],
                aliases=[identity],sources=[url],reference=reference,selector=selector_for(reference))
            source=output.parent/(identity+'.dspack')
            source.write_bytes(hardware_packs.make_pack(identity,reference['label'],[row],kind='loop'))
            fixture_store.install(source)
            actual=get_loop('cpu_block',identity);meshes,part=build_component(actual,'eco')
            assert meshes and len(part['ports'])==2 and not part['telemetry_bound']
            artwork=accessory_art('cpu_block',identity,'notebook_line')
            assert artwork and QSvgRenderer(QByteArray(artwork['svg'].encode('utf8'))).isValid()
            assert not artwork['rotors']
            fixture_store.remove(identity);clear_cache()
            assert get_loop('cpu_block',identity)=={} and cache_info()['entries']==0
            assert not any(name in sys.modules for name in ('liquid_block_pump_expansion046','liquid_fitting_tube_expansion046'))
            report['checks'].append('optional-loop-pack-mesh-svg-remove-no-graphics')
            # Read the actual shipped data pack, not an author catalogue or a
            # fabricated GPU fixture. Frozen bundles retain it in source/.
            source_root=Path(sys.executable).resolve().parent/'source' if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
            source=source_root/'model-packs/v047/DesktopStats-gpu-block-collection-047-1.0.0.dspack'
            assert source.is_file(), 'Missing bundled optional GPU block collection'
            fixture_store.install(source)
            gpu_rows=fixture_store.choices('loop')
            assert len(gpu_rows)==12 and len({row['id'] for row in gpu_rows})==12
            assert all(row['selector']['part_kind']=='gpu_block' for row in gpu_rows)
            identity='alphacool-core-rtx5090-rog-astral'
            actual=get_loop('gpu_block',identity)
            assert actual['id']==identity and actual['assembly_stage']=='standalone_reference_only'
            meshes,part=build_component(actual,'eco')
            assert meshes and not any(mesh.rotor for mesh in meshes)
            assert part['kind']=='gpu_block' and not part['telemetry_bound']
            assert not part['rotors_present'] and not part['pump_present']
            assert not part['attached_to_gpu'] and not part['routes_supported']
            assert not any(actual[key] for key in ('live_temperature_available','live_flow_available','live_rpm_available'))
            artwork=accessory_art('gpu_block',identity,'notebook_line')
            assert artwork and QSvgRenderer(QByteArray(artwork['svg'].encode('utf8'))).isValid()
            assert not artwork['rotors']
            from liquid_gpu_schema047 import compatibility
            generic=compatibility(actual,card_label='NVIDIA GeForce RTX 5090')
            assert generic['state']=='unlisted' and not generic['assembly_supported']
            assert not generic['installed_hardware_inferred']
            precise=compatibility(actual,product_code='90YV0LW1-M0NA00')
            assert precise['state']=='manufacturer_listed' and not precise['assembly_supported']
            fixture_store.remove('gpu-block-collection-047');clear_cache()
            status=fixture_store.memory_status()
            assert not fixture_store.choices('loop') and get_loop('gpu_block',identity)=={}
            assert status['packs']==0 and status['selected_records']==0 and cache_info()['entries']==0
            assert 'liquid_gpu_blocks047' not in sys.modules, 'Runtime imported the GPU author catalogue'
            report['gpu_block_pack_check']=dict(models=len(gpu_rows),model_id=identity,
                triangle_count=part['triangle_count'],svg_bytes=len(artwork['svg'].encode('utf8')),
                rotors=0,telemetry_bound=False,assembly_supported=precise['assembly_supported'],
                generic_chip_state=generic['state'],removed_packs=status['packs'],
                selected_records=status['selected_records'],artwork_entries=cache_info()['entries'],
                author_catalog_loaded=False)
            report['checks'].append('optional-gpu-block-pack-mesh-svg-remove-no-graphics')
        finally:
            hardware_packs._store=previous_store
            clear_cache()
        QCoreApplication.processEvents()
    finally:
        for item in [*objects, *components, engine]:
            item.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    report["qml_warnings"] = warnings
    assert not warnings, "; ".join(warnings)
