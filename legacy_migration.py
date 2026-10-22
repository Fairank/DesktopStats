"""Retire only this application's previous renderer; retain other Rainmeter skins."""

import json
import logging
import os
import subprocess
import time
import winreg
from pathlib import Path
from urllib.request import Request, urlopen

from stats_config import BASE, ORDER


def stop_web_version():
    try:
        with urlopen("http://127.0.0.1:8776/api/health", timeout=0.5) as response:
            if json.load(response).get("app") != "desktop-stats":
                return
        with urlopen("http://127.0.0.1:8776/api/config", timeout=2) as response:
            token = json.load(response)["token"]
        with urlopen(
            Request(
                "http://127.0.0.1:8776/api/exit",
                data=b"{}",
                headers={"X-Stats-Token": token, "Content-Type": "application/json"},
            ),
            timeout=8,
        ):
            pass
        time.sleep(0.5)
    except (OSError, ValueError, KeyError):
        pass


def retire_rainmeter():
    marker = BASE / "native-migration.json"
    if marker.exists():
        return
    rainmeter = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Rainmeter/Rainmeter.exe"
    )
    backup = BASE / "dpi-compat.before.json"
    if not backup.exists() and not (BASE / "skin").exists():
        marker.write_text('{"retired":true}', encoding="ascii")
        return
    if rainmeter.exists():
        for key in ORDER + ["Group"]:
            subprocess.run(
                [str(rainmeter), "!DeactivateConfig", "DesktopStats\\" + key],
                creationflags=0x08000000,
                timeout=8,
                capture_output=True,
            )
    if backup.exists():
        saved = json.loads(backup.read_text(encoding="utf-8"))
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
        ) as key:
            try:
                current = winreg.QueryValueEx(key, str(rainmeter))[0]
                if current == saved.get("applied", "~ HIGHDPIAWARE"):
                    if saved["value"] is None:
                        winreg.DeleteValue(key, str(rainmeter))
                    else:
                        winreg.SetValueEx(key, str(rainmeter), 0, winreg.REG_SZ, saved["value"])
            except FileNotFoundError:
                pass
        backup.unlink(missing_ok=True)
    marker.write_text('{"retired":true}', encoding="ascii")


def migrate():
    stop_web_version()
    try:
        retire_rainmeter()
    except Exception:
        logging.exception("Previous renderer retirement failed")
