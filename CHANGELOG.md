# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Screenshots in the README (`docs/screenshots`)

### Changed
- Removed an unused helper and an unused style rule
- `.gitattributes` keeps line endings consistent and marks screenshots as binary

## [0.5.2] - 2026-11-22

### Fixed
- Apps that report a generic category icon (for example a gamepad for Sober) now
  get their real icon, found through the Flatpak app id and the `.desktop` file
- Icons that the icon theme does not know (Flatpak, Snap) are loaded straight from
  the `hicolor` and `pixmaps` folders

## [0.5.1] - 2026-11-21

### Added
- Real app icons, resolved through the icon theme and installed `.desktop` files
  (including Flatpak and Snap); a colored letter tile when nothing matches
- Settings option to use Tidegate Microphone as the system default microphone
  (the previous default is restored on exit)
- `tidegate --diagnose` prints the audio setup for bug reports

### Changed
- Microphones are connected directly to their outputs instead of through an extra
  bus and loopback, which is more reliable
- A microphone that is unplugged and plugged back in reconnects by itself

## [0.5.0] - 2026-11-20

First public release.

### Added
- Board with inputs (apps, microphones) on the left and outputs on the right;
  every connection has its own volume and mute
- Live level meters on all inputs and outputs
- Profiles (save and switch the whole board), also via `Ctrl+1..9`, tray and CLI
- System tray icon with mute status, quick mute and profile menu; closing the
  window keeps Tidegate running
- Virtual output *Tidegate Stream* that doubles as the microphone *Tidegate
  Microphone*, plus *Tidegate Record*
- *Mute mic* silences Tidegate Microphone
- Remote control for global shortcuts: `--mic-mute`, `--profile`, `--show`, `--quit`
- Rename inputs and outputs, wire colors, move connections between outputs,
  set the default output from a card
- Optional auto-add of new apps, auto-connect to the default output, start at login
- Installer with install, uninstall, per-user and system-wide modes
