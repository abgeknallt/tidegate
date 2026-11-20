"""Tidegate - route and mix application audio with PipeWire."""
import argparse
import shutil
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import __version__
from .control import Server, send
from .engine import Engine
from .meters import Meters
from .tray import Tray
from .window import Window


def main():
    parser = argparse.ArgumentParser(
        prog="tidegate", description="Route and mix application audio with PipeWire.",
        epilog="Control a running instance (bind these to global shortcuts): "
               "--mic-mute, --profile NAME, --show, --quit.")
    parser.add_argument("--version", action="version", version=f"Tidegate {__version__}")
    parser.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    parser.add_argument("--profile", metavar="NAME", help="switch the running instance to a profile")
    parser.add_argument("--mic-mute", action="store_true", help="toggle microphone mute")
    parser.add_argument("--show", action="store_true", help="show the window")
    parser.add_argument("--quit", action="store_true", help="quit the running instance")
    args, qt_args = parser.parse_known_args()
    if not shutil.which("pactl"):
        sys.exit("tidegate: 'pactl' not found. Install libpulse and make sure PipeWire is running.")

    app = QApplication([sys.argv[0], *qt_args])
    commands = [c for c in (f"profile {args.profile}" if args.profile else "",
                            "toggle-mic-mute" if args.mic_mute else "",
                            "show" if args.show else "", "quit" if args.quit else "") if c]
    if commands:
        sent = [send(c) for c in commands]
        sys.exit(0 if all(sent) else "tidegate: no running instance found")
    if send("ping" if args.minimized else "show"):
        sys.exit(0)                         # already running: just raise it

    app.setStyle("Fusion")
    app.setApplicationName("Tidegate")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("tidegate")
    icon = QIcon.fromTheme("tidegate")
    if icon.isNull():                      # running from the source tree
        svg = Path(__file__).resolve().parents[2] / "data" / "tidegate.svg"
        icon = QIcon(str(svg)) if svg.exists() else icon
    app.setWindowIcon(icon)

    engine, meters = Engine(), Meters()
    win = Window(engine, meters, icon)
    server = Server()
    server.received.connect(win.handle)
    if QSystemTrayIcon.isSystemTrayAvailable():
        win.tray = Tray(win, icon)
        app.setQuitOnLastWindowClosed(False)
        win._update_profile_ui()
    app.aboutToQuit.connect(meters.stop_all)
    app.aboutToQuit.connect(engine.close)
    if not (args.minimized and win.tray):
        win.show()
    sys.exit(app.exec())
