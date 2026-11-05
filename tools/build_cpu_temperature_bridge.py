"""Build the fixed read-only ASUS bridge; never elevate, install or probe hardware."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.fetch_sensor_dependencies import checked  # noqa: E402

EXECUTABLE = "AsusCpuTemperatureBridge.exe"
MANIFEST = "build-manifest.json"
SOURCE = "AsusCpuTemperatureBridge.cs"
ALLOWED = {EXECUTABLE, MANIFEST}


def digest(path):
    return hashlib.sha256(checked(path).read_bytes()).hexdigest()


def existing_runtime(runtime):
    if not runtime.exists():
        return None
    checked(runtime)
    entries = list(runtime.iterdir())
    if not entries:
        return None
    if {item.name for item in entries} != ALLOWED:
        raise ValueError("CPU bridge runtime contains unowned files")
    value = json.loads(checked(runtime / MANIFEST).read_text(encoding="utf-8"))
    rows = value.get("files", [])
    if (value.get("schema") != 1 or value.get("provider") != "ASUS COM CPU"
            or len(rows) != 1 or rows[0].get("name") != EXECUTABLE):
        raise ValueError("Invalid CPU bridge ownership manifest")
    row = rows[0]
    executable = checked(runtime / EXECUTABLE)
    if executable.stat().st_size != row.get("bytes") or digest(executable) != row.get("sha256"):
        raise ValueError("Existing CPU bridge runtime was modified")
    return value


def build(*, root=ROOT, self_test=False):
    root = checked(root)
    collector = checked(root / "collector")
    source = checked(collector / SOURCE)
    builder = checked(root / "tools" / "build_cpu_temperature_bridge.py")
    runtime = collector / "cpu-temperature-runtime"
    previous = existing_runtime(runtime)
    source_hash, builder_hash = digest(source), digest(builder)
    compiler = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        raise FileNotFoundError("Existing Windows .NET Framework x64 compiler required; nothing will be installed")
    scratch = root / "qa-private" / "cpu-temperature-bridge-builds"
    scratch.mkdir(parents=True, exist_ok=True)
    checked(scratch)
    with tempfile.TemporaryDirectory(prefix="build-", dir=scratch) as temporary:
        stage = checked(temporary)
        if not stage.resolve().is_relative_to(scratch.resolve()):
            raise ValueError("Bridge staging escaped the project")
        target = stage / EXECUTABLE
        compiled = subprocess.run(
            [str(compiler), "/nologo", "/target:exe", "/platform:x64", "/optimize+", "/checked+",
             "/utf8output", "/out:" + str(target), "/reference:System.Core.dll", str(source)],
            cwd=stage, check=False, timeout=60, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if compiled.returncode:
            print(compiled.stdout)
            compiled.check_returncode()
        if digest(source) != source_hash or digest(builder) != builder_hash:
            raise ValueError("CPU bridge inputs changed during compilation")
        if self_test:
            subprocess.run([str(target), "--self-test"], cwd=stage, check=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        value = dict(
            schema=1, provider="ASUS COM CPU", architecture="x64", target=".NETFramework,Version=v4.7.2",
            sensor_id=100859922, sensor_name="CPU", protocol_bytes=64, protocol_schema=1,
            builder=dict(name="tools/build_cpu_temperature_bridge.py", sha256=builder_hash),
            sources=[dict(name=SOURCE, sha256=source_hash)],
            files=[dict(name=EXECUTABLE, bytes=target.stat().st_size, sha256=digest(target))],
        )
        (stage / MANIFEST).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        if existing_runtime(runtime) != previous:
            raise ValueError("CPU bridge runtime changed during compilation; nothing replaced")
        runtime.mkdir(exist_ok=True)
        checked(runtime)
        for name in (EXECUTABLE, MANIFEST):
            destination = runtime / name
            if previous:
                checked(destination)
                os.replace(stage / name, destination)
            else:
                with destination.open("xb") as output:
                    output.write((stage / name).read_bytes())
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run only the synthetic anonymous-memory protocol test")
    args = parser.parse_args()
    build(self_test=args.self_test)
    print("CPU temperature bridge built. No elevation, hardware probe or installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
