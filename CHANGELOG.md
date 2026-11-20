# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
