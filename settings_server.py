"""Loopback settings panel and the controller for our own Rainmeter widgets."""

import argparse
import configparser
import json
import logging
import os
import secrets
import shutil
import subprocess
import threading
import time
import winreg
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import sensors
from build_modular import ROOT, build, display_scale, skin_path
from localization import LANGUAGES
from localization import metadata as localized_metadata
from metrics import METRICS
from presets import catalogue as preset_catalogue
from stats_config import ASSETS, BASE, DEFAULT, MODULES, ORDER, SKINS, load, save, validate

RAINMETER = Path(
    os.environ.get(
        "DESKTOP_STATS_RAINMETER",
        str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Rainmeter/Rainmeter.exe"),
    )
)
SETTINGS = Path(os.environ["APPDATA"]) / "Rainmeter/Rainmeter.ini"
HOST = "127.0.0.1"
PORT = 8776
WEB = ASSETS / "panel"
TOKEN = secrets.token_urlsafe(24)
LOCK = threading.RLock()
HISTORY = deque(maxlen=40)
EXIT_CALLBACK = None
PREFERENCES_CALLBACK = None
CREATE_NO_WINDOW = 0x08000000


def bang(commands):
    if not RAINMETER.exists():
        raise RuntimeError("Rainmeter 尚未安装")
    # The executable accepts one bang followed by its arguments. Bracketed skin
    # actions are not a command-line batch: they can be mistaken for an INI path.
    for command in commands:
        result = subprocess.run(
            [str(RAINMETER), *map(str, command)],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
        )
        if result.returncode:
            raise RuntimeError("桌面组件暂时无法应用，请重试")


def saved_positions():
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        raw = SETTINGS.read_bytes()
        parser.read_string(
            raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        )
    except (OSError, UnicodeError, configparser.Error):
        pass
    return parser


def apply(config, rearrange=False):
    config = validate(config)
    manifest = build(config)
    target = skin_path()
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT, target, dirs_exist_ok=True)
    previous = saved_positions()
    commands = []
    for old in ("GlassHardware", "GlassHardware\\Details"):
        if previous.has_section(old) and previous.get(old, "Active", fallback="0") != "0":
            commands.append(["!DeactivateConfig", old])
    commands.append(["!RefreshApp"])
    active = {item["id"] for item in manifest}
    for key in ORDER + ["Group"]:
        name = "DesktopStats\\" + key
        if key not in active:
            if previous.has_section(name) and previous.get(name, "Active", fallback="0") != "0":
                commands.append(["!DeactivateConfig", name])
    dpi = display_scale()
    margin = round(22 * dpi)
    gap = round(9 * dpi)
    total_width = sum(i["width"] for i in manifest) + gap * max(0, len(manifest) - 1)
    offset = 0
    for i, item in enumerate(manifest):
        name = item["config"]
        if previous.get(name, "Active", fallback="0") != "1":
            commands.append(["!ActivateConfig", name, "Widget.ini"])
        commands.extend(
            [
                ["!ZPos", "-2", name],
                ["!Draggable", "0" if config["locked"] else "1", name],
                ["!ClickThrough", "0", name],
                ["!KeepOnScreen", "1", name],
            ]
        )
        if rearrange or not previous.has_section(name):
            if config["layout"] == "row":
                x = str(margin + total_width - offset) + "R"
                y = str(margin)
                offset += item["width"] + gap
            elif config["layout"] == "column":
                x = str(margin + item["width"]) + "R"
                y = str(margin + offset)
                offset += item["height"] + gap
            else:
                columns = 2
                unit_width = max((entry["width"] for entry in manifest), default=0)
                unit_height = max((entry["height"] for entry in manifest), default=0)
                x = str(margin + (2 - i % columns) * unit_width + (1 - i % columns) * gap) + "R"
                y = str(margin + (i // columns) * (unit_height + gap))
            commands.append(["!SetWindowPosition", x, y, "0", "0", name])
    bang(commands)
    return manifest


def commit(config, rearrange=False):
    config = validate(config)
    with LOCK:
        old = load()
        arrange = (
            rearrange
            or any(config[k] != old[k] for k in ("mode", "layout", "group_columns", "size"))
            or any(
                any(
                    config["widgets"][k][f] != old["widgets"][k][f]
                    for f in ("enabled", "size", "grouped")
                )
                for k in ORDER
            )
        )
        manifest = apply(config, arrange)
        if config["autostart"] != old["autostart"]:
            from installer import set_autostart

            set_autostart(config["autostart"])
        save(config)
    if PREFERENCES_CALLBACK:
        try:
            PREFERENCES_CALLBACK()
        except Exception:
            logging.exception("Tray menu refresh failed")
    return config, manifest


def quick_change(field):
    with LOCK:
        config = load()
        if field not in ("visible", "locked"):
            raise ValueError("Unsupported tray setting")
        config[field] = not config[field]
        return commit(config)


def native_dpi():
    """Select native application rendering instead of OS bitmap stretching, per app."""
    keypath = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, keypath) as key:
        try:
            old = winreg.QueryValueEx(key, str(RAINMETER))[0]
        except FileNotFoundError:
            old = None
        backup = BASE / "dpi-compat.before.json"
        flags = [
            v
            for v in (old or "").split()
            if v not in ("~", "DPIUNAWARE", "GDIDPISCALING", "HIGHDPIAWARE")
        ]
        new = "~ " + " ".join(flags + ["HIGHDPIAWARE"])
        if not backup.exists():
            backup.write_text(json.dumps({"value": old, "applied": new}), encoding="utf-8")
        if old == new:
            return False
        winreg.SetValueEx(key, str(RAINMETER), 0, winreg.REG_SZ, new)
        return True


def state():
    try:
        data = json.loads((BASE / "latest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data and (not HISTORY or data["time"] != HISTORY[-1]["time"]):
        HISTORY.append(data)
    return {
        "data": data,
        "config": load(),
        "fresh": 0 <= time.time() - data.get("time", 0) < 35,
        "history": list(HISTORY),
        "display_scale": display_scale(),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, body, kind="application/json; charset=utf-8"):
        content = (
            json.dumps(body, ensure_ascii=False).encode()
            if isinstance(body, (dict, list))
            else body
        )
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(content)

    def allowed_host(self):
        return self.headers.get("Host") in (f"{HOST}:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self.allowed_host():
            return self.respond(403, {"error": "仅支持本机访问"})
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self.respond(200, {"app": "desktop-stats", "version": "0.2.0"})
        if path == "/api/config":
            return self.respond(
                200,
                dict(
                    config=load(),
                    modules=MODULES,
                    metrics=METRICS,
                    skins=SKINS,
                    presets=preset_catalogue(),
                    languages=LANGUAGES,
                    locales={
                        code: localized_metadata(code, MODULES, METRICS, SKINS, preset_catalogue())
                        for code in LANGUAGES
                    },
                    order=ORDER,
                    defaults=DEFAULT,
                    token=TOKEN,
                ),
            )
        if path == "/api/state":
            if urlsplit(self.path).query == "inspect=1":
                sensors.INSPECT_UNTIL = time.monotonic() + 5
            return self.respond(200, state())
        files = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
        if path not in files:
            return self.respond(404, {"error": "未找到页面"})
        try:
            data = (WEB / files[path]).read_bytes()
        except OSError:
            return self.respond(503, {"error": "设置界面尚未就绪"})
        kind = {
            "/": "text/html; charset=utf-8",
            "/app.js": "text/javascript; charset=utf-8",
            "/style.css": "text/css; charset=utf-8",
        }[path]
        self.respond(200, data, kind)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if (
            not self.allowed_host()
            or self.headers.get("X-Stats-Token") != TOKEN
            or origin not in (None, f"http://{HOST}:{PORT}", f"http://localhost:{PORT}")
        ):
            return self.respond(403, {"error": "请从本机设置面板操作"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 24000:
                raise ValueError("设置内容过大")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("设置内容必须是对象")
            path = urlsplit(self.path).path
            if path == "/api/exit" and EXIT_CALLBACK:
                self.respond(200, {"ok": True})
                threading.Thread(target=EXIT_CALLBACK, daemon=True).start()
                return
            if path not in ("/api/config", "/api/validate"):
                return self.respond(404, {"error": "不支持此操作"})
            config = validate(payload.get("config"))
            if path == "/api/validate":
                return self.respond(200, {"config": config})
            config, manifest = commit(config, bool(payload.get("rearrange")))
            self.respond(200, dict(config=config, active=manifest))
        except ValueError as e:
            self.respond(400, {"error": str(e)})
        except Exception as e:
            with (BASE / "settings-error.log").open("a", encoding="utf-8") as log:
                log.write(repr(e) + "\n")
            self.respond(500, {"error": "应用失败，请重试。原有设置仍已保留。"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        changed = native_dpi()
        if changed:
            bang([["!Quit"]])
            time.sleep(1)
            subprocess.Popen([str(RAINMETER)], creationflags=CREATE_NO_WINDOW)
            time.sleep(1)
        config = load()
        apply(config, True)
        save(config)
        print("Modular desktop widgets installed with native DPI rendering.")
        return
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        return
    (BASE / "settings.pid").write_text(str(os.getpid()), encoding="ascii")
    (BASE / "settings.token").write_text(TOKEN, encoding="ascii")
    server.serve_forever()


if __name__ == "__main__":
    main()
