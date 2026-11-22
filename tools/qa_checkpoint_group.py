#!/usr/bin/env python3
"""Four actual owners: ordinary pose/vitals/inventory native checkpoint; no mission completion."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import qa_coop as qa
from qa_pathfinder_use import pose_difference
from qa_checkpoint_downed import assert_saved_role
from build_campaign_patch import build_trigger_patch, quarantine_obsolete_qa_trigger_overlays


def assert_owner_restore(saved, restored):
    """Strict per-seat oracle; never match a guest against another seat/current RAM."""
    if len(saved['host']) != 4 or len(restored['host']) != 4 or len(restored['local']) != 4:
        raise RuntimeError('Four native owners required')
    result=[]
    for slot in range(4):
        old,new=saved['host'][slot],restored['host'][slot]
        if old['clientnum']!=slot or new['clientnum']!=slot:
            raise RuntimeError('Wrong native owner slot')
        pose=pose_difference(old,new)
        if not pose['within_tolerance']:raise RuntimeError(f'Owner {slot} saved pose lost')
        for key in ('health','entity_health','inventory','stock','clip','selected'):
            if old[key]!=new[key]:raise RuntimeError(f'Owner {slot} saved {key} lost')
        cg=restored['local'][slot]['cgame']
        if cg['snapshot_client']!=slot:raise RuntimeError('Local current CGame snapshot has wrong owner')
        for field in ('snapshot','desired','predicted'):
            if cg[field]['name'].lower()!=new['selected']['name'].lower():raise RuntimeError('Own CGame weapon differs')
        cgpose={'position':cg['predicted_position'],'viewangles':cg['predicted_angles']}
        if not pose_difference(old,cgpose)['within_tolerance']:raise RuntimeError('Own CGame saved camera/position lost')
        if math.dist(old['position'],cg['snapshot_position'])>8:raise RuntimeError('Own current snapshot position lost')
        result.append({'slot':slot,'pose':pose,'health':new['health'],'entity_health':new['entity_health'],
                       'selected':new['selected'],'current_snapshot_client':cg['snapshot_client']})
    return result


def decode_role_v2(data, svg):
    """Read-only native Win32 Metadata ABI: V2=224B, roles at216, Owner stride16.

    Verified against pinned save_provenance.h static_assert and native files;
    this is not a proposed portable wire format or a metadata writer.
    """
    if len(data)!=224 or struct.unpack_from('<II',data)!=(0x43535049,2):raise ValueError('Expected exact native RoleV2 metadata')
    roles=list(data[216:220])
    if any(role not in (1,2) for role in roles):raise ValueError('All four native saved owner roles required')
    expected=hashlib.sha256(svg).hexdigest()
    if data[82:147].split(b'\0',1)[0].decode('ascii')!=expected:raise ValueError('RoleV2 hash does not bind actual SVG')
    owners=[]
    for slot in range(4):
        lease,address,port=struct.unpack_from('<QIH',data,152+slot*16)
        if slot and not lease:raise ValueError('Actual remote saved owner lease missing')
        owners.append({'slot':slot,'role':roles[slot],'lease':lease,'address':address,'port':port})
    return {'schema':2,'native_size':len(data),'roles':roles,'owners':owners,'svg_sha256':expected,
            'session':struct.unpack_from('<Q',data,8)[0],'map':data[18:82].split(b'\0',1)[0].decode('ascii')}


def assert_mixed_roles(record):
    assert_saved_role(record,1,False)
    assert_saved_role(record,2,True)
    for slot in (0,3):
        player=record['state']['players'][slot];owner=record['host'][slot]
        if player['downed'] or owner['health']!=(600 if slot==0 else 450) or owner['entity_health']!=owner['health']:
            raise RuntimeError('Mixed ordinary owner state lost')
        if record['cvars'].get(f'coop_actor_{slot}_state')!='ELIGIBLE':raise RuntimeError('Mixed ordinary actor eligibility lost')
    return [{'slot':i,'downed':record['state']['players'][i]['downed'],'health':record['host'][i]['health'],
             'actor':record['cvars'].get(f'coop_actor_{i}_state')} for i in range(4)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('source','run','runtime-dir'):parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--variant',choices=('cod1','uo'),default='cod1')
    parser.add_argument('--port',type=int,default=29950)
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--mixed-roles',action='store_true',help='HostAlive600; guestAlive1, guestDowned1, guestAlive450')
    args=parser.parse_args();out=args.run.resolve();executed_source=Path(__file__).read_bytes();root='Main' if args.variant=='cod1' else 'uo'
    argv=['--source',str(args.source.resolve()),'--run',str(out),'--runtime-dir',str(args.runtime_dir.resolve()),
          '--variant',args.variant,'--map','training','--players','4','--port',str(args.port),'--timeout',str(args.timeout),'--duration','3']
    if qa.main(argv+['--prepare-only']):return 1
    folders=[out/n for n in ('host','join1','join2','join3')]
    for folder in folders:
        quarantine_obsolete_qa_trigger_overlays(folder)
        build_trigger_patch(args.source.resolve(),folder/root/'zzzz_coop_triggers.pk3',args.variant)
        for name in ('qa-render-models.txt','qa-deferred-models.txt'):
            path=folder/name
            if path.exists():
                target=out/'quarantined-group-inputs'/str(time.time_ns())/folder.name/name
                target.parent.mkdir(parents=True);path.rename(target)
    observer=out/'qa-campaign-player.cpp';observer.write_bytes((qa.ROOT/'campaign_patches/qa_campaign_player.cpp').read_bytes())
    helper=out/'qa-campaign-player.exe'
    subprocess.run(['i686-w64-mingw32-g++',str(observer),'-o',str(helper),'-static','-O2','-std=c++17','-mwindows'],check=True)
    report={'status':'FAIL','scope':__doc__,'mixed_roles':args.mixed_roles,'variant':args.variant,'input':[],'observations':[],'runner_sha256':hashlib.sha256(executed_source).hexdigest(),
            'setup':'Original training scripts; saved owners separated by actual input, no pre-save teleport, forced kits, health memory setter or objective changes. Mixed-role post-load revival explicitly arranges only Host1000/peer3at64 from target2.',
            'observer_sha256':hashlib.sha256(observer.read_bytes()).hexdigest()}
    env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all')
    def native(folder,slot):
        proc=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),str(slot),args.variant],env=env,
                            capture_output=True,text=True,check=True,timeout=15)
        return json.loads(proc.stdout)
    def observe(label):
        host=[native(folders[0],slot) for slot in range(4)]
        record={'phase':label,'host':host,'local':[host[0]]+[native(f,0) for f in folders[1:]],'state':qa.read_state(folders[0]),'cvars':cvars()}
        report['observations'].append(record);return record
    def wait(check,label,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            for folder in folders:
                errors=qa.process_log_errors(folder)
                if errors:raise RuntimeError(label+': '+errors[0])
            result=check()
            if result:return result
            time.sleep(.12)
        raise RuntimeError('Timeout: '+label)
    def pulse(slot,action,duration):
        before=qa.read_state(folders[0])['players'][slot]
        qa.command(folders[slot],action,joiner=slot!=0)
        try:time.sleep(duration)
        finally:qa.command(folders[slot],'-'+action[1:],joiner=slot!=0)
        wait(lambda:qa.read_state(folders[0])['players'][slot]['command_time']>before['command_time'],'actual owner input clock')
        time.sleep(.2)
        after=qa.read_state(folders[0])['players'][slot]
        report['input'].append({'slot':slot,'action':action,'duration':duration,'before':before,'after':after})
    def cvars():
        log=(folders[0]/root/'console.log').read_text(errors='replace')
        return dict(re.findall(r'^\s*cvar set (coop_[a-z0-9_]+)\s+(.*?)\r?$',log,re.M))
    def ordinary():
        h=qa.read_state(folders[0]);return h and all(p['pm_type']==0 and not p['linked'] and not p['downed'] and p['health']>1 for p in h['players'])
    def scenario(_folders,processes,states):
        wait(ordinary,'all four actual ordinary standing owners',args.timeout)
        initial=observe('initial_connected')
        # Different normal input directions separate the initially adjacent bodies.
        for slot,action in enumerate(('+back','+forward','+moveleft','+moveright')):
            pulse(slot,action,.75)
            qa.command(folders[slot],'set cl_yawspeed 90',joiner=slot!=0)
            pulse(slot,'+left',.4+.5*slot)
        for slot,damage in (((1,599),(2,100000),(3,150)) if args.mixed_roles else ((1,50),(2,100),(3,150))):
            qa.command(folders[0],f'coopgod {slot} 0\ncoopkill {slot} {damage}')
        if args.mixed_roles:
            wait(lambda:[p['health'] for p in qa.read_state(folders[0])['players']]==[600,1,1,450] and [p['downed'] for p in qa.read_state(folders[0])['players']]==[False,False,True,False],'actual distinct mixed Alive/Downed native roles')
        else:
            wait(lambda:all(1<p['health']<initial['host'][p['slot']]['health'] for p in qa.read_state(folders[0])['players'][1:]),'three genuinely damaged healthy remote owners')
        time.sleep(1)
        saved=observe('saved_owner_baseline');report['saved']=saved
        for slot,p in enumerate(saved['host']):
            if p['pm_type']!=0 or p['linked'] or (not args.mixed_roles and (p['pm_flags']&3 or p['health']<=1)) or p['entity_health']!=p['health']:
                raise RuntimeError('Fixture requires coherent healthy plain native owner')
            if not args.mixed_roles and slot and p['health']!=initial['host'][slot]['health']-50*slot:raise RuntimeError('Distinct native damage did not produce exact owner health')
        if args.mixed_roles:report['saved_roles']=assert_mixed_roles(saved)
        if saved['host'][0]['health']!=initial['host'][0]['health']:raise RuntimeError('Damage changed Host')
        if min(math.dist(a['position'],b['position']) for i,a in enumerate(saved['host']) for b in saved['host'][i+1:])<24:
            raise RuntimeError('Actual input did not sufficiently separate four owners')
        if min(abs((a['viewangles'][1]-b['viewangles'][1]+180)%360-180) for i,a in enumerate(saved['host']) for b in saved['host'][i+1:])<10:
            raise RuntimeError('Actual input did not sufficiently separate four owner look directions')
        old_receipts={key:value for key,value in cvars().items() if re.fullmatch(r'coop_spawn_ticket_[0-3]',key)}
        save=folders[0]/root/'save/qa_group_checkpoint.svg';meta=Path(str(save)+'.coopowners')
        save.unlink(missing_ok=True);meta.unlink(missing_ok=True)
        generation=qa.read_state(folders[0])['world_wire']['generation']
        qa.command(folders[0],'savegame qa_group_checkpoint')
        wait(lambda:save.exists() and save.stat().st_size>1024 and meta.exists(),'actual completed four-owner SVG and ownership sidecar')
        for source in (save,meta):shutil.copy2(source,out/source.name)
        report['saved_files']={source.name:hashlib.sha256(source.read_bytes()).hexdigest() for source in (save,meta)}
        if args.mixed_roles:
            report['native_role_metadata']=decode_role_v2(meta.read_bytes(),save.read_bytes())
            if report['native_role_metadata']['roles']!=[1,1,2,1]:raise RuntimeError('Native RoleV2 seat mapping differs from actual saved roles')
        for slot in range(4):
            if not (args.mixed_roles and slot==2):pulse(slot,'+forward',.45)
            pulse(slot,'+right',.3)
        damaged_after=3 if args.mixed_roles else 2
        qa.command(folders[0],f'coopkill {damaged_after} 10')
        wait(lambda:qa.read_state(folders[0])['players'][damaged_after]['health']==saved['host'][damaged_after]['health']-10,'latest guest health differs from saved health')
        changed=observe('changed_after_save');report['changed_after_save']=changed
        for slot in range(4):
            if not (args.mixed_roles and slot==2) and math.dist(saved['host'][slot]['position'],changed['host'][slot]['position'])<8:raise RuntimeError('Actual post-save input did not change owner position')
            if max(abs((a-b+180)%360-180) for a,b in zip(saved['host'][slot]['viewangles'],changed['host'][slot]['viewangles']))<5:raise RuntimeError('Actual post-save input did not change owner look')
        oldtime=qa.read_state(folders[0])['server_time'];qa.command(folders[0],'loadgame qa_group_checkpoint')
        wait(lambda:(h:=qa.read_state(folders[0])) and h['world_wire']['generation']!=generation and h['server_time']<oldtime-1000,'real saved-world clock rollback',args.timeout)
        def rejoined():
            states=[qa.read_state(f) for f in folders]
            return all(states) and all(states[i]['joined'] and states[i]['slot']==i and states[i]['snapshot_num']>0 for i in range(1,4)) and all(p['active'] for p in states[0]['players'][1:])
        wait(rejoined,'all three actual peers rejoin saved own slots',args.timeout)
        wait(lambda:all(cvars().get(f'coop_inventory_{slot}_state')=='PRESERVED' for slot in range(4)),'all four native preserved lifecycle receipts')
        # Wait for real owner commands to complete the native view-delta seed.
        time.sleep(2);restored=observe('restored_saved_owners');report['restored']=restored
        report['owners']=assert_owner_restore(saved,restored)
        if args.mixed_roles:
            report['restored_roles']=assert_mixed_roles(restored)
            for n,f in enumerate(folders):qa.command(f,'screenshot',joiner=n!=0)
            time.sleep(.5)
            # Explicit observer arrangement: Host is1000 away; real third peer3
            # is64 away and must supply the ordinary three-second Use input.
            qa.command(folders[0],'cooplook 0 2 1000\ncooplook 3 2 64');time.sleep(.5)
            setup=observe('explicit_third_peer_revive_setup');report['revive_setup']=setup
            if math.dist(setup['host'][0]['position'],setup['host'][2]['position'])<=80:raise RuntimeError('Host too near third-peer revive isolation')
            qa.command(folders[3],'+activate',joiner=True)
            try:wait(lambda:not qa.read_state(folders[0])['players'][2]['downed'] and qa.read_state(folders[0])['players'][2]['health']>1,'actual third peer normal Use revives saved downed guest',8)
            finally:qa.command(folders[3],'-activate',joiner=True)
            report['third_peer_revived']=observe('after_third_peer_normal_revive')
        if any(cvars().get(key)!=value for key,value in old_receipts.items()):raise RuntimeError('Checkpoint issued fresh-owner tickets')
        report['receipts']=cvars()
        before=qa.read_state(folders[0]);time.sleep(1);qa.assess_liveness(before,qa.read_state(folders[0]),4)
        for slot in range(4):
            origin=native(folders[0],slot)['position'];pulse(slot,'+back',.5)
            if math.dist(origin,native(folders[0],slot)['position'])<8:raise RuntimeError('Restored owner cannot move through actual input')
            if restored['host'][slot]['selected']['name']!='none':
                before=native(folders[0],slot);pulse(slot,'+attack',.3);after=native(folders[0],slot)
                if sum(after['clip'])>=sum(before['clip']):raise RuntimeError('Armed restored owner did not consume own clip')
        report['functional']='PASS'
        raw=out/'checkpoint-group-native-evidence.json';raw.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        return {'scope':__doc__,'checks':['four actual native owner command clocks','distinct ordinary owner poses and real native damage','saved SVG differs from later live movement/look/health','all three rejoin own slots; exact saved inventory/vitals and bounded saved pose','own current CG snapshot/client/view/position match each owner','native PRESERVED and unchanged tickets; no fresh recipe','all four move via actual input after load; armed owners fire; mixed case peer3 revives2 with Host outside80'],
                'evidence':{'raw':str(raw),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'owners':report['owners'],'training_unarmed_valid':True}}
    try:
        code=qa.main(argv,scenario=scenario);report['status']='PASS' if code==0 and report.get('functional')=='PASS' else 'FAIL'
    except Exception as error:report['error']=str(error)
    finally:
        (out/'checkpoint-group-proof.json').write_text(json.dumps(report,indent=2)+'\n')
        (out/Path(__file__).name).write_bytes(executed_source)
        for folder in folders:shutil.copy2(folder/root/'zzzz_coop_triggers.pk3',out/(folder.name+'-production-overlay.pk3'))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
