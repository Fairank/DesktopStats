"""Export the reviewed current source snapshot, never a working-directory dump.

No application, collector, IPC client or native API is started. The reviewed
directory inventory below is intentional: adding a file to assets/ does not
silently make it public. Update that inventory only after reviewing new assets.
"""

import argparse
import ast
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build as BUILD  # noqa: E402 - direct tools/ CLI needs the project import root

_NATIVE = """
ActionButton.qml Appearance.qml Check.qml Choice.qml ContentCanvas.qml
ContentLayoutEditor.qml DesktopWidget.qml Details.qml FormField.qml
FrostedBackdrop.qml Gallery.qml GlassControl.qml GlassControls.qml GlassSurface.qml
HistoryPage.qml TrendChart.qml ScenarioPicker.qml DiagnosticsPanel.qml ScenePreview.qml
Icon.qml IconButton.qml IconData.js InspectorSection.qml MaterialSample.qml MetricIcon.qml
OptionTabs.qml Preview.qml SamplingControl.qml SensorBrowser.qml SettingRow.qml
Settings.qml SettingsGroup.qml SkinPicker.qml Theme.qml Toggle.qml TopBar.qml
TopBarDetails.qml TopBarItemInspector.qml TopBarMetricContent.qml TopBarGroupContent.qml
TopBarPreviewStrip.qml TopBarSettings.qml ValueSlider.qml WidgetEditor.qml
WidgetInspector.qml WidgetPreview.qml WindowChrome.qml
""".split()
_LUCIDE = """
activity arrow-down-to-line arrow-down-up arrow-up-from-line audio-lines battery
check chevron-down chevron-right chevron-up clock copy cpu fan gauge gpu
hard-drive-download hard-drive-upload hard-drive layout-grid memory-stick plus
redo search sliders-horizontal thermometer trash undo x zap
""".split()
_QT_LICENSES = {
    "pyside-pyside-setup": """
Apache-2.0 BSD-3-Clause GFDL-1.3-no-invariants-only GPL-2.0-only GPL-3.0-only
LGPL-3.0-only LicenseRef-Qt-Commercial Qt-GPL-exception-1.0
""".split(),
    "qt-qtbase": """
AFL-2.1 Apache-2.0 Bitstream-Vera blessing BSD-2-Clause BSD-3-Clause BSD-4-Clause
BSL-1.0 CC0-1.0 FTL GFDL-1.3-no-invariants-only GPL-2.0-only GPL-2.0-or-later
GPL-3.0-only HPND IJG Imlib2 IPL-1.0 LGPL-2.1-or-later LGPL-3.0-only libpng-2.0
Libpng LicenseRef-BSD-3-Clause-with-PCRE2-Binary-Like-Packages-Exception
LicenseRef-ICC-License LicenseRef-Lcs-Telegraphics LicenseRef-Qt-Commercial
LicenseRef-SHA1-Public-Domain Linux-syscall-note MIT-Khronos-old MIT-open-group MIT
MPL-2.0 Qt-GPL-exception-1.0 SPL-1.0 Unicode-3.0 X11 Xerox Zlib
""".split(),
    "qt-qtdeclarative": """
Apache-2.0 BSD-2-Clause BSD-3-Clause CC-BY-3.0 CC0-1.0
GFDL-1.3-no-invariants-only GPL-2.0-only GPL-3.0-only LGPL-3.0-only
LicenseRef-Qt-Commercial MIT OFL-1.1 Qt-GPL-exception-1.0 Unlicense
""".split(),
}
REVIEWED_FILES = frozenset(
    ["native/" + name for name in _NATIVE]
    + [
        f"assets/icon-{size}.{extension}"
        for size in (16, 20, 24, 32, 40, 48, 56, 64, 96, 128, 256, 512, 1024)
        for extension in ("png", "svg")
    ]
    + [
        "assets/" + name
        for name in (
            "icon-manifest.json",
            "ICON-NOTES.md",
            "icon.ico",
            "icon.png",
            "icon.svg",
            "niangao-source.svg",
            "lucide/LICENSE",
            "lucide/provenance.json",
            "showcase/history-light.png",
            "showcase/history-dark.png",
            "showcase/scene-preview.png",
            "showcase/source-diagnostics.png",
            "showcase/widgets-editor.png",
            "showcase/top-bar-styles.png",
            "showcase/top-bar-groups.png",
            "showcase/cpu-details.png",
            "showcase/top-bar-actions.png",
            "showcase/group-confirm.png",
        )
    ]
    + [f"assets/lucide/icons/{name}.svg" for name in _LUCIDE]
    + [
        f"licenses/qt-6.10.2/{repository}/{name}.txt"
        for repository, names in _QT_LICENSES.items()
        for name in names
    ]
    + [
        "licenses/qt-6.10.2/SOURCES.txt",
        "licenses/legacy/DesktopStats-through-0.18-MIT.txt",
        "hooks/hook-PySide6.QtGui.py",
        "hooks/hook-PySide6.QtQml.py",
        "docs/USER_GUIDE.md",
    ]
)
EXTRA_FILES = frozenset(
    {
        ".gitignore",
        "NOTICE",
        "LICENSING.md",
        "CHANGELOG.md",
        "collector/README.md",
        "tools/export_source.py",
        "tests/test_source_export.py",
        "build_modular.py",
        "settings_server.py",
    }
)
DEPENDENCY_ROOT = "third_party/librehardwaremonitor/0.9.6"
DEPENDENCY_MANIFEST_SHA256 = "7fa0fdefcf4f23a555521bc228a6e3cd940c0b67e7c692d0702cc96e600682f4"
DEPENDENCY_DLLS = frozenset(
    {
        "LibreHardwareMonitorLib.dll",
        "DiskInfoToolkit.dll",
        "BlackSharp.Core.dll",
        "RAMSPDToolkit-NDD.dll",
        "HidSharp.dll",
        "System.Memory.dll",
        "System.Buffers.dll",
        "System.Numerics.Vectors.dll",
        "System.Runtime.CompilerServices.Unsafe.dll",
    }
)
DEPENDENCY_LICENSES = frozenset(
    {
        "LICENSE-HidSharp-Apache-2.0.txt",
        "LICENSE-Microsoft-MIT.txt",
        "LICENSE-MPL-2.0.txt",
        "LICENSE-PawnIO-Modules-LGPL-2.1.txt",
    }
)
_PRIVATE_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "qa-private",
        "dist",
        "build",
        "__pycache__",
        "root-qml-isolated-profile",
        ".qa-profile",
        ".test-profile",
    }
)
_PRIVATE_SUFFIXES = {".pfx", ".p12", ".pem", ".key", ".token", ".pid", ".log", ".dmp"}
_BINARY_SUFFIXES = frozenset(
    {
        ".exe",
        ".dll",
        ".sys",
        ".so",
        ".pyd",
        ".msi",
        ".msp",
        ".msix",
        ".appx",
        ".dylib",
        ".ocx",
        ".drv",
        ".com",
        ".scr",
        ".cpl",
        ".pyc",
        ".pyo",
        ".bin",
        ".o",
        ".obj",
        ".a",
        ".lib",
        ".class",
        ".jar",
        ".wasm",
        ".whl",
        ".nupkg",
    }
)
_TEXT_SUFFIXES = {
    ".py",
    ".qml",
    ".js",
    ".json",
    ".md",
    ".txt",
    ".svg",
    ".toml",
    ".cs",
    ".ps1",
    ".cmd",
    ".config",
    "",
}
_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
_HOME = re.compile(r"(?i)(?:[A-Z]:[/\\]+Users[/\\]+|/home/|/Users/)([\w.@-]+)(?=[/\\])")
_FIXTURE_USERS = {
    "user",
    "username",
    "yourname",
    "your-name",
    "name",
    "someone",
    "me",
    "alice",
    "bob",
    "example",
    "public",
    "default",
    "test",
    "testuser",
    "fixture",
}


class ExportError(ValueError):
    """The requested export is not a reviewed, stable source snapshot."""


def _binary_path(name):
    leaf = PurePosixPath(name).name.casefold()
    return (
        PurePosixPath(leaf).suffix in _BINARY_SUFFIXES
        or re.search(r"\.so(?:\.\d+)+$", leaf) is not None
    )


def _binary_magic(data):
    # Fail closed if a known executable/object/container was renamed to a
    # permitted source or image suffix. PNG/SVG/ICO payloads remain unaffected.
    return data.startswith(
        (
            b"MZ",
            b"\x7fELF",
            b"\x00asm",
            b"\xfe\xed\xfa\xce",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xcf\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"!<arch>\n",
            b"PK\x03\x04",
            b"\xd0\xcf\x11\xe0",
        )
    )


def _relative_name(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ExportError("Invalid source path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
        raise ExportError("Source path escapes the project")
    if any(part.casefold() in _PRIVATE_PARTS for part in path.parts):
        raise ExportError("Private directory in public allowlist: " + name)
    leaf = path.name.casefold()
    if (
        path.suffix.casefold() in _PRIVATE_SUFFIXES
        or leaf.startswith((".env", "preferences"))
        or leaf in {"positions.json", "latest.json", "state.txt", "native-migration.json"}
    ):
        raise ExportError("Private file in public allowlist: " + name)
    return path


def _not_reparse(path):
    information = path.lstat()
    if stat.S_ISLNK(information.st_mode) or getattr(information, "st_file_attributes", 0) & 0x400:
        raise ExportError("Symbolic links and reparse points are not exportable")
    return information


def _checked_file(root, name):
    relative = _relative_name(name)
    current = root
    _not_reparse(current)
    for part in relative.parts:
        current = current / part
        _not_reparse(current)
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise ExportError("Source file escaped the project or is not a regular file: " + name)
    return current


def _read(root, name):
    path = _checked_file(root, name)
    data = path.read_bytes()
    _checked_file(root, name)
    return data


def _scan(name, data):
    if _binary_path(name) or _binary_magic(data):
        raise ExportError(
            "Executable/object binary is not permitted in this source export: " + name
        )
    if PurePosixPath(name).suffix.casefold() not in _TEXT_SUFFIXES:
        return
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ExportError("Expected UTF-8 source text: " + name) from error
    for number, line in enumerate(content.splitlines(), 1):
        if _TOKEN.search(line) or _PRIVATE_KEY.search(line):
            # Never echo the possible secret into a log or exception.
            raise ExportError(f"Possible credential literal in {name}:{number}")
        for match in _HOME.finditer(line):
            user = match.group(1).casefold()
            if user not in _FIXTURE_USERS and not user.startswith(("test-", "example-", "<", "{")):
                raise ExportError(f"Personal home-directory literal in {name}:{number}")


def _version(root):
    tree = ast.parse(_read(root, "product_version.py").decode("utf-8-sig"))
    values = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
    ]
    if (
        len(values) != 1
        or not isinstance(values[0], str)
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", values[0])
    ):
        raise ExportError("Invalid product version")
    return values[0]


def _build_sources(root):
    tree = ast.parse(_read(root, "tools/build.py").decode("utf-8-sig"))
    values = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SOURCES" for target in node.targets)
    ]
    if (
        len(values) != 1
        or not isinstance(values[0], (tuple, list))
        or not all(isinstance(name, str) for name in values[0])
    ):
        raise ExportError("Packaging source allowlist is not an explicit sequence")
    return tuple(values[0])


def collect_paths(root, contract=BUILD):
    """Resolve explicit paths and verify the actual packaging collector contract."""
    root = Path(root).absolute()
    if root != Path(contract.ROOT).absolute():
        raise ExportError("Packaging contract belongs to a different project")
    sources = _build_sources(root)
    if sources != tuple(contract.SOURCES):
        raise ExportError("Packaging source contract changed; start a fresh exporter process")
    paths = set(sources) | REVIEWED_FILES | EXTRA_FILES
    tests = root / "tests"
    _not_reparse(tests)
    # The project's complete direct Python test suite is explicitly authorized.
    paths.update("tests/" + item.name for item in tests.iterdir() if item.suffix == ".py")
    for name in paths:
        _checked_file(root, name)

    manifest_name = DEPENDENCY_ROOT + "/manifest.json"
    manifest_data = _read(root, manifest_name)
    if hashlib.sha256(manifest_data).hexdigest() != DEPENDENCY_MANIFEST_SHA256:
        raise ExportError("The reviewed third-party dependency manifest changed")
    manifest = json.loads(manifest_data)
    files, licenses = manifest.get("files", []), manifest.get("licenses", [])
    if (
        manifest.get("source_commit") != "3d331e3370efb858411f19511373eff65a218701"
        or len(files) != len(DEPENDENCY_DLLS)
        or {row["name"] for row in files} != DEPENDENCY_DLLS
        or len(licenses) != len(DEPENDENCY_LICENSES)
        or {row["name"] for row in licenses} != DEPENDENCY_LICENSES
    ):
        raise ExportError("Unexpected third-party dependency file set")
    for row in files + licenses:
        name = DEPENDENCY_ROOT + "/" + row["name"]
        data = _read(root, name)
        if (
            hashlib.sha256(data).hexdigest() != row["sha256"]
            or "bytes" in row
            and len(data) != row["bytes"]
        ):
            raise ExportError("Third-party dependency integrity failed: " + name)
        paths.add(name)
    paths.update({manifest_name, DEPENDENCY_ROOT + "/NOTICE.md"})

    # Validate all manifests before invoking the trusted packaging helper, so
    # its read_bytes never follows an unreviewed symlink or ../ manifest path.
    runtime = "collector/runtime/"
    build_data = _read(root, runtime + "build-manifest.json")
    build_manifest = json.loads(build_data)
    if not isinstance(build_manifest, dict):
        raise ExportError("Collector build manifest must be an object")
    runtime_rows = build_manifest.get("files", [])
    source_rows = build_manifest.get("sources", [])
    if not all(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
        for rows in (runtime_rows, source_rows)
    ):
        raise ExportError("Malformed collector manifest rows")
    for row in runtime_rows:
        if not isinstance(row.get("name"), str) or Path(row["name"]).name != row["name"]:
            raise ExportError("Invalid collector runtime manifest path")
        _checked_file(root, runtime + row["name"])
    expected_sources = {"Program.cs", "build.ps1", "DesktopStats.Collector.exe.config"}
    if len(source_rows) != 3 or {row["name"] for row in source_rows} != expected_sources:
        raise ExportError("Unexpected collector source manifest")
    for row in source_rows:
        _checked_file(root, "collector/" + row["name"])
    embedded = _read(root, runtime + "library-manifest.json")
    if embedded != manifest_data:
        raise ExportError("Collector and vendored dependency manifests differ")
    for path in contract.collector_files():
        relative = Path(path).relative_to(root).as_posix()
        _checked_file(root, relative)
        # Validation is mandatory, but no collector build product is published.
        # Canonical license texts and the pinned vendor metadata are below
        # third_party/. The runtime build manifest refers to a local old EXE.
    if _read(root, runtime + "build-manifest.json") != build_data:
        raise ExportError("Collector manifest changed during validation")
    paths.update({DEPENDENCY_ROOT + "/NOTICE.md"})
    folded = [name.casefold() for name in paths]
    if len(set(folded)) != len(folded):
        raise ExportError("Case-colliding source paths")
    return sorted(
        name
        for name in paths
        if not _binary_path(name) and not name.casefold().startswith("collector/runtime/")
    )


def _output_path(root, output):
    path = Path(output)
    if not path.is_absolute():
        path = root / path
    path = path.absolute()
    if (
        not path.is_relative_to(root)
        or ".." in path.parts
        or path.suffix.lower() != ".zip"
        or path == root
    ):
        raise ExportError("Output must be a new ZIP within the project workspace")
    current = root
    _not_reparse(root)
    for part in path.relative_to(root).parts[:-1]:
        current = current / part
        if current.exists() or current.is_symlink():
            _not_reparse(current)
            if not current.is_dir():
                raise ExportError("Output parent is not a directory")
    if path.exists() or path.is_symlink():
        raise FileExistsError("Source archives are immutable; choose a new output path")
    return path


def export_source(output=None, *, root=ROOT, contract=BUILD):
    root = Path(root).absolute()
    version = _version(root)
    output = _output_path(root, output or f"dist/DesktopStats-{version}-source.zip")
    payloads = {}
    paths = collect_paths(root, contract)
    for name in paths:
        data = _read(root, name)
        _scan(name, data)
        payloads[name] = data
    # Integrity checks apply to the captured snapshot, not just an earlier
    # version of a DLL or manifest that may have changed before read_bytes.
    if collect_paths(root, contract) != paths:
        raise ExportError("Source allowlist changed during snapshot collection")
    prefix = f"DesktopStats-{version}-source/"
    rows = [
        {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in payloads.items()
    ]
    manifest = {
        "format": 1,
        "kind": "reviewed-current-source",
        "version": version,
        "archive_root": prefix,
        "binaries_included": False,
        "binary_policy": "No executable/object/install binaries; reviewed image assets retained.",
        "dependency_preparation_required": True,
        "files": rows,
        "manifest_note": "This manifest describes every other archive member; no self-hash.",
    }
    manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Repeat validation after mkdir, then use exclusive creation, never overwrite.
    output = _output_path(root, output)
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for name, data in [*payloads.items(), ("SOURCE_MANIFEST.json", manifest_data)]:
                    info = zipfile.ZipInfo(prefix + name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
            # Changes during export invalidate the artifact instead of silently
            # mixing source generations. Recheck path identity and complete bytes.
            for name, data in payloads.items():
                if _read(root, name) != data:
                    raise ExportError("Source changed during export: " + name)
        return {
            "ok": True,
            "version": version,
            "file_count": len(rows),
            "archive": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New source ZIP inside this project")
    args = parser.parse_args(argv)
    try:
        result = export_source(args.output)
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Source export refused: {error}\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
