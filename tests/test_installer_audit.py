"""Installer/clean-quit audit with workspace files and fake OS/IPC interfaces only."""

import ast
import builtins
import copy
import json
import logging
import sys
import tempfile
import traceback
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app
import installer


class FakeRegistryKey:
    def __init__(self, registry, path):
        self.registry, self.path = registry, path

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def Close(self):
        pass


class FakeRegistry:
    HKEY_CURRENT_USER = "FAKE_HKCU"
    KEY_READ = 1
    KEY_WRITE = 2
    KEY_QUERY_VALUE = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    REG_DWORD = 4

    def __init__(self):
        self.values = {}
        self.fail_new_version = False

    def OpenKey(self, _root, path, *_args):
        if path not in self.values:
            raise FileNotFoundError(path)
        return FakeRegistryKey(self, path)

    def CreateKey(self, _root, path):
        self.values.setdefault(path, {})
        return FakeRegistryKey(self, path)

    CreateKeyEx = CreateKey

    def EnumValue(self, key, index):
        try:
            name, (value, kind) = list(self.values[key.path].items())[index]
        except IndexError:
            raise OSError("No more synthetic registry values") from None
        return name, value, kind

    def QueryValueEx(self, key, name):
        try:
            return self.values[key.path][name]
        except KeyError:
            raise FileNotFoundError(name) from None

    def SetValueEx(self, key, name, _reserved, kind, value):
        if self.fail_new_version and name == "DisplayVersion" and value == installer.VERSION:
            self.fail_new_version = False
            raise PermissionError("Synthetic registration failure")
        self.values[key.path][name] = (value, kind)

    def DeleteValue(self, key, name):
        if name not in self.values[key.path]:
            raise FileNotFoundError(name)
        del self.values[key.path][name]

    def DeleteKey(self, _root, path):
        if path not in self.values:
            raise FileNotFoundError(path)
        del self.values[path]

    def QueryInfoKey(self, key):
        return 0, len(self.values[key.path]), 0

    def EnumKey(self, _key, _index):
        raise OSError("No synthetic subkeys")

    def CloseKey(self, _key):
        pass


class CloseExistingAuditTests(unittest.TestCase):
    def setUp(self):
        self.send = Mock()
        module = types.ModuleType("native_ipc")
        module.send = self.send
        module.name = lambda: "fake-installer-audit-pipe"
        ipc = patch.dict(sys.modules, {"native_ipc": module})
        ipc.start()
        self.addCleanup(ipc.stop)
        sleep = patch.object(installer.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        absent = patch.object(installer, "_server_absent", return_value=True)
        self.absent = absent.start()
        self.addCleanup(absent.stop)

    @staticmethod
    def status(**changes):
        return dict(ok=True, native=True, dirty=False, pid=7007, **changes)

    def test_absent_instance_requires_an_independent_absent_server_probe(self):
        self.send.return_value = None
        installer.close_existing()
        self.send.assert_called_once_with({"command": "status"}, timeout=1200)
        self.absent.assert_called_once_with()
        self.send.reset_mock()
        self.absent.return_value = False
        with self.assertRaises(RuntimeError):
            installer.close_existing()
        self.send.assert_called_once_with({"command": "status"}, timeout=1200)

    def test_dirty_old_malformed_and_unknown_status_never_sends_quit(self):
        base = self.status()
        invalid = (
            {},
            [],
            "unknown",
            dict(base, ok=False),
            dict(base, native=False),
            dict(base, dirty=True),
            {key: value for key, value in base.items() if key != "dirty"},
            dict(base, dirty=None),
            dict(base, pid=True),
            dict(base, pid=0),
        )
        for status in invalid:
            with self.subTest(status=status):
                self.send.reset_mock()
                self.send.return_value = status
                with self.assertRaises(RuntimeError):
                    installer.close_existing()
                self.send.assert_called_once_with({"command": "status"}, timeout=1200)

    def test_acknowledgement_must_confirm_clean_quit_of_the_same_pid(self):
        valid = dict(ok=True, quitting=True, dirty=False, pid=7007)
        for ack in (
            None,
            {},
            [],
            dict(valid, ok=False),
            dict(valid, quitting=False),
            dict(valid, dirty=True),
            dict(valid, pid=7008),
            dict(valid, pid=True),
            {key: value for key, value in valid.items() if key != "dirty"},
        ):
            with self.subTest(ack=ack):
                self.send.reset_mock()
                self.send.side_effect = [self.status(), ack]
                with self.assertRaises(RuntimeError):
                    installer.close_existing()
                self.assertEqual(
                    [call.args[0]["command"] for call in self.send.call_args_list],
                    ["status", "quit_if_clean"],
                )

    def test_success_requires_status_disappearance_and_pipe_absence(self):
        self.send.side_effect = [
            self.status(),
            dict(ok=True, quitting=True, dirty=False, pid=7007),
            self.status(),
            None,
        ]
        installer.close_existing()
        self.assertEqual(
            [item.args[0]["command"] for item in self.send.call_args_list],
            ["status", "quit_if_clean", "status", "status"],
        )
        self.absent.assert_called_once_with()

    def test_ack_without_confirmed_termination_refuses_installation(self):
        replies = iter([self.status(), dict(ok=True, quitting=True, dirty=False, pid=7007)])
        self.send.side_effect = lambda *_args, **_kwargs: next(replies, None)
        self.absent.return_value = False
        with self.assertRaises(RuntimeError):
            installer.close_existing()
        self.assertNotIn("quit", [item.args[0]["command"] for item in self.send.call_args_list])

    def test_boolean_ack_pid_cannot_equal_integer_pid_one(self):
        self.send.side_effect = [
            dict(self.status(), pid=1),
            dict(ok=True, quitting=True, dirty=False, pid=True),
            None,
        ]
        with self.assertRaises(RuntimeError):
            installer.close_existing()


class ServerAbsentAuditTests(unittest.TestCase):
    def test_probe_is_read_only_and_accepts_only_server_not_found(self):
        for connected, error, expected in (
            (True, "server_not_found", False),
            (False, "server_not_found", True),
            (False, "timeout", False),
            (False, "access_denied", False),
        ):
            with self.subTest(connected=connected, error=error):
                socket = Mock()
                socket.waitForConnected.return_value = connected
                socket.error.return_value = error
                socket_type = Mock(return_value=socket)
                socket_type.LocalSocketError.ServerNotFoundError = "server_not_found"
                network = types.ModuleType("PySide6.QtNetwork")
                network.QLocalSocket = socket_type
                qt = types.ModuleType("PySide6")
                qt.__path__ = []
                qt.QtNetwork = network
                ipc = types.ModuleType("native_ipc")
                ipc.name = lambda: "fake-probe-only-pipe"
                ipc.send = Mock(side_effect=AssertionError("Probe must not send commands"))
                with patch.dict(
                    sys.modules, {"PySide6": qt, "PySide6.QtNetwork": network, "native_ipc": ipc}
                ):
                    self.assertEqual(installer._server_absent(), expected)
                socket.connectToServer.assert_called_once_with("fake-probe-only-pipe")
                socket.write.assert_not_called()
                socket.abort.assert_called_once_with()
                ipc.send.assert_not_called()


class InstallerTransactionAuditTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1]
        directory = workspace / "qa-private"
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="installer-audit-", dir=directory)
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(workspace))
        self.addCleanup(self.temp.cleanup)
        self.target = self.base / "Programs/DesktopStats"
        self.target.parent.mkdir()
        self.source = self.base / "candidate"
        self.source.mkdir()
        self.desktop, self.programs = self.base / "Desktop", self.base / "Shortcuts"
        self.desktop.mkdir()
        self.programs.mkdir()
        self.profile = self.base / "external-profile"
        self.profile.mkdir()
        self.preferences = self.profile / "preferences.json"
        self.preferences.write_bytes(b"external profile must remain byte-identical")
        self.registry = FakeRegistry()
        self.registry.values = {
            installer.REGISTRY: {"DisplayVersion": ("old", 1), "UserValue": (27, 4)},
            installer.RUN_KEY: {"DesktopStats": ("old startup", 1), "Unrelated": ("leave", 1)},
        }
        self.links = [folder / "Desktop Stats.lnk" for folder in (self.desktop, self.programs)]
        for link in self.links:
            link.write_bytes(b"old shortcut " + link.parent.name.encode())
        for target, value in (
            ("DIRECTORY", self.target),
            ("winreg", self.registry),
            ("close_existing", Mock()),
            ("shell_folder", lambda kind: self.desktop if kind == 0x10 else self.programs),
        ):
            helper = patch.object(installer, target, value)
            helper.start()
            self.addCleanup(helper.stop)
        for name, value in (
            ("frozen", True),
            ("executable", str(self.source / "DesktopStats.exe")),
        ):
            helper = patch.object(installer.sys, name, value, create=True)
            helper.start()
            self.addCleanup(helper.stop)
        config = types.ModuleType("stats_config")
        config.load = Mock(return_value={"autostart": False})
        config.BASE = self.profile
        modules = patch.dict(sys.modules, {"stats_config": config})
        modules.start()
        self.addCleanup(modules.stop)
        process = patch.object(installer.subprocess, "Popen", return_value=Mock())
        self.spawn = process.start()
        self.addCleanup(process.stop)

        def fake_shortcut_command(*_args, **_kwargs):
            for link in self.links:
                link.write_bytes(b"new synthetic shortcut")
            return SimpleNamespace(returncode=0)

        shell = patch.object(installer.subprocess, "run", side_effect=fake_shortcut_command)
        self.shell = shell.start()
        self.addCleanup(shell.stop)
        native = patch.object(installer.c, "windll", Mock(side_effect=AssertionError("No native")))
        native.start()
        self.addCleanup(native.stop)
        self.addCleanup(self.assert_profile_unchanged)

    def assert_profile_unchanged(self):
        self.assertEqual(
            self.preferences.read_bytes(), b"external profile must remain byte-identical"
        )

    def bundle(self, root=None):
        root = root or self.source
        for relative in (
            "DesktopStats.exe",
            "LICENSE",
            "README.md",
            "THIRD_PARTY_LICENSES.txt",
            "_internal/Qt6Core.dll",
            "source/app.py",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic candidate " + relative).encode())

    def old_install(self):
        self.target.mkdir()
        (self.target / "DesktopStats.exe").write_bytes(b"old executable")
        (self.target / "LICENSE").write_bytes(b"old license")
        (self.target / "source").mkdir()
        (self.target / "source/obsolete.py").write_bytes(b"old owned source")
        (self.target / "personal.txt").write_bytes(b"unrelated user note")
        (self.target / "install-manifest.json").write_text(
            json.dumps(["DesktopStats.exe", "LICENSE", "source/obsolete.py"]), encoding="utf-8"
        )

    def test_nonfrozen_install_refuses_before_touching_installation(self):
        with patch.object(installer.sys, "frozen", False):
            with self.assertRaises(RuntimeError):
                installer.install()
        installer.close_existing.assert_not_called()
        self.assertFalse(self.target.exists())
        self.spawn.assert_not_called()

    def test_source_inside_the_installation_refuses_self_overwrite(self):
        self.bundle(self.target)
        before = (self.target / "DesktopStats.exe").read_bytes()
        with patch.object(installer.sys, "executable", str(self.target / "DesktopStats.exe")):
            with self.assertRaises(RuntimeError):
                installer.install()
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), before)
        installer.close_existing.assert_not_called()
        self.spawn.assert_not_called()

    def test_each_required_bundle_entry_is_mandatory(self):
        self.bundle()
        for relative in (
            "DesktopStats.exe",
            "LICENSE",
            "README.md",
            "THIRD_PARTY_LICENSES.txt",
            "_internal",
            "source",
        ):
            with self.subTest(relative=relative):
                original = self.source / relative
                hidden = self.source / (original.name + ".withheld")
                original.rename(hidden)
                try:
                    with self.assertRaises((RuntimeError, ValueError, FileNotFoundError)):
                        installer.install()
                    self.assertFalse(self.target.exists())
                finally:
                    hidden.rename(original)
        self.spawn.assert_not_called()

    def test_nonempty_unknown_or_invalid_manifest_install_is_refused(self):
        self.bundle()
        self.target.mkdir()
        untouched = self.target / "user-file.txt"
        untouched.write_bytes(b"keep")
        manifest = self.target / "install-manifest.json"
        for content in (None, "not-json", json.dumps({"owned": []}), json.dumps(["../escape"])):
            with self.subTest(content=content):
                if content is not None:
                    manifest.write_text(content, encoding="utf-8")
                with self.assertRaises((RuntimeError, ValueError)):
                    installer.install()
                self.assertEqual(untouched.read_bytes(), b"keep")
                if manifest.exists():
                    manifest.unlink()
        self.spawn.assert_not_called()

    def test_nonplain_old_root_is_refused_before_manifest_read_or_close(self):
        self.bundle()
        self.old_install()
        original_plain = installer._plain
        original_read = Path.read_text

        def reject_old_root(path):
            return False if Path(path) == self.target else original_plain(path)

        def guarded_read(path, *args, **kwargs):
            if path == self.target / "install-manifest.json":
                raise AssertionError("Nonplain old root must not be read")
            return original_read(path, *args, **kwargs)

        with (
            patch.object(installer, "_plain", side_effect=reject_old_root),
            patch.object(Path, "read_text", guarded_read),
        ):
            with self.assertRaisesRegex(RuntimeError, "symbolic link or junction"):
                installer.install()
        installer.close_existing.assert_not_called()
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), b"old executable")
        self.assertFalse(list(self.target.parent.glob(".DesktopStats.stage-*")))
        self.assertFalse(list(self.target.parent.glob(".DesktopStats.backup-*")))
        self.spawn.assert_not_called()

    def test_success_preserves_unknown_files_and_complete_old_tree_backup(self):
        self.bundle()
        self.old_install()
        installer.install()
        self.assertEqual((self.target / "personal.txt").read_bytes(), b"unrelated user note")
        self.assertEqual(
            (self.target / "DesktopStats.exe").read_bytes(),
            (self.source / "DesktopStats.exe").read_bytes(),
        )
        self.assertFalse((self.target / "source/obsolete.py").exists())
        manifest = json.loads((self.target / "install-manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("personal.txt", manifest)
        backups = list(self.target.parent.glob(".DesktopStats.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "DesktopStats.exe").read_bytes(), b"old executable")
        self.assertEqual((backups[0] / "personal.txt").read_bytes(), b"unrelated user note")

    def test_unknown_file_conflict_refuses_without_overwriting_user_data(self):
        self.bundle()
        self.old_install()
        conflict = self.target / "source/app.py"
        conflict.write_bytes(b"user-created conflicting source")
        with self.assertRaises((RuntimeError, ValueError)):
            installer.install()
        self.assertEqual(conflict.read_bytes(), b"user-created conflicting source")
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), b"old executable")
        self.spawn.assert_not_called()

    def test_unknown_file_cannot_be_relocated_inside_a_new_bundle_directory(self):
        self.bundle()
        self.old_install()
        conflict = self.target / "_internal"
        conflict.write_bytes(b"unregistered user file named like a new directory")
        with self.assertRaises((RuntimeError, ValueError, OSError)):
            installer.install()
        self.assertEqual(
            conflict.read_bytes(), b"unregistered user file named like a new directory"
        )
        self.spawn.assert_not_called()

    def test_registration_snapshot_restores_values_and_exact_shortcut_bytes(self):
        original = copy.deepcopy(self.registry.values)
        links = {path: path.read_bytes() for path in self.links}
        snapshot = installer._snapshot_registration((self.desktop, self.programs))
        self.registry.values[installer.REGISTRY]["DisplayVersion"] = ("new", 1)
        self.registry.values[installer.REGISTRY]["DisplayName"] = ("new display name", 1)
        self.registry.values[installer.RUN_KEY]["DesktopStats"] = ("new startup", 1)
        for link in self.links:
            link.write_bytes(b"new shortcut")
        self.assertEqual(installer._restore_registration(snapshot), [])
        self.assertEqual(self.registry.values, original)
        self.assertEqual({path: path.read_bytes() for path in self.links}, links)

    def test_snapshot_restores_previously_missing_registration_and_shortcut(self):
        del self.registry.values[installer.REGISTRY]
        self.registry.values[installer.RUN_KEY].pop("DesktopStats")
        self.links[1].unlink()
        before = copy.deepcopy(self.registry.values)
        snapshot = installer._snapshot_registration((self.desktop, self.programs))
        self.registry.values[installer.REGISTRY] = {"DisplayName": ("new installation", 1)}
        self.registry.values[installer.RUN_KEY]["DesktopStats"] = ("new startup", 1)
        self.links[1].write_bytes(b"newly created shortcut")
        self.assertEqual(installer._restore_registration(snapshot), [])
        self.assertEqual(self.registry.values, before)
        self.assertFalse(self.links[1].exists())

    def test_new_registry_key_with_concurrent_unrelated_value_is_retained_and_reported(self):
        del self.registry.values[installer.RUN_KEY]
        snapshot = installer._snapshot_registration((self.desktop, self.programs))
        self.registry.values[installer.RUN_KEY] = {
            "DesktopStats": ("new startup", 1),
            "Unrelated": ("concurrently added startup", 1),
        }
        errors = installer._restore_registration(snapshot)
        self.assertEqual(
            self.registry.values[installer.RUN_KEY],
            {"Unrelated": ("concurrently added startup", 1)},
        )
        self.assertTrue(errors)
        self.assertIn(installer.RUN_KEY, " ".join(errors))
        self.assertIn("retained", " ".join(errors))

    def test_registration_restore_returns_explicit_errors_and_continues_shortcuts(self):
        before = {path: path.read_bytes() for path in self.links}
        snapshot = installer._snapshot_registration((self.desktop, self.programs))
        for link in self.links:
            link.write_bytes(b"changed shortcut")
        with patch.object(
            self.registry, "SetValueEx", side_effect=PermissionError("Synthetic restore denied")
        ):
            errors = installer._restore_registration(snapshot)
        self.assertTrue(errors)
        self.assertIn("Synthetic restore denied", " ".join(errors))
        self.assertEqual({path: path.read_bytes() for path in self.links}, before)

    def test_stage_copy_failure_keeps_original_and_diagnostic_stage(self):
        self.bundle()
        self.old_install()
        original_copy = installer.shutil.copy2

        def fail_copy(source, destination, *args, **kwargs):
            if Path(source).name == "LICENSE" and Path(destination).parent.name.startswith(
                ".DesktopStats.stage-"
            ):
                raise PermissionError("Synthetic stage copy failure")
            return original_copy(source, destination, *args, **kwargs)

        with (
            patch.object(installer.shutil, "copy2", side_effect=fail_copy),
            patch.object(
                installer.shutil, "rmtree", side_effect=AssertionError("No recursive deletion")
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Synthetic stage copy failure"):
                installer.install()
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), b"old executable")
        stages = list(self.target.parent.glob(".DesktopStats.stage-*"))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / "DesktopStats.exe").is_file())
        self.assertFalse(list(self.target.parent.glob(".DesktopStats.backup-*")))
        self.spawn.assert_not_called()

    def test_atomic_new_tree_rename_failure_restores_original_without_deleting_stage(self):
        self.bundle()
        self.old_install()
        original_rename = Path.rename

        def fail_swap(path, destination):
            if path.name.startswith(".DesktopStats.stage-") and Path(destination) == self.target:
                raise PermissionError("Synthetic atomic swap failure")
            return original_rename(path, destination)

        with (
            patch.object(Path, "rename", fail_swap),
            patch.object(
                installer.shutil, "rmtree", side_effect=AssertionError("No recursive deletion")
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Synthetic atomic swap failure"):
                installer.install()
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), b"old executable")
        self.assertEqual((self.target / "personal.txt").read_bytes(), b"unrelated user note")
        self.assertEqual(len(list(self.target.parent.glob(".DesktopStats.stage-*"))), 1)
        self.shell.assert_not_called()
        self.spawn.assert_not_called()

    def test_registration_failure_rolls_back_tree_registration_and_shortcuts(self):
        self.bundle()
        self.old_install()
        original_registry = copy.deepcopy(self.registry.values)
        original_links = {path: path.read_bytes() for path in self.links}
        self.registry.fail_new_version = True
        with patch.object(
            installer.shutil, "rmtree", side_effect=AssertionError("No recursive deletion")
        ):
            with self.assertRaises((RuntimeError, OSError)):
                installer.install()
        self.assertEqual((self.target / "DesktopStats.exe").read_bytes(), b"old executable")
        self.assertEqual((self.target / "personal.txt").read_bytes(), b"unrelated user note")
        self.assertEqual(self.registry.values, original_registry)
        self.assertEqual({path: path.read_bytes() for path in self.links}, original_links)
        self.spawn.assert_not_called()

    def test_fresh_install_registration_failure_retains_stage_and_restores_absence(self):
        self.bundle()
        self.registry.values.clear()
        for link in self.links:
            link.unlink()
        self.registry.fail_new_version = True
        with patch.object(
            installer.shutil, "rmtree", side_effect=AssertionError("No recursive deletion")
        ):
            with self.assertRaisesRegex(RuntimeError, "Synthetic registration failure"):
                installer.install()
        self.assertFalse(self.target.exists())
        stages = list(self.target.parent.glob(".DesktopStats.stage-*"))
        self.assertEqual(len(stages), 1)
        for relative in (
            "DesktopStats.exe",
            "LICENSE",
            "README.md",
            "THIRD_PARTY_LICENSES.txt",
            "_internal/Qt6Core.dll",
            "source/app.py",
        ):
            self.assertEqual(
                (stages[0] / relative).read_bytes(), (self.source / relative).read_bytes()
            )
        self.assertTrue((stages[0] / "install-manifest.json").is_file())
        self.assertFalse(list(self.target.parent.glob(".DesktopStats.backup-*")))
        self.assertEqual(self.registry.values, {})
        self.assertTrue(all(not link.exists() for link in self.links))
        self.spawn.assert_not_called()

    def test_failed_restore_is_explicit_in_the_reported_exception(self):
        self.bundle()
        self.old_install()
        self.registry.fail_new_version = True
        with patch.object(
            installer, "_restore_registration", return_value=["Synthetic restore failure"]
        ):
            with self.assertRaises(Exception) as raised:
                installer.install()
        self.assertIn(
            "Synthetic restore failure", "".join(traceback.format_exception(raised.exception))
        )

    def test_launch_failure_reports_commit_and_keeps_new_tree_and_old_backup(self):
        self.bundle()
        self.old_install()
        self.spawn.side_effect = PermissionError("Synthetic application launch failure")
        with self.assertRaisesRegex(RuntimeError, "committed, but launch failed"):
            installer.install()
        self.assertEqual(
            (self.target / "DesktopStats.exe").read_bytes(),
            (self.source / "DesktopStats.exe").read_bytes(),
        )
        backups = list(self.target.parent.glob(".DesktopStats.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "DesktopStats.exe").read_bytes(), b"old executable")


class EarlySelfCheckAuditTests(unittest.TestCase):
    def test_empty_self_check_returns_before_profile_qt_ipc_or_logging(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if (
                name == "stats_config"
                or name.startswith("PySide6")
                or name in ("native_ipc", "native_runtime")
            ):
                raise AssertionError("Empty self-check entered normal startup: " + name)
            return original_import(name, *args, **kwargs)

        fake = types.ModuleType("native_selfcheck")
        fake.run = Mock(return_value=2)
        with (
            patch.dict(sys.modules, {"native_selfcheck": fake}),
            patch("sys.argv", ["app.py", "--self-check", ""]),
            patch.object(
                app, "RotatingFileHandler", side_effect=AssertionError("No ordinary logging")
            ),
            patch("builtins.__import__", side_effect=guarded_import),
        ):
            self.assertEqual(app.main(), 2)
        fake.run.assert_called_once_with("")


class FakeClient:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode() + b"\n"
        self.output = bytearray()
        self.properties = {}
        self.disconnected = False

    def property(self, name):
        return self.properties.get(name)

    def setProperty(self, name, value):
        self.properties[name] = value

    def readAll(self):
        value, self.raw = self.raw, b""
        return value

    def write(self, data):
        self.output.extend(data)

    def flush(self):
        pass

    def disconnectFromServer(self):
        self.disconnected = True


class LocalServerCleanQuitAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "native_runtime.py"
        source = ast.parse(path.read_text(encoding="utf-8-sig"))
        server = next(
            node
            for node in source.body
            if isinstance(node, ast.ClassDef) and node.name == "LocalServer"
        )
        method = next(
            node
            for node in server.body
            if isinstance(node, ast.FunctionDef) and node.name == "read"
        )
        cls.method = ast.Module(body=[method], type_ignores=[])

    def setUp(self):
        self.callbacks = []
        self.logger = Mock(spec=logging)
        namespace = dict(
            json=json,
            os=SimpleNamespace(getpid=lambda: 7007),
            logging=self.logger,
            QTimer=SimpleNamespace(
                singleShot=lambda delay, callback: self.callbacks.append((delay, callback))
            ),
        )
        exec(
            compile(self.method, "<actual LocalServer.read; pure fake globals>", "exec"), namespace
        )
        self.read = namespace["read"]
        self.pending = False
        self.runtime = SimpleNamespace(
            controller=SimpleNamespace(dirty=False, version="synthetic"),
            settings=SimpleNamespace(property=lambda name: self.pending, isVisible=lambda: False),
            widgets={},
        )
        self.server = SimpleNamespace(
            runtime=self.runtime, application=SimpleNamespace(quit=Mock())
        )

    def request(self, payload):
        client = FakeClient(payload)
        self.read(self.server, client)
        self.assertTrue(client.disconnected)
        return json.loads(client.output)

    def test_clean_ack_is_written_before_the_queued_quit_callback(self):
        reply = self.request({"command": "quit_if_clean"})
        self.assertEqual(reply, dict(ok=True, quitting=True, dirty=False, pid=7007))
        self.server.application.quit.assert_not_called()
        self.assertEqual(len(self.callbacks), 1)
        self.callbacks[0][1]()
        self.server.application.quit.assert_called_once_with()

    def test_dirty_or_pending_settings_are_refused_without_queueing_quit(self):
        for dirty, pending in ((True, False), (False, True)):
            with self.subTest(dirty=dirty, pending=pending):
                self.runtime.controller.dirty, self.pending = dirty, pending
                reply = self.request({"command": "quit_if_clean"})
                self.assertFalse(reply["ok"])
                self.assertTrue(reply["dirty"])
                self.assertEqual(self.callbacks, [])
                self.server.application.quit.assert_not_called()

    def test_input_entered_after_ack_prevents_queued_quit(self):
        for controller_dirty in (True, False):
            with self.subTest(controller_dirty=controller_dirty):
                self.runtime.controller.dirty = self.pending = False
                self.callbacks.clear()
                self.request({"command": "quit_if_clean"})
                self.runtime.controller.dirty = controller_dirty
                self.pending = not controller_dirty
                self.callbacks[0][1]()
                self.server.application.quit.assert_not_called()

    def test_nonobject_json_commands_are_refused_without_quit_or_callbacks(self):
        for payload in ([], None, "quit_if_clean", 1, True):
            with self.subTest(payload=payload):
                self.logger.reset_mock()
                self.assertFalse(self.request(payload)["ok"])
                self.server.application.quit.assert_not_called()
                self.assertEqual(self.callbacks, [])
                self.logger.exception.assert_called_once_with("Local command rejected")


if __name__ == "__main__":
    unittest.main()
