#!/usr/bin/env python3
"""Natural Pathfinder intro + real remote Use; never a full mission proof."""
import argparse,ctypes,hashlib,json,math,os,re,shutil,subprocess,time
from pathlib import Path
import qa_coop as qa
from build_campaign_patch import quarantine_obsolete_qa_trigger_overlays, build_trigger_patch

def pose_difference(saved,restored):
 """Strict owned-PS oracle; this function is not a native acceptance result."""
 for record in (saved,restored):
  for key in ('position','viewangles'):
   values=record[key]
   if not isinstance(values,list) or len(values)!=3 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in values):
    raise ValueError('Native pose must contain finite three-component vectors')
 distance=math.dist(saved['position'],restored['position'])
 angles=[abs((a-b+180)%360-180) for a,b in zip(saved['viewangles'],restored['viewangles'])]
 return {'position_delta':distance,'angle_deltas':angles,'within_tolerance':distance<=8 and max(angles)<=2,
         'tolerance':{'world_units':8,'degrees':2}}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for flag in ('source','run','runtime-dir'):p.add_argument('--'+flag,type=Path,required=True)
 p.add_argument('--variant',choices=('cod1','uo','sp_improved','united_fronts'),default='cod1')
 p.add_argument('--port',type=int,default=29950);p.add_argument('--timeout',type=int,default=180)
 p.add_argument('--checkpoint',action='store_true',help='actual post-grant save/load; preserve user-selected Colt and consumed ammo')
 p.add_argument('--equipment-checkpoint-only',action='store_true',help='explicit scoped kit/save proof; never tests or claims legbag/beacon Use')
 p.add_argument('--look-backend',choices=('keyboard','xtest'),default='keyboard')
 p.add_argument('--input-counterfactual',action='store_true',help='require real peer keyboard yaw before route or kit checkpoint')
 p.add_argument('--native-mouse-counterfactual',action='store_true',help='owned-window SendInput baseline on both Host/peer; never physical-hardware proof')
 p.add_argument('--arranged-interactions',action='store_true',help='explicit actor setup at original objects; actual Use proof only, no natural tutorial/route acceptance')
 p.add_argument('--require-pose-restore',action='store_true',help='strict saved plain-standing owner position/look, beyond inventory-only checkpoint scope')
 p.add_argument('--require-vitals-restore',action='store_true',help='actual nonfatal native remote damage before save; strict both-owner PS/entity health after load')
 a=p.parse_args();out=a.run.resolve();root={'cod1':'Main','uo':'uo','sp_improved':'sp_improved','united_fronts':'UnitedFronts'}[a.variant]
 if a.require_pose_restore and not (a.checkpoint or a.equipment_checkpoint_only):p.error('--require-pose-restore requires an actual checkpoint scenario')
 if a.require_vitals_restore and not (a.checkpoint or a.equipment_checkpoint_only):p.error('--require-vitals-restore requires an actual checkpoint scenario')
 engine='cod1' if a.variant=='cod1' else 'uo';folders=[out/'host',out/'join1']
 argv=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant',a.variant,'--map','pathfinder','--players','2','--timeout',str(a.timeout),'--duration','2','--port',str(a.port)]
 if qa.main(argv+['--prepare-only']):return 1
 for folder in folders:
  for name in ('qa-render-models.txt','qa-deferred-models.txt'):
   f=folder/name
   if f.exists():
    target=out/'fixture-inputs-quarantined'/str(time.time_ns())/folder.name/name;target.parent.mkdir(parents=True);f.rename(target)
  quarantine_obsolete_qa_trigger_overlays(folder)
  build_trigger_patch(a.source.resolve(),folder/root/'zzzz_coop_triggers.pk3',a.variant,qa_pathfinder=True)
 helper=out/'qa-campaign-player.exe';observer=out/'qa-campaign-player.cpp'
 observer.write_bytes((qa.ROOT/'campaign_patches/qa_campaign_player.cpp').read_bytes())
 subprocess.run(['i686-w64-mingw32-g++',str(observer),'-o',str(helper),'-static','-O2','-std=c++17','-mwindows'],check=True)
 input_helper=out/'qa-campaign-input.exe'
 if a.native_mouse_counterfactual:
  input_source=out/'qa-campaign-input.cpp';input_source.write_bytes((qa.ROOT/'campaign_patches/qa_campaign_input.cpp').read_bytes())
  subprocess.run(['i686-w64-mingw32-g++',str(input_source),'-o',str(input_helper),'-static','-O2','-std=c++17','-mwindows'],check=True)
 report={'status':'FAIL','scope':__doc__,'variant':a.variant,'input':[],'observations':[],
         'arrangement':'No actor/object teleport, scripted trigger notify/useBy or intro skip. QA observation does not write mission objectives/flags/inventory; the reviewed production adapter alone gives the original fresh-owner recipe. Original Host parachute role remains unchanged.',
         'observer_sha256':hashlib.sha256(observer.read_bytes()).hexdigest()}
 if a.equipment_checkpoint_only:report['scope']='natural original intro and personal kit/native checkpoint only; shared Use not exercised'
 if a.arranged_interactions:
  report['scope']='isolated actual remote legbag/beacon activation; preceding intro/tutorial/route outside acceptance'
  report['arrangement']='After observed original Host detach, existing native cooplook arranges Host1000/peer300 from each ORIGINAL mission object. Only actual owner movement/look/activate after setup may advance original Use routines. No injected trigger notify/useBy, collision/AI/mission-flag changes. Preceding tutorial touch/route and complete intro participation are not certified.'
 trail=[];host_cursor=0
 def values():
  s=(folders[0]/root/'console.log').read_text(errors='replace')
  return dict(re.findall(r'^\s*cvar set (coop_[a-z0-9_]+)\s+(.*?)\r?$',s,re.M))
 def wait(check,label,timeout=35):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   for folder in folders:
    errors=qa.process_log_errors(folder)
    if errors:raise RuntimeError(label+': '+errors[0])
   result=check()
   if result:return result
   time.sleep(.1)
  raise RuntimeError('Timeout: '+label)
 env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all')
 def native(folder,slot):
  native_env=dict(env)
  if report.get('owned_input_surface'):native_env['DISPLAY']=report['owned_input_surface']['display']
  r=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),str(slot),engine],env=native_env,text=True,capture_output=True,check=True,timeout=15)
  return json.loads(r.stdout.strip())
 def observe(label):
  host=[native(folders[0],slot) for slot in (0,1)];local=[host[0],native(folders[1],0)]
  record={'phase':label,'host':host,'local':local};report['observations'].append(record);return record
 def focus_peer(slot=1):
  # XTest is confined to this harness's owned Xvfb and actual game Unix PID.
  # A title alone never authorizes focusing a user's unrelated game window.
  for proc in Path('/proc').glob('[0-9]*'):
   try:
    if proc.joinpath('comm').read_text().strip().lower()!=('codsp.exe' if engine=='cod1' else 'coduosp.exe'):continue
    command=proc.joinpath('cmdline').read_bytes().decode(errors='replace').replace('\\','/').lower()
    if str(folders[slot]).lower() not in command:continue
    environ=dict(part.split('=',1) for part in proc.joinpath('environ').read_bytes().decode(errors='replace').split('\0') if '=' in part)
    if environ.get('WINEPREFIX')!=str(out/'prefix'):continue
    display=environ['DISPLAY'];xenv=dict(os.environ,DISPLAY=display)
    ids=subprocess.check_output(['xdotool','search','--onlyvisible','--pid',proc.name],env=xenv,text=True).split()
    for window in ids:
     title=subprocess.check_output(['xdotool','getwindowname',window],env=xenv,text=True).strip()
     if 'call of duty' not in title.lower() and not (engine=='uo' and title=='CoD:United Offensive'):continue
     subprocess.run(['xdotool','windowraise',window,'windowfocus','--sync',window],env=xenv,check=True)
     subprocess.run(['xdotool','mousemove','--window',window,'320','240'],env=xenv,check=True)
     surface={'display':display,'unix_pid':int(proc.name),'window':window,'title':title}
     report.setdefault('owned_input_surfaces',{})[str(slot)]=surface
     if slot==1:report['owned_input_surface']=surface
     return
   except (OSError,KeyError,subprocess.CalledProcessError):continue
  raise RuntimeError('Could not bind input focus to this owned peer/Xvfb game window')
 def mouse(dx,dy,slot=1):
  if str(slot) not in report.get('owned_input_surfaces',{}):focus_peer(slot)
  surface=report['owned_input_surfaces'][str(slot)];xenv=dict(os.environ,DISPLAY=surface['display'])
  subprocess.run(['xdotool','windowraise',surface['window'],'windowfocus','--sync',surface['window']],env=xenv,check=True,timeout=3)
  time.sleep(.12)
  dx=max(-300,min(300,int(dx)));dy=max(-250,min(250,int(dy)))
  # Call the relative XTest API explicitly, avoiding an implementation's
  # absolute pointer-warp fallback when testing a relative-input game.
  x11=ctypes.CDLL('libX11.so.6');xtest=ctypes.CDLL('libXtst.so.6')
  x11.XOpenDisplay.argtypes=[ctypes.c_char_p];x11.XOpenDisplay.restype=ctypes.c_void_p
  x11.XCloseDisplay.argtypes=[ctypes.c_void_p];x11.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int]
  xtest.XTestFakeRelativeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
  display=x11.XOpenDisplay(surface['display'].encode())
  if not display:raise RuntimeError('Owned Xvfb XTest connection failed')
  try:
   if not xtest.XTestFakeRelativeMotionEvent(display,dx,dy,0):raise RuntimeError('Owned XTest relative motion failed')
   x11.XSync(display,0)
  finally:x11.XCloseDisplay(display)
  report['input'].append({'kind':'owned Xvfb direct XTestFakeRelativeMotionEvent','slot':slot,'dx':dx,'dy':dy})
  time.sleep(.18)
 def stable(label):
  def matched():
   r=observe(label)
   for slot in (0,1):
    name=r['host'][slot]['selected']['name'];cg=r['local'][slot]['cgame']
    if name=='none' or cg['snapshot_client']!=slot or any(cg[key]['name'].lower()!=name.lower() for key in ('snapshot','desired','predicted')):return None
   return r
  return wait(matched,'actual own Game/CG weapon selection: '+label)
 def pulse(slot,action,duration,settings=None):
  target=folders[slot];before=qa.read_state(folders[0])['players'][slot]
  qa.command(target,(settings+'\n' if settings else '')+action,joiner=slot!=0)
  try:time.sleep(duration)
  finally:qa.command(target,'-'+action[1:],joiner=slot!=0)
  wait(lambda:qa.read_state(folders[0])['players'][slot]['command_time']>before['command_time'],'actual owner command clock')
  report['input'].append({'slot':slot,'command':action,'duration':duration,'settings':settings,'before':before,'after':qa.read_state(folders[0])['players'][slot]})
  time.sleep(.12)
 def aim(target,pitch=None,slot=1):
  for _ in range(25):
   n=native(folders[0],slot);pos=n['position'];angle=n['viewangles']
   yaw=math.degrees(math.atan2(target[1]-pos[1],target[0]-pos[0]));delta=(yaw-angle[1]+180)%360-180
   local=native(folders[slot],0)
   report.setdefault('steering',[]).append({'slot':slot,'host_angles':angle,'host_cmd':n['cmd_angles'],'host_pm_flags':n['pm_flags'],'local_input':local.get('native_input'),'local_pid':local['pid'],'foreground_pid':local['foreground_pid'],'local_predicted_angles':local['cgame']['predicted_angles'],'desired_yaw':yaw})
   if abs(delta)<=4:break
   # The existing native command-file poll has250ms resolution. Scale the
   # ordinary local turn speed so short queued key presses do not oscillate
   # in45-degree steps; the resulting actual yaw remains independently read.
   if a.look_backend=='keyboard':pulse(slot,'+left' if delta>0 else '+right',.1,'set cl_yawspeed '+str(min(180,max(3,abs(delta)*2))))
   else:mouse(-delta/.044,0,slot=slot)
  else:
   # Failed route only: distinguish the injection backend from a remote-only
   # camera fault using the same owned Host window and normal input paths.
   focus_peer(0);before=native(folders[0],0)
   pulse(0,'+left',.4);keyboard=native(folders[0],0)
   mouse(-300,0,slot=0);pointer=native(folders[0],0)
   report['failed_camera_host_control']={'before':before,'after_keyboard':keyboard,'after_direct_xtest':pointer}
   focus_peer(1)
   raise RuntimeError('Actual owner yaw input could not face target')
  if pitch is not None:
   for _ in range(20):
    n=native(folders[0],slot);delta=pitch-n['viewangles'][0]
    if abs(delta)<5:break
    if a.look_backend=='keyboard':pulse(slot,'+lookdown' if delta>0 else '+lookup',.1,'set cl_pitchspeed '+str(min(120,max(3,abs(delta)*2))))
    else:mouse(0,delta/.044,slot=slot)
   else:raise RuntimeError('Actual owner pitch input could not face target')
 def approach(target,slot=1,stop=48):
  nonlocal host_cursor
  stalls=0
  for _ in range(90):
   n=native(folders[0],slot);distance=math.dist(n['position'][:2],target[:2])
   if slot==1:
    if not trail or math.dist(trail[-1],n['position'])>10:trail.append(n['position'])
    # Keep the original automatic catch-up rules enabled. The Host walks the
    # same actually traversed trail, staying well outside each final Use zone.
    if math.dist(native(folders[0],0)['position'],n['position'])>1400:
     while host_cursor<len(trail) and math.dist(trail[host_cursor],n['position'])>900:
      approach(trail[host_cursor],slot=0,stop=60);host_cursor+=1
   if distance<stop and abs(n['position'][2]-target[2])<96:return
   aim(target,0,slot=slot);before=n['position']
   pulse(slot,'+forward',min(max((distance-stop+8)/150,.12),.65))
   after=native(folders[0],slot)['position'];stalls=stalls+1 if math.dist(before,after)<3 else 0
   if stalls>=4:
    qa.command(folders[slot],'screenshot',joiner=slot!=0);time.sleep(.7)
    report['obstructed_route']={'slot':slot,'position':after,'target':target}
    raise RuntimeError('Natural path obstructed; no teleport or scripted progress substituted')
  raise RuntimeError('Natural approach exceeded bounded owner inputs')
 def unchanged(before,after,phase='Shared objective'):
  for slot in (0,1):
   for field in ('inventory','stock','clip','selected'):
    if before['host'][slot][field]!=after['host'][slot][field]:raise RuntimeError(phase+' changed personal '+field+' slot'+str(slot))
 def use(target,objective):
  aim(target,math.degrees(math.atan2(60,max(1,math.dist(native(folders[0],1)['position'][:2],target[:2])))))
  for _ in range(4):
   pulse(1,'+activate',.25)
   time.sleep(.4)
   if values().get('coop_pathfinder_qa_objective_'+str(objective)+'_count')=='1':return
  raise RuntimeError('Actual remote Use did not complete original objective'+str(objective))
 def checkpoint_proof():
  if a.variant=='united_fronts':raise RuntimeError('Classic Colt checkpoint recipe is not a UF role fixture')
  qa.command(folders[1],'weapon colt',joiner=True)
  wait(lambda: (r if r['host'][1]['selected']['name'].lower()=='colt' else None) if (r:=stable('normal_user_colt_selection')) else None,'actual normal user Colt choice')
  before=stable('before_colt_fire');pulse(1,'+attack',.3);saved=stable('consumed_colt_before_checkpoint')
  if a.require_vitals_restore:
   undamaged=saved
   qa.command(folders[0],'coopgod 1 0\ncoopkill 1 50')
   def damaged_owner():
    h=native(folders[0],1)
    return h if 1<h['health']<undamaged['host'][1]['health'] and h['health']==h['entity_health'] else None
   damaged=wait(damaged_owner,'actual nonfatal native G_Damage changes both remote PS and entity health')
   saved=stable('damaged_owner_before_checkpoint')
   report['vitals_damage']={'command':'coopgod 1 0; coopkill 1 50','before':undamaged,'damaged':damaged,'saved':saved}
   if any(n['pm_type']!=0 or n['linked'] or n['pm_flags']&3 or n['health']<=1 for n in saved['host']):raise RuntimeError('Vitals fixture requires actual healthy standing unlinked owners')
   if any(saved['host'][0][key]!=undamaged['host'][0][key] for key in ('health','entity_health')):raise RuntimeError('Remote native damage changed Host health')
  if a.require_pose_restore and any(n['pm_type']!=0 or n['linked'] or n['pm_flags']&3 for n in saved['host']):raise RuntimeError('Strict pose fixture requires actual plain unlinked standing owners')
  if sum(saved['host'][1]['clip'])>=sum(before['host'][1]['clip']):raise RuntimeError('Normal user Colt choice did not fire')
  save=folders[0]/root/'save/qa_pathfinder_use.svg';sidecar=Path(str(save)+'.coopowners')
  save.unlink(missing_ok=True);sidecar.unlink(missing_ok=True)
  old_generation=qa.read_state(folders[0])['world_wire']['generation']
  qa.command(folders[0],'savegame qa_pathfinder_use')
  wait(lambda:save.exists() and save.stat().st_size>1024 and sidecar.exists(),'completed actual native checkpoint and ownership metadata')
  saved_time=qa.read_state(folders[0])['server_time']
  wait(lambda:qa.read_state(folders[0])['server_time']>saved_time+2500,'natural world advances beyond saved checkpoint')
  before_load_time=qa.read_state(folders[0])['server_time'];qa.command(folders[0],'loadgame qa_pathfinder_use')
  def rolled_back():
   h=qa.read_state(folders[0]);return h if h and h['world_wire']['generation']!=old_generation and h['server_time']<before_load_time-1000 else None
  rollback=wait(rolled_back,'actual native checkpoint world-time rollback',a.timeout)
  def rejoined():
   h=qa.read_state(folders[0]);peer=qa.read_state(folders[1])
   return h and peer and peer['joined'] and peer['snapshot_num']>0 and h['players'][1]['active']
  wait(rejoined,'real peer rejoined actual checkpoint',a.timeout)
  wait(lambda:values().get('coop_pathfinder_loadout_1_state')=='PRESERVED_NO_GIVE','current native preserved receipt skips classic re-give')
  restored=stable('native_checkpoint_restored_user_colt')
  report['checkpoint']={'rollback':rollback,'saved':saved,'restored':restored,'current_cvars':values(),'save_sha256':hashlib.sha256(save.read_bytes()).hexdigest(),'scope':'actual user-selected Colt and consumed ammo preserved; pre-grant save remains open'}
  report['checkpoint']['pose']=[{'slot':slot,**pose_difference(saved['host'][slot],restored['host'][slot])} for slot in (0,1)]
  report['checkpoint']['pose_required']=a.require_pose_restore
  report['checkpoint']['vitals_required']=a.require_vitals_restore
  report['checkpoint']['vitals']=[{'slot':slot,'saved':{k:saved['host'][slot][k] for k in ('health','entity_health')},'restored':{k:restored['host'][slot][k] for k in ('health','entity_health')}} for slot in (0,1)]
  if a.require_pose_restore and any(not item['within_tolerance'] for item in report['checkpoint']['pose']):raise RuntimeError('Actual checkpoint did not preserve owner position/look')
  if a.require_vitals_restore and any(item['saved']!=item['restored'] for item in report['checkpoint']['vitals']):raise RuntimeError('Actual checkpoint did not preserve owner PS/entity health')
  if engine=='cod1':
   old_items=saved['host'][0];new_items=restored['host'][0]
   if not old_items.get('world_items_complete') or not new_items.get('world_items_complete'):raise RuntimeError('Native world-item snapshot incomplete')
   identity=lambda item:(item['entity'],item['weapon_id'],item['classname'])
   previous={identity(item) for item in old_items['world_items']}
   added=[item for item in new_items['world_items'] if identity(item) not in previous]
   report['checkpoint']['postload_added_world_items']=added
   if any(item['weapon_id']==saved['host'][1]['inventory']['pistol']['id'] for item in added):raise RuntimeError('Managed saved ghost produced a new Colt item in post-load world')
  unchanged(saved,restored,'Native checkpoint')
  if values().get('coop_pathfinder_loadout_1_give_count')!='1':raise RuntimeError('Checkpoint re-gave classic starting recipe')
 def evidence_summary():
  # Keep the shared harness's strict262KiB evidence bound. Full native snapshots
  # remain durable and hash-bound; never skip action/assertion/cleanup checks.
  raw=out/'pathfinder-raw-native-evidence.json'
  raw.write_text(json.dumps({'status':'PENDING_HARNESS_CLEANUP','scenario':report},indent=2,allow_nan=False)+'\n')
  result={'variant':a.variant,'scope':report['scope'],'arrangement':report['arrangement'],
          'raw_native_evidence':str(raw),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
          'native_observation_count':len(report['observations']),'input_event_count':len(report['input']),
          'world_result':{k:v for k,v in report.get('world_result',{}).items() if k.startswith('coop_pathfinder_qa_')}}
  if report.get('checkpoint'):
   c=report['checkpoint'];result['checkpoint']={'save_sha256':c['save_sha256'],'postload_added_world_items':c.get('postload_added_world_items'),
      'owners':[{'slot':i,'saved_selection':c['saved']['host'][i]['selected'],'restored_selection':c['restored']['host'][i]['selected'],
                 'saved_ammo':c['saved']['host'][i]['slot_ammo'],'restored_ammo':c['restored']['host'][i]['slot_ammo']} for i in (0,1)],
      'give_count':c['current_cvars'].get('coop_pathfinder_loadout_1_give_count'),'receipt':c['current_cvars'].get('coop_pathfinder_loadout_1_state'),
      'pose':c.get('pose'),'pose_required':c.get('pose_required',False),'vitals':c.get('vitals'),'vitals_required':c.get('vitals_required',False)}
  return result
 def scenario(_folders,processes,states):
  if a.variant=='united_fronts':
   providers=[]
   for folder in folders:
    log=(folder/root/'console.log').read_text(errors='replace')
    search=log.rsplit('Current search path:',1)[-1]
    names=re.findall(r'\\([^\\\r\n]+\.pk3) \(\d+ files\)',search)
    if 'zzzz_coop_triggers.pk3' not in names or 'zzzz_coop_campaign.pk3' not in names or names.index('zzzz_coop_triggers.pk3')>=names.index('zzzz_coop_campaign.pk3'):
     raise RuntimeError('Native search path does not prioritize mission overlay over variant Pathfinder')
    providers.append({'folder':folder.name,'native_pk3_order':names,'effective_pathfinder_provider':'zzzz_coop_triggers.pk3'})
   report['native_overlay_provider']=providers
  wait(lambda:values().get('coop_pathfinder_qa_original_landed')=='1','natural original Host parachute detach',90)
  wait(lambda:all(not p['linked'] and p['pm_type']==0 for p in qa.read_state(folders[0])['players'][:2]),'both actual players normally unlinked')
  focus_peer()
  qa.command(folders[1],'set sensitivity 2\nset m_yaw 0.022\nset m_pitch 0.022\nset cl_yawspeed 180\nset cl_pitchspeed 120',joiner=True)
  if a.variant!='united_fronts':
   wait(lambda:values().get('coop_pathfinder_loadout_1_state')=='FRESH_ORIGINAL_RECIPE_REQUESTED','native-capable fresh classic Pathfinder recipe')
   def acknowledged():
    v=values();key='coop_select_1_'
    return v.get(key+'source')=='pathfinder_initial' and v.get(key+'status')=='APPLIED' and all(v.get(key+'ack_'+field)==v.get(key+field) and v.get(key+field) is not None for field in ('seq','ticket','world','session_a','session_b','session_c'))
   wait(acknowledged,'exact current classic recipe Native selection acknowledgement')
  initial=stable('after_natural_intro');v=values();report['natural_intro']=v
  if a.variant!='united_fronts':
   expected=dict(primary='m1carbine',primaryb='thompson',pistol='colt',grenade='fraggrenade')
   for slot in (0,1):
    if {key:item['name'].lower() for key,item in initial['host'][slot]['inventory'].items()}!=expected or initial['host'][slot]['selected']['name'].lower()!='m1carbine':raise RuntimeError('Authored classic initial equipment/active selection incomplete for slot'+str(slot))
   if any(initial['host'][0][field]!=initial['host'][1][field] for field in ('stock','clip')):raise RuntimeError('Fresh remote ammunition differs from original unspent Host grant')
   if v.get('coop_pathfinder_loadout_1_give_count')!='1':raise RuntimeError('Classic starting recipe applied more than once')
  if a.input_counterfactual:
   before=native(folders[0],1);pulse(1,'+left',.4);after=native(folders[0],1)
   local=native(folders[1],0)
   report['input_counterfactual']={'before':before,'after':after,'local':local}
   delta=(after['viewangles'][1]-before['viewangles'][1]+180)%360-180
   if abs(delta)<15 or before['cmd_angles']==after['cmd_angles']:raise RuntimeError('Actual peer input-clock yaw counterfactual failed')
   if abs((local['cgame']['predicted_angles'][1]-before['viewangles'][1]+180)%360-180)<15:raise RuntimeError('Actual own CGame did not follow real peer keyboard yaw')
   if engine=='cod1' and local['native_input']['frame_msec']<=0:raise RuntimeError('Native input clock still nonpositive after actual peer yaw')
   mouse(-200,0);pointer=native(folders[0],1)
   report['input_counterfactual']['after_direct_xtest']=pointer
   report['input_counterfactual']['direct_xtest_yaw_observed']=abs((pointer['viewangles'][1]-after['viewangles'][1]+180)%360-180)>1
  if a.native_mouse_counterfactual:
   records=[]
   for slot in (0,1):
    before=native(folders[0],slot)
    input_env=dict(env,DISPLAY=report['owned_input_surface']['display'])
    event=subprocess.run(['wine',str(input_helper),str(folders[slot]).replace('/','\\'),engine,'-200','0'],env=input_env,capture_output=True,text=True,timeout=15)
    time.sleep(.2);after=native(folders[0],slot);local=native(folders[slot],0)
    try:delivery=json.loads(event.stdout)
    except ValueError:delivery={'stdout':event.stdout,'stderr':event.stderr}
    records.append({'slot':slot,'before':before,'after':after,'local':local,'native_injection':delivery,'delivery_ok':event.returncode==0,'returncode':event.returncode,'yaw_observed':abs((after['viewangles'][1]-before['viewangles'][1]+180)%360-180)>1})
   report['native_mouse_counterfactual']={'scope':'native owned-window SendInput only; not physical mouse hardware','players':records}
   if all(r['delivery_ok'] for r in records) and records[0]['yaw_observed'] and not records[1]['yaw_observed']:raise RuntimeError('Owned native mouse injection works on Host but not actual peer')
  if a.equipment_checkpoint_only:
   checkpoint_proof();report['functional']='PASS'
   return {'scope':'natural Pathfinder initial recipe and actual owner checkpoint only; no Use or mission completion',
           'checks':['original natural parachute completed','fresh remote received exact original slots/ammunition; active own Game/CG M1 and exactNative ACK','normal remote Colt choice fired own ammunition','actual checkpoint restored own Colt/consumed ammo without starting-kit repeat','legbag/beacon Use not exercised'],
           'evidence':evidence_summary()}
  bag=[float(v['coop_pathfinder_qa_bag_'+axis]) for axis in 'xyz'];beacon=[float(v['coop_pathfinder_qa_beacon_'+axis]) for axis in 'xyz']
  report['world_targets']={'bag':bag,'beacon':beacon}
  if math.dist(initial['host'][0]['position'],bag)<512:raise RuntimeError('Host naturally too close for outside-use-radius negative; no scene rearrangement substituted')
  pulse(1,'+activate',.25)
  if values().get('coop_pathfinder_qa_objective_1_count')=='1':raise RuntimeError('Out-of-range owner Use unexpectedly completed legbag')
  # Pinned map node_pathnode corridor through the initial farm/road, rather
  # than a straight line through its solid hedgerow. These are input targets;
  # no entity, collision, AI, objective or original catch-up rule is changed.
  route=[(-128,355,0),(202,355,37),(282,527,38),(255,743,39),(208,996,39),
         (214,1249,39),(560,1117,32),(576,1357,32),(608,1693,40),
         (744,2013,32),(800,2349,32),(784,2621,16),(672,2917,24),
         (504,3197,24),(360,3605,32),(168,3789,32)]
  if a.arranged_interactions:
   entity=int(v['coop_pathfinder_qa_bag_entity'])
   qa.command(folders[0],'cooplook 0 %d 1000\ncooplook 1 %d 300' % (entity,entity));time.sleep(.5)
   report['bag_actor_setup']={'entity':entity,'host_distance':1000,'peer_distance':300,'native':observe('arranged_bag_start')}
  else:
   report['input_waypoints']=route
   for point in route:approach(point,stop=48)
  approach(bag);before=stable('before_legbag');use(bag,1);after=stable('after_legbag');unchanged(before,after)
  v=values()
  if v.get('coop_pathfinder_qa_legbag_actor')!='1' or float(v.get('coop_pathfinder_qa_legbag_host_distance','0'))<512 or v.get('coop_pathfinder_qa_bag_exists')!='0':raise RuntimeError('Legbag original remote actor/world deletion proof missing')
  if a.arranged_interactions:
   entity=int(v['coop_pathfinder_qa_beacon_entity'])
   qa.command(folders[0],'cooplook 0 %d 1000\ncooplook 1 %d 300' % (entity,entity));time.sleep(.5)
   report['beacon_actor_setup']={'entity':entity,'host_distance':1000,'peer_distance':300,'native':observe('arranged_beacon_start')}
  approach(beacon);before=stable('before_beacon');use(beacon,2);after=stable('after_beacon');unchanged(before,after)
  v=values()
  if v.get('coop_pathfinder_qa_beacon_actor')!='1' or float(v.get('coop_pathfinder_qa_beacon_host_distance','0'))<512 or v.get('coop_pathfinder_qa_beacon_model')!='xmodel/eureka_beacon':raise RuntimeError('Beacon original remote actor/model proof missing')
  pulse(1,'+activate',.25);v=values()
  if any(v.get('coop_pathfinder_qa_objective_'+str(i)+'_count')!='1' for i in (1,2)):raise RuntimeError('Original objective completed more than once')
  before=stable('before_real_remote_fire');pulse(1,'+attack',.35);after=stable('after_real_remote_fire')
  if sum(after['host'][1]['clip'])>=sum(before['host'][1]['clip']):raise RuntimeError('Actual remote selected weapon did not consume ammunition')
  if any(after['host'][0][k]!=before['host'][0][k] for k in ('inventory','stock','clip','selected')):raise RuntimeError('Remote fire changed Host inventory/selection/ammo')
  if a.checkpoint:checkpoint_proof()
  report['world_result']=v;report['functional']='PASS'
  return {'scope':('isolated actual remote Pathfinder legbag/beacon activation; not natural tutorial/route or mission completion' if a.arranged_interactions else 'natural Pathfinder intro and actual remote legbag/beacon Use; not mission completion'),
          'checks':[('explicit native actor setup at original objects; preceding intro/tutorial/route not certified' if a.arranged_interactions else 'original parachute completed without skipping or arranging actors'),'actual remote movement/look/Use with Host outside512 units','original bag deleted, beacon model changed, objectives1/2 completed exactly once','own Game+local CG selection checked; shared Use preserved personal inventories/ammunition','actual remote selected weapon fired, consumed own ammo and left Host unchanged',('actual checkpoint preserved user-selected Colt and consumed ammo without recipe reapply' if a.checkpoint else 'checkpoint not requested; no preservation acceptance claim')],
          'evidence':evidence_summary()}
 try:
  status=qa.main(argv,scenario=scenario);report['status']='PASS' if status==0 and report.get('functional')=='PASS' else 'FAIL'
 except Exception as error:report['error']=str(error)
 finally:
  (out/'pathfinder-use-proof.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(__file__,out/'qa_pathfinder_use.py')
  for folder in folders:shutil.copy2(folder/root/'zzzz_coop_triggers.pk3',out/(folder.name+'-pathfinder-overlay.pk3'))
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
