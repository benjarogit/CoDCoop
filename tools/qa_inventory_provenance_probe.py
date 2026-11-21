#!/usr/bin/env python3
"""Actual Alice departure / new Bob process / native saved-owner regression."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import qa_coop as qa


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('source','run','runtime-dir'): parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--variant',choices=('cod1','uo'),required=True)
    parser.add_argument('--map',default='training')
    parser.add_argument('--port',type=int,default=29938)
    parser.add_argument('--timeout',type=int,default=240)
    args=parser.parse_args(argv)
    output=args.run.resolve();host=output/'host';peer=output/'join1'
    root='Main' if args.variant=='cod1' else 'uo'
    for key in ('CODCOOP_QA_DEFER_MODELS','CODCOOP_QA_BORROW_TREES','CODCOOP_QA_DOBJ_BARRIER'):
        os.environ.pop(key,None)
    os.environ['CODCOOP_QA_HOST_BODY_GC']='1'
    report={'status':'FAIL','variant':args.variant,'scope':'numeric native loadouts and saved-seat ownership; no script-state preservation claim',
            'qa_coop_sha256':hashlib.sha256(Path(qa.__file__).read_bytes()).hexdigest()}
    original_move=qa.move_remote;original_popen=qa.subprocess.Popen;original_errors=qa.process_log_errors
    launch=None;done=False;replacement_log=None;notice=None

    def popen(cmd,*pos,**kw):
        nonlocal launch
        if isinstance(cmd,list) and cmd and cmd[0]=='wine' and len(cmd)>1 and Path(cmd[1]).parent==peer:
            launch=(list(cmd),dict(kw))
        return original_popen(cmd,*pos,**kw)

    def savegame(name,processes):
        save=host/root/'save'/f'{name}.svg';sidecar=Path(str(save)+'.coopowners')
        save.unlink(missing_ok=True);sidecar.unlink(missing_ok=True)
        qa.command(host,'savegame '+name)
        qa.wait_for(lambda:save.exists() and save.stat().st_size>1024 and sidecar.exists(),processes,args.timeout,'completed native save and atomic ownership metadata')
        return save,sidecar

    def current(): return qa.read_state(host)['peer_inventory'][0]

    def reload(name,processes):
        prior=qa.read_state(host);generation=prior['world_wire']['generation'];clock=prior['server_time']
        qa.wait_for(lambda:qa.read_state(host)['server_time']>clock+1500,processes,args.timeout,'advance beyond saved native time')
        qa.command(host,'loadgame '+name)
        def ready():
            h,p=qa.read_state(host),qa.read_state(peer)
            if h and p and h['world_wire']['generation']!=generation and p['joined'] and h['players'][1]['active'] and p['snapshot_num']>0:
                return h
        h=qa.wait_for(ready,processes,args.timeout,'new native checkpoint world and real returning peer')
        time.sleep(1)
        return qa.read_state(host)

    def move(h,p,slot,processes,timeout,action='+forward'):
        nonlocal done,replacement_log,notice
        distance=original_move(h,p,slot,processes,timeout,action)
        if done:return distance
        done=True
        if original_errors(peer):raise RuntimeError('unexpected error before intentional departure')
        report['alice']=current()
        alice_save,alice_side=savegame('qa_inventory_alice',processes)
        report['alice_sidecar_sha256']=hashlib.sha256(alice_side.read_bytes()).hexdigest()
        qa.command(peer,'coopleave',joiner=True)
        qa.wait_for(lambda:qa.read_state(peer)['role']==0 and not current()['reserved'],processes,20,'Alice explicit departure releases owned seat')
        errors=original_errors(peer)
        if errors:
            if len(errors)!=1 or errors[0].strip() not in ('ERROR: Getrennt','ERROR: Disconnected'):
                raise RuntimeError('unexpected departure error: '+repr(errors))
            notice=errors[0];report['acknowledged_departure_notice']=notice
        qa.command(peer,'quit',joiner=True)
        old=processes[1]
        if old.wait(timeout=20)!=0:raise RuntimeError('Alice native process did not exit cleanly')
        archive=output/'alice-peer';archive.mkdir(exist_ok=True)
        for file in (peer/'codcoop_join.log',peer/root/'console.log'):
            if file.exists():shutil.copy2(file,archive/file.name)
        (peer/'qa-state.json').unlink(missing_ok=True)
        cmd,kw=launch;replacement_log=open(output/'process-bob.log','wb');kw.update(stdout=replacement_log,stderr=replacement_log)
        cmd+=['+set','name','Bob']
        processes[1]=original_popen(cmd,**kw)
        qa.wait_for(lambda:(s:=qa.read_state(peer)) and s['role']==2 and s['joined'] and current()['reserved'],processes,args.timeout,'Bob new native process enters Alice former slot')
        report['bob_new']=current()
        if report['bob_new']['lease']==report['alice']['lease'] or report['bob_new']['endpoint_port']==report['alice']['endpoint_port']:
            raise RuntimeError('Bob did not obtain a new actual endpoint and seat lease')
        offset=(host/'codcoop.log').stat().st_size
        report['alice_checkpoint_loaded_by_bob']=reload('qa_inventory_alice',processes)['peer_inventory'][0]
        if current()['installed'] or current()['loaded_lease']:
            raise RuntimeError('Bob inherited Alice saved inventory ownership')
        if 'spawn_ticket' in current() and current()['spawn_ticket']<=report['bob_new']['spawn_ticket']:
            raise RuntimeError('unverified saved owner did not get a fresh-role ticket')
        if 'restored guest ownership unverified' not in (host/'codcoop.log').read_text(errors='replace')[offset:]:
            raise RuntimeError('wrong-owner fallback was not visible')
        original_move(h,p,slot,processes,timeout,action)
        bob_before=current();bob_save,bob_side=savegame('qa_inventory_bob',processes)
        (output/'ownership-bob-before-truncation.bin').write_bytes(bob_side.read_bytes())
        report['bob_before_save']=bob_before
        report['bob_after_own_checkpoint']=reload('qa_inventory_bob',processes)['peer_inventory'][0]
        restored=current()
        if not restored['installed'] or restored['loaded_lease']!=bob_before['lease'] or any(restored[k]!=bob_before[k] for k in ('numeric_sha256','weapon','viewmodel')):
            raise RuntimeError('Bob own completed checkpoint lost exact numeric loadout')
        if 'spawn_ticket' in restored and restored['spawn_ticket']!=bob_before['spawn_ticket']:
            raise RuntimeError('verified own checkpoint incorrectly requested a fresh kit/refill')
        original_move(h,p,slot,processes,timeout,action)
        # A partial sidecar must never become proof, while host save still loads.
        bob_side.write_bytes(bob_side.read_bytes()[:17])
        report['partial_sidecar_after_load']=reload('qa_inventory_bob',processes)['peer_inventory'][0]
        if current()['installed'] or current()['loaded_lease']:raise RuntimeError('partial sidecar accepted')
        if 'spawn_ticket' in current() and current()['spawn_ticket']<=restored['spawn_ticket']:
            raise RuntimeError('partial saved ownership did not request a fresh role')
        original_move(h,p,slot,processes,timeout,action)
        report['status']='PASS'
        return distance

    def errors(folder):
        found=original_errors(folder)
        if folder==peer and notice in found:found.remove(notice)
        return found
    qa.move_remote=move;qa.subprocess.Popen=popen;qa.process_log_errors=errors
    try:
        result=qa.main(['--source',str(args.source),'--run',str(output),'--runtime-dir',str(args.runtime_dir),
            '--variant',args.variant,'--map',args.map,'--players','2','--timeout',str(args.timeout),'--duration','6','--port',str(args.port)])
        if result:report['status']='FAIL'
        return 0 if report['status']=='PASS' else 1
    finally:
        qa.move_remote=original_move;qa.subprocess.Popen=original_popen;qa.process_log_errors=original_errors
        if replacement_log:replacement_log.close()
        output.mkdir(parents=True,exist_ok=True)
        (output/'inventory-provenance-probe.json').write_text(json.dumps(report,indent=2))
        for source in (Path(__file__),Path(qa.__file__)):
            (output/('executed-'+source.name)).write_bytes(source.read_bytes())


if __name__=='__main__':raise SystemExit(main())
