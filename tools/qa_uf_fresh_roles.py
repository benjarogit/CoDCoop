#!/usr/bin/env python3
"""EXPERIMENTAL four real fresh UF roles/body/fire; no save, GUID-kit or production-registry acceptance."""
import argparse,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
import qa_coop as qa
from qa_uf_kits import kit_fixture,cgame_selection_matches
from qa_uf_world_observer import archive_cache_inputs
from uf_equipment_preferences import catalog_digest
from build_campaign_patch import build
from stage_suite import laa_bytes,UOSP_LAA

def normalized(name):return name.lower().removeprefix('xmodel/')

def owned_game_environment(inherited, *, trace_tree_free=False, borrow_trees=False, all_weapon_media=False):
 env=dict(inherited)
 for key in tuple(env):
  if key.startswith('CODCOOP_QA_') and key!='CODCOOP_QA_NO_STEAM':env.pop(key)
 env['CODCOOP_QA_DEFER_MODELS']='1'
 if trace_tree_free:env['CODCOOP_QA_TREE_FREE_TRACE']='1'
 if borrow_trees:env['CODCOOP_QA_BORROW_TREES']='1'
 if all_weapon_media:env['CODCOOP_QA_ALL_WEAPON_MEDIA']='1'
 return env

def host_plan_receipts_match(native,submitted):
 if native.get('coop_qa_kit_status')!='PLAN_VALIDATED':return False
 if native.get('coop_qa_kit_verified_catalog')!=submitted['coop_qa_kit_catalog'] or native.get('coop_qa_kit_verified_epoch')!=submitted['coop_qa_kit_epoch']:return False
 if any(native.get(key)!=value for key,value in submitted.items()):return False
 session=[native.get('coop_spawn_session_'+part,'') for part in ('a','b','c')]
 world=native.get('coop_spawn_world','')
 if not world.isdigit() or int(world)<=0 or any(not part.isdigit() for part in session):return False
 for slot in range(4):
  ticket=native.get('coop_spawn_ticket_%d'%slot,'')
  if not ticket.isdigit() or int(ticket)<=0:return False
  identity='|'.join(session+[str(slot),ticket,world])
  if native.get('coop_qa_kit_identity_%d'%slot)!=identity or native.get('coop_qa_kit_applied_%d'%slot)!=identity+'|'+submitted['coop_qa_kit_epoch']:return False
  if native.get('coop_inventory_%d_state'%slot)!='FRESH' or native.get('coop_inventory_%d_identity'%slot)!=identity:return False
 return True

def require_body_models(host, observers):
 ownership={}
 for label,observer in observers.items():
  if not observer.get('references_complete') or not observer.get('reference_layout_valid'):raise RuntimeError('Incomplete readonly DObj layout: '+label)
  own=observer.get('cgame',{}).get('snapshot_clientnum')
  if own not in range(4):raise RuntimeError('Current own CG identity missing: '+label)
  ownership[label]={'own_snapshot_client':own,'own_first_person_body_sides_present':[side for side in ('server','client') if any(obj['entity']==own and obj['side']==side for obj in observer['live_dobjs'])],
                    'scope':'Host authoritative server all4; every observer other3 client+shadow; no own third-person-body claim'}
  for slot in range(4):
   expected=normalized(host[slot].get('selected_world_model',''))
   if not expected:raise RuntimeError('Native selected WeaponDef lacks worldModel at slot%d'%slot)
   for side in ('server','client'):
    if slot==own and not (label=='host' and side=='server'):continue
    found=[obj for obj in observer['live_dobjs'] if obj['entity']==slot and obj['side']==side]
    if len(found)!=1:raise RuntimeError('Missing %s body slot%d in %s'%(side,slot,label))
    obj=found[0]
    actual=list(map(normalized,obj.get('model_names',[])));cs=list(map(normalized,obj.get('cs_model_names',[])));client_cs=list(map(normalized,obj.get('client_cs_model_names',[])))
    if expected not in actual:raise RuntimeError('Native weapon body model missing: %s/%s slot%d expected%s actual%s'%(label,side,slot,expected,actual))
    index=actual.index(expected)
    if index>=len(cs) or cs[index]!=expected or obj['raw_model_flags'][index]>=0:raise RuntimeError('Native DObj negative model ID disagrees with actual model/CS: %s/%s slot%d'%(label,side,slot))
    if index>=len(client_cs) or client_cs[index]!=expected:raise RuntimeError('Native actual client CS disagrees with visible model: %s/%s slot%d'%(label,side,slot))
    slots={row['index']:row for row in observer.get('native_model_slots',[])}
    for component,flag in enumerate(obj['raw_model_flags']):
     if flag>=0 or component>=len(actual) or -flag not in slots:raise RuntimeError('Body component lacks native byte-ID/cache evidence')
     native_slot=slots[-flag]
     if (normalized(native_slot['cache_name'])!=actual[component]
         or normalized(native_slot['server_cs'])!=actual[component]
         or normalized(native_slot['client_cs'])!=actual[component]):
      raise RuntimeError('Native body component/cache/CS mismatch: %s/%s owner%d component%d id%d'%(label,side,slot,component,-flag))
 return ownership

def argument_parser():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('source','run','runtime-dir'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--map',choices=('brecourt','noville','foy'),default='brecourt');p.add_argument('--port',type=int,default=29966)
 p.add_argument('--timeout',type=int,default=180);p.add_argument('--world-policy',choices=('universal','selected'),default='universal')
 p.add_argument('--experimental-borrow-trees',action='store_true',help='Explicit additional legacy QA native-tree ownership experiment, only after a preserved allocator negative')
 p.add_argument('--experimental-gmi-loader',action='store_true',help='QA-only pinned UO/GMI loader startup; leave disabled for original crash-payload causal traces')
 p.add_argument('--trace-tree-free',action='store_true',help='QA-only read-only native tree ownership/free-path trace; changes no free semantics')
 p.add_argument('--experimental-all-weapon-media',action='store_true',help='QA-only existing native item/media registration; no inventory grant or native acceptance proof')
 return p

def main():
 a=argument_parser().parse_args();out=a.run.resolve();base=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant','united_fronts','--map',a.map,'--players','4','--timeout',str(a.timeout),'--port',str(a.port),'--duration','2']
 qa.main(base+['--prepare-only'])
 folders=[out/name for name in ('host','join1','join2','join3')];kits,expected,fire=kit_fixture(4)
 catalog=json.loads((qa.ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
 values={'coop_qa_kit_enable':'1','coop_qa_kit_authority':'host','coop_qa_kit_commit':'1','coop_qa_kit_catalog':catalog_digest(catalog),'coop_qa_kit_map':a.map,'coop_qa_kit_epoch':'qa-fresh-body-'+str(time.time_ns())}
 for slot,kit in enumerate(kits):
  values.update({'coop_qa_kit_%d_mode'%slot:'manual','coop_qa_kit_%d_family'%slot:'american'})
  values.update({'coop_qa_kit_%d_%s'%(slot,key):str(value) for key,value in kit.items()})
 inputs={}
 for folder in folders:
  archive=out/'fresh-role-input-history'/str(time.time_ns())/folder.name;archive.mkdir(parents=True)
  inputs[folder.name]={'archived_cache_inputs':archive_cache_inputs(folder,archive,a.map)}
  for name in ('zzzz_coop_campaign.pk3','zzzz_coop_world_observer.pk3','zzzz_coop_triggers.pk3','zzzzz_coop_triggers.pk3','zzzzz_codcoop_triggers.pk3'):
   target=folder/'UnitedFronts'/name
   if target.is_symlink():raise ValueError('Refusing linked generated QA overlay')
   if target.exists():shutil.copy2(target,archive/name);target.unlink()
  overlay=folder/'UnitedFronts/zzzz_coop_campaign.pk3'
  build(folder/'UnitedFronts/ZUnitedFronts_1.1_beta.pk3',overlay,'united_fronts',qa_kits=True,world_policy=a.world_policy,qa_gmi=a.experimental_gmi_loader)
  exe=folder/'CoDUOSP.exe';exe.write_bytes(laa_bytes(exe.read_bytes()))
  inputs[folder.name].update(exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),yap_sha256=hashlib.sha256((folder/'plugins/yap/DDRAW.dll').read_bytes()).hexdigest(),overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest())
  if inputs[folder.name]['exe_sha256']!=UOSP_LAA:raise RuntimeError('Unreviewed UO executable')
  shutil.copy2(overlay,out/(folder.name+'-fresh-role-overlay.pk3'))
 config=folders[0]/'UnitedFronts/coop_qa_fresh_roles.cfg';config.write_text(''.join('set %s "%s"\n'%entry for entry in values.items()))
 helper=out/'qa-fresh-role-observer.exe';source=out/'qa-fresh-role-observer.cpp';source.write_bytes((qa.ROOT/'campaign_patches/qa_uf_player_state.cpp').read_bytes())
 subprocess.run(['i686-w64-mingw32-g++',str(source),'-o',str(helper),'-static','-O2','-std=c++17'],check=True)
 report={'status':'FAIL','scope':__doc__,'map':a.map,'players':4,'world_policy':a.world_policy,'hunk_megabytes':512,'inputs':inputs,'host_only_QA_plan_cvars':values,'network_resources':'normal resource-bootstrap v2; no peer-plan/offline media injection','experimental_defer_models':True,'experimental_borrow_trees':a.experimental_borrow_trees,'phases':[],'known_open':['No saved-world or GUID equipment binding proof','Experimental legacy registry globals not production promoted']}
 report['experimental_gmi_loader']=a.experimental_gmi_loader
 report['readonly_tree_free_trace']=a.trace_tree_free
 report['experimental_all_weapon_media']={'enabled':a.experimental_all_weapon_media,
     'scope':'QA-only original native item/media registration for existing definitions; no inventory grant or native proof from this option'}
 frozen=out/'runtime/fresh-role-source'
 for name in ('tools/qa_uf_fresh_roles.py','tools/qa_coop.py','tools/build_campaign_patch.py','campaign_patches/uf_starting_kits.gsc','campaign_patches/qa_uf_player_state.cpp','campaign_patches/uf_equipment_catalog.json'):
  target=frozen/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(qa.ROOT/name,target)
 for folder in folders:shutil.copy2(folder/'UnitedFronts/zzzz_coop_campaign.pk3',frozen/(folder.name+'-overlay.pk3'))
 shutil.copy2(helper,out/'runtime/qa-fresh-role-observer.exe')
 report['observer_exe_sha256']=hashlib.sha256(helper.read_bytes()).hexdigest()
 executed=Path(__file__).read_bytes();original=subprocess.Popen
 def launch(command,*args,**kwargs):
  if isinstance(command,list) and any(str(item).endswith('CoDUOSP.exe') for item in command):
   command=list(command)
   kwargs['env']=owned_game_environment(kwargs['env'],trace_tree_free=a.trace_tree_free,
       borrow_trees=a.experimental_borrow_trees,all_weapon_media=a.experimental_all_weapon_media)
   index=command.index('+devmap')
   if '+coopjoin' in command:del command[index:index+2]
   else:command[index:index]=['+exec','coop_qa_fresh_roles.cfg']
  return original(command,*args,**kwargs)
 env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all')
 def native(folder,slot,references=False):
  command=['wine',str(helper),str(folder).replace('/','\\'),str(slot)]+(['--model-references'] if references else [])
  result=subprocess.run(command,env=env,capture_output=True,text=True,check=True,timeout=15)
  return json.loads(result.stdout.strip())
 def scenario(actual_folders,processes,states):
  controls=[(folder,0 if folder==folders[0] else qa.read_state(folder)['slot']) for folder in folders]
  if sorted(slot for folder,slot in controls)!=list(range(4)):raise RuntimeError('Four unique actual native owner slots required')
  report['actual_owner_slots']={folder.name:slot for folder,slot in controls}
  def plan_ready():
   console=(folders[0]/'UnitedFronts/console.log').read_text(errors='replace')
   native=dict(re.findall(r'^[ \t]*cvar set (coop_[a-z0-9_]+)[ \t]*(.*?)\r?$',console,re.M))
   report['last_native_plan_cvars']=native
   status=native.get('coop_qa_kit_status','')
   if status.startswith(('FAIL_','BLOCKED_')):raise RuntimeError('Actual host kit producer rejected plan: '+status)
   return native if host_plan_receipts_match(native,values) else None
  report['validated_native_host_plan']=qa.wait_for(plan_ready,processes,35,'current native FRESH identities and all four unchanged QA kit receipts')
  def capture(phase,names=None,body=False):
   deadline=time.monotonic()+35;last_error=None
   while time.monotonic()<deadline:
    for folder in folders:
     errors=qa.process_log_errors(folder)
     if errors:raise RuntimeError('Native error during '+phase+': '+errors[0])
    host=[native(folders[0],slot) for slot in range(4)]
    observers={folder.name:native(folder,0,True) for folder,slot in controls}
    row={'phase':phase,'host':host,'observers':observers};report['last_observation']=row
    try:
     for slot,state in enumerate(host):
      if any(state['inventory'][key]!=value for key,value in expected[slot].items()):raise RuntimeError('Actual distinct kit mismatch at slot%d'%slot)
     for folder,slot in controls:
      if not cgame_selection_matches(host[slot],observers[folder.name],slot):raise RuntimeError('Own actual Game/currentCG mismatch at slot%d'%slot)
      if names is not None and normalized(host[slot]['selected_weapon_name'])!=normalized(names[slot]):raise RuntimeError('User-selected weapon not yet active at slot%d'%slot)
     if body:row['ownership_aware_body_scope']=require_body_models(host,observers)
     report['phases'].append(row);return row
    except RuntimeError as error:last_error=error;time.sleep(.2)
   raise last_error
  initial=capture('four_fresh_distinct_kits')
  for folder,slot in controls:
   if slot:report.setdefault('real_movement',{})[str(slot)]=qa.move_remote(folders[0],folder,slot,processes,a.timeout)
  time.sleep(.8)
  for folder,slot in controls:qa.command(folder,'weaponslot '+fire[slot],joiner=slot!=0)
  before=capture('actual_firearm_selection',[expected[slot][fire[slot]] for slot in range(4)],body=True)
  for folder,slot in controls:qa.command(folder,'+attack',joiner=slot!=0)
  time.sleep(.4)
  for folder,slot in controls:qa.command(folder,'-attack',joiner=slot!=0)
  after=capture('actual_four_owner_fire',[expected[slot][fire[slot]] for slot in range(4)],body=True)
  if any(after['host'][slot]['slot_ammo'][fire[slot]]['clip']>=before['host'][slot]['slot_ammo'][fire[slot]]['clip'] for slot in range(4)):raise RuntimeError('Actual attack must consume owned ammunition for every player')
  for phase,weapon_slot in (('MG_and_bazooka_visible','primary'),('pistol_and_binoculars_visible','pistol')):
   time.sleep(.8)
   for folder,slot in controls:qa.command(folder,'weaponslot '+weapon_slot,joiner=slot!=0)
   capture(phase,[expected[slot][weapon_slot] for slot in range(4)],body=True)
   for folder,slot in controls:
    shots=folder/'UnitedFronts/screenshots';old=set(shots.glob('*.tga'));qa.command(folder,'screenshot',joiner=slot!=0)
    shot=qa.wait_for(lambda: next(iter(set(shots.glob('*.tga'))-old),None),processes,8,'fresh actual owner screenshot')
    target=out/('%s-owner%d.tga'%(phase,slot));shutil.copy2(shot,target)
    archive=out/'runtime/fresh-role-native-images';archive.mkdir(exist_ok=True)
    shutil.copy2(shot,archive/target.name)
    report.setdefault('screenshots',{}).setdefault(phase,{})[str(slot)]={'source':str(shot),'copied':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
  for folder in folders[1:]:
   text=(folder/'codcoop_join.log').read_text(errors='replace')
   markers=['Resource bootstrap: SHA verified','QA native GAME_INIT','Resource bootstrap: native item/alt registration completed','Resource bootstrap: completed native Game/CG mapping verified','joiner: conectado']
   positions=[text.find(marker) for marker in markers]
   if min(positions)<0 or positions!=sorted(positions):raise RuntimeError('Real resource-bootstrap v2 before native slot attach not proved')
  report['status']='PASS'
  return {'scope':__doc__,'checks':['four actual fresh independent kits/current CG owners','normal resource-bootstrap v2; no offline plan/media on peers','all remotes moved via genuine owner input','all four consumed own firearm ammo','Host authoritative all4 server bodies and every observer other3 client/shadow bodies match native worldModel+negative actualclient/SV CS IDs; own first-person body presence recorded separately','MG/bazooka and pistol/binocular selection through actual weaponslot input; no firing/deployment claim for special weapons'], 'evidence':{'proof':'uf-fresh-roles-proof.json','map':a.map,'no_explicit_QA_save_or_load':True}}
 subprocess.Popen=launch
 code=1
 try:code=qa.main(base,scenario=scenario)
 except Exception as error:report['error']=str(error);code=1
 finally:
  subprocess.Popen=original
  if code:report['status']='FAIL'
  (out/'uf-fresh-roles-proof.json').write_text(json.dumps(report,indent=2)+'\n');(out/'executed_qa_uf_fresh_roles.py').write_bytes(executed)
 return code

if __name__=='__main__':raise SystemExit(main())
