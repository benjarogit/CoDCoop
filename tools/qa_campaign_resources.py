#!/usr/bin/env python3
"""Bounded native UF map-loading/model-budget gate; never a campaign completion.

Uses an existing qa_coop-owned host copy, no full game copy. --rank-only scans
BSP entity metadata to prioritize maps; static counts are not runtime budgets.
"""
import argparse
import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import struct
import subprocess
import time
import zipfile

import qa_coop
from build_campaign_patch import quarantine_obsolete_qa_trigger_overlays, build, build_trigger_patch

ROOT = Path(__file__).resolve().parents[1]


def entity_models(data):
    if data[:4] != b'IBSP' or struct.unpack_from('<I', data, 4)[0] != 59:
        raise ValueError('unreviewed BSP entity layout')
    size, offset = struct.unpack_from('<II', data, 8+29*8)
    if not size or offset+size > len(data):
        raise ValueError('invalid BSP entity lump')
    entities = data[offset:offset+size]
    return sorted({s.decode('latin1') for s in re.findall(rb'"model"\s+"(xmodel/[^"\r\n]+)"', entities)})


def rank_maps(game, inventory):
    rows = []
    archives = {}
    try:
        for mission in inventory['profiles']['united_fronts']['maps']:
            package = mission['bsp_package']
            if package not in archives:
                archives[package] = zipfile.ZipFile(game/package)
            archive = archives[package]
            names = {name.lower(): name for name in archive.namelist()}
            member = names['maps/'+mission['id'].lower()+'.bsp']
            models = entity_models(archive.read(member))
            rows.append({'map': mission['id'], 'package': package,
                         'static_entity_model_count': len(models), 'static_entity_models': models,
                         'runtime_status': 'NOT_RUN', 'campaign_completion': False})
    finally:
        for archive in archives.values(): archive.close()
    return sorted(rows, key=lambda row: (-row['static_entity_model_count'], row['map']))


def read_errors(console):
    if not console.exists(): return None
    text = console.read_text(errors='replace')
    matches = list(re.finditer(r'^.*(?:ERROR:|script compile error|script runtime error).*$', text, re.M))
    return text[max(0, matches[0].start()-150):matches[0].end()+450] if matches else None


def summarize_references(value):
    if not value.get('references_complete') or not value.get('reference_layout_valid'):
        raise ValueError('Incomplete or invalid native model-reference snapshot')
    references = {entry['index'] for entry in value['model_references']}
    for dobj in value['live_dobjs']:
        references.update(-flag for flag in dobj['raw_model_flags'] if flag < 0)
    if any(index < 1 or index > 255 for index in references):
        raise ValueError('Native reference outside byte model-index range')
    catalog = {entry['index']: entry['name'] for entry in value['models']}
    if not references <= catalog.keys(): raise ValueError('Referenced model missing from native CS table')
    return {'referenced_count': len(references), 'referenced_ids': sorted(references),
            'referenced_names': [catalog[index] for index in sorted(references)],
            'unreferenced_at_sample': [entry for entry in value['models'] if entry['index'] not in references],
            'scope': 'current live entity body/attachments, active player viewmodel, live server/client DObjs; not future-safe reclaimable slots'}


def observe_models(helper, game, env, references=False):
    result = subprocess.run(['wine', str(helper), str(game).replace('/', '\\'), '0', '--model-references' if references else '--models'],
                            env=env, capture_output=True, text=True, timeout=15, check=True)
    value = json.loads(result.stdout.strip())
    if value.get('clientnum') != 0 or not value.get('models'):
        raise RuntimeError('read-only native model-table observation invalid')
    if references: value['reference_summary'] = summarize_references(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True, help='existing qa_coop-owned host copy, never live installation')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path)
    parser.add_argument('--inventory', type=Path, default=ROOT/'content/campaign-inventory.json')
    parser.add_argument('--maps', nargs='+')
    parser.add_argument('--limit', type=int, default=8, help='highest static-model-count maps to load; 0 means all')
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--hunk', type=int, default=512)
    parser.add_argument('--port', type=int, default=29934)
    parser.add_argument('--baseline-scripts', action='store_true',
                        help='compare original installed UF scripts; temporarily move only the two generated Coop overlays')
    parser.add_argument('--world-policy', choices=('universal', 'selected'), default='universal')
    parser.add_argument('--set', dest='cvars', action='append', default=[], metavar='NAME=VALUE',
                        help='normal original-mod launch setting, recorded per run')
    parser.add_argument('--rank-only', action='store_true')
    parser.add_argument('--model-references', action='store_true', help='three read-only live reference samples after registration; not an allocator/reclamation proof')
    args = parser.parse_args()
    game, output = args.game.resolve(), args.output.resolve()
    if not (game.parent/'.codcoop-qa-owned').is_file():
        parser.error('game must be an existing isolated qa_coop-owned copy')
    if args.limit < 0 or args.timeout <= 0:
        parser.error('invalid limit/timeout')
    output.mkdir(parents=True, exist_ok=True)
    if (output/'report.json').exists():
        parser.error('choose a fresh output directory to preserve prior evidence')
    cvars = []
    for pair in args.cvars:
        name, separator, value = pair.partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or any(c in value for c in '\r\n;'):
            parser.error('invalid launch setting')
        cvars += ['+set', name, value]
    inventory = json.loads(args.inventory.read_text())
    rows = rank_maps(game, inventory)
    report = {'coverage': 'BSP metadata ranking plus native resource loading/model-budget gate only; no mission completion',
              'static_count_limit': 'entity model references exclude character aliases and runtime script precaches',
              'game': str(game), 'world_policy': args.world_policy, 'launch_settings': args.cvars, 'overlay_mode': 'original-UF-scripts' if args.baseline_scripts else 'production-Coop-overlay', 'hunk_megabytes': args.hunk, 'maps': rows}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Highest static BSP model counts:', [(row['map'], row['static_entity_model_count']) for row in rows[:12]], flush=True)
    if args.rank_only: return 0
    if not args.runtime_dir:
        parser.error('--runtime-dir is required for native gates')
    # Refuse to alter a copy already running in any Wine prefix.
    for process in Path('/proc').iterdir():
        if not process.name.isdigit(): continue
        try: command = (process/'cmdline').read_bytes().replace(b'\\', b'/').lower()
        except (OSError, PermissionError): continue
        if str(game/'CoDUOSP.exe').lower().encode() in command:
            parser.error('owned game copy is already in use')
    selected = rows if not args.limit else rows[:args.limit]
    if args.maps:
        wanted = set(args.maps)
        if not wanted <= {row['map'] for row in rows}: parser.error('map not in pinned inventory')
        selected = [row for row in rows if row['map'] in wanted]
    qa_coop.archive_previous(game.parent)
    snapshot = output/'runtime'; snapshot.mkdir()
    shutil.copy2(Path(__file__), output/Path(__file__).name)
    for name in ('CoDUOSP.exe', 'uo_gamex86.dll'):
        report.setdefault('native_input_sha256', {})[name] = hashlib.sha256((game/name).read_bytes()).hexdigest()
    report['runtime'] = {}
    for name in ('ddraw.dll', 'codcoop_core.dll'):
        shutil.copy2(args.runtime_dir.resolve()/name, snapshot/name)
        shutil.copy2(snapshot/name, game/name)
        report['runtime'][name] = hashlib.sha256((snapshot/name).read_bytes()).hexdigest()
    build(game/'UnitedFronts/ZUnitedFronts_1.1_beta.pk3', game/'UnitedFronts/zzzz_coop_campaign.pk3', 'united_fronts', qa=False, world_policy=args.world_policy)
    quarantine_obsolete_qa_trigger_overlays(game)
    build_trigger_patch(game, game/'UnitedFronts/zzzz_coop_triggers.pk3', 'united_fronts')
    for name in ('zzzz_coop_campaign.pk3', 'zzzz_coop_triggers.pk3'):
        shutil.copy2(game/'UnitedFronts'/name, output/name)
    if args.baseline_scripts:
        disabled = []
        for name in ('zzzz_coop_campaign.pk3', 'zzzz_coop_triggers.pk3'):
            source, destination = game/'UnitedFronts'/name, output/('disabled-'+name)
            source.replace(destination); disabled.append((source, destination))
        def restore_overlays():
            for source, destination in disabled:
                if destination.exists(): shutil.copy2(destination, source)
        atexit.register(restore_overlays)
    helper = output/'qa-uf-player-state.exe'
    subprocess.run(['i686-w64-mingw32-g++', str(ROOT/'campaign_patches/qa_uf_player_state.cpp'),
                    '-o', str(helper), '-static', '-O2', '-std=c++17'], check=True)
    shutil.copy2(ROOT/'campaign_patches/qa_uf_player_state.cpp', output/'qa_uf_player_state.cpp')
    env = dict(os.environ, WINEPREFIX=str(game.parent/'prefix'), WINEDEBUG='-all', CODCOOP_QA='1', CODCOOP_QA_NO_STEAM='1',
               WINEDLLOVERRIDES='ddraw=n,b;mscoree=;mshtml=', LIBGL_ALWAYS_SOFTWARE='1',
               MESA_EXTENSION_MAX_YEAR='2003', __GL_ExtensionStringVersion='15000')
    readfd, writefd = os.pipe()
    with open(output/'xvfb.log', 'wb') as display_log:
        display = subprocess.Popen(['Xvfb', '-displayfd', str(writefd), '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                   pass_fds=(writefd,), stdout=display_log, stderr=display_log)
        os.close(writefd)
        try:
            if not select.select([readfd], [], [], 10)[0]: raise RuntimeError('Xvfb did not allocate display')
            env['DISPLAY'] = ':'+os.read(readfd, 64).decode().strip(); os.close(readfd)
            for row in selected:
                case = output/row['map']; case.mkdir()
                console = game/'UnitedFronts/console.log'
                for old in (console, game/'qa-state.json', game/'codcoop.log', game/'codcoop.cmd', game/'UnitedFronts/uoconfig.cfg'):
                    old.unlink(missing_ok=True)
                root = qa_coop.zpath(game)
                command = ['wine', str(game/'CoDUOSP.exe'), '+set', 'fs_basepath', root, '+set', 'fs_homepath', root,
                           '+set', 'fs_cdpath', root, '+set', 'fs_game', 'UnitedFronts', '+set', 'r_fullscreen', '0',
                           '+set', 'r_mode', '-1', '+set', 'r_customwidth', '640', '+set', 'r_customheight', '480',
                           '+set', 'r_mode_auto', '0', '+set', 'com_introplayed', '1', '+set', 'logfile', '2',
                           '+set', 'coop_mainline', '0', '+set', 'coop_expected_players', '1',
                           '+set', 'com_hunkmegs', str(args.hunk), '+set', 'sv_cheats', '1',
                           ] + cvars + ['+devmap', row['map'], '+coophost', str(args.port)]
                started = time.monotonic(); ready_since = None; pressed = False
                with open(case/'process.log', 'wb') as process_log:
                    process = subprocess.Popen(command, env=env, cwd=game, stdout=process_log, stderr=process_log)
                    try:
                        while time.monotonic()-started < args.timeout:
                            error = read_errors(console)
                            if error:
                                row.update(runtime_status='FAIL_ENGINE_ERROR', error=error); break
                            state = qa_coop.read_state(game)
                            if state and state.get('role') == 1 and state.get('map') == row['map'] and state.get('cls_state') == 2 and state.get('snapshot_num', 0) > 0:
                                if not pressed:
                                    qa_coop.command(game, 'coopuiclick 320 240\ncoopqastart'); pressed = True
                                if ready_since is None: ready_since = time.monotonic()
                                if time.monotonic()-ready_since >= 2:
                                    models = observe_models(helper, game, env, args.model_references)
                                    count = len(models['models'])
                                    row.update(runtime_status='PASS_RESOURCE_LOAD', model_count=count, remaining_slots=255-count,
                                               budget_risk='HIGH' if count >= 248 else 'NORMAL', server_time=state.get('server_time'))
                                    (case/'model-table.json').write_text(json.dumps(models, indent=2)+'\n')
                                    (case/'qa-state.json').write_text(json.dumps(state, indent=2)+'\n')
                                    if args.model_references:
                                        samples = [models]
                                        row['reference_phase'] = 'early-live-after-native-registration; no end-registration hook'
                                        for number in (1, 2):
                                            time.sleep(3)
                                            error = read_errors(console)
                                            if error: raise RuntimeError(error)
                                            sample = observe_models(helper, game, env, True)
                                            samples.append(sample)
                                            (case/('model-references-%d.json' % number)).write_text(json.dumps(sample, indent=2)+'\n')
                                        seen = sorted({index for sample in samples for index in sample['reference_summary']['referenced_ids']})
                                        row['sample_referenced_counts'] = [sample['reference_summary']['referenced_count'] for sample in samples]
                                        row['early_live_referenced_union'] = seen
                                        row['early_live_unreferenced_count'] = count-len(seen)
                                    break
                            time.sleep(.1)
                        else: row.update(runtime_status='FAIL_TIMEOUT')
                    except Exception as error:
                        row.update(runtime_status='FAIL_OBSERVER', error=str(error))
                    finally:
                        try:
                            qa_coop.command(game, 'quit'); process.wait(timeout=8)
                        except (OSError, RuntimeError, subprocess.TimeoutExpired):
                            row['forced_cleanup'] = True
                        subprocess.run(['wineserver', '-k'], env=env, timeout=15, check=False)
                        if process.poll() is None: process.terminate(); process.wait(timeout=10)
                        row['wall_seconds'] = round(time.monotonic()-started, 3)
                        for source in (console, game/'codcoop.log'):
                            if source.exists(): shutil.copy2(source, case/source.name)
                        if console.exists():
                            row['nonfatal_diagnostics'] = re.findall(r'^.*\^1Error:.*$', console.read_text(errors='replace'), re.M)
                report['selected_count'] = len(selected)
                (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
                print(row['map'], row['runtime_status'], row.get('model_count'), flush=True)
        finally:
            display.terminate(); display.wait(timeout=10)
    return 0 if all(row['runtime_status'] == 'PASS_RESOURCE_LOAD' for row in selected) else 1


if __name__ == '__main__': raise SystemExit(main())
