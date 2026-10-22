"""Self-check isolation and non-destructive reports, without Qt or desktop activity."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import native_selfcheck


class SelfCheckTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1] / "qa-private/selfcheck-unit-temp"
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / "profile"
        self.output = self.base / "report.json"
        self.environment = patch.dict(os.environ, {"DESKTOP_STATS_DATA": str(self.base)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_requires_explicit_absolute_isolation_directory(self):
        for value in ("", "relative-profile"):
            with (
                patch.dict(os.environ, {"DESKTOP_STATS_DATA": value}),
                patch.object(native_selfcheck, "_check") as check,
            ):
                with self.assertRaises(ValueError):
                    native_selfcheck.run(self.output)
                check.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_rejects_existing_profiles_including_backup_only_and_png_only(self):
        self.base.mkdir()
        for name in (
            "preferences.backup.json",
            "preferences.json",
            "positions.json",
            "app.pid",
            "report.png",
        ):
            with self.subTest(name=name):
                existing = self.base / name
                existing.write_bytes(b"keep original")
                with patch.object(native_selfcheck, "_check") as check:
                    with self.assertRaises(ValueError):
                        native_selfcheck.run(self.output)
                    check.assert_not_called()
                self.assertEqual(existing.read_bytes(), b"keep original")
                self.assertFalse(self.output.exists())
                existing.unlink()

    def test_requires_json_suffix_and_refuses_escape_before_creating_profile(self):
        for target in (self.base / "report.png", self.base.parent / "outside.json"):
            with patch.object(native_selfcheck, "_check") as check:
                with self.assertRaises(ValueError):
                    native_selfcheck.run(target)
                check.assert_not_called()
        self.assertFalse(self.base.exists())

    def test_existing_report_is_never_overwritten(self):
        self.base.mkdir()
        self.output.write_bytes(b"original report")
        with patch.object(native_selfcheck, "_check") as check:
            with self.assertRaises(ValueError):
                native_selfcheck.run(self.output)
            check.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b"original report")

    def test_asset_import_failure_produces_failure_report_without_ui(self):
        with patch.object(native_selfcheck, "_check", side_effect=ImportError("missing asset")):
            self.assertEqual(native_selfcheck.run(self.output), 1)
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertFalse(report["ok"])
        self.assertIn("ImportError", report["error"])
        self.assertFalse(report["foreground_windows"])
        self.assertFalse(report["hardware"])

    def test_success_is_offscreen_and_cannot_reuse_a_written_profile(self):
        with patch.object(native_selfcheck, "_check") as check:
            self.assertEqual(native_selfcheck.run(self.output), 0)
            check.assert_called_once()
        self.assertEqual(os.environ["QT_QPA_PLATFORM"], "offscreen")
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertFalse(report["installed_app_ipc"])
        with self.assertRaises(ValueError):
            native_selfcheck.run(self.base / "another.json")
