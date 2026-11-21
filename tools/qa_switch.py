#!/usr/bin/env python3
"""Exercise a real two-player campaign restart through the native-game supervisor.

This is a transition/installation gate, NOT a campaign playthrough. All mutable
state, prefix, X server, game copies, save files and injected negative content
belong to a new or explicitly marked QA directory. The source is never changed.
"""
import argparse
import configparser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import zipfile

from coop_suite import PROTOCOL, atomic_write, check_installation, seal_installation
from qa_coop import command, read_state, assess_liveness, process_log_errors

ROOT = Path(__file__).resolve().parents[1]


def probe_unconfirmed_join(folder, port):
    """One synthetic late JOIN; the original host/joiner remain real games.

    This is a negative packet/allocation gate, not a third-player gameplay test.
    The host supplies its actual current world through ordinary HELLO/READY.
    """
    profile=configparser.ConfigParser()
    profile.read(folder/'coop/profile.ini')
    settings=profile['coop']
    if int(settings['protocol'])!=9 or PROTOCOL!=9:
        raise ValueError('late JOIN probe requires the documented protocol9 wire')
    variants={'cod1':1,'uo':2,'sp_improved':3,'united_fronts':4}
    identity=struct.pack('<IBBH32s',PROTOCOL,1 if settings['engine']=='cod1' else 2,
                         variants[settings['variant']],1,bytes.fromhex(settings['digest']))
    def frame(kind,world):return struct.pack('<IB',0xfffffffe,ord(kind))+identity+world
    state=read_state(folder)
    if not state or any(player['active'] for player in state['players'][2:]):
        raise RuntimeError('late JOIN gate needs exactly the genuine two-player fixture')
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as peer:
        peer.bind(('127.0.0.1',0));peer.settimeout(3)
        peer.sendto(frame('H',bytes(12)),('127.0.0.1',port))
        ready,_=peer.recvfrom(65535)
        if len(ready)!=57 or ready[:5]!=struct.pack('<IB',0xfffffffe,ord('K')) or ready[5:45]!=identity:
            raise RuntimeError('late JOIN probe did not negotiate the real host world')
        packet=frame('J',ready[45:57])+struct.pack('<4i',peer.getsockname()[1],0,0,0)+state['map'].encode('ascii')+b'\0'
        peer.sendto(packet,('127.0.0.1',port))
        rejected,_=peer.recvfrom(65535)
    if len(rejected)<59 or rejected[:5]!=struct.pack('<IB',0xfffffffe,ord('V')) or rejected[5:57]!=ready[5:57]:
        raise RuntimeError('unconfirmed late JOIN was not rejected before native slot allocation')
    reason=rejected[57:].split(b'\0',1)[0].decode('ascii')
    if 'campaign change is pending' not in reason:
        raise RuntimeError('late JOIN rejection has no actionable campaign-change reason')
    deadline=time.monotonic()+3
    after=None
    while time.monotonic()<deadline:
        after=read_state(folder)
        if after and after['tick']>state['tick']:break
        time.sleep(.05)
    if not after or after['tick']<=state['tick'] or any(player['active'] or player['state'] for player in after['players'][2:]):
        raise RuntimeError('late JOIN touched an unconfirmed native player slot')
    return {'scope':'synthetic negative packet gate with two genuine live players',
            'hello_sha256':hashlib.sha256(ready).hexdigest(),'join_sha256':hashlib.sha256(packet).hexdigest(),
            'rejection':reason,'before':state,'after':after}


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def difficulty_value(text):
    text = re.sub(r'\^[0-9]', '', text)
    matches = re.findall(r'(?im)"?g_gameskill"?\s+(?:is|ist)\s*:\s*"?([0-3])\b', text)
    if not matches:
        raise ValueError('engine did not report g_gameskill')
    return int(matches[-1])


def hunk_value(text):
    text=re.sub(r'\^[0-9]', '', text)
    matches=re.findall(r'(?im)"?com_hunkmegs"?\s+(?:is|ist)\s*:\s*"?([0-9]+)\b',text)
    if not matches: raise ValueError('engine did not report com_hunkmegs')
    return int(matches[-1])


def maxhealth_value(text):
    text=re.sub(r'\^[0-9]', '', text)
    matches=re.findall(r'(?im)"?g_player_maxhealth"?\s+(?:is|ist)\s*:\s*"?([0-9]+)\b',text)
    if not matches: raise ValueError('engine did not report g_player_maxhealth')
    return int(matches[-1])


def assess_runner_environment(environ, expected_prefix, bundle):
    if environ.get('WINEPREFIX') != str(expected_prefix):
        raise ValueError('external runner lost the isolated Wine prefix')
    if environ.get('CODCOOP_QA_PROFILE') != '1':
        raise ValueError('game did not receive verified profile identity mode')
    leaked = [key for key in environ if key.startswith('_PYI_')]
    if leaked:
        raise ValueError('PyInstaller runtime variables leaked to game: ' + ', '.join(leaked))
    keys = ('LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG', 'PATH', 'QT_PLUGIN_PATH',
            'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'WINEPREFIX', 'CODCOOP_QA_PROFILE')
    selected = {key: environ.get(key) for key in keys}
    for key, value in selected.items():
        if value and str(bundle / '_internal') in value:
            raise ValueError('bundled GUI libraries leaked to external runner: ' + key)
    return selected


def runner_environments(supervisors, folders, prefix):
    records = []
    for supervisor, folder in zip(supervisors, folders):
        pid = supervisor.game_pids()[-1]
        entries = Path('/proc/%d/environ' % pid).read_bytes().split(b'\0')
        environ = dict(item.decode(errors='replace').split('=', 1) for item in entries if b'=' in item)
        selected = assess_runner_environment(environ, prefix, folder/'coop/launcher')
        records.append({'pid': pid, 'environment': selected})
    return records


def verify_transition(before, after, old_pids, new_pids, variant, map_name, difficulty):
    if len(before) != 2 or before[0].get('role') != 'host' or before[0].get('live_players', 0) < 2 or before[1].get('role') != 'joiner' or not before[1].get('joined'):
        raise ValueError('test did not begin with two live connected players')
    if len(old_pids) != 2 or len(new_pids) != 2 or any(a == b for a, b in zip(old_pids, new_pids)):
        raise ValueError('both game processes must actually restart')
    if len(after) != 2 or after[0].get('role') != 'host' or after[0].get('live_players', 0) < 2:
        raise ValueError('the new host does not have two live players')
    if after[1].get('role') != 'joiner' or not after[1].get('joined'):
        raise ValueError('joiner did not reconnect')
    if any(s.get('variant') != variant or s.get('map') != map_name for s in after):
        raise ValueError('players did not reach the requested campaign and map')
    if any(s.get('render_ready') is not True for s in after):
        raise ValueError('target renderer is not ready on both players')
    if difficulty not in range(4):
        raise ValueError('invalid target difficulty')
    if any(s.get('variant') == variant for s in before):
        raise ValueError('test must start in a different campaign')


class Supervisor:
    def __init__(self, folder, command_line, env, log_path):
        self.folder = folder
        self.events = []
        self.log = open(log_path, 'w', encoding='utf-8')
        self.process = subprocess.Popen(command_line, env=env, cwd=folder, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
        def drain():
            for line in self.process.stdout:
                self.log.write(line); self.log.flush()
                try:
                    value = json.loads(line)
                    if isinstance(value, dict) and 'phase' in value:
                        self.events.append(value)
                except ValueError:
                    pass
        self.reader = threading.Thread(target=drain, daemon=True)
        self.reader.start()

    def control(self, action, **details):
        if self.process.poll() is not None:
            raise RuntimeError('supervisor exited: ' + str(self.process.returncode))
        self.process.stdin.write(json.dumps({'action': action, **details}) + '\n')
        self.process.stdin.flush()

    def game_pids(self):
        return [e['pid'] for e in self.events if e.get('phase') == 'running']

    def stop(self):
        if self.process.poll() is None:
            self.control('stop')
            try: self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try: self.process.wait(timeout=8)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
        self.reader.join(timeout=2)
        self.log.close()


def wait_for(predicate, supervisors, timeout, description, folders=(), allow_start=False, tick=None):
    deadline = time.monotonic() + timeout
    next_start = 0
    while time.monotonic() < deadline:
        for supervisor in supervisors:
            if supervisor.process.poll() is not None:
                raise RuntimeError(description + ': supervisor exited ' + str(supervisor.process.returncode))
        if tick is not None: tick()
        if allow_start and time.monotonic() > next_start:
            for n, folder in enumerate(folders):
                state = read_state(folder)
                if state and state.get('server_time', 0) <= 1000 and not (folder / ('codcoop_join.cmd' if n else 'codcoop.cmd')).exists():
                    command(folder, 'coopqastart', joiner=n != 0)
            next_start = time.monotonic() + 2
        result = predicate()
        if result:
            return result
        time.sleep(.25)
    raise TimeoutError(description)


def copy_installation(source, folder, payload, language=None, german_archive=None, hunkmegs=256):
    if not folder.exists():
        folder.mkdir()
        subprocess.run(['cp', '-a', '--reflink=auto', str(source) + '/.', str(folder)], check=True)
    # Reuse only a byte-verified copy of this exact immutable payload.
    installed_lock = folder/'coop/runtime-lock.json'
    same_payload = installed_lock.is_file() and installed_lock.read_bytes() == (payload/'coop/runtime-lock.json').read_bytes()
    ready = check_installation(folder) if same_payload else {'ok': False}
    current_language = 'de' if (folder/'Main/.cod-coop-german').exists() else 'en'
    if not ready['ok'] or (language and language != current_language):
        install = [sys.executable, str(ROOT/'tools/install-linux.py'), '--game', str(folder),
                   '--suite-source', str(payload), '--language', language or current_language, '--yes', '--repair']
        if german_archive: install += ['--german-archive', str(german_archive)]
        subprocess.run(install, check=True)
    spec=importlib.util.spec_from_file_location('qa_installer_defaults',ROOT/'tools/install-linux.py')
    defaults=importlib.util.module_from_spec(spec);spec.loader.exec_module(defaults)
    quality=''.join('seta %s "%s"\n' % (key,value) for key,value in defaults.QUALITY['hoch'].items())
    for root in ('Main', 'main', 'uo', 'sp_improved', 'UnitedFronts'):
        base = folder / root
        if not base.is_dir():
            continue
        for name in ('config.cfg', 'config_mp.cfg', 'uoconfig.cfg', 'console.log'):
            (base / name).unlink(missing_ok=True)
        # Only isolated test copies receive these rendering/logging settings.
        (base / 'autoexec.cfg').write_text('seta r_fullscreen "0"\nseta r_mode "-1"\nseta r_customwidth "640"\n'
                                        'seta r_customheight "480"\nseta r_mode_auto "0"\nseta logfile "2"\n'
                                        'seta com_introplayed "1"\nseta com_hunkmegs "%d"\n' % hunkmegs + quality, encoding='ascii')
    for pattern in ('__CoD*', 'codcoop*.cmd', 'codcoop*.log', 'qa-state.*'):
        for old in folder.glob(pattern):
            if old.is_file(): old.unlink()
    for name in ('session.lock', 'supervisor.json', 'switch.json', 'switch.ack', 'session.json', 'runtime-state.json'):
        (folder / 'coop' / name).unlink(missing_ok=True)
    # The real installer has already sealed and verified the complete suite.
    # Only excluded test configs/logs were changed afterward; a second full
    # hash pass here would duplicate the supervisor's mandatory preflight.


def checked_profiles(folders, variant, core_hash):
    profiles=[]
    for folder in folders:
        parser=configparser.ConfigParser()
        try:
            parser.read_string((folder/'coop/profile.ini').read_text())
            profile=dict(parser['coop'])
        except (configparser.Error, KeyError) as error:
            raise ValueError('game profile could not be read: '+str(error)) from error
        if profile.get('protocol')!=str(PROTOCOL) or profile.get('variant')!=variant or profile.get('core_sha256')!=core_hash or not re.fullmatch('[0-9a-f]{64}',profile.get('digest','')):
            raise ValueError('game did not prepare the expected verified profile')
        profiles.append(profile)
    if profiles[0]!=profiles[1]:
        raise ValueError('English/German installations produced different gameplay profiles')
    return profiles


def runtime_ready(folders, variant, map_name):
    states = [read_json(f / 'coop/runtime-state.json') for f in folders]
    if not all(states) or any(s.get('render_ready') is not True for s in states): return None
    if states[0].get('role') != 'host' or states[0].get('live_players', 0) < 2: return None
    if states[1].get('role') != 'joiner' or not states[1].get('joined'): return None
    if any(s.get('variant') != variant or s.get('map') != map_name for s in states): return None
    return states


def query_engine_number(folder, joining, supervisors, timeout, variable, filename, parse_value):
    for file in folder.rglob(filename): file.unlink()
    command(folder, variable+'\ncondump '+filename, joiner=joining)
    def found():
        for path in folder.rglob(filename):
            try: return {'value': parse_value(path.read_text(errors='replace')), 'path': str(path)}
            except (OSError, ValueError): pass
        return None
    return wait_for(found, supervisors, timeout, 'engine query: '+variable)


def query_difficulty(folder, joining, supervisors, timeout):
    return query_engine_number(folder, joining, supervisors, timeout,'g_gameskill','qa-switch-difficulty.txt',difficulty_value)


def query_hunkmegs(folder, joining, supervisors, timeout):
    return query_engine_number(folder, joining, supervisors, timeout,'com_hunkmegs','qa-switch-hunkmegs.txt',hunk_value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--from-variant', choices=('cod1', 'uo', 'sp_improved', 'united_fronts'), default='cod1')
    parser.add_argument('--from-map', default='training')
    parser.add_argument('--to-variant', choices=('cod1', 'uo', 'sp_improved', 'united_fronts'), default='sp_improved')
    parser.add_argument('--to-map', default='pathfinder')
    parser.add_argument('--difficulty', type=int, choices=range(4), default=2)
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--skip-negative', action='store_true')
    parser.add_argument('--supervisor-mode', choices=('source','bundled'), default='source', help='bundled exercises the installed frozen GUI worker and its external runner isolation')
    parser.add_argument('--host-language', choices=('en','de'))
    parser.add_argument('--joiner-language', choices=('en','de'))
    parser.add_argument('--german-archive', type=Path, help='pinned offline German ZIP for mixed-language installation')
    parser.add_argument('--hunkmegs', type=int, choices=(128,256,512), default=256, help='production default 256; changes are explicit and engine-verified')
    parser.add_argument('--verification-delay',type=int,default=0,help='QA-only source supervisor: delay real background validation121..180s to test visible native wait/late rejection/explicit Retry')
    parser.add_argument('--check-late-join',action='store_true',help='synthetic unconfirmed JOIN must reject before allocation while the real pair verifies; requires delayed source mode')
    parser.add_argument('--check-committed-retry',action='store_true',help='QA-only delay target joiner launch; explicitly Retry a real live target host still awaiting its committed party')
    parser.add_argument('--frozen-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verification_delay and (args.supervisor_mode!='source' or not 120<args.verification_delay<=180):
        parser.error('controlled verification delay requires source mode and121..180s')
    if args.check_late_join and (not args.verification_delay or args.skip_negative):
        parser.error('late JOIN check requires delayed verification and the negative preparation phase')
    source, payload, output = args.source.resolve(), args.payload.resolve(), args.run.resolve()
    if args.from_variant == args.to_variant:
        parser.error('choose a different target campaign')
    if output.is_relative_to(source) or source.is_relative_to(output) or output.is_relative_to(payload):
        parser.error('test source, payload and output must be separate trees')
    output.mkdir(parents=True, exist_ok=True)
    marker = output / '.codcoop-switch-qa-owned'
    if any(output.iterdir()) and not marker.exists():
        parser.error('refusing an unowned output directory')
    if (output/'result.json').exists():
        history = output/'history'/str(time.time_ns())
        history.mkdir(parents=True)
        shutil.copy2(output/'result.json', history/'result.json')
        for name in ('qa-switch-source.py', 'intermediate-source-scope.json'):
            if (output/name).is_file():
                shutil.copy2(output/name, history/name)
                if name == 'intermediate-source-scope.json': (output/name).unlink()
        for role in ('host', 'join1'):
            previous = output/role
            for pattern in ('codcoop*.log', 'qa-state.json', 'coop/runtime-state.json', 'Main/console.log', 'main/console.log', 'uo/console.log', 'sp_improved/console.log', 'UnitedFronts/console.log'):
                for file in previous.glob(pattern):
                    if file.is_file():
                        saved = history/role/file.relative_to(previous)
                        saved.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file, saved)
        (output/'result.json').unlink()
    marker.write_text('isolated real supervisor switch QA\n')
    if not args.frozen_worker:
        # Freeze the entire executable tool graph, including late imports in
        # the installer. Shared-checkout edits must not alter a running gate.
        frozen = output/'runner'/str(time.time_ns())/'tools'
        frozen.mkdir(parents=True)
        for name in ('qa_switch.py', 'qa_coop.py', 'qa_delayed_verification.py', 'install-linux.py', 'coop_suite.py', 'coop_session.py', 'frozen_runtime.py', 'runtime_protocol.py'):
            shutil.copy2(ROOT/'tools'/name, frozen/name)
        provenance = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir()}
        (frozen.parent/'provenance.json').write_text(json.dumps(provenance, indent=2))
        arguments = list(sys.argv[1:] if argv is None else argv)
        os.execv(sys.executable, [sys.executable, str(frozen/'qa_switch.py'), *arguments, '--frozen-worker'])
    shutil.copy2(__file__, output/'qa-switch-source.py')
    if not args.port:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as endpoint:
            endpoint.bind(('127.0.0.1', 0)); args.port = endpoint.getsockname()[1]
    results = {'status': 'FAIL', 'coverage': 'two-player process/campaign transition; not a campaign playthrough',
               'identity': 'QA isolation flag with verified profile.ini gameplay fingerprint; mandatory full receipt checks',
               'source': str(source), 'payload': str(payload), 'port': args.port, 'checks': [],
               'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'core_sha256': hashlib.sha256((payload/'codcoop_core.dll').read_bytes()).hexdigest(),
               'supervisor_mode': args.supervisor_mode,
               'languages': {'host': args.host_language, 'joiner': args.joiner_language},
               'hunkmegs': args.hunkmegs, 'quality': 'installer production high preset',
               'verification_delay_seconds':args.verification_delay,
               'frozen_tools': read_json(ROOT/'provenance.json')}
    folders = [output/'host', output/'join1']
    supervisors, logs, display_process = [], [], None
    env = os.environ.copy()
    env.update(WINEPREFIX=str(output/'prefix'), WINEDEBUG='-all', CODCOOP_QA='1', CODCOOP_QA_NO_STEAM='1', CODCOOP_QA_PROFILE='1',
               WINEDLLOVERRIDES='ddraw=n,b;mscoree=;mshtml=', LIBGL_ALWAYS_SOFTWARE='1',
               MESA_EXTENSION_MAX_YEAR='2003', __GL_ExtensionStringVersion='15000')
    try:
        for n, folder in enumerate(folders):
            copy_installation(source, folder, payload, args.host_language if n == 0 else args.joiner_language, args.german_archive, args.hunkmegs)
        results['checks'].append('both isolated complete installations sealed and verified')
        read_fd, write_fd = os.pipe()
        display_log = open(output/'xvfb.log', 'wb'); logs.append(display_log)
        display_process = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '1600x1000x24', '-nolisten', 'tcp'],
                                           pass_fds=(write_fd,), stdout=display_log, stderr=display_log)
        os.close(write_fd)
        if not select.select([read_fd], [], [], 10)[0]:
            raise RuntimeError('Xvfb did not allocate a display')
        env['DISPLAY'] = ':' + os.read(read_fd, 64).decode().strip(); os.close(read_fd)
        boot_log = open(output/'wineboot.log', 'wb'); logs.append(boot_log)
        if not (output/'prefix/system.reg').exists():
            subprocess.run(['wineboot', '--init'], env=env, stdout=boot_log, stderr=boot_log, check=True, timeout=90)
        # Renderer flags must be present before UO creates its GL context;
        # autoexec.cfg is processed too late in that engine. This explicit QA
        # runner changes only local rendering, never map/role/gameplay options.
        runner = output/'wine-qa-runner.py'
        runner.write_text('import os, sys\nos.execvp("wine", ["wine", *sys.argv[1:], '
                          '"+set", "r_fullscreen", "0", "+set", "r_mode", "-1", '
                          '"+set", "r_customwidth", "640", "+set", "r_customheight", "480", '
                          '"+set", "r_mode_auto", "0", "+set", "logfile", "2", '
                          '"+set", "com_hunkmegs", "'+str(args.hunkmegs)+'"])\n')
        recovery_gate=output/'qa-release-target-joiner'
        recovery_gate.unlink(missing_ok=True)
        if args.check_committed_retry:
            # Delay only the QA target-joiner runner, never a native readiness
            # value. The target host must create a real live world and wait for
            # the original two-player party before its explicit Retry is sent.
            original=runner.read_text()
            gate_code=('import os,sys,time\nfrom pathlib import Path\n'
                       'if "+coopjoin" in sys.argv and any(sys.argv[i:i+3]==["+set","coop_expected_players","2"] for i in range(len(sys.argv))):\n'
                       '    deadline=time.monotonic()+'+repr(max(240,args.timeout*2))+'\n'
                       '    while not Path('+repr(str(recovery_gate))+').exists():\n'
                       '        if time.monotonic()>deadline: raise SystemExit("QA target joiner gate timed out")\n'
                       '        time.sleep(.1)\n')
            runner.write_text(gate_code+original)
        for n, folder in enumerate(folders):
            worker = [str(folder/'coop/launcher/CoD-Coop-Launcher'), '--internal-command', 'session'] if args.supervisor_mode == 'bundled' else [sys.executable, str(ROOT/'tools/coop_session.py')]
            if args.verification_delay:
                worker=[sys.executable,str(ROOT/'tools/qa_delayed_verification.py'),'--delay',str(args.verification_delay)]
            cmd = [*worker, '--game', str(folder),
                   '--variant', args.from_variant, '--map', args.from_map, '--difficulty', '1', '--port', str(args.port),
                   '--runner', shlex.join([sys.executable, str(runner)])]
            cmd += ['--hosting'] if n == 0 else ['--host', '127.0.0.1:' + str(args.port)]
            supervisors.append(Supervisor(folder, cmd, env, output/('supervisor%d.log' % n)))
            if n == 0:
                def host_started():
                    state = read_state(folder)
                    runtime = read_json(folder/'coop/runtime-state.json')
                    return state and runtime and runtime.get('role') == 'host' and state.get('server_time', 0) > 1000
                wait_for(host_started, supervisors, args.timeout, 'host mission running before joiner startup', [folder], allow_start=True)
        before = wait_for(lambda: runtime_ready(folders, args.from_variant, args.from_map), supervisors, args.timeout,
                          'initial real host/joiner connection', folders, allow_start=True)
        qa_before = [read_state(f) for f in folders]
        old_pids = [s.game_pids()[-1] for s in supervisors]
        results['before'] = {'runtime': before, 'pids': old_pids, 'qa': qa_before}
        results['profiles_before'] = checked_profiles(folders, args.from_variant, results['core_sha256'])
        time.sleep(2)
        results['initial_liveness_after'] = read_state(folders[0])
        assess_liveness(qa_before[0], results['initial_liveness_after'], 2)
        results['checks'].append('initial two-player session advances actual user commands')
        if args.supervisor_mode == 'bundled':
            results['runner_environment_before'] = runner_environments(supervisors, folders, output/'prefix')
        # A launcher may not prepare/restart a client with altered content.
        if not args.skip_negative:
            bad = folders[1]/'uo/zzzz_qa_unreceipted.pk3'
            try:
                with zipfile.ZipFile(bad, 'w') as archive: archive.writestr('qa/negative.txt', 'not part of receipt')
                starts = [len(s.game_pids()) for s in supervisors]
                supervisors[0].control('switch', variant=args.to_variant, map=args.to_map, difficulty=args.difficulty)
                def late_join():
                    if not args.check_late_join or 'unconfirmed_late_join' in results:return
                    state=read_json(folders[0]/'coop/runtime-state.json') or {}
                    if state.get('switch',{}).get('phase')==1:
                        results['unconfirmed_late_join']=probe_unconfirmed_join(folders[0],args.port)
                def cancelled():
                    return any(e.get('phase') == 'cancelled' for s in supervisors for e in s.events)
                wait_for(cancelled, supervisors, args.timeout, 'changed client rejected and transition cancelled', folders,tick=late_join)
                if args.check_late_join and 'unconfirmed_late_join' not in results:
                    raise RuntimeError('negative late JOIN phase was not exercised')
                if any(len(s.game_pids()) != count for s, count in zip(supervisors, starts)):
                    raise RuntimeError('a client restarted despite failed readiness')
                if not runtime_ready(folders, args.from_variant, args.from_map):
                    raise RuntimeError('cancelled transition lost the old session')
                alive_before = read_state(folders[0]); time.sleep(2)
                assess_liveness(alive_before, read_state(folders[0]), 2)
                results['checks'].append('unreceipted client content cancels transition without process restart; both players remain live')
            finally:
                bad.unlink(missing_ok=True)
        saves_before = {str(p): p.stat().st_mtime_ns for p in folders[0].rglob('coop_switch.svg')}
        began = time.time_ns()
        supervisors[0].control('switch', variant=args.to_variant, map=args.to_map, difficulty=args.difficulty)
        retried_transactions=set()
        def retry_verified_wait():
            # Exercise the real visible Retry action after a slow cold-disk
            # preflight. Never retry a failed/incomplete verification or silently
            # reduce the party; the production supervisor does not auto-retry.
            state=read_json(folders[0]/'coop/runtime-state.json') or {}
            change=state.get('switch',{})
            transaction=change.get('transaction')
            if (change.get('waiting') is not True or type(transaction) is not int or
                    not transaction or transaction in retried_transactions): return
            if not all(any(e.get('phase')=='prepared' and e.get('transaction')==transaction and
                           e.get('variant')==args.to_variant for e in s.events) for s in supervisors): return
            retried_transactions.add(transaction)
            results.setdefault('verified_wait_retries',[]).append({'runtime':state,'events':[list(s.events) for s in supervisors]})
            supervisors[0].control('retry')
        wait_for(lambda: all(len(s.game_pids()) >= 2 for s in supervisors), supervisors, args.timeout,
                 'both supervisors restart their real games', folders, tick=retry_verified_wait)
        saved = [p for p in folders[0].rglob('coop_switch.svg') if p.stat().st_size > 0 and
                 p.stat().st_mtime_ns > saves_before.get(str(p), 0) and p.stat().st_mtime_ns >= began - 2_000_000_000]
        if not saved:
            raise RuntimeError('host did not write a fresh campaign save before restart')
        results['checks'].append('host writes a nonempty fresh coop_switch.svg before restart')
        results['save'] = [{'path': str(p), 'size': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in saved]
        if args.check_committed_retry:
            def live_waiting_host(minimum_tick=0):
                state=read_json(folders[0]/'coop/runtime-state.json') or {}
                native=read_state(folders[0]) or {}
                if (state.get('variant')==args.to_variant and state.get('map')==args.to_map and
                        state.get('role')=='host' and state.get('render_ready') is True and
                        state.get('live_players',0)<=1 and native.get('expected_players')==2 and
                        native.get('snapshot_num',0)>0 and
                        native.get('tick',0)>minimum_tick and
                        any(e.get('phase')=='reconnecting' for e in supervisors[0].events)):
                    return state
            waiting=wait_for(live_waiting_host,supervisors,args.timeout,'real target host waiting for committed peer',folders)
            waiting_pid=supervisors[0].game_pids()[-1]
            os.kill(waiting_pid,0)
            live_before=read_state(folders[0]);time.sleep(2);live_after=read_state(folders[0])
            # The normal pregame gate correctly pauses mission time until the
            # full party arrives. Require an actual rendered native snapshot
            # and continuing Core execution, without closing that UI for QA.
            if not live_before or not live_after or live_after.get('tick',0)<=live_before.get('tick',0):
                raise RuntimeError('target host was not executing before recovery Retry')
            supervisors[0].control('retry',variant='../invalid',map='wrong',difficulty=0,players=1,host='invalid')
            wait_for(lambda:len(supervisors[0].game_pids())>=3,supervisors,args.timeout,
                     'explicit recovery Retry restarts the live owned target host',folders)
            if supervisors[0].game_pids()[-1]==waiting_pid:
                raise RuntimeError('recovery Retry reused the waiting native process')
            replacement=wait_for(lambda:live_waiting_host(live_after.get('tick',0)),supervisors,args.timeout,
                'replacement rendered host still requires the committed two-player party',folders)
            replacement_native=read_state(folders[0]) or {}
            if replacement_native.get('tick',0)<=live_after.get('tick',0):
                raise RuntimeError('replacement readiness came from a stale native process')
            for saved_file in results['save']:
                path=Path(saved_file['path'])
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=saved_file['sha256']:
                    raise RuntimeError('committed recovery Retry changed the previous campaign save')
            recovery_gate.write_text('explicit host recovery Retry observed\n')
            results['committed_host_retry']={'scope':'real target host; target joiner runner deliberately delayed',
                'waiting_runtime':waiting,'waiting_pid':waiting_pid,'replacement_pid':supervisors[0].game_pids()[-1],
                'native_before':live_before,'native_after':live_after,
                'replacement_runtime':replacement,'replacement_native':replacement_native}
            results['checks'].append('explicit committed recovery Retry replaces a live native host without changing the committed map, skill or two-player party')
        after = wait_for(lambda: runtime_ready(folders, args.to_variant, args.to_map), supervisors, args.timeout,
                         'both players reconnect to target campaign/map', folders)
        new_pids = [s.game_pids()[-1] for s in supervisors]
        verify_transition(before, after, old_pids, new_pids, args.to_variant, args.to_map, args.difficulty)
        qa_before = read_state(folders[0]); time.sleep(2)
        assess_liveness(qa_before, read_state(folders[0]), 2)
        for n, folder in enumerate(folders):
            log = folder/('codcoop_join.log' if n else 'codcoop.log')
            if 'cmd: coopqastart' in log.read_text(errors='replace'):
                raise RuntimeError('target campaign required a QA start command')
        results['checks'].append('target campaign starts automatically without a QA UI click; both renderers become ready')
        results['checks'].append('both new game processes reconnect and advance live user commands')
        skills = [query_difficulty(f, n != 0, supervisors, 20) for n, f in enumerate(folders)]
        if any(s['value'] != args.difficulty for s in skills):
            raise RuntimeError('requested difficulty not active on both engines: ' + str(skills))
        results['difficulty_queries'] = skills
        results['checks'].append('both engines report requested target difficulty')
        health=[query_engine_number(f,n!=0,supervisors,20,'g_player_maxhealth','qa-switch-maxhealth.txt',maxhealth_value)
                for n,f in enumerate(folders)]
        if any(item['value']!=(1200,600,300,200)[args.difficulty] for item in health):
            raise RuntimeError('engine maximum health differs from the original difficulty preset')
        results['maxhealth_queries']=health
        results['checks'].append('both engines report the original maximum-health value for the requested difficulty')
        memory=[query_hunkmegs(f,n != 0,supervisors,20) for n,f in enumerate(folders)]
        if any(item['value'] != args.hunkmegs for item in memory):
            raise RuntimeError('engine memory differs from the declared production setting')
        results['hunkmegs_queries']=memory
        results['checks'].append('both engines report the declared hunk memory setting')
        results['after'] = {'runtime': after, 'pids': new_pids, 'qa': [read_state(f) for f in folders]}
        results['profiles_after'] = checked_profiles(folders, args.to_variant, results['core_sha256'])
        if args.supervisor_mode == 'bundled':
            results['runner_environment_after'] = runner_environments(supervisors, folders, output/'prefix')
            results['checks'].append('actual external Wine process environments isolate bundled GUI libraries and preserve owned prefix')
        for folder in folders:
            if process_log_errors(folder): raise RuntimeError(str(process_log_errors(folder)))
        for supervisor in supervisors: supervisor.stop()
        if any(s.process.returncode != 0 for s in supervisors):
            raise RuntimeError('a supervisor failed during clean shutdown')
        results['checks'].append('both supervisors and game processes close cleanly')
        results['status'] = 'PASS'
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        results['error'] = str(error)
    finally:
        for supervisor in supervisors:
            if supervisor.process.poll() is None: supervisor.stop()
        for log in logs: log.close()
        if display_process is not None:
            subprocess.run(['wineserver', '-k'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            display_process.terminate()
            try: display_process.wait(timeout=5)
            except subprocess.TimeoutExpired: display_process.kill(); display_process.wait()
        results['events'] = [s.events for s in supervisors]
        (output/'result.json').write_text(json.dumps(results, indent=2))
    print('RESULT: ' + results['status'])
    if 'error' in results: print(results['error'])
    return 0 if results['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
