#!/usr/bin/env python3
"""QA-only, monotonic first-use model registry experiment with real peers.

Imports an owned four-kit resource catalog if supplied, then transfers the
host's complete approved ledger plus native registered media before peer load.
This local file exchange is not a production transport or equipment lobby.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import time
import qa_coop as qa
from build_campaign_patch import build
from qa_model_mapping_relay import OwnedRelay


def fire_evidence_complete(requested, events, worlds):
    return not requested or len(events) >= worlds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'run', 'runtime-dir'):
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--map', default='foy')
    parser.add_argument('--union', type=Path, help='approved actual four-kit xmodel name union')
    parser.add_argument('--checkpoint-reloads', type=int, default=0)
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--port', type=int, default=29963)
    parser.add_argument('--delay-checkpoint-dobjs-ms', type=int, default=0, help='QA causal mapping-window relay,0..5000ms')
    parser.add_argument('--hunk-megs', type=int, choices=(256,512), default=256)
    parser.add_argument('--weapon-helper', type=Path, help='native read-only QA observer; requires actual remote fire/clip decrease')
    args = parser.parse_args(argv)
    if not 0 <= args.delay_checkpoint_dobjs_ms <= 5000: parser.error('DObj delay must be0..5000ms')
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    command = ['--source', str(args.source.resolve()), '--run', str(output), '--runtime-dir', str(args.runtime_dir.resolve()),
               '--variant', 'united_fronts', '--map', args.map, '--players', '2', '--timeout', str(args.timeout),
               '--duration', '5', '--port', str(args.port), '--checkpoint-reloads', str(args.checkpoint_reloads)]
    if qa.main(command + ['--prepare-only']): return 1
    for folder in (host, peer):
        build(folder / 'UnitedFronts/ZUnitedFronts_1.1_beta.pk3', folder / 'UnitedFronts/zzzz_coop_campaign.pk3', 'united_fronts', qa=False)
        for pattern in ('qa-model-ledger-*', 'qa-deferred-models.*', 'qa-model-export.*', 'qa-render-models.*', 'qa-render-preload.*'):
            for path in folder.glob(pattern): path.unlink()
        if args.union: (folder / 'qa-deferred-models.txt').write_bytes(args.union.read_bytes())
    original_spawn, original_wait, original_move, original_live = qa.subprocess.Popen, qa.wait_for, qa.move_remote, qa.assess_liveness
    report = {'scope': 'QA-only deferred-first-use; no production contract or campaign acceptance', 'map': args.map,
              'four_kit_union': str(args.union) if args.union else None, 'hunk_megs': args.hunk_megs,
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    game_env = {}
    relay = None
    def launch(command, *a, **kw):
        nonlocal relay
        if isinstance(command, list) and len(command) > 1 and Path(command[1]).name.lower() == 'coduosp.exe':
            command = list(command)
            if 'com_hunkmegs' in command: command[command.index('com_hunkmegs')+1] = str(args.hunk_megs)
            game_env.update(kw['env'])
        if isinstance(command, list) and len(command) > 1 and Path(command[1]).name.lower() == 'coduosp.exe' and Path(kw['cwd']) == peer:
            def ready():
                state = qa.read_state(host)
                try: audit = json.loads((host / 'qa-deferred-models.json').read_text())
                except (ValueError, OSError): return None
                return state if state and state['server_time'] > 1000 and audit['map'] == args.map else None
            report['host_before_peer'] = original_wait(ready, [], args.timeout, 'actual host ledger before peer native load')
            names = set()
            for path in [host / ('qa-model-ledger-' + args.map + '.txt'), host / 'qa-model-export.txt']:
                names.update(path.read_text().splitlines())
            if args.union: names.update(args.union.read_text().splitlines())
            text = '\n'.join(sorted(names)) + '\n'
            (peer / 'qa-deferred-models.txt').write_text(text)
            (output / 'deferred-host-derived-union.txt').write_text(text)
            report['union_names'] = len(names)
            if args.delay_checkpoint_dobjs_ms:
                at = command.index('+coopjoin')+1
                address,port = command[at].rsplit(':',1)
                relay = OwnedRelay((address,int(port)),args.delay_checkpoint_dobjs_ms/1000)
                command[at] = '127.0.0.1:' + str(relay.port)
        return original_spawn(command, *a, **kw)
    def waiting(predicate, processes, timeout, description):
        def checked():
            for folder in (host, peer):
                errors = qa.process_log_errors(folder)
                if errors: raise RuntimeError('native error during deferred registry probe: ' + errors[0])
            return predicate()
        return original_wait(checked, processes, timeout, description)
    def liveness(before,after,count):
        report.setdefault('liveness_samples',[]).append({'before':before,'after':after,'players':count})
        return original_live(before,after,count)
    def move_remote(host_folder, peer_folder, slot, processes, timeout, action='+forward'):
        result = original_move(host_folder,peer_folder,slot,processes,timeout,action)
        if args.weapon_helper:
            def observe():
                result = subprocess.run(['wine',qa.zpath(args.weapon_helper), str(host_folder).replace('/', '\\').split('\\')[-2] + '\\host',str(slot)],
                    env=game_env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10)
                if result.returncode: raise RuntimeError('native weapon observer failed: ' + str(result.returncode))
                return json.loads(result.stdout)
            before = observe()
            if not before['weapon']: raise RuntimeError('remote has no active weapon for actual firing probe')
            qa.command(peer_folder,'+attack',joiner=True)
            try:
                def fired():
                    after = observe()
                    decreases = [i for i,(a,b) in enumerate(zip(before['clips'],after['clips'])) if b < a]
                    if after['command_time'] > before['command_time'] and after['weapon'] == before['weapon'] and decreases:
                        return {'before':before,'after':after,'decreased_clip_indices':decreases}
                report.setdefault('actual_remote_fire',[]).append(original_wait(fired,processes,5,'native remote ammunition consumed through real attack input'))
            finally: qa.command(peer_folder,'-attack',joiner=True)
        return result
    old = os.environ.get('CODCOOP_QA_DEFER_MODELS')
    os.environ['CODCOOP_QA_DEFER_MODELS'] = '1'
    qa.subprocess.Popen, qa.wait_for, qa.move_remote, qa.assess_liveness = launch, waiting, move_remote, liveness
    try:
        result = qa.main(command)
        if relay:
            relay.close()
            report['mapping_window_relay'] = relay.evidence()
            if not result and not report['mapping_window_relay']['dropped_dobjs']:
                result = 1
                report['error'] = 'targeted mapping-window delay did not drop actual checkpoint DObj packets'
        if not result and not fire_evidence_complete(args.weapon_helper,report.get('actual_remote_fire',[]),args.checkpoint_reloads+1):
            result = 1
            report['error'] = 'requested native firing proof was not executed in every required world'
        report['status'] = 'PASS' if not result else 'FAIL'
        for seat, folder in [('host', host), ('join1', peer)]:
            try:
                report[seat] = {'registration': json.loads((folder / 'qa-deferred-models.json').read_text()),
                                'final': qa.read_state(folder).get('deferred_models')}
            except (OSError, ValueError, AttributeError): pass
        (output / 'deferred-models-probe.json').write_text(json.dumps(report, indent=2) + '\n')
        return result
    finally:
        if relay and relay.running: relay.close()
        qa.subprocess.Popen, qa.wait_for, qa.move_remote, qa.assess_liveness = original_spawn, original_wait, original_move, original_live
        if old is None: os.environ.pop('CODCOOP_QA_DEFER_MODELS', None)
        else: os.environ['CODCOOP_QA_DEFER_MODELS'] = old

if __name__ == '__main__': raise SystemExit(main())
