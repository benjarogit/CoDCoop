#!/usr/bin/env python3
"""Run the four-player UF scenario and watch the shared character definition.

QA-only orchestration: it starts the existing fresh-role runner with the
read-only tree trace, waits for each joiner to publish its owned character
definition (the one with the large node count), and attaches the standalone
write watchpoint to definition+4 with the value read at creation. It never
changes free semantics, timeouts or game data. A no-hit timeout is not proof
that the field is safe.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE = re.compile(r'QA tree trace phase=create-owned pid=(\d+) entity=(-?\d+) tree=([0-9a-fA-F]+) definition=([0-9a-fA-F]+) nodes=(-?\d+)')


def winpath(path):
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


def parse_created(line):
    match = CREATE.search(line)
    if not match:
        return None
    pid, entity, tree, definition, nodes = match.groups()
    if int(definition, 16) == 0 or int(nodes) <= 0:
        return None
    return dict(pid=int(pid), entity=int(entity), tree=tree, definition=definition, nodes=int(nodes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', type=Path, required=True, help='built qa_write_watchpoint.exe')
    parser.add_argument('--run', type=Path, required=True, help='owned scenario output directory')
    parser.add_argument('--prefix', type=Path, help='Wine prefix used by the game (defaults to RUN/prefix)')
    parser.add_argument('--timeout-ms', type=int, default=120000)
    args, extra = parser.parse_known_args()
    extra = [value for value in extra if value != '--']
    if '--run' in extra:
        parser.error('pass the output directory with --run, not in the runner arguments')
    if '--trace-tree-free' not in extra:
        extra.append('--trace-tree-free')
    run = args.run.resolve()
    prefix = (args.prefix or run / 'prefix').resolve()
    runner = [sys.executable, str(ROOT / 'tools/qa_uf_fresh_roles.py'), '--run', str(run)] + extra
    print('runner:', ' '.join(runner), flush=True)
    process = subprocess.Popen(runner, cwd=ROOT)
    watches = {}
    results = []
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all')
    try:
        while process.poll() is None:
            for name in ('join1', 'join2', 'join3'):
                if name in watches:
                    continue
                log = run / name / 'codcoop_join.log'
                try:
                    text = log.read_text(errors='replace')
                except OSError:
                    continue
                for line in text.splitlines():
                    created = parse_created(line)
                    if not created:
                        continue
                    output = run / ('watch-%s.jsonl' % name)
                    command = ['wine', str(args.watch), '--pid', str(created['pid']),
                               '--exe', winpath(run / name / 'CoDUOSP.exe'),
                               '--address', '%x' % (int(created['definition'], 16) + 4),
                               '--expected', str(created['nodes']),
                               '--timeout-ms', str(args.timeout_ms),
                               '--output', winpath(output)]
                    print('attach %s pid=%d definition=%s nodes=%d' %
                          (name, created['pid'], created['definition'], created['nodes']), flush=True)
                    watches[name] = dict(process=subprocess.Popen(command, env=env),
                                         target=created, output=output)
                    break
            time.sleep(.2)
        code = process.wait()
    finally:
        for entry in watches.values():
            if entry['process'].poll() is None:
                entry['process'].terminate()
    for name, entry in sorted(watches.items()):
        try:
            exit_code = entry['process'].wait(timeout=10)
        except subprocess.TimeoutExpired:
            entry['process'].kill()
            exit_code = -1
        events = []
        try:
            events = [json.loads(line) for line in entry['output'].read_text().splitlines()]
        except (OSError, ValueError):
            pass
        results.append(dict(peer=name, target=entry['target'], watcher_exit=exit_code, events=events))
    summary = dict(scope='QA-only owned scenario; one 4-byte definition field per joiner',
                   runner_exit=code, runner=runner, watches=results)
    (run / 'tree-watch.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(runner_exit=code, watches=[dict(peer=row['peer'], exit=row['watcher_exit'],
                                                          status=[event.get('status') for event in row['events']])
                                                     for row in results])))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
