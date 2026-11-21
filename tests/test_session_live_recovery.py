"""Real supervisor control loop with fake owned native processes; no engines."""
import argparse
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest import mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import coop_session as session

class CommittedRecoveryTests(unittest.TestCase):
    def scenario(self,action,joining=False):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);(game/'coop').mkdir();(game/'uo/save').mkdir(parents=True)
            save=game/'uo/save/coop_switch.svg';save.write_bytes(b'original committed progress')
            controls=queue.Queue();processes=[];launches=[];events=[];commands=[];clock=[0.];turns=[0]
            target={'action':'prepare','transaction':123,'variant':'uo','role':'joiner' if joining else 'host',
                    'host':'127.0.0.1:29111' if joining else '', 'port':29111,
                    'map':'bastogne1','difficulty':2,'players':3}
            class OwnedProcess:
                returncode=None
                def __init__(self):self.pid=10000+len(processes);self.stops=0
                def poll(self):return self.returncode
                def wait(self,timeout=None):
                    # Exercise the actual graceful stop and file cleanup helpers.
                    paths=[game/'codcoop.cmd',game/'codcoop_join.cmd']
                    pending=[p for p in paths if p.exists()]
                    if self.returncode is None:
                        assert pending and pending[0].read_text().strip()=='quit'
                        commands.append((self.pid,'quit'));self.stops+=1;self.returncode=0
                        # Old process can leave either role's command/pending files.
                        for path in paths:
                            path.write_text('quit\n');path.with_name(path.name+'.pending').write_text('quit\n')
                    return self.returncode
                def terminate(self):raise AssertionError('graceful stop must succeed')
                def kill(self):raise AssertionError('graceful stop must succeed')
            class Verifier:
                def __init__(self,_game):self.request=None
                def submit(self,r):self.request=dict(r)
                def cancel(self):self.request=None
                def poll(self):
                    request,self.request=self.request,None
                    return (request,True,'') if request else None
            def launch(*args):launches.append(args);return ['owned-fixture'],{}
            def spawn(*_args,**_kwargs):
                self.assertFalse(any((game/(name+suffix)).exists() for name in ('codcoop.cmd','codcoop_join.cmd') for suffix in ('','.pending')))
                if len(processes)>2:raise AssertionError('stale recovery restarted after resumed')
                p=OwnedProcess();processes.append(p);return p
            def ready():
                (game/'coop/runtime-state.json').write_text(json.dumps({'variant':'uo','map':'bastogne1',
                    'role':'joiner' if joining else 'host','joined':joining,'live_players':3,'render_ready':True}))
            def event(phase,**detail):
                events.append((phase,detail))
                if phase=='running' and len(processes)==1:
                    (game/'coop/switch.json').write_text(json.dumps(target))
                elif phase=='prepared':
                    if action=='precommit-cancel':controls.put({'action':'cancel'})
                    else:(game/'coop/switch.json').write_text(json.dumps(dict(target,action='commit')))
                elif phase=='restarting':processes[0].returncode=0
                elif phase=='reconnecting' and not detail.get('retrying'):
                    if len(processes)==2:
                        self.assertIsNone(processes[1].poll())
                        if action=='retry':
                            controls.put({'action':'retry','variant':'../bad','map':'wrong','difficulty':0,'players':1,'host':'evil'})
                        elif action=='cancel':controls.put({'action':'cancel'})
                    elif len(processes)==3:ready()
                elif phase=='recovery_waiting':
                    self.assertEqual(action,'wait');self.assertIsNone(processes[1].poll())
                    self.assertEqual(processes[1].stops,0);ready()
                elif phase=='resumed':
                    # This must never consume the old committed target again.
                    controls.put({'action':'retry'});controls.put({'action':'stop'})
                elif phase=='cancelled':controls.put({'action':'stop'})
            def sleep(_seconds):
                turns[0]+=1;clock[0]+=60 if action=='wait' else 1
                for name in ('codcoop.cmd','codcoop_join.cmd'):
                    path=game/name
                    if path.exists() and path.read_text().strip()!='quit':
                        text=path.read_text().strip()
                        commands.append((processes[-1].pid,text));path.unlink()
                        if text=='coopswitchcancel':
                            (game/'coop/switch.json').write_text(json.dumps(dict(target,action='cancel')))
                if turns[0]>20:raise AssertionError('control loop did not finish')
            args=argparse.Namespace(game=game,variant='cod1',host=None,hosting=True,port=28960,difficulty=1,map_name='training',runner=None)
            with mock.patch.object(session,'check_installation',return_value={'ok':True}), \
                 mock.patch.object(session,'launch_arguments',side_effect=launch), \
                 mock.patch.object(session,'spawn_owned',side_effect=spawn), \
                 mock.patch.object(session,'InstallationVerifier',Verifier), \
                 mock.patch.object(session.queue,'Queue',return_value=controls), \
                 mock.patch.object(session.threading,'Thread'), \
                 mock.patch.object(session.signal,'signal'), \
                 mock.patch.object(session.time,'monotonic',side_effect=lambda:clock[0]), \
                 mock.patch.object(session.time,'sleep',side_effect=sleep), \
                 mock.patch.object(session,'event',side_effect=event):
                self.assertEqual(session.supervise(args),0)
            self.assertEqual(save.read_bytes(),b'original committed progress')
            self.assertFalse((game/'coop/session.lock').exists())
            self.assertFalse((game/'coop/supervisor.json').exists())
            self.assertFalse(any((game/(name+suffix)).exists() for name in ('codcoop.cmd','codcoop_join.cmd') for suffix in ('','.pending')))
            self.assertEqual(len(launches),3 if action=='retry' else 1 if action=='precommit-cancel' else 2)
            for launch_args in launches[1:]:
                self.assertEqual(launch_args[1],'uo')
                self.assertEqual(launch_args[3:9],('127.0.0.1:29111' if joining else None,'bastogne1',not joining,29111,2,3))
            self.assertTrue(all(d.get('recovering') for p,d in events if p=='running' and d['variant']=='uo'))
            if action=='precommit-cancel':
                self.assertIn('coopswitchcancel',[text for _,text in commands])
                self.assertNotIn('recovery_cancelled',[p for p,_ in events])
                self.assertIn('cancelled',[p for p,_ in events])
            else:self.assertNotIn('coopswitchcancel',[text for _,text in commands])
            if action=='retry':self.assertEqual(processes[1].stops,1)
            if action=='cancel':
                self.assertIn('recovery_cancelled',[p for p,_ in events]);self.assertNotIn('resumed',[p for p,_ in events])
            if action=='wait':self.assertIn('recovery_waiting',[p for p,_ in events])
            self.assertEqual(events[-1][0],'stopped')

    def test_live_unconnected_host_retry_uses_only_bound_target(self):self.scenario('retry')
    def test_live_unconnected_joiner_retry_keeps_endpoint_role_and_party(self):self.scenario('retry',True)
    def test_committed_cancel_leaves_only_owned_session_and_preserves_save(self):self.scenario('cancel')
    def test_slow_native_reconnect_is_visible_without_automatic_restart_or_stop(self):self.scenario('wait')
    def test_precommit_cancel_only_cancels_native_transaction_without_restarting(self):self.scenario('precommit-cancel')

if __name__=='__main__':unittest.main()
