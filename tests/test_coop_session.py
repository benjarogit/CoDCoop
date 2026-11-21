import importlib.util
import argparse
import json
import queue
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import coop_session as session
from qa_coop import assess_liveness

class SessionTests(unittest.TestCase):
    def request(self, action='prepare', transaction=3):
        return {'action':action,'transaction':transaction,'variant':'uo','role':'host','port':28960,'host':''}
    def test_commit_requires_matching_preparation(self):
        m=session.SwitchState()
        with self.assertRaises(ValueError):m.accept(self.request('commit'))
        self.assertEqual(m.accept(self.request()),'prepare')
        with self.assertRaises(ValueError):m.accept(self.request('commit',4))
        self.assertEqual(m.accept(self.request('commit')),'commit')
        with self.assertRaises(ValueError):m.accept(self.request('commit'))
        self.assertEqual(m.accept(self.request()),'ignored')
    def test_cancel_never_restarts(self):
        m=session.SwitchState();m.accept(self.request());m.accept(self.request('cancel'))
        with self.assertRaises(ValueError):m.accept(self.request('commit'))
    def test_untrusted_requests_never_become_paths_or_commands(self):
        for key,value in [('variant','../foo'),('transaction',0),('role','admin'),('port',70000),('action','exec')]:
            r=self.request();r[key]=value
            with self.assertRaises(ValueError):session.validate_request(r)
        r=self.request();r.update(role='joiner',host='127.0.0.1;quit')
        with self.assertRaises(ValueError):session.validate_request(r)
    def test_qa_scorer_rejects_frozen_reserved_and_singleplayer(self):
        before={'role':1,'server_time':100,'players':[{}, {'state':1,'active':True,'command_time':10}]}
        frozen={'role':1,'server_time':200,'players':[{}, {'state':1,'active':True,'command_time':10}]}
        with self.assertRaises(ValueError):assess_liveness(before,frozen,2)
        frozen['players'][1]['command_time']=20
        assess_liveness(before,frozen,2)
        frozen['role']=0
        with self.assertRaises(ValueError):assess_liveness(before,frozen,2)

class SessionRecoveryRegressionTests(unittest.TestCase):
    def test_resume_requires_requested_map_role_and_actual_render_readiness(self):
        peer = {'variant': 'sp_improved', 'map': 'pathfinder', 'role': 'joiner',
                'joined': True, 'render_ready': True}
        self.assertTrue(session.recovery_ready(peer, 'sp_improved', 'pathfinder', False, 2))
        for key, value in [('map', 'training'), ('variant', 'uo'), ('role', 'host'),
                           ('joined', False), ('render_ready', False), ('render_ready', 'false')]:
            invalid = dict(peer, **{key: value})
            with self.subTest(field=key, value=value):
                self.assertFalse(session.recovery_ready(invalid, 'sp_improved', 'pathfinder', False, 2))
        host = dict(peer, role='host', joined=False, live_players=2)
        self.assertTrue(session.recovery_ready(host, 'sp_improved', 'pathfinder', True, 2))
        host['live_players'] = 1
        self.assertFalse(session.recovery_ready(host, 'sp_improved', 'pathfinder', True, 2))

    def request(self, action='prepare'):
        return {'action': action, 'transaction': 91, 'variant': 'uo', 'role': 'host',
                'port': 29003, 'host': '', 'map': 'bastogne1', 'difficulty': 3, 'players': 2}

    def test_known_ignored_pak_placeholder_does_not_hide_uo_mission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'coop').mkdir(); (root / 'Main').mkdir(); (root / 'uo').mkdir()
            manifest = {'schema': 1, 'protocol': session.PROTOCOL, 'complete_suite_required': True,
                        'variants': [{'id': variant, 'fs_game': '', 'content_roots': ['Main', 'uo']}
                                     for variant in session.VARIANTS]}
            (root / 'coop/variants.json').write_text(json.dumps(manifest), encoding='utf-8')
            (root / 'Main/pakb.pk3').write_bytes(b'\0')
            with zipfile.ZipFile(root / 'uo/pakuo00.pk3', 'w') as archive:
                archive.writestr('maps/bastogne1.bsp', b'fixture map')
            self.assertTrue(session.target_map_exists(root, 'uo', 'bastogne1'))
            self.assertFalse(session.target_map_exists(root, 'uo', 'not_installed'))
            self.assertEqual((root / 'Main/pakb.pk3').read_bytes(), b'\0')

    def test_recovery_preserves_target_map_difficulty_and_endpoint(self):
        request = self.request('commit')
        request.update(role='joiner', host='127.0.0.1:29003')
        spec = session.recovery_spec(request)
        self.assertEqual(spec, {'variant': 'uo', 'host': '127.0.0.1:29003', 'hosting': False,
                                'port': 29003, 'map': 'bastogne1', 'difficulty': 3})
        request.update(map='changed_after_validation', difficulty=0)
        self.assertEqual(spec['map'], 'bastogne1')
        self.assertEqual(spec['difficulty'], 3)

    def test_non_object_bridge_requests_are_rejected_cleanly(self):
        for value in (None, 0, [], 'prepare', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                session.validate_request(value)

    def test_owned_unresponsive_process_is_killed_after_graceful_attempts(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('fixture-game', 8),
                                    subprocess.TimeoutExpired('fixture-game', 5), 0]
        with mock.patch.object(session, 'send_command', return_value=True) as command:
            session.stop_owned(Path('/fixture'), process, False)
        command.assert_called_once_with(Path('/fixture'), 'quit', False)
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()

    def test_retry_consumes_failed_switch_before_launching_target(self):
        """Exercise the real supervisor loop with owned fake processes only.

        A commit whose old process crashed is retried at its requested map and
        difficulty. Advancing past the old quit deadline must not quit the newly
        launched target again.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'coop').mkdir()
            controls = queue.Queue()
            processes, launches, commands = [], [], []
            clock = [0.0]
            iterations = [0]
            retry_sent = [False]

            class OwnedProcess:
                def __init__(self):
                    self.pid = 1000 + len(processes)
                    self.returncode = None

                def poll(self):
                    return self.returncode

            def launch(*arguments):
                launches.append(arguments)
                return ['fixture-game'], {}

            def popen(*_arguments, **_keywords):
                if len(processes) >= 2:
                    raise AssertionError('retry started an unexpected additional process')
                process = OwnedProcess(); processes.append(process)
                return process

            def event(phase, **_details):
                if phase == 'running' and len(processes) == 1:
                    (root / 'coop/switch.json').write_text(json.dumps(self.request('prepare')))
                elif phase == 'prepared':
                    (root / 'coop/switch.json').write_text(json.dumps(self.request('commit')))
                elif phase == 'restarting':
                    processes[0].returncode = 9  # the old game fails after commitment
                elif phase == 'error' and not retry_sent[0]:
                    retry_sent[0] = True
                    controls.put({'action': 'retry'})

            def sleep(_seconds):
                iterations[0] += 1; clock[0] += 3
                if iterations[0] > 12:
                    raise AssertionError('supervisor did not finish the controlled recovery')
                if len(processes) == 2 and iterations[0] >= 5:
                    controls.put({'action': 'stop'})

            def send(_game, text, _joining):
                commands.append(text)
                return True

            def stop(_game, process, _joining):
                if process is not None:
                    process.returncode = 0

            args = argparse.Namespace(game=root, variant='cod1', host=None, hosting=True,
                                      port=28960, difficulty=1, map_name='pathfinder', runner=None)
            with mock.patch.object(session, 'check_installation', return_value={'ok': True, 'errors': [], 'variants': {'uo': 'digest'}}), \
                 mock.patch.object(session, 'target_map_exists', return_value=True), \
                 mock.patch.object(session, 'launch_arguments', side_effect=launch), \
                 mock.patch.object(session.subprocess, 'Popen', side_effect=popen), \
                 mock.patch.object(session.queue, 'Queue', return_value=controls), \
                 mock.patch.object(session.threading, 'Thread'), \
                 mock.patch.object(session.signal, 'signal'), \
                 mock.patch.object(session.time, 'monotonic', side_effect=lambda: clock[0]), \
                 mock.patch.object(session.time, 'sleep', side_effect=sleep), \
                 mock.patch.object(session, 'event', side_effect=event), \
                 mock.patch.object(session, 'send_command', side_effect=send), \
                 mock.patch.object(session, 'stop_owned', side_effect=stop):
                result = session.supervise(args)
            self.assertEqual(result, 0)
            self.assertEqual(len(launches), 2)
            self.assertEqual(launches[1][1], 'uo')
            self.assertEqual(launches[1][4:8], ('bastogne1', True, 29003, 3))
            self.assertNotIn('quit', commands)
            self.assertFalse((root / 'coop/session.lock').exists())
            self.assertFalse((root / 'coop/supervisor.json').exists())

if __name__=='__main__':unittest.main()
