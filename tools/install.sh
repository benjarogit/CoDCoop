#!/bin/sh
# One-command installer for Linux: downloads the 0.6 setup AppImage (it carries
# the complete pinned suite: CoD 1, UO, SP Improved, United Fronts and the YAP
# plugin), verifies its SHA-256 and starts the terminal setup.
#
#   curl -fsSL https://raw.githubusercontent.com/benjarogit/CoDCoop/v0.6.0/tools/install.sh | sh
#
# or save it and run:  sh install.sh [--game "/path/to/Call of Duty"] [--check]
#
# Without --yes the setup asks the same questions as the Windows installer. A
# graphical window is available by running the downloaded AppImage directly.
set -eu

# "curl ... | sh" hands the script a pipe as stdin, so every question would be
# answered by the end of the download. Switch back to the terminal when there
# is one; with --yes the setup stays non-interactive anyway.
if [ ! -t 0 ] && (exec </dev/tty) 2>/dev/null; then
    exec </dev/tty
fi

REPO=benjarogit/CoDCoop
TAG=${COD_COOP_TAG:-0.6.0}
ASSET=Install-CoD-Coop-Linux-x86_64.AppImage
SHA256=${COD_COOP_APPIMAGE_SHA:-d47b399d311ccfea2f13aa9165ec46e40da899d5c5fb081e5da82a75d5534c66}
URL=${COD_COOP_URL:-"https://github.com/$REPO/releases/download/$TAG/$ASSET"}

# Run from an unpacked release: everything is already there.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$HERE/install-linux.py" ] && [ -f "$HERE/coop_suite.py" ]; then
    exec python3 "$HERE/install-linux.py" "$@"
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required (sudo apt install python3 / sudo dnf install python3)" >&2
    exit 1
fi

SHA256=$(printf '%s' "$SHA256" | tr 'A-F' 'a-f')
case "$SHA256" in
    *[!0-9a-f]*|'') echo "No pinned SHA-256 for $ASSET; use a release installer." >&2; exit 1 ;;
esac
if [ "${#SHA256}" -ne 64 ]; then
    echo "The pinned SHA-256 for $ASSET is invalid." >&2
    exit 1
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/cod-coop.XXXXXX")
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "Downloading CoDCoop 0.6 setup (${ASSET})..."
if command -v curl >/dev/null 2>&1; then
    curl -fL --progress-bar -o "$TMP/$ASSET" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress -O "$TMP/$ASSET" "$URL"
else
    echo "curl or wget is required." >&2
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$TMP/$ASSET" | cut -d' ' -f1)
elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$TMP/$ASSET" | cut -d' ' -f1)
else
    echo "sha256sum or shasum is required to verify the download." >&2
    exit 1
fi
if [ "$actual" != "$SHA256" ]; then
    echo "Checksum mismatch for $ASSET; the download was discarded." >&2
    exit 1
fi

chmod +x "$TMP/$ASSET"
# The AppImage runtime needs FUSE by default; extract-and-run works everywhere.
status=0
APPIMAGE_EXTRACT_AND_RUN=1 "$TMP/$ASSET" --backend "$@" || status=$?
exit "$status"
