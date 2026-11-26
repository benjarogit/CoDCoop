#!/bin/sh
# Reproducible Linux GUI bundle: Python runtime + PySide6 + shared installer.
# Run from a Linux x86_64 builder with Python3, uv and appimagetool installed.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
# Build against Ubuntu 22.04 (GLIBC 2.35) or an older compatible floor.
# A newer host's libc requirements cannot be made portable by AppImage.
if ! getconf GNU_LIBC_VERSION | awk 'BEGIN{ok=0} $1=="glibc" && NF==2 {split($2,v,"."); ok=(v[1]<2 || (v[1]==2 && v[2]<=35))} END{exit !ok}'; then
    echo "Use the portable Ubuntu 22.04 builder; builder must provide GLIBC 2.35 or older." >&2
    exit 1
fi
PYTHON=${COOP_GUI_PYTHON:-}
if [ -z "$PYTHON" ]; then
    VENV=build/appimage-venv
    if [ ! -x "$VENV/bin/python" ]; then
        uv venv --system-site-packages --python /usr/bin/python3 "$VENV"
    fi
    uv pip install --python "$VENV/bin/python" 'pyinstaller==6.22.3' 'pyinstaller-hooks-contrib==2026.10' 'altgraph==0.17.5'
    PYTHON="$VENV/bin/python"
fi
# The isolated builder provides these pinned distributions; do not upgrade them.
"$PYTHON" -c 'import importlib.metadata as m; assert m.version("PySide6")=="6.12.0"; assert m.version("PyInstaller")=="6.22.3"; assert m.version("pyinstaller-hooks-contrib")=="2026.10"; assert m.version("altgraph")=="0.17.5"'
"$PYTHON" -m PyInstaller --noconfirm --clean --onedir --name CoDCoop-Setup \
    --distpath build/appimage-dist --workpath build/appimage-work --specpath build \
    --hidden-import coop_localization --hidden-import build_coop_localization --hidden-import frozen_runtime --hidden-import runtime_protocol --hidden-import configparser --hidden-import zipfile --hidden-import urllib.request \
    --hidden-import ssl --hidden-import hashlib --hidden-import shlex --hidden-import subprocess \
    --hidden-import tempfile --hidden-import json --hidden-import shutil --hidden-import struct \
    --add-data "$ROOT/tools/install-linux.py:." --add-data "$ROOT/tools/coop_suite.py:." \
    --add-data "$ROOT/tools/extract_installer.py:." "$ROOT/tools/install-gui.py"
APPDIR=build/CoDCoop-Setup.AppDir
# This is a generated build tree; do not retain removed dependencies between builds.
rm -rf -- "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a build/appimage-dist/CoDCoop-Setup "$APPDIR/usr/bin/"
cat > "$APPDIR/AppRun" <<'APP'
#!/bin/sh
exec "${APPDIR:-$(dirname -- "$0")}/usr/bin/CoDCoop-Setup/CoDCoop-Setup" "$@"
APP
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/codcoop-setup.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=CoDCoop Setup
Name[de]=CoDCoop Installation
Exec=CoDCoop-Setup
Icon=codcoop-setup
Categories=Game;
Terminal=false
DESKTOP
cat > "$APPDIR/codcoop-setup.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect x="4" y="4" width="120" height="120" rx="22" fill="#263b31"/><path d="M32 44h64v46H32z" fill="none" stroke="#fff" stroke-width="7"/><path d="M64 22v44m-15-15 15 15 15-15" fill="none" stroke="#e8bd57" stroke-width="7"/></svg>
SVG
# Match license and distro notices to the actual interpreter and collected ELF
# dependencies, including setup-specific Qt plugins. No host-specific paths.
"$PYTHON" - "$ROOT" <<'PYNOTICE'
import importlib.util
from pathlib import Path
import sys
import shutil
root=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('launcher_builder',root/'tools/build-launcher.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
bundle=root/'build/CoDCoop-Setup.AppDir/usr/bin/CoDCoop-Setup'
module.collect_notices(root,bundle,root/'build/appimage-work/CoDCoop-Setup/Analysis-00.toc')
(bundle/'licenses/CoDCoop-MIT.txt').write_bytes((root/'LICENSE').read_bytes())
shutil.copytree(root/'third_party/appimage',bundle/'licenses/appimage-runtime',dirs_exist_ok=True)
PYNOTICE
# Optional self-contained installer payload. Missing original base packages are
# retained as installer requirements; this never seals an incomplete game.
if [ -n "${COOP_SUITE_SOURCE:-}" ]; then
    set --
    if [ "${COOP_APPIMAGE_LINK_SUITE:-0}" = 1 ]; then set -- --hardlink; fi
    "$PYTHON" tools/package_appimage_suite.py "$@" --source "$COOP_SUITE_SOURCE" \
        --destination "$APPDIR/usr/bin/CoDCoop-Setup/suite" \
        --report "$APPDIR/bundled-suite.json"
fi
APPIMAGE_RUNTIME=${COOP_APPIMAGE_RUNTIME:-$ROOT/run/portable-builder/runtime-x86_64}
printf '%s  %s\n' '77f59c85aa4b171adf01d1870d86a53fcdeee7e27b31d119beb420dc4f140b66' "$APPIMAGE_RUNTIME" | sha256sum -c -
APPIMAGE_OUTPUT=${COOP_APPIMAGE_OUTPUT:-build/Install-CoD-Coop-Linux-x86_64.AppImage}
if [ -e "$APPIMAGE_OUTPUT" ]; then
    echo "Output already exists; choose a fresh COOP_APPIMAGE_OUTPUT or archive it first." >&2
    exit 1
fi
APPIMAGE_PROCESSORS=${COOP_APPIMAGE_PROCESSORS:-4}
case "$APPIMAGE_PROCESSORS" in ''|*[!0-9]*) echo "Invalid COOP_APPIMAGE_PROCESSORS" >&2; exit 1;; esac
if [ "$APPIMAGE_PROCESSORS" -lt 1 ] || [ "$APPIMAGE_PROCESSORS" -gt 64 ]; then
    echo "COOP_APPIMAGE_PROCESSORS must be between 1 and 64." >&2; exit 1
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 appimagetool --runtime-file "$APPIMAGE_RUNTIME" \
    --mksquashfs-opt=-processors --mksquashfs-opt="$APPIMAGE_PROCESSORS" "$APPDIR" "$APPIMAGE_OUTPUT"
sha256sum "$APPIMAGE_OUTPUT"
