"""System tray icon with status, quick mute and profile switching."""
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def status_icon(base, muted):
    pm = base.pixmap(64, 64)
    if pm.isNull():
        pm = QPixmap(64, 64)
        pm.fill(QColor("#4f8cff"))
    if muted:
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#14161a"), 3))
        p.setBrush(QColor("#e5484d"))
        p.drawEllipse(34, 34, 26, 26)
        p.end()
    return QIcon(pm)


class Tray(QSystemTrayIcon):
    def __init__(self, window, base_icon):
        super().__init__(window)
        self.win, self.base = window, base_icon
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._build)
        self.setContextMenu(self.menu)
        self.activated.connect(self._activated)
        self.update_state()
        self.show()

    def _build(self):
        eng, m = self.win.eng, self.menu
        m.clear()
        m.addAction("Hide window" if self.win.isVisible() else "Show window").triggered.connect(
            lambda _=False: self.win.toggle_visible())
        m.addSeparator()
        mute = m.addAction("Mute mic")
        mute.setCheckable(True)
        mute.setChecked(eng.mic_muted)
        mute.triggered.connect(lambda _=False: self.win.toggle_mic_mute())
        if eng.profiles:
            sub = m.addMenu("Profiles")
            for name in eng.profiles:
                act = sub.addAction(name)
                act.setCheckable(True)
                act.setChecked(name == eng.profile)
                act.triggered.connect(lambda _=False, n=name: self.win.apply_profile(n))
        m.addSeparator()
        m.addAction("Quit").triggered.connect(lambda _=False: self.win.quit())

    def _activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.win.toggle_visible()

    def update_state(self):
        eng = self.win.eng
        self.setIcon(status_icon(self.base, eng.mic_muted))
        tip = "Tidegate - mic muted" if eng.mic_muted else "Tidegate - mic live"
        self.setToolTip(tip + (f"\nProfile: {eng.profile}" if eng.profile else ""))
