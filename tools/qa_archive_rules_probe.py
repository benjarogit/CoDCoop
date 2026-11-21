#!/usr/bin/env python3
"""Real native quit/config-write preservation while host archive rules differ.

Uses actual Wine engines and owned reused installations. No coopleave is sent.
Relaunches once standalone without config overrides, then rejoins the live host.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import time
import qa_coop as qa


class ProcessSeat:
    def __init__(self, process):
        self.current = process

    def __getattr__(self, name):
        return getattr(self.current, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=29949)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    original_spawn, original_live = qa.subprocess.Popen, qa.assess_liveness
    engines = {}
    entered = False
    report = {'status': 'NOT_RUN', 'scope': 'native archive write/direct quit/standalone relaunch/real rejoin; no coopleave and no campaign completion'}

    def save():
        (output / 'archive-rules-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def launch(command, *a, **kw):
        if isinstance(command, list) and len(command) > 1 and Path(command[1]).name.lower() == 'coduosp.exe':
            folder = Path(kw['cwd'])
            cfg = 'set bg_allowJumpShot %d\nset cg_fov %d\n' % ((1, 83) if folder == host else (0, 101))
            (folder / 'sp_improved/coop_archive_probe.cfg').write_text(cfg)
            command = list(command)
            at = command.index('+devmap')
            command[at:at] = ['+exec', 'coop_archive_probe.cfg']
            seat = ProcessSeat(original_spawn(command, *a, **kw))
            engines[folder] = (seat, command, kw)
            return seat
        return original_spawn(command, *a, **kw)

    def probe(before, after, count):
        nonlocal entered
        original_live(before, after, count)
        if entered:
            return
        entered = True
        state = qa.read_state(peer)
        if not state['joined'] or state['rules']['jump_shot'] != 1 or not state['rules']['saved_local'] or state['local_fov'] != 101:
            raise RuntimeError('required original-peer0 / active-host1 archive divergence was not established')
        report['before_quit'] = state
        # Explicit write while still playing must preserve local disk values and
        # leave host numeric prediction and graphics values untouched in memory.
        written = peer / 'sp_improved/coop_archive_probe_written.cfg'
        written.unlink(missing_ok=True)
        qa.command(peer, 'writeconfig coop_archive_probe_written.cfg', joiner=True)
        qa.wait_for(lambda: written.is_file(), [], 10, 'native explicit config write')
        text = written.read_text(errors='replace')
        report['explicit_write_jump_shot'] = re.findall(r'^seta? bg_allowJumpShot "([^"]*)"', text, re.M)
        time.sleep(.5)
        report['after_explicit_write'] = qa.read_state(peer)
        if report['explicit_write_jump_shot'] != ['0'] or report['after_explicit_write']['rules']['jump_shot'] != 1:
            raise RuntimeError('native config serialization did not isolate local archive strings from active host prediction')
        seat, command, kw = engines[peer]
        qa.command(peer, 'quit', joiner=True)
        report['direct_exit_code'] = seat.wait(timeout=25)
        config = peer / 'sp_improved/uoconfig.cfg'
        text = config.read_text(errors='replace')
        (output / 'archive-direct-quit-uoconfig.cfg').write_text(text)
        shutil.copy2(peer / 'codcoop_join.log', output / 'archive-direct-quit-peer.log')
        report['written_jump_shot'] = re.findall(r'^seta? bg_allowJumpShot "([^"]*)"', text, re.M)
        menu = list(command)
        for flag in ('+exec', '+devmap', '+coopjoin'):
            at = menu.index(flag)
            del menu[at:at + 2]
        (peer / 'qa-state.json').unlink(missing_ok=True)
        seat.current = original_spawn(menu, **kw)
        qa.wait_for(lambda: qa.read_state(peer), [seat], args.timeout, 'standalone native relaunch without test overrides')
        time.sleep(.5)
        report['standalone_relaunch'] = qa.read_state(peer)
        fresh = report['standalone_relaunch']
        if report['written_jump_shot'] != ['0'] or fresh['rules']['jump_shot'] != 0 or fresh['local_fov'] != 101 or report['direct_exit_code'] != 0:
            raise RuntimeError('native direct quit leaked host archive settings into the local profile')
        qa.command(peer, 'quit')
        report['standalone_exit_code'] = seat.wait(timeout=25)
        qa.wait_for(lambda: not qa.read_state(host)['players'][1]['active'], [], 20, 'old connection released before actual rejoin')
        again = list(command)
        at = again.index('+exec')
        del again[at:at + 2]
        (peer / 'qa-state.json').unlink(missing_ok=True)
        seat.current = original_spawn(again, **kw)

        def joined():
            h, p = qa.read_state(host), qa.read_state(peer)
            if h and p and p['joined'] and p['rules']['jump_shot'] == 1 and p['local_fov'] == 101 and h['players'][1]['active']:
                return [h, p]

        report['rejoined'] = qa.wait_for(joined, [seat], args.timeout, 'real joined peer after unmodified config relaunch')
        time.sleep(2)
        original_live(report['rejoined'][0], qa.read_state(host), 2)
        report['status'] = 'PASS'
        save()

    qa.subprocess.Popen, qa.assess_liveness = launch, probe
    try:
        result = qa.main(['--source', str(args.source.resolve()), '--run', str(output), '--runtime-dir', str(args.runtime_dir.resolve()),
                          '--variant', 'sp_improved', '--map', 'pathfinder', '--players', '2', '--duration', '5',
                          '--port', str(args.port), '--timeout', str(args.timeout)])
        if result:
            report['status'] = 'FAIL'
        save()
        return result
    finally:
        qa.subprocess.Popen, qa.assess_liveness = original_spawn, original_live


if __name__ == '__main__':
    raise SystemExit(main())
