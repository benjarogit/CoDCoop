# Private dev5 build prerequisites / Voraussetzungen für private dev5-Builds

This is a build recipe for a **future immutable candidate**, not permission to
publish or a claim that current native gameplay is accepted. Preserve the old602
artifacts and never replace their bytes. Build only after the native milestone
and complete source checkpoint are released by the coordinating agent.

## Current boundaries

- Manifest dev5/protocol9 requires compiled mask31. Bit16 is asset bootstrap,
  not individual-kit readiness. The party equipment start is still disabled.
- Signed-party worker sources and full canonical local plan are present. Native
  emission, owner allocation and kit application still require their own proof.
- The generated bilingual Coop UI localization asset is released separately;
  mandatory staging/EN bank/DE selection integration is not yet completed here.
- Old Ubuntu image08bc and embedded Windows Python do **not** contain the new
  cryptography dependencies. Do not reuse those environments unchanged.
- Linux dependencies were installed in an isolated target and imported under
  Ubuntu22.04/Python3.10.12; Ed25519 and cffi passed, both ELF files require at most
  GLIBC2.34. Windows wheels passed an isolated embeddedPython3.12.10 import/sign/
  verify probe under Wine. These are dependency probes, not fresh frozen builds.
- pycparser3.12 requires Python>=3.11. Both source requirement lists now pin the
  tested compatible3.11. The failed3.12 probe is retained under run/crypto50-ubuntu-probe.

## Source graph and frozen worker

Capture one graph **once from the final Git archive**, then use that same file
for both target-OS builds and staging. Do not regenerate it from a half-edited
checkout. Capture covers worker sources, catalog, manifest and build/dependency
recipes. The freezer compiles its graph constant into the executable PYZ. The
sidecar launcher-build.json binds actual executable SHA and captured graph SHA.
Staging compares the explicit expected capture and executes only the registered
local launcher filename with `--internal-command capabilities`. The command
checks actual loaded signing/cffi/parser dependencies and returns fixed worker
capabilities, protocol, feature-validation support and embedded graph SHA.
These fields never grant native equipment readiness.

Old c655/7ab executables actually return2 for that command and remain unchanged.
A fresh frozen positive must be demonstrated after the allowed rebuild. An edited
receipt, graph mismatch, stale executable, unsupported capability or source
mutation fails before payload output. Source hashes are checked again before
publishing the generated directory. This establishes input coherence; byte-for-
byte freezer reproducibility has not yet been demonstrated.

## Future commands (do not run before native/source freeze)

Use new paths for every attempt. Replace SOURCE_COMMIT, VERIFIED_RUNTIME and
CORE_SHA with the exact released immutable inputs; never substitute a normal
rebuild of an already proven DLL. MinGW auto ImageBase can vary by output path.

```bash
set -euo pipefail
ROOT=/mnt/intern-1tb/.cod-work/CoDCoop
TAG=dev5-party-next-20261122-01
SNAP="$ROOT/run/$TAG-source"
OUT="$ROOT/run/$TAG"
SOURCE_COMMIT=REPLACE_WITH_RELEASED_CHECKPOINT
VERIFIED_RUNTIME=/REPLACE/WITH/IMMUTABLE/RUNTIME
CORE_SHA=REPLACE_WITH_EXACT_NATIVE_PROVEN_CORE_SHA256
test ! -e "$SNAP"
test ! -e "$OUT"
mkdir "$SNAP" "$OUT"
git -C "$ROOT" archive "$SOURCE_COMMIT" | tar -x -C "$SNAP"
```

Build the new dependency image from the archived recipe, whose FROM is the pinned
Ubuntu digest. The crypto wheels are hash locked in portable-linux/party-dependencies.lock;
the remaining GUI packages are version locked and pip check verifies closure.
Record the resulting image ID before using it. Old08bc remains untouched.

```bash
docker build -f "$SNAP/tools/portable-linux/Dockerfile" \
  -t "codcoop-portable-linux:$TAG" "$SNAP/tools"
IMAGE_ID=$(docker image inspect "codcoop-portable-linux:$TAG" --format '{{.Id}}')
# Mount SNAP as /work:ro and its new build/run directories separately writable.
# In that container, with /opt/coop-gui/bin/python:
python tools/launcher_provenance.py --output build/launcher-source-graph.json
python tools/build-launcher.py --source-graph build/launcher-source-graph.json \
  --output build/launcher-linux
python tools/check-linux-abi.py build/launcher-linux/CoD-Coop-Launcher \
  --output build/launcher-linux-abi.json
```

For Windows copy the existing embedded Python base into a **new** directory
inside the archived source run folder; do not modify the old base. Install the
four pinned Windows wheels from the reviewed run/crypto50-windows-probe cache
with its hash lock into the copy, then run the same build-launcher command under
a separate initialized Wine prefix (or on Windows), using the same captured
source graph and `--output build/launcher-windows`. Do not mix _internal files.
Capture actual worker seal/prepare/check positives and old protocol/partial-mask
negatives on tiny fixtures, plus capability JSON matching the embedded capture.
Wine is not native Windows10/11 hardware certification.

After both fresh workers and the exact released Core are validated, stage twice:

```bash
python3 "$SNAP/tools/stage_suite.py" \
  --game-source "$ROOT/run/prepared9-uo/host-en" \
  --runtime-source "$VERIFIED_RUNTIME" \
  --source-graph "$SNAP/build/launcher-source-graph.json" \
  --launcher-source "$SNAP/build/launcher-linux/CoD-Coop-Launcher" \
  --yap-archive "$ROOT/run/yap-r169.zip" \
  --yap-extras "$ROOT/run/yap-extras-r169.7z" \
  --base-archive "$ROOT/run/base-ready-v054.zip" \
  --checker-prefix "$ROOT/run/native-setup-prefix" \
  --output "$OUT/suite-linux"
# Repeat with launcher-windows and output suite-windows.
```

Normal downloadable GUI candidates use this slim staging mode. --include-base
is for a separately named owned offline payload; never remove files under an
existing lock to shrink it. Recheck actual Core SHA against CORE_SHA before and
after staging. Source game, saves and user settings are read only.

For AppImage run archived package-appimage.sh inside the new verified Ubuntu
image with COOP_GUI_PYTHON=/opt/coop-gui/bin/python, COOP_SUITE_SOURCE pointing at
the fresh Linux stage, pinned COOP_APPIMAGE_RUNTIME and COOP_APPIMAGE_PROCESSORS=4.
Use unique output `$OUT/Install-CoD-Coop-0.6.0-dev.5-party-next-Linux-x86_64.AppImage`.
Validate real extract/extract-and-run backend, actual xcb GUI startup, all embedded
pins and whole AppDir ELF floor. Preserve the pinned runtime: appimagetool changes
only its16-byte .digest_md5 field; compare normalized runtime code accordingly.

For Windows use archived tools/build-installer.py with the protected game source,
VERIFIED_RUNTIME and a new `$OUT/windows/Install-CoD-Coop-0.6.0-dev.5-party-next.exe`.
Copy the complete Windows stage to `$OUT/windows/suite`. The EXE alone is not a
complete downloadable setup; distribute a new named ZIP containing both if a
single Windows download is needed. Verify embedded resources plus every sidecar
file. No source-only signing helper or Python installation should be required
on the player's computer after a correctly frozen bundle.

## Inputs retained from old602

Exact source archive: run/combined602-source-98de830 (Git98de830;301 tracked source
hashes). Runtime: run/runtime-snapshot-combined602, Core602cb6af…, loader85fc865c…,
Steam e0ccfcdd…, checker0cd064f6…. Workers: run/worker9-api15-proof/linux (c6558d2c…)
and windows (7ab8e72f…). These are historical API15/protocol9 inputs and cannot
be staged as new dev5/API31 packages.

Old generated Linux/Windows stages, AppDir, setup resource input copies, resource
object, Windows sidecar suite and complete per-file manifests remain under their
combined602 names. Full paths, sizes, hashes and original proof JSON references
are recorded by the current read-only inventory in run/build-readiness-dev5.
Pinned archives are ReadyZIP c5f22a30…, YAP ZIP cdc9131a…, extras7z3e1fba1b….
Rebuilding from sources may produce different metadata/toolchain bytes; reusing
the exact archived generated inputs has not been re-packed during this audit.

## Space / Speicherplatz

Measured old slim stages are about1.5GiB Linux/1.4GiB Windows; old AppDir1.7GiB,
AppImage1.27GiB, Windows sidecar1.4GiB, workers153/113MiB, Windows Python base699MiB.
New crypto target adds about18MiB. Plan approximately **20–25 GiB free** for a new
pair of slim candidates, independent worker/build caches, new dependency image,
Windows environment copy and both persistent/temporary AppImage extractions.
An owned --include-base offline pair adds the measured neutral-base bytes again
per copy; it must be estimated separately. The audit found353 GiB free at start.

Dieser Stand beschreibt Voraussetzungen und neue, getrennte Ausgabepfade.
Es wurde kein neues Gesamtpaket gebaut oder veröffentlicht. Alte602-Pakete,
Quellen und Nachweise bleiben unverändert. Native Spielabnahme, echter neuer
Frozen-Positivtest und Lokalisierungsintegration sind eigenständige nächste
Prüfschritte; ein geprüfter Quellgraph ersetzt sie nicht.
