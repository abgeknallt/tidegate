"""Main window: header, profile bar, scrolling board of cards and wires."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu,
                               QScrollArea, QVBoxLayout, QWidget)

from .engine import MIC_NAME, STREAM, Item
from .system import autostart_enabled, set_autostart
from .widgets import (CARD_W, COLOR_NAMES, IDLE, PALETTE, STYLE, ConnRow, EmptyCard, InputCard, OutputCard,
                      PillButton, Wires, fade_in, fade_out, glyph, icon_for, menu_header, set_idle, tidy)


def menu_text(menu, label):
    """Short, middle-elided label so menus never grow wider than a card."""
    return menu.fontMetrics().elidedText(tidy(label), Qt.ElideMiddle, 250)


class Window(QWidget):
    def __init__(self, engine, meters, logo):
        super().__init__()
        self.eng, self.meters = engine, meters
        self.in_cards, self.out_cards = {}, {}
        self.hover, self.tray, self.quitting, self._told = None, None, False, False
        self.setWindowTitle("Tidegate")
        self.setStyleSheet(STYLE)
        self.resize(1060, 740)
        self.setMinimumSize(880, 520)

        self.add_in = self._attach(PillButton("Add input", "dropdown", chevron=True, height=40),
                                   self._fill_inputs)
        self.add_out = self._attach(PillButton("Add output", "dropdown", chevron=True, height=40),
                                    self._fill_outputs)
        for button in (self.add_in, self.add_out):
            button.setFixedWidth(CARD_W)
        mark = QLabel()
        mark.setPixmap(logo.pixmap(26, 26))
        word = QLabel("TIDEGATE")
        word.setStyleSheet("font-weight: 700; letter-spacing: 3px;")
        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(mark)
        brand.addWidget(word)
        top = QHBoxLayout()
        top.addWidget(self.add_in)
        top.addStretch()
        top.addLayout(brand)
        top.addStretch()
        top.addWidget(self.add_out)

        self.profile_btn = self._attach(PillButton("Profiles", "seg", chevron=True, centered=True,
                                                   height=34), self._fill_profiles)
        self.profile_btn.setMinimumWidth(170)
        self.mic_btn = PillButton("Mute mic", "seg", icon=glyph("mic"), centered=True, height=34)
        self.mic_btn.setMinimumWidth(150)
        self.mic_btn.setCheckable(True)
        self.mic_btn.setToolTip("Silences Tidegate Microphone: everything sent to Tidegate Stream (Ctrl+M)")
        self.mic_btn.clicked.connect(lambda _=False: self.toggle_mic_mute())
        self.settings_btn = self._attach(PillButton("Settings", "seg", chevron=True, centered=True,
                                                    height=34), self._fill_settings)
        self.settings_btn.setMinimumWidth(130)
        seg = QFrame()
        seg.setObjectName("segbar")
        seg_lay = QHBoxLayout(seg)
        seg_lay.setContentsMargins(4, 4, 4, 4)
        seg_lay.setSpacing(4)
        for i, button in enumerate((self.profile_btn, self.mic_btn, self.settings_btn)):
            if i:
                divider = QFrame()
                divider.setObjectName("segdiv")
                divider.setFixedSize(1, 18)
                seg_lay.addWidget(divider)
            seg_lay.addWidget(button)
        bar = QHBoxLayout()
        bar.addStretch()
        bar.addWidget(seg)
        bar.addStretch()

        self.hint = EmptyCard("No inputs yet", "Choose an app or a microphone with \u201cAdd input\u201d.")
        self.left, self.right = QVBoxLayout(), QVBoxLayout()
        for col in (self.left, self.right):
            col.setSpacing(14)
            col.addStretch()
        self.left.insertWidget(0, self.hint)
        self.wires = Wires(self)
        board = QWidget()
        lay = QHBoxLayout(board)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.addLayout(self.left)
        lay.addWidget(self.wires, 1)
        lay.addLayout(self.right)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(board)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addLayout(top)
        root.addLayout(bar)
        root.addWidget(scroll, 1)

        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.toggle_mic_mute)
        for i in range(9):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda i=i: self.apply_profile_index(i))
        QTimer(self, interval=1000, timeout=self.refresh).start()
        QTimer(self, interval=33, timeout=self._frame).start()
        self.refresh()
        self._update_profile_ui()

    # ---- building blocks ---------------------------------------------------
    @staticmethod
    def _attach(button, fill):
        menu = QMenu(button)
        menu.aboutToShow.connect(lambda: fill(menu))
        button.setMenu(menu)
        return button

    def color(self, out_key):
        custom = self.eng.out_colors.get(out_key)
        if custom:
            return custom
        try:
            return PALETTE[self.eng.board_out.index(out_key) % len(PALETTE)]
        except ValueError:
            return PALETTE[0]

    def _set_hover(self, key):
        self.hover = key

    def _do(self, fn, *args):
        fn(*args)
        self.refresh()

    # ---- dropdown menus ------------------------------------------------------
    def _fill_inputs(self, menu):
        menu.clear()
        have = {e["key"] for e in self.eng.board_in}
        avail = [i for i in self.eng.known.values() if i.key not in have]
        apps = sorted((i for i in avail if i.group == "app"),
                      key=lambda i: (not i.active, i.label.lower()))
        for title, items in (("Apps", apps), ("Microphones", [i for i in avail if i.group == "mic"])):
            if items:
                menu_header(menu, title)
            for it in items:
                menu.addAction(icon_for(it.icon, it.group), menu_text(menu, it.label)).triggered.connect(
                    lambda _=False, it=it: self._do(self.eng.add_input, it))
        if menu.isEmpty():
            menu.addAction("Nothing to add - play audio in an app first").setEnabled(False)

    def _fill_outputs(self, menu):
        menu.clear()
        avail = [o for o in self.eng.outs.values() if o.key not in self.eng.board_out]
        for title, group in (("Devices", "device"), ("Virtual", "virtual")):
            items = [o for o in avail if o.group == group]
            if items:
                menu_header(menu, title)
            for it in items:
                menu.addAction(icon_for(it.icon, it.group), menu_text(menu, it.label)).triggered.connect(
                    lambda _=False, k=it.key: self._do(self.eng.add_output, k))
        if menu.isEmpty():
            menu.addAction("No more outputs").setEnabled(False)

    def _fill_links(self, menu, ik):
        menu.clear()
        for ok in self.eng.board_out:
            if (ik, ok) not in self.eng.conns:
                it = self.eng.outs.get(ok)
                action = menu.addAction(icon_for(it.icon, it.group) if it else icon_for("", "device"),
                                        menu_text(menu, it.label if it else ok))
                action.triggered.connect(lambda _=False, ok=ok: self._do(self.eng.add_conn, ik, ok))
        if menu.isEmpty():
            menu.addAction("Add an output first").setEnabled(False)

    def _fill_profiles(self, menu):
        menu.clear()
        eng = self.eng
        for name in eng.profiles:
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(name == eng.profile)
            act.triggered.connect(lambda _=False, n=name: self.apply_profile(n))
        if eng.profiles:
            menu.addSeparator()
        menu.addAction("Save current as\u2026").triggered.connect(lambda _=False: self._save_profile_as())
        if eng.profile:
            menu.addAction(f"Update \u201c{eng.profile}\u201d").triggered.connect(
                lambda _=False: (eng.save_profile(eng.profile), self._update_profile_ui()))
            menu.addAction(f"Delete \u201c{eng.profile}\u201d").triggered.connect(
                lambda _=False: (eng.delete_profile(eng.profile), self._update_profile_ui()))

    def _fill_settings(self, menu):
        menu.clear()
        auto = menu.addAction("Auto-add new apps")
        auto.setCheckable(True)
        auto.setChecked(self.eng.auto_add)
        auto.triggered.connect(self._set_auto_add)
        link = menu.addAction("Connect new inputs to the default output")
        link.setCheckable(True)
        link.setChecked(self.eng.auto_connect)
        link.triggered.connect(self._set_auto_connect)
        login = menu.addAction("Start at login (minimized)")
        login.setCheckable(True)
        login.setChecked(autostart_enabled())
        login.triggered.connect(set_autostart)
        menu.addSeparator()
        menu.addAction("Quit Tidegate").triggered.connect(lambda _=False: self.quit())

    def _set_auto_connect(self, on):
        self.eng.auto_connect = bool(on)
        self.eng.save()

    def _set_auto_add(self, on):
        self.eng.auto_add = bool(on)
        self.eng.save()

    # ---- profiles, mute, remote commands ----------------------------------------
    def _save_profile_as(self):
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if ok and name.strip():
            self.eng.save_profile(name.strip())
            self._update_profile_ui()

    def _update_profile_ui(self):
        eng = self.eng
        self.profile_btn.set_text(f"Profile: {eng.profile}" if eng.profile else "Profiles")
        if self.tray:
            self.tray.update_state()

    def apply_profile(self, name):
        if self.eng.apply_profile(name):
            self.refresh()
            self._update_profile_ui()

    def apply_profile_index(self, i):
        names = list(self.eng.profiles)
        if i < len(names):
            self.apply_profile(names[i])

    def toggle_mic_mute(self):
        self.eng.set_mic_muted(not self.eng.mic_muted)
        self._update_mic_ui()

    def _update_mic_ui(self):
        muted = self.eng.mic_muted
        self.mic_btn.setChecked(muted)
        self.mic_btn.set_icon(glyph("mic-muted" if muted else "mic", "#ffffff" if muted else IDLE))
        self.mic_btn.set_text("Mic muted" if muted else "Mute mic")
        if self.tray:
            self.tray.update_state()

    def handle(self, command):
        name, _, arg = command.partition(" ")
        if name == "show":
            self.show_window()
        elif name == "toggle-mic-mute":
            self.toggle_mic_mute()
        elif name == "profile":
            self.apply_profile(arg.strip())
        elif name == "quit":
            self.quit()

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show_window()

    def quit(self):
        self.quitting = True
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray is not None and not self.quitting:
            event.ignore()
            self.hide()
            if not self._told:
                self._told = True
                self.tray.showMessage("Tidegate is still running",
                                      "Use the tray icon to reopen or quit.", self.tray.icon(), 4000)
        else:
            event.accept()

    # ---- board sync -----------------------------------------------------------
    def _rename(self, key):
        entry = next((e for e in self.eng.board_in if e["key"] == key), None)
        if entry is None:
            return
        text, ok = QInputDialog.getText(self, "Rename input", "Name:",
                                        text=entry.get("name") or entry["label"])
        if ok and text.strip():
            self.eng.rename_input(key, text.strip())
            self.refresh()

    def _row(self, ik, ok):
        it = self.eng.outs.get(ok)
        return ConnRow(self._out_name(ok), self.eng.conns[(ik, ok)],
                       lambda v: self.eng.set_conn(ik, ok, vol=v),
                       lambda m: self.eng.set_conn(ik, ok, mute=m),
                       lambda menu: self._fill_row_menu(menu, ik, ok), self.eng.save)

    def _out_name(self, key):
        it = self.eng.outs.get(key)
        return self.eng.out_names.get(key) or (it.label if it else key)

    def _fill_row_menu(self, menu, ik, ok):
        menu.clear()
        others = [o for o in self.eng.board_out if o != ok and (ik, o) not in self.eng.conns]
        if others:
            sub = menu.addMenu("Move to")
            for o in others:
                sub.addAction(menu_text(sub, self._out_name(o))).triggered.connect(
                    lambda _=False, o=o: self._do(self.eng.retarget_conn, ik, ok, o))
        menu.addAction("Disconnect").triggered.connect(
            lambda _=False: self._do(self.eng.remove_conn, ik, ok))

    def _rename_output(self, key):
        text, ok = QInputDialog.getText(self, "Rename output", "Name (empty = original):",
                                        text=self.eng.out_names.get(key, ""))
        if ok:
            self.eng.rename_output(key, text.strip())
            self.refresh()

    def refresh(self):
        known, outs = self.eng.scan()
        eng = self.eng
        keys = [e["key"] for e in eng.board_in]
        for entry in eng.board_in:
            key = entry["key"]
            if key not in self.in_cards:
                card = InputCard(entry, lambda k=key: self._do(eng.remove_input, k),
                                 lambda k=key: self._rename(k),
                                 lambda m, k=key: self._fill_links(m, k), self._set_hover)
                self.in_cards[key] = card
                self.left.insertWidget(self.left.count() - 1, card)
                if self.isVisible():
                    fade_in(card)
            card = self.in_cards[key]
            card.set_title(entry.get("name") or entry["label"])
            set_idle(card, not (key in known and known[key].active))
            bus = eng.buses.get(key)
            card.source = f"{bus}.monitor" if bus else None
            card.sync([o for o in eng.board_out if (key, o) in eng.conns],
                      lambda ok, k=key: self._row(k, ok))
        for key in [k for k in self.in_cards if k not in keys]:
            card = self.in_cards.pop(key)
            fade_out(card, lambda c=card: (self.left.removeWidget(c), c.deleteLater()))

        for key in eng.board_out:
            it = outs.get(key)
            if key not in self.out_cards:
                card = OutputCard(it or Item(key, key, "device", "speaker"),
                                  lambda v, k=key: eng.volume(k, v),
                                  lambda m, k=key: eng.mute(k, m),
                                  [("Rename\u2026", lambda k=key: self._rename_output(k)),
                                   ("Wire color", [(n, lambda k=key, c=c: self._do(eng.set_out_color, k, c), c)
                                                   for n, c in zip(COLOR_NAMES, PALETTE)]),
                                   ("Set as default output", lambda k=key: self._do(eng.set_default, k)),
                                   ("Remove output", lambda k=key: self._do(eng.remove_output, k))])
                self.out_cards[key] = card
                self.right.insertWidget(self.right.count() - 1, card)
                if self.isVisible():
                    fade_in(card)
            card = self.out_cards[key]
            card.set_sub(it.sub if it else "Not connected")
            card.set_default(key == eng.default)
            card.set_title(self._out_name(key))
            card.source = (MIC_NAME if key == STREAM else f"{key}.monitor") if it else None
            set_idle(card, it is None)
        for key in [k for k in self.out_cards if k not in eng.board_out]:
            card = self.out_cards.pop(key)
            fade_out(card, lambda c=card: (self.right.removeWidget(c), c.deleteLater()))

        self.hint.setVisible(not self.in_cards)
        self.meters.watch({c.source for c in (*self.in_cards.values(), *self.out_cards.values())
                           if c.source})

    def _frame(self):
        if not self.isVisible():
            return
        for card in (*self.in_cards.values(), *self.out_cards.values()):
            card.meter.set_level(self.meters.level(card.source) if card.source else 0.0)
        self.wires.update()
