#!/usr/bin/env python3
"""Two real UF/UO-engine players watch the native GSC movie and reconnect.

This is a targeted movie/transition probe, not a completed campaign mission.
The underlying harness owns copied installations, saves, Wine and Xvfb.
"""
import argparse
import json
from pathlib import Path
import time

import qa_coop as qa
from build_campaign_patch import build


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--port', type=int, default=29917)
    parser.add_argument('--timeout', type=int, default=480)
    parser.add_argument('--runtime-dir', type=Path,
                        help='Immutable native DLL input, forwarded to the real-instance harness')
    args = parser.parse_args(argv)
    output = args.run.resolve()
    smoke = ['--source', str(args.source.resolve()), '--run', str(output), '--variant', 'united_fronts',
             '--map', 'pathfinder', '--players', '2', '--timeout', str(args.timeout),
             '--duration', '5', '--port', str(args.port)]
    if args.runtime_dir:
        smoke += ['--runtime-dir', str(args.runtime_dir.resolve())]
    if qa.main(smoke + ['--prepare-only']):
        return 1
    (output / 'movie-probe.json').unlink(missing_ok=True)
    for seat in ('host', 'join1'):
        folder = output / seat / 'UnitedFronts'
        build(folder / 'ZUnitedFronts_1.1_beta.pk3', folder / 'zzzz_coop_campaign.pk3', 'united_fronts', qa=True)
    original = qa.assess_liveness
    report = {'status': 'NOT_RUN', 'coverage': 'native GSC movie, both playback handles, playing ACK, natural movie end and post-movie real peer reconnection/input; no campaign-completion claim'}
    entered = False

    def save():
        (output / 'movie-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    def states():
        return [qa.read_state(output / seat) for seat in ('host', 'join1')]

    def probe(before, after, count):
        nonlocal entered
        original(before, after, count)
        if entered:
            return
        entered = True
        qa.command(output / 'host', 'set coop_qa_movie run')

        def playing():
            value = states()
            return value if all(s and s.get('movieplaying') == 1 and s.get('cls_state') == 3 for s in value) and value[0].get('movie_ack_mask', 0) & 2 else None

        report['states_started'] = qa.wait_for(playing, [], 60, 'native script movie on both instances with playing ACK')
        report['status'] = 'STARTED'; save()

        def ended():
            value = states()
            return value if all(s and s.get('movieplaying') == 0 for s in value) else None

        report['states_ended'] = qa.wait_for(ended, [], 180, 'natural movie completion on both instances')
        if not report['states_ended'][1]['joined'] or report['states_ended'][1]['role'] != 2:
            raise RuntimeError('movie lost the joined party')
        report['status'] = 'ENDED'; save()
        qa.command(output / 'host', 'devmap pathfinder')
        last_start = [0.0]

        def resumed():
            host, peer = states()
            if host and host.get('cls_state') == 2 and host.get('server_time', 0) < 500 and time.monotonic() - last_start[0] > 2:
                qa.command(output / 'host', 'coopqastart')
                last_start[0] = time.monotonic()
            if (host and peer and host['map'] == peer['map'] == 'pathfinder' and peer['joined'] and
                    host['server_time'] > 500 and peer['snapshot_num'] > 0 and host['players'][1]['active'] and
                    host['players'][1]['state'] == 1):
                return [host, peer]

        live = qa.wait_for(resumed, [], args.timeout, 'post-movie native world and real peer reconnection')
        time.sleep(2)
        current = resumed()
        if not current:
            raise RuntimeError('reconnected peer lost its world')
        original(live[0], current[0], 2)
        report.update(status='PASS', states_resumed=current); save()

    qa.assess_liveness = probe
    try:
        result = qa.main(smoke)
        if result:
            report['status'] = 'FAIL'
        save()
        return result
    finally:
        qa.assess_liveness = original


if __name__ == '__main__':
    raise SystemExit(main())
