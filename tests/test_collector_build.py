"""The local Python build path needs no policy change, downloads or hardware IO."""

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import build_collector as builder


class CollectorBuildTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / "qa-private" / "collector-build-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.private = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.private.cleanup)
        self.root = Path(self.private.name)
        self.collector = self.root / "collector"
        self.vendor = self.root / "vendor"
        self.collector.mkdir()
        self.vendor.mkdir()
        (self.root / "tools").mkdir()
        (self.root / "tools/build_collector.py").write_text("# synthetic build fixture", encoding="utf-8")
        for name in ("Program.cs", "build.ps1", "DesktopStats.Collector.exe.config"):
            (self.collector / name).write_text("synthetic " + name, encoding="utf-8")
        payloads = {"LibreHardwareMonitorLib.dll": b"synthetic library", "LICENSE.txt": b"synthetic license"}
        rows = []
        for name, raw in payloads.items():
            (self.vendor / name).write_bytes(raw)
            rows.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        self.data = dict(files=rows[:1], licenses=rows[1:], source_commit="synthetic-fixed-commit")
        for name in ("manifest.json", "NOTICE.md"):
            (self.vendor / name).write_text("synthetic metadata", encoding="utf-8")
        self.compiler = self.root / "Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        self.compiler.parent.mkdir(parents=True)
        self.compiler.write_bytes(b"synthetic existing compiler")
        self.addCleanup(patch.stopall)
        patch.dict("os.environ", {"SystemRoot": str(self.root / "Windows")}).start()
        patch.object(builder, "manifest", return_value=(self.vendor, self.data)).start()
        self.calls = []

        def compile_or_selftest(command, **options):
            self.calls.append((command, options))
            if command[0] == str(self.compiler):
                target = next(arg[5:] for arg in command if arg.startswith("/out:"))
                Path(target).write_bytes(b"MZ-original-synthetic-collector")
            else:
                self.assertEqual(command[1:], ["--self-test"])

        self.process = patch.object(builder.subprocess, "run", side_effect=compile_or_selftest).start()

    def test_build_uses_only_existing_compiler_then_explicit_synthetic_test(self):
        result = builder.build(root=self.root, self_test=True)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[0][0][0], str(self.compiler))
        self.assertEqual(self.calls[1][0][1:], ["--self-test"])
        self.assertTrue((self.collector / "runtime/build-manifest.json").is_file())
        self.assertEqual(result["builder"]["name"], "tools/build_collector.py")
        self.assertEqual({row["name"] for row in result["sources"]},
                         {"Program.cs", "build.ps1", "DesktopStats.Collector.exe.config"})

    def test_compilation_failure_does_not_publish_a_partial_runtime(self):
        self.process.side_effect = subprocess.CalledProcessError(1, "synthetic compiler")
        with self.assertRaises(subprocess.CalledProcessError):
            builder.build(root=self.root)
        self.assertFalse((self.collector / "runtime").exists())

    def test_dependency_tamper_is_rejected_before_compiler_runs(self):
        (self.vendor / "LibreHardwareMonitorLib.dll").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Dependency integrity failed"):
            builder.build(root=self.root)
        self.process.assert_not_called()

    def test_foreign_runtime_is_never_overwritten(self):
        runtime = self.collector / "runtime"
        runtime.mkdir()
        foreign = runtime / "user.txt"
        foreign.write_text("user input", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            builder.build(root=self.root)
        self.assertEqual(foreign.read_text(), "user input")
        self.process.assert_not_called()

    def test_modified_owned_runtime_is_preserved_on_rebuild(self):
        builder.build(root=self.root)
        self.process.reset_mock()
        target = self.collector / "runtime/DesktopStats.Collector.exe"
        target.write_bytes(b"user modification")
        with self.assertRaisesRegex(ValueError, "Existing runtime was modified"):
            builder.build(root=self.root)
        self.assertEqual(target.read_bytes(), b"user modification")
        self.process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
