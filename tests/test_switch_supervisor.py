"""Scorer tests for the real-game transition harness (including negative twins)."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('qa_switch',ROOT/'tools/qa_switch.py')
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)


class SwitchGateTests(unittest.TestCase):
    def setUp(self):
        self.before=[{'variant':'cod1','role':'host','live_players':2},{'variant':'cod1','role':'joiner','joined':True}]
        self.after=[{'role':'host','variant':'sp_improved','map':'pathfinder','live_players':2,'render_ready':True},
                    {'role':'joiner','variant':'sp_improved','map':'pathfinder','joined':True,'render_ready':True}]

    def verify(self, old=(10,20), new=(30,40)):
        qa.verify_transition(self.before,self.after,old,new,'sp_improved','pathfinder',2)

    def test_real_transition_shape_accepted(self): self.verify()
    def test_not_initially_joined_is_not_success(self):
        self.before[1]['joined']=False
        with self.assertRaises(ValueError): self.verify()
    def test_no_restart_is_not_success(self):
        with self.assertRaises(ValueError): self.verify(new=(10,20))
    def test_only_one_restart_is_not_success(self):
        with self.assertRaises(ValueError): self.verify(new=(30,20))
    def test_reserved_slot_without_live_peer_is_not_success(self):
        self.after[0]['live_players']=1
        with self.assertRaises(ValueError): self.verify()
    def test_uninitialized_renderer_is_not_success(self):
        self.after[1]['render_ready']=False
        with self.assertRaises(ValueError): self.verify()
    def test_disconnected_joiner_is_not_success(self):
        self.after[1]['joined']=False
        with self.assertRaises(ValueError): self.verify()
    def test_wrong_map_is_not_success(self):
        self.after[1]['map']='training'
        with self.assertRaises(ValueError): self.verify()
    def test_difficulty_reads_actual_colored_engine_output(self):
        self.assertEqual(qa.difficulty_value('"g_gameskill" is:"^72^7" default:"1"'),2)
    def test_memory_reads_actual_engine_value(self):
        self.assertEqual(qa.hunk_value('"com_hunkMegs" is:"^7256^7" default:"128"'),256)
        with self.assertRaises(ValueError): qa.hunk_value("requested --hunkmegs 512")
    def test_health_requires_actual_named_engine_response(self):
        self.assertEqual(qa.maxhealth_value('"g_player_maxhealth" is:"^7300^7" default:"600"'),300)
        with self.assertRaises(ValueError): qa.maxhealth_value('requested +set g_player_maxhealth 300')
        with self.assertRaises(ValueError): qa.maxhealth_value('"health" is:"300"')
    def test_missing_query_fails(self):
        with self.assertRaises(ValueError): qa.difficulty_value('g_gameskill was passed on command line')

class NativeShutdownTests(unittest.TestCase):
    def test_all_real_process_lifetimes_require_zero_nonforced_exit(self):
        records=[{'phase':'game_stopped','pid':pid,'code':0,'forced':False} for pid in (10,20,30)]
        self.assertEqual(qa.verify_game_stops([10,20,30],records),records)
        for changed in (records[:-1],records+[dict(records[0])],
                        [dict(r,code=7) if r['pid']==20 else r for r in records],
                        [dict(r,forced=True) if r['pid']==20 else r for r in records]):
            with self.subTest(records=changed),self.assertRaises(ValueError):qa.verify_game_stops([10,20,30],changed)
        with self.assertRaises(ValueError):qa.verify_game_stops([],[])


class RunnerEnvironmentTests(unittest.TestCase):
    def test_realistic_clean_runner_retains_owned_prefix(self):
        value=qa.assess_runner_environment({'WINEPREFIX':'/owned/prefix','CODCOOP_QA_PROFILE':'1','PATH':'/usr/bin'},Path('/owned/prefix'),Path('/game/coop/launcher'))
        self.assertEqual(value['PATH'],'/usr/bin')
        self.assertIsNone(value['LD_LIBRARY_PATH'])
    def test_poisoned_library_path_cannot_pass_gate(self):
        with self.assertRaises(ValueError):
            qa.assess_runner_environment({'WINEPREFIX':'/owned/prefix','CODCOOP_QA_PROFILE':'1','LD_LIBRARY_PATH':'/game/coop/launcher/_internal'},Path('/owned/prefix'),Path('/game/coop/launcher'))
    def test_pyinstaller_private_state_cannot_pass_gate(self):
        with self.assertRaises(ValueError):
            qa.assess_runner_environment({'WINEPREFIX':'/owned/prefix','CODCOOP_QA_PROFILE':'1','_PYI_APPLICATION_HOME_DIR':'/tmp/app'},Path('/owned/prefix'),Path('/game/coop/launcher'))

class SupervisorLifetimeTests(unittest.TestCase):
    def test_supervisor_loop_clears_previous_quit_before_restart(self):
        import argparse
        import io
        import tempfile
        from unittest.mock import patch
        import coop_session as session

        class Finished(Exception): pass
        class Process:
            def __init__(self, pid): self.pid=pid; self.returncode=None
            def poll(self): return self.returncode
            def wait(self, timeout=None): self.returncode=0; return 0
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory); (game/'coop').mkdir()
            request={'action':'prepare','transaction':8,'variant':'sp_improved','role':'host',
                     'port':28960,'map':'pathfinder','difficulty':2,'players':2}
            children=[]; steps=[]; launched=[]
            real_sleep=session.time.sleep
            iterations=[0]
            def spawn(*args, **kwargs):
                # A stale quit must never reach either the first or recovered game.
                self.assertFalse(any(game.glob('codcoop*.cmd*')))
                child=Process(100+len(children));children.append(child)
                launched.append(args[0]);return child
            def sleep(_):
                iterations[0]+=1
                if iterations[0]>2000: self.fail('supervisor recovery fixture stalled')
                if not steps:
                    (game/'coop/switch.json').write_text(__import__('json').dumps(request));steps.append('prepare')
                elif steps==['prepare']:
                    # A real native host commits only after the asynchronous
                    # local verification has acknowledged preparation.
                    if 'prepared' not in phases:
                        real_sleep(.001)
                        return
                    request['action']='commit'
                    (game/'coop/switch.json').write_text(__import__('json').dumps(request));steps.append('commit')
                elif steps==['prepare','commit']:
                    # Race observed in real Wine run: old game exits while an
                    # additional quit/pending command survives on the disk.
                    for name in ('codcoop.cmd','codcoop_join.cmd','codcoop.cmd.pending','codcoop_join.cmd.pending'):
                        (game/name).write_text('quit\n')
                    children[0].returncode=0;steps.append('exited')
                else:
                    (game/'coop/runtime-state.json').write_text('{"variant":"sp_improved","role":"host","map":"pathfinder","render_ready":true,"live_players":2}')
            phases=[]
            def capture(phase, **details):
                phases.append(phase)
                if phase=='resumed': raise Finished()
            args=argparse.Namespace(game=game,variant='cod1',host=None,hosting=True,port=28960,
                                    difficulty=1,map_name='training',runner=None)
            for name in ('codcoop.cmd','codcoop_join.cmd.pending'): (game/name).write_text('quit\n')
            with patch.object(session,'check_installation',return_value={'ok':True,'errors':[], 'variants':{'sp_improved':{}}}), \
                 patch.object(session,'target_map_exists',return_value=True), \
                 patch.object(session,'launch_arguments',return_value=(['fake-game'],{})), \
                 patch.object(session.subprocess,'Popen',side_effect=spawn), \
                 patch.object(session.time,'sleep',side_effect=sleep), \
                 patch.object(session,'event',side_effect=capture), \
                 patch.object(session.signal,'signal'), patch.object(session.sys,'stdin',io.StringIO('')):
                with self.assertRaises(Finished): session.supervise(args)
            self.assertEqual(len(children),2)
            self.assertIn('prepared',phases); self.assertIn('restarting',phases);self.assertIn('resumed',phases)
            self.assertFalse(any(game.glob('codcoop*.cmd*')))
            self.assertFalse((game/'coop/session.lock').exists())


if __name__=='__main__': unittest.main()
