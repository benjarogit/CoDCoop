#!/usr/bin/env python3
"""Actual old-ACCEPT capability rejection via explicitly mutated localhost relay."""
import argparse
import hashlib
import json
from pathlib import Path
import qa_coop as qa
from qa_weapon_selection_relay import OwnedSelectionRelay


def rejection_ready(text,state):
    # Console output precedes the next 250ms QA-state publication. A stale
    # JOINER snapshot must be polled again, not mistaken for accepted gameplay.
    return 'host core lacks required player-selection capability' in text and state and state['role']==0 and not state['joined']


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','run','runtime-dir'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,default=29949)
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args(argv)
    output=args.run.resolve();peer=output/'join1';host=output/'host'
    report={'status':'FAIL','scope':'raw protocol9 old-host capability rejection; native slot may be allocated before ACCEPT, no pre-allocation claim',
            'qa_coop_sha256':hashlib.sha256(Path(qa.__file__).read_bytes()).hexdigest()}
    relay=OwnedSelectionRelay(('127.0.0.1',args.port),strip_capability=True)
    popen=qa.subprocess.Popen;wait=qa.wait_for

    def launch(command,*pargs,**kwargs):
        if isinstance(command,list) and '+coopjoin' in command:
            command=list(command);command[command.index('+coopjoin')+1]='127.0.0.1:'+str(relay.port)
        return popen(command,*pargs,**kwargs)

    def waiting(predicate,processes,timeout,description):
        def check():
            text='\n'.join(log.read_text(errors='replace') for log in (peer/'codcoop_join.log',peer/'uo/console.log') if log.exists())
            if 'host core lacks required player-selection capability' in text:
                state=qa.read_state(peer)
                if not rejection_ready(text,state):return None
                report['rejected_state']=state
                report['host_state']=qa.read_state(host)
                for folder in (peer,host):qa.command(folder,'quit',joiner=folder==peer)
                codes=[process.wait(timeout=20) for process in processes]
                if any(codes):raise RuntimeError('nonzero native exit after capability rejection')
                report['native_exit_codes']=codes;report['status']='PASS'
                raise qa.ExpectedProtocolRejection()
            return predicate()
        return wait(check,processes,timeout,description)

    qa.subprocess.Popen=launch;qa.wait_for=waiting
    try:
        result=qa.main(['--source',str(args.source),'--run',str(output),'--runtime-dir',str(args.runtime_dir),
                       '--variant','uo','--map','training','--players','2','--timeout',str(args.timeout),'--port',str(args.port)])
        if result:report['status']='FAIL'
    finally:
        qa.subprocess.Popen=popen;qa.wait_for=wait
        relay.close();report['relay']=relay.evidence()
        if relay.errors or not any(r['kind']=='capability_stripped' for r in report['relay']['records']):report['status']='FAIL'
        output.mkdir(parents=True,exist_ok=True)
        (output/'selection-capability-probe.json').write_text(json.dumps(report,indent=2))
        for source in (Path(__file__),Path(qa.__file__),Path(__file__).with_name('qa_weapon_selection_relay.py')):
            (output/('executed-'+source.name)).write_bytes(source.read_bytes())
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
