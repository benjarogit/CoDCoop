#!/bin/sh
# One-command installer for Linux: downloads the ready package (United Offensive
# 1.51 + the co-op, about 1 GB), extracts it and installs it.
#
#   curl -fsSL https://raw.githubusercontent.com/benjarogit/CoDCoop/master/tools/install.sh | sh
#
# or save it and run:  sh install.sh [--game "/path/to/Call of Duty"] [--check]
#
# Everything else is automatic: the game folder is detected (Steam, AnkerGames,
# current folder), Call of Duty 1.5 is installed from the package if needed, and
# existing files are kept as .bak. Nothing else has to be downloaded or unpacked.
set -eu

# "curl ... | sh" hands the script a pipe as stdin, so every question would be
# answered by the end of the download. Switch back to the terminal when there
# is one; with --yes the installer stays non-interactive anyway.
if [ ! -t 0 ] && [ -r /dev/tty ]; then
    exec </dev/tty
fi

REPO=benjarogit/CoDCoop
TAG=${COD_COOP_TAG:-v0.5.4}
URL=${COD_COOP_URL:-"https://github.com/$REPO/releases/download/$TAG/Call-of-Duty-UO-Coop-Ready.zip"}

# run from the extracted package: everything is already there, nothing to download
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$HERE/game/CoDUOSP.exe" ] && [ -f "$HERE/install-linux.py" ]; then
    exec python3 "$HERE/install-linux.py" "$@"
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required (sudo apt install python3 / sudo dnf install python3)" >&2
    exit 1
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/cod-coop.XXXXXX")
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "Downloading Call of Duty - UO Coop Ready (~1 GB)..."
if command -v curl >/dev/null 2>&1; then
    curl -fL --progress-bar -o "$TMP/ready.zip" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress -O "$TMP/ready.zip" "$URL"
else
    echo "curl or wget is required." >&2
    exit 1
fi

echo "Extracting..."
python3 -m zipfile -e "$TMP/ready.zip" "$TMP/x"

DIR="$TMP/x/Call of Duty - UO Coop Ready"
if [ ! -f "$DIR/install-linux.py" ]; then
    echo "Unexpected package layout - please report this." >&2
    exit 1
fi

python3 "$DIR/install-linux.py" "$@"