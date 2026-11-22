"""Matching apps to .desktop entries (the basis for real app icons). No Qt needed."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tidegate import desktop as D  # noqa: E402


class DesktopIndexTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, name, text, base=None):
        folder = (base or self.root) / "applications"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)

    def index(self, *extra):
        return D.build_index([self.root, *extra])

    def test_matches_program_name_and_returns_the_icon(self):
        self.write("spotify.desktop", "[Desktop Entry]\nName=Spotify\nExec=spotify %U\nIcon=spotify-client\n")
        self.assertEqual(D.lookup(self.index(), "", "spotify"), "spotify-client")

    def test_matches_window_class_name_and_desktop_id(self):
        self.write("org.example.Player.desktop",
                   "[Desktop Entry]\nName=Fancy Player\nExec=/opt/x/run\nStartupWMClass=FancyWM\nIcon=fancy\n")
        index = self.index()
        for hint in ("fancywm", "Fancy Player", "org.example.Player"):
            self.assertEqual(D.lookup(index, hint), "fancy", hint)

    def test_flatpak_exec_registers_the_app_id(self):
        self.write("discord.desktop", "[Desktop Entry]\nName=Discord\nIcon=com.discordapp.Discord\n"
                   "Exec=/usr/bin/flatpak run --branch=stable --command=discord com.discordapp.Discord @@u %U @@\n")
        index = self.index()
        self.assertEqual(D.lookup(index, "com.discordapp.discord"), "com.discordapp.Discord")
        self.assertIsNone(D.lookup(index, "flatpak"))

    def test_env_wrappers_are_skipped(self):
        self.write("game.desktop", "[Desktop Entry]\nName=Game\nExec=env FOO=1 BAR=2 mygame --fullscreen\nIcon=game-icon\n")
        self.assertEqual(D.lookup(self.index(), "mygame"), "game-icon")

    def test_first_directory_wins_and_icon_less_entries_are_ignored(self):
        other = self.root / "other"
        self.write("app.desktop", "[Desktop Entry]\nName=App\nExec=app\nIcon=user-icon\n")
        self.write("app.desktop", "[Desktop Entry]\nName=App\nExec=app\nIcon=system-icon\n", base=other)
        self.write("none.desktop", "[Desktop Entry]\nName=None\nExec=none\n", base=other)
        index = self.index(other)
        self.assertEqual(D.lookup(index, "app"), "user-icon")
        self.assertIsNone(D.lookup(index, "none"))

    def test_generic_icon_names_are_recognized(self):
        for name in ("applications-games", "applications-multimedia", "audio-x-generic", "chromium", "", None):
            self.assertTrue(D.is_generic(name), name)
        for name in ("spotify-client", "org.vinegarhq.Sober", "discord"):
            self.assertFalse(D.is_generic(name), name)

    def test_icon_file_prefers_scalable_then_largest(self):
        for size in ("48x48", "256x256", "scalable"):
            folder = self.root / "icons" / "hicolor" / size / "apps"
            folder.mkdir(parents=True)
            (folder / ("app.svg" if size == "scalable" else "app.png")).write_text("x")
        self.assertTrue(D.icon_file("app", [self.root]).endswith("scalable/apps/app.svg"))
        (self.root / "icons" / "hicolor" / "scalable" / "apps" / "app.svg").unlink()
        self.assertTrue(D.icon_file("app", [self.root]).endswith("256x256/apps/app.png"))
        self.assertIsNone(D.icon_file("missing", [self.root]))

    def test_icon_file_falls_back_to_pixmaps(self):
        (self.root / "pixmaps").mkdir()
        (self.root / "pixmaps" / "old.xpm").write_text("x")
        self.assertTrue(D.icon_file("old", [self.root]).endswith("pixmaps/old.xpm"))

    def test_only_the_main_group_is_read(self):
        self.write("x.desktop", "[Desktop Entry]\nName=X\nExec=x\nIcon=x-icon\n"
                   "[Desktop Action New]\nName=New\nExec=x --new\nIcon=other\n")
        self.assertEqual(D.lookup(self.index(), "x"), "x-icon")


if __name__ == "__main__":
    unittest.main()
