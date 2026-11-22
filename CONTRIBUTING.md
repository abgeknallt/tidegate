# Contributing

Thanks for helping! Bug reports and pull requests are welcome.

## Setup

```sh
git clone https://github.com/abgeknallt/tidegate && cd tidegate
PYTHONPATH=src python -m tidegate          # run from the source tree
python -m unittest discover -s tests -v    # run the tests
```

You need PipeWire with `pipewire-pulse`, `pactl`/`parec` (libpulse) and PySide6.

## Layout

| Path | What |
| --- | --- |
| `src/tidegate/engine.py` | Everything that talks to PipeWire (via `pactl`). No Qt in here. |
| `src/tidegate/widgets.py` | Cards, rows, meters, wires, theme |
| `src/tidegate/window.py` | Main window and menus |
| `src/tidegate/tray.py`, `control.py`, `meters.py`, `system.py` | Tray, single-instance + CLI control, level meters, autostart |
| `src/tidegate/icons.py`, `desktop.py` | App icon lookup: icon theme, `.desktop` files, letter tile |
| `tests/` | Engine tests against a fake `pactl` |

## Guidelines

- Keep audio logic in `engine.py` and cover it with a test; the engine is tested
  without a sound server.
- UI changes: include a screenshot in the pull request. Screenshots for the README
  live in `docs/screenshots` (PNG, about 1000 px wide, no personal data in them).
- Keep it small and readable; no new dependencies without a good reason.
