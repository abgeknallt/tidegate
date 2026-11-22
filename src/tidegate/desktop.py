"""Find .desktop entries so apps can be matched to their real icon. No Qt in here."""
import os
import shlex
from pathlib import Path

SKIP = {"flatpak", "env", "sh", "bash", "python", "python3", "snap"}


def data_dirs():
    home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    system = [Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    return [home, *system, home / "flatpak" / "exports" / "share",
            Path("/var/lib/flatpak/exports/share"), Path("/var/lib/snapd/desktop")]


def _entry(path):
    data, inside = {}, False
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return data
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            if inside:
                break
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            data.setdefault(key.strip(), value.strip())
    return data


def _exec_names(line):
    """Program name of an Exec= line, plus the app id for `flatpak run ... <id>`."""
    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.split()
    while parts and (parts[0] == "env" or "=" in parts[0]):
        parts.pop(0)
    if not parts:
        return []
    names = [os.path.basename(parts[0]).lower()]
    if names[0] == "flatpak" and "run" in parts:
        rest = [p for p in parts[parts.index("run") + 1:] if not p.startswith("-")]
        if rest:
            names.append(rest[0].lower())
    return names


def build_index(dirs=None):
    """Map lowercase desktop id / program / window class / name -> Icon value."""
    index = {}
    for base in data_dirs() if dirs is None else dirs:
        folder = Path(base) / "applications"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.desktop")):
            entry = _entry(path)
            icon = entry.get("Icon")
            if not icon:
                continue
            keys = [path.stem.lower(), entry.get("StartupWMClass", "").lower(),
                    entry.get("Name", "").lower(), *_exec_names(entry.get("Exec", ""))]
            for key in keys:
                if key and key not in SKIP:
                    index.setdefault(key, icon)
    return index


def lookup(index, *hints):
    for hint in hints:
        if hint and hint.lower() in index:
            return index[hint.lower()]
    return None
