#!/bin/sh
# 0.6 development bootstrap. Never execute the old backend from a 0.5 archive.
set -eu
if [ ! -t 0 ] && (exec </dev/tty) 2>/dev/null; then
    exec </dev/tty
fi
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$HERE/install-linux.py" ] && [ -f "$HERE/coop_suite.py" ]; then
    exec python3 "$HERE/install-linux.py" "$@"
fi
printf '%s\n' 'A complete CoDCoop 0.6 package is required.' 'Download a published 0.6 prerelease, or run tools/install.sh from its source checkout.' 'The v0.5.4 package cannot install the 0.6 full suite.' >&2
exit 2
