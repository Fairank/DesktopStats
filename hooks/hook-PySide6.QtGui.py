"""Keep native image/window plugins; do not bundle optional PDF or keyboard engines."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
hiddenimports = [name for name in hiddenimports if name == "PySide6.QtCore"]
allowed = {"qwindows.dll", "qoffscreen.dll", "qico.dll", "qjpeg.dll", "qsvg.dll", "qsvgicon.dll"}
binaries = [
    (source, destination)
    for source, destination in binaries
    if "/plugins/" not in source.replace("\\", "/").lower() or Path(source).name.lower() in allowed
]
