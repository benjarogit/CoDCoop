# Campaign compatibility evidence / Kampagnen-Kompatibilität

## Status

This inventory is **static evidence**, not campaign certification. No mission is
marked passed by the inventory or menu builder. Original PK3 files and the live
installation are read only. Game assets produced by the builder stay local in
ignored `run/` and must not be committed.

Das Inventar ist **statischer Befund**, kein Nachweis einer durchgespielten
Kampagne. Originalpakete und Live-Installation bleiben unverändert. Die lokal
gebauten Overlays passen gezielt Menüs, Missionsauslöser und UF-Spiellogik an;
ihre Erstellung allein beweist noch keinen erfolgreichen Kampagnendurchlauf.

## Reproduce / Reproduzieren

```sh
python3 tools/campaign_inventory.py --game "/path/to/Call of Duty" \
  --output content/campaign-inventory.json
python3 tools/build_campaign_patch.py --game "/path/to/Call of Duty" \
  --profile sp_improved --output run/overlays/sp_improved/zzzz_coop_campaign.pk3
python3 tools/build_campaign_patch.py --game "/path/to/Call of Duty" \
  --profile united_fronts --output run/overlays/UnitedFronts/zzzz_coop_campaign.pk3
python3 tools/build_campaign_patch.py --game "/path/to/Call of Duty" \
  --profile united_fronts --triggers-only --output run/overlays/UnitedFronts/zzzz_coop_triggers.pk3
python3 -m unittest discover -s tests -p test_campaign_patch.py -v
```

Copy generated overlays only into the corresponding mod directory of an isolated
test installation. They must be loaded after both the stock Coop menu and the mod
package; verify actual asset precedence and visible controls in the running game.
The source packages are hash pinned by their `ui/main.menu` member; an unknown
revision is rejected for review instead of applying a guessed patch.

## Observations from the installed packages

- SP Improved 1.5 and United Fronts 1.1 beta contain no native DLLs. Their own
  logic lives in GSC scripts and menu definitions. Disabling all Coop hooks on
  their `fs_game` names does not integrate their gameplay.
- Effective nonlocalized package layers contain 33 top-level BSP maps in the
  CoD1 profile, 49 in UO and SP Improved, and 122 in United Fronts. These counts
  include intros, credits and cinematic maps, not only playable missions.
- The generated inventory records every effective top-level BSP, associated
  script, provider archive, direct transition, conditional transition candidate,
  host assumption and relevant cvar. Engine-executed menu entrypoints and
  dynamically constructed transitions need runtime confirmation.
- UO profiles include the base game's assets. The static layer model is Main,
  then UO, then selected mod, with case-insensitive filename matching and sorted
  package names. It intentionally excludes localization archives and generated
  Coop overlays. Confirm engine asset precedence during runtime tests.
- `uo/uomappack00.pk3` contains `maps/mp/` assets and is a multiplayer map pack,
  not an additional singleplayer campaign.

## Per-map sample rules / Pro-Map-Stichprobenregeln

The four-player sampler (`tools/qa_campaign_sample.sh` ->
`tools/qa_uf_fresh_roles.py`) covers one or two key missions per chapter. A map
that violates a fixture assumption gets a named rule here, backed by its run
evidence; no gate is silently relaxed and no uncovered map is reported as
passed.

- `dawnville` (US, passed `run/qa-dawnville-m14-god1`): the mission opens in a
  live firefight, with axis actors 519-1100 units from `info_player_start`. An
  idle host died 41 s into the map while the peers were still loading; the
  death screen paused the listen server and no peer received a gamestate
  (`run/qa-dawnville-m14-sample1`). Rule: the sampler pins only the host with
  the mod's own `coopgod 0 1` command (`--host-god`) and records it in result
  and proof as a QA liveness input. Kits, ammo, bodies, movement and checkpoint
  reload keep their strict gates. Product open item: the paused death screen
  currently blocks pending joins.
- `bizerte` (content limitation): the level loads no allied player model, so no
  Coop body can be built on either side and the body gate cannot pass. Rule:
  bizerte is not a sample; `afrika2` is the desert sample. Evidence:
  `run/qa-bizerte-m14-sample1`.
- `carride`, `tankdrivecountry` (on-rails starts): the mission begins with the
  player attached to a moving vehicle, so owner-input movement cannot be
  measured. Rule: documented exception, not sampled.
- `bastogne1` (post-reload renderer catch-up): joiners re-enter with the
  renderer at 2 fps and zero snapshots for seconds, and the restored pose can
  face an obstacle. Rule: wait for fresh restored-world snapshots and probe all
  four walk directions while keeping the strict per-direction oracle. Evidence:
  `run/qa-bastogne1-m13-wall1`.
- `afrika2` (desert and vehicle sample): the map runs a Sherman and supplies
  its GIs as 3rd Infantry models; the host body lookup covers those families
  and the authored AI weapon pass yields every eight actors so four native
  clients do not trip the engine's script watchdog. Those are product fixes,
  not map rules. Evidence: `run/qa-afrika2-m14-yield1`.
- `pavlov` (Russian winter sample, passed `run/qa-pavlov-m15-sample3`): the map
  triggered a stock United Fronts defect, fixed in the overlay, and keeps two
  named content warnings. `Axis_Swap` leaves a hole in its per-year weapon
  tables (`ger_heer`/1942 sets no `sniper[1]`, a map spawner sets
  `sniper[2]`), and the unguarded `precacheItem` loop aborted the thread, so the
  remaining precache and the map's weapon assignment never ran
  (`run/qa-pavlov-m15-sample1`). The overlay now guards every entry with
  `isdefined` and the same map passes four-player Coop. Rule: the fixture
  allows exactly two console lines, `ERROR: Cannot precache
  'xmodel/head_blane'` and `ERROR: Cannot precache
  'xmodel/gear_german_headwrap'`, matched by exact text and recorded in the
  proof; the first model does not exist because the base game ships it as
  `Blane1` while `maps/pavlov.gsc` precaches the other name, the second is
  United Fronts' winter German table for `sewer`/`pavlov` only. Every other
  `ERROR:` line and every script runtime error stays fatal. Evidence:
  `run/qa-pavlov-m15-sample2` (all gameplay gates passed, final console gate
  failed on those two lines) and `run/qa-pavlov-m15-sample3`.
- `arnhem` (British sample, passed `run/qa-arnhem-m16-sample3`): the map needed
  a product fix and keeps one named content warning. Its BSP carries one
  `misc_model` with the authored name `Xmodel/chair_office_d` (capital X, the
  only such reference in the whole United Fronts package); the renderer cache
  reports that spelling, so the resource bootstrap rejected the map and the host
  never exported (`run/qa-arnhem-m16-sample1`). The bootstrap now canonicalizes
  only the `xmodel/` prefix. The map also places
  `xmodel/ammo_panzerfaust_box0` although retail ships only
  `ammo_panzerfaust_box1/2/3`, so every client logs `ERROR: Cannot precache
  'xmodel/ammo_panzerfaust_box0'` and the decorative crate is skipped
  (`run/qa-arnhem-m16-sample2`). Rule: that one line is allowed for `arnhem`
  and `wolfheze`, matched by exact text and recorded in the proof; the missing
  prop stays missing and no asset is invented. The fixture's kit catalog is the
  fixed American QA set, so the run proves kit transport, ownership and owner
  fire on a British mission, not a faction-correct loadout.
- `pegasusnight` (second British sample, passed
  `run/qa-pegasusnight-m17-sample4`): the glider intro owns the host body.
  `blackout()` calls `level.player freezeControls(true)`, teleports the player
  and calls `level.player shellshock("groggy", 20)` directly after
  `glider ride finished`; 16.1 s of crash voices later `intro_fadein()` releases
  the controls and re-gives the loadout captured at map start
  (`level.playerWeapon`, before the QA kit was applied), which is why a plain
  spawn kit disappears again (`run/qa-pegasusnight-m17-sample1`). On a listen
  server `level.player` is the host body, so only slot 0 is inside that window:
  the native observer recorded `shellshock{index=1,time=78050,duration=20000}`
  and host `pm_flags=0x03000002`, while all three peers stayed at `pm_flags=0`
  and consumed ammo on the first burst. The host kept `0x03000002` until about
  108 s, then `pm_flags=0x2` and its first consumed round (30→25). The bits
  above `0x2` are not named here; the raw values are recorded. Rule: after the
  scripted rearm the fixture repeats only the host's `+attack` burst inside a
  bounded 40 s window (`SCRIPTED_HOST_FIRE_RELEASE`) and records the native
  state of the first consumed round. The four-owner ammo gate is unchanged and
  still fails a host that never consumes; the map script stays unmodified and
  the QA kit stays the fixed American catalog.

Der Vier-Spieler-Sampler deckt ein bis zwei Schlüsselmissionen je Kapitel ab.
Verletzt eine Karte eine Annahme der Fixture, bekommt sie hier eine benannte,
durch Lauf-Evidenz belegte Regel; kein Gate wird still aufgeweicht und keine
nicht abgedeckte Karte als bestanden gemeldet. Dawnville startet in einem
laufenden Gefecht: Der Host starb nach 41 s Wartezeit, der Deathscreen pausierte
den Listen-Server und kein Peer bekam ein Gamestate. Deshalb setzt der Sampler
nur den Host mit dem mod-eigenen `coopgod 0 1` fest und protokolliert das als
QA-Liveness-Eingabe. Bizerte bleibt Inhaltsgrenze (kein alliiertes
Spielermodell), `carride`/`tankdrivecountry` bleiben On-Rails-Ausnahmen,
Bastogne1 wartet auf gerenderte Snapshots der wiederhergestellten Welt und
prüft alle vier Laufrichtungen. Pavlov deckte einen Stock-Fehler von United
Fronts auf: `Axis_Swap` hinterlässt in den Waffentabellen je Jahr eine Lücke
(`ger_heer`/1942 setzt kein `sniper[1]`, ein Karten-Spawner setzt `sniper[2]`),
und die ungeprüfte `precacheItem`-Schleife brach den Thread ab, sodass der Rest
der Precache-Schleife und die Waffenzuweisung der Karte ausfielen. Der Overlay
sichert jede dieser sechs Schleifen jetzt mit `isdefined` ab; die Karte besteht
danach mit vier Spielern. Zwei Konsolenzeilen bleiben als benannte
Inhaltswarnungen erlaubt (fehlendes `xmodel/head_blane`, das die Basis als
`Blane1` ausliefert, und `xmodel/gear_german_headwrap` aus der winterlichen
deutschen Tabelle für `sewer`/`pavlov`), exakt im Text verglichen und im Proof
protokolliert; jede andere `ERROR:`-Zeile und jeder Script-Runtime-Fehler bleibt
fatal.

Arnhem (britische Stichprobe, bestanden mit `run/qa-arnhem-m16-sample3`)
brauchte einen Produktfix und behält eine benannte Inhaltswarnung: Sein BSP
trägt genau eine `misc_model`-Entity mit dem Autorennamen
`Xmodel/chair_office_d` (großes X, die einzige solche Referenz im gesamten
United-Fronts-Paket); der Renderer-Cache meldet diese Schreibweise, deshalb
lehnte der Ressourcen-Bootstrap die Karte ab und der Host exportierte nie
(`run/qa-arnhem-m16-sample1`). Der Bootstrap schreibt jetzt nur das Präfix
`xmodel/` um. Zusätzlich platziert die Karte
`xmodel/ammo_panzerfaust_box0`, obwohl Retail nur `ammo_panzerfaust_box1/2/3`
ausliefert; jeder Client loggt deshalb `ERROR: Cannot precache
'xmodel/ammo_panzerfaust_box0'` und die dekorative Kiste entfällt
(`run/qa-arnhem-m16-sample2`). Diese eine Zeile ist für `arnhem` und `wolfheze`
erlaubt, exakt im Text verglichen und im Proof protokolliert; das fehlende
Objekt bleibt fehlend, es wird kein Asset erfunden. Der Kit-Katalog der Fixture
ist der feste amerikanische QA-Satz, der Lauf belegt also Kit-Transport,
Eigentum und Eigentümer-Schuss auf einer britischen Mission, keine
fraktionsrichtige Ausrüstung.

Pegasusnight (zweite britische Stichprobe, bestanden mit
`run/qa-pegasusnight-m17-sample4`) gehört dem Gleiter-Intro: `blackout()` ruft
`level.player freezeControls(true)` auf, versetzt den Spieler und ruft direkt
nach `glider ride finished` `level.player shellshock("groggy", 20)`; 16,1 s
Absturzstimmen später löst `intro_fadein()` die Kontrolle und gibt die beim
Kartenstart festgehaltene Ausrüstung (`level.playerWeapon`, vor dem QA-Kit)
erneut aus, weshalb ein normales Spawn-Kit wieder verschwindet
(`run/qa-pegasusnight-m17-sample1`). Im Listen-Server ist `level.player` der
Host-Körper, also liegt nur Slot 0 in diesem Fenster: Der native Observer las
`shellshock{index=1,time=78050,duration=20000}` und Host-`pm_flags=0x03000002`,
während alle drei Peers bei `pm_flags=0` blieben und schon im ersten Burst
Munition verbrauchten. Der Host behielt `0x03000002` bis etwa 108 s, dann
`pm_flags=0x2` und seine erste verbrauchte Patrone (30→25). Die Bits oberhalb
von `0x2` werden hier nicht benannt; die Rohwerte stehen im Proof. Regel: Nach
dem gescripteten Rearm wiederholt die Fixture nur den Host-`+attack`-Burst in
einem begrenzten 40-s-Fenster (`SCRIPTED_HOST_FIRE_RELEASE`) und protokolliert
den Native-Zustand der ersten verbrauchten Patrone. Das
Vier-Eigentümer-Ammo-Gate bleibt unverändert und scheitert weiterhin an einem
Host, der nie verbraucht; das Kartenskript bleibt unverändert und das QA-Kit
bleibt der feste amerikanische Katalog.

## Mission progression

SP Improved keeps separate base-game/UO mission selection and changes many
original scripts and BSPs. Its documentation describes starting at Training for
CoD1 and Bois Jacques (`bastogne1`) for UO.

United Fronts dispatches mission completion in `maps/_UF_maps.gsc`, function
`EndLevel`. Its per-map `missionSuccess` calls are often commented out. The
central dispatcher sets `nextmap[0]` and `nextmap[1]`; selection also depends on
`sp_order`, `sp_original` and other branches. The static inventory keeps branch
indices as candidates and never treats all edges as unconditional.

Test the chronological, reordered, original-only and mod selections through the
actual menus and mission completion. Starting every BSP or forcing `coopendlevel`
does not count as a successful playthrough or a validated campaign transition.

## Implemented, bounded script adaptations

The menu/mechanics overlay for United Fronts transforms only the pinned
`maps/_load.gsc` and `maps/_UF_weapons.gsc` revisions:

- A guarded joining-player monitor starts binocular, ammunition and bipod
  workers once per player, including late joins. It starts unconditionally from
  `_load`, independent of the mod's optional forced-weapon selection branch.
- Binocular ammunition/stockpile and reload cancellation notifications belong
  to the individual player. The existing infinite-ammunition option is applied
  to each player's own inventory rather than only the host's.
- Mine placement resolves the throwing player from authoritative native missile
  ownership, after allowing a host frame to publish the metadata. An absent
  owner is never interpreted as player zero. Placement, angles, pickup and
  explosion handlers remain bound to that player.
- The original `getPlant` implementation used the actual protagonist as a
  temporary return struct, assigning trace coordinates to `level.player.origin`.
  The patch uses `spawnstruct()` for those three temporary values and preserves
  the host's position and angles.
- Bipod placement/stance use per-player fields and the native
  `spawntriggermount(mins, maxs, crouched)` primitive. Trigger volumes follow the
  player's vicinity and are removed when the creator dies or disconnects.

The separate trigger overlay accepts actual player activators in four reviewed
mission functions: Brecourt explosive pickup, Burnville flak dialogue trigger,
Dawnville church exit and Pegasusnight bunker suppression. The original
single-world action and its break/notification remain unchanged; cinematic
protagonist references are not replaced. The builder chooses each profile's
effective script revision and rejects unknown input hashes.

These edits establish the implementation boundary; full mechanics and campaign
acceptance still require the runtime cases below.

## Original host assumptions and remaining checks

Original SP scripts intentionally store the authoritative protagonist in
`level.player`. Replacing this token globally with all players would duplicate
one-shot world effects and corrupt scripted scenes. Host-global references are
review candidates, not automatically bugs. The current inventory finds 1,088 in
CoD1, 2,708 in UO, 2,732 in SP Improved and 4,598 in United Fronts; these are lexical
counts, not runtime findings.

United Fronts has concrete per-player adaptation work in
`maps/_UF_weapons.gsc` (line numbers are for the pinned installed revision):

- `Binoculars_Ammo`, line 669: observes only `level.player` and stores ammunition
  restocking in global `level.stockpile`. `Reload`, line 774, updates the same
  global. Remote binoculars need actor-specific observations and stock accounting.
- `Check_Grenades`, line 990: scans all grenades, but its mine branch starts
  `PlantMine` on `level.player`, regardless of which player threw it. The mine's
  owner must come from engine projectile ownership, not nearest-player guessing.
- `PlantMine`, line 1059: mixes `self` with host angles and restarts mine
  explosion/pickup handlers on the host. Per-player ownership must remain
  consistent from placement through pickup and explosion.
- `Trigger_Mount`, line 3232, and `Trigger_Stance`, line 3286: share global
  `level.mount_mg`/`level.mount_pose` and host-only stance. Independent remote
  bipods need per-player trigger state and a verified engine mount target.
- Smoke-grenade airstrikes scan world entities, which is useful for multiple
  players, but attribution, damage, effects and duplicate application still need
  observation on host and joiners.

The menu overlay preserves mission selection, mod settings, weapons menus
and existing actions. It adds Coop at y=450 and moves only the Coop hosting label
to the lower left. Pause predicates use `ui_coop_paused`, keeping menu actions
reachable while hosting without pausing the shared world. A successful package
build does not imply runtime success for the script adaptations above.

### Native projectile-owner evidence

Ordinary PE disassembly (Capstone, not a retained REA Evidence record) of the
installed `uo_gamex86.dll` identifies grenade spawning at RVA `0x27a50`. At
`0x27acc` it reads the shooter's entity number (`[edi+6]`), writes it to the new
missile's `gentity+0xfc` at `0x27ad0`, and stores the shooter pointer at
`gentity+0x14c` at `0x27add`. The entity type is set to missile (`3`) at `0x27abb`.
Missile trace/impact code consumes `+0xfc`, including RVAs `0x272bd`, `0x2739c`
and `0x274f6`. The native Coop bridge validates entity type, active player index
and owner pointer before exporting a bounded registry of at most 128
`coop_owner_bank_<index>` integers to GSC. Each combines entity and owner in one
value, `(entityNumber + 1) * 4 + ownerNumber`; the script reads the published
count and matches the entity range. Empty, missing and overflowed ownership is
never treated as host ownership. This bounds persistent engine cvar allocation
instead of creating a new cvar for every missile entity index across missions.

`Coop_InitMineResources` prepares the original UF mine item, model, sound names
and explosion effect during `_load`. The original code only prepared these when
the protagonist already carried mines. This allows a remote mine loadout while
the protagonist retains ordinary grenades. The original shared grenade scanner
and its once-only `!isdefined(level.stuka_bomb)` startup guard are retained.

Native `spawntriggermount` at RVA `0x341a0` reads vector arguments 0/1 and integer
argument 2, normalizes the bounds, creates the trigger and initializes its stance.
This observation establishes the primitive's signature, not successful remote
mount gameplay by itself.

## Upstream Jeep issue

[Upstream issue #1](https://github.com/TheTiranix/CoDCoop/issues/1) is titled
“Client Crashes at the very first mission after moving away from jeep”. Its
attached screenshot was inspected directly: the game is United Offensive and
the error is `MT_AllocIndex: failed allocation of 9206 bytes for script usage`.
The issue contains no further reproduction detail or comments.

This is allocator exhaustion evidence, not proof of a vehicle collision bug.
Existing notes already describe UO-owned XAnim tree lifetime differences. Test
allocation/free balance while moving through BSP visibility areas, destroying
entities, changing models and repeatedly loading checkpoints. Correlate allocator
usage with DObj/tree creation and actual failed allocation before choosing a fix.
The screenshot alone does not prove a specific leak is responsible.

## Continuous recommended campaign

The recommended `sp_improved` profile uses the UO executable for both campaigns.
Its local mainline overlay changes the final Berlin objective handler only after
the existing objective checks and preserves `cod_end.roq`. With `coop_mainline=1`,
the normal transition enters a private alias of the original CoD credits map.
The alias retains the original credits script and its timing, then calls the
original `missionSuccess` transition to `bastogne1`. The UO credits remain intact
for the end of the UO campaign. Other profiles do not enable this route.

An alias is necessary because UO replaces `maps/credits.bsp` and its script:
simply entering `credits` after Berlin would show the UO ending. The builder
reads and verifies the original map and three scripts locally; none of these
game assets are committed or distributed by this repository. Build it with:

```sh
python3 tools/build_campaign_patch.py --game /path/to/game --profile sp_improved \
  --mainline --output /path/to/staging/sp_improved/zzzzzz_coop_mainline.pk3
```

The inventory records a concrete SP Improved ally change: several existing
American/Russian ally archetypes raise `bravery` from 6 to 55, while the checked
accuracy and health fields stay unchanged. This establishes a parameter change,
not an empirical claim that every AI actor behaves better or already targets
every remote player.

## Validation completed here

### Checkpoint regression and targeted correction

The production-only SP Improved profile was tested on `pathfinder` with two real
clients and actual native save/load commands. Earlier runs exposed three concrete
failures: a restored remote sent `snd_fade 1 0` through a native reliable manager
with zero capacity; a rolled-back snapshot reached a joiner before its local
reload; and an additional CGame entry point continued local world simulation
against host-owned vehicle DObjs.

The native correction guards uninitialized remote transports, detects restored
host world generations, waits for the joiner's genuinely new local world before
rejoining, and suppresses only the frozen joiner's extra server-simulation trap.
UO CGame syscall `0xfe` (CoD 1 counterpart `0xfc`) reaches game `vmMain(11)`:
its resumable entity simulation dispatches vehicle thinking and wheel-tag queries
outside the ordinary `SV_Frame` hook. Host vehicle mechanics and client animation
advancement remain active.

Core `19470452cdbebf4fea70eb1c5e438a2a43d03c759cc5c4b831cc217699d74641`
then passed three consecutive native checkpoint reloads and a separate five-reload
stress run on the same frozen binary. Every reload restored
an earlier host world time, rejoined the actual remote, advanced both command
clocks and retained rendered snapshots. Engine/GSC error checks, subsequent
observation and clean shutdown passed. The actual suppressed trap was logged at
each world entry. The local evidence is preserved under
`run/uf-ai-qa/history/1795269478334761857` (three reloads) and
`run/uf-ai-qa/history/1795269847901282619` (five reloads), including the native
saves, runtime DLLs, logs and images. Host and joiner screenshots after the
three-reload run were also visually inspected: both showed the normal scene,
weapon and HUD, without an error menu or black frame. This is focused checkpoint
coverage, not a mission playthrough.

### Completed focused checks

- Twenty-seven unit tests pass: comments/strings/braces handled, only pause predicates
  rewritten, mod settings preserved, Coop popup not nested inside main, unknown
  revisions rejected, source left unchanged, deterministic ZIP output, and
  commented-out transition calls excluded. Additional checks ensure only the
  reviewed actor-bound functions change, unknown gameplay revisions fail, and
  one-shot mission actions and protagonist camera roles are preserved.
- A real host and joiner loaded United Fronts with YAP and the script overlay.
  The QA fixture gave the two actual player entities different binocular
  ammunition, changed each independently, and observed the normal asynchronous
  workers preserve separate stockpiles. Two actual `spawntriggermount` entities
  were created with separate player bindings and removed after the check.
- With `--projectile-owner`, the actual joiner selected its grenade slot and
  threw using real attack input. A test-only GSC observer found the engine-created
  projectile and the production native-bank resolver returned that remote player.
  No projectile, registry entry or owner was synthesized by the test.
- The remote then carried the actual UF mine weapon while the host retained its
  grenade loadout. Real remote attack input created the native missile, the
  production owner resolver selected that remote actor, and the original mine
  placement handler populated the remote actor's mine array. The host's origin
  stayed unchanged. The normal pickup worker also removed the world mine and
  replenished the remote's grenade ammunition without a synthetic pickup event.
- A second real remote mine triggered its original proximity/explosion worker
  when a live axis actor was positioned beside it using the engine's actor
  teleport API. The fixture observed the real mine trigger flag, world-entity
  deletion and enemy health loss. It did not issue damage calls or fabricate an
  explosion notification. The explicit enemy positioning is a mechanic fixture,
  not proof of a naturally completed combat encounter or mission.
- This hostile-remote test exposed `animscripts/melee.gsc` reading AI-only
  `anim_pose` on a remote player. A pinned shared overlay now recognizes every
  actual player entity and reads that enemy's native `getstance()` instead;
  the original AI-enemy branch and melee animation choices are preserved. The
  repeated real mine/combat probe completed with no script runtime errors.
  The fixture never assigned an AI `enemy`, `target` or `goal`: native AI chose
  the remote player itself. The mine check measures damage to an enemy, however;
  it does not establish that this enemy damaged the remote player.
- A separate `--ai-remote` run then passed a stricter autonomous attack check.
  An existing live axis actor was positioned 32 units beyond the actual remote
  player on the line away from the host. No enemy, target, goal, accuracy or
  damage assignments were made. Native AI selected that remote as its `enemy`;
  the remote received an engine `damage` notification attributed to that exact
  actor with positive damage, and its health decreased. Real two-client liveness,
  movement, stable observation, no GSC runtime errors and clean shutdown also
  passed. This establishes one hostile-remote attack scenario, not every weapon,
  AI archetype, map or four-player encounter.
- A later Brecourt probe on core `19470452…` initially did **not** reproduce
  autonomous acquisition: a healthy axis actor at 32 units selected no enemy and
  delivered no remote damage. Both clients and real movement were healthy. That
  negative is retained, rather than explaining it away as a native restriction.
  Read-only disassembly shows that UO `0x20079360/0x200793A0` enumerate all 36
  sentient slots by team; perception `0x2006FB50` and enemy scoring `0x200710xx`
  use those iterators. ClientConnect initializes each actual client's sentient.
  The code is therefore not a simple player-0-only sensory implementation.
- A subsequent pinned-core Brecourt run added read-only sight/activation
  diagnostics. The trace hit real remote 1 (fraction `0.510516`); native actor 129
  chose remote 1 and delivered an engine-attributed 43 damage, reducing health
  600→557. An external `ReadProcessMemory` helper, with no writes, confirmed
  remote sentient slot 17/team 2/exclusion field `+0x30 == 0`; the actor's enemy
  pointer changed to that sentient and its per-remote visibility became 1. This
  run passed the real join, 147.1 units of remote input movement, stable
  observation, script-error checks and clean shutdown. No enemy/goal/target,
  flags, accuracy or damage assignments were used. Existing actor positioning
  is explicit fixture setup; varying endpoint/LOS/activation conditions and
  other maps still require wider acceptance coverage.
- UF's pinned Pathfinder script precached two nonexistent helmet assets. The
  local overlay replaces only those two calls with the three actual 82nd helmet
  variants from the mod's own pinned model alias; mission actions are retained.
  UF's complete 13-model union of world, pickup, gun and hand assets is
  recorded for its seven carry/deployable MG definitions. The current code uses
  native `precacheItem` for those seven definitions: world/pickup resources take
  server CS slots while native weapon/media caches prepare first-person assets. Package origins and SHA-256 values are recorded in
  `campaign_patches/uf_mount_models.json`; every asset was checked in the owned
  packages. The initial seven-world/drop-only fix exposed a second real attach
  failure (`viewmodel_30cal_z`), and the complete set then passed the Brecourt
  join above. Native precache validation remains enabled. This validates this
  loadout-divergence regression, not every UF model or campaign.
- A real remote MG deployment/fire scenario passed on frozen core
  `6cbb0f969b46357067bf05c8f02801f3206367feeaf44071592c48038c0a069d`
  with two UF Brecourt clients and `com_hunkmegs 512`. The actual remote used
  crouch, its real primary inventory slot, `weapalt` and the mod's normal ADS
  input. Test setup positioned it near an existing authored MG emplacement;
  it did not create terrain or bypass placement rules. The original production
  `BipodPlaceable()` checks accepted a position that remained stable after normal
  hull/gravity settling, and the production worker created its owned mount.
  A separate read-only process observer saw native deploy state 12/animation 19,
  followed by ready state 0, ADS fraction 1 and the native ADS flag. Real remote
  attack input then consumed four rounds (100→96) while the script's `isads()`
  remained true. The fresh joiner screenshot shows the deployed MG at actual
  sandbag cover. Join, 144.8 units of prior input movement, error checks and clean
  shutdown also passed. This validates one carried MG's deployment/fire flow;
  other MG families, simultaneous mounts, hit/damage results and 256 MB operation
  remain separate acceptance items.
- The MG probe initially rejected unsupported spawn-area terrain, which is an
  expected constraint. Fixture development also exposed real inventory-slot
  variation and an invalid observer assumption: UO returns to idle animation 0
  after deployment, rather than the legacy debug enum 18. Its actual deployment
  transition, complete ADS and ammunition consumption are now required together.
  Earlier failed observations are retained; no production rule was relaxed to
  make the test pass.
- The same real MG deployment/fire check subsequently passed on frozen core
  `efbf03ec85b220652f6d6cdbdd257cc3d3f5a95261fe6ad9376705f53f8ca0c3`
  with native item/media registration instead of direct first-person CS model
  entries. Remote attack again consumed 100→96 rounds while ADS remained active.
- A real remote smoke airstrike passed on that same core at 512 MB hunk. Native
  smoke projectile 304 belonged to remote 1, and its owner reached the original
  shared Bomber call. Normal smoke cost was 4→3; the host's grenade stock stayed
  8→8. Exactly one original call created a P47 aircraft, with the first original
  bomb-explosion/native `radiusDamage` path at 32,150 game milliseconds; four
  impacts occurred before shutdown. This is evidence that the normal action
  path executed, not a claim that a particular enemy took damage. Normal delay,
  aircraft ordering and damage code were not replaced. The full real-client
  smoke harness and corrected scenario aggregate returned PASS.
- Native binocular artillery also passed a separate real two-player probe on
  frozen `efbf03ec…` at 512 MB hunk. The normal inventory API supplied three
  tokens. Real remote equip/ADS/fire consumed exactly one; a second attack input
  inside the authored three-second fire time consumed no extra token. A
  read-only native observer captured exactly 20 distinct missile entities owned
  by remote 1, matching the weapon's projectile count. The original actor-local
  reload worker restored 2→3 after 180,100 game milliseconds with timescale 1;
  the host's pistol stock stayed 28→28. The remote remained alive at 600 health,
  normal liveness/input checks and clean shutdown passed, and no ammunition
  setters, timer overrides, synthetic projectiles, target assignments or damage
  calls were used by the fixture. Specific victim damage remains unmeasured.
- Aircraft resource initialization now preserves the original UF nation/type
  selection independently of the host's currently carried grenade. All four
  selectable aircraft and the shared bomb/gun/death/weather FX assets have
  verified package origins and hashes in `campaign_patches/uf_air_assets.json`.
  Caller radio follows the native projectile owner; an unknown caller uses the
  smoke marker's position rather than attributing it to the host.
- **The current universal resource-registration candidate is not ready for
  final packaging.** The new native loading gate found hard 256-model capacity
  failures on Noville, Foy and Tropez. Original UF script baselines loaded at
  251, 248 and 247 server CS models respectively. Brecourt fits at 250 after
  native MG item registration freed six unnecessary CS entries, but that result
  cannot establish dense-map compatibility. A host-selected resource/preload
  contract is still needed; capacity checks remain enabled and no mechanic has
  been removed to obtain a pass.
- Brolio Assault's source BSP pickup entity named nonexistent
  `xmodel/world_greasegun`. The local builder now generates that alias from the
  package's own canonical `xmodel/weapon_greasegun`, as used by its Greaser weapon
  definition. The BSP, pickup class and weapon behavior stay unchanged; BSP,
  definition and model hashes are pinned. Brolio then loaded at 222 CS models.
- A negative control changed the worker back to a shared stockpile. The same
  real two-player probe produced an explicit mechanics failure; the runner
  reported `DETECTOR: PASS`. Timeouts do not count as detecting this regression.
- The original CoD credits alias ran to its natural completion with a real
  host/joiner pair in the recommended UO-based profile. The native helper applied
  the original victory Continue action, both clients loaded `bastogne1` and
  rejoined, and the normal mission-start action waited for the party's readiness.
  The original Jeep introduction then released host and remote control, and
  remote movement through actual input, stable observation and clean shutdown
  passed. Credits used engine timescale 4; the route took 99.383 wall seconds,
  and timescale returned to 1 on arrival. This targeted route check does not
  constitute a Berlin mission or full-campaign playthrough.
- Both installed mod revisions generated local menu overlays successfully.
- All four profile inventories were generated from the installed packages.
- No campaign playthrough is inferred by these tools. Rendering, menu placement,
  transitions and gameplay must be accepted by the real-client runtime suite
  before declaring support.

The durable `tools/qa_campaign_resources.py` gate ranks all 122 UF entry maps
using BSP entity-model references, then loads a bounded selected set in one
existing owned QA copy. It records native CS model tables through a read-only
process observer, loader/core hashes, engine logs and nonfatal diagnostics.
Static counts omit character aliases and dynamic script precaches. Neither
static ranking nor native loading is a mission playthrough.

The highest static counts were Noville 155, Foy/Tropez 139, Aachen 137,
Ponyri 126 and Bastogne2/Brolio Assault/Sicily1 115. Native production resource
loads passed Aachen 249, Ponyri 250, Bastogne2 235, Brolio Assault 222 and
Sicily1 192 CS slots. Friendly-chain/path diagnostics were retained for campaign
investigation; they are distinguished from fatal `ERROR:` messages. The three
dense-map overflows above remain blocking acceptance findings.

Individual starting equipment is the chosen Coop policy: each of up to four
players plans their own four-slot kit before the mission; faction, year, order
and the shared world remain host-owned. The experimental `--world-policy
selected` builder preserves original selected equipment/aircraft registration
instead of reserving every possible server model. Its default-loadout resource
loads passed Noville 250, Foy 248 and Tropez 248. With fixed legal American
MG30cal + Thompson + binoculars + smoke, the selected candidate and unchanged
original UF scripts both used exactly Noville 252, Foy 250 and Tropez 253.
These single-host loading checks do not demonstrate four individual inventories.
The universal policy remains the builder default pending the native media and
preflight integration; the selected candidate is not a release-ready workaround.

`tools/uf_equipment_catalog.py` extracts active original options/victory menu
choices and the six weapon processors into
`campaign_patches/uf_equipment_catalog.json`. It records package/member/SHA-256
for the source scripts, menus, 76 weapon/alternate definitions and model media.
Commented controls and blank icon selectors are excluded. British, Russian,
American, German and Italian are active original nation choices. Polish has
script/menu remnants but no active nation selector and missing weapon assets;
the planner rejects that unavailable family. British Lewis/Mannlicher enum
remnants likewise do not become selectable just because a processor mentions
them. Manual processors have independent primary, secondary, pistol and grenade
choices with no year/history test; the authored automatic-loadout path has
separate history/year logic and is not flattened into this catalog.

The roster helper validates one to four complete individual kits, follows native
alternate-weapon registration, deduplicates world/pickup/projectile models, and
separates first-person media from server CS slots. A smoke kit resolves the
single shared aircraft using the original host faction/campaign/map decision,
including the original Omaha/Eugene Stuka exception. Personal kit nationality
does not change the shared aircraft. It preserves original equipment costs and
support cooldowns. Catalog extraction is read-only and commits metadata only.

A four-role American example (MG/smoke, scoped rifle/mine, bazooka/satchel and
rifle/frag) uses active original choices and requires 23 distinct world models
plus 39 media names. Union with the measured same-faction MG/smoke baseline
would require Noville 262, Foy 258 and Tropez 259 slots, beyond the native 255
usable entries. This is a conservative source-derived preflight result, not a
four-player runtime crash claim. Exact additions are retained in
`run/uf-individual-roster-policy.json`. The helper diagnoses overflow; it does
not remove roles, enlarge byte indices or approve map loading. Its CLI can
consume an external native model-table JSON, but marks world matching
unverified until the launcher supplies an exact baseline contract. Native early
renderer/XModel caching and full individual-kit application still need runtime
acceptance. All original mission/script/character resources must be included in
that baseline; BSP counts alone cannot establish capacity.

The separate pure `tools/uf_equipment_roster.py` contract now records one to
four independent participants using native slot IDs 0–3, including the host.
Duplicate, boolean, out-of-range or missing-host IDs are rejected. It binds the
catalog identity, host world, complete personal kits and revision into a
deterministic plan SHA-256. The host owns world/membership; each participant
alone submits their own kit, including the host's own kit. The host cannot
select a peer's kit through either kit edits or membership replacement. New
peers start automatic/unresolved until their own authenticated submission.
Joint role discussion does not transfer ownership of a participant's choices.
Any actual kit, world or party
change increments the revision, clears every ready acknowledgment and discards
the previous resource approval. Stale revisions/plans are rejected. Every
participant must acknowledge their own current plan after host resource
verification records the exact world/media union and an evidence identity.
The transport must provide authenticated actor identity; no identity claimed
inside a participant payload is trusted by this source contract.

Automatic equipment remains an unresolved authored-loadout request, with no
invented family/slot assignment or resource approval. It blocks contract
readiness until a future native resolver supplies an audited path. The public
snapshot includes host world, each participant/kit/ready state, plan/catalog
identities, resource requirements and a specific waiting status. It is suitable
for future read-only launcher display behind an explicit capability; protocol
7 alone grants no capability. Even a fully acknowledged source-contract plan
always reports `runtime_ready: false`: this module implements neither network
transport, native registration nor actual individual inventory application.
Nine focused contract tests cover these boundaries. Example planning data is
retained in `run/uf-individual-roster-contract.json`, without fabricated native
approval. The four-role union retains all 23 world models and 39 media names.

Recreate the catalog without copying game assets:

```sh
python3 tools/uf_equipment_catalog.py --game /path/to/owned/game \
  --output /path/to/uf-equipment-catalog.json
```

The focused campaign tooling suite currently has 37 passing unit tests,
including comment-aware menu parsing, separate kit/alternate resources,
unavailable choices, original aircraft decisions, negative DObj flag semantics
and the fixed model boundary.

The opt-in `build(..., qa_kits=True)` / `--qa-kits` experiment adds
`maps/_coop_uf_kits.gsc` only to clearly marked QA overlays. Default builds do
not contain this adapter. It clones the pinned original five active-family
weapon processors and `refill_ammo` into actor-local methods, preserving native
`giveweapon`, alternate registration, weapon switching and `giveStartAmmo`.
It does not swap global equipment CVars or copy another player's inventory.
The fixed QA host-plan fields require enable, authority marker, exact catalog
SHA, target map, nonempty fresh-world epoch, commit and all four canonical menu
values per manual slot. All requested choices are checked before precaching or
applying any kit. Automatic mode leaves the authored path intact; reviewed
exclusive-script maps are visibly blocked for this bounded prototype. These
QA CVars do not authenticate a production host: a future native API must accept
only the validated host roster, approved asset union and fresh-mission tickets.

`tools/qa_uf_kits.py` runs actual host/joiner processes on existing isolated
copies, supplies the labelled host plan through one `+exec` configuration and
reads native inventories/ammunition independently. Many `+set` arguments were
shown to exceed the original bounded command-line list; that launcher-fixture
failure is retained. The first real attachment attempt found host startup 240
approved models versus peer 234 and failed native validation on
`w_us_spw_binocular_world`. This is the still-open production asset-bootstrap
gap. For the isolated actor-kit proof only, the exact trusted roster's 21 media
models were supplied to both owned copies before `GAME_INIT`, using existing
QA cache hooks and unchanged strict native guards. No lobby or network resource
exchange is inferred from those local QA files.

With frozen protocol-9 Core `22a3d142…` and a 512 MiB hunk, Brecourt then
connected a real pair. Host inventory was Garand/Thompson/Colt/frag; remote
inventory was Carbine/Greaser/binoculars/mine. Actual attack input consumed
Garand clip 8→7 (stock 192) and remote Carbine clip 15→14 (stock 240). The
native checkpoint test exposed a genuine existing reset: after save/load and
real rejoin, host slot 1 instead held the host's Garand/Thompson/Colt/frag with
192 stock and clip 7. Slot 0 retained its own 192/7. The adapter's external
epoch receipts deliberately prevented reapplying kits or refilling restored
ammunition, so the runner reported **FAIL**. Native code must preserve each
restored remote's own weapon/ammo/slot data before saved-ghost disconnect and
restore it after `ClientConnect`/`ClientBegin`, suppressing host mirroring for
that restored slot. The earlier attempt also retained an original
`Ally_Names` script-watchdog error; it did not recur on the clobber-proof run,
and its bounded source loop was not disabled to obtain a pass.

Complete raw native before/after observations, saved checkpoint, exact executed
GSC/PK3s, runtime snapshots and logs are retained in
`run/uf-script-qa/history/kits-fire-pass-OWN-PS-checkpoint-clobber-1795287346623500980`.
The asset-bootstrap negative is in
`run/uf-script-qa/history/kit-bootstrap-missing-fail-1795286939001277722`.
Individual-kit checkpoint acceptance therefore remains open, alongside native
authenticated roster delivery and pre-registration asset bootstrap.

The subsequent immutable numeric-state candidate `2c9d17c7…` passed the same
real two-player **inventory/ammunition** regression. Before disconnecting the restored ghost, native
code captured slot 1's own weapon 13/viewmodel 102; after native connect/begin
it restored that numeric inventory. Host Garand 192 stock/clip 7 and remote
Carbine 240 stock/clip 14, all four inventory slots and all five native ammo
maps matched exactly after actual checkpoint load and rejoin. Movement checks
passed 202.3 units before and 181.3 units after loading, with stable observation
and clean shutdown. Full proof is retained in
`run/uf-script-qa/history/kits-ownPS-2c9d-PASS-1795288340884448186`.
This closes that targeted inventory/ammo clobber regression for the candidate;
production authenticated delivery/bootstrap and four-player retention remain
separate gates. The executable was original UO `c17e57c0…`, not the prepared
installer's LAA executable, with a requested QA hunk of 512 MiB.

The generated five-family processors and original refill function are now
audited for global gameplay effects during the build. Their only retained
world writes are `level.precache_mine = 1` and `level.precache_plane = 1`,
shared resource-union hints with no active readers in this pinned UF script
revision. Health, speed, faction, settings and `game[]` mutations are rejected
by the actor-clone audit. Debug printing reads a setting but changes no gameplay
state. No original weapon/ammo behavior is removed by this audit.

The durable kit runner also accepts `--players 4` with four different original
American roles and the exact 23-world/39-media resource union. Each actual
controller's native slot is read rather than inferred from its folder name.
It checks every native inventory/ammo map before and after checkpoint loading.
The MG and bazooka roles fire their original Thompson/BAR secondaries in this
inventory-retention probe; standing MG or launcher firing is not claimed.
The separate terrain-valid MG deployment test remains the deployment evidence.
The four existing owned test folders were reused; only the pinned YAP tree was
copied. Executable hashes and actual COFF LAA flags are recorded separately,
without claiming this raw 512 MiB gate represents the prepared 256 MiB preset.

The stricter follow-up found that the old inventory/ammo-only oracle omitted
the active selected weapon. In the two-player archive, remote inventory stayed
Carbine with stock 240/clip 14, but native active weapon changed 13→0 after
checkpoint load. In the four-role test, all inventories/ammo survived and
native reconnection arrived out of order 1→3→2, but Springfield 98→0 and BAR
5→0 lost their active selection. Fresh screenshots showed missing/cropped
first-person weapons and ammunition HUD for those peers. The historical raw
PASS reports remain preserved with supplemental **FAIL active selection**
audits; they must not be reported as complete checkpoint/kit acceptance.
Four-role evidence is retained in
`run/qa-cod1-four/history/four-role-ammo-PASS-activeweapon-FAIL-1795289399920232132`.
A later State15 run with native resources-only item registration on each peer
still lost Springfield selection, so XModel caching alone is not the cause.
The native observer is now recompiled from captured source each run and the
oracle requires active weapon, weapon name and viewmodel retention too; this
also fixes a retained stale-observer-binary/KeyError failure in the earlier QA
runner. Original script-watchdog failures remain visible and are not filtered
out to obtain a pass.

Native analysis identifies an actual Singleplayer assumption beyond source
`level.player` replacements: UO `self switchToWeapon` validates the actor's
owned bits in Game RVA `0x16fd0`, then calls `0xc600` **without an actor
argument**. That routine writes global local-engine `cg_weaponSelect` and
selection time through Game trap 8, with original alternate/run behavior.
Thus using it on a remote still changes the host's UI selection. Registration
table `0xaaec0` identifies the Game VM CVar `0x154780`; CGame registers the same
name at VM CVar `0x24aec0`. Native CGame `weapon <name-or-id>` at RVA
`0x342b0` resolves the definition and calls the normal selection routine
`0xb9f0`. Exact hashes, registration-table findings and assembly are retained
in `run/campaign-investigation/native-switch-selection-proof.json`.

An actor-targeted reliable selection bridge is therefore required for remote
kit processors. The receiver must use the normal local selection path only
after its own authoritative snapshot and owned weapon are available, with
session/world/owner/sequence validation. Checkpoint restoration also needs a
one-time selection seed before stale/default early user commands can erase the
restored active weapon. The isolated native State16 prototype now implements this bridge; authenticated
production asset/lobby delivery remains a separate requirement. No per-frame
forced selection, ammunition reset or silent removal of original switching
behavior was substituted. The source audit now explicitly lists
this native global method rather than implying source scans prove native
actor isolation. Reviewed UF mine/mount/binocular actor functions contain no
active `switchToWeapon` calls in this revision; they are not blanket-rewritten.

The opt-in GSC adapter now passes an immutable per-invocation owner context
(session parts, actual slot, spawn ticket, world and validated plan epoch)
through the five original loadout processors. Slot 0 retains the original
native switch; slots 1–3 commit canonical weapon names through the reviewed
fixed-field API, with sequence written last. Native acknowledgement must match
the entire request context. Missing API or stale ownership never falls back to
the global host switch. This remains `qa_kits=True`; default production overlays
do not apply this prototype or claim a lobby transport.

The stricter two-player gate passed with immutable Core `e9820fae…`:
`run/uf-script-qa/history/selection-e982-two-STRICT-PASS-1795292190790199867`.
Immediately before actual Save, host Garand 192/7 and remote Carbine 240/14
matched native host PS and each controller's own current CGame snapshot,
prediction and desired selection. Native load/rejoin retained them exactly;
real firing afterwards consumed another round on both controllers.

The four-role gate passed with immutable Core `ddc1a6d3…`:
`run/qa-cod1-four/history/four-selection-ddc-STRICT-PASS-1795292654322543580`.
Immediately before Save the active weapons were Thompson 270/25, Springfield
55/4, BAR 200/17 and Garand 192/7. All four kits, ammunition and active selections
survived actual native checkpoint loading. Each actual controller then fired
again; final separated screenshots show all four correct guns and ammo HUDs
(22/270, 3/55, 15/200 and 6/192). The initial overlapping-body checkpoint
screenshots remain preserved alongside the clean final views. Both runs used
raw original `c17e57c0…` executables, requested 512 MiB hunk, pinned YAP and an
explicit offline host-derived resource/item union. They establish the bounded
prototype regression, not prepared 256 MiB installation acceptance, arbitrary
kit combinations, automatic-kit behavior or campaign completion. The separate normal user-choice/stale-selection gate also passed with the same
`ddc1a6d3…` Core:
`run/uf-script-qa/history/selection-ddc-USERCHOICE-NEGATIVES-CP-PASS-1795292850597022590`.
After actual Carbine firing (240/14), the remote used the normal local
`weaponslot primaryb` command to hold its own Greaser. Host Garand stayed
unchanged. Replaying the authentic earlier Carbine selection as duplicate,
wrong-ticket, wrong-world and wrong-session packets could not undo this user
choice; wrong-world/session each increased native type-115 stale counts
(0→1→2). Independent fixed host requests with invalid ticket and session were
visibly REJECTED with fresh matching acknowledgements. The runner was corrected
for changed-only CVar publication: an unchanged REJECTED status need not be
logged again, but a fresh exact acknowledgement is required. The failed oracle
run remains archived; native errors were not suppressed.

Immediately before native Save, remote Greaser was 270/30 and the previously
fired Carbine remained 240/14. Actual load/rejoin retained both and the user's
held Greaser, with matching host PS and own CGame desired/predicted/current
snapshot names. Real firing afterwards yielded clean final Garand 6/192 and
Greaser 28/270 screenshots. This proves no prototype starting-kit refill or
forced return to the starting Carbine in this bounded scenario.

An additional pinned UF resource repair restores early `gear_US_load1`
registration only for Foy/Noville with optional models enabled. Original
`US_Airborne` still randomly attaches that model, while its original precache
branch explicitly skipped those maps. The source mod SHA is `4be5bb5c…` and
the original Main/pak0 XModel SHA is `a7fdc7e7…`. Random appearance selection
and late-registration validation remain intact; the next dense-map resource
gate must include this corrected overlay.

An independent read-only reference measurement is retained in
`run/uf-model-live-references`. The same fixed legal MG/Thompson/binocular/smoke
kit, selected policy, frozen `efbf03ec…` Core and 512 MiB hunk loaded all three
dense maps with clean shutdown. Three early-live snapshots found Noville
54/54/54 distinct referenced model IDs out of 252 reserved; Foy 51/51/51 out
of 250; Tropez 54/56/56 out of 253. The union therefore left 198, 199 and 197
CS entries unreferenced **at these samples**. This shows a reservation gap and
does not establish that any entry is safe to recycle. No allocator or model
index rebinding was implemented.

The observer now includes every in-use entity's body byte `+0x131` and seven
attachment bytes `+0x2a8`, active player state viewmodel DWORD `+0xd4`, and live
server/client DObj negative signed model flags. Native `G_InitGentity` RVA
`0x49fd0` sets entity in-use byte `+0x11c`; `G_FreeEntity` RVA `0x4a2c0`
zeroes the entire `0x2d0`-byte entity. `G_DObjUpdate` RVA `0x48900` resolves
body/attachment IDs and passes their negation into DObj model entries. Engine
`0x47b550` copies these signed flags to DObj `+0x3c`; positive flags are not
treated as CS model IDs. The native `setviewmodel` method RVA `0x178c0`
obtains `G_ModelIndex` and writes the result through entity client `+0x108`
to player state `+0xd4`; `ClientSpawn` preserves it. Server/client map reads
also validate the native 1024-slot DObj pool, model counts and ownership bits.
The exact native executable/DLL hashes, observer source, raw snapshots and
layout evidence are included with the run. These samples occur after native
registration; no hook captured the exact end-registration instant. Future
mission scripts, save/load persistence, transient events and retained network
snapshots still require lifetime analysis before index reuse can be considered.

Local evidence retained in this checkout (not committed game assets):

- Autonomous AI attack: `run/uf-ai-qa/history/1795267034608368616`, core `90c2e8eb…`.
- Brecourt read-only AI/LOS + complete MG asset regression: `run/uf-script-qa/history/1795273220045343268`, core `19470452…`; includes exact QA overlays, native helper source/binary, process memory observations, DLL snapshot and engine logs.
- Healthy Brecourt acquisition negative: `run/uf-script-qa/history/1795272974986328327`, core `19470452…`; no fabricated success.
- Seven-model-only join failure (`viewmodel_30cal_z`): `run/uf-script-qa/history/1795273147401913651` and `run/campaign-investigation/native-ai-readonly-before-13models.log`.
- Remote MG deployment/fire: `run/uf-script-qa/history/mg-deploy-fire-pass-1795274773072159180`, core `6cbb0f96…`, hunk512; includes exact QA scripts, native read-only observer, DLLs, logs, results and visually inspected fresh screenshots.
- MG invalid-oracle observations: `run/uf-script-qa/history/mg-native-ADS-invalid-oracle-1795274684232303073`; native complete ADS preceded a later downed transition.
- Native artillery cost/early-retry/180-second refill: `run/uf-script-qa/history/artillery-180s-pass-1795277774811289618`, including exact QA overlay, native observer/source, DLLs, missile observations, logs and final screenshots.
- Revised item/media-cache MG pass: `run/uf-script-qa/history/mg-itemcache-efbf-pass-1795276036315976145`.
- Final remote airstrike/aggregate pass: `run/uf-script-qa/history/airstrike-itemcache-final-pass-1795276234515570026`.
- Resource ranking/gates: `run/uf-resource-ranking`, `run/uf-resource-top8`, `run/uf-resource-rerun3b`; original-script comparisons `run/uf-resource-baseline-dense` and `run/uf-resource-baseline-foy`.
- Native cinematic/group-rejoin: `run/uf-script-qa/history/1795269816358340004`, core `8c5f8ead…`.
- Shared-stockpile negative control: `run/uf-negative-qa`, core `c24a9b1d…`; expected game-test failure and detector success.
- Earlier checkpoint failures: `run/uf-ai-qa/history/1795267698660576246` (reliable manager),
  `1795268049588563255` (clock rollback), `1795268480456367355` (early rejoin),
  `1795268830176372010` and `1795269357164988371` (remaining vehicle simulation).

Reproduce the UF mechanics probe against an owned installation containing the
pinned YAP integration. It makes isolated copies and adds test-only GSC there:

```sh
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-positive --port 29864
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-mines --port 29867 --map brecourt --mine-mechanics
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-ai --port 29869 --map brecourt --ai-remote
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-mg --port 29870 --map brecourt --mg-deployment \
  --runtime-dir /path/to/frozen/runtime
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-air --port 29871 --map brecourt --airstrike \
  --runtime-dir /path/to/frozen/runtime
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-arty --port 29872 --map brecourt --artillery \
  --runtime-dir /path/to/frozen/runtime
python3 tools/qa_campaign_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/uf-negative --port 29865 --mutant-host-stockpile
python3 tools/qa_mainline_probe.py --source /path/to/owned/test/source \
  --run /path/to/isolated/mainline --port 29866 --timeout 240
```

The probe does not yet demonstrate every MG family or simultaneous mounts,
specific artillery/airstrike victim damage, natural mission completion, or native
Windows behavior. These remain explicit gameplay acceptance work.

## Read-only startup-rule bootstrap audit (proposal, not wired)

The pinned UF package SHA-256 is
`b4f6bb7d03477d7e77e5150af4ca88eeb3dee30e0f715edfa1e2338d3e9d1cbe`;
SP Improved is
`25c1978fb48ec9324babed270be78d2f647e0d8a3e24c2415cd88aabb012e678`.
A comment-aware read-only scan of every `.gsc`, `.menu` and `.cfg` member in
these two packages records 160 UF literal CVar names/30 dynamic read sites and
52 SP Improved names/no dynamic read sites. Menu item blocks are parsed within
their own braces, including yes/no controls, rather than borrowing a following
item's choices. Raw original source is retained only in ignored investigation
output. Exact member hashes, original line numbers, readers/writers, active
menu domains and the proposed contract are in
`run/campaign-investigation/host-rule-bootstrap/{all,reviewed-proposal}.json`;
`collect.py` and `review.py` reproduce them without running the game. This is
an inventory of syntactically active package readers, not proof that every
function is reached on every map, nor a complete audit of inherited native
engine/base-package options.

The concrete shared startup inputs missing from a model/item-only bootstrap
are UF `sp_order` (0 chronological, 1 original), the two faction overrides
(menu `sp_fr`/`sp_en` values 0–13, mapped to the fixed `sp_ally`/`sp_axis`
strings), `sp_ammo` (0/1), and the legacy authored weapon mode
`sp_forceweapons` (0/1/2). Its current-family selector `sp_campaign` has active
menu choices 0 British, 1 Russian, 2 American, 3 German and 4 Italian.
The Polish case 5 exists in script but does not establish supported menu/assets.
Original menu evidence is `ui/options_mod.menu` items starting at lines 191,
491, 517, 559, 685 and 763. Individual manual/automatic kits remain the
separate owner-confirmed catalog/roster contract; these legacy global selectors
must never silently replace a remote's own role.

`sp_ammo` has a particularly important world effect: besides original
`maps/_UF_weapons.gsc:611/709` ammunition behavior, it changes original spawner
counts/wave handling in `maps/_UF_mod.gsc:1628` and later branches at
1733, 1803, 1885 and 2067. It therefore cannot become a private per-player
"extra ammo" toggle. `sp_history` has live readers at
`maps/_UF_loadout.gsc:1508` and `maps/_UF_mod.gsc:27`, setting
`level.mod_events` when equal to 1, although its menu item at
`ui/options_mod.menu:222` is commented out. Capture an explicit host semantic
value for compatibility; do not advertise that dormant control as an active UI.

Year, climate and resolved faction/nation are not independent menu options.
`maps/_UF_loadout.gsc:1099–1203` derives `sp_year` from the mission (1940–1945).
`maps/_UF_mod.gsc:1017–1077` derives `sp_climate` as none/winter/desert from
spawners and map identity. That script writes resolved faction/nation at
874–878 and retains them through `Save_Faction_Cvars` at 885–918.
`sp_loadgame` changes restoration/precache/loadout branches and is reset by
native save lifecycle scripts. Dynamic `sp_name_*`, `sp_nation_*`,
`sp_faction_*`, `*_head`, `*_head_type` and `*_body` readers also exist.
These are derived/saved state, not permission to transmit arbitrary CVar
names or asset strings. A host resource graph needs to bind and validate the
resolved results and checkpoint lifecycle; copying only six raw `sp_*`
selectors is insufficient to reproduce them safely.

Both packages read ordinary `g_gameskill` values 0–3 in mission branches;
UF additionally exposes native `difficultygimp` in its menu. This audit does
not establish that command's numeric mapping and does not guess one. The
shared difficulty contract must explicitly resolve that mapping before claiming
support. No active `ai_*` literal CVar readers or adjustable AI menu controls
were found in these two packages. The already recorded SP Improved bravery
changes and UF scripted actor parameters are pinned content, not newly
invented AI-setting fields. Existing YAP shared sprint/jump-shot rules remain
`player_sprintSpeedScale`, `player_sprintmult` and `bg_allowJumpShot`, with
their existing native ranges and acknowledgement semantics. FOV, input,
resolution, HUD/crosshair, weapon sprint presentation and local language
remain individual. The inspected YAP `g_enemyFireDist` reader controls
crosshair coloring, not enemy detection or firing distance. Some presentation
CVars are read by host mission scripts; that alone does not authorize forcing
them on every client's renderer.

Proposed native format: a capability/versioned, exact-length block of numbered
fixed fields with compile-time names and enum mappings, bound to variant,
pinned package/catalog, exact map, session, world generation, rules revision
and roster/resource digest. Validate every field and the ordered native
item/approved-media tables before `GAME_INIT`, stage them together, then commit
atomically and acknowledge that exact identity before readiness. Reject unknown,
duplicate, missing required or wrong-variant fields. Never concatenate received
console text, accept arbitrary CVar names, or partially apply a malformed block.
Keep derived world results and save ownership separate from user options.
`start`, `skip*`, `quick_*`, developer/cheat/testing flags and dynamic character
strings are excluded from this proposed transfer. SP Improved's script-only
`no_intro == "true"` at `maps/bastogne1.gsc:503` is another explicit scene-policy
input to review, not a silent authorized skip; stale peer development overrides
need detection. Native receive/apply/resource exchange and real phase-order
acceptance remain unimplemented by this audit. No Core, GSC or GUI code was
changed and no additional game instances were started for it.

## Cold-save preservation producer (source prototype; native gate pending)

The opt-in UF kit producer now requires a native inventory decision in addition
to its owner ticket. Native publishes `coop_inventory_<slot>_state` as WAIT,
FRESH or PRESERVED, with `coop_inventory_<slot>_identity` equal to the complete
current `session_a|session_b|session_c|slot|ticket|world` tuple. Publication is
WAIT first, identity next and final state last. Missing, malformed, mismatched
or changing publication is WAIT. The producer checks it again directly before
`takeallweapons`. Older runtimes lacking this explicit bridge conservatively
wait; their earlier immutable positive overlays remain archived unchanged.

PRESERVED is handled before current external plan/mode checks: it updates only
the external full-identity receipt and skips all kit application, giving,
refilling and actor-field changes. FRESH alone may apply the already validated
individual starting kit. No saved ticket counter is restored and no save
metadata revision is invented by this source change. The native selected-weapon
restore seed is independently derived from successful numeric inventory restore,
not from a stale external next-map kit plan. Native implementation and successful
host-slot-0 legacy-save handling belong to the separately reviewed Core change.

`tools/qa_uf_kits.py` now prepares a bounded two-player cross-map regression:
Brecourt A consumes actual ammunition and saves; fresh Pathfinder B applies
different legal primary/secondary choices and both real controllers fire; loading
the actual Save A must restore A's exact inventory/ammunition/active weapon and
own CGame selection, with PRESERVED proof and no additional
`COOP_UF_KIT_APPLIED` event. External B identity receipts are retained. An
always-FRESH/null preservation implementation therefore fails through refill or
an extra application; an always-PRESERVED implementation cannot pass fresh A/B
kit checks. The runner requires the actual recovered A map and a new native
world, because B's smaller clock must not be mistaken for a checkpoint rollback.
It accepts an explicit immutable Pathfinder native model ledger for offline media
preload before either process starts; this is not production asset exchange.

The new source has 41 focused tests passing, including stale world/owner
publication, preservation-before-plan ordering and the prohibition on Give/Apply
in the PRESERVED branch. Native GSC compilation and the actual A→B→Save-A
runtime gate have **not yet run** for this producer revision. Original special
script guards remain intact; no training/parachute/vehicle role is globally
unblocked to obtain a pass. The next game window must be coordinated with the
frozen installer/switch gates before using an immutable Core that implements the
bridge.

### Later native difficulty evidence corrects the skill-only proposal

After the source audit above, native menu handlers were verified and executed
through buffered real CLI commands in both original engines. Gimp is
`g_gameskill=0` plus `g_player_maxhealth=12000`; Easy is 0/1200,
Medium 1/600, Hard 2/300 and Fu 3/200. There is no skill 4. Setting the skill
alone left a deliberately distinct health value of 777 unchanged, so the
original audit's proposed 0–3 skill field cannot represent a complete native
difficulty preset or distinguish Gimp from Easy.

This is subsequent evidence, not a retroactive claim that the earlier package
scan was complete. Preserve its historical report and use a fixed five-preset
enum with an exact compile-time skill/health pair in the revised bootstrap
proposal. Commit both before `GAME_INIT`; reject contradictory/unknown pairs
rather than guessing from skill 0 or quietly mapping Gimp to Easy. Custom
skill/health combinations need separately versioned semantics. Evidence:
`run/native-difficulty-menu-probe-buffered/result.json` (PASS, both engines,
no Coop DLL and no mission started), the native difficulty registration/handler
disassemblies in `run/campaign-investigation/`, and the independently hashed
`host-rule-bootstrap/native-difficulty-addendum.json`. The bootstrap receiver
and gameplay acceptance are still separate work.

The first native State17 `8e0482f5…` cross-map attempts now compile and execute
the new producer on two real UF instances. Native A FRESH publication,
individual kits and consumed ammo/save passed. Actual fresh Pathfinder B
allocated new host/remote tickets (A 2/3 → B 4/5), applied the different legal
Thompson/Greaser primaries and both fired them (270/30 → 270/24 and 270/28).
The normal map-before-`coophost` argument order was retained. Native logs show
hosting already active at actual initial `GAME_INIT`; this does not prove the
separate true standalone-to-host warm-import branch.

The cold return to A **failed before preservation acceptance** with the real
engine error `G_LoadGame: client mis-match in savegame`. Native save ownership
was verified (`leases=1/0/0`), saved-intent 1/map Brecourt was observed and both
current identities correctly entered WAIT in world 4; no successful PRESERVED
state or no-refill outcome is claimed. Full immutable runtime, native saves,
sidecars, executed scripts/observer, logs and source are retained in
`run/uf-script-qa/history/preservation8e-COLD-A-native-client-mismatch-FAIL-1795295790571384576`.

Read-only disassembly narrows the failure: pinned UO Game DLL `9fd3665b…`,
string VA `0x20097788`, reference `0x20030b76`. The saved-client loop computes
`[0x20307f00] + savedIndex * 0x8330` and requires its field `+0x8228` to be
nonzero at `0x20030b69–74`, before deserializing that client. An index greater
than four has a different error branch; this is not evidence of a generic
client-count comparison. The failing index was not captured and no native
field was overwritten to bypass the guard. Evidence is in
`run/campaign-investigation/native-save-client-mismatch{.json,.disasm.txt}`.
Native connection-state reconstruction across cold loading remains an open
Core issue.

Two earlier failed QA-oracle runs are retained separately: GSC `println`
application messages were not emitted into this normal console log, so the
runner now counts actual `coop_qa_kit_applied_<slot>` receipt commits; another
run attempted B firing while original native `weapon_state=1` was still
raising the host weapon. The runner now waits for the original ready state 0
with a bounded timeout before sending actual attack input. These corrections
change observation timing only and do not disable script, model, ownership or
native save guards.

### State18 closes the reproduced cold-load/no-refill case

The exact case was repeated with immutable Core `dbda01bc…`, retaining the
same executed QA wrapper, generated host/peer PK3s and observer source as the
`8e0482f5…` native failure. Their hashes match byte-for-byte; the separately
rebuilt observer EXEs differ only in the COFF build timestamp and PE checksum,
with original binaries retained and normalized comparison recorded. The Core
repairs the lifetime of the existing reviewed saved-remote branch patch before
native saved-world deserialization; no additional serializer check was disabled.

The real two-player A→B→Save-A run **passed**. Actual Save A held Garand
192/7 and Carbine 240/14. Fresh Pathfinder B used different approved
Thompson/Greaser primaries, advanced current tickets 2/3→4/5, and both actual
controllers fired (remaining clips 27/28). Loading Save A retained current
tickets 4/5 in new world 4 and emitted exact native PRESERVED tuples for host
and guest. Original A inventory/ammunition and active weapons matched both host
PS and each controller's own CGame desired/predicted/current snapshot. Native
application receipts stayed exactly two per slot (A and B); the cold load
updated only external identity receipts, so no fresh kit or starting ammo was
reapplied. Actual post-load attacks produced visually verified final Garand
6/192 and Carbine 13/240 HUDs. Both games exited cleanly without engine errors.

The native log orders the existing patch rearm at 22:21:44.116, immediately
inside saved-intent-1 `GAME_INIT` before original deserialization; save ownership
verification follows at 22:21:44.125, host PRESERVED at 22:21:47.212, and guest
numeric restore/targeted selected-weapon seed/PRESERVED at 22:21:47.266.
Full immutable proof and the source/PK3 comparison are retained in
`run/uf-script-qa/history/preservation-dbda-COLD-A-NO-REFILL-STRICT-PASS-1795296164772889368`.
The earlier native failure remains its negative control. This closes that
specific cold cross-map inventory/refill regression for the prototype; it does
not certify every save lifetime, true standalone warm hosting, wrong-owner
restoration, arbitrary roles or campaign completion. The test still used
Wine/Xvfb, original non-LAA UO, requested 512 MiB hunk and explicit offline QA
item/media bootstrap, rather than the prepared 256 MiB installation path.

## Mission-interaction audit and next native action cases

A read-only effective-source audit reuses the campaign inventory and checks each
profile's installed original script layers against the current trigger overlay.
Raw pinned member hashes, predicate contexts, BSP entities and the exact
four-profile overlay footprint are retained under ignored
`run/campaign-investigation/mission-interactions/`. The scan includes host
Use/Touch/distance/activator predicates; it is a candidate inventory, not a
claim that every match blocks mandatory progress. In-memory transforms of all
four profiles accept the pinned revisions and preserve bytes outside each
reviewed function. Existing tests now explicitly preserve the normal Moody
handoff gate when testing the old fallback-only transform, making that missing
coverage visible rather than accidentally calling the fallback a full fix.

The concrete ordinary-action gap is Brecourt's **normal surviving-Moody**
explosive handoff. After objective 4 becomes active, `Moody_GetInjuredMan`
waits for host distance ≤100 at original CoD `maps/brecourt.gsc:836`,
SP Improved :845 and UF :866. Only then does the original NPC animation lead
to `got_explosives`, `Has_Explosives`, objective 4 done and bomb-trigger
activation. At the initial audit the overlay changed only
`explosives_objective_wait`, the separate failed-rescue/fallback branch. A
remote near the surviving Moody could not advance the normal gate while the
host remained away; the later scoped fix is described below.
The surrounding goal, dialogue and hand animation operate on Moody/lastnode;
there is no player camera/link or exclusive player inventory role to preserve
at this gate. The eligible-recipient replacement must reject dead/downed
participants using actual native eligibility,
not equate `is_player` or `isalive` with being able to act. Coop downed players
remain alive at health 1; excluding every health-1 player would incorrectly
reject a legitimately standing survivor and is not an accepted substitute.

Other concrete remaining host assumptions include Brecourt's door failsafe
(:1785 original/:1815 UF), which shoves only the host if blocking the door,
and Chateau's ordinary `doorBlocker` wait (:553), which waits only for the
host rather than any blocking player. UO `bastogne1_add::ammo_max_think`
(:509–515) consumes an actual ammo trigger but gives max MG30cal ammo to
`level.player`, regardless of the activator; its later ordinary Moody-follow
gate (:1025) measures only host proximity. The first-foxhole `player_save`
protection loop (:4102) also affects only the host, although its independent
objective-completion listener accepts an unfiltered trigger. These require
separate per-actor/collision review; they are not solved by the four existing
activator substitutions. UO Bastogne2's host-only walk/talk checks at
`bastogne2_event1to2:2110/2125` are candidates, but parallel scripted routes
exist, so this scan does not declare them proven unavoidable progression
blockers. UF's host-held next-map confirmation remains host world control,
not a reason to let every player independently change the mission.

The next actual native action tests are specified in `selected-cases.json`:

- **CoD 1 Pathfinder:** after normal approach, the joiner alone uses the
  legbag (`trigger_use` *27; object at 171,3857,4), then the unlocked beacon
  (object at −1391,5255,0). Original `objectives` :1222–1236 and
  `beacon_think` :1114–1135 already have unfiltered trigger waits. Require
  legbag removal/objective 1 done, then actual beacon model/sound change and
  objective 2 done. These are real mandatory actions, not merely loaded maps.
- **UO Bastogne1:** complete the original Jeep and barn approach normally,
  then let only the joiner enter the first required `player_save` foxhole
  brush while objective 3 is active. The actively threaded `alpha_killer`
  :2816–2823 emits `objective_3_complete`; `objectives_add` :309–319 then
  advances objective 3→4. The MG30cal pickup objective nearby is commented
  out and must not be reported as this mandatory objective.
- **SP Improved Brecourt:** follow the real successful cover/rescue path to
  normal Moody objective 4. Keep the host >100 units away; move an eligible
  joiner to ≤100. The current old overlay is the negative control; allowing
  the host into range is the original-behavior positive control. The scoped
  fix must produce the original handoff and real bomb unlock/objective 4
  event once, while the host remains outside. Dead/downed-only approaches
  must not advance it. The normal branch is proximity based; the Use prompt
  belongs to the distinct fallback branch.
- **UF Dendre1:** after the actual assault/APC prerequisites and `door2`
  opening, the joiner alone operates field-radio `trigger_use` *21 using its
  original HINT_ACTIVATE/Use interaction. `radio` :320–348 completes objective
  2, swaps the authored radio models, deletes the trigger and plays
  `uk_fire_mission`/`uk_arty_gtg`; normal sequential `main` proceeds to
  `mortars`. This authored radio is separate from the optional UF support
  weapon and does not justify overriding artillery costs or availability.

The inspected configs bind Use to F/`+activate`. Future automation must send
actual owner movement/look/`+activate`/`-activate` input and independently
observe the remote activator plus host outside the action zone, original
objective/notification and changed world objects. No direct `useBy`, fabricated
notify, actor teleport, objective setter or mission jump may stand in for that
proof. An earned pre-action checkpoint can reproduce the setup; loading it
alone never counts as success. At the time of that source audit none of these
four cases had been run. The bounded Brecourt follow-up below tests only the
original post-goal handoff; the normal rescue/navigation route and the other
three natural mission-action cases remain open.

### Brecourt normal handoff: scoped implementation and native evidence

The generated overlay now fixes the surviving-Moody gate in the pinned CoD1,
inherited UO, SP Improved and United Fronts script revisions. It factors the
original normal branch without changing Moody's goal, navigation, dialogue,
hand animation, fallback branch or shared explosives. The original inclusive
100-unit gate chooses the nearest eligible actual player; ties use slot order.
`maps/_coop_brecourt_handoff.gsc` checks the native actor API and current
session/slot/ticket/world identity. It rejects JOINER-local execution, stale
identities, waiting actors and native downed/dead actors. With no native API it
retains the original protagonist-only behavior. It never treats `isalive` or
health1 alone as permission. Source hashes and exact source-shape checks fail
closed before producing an overlay; original game assets are transformed
locally rather than committed to this repository.

`tools/qa_brecourt_handoff.py` is an explicit isolated scene, **not Brecourt
completion**. Its opt-in QA overlay models the already-arrived post-goal
precondition at the actual live Moody position. It removes scene Axis actors,
opens the original post-document clip and arranges both players once with the
existing native `cooplook` command. Thereafter the real Joiner approaches with
actual acknowledged usercmd input. It invokes the same original post-goal
function as production and observes the original `Has_Explosives`, objective4
builtin and bomb triggers restored to their original world positions. It does
not fabricate these success events or alter production NPC navigation. Full
original battle/rescue/navigation acceptance remains open.

Native CoD1 proofs use the immutable `cb7071e5c92f794a91634b63cc2afba87865ba35e267507bbe5c628512528a41`
Core, two actual Wine processes and 256 MiB hunk. The real Joiner alone triggered
the original handoff with the Host 391 units away; objective 4 completed and all
four original bomb triggers became active. An actual native damage/downing
counterexample kept the alive health 1 Joiner ineligible and the real handoff
gate live without completion for 3.5 native seconds. A separately arranged
standing health 1 player was accepted. The original Host action also completed.
Each PASS includes normal rendering, engine-log checks and both actual game
processes quitting successfully. The inspected Host/Joiner images show the
original scene and completed-objective HUD. These proofs do not cover native
Windows, complete missions, NPC navigation or combat AI.

Durable local evidence (ignored game assets remain outside source control):

- `run/qa-cod1-four/history/brecourt-cb7071-POSTGOAL-JOINER-PASS-1795300001531623044`
- `run/qa-cod1-four/history/brecourt-cb7071-ACTUAL-DOWNED-GATE-NEGATIVE-PASS-1795300080686952272`
- `run/qa-cod1-four/history/brecourt-cb7071-cod1-standing-one-hp-PASS-1795300110559756232`
- `run/qa-cod1-four/history/brecourt-cb7071-cod1-HOST-CONTROL-PASS-1795300434037251644`
- `run/campaign-investigation/brecourt-joiner-postgoal-contact.png`
- `run/campaign-investigation/brecourt-downed-gate-contact.png`

The same post-goal actual-Joiner action also passes in original UO and SP
Improved (256 MiB, actual pinned YAP loaded for SP Improved). Their archives
are `brecourt-cb7071-UO-POSTGOAL-JOINER-PASS-1795300695362383390` and
`brecourt-cb7071-SPI-POSTGOAL-JOINER-PASS-1795300814520113735` under the same
history directory. The UO fixture initially missed the original pre-goal
`cant_shoot` initialization: the original `can_shoot` tail correctly errored
when restoring an undefined sight-distance field. The fixture now runs that
original prerequisite, without changing production NPC behavior. This failed
run is retained as `brecourt-cb7071-UO-postgoal-cantshoot-prerequisite-FAIL-1795300636383239501`.
An earlier UO startup also rejected leftover UF-only renderer QA input names;
that failure is preserved, and unrelated QA renderer/deferred-model input
files are now quarantined before this normal-profile scene. Strict asset
validation remains enabled.

United Fronts also passes the same actual-Joiner post-goal action, with its
authored script revision and YAP, in
`brecourt-cb7071-UF-POSTGOAL-JOINER-PASS-1795300878060897947` under the same
history directory. This targeted raw-copy probe used 512 MiB, so it does not
establish the installer's 256 MiB production preset. All four profile proofs
use the same immutable native actor Core but individually generated and
archived source-derived overlays; the fixtures evolved as the missing UO
pre-goal prerequisite was identified. No complete Brecourt playthrough is
claimed for any profile.

Reproduction from the checkout uses `/usr/bin/python3 tools/qa_brecourt_handoff.py`
with `--source run/campaign-host --run run/qa-cod1-four --runtime-dir
run/actor-eligibility-prototype/cb7071e5c92f794a91634b63cc2afba87865ba35e267507bbe5c628512528a41`
and `--variant cod1|uo|sp_improved|united_fronts --scenario joiner-positive`.
The alternatives `standing-one-hp`, `downed-negative` and `host-control` were
tested on CoD1. `dead-boundary` remains a documented failing live-gate setup.
The runner modifies only owned QA copies and builds an explicit opt-in scene;
it is never a normal campaign launcher.

### Pathfinder shared Use and initial-equipment follow-up

The original `objectives` legbag and `beacon_think` routines contain no personal
weapon/ammo reward. They advance shared flags/objectives and delete/change the
original world objects. New pinned transformations capture the actual native
Use activator for these two waits and require the same current native actor
eligibility as the Brecourt gate. The separate first tutorial trigger, original
intro/camera and original shared effects remain unchanged. The higher-precedence
UF mission overlay retains the already-reviewed authored helmet-model repair.

The first actual CoD1 follow-up completed the original parachute without an
intro skip or actor/object arrangement. Read-only native observation matched
each player's active Game weapon with their own CGame desired/predicted/current
snapshot selection. It exposed a separate concrete equipment gap: after the
Host's four original grants, the remote retained only the earlier fallback
Thompson. Neither shared Use object is supposed to award these missing items.

The source fix now starts a scoped watcher after the original classic Host
detach. On CoD1/UO/SP Improved's exact classic revision it gives the original
`m1carbine`, `thompson`, `colt`, `fraggrenade` recipe only to a current FRESH
remote owner once, clearing only that owner's provisional fallback first to
restore the original empty-before-grant condition and weapon-slot order. It
waits without clearing/giving when the explicit native mission
selection capability is missing. A matching PRESERVED owner only updates its
external receipt, with no give/refill or active-weapon replacement. UF has a
different authored/individual recipe and never calls this classic adapter.
The fixed native request source is `pathfinder_initial`, epoch 0 and canonical
`m1carbine`, committed after the complete current session/slot/ticket/world
identity. Actual CoD1 integration now verifies the original primary M1 Carbine,
secondary Thompson, Colt and frag grenade slots, exact original unspent Host
stock/clip arrays, both active Game/own-CGame M1 selections and exact current
native acknowledgement. Clearing the remote did not change Host equipment.
The previous fallback-retained slot order is preserved as a partial earlier
proof, not accepted as the original recipe. A pre-grant checkpoint resumed through the
later earned grant needs separate event provenance; it is not covered by the
conservative PRESERVED skip policy.

There is **no Pathfinder Use PASS yet**. The natural-route probe stopped before
approaching because native keyboard-turn inputs produced no actual yaw. A
repeat verified focus on the owned peer's own Xvfb window and observed normal
unlinked Host PS, raw command angles0 and native input-frame milliseconds0.
Native `CL_AdjustAngles` at CoD1 `0x40a5b0` scales keyboard turn by that field
before writing engine view angles; the evidence is in
`run/campaign-investigation/native-cod1-keyboard-look.disasm.txt`. This is a
bounded observed keyboard-input failure, not a claim that mouse aiming fails.
The next probe uses XTest mouse motion confined to that owned Xvfb/window and
still requires actual own-CGame plus HostPS yaw and native objective evidence.

Both failed runs and exact sources/overlays are retained under
`run/qa-cod1-four/history/pathfinder22e-NATURAL-INTRO-ownCG-PASS-yaw-input-FAIL-1795301698666286073`
and `pathfinder22e-owned-focus-keyboard-look-frametime0-FAIL-1795301952502182565`
in the same history directory. The `PASS` word in the first archive labels
only the observed natural intro/own-CGame prerequisite; its overall result is
FAIL. No interaction, mission or campaign completion is claimed.

The native client-input clock correction has a real counterfactual: with
`dbf6b9c2e11a0135d393f1a8a9e9280cdc2dd75f900b4f6853c6839ce1d065c8`,
the same remote keyboard turn changes Host PS yaw29.998→120.718, raw owner
command angles and own predicted CGame yaw; its native input clock reads13ms.
The remote then genuinely walks about1,600units along the original route.
This is not a mouse-hardware claim. Direct XTest motion did not produce yaw
in that run. The route subsequently stopped because the existing250ms command
poll quantized the QA controller's180deg/s turn pulses into45degree steps;
the queued-key controller now scales the ordinary local turn speed instead.
That overall run remains FAIL, archived as
`pathfinder-dbf6-input-clock-counterfactual-PASS-steering-poll-quantization-FAIL-1795303760336724622`.

The separate actual post-grant checkpoint test restored the remote's normally
user-selected Colt and consumed ammunition exactly, with PRESERVED/no recipe
repeat. It nevertheless remains **FAIL**: Host owned pistol reserve changed
28→51. Read-only native slot mapping confirms Colt stock/clip index4, so this
cannot be dismissed as an unused raw-array word. Static native analysis shows
classic `ClientDisconnect` can drop a held weapon when a saved ghost still has
connected state2, and managed ghost cleanup invokes that original callback.
Actual pickup causation and the narrowly scoped cleanup correction are being
verified; no Host-ammo exception was added. The negative evidence is
`pathfinder-bac5739-remote-Colt-CP-exact-PASS-Host-stock4-FAIL-1795303251601764946`.
The complete original-recipe prerequisite is in
`pathfinder-bac5739-exactslots-ammo-ownCG-PASS-remote-keyboard-clock0-FAIL-1795302951051601090`.
All archives are under the same owned QA history directory. At that source
boundary UO/SP Improved's new initial-grant behavior and actual shared Use
still needed runtime checks; subsequent scoped results are recorded below.
Complete mission flow, native Windows and physical mouse input remain open.

The following CoD1 **equipment/checkpoint-only** run now passes completely:
`pathfinder7f19-nearHost-Colt-nativeCP-exact-MOUSE-KEYBOARD-PASS-1795304573891484772`.
It uses immutable `7f19ec02b05655cd3fbdc993ae664c11576a9d1ac66958a98bd741e665b56449`
with the original engine and 256 MiB hunk. The actual managed-ghost log records
numeric capture followed by native connected state2→1 before ordinary cleanup.
After real save/load and rejoin, Host pistol reserve28/clip7 remains exact;
the remote's normally selected Colt reserve28/consumed clip6, every inventory
slot and active Game/own-CGame selection remain exact. Give-count stays1 and
the current lifecycle receipt becomes PRESERVED/no give. The post-load world
item snapshot has no added items. Strict Host-ammo comparison remains enabled.

The same run separately exercises owned-window Win32 `SendInput` on both
actual processes: Host yaw29.998→65.528 and remote yaw122.333→136.549, with
matching own predicted CGame angles. Each target's actual foreground PID and
successful injected event are recorded. This proves the native injected
mouse path, **not physical mouse hardware**. It is independent of the keyboard
counterfactual. The inspected original-engine images show Host M1 Carbine and
remote Colt6/28 after the checkpoint in
`run/campaign-investigation/pathfinder7f19-postcheckpoint-hostM1-peerColt.png`.
Both processes render, pass strict log checks and quit successfully. Shared
legbag/beacon Use is explicitly not exercised in this accepted scope.

A subsequent genuine-input straight-line route stops at a solid map barrier
(remote Y1348.875); it does not disable collision or fabricate progress. The
preserved failure is `pathfinder7f19-natural-directline-worldbarrier-FAIL-1795305318751775284`.
The route controller is now following the pinned map's initial farm/road
pathnode corridor. The Host also walks the remote's actually traversed trail,
keeping the original automatic catch-up enabled while remaining outside each
final object's Use zone. These are ordinary input targets, not entity or
navigation-script changes. The complete natural route remains pending.

The isolated **actual remote legbag/beacon activation plus checkpoint** case
now passes in CoD1 under the same7f19 native snapshot:
`pathfinder7f19-ARRANGED-actualREMOTE-USE-bag-beacon-CP-PASS-1795306469849525361`.
Pre-action actor positions use the existing native debug setup at the two
original objects: Host1000units and remote300units. After setup, actual owner
movement/look/`+activate` is required; no `useBy`, injected trigger notification,
mission-flag setter, collision change or AI deletion substitutes for the action.
The preceding tutorial touch, route and full intro participation are explicitly
outside this acceptance scope.

Both original native Use events report actual actor1, with Host distances
1000.03 and999.997. The original legbag disappears, beacon changes to
`xmodel/eureka_beacon`, original objectives1/2 each complete once, and repeating
Use cannot repeat them. Every owner's inventory/ammo/active Game and own CGame
selection remains unchanged during the shared actions. Real remote M1 fire
consumes only its own ammunition; a subsequent normal Colt choice/fire and
actual save/load preserve both owners exactly, without recipe repeat or new
post-load items. Strict engine logs, final rendering, native QUIT and both
actual process exit codes pass. This remains an isolated action proof, not
natural navigation, a complete mission or campaign completion.

The first run passed these action assertions but correctly failed the generic
harness's262KiB evidence bound; its raw274,847byte report is retained as
`pathfinder7f19-actualUse-andCP-phases-PASS-evidence-limit-FAIL-1795306357078332936`.
The limit remains unchanged. The accepted repeat returns a bounded summary and
SHA256-binds its full native JSON sidecar; the sidecar hash was independently
checked against the final generic result. All action assertions and normal
screenshot/log/cleanup checks still execute. No generic PASS exception or
liveness bypass was introduced.

The inherited UO script/engine with actual YAP also passes the same arranged
remote Use and inventory/selection checkpoint scope, archived as
`pathfinder7f19-UO-ARRANGED-actualREMOTE-USE-numericCP-PASS-1795306804727853302`.
Actor1 operates both objects with Host1000.03/999.996 away; original goals
complete once and strict personal-ammo/selection and clean-exit checks pass.
These raw-copy UO checks use256 MiB and the original UO executable; they do not
establish an installed Windows/LAA/production-quality preset.

**Checkpoint pose is a newly observed open gate, separate from the numeric
inventory PASS.** After the CoD1 beacon save, Host position/look restore, but
the remote moves from saved(−1359.238,5227.633,0), yaw137.318 to initial map
spawn(−1052,−68,−191.872), yaw29.998 after reconnect. UO reproduces the same
position reset. The inspected post-load image independently shows the remote
back at the starting house; the full raw observations retain both owners'
positions and angles. No complete checkpoint-position acceptance is claimed.
`--require-pose-restore` adds a strict optional plain-unlinked-standing gate
(8world units/2degrees); numeric-only runs always record their pose difference
instead of silently treating it as restored. A map-start respawn cannot pass
the focused pose-oracle fixture. Native loaded-state capture/restore is being
traced before the saved ghost cleanup; no GSC teleport or re-give masks it.

The zero-health test remains a **failed live-gate test setup**, not a passing
death-lifecycle proof. An entity-only GSC health 0 write was observed as 600 on
the subsequent probe. The native command writing both entity/playerState did
produce health 0 and native INELIGIBLE, then WAIT as the original engine entered
mission failure and dropped remotes. That terminal lifecycle prevents the
proposed live-gate observation; its full evidence is retained in
`brecourt-cb7071-cod1-dead-boundary-FAIL-1795300128214990182` and
`brecourt-cb7071-cod1-native-zero-health-MISSIONFAIL-FAIL-1795300473460583871`
under the same history directory. No mission-failure guard was disabled.

Earlier filename/scene failures are also retained. Actual engine `path` output
showed a new QA PK3 shadowed by the older generated overlay; a subsequent real
`zz_` filename was not mounted because CoD1 reserves that prefix for its
`sp_` alias handling. That historical fixture updated the then-current owned generated
`zzzzz_codcoop_triggers.pk3`; its precedence defect is corrected below. Native comparator evidence and engine-aware
inventory ordering are separate from historical source-only inventories; no
general package renaming or authored-package reorder was applied.

The generic QA harness accepts targeted scenarios only through the explicit
Python callback API. It first proves real connection and advancing clocks,
requires bounded explicit scope/checks/evidence, and retains screenshot/log
checks, native QUIT and exit-code checks. Targeted scenarios cannot silently
skip requested checkpoint reloads. The ordinary CLI smoke path is unchanged.


### Generated mission overlay precedence correction (2026-11-22)

The canonical generated mission package is now `zzzz_coop_triggers.pk3` in
Main, uo, sp_improved and UnitedFronts. The required-content manifest, stager
and campaign QA tools agree on that name. This is a generated-package change;
authored packages and the native search comparator remain unchanged.

The preserved UF failure
`pathfinder7f19-UF-generated-variant-shadowed-mission-overlay-FAIL-1795307264124166898`
shows actual native `Current search path` placing `zzzz_coop_campaign.pk3`
before `zzzzz_codcoop_triggers.pk3`. Both contain `maps/pathfinder.gsc`, so the
variant's asset-only repair shadowed the mission compatibility code and QA
observer. Native comparison folds ASCII to uppercase: underscore sorts after
Z, so adding Z characters cannot establish the intended priority. At the
shared `ZZZZ_COOP_` prefix, the new mission name's T sorts after the variant
name's C. A ZIP-provider regression checks this exact overlapping entry under
the verified native comparator, including the previously failing order.

Owned QA clones quarantine only recognized old generated trigger packages
(`zzzzz_codcoop_triggers.pk3` and `zzzzz_coop_triggers.pk3`) before building.
Their original bytes remain in timestamped clone-local archives. Unrecognized
same-name packages cause a preflight error before any move. Production cleanup
is separately transactional and requires the prior installed runtime-lock
ownership; a modified or unowned package is never silently removed.

The read-only pose trace is preserved as
`pathfinder1805-loaded-pose-correct-before-disconnect-strict-postCP-pose-FAIL-1795307542640380149`.
Core SHA1805e8117c47e327b9c12fff021885621d03c76a613e1bb0fdd3ce37aef76ec7
reports the actual restored guest immediately before ghost disconnect:
origin(-1359.238159,5227.186035,0.002634), view(51.586304,137.312622,0),
plain pm_type0, health600, unlinked, matching lease1. The strict post-reconnect
pose assertion still fails. Thus deserialization has the correct saved pose;
the subsequent disconnect/connect lifecycle loses it. This is an observed
negative result, not a pose restoration implementation or acceptance claim.

The corrected UF arrangement now passes with two real Wine game processes:
`pathfinder7f19-UF-canonical-provider-ARRANGED-actualREMOTE-USE-PASS-1795307700843026510`
under `run/qa-cod1-four/history/`. Both native search-path reports show the
canonical mission overlay first and the variant overlay second. Actual remote
actor1 activates the original legbag and beacon; Host distances are1000.03 and
999.999. Original objectives1/2 complete once, the legbag is deleted, and the
beacon becomes `xmodel/eureka_beacon`. Shared actions leave both owners'
inventory, ammunition and active Game/own CGame selection unchanged. Subsequent
real remote fire consumes only its own clip. Both native screenshots render
normally (YAP visible), strict logs pass and both actual processes quit0.

This UF proof uses the unchanged7f19 Core snapshot, raw original UO executable,
YAP and512MiB harness setting. It does not certify the production256MiB preset,
checkpoint pose, individual UF starting-kit bootstrap, natural tutorial/route
or complete mission. The accepted screenshot contact is
`run/campaign-investigation/pathfinder-UF-canonical-provider-actual-use.png`.
The prior shadowed-layer failure and exact old packages remain archived.

### Plain-owner checkpoint pose: targeted native regression PASS

The previously observed position/look reset is now fixed for the tested plain
standing, healthy, unlinked owners by candidate Core
`4861e9a0464916726d3fb9a9d5f31dc3aa3fff44459c2bc63c25b92dfd006cfa`
(State20, loader85fc). The original negative trace above remains unchanged.
Two real-player tests with `--arranged-interactions --checkpoint
--require-pose-restore` pass for CoD1 and UO with YAP, using256MiB and the
existing isolated raw-copy installations:

- `pathfinder4861-CoD1-arrangedUse-strictPOSE-nativeCP-PASS-1795307830696259045`
- `pathfinder4861-UO-YAP-arrangedUse-strictPOSE-nativeCP-PASS-1795307912327709811`

Both full archives are under `run/qa-cod1-four/history/`. The command uses
`tools/qa_pathfinder_use.py --source run/campaign-host --run run/qa-cod1-four
--runtime-dir run/saved-pose-prototype --variant cod1 --port 29950 --timeout 180
--arranged-interactions --checkpoint --require-pose-restore`; the second test
changes only the variant to `uo`.

Both Host and remote position deltas and all three look-angle deltas are
exactly0 after actual save/load, reconnection and stable current snapshots.
CoD1 remote saved/restored position is(-1359.23816,5227.80859,-0.00423),
view(51.76758,137.26868,0); UO is(-1359.23572,5229.19434,-0.01952),
view(52.46521,138.55408,0). Actual own CGame current client1 and predicted
angles agree before/after. The inspected images retain the remote Colt6/28
at the beacon instead of returning to the initial house; Host remains M1.
Screenshot contacts are `run/campaign-investigation/pathfinder4861-strict-pose-CoD1.png`
and `run/campaign-investigation/pathfinder4861-strict-pose-UO.png`.

All earlier assertions remain active: actual remote bag/beacon Use with Host
outside512units, original objectives once, exact original initial slots/ammo,
real remote fire and later normal Colt selection/fire, both owners' consumed
ammunition/active Game and own CGame selection retained, no recipe repeat
(give_count1/PRESERVED), no added ghost Colt item, clean strict logs, final
rendering and native exit0 for both processes. The fix restores bounded numeric
plain pose after ClientBegin and applies view deltas only against a real current
owner command; it does not copy script, vehicle or entity pointers. Linked,
vehicle, scripted-camera, dead/downed and other exclusive-role restoration
remain separate acceptance work. Neither test is natural route or full mission
completion, native Windows testing or general campaign checkpoint acceptance.

### Damaged-owner checkpoint health: confirmed negative counterfactual

The added opt-in `--require-vitals-restore` preserves the same actual Use,
checkpoint, pose, inventory and selection checks, disables only remote
`coopgod`, then calls the existing native `coopkill 1 50` damage path before
saving. No direct health-memory setter or scripted damage substitute is used.
The read-only observer records both verified PS_HEALTH and GE_HEALTH (CoD1
PS+0xe4/entity+0x1d8; UO+0x10c/+0x1e0), independently of the QA convenience
state. The fixture requires a real nonfatal drop in both fields, plain standing
unlinked owners and unchanged Host health.

On immutable4861 CoD1 this correctly **FAILS**: the actual remote PS/entity
health drops600→550, remains550 in the pre-save native observation, but becomes
600/600 after actual checkpoint load and reconnect. Host stays600/600. Both
owners' position/look deltas remain0; health preservation is a distinct open
checkpoint gate. The full failed fixture, source/helper, original packages,
runtime, logs and numeric evidence are retained in
`run/qa-cod1-four/history/pathfinder4861-CoD1-nonfatalNativeDamage-strictCP-vitals-550to600-FAIL-1795308050024091614`.
The failure is reported before successful scenario completion; it is not a
clean-exit acceptance result. No health restoration workaround or Native guard
change is included in the QA producer. A loaded-PS-before-cleanup trace is the
next cause-isolation step; the current evidence alone does not distinguish
native save deserialization from ClientBegin resetting health.

The exact native cause boundary is now confirmed with the unchanged read-only
1805 trace Core. Archive
`pathfinder1805-preGhost-health550-postBegin600-nativeCP-vitals-FAIL-1795308167222866938`
under the same history directory records actual nonfatal damage550, saved
PS/entity550, and the pre-Capture/pre-Disconnect native log:
`01:42:25.683 pose: loaded ghost slot=1 lease=1 loaded_lease=1 world=3 pm=0 health=550 linked=0`.
After ClientConnect/ClientBegin the observer reads PS/entity600/600; Host remains
600/600. Thus native deserialization does retain saved health, and the subsequent
remote lifecycle loses it. The old diagnostic Core's known pose reset is also
recorded (5309units), explicitly not required in this health-isolation run.
Overall strict vitals result remains FAIL; no Native health fix is implied.

### Damaged plain-owner checkpoint health: targeted native regression PASS

Core `d982970ed3bac9ef70b4068a593b044ade6656f95105dfe1bb2f5956b469caf5`
(State21, exact snapshot `run/saved-vitals-native-prototype`, loader85fc)
passes the identical nonfatal-damage counterfactual for both CoD1 and UO+YAP.
The preceding failure/trace archives remain intact. Complete new archives under
`run/qa-cod1-four/history/` are:

- `pathfinderd982-CoD1-actualDamage50-strictPOSE-VITALS-nativeCP-PASS-1795308507691535724`
- `pathfinderd982-UO-YAP-actualDamage50-strictPOSE-VITALS-nativeCP-PASS-1795308585953522895`

Use the strict pose command above with runtime `run/saved-vitals-native-prototype`
and add `--require-vitals-restore`. The existing native damage command genuinely
reduces the remote from600 to550 before save; independent PS and entity reads
both remain550 after actual load/reconnect. Host stays600. Native capture and
restore logs also report health550/max600. Both owners' position and all look
angle deltas remain exactly0, with own CGame currentclient1 and predicted angles
matching. All earlier actual Use, precise personal inventory/ammunition, active
Game/own CGame weapon, recipe-once, ghost-item and strict log/render/exit checks
remain enabled and pass. The screenshot contacts
`run/campaign-investigation/pathfinderd982-strict-vitals-CoD1.png` and
`run/campaign-investigation/pathfinderd982-strict-vitals-UO.png` were inspected:
Host M1 remains at the bunker, remote Colt6/28 remains beside the beacon.

Both tests use256MiB isolated raw-copy Wine installations. This closes only the
shown healthy, unlinked, ordinary-owner checkpoint health/pose counterexample.
It does not establish linked/vehicle/cinematic/downed/dead restoration,
checkpoint correctness in all missions, full campaigns or native Windows.
The Native fix adds bounded owner/world-bound numeric vitals after ClientBegin;
no script, links, entity pointers or full playerState are copied by the fixture.

### Four saved owners versus later live state: native training PASS

`tools/qa_checkpoint_group.py` runs four actual CoD1 instances under the trusted
scenario API with immutable d982 and256MiB. The tightened accepted archive is
`run/qa-cod1-four/history/four-owner-d982-training-distinct-yaw-saved-not-latest-pose-vitals-nativeCP-PASS-1795309048301166085`.
Original training scripts run; no forced weapons, player teleport or objective
completion substitutes for the fixture. Actual movement separates all four
owners by at least24units, and real look input establishes distinct yaw
[-58.3374,-13.24402,32.74475,79.99695]. Native damage50/100/150 produces
PS/entity health[600,550,500,450], with Host unchanged and all owners ordinary,
alive and unlinked.

After the actual SVG and ownership sidecar are written, every owner genuinely
moves and turns again. Guest2 takes another10 native damage, reaching490.
Loading the SVG restores its saved500 rather than current490; all owners'
saved positions and look angles return with measured deltas0. Personal weapon
slots, stock/clip arrays and active selection match their own saved seats.
Every local current CGame snapshot has its true client0..3, saved snapshot and
predicted positions and saved predicted look. No fresh tickets are issued;
all four native inventory lifecycle receipts are PRESERVED. All four owners
then move through actual input, command clocks and snapshots remain live,
strict logs pass and all four actual processes quit0. Training is naturally
unarmed here, so this proves no armed-fire or four-role weapon-selection case.
The earlier numeric pass with coincident yaw0/2 is separately retained as
`four-owner-d982-training-saved-not-latest-pose-vitals-nativeCP-PASS-1795308946013610840`;
the tightened fixture explicitly rejects insufficient pairwise yaw separation.

The focused oracle rejects swapped owner records, fresh/default health,
post-save current positions and a wrong local snapshot client. Full raw native
JSON is separately SHA-bound to the bounded scenario summary. This is a
four-owner checkpoint isolation proof in the starting training area, not
training completion or a campaign-wide checkpoint claim.

### Actual downed-owner checkpoint: confirmed negative gate

`tools/qa_checkpoint_downed.py` uses two actual training instances and d982.
With Host alive, native `coopgod 1 0` then `coopkill 1 100000` enters the genuine
Core downed lifecycle: downed=true, PS/entity health1, native prone flag1 and
actor INELIGIBLE. This is explicitly not an inference from health1; an ordinary
standing1HP owner is a different valid state. Only Host camera/position is
arranged96units from the actual guest for the visible-body observation; guest
body and mission scripts are not teleported or rewritten.

Actual SVG save/load and real peer reconnection lose the downed state:
downed=false, PS/entity600, prone flag0, actor ELIGIBLE. Host remains alive.
The strict downed assertion correctly fails, so the normal Host three-second
Use revive phase is not attempted or claimed. Both the actual native state
records and inspected screenshots show the prone guest/body and YOU ARE DOWN
before load, then a standing body/full health afterward. Evidence is retained
in `run/qa-cod1-four/history/downed-owner-d982-training-actuallethal-save-load-lostflag-FAIL-1795309478092150380`,
including the original SVG and ownership sidecar. The inspected before/after
contact is `run/campaign-investigation/downed-d982-before-after-nativeCP.png`.
This separate negative does not invalidate the explicitly ordinary healthy
four-owner restoration proof, but prevents general downed checkpoint acceptance.
No fixture writes S.downed or health memory and no Core fix is included here.

### Actual downed-owner checkpoint and normal revive: native regression PASS

Candidate Core `fc01f8d89702af7bbf47240a0f01b49e3001adcc9b3468b567214104509e1905`
(State22, exact snapshot `run/saved-role-prototype`, loader85fc) passes the
same genuine lethal-damage/save/load counterfactual for CoD1 and UO+YAP:

- `downed-owner-fc01-CoD1-actuallethal-nativeCP-HP1-prone-normalUseRevive-PASS-1795310281883047058`
- `downed-owner-fc01-UO-YAP-actuallethal-nativeCP-HP1-prone-normalUseRevive-PASS-1795310338602983641`

Both full archives are under `run/qa-cod1-four/history/`, including the exact
native SVG and V2 ownership sidecar, frozen runtime/helper/source, logs and
screenshots. Run `tools/qa_checkpoint_downed.py --source run/campaign-host
--run run/qa-cod1-four --runtime-dir run/saved-role-prototype --variant cod1
--port 29950 --timeout 180`, changing variant to `uo` for the YAP case.

Actual downed state remains true after reconnect, with PS/entity health1,
prone bit1 and actor INELIGIBLE. Both owners' saved position/look deltas are0;
the actual guest current CGame snapshot client1, predicted position and look
agree with its saved owner. Personal equipment remains unchanged. The Host
then uses the normal actual `+activate` input at the fixture's64unit camera
arrangement; native logs show one, two and three seconds of revive followed by
the original revival. Observed result is downed=false, PS/entity300, prone0,
actor ELIGIBLE. Native body images remain prone before and after load, then
stand after revival; the guest has YOU ARE DOWN and its low camera before and
after load, then its ordinary camera afterward. Inspected contacts are
`run/campaign-investigation/downed-fc01-CoD1-restored-and-revived.png` and
`run/campaign-investigation/downed-fc01-UO-restored-and-revived.png`.

Both real processes per test render, pass strict logs and quit0. UO retains the
explicit prone bit rather than copying every transient movement flag (observed
saved8193→restored1). The explicit saved-role metadata distinguishes genuine
Downed from a valid standing Alive owner with1HP; no role is inferred from
health alone. Standing1HP and Host-down checkpoints are still separate next
counterfactuals. These256MiB raw-copy Wine tests cover this guest-down scenario
in training, not linked roles, campaign completion or native Windows.

### Host-down and standing Alive1HP: separate native counterfactuals PASS

The same immutablefc01 Core passes both additional modes of
`tools/qa_checkpoint_downed.py` for CoD1 and UO+YAP. Add `--mode host-down` or
`--mode standing-one-hp` to the command above. All four archives under
`run/qa-cod1-four/history/` preserve the original native SVG and V2 sidecar:

- `role-fc01-CoD1-actualHOSTdown-nativeCP-GUESTnormalUseRevive-PASS-1795310559443487904`
- `role-fc01-UO-YAP-actualHOSTdown-nativeCP-GUESTnormalUseRevive-PASS-1795310661000967671`
- `role-fc01-CoD1-standingALIVE1HP-native599damage-nativeCP-normalinput-PASS-1795310600299534519`
- `role-fc01-UO-YAP-standingALIVE1HP-native599damage-nativeCP-normalinput-PASS-1795310716483178300`

For Host-down, genuine native lethal damage acts on slot0 while the real guest
is alive. The native SVG load preserves Host Downed=true, PS/entity1, prone1,
actor INELIGIBLE and the saved own Host current-CGame camera. The real guest
rejoins its reserved saved seat. Both owners' saved pose deltas are0; the guest
then holds actual Use, native progress reaches one/two/three seconds, and Host
revives to PS/entity300, Downed=false, prone0, actor ELIGIBLE. Inspected contacts
`run/campaign-investigation/hostdown-fc01-CoD1-restored-and-revived.png` and
`run/campaign-investigation/hostdown-fc01-UO-restored-and-revived.png` show the
Host's low downed camera and prone body before/after load, then normal standing
body/camera after the guest's revival.

For standing Alive1HP, actual native damage599 reduces an initially observed
600HP guest to1HP without entering Downed. After actual save/load/rejoin it
remains Downed=false, PS/entity1, posture bits0 and actor ELIGIBLE. The saved
pose/current own CG camera match with0 deltas. Actual backward input then moves
the owner while it remains Alive1HP/ELIGIBLE (observed moving flag64, no posture
bits). The inspected contact
`run/campaign-investigation/standing1HP-fc01-CoD1-UO-afterCP-and-input.png` shows
standing bodies and normal guest cameras with the low health bar. These
unarmed training cases do not claim weapon-fire coverage.

All four tests keep personal inventory checks, original mission scripts,
strict logs, rendering and actual exit0 for both processes. Only the observer's
camera/position is arranged; the damaged target is not teleported. The pure
role oracle explicitly distinguishes Alive1HP from Downed1HP and rejects wrong
posture, health resets or eligibility. The first CoD1 Host-down execution used
an earlier boolean posture check; its actual recorded prone bit1 also satisfies
the tightened explicit-prone oracle. Future runs archive the producer bytes
captured at startup and their SHA so later source edits cannot replace the
executed producer snapshot. No Core edits or health/role-memory setters are
performed by these fixtures. This closes the shown ordinary-Alive and genuine
Host/guest-Downed distinction in training; exclusive linked/vehicle/cinematic
roles, complete missions/campaigns and native Windows remain separate gates.

### Mixed four-owner Alive1HP/Downed1HP checkpoint: new look negative

The `--mixed-roles` mode of `tools/qa_checkpoint_group.py` uses immutablefc01,
four real CoD1 training instances and256MiB. Initial actual input separates four
positions and look directions. Native damage produces HostAlive600,
guest1Alive1 (599damage), guest2Downed1 (genuine lethal damage) and guest3Alive450.
The actual native ownership sidecar is read-only decoded using the pinned
Win32 C++ layout (224bytes, roles offset216, Owner stride16), not a proposed
wire serialization. It binds the SVG SHA and saved slots0..3 roles[1,1,2,1],
remote leases[1,2,3]. Focused fixtures reject V1/wrong size, wrong SVG hash,
missing leases and swapped Alive1HP/Downed1HP state/eligibility.

After the actual SVG save, healthy owners move and every owner looks elsewhere;
guest3 takes another10damage to440. The real load/rejoin correctly restores
all four saved positions and health[600,1,1,450], including the explicit
Alive/Downed distinction at identical1HP. However the strict complete scenario
**FAILS** on guest2 look: saved yaw32.74475, changed live yaw10.24475,
after-load own Game/own current CG yaw2.99927 (29.74548degrees off). Native
log `02:30:31.419 pose: restored own view slot=2 command=37250 view=0.000000,32.744751,0.000000`
shows the initial restoration, followed by the later discrepancy. The other
three owners' position and look deltas are0. Recorded final slot2 raw command
angles and local CL angles are[0,0,0], with no left/strafe held; earlier saved
CL yaw is114.74998 and changed-after-save CL yaw92.24998.

Full four-process evidence, producer/helper, logs, runtime, exact native SVG and
V2 sidecar are preserved in
`run/qa-cod1-four/history/mixed-four-role-fc01-training-rolefile-1121-PASS-downedYaw29deg-FAIL-1795311078160280035`.
The suffix's role-file PASS is only that narrow field-mapping observation;
overall scenario result is FAIL. Root cause of the later view change remains
open. The proposed third-peer3 normal Use revival with Host outside80units is
not attempted after this failure, and no four-role mixed acceptance is claimed.
The producer preserves the failure rather than re-aiming the guest or waiving
the saved-look requirement. No Core edits are included in this investigation.

The identical mixed fixture remains an overall **FAIL** on merged State23 Core
`9c2e888156ceac4c7db95d89d88e4abac22e114ceacba133ec7ef2aa9e2ddff5`
(exact `run/view-basis-prototype`, loader85fc). The new current-owned-selection
ACK/raw-command barrier does execute: native log02:36:15.603 reports saved
slot2 view32.744751 restored with raw[0,0,0], seed1, after its own native CGame
weapon command acknowledgment. Yet final authoritative and ownCG yaw is again
2.99927,29.74548degrees from saved32.74475. The other three saved views,
all four positions and actual mixed health/role mapping are correct. Full
four-process runtime/source/helper/native SVG/V2 evidence is archived as
`run/qa-cod1-four/history/mixed-four-role-9c2e-ACKbasisguard-proneYaw29deg-FAIL-1795311435403367076`.
Third-peer revival remains unattempted after the strict pose failure.

The repeated final angle is approximately the initial native map facing
−82.00195 plus85degrees, even with the final raw/CL basis0. This is a concrete
numerical lead toward a native prone-facing clamp, **not a proven cause or
implemented fix**. Existing field notes list the bounded numeric proneDirection,
proneDirectionPitch and proneTorsoPitch at CoD1 PS+0x350/+0x354/+0x358 and UO
+0x58c/+0x590/+0x594. They require native call-path verification and actual
before/after observation before any restoration change. No field restoration,
extra re-aim or timing waiver is added by the QA producer.

A read-only exact9c2e mixed-four repeat now directly observes the three mapped
prone fields on authoritative Host PSslot2 and the actual owner's CURRENT CG
snapshot/predicted PS. Saved host triplet is[31.39343,359.98242,359.98242],
view yaw31.39343. After live post-save look it is
[31.39343,359.98242,-0.09338], view9.16260. After load/rejoin it becomes
[-76.94196,-0.18677,-0.10986], view2.99927. The actual guest current snapshot
and predicted triplets agree with the Host PS in each phase. The observer's
host ownCGclient0 or remote frozen localGamePS0 fields are not mistaken for
actual owner2; only HostPS2 and owner2's current/predicted CG are compared.
Saved HostPS delta yaw50608 becomes66082; final actual raw command and local
CL yaw are0. This demonstrates a lost saved numeric prone basis, without
asserting the exact clamp call-path or restoring any fields.

The full expected failed trace is preserved as
`run/qa-cod1-four/history/mixed-four-role-9c2e-READONLY-pronebasis-saved32-to-Beginminus82-FAIL-1795311603484718866`.
The informal filename is approximate; exact saved31.39343 and restored
−76.94196 are in the native JSON. Observer changes only read the mapped triplets
and raw delta angles; no Core, GSC, gameplay branch or assertion was changed.
The strict saved-look failure still prevents third-peer revival acceptance.

### Mixed four-owner saved prone basis and third-peer revive: native PASS

Immutable State24 Core
`6bac8ba85474835f26790a7154ec5efb23fd9d8b7dce4588b4ee8aa2bf3c2e7c`
(`run/prone-basis-state24`, loader85fc) passes the unchanged strict mixed-four
counterfactual for both CoD1 and UO+YAP. Run
`tools/qa_checkpoint_group.py --source run/campaign-host --run run/qa-cod1-four
--runtime-dir run/prone-basis-state24 --variant cod1 --mixed-roles --port 29950
--timeout 180`, changing variant to `uo` for the second case. The UO addition is
only engine/folder selection; all per-owner assertions remain identical.

Full four-process archives under `run/qa-cod1-four/history/` are:

- `mixed-four-role-State24-CoD1-proneBasis-strictsavedPose-thirdPeerRevive-PASS-1795312133933698964`
- `mixed-four-role-State24-UO-YAP-proneBasis-strictsavedPose-thirdPeerRevive-PASS-1795312273472664884`

Both native RoleV2 files bind the actual SVG and map slots0..3 to[1,1,2,1].
Health[600,1,1,450] restores exactly after post-save changes (guest3 had reached
440). The two1HP guests retain distinct Alive/Downed state and actor
ELIGIBLE/INELIGIBLE. Every saved position and all view angles have measured
restore deltas0, with real own current CG clients0..3, saved snapshot/predicted
positions and camera angles correct. Saved/restored downed guest2 basis agrees
on HostPS and actual own CURRENT/predictedCG: CoD1
[31.66260,359.98334,359.98334], UO[34.18396,0,0]. Old9c2e/fc01 negatives remain
preserved; no re-aim or saved-look tolerance waiver replaces the failed check.

Only after these strict gates, an explicit post-load observer arrangement puts
Host1000units from downed guest2 and peer3at64. The measured UO Host distance
is1014.01, still outside the native80unit revive radius. Actual peer3 Use
progresses through native one/two/three-second logs and revives guest2to300.
All four then move through actual input. Training is naturally unarmed; there
is no armed-fire claim. All four command clocks/snapshots remain live, strict
logs pass, screenshots render and all four actual processes quit0 per test.

Inspected restored-before-revive contacts are
`run/campaign-investigation/mixed-four-State24-CoD1-restored-before-revive.png`
and `run/campaign-investigation/mixed-four-State24-UO-restored-before-revive.png`.
They show the standing Alive1HP guest separately from the prone Downed1HP body
and low downed camera. These are256MiB isolated raw-copy Wine tests in original
training, not mission/campaign completion or native Windows acceptance.
State24 captures the three bounded numeric prone fields only from an already
native-prone Downed source, then restores them after native prone entry. The
immediate Downed-before-native-prone save boundary is a separate untested case;
queued genuine damage+save commands can target it, but actual saved non-prone
flags must first be observed rather than inferred or forced by the fixture.

### Immediate genuine Downed+save: non-prone source boundary not reproduced

`qa_checkpoint_downed.py --mode guest-down --immediate-save` queues actual
native commands together: `coopgod 1 0`, `coopkill 1 100000`, then `savegame`.
Only genuine owner movement/look before damage establishes a non-default saved
facing; no role/health/posture fields are written by the fixture. The QA-only
read-only Core `f10d9f8658946ca1f77c218fdf2c025f316b406c8ffa490e0ae9706da1974133`
(`run/save-boundary-observer`, effective State24 behavior) logs actual PS fields
at native save file open AND close. The fixture requires both phases to record
RoleDowned2/health1 with prone bit0 before it can claim this source boundary.
A focused parser fixture rejects missing phases, wrong role/owner or a prone
bit present at either phase.

The actual CoD1 attempt does **not reproduce** that boundary. Genuine Downed
entry occurs02:55:14.742; native save open and close both occur02:55:14.789,
47ms later. Both source observations already contain role2, health1, flags1,
view31.843872 and matching native prone direction31.843872. The scenario
correctly fails its boundary prerequisite and does not proceed to load or claim
acceptance. A UO repeat is not run because the required CoD1 source condition
was not established. Exact native SVG, V2 sidecar, hashes, observer/runtime,
producer and trace are retained in
`run/qa-cod1-four/history/immediate-save-f10d-CoD1-queued-native-damage-save-sourceALREADYprone-NOTREPRODUCED-1795312530513939384`.
This is a failed fixture reproduction, not evidence of a new checkpoint defect.
The Downed-before-native-prone save boundary remains explicitly open unless a
legitimate reproducible path and actual source-field proof are established.

### Center-banner localization: native encoding identified, fix not yet applied

The actual mixed-role UO images expose red `UNLOCALIZED(YOU ARE DOWN)`.
Read-only native investigation confirms that both engines' `cp` command routes
through native localize-message (CoD1cgame300207a9→3000f200→CGtrap0x3a→engine
4027db→49f270; UOcgame30028046→30010b40→CGtrap0x3a→402c6e→4a3e50).
The translator starts with key lookup enabled. Byte0x14 enables localized-key
segments;0x15 marks following literal text;0x16 affects formatting. Raw English
Core cp strings are therefore incorrectly treated as keys. Global warning
suppression is neither needed nor proposed. A literal0x15 prefix alone would
remove the wrapper while leaving English and does not satisfy the full DE/EN
requirement.

The read-only scope proposal and exact PE evidence are in
`run/banner-localization-re/FINDINGS.md`. It recommends owned native CODCOOP
string keys with deterministic, reviewed EN/DE local-resource variants, so
language resolves on each client and no Host-language inheritance is introduced.
The current German installation deliberately aliases German LANG_ENGLISH
resources under localizedstrings/english (verified native training assets and
installer contract); merely adding LANG_GERMAN is insufficient. A tiny generated
Main/localized_english_codcoop_ui.pk3 with two explicitly approved locale hashes
fits the existing known-localization fingerprint policy, provided normal
ownership, installation, repair and rollback are integrated. It must not be
misattributed to the original Ready archive. All four profiles inherit Main.

No Core or resource-pack fix was applied during this investigation. Actual DE/EN
mixed-client native rendering, warning-free missing-key checks, equal approved
locale gameplay fingerprints and modified-file rejection remain acceptance
work. The save-role/mechanics PASSs above do not imply localization acceptance.

### Initial unpublished banner assets (superseded after native visual review)

`tools/build_coop_localization.py` now deterministically generates the asset
half only. English is the default. Both EN and DE write the same installed
path `Main/localized_english_codcoop_ui.pk3`, containing exactly one owned
`localizedstrings/english/codcoop.str`. It uses native VERSION1/LANG_ENGLISH,
Latin1 bytes, CRLF, fixed2000 timestamps and ZIP_STORED; no stock assets are
copied. Files are generated explicitly with `--language en|de --output PATH`.

Reviewed generated package identities are:

- EN:1034bytes, SHA256 `1ee330032dbf555f5aeeaf18d7fe0a0613e8ee2c3ed1a491ba7665c0b1796ab6`.
- DE:1158bytes, SHA256 `5c3dfe67c21b0ce5bc1005529740ade44d762f7cff3dafaa73a2321222817982`.

These initial hashes were registered at that stage; the current manifest now
uses only the later line37-safe replacements below. Tests
verify identical native key/template domains, deterministic bytes/metadata,
English default, proper German single-byte glyphs, and only the expected STR
entry. Equal reviewed EN/DE packages yield equal gameplay fingerprints across
all four profiles; a modified PK3 containing an extra GSC is not exempt and
yields different fingerprints.

The exact CODCOOP keys are DOWNED_TITLE, DOWNED_HINT, OTHER_DOWNED,
OTHER_DOWNED_HINT, REVIVED_SELF, REVIVED_OTHER, BEING_REVIVED, REVIVING_PLAYER,
CATCHUP and DISCONNECTED. Only OTHER_DOWNED, REVIVED_OTHER, REVIVING_PLAYER and
DISCONNECTED have one native `%s` argument, for a trusted decimal player1..4.
Colors/newline/progress are separate literal segments. In particular, the
player-number literal must end before a following newline/progress literal;
otherwise native `%s` substitution can insert that suffix inside the sentence.
An other-player-down wire message is the segment sequence:
literal `^1`, key CODCOOP_OTHER_DOWNED, literal `3`, literal `^7\\n`, key
CODCOOP_OTHER_DOWNED_HINT. Each key segment starts byte0x14; EACH literal
segment, including consecutive literals, starts0x15. C++ hex escapes must be
bounded by adjacent literals or explicit chars.

No Core encoding, installer/backend/stager integration, full payload build or
native-render acceptance is included in this asset milestone. The new file is
not yet required/installed automatically and is not misattributed to Ready.zip.
Generated manual QA banks live at `run/banner-localization-assets/{en,de}/Main/`.
CoD1/UO actual key lookup and mixed-local-UI EN/DE rendering remain next steps
with the parent's encoded Core candidate. Those manual asset checks must be
labelled separately from real installer language-switch/repair acceptance.

### Native UI language QA preparation and actual mixed-banner acceptance

`qa_coop.py --ui-languages de,en` explicitly selects local banner banks in
Host,join1,... folder order; the list must have exactly the actual player count
of en/de entries. Raw QA defaults to all EN on every preparation, including
reused copies. Generation occurs only inside marked owned QA clones after copy
and before launch. The selected reviewed bank is kept if unchanged; changing a
reviewed EN/DE bank archives its original bytes first. Unknown banks or symlink
escapes fail. Provenance records language, bytes/hash and
OWNED_GENERATED_QA_LOCALE_BANK_ONLY, explicitly not installer-language proof.
The parent's pre-change motion-run producer was preserved before editing at
`run/motion-scope-state24/executed_qa_coop_before_locale.py`, SHA256
`12a4b1d41d179c00eaedbb53c33f92a70730a8c0ebe97cb9972c8e06c47d4243`.

The first two actual CoD1 mixed-UI runs did resolve keys and `%s` arguments
correctly, but native image review exposed **visual failure**: German hints
were clipped. Native CoD1 cgame3000f3f7 and UO30010d37 cap each line buffer at
40 raw bytes; the renderer then skips the remaining source line instead of
wrapping it. Those initial archives retain their original narrow lookup PASS
and an additional post-run-visual-review.json marking complete banner visual
acceptance FAIL:
`banner-eea-CoD1-DEHost-ENpeer-down-progress-revived-PASS-1795313783370651456`
and `banner-eea-CoD1-ENHost-DEpeer-down-progress-revived-PASS-1795313925312350042`.
No native line-limit patch or warning suppression was introduced.

Owned EN/DE messages now validate each key and actual player1..4 substitution
at **at most37 Latin1 bytes**, allowing the wire color-prefix budget below the
native40-byte cap. German hints are now the complete native-safe
"Mitspieler können dich wiederbeleben" and
"Komm näher und halte Benutzen 3 s". Catch-up messages were shortened in both
languages as well. The only CURRENT approved package identities are:

- EN1029bytes, SHA256 `bea6ef3a24f586631569408f51efc3f9d857ee948951fd4a8b4ef3ef909c96c2`.
- DE1107bytes, SHA256 `908ce0bdfdd78a95a736b23de87b56c19e72be5256f7db3fb269ec7618659741`.

Old clipped bank hashes are not in the current manifest. Their exact owned QA
bytes remain archived; only those exact historical generated banks were
quarantined before the new tests. Unknown assets are never treated as retired
owned locale banks. English default, deterministic single-entry stored PK3,
matching key/format domains, native length bound and exact-hash localization
fingerprint tests pass.

With immutable encoded Core
`eea592c7c55435f6df5fac8e2d72964bb2ea490da19cace42d28d50e850a8075`
(`run/banner-native-state24`, loader85fc), all four final targeted native UI
cases pass with the new assets. Full archives under `run/qa-cod1-four/history/`:

- `banner-eea-line37-CoD1-DEHost-ENpeer-full-text-down-progress-revived-PASS-1795314179064262850`
- `banner-eea-line37-CoD1-ENHost-DEpeer-full-text-down-progress-revived-PASS-1795314230670028872`
- `banner-eea-line37-UO-YAP-LAA-DEHost-ENpeer-full-text-down-progress-revived-PASS-1795314276377667437`
- `banner-eea-line37-UO-YAP-LAA-ENHost-DEpeer-full-text-down-progress-revived-PASS-1795314337179857616`

`tools/qa_banner_localization.py` uses genuine native lethal damage and normal
Host three-second Use revival. It checks actual translated center-print buffers
on each own CGame instance, correct local language, decimal player2 substitution,
no unresolved key/UNLOCALIZED or center-print translation warning, and the
actual40-byte line budget. It captures both screens at downed, progress and
revived stages, keeps the full raw native sidecar SHA-bound to a bounded
scenario result, and retains normal clocks/logs/native exit0 checks for both
processes. All24 final stage screenshots were inspected: complete German/English
hints and progress labels, German glyphs, player numbers and revived messages
are visible without clipping or UNLOCALIZED. Contact images are
`run/campaign-investigation/banner-eea-line37-{CoD1,UO}-{DEHost-ENpeer,ENHost-DEpeer}.png`.

Both UO copies use reviewed LAA executable SHA256
`0a0c52e5aa3e15f4b7039bb22593b8b58f594db5061b4fd4e25a2b4ca3a10018`
and YAP SHA256`9111847c9ed2f1afbdb513d22f2f87f60e23766ba48df60f813d22e1dcaaf431`;
original raw-executable provenance is preserved. These256MiB raw QA cases select
only CoDCoop UI language banks; the existing base-game text/voice language is
unchanged. They do not replace full game-language mixed-installation or actual
installer/stager/repair/rollback acceptance. The normal localization warning
settings are not modified, no Core writes are made by the producer, and no
mission/campaign completion is claimed. Native catch-up/disconnect banner
execution and full console/UI translation remain outside these six-message
rendering checks.

### Exact exported feature63 Core: two targeted native consolidation PASSs

The current capability-declaring binary is immutable
`run/banner-feature63-state24/codcoop_core.dll`, SHA256
`6c726d798f862361d0079f317185330d98c89648c8daa1ae497a3f295e139781`,
loader85fc, protocol9/State24/features63. The parent reports only the exported
localized-banner feature bit differs from the prior encoded prototype; these
checks nevertheless execute this exact new DLL rather than treating old source
proof as new binary acceptance.

Two existing strict UO+YAP/LAA0a scenarios run separately and pass, each with
both actual processes rendering, strict logs and native exit0:

- `banner-feature63-UO-YAP-LAA-ENHost-DEpeer-full-text-down-progress-revived-PASS-1795314640300569815`
- `role-feature63-UO-YAP-LAA-guestDOWN-nativeCP-strictpose-vitals-normalUseRevive-PASS-1795314733563607760`

The first checks EN Host/DE peer native center text and all six screenshots at
actual downed, normal three-second Use progress and revived stages. Correct
local text, player2 formatting, complete40-byte-safe lines and no unresolved
keys/UNLOCALIZED/translation warnings pass on the exactfeature63 DLL.

The second uses explicit raw-QA default EN/EN banks in its recorded provenance.
It genuinely downs guest1, writes the native SVG/V2 sidecar, loads it and
rejoins while still downed. Both owners' pose/view deltas are0; the actual own
CG current client1 camera agrees. Saved/restored guest Downed=true,
PS/entity1, prone bit1, actor INELIGIBLE and personal inventory remain correct.
Normal Host three-second Use then produces Alive300, prone0, actor ELIGIBLE.
Exact SVG/sidecar, runtime, native input hashes and reviewed UI bank bytes are
preserved with the complete archives under `run/qa-cod1-four/history/`.

Inspected contacts are `run/campaign-investigation/banner-feature63-UO-ENHost-DEpeer.png`
and `run/campaign-investigation/feature63-UO-down-checkpoint-revive.png`.
These are two separate256MiB isolated native scopes, not one combined mixed-UI
checkpoint session, installed payload acceptance, native Windows or campaign
completion. No oracle was weakened and no Core writes were made by the tests.

### UF original-loop world witness: source-only proposal

`campaign_patches/uf_world_observer.gsc` and
`tools/build_uf_world_observer_fixture.py` prepare a bounded observer for the
pinned original UF sources. This is not integrated into the common builder,
packaged, compiled by the game, installed or native-verified. Its review output
must not be mounted over the existing compatibility overlay: the uncomposed
original `_UF_mod.gsc` would shadow earlier asset/mechanic fixes.

The original synchronous prefix is `give_loadout` → Campaign → conditional
Cvars → Map_Climate → Levels/year, before the special-map returns and ordinary
equipment setup. Original `thread Campaign()` and the relevant Levels prefix
contain no waits. Cvars assigns the actual nation CVars immediately, while its
Save_Faction_Cvars child waits one second before copying nation fields; the
observer therefore compares `sp_ally_nation`/`sp_axis_nation`, not delayed level
fields. UF_mod's later Spawners stage can change the population, so later
`getspawnerarray()` rereads are not equivalent evidence.

The fixture retains one original array read and one classname read per original
iteration. It records the last recognized Campaign index/class in the original
three case groups and the first exact snow-class match in the separate climate
scan. The later climate map override is retained and does not invent a snow
actor. The independent resolver graph supplies the recognized23 campaign and10
snow classes; class matching remains case-sensitive, including snow_BAR.

The proposed native input prefix is `coop_uf_native_` with fixed fields `api`,
`mode`, `intent`, `map`, `preinit_world`, `init`, `epoch`. The native publisher
must clear output to WAIT before GAME_INIT and provide a fresh opaque epoch and
serial. Only actual HOST/fresh intent0 is observed. GSC requires the actual
`level.script` and `mapname` to match the published map and rereads the stamp
before its final commit. Saved intent1, stale contexts and absent API do not
produce a witness. Initial proof must establish HOST before actual GAME_INIT;
late activation after an already completed solo init is not covered.

Output prefix `coop_uf_world_` contains stamp `map`, `preinit_world`,
`init_serial`, `epoch`, `graph`; independent `campaign_count`, `last_index`,
`last_class`, `climate_count`, `winter`, `winter_index`, `winter_class`; stage
SVids `campaign_world`, `climate_world`, `year_world`; and `cmp_campaign`,
`cmp_climate`, `cmp_year`, `cmp_ally_nation`, `cmp_axis_nation` comparison outputs.
Indices use -1/empty sentinels and positive matches must be inside their own
observed count. Counts above4096 fail explicitly; this is an observer export
bound, not a claimed native entity capacity. Only fixed observer CVars are
written; no actors, game/level fields, mechanics, commands or resource state
are changed. The final status is OBSERVED, never gameplay/lobby/resource READY.

Fast restart can update native `sv_serverid` after GAME_INIT. Consequently GSC
does not require the pre-init ID to equal each later stage ID. The future native
consumer must latch the source snapshot after original init and validate each
stage's ID against the known pre-init or completed-init world under the same
private epoch/serial/map/game-VM scope, then bind to the completed final ID.
An old loaded CVar bank must never be reasserted as current observed facts.

Five focused fixture tests pass, including transformation of the actual pinned
UF archive, single-read/order preservation, map-override separation, observer
write scope and rejection of an unknown source SHA. Reproduce with
`/usr/bin/python3 -m unittest discover -s tests -p 'test_uf_world_observer_fixture.py'`.
Native publisher/consumer, composition with the production overlay, GSC compile
and actual paused-pregame observation remain open. The intended native proof
must distinguish real engine pregame pause (stable world clock/actors with live
UI/heartbeat) from UF introscreen control locking; neither source tests nor a
loaded map establish that behavior.

### QA-only native UF world epoch and paused preparation

The subsequent isolated native prototype uses immutable Core
`6ffc8fd0fd0eea1a5dedde03e47d925468122d659716b417087bba97fea8eb1a`
from `run/uf-observer-epoch-prototype`, loader85fc, reviewed UO LAA0a and YAP911.
`tools/qa_uf_world_observer.py` uses only an owned existing Host clone/prefix,
port29968 and512MiB hunk. It enables only the explicit QA observer publisher,
starts `coophost` before `devmap`, and supplies expectedplayers2 with only one
actual Host. This is deliberately a single-Host preparation observation, not a
joined-player/liveness or equipment-application test. No model-capacity increase
or deferred-model policy is enabled.

The fixture now optionally composes instrumentation **after** the pinned
`uf_airborne_missing_load` transform. Repaired `_UF_mod.gsc` hash is
`c6722cdc75db316cc39fb5ee190ee17165eb415979fc768f3b98accdab5affc6`;
the composed instrumented hash is
`e972fe9c30c41624256c12250488ffc3c6b4eb9ce38780229265058599c33034`.
Only the owned QA overlay `zzzz_coop_world_observer.pk3` contains this composed
source; normal compatibility assets remain in the separately rebuilt campaign
overlay. Existing generated QA overlays are archived before replacement.

Actual Brecourt and Foy original-loop scripts compile and publish OBSERVED with
matching native epoch/serial/map, completed init and known stage world IDs.
Brecourt reports91 Campaign and Climate spawners, last recognized index90
`actor_ally_airborne_thompson`, no snow match, american campaign/year1944,
american/german nation CVars. Foy reports177 in both scans, last recognized166
`actor_ally_airborne_snow_garand`, first winter index3
`actor_axis_snow_wehrmacht_soldier_kar98k`, american/year1945/winter. These actual
ordered-loop observations happen to agree with the separate static BSP
candidates on these cases; this does not make BSP order a general native oracle.

The paused-pregame samples keep native world time300, `cl_paused=1`,
`cg_norender=1` and Host position unchanged while native diagnostic files update
each second. Manually inspected screenshots show the original mission journal
and “Klicken zum Starten”, not UF's later introscreen cards. Foy then receives
the ordinary Start UI action; native world time advances to528 and native
exit0 follows. Other AI actor coordinates were not independently sampled;
world-clock pause, Host pose and original UI are the demonstrated scope.

Evidence is preserved under `run/uf-script-qa/history/`:

- `1795317003001667421`: initial Brecourt overall FAIL because the first QA
  oracle inspected OBSERVED before the next native completed-init export.
  Native completion immediately followed; the repeat waits for both and does
  not reinterpret this original failed report as a PASS.
- `1795317068674672270`: Brecourt compile/context/paused-journal PASS, followed
  directly by normal quit; this earlier scope does not include Start release.
- `1795317107105074898`: Foy compile/context/pause and ordinary Start-release
  PASS with normal exit0.
- `1795317181585869391`: Noville **FAIL**, native `G_ModelIndex: overflow` after
  model255. The original-loop console reached OBSERVED first (count167,
  last158 snow_garand, first winter2 snow_waffen_mp40/year1945), but no completed
  native context or paused-preparation acceptance exists for this run. Those
  console values are partial diagnostics, not a valid completed-world witness.

The native publisher remains QA-only and declares `runtime_ready=false`. There
is no production observer capability, independent native resolver enforcement,
individual-role ready state, late-solo-host handoff, saved-world observation,
full resource-capacity acceptance or campaign-completion claim. The unchanged
Noville model overflow is an explicit blocker. Focused source/oracle tests now
total19, including stale/incomplete epoch rejection and accepting only known
pre-init/completed IDs under the same context.

### Clean-input selected-resource counterfactual and final witness baseline

A later provenance review found an old owned `qa-render-models.txt` in the
reused clone. Its SHA256 was
`a9a7824676355cdb2a41bc53b2f9ab0dfb94a7d46ecabda9efff4f40632bbaff`,
also shared by its old deferred-input file. Deferred mode was disabled, but the
renderer-only hook consumed242 cache names. Native logs explicitly showed
unchanged server CS counts (for example252→252); this is not evidence that the
cache caused or cured CS overflow. Earlier successful observation runs retain
their measured scope with this extra-cache caveat. The runner now archives and
removes both exact known owned input files before launch and explicitly clears
unrelated QA environment switches. No engine guard is disabled.

The final clean-input cases preserve independent runtime/source/overlay hashes,
native read-only model-table JSON, genuine journal screenshots, original-loop
facts, paused samples and ordinary UI Start→native-clock advance:

- `1795317423538485041`: Brecourt, unchanged universal production builder
  parameter, **PASS**,250 actual server model IDs; paused300→Start543, exit0.
- `1795317315857769029`: Noville, explicit experimental `selected` resource
  policy, **PASS**,252 model IDs; original facts167/last158 snow_garand and
  first snow2 snow_waffen_mp40, matching epoch/completed init and journal pause,
  then normal Start and exit0.
- `1795317353239061777`: Noville, same Core/observer with clean inputs and
  universal resources, **FAIL**, native `G_ModelIndex: overflow` at255. This is
  not a completed-world/pause PASS despite an earlier GSC OBSERVED console line.
- `1795317391011712346`: Foy, clean inputs/universal resources, **FAIL**, same
  native overflow. The earlier Foy success must not be generalized to every
  authored/random startup path; a causal explanation for its variation has not
  been proven.
- `1795317480908677820`: Foy, explicit experimental selected resources,
  **PASS**,249 native model IDs;177/last166 snow_garand, first snow3
  snow_wehrmacht_kar98k, paused300→ordinary Start542, exit0.

All paths above are under `run/uf-script-qa/history/`. The first selected Noville
case `1795317288090733712` also passed252 with the old cache present and remains
distinct from the subsequent clean-input repeat. Selected policy removes only
our unconditional universal reservations while retaining the original chosen
equipment/aircraft setup; it remains a diagnostic parameter. The global builder
default is unchanged. These checks do not prove four different kits, every
legal resource union, aircraft/MG mechanics or production asset transport.

The witnessed GSC prefix executes before original equipment setup, but the
native JSON export is available only after native GAME_INIT returns. By the
visible journal pause the resource registration has already happened. A future
approved individual-kit resource plan therefore needs an explicit preparation
and initialization/restart contract; it cannot infer permission to add late
models from this OBSERVED snapshot. All owned native games are stopped. The
clone's current observer overlay and selected diagnostic campaign overlay must
be quarantined/rebuilt before unrelated UF mechanics acceptance.

### Experimental existing six-caller deferral: three Host-only diagnostics

The same immutable6ffc Core, composed witness, **universal** compatibility
overlay, UO LAA0a/YAP911 and512MiB hunk were measured with the existing explicit
`CODCOOP_QA_DEFER_MODELS=1` QA branch. Native model IDs remain byte-sized and the
native255-slot limit/late guards stay enabled. There is no512-model override,
ID reuse, new allocator, production registry promotion or Core edit.

Before each launch the runner archives/hashes/removes the exact owned renderer
input, deferred input and current-map `qa-model-ledger-<map>.txt` input. Symlinks,
including dangling links, are refused before any of those input files is
changed. A real-filesystem regression test checks this refusal and confirms
other-map ledgers and external targets remain untouched. Each actual native log
reports BEFORE_GAME_INIT with imported0; persistent ledgers therefore do not
silently prime the experiment. New ledger/media telemetry is retained afterward.

All three native original-loop witnesses match fresh HOST epoch/init/world and
their earlier class/year/nation observations. Each shows genuine original
journal pause, unchanged world time300 and Host position while diagnostics
continue, then ordinary UI Start, native first live registration and exit0.
Manually inspected three-journal contact is retained in the final Brecourt
archive. Measurements under `run/uf-script-qa/history/` are:

- `1795318466241371291`, Foy: approved257/loaded257 media,669 deferred discard
  calls,155 CS IDs before and after EndRegistration; actual paused155 and first
  live186. Game active m1carbine40 agrees with own current CG snapshot,
  prediction and desired selection40/name. Its raw registration audit was
  inspected directly; subsequent runner versions also assert the audit fields.
- `1795318525433381835`, Noville: approved258/loaded258,736 deferrals,
  EndRegistration CS173→173; actual paused173 and first live202. Strict1 and
  unchanged guards are asserted alongside the complete media preload.
- `1795318574427996733`, Brecourt: approved250/loaded250,617 deferrals,
  EndRegistration CS111→111; actual paused111 and first live145. Game active
  m1garand42 agrees with own desired/predicted/current snapshot42/name. Native
  last-use binding log reaches145 through the normal actor attachment caller.

The startup read-race failure `1795318497480349997` is retained separately:
Noville's runner tried to inspect the Core log before it existed, before map
initialization. Only the observer's existence check was corrected; no native
error or gameplay assertion was waived. The later complete repeat is distinct.

These bounded results show reservation pressure can be avoided by the existing
QA six-caller deferred path while preserving full early media caching. They do
not validate production lifecycle/persistence, saved games, hot reload, four
individual kits, network approval/registration, gameplay completion or all
eventual map resource demands. The known held-gun ModelIndex lookup issue is
**unfixed** in this Core; matching own Game/CG selected weapon names is not proof
of correct third-person weapon models. No actor/world/inventory state is
changed by this diagnostic beyond ordinary original Start behavior. All owned
game processes are stopped; the existing QA-only globals are not promoted.

### Experimental four fresh UF roles: body/cache counterfactuals and Brecourt

`tools/qa_uf_fresh_roles.py` is a separate trusted-scenario driver; the older
checkpoint driver is unchanged. It uses four actual owned instances, the four
reviewed American `kit_fixture(4)` choices and a Host-only fixed QA plan. Peers
start without `devmap` and receive the normal resource-bootstrap v2 contract;
no peer plan, offline item bootstrap or renderer/deferred input union is
injected. The universal overlay and existing experimental deferral are explicit.
No borrowed-tree, MT-epoch or DObj-barrier QA flag is enabled in these cases.
All owned executable/plugin inputs remain LAA0a/YAP911, with512MiB hunk and the
unmodified native255 model-ID budget.

The read-only native observer distinguishes actual DObj XModel names from
negative flag IDs' server-shadow CS and actual-client CS names. Its complete
1..255 slot table retains holes and independently reports the native Game
model-cache name at RVA D2E70. The ownership-aware oracle requires Host server
bodies for all four owners, and other-three client/server-shadow bodies in each
first-person observer. First-person own-body presence/absence is explicitly
recorded; it is not treated as third-person self-body rendering. Every checked
body component must match actual model, negative ID, both CS tables and native
cache name. Own current CG client/weapon identity, native inventory and real
input/fire remain independently required. Negative fixtures reject missing
other bodies, wrong actual models, wrong client/shadow CS, positive flags and
wrong cache despite otherwise matching names.

All archives below are under `run/qa-cod1-four/history/`:

- `1795319400630017697`, Core06cf5844, **FAIL**: four distinct native kits/own CG
  and real remote movement159/203/188 units pass. The initial oracle also
  expected an own first-person body (subsequently corrected as above), but the
  raw observation independently proves missing late shadow mappings for other
  bodies: peer1 server body2 has actual weapon_bar/flag-157 with empty shadow
  CS; head basehead2_02/flag-154 is also empty. This remains an overall failure,
  not a retrospective PASS. Proof SHA256
  `3969fafbba80af65bb35b0e491d2df442b13106e99a2e7cda7a9af79d01deaf9`.
- `1795319617626340645`, Core232d34c4, **FAIL**: fresh kits/own CG and real
  movement196/152/169 pass, but every peer lacks all player-body DObjs while
  Host has the correct four. Thus the ownership-aware other-player oracle
  independently fails. The case-sensitive new mirror rejected native
  case-equivalent model names. Proof SHA256
  `aa8b179ba45a5a6df144afae4aa3b149242457c705ba94a3206193db447ac577`.
- `1795319859267421478`, Corea8bb4213, **diagnostic stopped FAIL**: first real
  WAIT reason8 reports id107 `gear_us_helmet` versus client/shadow
  `gear_US_helmet`. Independent complete slot data also shows stale native cache
  `gear_us_moody` at107, a separate same-ID cache problem. After this exact
  diagnosis all instances receive normal quit; the harness reports exited
  during connection. This interrupted diagnostic is not four-owner acceptance.
- `1795320305470444441`, Corebb02a762, **PASS**, with the corrected native
  case-fold comparison and same-name stale-cache repair. All strict component
  checks above pass for four fresh roles, including real primary MG/bazooka
  selection and pistol/binocular selection through normal `weaponslot` input.
  No observer writes or cache-mismatch waiver are used. Actual owner assignment
  is Host0, join1→2, join2→1, join3→3; the driver follows observed owner slots
  rather than assuming process launch order. Before/after actual firearm clips
  are30/5/20/8→29/4/15/7; all three guests also move through actual owner input.
  Own current CG, Host active weapon and inventory agree. Normal bootstrap
  transfer→native init→item registration→Game/CG verification→attach ordering is
  asserted on all three peers. Four actual native exits are0.

The final proof SHA256 is
`ca9d08ad51602cb40f0fe0aeff9b65ce33c05b42e996ed6300bacff0ebc24705`;
generic harness result SHA256 is
`b6c55dae07df3559253f3025a75e7fe4d5237490709e54a18b3ce99dc3d8880f`.
Exact runtime/source/overlays, helper executable and eight raw native images
are archived. The eight-image contact and a full owner3 image were inspected:
normal world, held MG/bazooka/binoculars/pistols and other-player bodies render.
Root independently spot-checked owner2 bazooka and owner0 binocular images.
This is model/selection/regular-fire evidence, not MG deployment or bazooka
firing, full animation/mission acceptance, a production registry, GUID-bound
kit selection or save/load testing. The original mission naturally writes its
startup autosave; the driver issues no save/load command and makes no saved
world correctness claim. This successful run overlapped independent installer
I/O and had slow loading; no FPS or loading-performance acceptance is inferred.

### Noville four-owner extension: native crash, separate GMI producer gap

The serial Noville extension on the same immutablebb02 Core/universal overlay,
fresh QA plan and normal resource-bootstrap v2 **FAILS**. No borrowed-tree or
additional MT/barrier experiment is enabled. Join1 logs real access violation
`c0000005` at engine`0045fd50`, registers eax`ff000002`, ebx/ecx`0000cc00`,
edx7, with stack starting`00433230`; the parent independently identifies this
as the native XAnimFreeTree→MT_FreeIndex path. A causal Core caller/ownership
trace remains required. It must not be described as a model-capacity failure,
mere timeout, successful four-role map load or a reason to waive the allocator.

Evidence is preserved in
`run/qa-cod1-four/history/1795320581657023310`, proof SHA256
`f3d8a087904e92299bf36a452a43c95f9c77bd7aa157314f29c6d3300aaea6fa`.
The `noville-native-crash-before-cleanup/` directory captures Host/three-peer
Core logs and raw states before normal quit requests. Generic harness cleanup
then ends the exclusively owned prefix; no owned live game remains. The
generic result reports exit during connection after cleanup, while the explicit
native-crash sidecar preserves the actual failing cause. Foy four-owner testing
has not started because the Noville gate failed.

A separate source audit explains why this Noville run cannot claim distinct
kits even before that crash: its raw plan inputs execute, but PLAN_VALIDATED
and application receipts never appear and Native Host-loadout fallback repeats.
Pinned UF `maps/noville.gsc` and `maps/foy.gsc` call
`maps\\_load_gmi::main()`, whereas the current adapter and shared compatibility
startup injection only modify `maps/_load.gsc`. UF `_load_gmi.gsc` SHA256 is
`1062d0435eb6bfa4c3020b27ddb7fb2f6a8c1241f1339d675034b8ef5b76baff`.
Its original order binds the protagonist, runs `_tank_gmi`, UF give_loadout and
UF_mod; its authored speed/environment resets must be preserved. A separately
pinned GMI-loader adaptation needs source/compile/runtime verification. This
producer omission is independent of the native tree-free crash and does not
justify inventing a kit or changing original special-role guards. No GMI
behavior or Core source is changed as part of this read-only finding.

### Separately pinned GMI startup adaptation: source/fixture stage only

The next source candidate adds `transform_uf_gmi_load` with the independent
UF1062d043 source pin. It reuses only the existing small startup insertion after
the original player binding: mount/media, mine/air resources and the scoped
player observer. Under explicit `qa_gmi=True` plus `qa_kits=True`, its kit Start
call follows the original UF give_loadout and precedes the original UF_mod main.
The UO `_tank_gmi` call, g_speed190 and authored environment/reset code remain
byte-identical outside these two bounded insertions. Missing/duplicate expected
binding patterns and unknown source hashes fail closed.

This build mode is explicitly QA-only: `build(..., qa_gmi=False)` remains the
default; CLI `--qa-gmi` requires the UF QA-kit overlay mode. The fresh-role runner
exposes `--experimental-gmi-loader`, also default false. Production staging and
the original Noville causal trace therefore keep their old payload. A focused
test proves disabled mode reproduces the archived failing Noville overlay
**byte for byte**, while the enabled mode adds only `maps/_load_gmi.gsc` plus
explicit experimental metadata; all other package entries are unchanged.

Four focused tests pass for original ordering/world-rule preservation, unknown
revision and prefix-shape rejection, option gating, deterministic real pinned
archive composition and disabled-byte parity. The44 existing campaign patch
tests also pass. Reproduce with
`/usr/bin/python3 -m unittest discover -s tests -p 'test_uf_gmi_loader.py'`.
No native game has compiled or executed this GMI-adapted candidate yet. The
parent's unchanged-old-payload tree-free causal trace must run first; neither
this source fix nor future kit receipts explain or waive the archived native
XAnimFreeTree crash.

### Unchanged-payload native tree trace: connectivity FAIL, crash not reproduced

Immutable Core9f86261d's optional read-only `CODCOOP_QA_TREE_FREE_TRACE=1`
is enabled through the separate runner `--trace-tree-free` flag. The GMI option
remains off, as do borrowed-tree/MT/barrier experiments. Actual overlay SHA256
`dde752845fc22cb23a67535c1c01154d6ff4f854e8958d804e9eed1f9a74934f`
matches the archived bb02 Noville failure payload byte for byte.

This four-process attempt ends **FAIL** at the unchanged180-second connection
deadline, with no native crash reproduced. Only join3 attaches as native slot1;
join1/join2 repeatedly queue the same map before owned-tree creation. The
independent read-only bootstrap audit identifies earlier registered-bit
differences despite matching Game/CG weapon names: springfield98 expected0/
actual1 on join1, thompson28 index111 expected0/actual1 on join2. Its separate
snapshot is `run/noville9f-bootstrap-diagnostic/1795328608465252512/report.json`.
This is neither four-owner acceptance nor evidence that the original tree-free
crash has been fixed.

The joined peer does record complete normal free sequences. For example
entity334/tree00963400 starts with definition3016a9a0,988 nodes, refs17/mark1;
server free keeps those fields, client sync clears mark, info release reduces
refs to0, and immediately before native tree free definition/nodes remain
unchanged. After native free the readable allocation has definition0/nodes0.
Other recorded frees similarly retain their definition through native entry.
These observed normal phases do not identify the corruption in the prior
crashing run. The prototype's `notify` field reads16 bytes before the actual
native info field and must **not** be interpreted as an actual SL handle; the
parent identified this read-only diagnostic limitation independently.

The failed run, complete traces, runtime/source and byte-identical old overlays
are archived at `run/qa-cod1-four/history/1795328672428275680`, proof SHA256
`0020a28400818cc7e753be3236be5889cfdfa0b7c50139bf5ed994cbfe992c1f`,
harness result SHA256
`ebf59c7f4af081626735d21d0e40cb6bcd834262411b5a8a06d26982ca2bd63b`.
All owned processes are stopped. No guards or free behavior were changed,
no GMI-adapted native game ran, and the original native crash remains open.

### GMI-on453995: producer verified partially, corrupt definition at free entry

Immutable Core453995fb executes the GMI-on Noville attempt with corrected
read-only notify offset, strict native registered bitmap unchanged and bounded
bootstrap feedback changes. Default255, deferral1, no borrowed-tree/MT/barrier
extras and real bootstrap v2 remain explicit. The runner now requires the
validated catalog/epoch, unchanged four submitted manual choices and all four
application receipts tied to current native FRESH session/slot/ticket/world
before entering its acceptance phases. Wrong receipt/ticket/disposition/catalog
fixtures fail; no four-owner result can be inferred from input CVars alone.

The new loader actually compiles and runs: Host PLAN_VALIDATED and exact
receipts0,1,2 appear. Receipt3 never appears. A separate postmortem verifies all
submitted plan fields stayed unchanged, all four overlay metadata records carry
the pinned1062d043 GMI source, but the strict all-four receipt result is false.
This establishes the loader omission and its partial correction independently
of a successful four-player session.

The attempt **FAILS with two actual native crashes**, not an acceptance timeout:
join2 entity341 is created at07:29:43.600 with tree00975400,
definition3016db60 and988 nodes. At07:29:56.390 the same tree/definition already
has node count-16777216 at **free-entry**, before server free, client sync or
info release. It stays negative through native-free entry and faults45fd50.
Join1 simultaneously reaches the same invalid shared-definition content at
free-entry (tree00971400, refs14 versus join2 refs0) and faults too. Loaded=true
does not prove definition-content integrity. This localizes the corruption
before these particular free sequences; it does not identify the earlier write
instruction or authorize skipping the allocator. The owned-window hardware
write-watchpoint investigation is separate and pending.

All runtime/source/overlays and pre-cleanup logs/console/states are archived at
`run/qa-cod1-four/history/1795329148842541172`, proof SHA256
`8cbfaa378db53eb06c952c24ddd413d2ab6d1c7f05aec1ac1e04d96f6a89c6a9`,
result SHA256
`bc5d500f325a20737bd2e5ef0f954037ad009336436453fc912c1f3d2ba96471`.
`453995-native-crash-before-cleanup/` retains the actual fault context, and
`453995-partial-plan-audit.json` explicitly refuses four-owner success. All
owned processes are stopped; no fire/body phase or Foy four-player run follows.

Peer3 independently preserves a precise compatibility WAIT: index111,
thompson28, Host expected_registered0 but local Game registered1. All119
expected/Game/CG names agree; this is the only difference, and peers1/2 have no
mapping difference. Thus an **extra local registration0→1** persists despite
the Host's GMI plan, not a missing required1→0 item. Original network mapping
TSVs and transmitted/received resource text are copied with SHA/mtime into
`bootstrap-postmortem/`; `audit.json` records the exact comparison.

Host and peer3 logged derived American/German nations,1945 and winter. Raw
sp_ally/axis/forceweapons/ammo/history/order/campaign/loadgame values were not
logged; they are unknown rather than assumed empty/equal. The pinned original
American loadout uses Noville's load5 candidate lists and random rifle/SMG
selection, including thompson28. Host's initial CG selects m1garand42 while
peer3's selects m1carbine40 before manual application. Independent original
random selection is consistent with the mismatch, but neither these logs nor
the registration bitmap prove which native caller registered thompson28; AI
startup remains another possible source.

Host's synchronous plan resource pre-cache/PLAN_VALIDATED precedes renderer
EndRegistration07:29:14.493 and completed init15.025. Bootstrap exports at
17.327/27.251/38.932 all carry347 models/119 weapons. Therefore the mismatch
occurs after a plan-aware initial export, rather than proving that the Host
never prepared the requested resources. Native bitmap enforcement stays strict.

The feedback behavior has a separate bounded positive scope despite the native
crash/four-owner FAIL: after peer3's explicit mapping WAIT, no repeated host-map
queue log occurs, and its visible status keeps the concrete failure instead of
being overwritten. The first partial five-second sample contains101 control
packets; subsequent complete samples contain24–28, compared with the old rapid
reload loop. Exact per-type ACK/M_MAP packets were not captured, so total control
counts are not presented as individual message counters. This feedback evidence
does not waive either the compatibility rejection or the native corruption.

### All-existing-weapon media option: source-only preparation

The fresh-role runner adds explicit
`--experimental-all-weapon-media`, default false. For each of its four owned
game launches this sets only `CODCOOP_QA_ALL_WEAPON_MEDIA=1` in addition to the
already declared diagnostic flags; it changes no GSC plan, inventory grant,
model capacity, bitmap comparison or actor/world state. Inherited copies of
this QA flag are removed when the option is absent, preventing an unrelated
environment from silently changing a causal trace. Metadata labels it native
item/media registration, not inventory or native acceptance evidence.

The parent's separate future all-media Core experiment has not been run here.
Its intended complete existing119-definition media registration must retain
normal native item registration and strict comparison/255-slot guards; its
effectiveness and512-entry approved-name closure remain unverified. The next
hardware write-watchpoint run must use the immutable453995 registration layout
without this option so it can catch the original definition corruption.

A pure parser/environment regression verifies opt-in behavior, exactly one
added environment key, inherited-flag suppression, preservation of the input
environment and no implicit borrowed-tree flag. These tests parse paths without
accessing a prefix or launching a game. Five fresh-role source/oracle tests pass;
no native or prefix mutation is performed for this option preparation.
