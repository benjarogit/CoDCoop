#!/usr/bin/env python3
"""Own one game process and preserve its group session over campaign restarts.

The in-engine bridge uses allowlisted variant IDs, never remote executable paths.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from coop_suite import PROTOCOL, atomic_write, canonical, check_installation, launch_arguments, load_manifest, resolve
from frozen_runtime import spawn_owned

VARIANTS = ('cod1', 'uo', 'sp_improved', 'united_fronts')


def event(phase, **details):
    print(json.dumps({'phase': phase, **details}), flush=True)


def validate_request(data):
    if not isinstance(data, dict) or data.get('variant') not in VARIANTS:
        raise ValueError('unknown requested campaign')
    transaction = data.get('transaction')
    if not isinstance(transaction, int) or not 0 < transaction <= 0xffffffff:
        raise ValueError('invalid switch transaction')
    if data.get('action') not in ('prepare', 'commit', 'cancel'):
        raise ValueError('invalid switch action')
    if data.get('role') not in ('host', 'joiner'):
        raise ValueError('invalid switch role')
    endpoint = data.get('host', '')
    if data['role'] == 'joiner' and not re.fullmatch(r'(?:[0-9.]+:[0-9]+|steam:[0-9]+)', endpoint):
        raise ValueError('invalid reconnect endpoint')
    if not isinstance(data.get('port', 28960), int) or not 1 <= data.get('port', 28960) <= 65535:
        raise ValueError('invalid host port')
    if not isinstance(data.get('difficulty', 1), int) or not 0 <= data.get('difficulty', 1) <= 3:
        raise ValueError('invalid difficulty')
    if data.get('map') is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', data['map']):
        raise ValueError('invalid map name')
    if type(data.get('players', 1)) is not int or not 1 <= data.get('players', 1) <= 4:
        raise ValueError('invalid participant count')
    return data


def target_map_exists(game, variant_id, map_name):
    if not map_name:
        return True
    manifest, _ = load_manifest(game)
    variant = next(v for v in manifest['variants'] if v['id'] == variant_id)
    wanted = 'maps/' + map_name.lower() + '.bsp'
    for folder in variant['content_roots']:
        base = resolve(game, folder)
        for path in base.rglob('*'):
            if path.is_file() and path.suffix.lower() == '.pk3' and 'localized_backup' not in path.parts:
                try:
                    with zipfile.ZipFile(path) as archive:
                        if any(name.lower() == wanted for name in archive.namelist()):
                            return True
                except zipfile.BadZipFile:
                    # The engine ignores placeholders such as the known one-byte pakb.
                    # The full receipt was already verified before this lookup.
                    continue
    return False


def process_alive(pid):
    if os.name == 'nt':
        import ctypes
        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not process: return False
        status = ctypes.c_ulong()
        alive = bool(ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(status))) and status.value == 259
        ctypes.windll.kernel32.CloseHandle(process)
        return alive
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def send_command(game, text, joining):
    path = game / ('codcoop_join.cmd' if joining else 'codcoop.cmd')
    if path.exists(): return False
    atomic_write(path, (text + '\n').encode('ascii'))
    return True


class SwitchState:
    """Only a locally verified preparation may be committed once."""
    def __init__(self):
        self.prepared = None
        self.committed = set()

    def accept(self, request):
        request = validate_request(request)
        key = (request['transaction'], request['variant'])
        if request['action'] == 'prepare':
            if key in self.committed: return 'ignored'
            self.prepared = key
            return 'prepare'
        if request['action'] == 'cancel':
            if self.prepared == key: self.prepared = None
            return 'cancel'
        if self.prepared != key or key in self.committed:
            raise ValueError('commit without matching verified preparation')
        self.committed.add(key)
        self.prepared = None
        return 'commit'


def recovery_spec(request):
    request = validate_request(request)
    return {'variant': request['variant'], 'host': request.get('host') or None,
            'hosting': request['role'] == 'host', 'port': request.get('port', 28960),
            'map': request.get('map'), 'difficulty': request.get('difficulty', 1)}


def recovery_ready(state, variant, map_name, hosting, players):
    if not isinstance(state, dict) or state.get('variant') != variant or state.get('render_ready') is not True:
        return False
    if not state.get('map') or (map_name and state.get('map') != map_name):
        return False
    if hosting:
        return state.get('role') == 'host' and state.get('live_players', 0) >= players
    return state.get('role') == 'joiner' and state.get('joined') is True


def clear_command_files(game):
    """Commands belong to one owned game lifetime, never to its successor."""
    for name in ('codcoop.cmd', 'codcoop_join.cmd'):
        for suffix in ('', '.pending'):
            (game / (name + suffix)).unlink(missing_ok=True)


def stop_owned(game, process, joining):
    if process is None or process.poll() is not None:
        return
    deadline = time.monotonic() + 3
    while not send_command(game, 'quit', joining) and time.monotonic() < deadline:
        time.sleep(.1)
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()


def supervise(args):
    game = args.game.resolve()
    check = check_installation(game)
    if not check['ok']: raise ValueError('; '.join(check['errors']))
    lock_path = game / 'coop/session.lock'
    if lock_path.exists():
        previous = json.loads(lock_path.read_text())
        if process_alive(int(previous['pid'])):
            raise ValueError('a launcher session already owns this installation')
        lock_path.unlink()
    with lock_path.open('x') as lock:
        lock.write(json.dumps({'pid': os.getpid(), 'id': uuid.uuid4().hex}))
    atomic_write(game / 'coop/supervisor.json', canonical({'pid': os.getpid(), 'protocol': PROTOCOL}))
    requests = game / 'coop/switch.json'
    ack = game / 'coop/switch.ack'
    requests.unlink(missing_ok=True); ack.unlink(missing_ok=True)
    controls = queue.Queue()
    stopping = threading.Event()
    def read_controls():
        for line in sys.stdin:
            try: controls.put(json.loads(line))
            except ValueError: event('error', error='invalid local control message')
    threading.Thread(target=read_controls, daemon=True).start()
    def stop_signal(*_): stopping.set()
    for signum in (signal.SIGINT, signal.SIGTERM): signal.signal(signum, stop_signal)
    variant = args.variant
    host = args.host
    hosting = args.hosting
    port = args.port
    current = None
    difficulty = args.difficulty
    machine = SwitchState()
    last_event = None
    heartbeat = 0
    commit_seen = 0
    quit_sent = False
    restart = None
    recovery = None
    recovery_wait = False
    command_queue = []
    pending_reply = None
    awaiting_launch = True
    next_map = args.map_name
    try:
        while True:
            if time.monotonic() - heartbeat > 2:
                atomic_write(game / "coop/supervisor.json", canonical({"pid": os.getpid(), "protocol": PROTOCOL}))
                heartbeat = time.monotonic()
            if restart is not None and not quit_sent and current is not None and current.poll() is None and time.monotonic() - commit_seen > 2:
                quit_sent = send_command(game, "quit", bool(host))
            if awaiting_launch:
                command, env = launch_arguments(game, variant, args.runner, host, next_map, hosting, port, difficulty, recovery.get("players", 1) if recovery else 1)
                clear_command_files(game)
                (game / 'coop/runtime-state.json').unlink(missing_ok=True)
                current = spawn_owned(command, cwd=game, env=env)
                recovery_wait = False
                awaiting_launch = False
                event('running', variant=variant, pid=current.pid)
            while not controls.empty():
                control = controls.get()
                if not isinstance(control, dict):
                    event('error', error='local control must be an object'); continue
                action = control.get('action')
                if action == 'stop': stopping.set()
                elif action == 'switch':
                    if not hosting or control.get('variant') not in VARIANTS:
                        event('error', error='only the host can select a registered campaign')
                    else:
                        mission = control.get('map') or 'default'
                        skill = control.get('difficulty', difficulty)
                        if not isinstance(mission, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', mission) or not isinstance(skill, int) or not 0 <= skill <= 3:
                            event('error', error='invalid target mission or difficulty')
                        else:
                            command_queue.append(('coopswitch %s %s %d' % (control['variant'], mission, skill), time.monotonic() + 5, True))
                elif action == 'cancel': command_queue.append(('coopswitchcancel', time.monotonic()+5, False))
                elif action == 'retry':
                    if recovery is not None and current.poll() is not None:
                        spec = recovery_spec(recovery)
                        variant, host, hosting, port = spec['variant'], spec['host'], spec['hosting'], spec['port']
                        next_map, difficulty = spec['map'], spec['difficulty']
                        restart = None; commit_seen = 0; quit_sent = False; last_event = None
                        command_queue.clear(); pending_reply = None
                        requests.unlink(missing_ok=True); ack.unlink(missing_ok=True)
                        awaiting_launch = True
                    else:
                        command_queue.append(('coopswitchretry', time.monotonic()+5, False))
                else: event('error', error='unknown local control action')
            if command_queue:
                text, deadline, expects_reply = command_queue[0]
                if send_command(game, text, bool(host)):
                    command_queue.pop(0)
                    if expects_reply: pending_reply = time.monotonic() + 10
                elif time.monotonic() > deadline:
                    command_queue.pop(0)
                    event('error', error='game command queue is busy; retry the action')
            if pending_reply is not None and time.monotonic() > pending_reply:
                pending_reply = None
                event('error', error='game did not accept the campaign change; check its Co-op status')
            if stopping.is_set():
                stop_owned(game, current, bool(host))
                event('stopped')
                return 0
            if requests.exists():
                raw = requests.read_bytes()
                if raw != last_event:
                    try:
                        request = validate_request(json.loads(raw))
                        pending_reply = None
                        action = machine.accept(request)
                        last_event = raw
                        if action == 'prepare':
                            # Verify without changing profile.ini while the old game runs.
                            check = check_installation(game)
                            ok = check['ok'] and request['variant'] in check.get('variants', {}) and target_map_exists(game, request['variant'], request.get('map'))
                            atomic_write(ack, ('%d %d\n' % (request['transaction'], 1 if ok else 0)).encode('ascii'))
                            if not ok:
                                machine.prepared = None
                                event('error', error='; '.join(check['errors']) or 'Target mission is not installed')
                            else: event('prepared', variant=request['variant'], transaction=request['transaction'])
                        elif action == 'cancel': event('cancelled', variant=variant)
                        elif action == 'commit':
                            restart = request
                            recovery = dict(request)
                            commit_seen = time.monotonic()
                            quit_sent = False
                            command_queue.clear(); pending_reply = None
                            atomic_write(game / 'coop/session.json', canonical(request))
                            event('restarting', variant=request['variant'])
                    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
                        last_event = raw
                        event('error', error=str(error))
            runtime_state = game / 'coop/runtime-state.json'
            if recovery is not None and restart is None and current.poll() is None and runtime_state.exists():
                try:
                    state = json.loads(runtime_state.read_bytes())
                    ready = recovery_ready(state, variant, next_map, hosting, recovery.get('players', 1))
                    if ready:
                        recovery = None
                        event('resumed', variant=variant)
                except (OSError, ValueError): pass
            if current is not None and current.poll() is not None:
                if restart is None and recovery is None:
                    event('exited', code=current.returncode)
                    return current.returncode
                if restart is not None and current.returncode == 0:
                    spec = recovery_spec(restart)
                    variant, host, hosting, port = spec['variant'], spec['host'], spec['hosting'], spec['port']
                    next_map, difficulty = spec['map'], spec['difficulty']
                    awaiting_launch = True
                    requests.unlink(missing_ok=True); ack.unlink(missing_ok=True)
                    last_event = None; restart = None; commit_seen = 0; quit_sent = False
                    command_queue.clear(); pending_reply = None
                    clear_command_files(game)
                elif not recovery_wait:
                    recovery_wait = True
                    event('error', error='game failed during switch; retry is available')
            time.sleep(.2)
    finally:
        stop_owned(game, current, bool(host))
        clear_command_files(game)
        (game / 'coop/supervisor.json').unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, type=Path)
    parser.add_argument('--variant', choices=VARIANTS, default='sp_improved')
    parser.add_argument('--host')
    parser.add_argument('--hosting', action='store_true')
    parser.add_argument('--port', type=int, default=28960)
    parser.add_argument('--map', dest='map_name')
    parser.add_argument('--runner')
    parser.add_argument('--difficulty', type=int, choices=range(4), default=1)
    args = parser.parse_args(argv)
    if args.host and args.hosting: parser.error('choose joining or hosting')
    try: return supervise(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        event('error', error=str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
