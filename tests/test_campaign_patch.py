import hashlib
import importlib.util
import json
import re
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import build_campaign_patch as patch
from campaign_inventory import analyze_script, uncomment
from qa_campaign_probe import final_probe_status
from qa_campaign_resources import entity_models, summarize_references
from uf_equipment_catalog import menu_choices, roster_resources, chosen_aircraft, budget


class CampaignPatchTests(unittest.TestCase):
    def test_live_model_references_use_negative_dobj_flags_and_keep_incomplete_snapshots_invalid(self):
        value = {'references_complete': True, 'reference_layout_valid': True,
                 'models': [{'index': 1, 'name': 'xmodel/body'}, {'index': 2, 'name': 'xmodel/hands'}, {'index': 3, 'name': 'xmodel/reserved'}],
                 'model_references': [{'kind': 'entity_body', 'entity': 4, 'index': 1}],
                 'live_dobjs': [{'raw_model_flags': [-1, -2, 287]}]}
        result = summarize_references(value)
        self.assertEqual(result['referenced_ids'], [1, 2])
        self.assertEqual(result['unreferenced_at_sample'][0]['index'], 3)
        value['reference_layout_valid'] = False
        with self.assertRaisesRegex(ValueError, 'Incomplete or invalid'):
            summarize_references(value)

    def equipment_catalog(self):
        return json.loads((TOOLS.parent / 'campaign_patches/uf_equipment_catalog.json').read_text())

    def test_equipment_menu_comments_and_blank_icon_controls_are_not_choices(self):
        menu = '''/* itemDef { cvar "sp_fake" cvarFloatList { "fake" 99 } } */
        itemDef { cvarTest "sp_campaign" showCvar { "2" }
          cvar "sp_us1" cvarFloatList { "@MENU_NONE" 0 "MG" 9 } }
        itemDef { cvar "sp_us1" cvarFloatList { " " 0 " " 9 } }
        '''
        result = menu_choices(menu)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['visibility']['values'], ['2'])
        self.assertEqual(result[0]['choices'][1]['value'], 9)

    def test_individual_roster_preserves_distinct_kits_and_alt_resources(self):
        catalog = self.equipment_catalog()
        kits = [
            {'family': 'american', 'slots': {'primary': 9, 'secondary': 6, 'pistol': 22, 'grenade': 34}},
            {'family': 'italian', 'slots': {'primary': 1, 'secondary': 2, 'pistol': 21, 'grenade': 32}},
        ]
        result = roster_resources(catalog, kits, {'sp_ally': 'us_inf'})
        self.assertEqual(result['kits'][1]['weapons']['grenade'], 'land_mine')
        self.assertEqual(result['kits'][0]['weapons']['grenade'], 'smokegrenade')
        self.assertIn('mg30cal_de', result['weapons'])
        self.assertIn('xmodel/v_us_air_p47', result['required_server_models'])
        self.assertNotIn('xmodel/vehicle_plane_stuka', result['required_server_models'])
        self.assertIn('xmodel/viewmodel_30cal_z', result['required_media_models'])
        self.assertNotIn('xmodel/viewmodel_30cal_z', result['required_server_models'])
        self.assertEqual(len(result['required_server_models']), len(set(result['required_server_models'])))

    def test_original_unavailable_family_and_bad_slots_fail_before_planning(self):
        catalog = self.equipment_catalog()
        with self.assertRaisesRegex(ValueError, 'active original campaign menu'):
            roster_resources(catalog, [{'family': 'polish', 'slots': {}}])
        with self.assertRaisesRegex(ValueError, 'all four slots'):
            roster_resources(catalog, [{'family': 'american', 'slots': {'primary': 9}}])
        with self.assertRaisesRegex(ValueError, 'Unavailable menu choice'):
            roster_resources(catalog, [{'family': 'british', 'slots': {'primary': 9, 'secondary': 0, 'pistol': 0, 'grenade': 0}}])
        with self.assertRaisesRegex(ValueError, 'one to four'):
            roster_resources(catalog, [])

    def test_aircraft_comes_from_host_world_and_preserves_original_special_cases(self):
        self.assertEqual(chosen_aircraft({'sp_ally': 'uk_sas'}), 'v_br_air_spitfire')
        self.assertEqual(chosen_aircraft({'campaign': 'american', 'map': 'gfm_omaha'}), 'vehicle_plane_stuka')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            chosen_aircraft({'campaign': 'italian'})

    def test_model_budget_deduplicates_exact_names_and_never_expands_byte_capacity(self):
        baseline = ['xmodel/model_' + str(n) for n in range(254)]
        fit = budget(baseline, ['MODEL_1', 'xmodel/model_254'])
        self.assertEqual(fit['total'], 255)
        self.assertEqual(fit['status'], 'FITS_MODEL_TABLE_ONLY')
        overflow = budget(baseline, ['model_254', 'model_255'])
        self.assertEqual(overflow['status'], 'OVER_BUDGET')
        self.assertEqual(overflow['remaining'], -1)

    def sample(self):
        return b'''#include "ui/menudef.h"
{
 // menuDef { name main } -- ignored comment
 menuDef {
  /* name ignored */ name "main"
  itemDef { name missionselect text "Keep {this}"
   cvarTest "cl_paused" showCvar { "0" }
   action { open missionselect; } }
  itemDef { name order cvarTest "sp_order" showCvar { "0" } }
  // cvarTest "cl_paused" showCvar { "0" }
 }
 menuDef { name options itemDef { name video action { exec "vid_restart"; } } }
}
'''

    def test_preserves_mod_controls_and_only_rewrites_pause_predicates(self):
        output = patch.transform_menu(self.sample(), button='itemDef { name coop }', popup='menuDef { name coop_popmenu }').decode()
        self.assertIn('name missionselect text "Keep {this}"', output)
        self.assertIn('action { open missionselect; }', output)
        self.assertIn('cvarTest "ui_coop_paused" hideCvar { "1" }', output)
        self.assertIn('cvarTest "sp_order" showCvar { "0" }', output)
        self.assertIn('// cvarTest "cl_paused" showCvar { "0" }', output)
        self.assertEqual(len(patch.blocks(output, 'menuDef')), 3)
        self.assertEqual(uncomment(output).count('name coop_popmenu'), 1)

    def test_does_not_nest_popup_inside_main(self):
        text = patch.transform_menu(self.sample(), button='itemDef { name coop }', popup='menuDef { name coop_popmenu }').decode()
        menus = patch.blocks(text, 'menuDef')
        first = text[menus[0][0]:menus[0][2]]
        self.assertIn('name coop', first)
        self.assertNotIn('name coop_popmenu', first)
        self.assertGreater(menus[-1][0], menus[1][2])

    def test_repatch_or_broken_layout_is_rejected(self):
        transformed = patch.transform_menu(self.sample())
        with self.assertRaisesRegex(ValueError, 'already patched'):
            patch.transform_menu(transformed)
        with self.assertRaisesRegex(ValueError, 'Unbalanced'):
            patch.transform_menu(self.sample()[:-4])

    def test_unknown_package_rejected_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            source, dest = Path(d) / 'source.pk3', Path(d) / 'patch.pk3'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('ui/main.menu', self.sample())
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Unknown'):
                patch.build(source, dest, 'sp_improved')
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(dest.exists())

    def test_known_revision_build_is_deterministic_and_not_gameplay_certificate(self):
        profile = 'sp_improved'
        previous = patch.MENU_HASHES[profile]
        try:
            patch.MENU_HASHES[profile] = hashlib.sha256(self.sample()).hexdigest()
            with tempfile.TemporaryDirectory() as d:
                source = Path(d) / 'source.pk3'
                with zipfile.ZipFile(source, 'w') as z:
                    z.writestr('ui/main.menu', self.sample())
                    z.writestr('maps/mission.gsc', b'do_not_copy_originals();')
                a, b = Path(d) / 'a.pk3', Path(d) / 'b.pk3'
                result = patch.build(source, a, profile)
                patch.build(source, b, profile)
                self.assertEqual(a.read_bytes(), b.read_bytes())
                self.assertFalse(result['runtime_verified'])
                with zipfile.ZipFile(a) as z:
                    self.assertNotIn('maps/mission.gsc', z.namelist())
        finally:
            patch.MENU_HASHES[profile] = previous

    def test_shared_air_resources_preserve_original_choice_costs_and_world_actions(self):
        source = r'''main() {
          grenade = level.player getweaponslotweapon("grenade");
          switch (grenade) {
            case "land_mine": level.mine = "keep-original-mine"; break;
            case "smokegrenade":
              switch (getcvar("sp_ally")) {
                case "us_inf": level.stuka_type = "xmodel/v_us_air_p47"; break;
                default: level.stuka_type = "xmodel/vehicle_plane_stuka"; break;
              }
              level._effect["firetrail"] = loadfx("fx/map_bomber/fire_trail_fighter");
              break;
          }
          thread Check_Grenades();
        }
        Airstrike(smoke) {
          org = spawn("script_origin", smoke.origin);
          org linkto(smoke);
          while (isdefined(smoke)) { wait .05; }
          Bomber(org); org delete();
        }
        Bomber(target) {
          wait (22 + randomfloat(2));
          level.stuka_num++;
          thread playSoundinSpace(level.bomber_call, level.player.origin);
          radiusDamage(target.origin, 300, 350, 10);
        }
        MissionCamera() { level.player setorigin((1,2,3)); }
        Reload() { wait 180; }
        '''
        result = patch.transform_uf_support(source)
        a, b = patch.function_span(result, 'main')
        self.assertLess(result[a:b].index('Coop_InitAirResources'), result[a:b].index('switch (grenade)'))
        self.assertIn('case "land_mine": level.mine = "keep-original-mine"; break;', result)
        a, b = patch.function_span(result, 'Coop_InitAirResources')
        self.assertIn('switch (getcvar("sp_ally"))', result[a:b])
        self.assertIn('level.coop_air_resources_ready = true', result[a:b])
        self.assertIn('caller = Coop_GrenadeOwner(smoke)', result)
        self.assertIn('Bomber(org, caller)', result)
        self.assertIn('radio_origin = target.origin', result)
        self.assertIn('if (isdefined(caller)) radio_origin = caller.origin', result)
        self.assertIn('level.stuka_num++', result)
        self.assertIn('wait (22 + randomfloat(2))', result)
        self.assertIn('radiusDamage(target.origin, 300, 350, 10)', result)
        self.assertIn('MissionCamera() { level.player setorigin((1,2,3)); }', result)
        self.assertIn('Reload() { wait 180; }', result)

    def test_air_precache_covers_every_plane_option_and_both_weather_fx(self):
        catalog = json.loads((patch.ROOT / 'campaign_patches/uf_air_assets.json').read_text())
        helper = (patch.ROOT / 'campaign_patches/uf_binocular_players.gsc').read_text()
        a, b = patch.function_span(helper, 'Coop_PrecacheAirAssets')
        body = uncomment(helper[a:b])
        for plane in ('v_us_air_p47', 'v_br_air_spitfire', 'v_rs_air_il2', 'vehicle_plane_stuka'):
            self.assertIn('xmodel/'+plane, catalog)
            self.assertIn('precacheModel("xmodel/'+plane+'")', body)
        for asset in catalog:
            if asset.startswith('fx/'):
                self.assertIn('loadfx("'+asset+'")', body)
        self.assertIn('precacheItem("smokegrenade")', body)
        self.assertNotIn('giveweapon', body.lower())
        self.assertNotIn('Bomber(', body)

    def test_support_result_requires_both_world_scenario_and_real_client_checks(self):
        report = {'status': 'NOT_RUN', 'requested_airstrike': True,
                  'airstrike': 'PASS_actual_owner_cost_plane_original_impact'}
        self.assertEqual(final_probe_status(0, report), 'PASS')
        self.assertEqual(final_probe_status(1, report), 'FAIL')
        report['airstrike'] = 'TIMEOUT'
        self.assertEqual(final_probe_status(0, report), 'FAIL')
        del report['airstrike']
        self.assertEqual(final_probe_status(0, report), 'FAIL')
        self.assertEqual(final_probe_status(0, {'status': 'PASS', 'requested_mg_deployment': True}), 'FAIL')
        artillery = {'status': 'NOT_RUN', 'requested_artillery': True,
                     'artillery': 'PASS_native_cost_cooldown_actor_refill'}
        self.assertEqual(final_probe_status(0, artillery), 'FAIL')
        artillery['artillery_projectiles'] = 'PASS_actual_remote_native_missiles'
        self.assertEqual(final_probe_status(0, artillery), 'PASS')

    def test_brolio_alias_preserves_item_and_bsp_and_requires_exact_sources(self):
        entries = {'maps/brolio_assault.bsp': b'original BSP entity',
                   'weapons/sp/greaser': b'worldModel weapon_greasegun',
                   'xmodel/weapon_greasegun': b'owned canonical model'}
        names = ('UF_BROLIO_BSP_HASH', 'UF_GREASER_HASH', 'UF_GREASE_MODEL_HASH')
        old = [getattr(patch, name) for name in names]
        try:
            for name, value in zip(names, entries.values()): setattr(patch, name, hashlib.sha256(value).hexdigest())
            with tempfile.TemporaryDirectory() as directory:
                package = Path(directory)/'uf.pk3'
                with zipfile.ZipFile(package, 'w') as archive:
                    for name, value in entries.items(): archive.writestr(name, value)
                before = package.read_bytes()
                with zipfile.ZipFile(package) as archive:
                    aliases = patch.uf_asset_aliases(archive)
                    self.assertEqual(aliases, [('xmodel/world_greasegun', b'owned canonical model')])
                    patch.UF_GREASER_HASH = '0'*64
                    with self.assertRaisesRegex(ValueError, 'Unknown United Fronts Brolio'):
                        patch.uf_asset_aliases(archive)
                self.assertEqual(package.read_bytes(), before)
        finally:
            for name, value in zip(names, old): setattr(patch, name, value)

    def test_shared_trigger_package_does_not_depend_on_variant_asset_aliases(self):
        data = b'activate() { if (other == level.player) perform_once(); }'
        old = patch.TRIGGER_PATCHES
        patch.TRIGGER_PATCHES = {'maps/example.gsc': ('activate', r'other\s*==\s*level\.player',
            'maps\\\\_coop_players::is_player(other)', {hashlib.sha256(data).hexdigest()})}
        try:
            with tempfile.TemporaryDirectory() as directory:
                game = Path(directory); (game/'Main').mkdir()
                with zipfile.ZipFile(game/'Main/pak0.pk3', 'w') as archive:
                    archive.writestr('maps/example.gsc', data)
                output = game/'shared.pk3'
                patch.build_trigger_patch(game, output, 'cod1')
                with zipfile.ZipFile(output) as archive:
                    self.assertIn(b'perform_once()', archive.read('maps/example.gsc'))
                    self.assertIn('maps/_coop_players.gsc', archive.namelist())
                    self.assertNotIn('xmodel/world_greasegun', archive.namelist())
        finally:
            patch.TRIGGER_PATCHES = old

    def test_resource_ranking_reads_only_reviewed_bsp_entity_lump(self):
        entities = b'{"model" "xmodel/real"} {"model" "*2"} {"model" "xmodel/real"}'
        header = bytearray(8+33*8)
        header[:8] = b'IBSP'+struct.pack('<I', 59)
        struct.pack_into('<II', header, 8+29*8, len(entities), len(header))
        data = bytes(header)+entities+b'{"model" "xmodel/not-in-entity-lump"}'
        self.assertEqual(entity_models(data), ['xmodel/real'])
        with self.assertRaisesRegex(ValueError, 'unreviewed BSP'):
            entity_models(b'IBSP'+struct.pack('<I', 60)+data[8:])
        struct.pack_into('<II', header, 8+29*8, 99999, len(header))
        with self.assertRaisesRegex(ValueError, 'invalid BSP'):
            entity_models(bytes(header)+entities)

    def test_selected_world_candidate_keeps_original_availability_and_actor_workers(self):
        helper = (patch.ROOT/'campaign_patches/uf_binocular_players.gsc').read_text()
        source = 'main() { Coop_InitAirResources(); switch(grenade) { case "smokegrenade": Coop_InitAirResources(); break; } }\n'+helper
        result = patch.select_uf_world_resources(source)
        for name in ('Coop_PrecacheMountModels', 'Coop_PrecacheAirAssets', 'Coop_InitMineResources'):
            a, b = patch.function_span(result, name)
            self.assertNotIn('precacheItem(', uncomment(result[a:b]))
            self.assertNotIn('precacheModel(', uncomment(result[a:b]))
        a, b = patch.function_span(result, 'main')
        self.assertIn('Coop_InitReachableAirResources()', result[a:b])
        self.assertIn('case "smokegrenade": Coop_InitAirResources(); break;', result[a:b])
        a, b = patch.function_span(source, 'Coop_GrenadeOwner')
        c, d = patch.function_span(result, 'Coop_GrenadeOwner')
        self.assertEqual(source[a:b], result[c:d])
        self.assertIn('players[i] getweaponslotweapon("grenade")', result)
        self.assertIn('getentarray("weapon_smokegrenade", "classname")', result)
        self.assertIn('level.mine = "xmodel/gamemodel_land_mine"', result)
        self.assertNotIn('takeweapon(', result)
        self.assertNotIn('giveweapon(', result)

    def test_inventory_skips_commented_transitions_and_records_dynamic_edges(self):
        source = b'''// missionSuccess("wrong", false);
        /* level.player usebuttonpressed(); */
        level.player usebuttonpressed();
        missionSuccess("actual", true);
        changelevel(nextmap[0], true);
        switch (getcvar("mapname")) {
          case "first": nextmap[0] = "second"; nextmap[1] = "alternate"; break;
        }
        '''
        result = analyze_script('maps/test.gsc', source, 'test.pk3')
        self.assertEqual(result['assumptions']['host_use_gate']['count'], 1)
        self.assertEqual([t['target'] for t in result['transitions']], ['actual', None])
        self.assertEqual([e['target'] for e in result['dispatch_edges']], ['second', 'alternate'])
        self.assertEqual([e['branch'] for e in result['dispatch_edges']], [0, 1])

    def test_uf_worker_rewrites_only_reviewed_functions(self):
        source = b'''main() { thread Infinite_Ammo(); thread Binoculars_Ammo(); thread Trigger_Mount(); }
        WorldAction() { level.player setorigin((0,0,0)); level.stockpile = 99; }
        Binoculars_Ammo() {
          level notify("binocs off"); level endon("binocs off");
          current = level.player getCurrentWeapon(); level.stockpile = 3;
          thread Reload(3);
        }
        Reload(currentammo) { level endon("infinite ammo"); level.player setWeaponSlotAmmo("pistol", level.stockpile); }
        Infinite_Ammo() { level.player giveMaxAmmo("thompson"); }
        Check_Grenades() {
          level.player thread PlantMine();
          grenades[i].active = 1;
          grenades[i] delete();
        }
        PlantMine() { level.player thread ExplodeMine(placedMines); }
        getPlant() { temp = level.player; temp = level.player; temp = level.player; return temp; }
        Trigger_Mount() {
          thread Trigger_Stance();
          while (isAlive(level.player)) {
            stance = Get_Stance();
            level.mount_mg = spawn("trigger_mount", (0,0,0), 0);
            level.mount_mg = spawn("trigger_mount", (0,0,0), 1);
          }
        }
        Trigger_Stance() {
          stance = Get_Stance();
          level.mount_mg = spawn("trigger_mount", (0,0,0), 0);
          level.mount_mg = spawn("trigger_mount", (0,0,0), 1);
        }
        Get_Stance() { return level.player getstance(); }
        BipodPlaceable() { stance = Get_Stance(); level.mount_pose = 0; return true; }
        '''
        old = patch.UF_WEAPONS_HASH
        try:
            patch.UF_WEAPONS_HASH = hashlib.sha256(source).hexdigest()
            transformed = patch.transform_uf_binoculars(source).decode()
        finally:
            patch.UF_WEAPONS_HASH = old
        world_a, world_b = patch.function_span(transformed, 'WorldAction')
        self.assertIn('level.player setorigin', transformed[world_a:world_b])
        self.assertIn('level.stockpile = 99', transformed[world_a:world_b])
        for name in ('Binoculars_Ammo', 'Reload', 'Infinite_Ammo'):
            a, b = patch.function_span(transformed, name)
            self.assertNotIn('level.player', uncomment(transformed[a:b]))
            self.assertNotIn('level.stockpile', uncomment(transformed[a:b]))
        self.assertIn('self thread Reload(3)', transformed)
        self.assertIn('self.coop_binocular_stockpile', transformed)
        self.assertIn('getentarray("player", "classname")', transformed)
        self.assertIn('player thread Infinite_Ammo()', transformed)
        self.assertIn('mine_owner = Coop_GrenadeOwner(grenades[i])', transformed)
        self.assertIn('mine_owner thread PlantMine()', transformed)
        self.assertIn('self thread ExplodeMine(placedMines)', transformed)
        self.assertEqual(transformed.count('temp = spawnstruct();'), 3)
        self.assertIn('getcvarint("coop_owner_bank_count")', transformed)
        self.assertIn('count > 128', transformed)
        self.assertIn('encoded >= base && encoded < base + 4', transformed)
        self.assertIn('ownernum = encoded - base', transformed)
        self.assertIn('gettime() - grenade.coop_owner_observed', transformed)
        for name in ('Trigger_Mount', 'Trigger_Stance', 'Get_Stance', 'BipodPlaceable'):
            a, b = patch.function_span(transformed, name)
            active = uncomment(transformed[a:b])
            self.assertNotIn('level.player', active)
            self.assertNotIn('level.mount_mg', active)
            self.assertNotIn('level.mount_pose', active)
        self.assertIn('spawntriggermount(self.origin +', transformed)
        self.assertIn('trigger thread Coop_MountLifetime()', transformed)
        self.assertNotIn('Coop_QAProbe', transformed)
        self.assertNotIn('Coop_QAMovieProbe', transformed)

    def test_unknown_uf_gameplay_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown United Fronts weapons'):
            patch.transform_uf_binoculars(b'main() {}')

    def test_uf_pathfinder_precaches_existing_alias_models_without_changing_mission(self):
        source = b'''main() {
          precacheModel("xmodel/gear_US_helmet_82");
          precacheModel("xmodel/helmet_us_82");
          precacheModel("xmodel/c47");
          level.player.threatbias = -150;
          thread original_parachute_sequence();
        }'''
        old = patch.UF_PATHFINDER_HASH
        try:
            patch.UF_PATHFINDER_HASH = hashlib.sha256(source).hexdigest()
            transformed = patch.transform_uf_pathfinder_assets(source).decode()
        finally:
            patch.UF_PATHFINDER_HASH = old
        for model in patch.UF_HELMET_MODELS:
            self.assertEqual(transformed.count('precacheModel("' + model + '")'), 1)
        self.assertNotIn('"xmodel/helmet_us_82"', transformed)
        self.assertNotIn('"xmodel/gear_US_helmet_82"', transformed)
        self.assertIn('precacheModel("xmodel/c47");', transformed)
        self.assertIn('level.player.threatbias = -150;', transformed)
        self.assertIn('thread original_parachute_sequence();', transformed)

    def test_unknown_uf_pathfinder_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown United Fronts pathfinder'):
            patch.transform_uf_pathfinder_assets(b'unknown')

    def test_uf_mg_precache_uses_native_weapon_media_without_world_viewmodels(self):
        helper = (patch.ROOT / 'campaign_patches/uf_binocular_players.gsc').read_text()
        start, end = patch.function_span(helper, 'Coop_PrecacheMountModels')
        body = uncomment(helper[start:end])
        items = re.findall(r'precacheItem\("([^"]+)"\)', body)
        weapons = json.loads((patch.ROOT / 'campaign_patches/uf_mg_weapons.json').read_text())
        models = json.loads((patch.ROOT / 'campaign_patches/uf_mount_models.json').read_text())
        self.assertEqual(set(items), {'mg30Cal', 'mg30cal_de', 'mg34', 'mg34_de', 'mg42', 'mg42_de', 'dp28'})
        self.assertEqual(set(items), set(weapons))
        self.assertNotIn('precacheModel', body)
        self.assertEqual(len(models), 13)
        self.assertTrue(all(len(entry['sha256']) == 64 for entry in weapons.values()))
        self.assertIn('xmodel/viewmodel_30cal_z', models)
        self.assertIn('xmodel/viewmodel_hands_new', models)

    def test_uf_resource_precache_precedes_random_loadout_and_is_not_qa_only(self):
        source = b'main() { level.player = player; maps\\_UF_loadout::give_loadout(); }'
        old = patch.UF_LOAD_HASH
        try:
            patch.UF_LOAD_HASH = hashlib.sha256(source).hexdigest()
            transformed = patch.transform_uf_load(source, qa=False).decode()
        finally:
            patch.UF_LOAD_HASH = old
        self.assertLess(transformed.index('Coop_PrecacheMountModels'), transformed.index('give_loadout'))
        self.assertLess(transformed.index('Coop_InitMineResources'), transformed.index('give_loadout'))
        self.assertNotIn('Coop_QA', transformed)

    def test_trigger_patch_preserves_single_world_action_and_camera_protagonist(self):
        path = 'maps/brecourt.gsc'
        source = b'''explosives_objective_wait() {
          while (1) {
            trigger waittill("trigger",other);
            if (other == level.player) {
              level.moody detach("pack", "tag");
              thread got_explosives();
              break;
            }
          }
        }
        camera_scene() { level.player setorigin(scene.origin); }
        '''
        old = patch.TRIGGER_PATCHES[path]
        try:
            patch.TRIGGER_PATCHES[path] = (*old[:3], {hashlib.sha256(source).hexdigest()})
            transformed = patch.transform_trigger(path, source).decode()
        finally:
            patch.TRIGGER_PATCHES[path] = old
        self.assertIn(r'maps\_coop_players::is_player(other)', transformed)
        self.assertEqual(transformed.count('thread got_explosives();'), 1)
        self.assertEqual(transformed.count('break;'), 1)
        self.assertIn('level.player setorigin(scene.origin)', transformed)

    def test_unknown_trigger_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown mission script'):
            patch.transform_trigger('maps/brecourt.gsc', b'cannot match original')

    def test_ai_melee_uses_actual_enemy_stance_for_every_player(self):
        path = 'animscripts/melee.gsc'
        source = b'''MeleeCombat(reason) {
          player = animscripts\\utility::GetPlayer();
          if (self.enemy == player) { enemypose = player getstance(); }
          else { enemypose = self.enemy.anim_pose; }
          self setanimknoball(anim, body, 1, .05, 1);
        }'''
        old = patch.TRIGGER_PATCHES[path]
        try:
            patch.TRIGGER_PATCHES[path] = (*old[:3], {hashlib.sha256(source).hexdigest()})
            transformed = patch.transform_trigger(path, source).decode()
        finally:
            patch.TRIGGER_PATCHES[path] = old
        self.assertIn(r'maps\_coop_players::is_player(self.enemy)', transformed)
        self.assertIn('enemypose = self.enemy getstance();', transformed)
        self.assertIn('else { enemypose = self.enemy.anim_pose; }', transformed)
        self.assertIn('self setanimknoball(anim, body, 1, .05, 1);', transformed)

    def test_mainline_berlin_preserves_objectives_and_original_movie(self):
        source = b'''objectives_wait2() {
          level waittill("all_objectives_complete");
          if (level.missionfailed) return;
          setcvar("nextmap", "map credits");
          cinematic("cod_end.roq");
        }
        '''
        old = patch.MAINLINE_BERLIN_HASH
        try:
            patch.MAINLINE_BERLIN_HASH = hashlib.sha256(source).hexdigest()
            transformed = patch.transform_mainline_berlin(source).decode()
        finally:
            patch.MAINLINE_BERLIN_HASH = old
        self.assertIn('level waittill("all_objectives_complete")', transformed)
        self.assertIn('if (level.missionfailed) return', transformed)
        self.assertIn('"map coop_cod1_credits"', transformed)
        self.assertIn('else\n            setcvar("nextmap", "map credits")', transformed)
        self.assertEqual(transformed.count('cinematic("cod_end.roq")'), 1)

    def test_mainline_credit_completion_keeps_waits_and_targets_uo(self):
        source = b'''endLevel() {
          flag_wait("credits done");
          wait 0.5;
          missionSuccess("training", false);
        }
        unrelated() { missionSuccess("training", false); }
        '''
        old = patch.MAINLINE_CREDITS_HASH
        try:
            patch.MAINLINE_CREDITS_HASH = hashlib.sha256(source).hexdigest()
            transformed = patch.transform_mainline_credits(source).decode()
        finally:
            patch.MAINLINE_CREDITS_HASH = old
        self.assertIn('flag_wait("credits done")', transformed)
        self.assertIn('missionSuccess("bastogne1", false)', transformed)
        self.assertIn('unrelated() { missionSuccess("training", false); }', transformed)

    def test_unknown_mainline_sources_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown SP Improved Berlin'):
            patch.transform_mainline_berlin(b'unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown original CoD credits'):
            patch.transform_mainline_credits(b'unknown')

    def test_mainline_sound_aliases_keep_only_original_credit_rows(self):
        source = b'name,file,loadspec\nshared,shared.wav,\nother,other.wav,berlin\n' + b''.join(
            ('credit%d,c%d.wav,dawnville credits\n' % (i, i)).encode() for i in range(4))
        entries = dict(patch.mainline_sound_entries(source))
        aliases = entries['soundaliases/coop_cod1_credits.csv'].decode()
        self.assertNotIn('shared.wav', aliases)
        self.assertNotIn('other.wav', aliases)
        self.assertNotIn('dawnville', aliases)
        self.assertEqual(aliases.count('coop_cod1_credits'), 4)
        self.assertIn(b'iw_sound.csv', entries['soundloadspecs/sp/coop_cod1_credits.csv'])
        with self.assertRaisesRegex(ValueError, 'sound selection changed'):
            patch.mainline_sound_entries(b'name,file,loadspec\ncredit,c.wav,credits\n')

    def test_inventory_records_ai_parameters_without_claiming_effectiveness(self):
        result = analyze_script('aitype/ally.gsc', b'main() {self.bravery=55; self.accuracy=0.4;}', 'mod.pk3')
        self.assertEqual(result['ai_fields'], {'bravery':55.0,'accuracy':0.4})

    def test_probe_scorer_uses_engine_log_byte_offsets(self):
        from qa_campaign_probe import read_new_log
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'console.log'
            path.write_bytes(b'old line\r\n' * 100)
            offset = path.stat().st_size
            with path.open('ab') as stream:
                stream.write(b'cvar set coop_uf_probe_result FAIL_ammo_isolation_or_mounts\r\n')
            self.assertIn('coop_uf_probe_result FAIL_', read_new_log(path, offset))


if __name__ == '__main__':
    unittest.main()
