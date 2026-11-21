#!/usr/bin/env python3
"""Replay genuine old-world control AND native engine packets after reload."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import qa_coop as qa
from qa_world_replay_relay import ReplayRelay


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--runtime-dir', required=True, type=Path)
    parser.add_argument('--chaos-checkout', required=True, type=Path)
    parser.add_argument('--port', type=int, default=29961)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    report = {'status': 'NOT_RUN', 'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'coverage': 'actual old-world replay across native restart, current-world input and clean exits; no campaign completion'}
    original, start = qa.assess_liveness, qa.subprocess.Popen
    relay = None
    entered = False

    def save():
        (output / 'world-replay-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def popen(command, *positional, **keywords):
        nonlocal relay
        if isinstance(command, (list, tuple)) and 'relay' in command and '--target' in command:
            target = list(command).index('--target') + 1
            if command[target] == '127.0.0.1:%d' % args.port:
                if relay is not None:
                    raise RuntimeError('replay relay already started')
                relay = ReplayRelay(args.port, output)
                command = list(command)
                command[target] = '127.0.0.1:%d' % relay.port
        return start(command, *positional, **keywords)

    def states():
        return qa.read_state(host), qa.read_state(peer)

    def healthy():
        if relay is None or relay.error:
            raise RuntimeError('replay relay unavailable: ' + str(relay.error if relay else None))
        for folder in (host, peer):
            errors = qa.process_log_errors(folder)
            if errors:
                raise RuntimeError('native replay error: ' + errors[0])

    def probe(before, after, count):
        nonlocal entered
        original(before, after, count)
        if entered:
            return
        entered = True
        healthy()
        baseline = states()
        if any('stale_by_type' not in state.get('world_wire', {}) for state in baseline):
            raise RuntimeError('runtime lacks protocol9 typed replay-drop diagnostics')
        report['before'] = baseline
        qa.command(host, 'devmap training')

        def rejected():
            healthy()
            h, p = states()
            if not relay.delivered or not h or not p or not p['joined'] or not h['players'][1]['active']:
                return None
            required = {direction: {kind for route, kind in relay.gate.captured if route == direction}
                        for direction in ('c2s', 's2c')}
            if not {ord('z'), ord('D'), ord('N'), ord('E')}.issubset(required['s2c']) or ord('z') not in required['c2s']:
                raise RuntimeError('actual native/model/animation/entity replay inputs missing')
            for direction, index in (('c2s', 0), ('s2c', 1)):
                old = baseline[index]['world_wire']['stale_by_type']
                now = (h, p)[index]['world_wire']['stale_by_type']
                if any(now.get(str(kind), 0) <= old.get(str(kind), 0) for kind in required[direction]):
                    return None
            return h, p

        live = qa.wait_for(rejected, [], args.timeout, 'genuine old-world frames rejected by type in both directions')
        report['replay_counts'] = dict(relay.counts)
        report['old_world'], report['new_world'] = relay.gate.initial, relay.gate.current
        if report['old_world'] == report['new_world']:
            raise RuntimeError('world did not actually change')
        # Native startup/readiness may settle after the first attached snapshot.
        def advancing():
            current = rejected()
            if not current:
                return None
            try:
                original(live[0], current[0], count)
            except ValueError:
                return None
            return current
        recovered = qa.wait_for(advancing, [], 15, 'current-world user commands advance after old-world replay')
        distance = qa.move_remote(host, peer, recovered[1]['slot'], [], args.timeout)
        report.update(status='PASS', rejected=recovered, movement_units=distance)
        save()

    qa.assess_liveness, qa.subprocess.Popen = probe, popen
    try:
        result = qa.main(['--source', str(args.source.resolve()), '--run', str(output),
                          '--runtime-dir', str(args.runtime_dir.resolve()), '--variant', 'cod1',
                          '--map', 'training', '--players', '2', '--duration', '5',
                          '--port', str(args.port), '--timeout', str(args.timeout),
                          '--chaos-checkout', str(args.chaos_checkout.resolve()), '--chaos-profile', 'lan'])
        if result:
            report.update(status='FAIL', last_states=states())
        save()
        return result
    finally:
        qa.assess_liveness, qa.subprocess.Popen = original, start
        if relay is not None:
            relay.close()


if __name__ == '__main__':
    raise SystemExit(main())
