#!/usr/bin/env python3
"""Real warm-host, host-alone fresh-map and fast-restart receipt regression.

Uses QA native UI actions for pregame; does not certify automatic UI startup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import qa_coop as qa


def disposition(text):
    matches = re.findall(r'inventory: disposition slot=0 state=(FRESH|PRESERVED) ticket=(\d+) world=(\d+)', text)
    return (matches[-1][0], int(matches[-1][1]), int(matches[-1][2])) if matches else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'run', 'runtime-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--variant', choices=('cod1','uo'), default='uo')
    parser.add_argument('--port', type=int, default=29957)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args(argv)
    output = args.run.resolve(); host = output/'host'; peer = output/'join1'
    report = {'status':'FAIL', 'coverage':__doc__, 'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'phases':[]}
    original = qa.assess_liveness; errors = qa.process_log_errors
    popen = qa.subprocess.Popen; send = qa.command
    entered = False; departure = None; warm_started = False

    def launch(command,*pargs,**kwargs):
        if isinstance(command,list) and '+coophost' in command:
            command=list(command);index=command.index('+coophost');del command[index:index+2]
        return popen(command,*pargs,**kwargs)

    def command(folder,value,joiner=False):
        nonlocal warm_started
        send(folder,value,joiner=joiner)
        if folder!=host or warm_started or 'coopqastart' not in value:return
        warm_started=True;last_click=[0.0]
        def solo_ready():
            state=qa.read_state(host)
            if time.monotonic()-last_click[0]>1:
                send(host,'coopqastart');last_click[0]=time.monotonic()
            if errors(host):raise RuntimeError('native standalone world failed before hosting')
            if state and state.get('role')==0 and state.get('cls_state')==2 and state.get('map')=='training' and state.get('server_time',0)>500:
                return state
        report['standalone_before_host']=qa.wait_for(solo_ready,[],args.timeout,'actual standalone ready world before coophost')
        save();send(host,'coophost '+str(args.port))

    def save():
        (output/'preservation-lifecycle-probe.json').write_text(json.dumps(report, indent=2))

    def text():
        return (host/'codcoop.log').read_text(errors='replace')

    def probe(before, after, count):
        nonlocal entered, departure
        original(before, after, count)
        if entered:return
        entered = True
        initial = disposition(text())
        if not initial or initial[0]!='FRESH' or 'hosting observed native init' not in text():
            raise RuntimeError('warm map-before-host startup lacks actual observed native FRESH receipt')
        report['initial'] = initial;save()
        qa.command(peer,'coopleave',joiner=True)
        qa.wait_for(lambda: (qa.read_state(peer) or {}).get('role')==0 and not (qa.read_state(host) or {}).get('players',[{},{}])[1].get('active',True), [],20,'explicit peer departure')
        notices=errors(peer)
        if notices:
            if len(notices)!=1 or notices[0].strip() not in ('ERROR: Getrennt','ERROR: Disconnected'):
                raise RuntimeError('unexpected departure errors: '+repr(notices))
            departure=notices[0]
        previous=initial
        for command in ('devmap training','map_restart'):
            start=len(text()); previous_generation=qa.read_state(host)['world_wire']['generation']
            qa.command(host,command)
            last_click=[0.0]
            def ready():
                state=qa.read_state(host); tail=text()[start:]; marker=disposition(tail)
                if time.monotonic()-last_click[0]>1:
                    qa.command(host,'coopqastart');last_click[0]=time.monotonic()
                if not state or state.get('cls_state')!=2 or state.get('server_time',0)<=500 or not marker:return
                if not re.search(r'observed native init serial=\d+ intent=0 ',tail):return
                if marker[0]!='FRESH' or marker[1]<=previous[1]:
                    raise RuntimeError('fresh native init reused a prior equipment ticket')
                if marker[2]!=previous_generation+1 or state['world_wire']['generation']!=marker[2]:
                    raise RuntimeError('native fresh init announced zero or multiple world transitions')
                return {'command':command,'state':state,'marker':marker,'native_log':tail}
            phase=qa.wait_for(ready,[],args.timeout,'host-alone '+command+' fresh receipt')
            if command=='map_restart' and 'QA native SpawnServer' in phase['native_log']:
                raise RuntimeError('map_restart used SpawnServer; fast no-Spawn path was not exercised')
            report['phases'].append(phase);previous=phase['marker'];save()
        qa.command(peer,'coopjoin 127.0.0.1:'+str(args.port),joiner=True)
        def joined():
            h,p=qa.read_state(host),qa.read_state(peer)
            return h and p and p.get('joined') and p.get('snapshot_num',0)>0 and h['players'][1]['active']
        qa.wait_for(joined,[],args.timeout,'real peer rejoin after host-alone fresh worlds')
        report['status']='PASS';save()

    def scoped_errors(folder):
        result=list(errors(folder))
        if folder==peer and departure in result:result.remove(departure)
        return result
    qa.assess_liveness=probe;qa.process_log_errors=scoped_errors
    qa.subprocess.Popen=launch;qa.command=command
    try:
        result=qa.main(['--source',str(args.source),'--run',str(output),'--runtime-dir',str(args.runtime_dir),
            '--variant',args.variant,'--map','training','--players','2','--port',str(args.port),'--timeout',str(args.timeout)])
        if result:report['status']='FAIL'
        save();return result
    finally:
        qa.assess_liveness=original;qa.process_log_errors=errors
        qa.subprocess.Popen=popen;qa.command=send


if __name__=='__main__':raise SystemExit(main())
