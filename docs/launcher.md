# Native campaign launcher

The launcher selects one of the four registered variants, validates the
complete installation and starts the local session supervisor. It remains open
while the game runs so the squad can follow a campaign change across process
restarts.

English is the initial interface language. German is available from the
language selector. The normal entry starts with **CoD + UO — Improved Coop**.
It uses SP Improved 1.5 on the UO engine and runs the CoD 1 campaign, its
original credits, and United Offensive. After the UO credits the host's
supervisor starts the United Fronts transition. The launchers verify the
party, save the current campaign and reconnect after the restart. The host
can use **Continue to United Fronts** to retry the transition.

## Controls

- Choose the complete game installation. **Advanced launch options** shows
  the campaign selector for individual profiles and their existing saves.
- Host a game, or join using the host's IP endpoint or Steam ID.
- The host selects Recruit, Regular, Hardened or Veteran for a new campaign
  (Regular is the default). Joiners follow the host; existing saves retain
  their own difficulty.
- Use **Check installation** to identify missing or changed content before
  starting. A failed check never launches the game.
- While hosting, select a different variant and use **Switch campaign**.
  Selecting alone does nothing. Confirming asks the supervisor to prepare the
  group change; the engine controls safe-point saving and peer readiness.
- The switch confirmation includes the selected target mission and difficulty;
  the advanced starting-mission field can be left blank for the campaign's
  beginning when switching.
- Joiners cannot select a different campaign for the group.
- Use **Cancel switch** or **Retry** when a pending change cannot complete.
- **Leave session** sends a cooperative stop request to the supervisor, which
  shuts down only the game process it owns.

The advanced controls expose an optional starting mission and the local
Wine/Proton runner. They are passed as process arguments without a shell. The
supervisor resolves registered game executables and validates the mission and
host arguments; a peer never supplies an executable path.

## Source and bundled operation

From source, install the pinned dependencies in
[tools/requirements-launcher.txt](../tools/requirements-launcher.txt), then run:

```sh
python tools/launch-gui.py --game "/path/to/Call of Duty" --variant sp_improved
```

On Windows, build the self-contained native directory with the pinned native
Python environment:

```sh
python tools/launcher_provenance.py --output build/launcher-source-graph.json
python tools/build-launcher.py --source-graph build/launcher-source-graph.json
```

For distributable Linux binaries, use the isolated Ubuntu 22.04 builder:

```sh
APPIMAGETOOL_SOURCE=/path/to/pinned/appimagetool tools/build-portable-linux.sh
```

The base image is pinned by repository digest; apt package versions and all
Python wheel versions are locked in `tools/portable-linux/apt-packages.lock`
and `tools/requirements-launcher-linux.lock`. The script uses project-local
`run/` and `build/` mounts and records the actual builder image and dependency
versions in `build/portable-provenance/`. It does not install packages on the
host. Its appimagetool and embedded runtime SHA-256 values are checked before
packaging; the runtime is supplied explicitly, with no implicit latest-runtime
download. An already prepared
builder can be selected by immutable image ID using `COOP_PORTABLE_IMAGE`.

The distributed Linux GUIs require x86-64 and glibc 2.35 or newer (Ubuntu
22.04 is the tested baseline). The ABI gate checks every bundled ELF; building
against newer host Python/Qt libraries is unsuitable for a portable release.

The default output is `build/launcher/CoD-Coop-Launcher/` (with an `.exe`
entrypoint on Windows). Package the complete directory, including its runtime
dependencies; the executable alone is not sufficient. The source checkout and
a system Python installation are not needed by the resulting bundle.

The distribution step installs that directory into `coop/launcher/` and passes
`--game` and optional `--variant` from the generated shortcuts. The Linux
installer's AppImage is a separate application from the installed campaign
launcher.

Frozen bundles re-enter the same executable for validation and session workers
using an internal command allowlist. On Windows, those workers attach Python's
standard streams to the pipes supplied by the GUI. This preserves both status
messages and the supervisor's stop/retry/cancel interface without opening a
console window.

External game processes receive their own library search environment. A frozen
worker restores the original user library path and removes only its bundled
Qt/QML/PATH entries and private PyInstaller process state. Wine prefixes and
Proton options remain unchanged. Windows workers temporarily restore normal
DLL search while spawning the game, then restore their own runtime directory,
including on failed launches. A restoration failure cannot leave an unowned
new game process behind.

## Verification boundaries

Source GUI smoke checks were rendered in English and German with PySide6
6.12.0. Focused tests cover refusal to launch an invalid installation, missing
join addresses, host confirmation, denial of joiner-initiated group changes
and bundled worker command construction. A self-contained Linux bundle was
built and its actual validation worker returned the expected failure for a
missing installation.

A Windows x86-64 bundle was also built under Wine using the official embedded
CPython 3.12.10 distribution and pinned Windows wheels. Its actual executable
rendered the GUI and its bundled installation-check worker returned the same
expected missing-installation error. The nine focused GUI tests also passed
under the Windows Python/Qt runtime in Wine. This verifies the packaged worker
pipe dispatch in that environment, not native Windows hardware behavior.

The final Windows frozen session worker also spawned an owned native Win32
probe under Wine after validating its deliberately minimal test receipt. The
child observed normal empty DLL-directory state, no private bundled PATH/Qt
plugin entries, and the preserved test environment marker. Six additional
isolation tests passed in both the Linux and Windows Python environments. This
is evidence for the frozen process boundary, not a real Windows campaign run.

These checks do not establish full-game campaign acceptance. Native Windows
10/11 operation and real cross-platform sessions remain independent release
gates even when a Windows executable is successfully built or exercised under
Wine.

The final portable Linux launcher was executed offscreen inside Ubuntu 22.04,
including its actual frozen validation worker. All 189 bundled ELFs required
at most glibc 2.35. Nine GUI tests and ten session tests passed using that
builder's Python 3.10.12/PySide6 6.12.0 environment. This verifies the Linux
GUI/runtime baseline, not Wine/Proton gameplay on every distribution.

Each final directory bundle includes `licenses/`, complete Qt LGPL/GPL and
CPython texts, PyInstaller's bootloader exception, notices supplied by its
installed Python distributions, and `runtime-notices.json` with actual Python,
Qt and package versions. Native Linux builds additionally collect package
metadata and available license directories for the shared libraries/plugins
actually selected by PyInstaller. Build work directories are separated by
platform so a Wine build cannot replace the Linux dependency inventory.
The retained upstream notices and source/replacement information are in
[third_party/gui](../third_party/gui/README.md). The notice collector has been
exercised with both the native Linux Python and Windows CPython under Wine;
this does not imply native Windows acceptance.
