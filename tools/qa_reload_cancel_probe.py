#!/usr/bin/env python3
"""Actual host cancellation while a peer loads, followed by a fresh session.

Checks that the pending automatic rejoin stops before explicitly starting a new
session. One observed intentional native disconnect notice is acknowledged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import qa_coop as qa
from qa_party_probe import remove_acknowledged_departure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--runtime-dir', required=True, type=Path)
    parser.add_argument('--port', type=int, default=29947)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    report = {'status': 'NOT_RUN', 'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'coverage': 'host cancellation during native map loading, stopped rejoin and fresh session; no campaign completion'}
    original, original_errors = qa.assess_liveness, qa.process_log_errors
    entered = False
    notice = None

    def save():
        (output / 'cancel-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def states():
        return qa.read_state(host), qa.read_state(peer)

    def probe(before, after, count):
        nonlocal entered, notice
        original(before, after, count)
        if entered:
            return
        entered = True
        if original_errors(host) or original_errors(peer):
            raise RuntimeError('native error before cancellation')
        log = host / 'codcoop.log'
        offset = log.stat().st_size
        qa.command(host, 'devmap pathfinder')
        qa.wait_for(lambda: 'host: carga el mapa pathfinder' in log.read_bytes()[offset:].decode(errors='replace'), [],
                    args.timeout, 'native transition begins')
        # The host consumes this command after its blocking native map load;
        # the peer is already loading and its native slot has been dropped.
        qa.command(host, 'coopleave')

        def cancelled():
            h, p = states()
            text = (peer / 'sp_improved/console.log').read_text(errors='replace')
            if h and p and h['role'] == 0 and p['role'] == 0 and not p['joined'] and p.get('cls_state') == 0 and 'host closed the co-op game' in text:
                return h, p

        report['cancelled'] = qa.wait_for(cancelled, [], args.timeout, 'pending peer receives authenticated host cancellation')
        transition_log = log.read_bytes()[offset:].decode(errors='replace')
        if 'host: jugador remoto' in transition_log:
            raise RuntimeError('peer was already reallocated before host cancellation; invalid pending-load scenario')
        report['host_cancelled_before_remote_reallocation'] = True
        errors = original_errors(peer)
        if errors:
            if len(errors) != 1 or errors[0].strip() not in ('ERROR: Getrennt', 'ERROR: Disconnected'):
                raise RuntimeError('unexpected native error on host cancellation: ' + repr(errors))
            notice = errors[0]
            report['acknowledged_native_disconnect_notice'] = notice
        for _ in range(10):
            time.sleep(0.5)
            if not cancelled():
                raise RuntimeError('queued automatic rejoin revived cancelled session')
        report['stopped_rejoin_seconds'] = 5
        save()
        qa.command(host, 'coophost %d' % args.port)
        qa.command(peer, 'coopjoin 127.0.0.1:%d' % args.port, joiner=True)

        def fresh():
            h, p = states()
            if h and p and h['role'] == 1 and p['role'] == 2 and p['joined'] and p.get('snapshot_num', 0) > 0 and h['players'][1]['active'] and h['map'] == p['map'] == 'pathfinder':
                return h, p

        live = qa.wait_for(fresh, [], args.timeout, 'explicit fresh session after cancellation')
        time.sleep(2)
        recovered = fresh()
        if not recovered:
            raise RuntimeError('fresh session disconnected')
        original(live[0], recovered[0], count)
        report.update(status='PASS', fresh_session=recovered)
        save()

    def errors(folder):
        found = original_errors(folder)
        return remove_acknowledged_departure(found, notice) if folder == peer else found

    qa.assess_liveness, qa.process_log_errors = probe, errors
    try:
        result = qa.main(['--source', str(args.source.resolve()), '--run', str(output),
                          '--runtime-dir', str(args.runtime_dir.resolve()), '--variant', 'sp_improved',
                          '--map', 'training', '--players', '2', '--duration', '5',
                          '--port', str(args.port), '--timeout', str(args.timeout)])
        if result:
            report.update(status='FAIL', last_states=states())
        save()
        return result
    finally:
        qa.assess_liveness, qa.process_log_errors = original, original_errors


if __name__ == '__main__':
    raise SystemExit(main())
