#!/usr/bin/env python3
"""Real peer timeout then intentional departure; no campaign completion claim."""
import argparse
import json
import time
from pathlib import Path
import qa_coop as qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'run', 'runtime-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--variant', choices=('cod1', 'uo'), default='cod1')
    parser.add_argument('--port', type=int, default=29970)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()

    def scenario(folders, processes, initial):
        evidence = {'initial': initial}
        host, peer = folders
        def record():
            path=args.run/'reserved-departure-evidence.json'
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(evidence,indent=2,allow_nan=False))
            temporary.replace(path)
        record()
        slot = initial[1]['slot']
        def state():
            h = qa.read_state(host)
            return h if h and h['role'] == 1 else None
        def seat(h):
            return next(row for row in h['peer_inventory'] if row['slot'] == slot)
        if initial[0]['expected_players'] != 2 or not seat(initial[0])['reserved']:
            raise RuntimeError('Missing real two-player owner baseline')
        # Ordinary exposed network-loss control, not a direct remote/PS edit.
        qa.command(peer, 'coopnet 0 100', joiner=True)
        def timed_out():
            h = state()
            return h if h and not h['players'][slot]['active'] and seat(h)['reserved'] else None
        evidence['temporary_timeout'] = qa.wait_for(timed_out, processes, 20,
            'real host timeout retains inactive owner seat')
        record()
        if evidence['temporary_timeout']['expected_players'] != 2:
            raise RuntimeError('A temporary outage removed a confirmed party member')
        # One command batch restores sends, then emits the original three BYEs.
        qa.command(peer, 'coopnet 0 0\ncoopleave', joiner=True)
        def departed():
            h = state(); p = qa.read_state(peer)
            return [h, p] if h and p and p['role'] == 0 and not seat(h)['reserved'] and h['expected_players'] == 1 else None
        evidence['intentional_departure'] = qa.wait_for(departed, processes, 15,
            'inactive real owner leaves and releases precisely one party seat')
        record()
        before = evidence['intentional_departure'][0]['server_time']
        time.sleep(2)
        after = state()
        if (not after or after['server_time'] <= before or seat(after)['reserved'] or
                after['expected_players'] != 1 or after['players'][slot]['active']):
            raise RuntimeError('Host did not remain live with one seat after repeated BYEs')
        evidence['host_stays_live'] = after
        record()
        # End with a separately requested fresh join so the harness can retain
        # its ordinary all-player observation and clean-shutdown checks.
        old_lease=seat(initial[0])['lease']
        qa.command(peer, 'coopjoin 127.0.0.1:'+str(args.port), joiner=True)
        def fresh_join():
            h=state();p=qa.read_state(peer)
            if not h or not p or not p['joined']:return None
            owner=seat(h)
            return [h,p] if h['players'][slot]['active'] and p['slot']==slot and owner['reserved'] and owner['lease']>old_lease and h['expected_players']==2 else None
        evidence['explicit_fresh_join']=qa.wait_for(fresh_join,processes,args.timeout,
            'explicit fresh join obtains a new owner lease')
        record()
        return {'scope': 'Native timeout preserves owner; intentional inactive-owner leave releases it once; explicit fresh rejoin gets new lease',
                'checks': ['Two real players connected with advancing command clocks',
                           'Actual host timeout preserved reserved seat and expected party size',
                           'Original coopleave released inactive owner and decremented party once',
                           'Host world continued; departed peer did not regain a seat automatically',
                           'Explicit fresh rejoin acquired a new owner lease and restored two-player party'],
                'evidence': evidence,'intentional_departures':[1]}

    return qa.main(['--source', str(args.source), '--run', str(args.run),
                    '--runtime-dir', str(args.runtime_dir), '--variant', args.variant,
                    '--map', 'training', '--port', str(args.port), '--timeout', str(args.timeout)],
                   scenario=scenario)


if __name__ == '__main__':
    raise SystemExit(main())
