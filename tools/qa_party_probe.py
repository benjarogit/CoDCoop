#!/usr/bin/env python3
"""Real explicit departure, host-only mission start and remote rejoin regression.

Uses the owned Wine/Xvfb harness. It does not certify a campaign playthrough.
No target mission UI click is injected: the mainline must start it normally.
"""
import argparse
import json
from pathlib import Path
import time

import qa_coop as qa


def remove_acknowledged_departure(errors, notice):
    """A deliberate native disconnect prints one localized ERROR notice.

    Remove only that observed occurrence; another disconnect still fails.
    """
    remaining = list(errors)
    if notice in remaining:
        remaining.remove(notice)
    return remaining


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=29929)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    report = {'status': 'NOT_RUN', 'coverage': 'explicit peer departure, host-only next mission readiness, real rejoin/input; no campaign completion'}
    smoke = ['--source', str(args.source.resolve()), '--run', str(output),
             '--runtime-dir', str(args.runtime_dir.resolve()), '--variant', 'sp_improved',
             '--map', 'pathfinder', '--players', '2', '--duration', '5',
             '--port', str(args.port), '--timeout', str(args.timeout)]
    original = qa.assess_liveness
    original_errors = qa.process_log_errors
    departure_notice = None
    entered = False

    def save():
        (output / 'party-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def states():
        return qa.read_state(host), qa.read_state(peer)

    def probe(before, after, count):
        nonlocal entered, departure_notice
        original(before, after, count)
        if entered:
            return
        entered = True
        report['initial'] = states()
        if report['initial'][0].get('expected_players') != 2:
            raise RuntimeError('initial agreed party is not two real players')
        if original_errors(peer):
            raise RuntimeError('peer already had native errors before explicit departure')
        qa.command(peer, 'coopleave', joiner=True)

        def departed():
            h, p = states()
            if h and p and p['role'] == 0 and not h['players'][1]['active']:
                if h.get('expected_players') != 1:
                    raise RuntimeError('explicit departure left a stale expected party')
                return [h, p]

        report['departed'] = qa.wait_for(departed, [], 20, 'explicit peer departure and adjusted party')
        notices = original_errors(peer)
        if notices:
            if len(notices) != 1 or notices[0].strip() not in ('ERROR: Getrennt', 'ERROR: Disconnected'):
                raise RuntimeError('unexpected native error during explicit departure: ' + repr(notices))
            departure_notice = notices[0]
            report['acknowledged_native_departure_notice'] = departure_notice
        save()
        log = host / 'codcoop.log'
        prior = len(log.read_bytes())
        qa.command(host, 'devmap pathfinder')

        def started_alone():
            h = qa.read_state(host)
            new_log = log.read_bytes()[prior:].decode('utf-8', errors='replace')
            if h and h.get('expected_players') == 1 and h['server_time'] > 500 and h.get('cls_state') == 2 and 'mainline: 1 players ready, normal mission-start UI action' in new_log:
                return h

        report['started_alone'] = qa.wait_for(started_alone, [], args.timeout, 'normal host-only next mission start')
        save()
        qa.command(peer, 'coopjoin 127.0.0.1:%d' % args.port, joiner=True)

        def rejoined():
            h, p = states()
            if h and p and p['role'] == 2 and p['joined'] and p['snapshot_num'] > 0 and h['players'][1]['active'] and h.get('expected_players') == 2:
                return [h, p]

        live = qa.wait_for(rejoined, [], args.timeout, 'real remote rejoin and restored party')
        time.sleep(2)
        current = rejoined()
        if not current:
            raise RuntimeError('remote lost its world after rejoining')
        original(live[0], current[0], 2)
        report.update(status='PASS', rejoined=current)
        save()

    qa.assess_liveness = probe
    def scoped_errors(folder):
        errors = original_errors(folder)
        return remove_acknowledged_departure(errors, departure_notice) if folder == peer else errors
    qa.process_log_errors = scoped_errors
    try:
        result = qa.main(smoke)
        if result:
            report['status'] = 'FAIL'
        save()
        return result
    finally:
        qa.assess_liveness = original
        qa.process_log_errors = original_errors


if __name__ == '__main__':
    raise SystemExit(main())
