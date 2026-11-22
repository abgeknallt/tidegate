"""Real app icons: icon theme, then .desktop entries, then a colored letter tile."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from .desktop import build_index, icon_file, is_generic, lookup

_index, _cache = None, {}


def _from_spec(spec):
    if not spec:
        return None
    if spec.startswith("/"):
        return QIcon(spec) if os.path.exists(spec) else None
    icon = QIcon.fromTheme(spec)
    if not icon.isNull():
        return icon
    path = icon_file(spec)              # the theme may not know it (Flatpak, Snap)
    return QIcon(path) if path else None


def letter_icon(name, size=24):
    """Fallback tile: first letter on a color derived from the name."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor.fromHsl(sum(ord(c) for c in name.lower()) * 37 % 360, 150, 95))
    p.drawRoundedRect(0, 0, size * 2, size * 2, size * 0.55, size * 0.55)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * 1.1))
    p.setFont(font)
    p.setPen(QColor("#ffffff"))
    p.drawText(pm.rect(), Qt.AlignCenter, (name.strip()[:1] or "?").upper())
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def _find(label, icon, binary, app_id):
    global _index
    generic = is_generic(icon)
    found = None if generic else _from_spec(icon)
    if found:
        return found
    if _index is None:
        _index = build_index()
    found = _from_spec(lookup(_index, app_id, binary, label))
    if found:
        return found
    for name in (app_id, binary, label.lower().replace(" ", "-"), label.lower(), *([] if generic else [icon])):
        found = _from_spec(name)
        if found:
            return found
    return None


def find_app_icon(label, icon="", binary="", app_id=""):
    key = (label, icon, binary, app_id)
    if key not in _cache:
        _cache[key] = _find(label, icon, binary, app_id) or letter_icon(label)
    return _cache[key]
