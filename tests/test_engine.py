"""Engine tests. They run against a fake pactl: no audio system and no Qt needed."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidegate import engine as E  # noqa: E402

STREAM, MIC = "tidegate_stream", "tidegate_mic"


class FakePactl:
    """Just enough of pactl/PipeWire to drive the engine."""

    def __init__(self):
        self.calls, self.next_module = [], 100
        self.state = {
            "sinks": [
                {"name": "speakers", "index": 1, "description": "Speakers",
                 "volume": {"fl": {"value_percent": "70%"}}, "properties": {"device.form_factor": "speaker"}},
                {"name": "headset", "index": 3, "description": "Headset", "volume": {},
                 "properties": {"device.form_factor": "headset"}},
            ],
            "sink-inputs": [
                {"index": 10, "sink": 1, "owner_module": None,
                 "properties": {"application.name": "Chromium", "application.process.binary": "Discord"}},
            ],
            "sources": [
                {"name": "usb_mic", "description": "USB Mic"},
                {"name": "speakers.monitor", "description": "Monitor of Speakers"},
            ],
        }

    def pactl(self, *args):
        self.calls.append(args)
        if args[0] == "load-module":
            self.next_module += 1
            if args[1] == "module-null-sink":
                name = next(a for a in args if a.startswith("sink_name="))[len("sink_name="):]
                self.state["sinks"].append({"name": name, "index": 50 + self.next_module,
                                            "description": name, "volume": {}, "properties": {}})
            if args[1] == "module-remap-source":
                self.state["sources"].append({"name": MIC, "description": "Tidegate Microphone"})
            return str(self.next_module)
        if args[0] == "get-default-sink":
            return "speakers"
        return ""

    def plist(self, kind):
        return self.state[kind]

    def show_loopbacks(self, engine):
        """Make the loopback streams of live links visible, as PipeWire would."""
        have = {s["owner_module"] for s in self.state["sink-inputs"]}
        for mod in engine.links.values():
            if mod not in have:
                self.state["sink-inputs"].append(
                    {"index": 200 + int(mod), "sink": 1, "owner_module": mod, "properties": {}})


class HelperTest(unittest.TestCase):
    def test_props_never_contain_plain_spaces(self):
        arg = E.props("Tidegate Stream")
        self.assertNotIn(" ", arg)
        self.assertIn("Tidegate\u00a0Stream", arg)

    def test_generic_app_names_fall_back_to_the_binary(self):
        self.assertEqual(E.app_label({"application.name": "Chromium",
                                      "application.process.binary": "/usr/bin/discord"}), "Discord")
        self.assertEqual(E.app_label({"application.name": "Spotify"}), "Spotify")

    def test_level_meter_scale(self):
        loud = struct.pack("<200h", *([30000] * 200))
        quiet = struct.pack("<200h", *([100] * 200))
        floor = struct.pack("<200h", *([10] * 200))
        self.assertGreater(E.level_from_pcm(loud), 0.95)
        self.assertTrue(0 < E.level_from_pcm(quiet) < 0.3)
        self.assertEqual(E.level_from_pcm(floor), 0)
        self.assertEqual(E.level_from_pcm(b""), 0)


class EngineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fake = FakePactl()
        saved = (E.pactl, E.plist, E.CONFIG)
        E.pactl, E.plist, E.CONFIG = self.fake.pactl, self.fake.plist, Path(tmp.name) / "config.json"
        self.addCleanup(lambda: (setattr(E, "pactl", saved[0]), setattr(E, "plist", saved[1]),
                                 setattr(E, "CONFIG", saved[2])))
        self.config = E.CONFIG

    def engine(self):
        return E.Engine()

    def board(self):
        """Engine with Discord and the USB mic on the board, scanned once."""
        eng = self.engine()
        known, _ = eng.scan()
        eng.add_input(known["app:Discord"])
        eng.add_input(known["mic:usb_mic"])
        return eng

    def test_virtual_devices_are_created(self):
        self.engine()
        loaded = [c for c in self.fake.calls if c[0] == "load-module"]
        self.assertTrue(any(f"sink_name={STREAM}" in c for c in loaded))
        self.assertTrue(any("module-remap-source" in c and f"master={STREAM}.monitor" in c for c in loaded))

    def test_scan_lists_apps_mics_and_outputs(self):
        known, outs = self.engine().scan()
        self.assertEqual(known["app:Discord"].label, "Discord")
        self.assertIn("mic:usb_mic", known)
        self.assertNotIn("mic:tidegate_mic", known)       # our own mic is never offered as input
        self.assertEqual((outs["headset"].sub, outs["headset"].icon), ("Headset", "headphones"))
        self.assertEqual(outs[STREAM].label, "Tidegate Stream")

    def test_nothing_connects_automatically(self):
        eng = self.board()
        eng.scan()
        self.assertEqual(eng.conns, {})
        self.assertEqual(eng.links, {})

    def test_auto_connect_is_opt_in(self):
        eng = self.engine()
        eng.auto_connect = True
        known, _ = eng.scan()
        eng.add_input(known["app:Discord"])
        self.assertIn(("app:Discord", "speakers"), eng.conns)

    def test_inputs_can_feed_any_outputs_with_own_volume(self):
        eng = self.board()
        eng.add_output("headset")
        for link in (("mic:usb_mic", STREAM), ("mic:usb_mic", "headset"), ("app:Discord", "speakers")):
            eng.add_conn(*link)
        eng.scan()
        self.assertEqual(len(eng.links), 3)
        self.assertTrue(any(c[0] == "move-sink-input" and c[1] == "10" for c in self.fake.calls))
        self.fake.show_loopbacks(eng)
        eng.scan()
        eng.set_conn("mic:usb_mic", STREAM, vol=40)
        stream = eng.loop[("mic:usb_mic", STREAM)]
        self.assertIn(("set-sink-input-volume", str(stream), "40%"), self.fake.calls)

    def test_mute_mic_silences_only_what_goes_to_the_stream(self):
        eng = self.board()
        eng.add_output("headset")
        eng.add_conn("mic:usb_mic", STREAM)
        eng.add_conn("mic:usb_mic", "headset")
        eng.scan()
        self.fake.show_loopbacks(eng)
        eng.scan()
        self.fake.calls.clear()
        eng.set_mic_muted(True)
        self.assertIn(("set-source-mute", MIC, "1"), self.fake.calls)
        self.assertIn(("set-sink-input-mute", str(eng.loop[("mic:usb_mic", STREAM)]), "1"), self.fake.calls)
        self.assertNotIn(("set-sink-input-mute", str(eng.loop[("mic:usb_mic", "headset")]), "1"),
                         self.fake.calls)
        eng.set_mic_muted(False)
        self.assertIn(("set-source-mute", MIC, "0"), self.fake.calls)

    def test_retarget_keeps_volume_and_mute(self):
        eng = self.board()
        eng.add_output("headset")
        eng.add_conn("app:Discord", "speakers")
        eng.set_conn("app:Discord", "speakers", vol=35, mute=True)
        eng.retarget_conn("app:Discord", "speakers", "headset")
        eng.scan()
        self.assertNotIn(("app:Discord", "speakers"), eng.links)
        self.assertIn(("app:Discord", "headset"), eng.links)
        self.assertEqual(eng.conns[("app:Discord", "headset")], {"vol": 35, "mute": True})

    def test_removing_an_input_tears_down_its_bus_and_links(self):
        eng = self.board()
        eng.add_conn("app:Discord", "speakers")
        eng.scan()
        self.assertIn("app:Discord", eng.buses)
        eng.remove_input("app:Discord")
        eng.scan()
        self.assertNotIn("app:Discord", eng.buses)
        self.assertNotIn(("app:Discord", "speakers"), eng.links)

    def test_profiles_round_trip_and_persist(self):
        eng = self.board()
        eng.add_conn("app:Discord", "speakers")
        eng.save_profile("Call")
        eng.remove_conn("app:Discord", "speakers")
        self.assertTrue(eng.apply_profile("Call"))
        eng.scan()
        self.assertIn(("app:Discord", "speakers"), eng.links)
        eng.close()
        again = self.engine()
        self.assertEqual((again.profile, list(again.profiles)), ("Call", ["Call"]))

    def test_output_names_and_colors_persist(self):
        eng = self.engine()
        eng.rename_output("headset", "My Headset")
        eng.set_out_color("headset", "#ff0000")
        again = self.engine()
        self.assertEqual(again.out_names, {"headset": "My Headset"})
        self.assertEqual(again.out_colors, {"headset": "#ff0000"})

    def test_apps_can_be_auto_added(self):
        eng = self.engine()
        eng.auto_add = True
        eng.scan()
        self.assertEqual([e["key"] for e in eng.board_in], ["app:Discord"])

    def test_old_or_broken_config_never_crashes(self):
        for text in ('{"links": [["a", "b"]], "hidden": ["x"]}', "[1, 2, 3]", "not json", "{}"):
            self.config.write_text(text)
            self.assertEqual(self.engine().conns, {})
        self.config.write_text(json.dumps({"profiles": [], "outputs": None}))
        self.engine()


if __name__ == "__main__":
    unittest.main()
