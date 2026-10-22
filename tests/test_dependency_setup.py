"""Local fixture archives verify all dependencies before writing or executing any."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from tools import fetch_sensor_dependencies as setup


class DependencySetupTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / "qa-private" / "dependency-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.private = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.private.cleanup)
        self.root = Path(self.private.name)
        self.vendor = self.root / setup.DEPENDENCIES
        self.vendor.mkdir(parents=True)
        self.contents = {"First.dll": b"synthetic-one", "Second.dll": b"synthetic-two"}
        self.archive = self.root / "official.zip"
        self.create_archive(self.contents)
        data = dict(release_asset_url=setup.ASSET_URL,
                    release_asset_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                    files=[dict(name=name, bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
                           for name, value in self.contents.items()])
        self.manifest = self.vendor / "manifest.json"
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(setup, "MANIFEST_SHA256", hashlib.sha256(self.manifest.read_bytes()).hexdigest()))
        stack.enter_context(patch.object(setup, "ASSET_SHA256", data["release_asset_sha256"]))

    def create_archive(self, contents):
        with zipfile.ZipFile(self.archive, "w") as output:
            for name, value in contents.items():
                output.writestr("Framework/" + name, value)
            output.writestr("../../private.txt", "Do not extract whole untrusted archives")
            output.writestr("Framework/Unwanted.exe", b"synthetic-executable")

    def test_only_exact_verified_files_are_extracted_and_no_archive_paths_are_followed(self):
        self.assertEqual(setup.install_from_archive(self.archive, root=self.root), 2)
        for name, content in self.contents.items():
            self.assertEqual((self.vendor / name).read_bytes(), content)
        self.assertEqual(sorted(path.name for path in self.vendor.iterdir()),
                         ["First.dll", "Second.dll", "manifest.json"])
        self.assertFalse((self.root / "private.txt").exists())

    def test_a_bad_release_hash_writes_nothing(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "archive hash mismatch"):
            setup.install_from_archive(self.archive, root=self.root)
        self.assertEqual([path.name for path in self.vendor.iterdir()], ["manifest.json"])

    def test_missing_or_tampered_library_is_rejected_before_any_library_write(self):
        self.create_archive({"First.dll": self.contents["First.dll"], "Second.dll": b"wrong"})
        with patch.object(setup, "ASSET_SHA256", hashlib.sha256(self.archive.read_bytes()).hexdigest()):
            raw = json.loads(self.manifest.read_text())
            raw["release_asset_sha256"] = setup.ASSET_SHA256
            self.manifest.write_text(json.dumps(raw), encoding="utf-8")
            with patch.object(setup, "MANIFEST_SHA256", hashlib.sha256(self.manifest.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(ValueError, "Pinned library absent"):
                    setup.install_from_archive(self.archive, root=self.root)
        self.assertFalse((self.vendor / "First.dll").exists())

    def test_existing_foreign_library_is_preserved(self):
        target = self.vendor / "First.dll"
        target.write_bytes(b"user-library")
        with self.assertRaisesRegex(ValueError, "Existing dependency differs"):
            setup.install_from_archive(self.archive, root=self.root)
        self.assertEqual(target.read_bytes(), b"user-library")
        self.assertFalse((self.vendor / "Second.dll").exists())

    def test_changed_manifest_is_not_trusted(self):
        self.manifest.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            setup.install_from_archive(self.archive, root=self.root)


if __name__ == "__main__":
    unittest.main()
