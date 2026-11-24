import hashlib
import importlib.util
import json
import re
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import build_campaign_patch as patch
from campaign_inventory import analyze_script, uncomment
from qa_campaign_probe import final_probe_status
from qa_campaign_resources import entity_models, summarize_references
from uf_equipment_catalog import menu_choices, roster_resources, chosen_aircraft, budget
from qa_uf_kits import kit_fixture, selection_ack_matches, cgame_selection_matches, preservation_publication_matches


class CampaignPatchTests(unittest.TestCase):
    def test_selection_ack_cannot_reuse_old_world_ticket_even_with_same_sequence(self):
        values = {'coop_select_1_status':'APPLIED'}
        for key,value in {'seq':'1','ticket':'7','world':'22','session_a':'5','session_b':'9','session_c':'1'}.items():
            values['coop_select_1_'+key]=value;values['coop_select_1_ack_'+key]=value
        self.assertTrue(selection_ack_matches(values,1))
        values['coop_select_1_ack_world']='21'
        self.assertFalse(selection_ack_matches(values,1))
        values['coop_select_1_ack_world']='22';values['coop_select_1_ack_ticket']='6'
        self.assertFalse(selection_ack_matches(values,1))

    def test_preservation_proof_requires_current_owner_world_and_explicit_native_decision(self):
        values={'coop_spawn_session_a':'12','coop_spawn_session_b':'34','coop_spawn_session_c':'1',
                'coop_spawn_ticket_1':'8','coop_spawn_world':'56',
                'coop_inventory_1_state':'PRESERVED','coop_inventory_1_identity':'12|34|1|1|8|56'}
        self.assertTrue(preservation_publication_matches(values,1,'PRESERVED'))
        for field,value in [('coop_inventory_1_state','WAIT'),('coop_inventory_1_identity','12|34|1|1|7|56'),
                            ('coop_inventory_1_identity','12|34|1|1|8|55'),('coop_inventory_1_identity','12|34|1|2|8|56'),
                            ('coop_spawn_ticket_1','0'),('coop_spawn_session_c','4'),('coop_spawn_world','056')]:
            with self.subTest(field=field,value=value):
                invalid=dict(values);invalid[field]=value
                self.assertFalse(preservation_publication_matches(invalid,1,'PRESERVED'))
        self.assertFalse(preservation_publication_matches(values,1,'FRESH'))
        self.assertFalse(preservation_publication_matches({},1,'PRESERVED'))
        values['coop_inventory_1_state']='FRESH'
        self.assertTrue(preservation_publication_matches(values,1,'FRESH'))

    def test_selected_weapon_needs_actual_own_snapshot_and_both_local_states(self):
        host={'weapon':98,'selected_weapon_name':'springfield'}
        local={'cgame':{'snapshot_clientnum':1,'snapshot_server_time':2000,'desired_name':'springfield','predicted_name':'springfield','snapshot_name':'springfield'}}
        self.assertTrue(cgame_selection_matches(host,local,1))
        local['cgame']['snapshot_clientnum']=0
        self.assertFalse(cgame_selection_matches(host,local,1))
        local['cgame']['snapshot_clientnum']=1;local['cgame']['desired_name']='none'
        self.assertFalse(cgame_selection_matches(host,local,1))
    def test_four_native_fixture_uses_legal_individual_roles_and_does_not_fire_unmounted_mg(self):
        catalog = self.equipment_catalog()
        kits, inventory, fired = kit_fixture(4)
        resources = roster_resources(catalog, [{'family': 'american', 'slots': kit} for kit in kits], {'sp_ally': 'us_inf'})
        self.assertEqual(len(resources['required_server_models']), 23)
        self.assertEqual(len(resources['required_media_models']), 39)
        self.assertEqual(inventory[0]['primary'], 'mg30cal')
        self.assertEqual(inventory[2]['primary'], 'bazooka')
        self.assertEqual(fired, ['primaryb', 'primary', 'primaryb', 'primary'])
        self.assertEqual(len({json.dumps(kit,sort_keys=True) for kit in kits}), 4)

    def test_actor_kit_adapter_is_opt_in_and_preserves_original_actor_give_ammo_calls(self):
        import inspect
        self.assertIs(inspect.signature(patch.build).parameters['qa_kits'].default, False)
        source = b'''process_weapon_American(weaponcvar,type) {
          weapon_num = getcvarint(weaponcvar);
          level.player giveweapon("m1garand"); thread debug_console("kept"); level.player switchToWeapon("m1garand");
        }
        refill_ammo() { level.player giveStartAmmo("m1garand"); }
        '''
        catalog = {'sources': [{'member': 'maps/_UF_loadout.gsc', 'sha256': hashlib.sha256(source).hexdigest()}],
                   'families': {'american': {'active_campaign_menu': True, 'enum': {'0': None, '3': 'm1garand'},
                    'menu_slots': {slot: {'choices': {'0': {'weapon': None}, '3': {'weapon': 'm1garand'}}} for slot in ('primary','secondary','pistol','grenade')}}}}
        helper = (patch.ROOT/'campaign_patches/uf_starting_kits.gsc').read_text()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'campaign_patches').mkdir()
            (root/'campaign_patches/uf_equipment_catalog.json').write_text(json.dumps(catalog))
            (root/'campaign_patches/uf_starting_kits.gsc').write_text(helper)
            with mock.patch.object(patch, 'ROOT', root):
                result = patch.uf_actor_kit_adapter(source).decode()
                with self.assertRaisesRegex(ValueError, 'Unknown'):
                    patch.uf_actor_kit_adapter(source+b'changed')
        self.assertIn('self giveweapon("m1garand")', result)
        self.assertIn('self giveStartAmmo("m1garand")', result)
        self.assertIn('self Coop_SelectWeapon("m1garand", context);', result)
        start,end=patch.function_span(result,'Coop_Process_american')
        self.assertNotIn('switchToWeapon',uncomment(result[start:end]))
        self.assertIn('thread maps\\_UF_loadout::debug_console(', result)
        self.assertNotIn('level.player', result)
        self.assertNotIn('getcvarint(weaponcvar)', result)
        self.assertIn('coop_qa_kit_applied_', result)
        self.assertIn('BLOCKED_ORIGINAL_SPECIAL_SCRIPT', result)

    def test_cold_save_native_proof_precedes_external_receipt_and_never_refills_preserved_actor(self):
        text = (patch.ROOT/'campaign_patches/uf_starting_kits.gsc').read_text()
        start,end = patch.function_span(text,'WatchPlayers')
        watch = uncomment(text[start:end])
        self.assertLess(watch.index('InventoryDisposition('), watch.index('getcvar(identity_key) == native_identity'))
        self.assertLess(watch.index('disposition == "PRESERVED"'), watch.index('ReadHostPlan(false)'))
        begin = watch.index('if (disposition == "PRESERVED")')
        end = watch.index('if (getcvar("coop_qa_kit_', begin)
        preserved = watch[begin:end]
        self.assertIn('setcvar(identity_key, native_identity)', preserved)
        self.assertIn('continue;', preserved)
        for forbidden in ('Apply(', 'Refill', 'giveweapon', 'giveStartAmmo', 'takeallweapons', 'player.coop_kit_epoch =', 'setcvar(key,'):
            self.assertNotIn(forbidden, preserved)
        start,end = patch.function_span(text,'InventoryDisposition')
        boundary = uncomment(text[start:end])
        self.assertIn('published_identity != (identity + "|" + world)', boundary)
        self.assertIn('SpawnIdentity(slot) != identity', boundary)
        self.assertIn('getcvar("coop_spawn_world") != world', boundary)
        self.assertIn('state != "FRESH" && state != "PRESERVED"', boundary)
        start,end = patch.function_span(text,'Apply')
        apply = uncomment(text[start:end])
        self.assertLess(apply.index('InventoryDisposition('), apply.index('takeallweapons'))
        self.assertIn('!= "FRESH") return false;', apply)
        self.assertIn('if (!(player Apply(', watch)

    def test_actor_processors_reject_global_gameplay_coupling_but_keep_resource_union_hints(self):
        safe = '''Coop_Process_american(weapon_num) {
          level.precache_mine = 1; level.precache_plane = 1; self giveweapon("land_mine");
        }
        Coop_RefillOriginal() { self giveStartAmmo("land_mine"); }'''
        self.assertEqual(patch.audit_uf_actor_adapter(safe)['Coop_Process_american'], ['precache_mine', 'precache_plane'])
        for effect in ('setcvar("g_speed", "300");', 'level.faction = "german";', 'game["gaveweapons"] = 1;', 'self setnormalhealth(1);', 'level.precache_plane = 0;'):
            with self.subTest(effect=effect), self.assertRaises(ValueError):
                patch.audit_uf_actor_adapter(safe.replace('self giveweapon("land_mine");', effect))

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
        Moody_GetInjuredMan() {
          if (level.flags["moodydied"] == false) {
            lastnode = scene;
            level.moody waittill("goal");
            while (distance(level.player.origin, level.moodyloc) > 100) wait 1;
            thread got_explosives();
          } else { original_fallback(); }
        }
        '''
        old = patch.TRIGGER_PATCHES[path]
        try:
            patch.TRIGGER_PATCHES[path] = (*old[:3], {hashlib.sha256(source).hexdigest()})
            transformed = patch.transform_trigger(path, source).decode()
        finally:
            patch.TRIGGER_PATCHES[path] = old
        self.assertIn(r'maps\_coop_players::is_player(other)', transformed)
        self.assertEqual(transformed.count('thread got_explosives();'), 2)
        self.assertNotIn('while (distance(level.player.origin, level.moodyloc) > 100) wait 1;', transformed)
        self.assertIn(r'maps\_coop_brecourt_handoff::wait_for_recipient(level.moodyloc, 100)', transformed)
        self.assertIn('level notify("coop_brecourt_handoff_recipient", coop_recipient)', transformed)
        self.assertEqual(transformed.count('Coop_NormalHandoff();'), 1)
        self.assertIn('original_fallback();', transformed)
        self.assertEqual(transformed.count('break;'), 1)
        self.assertIn('level.player setorigin(scene.origin)', transformed)

    def test_normal_brecourt_handoff_requires_native_eligibility_and_keeps_old_core_host_gate(self):
        text=(patch.ROOT/'campaign_patches/brecourt_handoff.gsc').read_text()
        a,b=patch.function_span(text,'identity');identity=uncomment(text[a:b])
        self.assertIn('getcvar("coop_actor_api") != "1"',identity)
        self.assertIn('mode != "HOST"',identity)
        self.assertIn('slot != 0',identity)
        self.assertIn('"solo|" + native_world + "|0"',identity)
        a,b=patch.function_span(text,'eligible');eligible=uncomment(text[a:b])
        self.assertIn('!isalive(actor)',eligible)
        self.assertIn('state != "ELIGIBLE" || published != expected',eligible)
        self.assertIn('getentitynumber()',eligible)
        self.assertNotRegex(eligible,r'health\s*[><=]')
        a,b=patch.function_span(text,'wait_for_recipient');wait=uncomment(text[a:b])
        self.assertIn('while (distance(level.player.origin, location) > radius) wait 1;',wait)
        self.assertIn('return level.player;',wait)
        self.assertIn('actor = nearest_recipient(location, radius)',wait)
        self.assertNotIn('missionSuccess',text)
        self.assertNotIn('objective_state',text)
        self.assertNotIn('setorigin',text.lower())

    def test_unknown_trigger_revision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown mission script'):
            patch.transform_trigger('maps/brecourt.gsc', b'cannot match original')

    def test_pathfinder_preserves_intro_inventory_and_single_shared_use_actions(self):
        source=b'''objectives() {
          trigger waittill("trigger"); objective_state(0,"done");
          trigger = getent("legbag_trigger","targetname");
          trigger waittill("trigger"); flag_set("legbag");
          legbag delete(); trigger delete(); objective_state(1,"done");
        }
        beacon_think(beacon) {
          flag_wait("legbag"); trigger waittill("trigger"); trigger delete();
          flag_set("flares set"); beacon setmodel("xmodel/eureka_beacon");
        }
        parachute_player() { level.player giveWeapon("m1carbine"); level.player switchToWeapon("m1carbine"); level.player unlink(); }
        '''
        path='maps/pathfinder.gsc';old=patch.TRIGGER_PATCHES[path];classic=patch.CLASSIC_PATHFINDER_HASH
        try:
            patch.TRIGGER_PATCHES[path]=(*old[:3],{hashlib.sha256(source).hexdigest()})
            patch.CLASSIC_PATHFINDER_HASH=hashlib.sha256(source).hexdigest()
            result=patch.transform_trigger(path,source).decode()
            with self.assertRaisesRegex(ValueError,'Unknown mission script revision'):
                patch.transform_trigger(path,source.replace(b'flag_set("legbag")',b'flag_set("unknown")'))
        finally:patch.TRIGGER_PATCHES[path]=old;patch.CLASSIC_PATHFINDER_HASH=classic
        self.assertEqual(result.count(r'maps\_coop_mission_use::wait_for_actor(trigger)'),2)
        self.assertEqual(result.count('trigger waittill("trigger")'),1)
        self.assertEqual(result.count('flag_set("legbag")'),1)
        self.assertIn('level.player giveWeapon("m1carbine")',result)
        self.assertIn('level.player switchToWeapon("m1carbine")',result)
        self.assertIn(r'thread maps\_coop_pathfinder_equipment::watch()',result)
        self.assertEqual(result.count('beacon setmodel("xmodel/eureka_beacon")'),1)
        helper=(patch.ROOT/'campaign_patches/mission_use.gsc').read_text()
        self.assertIn('waittill("trigger", actor)',helper)
        self.assertIn(r'maps\_coop_brecourt_handoff::eligible(actor)',helper)
        self.assertIn('actor != level.player',helper)
        self.assertNotIn('giveWeapon',helper)

    def test_pathfinder_classic_recipe_waits_for_fresh_native_owner_and_never_refills_preserved(self):
        text=(patch.ROOT/'campaign_patches/pathfinder_equipment.gsc').read_text()
        a,b=patch.function_span(text,'consider');body=uncomment(text[a:b])
        preserved=body[body.index('if (state == "PRESERVED")'):body.index('if (state != "FRESH"')]
        self.assertNotIn('giveWeapon',preserved)
        self.assertNotIn('takeallweapons',preserved)
        self.assertIn('PRESERVED_NO_GIVE',preserved)
        self.assertLess(body.index('getcvar(native + "identity") != context'),body.index('giveWeapon'))
        self.assertLess(body.index('coop_select_pathfinder_api'),body.index('giveWeapon'))
        self.assertEqual(re.findall(r'giveWeapon\("([^"]+)"\)',body),['m1carbine','thompson','colt','fraggrenade'])
        self.assertLess(body.index('coop_select_pathfinder_api'),body.index('takeallweapons'))
        self.assertLess(body.index('takeallweapons'),body.index('giveWeapon'))
        a,b=patch.function_span(text,'request_selection');request=uncomment(text[a:b])
        self.assertIn('"source","pathfinder_initial"',request)
        self.assertIn('"epoch",0',request)
        self.assertTrue(request.rstrip().endswith('setcvar(key + "seq",sequence + 1);'))

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


    def test_axis_weapon_loop_gets_a_bounded_yield(self):
        package = patch.ROOT / 'run/campaign-host/UnitedFronts/ZUnitedFronts_1.1_beta.pk3'
        if not package.is_file():
            self.skipTest('Owned original UF package unavailable; pinned source check only')
        with zipfile.ZipFile(package) as source:
            original = source.read('maps/_UF_mod.gsc')
        patched = patch.uf_actor_weapon_loop_yield(original)
        self.assertEqual(original.count(b'for (i=0;i<axis.size;i++)'),
                         patched.count(b'for (i=0;i<axis.size;i++)'))
        self.assertIn(b'chunk = 0;', patched)
        self.assertEqual(patched.count(b'if (chunk == 8) { chunk = 0; wait 0; }'), 1)
        # The yield sits inside the loop, after its opening brace.
        loop = patched.index(b'\t\tfor (i=0;i<axis.size;i++)\r\n\t\t{\r\n')
        self.assertLess(loop, patched.index(b'if (chunk == 8) { chunk = 0; wait 0; }'))
        with self.assertRaisesRegex(ValueError, 'Unknown UF axis weapon loop revision'):
            patch.uf_actor_weapon_loop_yield(
                b'\t\tfor (i=0;i<axis.size;i++)\r\n\t\t{\r\n'
                b'\t\tfor (i=0;i<axis.size;i++)\r\n\t\t{\r\n')
        # Synthetic build fixtures without the authored script pass through.
        self.assertEqual(patch.uf_actor_weapon_loop_yield(b'main() {}'), b'main() {}')


if __name__ == '__main__':
    unittest.main()
