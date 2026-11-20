<p align="center">
  <img src="data/tidegate.svg" width="112" alt="Tidegate logo">
</p>

<h1 align="center">Tidegate</h1>

<p align="center">
  <i>The MixLine alternative for Linux.</i>
</p>

<p align="center">
  <a href="https://github.com/abgeknallt/tidegate/actions/workflows/ci.yml"><img src="https://github.com/abgeknallt/tidegate/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license">
  <img src="https://img.shields.io/badge/PipeWire-required-informational" alt="PipeWire">
  <img src="https://img.shields.io/badge/status-0.5.0-orange" alt="Status">
</p>

> **Early software.** 0.5.0 works, but the CLI, config format and UI can still
> change between releases. Tidegate never touches your system config and undoes
> everything it did when you quit — a crash costs you a `pipewire-pulse` restart.

<!-- Screenshot: save it as docs/screenshot.png and uncomment.
<p align="center"><img src="docs/screenshot.png" alt="Tidegate board with inputs, outputs and wires" width="820"></p>
-->

## Why

PipeWire can route anything anywhere — but only through tools that make you think
in nodes and ports, and forget everything afterwards. Tidegate gives you the board
you actually want:

- Discord loud in your headphones, the same game silent on stream.
- A mic device that only carries what you put on it.
- One click between "Gaming", "Stream" and "Call".
- Nothing wired up behind your back.

If you just need to move one stream once, a plain patchbay is fine. Tidegate is for
the setup you rebuild every evening.

## MixLine alternative for Linux

[MIXLINE](https://www.logitechg.com/en-us/software/mixline) by Logitech G does what
Tidegate does: draw lines between inputs and outputs, set a level per route, keep
one mix for yourself and another for your audience. It ships for Windows and macOS.
On Linux there was nothing like it, so Tidegate is that — the same two-column
board, per-wire volume, profiles and a virtual mic, built on PipeWire.

| | MIXLINE | Tidegate |
| --- | --- | --- |
| Platform | Windows, macOS | Linux |
| Price | free, Logitech G account | MIT, free |
| Patchbay with wires | yes | yes |
| Per-connection volume | yes | yes |
| Virtual microphone | yes | yes |
| Profiles | yes | yes |
| Effects, built-in recorder, dual-PC | yes | not yet |

The differences that matter: MIXLINE installs its own audio driver and hooks into
Streamlabs. Tidegate uses the PipeWire modules that are already running, needs no
root, leaves no driver behind and is gone from your system again after
`./install.sh --uninstall`. If you need effects or a recorder, MIXLINE is ahead —
on Linux put [EasyEffects](https://github.com/wwmm/easyeffects) in front of
Tidegate instead.

## Features

**Routing**
- Per-connection volume and mute. One input can feed several outputs, each at its
  own level — full in your ears, off in the recording.
- You decide every connection. Move a wire to another output, rename outputs, pick
  its color, remove it.
- Live level meters on every input and output, so you see where audio actually flows.

**Microphone**
- **Tidegate Stream** doubles as the input device **Tidegate Microphone**, which
  Discord, browsers and games list as a normal mic.
- **Mute mic** silences it in one keystroke, with a red tray dot while active.

**Workflow**
- Profiles store the whole board and switch via click, `Ctrl+1..9`, tray or CLI.
- Tray icon with quick mute, profile menu and status; closing the window keeps
  Tidegate running.
- Optional: auto-add new apps, auto-connect new inputs, start minimized at login.
- The board is remembered between runs. All audio changes are reverted on quit.

## Install

**Dependencies:** PipeWire with `pipewire-pulse`, `pactl` and `parec`
(`libpulse` / `pulseaudio-utils`), Python 3 with PySide6.

Both X11 and Wayland work; on Wayland global hotkeys go through your desktop's
shortcut settings (see below).

```sh
git clone https://github.com/abgeknallt/tidegate && cd tidegate
./install.sh              # for your user, to ~/.local
./install.sh --system     # system-wide, to /usr/local
./install.sh --uninstall  # remove again
```

The installer pulls missing dependencies via pacman on Arch-based systems
(CachyOS, Arch, Manjaro). On others install `pactl`/`parec` and PySide6 first and
run `./install.sh --no-deps`. Make sure `~/.local/bin` is in your `PATH`.

Arch users: [`packaging/arch`](packaging/arch) has a `PKGBUILD`.

## Quick start

1. **Add input** (top left) — a running app or a microphone.
2. **Add output** (top right) — speakers, headphones or a virtual device.
3. Hit **+** on an input and choose an output. Use **⋮** on the wire (or right
   click) to move or remove it.
4. Save it as a profile so you can get back to it.

An app only appears in the list after it has opened an audio stream. Once added it
stays on the board and is dimmed while idle.

### Calls and streams

Connect your mic and everything else the other side should hear to
**Tidegate Stream**, then select **Tidegate Microphone** as input in Discord, your
browser or the recording app. In OBS, capture **Monitor of Tidegate Record**
instead.

Don't route the app that *receives* the call into Tidegate Stream — the other side
will hear itself.

### Global shortcuts

Wayland won't let apps grab global keys, so bind these commands in your desktop
(KDE: *System Settings → Keyboard → Shortcuts → Add Command*):

| Command | Does |
| --- | --- |
| `tidegate --mic-mute` | toggle *Mute mic* |
| `tidegate --profile Gaming` | switch to profile "Gaming" |
| `tidegate --show` / `--quit` | show window / quit |
| `tidegate --minimized` | start hidden in tray |

In the window: `Ctrl+M` toggles *Mute mic*, `Ctrl+1..9` picks profiles.

## How it works

Tidegate shells out to `pactl` and `parec` only. No daemon, no root, no config
rewriting.

- Every input gets a null sink as its bus; the app's streams are moved onto it.
- Every wire is a 20 ms `module-loopback` from that bus to an output. The wire's
  slider is the loopback's volume.
- *Tidegate Stream* is a null sink, *Tidegate Microphone* a `module-remap-source`
  on its monitor — which is why apps treat it as a real mic.
- Meters read bus and output monitors through a short-lived `parec`.
- On exit, every module Tidegate loaded is unloaded again.

Board and settings: `~/.config/tidegate/config.json`.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| App missing from *Add input* | It must have played audio once. Start playback, reopen the menu. |
| Added app is silent | It sits on its own bus now. Press **+** on its card and wire it to an output. |
| *Tidegate Microphone* not listed in Discord/browser | Restart the app after Tidegate started. Verify with `pactl list short sources \| grep tidegate`. |
| Meters don't move | `parec` missing (`libpulse`). |
| Devices left after a crash | `pactl list short modules \| grep -i tidegate`, unload each id, or `systemctl --user restart pipewire-pulse`. |

## Limitations

- *Mute mic* silences everything sent to Tidegate Stream, not physical devices.
- No effects yet (noise suppression, EQ, compressor) — use EasyEffects for now.
- No built-in recorder or streaming; feed OBS or the app of your choice.
- Output volumes are left to the system and not saved by Tidegate.

## Development

```sh
PYTHONPATH=src python -m tidegate           # run from the source tree
python -m unittest discover -s tests -v     # tests, no sound server needed
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md). Bug
reports with your PipeWire version and the output of `pactl list short modules`
are gold.

## License

[MIT](LICENSE)
