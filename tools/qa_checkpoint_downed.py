#!/usr/bin/env python3
"""Actual saved Alive/Downed role isolation; not campaign completion."""
import argparse,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
import qa_coop as qa
from qa_pathfinder_use import pose_difference
from build_campaign_patch import build_trigger_patch,quarantine_obsolete_qa_trigger_overlays


def assert_saved_role(record, target, downed):
 """Explicit role decides eligibility/posture, never HP1 alone."""
 player=record['state']['players'][target];native=record['host'][target]
 if player['downed'] is not downed:raise RuntimeError('Native checkpoint lost explicit saved role')
 if native['health']!=1 or native['entity_health']!=1:raise RuntimeError('Native checkpoint lost actual saved health1')
 if (downed and not native['pm_flags']&1) or (not downed and native['pm_flags']&3):raise RuntimeError('Native checkpoint changed saved ordinary/prone posture')
 expected='INELIGIBLE' if downed else 'ELIGIBLE'
 if record['cvars'].get(f'coop_actor_{target}_state')!=expected:raise RuntimeError('Saved actor role eligibility differs')


def parse_nonprone_save_boundary(text,slot):
 pattern=r'save-observe: phase=(open|close) save=(\S+) slot=(\d+) role=(\d+) flags=(\d+) health=(-?\d+) view=([^ ]+) prone=([^\r\n]+)'
 rows=[]
 for match in re.finditer(pattern,text):
  phase,save,actual,role,flags,health,view,prone=match.groups()
  if int(actual)!=slot:continue
  rows.append({'phase':phase,'save':save,'slot':slot,'role':int(role),'flags':int(flags),'health':int(health),
               'view':[float(v) for v in view.split(',')],'prone':[float(v) for v in prone.split(',')]})
 pairs=rows[-2:]
 valid=(len(pairs)==2 and [r['phase'] for r in pairs]==['open','close'] and pairs[0]['save']==pairs[1]['save']
        and all(r['role']==2 and r['health']==1 and not r['flags']&1 for r in pairs))
 return {'valid_nonprone_downed_source':valid,'observations':rows}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for flag in ('source','run','runtime-dir'):p.add_argument('--'+flag,type=Path,required=True)
 p.add_argument('--variant',choices=('cod1','uo'),default='cod1')
 p.add_argument('--mode',choices=('guest-down','host-down','standing-one-hp'),default='guest-down')
 p.add_argument('--immediate-save',action='store_true',help='queue genuine damage and save together; requires native open/close Downed but not-prone trace')
 p.add_argument('--port',type=int,default=29950);p.add_argument('--timeout',type=int,default=180)
 a=p.parse_args();target=0 if a.mode=='host-down' else 1;reviver=1-target;downed=a.mode!='standing-one-hp';basename='qa_role_'+a.mode.replace('-','_');out=a.run.resolve();folders=[out/'host',out/'join1'];root='Main' if a.variant=='cod1' else 'uo'
 if a.immediate_save and a.mode!='guest-down':p.error('--immediate-save is the bounded actual guest-down fixture')
 basename+= '_immediate' if a.immediate_save else ''
 executed_source=Path(__file__).read_bytes()
 argv=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant',a.variant,'--map','training','--players','2','--port',str(a.port),'--timeout',str(a.timeout),'--duration','3']
 if qa.main(argv+['--prepare-only']):return 1
 for folder in folders:
  quarantine_obsolete_qa_trigger_overlays(folder)
  build_trigger_patch(a.source.resolve(),folder/root/'zzzz_coop_triggers.pk3',a.variant)
 source=out/'qa-campaign-player.cpp';source.write_bytes((qa.ROOT/'campaign_patches/qa_campaign_player.cpp').read_bytes())
 helper=out/'qa-campaign-player.exe'
 subprocess.run(['i686-w64-mingw32-g++',str(source),'-o',str(helper),'-static','-O2','-std=c++17','-mwindows'],check=True)
 env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all')
 report={'status':'FAIL','scope':__doc__,'variant':a.variant,'mode':a.mode,'immediate_save':a.immediate_save,'target':target,'runner_sha256':hashlib.sha256(executed_source).hexdigest(),'setup':'Original training; actual native damage, other owner alive. Observer-only cooplook camera arrangement96units; target never teleported. No direct role flag/health setter.'}
 def native(folder,slot):
  r=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),str(slot),a.variant],env=env,text=True,capture_output=True,check=True,timeout=15)
  return json.loads(r.stdout)
 def cvars():
  text=(folders[0]/root/'console.log').read_text(errors='replace')
  return dict(re.findall(r'^\s*cvar set (coop_[a-z0-9_]+)\s+(.*?)\r?$',text,re.M))
 def observe():return {'state':qa.read_state(folders[0]),'host':[native(folders[0],i) for i in range(2)],'local':[native(f,0) for f in folders],'cvars':cvars()}
 def wait(check,label,timeout=40):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   for f in folders:
    errors=qa.process_log_errors(f)
    if errors:raise RuntimeError(label+': '+errors[0])
   r=check()
   if r:return r
   time.sleep(.1)
  raise RuntimeError('Timeout: '+label)
 def scenario(_folders,processes,states):
  wait(lambda:all(p['pm_type']==0 and not p['linked'] and not p['downed'] for p in qa.read_state(folders[0])['players'][:2]),'two actual ordinary live owners')
  report['initial']=observe()
  save=folders[0]/root/'save'/(basename+'.svg');meta=Path(str(save)+'.coopowners')
  save.unlink(missing_ok=True);meta.unlink(missing_ok=True)
  generation=qa.read_state(folders[0])['world_wire']['generation']
  if a.immediate_save:
   # Genuine owned input makes the pre-save facing differ from map-entry yaw.
   qa.command(folders[target],'+forward',joiner=True);time.sleep(.75);qa.command(folders[target],'-forward',joiner=True)
   qa.command(folders[target],'set cl_yawspeed 90\n+left',joiner=True);time.sleep(1.25);qa.command(folders[target],'-left',joiner=True);time.sleep(.4)
   report['before_inline_damage_save']=observe()
  if report['initial']['host'][target]['health']!=600:raise RuntimeError('Fixture requires actual native initial600 health')
  damage=100000 if downed else 599
  text_before=(folders[0]/'codcoop.log').read_text(errors='replace')
  qa.command(folders[0],f'coopgod {target} 0\ncoopkill {target} {damage}'+('\nsavegame '+basename if a.immediate_save else ''))
  if a.immediate_save:
   wait(lambda:save.exists() and save.stat().st_size>1024 and meta.exists(),'inline genuine damage/save completed')
   for source in (save,meta):shutil.copy2(source,out/source.name)
   report['saved_files']={source.name:hashlib.sha256(source.read_bytes()).hexdigest() for source in (save,meta)}
   native_log=(folders[0]/'codcoop.log').read_text(errors='replace')[len(text_before):]
   report['source_boundary']=parse_nonprone_save_boundary(native_log,target)
   if not report['source_boundary']['valid_nonprone_downed_source']:raise RuntimeError('Immediate Downed-before-native-prone source boundary not reproduced')
  wait(lambda:qa.read_state(folders[0])['players'][target]['downed']==downed and qa.read_state(folders[0])['players'][target]['health']==1,'genuine native damage enters expected explicit role')
  wait(lambda:cvars().get(f'coop_actor_{target}_state')==('INELIGIBLE' if downed else 'ELIGIBLE'),'native eligibility for actual saved role')
  # The immediate save already exists: arranging a camera now would corrupt
  # the expected saved observer pose. Normal delayed cases arrange before save.
  if not a.immediate_save:qa.command(folders[0],f'cooplook {reviver} {target} 96');time.sleep(.5)
  saved=observe();report['saved']=saved
  assert_saved_role(saved,target,downed)
  if a.immediate_save:
   source_view=report['source_boundary']['observations'][-1]['view']
   if any(abs((a-b+180)%360-180)>.01 for a,b in zip(source_view,saved['host'][target]['viewangles'])):raise RuntimeError('Post-save observer view differs from actual native save source')
   before=report['before_inline_damage_save']['host'][target]
   if sum((a-b)**2 for a,b in zip(before['position'],saved['host'][target]['position']))>.01:raise RuntimeError('Inline damage-save position moved before native proof')
  if saved['state']['players'][reviver]['health']<=1 or saved['state']['players'][reviver]['downed']:raise RuntimeError('Other real player must remain alive')
  for i,f in enumerate(folders):qa.command(f,'screenshot',joiner=i!=0)
  time.sleep(.5)
  if not a.immediate_save:qa.command(folders[0],'savegame '+basename)
  wait(lambda:save.exists() and save.stat().st_size>1024 and meta.exists(),'actual native downed checkpoint completed')
  for source in (save,meta):shutil.copy2(source,out/source.name)
  report['saved_files']={source.name:hashlib.sha256(source.read_bytes()).hexdigest() for source in (save,meta)}
  savedtime=qa.read_state(folders[0])['server_time'];wait(lambda:qa.read_state(folders[0])['server_time']>savedtime+3000,'world advances after saved downed owner')
  oldtime=qa.read_state(folders[0])['server_time'];qa.command(folders[0],'loadgame '+basename)
  wait(lambda:(h:=qa.read_state(folders[0])) and h['world_wire']['generation']!=generation and h['server_time']<oldtime-1000,'actual native saved-world rollback',a.timeout)
  wait(lambda:(h:=qa.read_state(folders[1])) and h['joined'] and h['snapshot_num']>0 and qa.read_state(folders[0])['players'][1]['active'],'actual remote rejoined saved downed world',a.timeout)
  time.sleep(1);restored=observe();report['restored']=restored
  for i,f in enumerate(folders):qa.command(f,'screenshot',joiner=i!=0)
  time.sleep(.5)
  assert_saved_role(restored,target,downed)
  report['pose']=[{'slot':slot,**pose_difference(saved['host'][slot],restored['host'][slot])} for slot in range(2)]
  if any(not p['within_tolerance'] for p in report['pose']):raise RuntimeError('Downed checkpoint lost saved owner pose')
  cg=restored['local'][target]['cgame']
  if cg['snapshot_client']!=target or not pose_difference(saved['host'][target],{'position':cg['predicted_position'],'viewangles':cg['predicted_angles']})['within_tolerance']:raise RuntimeError('Downed own current CGame camera/position mismatch')
  for slot in range(2):
   for key in ('inventory','stock','clip','selected'):
    if saved['host'][slot][key]!=restored['host'][slot][key]:raise RuntimeError('Downed checkpoint changed personal '+key)
  if downed:
   qa.command(folders[0],f'cooplook {reviver} {target} 64');time.sleep(.3);qa.command(folders[reviver],'+activate',joiner=reviver!=0)
   try:wait(lambda:not qa.read_state(folders[0])['players'][target]['downed'] and qa.read_state(folders[0])['players'][target]['health']>1,'normal other-owner actual three-second Use revive',8)
   finally:qa.command(folders[reviver],'-activate',joiner=reviver!=0)
   wait(lambda:cvars().get(f'coop_actor_{target}_state')=='ELIGIBLE','revived actor eligible')
   report['revived']=observe()
  else:
   before=qa.read_state(folders[0])['players'][target]
   qa.command(folders[target],'+back',joiner=target!=0);time.sleep(.7);qa.command(folders[target],'-back',joiner=target!=0)
   wait(lambda:qa.read_state(folders[0])['players'][target]['command_time']>before['command_time'],'restored Alive1HP actual input clock')
   after=observe();report['after_normal_input']=after
   if sum((a-b)**2 for a,b in zip(before['position'],after['host'][target]['position']))<64:raise RuntimeError('Restored standing1HP owner cannot move')
   assert_saved_role(after,target,False)
  report['functional']='PASS'
  raw=out/'downed-checkpoint-native-evidence.json';raw.write_text(json.dumps(report,indent=2)+'\n')
  return {'scope':__doc__,'checks':['actual native damage produces explicit intended Alive or Downed role atHP1','native save/load and real remote rejoin','saved downed flag/PS+GE1/eligibility and personal inventory retained','normal other-owner three-second Use revives Downed, or standing Alive1HP moves normally'],
          'evidence':{'raw':str(raw),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}}
 try:
  status=qa.main(argv,scenario=scenario);report['status']='PASS' if status==0 and report.get('functional')=='PASS' else 'FAIL'
 except Exception as error:report['error']=str(error)
 finally:
  (out/'downed-checkpoint-proof.json').write_text(json.dumps(report,indent=2)+'\n');(out/Path(__file__).name).write_bytes(executed_source)
 return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
