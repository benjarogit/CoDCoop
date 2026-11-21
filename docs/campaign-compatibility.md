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
All archives are under the same owned QA history directory. UO/SP Improved's
new initial-grant behavior, actual shared Use, complete mission flow, native
Windows and physical mouse input still need acceptance.

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
`sp_` alias handling. The current fixture updates only the known owned generated
`zzzzz_codcoop_triggers.pk3`. Native comparator evidence and engine-aware
inventory ordering are separate from historical source-only inventories; no
general package renaming or authored-package reorder was applied.

The generic QA harness accepts targeted scenarios only through the explicit
Python callback API. It first proves real connection and advancing clocks,
requires bounded explicit scope/checks/evidence, and retains screenshot/log
checks, native QUIT and exit-code checks. Targeted scenarios cannot silently
skip requested checkpoint reloads. The ordinary CLI smoke path is unchanged.
