#!/usr/bin/env python3
"""Owned standalone fixture acceptance only; never selects or starts a game."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def run(output: Path, prefix: Path):
    output = output.resolve()
    env = dict(os.environ, WINEPREFIX=str(prefix.resolve()), WINEDEBUG='-all')
    win = lambda path: 'Z:' + str(path.resolve()).replace('/', '\\')
    results = []
    for label, mode in [('positive', 1), ('new-thread', 2), ('timeout-reattach', 0),
                        ('wrong-process-path', 1), ('wrong-pid', 1), ('wrong-initial', 1),
                        ('existing-hardware', 3), ('existing-debugger', 0)]:
        desc = output / (label + '.txt')
        desc.unlink(missing_ok=True)
        with (output / (label + '-stderr.log')).open('wb') as err:
            target = subprocess.Popen(['wine', str(output / 'fixture.exe'), win(desc), '1800', str(mode), '2000'], env=env, stdout=subprocess.DEVNULL, stderr=err)
            deadline = time.monotonic() + 30
            while not desc.exists() and target.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert desc.exists(), (label, 'fixture did not publish identity', target.poll())
            pid, address = desc.read_text().splitlines()[0].split()
            path = desc.read_text().splitlines()[1]
            timeout = 500 if label == 'timeout-reattach' else 4000
            expected = '989' if label == 'wrong-initial' else '988'
            claimed_path = win(output / 'watch.exe') if label == 'wrong-process-path' else path
            claimed_pid = '2147483646' if label == 'wrong-pid' else pid
            def command(log, timeout_ms=timeout):
                return ['wine', str(output / 'watch.exe'), '--pid', claimed_pid, '--exe', claimed_path, '--address', address, '--expected', expected, '--timeout-ms', str(timeout_ms), '--output', win(log)]
            log = output / (label + '.jsonl')
            if label == 'existing-debugger':
                firstlog = output / (label + '-first.jsonl')
                first = subprocess.Popen(command(firstlog, 1200), env=env, stdout=subprocess.DEVNULL, stderr=err)
                deadline = time.monotonic() + 10
                while (not firstlog.exists() or 'ARMED' not in firstlog.read_text()) and time.monotonic() < deadline:
                    time.sleep(.02)
                assert firstlog.exists() and 'ARMED' in firstlog.read_text()
                result = subprocess.run(command(log), env=env, stdout=subprocess.DEVNULL, stderr=err, timeout=15)
                assert first.wait(timeout=15) == 4
            else:
                result = subprocess.run(command(log), env=env, stdout=subprocess.DEVNULL, stderr=err, timeout=15)
            events = [json.loads(line) for line in log.read_text().splitlines()]
            if label == 'timeout-reattach':
                secondlog = output / (label + '-second.jsonl')
                second = subprocess.run(command(secondlog), env=env, stdout=subprocess.DEVNULL, stderr=err, timeout=15)
                assert second.returncode == 4
                second_events = [json.loads(line) for line in secondlog.read_text().splitlines()]
                assert second_events[-1]['restored'] and second_events[-1]['detached']
                assert any(event['status'] == 'ARMED' for event in second_events), 'original hardware registers were not restored'
            target_exit = target.wait(timeout=15)
        expected_exit = 0 if mode in (1, 2) and label in ('positive', 'new-thread') else 4 if label == 'timeout-reattach' else 3
        assert result.returncode == expected_exit, (label, result.returncode, events)
        assert target_exit == 0 and Path(str(desc) + '.done').exists(), (label, 'target did not continue/exit cleanly')
        if expected_exit == 0:
            hit = next(event for event in events if event['status'] == 'WRITE')
            assert hit['new_value'] == 0xff000000 and hit['context_read'] and hit['code_read'] and hit['stack_read']
            assert hit['module'].lower() == path.lower()
        if expected_exit in (0, 4) or label == 'existing-hardware':
            assert events[-1]['restored'] and events[-1]['detached'], events
        results.append(dict(case=label, watcher_exit=result.returncode, target_exit=target_exit, events=events))
    proof = dict(status='PASS', scope='standalone owned fixture only; no game writer attribution', cases=results,
                 sha256={name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('watch.exe', 'fixture.exe')})
    (output/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(dict(status=proof['status'], cases=len(results), sha256=proof['sha256'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.prefix)
