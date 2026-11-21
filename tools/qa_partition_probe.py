#!/usr/bin/env python3
"""Real two-peer map change while the pinned relay drops reload controls.

A PASS requires packet evidence of the bounded partition, a changed map,
automatic reconnection, actual movement and the harness's clean shutdown gate.
No automatic/manual coopjoin command is injected after the interruption.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import socket
import time

import qa_coop as qa


def relay_call(port, method, **params):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    with socket.create_connection(('127.0.0.1', port), timeout=5) as connection:
        connection.sendall((json.dumps(request) + '\n').encode('ascii'))
        with connection.makefile('rb') as stream:
            response = json.loads(stream.readline(65536))
    if response.get('id') != 1 or 'error' in response:
        raise RuntimeError('relay RPC failed: ' + repr(response))
    return response['result']


def partition_evidence(path, direction='s2c'):
    events = [json.loads(line) for line in path.read_text().splitlines() if line]
    controls = [entry for entry in events if entry.get('dir') == 's2c'
                and entry.get('head', '').startswith('feffffff52')]
    dropped = [entry for entry in controls
               if entry.get('verdict') == 'drop'
               and entry.get('reason') == 'partition']
    partitions = [entry for entry in events if entry.get('event') == 'partition'
                  and entry.get('dir') == direction]
    lost_ack = [entry for entry in events if entry.get('dir') == 'c2s'
                and entry.get('head', '').startswith('feffffff74')
                and entry.get('verdict') == 'drop' and entry.get('reason') == 'partition']
    start = next((entry.get('t') for entry in partitions if entry.get('on') is True), None)
    end = next((entry.get('t') for entry in partitions if entry.get('on') is False), None)
    return {'dropped_reload_controls': len(dropped),
            'dropped_reload_acknowledgements': len(lost_ack),
            'reload_controls': len(controls), 'partitions': partitions,
            'observed_partition_ms': None if start is None or end is None else end - start}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--runtime-dir', required=True, type=Path)
    parser.add_argument('--chaos-checkout', required=True, type=Path)
    parser.add_argument('--port', type=int, default=29937)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--recovery-timeout', type=int, default=60)
    parser.add_argument('--partition-direction', choices=('s2c', 'c2s'), default='s2c')
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    report = {'status': 'NOT_RUN', 'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'coverage': 'two-second ' + args.partition_direction + ' partition during actual map change; no campaign completion'}
    original = qa.assess_liveness
    entered = False

    def save():
        (output / 'partition-probe.json').write_text(json.dumps(report, indent=2) + '\n')

    def states():
        return qa.read_state(host), qa.read_state(peer)

    def probe(before, after, count):
        nonlocal entered
        original(before, after, count)
        if entered:
            return
        entered = True
        report['before_partition'] = states()
        info = json.loads((output / 'chaos-info.json').read_text())
        report['partition_ack'] = relay_call(info['rpc'], 'partition', dir=args.partition_direction, on=True, duration_ms=2000)
        report['partition_started_monotonic'] = time.monotonic()
        qa.command(host, 'devmap pathfinder')
        time.sleep(2.5)
        report['packet_evidence'] = partition_evidence(output / 'chaos.jsonl', args.partition_direction)
        save()
        dropped_field = 'dropped_reload_controls' if args.partition_direction == 's2c' else 'dropped_reload_acknowledgements'
        if not report['packet_evidence'][dropped_field]:
            raise RuntimeError('partition did not actually drop the targeted native reload control/ACK; invalid scenario')
        duration = report['packet_evidence']['observed_partition_ms']
        if duration is None or not 1900 <= duration <= 3000:
            raise RuntimeError('relay did not document the bounded two-second partition')

        def recovered():
            h, p = states()
            for folder in (host, peer):
                errors = qa.process_log_errors(folder)
                if errors:
                    raise RuntimeError('native error after partition: ' + errors[0])
            if h and p and h.get('map') == p.get('map') == 'pathfinder' and h.get('role') == 1 and p.get('role') == 2 and p.get('joined') and p.get('snapshot_num', 0) > 0 and h['players'][1]['active']:
                return h, p

        live = qa.wait_for(recovered, [], args.recovery_timeout, 'automatic reconnection after dropped reload controls')
        time.sleep(2)
        final = recovered()
        if not final:
            raise RuntimeError('peer lost the recovered world')
        original(live[0], final[0], count)
        qa.wait_for(lambda: qa.read_state(host)['players'][1].get('pm_type') == 0 and not qa.read_state(host)['players'][1].get('linked'), [], args.timeout, 'remote controllable after partition')
        origin = qa.read_state(host)['players'][1]['position']
        qa.command(peer, '+forward', joiner=True)
        try:
            qa.wait_for(lambda: qa.read_state(host)['players'][1].get('forward', 0) > 0, [], 10, 'recovered host receives actual input')
            time.sleep(0.8)
        finally:
            qa.command(peer, '-forward', joiner=True)
        distance = math.dist(origin, qa.read_state(host)['players'][1]['position'])
        if distance < 5:
            raise RuntimeError('remote failed actual movement after partition')
        peer_log = (peer / 'codcoop_join.log').read_text(errors='replace')
        reload_count = peer_log.count('joiner: el host carga pathfinder (nivel nuevo)')
        if reload_count != 1:
            raise RuntimeError('peer did not process exactly one map change: ' + str(reload_count))
        report.update(status='PASS', recovered=final, movement_units=distance, peer_map_change_count=reload_count)
        save()

    qa.assess_liveness = probe
    try:
        result = qa.main(['--source', str(args.source.resolve()), '--run', str(output),
                          '--runtime-dir', str(args.runtime_dir.resolve()), '--variant', 'sp_improved',
                          '--map', 'training', '--players', '2', '--duration', '5',
                          '--port', str(args.port), '--timeout', str(args.timeout),
                          '--chaos-checkout', str(args.chaos_checkout.resolve()), '--chaos-profile', 'lan'])
        if result:
            report['status'] = 'FAIL'
            report['last_states'] = states()
        packet_log = output / 'chaos.jsonl'
        if packet_log.exists():
            report['final_packet_evidence'] = partition_evidence(packet_log, args.partition_direction)
        save()
        return result
    finally:
        qa.assess_liveness = original


if __name__ == '__main__':
    raise SystemExit(main())
