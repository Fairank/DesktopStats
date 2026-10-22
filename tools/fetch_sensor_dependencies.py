"""Fetch only the pinned collector DLLs for local development; never execute them."""

import argparse
import hashlib
import json
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = "third_party/librehardwaremonitor/0.9.6"
MANIFEST_SHA256 = "7fa0fdefcf4f23a555521bc228a6e3cd940c0b67e7c692d0702cc96e600682f4"
ASSET_URL = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip"
ASSET_SHA256 = "086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001"
MAX_DOWNLOAD = 64 * 1024 * 1024


def checked(path):
    """Refuse symlinks/junctions in a dependency path before reading or writing."""
    current = Path(path).absolute()
    for part in (current, *current.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Dependency paths cannot contain links or reparse points")
    return current


def manifest(root):
    directory = checked(Path(root) / DEPENDENCIES)
    content = checked(directory / "manifest.json").read_bytes()
    if hashlib.sha256(content).hexdigest() != MANIFEST_SHA256:
        raise ValueError("The reviewed dependency manifest changed")
    value = json.loads(content)
    if value["release_asset_url"] != ASSET_URL or value["release_asset_sha256"] != ASSET_SHA256:
        raise ValueError("Unexpected dependency release")
    return directory, value


def missing_files(directory, rows):
    missing = []
    for row in rows:
        name = row["name"]
        if PurePosixPath(name).name != name or not name.endswith(".dll"):
            raise ValueError("Unexpected dependency filename")
        target = directory / name
        if target.exists() or target.is_symlink():
            content = checked(target).read_bytes()
            if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError("Existing dependency differs; inspect it before replacing: " + name)
        else:
            missing.append(row)
    return missing


def install_from_archive(archive, *, root=ROOT):
    directory, data = manifest(root)
    missing = missing_files(directory, data["files"])
    archive = checked(archive)
    if archive.stat().st_size > MAX_DOWNLOAD or hashlib.sha256(archive.read_bytes()).hexdigest() != ASSET_SHA256:
        raise ValueError("Official release archive hash mismatch")
    payloads = {}
    with zipfile.ZipFile(archive) as source:
        for row in missing:
            for entry in source.infolist():
                if PurePosixPath(entry.filename).name != row["name"] or entry.file_size != row["bytes"]:
                    continue
                content = source.read(entry)
                if hashlib.sha256(content).hexdigest() == row["sha256"]:
                    payloads[row["name"]] = content
                    break
            else:
                raise ValueError("Pinned library absent from official archive: " + row["name"])
    # Validate the complete archive and every DLL before any library is written.
    for name, content in payloads.items():
        checked(directory)
        with (directory / name).open("xb") as stream:
            stream.write(content)
    return len(payloads)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use an already downloaded official release ZIP")
    args = parser.parse_args()
    directory, data = manifest(ROOT)
    if not missing_files(directory, data["files"]):
        print("All nine pinned libraries are already verified; no download or execution.")
        return 0
    if args.archive:
        count = install_from_archive(args.archive)
    else:
        scratch = ROOT / "qa-private" / "dependency-downloads"
        scratch.mkdir(parents=True, exist_ok=True)
        checked(scratch)
        with tempfile.TemporaryDirectory(prefix="official-", dir=scratch) as temporary:
            archive = Path(temporary) / "LibreHardwareMonitor.zip"
            request = urllib.request.Request(ASSET_URL, headers={"User-Agent": "DesktopStats-dependency-setup"})
            with urllib.request.urlopen(request, timeout=30) as response, archive.open("xb") as target:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > MAX_DOWNLOAD:
                        raise ValueError("Official archive exceeded the allowed download size")
                    target.write(block)
            count = install_from_archive(archive)
    print(f"Prepared {count} pinned libraries. No downloaded code was executed; build the original collector separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
