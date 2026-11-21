# YAP and CoD Coop: integration and current evidence

YAP is required for the UO-based profiles. The original `CoDSP.exe` profile
does not load it. SP Improved and United Fronts are PK3 data/script mods;
their presence is not a reason to disable the Co-op engine hooks.

## Pinned upstream build

- Project: [Clippy95/CoDUO-YAP](https://github.com/Clippy95/CoDUO-YAP).
- Release: [r169](https://github.com/Clippy95/CoDUO-YAP/releases/tag/r169).
- Release source tag: `cfb01070cea05ab7055684fa340070731026252b`.
- `CoDUO-YAP.zip`, 3,578,074 bytes, SHA-256
  `cdc9131a189796143ace80f9ecb9f19c347bdb8553558b5fd26e6f7d08bb2ae9`.
- DLL, 1,056,768 bytes, SHA-256
  `9111847c9ed2f1afbdb513d22f2f87f60e23766ba48df60f813d22e1dcaaf431`.
- `EXTRAS_CODUO-YAP.7z`, 2,156 bytes, SHA-256
  `3e1fba1bbb7a71bdc5dd2532b7a366eb961dfe7372bd670ba3fcf241a45a74b2`.

The release archive's DLL displays **r171** in its in-game branding. That is
the upstream artifact's own version string; our artifact identity is its exact
SHA-256, not that string. The release source tag was inspected, but rebuilding
that tag has not established a byte-identical DLL.

The GPL-3.0 license is retained in [third_party/yap/LICENSE](../third_party/yap/LICENSE).
Distribution/source requirements are recorded in
[third_party/yap/NOTICE.md](../third_party/yap/NOTICE.md).

## Initialization contract

1. Co-op remains the game's root `ddraw.dll` proxy.
2. During process attach, before installing its engine hooks, it loads the
   pinned plugin by absolute path as `plugins/yap/DDRAW.dll`.
3. YAP performs its own process-attach initialization and installs its hooks.
4. Co-op verifies the original bytes of its four fixed engine hooks and
   installs them. A missing plugin, failed load or changed hook prologue is
   a visible startup error, not a successful non-Coop launch.
5. YAP stays loaded for the process lifetime. Reloading the Co-op core does
   not unload or reinitialize YAP.

**The uppercase `DDRAW.dll` basename is intentional.** The upstream plugin
compares its own filename case-sensitively to `L"DDRAW.dll"`. With lowercase
`ddraw.dll` or `coduo_yap.dll`, it opens a modal warning about a missing ASI
loader. Keeping the original basename in a separate directory avoids that
warning without pretending to implement Ultimate ASI Loader or modifying the
upstream binary. Co-op verifies that the returned module path is the requested
plugin and not the root proxy.

The system DirectDraw exports still go to the system library. YAP is not the
export-forwarding destination of our proxy. No renderer, input or gameplay
feature is disabled by this integration.

## Support files and configuration

Installing only the DLL is incomplete. Retain the archive's `menuwide/`,
`YAP_raw/` and UO menu support files in their game-relative locations. Install
the extras archive's UO and United Fronts `eWeapons/` definitions too: the
default sprint weapon animation feature otherwise has no definitions.

The executable must be prepared for YAP's LAA requirement by the installer,
with a backup. The runtime test used a **test-copy-only** `dontaskagain.LAA`
marker to suppress the upstream patch prompt; that marker is not evidence
of a correctly prepared production executable.

YAP owns its display/aspect, raw-input and weapon-view animation fixes.
The authoritative host's gameplay settings must match all clients through
the suite profile/preflight mechanism. Actual verification of every such
setting is a separate acceptance gate from loading the plugin.

## Observed runtime checks: 21 November 2026

Platform: Wine 11.22, separate copied installs, Xvfb and Mesa/llvmpipe.
No changes were made to the installed game's files for these tests.

- The upstream DLL initialized from the uppercase plugin path; Co-op's four
  UO hook prologues passed and their trampolines were installed.
- SP Improved loaded `pathfinder`, opened the host UDP socket and installed
  the damage, checkpoint, getent and user-command hooks.
- A second actual game process with SP Improved and YAP joined as slot 1.
  The join completed with 267 configstrings; the host sent 100 snapshots per
  five seconds and received live remote commands.
- The joiner advanced three animation trees at approximately 46 frames/s,
  accumulating 10.1 seconds of animation in a ten-second logging interval.
- The game's own console confirmed `cg_fixedAspectFOV=1`,
  `cg_weaponSprint_mod=1` and `player_sprintSpeedScale=1.6`.
- A game-native screenshot was visually checked: rendered level, weapon,
  HUD and upstream YAP branding were present.

These plugin-isolation tests used the previous core DLL with SHA-256
`efceeff7bd38e88a25ff530859faece9dd950f79055a57370891efed110a1c5b`.
They establish coexistence with the loader and basic replication, **not**
acceptance of the new protocol/core, all missions, all YAP options or Windows.
Repeat through the suite harness after changes to any of these components.

A subsequent protocol-6 development-core run also joined successfully:
the joiner logged `suite: host compatibility verified, requesting player slot`,
then connected as slot 1 with 260 configstrings. The host snapshot clock
advanced from 52,400 to 75,750 ms and the joiner continued receiving snapshots
and advancing five animation trees. The actual loaded temporary core was
SHA-256 `f9e598fb524522cd69006402d5c69acbb536e14b1f4b38ef242b2e95ea13501b`;
the loader used was `dccddc4ea00a03ed2f161a20b23afebfd01e66ad2aaab75a097b4d93801a2280`.
This run explicitly used the isolated-test `CODCOOP_QA=1` identity, so it does
not establish acceptance of a production install receipt. Loaded software
rendering produced variable wall-clock animation advancement under concurrent
tests; no claim of constant real-time animation speed is made for this run.

## Remaining acceptance gates

- New-core two/four-player runs; hot reload and repeated save/load/level changes.
- All YAP gameplay options, local input and animation features on every seat.
- All SP Improved and United Fronts missions and special mechanics.
- Native Windows 10/11 and mixed Windows/Linux runs; Steam with separate accounts.

For headless checks, a custom mode (`r_mode -1`, explicit dimensions and
`r_mode_auto 0`) avoids a mode-table mismatch seen with `r_mode 3` under Xvfb.
Stock hardware-change dialogs are handled on the copied installation before
scoring a run. Neither an unresolved dialog nor a merely loaded map counts as
a passing campaign test.

## Native campaign movie investigation

The shipped CoD 1.5 and UO 1.51 game DLLs implement the GSC `cinematic`
builtin at RVAs `0x35b60` and `0x390a0`. Their level-exit runners format
`cinematic NAME 0 force` and invoke the engine console trap `0x29`, mode
`EXEC_APPEND=2`, at command callsites `0x1e7fc` and `0x20d98`. This is a
local console command, unlike the same runners' broadcast server-command
trap `0x2c`. Consequently, script movies require explicit Coop replication.

The corresponding executable console handlers are CoD `0x407a90` and UO
`0x4084c0`. UO calls `CIN_PlayCinematic` at `0x407b50`, with cdecl arguments
`(filename, x, y, width, height, flags)`; a script movie uses flags 5.
The cinematic path calls the UI VM with command 7 at `0x407f1f`, then
changes `cls_state` to 3 at `0x407ff1`. The global `0x482df44` is `uivm`,
so this is UI menu closure, not evidence of a cgame/server teardown.
Receiving a filename alone does not establish successful post-movie campaign
continuation; actual two-instance evidence remains required.

`src/cinematics.h` observes the first-field syscall pointer of the game VM.
Only an authoritative host enables it, and only the native script command
format triggers a callback. Menu movies and a peer's local console playback
do not pass this origin gate. The helper preserves the previous syscall
chain and forwards every original trap exactly once. Native ASan/UBSan
tests cover command injection rejection, origin filtering, forwarding and
VM replacement; MinGW32 compilation checks its target ABI. These tests do
not substitute for a real two-instance movie and transition run.

The subsequent real two-instance UF/UO-engine probe passed with core SHA-256
`8c5f8ead031644ed4959e0e3193a76769276e72d09e6f2f128dc31b773d34026`.
Both actual joined players entered native `cod_end.roq` playback; the joiner
acknowledged its active native cinematic handle. The movie ended naturally on
both instances after approximately 61 seconds, with their Coop roles and
heartbeats retained. A subsequent explicit host `devmap pathfinder` test drove
normal `M_RELOAD`, local map loading and automatic real-peer reconnection;
the joiner then moved using actual player input, rendered snapshots and
advanced five animation trees at approximately 56 frames/s. Both processes
exited cleanly. This deliberately requested post-movie test map is not a
campaign mission completion or proof of the Berlin-to-UO story route.

Runtime evidence corrected two static assumptions: `cl_movieplaying` remained
zero during actual playback, so the authoritative predicate is `cls_state=3`
plus a nonnegative native cinematic handle. Native movie playback also
invalidated the prior world's animation allocator blocks. Keeping three old
joiner tree indices caused a reproducible post-movie `MT_FreeIndex` crash.
The fix forgets those pointers before native playback, suspends world/snapshot
application and native animation work while retaining the party control link,
then resumes through the host's normal reload. The identical full movie and
reconnection probe passed with this correction.

Evidence: `run/uf-script-qa/{movie-probe,result,provenance}.json` and per-seat
logs/screenshots. The reusable isolated probe is
`python tools/qa_movie_probe.py --source /owned/game-copy --run /separate/qa-run`.
It constructs a QA-only GSC watcher and invokes the real native `cinematic`
builtin after a live join. Earlier failing evidence is preserved under
`run/movie-evidence-first` and `run/movie-evidence-staletree`. Native Windows,
four simultaneous movie viewers, packet-loss movie tests, and the complete
original CoD executable campaign remain separate acceptance items.

Addresses above were verified by disassembling the shipped PE files with
the repository's Capstone tools. REA 6.4.0 rejected the locally installed
Ghidra 12.2 because that provider requires Ghidra 12.1.x; no REA decompilation
result is claimed for this investigation.

Inspected game DLL SHA-256 values: CoD
`27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577`;
UO `9fd3665ba2b67426bfd76df673d7e6575e237224bd5e86c4b979a4287bbeb32e`.
The local executable files inspected have SHA-256 values
`c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`
and `c17e57c060f08ef65d7cddea738cced61ab7ccb6d98df95fe185b1ab8aa7e325`
respectively. Executable-header/LAA variants must still be checked against the
suite's manifest before applying any engine-specific address.

## Host gameplay settings (protocol 7)

The pinned release does not ship a `YAP.ini`. Its native gameplay settings are
engine CVars, which may be changed through local configs or the console.
Coop therefore carries an explicit three-setting host snapshot:
`player_sprintSpeedScale`, `player_sprintmult`, and `bg_allowJumpShot`.
YAP applies sprint scale and jump-shot rules to both native game logic and
client prediction. The accepted snapshot is applied before native attachment,
acknowledged, retried every 250 ms when needed, and updated with a monotonic
sequence number. Old sequences cannot override a newer rule state.

The wire accepts the upstream sprint-scale range `[0, FLT_MAX]`, any finite
native sprint multiplier (upstream declares no range), and a canonical 0/1
jump-shot flag. Unsupported/nonfinite host values cause a visible rejection;
they are never silently clamped differently on a peer. Original local strings
are saved once and restored on leave, failed attachment, or Core shutdown.
Live local overrides are replaced with the accepted host values. FOV, raw
input, bobbing, aspect ratio and crosshair colors remain local. In particular,
YAP's misleadingly named `g_enemyFireDist` only controls enemy-crosshair
coloring in the inspected source; it does not set AI weapon range.

United Fronts' `sp_order`, `sp_forceweapons`, country-specific weapon choices,
`sp_ammo`, faction/nation/year/history settings are read by host GSC. The host
therefore selects campaign order, actual loadouts, ammo and actor composition;
peers receive the resulting authoritative world/player states. The bounded
early UF model catalog handles differing local loadout precache branches.
SP Improved's mission/difficulty branches likewise execute on the host.

The real two-instance Wine probe passed with Core SHA-256
`efbf03ec85b220652f6d6cdbdd257cc3d3f5a95261fe6ad9376705f53f8ca0c3`:
divergent native configs converged before joined play, a live host change was
acknowledged, a local override was corrected, explicit leave restored the
peer's original settings, and rejoin/input/stable snapshots/clean exit passed.
Host FOV 83 and peer FOV 101 stayed distinct throughout. Evidence is preserved
in `run/mainline-credits-qa/proof-host-rules-efbf-PASS`; reproduce with
`python tools/qa_host_rules_probe.py --source /owned/game-copy --run /owned/qa-run --runtime-dir /immutable/runtime`.
Typed sanitizer tests cover finite ranges, stale/wrapped sequences, exact
string restoration, repeated cleanup and oversized saved-setting rejection.
This is a targeted host-rule test, not a campaign completion or native Windows
hardware test.

The same final `efbf03ec…f8ca0c3` Core also passed the real two-instance UF
native-movie gate again on protocol 7: both active playback handles and the
playing ACK, natural completion with party retained, explicit normal host
reload, automatic peer reconnection, 176.1 units of actual remote movement,
stable snapshots, no detected native/script/asset errors, and clean process
exits. Exact evidence and effective QA overlays are retained in
`run/uf-script-qa/history/movie-efbf-pass-1795274971599536253`.

### Native config writes and direct quit

Restoring memory during `Coop_Shutdown` alone did not protect archived local
settings: a real peer starting with `bg_allowJumpShot=0`, playing under host
value 1, then issuing native `quit` persisted 1. A standalone restart without
test config overrides read the leaked value. The failing evidence is retained
in `run/mainline-credits-qa/proof-direct-quit-LEAK-1795276527153333085`.

The fix intercepts the native archive serializer, UO `0x4344e0` (equivalent CoD
function `0x432750`). Disassembly establishes `cdecl(int fileHandle)`, a six-byte
`sub esp,0x404` entry, archive flag at cvar `+0x10`, current string `+4`, optional
latched string `+0x0c`, and list link `+0x24`. UO's automatic config path clears
the dirty archive bit at `0x4322c0` before the common writer at `0x432230` calls
this serializer at `0x432262`. The wrapper temporarily lends the three saved
local strings to this writer and restores the original pointers immediately
afterward. Numeric prediction values, archive flags, FOV and input settings
are never changed. It does not call `Cvar_Set` during serialization, avoiding
archive-dirty/write loops. Persistent bookkeeping also permits pointer recovery
at the next Core entry if native `Com_Error` longjmps out of the writer.
The hook restores only its own jump; a retained later-plugin chain keeps the
disabled forwarding callback mapped until process exit.

Core SHA-256
`7747b1a3864ac9c29bf0d27d1791a54d630fe9cdd1024de840b909d37da82970`
passed the real direct-quit regression: explicit native config write serialized
local 0 while active host prediction remained 1; native quit persisted 0;
standalone relaunch without test config overrides read 0 and retained FOV 101;
actual rejoin, 150.5 units of remote input, stable snapshots and clean exits
passed. The final native quit also persisted 0. Exact evidence, configuration
files, runtime and disassembly are preserved in
`run/mainline-credits-qa/proof-archive-rules-7747-PASS-1795276867629366136`.
Reproduce with `python tools/qa_archive_rules_probe.py --source /owned/game-copy --run /owned/qa-run --runtime-dir /immutable/runtime`.

The final ownership-failure guard additionally leaves visibly if a hot-reloaded
Core cannot protect archive writes because another plugin owns the writer.
Final Core SHA-256
`1a0bc53fb1fb01b09409b654f6bf8e4073d4bb548a43b07db5ac2fbcd17c100d`
passed the complete direct-quit gate again, preserved at
`run/mainline-credits-qa/proof-archive-rules-1a0b-PASS-1795277060720289776`.
The ordinary divergent-config/live-update/local-override/explicit-leave/rejoin
gate also passed on this exact immutable runtime. No native Windows hardware
result is inferred from these Wine runs.
