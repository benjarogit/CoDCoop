# Original UF world resolution — source-only prerequisite

This is an independent resolver for the original United Fronts 1.1 beta startup
graph. It is **not connected to Core, a native preparation gate, or a party
capability**. It does not make a proposed lobby world authoritative. It does not
prove resource closure, the 255 model-index budget, or a mission playthrough.

## Pinned evidence and reproduction

`campaign_patches/uf_world_rules.json` records the exact original member SHA256s.
The reviewed package is `ZUnitedFronts_1.1_beta.pk3`, SHA256
`b4f6bb7d03477d7e77e5150af4ca88eeb3dee30e0f715edfa1e2338d3e9d1cbe`.
The extractor refuses an unknown revision rather than applying an approximate
parser to it. The map allowlist comes from the existing campaign inventory.
No game script or model asset is redistributed by this graph.

```sh
python3 tools/uf_world_rules.py --extract-package /path/to/ZUnitedFronts_1.1_beta.pk3 --output /tmp/uf-world-rules.json
cmp campaign_patches/uf_world_rules.json /tmp/uf-world-rules.json
python3 -m unittest discover -s tests -p test_uf_world_rules.py -v
```

The independent extraction contains 122 registered maps, 99 explicit map
campaign labels, 96 explicit map/year labels, 23 campaign-changing spawner
classes, 10 winter spawner classes, and 13 explicit faction/nation mappings.
Original defaults remain recorded as defaults, rather than invented map data.

## Original call order and stage boundaries

1. `maps/_load.gsc:58–70` assigns `level.script`, obtains the original player,
   and calls `_UF_loadout::give_loadout` before `_UF_mod::main`.
2. `_UF_loadout.gsc:1500–1506` starts `Campaign`, fresh-load `Cvars`, and
   `Map_Climate`. These functions have no wait before producing the facts below.
   `Cvars` starts a separate delayed maintenance thread after its initial writes.
3. `Campaign:683–833` first assigns a campaign by map, then scans the actual
   **ordered** `getspawnerarray()`. Every recognized classname overwrites it;
   the last recognized spawner wins. Reversing a mixed British/Russian array
   changes the campaign. A map alone cannot establish the final value.
4. `_UF_mod::Cvars:800–882` uses the actual raw `sp_ally` and `sp_axis` strings
   to select nations; special default maps include German-side
   `gfm_omaha`/`sp_eugene` and British/Italian `sicily1`/`sicily2`.
   `Save_Faction_Cvars:885–918` waits one second and maintains the resulting
   faction/nation state periodically. It is not a source of new user choices.
5. `Map_Climate:1015–1077` checks original spawners and then map overrides.
   A snowy spawner on a desert map sets **both** winter and desert flags, with
   the displayed climate ending at `desert`. The original flags are not a
   mutually exclusive enum. Classname comparisons retain their original case.
6. `give_loadout:1538–1540` calls `_UF_maps::main` and starts `Levels`.
   `Levels:1090–1207` sets year by map, defaulting to 1944. For example training
   is 1942, Brecourt 1944, Foy and Noville 1945. Campaign-order selection does
   not change those year assignments for an already selected map.
7. `Levels` and the loadout family functions then select original hands,
   loadouts, carryover and ammo. `ship` has a separate enemy-disguise hands
   branch. Those actor/RNG/resource decisions are not synthesized by this
   resolver. `_UF_mod::main` performs additional character/resource work.
8. `_load` starts `_UF_introscreen::main` **after** these calls. Its timed HUD
   cards and `freezeControls` sequence are different from the engine's paused
   pregame menu. A card or frozen player alone does not prove paused world time.

### Raw input versus derived state

`sp_fr` and `sp_en` occur in the reviewed menu actions, not in the GSC reader
graph. The menu writes both the selector number and the actual `sp_ally` or
`sp_axis` string. The original active GSC inventory has no writer for these
two raw faction inputs. It does write `sp_ally_faction`, `sp_axis_faction`,
`sp_ally_nation`, `sp_axis_nation`, and `sp_climate`.

The menu mapping is 0 none; 1 US airborne; 2 US infantry; 3 Russian; 4 British
airborne; 5 British infantry; 6 SAS; 7 RAF; 8 Dutch resistance; 9 German army;
10 SS; 11 German paratroopers; 12 German navy; 13 Italian.

A stale `sp_fr=2` with actual `sp_ally=ru` therefore resolves from `ru` and
reports the selector mismatch. Rewriting one from the other would alter the
original input. Empty/default strings retain their provenance. Unknown strings
or unsupported enum choices raise a visible unsupported-input error, rather
than being clamped or silently changed.

On a save load, original `give_loadout` skips `Cvars`; saved level/game faction
state can differ from current menu values. The resolver returns WAIT for the
saved-world nation/flags. A fresh-map recomputation is not a saved-state proof.

## Typed seam

`Inputs` contains only reviewed original raw inputs; `HostFacts` contains the
registered map, nonzero native world/init serial, and the original ordered
spawner classname array. `None` means unavailable; an empty tuple means an
actually observed empty array. Missing facts remain WAIT. Source-stage output
is not an after-init or resource-ready assertion. A native adapter must capture
facts at the original calls or prove they remain unchanged; reading a later
mutated/spawn-consumed array is not equivalent. No party JSON is an accepted
source for the ordered facts.

## Host gameplay settings outside the current roster world fields

The current `uf_equipment_roster.WORLD_FIELDS` includes map, campaign, raw
factions, ally nation, year, history, order and difficulty. It does not encode
the whole original gameplay graph:

- `sp_ammo`: original `_UF_weapons:611/709` ammo/refill branches **and**
  `_UF_mod:1628–2067` original spawner/wave changes. It is a shared world rule,
  not an individual unlimited-ammo preference. Only exact `1` activates these
  branches; empty and `0` follow the same branch but remain distinct raw inputs.
- `sp_forceweapons` 0/1/2 and `sp_campaign` 0–4: original forced-loadout and
  carryover behavior; `_UF_loadout:2258–2404` has map- and history-dependent
  exceptions. These settings cannot override each owner's approved kit by
  copying Host weapons. The Polish processor case 5 exists, but is absent from
  the reviewed active family menu and remains unsupported by this typed input.
- Actual `sp_ally`/`sp_axis` plus UI transaction provenance: selectors are not
  interchangeable with derived faction/nation or next-world inputs.
- Derived `sp_axis_nation`, `sp_climate`, winter/desert flags, faction identity,
  `game["ally_faction"]`/`game["axis_faction"]`: character/media and aircraft
  decisions consume this graph. It needs an independently observed Host
  context, not a second arbitrary user setting or a guessed default.
- Original dynamic weapon-family CVars feed six `process_weapon_*` readers.
  Those are legacy equipment inputs; individual confirmed actor plans need
  their separate reviewed adapter. The current resolver does not apply kits.
- Original `sp_faction_<character>`, body/head/name namespaces and
  `enemy_wehr`, `enemy_ss`, `enemy_wehr_w`, `enemy_ss_w`, `enemy_para`,
  `enemy_ita`, `enemy_dak` participate in character/media selection or precache
  latches. For example `_UF_mod:5350–5357` uses `enemy_wehr` to avoid repeating
  a precache and then writes it. These are lifecycle/resource state, not safe
  generic lobby toggles; capture actual resource closure and original resets.
- Original mission/test inputs still exist: e.g. `boathealth` in Sicily2,
  `mg42` in `_mg42_gmi`, `no_shellshock`/`for_e3` in Trenches, `minguys` and
  `totalguys` in Stalingrad, and the `start`/`skip*`/`quick_*`/`scr_*_fast`
  families. They are not reviewed party options. The full source inventory is
  `run/campaign-investigation/host-rule-bootstrap/all.json`; a future native
  gate must distinguish original lifecycle writes from stale developer
  overrides, and visibly reject unapproved overrides without silently
  disabling original scene mechanics. `timescale` is likewise not a player
  preference. The static inventory alone is not native CVar coverage.
- Existing YAP prediction rules (`player_sprintSpeedScale`, `player_sprintmult`,
  `bg_allowJumpShot`) already have their own canonical Host authority and
  lifecycle; reuse it. Local FOV, graphics and input are not world rules.

`sp_history` is already a roster field, but its menu item is commented out
while its original script reader is active. `sp_order` controls UI/progression
selection (`_UF_maps:222,784`), not a user's arbitrary declaration of year.

## Preparation gate still to prove

Existing Core `HostNoPause` leaves the actual pregame pause alone;
`MainlineStartMission` waits for the expected active/world-ready party before
the original UI start action. This suggests a Host preparation world can
provide the genuine automatic context before players confirm roles. It is
**source evidence only**. The ordinary QA runner's early `coopuiclick` and
`coopqastart` cannot demonstrate an unchanged paused preparation world.

A dedicated native proof must withhold those actions, measure stable native
world time and actor positions while local observation/handshake remains
responsive, then release through the original start action. Native item/media
registration for newly chosen kits must separately be proven safe before
release and before Joiner GAME_INIT, retaining original index order and guards.
If late registration is unavailable, a normal Host reload after confirmation
is a possible conservative design, with the captured context revalidated in
the new world. Neither late registration nor that reload design is implemented
or claimed by this source-only resolver.
