"""Desktop integration helpers."""
import os
import shutil
import sys
from pathlib import Path

AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "tidegate.desktop"


def autostart_enabled():
    return AUTOSTART.exists()


def set_autostart(on):
    if not on:
        AUTOSTART.unlink(missing_ok=True)
        return
    exe = shutil.which("tidegate") or f"{sys.executable} -m tidegate"
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=Tidegate\n"
                         f"Exec={exe} --minimized\nIcon=tidegate\nTerminal=false\n"
                         "X-GNOME-Autostart-enabled=true\n")
