#!/usr/bin/env bash
# Tidegate installer / uninstaller
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HOME/.local"
SYSTEM=no
DEPS=yes
ACTION=install

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Tidegate installer

Usage: ./install.sh [options]

  --prefix DIR   install below DIR (default: ~/.local)
  --system       install system-wide to /usr/local (uses sudo)
  --no-deps      skip the dependency check
  --uninstall    remove Tidegate
  -h, --help     show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)    [[ $# -ge 2 ]] || die "--prefix needs a directory"; PREFIX="$2"; shift ;;
    --system)    SYSTEM=yes; PREFIX=/usr/local ;;
    --no-deps)   DEPS=no ;;
    --uninstall) ACTION=uninstall ;;
    -h|--help)   usage; exit 0 ;;
    *)           usage; die "unknown option: $1" ;;
  esac
  shift
done

run() {
  if [[ $SYSTEM == yes && $EUID -ne 0 ]]; then sudo "$@"; else "$@"; fi
}

LIB="$PREFIX/lib/tidegate"
BIN="$PREFIX/bin/tidegate"
DESKTOP="$PREFIX/share/applications/tidegate.desktop"
ICON="$PREFIX/share/icons/hicolor/scalable/apps/tidegate.svg"

refresh_caches() {
  if command -v update-desktop-database >/dev/null; then
    run update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
  fi
  if command -v gtk-update-icon-cache >/dev/null; then
    run gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
  fi
}

check_deps() {
  local missing=()
  command -v pactl >/dev/null || missing+=(libpulse)
  python3 -c 'import PySide6' 2>/dev/null || missing+=(pyside6)
  [[ ${#missing[@]} -eq 0 ]] && return 0
  if command -v pacman >/dev/null; then
    say "Installing dependencies: ${missing[*]}"
    sudo pacman -S --needed --noconfirm "${missing[@]}"
  else
    die "missing: ${missing[*]} (provides pactl / PySide6 for Python 3). Install them and re-run."
  fi
}

do_install() {
  [[ $DEPS == yes ]] && check_deps
  if command -v pactl >/dev/null && ! pactl info 2>/dev/null | grep -qi pipewire; then
    say "Warning: PipeWire (pipewire-pulse) does not seem to be running."
  fi

  say "Installing to $PREFIX"
  run install -d "$LIB" "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
  run rm -rf "$LIB/tidegate"
  run cp -r "$SRC/src/tidegate" "$LIB/"
  run find "$LIB" -name __pycache__ -prune -exec rm -rf {} +

  local tmp; tmp="$(mktemp)"
  cat >"$tmp" <<EOF
#!/usr/bin/env bash
exec env PYTHONPATH="$LIB\${PYTHONPATH:+:\$PYTHONPATH}" python3 -m tidegate "\$@"
EOF
  run install -m755 "$tmp" "$BIN"

  sed "s|@EXEC@|$BIN|" "$SRC/data/tidegate.desktop" >"$tmp"
  run install -m644 "$tmp" "$DESKTOP"
  rm -f "$tmp"
  run install -m644 "$SRC/data/tidegate.svg" "$ICON"
  refresh_caches

  say "Done. Start Tidegate from your app menu or run: tidegate"
  case ":$PATH:" in *":$(dirname "$BIN"):"*) ;; *) say "Note: $(dirname "$BIN") is not in your PATH." ;; esac
}

do_uninstall() {
  say "Removing Tidegate from $PREFIX"
  run rm -rf "$LIB"
  run rm -f "$BIN" "$DESKTOP" "$ICON"
  refresh_caches
  say "Removed."
}

if [[ $ACTION == install ]]; then do_install; else do_uninstall; fi
