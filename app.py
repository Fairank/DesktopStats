"""Desktop Stats: standalone native Windows software, without a browser runtime."""

import argparse
import ctypes as c
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from product_version import VERSION


def main():
    parser = argparse.ArgumentParser(description="Desktop Stats native Windows widgets")
    parser.add_argument("--background", action="store_true", help="Open widgets and tray only")
    parser.add_argument("--headless", action="store_true", help="Collect sensors without windows")
    parser.add_argument("--install", action="store_true", help="Install for the current user")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall; keep preferences")
    parser.add_argument("--quit", action="store_true", help="Close the running app")
    parser.add_argument("--status", action="store_true", help="Report the running native instance")
    parser.add_argument("--diagnose", metavar="JSON", help="Save private native-render diagnostics")
    parser.add_argument("--secondary", action="store_true", help="Run an isolated second version without installing")
    parser.add_argument("--secondary-profile", metavar="DIRECTORY", help="Separate second-version data directory")
    parser.add_argument("--secondary-screen", metavar="NATIVE_ID", help="Strict second-version monitor; no primary fallback")
    parser.add_argument("--share-installed-cpu-cache", metavar="PID:CREATED", help="Explicitly read the existing installed owner's CPU cache only")
    parser.add_argument("--storage-read", metavar="JSON", help=argparse.SUPPRESS)
    parser.add_argument(
        "--self-check", metavar="JSON", help="Check an isolated bundle without desktop activity"
    )
    args = parser.parse_args()
    if not args.secondary and any((args.secondary_profile,args.secondary_screen,args.share_installed_cpu_cache)):
        parser.error("Secondary options require --secondary")
    if args.secondary and (args.install or args.uninstall):
        parser.error("第二版不安装或卸载原版。")
    if args.storage_read is not None:
        from storage_sensor import worker_main

        return worker_main(args.storage_read)
    if args.self_check is not None:
        # Self-checks never open an inherited real-owner cache lease.
        os.environ["DESKTOP_STATS_CPU_BRIDGE_DISABLED"] = "1"
        os.environ.pop("DESKTOP_STATS_SECONDARY_CPU_OWNER055",None)
        from native_selfcheck import run

        return run(args.self_check)
    from secondary_mode055 import configure, display_name, apply_process_identity
    secondary = configure(args)
    if secondary is not None:
        apply_process_identity()
    if secondary is not None and not (args.status or args.quit or args.diagnose):
        args.background = True
    from stats_config import ASSETS, BASE

    handler = RotatingFileHandler(
        BASE / "app.log", maxBytes=512000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        handlers=[handler], level=logging.WARNING,
        format="%(asctime)s %(levelname)s [pid=%(process)d] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
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
    application.setApplicationName(display_name())
    application.setOrganizationName("Fairank")
    application.setQuitOnLastWindowClosed(False)
    from native_card import ui_font
    from stats_config import load, save

    application.setFont(QFont(ui_font(load()["language"]), 10))
    application.setWindowIcon(QIcon(str(ASSETS / "assets/icon.ico")))
    if args.install:
        from installer import install

        install(background=args.background)
        return
    if args.uninstall:
        from installer import close_existing, remove_registration

        close_existing()
        remove_registration()
        return
    command = {
        "command": "quit"
        if args.quit
        else "diagnose"
        if args.diagnose
        else "status"
        if args.status or args.background or args.headless
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
    lifecycle = logging.getLogger("DesktopStats.lifecycle")
    lifecycle.setLevel(logging.INFO)
    runtime = pid_file = None
    try:
        if secondary is None:
            from legacy_migration import migrate
            migrate()
        else:
            from native_runtime import _desktop_session_ready
            if _desktop_session_ready() is not True:
                raise RuntimeError("第二版等待可安全交互的桌面；未显示任何窗口。")
            secondary.select_screen(application)
            save(secondary.profile_value(load()))
        runtime = Runtime(application, background=args.background, headless=args.headless)
        server.runtime = runtime
        pid_file = BASE / "app.pid"
        pid_file.write_text(str(os.getpid()), encoding="ascii")
        lifecycle.info("started version=%s background=%s headless=%s",
                       VERSION, args.background, args.headless)
        exit_code = application.exec()
        lifecycle.info("event loop ended version=%s exit_code=%s", VERSION, exit_code)
    finally:
        try:
            if runtime is not None and not runtime.shutting_down:
                runtime.shutdown()
        finally:
            try:
                server.close()
            finally:
                if (pid_file is not None and pid_file.exists()
                        and pid_file.read_text(encoding="ascii") == str(os.getpid())):
                    pid_file.unlink()


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        logging.exception("Application failed")
        if "--secondary" in sys.argv or ("--install" in sys.argv and "--background" in sys.argv) or any(
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
