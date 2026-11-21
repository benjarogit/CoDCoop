#!/usr/bin/env python3
"""Real Wine host/joiner smoke tests. A smoke PASS is not a campaign playthrough.

Copies (never hardlinks) the source installation. Owns its X server, Wine prefix,
processes, command files and saves. No global wineserver/Steam manipulation.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
COOP_ANYTHING_REVISION = 'e83fc578ad2c3d3bb30b06f98ba11d965d11e105'


def zpath(path):
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


def read_state(folder):
    try:
        return json.loads((folder / 'qa-state.json').read_text())
    except (OSError, ValueError):
        return None


def command(folder, text, joiner=False):
    path = folder / ('codcoop_join.cmd' if joiner else 'codcoop.cmd')
    deadline = time.monotonic() + 5
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    if path.exists():
        raise RuntimeError('command queue did not drain: ' + str(folder))
    temp = path.with_suffix('.pending')
    temp.write_text(text + '\n', encoding='ascii')
    temp.replace(path)


def wait_for(predicate, processes, timeout, description):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError('game exited during ' + description + ' (exit ' + str(process.returncode) + ')')
        result = predicate()
        if result:
            return result
        time.sleep(0.25)
    raise TimeoutError(description)


def assess_liveness(before, after, count):
    """Do not mistake a reserved slot / frozen / crashed client for a live one."""
    if before['role'] != 1 or after['role'] != 1:
        raise ValueError('not a real host')
    for slot in range(1, count):
        a, b = before['players'][slot], after['players'][slot]
        if not b['active'] or b['state'] != 1 or b['command_time'] <= a['command_time']:
            raise ValueError('joiner %d is not advancing real user commands' % slot)
    if after['server_time'] <= before['server_time']:
        raise ValueError('host simulation is frozen')


def move_remote(host, peer, slot, processes, timeout, action='+forward'):
    """Require native player movement, including after a checkpoint reconnect."""
    wait_for(lambda: (p := read_state(host)['players'][slot]) and p.get('pm_type') == 0 and not p.get('linked'),
             processes, timeout, 'remote player controllable outside a vehicle/cinematic')
    before = read_state(host)['players'][slot]
    origin, clock = before['position'], before['command_time']
    command(peer, action, joiner=True)
    try:
        def moved():
            current = read_state(host)['players'][slot]
            direction = current.get('forward', 0)
            acknowledged = (action != '+forward' or direction > 0) and (action != '+back' or direction < 0)
            return acknowledged and current['command_time'] > clock and math.dist(origin, current['position']) > 5
        wait_for(moved, processes, 10, 'host applies remote movement input')
        time.sleep(0.8)
    finally:
        command(peer, '-' + action[1:], joiner=True)
    distance = math.dist(origin, read_state(host)['players'][slot]['position'])
    if distance < 5:
        raise RuntimeError('remote %d did not move via real input: %.2f' % (slot, distance))
    return distance


def process_log_errors(folder):
    errors = []
    paths = list(folder.glob('codcoop*.log'))
    paths += [folder / root / 'console.log' for root in ('Main', 'main', 'uo', 'sp_improved', 'UnitedFronts')
              if (folder / root / 'console.log').exists()]
    for path in paths:
        for line in path.read_text(errors='replace').splitlines():
            if ('CRASH ' in line or 'MT_AllocIndex: failed' in line or
                    'script runtime error' in line.lower() or 'Server time went backwards' in line or
                    line.strip().startswith('ERROR:')):
                errors.append(line)
    return errors


def archive_previous(output):
    """Retain failed and successful evidence before reusing owned game copies."""
    if not (output / 'result.json').exists():
        return
    archive = output / 'history' / str(time.time_ns())
    archive.mkdir(parents=True)
    for path in list(output.iterdir()):
        if path.is_file() and path.suffix.lower() in ('.json', '.jsonl', '.log', '.png'):
            path.rename(archive / path.name)
    if (output / 'runtime').exists():
        (output / 'runtime').rename(archive / 'runtime')
    for game in (output / 'host', *(output / ('join%d' % n) for n in range(1, 4))):
        if not game.is_dir(): continue
        paths = list(game.glob('codcoop*.log')) + list(game.glob('*/console.log'))
        for path in paths:
            target = archive / game.name / path.relative_to(game)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path, help='new or reusable isolated output directory')
    parser.add_argument('--runtime-dir', type=Path, help='immutable DLL snapshot; defaults to the current build directory')
    parser.add_argument('--variant', choices=('cod1', 'uo', 'sp_improved', 'united_fronts'), default='cod1')
    parser.add_argument('--map', default='training')
    parser.add_argument('--players', type=int, choices=(2, 4), default=2)
    parser.add_argument('--initial-expected-players', type=int, choices=range(1, 5),
                        help='launcher party estimate before real players join; defaults to --players')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--duration', type=int, default=12)
    parser.add_argument('--port', type=int, default=29860)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--host-delay', type=int, default=0, help='start a joiner first and wait this many real seconds before the host')
    parser.add_argument('--checkpoint-reloads', type=int, choices=range(0, 6), default=0,
                        help='save and reload a real host checkpoint this many times (0..5)')
    parser.add_argument('--chaos-checkout', type=Path, help='Co-op Anything checkout at the pinned revision; enables its UDP relay')
    parser.add_argument('--chaos-profile', choices=('lan', 'good_wifi', 'bad_wifi', 'mobile_tether', 'transatlantic', 'hell'), default='bad_wifi')
    parser.add_argument('--chaos-seed', type=int, default=260621)
    args = parser.parse_args(argv)
    runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    chaos_script = None
    if args.chaos_checkout:
        checkout = args.chaos_checkout.resolve()
        revision = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != COOP_ANYTHING_REVISION:
            parser.error('Co-op Anything revision mismatch; expected ' + COOP_ANYTHING_REVISION)
        if subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True).strip():
            parser.error('Co-op Anything checkout has unreviewed local changes')
        chaos_script = checkout / 'tools/chaos/chaos.py'
    source, output = args.source.resolve(), args.run.resolve()
    runtime_source = (args.runtime_dir or ROOT / 'build').resolve()
    if runtime_source == output / 'runtime' or runtime_source.is_relative_to(output / 'runtime'):
        parser.error('runtime input must be separate from the output snapshot that is archived on retry')
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        parser.error('test output must be separate from the source installation')
    output.mkdir(parents=True, exist_ok=True)
    marker = output / '.codcoop-qa-owned'
    if any(output.iterdir()) and not marker.exists():
        parser.error('refusing an existing unowned test directory')
    marker.write_text('isolated CoDCoop QA\n')
    archive_previous(output)
    for previous in ('result.json', 'before.json', 'after.json'):
        (output / previous).unlink(missing_ok=True)
    runtime = output / 'runtime'
    runtime.mkdir(exist_ok=True)
    for module in ('ddraw.dll', 'codcoop_core.dll'):
        shutil.copy2(runtime_source / module, runtime / module)
    folders = []
    for n in range(args.players):
        folder = output / ('host' if n == 0 else 'join%d' % n)
        if not folder.exists():
            folder.mkdir()
            subprocess.run(['cp', '-a', '--reflink=auto', str(source) + '/.', str(folder)], check=True)
        for module in ('ddraw.dll', 'codcoop_core.dll'):
            shutil.copy2(runtime / module, folder / module)
        for root in ('Main', 'main', 'uo', 'sp_improved', 'UnitedFronts'):
            for config in ('config.cfg', 'config_mp.cfg', 'uoconfig.cfg', 'console.log'):
                (folder / root / config).unlink(missing_ok=True)
        for pattern in ('__CoD*', 'codcoop*.cmd', 'codcoop*.log', 'qa-state.*'):
            for old in folder.glob(pattern):
                if old.is_file(): old.unlink()
        folders.append(folder)
    provenance = {'source': str(source), 'variant': args.variant, 'map': args.map, 'players': args.players,
                  'runner_sha256': runner_hash,
                  'runtime_source': str(runtime_source),
                  'host_delay_seconds': args.host_delay, 'checkpoint_reloads': args.checkpoint_reloads,
                  'initial_expected_players': args.initial_expected_players or args.players,
                  'runtime': {p: hashlib.sha256((runtime / p).read_bytes()).hexdigest() for p in ('ddraw.dll', 'codcoop_core.dll')},
                  'coverage': 'connection/liveness/movement smoke only; no campaign completion claim'}
    if chaos_script:
        provenance['network'] = {'tool': 'coop-anything/chaos', 'revision': COOP_ANYTHING_REVISION,
                                 'profile': args.chaos_profile, 'seed': args.chaos_seed}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    if args.prepare_only:
        return 0
    processes = []
    handles = []
    display_process = None
    relay_process = None
    env = os.environ.copy()
    env.update(WINEPREFIX=str(output / 'prefix'), WINEDEBUG='-all', CODCOOP_QA='1', CODCOOP_QA_NO_STEAM='1',
               WINEDLLOVERRIDES='ddraw=n,b;mscoree=;mshtml=', LIBGL_ALWAYS_SOFTWARE='1',
               MESA_EXTENSION_MAX_YEAR='2003', __GL_ExtensionStringVersion='15000')
    results = {'status': 'FAIL', **provenance, 'checks': []}
    try:
        if args.variant != 'cod1':
            for folder in folders:
                if not (folder / 'plugins/yap/DDRAW.dll').is_file():
                    raise RuntimeError('incomplete UO QA source: missing plugins/yap/DDRAW.dll in ' + str(folder))
        join_port = args.port
        if chaos_script:
            info_file = output / 'chaos-info.json'
            info_file.unlink(missing_ok=True)
            relay_log = open(output / 'chaos-process.log', 'wb'); handles.append(relay_log)
            relay_process = subprocess.Popen([sys.executable, '-I', str(chaos_script), 'relay',
                '--target', '127.0.0.1:' + str(args.port), '--profile', args.chaos_profile,
                '--seed', str(args.chaos_seed), '--log', str(output / 'chaos.jsonl'),
                '--info-file', str(info_file)], stdout=relay_log, stderr=relay_log)
            def relay_ready():
                try: return json.loads(info_file.read_text())
                except (OSError, ValueError): return None
            join_port = wait_for(relay_ready, [relay_process], 15, 'Co-op Anything UDP relay')['listen']
        # Ask Xvfb for a free display instead of stealing a fixed display number.
        read_fd, write_fd = os.pipe()
        log = open(output / 'xvfb.log', 'wb'); handles.append(log)
        display_process = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '1600x1000x24', '-nolisten', 'tcp'], pass_fds=(write_fd,), stdout=log, stderr=log)
        os.close(write_fd)
        if not select.select([read_fd], [], [], 10)[0]:
            raise RuntimeError('Xvfb did not allocate a display')
        display = os.read(read_fd, 64).decode().strip(); os.close(read_fd)
        env['DISPLAY'] = ':' + display
        boot_log = open(output / 'wineboot.log', 'wb'); handles.append(boot_log)
        prefix_ready = output / 'prefix/.codcoop-qa-prefix-ready'
        if not prefix_ready.exists():
            subprocess.run(['wineboot', '--init'], env=env, stdout=boot_log, stderr=boot_log, check=True, timeout=max(90, args.timeout))
            prefix_ready.write_text('wineboot --init completed successfully\n')
        exe = 'CoDSP.exe' if args.variant == 'cod1' else 'CoDUOSP.exe'
        fs_game = {'cod1': '', 'uo': '', 'sp_improved': 'sp_improved', 'united_fronts': 'UnitedFronts'}[args.variant]
        order = [1, 0] if args.host_delay and args.players == 2 else list(range(args.players))
        for n in order:
            folder = folders[n]
            if args.host_delay and n == 0:
                time.sleep(args.host_delay)
            log = open(output / ('process%d.log' % n), 'wb'); handles.append(log)
            root = zpath(folder)
            cmd = ['wine', str(folder / exe), '+set', 'fs_basepath', root, '+set', 'fs_homepath', root,
                   '+set', 'fs_cdpath', root, '+set', 'fs_game', fs_game, '+set', 'r_fullscreen', '0',
                   '+set', 'coop_mainline', '1' if args.variant == 'sp_improved' else '0',
                   '+set', 'coop_expected_players', str(args.initial_expected_players or args.players),
                   '+set', 'r_mode', '-1', '+set', 'r_customwidth', '640', '+set', 'r_customheight', '480',
                   '+set', 'r_mode_auto', '0', '+set', 'com_introplayed', '1', '+set', 'logfile', '2',
                   '+set', 'com_hunkmegs', '512' if args.variant == 'united_fronts' else '256',
                   '+set', 'sv_cheats', '1', '+devmap', args.map]
            cmd += ['+coophost', str(args.port)] if n == 0 else ['+coopjoin', '127.0.0.1:' + str(join_port)]
            processes.append(subprocess.Popen(cmd, env=env, cwd=folder, stdout=log, stderr=log))
            wait_for(lambda: read_state(folder), processes, args.timeout, 'core initialization for slot %d' % n)
            # Engine UI calls, no desktop mouse injection and no direct world-state teleport.
            command(folder, 'coopuiclick 320 240\ncoopqastart', joiner=n != 0)
        def connected():
            states = [read_state(f) for f in folders]
            if not all(states): return None
            host = states[0]
            if host['role'] != 1 or not all(p['active'] and p['state'] == 1 for p in host['players'][1:args.players]): return None
            if not all(s['joined'] and s['compatible'] and s['role'] == 2 and
                       s['snapshot_num'] > 0 and s['snapshot_time'] > 0 and
                       s['map'] == host['map'] for s in states[1:]): return None
            return states
        states = wait_for(connected, processes, args.timeout, 'real host and all joiners connected')
        results['checks'].append('real connected host and joiners')
        before = states[0]
        time.sleep(2)
        assess_liveness(before, connected()[0], args.players)
        results['checks'].append('host and every remote user-command clock advance')
        (output / 'before.json').write_text(json.dumps(states, indent=2))
        for n, folder in enumerate(folders[1:], 1):
            slot = states[n]['slot']
            if slot < 1 or slot >= args.players: raise RuntimeError('invalid joiner slot')
            distance = move_remote(folders[0], folder, slot, processes, args.timeout)
            results['checks'].append('remote %d moved %.1f units via player input' % (slot, distance))
        for iteration in range(args.checkpoint_reloads):
            # Use the actual native save/load commands, including remote player
            # records. Loading a fresh map is not a checkpoint roundtrip.
            save_root = 'Main' if args.variant == 'cod1' else (fs_game or 'uo')
            save = folders[0] / save_root / 'save/coop_qa_checkpoint.svg'
            save.unlink(missing_ok=True)
            command(folders[0], 'savegame coop_qa_checkpoint')
            wait_for(lambda: save.exists() and save.stat().st_size > 1024, processes,
                     args.timeout, 'native host checkpoint written')
            saved_time = read_state(folders[0])['server_time']
            wait_for(lambda: read_state(folders[0])['server_time'] > saved_time + 5000,
                     processes, args.timeout, 'world advances beyond saved checkpoint')
            old_time = read_state(folders[0])['server_time']
            command(folders[0], 'loadgame coop_qa_checkpoint')
            wait_for(lambda: read_state(folders[0])['server_time'] < old_time - 1000,
                     processes, args.timeout, 'native checkpoint restores earlier world time')
            def checkpoint_connected():
                for folder in folders:
                    errors = process_log_errors(folder)
                    if errors: raise RuntimeError('checkpoint engine error: ' + errors[0])
                return connected()
            states = wait_for(checkpoint_connected, processes, args.timeout, 'all players rejoin restored checkpoint')
            baseline_reload = states[0]
            time.sleep(2)
            recovered = checkpoint_connected()
            if not recovered:
                raise RuntimeError('remote disconnected during checkpoint recovery')
            assess_liveness(baseline_reload, recovered[0], args.players)
            if not all(s['snapshot_num'] > 0 and s['snapshot_time'] > 0 for s in recovered[1:]):
                raise RuntimeError('checkpoint joiner has no actual rendered snapshots')
            results['checks'].append('native checkpoint reload %d restored world and all remote command clocks' % (iteration + 1))
            for peer_number, folder in enumerate(folders[1:]):
                slot = read_state(folder)['slot']
                # Separate the actual players after native respawn as well as
                # checking input: overlapping bodies would obstruct screenshots.
                action = ('+forward', '+back', '+moveleft')[peer_number]
                distance = move_remote(folders[0], folder, slot, processes, args.timeout, action)
                results['checks'].append('checkpoint %d remote %d moved %.1f units via %s' %
                                        (iteration + 1, slot, distance, action))
        # Unallocated endpoints must not be able to inject engine snapshots.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b'\x01\x00\x00\x00' + b'fake engine packet', ('127.0.0.1', args.port))
        baseline = read_state(folders[0])
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            if relay_process and relay_process.poll() is not None:
                raise RuntimeError('network impairment relay exited during observation')
            for process in processes:
                if process.poll() is not None: raise RuntimeError('game exited during observation')
            time.sleep(0.5)
        final = connected()
        if not final: raise RuntimeError('a joiner was lost during observation')
        assess_liveness(baseline, final[0], args.players)
        for folder in folders:
            if process_log_errors(folder): raise RuntimeError(str(process_log_errors(folder)))
        (output / 'after.json').write_text(json.dumps(final, indent=2))
        results['checks'].append('stable observation with unallocated packet rejected')
        for n, folder in enumerate(folders):
            command(folder, 'screenshot', joiner=n != 0)
        time.sleep(1)
        # A clean exit is part of the test, rather than hiding shutdown crashes.
        for n, folder in enumerate(reversed(folders)):
            command(folder, 'quit', joiner=folder != folders[0])
        for process in processes:
            if process.wait(timeout=20) != 0: raise RuntimeError('nonzero game shutdown')
        results['checks'].append('all game processes shut down cleanly')
        results['status'] = 'PASS'
    except KeyboardInterrupt:
        results['status'] = 'ABORTED'
        results['error'] = 'test interrupted; no successful gameplay result'
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        results['error'] = str(error)
    finally:
        if relay_process and relay_process.poll() is None:
            relay_process.terminate()
            relay_process.wait(timeout=5)
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
        # Prefix is owned exclusively by this harness; never kill the user's server.
        subprocess.run(['wineserver', '-k'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            subprocess.run(['wineserver', '-w'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        if display_process is not None:
            display_process.terminate(); display_process.wait(timeout=5)
        for handle in handles: handle.close()
        (output / 'result.json').write_text(json.dumps(results, indent=2))
    print('RESULT: ' + results['status'])
    if 'error' in results: print(results['error'])
    return 0 if results['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
