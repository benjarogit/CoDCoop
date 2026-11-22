<div align="center">

# Call of Duty Coop

**The original campaigns. One squad.**

[![Development](https://img.shields.io/badge/0.6.0--dev.6-development-orange)](#development-status)
![Players](https://img.shields.io/badge/players-2%E2%80%934-blue)
![Windows target](https://img.shields.io/badge/target-Windows%2010%20%2F%2011-0078D4)
![Linux](https://img.shields.io/badge/Linux-Wine%20%2F%20Proton-FCC624)
[![License](https://img.shields.io/badge/CoDCoop-MIT-green)](LICENSE)

**English** · [Deutsch](README.de.md)

[Installation](#installation) · [Campaigns](#campaigns) · [Play together](#play-together) · [Development status](#development-status) · [Building and tests](#building-and-tests)

</div>

> **0.6.0-dev.6 is under development.** This branch implements the complete-suite upgrade;
> it is not a verified full-campaign release. The existing [v0.5.4 release](https://github.com/benjarogit/CoDCoop/releases/tag/v0.5.4)
> predates this work and does **not** provide Coop for SP Improved or United Fronts.
> A successful install or short connection test does not certify a campaign.

The current package contract requires Core API mask 63, including native
asset bootstrap and owned English/German Coop banners. This does not enable individual UF kits; their party/native
binding and equipment start remain gated.

## Campaigns

**Recommended main campaign: CoD + UO — Improved Coop.** Start with the first
CoD campaign, keep the SP Improved 1.5 AI/gameplay improvements, watch the original
CoD closing sequence, then continue into UO with the same group. This route uses
the UO engine throughout. The credits→UO bridge has passed a targeted two-client
test; full campaign playthroughs remain part of acceptance.
Classic profiles and United Fronts remain separate choices.


| Variant | What you play | Runtime |
|---|---|---|
| Call of Duty | The original 2003 campaign | CoD 1.5 |
| United Offensive | The original expansion campaign | UO 1.51 + YAP |
| SP Improved 1.5 | CoD/UO missions with the mod's gameplay and quality improvements | UO + YAP |
| United Fronts 1.1 beta | Its original and custom missions, campaign-order settings and special weapons | UO + YAP |

Each variant keeps its own rules and saves. They are **not merged into one mod**.
The complete pinned set is required on every Coop machine; language, resolution
and other personal display settings remain local. German and English gameplay
installations are intended to be compatible. Untranslated custom content keeps
its original language.

In UO-based profiles, the host's sprint and jump-shot settings also govern client
prediction. Your previous local values are restored when you leave. The launcher
shows the verified suite version and the latest local save for each campaign;
joining always follows the host's progress.

**Call of Duty 2 is experimental and outside the current completion target.**
The UO Map Pack is an ordinary multiplayer extra, not a collection of new Coop
campaign missions.

## Play together

The host runs the shared world: AI, objectives, scripts and progress. Up to three
other players join. The implementation includes player bodies and animations,
friendly-fire settings, downed players and reviving, checkpoint recovery,
mission changes and vehicle passengers.

The 0.6 work extends that behavior to the additional variants and their mechanics.
The goal is for every player to participate in objectives. An exclusive scripted
vehicle or cinematic role remains with the host; the others receive appropriate
passenger, gunner or shared-scene behavior. This is a development target until
its mission tests pass.

1. Start **CoDCoop Launcher** and choose a campaign variant.
2. The host selects **Host** and starts a mission. Other players select **Join**.
3. Use the host's IP for LAN/direct-IP play, or the Steam join integration when
   its prerequisites are met.
4. Only the host chooses a new campaign. The group must be ready, the current
   game must be saved at a safe point, then the launchers restart and reconnect.

The host owns the saves. Keep that host's saves to continue a campaign. There is
no automatic host migration. During ordinary play, opening the host's pause menu
does not pause connected teammates; mission start/end screens retain their
required behavior.

<details>
<summary>Connection requirements</summary>

Direct IP uses **UDP 28960** by default. LAN uses the host's local address;
Internet IP play requires forwarding that UDP port to the host.

Steam uses **Spacewar, AppID 480**. Each player needs their own signed-in Steam
account. Under Linux, use the Steam/Proton launch route described in
[the Linux guide](docs/linux.md). A local two-process IP test does not prove
Steam invitation behavior across two computers.

</details>

## Installation

**Requirements:** an existing Call of Duty installation, enough disk space for
UO and the full extra set, 64-bit Windows 10/11 or x86_64 Linux with a working Wine/Proton
runtime. The Linux graphical bundles require glibc 2.35 or newer (Ubuntu 22.04
baseline). Game files are not stored in this source repository.

| Platform | 0.6 installation route |
|---|---|
| Windows | Native setup window; complete pinned local suite payload during development |
| Linux | Graphical AppImage assistant; terminal backend also available |
| Offline | The same pinned payload and required game data, available locally |

The setup checks content and runtime hashes, preserves personal configurations
and saves during repair, and creates an installation receipt. Missing or modified
required files prevent a successful final check. Language changes are explicit;
repair does not silently replace your settings.

**0.6 download links will appear only after an actual prerelease is built and
published.** Do not combine a 0.5.4 installer with arbitrary new DLLs and assume
that the full suite is installed. GitHub is the primary release location; MEGA
mirrors must identify the same version and checksums.

For local development payloads and exact commands see
[development installation](docs/development-0.6.md).

<details>
<summary>Repair, backups and rollback</summary>

Use the setup's check/repair operation for a damaged installation. Replacing a
file with another file of the same size is detected by its hash. Installation
attempts keep a transaction journal and restore changed files on failure.

The Linux backend exposes `--rollback latest` (or a recorded transaction ID).
Keep the generated backups until you have checked the new installation.

</details>

<details>
<summary>Linux startup and display fixes</summary>

Wine must load the mod's `ddraw.dll` using `WINEDLLOVERRIDES="ddraw=n,b"`.
Older OpenGL engines can overflow on modern extension strings. The launcher
sets `__GL_ExtensionStringVersion=15000` and `MESA_EXTENSION_MAX_YEAR=2003`.
See [Linux / Proton details](docs/linux.md).

</details>

## Development status

The release gate is **complete tested campaigns**, not merely successful map
loads. Native Windows 10/11 tests, Steam with separate accounts, all campaign
playthroughs and the extra mechanics must be recorded before a stable release.

- [Implementation and test handoff](docs/HANDOFF-0.6.md)
- [Campaign inventory and compatibility](docs/campaign-compatibility.md)
- [YAP compatibility and pinned source](docs/yap-compatibility.md)
- [English / German changelog](CHANGELOG.md)

Tests deliberately distinguish connection/mechanics smoke tests from actual
mission completion. They use isolated game copies and do not modify your live
installation. Missing tests remain open; no platform or campaign is certified
by inference from Wine or a screenshot.

## Building and tests

On Linux install the 32-bit MinGW-w64 toolchain, then run:

```sh
./build.sh
python3 -m unittest discover -s tests -v
g++ -std=c++17 tests/test_suite_protocol.cpp -o build/test_suite_protocol
./build/test_suite_protocol
```

The Python tooling requires Python 3.10 or later. Graphical development tools
use PySide6. See [development commands](docs/development-0.6.md) for native
checker tests, isolated Wine tests, payload building and AppImage packaging.

<details>
<summary>Architecture and research tools</summary>

The host runs the game's own single-player server. The loader bridges its
loopback networking to remote clients and supplies state normally shared in
process memory. The core can be reloaded during development; incompatible code
or content requires matching participants.

[Ghidra and REA](https://github.com/morluto/rea) help investigate specific engine
functions and failures. [Co-op Anything](https://github.com/cranebeaker/coop-anything)
provides testing and reverse-engineering methods. Using these tools does not
itself prove compatibility: behavior must be tested in real game clients.

Original technical notes: [architecture](notes/ARQUITECTURA.md).

</details>

## Credits and licenses

Maintained fork of [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop).
CoDCoop source: [MIT](LICENSE). YAP is a separate
[GPL-3.0 component](third_party/yap/LICENSE); retain its source/version information
and license when packaging. Credits for SP Improved, United Fronts and their
included community content remain with their authors. Call of Duty belongs to
Activision; Steam components belong to Valve.
