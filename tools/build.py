"""Build a native, replaceable-library Windows distribution with vetted source."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from product_version import VERSION

SOURCES = (
    ".gitignore",
    "appearance_preview.py",
    "app.py",
    "activity_sensors.py",
    "appbar_platform.py",
    "battery_sensor.py",
    "build_modular.py",
    "card_layout.py",
    "compact_labels.py",
    "configuration_scopes.py",
    "cooling_sensor.py",
    "desktop_placement.py",
    "energy_sensor.py",
    "diagnostic_actions.py",
    "history_store.py",
    "external_engine.py",
    "external_sensor.py",
    "installer.py",
    "layout_assist.py",
    "legacy_migration.py",
    "localization.py",
    "locales.txt",
    "metrics.py",
    "material_policy.py",
    "magnet_layout.py",
    "native_card.py",
    "native_controller.py",
    "native_ipc.py",
    "native_glass.py",
    "native_layout.py",
    "native_platform.py",
    "native_runtime.py",
    "native_selfcheck.py",
    "native_surface.py",
    "native_widget_material.py",
    "widget_material_geometry.py",
    "skin_styles.py",
    "presets.py",
    "responsive_layout.py",
    "settings_material_lifecycle.py",
    "settings_server.py",
    "settings_material_bridge.py",
    "settings_blur_material.py",
    "raster_blur_material.py",
    "modern_menu.py",
    "settings_acrylic_material.py",
    "settings_backdrop_host.py",
    "product_version.py",
    "sensors.py",
    "stats_config.py",
    "storage_sensor.py",
    "sensor_diagnostics.py",
    "top_bar_config.py",
    "top_bar_layout.py",
    "top_bar_profiles.py",
    "top_bar_feedback.py",
    "top_bar_runtime.py",
    "top_bar_backdrop_host.py",
    "widget_catalog.py",
    "workspace_tools.py",
    "workspace_scenarios.py",
    "requirements.txt",
    "requirements-build.txt",
    "requirements-artwork.txt",
    "pyproject.toml",
    "LICENSE",
    "NOTICE",
    "LICENSING.md",
    "CHANGELOG.md",
    "docs/USER_GUIDE.md",
    "THIRD_PARTY_NOTICES.md",
    "licenses/three-r150/LICENSE.txt",
    "licenses/three-r150/NOTICE.md",
    "licenses/three-r150/SOURCES.json",
    "third_party/threejs/r150/SimplexNoise.js",
    "third_party/threejs/r150/LightningStrike.js",
    "tools/three_simplex4d.py",
    "tools/generate_metric_motion.py",
    "README.md",
    "Install.cmd",
    "Uninstall.cmd",
    "tests/test_native.py",
    "tests/test_cpu_details.py",
    "tests/test_top_bar_effects.py",
    "tests/test_top_bar_action_ui.py",
    "tests/test_top_bar_cpu_effects_qml.py",
    "tests/test_top_bar_design_config.py",
    "tests/test_top_bar_design_ui.py",
    "tests/test_top_bar_design_content.py",
    "tests/test_top_bar_workflow.py",
    "tests/test_top_bar_history_identity.py",
    "tests/test_top_bar_details_design.py",
    "tests/test_metric_icon_effects.py",
    "tests/test_metric_state_feedback_qml.py",
    "tests/test_top_bar_effect_activity.py",
    "tests/test_top_bar_drag_feedback.py",
    "tests/test_product.py",
    "tests/test_extensions.py",
    "tests/test_energy_sensor.py",
    "tests/test_power_integration.py",
    "tests/test_runtime_preview.py",
    "tests/test_appearance_preview.py",
    "tests/test_appearance_runtime.py",
    "tests/test_customization.py",
    "tests/test_material_policy.py",
    "tests/test_card_layout.py",
    "tests/test_responsive_layout.py",
    "tests/test_layout_customization.py",
    "tests/test_layout_audit.py",
    "tests/test_layout_assist.py",
    "tests/test_draft_history.py",
    "tests/test_editor_actions.py",
    "tests/test_performance_contracts.py",
    "tests/test_inventory_display.py",
    "tests/test_alpha_material.py",
    "tests/test_selfcheck.py",
    "tests/test_native_glass.py",
    "tests/test_magnet_layout.py",
    "tests/test_magnet_runtime.py",
    "tests/test_sampling.py",
    "tests/test_sampling_delivery.py",
    "tests/test_sensor_source_isolation.py",
    "tests/test_hwinfo_cache.py",
    "tests/test_dependency_setup.py",
    "tests/test_collector_build.py",
    "tests/test_activity_failures.py",
    "tests/test_source_export.py",
    "tests/test_redesign_contracts.py",
    "tests/test_material_styles.py",
    "tests/test_glass_preferences.py",
    "tests/test_cooling_sensor.py",
    "tests/test_external_config.py",
    "tests/test_external_sensor.py",
    "tests/test_external_engine.py",
    "tests/test_provider_recovery.py",
    "tests/test_storage_sensor.py",
    "tests/test_storage_audit.py",
    "tests/test_stale_readings.py",
    "tests/test_installer_audit.py",
    "tests/test_top_bar_config.py",
    "tests/test_top_bar_upgrade.py",
    "tests/test_reading_presentation.py",
    "tests/test_appbar_platform.py",
    "tests/test_top_bar_layout.py",
    "tests/test_top_bar_runtime.py",
    "tests/test_top_bar_shutdown.py",
    "tests/test_top_bar_detail_presentation.py",
    "tests/test_top_bar_backdrop_host.py",
    "tests/test_top_bar_editor_preview.py",
    "tests/test_top_bar_monitor_selection.py",
    "tests/test_lucide_icons.py",
    "tests/test_main_window_palette.py",
    "tests/test_top_bar_transactions.py",
    "tests/test_top_bar_display_config.py",
    "tests/test_top_bar_presentation.py",
    "tests/test_top_bar_profiles.py",
    "tests/test_top_bar_groups.py",
    "tests/test_top_bar_groups_qml.py",
    "tests/test_top_bar_module_qml.py",
    "tests/test_material_diagnostics.py",
    "tests/test_settings_material_lifecycle.py",
    "tests/test_settings_material_bridge.py",
    "tests/test_settings_material_integration.py",
    "tests/test_frame_settlement.py",
    "tests/test_settings_blur_material.py",
    "tests/test_raster_blur_material.py",
    "tests/test_modern_menu.py",
    "tests/test_settings_acrylic_material.py",
    "tests/test_settings_material_frame_source.py",
    "tests/test_settings_hidden_preparation.py",
    "tests/test_theme_material_contract.py",
    "tests/test_configuration_scopes.py",
    "tests/test_history_store.py",
    "tests/test_history_qml.py",
    "tests/test_history_options_qml.py",
    "tests/test_workspace_tools.py",
    "tests/test_workspace_routing.py",
    "tests/test_workspace_ui.py",
    "tests/test_workspace_recovery.py",
    "tests/test_workspace_ui_recovery.py",
    "tests/test_history_recovery.py",
    "tests/test_history_sampling.py",
    "tests/test_diagnostic_export.py",
    "tests/test_widget_blur.py",
    "tests/test_widget_material_geometry.py",
    "tests/test_widget_material_runtime.py",
    "tests/test_runtime_status.py",
    "tests/test_collector_contract.py",
    "collector/Program.cs",
    "collector/README.md",
    "collector/build.ps1",
    "collector/DesktopStats.Collector.exe.config",
    "tools/build.py",
    "tools/generate_icons.py",
    "tools/verify_native.py",
    "tools/verify_upgrade.py",
    "tools/verify_scroll.py",
    "tools/verify_customization.py",
    "tools/fetch_qt_licenses.py",
    "tools/test_isolated.py",
    "tools/export_source.py",
    "tools/fetch_sensor_dependencies.py",
    "tools/build_collector.py",
)


def collector_files():
    """Validate the exact runtime/source allowlist before packaging any helper."""
    runtime = ROOT / "collector/runtime"
    manifest = json.loads((runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
    if (manifest.get("provider") != "LibreHardwareMonitor"
            or manifest.get("provider_version") != "0.9.6"
            or manifest.get("upstream_commit") != "3d331e3370efb858411f19511373eff65a218701"):
        raise ValueError("Unexpected collector provider")
    allowed = {
        "BlackSharp.Core.dll", "DiskInfoToolkit.dll", "HidSharp.dll", "LibreHardwareMonitorLib.dll",
        "RAMSPDToolkit-NDD.dll", "System.Buffers.dll", "System.Memory.dll",
        "System.Numerics.Vectors.dll", "System.Runtime.CompilerServices.Unsafe.dll",
        "DesktopStats.Collector.exe", "DesktopStats.Collector.exe.config", "library-manifest.json",
        "LICENSE-HidSharp-Apache-2.0.txt", "LICENSE-Microsoft-MIT.txt", "LICENSE-MPL-2.0.txt",
        "LICENSE-PawnIO-Modules-LGPL-2.1.txt", "THIRD-PARTY-NOTICES.md",
    }
    rows = manifest.get("files", [])
    if len(rows) != len(allowed) or {row["name"] for row in rows} != allowed:
        raise ValueError("Collector runtime does not match the public file allowlist")
    for row in rows:
        file = runtime / row["name"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Collector runtime integrity failed: " + row["name"])
    for row in manifest["sources"]:
        if row["name"] not in ("Program.cs", "build.ps1", "DesktopStats.Collector.exe.config"):
            raise ValueError("Unexpected collector source")
        if hashlib.sha256((ROOT / "collector" / row["name"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Rebuild collector after source changes")
    return [runtime / name for name in sorted(allowed | {"build-manifest.json"})]


def main():
    archive = ROOT / f"dist/DesktopStats-{VERSION}-Windows-x64.zip"
    if archive.exists():
        raise FileExistsError("Versioned release archives are immutable; choose a new candidate version")
    collector = collector_files()
    for target in (ROOT / "dist/native/DesktopStats", ROOT / "build/native"):
        if (
            not target.resolve().is_relative_to(ROOT.resolve())
            or target.resolve() == ROOT.resolve()
        ):
            raise RuntimeError("Build output escaped the project")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "DesktopStats",
        "--icon",
        str(ROOT / "assets/icon.ico"),
        "--additional-hooks-dir",
        str(ROOT / "hooks"),
        "--distpath",
        str(ROOT / "dist/native"),
        "--workpath",
        str(ROOT / "build/native"),
    ]
    for directory in ("native", "assets"):
        command += ["--add-data", str(ROOT / directory) + ";" + directory]
    command += ["--add-data", str(ROOT / "locales.txt") + ";."]
    for file in collector:
        command += ["--add-data", str(file) + ";collector"]
    for module in (
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PIL",
        "pystray",
        "lupa",
        "pytest",
    ):
        command += ["--exclude-module", module]
    # Dependency discovery must follow Windows' system DLLs rather than unrelated
    # tools on PATH (e.g. Poppler's versioned ICU under the same icuuc.dll name).
    environment = dict(os.environ)
    windows = Path(os.environ["WINDIR"])
    environment["PATH"] = os.pathsep.join(
        map(
            str, [Path(sys.executable).parent, Path(sys.base_prefix), windows / "System32", windows]
        )
    )
    subprocess.run(command + [str(ROOT / "app.py")], cwd=ROOT, check=True, env=environment)
    package = ROOT / "dist/native/DesktopStats"
    if (package / "_internal/icuuc.dll").exists():
        raise RuntimeError("Do not shadow Windows ICU with an unrelated bundled library")
    licenses = []
    for name in ("psutil", "PySide6-Essentials", "shiboken6", "PyInstaller"):
        dist = metadata.distribution(name)
        for file in dist.files or []:
            if "license" in str(file).lower() or file.name.lower() in (
                "copying",
                "copying.txt",
                "notice",
            ):
                path = Path(dist.locate_file(file))
                if path.is_file() and path.suffix.lower() in (".txt", ".rst", "", ".md"):
                    licenses.append(
                        f"\n\n===== {name} {dist.version} / {file.name} =====\n"
                        + path.read_text(encoding="utf-8", errors="replace")
                    )
    for file in sorted([
        *(ROOT / "licenses/qt-6.10.2").rglob("*.txt"),
        ROOT / "licenses/three-r150/LICENSE.txt",
    ]):
        licenses.append(
            "\n\n===== "
            + str(file.relative_to(ROOT / "licenses"))
            + " =====\n"
            + file.read_text(encoding="utf-8")
        )
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        licenses.append("\n\n===== Python =====\n" + python_license.read_text(encoding="utf-8"))
    (package / "THIRD_PARTY_LICENSES.txt").write_text(
        "Desktop Stats native Windows distribution\n"
        "Original application: PolyForm Noncommercial 1.0.0; see LICENSE, NOTICE and LICENSING.md.\n"
        "Third-party and prior MIT rights remain intact. Qt / PySide / Shiboken: LGPL v3 option.\n"
        "Qt libraries are dynamically loaded from _internal and may be replaced with compatible modified versions.\n"
        "Source/rebuild instructions are included in source/. Reverse engineering for debugging modifications to LGPL libraries is permitted.\n"
        "Unmodified upstream sources: https://download.qt.io/official_releases/qt/6.10/6.10.2/submodules/\n"
        "PySide/Shiboken source: https://github.com/pyside/pyside-setup/tree/v6.10.2\n"
        "Sensor collector libraries and complete notices: _internal/collector/THIRD-PARTY-NOTICES.md.\n"
        "MPL-2.0 / Apache-2.0 / MIT / embedded LGPL-2.1 libraries retain their own licenses.\n"
        "Immutable corresponding-source references and dependency provenance are included in source/third_party/librehardwaremonitor/0.9.6/.\n"
        + "".join(licenses),
        encoding="utf-8",
    )
    for name in ("Install.cmd", "Uninstall.cmd", "LICENSE", "NOTICE", "LICENSING.md",
                 "CHANGELOG.md", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, package / name)
    source = package / "source"
    for name in SOURCES:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for directory in ("native", "assets", "hooks", "licenses"):
        shutil.copytree(
            ROOT / directory,
            source / directory,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for file in collector:
        target = source / "collector/runtime" / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    dependencies = ROOT / "third_party/librehardwaremonitor/0.9.6"
    dependency_manifest = json.loads((dependencies / "manifest.json").read_text(encoding="utf-8"))
    names = [row["name"] for row in dependency_manifest["files"] + dependency_manifest["licenses"]]
    for name in [*names, "manifest.json", "NOTICE.md"]:
        if Path(name).name != name:
            raise ValueError("Invalid dependency filename")
        target = source / "third_party/librehardwaremonitor/0.9.6" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dependencies / name, target)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for file in sorted(package.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                output.write(file, "DesktopStats/" + file.relative_to(package).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / f"dist/SHA256SUMS-{VERSION}.txt").write_text(
        digest + "  " + archive.name + "\n", encoding="ascii"
    )
    print(archive)


if __name__ == "__main__":
    main()
