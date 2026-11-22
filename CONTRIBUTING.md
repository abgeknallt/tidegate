# Contributing

Thanks for helping! Bug reports and pull requests are welcome. Tidegate is a small
project, so a bit of context goes a long way — please read the short sections below
before opening an issue or a PR.

## Before you start

- **Bug reports:** include your distribution, PipeWire version, the steps that lead
  to the problem, and the output of `tidegate --diagnose`. That covers most of what
  we would ask for anyway.
- **Big changes:** open an issue first so we can agree on the approach before you
  spend time on code.
- **Small fixes:** just send the PR.

## Setup

You need PipeWire with `pipewire-pulse`, `pactl`/`parec` (libpulse) and PySide6.

```sh
git clone https://github.com/abgeknallt/tidegate && cd tidegate
PYTHONPATH=src python -m tidegate          # run from the source tree
python -m unittest discover -s tests -v    # run the tests
```

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

- Keep audio logic in `engine.py` and cover it with a test. The engine is tested
  without a sound server, so tests must not need one.
- UI changes: attach a screenshot to the pull request.
- README screenshots live in `docs/screenshots`: PNG, about 1000 px wide, no
  personal data (real names, window titles, server names) visible.
- Keep it small and readable. No new dependencies without a good reason.
- Match the style of the surrounding code; no drive-by reformatting.

## Commits and pull requests

- One topic per PR. Unrelated cleanups belong in their own branch.
- Write commit subjects in the imperative mood (`engine: unload loopback on remove`).
- Describe *why* in the body, not just *what* — the diff already shows the what.
- Note the behaviour change in `CHANGELOG.md` if a user would notice it.
- A PR is ready when the tests pass and the branch is rebased on `main`.

## License

By contributing you agree that your work is released under the [MIT license](LICENSE).
