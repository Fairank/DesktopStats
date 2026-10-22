"""Independent storage teardown audit: synthetic children only, no native or IPC."""

import builtins
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import app
from storage_sensor import SOURCE, StorageHealth


class StorageCleanupAuditTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(__file__).resolve().parents[1]
        temporary_root = workspace / "qa-private"
        temporary_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="storage-audit-", dir=temporary_root)
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(workspace))
        self.addCleanup(self.temp.cleanup)
        self.health = StorageHealth(self.base)
        self.children = []
        native_patch = patch(
            "storage_sensor.c.WinDLL",
            side_effect=AssertionError("Audit must never load a native library"),
            create=True,
        )
        self.native = native_patch.start()
        self.addCleanup(native_patch.stop)
        spawn_patch = patch(
            "storage_sensor.subprocess.Popen",
            side_effect=AssertionError("Audit must never start a real process"),
        )
        self.spawn = spawn_patch.start()
        self.addCleanup(spawn_patch.stop)
        self.addCleanup(self.finish_owned_fakes)

    def finish_owned_fakes(self):
        for child in self.children:
            child.poll.side_effect = None
            child.poll.return_value = 0
            child.kill.side_effect = None
            child.wait.side_effect = None
            child.returncode = 0
        self.health._thread = None
        self.health.close()

    def pending_child(self, *, kill_error=None, wait_error=None):
        child = Mock(returncode=None)
        child.poll.return_value = None
        child.wait.side_effect = wait_error or subprocess.TimeoutExpired("owned-fake", 3)
        child.kill.side_effect = kill_error
        self.children.append(child)
        self.spawn.side_effect = None
        self.spawn.return_value = child
        return child

    def assert_pending_ownership(self, child, folder):
        self.assertIs(self.health._process, child)
        self.assertEqual(self.health._folder, str(folder))
        self.assertTrue(folder.is_dir())
        self.assertEqual(self.health.read()["storage_status"]["state"], "cleanup_pending")

    def test_kill_failure_does_not_escape_or_lose_owned_folder(self):
        child = self.pending_child(kill_error=PermissionError("Synthetic kill denied"))
        self.health._query()
        folder = Path(self.health._folder)
        self.assert_pending_ownership(child, folder)
        self.assertEqual(child.wait.call_args_list, [call(timeout=3)])

        self.health._query()
        self.spawn.assert_called_once()
        self.assert_pending_ownership(child, folder)
        self.assertFalse(self.health.close())
        self.assert_pending_ownership(child, folder)

        child.poll.return_value = 0
        self.assertTrue(self.health.close())
        self.assertIsNone(self.health._process)
        self.assertIsNone(self.health._folder)
        self.assertFalse(folder.exists())
        self.assertEqual(self.health.read()["storage_status"]["state"], "closed")
        self.native.assert_not_called()

    def test_final_wait_timeout_is_nonthrowing_and_blocks_another_spawn(self):
        child = self.pending_child()
        self.health._query()
        folder = Path(self.health._folder)
        self.assert_pending_ownership(child, folder)
        self.assertEqual(child.wait.call_args_list, [call(timeout=3), call(timeout=1)])
        child.kill.assert_called_once_with()

        self.health._query()
        self.assert_pending_ownership(child, folder)
        self.spawn.assert_called_once()
        self.assertEqual(child.wait.call_args_list[-1], call(timeout=1))
        self.assertFalse(self.health.close())
        self.assert_pending_ownership(child, folder)

        child.poll.return_value = -9
        self.assertTrue(self.health.close())
        self.assertIsNone(self.health._process)
        self.assertIsNone(self.health._folder)
        self.assertFalse(folder.exists())

    def test_later_confirmed_exit_cleans_old_folder_before_next_query(self):
        previous = self.pending_child(kill_error=PermissionError("Synthetic kill denied"))
        self.health._query()
        old_folder = Path(self.health._folder)
        previous.poll.return_value = 0
        current = Mock(returncode=0)
        current.poll.return_value = 0
        self.children.append(current)

        def recovered_spawn(command, **options):
            self.assertFalse(old_folder.exists())
            self.assertIsNone(self.health._process)
            Path(command[-1]).write_text(
                json.dumps(
                    dict(
                        schema=1,
                        provider=SOURCE,
                        timestamp=time.time(),
                        state="ready",
                        storages={
                            "1": dict(
                                state="available",
                                storage_temp=29.85,
                                storage_spare_percent=100,
                                storage_wear_percent=0,
                            )
                        },
                    )
                ),
                encoding="utf-8",
            )
            return current

        self.spawn.side_effect = recovered_spawn
        self.health._query()
        self.assertEqual(self.spawn.call_count, 2)
        self.assertIsNone(self.health._process)
        self.assertIsNone(self.health._folder)
        self.assertEqual(self.health.read()["storage_status"]["state"], "ready")
        self.assertEqual(self.health.read()["storages"]["1"]["storage_wear_percent"], 0)

    def test_poll_failure_retains_process_and_folder_without_throwing(self):
        child = self.pending_child(kill_error=PermissionError("Synthetic kill denied"))
        self.health._query()
        folder = Path(self.health._folder)
        child.poll.side_effect = OSError("Synthetic process status failure")
        kills_before = child.kill.call_count

        self.assertFalse(self.health._retire_owned())
        self.assert_pending_ownership(child, folder)
        self.assertFalse(self.health.close())
        self.health._query()
        self.spawn.assert_called_once()
        self.assertEqual(child.kill.call_count, kills_before)

        child.poll.side_effect = None
        child.poll.return_value = 0
        self.assertTrue(self.health.close())
        self.assertFalse(folder.exists())

    def test_returning_from_wait_does_not_replace_exit_confirmation(self):
        child = self.pending_child(kill_error=PermissionError("Synthetic kill denied"))
        self.health._query()
        folder = Path(self.health._folder)
        child.kill.side_effect = None
        child.wait.side_effect = None
        child.wait.return_value = 0
        # This deliberately inconsistent fake proves poll-confirmed ownership.
        self.assertFalse(self.health._retire_owned())
        self.assert_pending_ownership(child, folder)
        self.assertIn("has not exited", self.health.read()["storage_status"]["detail"])

    def test_failed_folder_cleanup_blocks_spawn_after_child_exit(self):
        child = self.pending_child(kill_error=PermissionError("Synthetic kill denied"))
        self.health._query()
        folder = Path(self.health._folder)
        child.poll.return_value = 0

        with patch("storage_sensor.shutil.rmtree", side_effect=PermissionError("Busy reply file")):
            self.assertFalse(self.health._retire_owned())
            self.assertIsNone(self.health._process)
            self.assertEqual(self.health._folder, str(folder))
            self.assertTrue(folder.exists())
            self.health._query()
            self.spawn.assert_called_once()
            self.assertFalse(self.health.close())
            self.assertEqual(self.health.read()["storage_status"]["state"], "cleanup_pending")

        self.assertTrue(self.health.close())
        self.assertIsNone(self.health._folder)
        self.assertFalse(folder.exists())

    def test_cleanup_rejects_paths_outside_the_exact_owned_probe_parent(self):
        for target in (
            self.base / "owned-other",
            self.base / "storage-probes",
            self.base / "storage-probes" / "unowned",
            self.base / "storage-probes" / "nested" / "owned-child",
        ):
            with self.subTest(target=target):
                self.health._folder = str(target)
                with patch("storage_sensor.shutil.rmtree") as remove:
                    self.assertFalse(self.health._retire_owned())
                    self.assertEqual(self.health._folder, str(target))
                    remove.assert_not_called()
        self.health._folder = None

    def test_live_worker_thread_prevents_successful_close_and_later_can_recover(self):
        worker = Mock()
        worker.is_alive.return_value = True
        self.health._thread = worker
        self.assertFalse(self.health.close())
        worker.join.assert_called_once_with(timeout=4.5)
        self.assertEqual(self.health.read()["storage_status"]["state"], "closing")
        self.assertFalse(self.health._closed)
        self.spawn.assert_not_called()

        worker.is_alive.return_value = False
        self.assertTrue(self.health.close())
        self.assertTrue(self.health._closed)
        self.assertEqual(self.health.read()["storage_status"]["state"], "closed")


class StorageCliAuditTests(unittest.TestCase):
    def test_explicit_empty_storage_option_always_returns_before_normal_startup(self):
        original_import = builtins.__import__

        def guard_import(name, *args, **kwargs):
            if name.startswith("PySide6") or name in ("native_ipc", "native_runtime", "installer"):
                raise AssertionError("Worker option reached normal startup import: " + name)
            return original_import(name, *args, **kwargs)

        for arguments in (("--storage-read", ""), ("--storage-read=",)):
            with self.subTest(arguments=arguments):
                with (
                    patch("sys.argv", ["app.py", *arguments]),
                    patch("storage_sensor.worker_main", return_value=2) as worker,
                    patch(
                        "app.RotatingFileHandler",
                        side_effect=AssertionError("Worker option reached ordinary logging"),
                    ) as log,
                    patch("builtins.__import__", side_effect=guard_import),
                ):
                    self.assertEqual(app.main(), 2)
                    worker.assert_called_once_with("")
                    log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
