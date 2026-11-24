import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_uf_fresh_roles import require_body_models,host_plan_receipts_match,argument_parser,owned_game_environment,planned_weapon_cvars,union_extra_cvars,supported_maps,restored_world_rendered,move_with_room,SCRIPTED_HOST_LOADOUT_REARM,SCRIPTED_HOST_FIRE_RELEASE,KNOWN_CONTENT_ERRORS

class FreshRoleBodyOracle(unittest.TestCase):
 def test_cli_all_weapon_media_is_opt_in_and_changes_only_one_native_flag(self):
  required=['--source','/not-accessed','--run','/not-created','--runtime-dir','/not-loaded']
  default=argument_parser().parse_args(required)
  explicit=argument_parser().parse_args(required+['--experimental-all-weapon-media'])
  self.assertFalse(default.experimental_all_weapon_media);self.assertTrue(explicit.experimental_all_weapon_media)
  inherited={'WINEPREFIX':'owned','CODCOOP_QA':'1','CODCOOP_QA_NO_STEAM':'1','CODCOOP_QA_ALL_WEAPON_MEDIA':'1','CODCOOP_QA_BORROW_TREES':'1'}
  old=dict(inherited)
  baseline=owned_game_environment(inherited,all_weapon_media=default.experimental_all_weapon_media)
  changed=owned_game_environment(inherited,all_weapon_media=explicit.experimental_all_weapon_media)
  self.assertEqual(changed,{**baseline,'CODCOOP_QA_ALL_WEAPON_MEDIA':'1'})
  self.assertNotIn('CODCOOP_QA_ALL_WEAPON_MEDIA',baseline);self.assertNotIn('CODCOOP_QA_BORROW_TREES',baseline)
  self.assertEqual(inherited,old)
  self.assertEqual(baseline,{'WINEPREFIX':'owned','CODCOOP_QA':'1','CODCOOP_QA_NO_STEAM':'1','CODCOOP_QA_DEFER_MODELS':'1'})
 def test_cli_plan_union_media_is_opt_in_and_sets_one_flag(self):
  required=['--source','/not-accessed','--run','/not-created','--runtime-dir','/not-loaded']
  default=argument_parser().parse_args(required)
  explicit=argument_parser().parse_args(required+['--experimental-plan-union-media'])
  self.assertFalse(default.experimental_plan_union_media);self.assertTrue(explicit.experimental_plan_union_media)
  self.assertEqual(default.duration,2)
  self.assertEqual(argument_parser().parse_args(required+['--duration','1']).duration,1)
  self.assertEqual(default.checkpoint_reloads,0)
  self.assertEqual(argument_parser().parse_args(required+['--checkpoint-reloads','1']).checkpoint_reloads,1)
  inherited={'WINEPREFIX':'owned','CODCOOP_QA':'1'}
  baseline=owned_game_environment(inherited)
  changed=owned_game_environment(inherited,plan_union_media=explicit.experimental_plan_union_media)
  self.assertEqual(changed,{**baseline,'CODCOOP_QA_PLAN_UNION_MEDIA':'1'})
  self.assertNotIn('CODCOOP_QA_PLAN_UNION_MEDIA',baseline)
 def test_plan_union_uses_native_weapon_names_not_catalog_enums(self):
  import json
  from pathlib import Path
  catalog=json.loads((Path(__file__).parents[1]/'campaign_patches/uf_equipment_catalog.json').read_text())
  kits=[dict(primary=5,secondary=1,pistol=21,grenade=33)]
  values=planned_weapon_cvars(catalog,kits)
  self.assertEqual(values,{'coop_qa_kit_0_primary_weapon':'springfield',
      'coop_qa_kit_0_secondary_weapon':'carbinem1s','coop_qa_kit_0_pistol_weapon':'colt',
      'coop_qa_kit_0_grenade_weapon':'land_mine'})
  self.assertTrue(all(isinstance(value,str) and not value.isdigit() for value in values.values()))
  self.assertEqual(planned_weapon_cvars(catalog,[dict(primary=0)]),{})
  two=planned_weapon_cvars(catalog,[dict(primary=5),dict(primary=9)])
  self.assertEqual(two,{'coop_qa_kit_0_primary_weapon':'springfield','coop_qa_kit_1_primary_weapon':'mg30cal'})
 def test_map_script_union_extras_are_explicit_and_map_scoped(self):
  self.assertEqual(union_extra_cvars('noville'),{'coop_qa_union_extra_0':'thompson28'})
  self.assertEqual(union_extra_cvars('brecourt'),{})
  self.assertEqual(union_extra_cvars('foy'),{})
  # bastogne1 is the map upstream names for the jeep/revive fixes: American,
  # winter 1944 in campaign_patches/uf_world_rules.json, no post-export item
  # registration observed yet.
  self.assertEqual(union_extra_cvars('bastogne1'),{})
 def test_map_choice_is_any_registered_united_fronts_map(self):
  maps=supported_maps()
  self.assertLessEqual({'brecourt','noville','foy','bastogne1','bizerte'},maps)
  self.assertNotIn('not_a_map',maps)
  self.assertEqual(argument_parser().parse_args(['--source','/a','--run','/b','--runtime-dir','/c']).map,'brecourt')
 def test_scripted_host_loadout_rearm_is_named_per_map_only(self):
  self.assertEqual(set(SCRIPTED_HOST_LOADOUT_REARM),{'pegasusnight'})
  self.assertLessEqual(set(SCRIPTED_HOST_LOADOUT_REARM),supported_maps())
  self.assertTrue(all(isinstance(rule,str) and rule for rule in SCRIPTED_HOST_LOADOUT_REARM.values()))
 def test_scripted_host_fire_release_is_bounded_and_named_per_map_only(self):
  self.assertEqual(set(SCRIPTED_HOST_FIRE_RELEASE),{'pegasusnight'})
  self.assertLessEqual(set(SCRIPTED_HOST_FIRE_RELEASE),supported_maps())
  for rule in SCRIPTED_HOST_FIRE_RELEASE.values():
   self.assertGreater(rule['window_seconds'],0)
   self.assertLessEqual(rule['window_seconds'],60)
   self.assertIn('level.player',rule['reason'])
   self.assertIn('peer',rule['reason'])
 def test_known_content_errors_are_exact_and_map_scoped(self):
  self.assertLessEqual(set(KNOWN_CONTENT_ERRORS),supported_maps())
  for map_name,markers in KNOWN_CONTENT_ERRORS.items():
   self.assertTrue(markers,map_name)
   for marker in markers:
    self.assertTrue(marker.startswith("ERROR: Cannot precache '"),marker)
    self.assertTrue(marker.endswith("'") and marker.count("'")==2,marker)
  self.assertEqual(KNOWN_CONTENT_ERRORS['foy'],("ERROR: Cannot precache 'xmodel/c_us_helmet_moody_winter'",
      "ERROR: Cannot precache 'xmodel/weapon_garand'"))
  self.assertNotIn('sicily1',KNOWN_CONTENT_ERRORS)
 def test_restored_world_requires_fresh_snapshots_before_input(self):
  old=[{'snapshot_num':7,'snapshot_time':1000},{'snapshot_num':9,'snapshot_time':2000}]
  self.assertTrue(restored_world_rendered(old,[{'snapshot_num':8,'snapshot_time':1100},{'snapshot_num':10,'snapshot_time':2100}]))
  self.assertFalse(restored_world_rendered(old,[{'snapshot_num':8,'snapshot_time':1100},dict(old[1])]))
  self.assertFalse(restored_world_rendered(old,[{},dict(old[1])]))
  self.assertFalse(restored_world_rendered(old,old[:1]))
 def test_movement_probe_keeps_the_strict_oracle_per_direction(self):
  calls=[]
  def blocked_then_free(host,peer,slot,processes,timeout,action):
   calls.append(action)
   if action=='+forward':raise TimeoutError('host applies remote movement input')
   return 12.5
  action,distance=move_with_room(None,None,2,None,10,move=blocked_then_free)
  self.assertEqual((action,distance),('+back',12.5))
  self.assertEqual(calls,['+forward','+back'])
  calls.clear()
  def never_moves(host,peer,slot,processes,timeout,action):
   calls.append(action);raise TimeoutError('host applies remote movement input')
  with self.assertRaises(TimeoutError) as raised:move_with_room(None,None,2,None,10,move=never_moves)
  self.assertEqual(calls,['+forward','+back','+moveleft','+moveright'])
  self.assertIn('did not move in any walk direction',str(raised.exception))
  def other_failure(host,peer,slot,processes,timeout,action):
   raise TimeoutError('remote player controllable outside a vehicle/cinematic')
  with self.assertRaises(TimeoutError):move_with_room(None,None,2,None,10,move=other_failure)
 def test_all_four_plan_receipts_require_current_native_identity(self):
  submitted={'coop_qa_kit_catalog':'hash','coop_qa_kit_epoch':'epoch'}
  native=dict(submitted,coop_qa_kit_status='PLAN_VALIDATED',coop_qa_kit_verified_catalog='hash',coop_qa_kit_verified_epoch='epoch',coop_spawn_session_a='10',coop_spawn_session_b='20',coop_spawn_session_c='1',coop_spawn_world='3')
  for slot in range(4):
   identity='10|20|1|%d|7|3'%slot
   native.update({'coop_spawn_ticket_%d'%slot:'7','coop_qa_kit_identity_%d'%slot:identity,'coop_qa_kit_applied_%d'%slot:identity+'|epoch','coop_inventory_%d_state'%slot:'FRESH','coop_inventory_%d_identity'%slot:identity})
  self.assertTrue(host_plan_receipts_match(native,submitted))
  # A peer dropped during its own map load returns into the PRESERVED disposition
  # of the same native identity; only that second state is acceptable.
  preserved=dict(native,coop_inventory_1_state='PRESERVED')
  self.assertTrue(host_plan_receipts_match(preserved,submitted))
  for field,value in [('coop_qa_kit_applied_2','stale'),('coop_spawn_ticket_3','8'),('coop_inventory_1_state','STALE'),('coop_qa_kit_verified_catalog','wrong')]:
   mutant=dict(native);mutant[field]=value
   with self.subTest(field=field):self.assertFalse(host_plan_receipts_match(mutant,submitted))
 def fixture(self):
  host=[{'selected_world_model':'xmodel/gun%d'%slot} for slot in range(4)]
  observer={'references_complete':True,'reference_layout_valid':True,'cgame':{'snapshot_clientnum':0},'live_dobjs':[
   {'entity':slot,'side':side,'model_names':['body','gun%d'%slot],'cs_model_names':['xmodel/body','xmodel/gun%d'%slot],'client_cs_model_names':['xmodel/body','xmodel/gun%d'%slot],'raw_model_flags':[-1,-slot-2]} for slot in range(4) for side in ('server','client')]}
  observer['native_model_slots']=[{'index':index,'server_cs':'xmodel/'+name,'client_cs':'xmodel/'+name,'cache_name':name} for index,name in [(1,'body')]+[(slot+2,'gun%d'%slot) for slot in range(4)]]
  peer=copy.deepcopy(observer);peer['cgame']['snapshot_clientnum']=1;peer['live_dobjs']=[obj for obj in peer['live_dobjs'] if obj['entity']!=1]
  return host,{'host':observer,'join1':peer}
 def test_native_model_and_negative_cs_must_both_match(self):
  host,observers=self.fixture();require_body_models(host,observers)
  for field,value in [('model_names',['body','wrong']),('cs_model_names',['xmodel/body','xmodel/wrong']),('client_cs_model_names',['xmodel/body','xmodel/wrong']),('raw_model_flags',[-1,7])]:
   mutant=copy.deepcopy(observers);mutant['join1']['live_dobjs'][5][field]=value
   with self.subTest(field=field),self.assertRaises(RuntimeError):require_body_models(host,mutant)
 def test_missing_shadow_or_client_never_passes(self):
  host,observers=self.fixture();observers['join1']['live_dobjs'].pop()
  with self.assertRaises(RuntimeError):require_body_models(host,observers)
 def test_wrong_native_cache_never_passes_even_when_model_and_both_cs_match(self):
  host,observers=self.fixture();observers['join1']['native_model_slots'][0]['cache_name']='other_body'
  with self.assertRaises(RuntimeError):require_body_models(host,observers)

if __name__=='__main__':unittest.main()
