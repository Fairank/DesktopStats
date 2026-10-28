"""Read-only profile selection and identity; no creation, migration or fallback on errors."""

import hashlib
import json
import os
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_SIDECAR_BYTES = 16 * 1024
POINTER_NAME = "profile-location.json"
MARKER_NAME = ".desktopstats-profile.json"


class ProfilePathError(RuntimeError):
    """Invalid explicit installed profile; messages intentionally omit paths."""


@dataclass(frozen=True)
class ProfilePaths:
    directory: Path
    source: str
    profile_id: str | None
    storage_fingerprint: str | None
    ipc_key: str

    def status(self):
        return dict(source=self.source, profile_id=self.profile_id,
                    storage_fingerprint=self.storage_fingerprint)


def _identity(info):
    return info.st_dev, info.st_ino


def _fingerprint(info):
    if not stat.S_ISDIR(info.st_mode) or not info.st_ino:
        return None
    raw = json.dumps([1, int(info.st_dev), int(info.st_ino)], separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _observed_fingerprint(directory):
    try:
        return _fingerprint(directory.stat())
    except OSError:
        return None


def _no_links(path, label):
    """Inspect lexical components first; resolve() must not hide a redirection."""
    result = None
    try:
        for part in reversed((path, *path.parents)):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ProfilePathError(label + " contains a link or reparse point")
            if part != path and not stat.S_ISDIR(info.st_mode):
                raise ProfilePathError(label + " has a non-directory ancestor")
            result = info
    except OSError:
        raise ProfilePathError(label + " is missing or cannot be inspected") from None
    return result


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ProfilePathError("Profile sidecar has duplicate JSON fields")
        value[key] = item
    return value


def _sidecar(path, label):
    before = _no_links(path, label)
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SIDECAR_BYTES:
        raise ProfilePathError(label + " must be a bounded regular file")
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _identity(opened) != _identity(before):
                raise ProfilePathError(label + " changed before reading")
            raw = stream.read(MAX_SIDECAR_BYTES + 1)
            after_read = os.fstat(stream.fileno())
        after = _no_links(path, label)
        def signature(info):
            return _identity(info), info.st_size, info.st_mtime_ns

        if (len(raw) > MAX_SIDECAR_BYTES or signature(before) != signature(opened)
                or signature(opened) != signature(after_read) or signature(after_read) != signature(after)):
            raise ProfilePathError(label + " changed while reading")
        result = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise ProfilePathError(label + " cannot be read as bounded UTF-8 JSON") from None
    if not isinstance(result, dict) or type(result.get("schema")) is not int or result["schema"] != 1:
        raise ProfilePathError(label + " has an unsupported schema")
    return result


def _profile_id(value, label):
    if not isinstance(value, str) or len(value) != 36:
        raise ProfilePathError(label + " has an invalid profile UUID")
    try:
        result = str(uuid.UUID(value))
    except ValueError:
        raise ProfilePathError(label + " has an invalid profile UUID") from None
    if result != value.lower():
        raise ProfilePathError(label + " has a noncanonical profile UUID")
    return result


def _directory(value, user):
    if not isinstance(value, str) or not value or value.startswith(("\\\\", "//")):
        raise ProfilePathError("Profile directory must be an absolute local path")
    if any(ord(character) < 32 or ord(character) == 127 or 0xD800 <= ord(character) <= 0xDFFF
           for character in value):
        raise ProfilePathError("Profile directory has invalid path characters")
    path = Path(value)
    parts = value.replace("\\", "/").split("/")
    if (not path.is_absolute() or any(part in (".", "..") or part.endswith((".", " ")) for part in parts if part)
            or any(":" in part for part in path.parts[1:])):
        raise ProfilePathError("Profile directory must be a canonical absolute local path")
    if path.name.casefold() not in ("desktopstats", ".desktopstats"):
        raise ProfilePathError("Profile directory must be a dedicated DesktopStats directory")
    if not user.is_absolute() or path == user or not path.is_relative_to(user):
        raise ProfilePathError("Profile directory is outside this USERPROFILE")
    user_info = _no_links(user, "USERPROFILE")
    info = _no_links(path, "Profile directory")
    if not stat.S_ISDIR(user_info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ProfilePathError("Profile directory or USERPROFILE is not a directory")
    try:
        if path.resolve(strict=True) != path or user.resolve(strict=True) != user:
            raise ProfilePathError("Profile directory has an unexpected storage redirect")
    except (OSError, RuntimeError):
        raise ProfilePathError("Profile directory cannot be resolved") from None
    if _fingerprint(info) is None:
        raise ProfilePathError("Profile directory storage identity is unavailable")
    return path, info


def resolve_profile_paths(*, environ=None, frozen=None, executable=None, home=None):
    """Return selected paths without writing, creating or migrating anything.

    USERPROFILE containment is checked; this is not an NTFS ACL ownership audit.
    Explicit data overrides retain their old Path spelling and IPC isolation.
    """
    env = os.environ if environ is None else environ
    if "DESKTOP_STATS_DATA" in env:
        directory = Path(env["DESKTOP_STATS_DATA"])
        return ProfilePaths(directory, "environment", None, _observed_fingerprint(directory), str(directory))
    user = Path(env.get("USERPROFILE", home if home is not None else Path.home()))
    ipc_key = str(user / "AppData" / "Local" / "DesktopStats")
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if packaged:
        pointer = Path(sys.executable if executable is None else executable).absolute().parent / POINTER_NAME
        try:
            pointer.lstat()
        except FileNotFoundError:
            _no_links(pointer.parent, "Installed application directory")
            pass  # Only genuine absence retains legacy behavior; dangling links do not.
        except OSError:
            raise ProfilePathError("Installed profile pointer cannot be inspected") from None
        else:
            selected = _sidecar(pointer, "Installed profile pointer")
            if set(selected) != {"schema", "profile_id", "directory"}:
                raise ProfilePathError("Installed profile pointer has unexpected fields")
            profile_id = _profile_id(selected["profile_id"], "Installed profile pointer")
            if "USERPROFILE" not in env:
                raise ProfilePathError("Installed profile pointer requires USERPROFILE")
            directory, info = _directory(selected["directory"], user)
            marker = _sidecar(directory / MARKER_NAME, "Profile identity marker")
            if set(marker) != {"schema", "profile_id"} or _profile_id(marker.get("profile_id"), "Profile identity marker") != profile_id:
                raise ProfilePathError("Profile identity marker does not match installed pointer")
            final = _no_links(directory, "Profile directory")
            if _identity(final) != _identity(info):
                raise ProfilePathError("Profile directory identity changed during selection")
            return ProfilePaths(directory, "installed_pointer", profile_id, _fingerprint(final), ipc_key)
    directory = Path(env.get("LOCALAPPDATA", home if home is not None else Path.home())) / "DesktopStats"
    return ProfilePaths(directory, "legacy_default", None, _observed_fingerprint(directory), ipc_key)
