"""Run each unittest module offscreen with a private profile before any app import."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "qa-private" / "isolated-tests"


def worker(pattern):
    if Path(pattern).name != pattern or not pattern.startswith("test_") or not pattern.endswith(".py"):
        raise ValueError("Expected a test module filename")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=Path(pattern).stem + "-", dir=SCRATCH) as private:
        profile = Path(private) / "profile"
        profile.mkdir()
        os.environ.update(
            DESKTOP_STATS_DATA=str(profile), QT_QPA_PLATFORM="offscreen",
            QT_QUICK_BACKEND="software", QSG_RENDER_LOOP="basic", TEMP=private, TMP=private,
        )
        font_directory = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
        if font_directory.is_dir():
            os.environ["QT_QPA_FONTDIR"] = str(font_directory)
        tempfile.tempdir = private
        sys.path.insert(0, str(ROOT))

        def live_target(value):
            if not isinstance(value, (str, bytes, os.PathLike)):
                return False
            parts = tuple(part.casefold() for part in Path(os.path.abspath(os.fsdecode(value))).parts)
            return "appdata" in parts and "desktopstats" in parts

        def fence(event, args):
            paths = []
            if event == "open":
                path, mode, flags = args
                if (isinstance(mode, str) and any(mark in mode for mark in "wax+")) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
                ):
                    paths = [path]
            elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime"}:
                paths = args[:1]
            elif event in {"os.rename", "os.link", "os.symlink"}:
                paths = args[:2]
            if any(live_target(path) for path in paths):
                raise PermissionError("Tests cannot modify a live Desktop Stats AppData profile")

        sys.addaudithook(fence)
        result = unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
        )
        print(json.dumps(dict(module=pattern, tests=result.testsRun, skipped=len(result.skipped),
                              passed=result.wasSuccessful())))
        return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", action="append", help="Glob to select test modules; repeatable")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    paths = sorted({path for pattern in args.pattern or ["test_*.py"]
                    for path in (ROOT / "tests").glob(pattern) if path.is_file()})
    if not paths or any(path.parent != ROOT / "tests" for path in paths):
        parser.error("Select at least one test module directly inside tests/")

    def run(path):
        try:
            process = subprocess.run(
                [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker", path.name],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return path.name, process.returncode, process.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return path.name, 1, "Isolated module exceeded its 180-second limit.\n"

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(run, paths))
    for name, status, output in rows:
        print(f"{'PASS' if status == 0 else 'FAIL'} {name}")
        if status:
            print(output[-6000:])
    counts = []
    for name, _status, output in rows:
        for line in output.splitlines():
            if line.startswith('{"module":'):
                value = json.loads(line)
                if value.get("module") == name:
                    counts.append(value)
    print(json.dumps(dict(tests=sum(value["tests"] for value in counts),
                          skipped=sum(value["skipped"] for value in counts),
                          modules=len(rows), passed=all(status == 0 for _, status, _ in rows))))
    print(f"{sum(status == 0 for _, status, _ in rows)}/{len(rows)} isolated modules passed")
    return 0 if all(status == 0 for _, status, _ in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
