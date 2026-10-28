"""Public-export privacy and integrity regressions using only workspace fixtures."""

import copy
import hashlib
import json
import shutil
import stat
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import build
from tools import export_source as export

PROJECT = Path(__file__).resolve().parents[1]
SCRATCH = PROJECT / "qa-private" / "source-export-tests"


class SourceExportTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        if not SCRATCH.resolve().is_relative_to(PROJECT.resolve()):
            raise AssertionError("Source-export scratch escaped the project")
        self.temporary = tempfile.TemporaryDirectory(prefix="snapshot-", dir=SCRATCH)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        if not self.root.resolve().is_relative_to(SCRATCH.resolve()):
            raise AssertionError("Temporary source fixture escaped its scratch root")
        self.output = self.root / "dist" / "candidate-source.zip"
        self.write("product_version.py", 'VERSION = "0.19.0-preview.1"\n')
        self.write("app.py", '"""Synthetic source; no application starts."""\nVALUE = 42\n')
        self.write("LICENSE", "Synthetic application license\n")
        self.write("assets/icon.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>\n')
        self.write("tests/test_example.py", "# Generic fixture path: C:/Users/TestUser/example\n")
        self.write("NOTICE", "Required Notice: Synthetic test copyright\n")
        for folder in ("collector", "third_party/librehardwaremonitor/0.9.6"):
            shutil.copytree(
                PROJECT / folder,
                self.root / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        sources = (
            "product_version.py",
            "app.py",
            "LICENSE",
            "tools/build.py",
            "collector/Program.cs",
            "collector/build.ps1",
            "collector/DesktopStats.Collector.exe.config",
        )
        self.write("tools/build.py", "SOURCES = " + repr(sources) + "\n")
        # This is the actual packaging validator, with only its project root
        # changed. A fake that merely returns paths would miss integrity bugs.
        collector_files = types.FunctionType(
            build.collector_files.__code__, {**build.__dict__, "ROOT": self.root}
        )
        self.contract = SimpleNamespace(
            ROOT=self.root, SOURCES=sources, collector_files=collector_files
        )
        self.addCleanup(patch.stopall)
        patch.object(export, "REVIEWED_FILES", frozenset({"assets/icon.svg"})).start()
        patch.object(export, "EXTRA_FILES", frozenset({"NOTICE"})).start()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def run_export(self, output=None):
        return export.export_source(output or self.output, root=self.root, contract=self.contract)

    def test_current_snapshot_has_exact_manifest_and_byte_identical_members(self):
        result = self.run_export()
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.19.0-preview.1")
        self.assertEqual(result["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            prefix = "DesktopStats-0.19.0-preview.1-source/"
            manifest = json.loads(archive.read(prefix + "SOURCE_MANIFEST.json"))
            actual = set(archive.namelist())
            self.assertEqual(
                actual,
                {prefix + row["path"] for row in manifest["files"]}
                | {prefix + "SOURCE_MANIFEST.json"},
            )
            self.assertEqual(len(manifest["files"]), result["file_count"])
            for row in manifest["files"]:
                data = archive.read(prefix + row["path"])
                self.assertEqual(data, (self.root / row["path"]).read_bytes())
                self.assertEqual(row["bytes"], len(data))
                self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())
                self.assertFalse(Path(row["path"]).is_absolute())
            self.assertFalse(manifest["binaries_included"])
            self.assertTrue(manifest["dependency_preparation_required"])
            self.assertFalse(any("collector/runtime/" in name for name in actual))
            self.assertIn(prefix + "collector/Program.cs", actual)
            self.assertIn(prefix + export.DEPENDENCY_ROOT + "/manifest.json", actual)
            self.assertIn(prefix + export.DEPENDENCY_ROOT + "/NOTICE.md", actual)
            self.assertIn(prefix + export.DEPENDENCY_ROOT + "/LICENSE-MPL-2.0.txt", actual)
            self.assertFalse(any(export._binary_path(name) for name in actual))
            self.assertFalse(any(export._binary_magic(archive.read(name)) for name in actual))
            self.assertIn(prefix + "tests/test_example.py", actual)

    def test_even_explicit_build_binary_inputs_are_excluded_but_png_and_ico_remain(self):
        sources = list(self.contract.SOURCES)
        for name in (
            "old.exe",
            "driver.sys",
            "plugin.pyd",
            "install.msi",
            "lib.dylib",
            "lib.so.1.2",
            "old.dll",
            "lib.a",
            "object.obj",
            "app.jar",
            "logic.wasm",
        ):
            self.write(name, b"MZ\x00compiled payload")
            sources.append(name)
        for name, data in (
            ("assets/test.png", b"\x89PNG\r\n\x1a\nimage"),
            ("assets/test.ico", b"\x00\x00\x01\x00icon"),
        ):
            self.write(name, data)
            sources.append(name)
        self.contract.SOURCES = tuple(sources)
        self.write("tools/build.py", "SOURCES = " + repr(self.contract.SOURCES) + "\n")
        self.run_export()
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            self.assertFalse(any(export._binary_path(name) for name in names))
            self.assertTrue(any(name.endswith("assets/test.png") for name in names))
            self.assertTrue(any(name.endswith("assets/test.ico") for name in names))

    def test_reviewed_original_shader_source_and_render_asset_roundtrip(self):
        names = ("assets/shaders/metric-discharge.frag", "assets/shaders/metric-discharge.frag.qsb")
        for name in names:
            self.write(name, (PROJECT / name).read_bytes())
        with patch.object(export, "REVIEWED_FILES", frozenset({"assets/icon.svg", *names})):
            self.run_export()
        with zipfile.ZipFile(self.output) as archive:
            for name in names:
                self.assertEqual(archive.read("DesktopStats-0.19.0-preview.1-source/"+name),
                                 (PROJECT / name).read_bytes())

    def test_fragment_shader_source_is_scanned_for_private_data(self):
        with self.assertRaises(export.ExportError):
            export._scan("assets/shaders/example.frag", b"// C:/"+b"Users/"+b"PrivateOwner/local-project")

    def test_renamed_executable_magic_is_rejected_as_source_or_image(self):
        for name, payload in (
            ("app.py", b"MZ\x00not source"),
            ("assets/icon.svg", b"\x7fELF\x00not an image"),
        ):
            original = (self.root / name).read_bytes()
            self.write(name, payload)
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(export.ExportError, "binary is not permitted"),
            ):
                self.run_export()
            self.write(name, original)
        self.assertFalse(self.output.exists())

    def test_unlisted_private_files_and_previous_versions_never_enter_archive(self):
        private = "PRIVATE" + "-DO-NOT-PUBLISH"
        for name in (
            ".env",
            ".git/config",
            ".qa-profile/preferences.json",
            "qa-private/person.json",
            "dist/old-0.11.zip",
            "build/output.txt",
            "root-qml-isolated-profile/latest.json",
            "assets/private-notes.md",
            "native/private-note.txt",
            "hooks/private-note.txt",
            "licenses/private-note.txt",
        ):
            self.write(name, private)
        self.run_export()
        with zipfile.ZipFile(self.output) as archive:
            self.assertFalse(
                any(private.encode() in archive.read(name) for name in archive.namelist())
            )
            self.assertFalse(
                any("old-0.11" in name or "private-note" in name for name in archive.namelist())
            )

    def test_existing_output_is_never_replaced(self):
        self.write("dist/candidate-source.zip", b"old immutable artifact")
        with self.assertRaises(FileExistsError):
            self.run_export()
        self.assertEqual(self.output.read_bytes(), b"old immutable artifact")

    def test_output_cannot_escape_workspace_or_use_parent_traversal(self):
        for output in (self.root.parent / "outside.zip", self.root / "x/../escape.zip"):
            with self.subTest(output=output), self.assertRaises(export.ExportError):
                self.run_export(output)
        self.assertFalse(self.output.exists())

    def test_source_allowlist_cannot_include_parent_or_private_folder(self):
        for name in (
            "../outside.py",
            "qa-private/note.py",
            "assets/../../outside.py",
            "C:/outside.py",
            "assets/private.key",
        ):
            contract = copy.copy(self.contract)
            contract.SOURCES = (*self.contract.SOURCES, name)
            self.write("tools/build.py", "SOURCES = " + repr(contract.SOURCES) + "\n")
            with self.subTest(name=name), self.assertRaises(export.ExportError):
                export.export_source(self.output, root=self.root, contract=contract)
        self.assertFalse(self.output.exists())

    def test_real_symlink_source_is_refused_before_read(self):
        target = self.write("private-original.py", "PRIVATE DATA\n")
        app = self.root / "app.py"
        app.unlink()
        try:
            app.symlink_to(target)
        except OSError as error:
            self.skipTest("Host does not grant symlink creation: " + str(error.winerror))
        with self.assertRaisesRegex(export.ExportError, "links and reparse"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_windows_directory_junction_attribute_is_refused_without_reading_file(self):
        directory = self.root / "assets"
        original = Path.lstat
        original_read = Path.read_bytes

        def reparse(path):
            if path == directory:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x410)
            return original(path)

        def guarded_read(path):
            if path == directory / "icon.svg":
                raise AssertionError("Read followed a simulated Windows junction")
            return original_read(path)

        with patch.object(Path, "lstat", reparse), patch.object(Path, "read_bytes", guarded_read):
            with self.assertRaisesRegex(export.ExportError, "links and reparse"):
                self.run_export()
        self.assertFalse(self.output.exists())

    def test_symbolic_link_metadata_is_rejected_on_hosts_without_link_privilege(self):
        original = Path.lstat

        def symbolic(path):
            if path == self.root / "app.py":
                return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
            return original(path)

        with patch.object(Path, "lstat", symbolic), self.assertRaises(export.ExportError):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_output_parent_reparse_point_is_refused(self):
        self.output.parent.mkdir()
        original = Path.lstat

        def reparse(path):
            if path == self.output.parent:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x410)
            return original(path)

        with patch.object(Path, "lstat", reparse), self.assertRaises(export.ExportError):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_tampered_vendor_manifest_and_self_consistent_replacement_are_refused(self):
        manifest = self.root / export.DEPENDENCY_ROOT / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        dll = manifest.parent / data["files"][0]["name"]
        dll.write_bytes(b"modified dependency")
        data["files"][0].update(
            bytes=dll.stat().st_size, sha256=hashlib.sha256(dll.read_bytes()).hexdigest()
        )
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(
            export.ExportError, "reviewed third-party dependency manifest changed"
        ):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_unchanged_manifest_with_tampered_vendor_dll_is_refused(self):
        self.write(export.DEPENDENCY_ROOT + "/HidSharp.dll", b"modified vendor binary")
        with self.assertRaisesRegex(export.ExportError, "dependency integrity failed"):
            self.run_export()

    def test_real_collector_validator_refuses_changed_runtime_binary(self):
        self.write("collector/runtime/DesktopStats.Collector.exe", b"modified own collector")
        with self.assertRaisesRegex(ValueError, "Collector runtime integrity failed"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_dependency_change_between_validation_and_snapshot_is_rejected(self):
        original = export.collect_paths
        calls = 0

        def change_after_first_validation(root, contract):
            nonlocal calls
            paths = original(root, contract)
            calls += 1
            if calls == 1:
                self.write(export.DEPENDENCY_ROOT + "/HidSharp.dll", b"changed after validation")
            return paths

        with patch.object(export, "collect_paths", change_after_first_validation):
            with self.assertRaisesRegex(export.ExportError, "dependency integrity failed"):
                self.run_export()
        self.assertFalse(self.output.exists())

    def test_loaded_packaging_allowlist_must_match_source_being_published(self):
        self.write("tools/build.py", "SOURCES = ('app.py',)\n")
        with self.assertRaisesRegex(export.ExportError, "source contract changed"):
            self.run_export()

    def test_collector_manifest_cannot_read_parent_path(self):
        manifest = self.root / "collector/runtime/build-manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        data["files"][0]["name"] = "../../private.txt"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(export.ExportError, "Invalid collector runtime manifest path"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_malformed_collector_metadata_is_a_clean_refusal(self):
        for data in ([], {"files": [None], "sources": []}):
            self.write("collector/runtime/build-manifest.json", json.dumps(data))
            with self.subTest(data=data), self.assertRaises(export.ExportError):
                self.run_export()
        self.assertFalse(self.output.exists())

    def test_possible_secret_and_actual_personal_home_literal_block_without_echoing_values(self):
        secret = "ghp" + "_" + "8Yv0FudqRbNmS74pAz6G1Ci9Xk3D5LwE"
        self.write("app.py", 'TOKEN = "' + secret + '"\n')
        with self.assertRaises(export.ExportError) as caught:
            self.run_export()
        self.assertNotIn(secret, str(caught.exception))
        personal = "C:" + "/" + "Users/" + "private-person/OneDrive/data.json"
        self.write("app.py", 'FILE = "' + personal + '"\n')
        with self.assertRaisesRegex(export.ExportError, "Personal home-directory literal"):
            self.run_export()
        self.assertFalse(self.output.exists())

    def test_generic_fixture_paths_are_allowed_and_export_is_reproducible(self):
        self.write(
            "tests/test_paths.py",
            "\n".join(
                "# Fixture " + prefix + user + "/example"
                for prefix in ("C:/" + "Users/", "/home/", "/Users/")
                for user in ("alice", "TestUser", "test-profile", "<username>")
            ),
        )
        first = self.run_export()
        second = self.run_export(self.root / "dist/second.zip")
        self.assertEqual(first["sha256"], second["sha256"])

    def test_source_mutation_during_archive_write_invalidates_and_removes_only_new_artifact(self):
        original = zipfile.ZipFile.writestr
        modified = False

        def mutate(archive, name, data, *args, **kwargs):
            nonlocal modified
            result = original(archive, name, data, *args, **kwargs)
            if not modified:
                modified = True
                self.write("app.py", 'VALUE = "changed mid-export"\n')
            return result

        with patch.object(zipfile.ZipFile, "writestr", mutate):
            with self.assertRaisesRegex(export.ExportError, "Source changed during export"):
                self.run_export()
        self.assertFalse(self.output.exists())
        self.assertIn("changed mid-export", (self.root / "app.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
