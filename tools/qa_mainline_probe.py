#!/usr/bin/env python3
"""Observe the real CoD credits -> UO transition with two live clients.

This targeted route test starts at the original credits alias, not Berlin.
It accelerates engine time while the unchanged credits run to completion.
It never changes mission flags, calls missionSuccess, or issues a map command.
"""
import argparse
import json
from pathlib import Path
import shutil
import time

import qa_coop
from build_campaign_patch import build, build_mainline_patch, build_trigger_patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--port', default=29865, type=int)
    parser.add_argument('--timeout', default=240, type=int)
    parser.add_argument('--runtime-dir', type=Path, help='immutable directory containing the exact runtime DLLs to test')
    args = parser.parse_args()
    output = args.run.resolve()
    smoke = ['--source', str(args.source.resolve()), '--run', str(output),
             '--variant', 'sp_improved', '--map', 'coop_cod1_credits', '--players', '2',
             '--initial-expected-players', '1',
             '--timeout', str(args.timeout), '--duration', '12', '--port', str(args.port)]
    if args.runtime_dir:
        smoke += ['--runtime-dir', str(args.runtime_dir.resolve())]
    if qa_coop.main(smoke + ['--prepare-only']) != 0:
        return 1
    (output / 'mainline-probe.json').unlink(missing_ok=True)
    (output / 'mainline-arrival.json').unlink(missing_ok=True)
    (output / 'mainline-departure.json').unlink(missing_ok=True)
    folders = [output / 'host', output / 'join1']
    for folder in folders:
        # Reused historical clones must receive the current production overlays,
        # not only the bridge itself. The source packages remain untouched.
        (folder / 'sp_improved/zzzzzz_coop_mainline.pk3').unlink(missing_ok=True)
        build(folder / 'sp_improved/sp_improved_1.5.pk3', folder / 'sp_improved/zzzz_codcoop.pk3', 'sp_improved')
        build_trigger_patch(folder, folder / 'sp_improved/zzzzz_codcoop_triggers.pk3', 'sp_improved')
        build_mainline_patch(folder, folder / 'sp_improved/zzzzzz_codcoop_mainline.pk3')
    original = qa_coop.assess_liveness
    entered = False
    report = {'status': 'NOT_RUN', 'timescale': 4,
              'coverage': 'natural original credits completion to Bastogne with a real host and joiner; no Berlin playthrough'}
    capture_root = output / 'credits-captures' / str(time.time_ns())

    def capture_credits(label):
        directory = capture_root / label
        directory.mkdir(parents=True)
        states = [qa_coop.read_state(folder) for folder in folders]
        if any(not state or state.get('map') != 'coop_cod1_credits' for state in states):
            raise RuntimeError('credits screenshot was requested outside the actual credits map')
        (directory / 'states.json').write_text(json.dumps(states, indent=2))
        previous = [set((folder / 'sp_improved/screenshots').glob('*')) for folder in folders]
        for n, folder in enumerate(folders):
            qa_coop.command(folder, 'screenshot', joiner=n != 0)
        paths = []
        for n, folder in enumerate(folders):
            def image_ready():
                new = [p for p in (folder / 'sp_improved/screenshots').glob('*')
                       if p not in previous[n] and p.suffix.lower() in ('.jpg', '.tga', '.png') and p.stat().st_size > 1024]
                if not new:
                    return None
                image = sorted(new, key=lambda p: (p.suffix.lower() != '.jpg', p.name))[0]
                size = image.stat().st_size
                time.sleep(0.15)
                return image if image.stat().st_size == size else None
            source = qa_coop.wait_for(image_ready, [], 15, 'native credits screenshot from ' + folder.name)
            target = directory / (folder.name + source.suffix.lower())
            shutil.copy2(source, target)
            paths.append(str(target.relative_to(output)))
        report.setdefault('credits_captures', []).append({'label': label, 'images': paths})

    def observe(before, after, count):
        nonlocal entered
        original(before, after, count)
        if entered:
            return
        entered = True
        initial = [qa_coop.read_state(folder) for folder in folders]
        if any(s.get('map') != 'coop_cod1_credits' for s in initial) or not initial[1].get('joined'):
            raise RuntimeError('credits alias and real joined peer were not established')
        report['initial_maps'] = [s['map'] for s in initial]
        (output / 'mainline-departure.json').write_text(json.dumps(initial, indent=2))
        started = time.monotonic()
        for n, folder in enumerate(folders):
            qa_coop.command(folder, 'set coop_mainline 1\ntimescale 4', joiner=n != 0)
        deadline = time.monotonic() + args.timeout
        maps = []
        capture_times = [(5, 'early'), (20, 'middle'), (40, 'late')]
        while time.monotonic() < deadline:
            states = [qa_coop.read_state(folder) for folder in folders]
            maps = [s.get('map') if s else None for s in states]
            if capture_times and time.monotonic() - started >= capture_times[0][0] and maps == ['coop_cod1_credits', 'coop_cod1_credits']:
                _, label = capture_times.pop(0)
                capture_credits(label)
            if maps == ['bastogne1', 'bastogne1'] and states[1].get('joined') and states[1].get('compatible'):
                for n, folder in enumerate(folders):
                    qa_coop.command(folder, 'timescale 1', joiner=n != 0)
                report['status'] = 'ARRIVED'
                report['route_status'] = 'PASS'
                report['elapsed_wall_seconds'] = round(time.monotonic() - started, 3)
                report['maps'] = maps
                (output / 'mainline-arrival.json').write_text(json.dumps(states, indent=2))
                # The first new-map snapshot precedes passenger attachment.
                # Require the protagonist to finish the original Jeep intro as
                # well as the remote becoming controllable before measuring input.
                control_deadline = time.monotonic() + args.timeout
                while time.monotonic() < control_deadline:
                    state = qa_coop.read_state(folders[0])
                    if state and all(p.get('pm_type') == 0 and not p.get('linked') for p in state['players'][:2]):
                        report['controllability'] = 'PASS'
                        time.sleep(1)
                        return
                    time.sleep(0.5)
                report['controllability'] = 'TIMEOUT'
                raise RuntimeError('original Bastogne intro did not release host and remote control')
            time.sleep(0.5)
        report['status'] = 'TIMEOUT'
        report['elapsed_wall_seconds'] = round(time.monotonic() - started, 3)
        report['maps'] = maps
        raise RuntimeError('natural credits transition did not reconnect both players to bastogne1')

    qa_coop.assess_liveness = observe
    try:
        result = qa_coop.main(smoke)
        report['status'] = 'PASS' if result == 0 and report.get('controllability') == 'PASS' else 'FAIL'
    finally:
        qa_coop.assess_liveness = original
        report['runtime'] = json.loads((output / 'provenance.json').read_text())['runtime']
        (output / 'mainline-probe.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if result == 0 and report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
