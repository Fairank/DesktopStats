"""Desktop Stats: standalone native Windows software, without a browser runtime."""

import argparse
import ctypes as c
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def main():
    parser = argparse.ArgumentParser(description="Desktop Stats native Windows widgets")
    parser.add_argument("--background", action="store_true", help="Open widgets and tray only")
    parser.add_argument("--headless", action="store_true", help="Collect sensors without windows")
    parser.add_argument("--install", action="store_true", help="Install for the current user")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall; keep preferences")
    parser.add_argument("--quit", action="store_true", help="Close the running app")
    parser.add_argument("--status", action="store_true", help="Report the running native instance")
    parser.add_argument("--diagnose", metavar="JSON", help="Save private native-render diagnostics")
    parser.add_argument("--storage-read", metavar="JSON", help=argparse.SUPPRESS)
    parser.add_argument(
        "--self-check", metavar="JSON", help="Check an isolated bundle without desktop activity"
    )
    args = parser.parse_args()
    if args.storage_read is not None:
        from storage_sensor import worker_main

        return worker_main(args.storage_read)
    if args.self_check is not None:
        from native_selfcheck import run

        return run(args.self_check)
    from stats_config import ASSETS, BASE

    handler = RotatingFileHandler(
        BASE / "app.log", maxBytes=512000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(handlers=[handler], level=logging.WARNING)
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    # Python-painted cards share the GUI thread. Retain D3D composition without
    # a render-thread/GIL lock inversion when Windows exposes a new window.
    os.environ["QSG_RENDER_LOOP"] = "basic"
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtWidgets import QApplication

    from native_ipc import send

    QQuickWindow.setDefaultAlphaBuffer(True)
    application = QApplication(sys.argv[:1])
    application.setApplicationName("Desktop Stats")
    application.setOrganizationName("Fairank")
    application.setQuitOnLastWindowClosed(False)
    from native_card import ui_font
    from stats_config import load

    application.setFont(QFont(ui_font(load()["language"]), 10))
    application.setWindowIcon(QIcon(str(ASSETS / "assets/icon.ico")))
    if args.install:
        from installer import install

        install()
        return
    if args.uninstall:
        from installer import close_existing, remove_registration

        close_existing()
        remove_registration()
        return
    command = {
        "command": "status"
        if args.status or args.background or args.headless
        else "quit"
        if args.quit
        else "diagnose"
        if args.diagnose
        else "show"
    }
    if args.diagnose:
        command["path"] = args.diagnose
    existing = send(command, timeout=600)
    if args.status or args.quit or args.diagnose:
        print(json.dumps(existing or {"ok": False, "running": False}))
        return
    if existing:
        return
    from native_runtime import LocalServer, Runtime

    server = LocalServer(application)
    if not server.start():
        send({"command": "show"})
        return
    from legacy_migration import migrate

    migrate()
    runtime = Runtime(application, background=args.background, headless=args.headless)
    server.runtime = runtime
    pid_file = BASE / "app.pid"
    pid_file.write_text(str(os.getpid()), encoding="ascii")
    application.exec()
    server.close()
    if pid_file.exists() and pid_file.read_text(encoding="ascii") == str(os.getpid()):
        pid_file.unlink()


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        logging.exception("Application failed")
        if any(
            arg in ("--self-check", "--storage-read")
            or arg.startswith(("--self-check=", "--storage-read="))
            for arg in sys.argv
        ):
            sys.exit(1)
        else:
            c.windll.user32.MessageBoxW(
                None,
                "Desktop Stats 启动失败。详细信息已保存在本机 app.log。",
                "Desktop Stats",
                0x10,
            )
