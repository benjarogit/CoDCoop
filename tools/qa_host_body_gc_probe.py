#!/usr/bin/env python3
"""Ordinary UO: persistent Core body ownership through hot reload and native saves.

Uses the real game harness and no deferred-model/borrow/barrier experiments.
Raw QA must opt into body GC; prepared-profile acceptance is a separate gate.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import qa_coop as qa


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    prepared='--prepared-profile' in args
    if prepared:args.remove('--prepared-profile')
    if '--run' not in args:
        raise ValueError('--run is required')
    output = Path(args[args.index('--run') + 1]).resolve()
    for name in ('CODCOOP_QA_DEFER_MODELS', 'CODCOOP_QA_BORROW_TREES',
                 'CODCOOP_QA_DOBJ_BARRIER', 'CODCOOP_QA_MT_EPOCH'):
        os.environ.pop(name, None)
    if prepared:
        os.environ.pop('CODCOOP_QA_HOST_BODY_GC',None)
        os.environ['CODCOOP_QA_PROFILE']='1'
    else:
        os.environ.pop('CODCOOP_QA_PROFILE',None)
        os.environ['CODCOOP_QA_HOST_BODY_GC'] = '1'
    for flag, value in (('--variant', 'uo'), ('--players', '2'), ('--checkpoint-reloads', '5')):
        if flag in args:
            if args[args.index(flag) + 1] != value:
                raise ValueError(flag + ' must be ' + value)
        else:
            args += [flag, value]
    report = {'status': 'FAIL', 'scope': 'prepared UO profile default policy, 256 MB' if prepared else 'ordinary UO, raw QA opt-in, 256 MB',
              'prepared_profile':prepared,'raw_gc_override':os.environ.get('CODCOOP_QA_HOST_BODY_GC'),
              'runner_sha256': hashlib.sha256(Path(qa.__file__).read_bytes()).hexdigest(),
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    original = qa.assess_liveness
    performed = False

    def assess(before, after, count):
        nonlocal performed
        original(before, after, count)
        if performed:
            return
        performed = True
        host, peer = output / 'host', output / 'join1'
        current = qa.read_state(host)
        ownership = current['host_body_gc']
        if not ownership['required'] or not ownership['ready'] or ownership['tracked'] != 2:
            raise RuntimeError('active host bodies are not tracked before hot reload')
        for key in ('deferred_models', 'native_tree_borrow'):
            if current.get(key, {}).get('enabled'):
                raise RuntimeError('unrelated experimental feature enabled: ' + key)
        report['before_hotreload'] = current
        log = host / 'codcoop.log'
        offset = log.stat().st_size
        qa.command(host, 'coopreload')

        def reloaded():
            text = log.read_text(errors='replace')[offset:]
            state = qa.read_state(host)
            remote = qa.read_state(peer)
            if not state or not remote or 'estado conservado' not in text:
                return None
            gc = state['host_body_gc']
            if state['role'] == 1 and remote['joined'] and gc['ready'] and gc['tracked'] == 2 and state['server_time'] > current['server_time'] + 1000:
                if state['mt_epoch']['value'] != current['mt_epoch']['value']:
                    raise RuntimeError('same-world hot reload changed native allocator epoch')
                if gc['freed'] < ownership['freed'] or gc['forgotten'] != ownership['forgotten']:
                    raise RuntimeError('hot reload lost persisted ownership counters')
                original(current, state, count)
                return state
        report['after_hotreload'] = qa.wait_for(reloaded, [], 45, 'same-binary active-host reload preserving ownership')

    qa.assess_liveness = assess
    try:
        result = qa.main(args)
        final = json.loads((output / 'after.json').read_text()) if (output / 'after.json').exists() else None
        report['final'] = final
        if result == 0 and performed:
            gc = final[0]['host_body_gc']
            if not gc['ready'] or gc['tracked'] != 2 or gc['freed'] < 10 or gc['forgotten']:
                raise RuntimeError('five-load ownership cleanup not demonstrated')
            report['status'] = 'PASS'
        return 0 if report['status'] == 'PASS' else 1
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        report['error'] = str(error)
        return 1
    finally:
        qa.assess_liveness = original
        output.mkdir(parents=True, exist_ok=True)
        (output / 'host-body-gc-probe.json').write_text(json.dumps(report, indent=2))
        for source in (Path(__file__), Path(qa.__file__)):
            (output / ('executed-' + source.name)).write_bytes(source.read_bytes())


if __name__ == '__main__':
    raise SystemExit(main())
