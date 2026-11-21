#!/usr/bin/env python3
"""QA-only, monotonic first-use model registry experiment with real peers.

Imports an owned four-kit resource catalog if supplied, then transfers the
host's complete approved ledger plus native registered media before peer load.
This local file exchange is not a production transport or equipment lobby.
"""
import argparse
import json
import os
from pathlib import Path
import time
import qa_coop as qa
from build_campaign_patch import build


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'run', 'runtime-dir'):
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--map', default='foy')
    parser.add_argument('--union', type=Path, help='approved actual four-kit xmodel name union')
    parser.add_argument('--checkpoint-reloads', type=int, default=0)
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--port', type=int, default=29963)
    args = parser.parse_args(argv)
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
    original_spawn, original_wait = qa.subprocess.Popen, qa.wait_for
    report = {'scope': 'QA-only deferred-first-use; no production contract or campaign acceptance', 'map': args.map,
              'four_kit_union': str(args.union) if args.union else None}
    def launch(command, *a, **kw):
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
        return original_spawn(command, *a, **kw)
    def waiting(predicate, processes, timeout, description):
        def checked():
            path = peer / 'codcoop_join.log'
            if path.exists() and 'native world attachment failed' in path.read_text(errors='replace'):
                raise RuntimeError('deferred model peer attachment failed; retained original native error')
            for folder in (host, peer):
                errors = qa.process_log_errors(folder)
                if errors: raise RuntimeError('native error during deferred registry probe: ' + errors[0])
            return predicate()
        return original_wait(checked, processes, timeout, description)
    old = os.environ.get('CODCOOP_QA_DEFER_MODELS')
    os.environ['CODCOOP_QA_DEFER_MODELS'] = '1'
    qa.subprocess.Popen, qa.wait_for = launch, waiting
    try:
        result = qa.main(command)
        report['status'] = 'PASS' if not result else 'FAIL'
        for seat, folder in [('host', host), ('join1', peer)]:
            try:
                report[seat] = {'registration': json.loads((folder / 'qa-deferred-models.json').read_text()),
                                'final': qa.read_state(folder).get('deferred_models')}
            except (OSError, ValueError, AttributeError): pass
        (output / 'deferred-models-probe.json').write_text(json.dumps(report, indent=2) + '\n')
        return result
    finally:
        qa.subprocess.Popen, qa.wait_for = original_spawn, original_wait
        if old is None: os.environ.pop('CODCOOP_QA_DEFER_MODELS', None)
        else: os.environ['CODCOOP_QA_DEFER_MODELS'] = old

if __name__ == '__main__': raise SystemExit(main())
