#!/usr/bin/env python3
"""Native Windows host/joiner smoke. A smoke PASS is not a campaign playthrough.

Runs on Windows itself (no Wine, no X server). It copies the installed game
folder per player, launches the real CoDSP.exe/CoDUOSP.exe, and reuses the
proven liveness/movement/log predicates from qa_coop.py. A PASS only claims a
real connection, advancing remote command clocks, native player movement and a
clean shutdown; it makes no campaign completion claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import qa_coop
from qa_coop import (assess_liveness, command, move_remote, process_log_errors,
                     read_state, wait_for, wait_liveness)

ROBOCOPY_OK = range(8)

# Mesa WGL modules copied into the per-player QA copies. Only the two core
# modules are mandatory; the DXIL compiler pair is needed by the d3d12 driver
# and is copied when the given Mesa directory ships it.
MESA_MODULES = ('opengl32.dll', 'libgallium_wgl.dll', 'dxil.dll', 'spirv_to_dxil.dll')


def copytree(source, destination):
    """Copy an installed game folder without hardlinks (robocopy is native)."""
    if destination.is_dir() and any(destination.iterdir()):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ['robocopy', str(source), str(destination), '/E', '/COPY:DAT', '/DCOPY:DAT',
         '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP'],
        capture_output=True, text=True)
    if result.returncode not in ROBOCOPY_OK:
        raise RuntimeError('robocopy failed (%d): %s' % (result.returncode, result.stdout[-2000:]))


def prepare_folders(source, output, players, runtime_dir=None, mesa_dir=None, steam_api=None):
    folders = []
    for n in range(players):
        folder = output / ('host' if n == 0 else 'join%d' % n)
        copytree(source, folder)
        if runtime_dir is not None:
            for module in ('ddraw.dll', 'codcoop_core.dll'):
                shutil.copy2(runtime_dir / module, folder / module)
        if steam_api is not None:
            shutil.copy2(steam_api, folder / 'steam_api.dll')
        if mesa_dir is not None:
            # id Tech 3 needs a real OpenGL 1.4+ driver; the VM has no GPU, so
            # the smoke uses Mesa in the player copies only. The installed
            # acceptance folder stays byte-identical to the suite. The d3d12
            # WGL driver additionally needs the DXIL shader compiler next to
            # libgallium_wgl.dll, so those modules are copied when present.
            for module in MESA_MODULES:
                candidate = mesa_dir / module
                if candidate.is_file():
                    shutil.copy2(candidate, folder / module)
        for root in ('Main', 'main', 'uo', 'sp_improved', 'UnitedFronts'):
            for config in ('config.cfg', 'config_mp.cfg', 'uoconfig.cfg', 'console.log'):
                (folder / root / config).unlink(missing_ok=True)
        for pattern in ('__CoD*', 'codcoop*.cmd', 'codcoop*.log', 'qa-state.*'):
            for old in folder.glob(pattern):
                if old.is_file():
                    old.unlink()
        folders.append(folder)
    return folders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='installed game folder (already coop-patched)')
    parser.add_argument('--run', required=True, type=Path, help='owned output directory')
    parser.add_argument('--players', type=int, choices=(2, 4), default=2)
    parser.add_argument('--map', default='training')
    parser.add_argument('--variant', choices=('cod1', 'uo', 'sp_improved', 'united_fronts'), default='cod1')
    parser.add_argument('--duration', type=int, default=12, help='stable observation seconds')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--port', type=int, default=29860)
    parser.add_argument('--host-god', action='store_true',
                        help='pin the host with coopgod while peers load; liveness only')
    parser.add_argument('--runtime-dir', type=Path, help='optional DLL snapshot copied over every folder')
    parser.add_argument('--mesa-dir', type=Path, help='optional Mesa x86 opengl32.dll/libgallium_wgl.dll for GPU-less hosts')
    parser.add_argument('--steam-api', type=Path,
                        help='stand-in steam_api.dll copied into every player folder; joiners use '
                             '+coopjoin steam:<id> instead of 127.0.0.1')
    parser.add_argument('--steam-host-id', type=int, default=76561190000000001,
                        help='fake SteamID64 of the host with --steam-api; joiners get the next IDs')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    if args.steam_api is not None and not args.steam_api.is_file():
        parser.error('--steam-api is not a file: ' + str(args.steam_api))

    source, output = args.source.resolve(), args.run.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        parser.error('test output must be separate from the source installation')
    output.mkdir(parents=True, exist_ok=True)
    marker = output / '.codcoop-qa-owned'
    if any(output.iterdir()) and not marker.exists():
        parser.error('refusing an existing unowned test directory')
    marker.write_text('isolated CoDCoop native Windows QA\n')

    provenance = {
        'platform': 'native-windows',
        'network_scope': 'same-host',
        'source': str(source), 'variant': args.variant, 'map': args.map, 'players': args.players,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'coverage': 'native Windows connection/liveness/movement smoke only; no campaign completion claim',
    }
    if args.runtime_dir is not None:
        provenance['runtime'] = {p: hashlib.sha256((args.runtime_dir / p).read_bytes()).hexdigest()
                                 for p in ('ddraw.dll', 'codcoop_core.dll')}
    if args.mesa_dir is not None:
        provenance['mesa'] = {p: hashlib.sha256((args.mesa_dir / p).read_bytes()).hexdigest()
                              for p in MESA_MODULES if (args.mesa_dir / p).is_file()}
    if args.steam_api is not None:
        provenance['transport'] = 'steam-fake'
        provenance['steam_api'] = hashlib.sha256(args.steam_api.read_bytes()).hexdigest()
        provenance['steam_host_id'] = args.steam_host_id
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2))

    folders = prepare_folders(source, output, args.players, args.runtime_dir, args.mesa_dir, args.steam_api)
    if args.prepare_only:
        return 0

    processes, handles = [], []
    env = os.environ.copy()
    env.update(CODCOOP_QA='1')
    if not args.steam_api:
        env['CODCOOP_QA_NO_STEAM'] = '1'
    results = {'status': 'FAIL', **provenance, 'checks': []}
    try:
        exe = 'CoDSP.exe' if args.variant == 'cod1' else 'CoDUOSP.exe'
        fs_game = {'cod1': '', 'uo': '', 'sp_improved': 'sp_improved',
                   'united_fronts': 'UnitedFronts'}[args.variant]
        for n, folder in enumerate(folders):
            log = open(output / ('process%d.log' % n), 'wb')
            handles.append(log)
            cmd = [str(folder / exe), '+set', 'fs_basepath', str(folder),
                   '+set', 'fs_homepath', str(folder), '+set', 'fs_cdpath', str(folder),
                   '+set', 'fs_game', fs_game, '+set', 'r_fullscreen', '0',
                   '+set', 'coop_mainline', '1' if args.variant == 'sp_improved' else '0',
                   '+set', 'coop_expected_players', str(args.players),
                   '+set', 'r_mode', '-1', '+set', 'r_customwidth', '640',
                   '+set', 'r_customheight', '480', '+set', 'r_mode_auto', '0',
                   '+set', 'com_introplayed', '1', '+set', 'logfile', '2',
                   '+set', 'com_hunkmegs', '512' if args.variant == 'united_fronts' else '256',
                   '+set', 'sv_cheats', '1', '+devmap', args.map]
            if n == 0:
                cmd += ['+coophost', str(args.port)]
            elif args.steam_api:
                cmd += ['+coopjoin', 'steam:%d' % args.steam_host_id]
            else:
                cmd += ['+coopjoin', '127.0.0.1:' + str(args.port)]
            player_env = env
            if args.steam_api:
                player_env = env.copy()
                player_env['FAKESTEAM_ID'] = str(args.steam_host_id + n)
                player_env['FAKESTEAM_NAME'] = 'QA%d' % n
                player_env['FAKESTEAM_DIR'] = str(output / 'fakesteam')
            processes.append(subprocess.Popen(cmd, env=player_env, cwd=str(folder), stdout=log, stderr=log))
            wait_for(lambda folder=folder: read_state(folder), processes, args.timeout,
                     'core initialization for slot %d' % n)
            start = 'coopuiclick 320 240\ncoopqastart'
            if args.host_god and n == 0:
                start += '\ncoopgod 0 1'
            command(folder, start, joiner=n != 0)

        def connected():
            states = [read_state(f) for f in folders]
            if not all(states):
                return None
            host = states[0]
            if host['role'] != 1 or not all(p['active'] and p['state'] == 1 for p in host['players'][1:args.players]):
                return None
            if not all(s['joined'] and s['compatible'] and s['role'] == 2 and
                       s['snapshot_num'] > 0 and s['snapshot_time'] > 0 and
                       s['map'] == host['map'] for s in states[1:]):
                return None
            return states

        states = wait_for(connected, processes, args.timeout, 'real host and all joiners connected')
        results['checks'].append('real connected host and joiners')
        before = states[0]
        wait_liveness(before, connected, processes, args.players)
        results['checks'].append('host and every remote user-command clock advance')
        (output / 'before.json').write_text(json.dumps(states, indent=2))
        for n, folder in enumerate(folders[1:], 1):
            slot = states[n]['slot']
            if slot < 1 or slot >= args.players:
                raise RuntimeError('invalid joiner slot')
            distance = move_remote(folders[0], folder, slot, processes, args.timeout)
            results['checks'].append('remote %d moved %.1f units via player input' % (slot, distance))

        # Unallocated endpoints must not be able to inject engine snapshots.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b'\x01\x00\x00\x00' + b'fake engine packet', ('127.0.0.1', args.port))
        baseline = read_state(folders[0])
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError('game exited during observation')
            time.sleep(0.5)
        final = connected()
        if not final:
            raise RuntimeError('a joiner was lost during observation')
        wait_liveness(baseline, connected, processes, args.players)
        final = connected() or final
        for folder in folders:
            errors = process_log_errors(folder)
            if errors:
                raise RuntimeError(str(errors))
        (output / 'after.json').write_text(json.dumps(final, indent=2))
        results['checks'].append('stable observation with unallocated packet rejected')
        for n, folder in enumerate(folders):
            command(folder, 'screenshot', joiner=n != 0)
        time.sleep(1)
        for folder in reversed(folders):
            command(folder, 'quit', joiner=folder != folders[0])
        for process in processes:
            if process.wait(timeout=30) != 0:
                raise RuntimeError('nonzero game shutdown')
        results['checks'].append('all game processes shut down cleanly')
        results['status'] = 'PASS'
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        results['error'] = str(error)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for handle in handles:
            handle.close()
        (output / 'result.json').write_text(json.dumps(results, indent=2))
    print('RESULT: ' + results['status'])
    if 'error' in results:
        print(results['error'])
    return 0 if results['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
