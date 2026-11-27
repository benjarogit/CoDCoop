# Changelog · Änderungsprotokoll

[English](#061--english) · [Deutsch](#061--deutsch)

## 0.6.3

- **EN:** Players can join the in-game lobby before the host starts or loads a
  mission. The Co-op menu shows who is waiting, and the regular mission join
  takes over when the world is ready. The lobby is based on
  [TheTiranix's upstream change](https://github.com/TheTiranix/CoDCoop/commit/185533d).
- **DE:** Mitspieler können der Lobby beitreten, bevor der Host eine Mission
  startet oder lädt. Das Coop-Menü zeigt, wer wartet. Sobald die Mission bereit
  ist, übernimmt der normale Beitritt. Grundlage ist
  [die Upstream-Änderung von TheTiranix](https://github.com/TheTiranix/CoDCoop/commit/185533d).

- **EN:** The game and launcher distinguish the LAN address from the public
  internet IPv4 address. Request the public address on demand. The launcher
  copies either address with the port and explains UDP forwarding for internet play.
- **EN:** A Steam invitation received before Steam is ready waits for initialization.
  The game also reads the Steam launch request when opened from an invitation.
  The status and log show whether the pending request starts or expires.
- **EN:** The main menu shows join progress and reports whether Steam or UDP
  timed out before the host handshake. Steam callbacks also work with an
  already initialized Steam client interface.
- **EN:** The launcher defaults to **CoD + UO — Improved Coop**. Individual
  campaign profiles remain available in the advanced options. After the United
  Offensive credits, the launchers save and take the group into United Fronts.
  **Continue to United Fronts** retries the change.
- **EN:** The Linux wrapper preserves the campaign and join arguments when
  starting Proton. The game logs Steam Overlay readiness and activation.
  Steam join information is retried if Steam rejects the update. The game also
  logs changes in Steam relay availability.
- **EN:** In a match, **P** opens the console when the key is free.
  The [connection guide](docs/connect.md) covers LAN, internet, Steam and VPN.
- **DE:** Spiel und Launcher kennzeichnen Heimnetz-Adresse und öffentliche IPv4
  getrennt. Die öffentliche Adresse wird auf Klick ermittelt. Der Launcher
  kopiert beide Adressen samt Port und erklärt die UDP-Weiterleitung.
- **DE:** Eine Steam-Einladung, die vor der Steam-Initialisierung eintrifft,
  bleibt kurz vorgemerkt. Beim Start über eine Einladung liest das Spiel auch
  die Steam-Startanfrage. Der Status und das Log zeigen, ob der Beitritt
  startet oder die Wartezeit abläuft.
- **DE:** Das Hauptmenü zeigt den Verbindungsfortschritt und meldet, ob der
  Beitritt über Steam oder UDP vor der Antwort des Hosts abgelaufen ist.
  Die Steam-Ereignisse werden auch bei bereits initialisierter API verarbeitet.
- **DE:** Der Launcher startet vorausgewählt mit **CoD + UO — Verbesserter
  Coop**. Einzelne Kampagnen bleiben unter den erweiterten Optionen erreichbar.
  Nach dem United-Offensive-Abspann speichern die Launcher und nehmen die Gruppe
  mit nach United Fronts. **Weiter zu United Fronts** wiederholt den Wechsel.
- **DE:** Das Linux-Startskript übergibt Kampagne und Beitrittsadresse an Proton.
  Das Spiel protokolliert, wann das Steam-Overlay bereit ist und geöffnet wird.
  Lehnt Steam die Beitrittsdaten ab, veröffentlicht das Spiel sie erneut.
  Änderungen an der Steam-Relay-Verfügbarkeit erscheinen im Log.
- **DE:** Im Spiel öffnet **P** die Konsole, wenn die Taste frei ist.
  Die [Verbindungsanleitung](docs/connect.de.md) erklärt Heimnetz, Internet,
  Steam und VPN.

## 0.6.2 · Hotfix

- **EN:** Direct AnkerGames, Steam and game-executable starts prepare a missing
  or mismatched campaign profile when hosting or joining. Wine and Proton must
  load the bundled `ddraw.dll`. The in-game Join button asks for the host
  address when the field is empty.
- **EN:** Setup shows the active download, transferred size, percentage and
  verification phase. Windows adds a **CoDCoop** shortcut in the game folder.
  Linux can open the launcher when setup finishes.
- **DE:** Beim direkten Start über AnkerGames, Steam oder die Spiel-EXE bereitet
  die Mod ein fehlendes oder unpassendes Kampagnenprofil beim Hosten oder
  Beitreten vor. Wine und Proton müssen die mitgelieferte `ddraw.dll` laden.
  Der Beitrittsknopf fragt nach der Host-Adresse, wenn das Feld leer ist.
- **DE:** Das Setup zeigt den laufenden Download, die übertragene Datenmenge,
  den Prozentwert und die Prüfung an. Windows legt **CoDCoop** im Spielordner
  an. Unter Linux lässt sich der Launcher nach der Installation direkt öffnen.

## 0.6.1 — English

**Released 2026-11-26. Steam join fix. Steam with two real accounts and a
human full-campaign playthrough remain documented as not covered.**

- Fix Steam joins (ported from upstream `1cfb017`, adapted to this tree).
  `SteamNetworkingIdentity` is packed in the Steamworks SDK, so the sender
  identity inside `SteamNetworkingMessage_t` is at offset 12 on 32-bit builds,
  not 16. Reading it at 16 gave every sender the bogus SteamID `0x01100001`, so
  the host answered no Steam session and a friend joining from the Steam friend
  list never connected. The host now accepts the session; the joiner spawns,
  moves and shuts down cleanly.
- Log the Steam networking state and relay/identity details, so a failed join
  can be diagnosed from `codcoop.log`.
- Add `tools/fakesteam.cpp`, a stand-in `steam_api.dll` for two-user tests on
  one PC, and extend `tools/qa_coop.py` with `--steam-api` / `--steam-host-id`:
  every player copy gets the stand-in API, its own SteamID and joins with
  `+coopjoin steam:<host id>` instead of an IP address.
- Verified: two-player CoD 1 `training` smoke over the Steam transport on
  Linux/Wine — host accepted the session, joiner moved 238.7 units, clean
  shutdown (`run/qa-steam-fake1`, `transport=steam-fake`). This exercises the
  SDK ABI and the mod's Steam path with a stand-in DLL, not two real Steam
  accounts; that remains untested and is not claimed.

## 0.6.1 — Deutsch

**Veröffentlicht am 26.11.2026. Steam-Beitritt repariert. Steam mit zwei echten
Konten und ein menschlicher Komplett-Durchlauf bleiben als nicht abgedeckt
dokumentiert.**

- Steam-Beitritte reparieren (aus Upstream `1cfb017` übernommen und an diesen
  Stand angepasst). `SteamNetworkingIdentity` ist im Steamworks-SDK gepackt,
  deshalb steht die Absender-Identität in `SteamNetworkingMessage_t` auf
  32-Bit-Builds bei Offset 12, nicht 16. Bei Offset 16 bekam jeder Absender die
  falsche SteamID `0x01100001`; der Host antwortete keiner Steam-Sitzung und ein
  Beitritt aus der Steam-Freundesliste kam nie zustande. Der Host nimmt die
  Sitzung jetzt an; der Beitretende spawnt, bewegt sich und beendet sauber.
- Steam-Netzwerkzustand und Relay-/Identitätsdetails werden protokolliert, damit
  ein fehlgeschlagener Beitritt aus `codcoop.log` diagnostizierbar ist.
- `tools/fakesteam.cpp` ergänzt: eine `steam_api.dll` als Ersatz für Zwei-Spieler-
  Tests auf einem PC. `tools/qa_coop.py` erhält `--steam-api` / `--steam-host-id`:
  jede Spielerkopie bekommt die Ersatz-API, eine eigene SteamID und tritt mit
  `+coopjoin steam:<Host-ID>` statt einer IP-Adresse bei.
- Geprüft: Zwei-Spieler-Smoke auf CoD 1 `training` über den Steam-Transport unter
  Linux/Wine — Host nahm die Sitzung an, der Beitretende bewegte sich 238,7
  Einheiten, beide beendeten sauber (`run/qa-steam-fake1`,
  `transport=steam-fake`). Das prüft die SDK-ABI und den Steam-Pfad des Mods mit
  einer Ersatz-DLL, nicht zwei echte Steam-Konten; das bleibt ungeprüft und wird
  nicht behauptet.

## 0.6.0 — English

**Released 2026-11-26. Coverage is recorded per chapter; a human full-campaign
playthrough and Steam with two separate accounts are documented as not covered.**

- Verify the Windows package on real Windows 11 (QEMU/KVM, UEFI + TPM 2.0), not
  only under Wine. A fresh base game without any suite installs with
  `Install-CoD-Coop.exe --yes` (exit 0), `coop\suite-check.exe` confirms every
  required suite file by SHA256 after the QA runs, and the installed 0.6.0 suite
  passes the native smoke on `training`: **four players** on CoD 1 (172.3 /
  229.9 / 110.1 units of joiner movement through native input), two players on
  UO (200.0), SP Improved (154.4) and United Fronts (173.2), each with a real
  connect, advancing remote command clocks, rejected packets from unallocated
  endpoints and clean shutdowns. The VM has no GPU, so
  the smoke runs on Mesa's `llvmpipe` WGL driver (copied into the per-player QA
  copies only); the installed acceptance folder stays byte-identical to the
  suite. Two findings from that work are worth keeping: Mesa's d3d12 WGL path
  initialises GL but crashes inside `libgallium_wgl.dll` while the map loads its
  surfaces, and a game folder without the shipped `miles/` directory loses every
  Miles 3D provider, which makes the single-player sound init fatal. Details,
  commands and the rejected driver paths are in
  [`run/qa-win-native1/NOTES.md`](run/qa-win-native1/NOTES.md).

- Foy, Noville, Brecourt and Bastogne1 pass four-player Co-op on the production
  path: native tree adoption, own trees and host player-body trees on the heap
  (no script-pool exhaustion), checkpoint reload for every joiner, and the
  upstream fixes for smoother joiner animations, the host's weapon in vehicles,
  revive protection and teammates leaving vehicles next to the host. Keep-alive
  now runs in the packet pump, so a long native load no longer drops a joiner's
  slot after 8 s.
- Record campaign coverage chapter by chapter instead of claiming a playthrough.
  A human full playthrough is explicitly **not** a release gate: it can only be
  produced by playing the game correctly for hours, so it is documented as not
  covered while the per-chapter samples remain the coverage claim.
  Both bastogne1 failures that preceded the pass are retained as evidence: the
  rejoin renderer catches up at 2 fps and the restored pose can face an
  obstacle, so the fixture now waits for restored-world snapshots and probes the
  four walk directions while keeping the strict per-direction movement oracle.
  bizerte is the first named content limitation: the level loads no allied
  player model, so Coop bodies cannot be built there and the desert sample moves
  to afrika2, which passes four-player Coop with 25 adoptions per joiner and
  210.0/182.9/172.8 reload movement. Afrika2 also exposed two real defects that
  are now fixed: the host body lookup now covers the 3rd Infantry and 29th
  Division model families, and the authored AI weapon pass yields every eight
  actors so four native clients on one machine no longer trip the engine's
  script watchdog and lose the remaining actors' weapons.
- Afrika2 and Dawnville extend the four-player samples: 25 and 12 native-tree
  adoptions per joiner, 19 host bodies each, genuine owner movement and a
  native checkpoint reload with every joiner re-joined. Dawnville opens inside a
  live firefight: an idle host died before the peers finished loading, and the
  paused death screen blocked the joins. The sampler now pins only the host
  with the mod's own `coopgod` command and records that as a QA liveness input,
  never as a damage or death claim. A host death while peers are still loading
  still leaves the listen server paused; that product case is documented as
  open in the handoff.
- Pavlov adds the Russian winter sample and exposes a stock United Fronts
  defect: `Axis_Swap` leaves a hole in its per-year weapon tables
  (`ger_heer`/1942 sets no `sniper[1]`, a map spawner sets `sniper[2]`), and the
  unguarded `precacheItem` loop aborted the script thread, so the remaining
  precache and the map's weapon assignment never ran. The overlay now guards
  each of the six loops with `isdefined`; pavlov then passes four-player Coop
  with 10 adoptions per joiner and 211.3/199.8/174.7 initial, 56.5/48.5/60.0
  post-reload movement. Its two remaining console lines are named content
  warnings (missing `xmodel/head_blane`, shipped as `Blane1`, and
  `xmodel/gear_german_headwrap` from United Fronts' winter German table) and are
  allowlisted by exact text, recorded in the proof; every other `ERROR:` line
  and every script runtime error stays fatal.
- Arnhem adds the British sample and needed a product fix: its BSP names one
  static prop `Xmodel/chair_office_d` (capital X, the only such reference in the
  whole United Fronts package), the renderer cache reports that spelling, and
  the resource bootstrap rejected the map so the host never exported. The
  bootstrap now canonicalizes only the `xmodel/` prefix to the spelling the pak
  member and the peers use, and the map passes four-player Coop with 24
  adoptions per joiner, the mission's own British bodies and
  159.4/175.0/148.9 initial, 178.6/149.6/206.6 post-reload movement. One stock
  content warning stays: arnhem and wolfheze place
  `xmodel/ammo_panzerfaust_box0`, which retail never shipped, so the decorative
  crate is skipped and the line is a named per-map exception.
- Pegasusnight adds the second British sample and exposes a host-only scripted
  state: the glider crash calls `level.player freezeControls(true)` and
  `shellshock("groggy", 20)` on the host body, and the fade-in re-gives the
  loadout captured before the QA kit. The fixture detects that native swap,
  re-commits the same plan once with an `identity|world|epoch` receipt, and
  repeats only the host `+attack` burst in a bounded 40 s window because the
  host stayed at `pm_flags=0x03000002` until about 108 s while the peers were
  already free. The map passes four-player Coop with 63.1/117.4/64.9 initial
  and 66.6/116.4/109.4 post-reload movement, clips 30/5/20/8→25/4/15/7, both
  visible-selection phases and all four owners. The four-owner ammo gate is
  unchanged and still fails a host that never consumes; the map script stays
  unmodified and the QA kit stays the fixed American catalog.
- The plain CoD1, UO and SP Improved variant smokes pass four clients on
  `training` with the current runtime (`run/qa-cod1-smoke1`,
  `run/qa-uo-smoke3`, `run/qa-sp-improved-smoke1`): real connection, advancing
  user-command clocks, distinct owner-input movement
  (179.0/192.6/151.2, 195.7/165.9/180.1 and 192.9/173.8/187.5 units) and clean
  shutdown. A first UO attempt on `sicily1` connected all four clients but
  measured the mission's
  scripted boat ride (123.2 units on every remote), because
  `docks_boat_arrival()` links the player and the squad to the same boat; that
  opening is an on-rails exception like carride and tankdrivecountry
  (`run/qa-uo-smoke2`). Testing `foy` exposed two cosmetic stock precache
  lines in the untouched UO scripts:
  `maps/foy.gsc` asks for `xmodel/c_us_helmet_moody_winter` although the tested
  packages ship `c_us_helmet_moody` and `c_us_bod_moody_winter`, and
  `maps/foy_dummies.gsc` asks for `xmodel/weapon_garand` although they ship
  `xmodel/weapon_M1Garand`. Neither asset is invented; the two exact lines are a
  named per-map content rule (`run/qa-uo-smoke1`), and the map's full
  four-player connection and movement gate passed before the generic smoke
  rejected the console lines.
- A host can no longer lose the session while friends are still loading. If the
  host takes a lethal hit while a peer is inside the resource bootstrap and no
  remote is active, the hit is measured with the coop's own inflated-health
  technique and clamped to 1 health instead of opening the single-player death
  screen, which pauses the listen server and leaves the joining peers without a
  gamestate (`run/qa-dawnville-m14-sample1`). The window is native state, not a
  timer: a fresh (120 s) bootstrap peer; a reserved seat does not count, so a
  solo host with saved seats stays killable. With an active remote the normal
  downed/revive rules apply again. `run/qa-join-guard4` fires
  `coopkill 0 100000` into that window: the host stays at 1 health, all three
  peers join, move and shut down cleanly; `tests/test_join_guard.cpp` covers the
  decision table.
- Level triggers now only fire for the host: a teammate standing in a scripted
  danger zone no longer drops that zone's response (the bastogne1 mortars) on
  the host, and advance triggers no longer complete without the host. A peer
  that joins mid-mission appears at the host spot instead of the map start, and
  everyone gets 3 s without damage while the level's opening shots settle. The
  joiner's frozen local game no longer runs its free-CPU `vmMain` 10/11 frames,
  and its entity states are restored before that local map closes.
  `run/qa-c1da93f-smoke2` passes a four-player CoD1 smoke with both trigger
  hooks installed, all three local-state restores and 164.0/179.3/215.7 units
  of movement; the UO and SP Improved variants pass on the same build
  (`run/qa-c1da93f-uo1` 189.9/193.4/168.8, `run/qa-c1da93f-sp1`
  159.8/175.7/185.2); `tests/test_trigger_filter.cpp`,
  `tests/test_join_placement.cpp` and `tests/test_frozen_vm.cpp` cover the
  decisions.
- Fix atomic lobby-file exchange when a Windows/Wine reader temporarily blocks
  replacement; keep bounded retries, prior-file preservation and link rejection.
  Fresh frozen Linux and Windows/Wine workers pass signed party transactions,
  including four-party restart/ownership checks. Native game kit binding remains open.
- Record clean UF Foy/Noville startup failures at the native 255-model limit.
  First-use registration remains experimental; selected-host-only startup is
  diagnostic evidence, not support for four individual kits.

- Source `0.6.0` requires compiled Core feature mask 63, including native
  asset bootstrap and localized Coop banners. Reject historical API15/API31 DLLs before new staging; individual
  UF kit application remains gated pending native owner/plan binding.
- Transfer and verify the native model/weapon resource contract before loading
  a joiner's target world. Detach stale native client model mappings before
  publishing the Host's IDs; retain native allocation ownership.
- Preserve the saved prone direction and terrain pitches after reconnect.
  Strict mixed-role four-player checkpoint tests pass in CoD1 and UO+YAP,
  followed by normal teammate revival and four clean game exits.

- Require a complete, pinned set: CoD, UO, SP Improved, United Fronts and YAP.
- Make the recommended CoD→UO mainline use SP Improved's AI/gameplay improvements
  throughout. Preserve the original CoD ending and credits before continuing into
  UO with the same party; start the next mission when the party is ready.
- Add shared variant manifests, local installation receipts and gameplay fingerprints.
- Negotiate engine, protocol, campaign and content before assigning a player slot.
- Separate same-IP joiners with distinct qports; the original SP transport wrote zero.
- Add bounded control-packet writing and complete animation-fragment assembly.
- Load the pinned YAP plugin alongside Coop on UO-based variants; preserve its
  original `DDRAW.dll` basename in a separate plugin directory.
- Build reviewed mod-specific menu and gameplay overlays from the owner's files.
  Preserve each mod's mission selection; adapt United Fronts player mechanics and
  selected original-campaign mission activators for remote players.
- Add supervised campaign-switch preparation, safe-point saving and restart control.
- Add transactional installation, checksum-verified resumable downloads, repair
  preservation and rollback; add graphical Linux setup and launcher sources/builds.
- Add real multi-instance Wine smoke tests with live remote command-clock checks.
- Prevent a waiting joiner's independent world clock from running ahead of the
  host; recover an already advanced world through a normal reload before joining.
- Correct the shared AI melee script to recognize remote players, and bind UF
  mines, ammunition workers and mount bookkeeping to the actual acting player.
- Repair repeated native CoD/UO checkpoint reloads, including absent reliable
  command buffers, world-time rollback and a secondary native simulation path.
  Rearm hooks after mission changes even when the game DLL reuses its address.
- Share original script movies and reconnect through normal world loading;
  carry the confirmed party size through CoD credits into UO mission startup.
- Validate canonical English language packs separately from German overlays;
  preserve existing saves and personal settings across language changes.
- Development protocol7 requires host-owned YAP sprint/jump-shot prediction
  rules before attaching a peer, retries live changes and restores local values
  on leaving. FOV and input preferences remain individual.
- Development `0.6.0-dev.3` uses protocol8: acknowledge mission/checkpoint
  changes by session and generation, retry after packet loss, and acknowledge
  duplicates without starting the same load twice. A real two-second outage
  during a map change now recovers; full delayed-world-packet coverage is open.
- Development `0.6.0-dev.4` uses protocol9: tag native engine and Coop state
  packets with their session and world generation before processing them.
  Preserve readable incompatibility messages for earlier development clients.
- Wait visibly and reconnect through native world loading after a longer link
  outage. Stop old native input sends while rejoining; cancel loading peers
  when the host closes, and invalidate deferred tree indices on disconnect.
- Preserve local archived YAP settings even when quitting directly while joined.
- Correct the native DObj-destruction wrapper's missing stack argument.
- Add individual United Fronts equipment preferences and a validated role/ready
  roster contract. Applying independent kits through the native session remains
  in development; dense-map model/animation memory is an open integration gate.
- Show the verified package version and latest local save per campaign in the
  English/German launcher. Compare extra loaded PK3s even under multiplayer filenames.
- Add English/German documentation and mark CoD 2 experimental.
- Preserve each player's weapon slots, ammunition and active weapon across
  checkpoint loading; issue a fresh mission kit only for a fresh player state.
  Avoid a duplicate weapon drop when cleaning up a player restored from a save.
- Keep the joiner's native input timer running while freezing its independent
  world simulation, restoring keyboard and mouse look between host snapshots.
- Adapt Brecourt's post-goal handoff to a healthy participating player, retaining
  the original one-time objectives and explosives actions. Targeted native tests
  cover all four variants; full mission completion remains open.
- Require the same pinned visual patches in every installation and check native
  Core feature exports before declaring a payload compatible. Preserve nested
  save directories during installation and repair.
- Record actual game exit codes during launcher retries and process transitions;
  a successful supervisor exit alone does not prove successful game shutdown.
- Add a signed LAN launcher lobby with persistent participant identities,
  individual equipment choice, confirmation, retry and visible reconnect waits.
  Actual two-/four-process and GUI checks pass. Native owner/plan/resource
  acknowledgement remains in development, so the equipment launch stays disabled.
- Honor intentional departure after a temporary timeout: release only the
  current inactive owner's seat, then give an explicit fresh rejoin a new lease.
- Restore saved position, view and health after reconnecting ordinary players;
  retain explicit downed state and normal revival for Host and joiners. A
  standing1HP player remains alive. Targeted CoD1/UO+YAP checks pass; full
  mission, vehicle and scripted-role coverage is still required.
- Give generated mission fixes priority over mod asset overlays, and retire
  unchanged older owned layers transactionally when updating.

Mission-level coverage, Steam across accounts and all special mechanics remain
acceptance gates. See [handoff](docs/HANDOFF-0.6.md).

## 0.6.0 — Deutsch

**Veröffentlicht am 26.11.2026. Die Abdeckung wird kapitelweise festgehalten; ein
vollständiger Durchspiel-Lauf von Hand und Steam mit zwei getrennten Accounts
sind ausdrücklich als nicht abgedeckt dokumentiert.**

- Das Windows-Paket auf echtem Windows 11 prüfen (QEMU/KVM, UEFI + TPM 2.0),
  nicht nur unter Wine. Ein frisches Basisspiel ohne Suite lässt sich mit
  `Install-CoD-Coop.exe --yes` installieren (Exit 0), `coop\suite-check.exe`
  bestätigt jede Pflichtdatei der Suite per SHA256 auch nach den QA-Läufen, und
  die installierte Suite 0.6.0 besteht den nativen Smoke auf `training`:
  **vier Spieler** in CoD 1 (172,3 / 229,9 / 110,1 Einheiten Joiner-Bewegung
  über echte Eingabe), zwei Spieler in UO (200,0), SP Improved (154,4) und
  United Fronts (173,2), jeweils mit echtem Connect, fortlaufenden
  Remote-Command-Uhren, verworfenen Paketen nicht reservierter Endpunkte und
  sauberem Herunterfahren. Die VM hat keine GPU, deshalb läuft der Smoke auf
  Mesas `llvmpipe`-WGL-Treiber (nur in die QA-Kopien je Spieler kopiert); der
  installierte Abnahmeordner bleibt byte-identisch zur Suite. Zwei Befunde
  daraus bleiben wichtig: Mesas d3d12-WGL-Pfad initialisiert GL, stürzt aber
  beim Laden der Karten-Oberflächen in `libgallium_wgl.dll` ab, und ein
  Spielordner ohne das mitgelieferte `miles/`-Verzeichnis verliert sämtliche
  Miles-3D-Provider, wodurch die Singleplayer-Soundinitialisierung fatal endet.
  Einzelheiten, Befehle und die verworfenen Treiberwege stehen in
  [`run/qa-win-native1/NOTES.md`](run/qa-win-native1/NOTES.md).

- Foy, Noville, Brecourt und Bastogne1 bestehen mit vier Spielern auf dem Produktionspfad:
  Übernahme der nativen Bäume, Eigenbäume und Host-Körperbäume im Heap (keine
  Erschöpfung des Script-Pools), Checkpoint-Reload für jeden Joiner und die
  Upstream-Fixes für weichere Joiner-Animationen, die Host-Waffe im Fahrzeug,
  Revive-Schutz und Mitfahrer, die neben dem Host aussteigen. Das Keep-Alive
  läuft jetzt im Paket-Pump, damit ein langer nativer Ladevorgang den
  Joiner-Slot nicht mehr nach 8 s freigibt.
- Kampagnenabdeckung kapitelweise festhalten statt einen Durchlauf zu
  behaupten. Ein vollständiger Durchspiel-Lauf von Hand ist ausdrücklich **kein**
  Veröffentlichungskriterium: Er entsteht nur durch stundenlanges korrektes
  Spielen und wird deshalb als nicht abgedeckt dokumentiert, während die
  Kapitel-Stichproben die Abdeckungsaussage bleiben. Beide Bastogne1-Fehler vor dem Bestehen bleiben als Evidenz
  erhalten: Der Renderer holt beim Rejoin mit 2 Bildern/s auf, und die
  wiederhergestellte Pose kann auf ein Hindernis zeigen; deshalb wartet die
  Fixture jetzt auf Snapshots der wiederhergestellten Welt und probiert die vier
  Laufrichtungen, während das strenge Bewegungs-Orakel je Richtung bleibt.
  Bizerte ist die erste benannte Inhaltsgrenze: Das Level lädt kein alliiertes
  Spielermodell, deshalb können dort keine Coop-Körper entstehen, und die
  Wüstenstichprobe wechselt zu afrika2, das mit vier Spielern besteht (25
  Übernahmen je Joiner, Reload-Bewegung 210,0/182,9/172,8). Afrika2 hat zudem
  zwei echte Fehler aufgedeckt, die jetzt behoben sind: Die Host-Körpersuche
  deckt auch die Modellfamilien der 3rd Infantry und der 29th Division ab, und
  der Waffendurchlauf der Mod setzt alle acht Soldaten ein `wait 0`, damit vier
  native Clients auf einer Maschine nicht mehr das Script-Watchdog der Engine
  auslösen und die Waffen der restlichen Soldaten verloren gehen.
- Afrika2 und Dawnville erweitern die Vier-Spieler-Stichproben: 25 bzw. 12
  native Baum-Übernahmen je Joiner, je 19 Host-Körper, echte Bewegung über
  Eigentümer-Eingaben und ein nativer Checkpoint-Reload, bei dem alle Joiner
  wieder beitreten. Dawnville startet in einem laufenden Gefecht: Ein untätiger
  Host starb, bevor die Peers fertig geladen hatten, und der pausierte
  Deathscreen blockierte die Beitritte. Der Sampler hält jetzt nur den Host mit
  dem mod-eigenen `coopgod`-Befehl fest und protokolliert das als
  QA-Liveness-Eingabe, nie als Damage-/Death-Aussage. Stirbt der Host, während
  Peers noch laden, bleibt der Listen-Server weiterhin pausiert; dieser
  Produktfall ist im Handoff als offen dokumentiert.
- Pavlov ergänzt die russische Winterstichprobe und legt einen Stock-Fehler von
  United Fronts offen: `Axis_Swap` hinterlässt in den Waffentabellen je Jahr
  eine Lücke (`ger_heer`/1942 setzt kein `sniper[1]`, ein Karten-Spawner setzt
  `sniper[2]`), und die ungeprüfte `precacheItem`-Schleife brach den
  Script-Thread ab, sodass der Rest der Precache-Schleife und die
  Waffenzuweisung der Karte ausfielen. Der Overlay sichert jede der sechs
  Schleifen jetzt mit `isdefined` ab; Pavlov besteht danach mit vier Spielern,
  10 Übernahmen je Joiner und Anfangsbewegung 211,3/199,8/174,7 sowie
  56,5/48,5/60,0 nach dem Reload. Die zwei verbleibenden Konsolenzeilen sind
  benannte Inhaltswarnungen (fehlendes `xmodel/head_blane`, das die Basis als
  `Blane1` ausliefert, und `xmodel/gear_german_headwrap` aus der winterlichen
  deutschen Tabelle von United Fronts) und werden exakt im Text erlaubt und im
  Proof protokolliert; jede andere `ERROR:`-Zeile und jeder Script-Runtime-Fehler
  bleibt fatal.
- Arnhem ergänzt die britische Stichprobe und brauchte einen Produktfix: Sein
  BSP benennt eine Dekoration `Xmodel/chair_office_d` (großes X, die einzige
  solche Referenz im gesamten United-Fronts-Paket), der Renderer-Cache meldet
  diese Schreibweise, und der Ressourcen-Bootstrap lehnte die Karte ab, sodass
  der Host nie exportierte. Der Bootstrap schreibt jetzt nur das Präfix
  `xmodel/` auf die Schreibweise um, die Paketmitglied und Peers nutzen, und die
  Karte besteht mit vier Spielern, 24 Übernahmen je Joiner, den britischen
  Körpern der Mission und Anfangsbewegung 159,4/175,0/148,9 sowie
  178,6/149,6/206,6 nach dem Reload. Eine Stock-Inhaltswarnung bleibt: Arnhem
  und Wolfheze platzieren `xmodel/ammo_panzerfaust_box0`, das Retail nie
  ausgeliefert hat; die dekorative Kiste entfällt, und die Zeile ist eine
  benannte Pro-Map-Ausnahme.
- Pegasusnight ergänzt die zweite britische Stichprobe und legt einen
  host-spezifischen Skriptzustand offen: Der Gleiterabsturz ruft
  `level.player freezeControls(true)` und `shellshock("groggy", 20)` auf dem
  Host-Körper auf, und das Fade-in gibt die vor dem QA-Kit festgehaltene
  Ausrüstung erneut aus. Die Fixture erkennt diesen nativen Tausch, setzt
  denselben Plan einmal mit einer `identity|world|epoch`-Quittung erneut durch
  und wiederholt nur den Host-`+attack`-Burst in einem begrenzten 40-s-Fenster,
  weil der Host bis etwa 108 s bei `pm_flags=0x03000002` blieb, während die
  Peers schon frei waren. Die Karte besteht mit vier Spielern,
  Anfangsbewegung 63,1/117,4/64,9 und 66,6/116,4/109,4 nach dem Reload,
  Magazinen 30/5/20/8→25/4/15/7, beiden Sichtwahl-Phasen und allen vier
  Eigentümern. Das Vier-Eigentümer-Ammo-Gate bleibt unverändert und scheitert
  weiterhin an einem Host, der nie verbraucht; das Kartenskript bleibt
  unverändert und das QA-Kit bleibt der feste amerikanische Katalog.
- Die Varianten-Smokes für CoD1, UO und SP Improved bestehen mit vier Clients
  auf `training` mit der aktuellen Laufzeit (`run/qa-cod1-smoke1`,
  `run/qa-uo-smoke3`, `run/qa-sp-improved-smoke1`): echte Verbindung,
  fortlaufende User-Command-Uhren, unterschiedliche
  Eigentümer-Eingabebewegung (179,0/192,6/151,2, 195,7/165,9/180,1 und
  192,9/173,8/187,5 Einheiten) und sauberer Shutdown. Ein erster
  UO-Versuch auf `sicily1` verband alle vier Clients, maß aber die gescriptete
  Bootsfahrt der Mission (123,2 Einheiten auf jedem Remote), weil
  `docks_boat_arrival()` Spieler und Squad an dasselbe Boot bindet; dieser
  Auftakt ist eine On-Rails-Ausnahme wie carride und tankdrivecountry
  (`run/qa-uo-smoke2`). Der Test von `foy` legte zwei kosmetische
  Stock-Precache-Zeilen in den unveränderten UO-Skripten offen: `maps/foy.gsc` verlangt
  `xmodel/c_us_helmet_moody_winter`, obwohl die getesteten Pakete
  `c_us_helmet_moody` und `c_us_bod_moody_winter` ausliefern, und
  `maps/foy_dummies.gsc` verlangt `xmodel/weapon_garand`, obwohl sie
  `xmodel/weapon_M1Garand` ausliefern. Kein Asset wird erfunden; die zwei
  exakten Zeilen sind eine benannte Pro-Map-Inhaltsregel (`run/qa-uo-smoke1`),
  und das vollständige Vier-Spieler-Verbindungs- und Bewegungsgate der Karte
  bestand, bevor der generische Smoke die Konsolenzeilen ablehnte.
- Der Host kann die Sitzung nicht mehr verlieren, während Freunde noch laden.
  Nimmt er einen tödlichen Treffer, während ein Peer im Resource-Bootstrap
  steckt und kein Remote aktiv ist, wird der Treffer mit der coop-eigenen
  Inflated-Health-Technik gemessen und auf 1 Leben geklemmt, statt den
  Singleplayer-Deathscreen zu öffnen, der den Listen-Server pausiert und die
  beitretenden Peers ohne Gamestate lässt (`run/qa-dawnville-m14-sample1`). Das
  Fenster ist nativer Zustand, kein Timer: ein frischer (120 s) Bootstrap-Peer;
  ein reservierter Sitz zählt nicht, damit ein Solo-Host mit gespeicherten
  Sitzen sterblich bleibt. Mit aktivem Remote gelten wieder die normalen
  Caído/Levantar-Regeln. `run/qa-join-guard4` feuert `coopkill 0 100000` in
  dieses Fenster: Der Host bleibt bei 1 Leben, alle drei Peers treten bei,
  bewegen sich und fahren sauber herunter; `tests/test_join_guard.cpp` deckt die
  Entscheidungstabelle ab.
- Level-Trigger lösen nur noch für den Host aus: Steht ein Mitspieler in einer
  gescripteten Gefahrenzone, fällt deren Reaktion (die Mörser in bastogne1)
  nicht mehr auf den Host, und Fortschritts-Trigger erfüllen sich nicht mehr
  ohne ihn. Ein Peer, der mitten in der Mission beitritt, erscheint am Host
  statt am Kartenstart, und alle bekommen 3 s ohne Schaden, während sich die
  Eröffnungssalven des Levels legen. Das eingefrorene lokale Spiel des Joiners
  führt seine Freizeit-`vmMain`-10/11-Frames nicht mehr aus, und seine
  Entity-Zustände werden vor dem Schließen der lokalen Karte zurückgesetzt.
  `run/qa-c1da93f-smoke2` besteht einen Vier-Spieler-CoD1-Smoke mit beiden
  Trigger-Hooks, allen drei Zustands-Resets und 164,0/179,3/215,7 Einheiten
  Bewegung; die UO- und SP-Improved-Varianten bestehen auf demselben Build
  (`run/qa-c1da93f-uo1` 189,9/193,4/168,8, `run/qa-c1da93f-sp1`
  159,8/175,7/185,2); `tests/test_trigger_filter.cpp`,
  `tests/test_join_placement.cpp` und `tests/test_frozen_vm.cpp` decken die
  Entscheidungen ab.
- Atomaren Lobby-Dateiaustausch bei vorübergehend blockierenden Windows-/Wine-
  Lesern korrigieren; begrenzte Wiederholungen, Erhalt der vorherigen Datei und
  Link-Abweisung beibehalten. Neu gebaute Linux- und Windows/Wine-Worker bestehen
  signierte Gruppentests einschließlich Vierergruppe, Neustart und Spielerbindung.
  Die native Ausrüstungsbindung im Spiel bleibt offen.
- Saubere UF-Startfehler in Foy/Noville an der nativen Grenze von 255 Modellen
  dokumentieren. Registrierung bei tatsächlicher Verwendung bleibt experimentell;
  der Start nur mit Host-Ausrüstung ist ein Diagnosetest, kein Nachweis für vier
  individuelle Ausrüstungen.

- Quellenstand `0.6.0` verlangt Core-Maske 63 einschließlich nativer
  Ressourcenübertragung und lokalisierter Coop-Hinweise. Alte API 15-DLLs werden vor neuem Staging abgewiesen;
  individuelle UF-Ausrüstung wartet weiter auf die native Spieler-/Planbindung.
- Nativen Modell-/Waffenbestand vor dem Laden der Zielwelt des Mitspielers
  übertragen und prüfen. Alte clientseitige Modellzuordnungen vor Übernahme der
  Host-IDs lösen; die native Speicherzuständigkeit erhalten.
- Gespeicherte Liegerichtung und Geländeneigung nach dem Wiederbeitritt
  wiederherstellen. Strenge Vier-Spieler-Checkpoint-Tests mit unterschiedlichen
  Zuständen bestehen in CoD1 und UO+YAP, einschließlich normaler Wiederbelebung
  durch Mitspieler und vier sauberer Spielenden.

- Vollständiger festgelegter Paketstand: CoD, UO, SP Improved, United Fronts und YAP.
- Empfohlene CoD→UO-Hauptkampagne durchgehend mit KI-/Gameplay-Verbesserungen von
  SP Improved. Ursprünglichen CoD-Abschluss samt Abspann erhalten und anschließend
  mit derselben Gruppe in UO fortfahren; Missionsstart nach Bereitschaft der Gruppe.
- Gemeinsame Variantenmanifeste, Installationsnachweise und Inhaltsprüfsummen.
- Engine, Protokoll, Kampagne und Inhalte vor Zuweisung eines Spielerplatzes prüfen.
- Mitspieler hinter derselben IP durch eigene qports unterscheiden; der SP-Transport
  schrieb ursprünglich immer null.
- Kontrollpakete begrenzen und Animationsteilstücke erst vollständig anwenden.
- Festgelegtes YAP neben Coop in UO-Varianten laden; Originalname `DDRAW.dll` bleibt
  in einem getrennten Plugin-Verzeichnis erhalten.
- Geprüfte Menü- und Gameplay-Anpassungen aus den vorhandenen Mod-Dateien erzeugen.
  Missionsauswahl erhalten, United-Fronts-Spielermechaniken und ausgewählte
  Missionsauslöser der ursprünglichen Kampagne für Mitspieler anpassen.
- Begleiteten Kampagnenwechsel mit Vorbereitung, Speichern am sicheren Punkt und
  Neustartsteuerung ergänzen.
- Installation mit Änderungsjournal, geprüften fortsetzbaren Downloads, Erhalt
  persönlicher Daten und Rücknahme; grafisches Linux-Setup und Launcher ergänzen.
- Echte Wine-Mehrinstanztests mit Prüfung laufender Mitspielerbefehle ergänzen.
- Verhindern, dass die lokale Spielzeit wartender Mitspieler dem Host vorauseilt;
  bereits weitergelaufene Welten vor dem Beitritt über reguläres Neuladen zurücksetzen.
- Gemeinsames KI-Nahkampfsystem auf echte Mitspieler prüfen und UF-Minen,
  Munitionsverwaltung und MG-Verwaltung dem tatsächlich handelnden Spieler zuordnen.
- Wiederholtes echtes Checkpoint-Laden in CoD/UO absichern, einschließlich
  zuverlässiger Befehlsbuffer, rückgesetzter Weltzeit und einer zweiten nativen
  Simulationsschleife. Nach Missionswechseln Hooks auch bei gleicher DLL-Adresse erneuern.
- Originale Skriptfilme gemeinsam abspielen und danach regulär wieder verbinden;
  bestätigte Mitspielerzahl über den CoD-Abspann bis zum UO-Start erhalten.
- Englische Basis-Sprachdateien und deutsche Overlays getrennt prüfen;
  unveränderte Spielstände und Einstellungen bei Sprachwechseln erhalten.
- Entwicklungsprotokoll7 übernimmt YAP-Sprint-/Sprungschuss-Regeln vor dem
  Beitritt vom Host, bestätigt laufende Änderungen und stellt beim Verlassen
  die lokalen Werte wieder her. FOV und Eingabeeinstellungen bleiben individuell.
- Entwicklungsstand `0.6.0-dev.3` verwendet Protokoll8: Missions-/Checkpoint-Wechsel
  anhand von Sitzung und Generation bestätigen, nach Paketverlust wiederholen
  und Duplikate ohne erneutes Laden bestätigen. Ein echter zweisekündiger
  Ausfall beim Kartenwechsel wird aufgefangen; verzögerte Pakete alter Welten
  müssen noch umfassend geprüft werden.
- Entwicklungsstand `0.6.0-dev.4` verwendet Protokoll9: Engine- und Coop-Zustandspakete
  vor der Verarbeitung ihrer Sitzung und Weltgeneration zuordnen. Ältere
  Entwicklungsstände erhalten weiterhin verständliche Inkompatibilitätsmeldungen.
- Nach längerem Verbindungsausfall sichtbar warten und über reguläres Laden
  wieder verbinden. Alte Eingabepakete während des Beitritts sperren, ladende
  Mitspieler beim Beenden des Hosts informieren und zurückgestellte Baumindizes
  beim Trennen verwerfen.
- Persönlich gespeicherte YAP-Werte auch beim direkten Beenden während des
  Beitritts erhalten.
- Fehlendes Stack-Argument im nativen DObj-Aufruf korrigieren.
- Individuelle United-Fronts-Ausrüstungswünsche und einen geprüften Vertrag für
  Rollen und Bereitschaft ergänzen. Die tatsächliche Vergabe über die Sitzung
  ist noch in Arbeit; Modell-/Animationsspeicher auf dichten Karten bleibt offen.
- Geprüften Paketstand und letzten lokalen Spielstand je Kampagne im deutschen
  und englischen Launcher anzeigen. Zusätzliche geladene PK3s auch unter
  Multiplayer-Dateinamen beim Inhaltsvergleich berücksichtigen.
- Englische/deutsche Dokumentation; CoD 2 ausdrücklich experimentell.
- Waffenplätze, Munition und aktive Waffe jedes Spielers beim Checkpoint-Laden
  erhalten; eine neue Missionsausrüstung nur an einen frischen Spielerzustand
  vergeben. Beim Bereinigen geladener Spielerreste keinen Waffenduplikat abwerfen.
- Lokalen Eingabetakt des Mitspielers trotz eingefrorener eigener Weltsimulation
  fortführen, damit Tastatur- und Mausblick zwischen Host-Snapshots funktionieren.
- Brecourts Übergabe nach dem Missionsziel auf einen gesunden beteiligten Spieler
  erweitern; ursprüngliche einmalige Ziele und Sprengstoffaktionen erhalten.
  Gezielte echte Spieltests decken alle vier Varianten ab; der vollständige
  Missionsdurchlauf bleibt offen.
- Dieselben festgelegten Grafikpatches in jeder Installation verlangen und native
  Core-Funktionsexporte vor der Kompatibilitätsbestätigung prüfen. Verschachtelte
  Spielstandverzeichnisse bei Installation und Reparatur erhalten.
- Tatsächliche Spielprozess-Exitcodes bei Launcher-Wiederholungen und Neustarts
  erfassen; ein erfolgreicher Begleitprozess allein belegt kein sauberes Spielende.
- Signierte LAN-Lobby im Launcher mit dauerhaften Teilnehmerkennungen,
  individueller Ausrüstungswahl, Bestätigung, Wiederholungen und sichtbarem
  Warten ergänzen. Echte Zwei-/Vierprozess- und GUI-Prüfungen bestehen.
  Die native Besitzer-/Plan-/Ressourcenbestätigung ist noch in Arbeit;
  der Ausrüstungsstart bleibt deshalb gesperrt.
- Bewusstes Verlassen nach einem Ausfall beachten: ausschließlich den Platz
  dieses inaktiven Besitzers freigeben; ein neuer Beitritt erhält eine neue Kennung.
- Gespeicherte Position, Blickrichtung und Gesundheit nach der Neuanmeldung
  normaler Spieler erhalten; Downed-Zustand und reguläres Wiederbeleben für
  Host und Mitspieler bewahren. Ein stehender Spieler mit1HP bleibt lebendig.
  Gezielte CoD1-/UO+YAP-Prüfungen bestehen; vollständige Missionen, Fahrzeuge
  und geskriptete Rollen müssen weiter abgenommen werden.
- Generierte Missionskorrekturen vor Mod-Asset-Paketen laden; ältere unveränderte
  eigene Pakete beim Update gesichert und mit Rücknahme entfernen.

Missionsabdeckung, Steam zwischen Accounts und sämtliche Spezialmechaniken
bleiben Abnahmekriterien. Siehe [Übergabe](docs/HANDOFF-0.6.md).

## Previous release · Vorherige Veröffentlichung

[v0.5.4](https://github.com/benjarogit/CoDCoop/releases/tag/v0.5.4): existing installer
and CoD/UO animation hotfix. Those published assets remain unchanged. / Bestehender
Installer und CoD-/UO-Animationsfix. Veröffentlichte Dateien bleiben unverändert.
