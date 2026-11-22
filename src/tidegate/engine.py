"""Tidegate audio engine: drives PipeWire through pactl. No Qt in here."""
import copy
import json
import math
import os
import re
import subprocess
from array import array
from dataclasses import dataclass
from pathlib import Path

NBSP = "\u00a0"   # pactl splits module arguments on spaces, so labels use no-break spaces
VIRTUAL = (("tidegate_stream", "Tidegate Stream"), ("tidegate_record", "Tidegate Record"))
STREAM = VIRTUAL[0][0]
MIC_NAME, MIC_LABEL = "tidegate_mic", "Tidegate Microphone"
BUS_PREFIX = "tidegate_in_"
OWN = "tidegate_"
GENERIC = ("chromium", "chromium input", "webrtc voiceengine", "audio stream",
           "playback", "alsa plug-in", "pulseaudio", "unknown")
FORM = {"headset": ("Headset", "headphones"), "headphone": ("Headphones", "headphones"),
        "hands-free": ("Hands-free", "headphones"), "speaker": ("Speaker", "speaker"),
        "hdmi": ("HDMI", "speaker"), "internal": ("Internal", "speaker")}
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tidegate" / "config.json"


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout.strip()


def plist(kind):
    try:
        return json.loads(pactl("--format=json", "list", kind))
    except json.JSONDecodeError:
        return []


def percent(sink):
    try:
        ch = next(iter(sink["volume"].values()))
        return int(ch["value_percent"].rstrip("%"))
    except (KeyError, StopIteration, ValueError):
        return 100


def props(description, kind="sink"):
    text = description.replace('"', "").replace("'", "").replace(" ", NBSP)
    return f"{kind}_properties=device.description={text}"


def app_label(p):
    """Readable app name; Electron apps (Discord) report generic names, so use
    the executable name for those."""
    name = p.get("application.name") or p.get("media.name") or "Unknown"
    binary = Path(p.get("application.process.binary", "")).name
    if binary and name.lower().startswith(GENERIC):
        name = binary
    return name[:1].upper() + name[1:]


def level_from_pcm(data):
    """Peak of 16-bit mono PCM mapped from -60..0 dB to 0..1."""
    n = len(data) // 2
    if not n:
        return 0.0
    peak = max(abs(s) for s in array("h", data[: n * 2])) / 32768
    if peak <= 0.00002:
        return 0.0
    return min(1.0, max(0.0, (20 * math.log10(peak) + 60) / 60))


@dataclass
class Item:
    key: str
    label: str
    group: str            # app | mic | device | virtual
    icon: str = ""
    sub: str = ""
    volume: int = 100
    active: bool = True
    binary: str = ""
    app_id: str = ""


class Engine:
    """Every board input gets a null sink (its "bus"); every connection is a
    loopback from that bus to an output with its own volume and mute."""

    def __init__(self):
        cfg = self._read()
        self.board_in = [e for e in cfg.get("inputs", []) if isinstance(e, dict) and "key" in e]
        self.conns = self._parse_links(cfg.get("links", []))
        profiles = cfg.get("profiles", {})
        self.profiles = {n: p for n, p in profiles.items() if isinstance(p, dict)} \
            if isinstance(profiles, dict) else {}
        self.profile = cfg.get("profile") if cfg.get("profile") in self.profiles else ""
        self.auto_add = bool(cfg.get("auto_add", False))
        self.auto_connect = bool(cfg.get("auto_connect", False))   # off: you wire everything yourself
        self.out_colors = {k: v for k, v in (cfg.get("out_colors") or {}).items() if isinstance(v, str)}
        self.out_names = {k: v for k, v in (cfg.get("out_names") or {}).items() if isinstance(v, str)}
        self.mic_muted = False
        self.default_mic = bool(cfg.get("default_mic", False))
        self.prev_mic = cfg["prev_mic"] if isinstance(cfg.get("prev_mic"), str) else ""
        self.mics = set()
        self.dismissed = set()      # apps removed this session (not auto-added again)
        self.modules, self.buses, self.bus_mods = [], {}, {}
        self.links, self.loop, self.applied = {}, {}, {}
        self.known, self.outs = {}, {}

        existing = {s["name"] for s in plist("sinks")}
        for name, label in VIRTUAL:
            if name not in existing:
                self._load("module-null-sink", f"sink_name={name}", props(label))
        # A real (non-monitor) source, so Discord, browsers etc. list it as a microphone.
        if MIC_NAME not in {s["name"] for s in plist("sources")}:
            self._load("module-remap-source", f"master={STREAM}.monitor",
                       f"source_name={MIC_NAME}", props(MIC_LABEL, "source"))
        self.default = pactl("get-default-sink")
        if self.default_mic:
            self._apply_default_mic()
        self.board_out = cfg.get("outputs") or [n for n in (self.default, STREAM) if n]
        keys = {e["key"] for e in self.board_in}
        self.conns = {l: s for l, s in self.conns.items() if l[0] in keys and l[1] in self.board_out}

    # ---- persistence -------------------------------------------------------
    @staticmethod
    def _read():
        try:
            data = json.loads(CONFIG.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_links(items):
        out = {}
        for c in items if isinstance(items, list) else []:
            if isinstance(c, dict) and "in" in c and "out" in c:
                out[(c["in"], c["out"])] = {"vol": int(c.get("vol", 100)),
                                            "mute": bool(c.get("mute", False))}
        return out

    def _links_data(self):
        return [{"in": i, "out": o, **st} for (i, o), st in sorted(self.conns.items())]

    def save(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({
            "inputs": self.board_in, "outputs": self.board_out, "links": self._links_data(),
            "profiles": self.profiles, "profile": self.profile, "auto_add": self.auto_add,
            "auto_connect": self.auto_connect, "out_colors": self.out_colors,
            "out_names": self.out_names, "default_mic": self.default_mic,
            "prev_mic": self.prev_mic,
        }, indent=2))

    # ---- pactl plumbing ----------------------------------------------------
    def _load(self, *args):
        mod = pactl("load-module", *args)
        if mod.isdigit():
            self.modules.append(mod)
            return mod
        return None

    def _unload(self, mod):
        pactl("unload-module", mod)
        if mod in self.modules:
            self.modules.remove(mod)

    def bus(self, key, label):
        """Null sink that collects one app's streams."""
        if key in self.buses:
            return self.buses[key]
        name = BUS_PREFIX + re.sub(r"\W+", "_", key.lower())
        mod = self._load("module-null-sink", f"sink_name={name}", props(f"Tidegate bus - {label}"))
        self.bus_mods[key] = [mod] if mod else []
        self.buses[key] = name
        return name

    def _source(self, key):
        """What a connection reads from: a microphone directly, or an app's bus."""
        if key.startswith("mic:"):
            return key[4:] if key[4:] in self.mics else None
        return f"{self.buses[key]}.monitor" if key in self.buses else None

    def _muted(self, link):
        return self.conns[link]["mute"] or (self.mic_muted and link[1] == STREAM)

    def _reconcile(self, outs):
        """Tear down whatever the board no longer wants (removed cards, profile switch)."""
        keys = {e["key"] for e in self.board_in}
        for link in [l for l in self.links if l not in self.conns or l[0] not in keys
                     or l[1] not in self.board_out or l[1] not in outs
                     or self._source(l[0]) is None]:
            self.disconnect(*link)
        for key in [k for k in self.buses if k not in keys]:
            for mod in reversed(self.bus_mods.pop(key, [])):
                self._unload(mod)
            del self.buses[key]

    def scan(self):
        """Refresh devices and apps, keep board apps on their buses, apply routing."""
        sinks = plist("sinks")
        idx = {s["name"]: s["index"] for s in sinks}
        self.default = pactl("get-default-sink")
        labels = dict(VIRTUAL)
        outs = {}
        for s in sinks:
            n = s["name"]
            if n.startswith(BUS_PREFIX):
                continue
            if n.startswith(OWN):
                sub = f"Virtual mic: {MIC_LABEL}" if n == STREAM else "Virtual"
                outs[n] = Item(n, labels.get(n, s["description"]), "virtual", "virtual", sub, percent(s))
            else:
                ff = s.get("properties", {}).get("device.form_factor", "")
                sub, icon = FORM.get(ff, (ff.capitalize() or "Output", "speaker"))
                outs[n] = Item(n, s["description"], "device", icon, sub, percent(s))
        self.outs = outs
        self._reconcile(outs)

        for item in self.known.values():
            item.active = False
        streams, owner = {}, {}
        for s in plist("sink-inputs"):
            om = s.get("owner_module")
            if om not in (None, "n/a"):
                owner[str(om)] = s["index"]        # our loopbacks: module -> stream
                continue
            p = s.get("properties", {})
            streams.setdefault(app_label(p), []).append((s, p))
        board = {e["key"]: e for e in self.board_in}
        for label, items in streams.items():
            key = "app:" + label
            p = items[0][1]
            binary = Path(p.get("application.process.binary", "")).name.lower()
            item = Item(key, label, "app", p.get("application.icon_name") or binary,
                        binary=binary,
                        app_id=p.get("application.id") or p.get("pipewire.access.portal.app_id") or "")
            self.known[key] = item
            if key not in board and self.auto_add and key not in self.dismissed:
                self.add_input(item)
                board = {e["key"]: e for e in self.board_in}
            if key in board:
                entry = board[key]          # remember what is needed to find the app's icon later
                for field, value in (("icon", item.icon), ("binary", binary), ("app_id", item.app_id)):
                    entry[field] = entry.get(field) or value
                bus = self.bus(key, label)
                for s, _ in items:
                    if s["sink"] != idx.get(bus):
                        pactl("move-sink-input", str(s["index"]), bus)
        sources = {}
        for s in plist("sources"):
            if s["name"].endswith(".monitor") or s["name"].startswith(OWN):
                continue
            sources[s["name"]] = s["description"]
            key = "mic:" + s["name"]
            self.known[key] = Item(key, s["description"], "mic", "mic")
        self.mics = set(sources)
        for key, entry in board.items():
            if key.startswith("app:"):
                self.bus(key, entry["label"])

        for link in list(self.conns):
            if link[0] in board and self._source(link[0]) and link[1] in outs \
                    and link[1] in self.board_out:
                self.connect(*link)
        self.loop = {l: owner[m] for l, m in self.links.items() if m in owner}
        for link, stream in self.loop.items():
            if self.applied.get(link) != self.links[link]:
                st = self.conns[link]
                pactl("set-sink-input-volume", str(stream), f"{st['vol']}%")
                pactl("set-sink-input-mute", str(stream), "1" if self._muted(link) else "0")
                self.applied[link] = self.links[link]
        return self.known, outs

    # ---- connections -------------------------------------------------------
    def connect(self, ik, ok):
        source = self._source(ik)
        if (ik, ok) in self.links or not source:
            return
        mod = self._load("module-loopback", f"source={source}",
                         f"sink={ok}", "latency_msec=20",
                         "source_dont_move=true", "sink_dont_move=true")
        if mod:
            self.links[(ik, ok)] = mod

    def disconnect(self, ik, ok):
        mod = self.links.pop((ik, ok), None)
        self.loop.pop((ik, ok), None)
        self.applied.pop((ik, ok), None)
        if mod:
            self._unload(mod)

    def add_conn(self, ik, ok):
        self.conns[(ik, ok)] = {"vol": 100, "mute": False}
        self.save()

    def remove_conn(self, ik, ok):
        self.conns.pop((ik, ok), None)
        self.disconnect(ik, ok)
        self.save()

    def set_conn(self, ik, ok, vol=None, mute=None):
        st = self.conns[(ik, ok)]
        stream = self.loop.get((ik, ok))
        if vol is not None:
            st["vol"] = vol
            if stream is not None:
                pactl("set-sink-input-volume", str(stream), f"{vol}%")
        if mute is not None:
            st["mute"] = mute
            if stream is not None:
                pactl("set-sink-input-mute", str(stream), "1" if self._muted((ik, ok)) else "0")

    def set_mic_muted(self, on):
        """Silence Tidegate Microphone, i.e. everything sent to Tidegate Stream.
        Done twice (the virtual source and every loopback feeding the stream) so it
        holds even if one layer ignores the mute."""
        self.mic_muted = on
        pactl("set-source-mute", MIC_NAME, "1" if on else "0")
        for link, stream in self.loop.items():
            if link[1] == STREAM:
                pactl("set-sink-input-mute", str(stream), "1" if self._muted(link) else "0")

    # ---- board -------------------------------------------------------------
    def add_input(self, item):
        if any(e["key"] == item.key for e in self.board_in):
            return
        self.board_in.append({"key": item.key, "label": item.label, "icon": item.icon,
                              "binary": item.binary, "app_id": item.app_id})
        if self.auto_connect and item.group == "app" and self.default in self.board_out:
            self.conns[(item.key, self.default)] = {"vol": 100, "mute": False}
        self.save()

    def remove_input(self, key):
        self.dismissed.add(key)
        self.board_in = [e for e in self.board_in if e["key"] != key]
        self.conns = {l: s for l, s in self.conns.items() if l[0] != key}
        self.save()

    def rename_input(self, key, name):
        for entry in self.board_in:
            if entry["key"] == key:
                entry["name"] = name
        self.save()

    def add_output(self, key):
        if key not in self.board_out:
            self.board_out.append(key)
            self.save()

    def remove_output(self, key):
        self.board_out = [o for o in self.board_out if o != key]
        self.conns = {l: s for l, s in self.conns.items() if l[1] != key}
        self.save()

    def retarget_conn(self, ik, old, new):
        """Move a connection to another output, keeping its volume and mute."""
        if (ik, old) in self.conns and (ik, new) not in self.conns and new in self.board_out:
            self.conns[(ik, new)] = self.conns.pop((ik, old))
            self.save()

    def rename_output(self, key, name):
        if name:
            self.out_names[key] = name
        else:
            self.out_names.pop(key, None)
        self.save()

    def set_out_color(self, key, color):
        self.out_colors[key] = color
        self.save()

    def set_default_mic(self, on):
        """Make Tidegate Microphone the system's default input (restored on exit)."""
        self.default_mic = on
        if on:
            self._apply_default_mic()
        else:
            self._restore_default_mic()
        self.save()

    def _apply_default_mic(self):
        current = pactl("get-default-source")
        if current and current != MIC_NAME:
            self.prev_mic = current
        pactl("set-default-source", MIC_NAME)

    def _restore_default_mic(self):
        if self.prev_mic:
            pactl("set-default-source", self.prev_mic)

    def set_default(self, sink):
        pactl("set-default-sink", sink)
        self.default = sink

    @staticmethod
    def volume(sink, value):
        pactl("set-sink-volume", sink, f"{value}%")

    @staticmethod
    def mute(sink, on):
        pactl("set-sink-mute", sink, "1" if on else "0")

    # ---- profiles ----------------------------------------------------------
    def save_profile(self, name):
        self.profiles[name] = {"inputs": copy.deepcopy(self.board_in),
                               "outputs": list(self.board_out), "links": self._links_data()}
        self.profile = name
        self.save()

    def delete_profile(self, name):
        self.profiles.pop(name, None)
        if self.profile == name:
            self.profile = ""
        self.save()

    def apply_profile(self, name):
        p = self.profiles.get(name)
        if not p:
            return False
        self.board_in = [e for e in copy.deepcopy(p.get("inputs", [])) if isinstance(e, dict) and "key" in e]
        self.board_out = list(p.get("outputs", []))
        self.conns = self._parse_links(p.get("links", []))
        self.profile = name
        self.save()
        return True

    def close(self):
        self.save()
        if self.default_mic:
            self._restore_default_mic()
        for mod in reversed(self.modules):
            pactl("unload-module", mod)
