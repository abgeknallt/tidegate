"""Widgets for Tidegate's board: cards, rows, meters, wires and the theme."""
import re
import time

from PySide6.QtCore import (QAbstractAnimation, QByteArray, QEasingCurve, QPointF,
                            QPropertyAnimation, QSize, Qt)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMenu,
                               QPushButton, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
                               QWidgetAction)

from .icons import find_app_icon

CARD_W = 340
PALETTE = ["#8b5cf6", "#f4975a", "#2fd6b0", "#ec4899", "#60a5fa", "#facc15"]
COLOR_NAMES = ["Violet", "Orange", "Teal", "Pink", "Blue", "Yellow"]
IDLE = "#aab0bc"

STYLE = """
QWidget { background: #121418; color: #e8eaee; font-size: 13px; }
QLabel, QSlider, QToolButton { background: transparent; }
#card { background: #1a1d23; border: 1px solid #242831; border-radius: 12px; }
#card:hover { border-color: #3a404c; }
#card[idle="true"] #title { color: #6f7581; }
#empty { background: transparent; border: 1px dashed #2f3540; border-radius: 12px; }
#title { font-size: 14px; font-weight: 600; }
#sub { color: #8a909c; font-size: 11px; }
#badge { color: #7aa7ff; background: #1c2840; border-radius: 8px; padding: 2px 8px;
         font-size: 10px; font-weight: 700; }
#menuhead { background: transparent; color: #6f7581; font-size: 10px; font-weight: 700;
            letter-spacing: 1px; padding: 8px 16px 4px 16px; }
QPushButton#dropdown { background: #1a1d23; border: 1px solid #242831; border-radius: 10px; }
QPushButton#dropdown:hover { border-color: #3a404c; background: #1f232a; }
QPushButton::menu-indicator { image: none; width: 0; }
#segbar { background: #1a1d23; border: 1px solid #242831; border-radius: 12px; }
#segdiv { background: #2a2f38; }
QPushButton#seg { background: transparent; border: none; border-radius: 9px; }
QPushButton#seg:hover { background: #232730; }
QPushButton#seg:checked { background: #b4232f; }
QPushButton#seg:checked QLabel { color: #ffffff; }
QToolButton { border: 1px solid transparent; border-radius: 7px; padding: 2px; color: #aab0bc; }
QToolButton:hover { background: #262a32; }
QToolButton::menu-indicator { image: none; width: 0; }
#mute { border: 1px solid #2c313a; }
#mute:checked { background: #b4232f; border-color: #b4232f; }
#add { border: 1px solid #2c313a; border-radius: 12px; font-size: 13px; padding: 0 10px; }
#add:hover { background: #262a32; border-color: #4f8cff; }
QSlider::groove:horizontal { height: 4px; background: #2c313a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4f8cff; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #ffffff; border-radius: 7px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #2c313a; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #1a1d23; border: 1px solid #242831; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 8px 20px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: #262a32; }
QMenu::item:disabled { color: #6f7581; }
QMenu::separator { height: 1px; background: #242831; margin: 6px 8px; }
"""

# ---- icons: drawn from small SVGs so the look never depends on the icon theme ----
GLYPHS = {
    "speaker": '<path d="M4 9v6h4l5 4V5L8 9H4z" fill="{c}"/><path d="M16 8.5a5 5 0 010 7M18.5 6a8.5 8.5 0 010 12" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "speaker-muted": '<path d="M4 9v6h4l5 4V5L8 9H4z" fill="{c}"/><path d="M16.5 9l5 6M21.5 9l-5 6" fill="none" stroke="{c}" stroke-width="1.9" stroke-linecap="round"/>',
    "headphones": '<path d="M4 15v-3a8 8 0 0116 0v3" fill="none" stroke="{c}" stroke-width="1.8"/><rect x="3" y="14" width="4" height="6" rx="1.5" fill="{c}"/><rect x="17" y="14" width="4" height="6" rx="1.5" fill="{c}"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3" fill="{c}"/><path d="M5.5 11a6.5 6.5 0 0013 0M12 17.5V21" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "mic-muted": '<rect x="9" y="3" width="6" height="11" rx="3" fill="{c}"/><path d="M5.5 11a6.5 6.5 0 0013 0M12 17.5V21M4 4l16 16" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round"/>',
    "chevron": '<path d="M6 9l6 6 6-6" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "virtual": '<path d="M4 12h2M8 8v8M12 5v14M16 8v8M20 12h-2" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"/>',
    "app": '<rect x="4" y="4" width="16" height="16" rx="4" fill="none" stroke="{c}" stroke-width="1.8"/><circle cx="12" cy="12" r="2.5" fill="{c}"/>',
}
_cache = {}


def glyph(name, color=IDLE, size=18):
    key = (name, color, size)
    if key not in _cache:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
               + GLYPHS[name].format(c=color) + "</svg>")
        pm = QPixmap(size * 2, size * 2)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        QSvgRenderer(QByteArray(svg.encode())).render(painter)
        painter.end()
        pm.setDevicePixelRatio(2)
        _cache[key] = QIcon(pm)
    return _cache[key]


def icon_for(name, group):
    """Apps use their real icon when the theme has one; devices use our glyphs."""
    if group == "app":
        themed = QIcon.fromTheme(name) if name else QIcon()
        if not themed.isNull():
            return themed
        return glyph("app")
    return glyph(name if name in GLYPHS else {"mic": "mic", "virtual": "virtual"}.get(group, "speaker"))


def input_icon(key, label, icon="", binary="", app_id=""):
    """Microphones get our glyph; apps get their real icon (or a colored letter tile)."""
    if key.startswith("mic:"):
        return glyph("mic")
    return find_app_icon(label, icon, binary, app_id)


# ---- animation helpers ----------------------------------------------------------
def fade_in(widget, ms=240):
    fx = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(fx)
    anim = QPropertyAnimation(fx, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QAbstractAnimation.DeleteWhenStopped)


def fade_out(widget, done, ms=170):
    fx = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(fx)
    anim = QPropertyAnimation(fx, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.InCubic)
    anim.finished.connect(done)
    anim.start(QAbstractAnimation.DeleteWhenStopped)


# ---- small builders ------------------------------------------------------------
def tidy(label):
    """Shorten verbose device names: drops (...) and [...] parts and "Controller"."""
    text = re.sub(r"\s*[(\[][^)\]]*[)\]]", "", label)
    for old in ("High Definition Audio Controller", "HD Audio Controller"):
        text = text.replace(old, "Audio")
    return re.sub(r"\s+", " ", text).strip() or label


def menu_header(menu, title):
    """Small muted section title inside a menu."""
    if not menu.isEmpty():
        menu.addSeparator()
    label = QLabel(title.upper())
    label.setObjectName("menuhead")
    action = QWidgetAction(menu)
    action.setDefaultWidget(label)
    menu.addAction(action)


def set_idle(widget, idle):
    if widget.property("idle") != idle:
        widget.setProperty("idle", idle)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def make_slider(value, on_change, on_release):
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(min(value, 100))
    slider.valueChanged.connect(on_change)
    slider.sliderReleased.connect(on_release)
    return slider


def make_mute(checked, on_toggle):
    button = QToolButton()
    button.setObjectName("mute")
    button.setCheckable(True)
    button.setChecked(checked)
    button.setFixedSize(32, 30)
    button.setIconSize(QSize(18, 18))

    def paint(on):
        button.setIcon(glyph("speaker-muted" if on else "speaker", "#ffffff" if on else IDLE))

    paint(checked)
    button.toggled.connect(paint)
    button.toggled.connect(on_toggle)
    return button


def dot_icon(color, size=12):
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(2, 2, size * 2 - 4, size * 2 - 4)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def make_more(actions):
    """\u22ee button. Actions are (text, fn) or (text, [(label, fn, color), ...]) for a submenu."""
    button = QToolButton()
    button.setText("\u22ee")
    button.setPopupMode(QToolButton.InstantPopup)
    menu = QMenu(button)
    for text, target in actions:
        if isinstance(target, list):
            sub = menu.addMenu(text)
            for label, fn, color in target:
                sub.addAction(dot_icon(color), label).triggered.connect(lambda _=False, f=fn: f())
        else:
            menu.addAction(text).triggered.connect(lambda _=False, f=target: f())
    button.setMenu(menu)
    return button


def make_menu_more(fill):
    """\u22ee button whose menu is (re)built every time it opens."""
    button = QToolButton()
    button.setText("\u22ee")
    button.setPopupMode(QToolButton.InstantPopup)
    menu = QMenu(button)
    menu.aboutToShow.connect(lambda: fill(menu))
    button.setMenu(menu)
    return button


class ElidedLabel(QLabel):
    """Label that elides its text to whatever width the layout gives it, so
    long names end in an ellipsis instead of being clipped mid-letter."""

    def __init__(self, text="", mode=Qt.ElideRight):
        super().__init__()
        self.full, self.mode = None, mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.set_full(text)

    def set_full(self, text):
        if text != self.full:
            self.full = text
            self._elide()

    def _elide(self):
        width = self.width() if self.width() > 20 else 10000
        QLabel.setText(self, self.fontMetrics().elidedText(self.full, self.mode, width))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class PillButton(QPushButton):
    """Button whose icon, text and chevron we lay out ourselves, so padding and
    centering never depend on how the style draws a QPushButton."""

    def __init__(self, text, kind, icon=None, chevron=False, centered=False, height=38):
        super().__init__()
        self.setObjectName(kind)
        self.setCursor(Qt.PointingHandCursor)
        self.min_height = height
        self.icon_label, self.label, self.chevron = QLabel(), QLabel(text), QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.chevron.setPixmap(glyph("chevron", IDLE, 14).pixmap(14, 14))
        self.chevron.setVisible(chevron)
        for part in (self.icon_label, self.label, self.chevron):
            part.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 14, 0)
        lay.setSpacing(8)
        if centered:
            lay.addStretch()
            lay.addWidget(self.icon_label)
            lay.addWidget(self.label)
            lay.addWidget(self.chevron)
            lay.addStretch()
        else:
            lay.addWidget(self.icon_label)
            lay.addWidget(self.label, 1)
            lay.addWidget(self.chevron)
        self.set_icon(icon)

    def set_text(self, text):
        self.label.setText(text)
        self.updateGeometry()

    def set_icon(self, icon):
        self.icon_label.setVisible(icon is not None)
        if icon is not None:
            self.icon_label.setPixmap(icon.pixmap(16, 16))

    def sizeHint(self):
        hint = self.layout().sizeHint()
        return QSize(hint.width(), max(hint.height(), self.min_height))

    def minimumSizeHint(self):
        return self.sizeHint()


class MeterBar(QWidget):
    """Row of dots that light up with the signal level (green, amber, red)."""
    DOT, GAP = 3, 3

    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self.level = 0.0

    def set_level(self, value):
        if abs(value - self.level) > 0.01 or (value == 0 and self.level):
            self.level = value
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        step = self.DOT + self.GAP
        n = max(1, self.width() // step)
        lit = int(self.level * n + 0.5)
        for i in range(n):
            frac = i / n
            if i < lit:
                color = "#e5484d" if frac > 0.9 else "#f5b83d" if frac > 0.72 else "#3ddc97"
            else:
                color = "#2a2f38"
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(i * step + self.DOT / 2, self.height() / 2), self.DOT / 2, self.DOT / 2)


class ConnRow(QWidget):
    """One connection of an input: target name, own volume and mute, and a menu
    (also on right-click) to move or remove it."""

    def __init__(self, label, state, on_vol, on_mute, fill_menu, on_save):
        super().__init__()
        self.fill_menu = fill_menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        name = ElidedLabel(tidy(label))
        name.setObjectName("sub")
        name.setToolTip(label)
        more = make_menu_more(fill_menu)
        more.setFixedSize(22, 18)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(name, 1)
        top.addWidget(more)
        slider = make_slider(state["vol"], on_vol, on_save)
        self.mute = make_mute(state["mute"], lambda m: (on_mute(m), on_save()))
        left = QVBoxLayout()
        left.setSpacing(3)
        left.addLayout(top)
        left.addWidget(slider)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(left, 1)
        lay.addWidget(self.mute, alignment=Qt.AlignBottom)

    def _menu(self, pos):
        menu = QMenu(self)
        self.fill_menu(menu)
        menu.exec(self.mapToGlobal(pos))


class InputCard(QFrame):
    def __init__(self, entry, on_remove, on_rename, fill_links, on_hover):
        super().__init__()
        self.setObjectName("card")
        self.setFixedWidth(CARD_W)
        self.key, self.on_hover, self.rows, self.source = entry["key"], on_hover, {}, None
        icon = QLabel()
        icon.setPixmap(input_icon(self.key, entry["label"], entry.get("icon", ""),
                                  entry.get("binary", ""), entry.get("app_id", "")).pixmap(22, 22))
        self.title = ElidedLabel()
        self.title.setObjectName("title")
        self.set_title(entry.get("name") or entry["label"])
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(icon)
        head.addWidget(self.title, 1)
        head.addWidget(make_more([("Rename\u2026", on_rename), ("Remove input", on_remove)]))
        self.meter = MeterBar()
        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(12)
        self.add = QToolButton()
        self.add.setObjectName("add")
        self.add.setText("+   Connect to an output")
        self.add.setMinimumSize(24, 24)
        self.add.setToolTip("Connect to an output")
        self.add.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.add)
        menu.aboutToShow.connect(lambda: fill_links(menu))
        self.add.setMenu(menu)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 14, 14)
        lay.setSpacing(12)
        lay.addLayout(head)
        lay.addWidget(self.meter)
        lay.addLayout(self.rows_box)
        lay.addWidget(self.add, alignment=Qt.AlignHCenter)

    def set_title(self, text):
        self.title.set_full(tidy(text))
        self.title.setToolTip(text)

    def sync(self, wanted, make_row):
        for key in [k for k in self.rows if k not in wanted]:
            row = self.rows.pop(key)
            fade_out(row, lambda r=row: (self.rows_box.removeWidget(r), r.deleteLater()))
        for key in wanted:
            if key not in self.rows:
                row = make_row(key)
                self.rows[key] = row
                self.rows_box.addWidget(row)
                if self.isVisible():
                    fade_in(row)
        self.add.setText("+" if self.rows else "+   Connect to an output")

    def enterEvent(self, event):
        self.on_hover(self.key)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.on_hover(None)
        super().leaveEvent(event)


class OutputCard(QFrame):
    def __init__(self, item, on_vol, on_mute, actions):
        super().__init__()
        self.setObjectName("card")
        self.setFixedWidth(CARD_W)
        self.source = None
        icon = QLabel()
        icon.setPixmap(icon_for(item.icon, item.group).pixmap(20, 20))
        self.title = ElidedLabel()
        self.title.setObjectName("title")
        self.set_title(item.label)
        self.sub = ElidedLabel()
        self.sub.setObjectName("sub")
        names = QVBoxLayout()
        names.setSpacing(1)
        names.addWidget(self.title)
        names.addWidget(self.sub)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(icon)
        self.badge = QLabel("DEFAULT")
        self.badge.setObjectName("badge")
        self.badge.hide()
        head.addLayout(names, 1)
        head.addWidget(self.badge, alignment=Qt.AlignVCenter)
        head.addWidget(make_more(actions))
        self.meter = MeterBar()
        slider = make_slider(item.volume, on_vol, lambda: None)
        self.mute = make_mute(False, on_mute)
        body = QHBoxLayout()
        body.addWidget(slider, 1)
        body.addWidget(self.mute)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 14, 14)
        lay.setSpacing(12)
        lay.addLayout(head)
        lay.addWidget(self.meter)
        lay.addLayout(body)

    def set_title(self, text):
        self.title.set_full(tidy(text))
        self.title.setToolTip(text)

    def set_sub(self, text):
        self.sub.set_full(text)

    def set_default(self, on):
        self.badge.setVisible(on)


class EmptyCard(QFrame):
    """Placeholder shown while the board has no inputs."""

    def __init__(self, title, text):
        super().__init__()
        self.setObjectName("empty")
        self.setFixedWidth(CARD_W)
        head = QLabel(title)
        head.setObjectName("title")
        body = QLabel(text)
        body.setObjectName("sub")
        body.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(4)
        lay.addWidget(head)
        lay.addWidget(body)


class Wires(QWidget):
    """Draws a wire per connection. Wires fade in; hovering an input card
    highlights its wires and dims the rest."""
    PORT = 5

    def __init__(self, window):
        super().__init__()
        self.win, self.born = window, {}
        self.setMinimumWidth(220)

    def _y(self, widget):
        return self.mapFromGlobal(widget.mapToGlobal(widget.rect().center())).y()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now, hover, seen = time.monotonic(), self.win.hover, set()
        left, right = self.PORT + 2, self.width() - self.PORT - 2
        for ik, card in self.win.in_cards.items():
            for ok, row in card.rows.items():
                out = self.win.out_cards.get(ok)
                if out is None:
                    continue
                link = (ik, ok)
                seen.add(link)
                t = min(1.0, (now - self.born.setdefault(link, now)) / 0.35)
                alpha = 1 - (1 - t) ** 3
                if hover and hover != ik:
                    alpha *= 0.22
                color = QColor(self.win.color(ok))
                color.setAlphaF(alpha)
                a = QPointF(left, self._y(row.mute))
                b = QPointF(right, self._y(out.mute))
                path = QPainterPath(a)
                dx = (b.x() - a.x()) / 2
                path.cubicTo(a.x() + dx, a.y(), b.x() - dx, b.y(), b.x(), b.y())
                p.setPen(QPen(color, 2.4 if hover == ik else 1.6))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                p.drawEllipse(a, self.PORT, self.PORT)
        self.born = {l: t for l, t in self.born.items() if l in seen}
        p.setPen(Qt.NoPen)
        for ok, out in self.win.out_cards.items():
            p.setBrush(QColor(self.win.color(ok)))
            p.drawEllipse(QPointF(right, self._y(out.mute)), self.PORT, self.PORT)
