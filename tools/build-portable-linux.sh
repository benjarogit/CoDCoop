#!/bin/sh
# Build Linux GUIs on the pinned Ubuntu 22.04/glibc 2.35 floor, never host Qt.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
mkdir -p run/portable-home run/portable-cache build/portable-provenance
mkdir -p run/portable-builder
if [ ! -x run/portable-builder/appimagetool ]; then
    TOOL=${APPIMAGETOOL_SOURCE:-$(command -v appimagetool || true)}
    if [ -z "$TOOL" ]; then
        echo "Provide the pinned appimagetool via APPIMAGETOOL_SOURCE." >&2
        exit 1
    fi
    cp -L "$TOOL" run/portable-builder/appimagetool
    chmod +x run/portable-builder/appimagetool
fi
printf '%s\n' '95cbe7cce9717fce90c484e34052ee7c7f1d7635b33c12525b4776826a7d29b6  run/portable-builder/appimagetool' | sha256sum -c -
RUNTIME_BYTES=$(run/portable-builder/appimagetool --appimage-offset)
head -c "$RUNTIME_BYTES" run/portable-builder/appimagetool > run/portable-builder/runtime-x86_64
chmod +x run/portable-builder/runtime-x86_64
printf '%s\n' '77f59c85aa4b171adf01d1870d86a53fcdeee7e27b31d119beb420dc4f140b66  run/portable-builder/runtime-x86_64' | sha256sum -c -
IMAGE=${COOP_PORTABLE_IMAGE:-codcoop-portable-linux:ubuntu22.04-locked}
if [ -z "${COOP_PORTABLE_IMAGE:-}" ]; then
    docker build -f tools/portable-linux/Dockerfile -t "$IMAGE" tools
fi
IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
docker image inspect "$IMAGE_ID" > build/portable-provenance/builder-image.json
printf '%s\n' "$IMAGE_ID" > build/portable-provenance/builder-image-id.txt
docker run --rm --user "$(id -u):$(id -g)" \
    -e HOME=/work/run/portable-home -e XDG_CACHE_HOME=/work/run/portable-cache \
    -e QT_QPA_PLATFORM=offscreen -e LANG=C.UTF-8 \
    -e COOP_GUI_PYTHON=/opt/coop-gui/bin/python \
    -e PATH=/work/run/portable-builder:/opt/coop-gui/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    -v "$ROOT:/work:ro" -v "$ROOT/run:/work/run:rw" -v "$ROOT/build:/work/build:rw" \
    "$IMAGE_ID" /bin/sh -ec '
        cp /opt/*dependencies.lock /work/build/portable-provenance/
        /opt/coop-gui/bin/python tools/build-launcher.py
        /bin/sh tools/package-appimage.sh
        /opt/coop-gui/bin/python tools/check-linux-abi.py build/launcher/CoD-Coop-Launcher --output build/portable-provenance/launcher-abi.json
        /opt/coop-gui/bin/python tools/check-linux-abi.py build/CoDCoop-Setup.AppDir --output build/portable-provenance/setup-abi.json
        /opt/coop-gui/bin/python -m unittest discover -s tests -p test_launch_gui.py -q
        /opt/coop-gui/bin/python -m unittest discover -s tests -p test_coop_session.py -q
        /opt/coop-gui/bin/python -m unittest discover -s tests -p test_coop_suite.py -q
        /opt/coop-gui/bin/python -m unittest discover -s tests -p test_frozen_runtime.py -q
    '
