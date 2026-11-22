#!/usr/bin/env python3
"""Production-path pre-map network assets, no bootstrap QA switch or offline peer catalog; UF registry remains experimental."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import shutil
import threading
sys.path.insert(0,str(Path.cwd()/'tools'))
import qa_coop as qa
from qa_bootstrap_relay import OwnedBootstrapRelay,verify_order,verify_refresh


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','run','runtime-dir'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--variant',choices=('cod1','uo','sp_improved','united_fronts'),default='uo')
    parser.add_argument('--map',default='training')
    parser.add_argument('--port',type=int,default=29965)
    parser.add_argument('--timeout',type=int,default=240)
    parser.add_argument('--drop-first-part',action='store_true')
    parser.add_argument('--host-delay',type=int,default=0)
    parser.add_argument('--require-world-refresh',action='store_true')
    parser.add_argument('--capture-overlap',action='store_true')
    parser.add_argument('--initial-dobj-delay',type=float,default=0)
    parser.add_argument('--checkpoint-reloads',type=int,default=0)
    parser.add_argument('--hotreload-peer',action='store_true')
    parser.add_argument('--hotreload-host',action='store_true')
    parser.add_argument('--strip-ready-capability',action='store_true')
    parser.add_argument('--inject-invalid-acks',action='store_true')
    parser.add_argument('--corrupt-first-part',action='store_true')
    args=parser.parse_args(argv);output=args.run.resolve();host=output/'host';peer=output/'join1'
    if args.hotreload_host and args.hotreload_peer:parser.error('choose one DLL lifecycle at a time')
    if (args.capture_overlap or args.initial_dobj_delay) and args.variant=='cod1':parser.error('native camera/model mapping observers currently support the UO engine only')
    observers={}
    for required,name in ((args.capture_overlap,'qa_camera_observer'),(args.initial_dobj_delay,'qa_native_model_mapping')):
        if required:
            output.mkdir(parents=True,exist_ok=True)
            source=Path(__file__).with_name(name+'.cpp');target=output/(name+'.exe')
            qa.subprocess.run(['i686-w64-mingw32-g++','-std=c++17','-O2','-static','-mwindows',str(source),'-o',str(target)],check=True)
            observers[name]=target
    report={'status':'FAIL','scope':__doc__,'excluded':['mod world/nation/year settings','individual-kit planning transport','XAnim/sound/material-specific closure','native Windows/Steam acceptance'],
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'qa_coop_sha256':hashlib.sha256(Path(qa.__file__).read_bytes()).hexdigest()}
    frozen_sources={path.name:path.read_bytes() for path in (Path(__file__),Path(__file__).with_name('qa_bootstrap_relay.py'),Path(qa.__file__))}
    relay=OwnedBootstrapRelay(('127.0.0.1',args.port),args.drop_first_part,args.initial_dobj_delay,args.strip_ready_capability,host/'qa-state.json' if args.inject_invalid_acks else None,args.corrupt_first_part)
    popen=qa.subprocess.Popen;assess=qa.assess_liveness;waiting=qa.wait_for;log_errors=qa.process_log_errors;entered=False;native_env=None
    def lifecycle_errors(folder,intentional_departures=0):
        if not (args.hotreload_peer or args.hotreload_host) or folder!=peer or intentional_departures!=1:return log_errors(folder,intentional_departures)
        # DLL reinitialization emits fixed API/cvar retirement messages between
        # its deliberate Leave marker and native disconnect. Scope this one
        # banner to the observed lifecycle, never to ordinary engine errors.
        errors=log_errors(folder,0);found=[]
        for root in ('Main','main','uo','UnitedFronts'):
            path=folder/root/'console.log'
            if not path.exists():continue
            lines=path.read_text(errors='replace').splitlines()
            for i,line in enumerate(lines):
                if line.strip() not in ('ERROR: Getrennt','ERROR: Disconnected'):continue
                window=lines[max(0,i-32):i]
                if args.hotreload_peer and any(v.strip()=='^3COOP: You left the co-op game.' for v in window) and any('Co-op stopped for a core update.' in v for v in window):found.append(line)
                if args.hotreload_host and any(v.strip()=='^3COOP: The host closed the co-op game.' for v in window):found.append(line)
        if len(found)!=1:return errors+['Expected exactly one acknowledged DLL-reload disconnect banner']
        errors.remove(found[0]);report['acknowledged_reload_banner']=found[0]
        return errors
    def expected_rejection(predicate,processes,timeout,description):
        if not args.strip_ready_capability or description!='real host and all joiners connected':return waiting(predicate,processes,timeout,description)
        def rejected():
            h=qa.read_state(host);p=qa.read_state(peer)
            text=(peer/'codcoop_join.log').read_text(errors='replace')
            if h and p and p['role']==0 and not p['joined'] and 'Host lacks the required resource-bootstrap v2 capability' in text:
                if any(slot['active'] for slot in h['players'][1:]):raise RuntimeError('missing capability allocated a native slot')
                if 'QA native GAME_INIT' in text:raise RuntimeError('missing capability loaded a native peer map')
                return [h,p]
        report['capability_rejection']=waiting(rejected,processes,timeout,'readable missing resource capability before native map/slot')
        for index,folder in enumerate((host,peer)):
            if qa.process_log_errors(folder):raise RuntimeError('native errors during capability rejection')
            qa.command(folder,'quit',joiner=bool(index))
        for process in processes:
            if process.wait(timeout=20)!=0:raise RuntimeError('nonzero shutdown during capability rejection')
        report['status']='PASS';report['capability_clean_exits']=True
        raise qa.ExpectedProtocolRejection()
    observing=threading.Event();observing.set();samples=[];observer_errors=[];observer_thread=None
    def mapping_watch():
        observer=observers['qa_native_model_mapping']
        while observing.is_set():
            observed=qa.subprocess.run(['wine',str(observer),qa.zpath(peer)],env=native_env,capture_output=True,text=True)
            if observed.returncode==0:
                try:
                    rows=[json.loads(line) for line in observed.stdout.splitlines() if line.startswith('{')]
                    for row in rows:
                        if 'model_mapping_mismatches' in row:row['observed_time']=time.time();samples.append(row)
                except ValueError as error:observer_errors.append(str(error))
            time.sleep(.12)
    def launch(command,*pargs,**kwargs):
        nonlocal native_env,observer_thread
        if isinstance(command,list) and any(str(arg).endswith(('CoDUOSP.exe','CoDSP.exe')) for arg in command):
            command=list(command);folder=Path(kwargs['cwd'])
            kwargs['env']=dict(kwargs['env']);kwargs['env'].pop('CODCOOP_QA_NETWORK_ASSETS',None)
            native_env=kwargs['env']
            if args.checkpoint_reloads:kwargs['env']['CODCOOP_QA_MT_EPOCH']='1'
            if args.variant=='united_fronts':
                kwargs['env'].update(CODCOOP_QA_DEFER_MODELS='1',CODCOOP_QA_BORROW_TREES='1',CODCOOP_QA_DOBJ_BARRIER='1',CODCOOP_QA_MT_EPOCH='1')
                report['uf_scope']='default authored world/loadout only; QA first-use/borrow/barrier at512MiB; no individual-kit/world-options transport'
                report.setdefault('script_inputs',{})[folder.name]={str(path.relative_to(folder)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (folder/'UnitedFronts').glob('zzz*.pk3')}
            # Eliminate prior QA disk catalogs on both ordinary-game copies.
            for pattern in ('qa-deferred-models.txt','qa-render-models.txt','qa-model-ledger-*.txt','qa-network-*'):
                for path in folder.glob(pattern):path.unlink()
            if '+coopjoin' in command:
                command[command.index('+coopjoin')+1]='127.0.0.1:'+str(relay.port)
                index=command.index('+devmap');del command[index:index+2]
                report['peer_before_launch']={'map_argument':False,'offline_model_catalogs':list(map(str,folder.glob('qa-*-models.txt')))}
                if args.initial_dobj_delay:
                    observer_thread=threading.Thread(target=mapping_watch,daemon=True);observer_thread.start()
        return popen(command,*pargs,**kwargs)
    def probe(before,after,count):
        nonlocal entered
        assess(before,after,count)
        if entered:
            if qa.read_state(peer).get('trees',0)<=0:raise RuntimeError('Peer lacks replicated native DObjs after delivery resumed')
            return
        entered=True
        hlog=(host/'codcoop.log').read_text(errors='replace');plog=(peer/'codcoop_join.log').read_text(errors='replace')
        transfer=plog.find('Resource bootstrap: SHA verified');init=plog.find('QA native GAME_INIT');ready=plog.find('Resource bootstrap: completed native Game/CG mapping verified');joined=plog.find('joiner: conectado')
        if min(transfer,init,ready,joined)<0 or not transfer<init<ready<joined:raise RuntimeError('native peer bootstrap order was not verified')
        if not args.initial_dobj_delay and qa.read_state(peer).get('trees',0)<=0:raise RuntimeError('Peer lacks actual replicated native DObjs/owned trees')
        if 'Resource bootstrap: native ready ACK' not in hlog:raise RuntimeError('host lacks native-ready acknowledgement before slot')
        sent=(host/'qa-network-sent.txt').read_bytes();received=(peer/'qa-network-received.txt').read_bytes()
        if sent!=received:raise RuntimeError('actual network resource body differs between instances')
        report.update(status='PASS',resource_sha256=hashlib.sha256(received).hexdigest(),resource_bytes=len(received),peer_mapping=(peer/'qa-network-mapping.tsv').read_text(),native_order={'transfer':transfer,'first_game_init':init,'mapping_ready':ready,'joined':joined})
        if args.capture_overlap:
            for index,folder in enumerate((host,peer)):
                old=set(folder.rglob('*.tga'))
                qa.command(folder,'screenshot',joiner=bool(index));time.sleep(1)
                fresh=set(folder.rglob('*.tga'))-old
                if len(fresh)!=1:raise RuntimeError('initial native screenshot missing/ambiguous')
                shutil.copy2(fresh.pop(),output/('native-initial-'+folder.name+'.tga'))
                observer=observers['qa_camera_observer']
                observed=qa.subprocess.run(['wine',str(observer),qa.zpath(folder)],env=native_env,capture_output=True,text=True,check=True)
                (output/('camera-initial-'+folder.name+'.json')).write_text(observed.stdout)
            (output/'overlap-initial-state.json').write_text(json.dumps([qa.read_state(host),qa.read_state(peer)],indent=2))
    qa.subprocess.Popen=launch;qa.assess_liveness=probe;qa.wait_for=expected_rejection;qa.process_log_errors=lifecycle_errors
    def lifecycle(folders,processes,states):
        target=host if args.hotreload_host else peer
        target_log=target/('codcoop.log' if args.hotreload_host else 'codcoop_join.log')
        old=qa.read_state(target);offset=target_log.stat().st_size
        qa.command(target,'coopreload',joiner=not args.hotreload_host)
        def stopped():
            p=qa.read_state(peer);h=qa.read_state(host)
            text=target_log.read_text(errors='replace')[offset:]
            if p and h and p['role']==0 and not p['joined'] and not h['players'][1]['active'] and (not args.hotreload_host or h['role']==0) and 'core reload ended session; fresh handshake required' in text:return [h,p]
        ended=qa.wait_for(stopped,processes,45,'native DLL reload ending old resource session')
        if args.hotreload_host:
            qa.command(host,'coophost '+str(args.port))
            qa.wait_for(lambda:qa.read_state(host)['role']==1,processes,30,'explicit new native host session')
            # Ending the former host session does not relabel its old native
            # init/save-owner proof. The new session loads a real fresh world.
            qa.command(host,'devmap '+args.map)
        qa.command(peer,'coopjoin 127.0.0.1:'+str(relay.port),joiner=True)
        def rejoined():
            h=qa.read_state(host);p=qa.read_state(peer)
            if h and p and h['players'][1]['active'] and p['joined'] and p.get('trees',0)>0:return [h,p]
        fresh=qa.wait_for(rejoined,processes,args.timeout,'fresh native resource handshake after DLL reload')
        report['hotreload']={'before':old,'ended':ended,'after':fresh}
        return {'scope':'Explicit DLL reload closes and revalidates the initial resource contract',
            'checks':['old native resource session ended visibly','fresh resource handshake, native map and replicated DObjs after reload'],
            'evidence':report['hotreload'],'intentional_departures':[1]}
    try:
        result=qa.main(['--source',str(args.source),'--run',str(output),'--runtime-dir',str(args.runtime_dir),
            '--variant',args.variant,'--map',args.map,'--players','2','--port',str(args.port),'--timeout',str(args.timeout),'--host-delay',str(args.host_delay),
            '--checkpoint-reloads',str(args.checkpoint_reloads)],scenario=lifecycle if (args.hotreload_peer or args.hotreload_host) else None)
        if result:report['status']='FAIL'
    finally:
        observing.clear()
        if observer_thread:observer_thread.join(timeout=10)
        qa.subprocess.Popen=popen;qa.assess_liveness=assess;qa.wait_for=waiting;qa.process_log_errors=log_errors;relay.close();report['relay']=relay.evidence()
        if args.initial_dobj_delay:
            from qa_model_mapping_observation import analyze
            report['mapping_observation']=analyze(samples,(peer/'codcoop_join.log').read_text(errors='replace'))
            report['mapping_observer_errors']=observer_errors
            (output/'mapping-samples.json').write_text(json.dumps(samples,indent=2))
        if relay.errors or (not args.strip_ready_capability and not verify_order(relay.records,args.inject_invalid_acks)):report['status']='FAIL'
        if args.strip_ready_capability and (not relay.stripped or any(row['type'] in (0xb0,ord('J'),ord('A')) for row in relay.records)):report['status']='FAIL'
        if args.inject_invalid_acks and (len(relay.ack_injected)!=4 or len(relay.ack_guard_samples)<2 or any(any(row['active']) for row in relay.ack_guard_samples)):report['status']='FAIL'
        if args.drop_first_part and not relay.dropped:report['status']='FAIL'
        if args.corrupt_first_part and (not relay.corrupted or 'rejected digest/canonical payload; requesting a new nonce' not in (peer/'codcoop_join.log').read_text(errors='replace')):report['status']='FAIL'
        report['observed_world_refresh']=verify_refresh(relay.records)
        if args.require_world_refresh and not report['observed_world_refresh']:report['status']='FAIL'
        output.mkdir(parents=True,exist_ok=True);(output/'network-bootstrap-probe.json').write_text(json.dumps(report,indent=2))
        for name,body in frozen_sources.items():(output/('executed-'+name)).write_bytes(body)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
