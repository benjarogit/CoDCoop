#!/usr/bin/env python3
"""Actual catch-up trail isolation across native map changes; not mission completion."""
import argparse,hashlib,json,math,time
from pathlib import Path
import qa_coop as qa

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','run','runtime-dir'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--port',type=int,default=29974)
    p.add_argument('--variant',choices=('cod1','uo'),default='cod1')
    a=p.parse_args();out=a.run.resolve();folders=[out/'host',out/'join1'];frozen=Path(__file__).read_bytes()
    argv=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),
          '--variant',a.variant,'--map','training','--players','2','--port',str(a.port),'--timeout','180','--duration','3']
    report={'status':'FAIL','scope':__doc__,'variant':a.variant,'runner_sha256':hashlib.sha256(frozen).hexdigest(),
            'setup':'Actual Host input establishes old-world trail; normal native map Brecourt. Explicit QA-only remote placement3000 from Host exercises catch-up. No mission progress or vehicle claim.'}
    def scenario(_,processes,states):
        def wait(f,label,timeout=40):return qa.wait_for(f,processes,timeout,label)
        def host():
            for folder in folders:
                errors=qa.process_log_errors(folder)
                if errors:raise RuntimeError(errors[0])
            return qa.read_state(folders[0])
        report['initial']=host()
        report['initial_remote_input_distance']=qa.move_remote(folders[0],folders[1],1,processes,40)
        qa.command(folders[0],'coopgod 0 1\ncoopgod 1 1\n+back')
        try:time.sleep(1.2)
        finally:qa.command(folders[0],'-back')
        report['old_world']=host()
        if math.dist(report['initial']['players'][0]['position'],report['old_world']['players'][0]['position'])<64:
            raise RuntimeError('Actual Host input did not establish a useful old-world trail')
        old_generation=report['old_world']['world_wire']['generation']
        qa.command(folders[0],'map brecourt')
        wait(lambda:(s:=host()) and s['world_wire']['generation']!=old_generation and s.get('map')=='brecourt', 'actual different native world',180)
        wait(lambda:(s:=host()) and s['players'][1]['active'] and qa.read_state(folders[1]).get('joined'), 'actual rejoin after map change',180)
        wait(lambda:all(p['pm_type']==0 and not p['linked'] and not p['downed'] for p in host()['players'][:2]),'ordinary unlinked owners in new world',90)
        time.sleep(1)
        report['new_world']=host()
        # Keep the Host stationary, so the current-world trail has no point
        # >48 units away. A catch-up here can only use an old-world point.
        anchor=report['new_world']['players'][0]['position']
        if math.dist(anchor,report['old_world']['players'][0]['position'])<256:
            raise RuntimeError('The two native maps did not establish distinct coordinate contexts')
        log=folders[0]/'codcoop.log';before=log.read_text(errors='replace')
        qa.command(folders[0],'cooplook 1 0 3000')
        wait(lambda:math.dist(host()['players'][1]['position'],anchor)>2100,'explicit distant remote fixture')
        samples=[];deadline=time.monotonic()+13
        while time.monotonic()<deadline:
            s=host();samples.append(s)
            if math.dist(s['players'][0]['position'],anchor)>8:raise RuntimeError('Host moved while testing stationary new-world trail')
            time.sleep(.2)
        report['samples']=samples;tail=log.read_text(errors='replace')[len(before):];report['native_log_tail']=tail
        if 'aparece en su rastro' in tail:raise RuntimeError('Catch-up used a trail despite stationary new-world Host')
        # The world fence must not simply disable catch-up. Create a real new
        # trail through Host input and require the distant guest to use it.
        qa.command(folders[0],'+forward')
        try:wait(lambda:math.dist(host()['players'][0]['position'],anchor)>96,'actual Host creates current-world trail',8)
        finally:qa.command(folders[0],'-forward')
        wait(lambda:math.dist(host()['players'][1]['position'],anchor)<256,'catch-up uses actual current-world trail',20)
        tail=log.read_text(errors='replace')[len(before):]
        if 'aparece en su rastro' not in tail:raise RuntimeError('No normal catch-up after real new-world Host movement')
        report['current_world_catchup']=host();report['native_log_tail']=tail
        if math.dist(report['current_world_catchup']['players'][1]['position'],report['old_world']['players'][0]['position'])<512:
            raise RuntimeError('Catch-up destination overlaps previous-world context')
        report['post_catchup_remote_input_distance']=qa.move_remote(folders[0],folders[1],1,processes,40,'+moveleft')
        report['functional']='PASS'
        (out/'motion-epoch-proof.json').write_text(json.dumps(report,indent=2)+'\n')
        return {'scope':__doc__,'checks':['actual Host input in old map','normal native new map and real remote rejoin',
                'stationary new-world Host never supplies stale previous-world trail',
                'real Host movement creates valid new-world catch-up path','real remote input before and after catch-up'],
                'evidence':{'proof':str(out/'motion-epoch-proof.json')}}
    try:
        status=qa.main(argv,scenario=scenario)
        report['status']='PASS' if status==0 and report.get('functional')=='PASS' else 'FAIL'
    except Exception as error:report['error']=str(error)
    finally:
        out.mkdir(parents=True,exist_ok=True)
        (out/'motion-epoch-proof.json').write_text(json.dumps(report,indent=2)+'\n')
        (out/Path(__file__).name).write_bytes(frozen)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
