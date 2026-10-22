"""Compile the original collector without changing PowerShell execution policy."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.fetch_sensor_dependencies import checked, manifest  # noqa: E402


def digest(path):
    return hashlib.sha256(checked(path).read_bytes()).hexdigest()


def build(*, root=ROOT, self_test=False):
    root = checked(root)
    vendor, dependencies = manifest(root)
    collector = checked(root / "collector")
    inputs = ["Program.cs", "build.ps1", "DesktopStats.Collector.exe.config"]
    for name in inputs:
        checked(collector / name)
    for row in dependencies["files"] + dependencies["licenses"]:
        if digest(vendor / row["name"]) != row["sha256"]:
            raise ValueError("Dependency integrity failed: " + row["name"])
    runtime = collector / "runtime"
    allowed = {row["name"] for row in dependencies["files"] + dependencies["licenses"]} | {
        "library-manifest.json", "THIRD-PARTY-NOTICES.md", "DesktopStats.Collector.exe.config",
        "DesktopStats.Collector.exe", "build-manifest.json",
    }
    previous = {}
    if runtime.exists():
        checked(runtime)
        existing = list(runtime.iterdir())
        if existing:
            previous = json.loads(checked(runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
            rows = {row["name"]: row for row in previous.get("files", [])}
            if {path.name for path in existing} != allowed or set(rows) != allowed - {"build-manifest.json"}:
                raise ValueError("Runtime contains unowned files; inspect it before building")
            for name, row in rows.items():
                if digest(runtime / name) != row["sha256"]:
                    raise ValueError("Existing runtime was modified: " + name)
    compiler = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        raise FileNotFoundError("Existing Windows .NET Framework x64 compiler required; nothing will be installed")
    scratch = root / "qa-private" / "collector-builds"
    scratch.mkdir(parents=True, exist_ok=True)
    checked(scratch)
    with tempfile.TemporaryDirectory(prefix="build-", dir=scratch) as temporary:
        stage = checked(temporary)
        if not stage.resolve().is_relative_to(scratch.resolve()):
            raise ValueError("Compiler staging escaped the project")
        for row in dependencies["files"] + dependencies["licenses"]:
            shutil.copy2(vendor / row["name"], stage / row["name"])
            if digest(stage / row["name"]) != row["sha256"]:
                raise ValueError("Dependency changed during staging: " + row["name"])
        shutil.copy2(vendor / "manifest.json", stage / "library-manifest.json")
        shutil.copy2(vendor / "NOTICE.md", stage / "THIRD-PARTY-NOTICES.md")
        shutil.copy2(collector / inputs[-1], stage / inputs[-1])
        target = stage / "DesktopStats.Collector.exe"
        subprocess.run(
            [str(compiler), "/nologo", "/target:exe", "/platform:x64", "/optimize+", "/checked+", "/utf8output",
             "/out:" + str(target), "/reference:" + str(stage / "LibreHardwareMonitorLib.dll"),
             "/reference:System.Web.Extensions.dll", str(collector / "Program.cs")],
            cwd=stage, check=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if self_test:
            subprocess.run([str(target), "--self-test"], cwd=stage, check=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = dict(
            schema=1, provider="LibreHardwareMonitor", provider_version="0.9.6",
            upstream_commit=dependencies["source_commit"], target=".NETFramework,Version=v4.7.2",
            architecture="x64", builder=dict(name="tools/build_collector.py", sha256=digest(root / "tools/build_collector.py")),
            sources=[dict(name=name, sha256=digest(collector / name)) for name in inputs],
            files=[dict(name=path.name, bytes=path.stat().st_size, sha256=digest(path))
                   for path in sorted(stage.iterdir())],
        )
        (stage / "build-manifest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Compilation/self-test finish before publishing any runtime. Refuse a
        # user modification detected since the initial ownership check.
        if runtime.exists() and list(runtime.iterdir()):
            current = json.loads(checked(runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
            if current != previous or any(digest(runtime / row["name"]) != row["sha256"]
                                          for row in previous["files"]):
                raise ValueError("Runtime changed during compilation; nothing replaced")
        runtime.mkdir(exist_ok=True)
        checked(runtime)
        for path in sorted(stage.iterdir()):
            destination = runtime / path.name
            if previous:
                checked(destination)
                os.replace(path, destination)
            else:
                with destination.open("xb") as stream:
                    stream.write(path.read_bytes())
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run only the original helper's synthetic protocol test")
    args = parser.parse_args()
    build(self_test=args.self_test)
    print("Collector built locally. No hardware probe, driver installation or policy change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
