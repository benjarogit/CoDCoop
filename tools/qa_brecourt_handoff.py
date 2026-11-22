#!/usr/bin/env python3
"""Isolated actual-Joiner original Brecourt handoff; NOT a campaign playthrough."""
import argparse,json,math,re,shutil,time
from pathlib import Path
import qa_coop
from build_campaign_patch import quarantine_obsolete_qa_trigger_overlays, build_trigger_patch

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
 p.add_argument('--runtime-dir',type=Path,required=True);p.add_argument('--variant',choices=('cod1','uo','sp_improved','united_fronts'),default='cod1')
 p.add_argument('--scenario',choices=('joiner-positive','standing-one-hp','downed-negative','dead-boundary','host-control'),default='joiner-positive')
 p.add_argument('--port',type=int,default=29950);p.add_argument('--timeout',type=int,default=120)
 a=p.parse_args();out=a.run.resolve();folder={'cod1':'Main','uo':'uo','sp_improved':'sp_improved','united_fronts':'UnitedFronts'}[a.variant]
 base=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant',a.variant,'--map','brecourt','--players','2','--timeout',str(a.timeout),'--port',str(a.port),'--duration','2']
 if qa_coop.main(base+['--prepare-only']):return 1
 quarantined=[]
 for n in ['host','join1']:
  # Reused copies can retain unrelated UF asset-bootstrap QA inputs. This
  # scene uses normal profile assets; keep those inputs as evidence but never
  # feed an old profile's asset names into the next native renderer startup.
  for name in ('qa-render-models.txt','qa-deferred-models.txt'):
   old_input=out/n/name
   if old_input.exists():
    target=out/'fixture-inputs-quarantined'/str(time.time_ns())/n/name
    target.parent.mkdir(parents=True);old_input.rename(target)
    quarantined.append(str(target))
  for old in ('zzzzzzzz_qa_brecourt.pk3','zz_codcoop_brecourt_qa.pk3'):
   (out/n/folder/old).unlink(missing_ok=True)
  quarantine_obsolete_qa_trigger_overlays(out/n)
  build_trigger_patch(a.source.resolve(),out/n/folder/'zzzz_coop_triggers.pk3',a.variant,qa=True)
 report={'status':'NOT_RUN','scope':__doc__,'variant':a.variant,'scenario':a.scenario,'arrangement':'QA models the post-goal precondition at the actual live NPC position; original NPC navigation and battle are not tested. Original post-docs clip is nonsolid and scene axis actors removed. Players are arranged once via existing native cooplook; Joiner approach uses actual input. Explicit1/0health boundaries do not claim native damage/death history. Original shared normal post-goal NPC animation/Has_Explosives/objective4/bomb enable are not fabricated.','input':[]}
 report['quarantined_unrelated_qa_inputs']=quarantined
 sequence=0
 def values():
  s=(out/'host'/folder/'console.log').read_text(errors='replace')
  return dict(re.findall(r'^[ \t]*cvar set (coop_[a-z0-9_]+)[ \t]*(.*?)\r?$',s,re.M))
 def wait(condition,label,timeout=60):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   for n in ['host','join1']:
    error=qa_coop.process_log_errors(out/n)
    if error:raise RuntimeError(label+': '+error[0])
   result=condition()
   if result:return result
   time.sleep(.1)
  raise RuntimeError('Timeout: '+label)
 def probe():
  nonlocal sequence
  sequence+=1;qa_coop.command(out/'host','set coop_brecourt_qa_probe_seq '+str(sequence))
  return wait(lambda: (v if v.get('coop_brecourt_qa_probe_ack')==str(sequence) else None) if (v:=values()) else None,'fresh native script probe')
 def pulse(n,action,duration=.25):
  before=qa_coop.read_state(out/'host')['players'][n];target=out/('host' if n==0 else 'join1')
  qa_coop.command(target,action,joiner=n!=0)
  def ack():
   now=qa_coop.read_state(out/'host')['players'][n]
   direction=now['forward']>0 if action=='+forward' else now['forward']<0
   return now if direction and now['command_time']>before['command_time'] else None
  try:
   during=wait(ack,'native owner movement command acknowledgement',10)
   time.sleep(duration)
  finally:qa_coop.command(target,'-'+action[1:],joiner=n!=0)
  def stopped():
   now=qa_coop.read_state(out/'host')['players'][n]
   return now if now['forward']==0 and now['command_time']>during['command_time'] else None
  after=wait(stopped,'native owner movement release',10)
  distance=math.dist(during['position'],after['position'])
  report['input'].append({'slot':n,'action':action,'before':before,'ack':during,'after':after,'distance_after_ack':distance})
  return distance
 def scenario(folders,processes,states):
  wait(lambda: values().get('coop_brecourt_qa_status')=='READY_ISOLATED_NOT_CAMPAIGN','actual host/remote scene ready')
  anchor=int(values()['coop_brecourt_qa_anchor'])
  qa_coop.command(out/'host','cooplook 0 %d 400\ncooplook 1 %d 200' % (anchor,anchor))
  time.sleep(.4)
  report['native_scene_arrangement']={'command':'existing native cooplook 0/1 anchor at400/200, once before real input','anchor':anchor}
  v=probe();report['out_of_range']=v
  if v['coop_brecourt_qa_probe_actor']!='-1':raise RuntimeError('Out-of-range scene unexpectedly eligible')
  for _ in range(20):
   if float(v['coop_brecourt_qa_remote_distance'])<=85:break
   pulse(1,'+forward');v=probe()
  else:raise RuntimeError('Actual remote could not approach original handoff location')
  if float(v['coop_brecourt_qa_host_distance'])<=100 or v['coop_brecourt_qa_probe_actor']!='1':raise RuntimeError('Actual remote was not sole eligible recipient')
  report['healthy_remote']=v
  if a.scenario=='downed-negative':
   qa_coop.command(out/'host','coopkill 1 100000')
   wait(lambda: qa_coop.read_state(out/'host')['players'][1]['downed'],'actual native downed transition')
   v=probe();report['downed_remote']=v
   if v['coop_brecourt_qa_probe_actor']!='-1' or v.get('coop_actor_1_state')!='INELIGIBLE':raise RuntimeError('Downed live remote incorrectly eligible')
  elif a.scenario in ('standing-one-hp','dead-boundary'):
   health='1' if a.scenario=='standing-one-hp' else '0'
   # The native QA command writes both entity health and playerState health.
   # A GSC entity-only zero write was observed to remain at600 on a later
   # probe and is preserved as a failed boundary setup, not an eligibility pass.
   qa_coop.command(out/'host',('set coop_brecourt_qa_health_boundary 1' if health=='1' else 'coophealth 1 0'))
   time.sleep(.3);v=probe();report['explicit_health_boundary']=v
   if v.get('coop_brecourt_qa_remote_health')!=health:raise RuntimeError('Native script target health boundary did not apply')
   expected='1' if health=='1' else '-1'
   if v['coop_brecourt_qa_probe_actor']!=expected:raise RuntimeError('Native health boundary recipient mismatch')
   if health=='0' and v.get('coop_actor_1_state')!='INELIGIBLE':raise RuntimeError('Native zero-health boundary was not ineligible')
  elif a.scenario=='host-control':
   qa_coop.command(out/'host','cooplook 1 %d 200\ncooplook 0 %d 85' % (anchor,anchor));time.sleep(.4)
   v=probe();report['host_control']=v
   if v['coop_brecourt_qa_probe_actor']!='0':raise RuntimeError('Actual healthy native host not eligible')
  qa_coop.command(out/'host','set coop_brecourt_qa_run 1')
  if a.scenario in ('downed-negative','dead-boundary'):
   wait(lambda:values().get('coop_brecourt_qa_gate_waiting')=='1','original normal handoff reaches real recipient gate')
   start=qa_coop.read_state(out/'host')['server_time']
   wait(lambda:qa_coop.read_state(out/'host')['server_time']>start+3500,'native gate remains live for negative observation')
   v=values()
   if any(v.get(k)=='1' for k in ('coop_brecourt_qa_original_has_explosives','coop_brecourt_qa_original_objective4_done')) or 'coop_brecourt_qa_actor' in v:
    raise RuntimeError('Downed remote advanced actual normal handoff')
   report['negative_gate_result']=v;report['functional']='PASS'
   return {'scope':'isolated Brecourt original normal handoff '+a.scenario+' rejection; not campaign completion',
           'checks':['real connected host/remote; actual remote input entered range',('native world damage caused real downed actor' if a.scenario=='downed-negative' else 'explicitly arranged zero-health native script boundary; no death-life claim'),'original normal gate stayed live without handoff/objective4/bomb unlock for3.5native seconds'],
           'evidence':report}

  v=wait(lambda: (v if v.get('coop_brecourt_qa_original_objective4_done')=='1' and int(v.get('coop_brecourt_qa_original_bombs_enabled','0'))>0 else None) if (v:=values()) else None,'original normal NPC handoff/objective4/bombs',90)
  expected_actor='0' if a.scenario=='host-control' else '1'
  if v.get('coop_brecourt_qa_actor')!=expected_actor:raise RuntimeError('Original action used wrong actual recipient')
  if a.scenario=='joiner-positive' and float(v['coop_brecourt_qa_host_distance_at_action'])<=100:raise RuntimeError('Host entered range during actual Joiner handoff')
  report['original_world_result']=v;report['functional']='PASS'
  return {'scope':'isolated Brecourt original normal handoff '+a.scenario+'; not campaign completion',
          'checks':['actual host/remote and native actor eligibility',('native host placement control; no host input proof' if a.scenario=='host-control' else 'real Joiner input reached original100unit handoff range'),'original NPC handoff completed real objective4 and enabled original bombs'],
          'evidence':report}

 try:
  status=qa_coop.main(base,scenario=scenario);report['status']='PASS' if status==0 and report.get('functional')=='PASS' else 'FAIL'
 except Exception as error:report.update(status='FAIL',error=str(error))
 finally:
  (out/'brecourt-handoff-proof.json').write_text(json.dumps(report,indent=2)+'\n')
  shutil.copy2(__file__,out/'qa_brecourt_handoff.py')
  for n in ['host','join1']:shutil.copy2(out/n/folder/'zzzz_coop_triggers.pk3',out/(n+'-brecourt-overlay.pk3'))
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
