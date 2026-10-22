"""Synthetic collector transport checks; never enter an upstream hardware API."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "collector" / "runtime"
EXE = RUNTIME / "DesktopStats.Collector.exe"


@unittest.skipUnless(sys.platform == "win32" and EXE.is_file(), "built Windows collector required")
class CollectorContractTests(unittest.TestCase):
    def run_synthetic(self, *arguments):
        # Only self-test or argument errors are used in this test module.
        return subprocess.run(
            [str(EXE), *arguments], cwd=RUNTIME,
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_synthetic_protocol_preserves_raw_energy_and_real_zero(self):
        result = self.run_synthetic("--self-test")
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual((payload["schema"], payload["provider"], payload["version"]),
                         (1, "LibreHardwareMonitor", "0.9.6"))
        self.assertIsInstance(payload["timestamp"], (int, float))
        energy, power = payload["sensors"]
        self.assertEqual((energy["unit"], energy["value"], energy["min"], energy["max"]),
                         ("mWh", 12345, 12000, 13000))
        self.assertEqual((power["unit"], power["value"]), ("W", 0))
        self.assertEqual(energy["hardware_id"], payload["hardware"][0]["id"])
        self.assertLess(len(result.stdout), 2 * 1024 * 1024)
        self.assertIn(b"hardware was not opened", result.stderr)

    def test_invalid_cadence_and_commands_fail_before_collection(self):
        invalid_arguments = [
            ("--interval", "0.01"), ("--interval", "5.01"),
            ("--interval", "NaN"), ("--interval", "Infinity"),
            ("--duration", "0"), ("--duration", "86401"),
            ("--admin",), ("--enable-driver",), ("--interval",),
        ]
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                result = self.run_synthetic(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr)

    def test_built_runtime_has_exact_verified_library_closure(self):
        manifest = json.loads((RUNTIME / "library-manifest.json").read_text(encoding="utf-8"))
        expected = {entry["name"] for entry in manifest["files"]}
        self.assertEqual(expected, {path.name for path in RUNTIME.glob("*.dll")})
        self.assertEqual(len(expected), 9)
        for entry in manifest["files"] + manifest["licenses"]:
            with self.subTest(file=entry["name"]):
                raw = (RUNTIME / entry["name"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])
        for pattern in ("*.sys", "*.inf", "*.cat"):
            self.assertFalse(list(RUNTIME.glob(pattern)))
        self.assertEqual({path.name for path in RUNTIME.glob("*.exe")}, {EXE.name})


if __name__ == "__main__":
    unittest.main()
