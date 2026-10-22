"""Collect only the LGPL Qt Quick modules used by this native application."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [
    (source, destination)
    for source, destination in binaries
    if "/plugins/qmltooling/" not in source.replace("\\", "/").lower()
]
qml_root = Path(pyside6_library_info.location["QmlImportsPath"])
destination = Path(pyside6_library_info.qt_rel_dir) / "qml"
allowed = {
    "QtQml",
    "QtQml/Models",
    "QtQml/WorkerScript",
    "QtCore",
    "QtQuick",
    "QtQuick/Window",
    "QtQuick/Layouts",
    "QtQuick/Effects",
    "QtQuick/Templates",
    "QtQuick/Controls",
    "QtQuick/Controls/impl",
    "QtQuick/Controls/Basic",
    "QtQuick/Controls/Basic/impl",
}
for relative in sorted(allowed):
    qmldir = qml_root / relative / "qmldir"
    if not qmldir.exists():
        continue
    plugin_binaries, plugin_data = pyside6_library_info._process_qml_plugin(qmldir)
    for file in plugin_binaries:
        binaries.append((str(file), str(destination / file.relative_to(qml_root).parent)))
    for file in plugin_data:
        dest = file.relative_to(qml_root) if file.is_dir() else file.relative_to(qml_root).parent
        datas.append((str(file), str(destination / dest)))
