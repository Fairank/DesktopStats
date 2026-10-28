"""Pure profile-pointer validation with temporary synthetic directories only."""

import ast
import copy
import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import profile_paths as profiles

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "d94acf3b-0f42-4b0e-8b45-7b1db139887c"
OTHER_ID = "ae9a1f39-0a84-4248-af49-f3ec6c344016"


class ProfilePathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="desktopstats-profile-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.user = self.root / "user"
        self.install = self.root / "install"
        self.user.mkdir()
        self.install.mkdir()
        self.executable = self.install / "DesktopStats.exe"
        self.pointer = self.install / profiles.POINTER_NAME
        self.target = self.user / ".desktopstats"
        self.target.mkdir()
        self.marker = self.target / profiles.MARKER_NAME
        self.env = dict(USERPROFILE=str(self.user), LOCALAPPDATA=str(self.user / "AppData/Local"))

    def write_pointer(self, **changes):
        value = dict(schema=1, profile_id=PROFILE_ID, directory=str(self.target))
        value.update(changes)
        self.pointer.write_text(json.dumps(value), encoding="utf-8")

    def write_marker(self, **changes):
        value = dict(schema=1, profile_id=PROFILE_ID)
        value.update(changes)
        self.marker.write_text(json.dumps(value), encoding="utf-8")

    def resolve(self, **changes):
        options = dict(environ=self.env, frozen=True, executable=self.executable)
        options.update(changes)
        return profiles.resolve_profile_paths(**options)

    def tree(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*")
                if path.is_file() and not path.is_symlink()}

    def test_missing_pointer_retains_legacy_directory_and_resolver_writes_nothing(self):
        before = self.tree()
        result = self.resolve()
        self.assertEqual(result.directory, Path(self.env["LOCALAPPDATA"]) / "DesktopStats")
        self.assertEqual(result.source, "legacy_default")
        self.assertIsNone(result.profile_id)
        self.assertIsNone(result.storage_fingerprint)
        self.assertFalse(result.directory.exists())
        self.assertEqual(self.tree(), before)

    def test_nonfrozen_ignores_invalid_sibling_pointer(self):
        self.pointer.write_bytes(b"invalid")
        with patch.object(profiles, "_sidecar", side_effect=AssertionError("Pointer must not be read")):
            self.assertEqual(self.resolve(frozen=False).source, "legacy_default")

    def test_production_namespace_does_not_follow_a_redirected_localappdata_value(self):
        result = self.resolve(environ=dict(self.env, LOCALAPPDATA=str(self.user / "private-cache/Local")))
        self.assertEqual(result.directory, self.user / "private-cache/Local/DesktopStats")
        self.assertEqual(result.ipc_key, str(self.user / "AppData/Local/DesktopStats"))

    def test_explicit_override_bypasses_pointer_and_preserves_original_ipc_spelling(self):
        self.pointer.write_bytes(b"invalid")
        for value in (str(self.root / "isolated-data"), "relative/isolated", ""):
            with self.subTest(value=value), \
                    patch.object(profiles, "_sidecar", side_effect=AssertionError("No pointer read")), \
                    patch.object(profiles, "_observed_fingerprint", return_value=None):
                result = self.resolve(environ=dict(self.env, DESKTOP_STATS_DATA=value))
                self.assertEqual(result.source, "environment")
                self.assertEqual(result.directory, Path(value))
                self.assertEqual(result.ipc_key, str(Path(value)))
        self.assertFalse((self.root / "isolated-data").exists())

    def test_valid_pointer_matches_marker_and_returns_no_path_in_status(self):
        self.write_pointer()
        self.write_marker()
        before = self.tree()
        result = self.resolve()
        self.assertEqual(result.directory, self.target)
        self.assertEqual((result.source, result.profile_id), ("installed_pointer", PROFILE_ID))
        self.assertEqual(len(result.storage_fingerprint), 64)
        self.assertEqual(set(result.status()), {"source", "profile_id", "storage_fingerprint"})
        self.assertNotIn(str(self.user), json.dumps(result.status()))
        self.assertEqual(self.tree(), before)

    def test_same_uuid_another_directory_changes_storage_fingerprint_not_production_pipe(self):
        self.write_pointer()
        self.write_marker()
        first = self.resolve()
        second_target = self.user / "alternate/DesktopStats"
        second_target.mkdir(parents=True)
        (second_target / profiles.MARKER_NAME).write_bytes(self.marker.read_bytes())
        self.write_pointer(directory=str(second_target))
        second = self.resolve()
        legacy = self.resolve(frozen=False)
        expected = str(self.user / "AppData/Local/DesktopStats")
        self.assertEqual(first.ipc_key, expected)
        self.assertEqual(second.ipc_key, expected)
        self.assertEqual(legacy.ipc_key, expected)
        self.assertNotEqual(first.storage_fingerprint, second.storage_fingerprint)

    def test_schema_uuid_and_fields_fail_explicitly_without_fallback(self):
        self.write_marker()
        for changes in (dict(schema=True), dict(schema=1.0), dict(schema=2), dict(profile_id="invalid"),
                        dict(profile_id=PROFILE_ID.replace("-", "")), dict(extra=True)):
            with self.subTest(changes=changes):
                self.write_pointer(**changes)
                with self.assertRaises(profiles.ProfilePathError):
                    self.resolve()

    def test_duplicate_json_fields_and_oversize_or_nonregular_pointer_are_rejected(self):
        self.write_marker()
        for raw in (b'{"schema":1,"schema":1}', b"x" * (profiles.MAX_SIDECAR_BYTES + 1), b"[]", b"\xff"):
            with self.subTest(raw_size=len(raw)):
                self.pointer.write_bytes(raw)
                with self.assertRaises(profiles.ProfilePathError):
                    self.resolve()
        self.pointer.unlink()
        self.pointer.mkdir()
        with self.assertRaises(profiles.ProfilePathError):
            self.resolve()

    def test_missing_bad_mismatched_or_oversize_marker_cannot_fall_back(self):
        self.write_pointer()
        with self.assertRaises(profiles.ProfilePathError):
            self.resolve()
        for changes in (dict(profile_id=OTHER_ID), dict(schema=True), dict(extra=True)):
            self.write_marker(**changes)
            with self.assertRaises(profiles.ProfilePathError):
                self.resolve()
        self.marker.write_bytes(b" " * (profiles.MAX_SIDECAR_BYTES + 1))
        with self.assertRaises(profiles.ProfilePathError):
            self.resolve()

    def test_userprofile_containment_dedicated_leaf_and_windows_path_ambiguities(self):
        self.write_marker()
        bad = [str(self.root / "user-sibling/DesktopStats"), str(self.user), str(self.user / "other"),
               "relative/DesktopStats", "C:DesktopStats", r"\DesktopStats", r"\\host\share\DesktopStats",
               str(self.target) + ":stream", str(self.target) + " ", str(self.target) + ".",
               str(self.user / "parent/../DesktopStats"), str(self.target) + "\n"]
        for directory in bad:
            with self.subTest(directory=directory):
                self.write_pointer(directory=directory)
                with self.assertRaises(profiles.ProfilePathError) as error:
                    self.resolve()
                self.assertNotIn(str(self.user), str(error.exception))

    def test_reparse_pointer_marker_target_and_ancestor_are_rejected_without_real_links(self):
        self.write_pointer()
        self.write_marker()
        original = Path.lstat
        for poisoned in (self.pointer, self.marker, self.target, self.user):
            def lstat(path, *, selected=poisoned):
                result = original(path)
                if path == selected:
                    return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size,
                        st_dev=result.st_dev, st_ino=result.st_ino, st_mtime_ns=result.st_mtime_ns,
                        st_file_attributes=0x400)
                return result
            with self.subTest(poisoned=poisoned.name), patch.object(Path, "lstat", lstat), \
                    self.assertRaises(profiles.ProfilePathError):
                self.resolve()

    def test_dangling_pointer_link_is_not_treated_as_absence(self):
        self.write_pointer()
        original = Path.lstat
        def lstat(path):
            result = original(path)
            if path == self.pointer:
                return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0)
            return result
        with patch.object(Path, "lstat", lstat), self.assertRaises(profiles.ProfilePathError):
            self.resolve()

    def test_storage_redirect_and_changed_open_file_identity_fail_closed(self):
        self.write_pointer()
        self.write_marker()
        original_resolve = Path.resolve
        def redirected(path, **options):
            return self.user / "elsewhere/DesktopStats" if path == self.target else original_resolve(path, **options)
        with patch.object(Path, "resolve", redirected), self.assertRaises(profiles.ProfilePathError):
            self.resolve()
        original_fstat = profiles.os.fstat
        def changed(descriptor):
            result = original_fstat(descriptor)
            return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size,
                st_dev=result.st_dev, st_ino=result.st_ino + 1, st_mtime_ns=result.st_mtime_ns)
        with patch.object(profiles.os, "fstat", changed), self.assertRaises(profiles.ProfilePathError):
            self.resolve()

    def test_native_pipe_function_uses_production_compatibility_and_isolated_keys(self):
        tree = ast.parse((ROOT / "native_ipc.py").read_bytes())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "name")
        production = self.resolve().ipc_key
        isolated = self.resolve(environ=dict(self.env, DESKTOP_STATS_DATA=str(self.root / "test-profile"))).ipc_key
        for key in (production, isolated):
            namespace = dict(hashlib=hashlib, IPC_PROFILE_KEY=key)
            exec(compile(ast.Module(body=[copy.deepcopy(function)], type_ignores=[]), "<pure-ipc-name>", "exec"), namespace)
            self.assertEqual(namespace["name"](), "DesktopStatsNative-" + hashlib.sha256(key.encode()).hexdigest()[:20])
        self.assertNotEqual(production, isolated)


if __name__ == "__main__":
    unittest.main()
