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
  --profile united_fronts --triggers-only --output run/overlays/UnitedFronts/zzzzz_coop_triggers.pk3
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

The focused campaign tooling suite currently has 34 passing unit tests,
including comment-aware menu parsing, separate kit/alternate resources,
unavailable choices, original aircraft decisions, negative DObj flag semantics
and the fixed model boundary.

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
