#!/usr/bin/env python3
"""Actual twenty-second link outage across native same-map restart.

Requires a visible logical reconnection wait, automatic new-world attachment,
native movement and clean shutdown. No post-outage join command is injected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import qa_coop as qa
from qa_partition_probe import relay_call, partition_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--runtime-dir', required=True, type=Path)
    parser.add_argument('--chaos-checkout', required=True, type=Path)
    parser.add_argument('--port', type=int, default=29953)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    report = {'status': 'NOT_RUN', 'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'coverage': '20s both-direction outage across actual same-map restart; no campaign completion'}
    original = qa.assess_liveness
    entered = False

    def save():
        (output / 'reconnect-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def states():
        return qa.read_state(host), qa.read_state(peer)

    def healthy():
        for folder in (host, peer):
            errors = qa.process_log_errors(folder)
            if errors:
                raise RuntimeError('native error during outage recovery: ' + errors[0])

    def probe(before, after, count):
        nonlocal entered
        original(before, after, count)
        if entered:
            return
        entered = True
        report['before'] = states()
        previous_world = report['before'][1]['snapshot_time']
        offset = (peer / 'codcoop_join.log').stat().st_size
        info = json.loads((output / 'chaos-info.json').read_text())
        report['partition_ack'] = relay_call(info['rpc'], 'partition', dir='both', on=True, duration_ms=20000)
        qa.command(host, 'devmap training')

        def waiting():
            healthy()
            h, p = states()
            if p and p.get('recovering_connection') and p['role'] == 2 and not p['joined']:
                return h, p

        report['waiting'] = qa.wait_for(waiting, [], 19, 'logical reconnection wait before link restoration')
        save()

        def recovered():
            healthy()
            h, p = states()
            if h and p and h['role'] == 1 and p['role'] == 2 and p['joined'] and not p.get('recovering_connection') and p.get('snapshot_num', 0) > 0 and h['players'][1]['active'] and h['map'] == p['map'] == 'training':
                text = (peer / 'codcoop_join.log').read_bytes()[offset:].decode(errors='replace')
                if 'joiner: native map training ready, generation' in text:
                    return h, p

        live = qa.wait_for(recovered, [], args.timeout, 'automatic recovery after link restoration')
        report['packet_evidence'] = partition_evidence(output / 'chaos.jsonl', 'both')
        duration = report['packet_evidence']['observed_partition_ms']
        if duration is None or not 19500 <= duration <= 22000 or not report['packet_evidence']['dropped_reload_controls']:
            raise RuntimeError('outage/reload loss was not actually observed in relay log')
        time.sleep(2)
        final = recovered()
        if not final:
            raise RuntimeError('recovered peer lost world')
        original(live[0], final[0], count)
        distance = qa.move_remote(host, peer, final[1]['slot'], [], args.timeout)
        report.update(status='PASS', recovered=final, movement_units=distance,
                      old_snapshot_time=previous_world)
        save()

    qa.assess_liveness = probe
    try:
        result = qa.main(['--source', str(args.source.resolve()), '--run', str(output),
                          '--runtime-dir', str(args.runtime_dir.resolve()), '--variant', 'cod1',
                          '--map', 'training', '--players', '2', '--duration', '5',
                          '--port', str(args.port), '--timeout', str(args.timeout),
                          '--chaos-checkout', str(args.chaos_checkout.resolve()), '--chaos-profile', 'lan'])
        if result:
            report.update(status='FAIL', last_states=states())
        log = output / 'chaos.jsonl'
        if log.exists():
            report['final_packet_evidence'] = partition_evidence(log, 'both')
        save()
        return result
    finally:
        qa.assess_liveness = original


if __name__ == '__main__':
    raise SystemExit(main())
