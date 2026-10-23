"""Per-user native application installation; keep preferences and unrelated files."""

import ctypes as c
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import winreg
from pathlib import Path

from product_version import VERSION

DIRECTORY = Path(os.environ["LOCALAPPDATA"]) / "Programs/DesktopStats"
REGISTRY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DesktopStats"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def shell_folder(kind):
    result = c.create_unicode_buffer(32768)
    if c.windll.shell32.SHGetFolderPathW(None, kind, None, 0, result):
        raise OSError("Windows folder unavailable")
    return Path(result.value)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def startup_command(executable=None):
    if executable is not None or getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(executable or sys.executable), "--background"])
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = str(pythonw if pythonw.exists() else sys.executable)
    return subprocess.list2cmdline(
        [interpreter, str(Path(__file__).with_name("app.py")), "--background"]
    )


def set_autostart(enabled, executable=None):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, "DesktopStats", 0, winreg.REG_SZ, startup_command(executable))
        else:
            try:
                winreg.DeleteValue(key, "DesktopStats")
            except FileNotFoundError:
                pass


class _ProcessExitWaiter:
    """Retain one process identity until its kernel object confirms termination."""

    def __init__(self, pid):
        kernel = c.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [c.c_ulong, c.c_int, c.c_ulong]
        kernel.OpenProcess.restype = c.c_void_p
        kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_ulong]
        kernel.WaitForSingleObject.restype = c.c_ulong
        kernel.CloseHandle.argtypes = [c.c_void_p]
        kernel.CloseHandle.restype = c.c_int
        self.kernel = kernel
        self.handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only.
        if not self.handle:
            raise OSError(c.get_last_error(), "Could not retain the running application process")

    def exited(self):
        result = self.kernel.WaitForSingleObject(self.handle, 0)
        if result == 0:
            return True
        if result == 258:
            return False
        raise OSError(c.get_last_error(), "Could not confirm application process termination")

    def close(self):
        if self.handle:
            if not self.kernel.CloseHandle(self.handle):
                raise OSError(c.get_last_error(), "Could not close application process wait handle")
            self.handle = None


def _valid_status(status):
    return (
        isinstance(status, dict)
        and status.get("ok") is True
        and status.get("native") is True
        and type(status.get("dirty")) is bool
        and type(status.get("pid")) is int
        and 0 < status["pid"] <= 0xFFFFFFFF
    )


def close_existing():
    from native_ipc import send

    status = send({"command": "status"}, timeout=1200)
    if status is None:
        if _server_absent():
            return
        raise RuntimeError("无法确认当前软件已关闭；请手动退出 Desktop Stats 后重试。")
    if not _valid_status(status):
        raise RuntimeError("当前软件未提供可靠状态；请手动退出 Desktop Stats 后重试。")
    if status["dirty"]:
        raise RuntimeError("当前软件有未应用的设置，请先应用或撤销，再手动退出。")
    process = _ProcessExitWaiter(status["pid"])
    try:
        if process.exited():
            raise RuntimeError("当前软件进程已改变；请重新运行安装。")
        # Reconfirm the pipe's live instance while holding its process object.
        # A disappeared/reused PID or new unsaved input must fail closed.
        current = send({"command": "status"}, timeout=1200)
        if (not _valid_status(current) or current["pid"] != status["pid"]
                or current["dirty"] or process.exited()):
            raise RuntimeError("当前软件实例或设置已改变；请手动退出后重试。")
        reply = send({"command": "quit_if_clean"}, timeout=1200)
        if (
            not isinstance(reply, dict)
            or reply.get("ok") is not True
            or reply.get("quitting") is not True
            or reply.get("dirty") is not False
            or type(reply.get("pid")) is not int
            or reply.get("pid") != status["pid"]
        ):
            raise RuntimeError("当前版本不能安全自动退出；请手动退出 Desktop Stats 后重试。")
        for _ in range(20):
            time.sleep(0.25)
            if (send({"command": "status"}, timeout=150) is None
                    and _server_absent() and process.exited()):
                return
        raise RuntimeError("软件仍在运行，安装尚未开始；请手动退出后重试。")
    finally:
        process.close()


def _server_absent():
    """Distinguish a missing own pipe from timeout/malformed IPC, without commands."""
    from PySide6.QtNetwork import QLocalSocket

    from native_ipc import name

    socket = QLocalSocket()
    try:
        socket.connectToServer(name())
        if socket.waitForConnected(250):
            return False
        return socket.error() == QLocalSocket.LocalSocketError.ServerNotFoundError
    finally:
        socket.abort()


def owned_files():
    try:
        value = json.loads((DIRECTORY / "install-manifest.json").read_text(encoding="utf-8"))
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, str):
                continue
            relative = Path(item)
            candidate = DIRECTORY / relative
            if (
                not relative.is_absolute()
                and ".." not in relative.parts
                and candidate.resolve().is_relative_to(DIRECTORY.resolve())
            ):
                result.append(candidate)
        return result
    except (OSError, ValueError):
        return []


BUNDLE_PARTS = (
    "DesktopStats.exe",
    "LICENSE",
    "NOTICE",
    "LICENSING.md",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "THIRD_PARTY_LICENSES.txt",
    "README.md",
    "_internal",
    "source",
)
UNINSTALL_VALUES = (
    "DisplayName",
    "DisplayVersion",
    "Publisher",
    "InstallLocation",
    "DisplayIcon",
    "UninstallString",
    "NoModify",
    "NoRepair",
)


def _plain(path):
    return not path.is_symlink() and not getattr(path, "is_junction", lambda: False)()


def _files(root):
    """Bounded tree walk, rejecting reparse paths before descending or copying."""
    resolved = root.resolve()
    if not _plain(root):
        raise RuntimeError("Installation trees cannot be symbolic links or junctions")
    result, directories = {}, []
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in [*folders, *files]:
            path = Path(directory) / name
            if not _plain(path) or not path.resolve().is_relative_to(resolved):
                raise RuntimeError(
                    "Installation tree contains a link or escaped path: " + str(path)
                )
            relative = path.relative_to(root)
            if path.is_dir():
                directories.append(relative)
            elif path.is_file():
                result[relative] = path
            else:
                raise RuntimeError("Installation tree contains a non-regular file")
    return result, directories


def _old_manifest(root):
    if not _plain(root):
        raise RuntimeError("Existing installation cannot be a symbolic link or junction")
    if not root.exists() or not any(root.iterdir()):
        return set()
    try:
        manifest = json.loads((root / "install-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("现有安装清单缺失或损坏；原文件未更改，请先手动备份并检查。") from error
    if not isinstance(manifest, list):
        raise RuntimeError("Invalid existing installation manifest")
    result = set()
    for name in manifest:
        if not isinstance(name, str) or not name:
            raise RuntimeError("Invalid installation manifest entry")
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative == Path(".")
            or not (root / relative).resolve().is_relative_to(root.resolve())
        ):
            raise RuntimeError("Installation manifest escapes the original directory")
        key = relative.as_posix().casefold()
        if key in result:
            raise RuntimeError("Duplicate installation manifest entry")
        result.add(key)
    return result


def _bundle_files(source):
    selected, directories = {}, []
    for name in BUNDLE_PARTS:
        path = source / name
        if not path.exists() or not _plain(path):
            raise RuntimeError("Release bundle is incomplete: " + name)
        if name in ("_internal", "source") and not path.is_dir():
            raise RuntimeError("Release bundle directory is invalid: " + name)
        if name not in ("_internal", "source") and not path.is_file():
            raise RuntimeError("Release bundle file is invalid: " + name)
        if path.is_dir():
            nested, nested_directories = _files(path)
            selected.update({Path(name) / relative: file for relative, file in nested.items()})
            directories.extend(
                [Path(name), *(Path(name) / relative for relative in nested_directories)]
            )
        else:
            selected[Path(name)] = path
    folded = [path.as_posix().casefold() for path in selected]
    if len(folded) != len(set(folded)):
        raise RuntimeError("Release bundle contains case-colliding paths")
    return selected, directories


def _sibling(kind):
    if not DIRECTORY.is_absolute() or not _plain(DIRECTORY):
        raise RuntimeError("Unexpected installation target")
    parent = DIRECTORY.parent.resolve()
    if DIRECTORY.resolve().parent != parent:
        raise RuntimeError("Installation target escaped its parent")
    result = parent / ("." + DIRECTORY.name + "." + kind + "-" + uuid.uuid4().hex)
    if result.exists() or result.resolve().parent != parent:
        raise RuntimeError("Unexpected installation transaction path")
    return result


def _verify_transaction_paths(stage, backup):
    parent = DIRECTORY.parent.resolve()
    if any(
        not _plain(path) or path.resolve().parent != parent for path in (DIRECTORY, stage, backup)
    ):
        raise RuntimeError("Installation transaction escaped its intended parent")


def _snapshot_registration(folders):
    registry = {}
    for location, names in ((REGISTRY, UNINSTALL_VALUES), (RUN_KEY, ("DesktopStats",))):
        values, existed = {}, True
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, location) as key:
                for name in names:
                    try:
                        values[name] = winreg.QueryValueEx(key, name)
                    except FileNotFoundError:
                        values[name] = None
        except FileNotFoundError:
            existed, values = False, dict.fromkeys(names)
        registry[location] = dict(existed=existed, values=values)
    links = {}
    for folder in folders:
        link = folder / "Desktop Stats.lnk"
        if not _plain(link) or link.exists() and not link.is_file():
            raise RuntimeError("Shortcut path is not a regular owned filename")
        links[link] = link.read_bytes() if link.exists() else None
    return dict(registry=registry, links=links)


def _restore_registration(snapshot):
    errors = []
    for location, before in snapshot["registry"].items():
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, location) as key:
                for name, value in before["values"].items():
                    if value is None:
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
                    else:
                        winreg.SetValueEx(key, name, 0, value[1], value[0])
            if not before["existed"]:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, location) as key:
                    subkeys, values, _modified = winreg.QueryInfoKey(key)
                if subkeys or values:
                    raise RuntimeError(
                        "New registry key has unowned data; retained during rollback"
                    )
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, location)
        except Exception as error:
            errors.append("registry " + location + ": " + str(error))
    for path, value in snapshot["links"].items():
        try:
            if not _plain(path):
                raise RuntimeError("Shortcut changed into a link during rollback")
            if value is None:
                path.unlink(missing_ok=True)
            else:
                temporary = path.with_name(path.name + ".restore-" + uuid.uuid4().hex)
                with temporary.open("xb") as file:
                    file.write(value)
                temporary.replace(path)
        except Exception as error:
            errors.append("shortcut " + str(path) + ": " + str(error))
    return errors


def _write_registration(target, folders):
    script = "$ErrorActionPreference='Stop';$shell=New-Object -ComObject WScript.Shell;"
    for folder in folders:
        script += f"$link=$shell.CreateShortcut({ps_quote(folder / 'Desktop Stats.lnk')});$link.TargetPath={ps_quote(target)};$link.WorkingDirectory={ps_quote(DIRECTORY)};$link.IconLocation={ps_quote(str(target) + ',0')};$link.Save();"
    powershell = Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        creationflags=0x08000000,
    )
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY) as key:
        for name, value in {
            "DisplayName": "Desktop Stats",
            "DisplayVersion": VERSION,
            "Publisher": "Fairank",
            "InstallLocation": str(DIRECTORY),
            "DisplayIcon": str(target),
            "UninstallString": '"' + str(target) + '" --uninstall',
        }.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)
    from stats_config import load

    set_autostart(load()["autostart"], target)


def install():
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Use the packaged DesktopStats.exe to install")
    source_root = Path(sys.executable).parent.resolve()
    if source_root == DIRECTORY.resolve() or source_root.is_relative_to(DIRECTORY.resolve()):
        raise RuntimeError("请从解压后的新发布包运行安装，不能覆盖当前正在执行的安装目录。")
    files, directories = _bundle_files(source_root)
    old_owned = _old_manifest(DIRECTORY)
    close_existing()
    DIRECTORY.parent.mkdir(parents=True, exist_ok=True)
    stage, backup = _sibling("stage"), _sibling("backup")
    stage.mkdir()
    moved_old = moved_new = registration_started = False
    snapshot = None
    try:
        for relative in directories:
            (stage / relative).mkdir(parents=True, exist_ok=True)
        for relative, file in files.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        new_owned = {path.as_posix().casefold() for path in files}
        if DIRECTORY.exists():
            originals, original_directories = _files(DIRECTORY)
            for relative, file in originals.items():
                key = relative.as_posix().casefold()
                if key in old_owned or key == "install-manifest.json":
                    continue
                target = stage / relative
                if key in new_owned or target.exists():
                    raise RuntimeError("新发布文件与未登记的用户文件冲突：" + str(relative))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
            for relative in original_directories:
                target = stage / relative
                if target.exists() and not target.is_dir():
                    raise RuntimeError("新发布文件与原有目录冲突：" + str(relative))
                if not target.exists():
                    target.mkdir(parents=True)
        (stage / "install-manifest.json").write_text(
            json.dumps(sorted(path.as_posix() for path in files)), encoding="utf-8"
        )
        # Copying the bundle can take time. A user may have reopened the old
        # app meanwhile; confirm clean termination before snapshot or swap.
        close_existing()
        folders = tuple(dict.fromkeys((shell_folder(0x10), shell_folder(2))))
        snapshot = _snapshot_registration(folders)
        # These are same-parent, verified transaction paths. No tree is deleted.
        _verify_transaction_paths(stage, backup)
        if DIRECTORY.exists():
            DIRECTORY.rename(backup)
            moved_old = True
        _verify_transaction_paths(stage, backup)
        stage.rename(DIRECTORY)
        moved_new = True
        registration_started = True
        _write_registration(DIRECTORY / "DesktopStats.exe", folders)
    except Exception as error:
        rollback_errors = _restore_registration(snapshot) if registration_started else []
        try:
            _verify_transaction_paths(stage, backup)
            if moved_new:
                if stage.exists():
                    raise RuntimeError("Diagnostic stage path unexpectedly exists")
                DIRECTORY.rename(stage)
            if moved_old:
                _verify_transaction_paths(stage, backup)
                backup.rename(DIRECTORY)
        except Exception as rollback_error:
            rollback_errors.append("file tree: " + str(rollback_error))
        detail = (
            "; rollback incomplete: " + "; ".join(rollback_errors)
            if rollback_errors
            else "; original installation restored or unchanged"
        )
        raise RuntimeError(
            "Installation failed: "
            + str(error)
            + detail
            + "; diagnostic stage="
            + str(stage)
            + "; backup="
            + str(backup)
        ) from error
    # The backup remains recoverable. Starting the committed build is separate
    # from the transaction: launch failure must not claim installation rollback.
    target = DIRECTORY / "DesktopStats.exe"
    try:
        subprocess.Popen([str(target)], creationflags=0x08000000)
    except Exception as error:
        raise RuntimeError(
            "Installation committed, but launch failed; backup=" + str(backup)
        ) from error


def remove_registration():
    set_autostart(False)
    for folder in (shell_folder(0x10), shell_folder(2)):
        link = folder / "Desktop Stats.lnk"
        if link.exists():
            link.unlink()
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY)
    except FileNotFoundError:
        pass
    # Resolve every owned path before scheduling any deletion. Never recurse
    # over the installation directory, which may contain unrelated user files.
    expected = Path(os.environ["LOCALAPPDATA"]) / "Programs/DesktopStats"
    if DIRECTORY.resolve() != expected.resolve():
        raise RuntimeError("Unexpected install path")
    targets = owned_files()
    targets += [
        DIRECTORY / name
        for name in (
            "DesktopStats.exe",
            "LICENSE",
            "THIRD_PARTY_LICENSES.txt",
            "install-manifest.json",
        )
    ]
    targets = sorted(set(path.resolve() for path in targets))
    if any(not path.is_relative_to(expected.resolve()) for path in targets):
        raise RuntimeError("Unexpected uninstall file")
    folders = {
        parent
        for target in targets
        for parent in target.parents
        if parent.is_relative_to(expected.resolve())
    }
    cleanup = DIRECTORY / "uninstall-files.json"
    targets.append(cleanup)
    cleanup.write_text(
        json.dumps(
            {
                "files": [str(item) for item in targets],
                "folders": [
                    str(item)
                    for item in sorted(folders, key=lambda item: len(item.parts), reverse=True)
                ],
            }
        ),
        encoding="utf-8-sig",
    )
    script = (
        "Start-Sleep -Seconds 2;$ErrorActionPreference='SilentlyContinue';"
        f"$taskRoot={ps_quote(expected.resolve())};"
        f"$taskJobs=Get-Content -LiteralPath {ps_quote(cleanup)} -Raw | ConvertFrom-Json;"
        "$taskPrefix=$taskRoot+'\\';"
        "foreach($taskFile in $taskJobs.files){"
        "$taskFull=[IO.Path]::GetFullPath($taskFile);"
        "if($taskFull.StartsWith($taskPrefix,[StringComparison]::OrdinalIgnoreCase)){"
        "Remove-Item -LiteralPath $taskFull -Force}};"
        "foreach($taskFolder in $taskJobs.folders){"
        "$taskFull=[IO.Path]::GetFullPath($taskFolder);"
        "if(($taskFull -eq $taskRoot -or $taskFull.StartsWith($taskPrefix,[StringComparison]::OrdinalIgnoreCase)) "
        "-and -not (Get-ChildItem -LiteralPath $taskFull -Force)){Remove-Item -LiteralPath $taskFull}}"
    )
    powershell = Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.Popen(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        creationflags=0x08000000,
    )
