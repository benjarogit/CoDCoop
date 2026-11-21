#!/usr/bin/env python3
"""Real YAP divergent config / host update / override / local restore gate.

Reuses owned Wine copies; does not certify mission completion or Windows hardware.
"""
import argparse
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
    parser.add_argument('--port', default=29939, type=int)
    parser.add_argument('--timeout', default=300, type=int)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    smoke = ['--source', str(args.source.resolve()), '--run', str(output), '--runtime-dir', str(args.runtime_dir.resolve()),
             '--variant', 'sp_improved', '--map', 'pathfinder', '--players', '2', '--duration', '5',
             '--port', str(args.port), '--timeout', str(args.timeout)]
    original_spawn, original_live, original_errors = qa.subprocess.Popen, qa.assess_liveness, qa.process_log_errors
    report = {'status': 'NOT_RUN', 'coverage': 'real host authority for three YAP prediction/gameplay settings; no full campaign claim'}
    entered = False
    notice = None

    def save():
        (output / 'host-rules-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def engine_spawn(command, *a, **kw):
        if isinstance(command, list) and len(command) > 1 and Path(command[1]).name.lower() == 'coduosp.exe':
            folder = Path(kw['cwd'])
            values = (1.9, 0.55, 1, 83) if folder == host else (0.8, 0.25, 0, 101)
            cfg = 'set player_sprintSpeedScale %s\nset player_sprintmult %s\nset bg_allowJumpShot %s\nset cg_fov %s\n' % values
            (folder / 'sp_improved/coop_rules_probe.cfg').write_text(cfg)
            command = list(command)
            at = command.index('+devmap')
            command[at:at] = ['+exec', 'coop_rules_probe.cfg']
        return original_spawn(command, *a, **kw)

    def same(state, values):
        r = state.get('rules', {}) if state else {}
        return (r.get('valid') and abs(r.get('sprint_scale', -99) - values[0]) < 0.00001 and
                abs(r.get('sprint_multiplier', -99) - values[1]) < 0.00001 and r.get('jump_shot') == values[2])

    def matched(values, newer_than=0):
        h, p = qa.read_state(host), qa.read_state(peer)
        if not h or not p or not p.get('joined') or not same(h, values) or not same(p, values):
            return None
        hr, pr = h['rules'], p['rules']
        if hr['serial'] <= newer_than or hr['serial'] != pr['serial'] or pr['required'] != hr['serial'] or not hr['ack_mask'] & (1 << p['slot']):
            return None
        if abs(h.get('local_fov', 0) - 83) > 0.01 or abs(p.get('local_fov', 0) - 101) > 0.01:
            raise RuntimeError('local graphics setting changed while synchronizing gameplay rules')
        return [h, p]

    def probe(before, after, count):
        nonlocal entered, notice
        original_live(before, after, count)
        if entered:
            return
        entered = True
        report['initial'] = qa.wait_for(lambda: matched((1.9, 0.55, 1)), [], 20, 'divergent initial configs converged to host rules')
        log = (peer / 'codcoop_join.log').read_text(errors='replace')
        applied = log.find('rules: applied host sequence ')
        attached = log.find('joiner: conectado al host como slot ')
        if applied < 0 or attached < 0 or applied >= attached:
            raise RuntimeError('host gameplay settings were not applied before native attachment')
        report['before_attach_log_order'] = 'PASS'
        initial_serial = report['initial'][0]['rules']['serial']
        qa.command(host, 'set player_sprintSpeedScale 2.25\nset player_sprintmult 0.75\nset bg_allowJumpShot 0')
        report['updated'] = qa.wait_for(lambda: matched((2.25, 0.75, 0), initial_serial), [], 20, 'live host rule update acknowledged')
        qa.command(peer, 'set player_sprintSpeedScale 0.1\nset player_sprintmult 0.1\nset bg_allowJumpShot 1', joiner=True)
        time.sleep(1)
        report['local_override_corrected'] = qa.wait_for(lambda: matched((2.25, 0.75, 0)), [], 10, 'host rules restored after local override')
        qa.command(peer, 'coopleave', joiner=True)

        def restored():
            h, p = qa.read_state(host), qa.read_state(peer)
            if h and p and p['role'] == 0 and not h['players'][1]['active'] and same(p, (0.8, 0.25, 0)) and not p['rules']['saved_local']:
                if p.get('local_fov') != 101:
                    raise RuntimeError('local FOV changed during leave')
                return [h, p]

        report['restored'] = qa.wait_for(restored, [], 20, 'explicit leave restored original local gameplay settings')
        errors = original_errors(peer)
        if errors:
            if len(errors) != 1 or errors[0].strip() not in ('ERROR: Getrennt', 'ERROR: Disconnected'):
                raise RuntimeError('unexpected native error during deliberate departure: ' + repr(errors))
            notice = errors[0]
            report['acknowledged_native_departure_notice'] = notice
        save()
        qa.command(peer, 'coopjoin 127.0.0.1:%d' % args.port, joiner=True)
        report['rejoined'] = qa.wait_for(lambda: matched((2.25, 0.75, 0)), [], args.timeout, 'real rejoin reapplied host rules')
        time.sleep(2)
        original_live(report['rejoined'][0], qa.read_state(host), 2)
        report['status'] = 'PASS'
        save()

    def errors(folder):
        observed = original_errors(folder)
        return remove_acknowledged_departure(observed, notice) if folder == peer else observed

    qa.subprocess.Popen, qa.assess_liveness, qa.process_log_errors = engine_spawn, probe, errors
    try:
        result = qa.main(smoke)
        if result:
            report['status'] = 'FAIL'
        save()
        return result
    finally:
        qa.subprocess.Popen, qa.assess_liveness, qa.process_log_errors = original_spawn, original_live, original_errors


if __name__ == '__main__':
    raise SystemExit(main())
