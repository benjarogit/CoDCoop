#!/usr/bin/env python3
"""CoDCoop UDP over two simulated homes, using isolated Linux network namespaces."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HOST_LAN = '10.61.1.2'
HOST_WAN = '198.18.61.1'
JOIN_WAN = '198.18.61.2'
HOST_TUNNEL = '100.64.61.1'
JOIN_TUNNEL = '100.64.61.2'
TUNNEL_PORT = 51820


class HomeNetworks:
    def __init__(self, cleanup, port, wan_port, transport):
        self.port = port
        self.wan_port = wan_port
        self.transport = transport
        self.nodes = [self.namespace(cleanup) for _ in range(4)]
        self.host, self.host_router, self.joiner, self.join_router = self.nodes
        self.run(['ip', 'link', 'add', 'wan', 'type', 'bridge'])
        self.run(['ip', 'addr', 'add', '198.18.61.254/24', 'dev', 'wan'])
        self.run(['ip', 'link', 'set', 'wan', 'up'])
        for router, node, subnet, public in (
                (self.host_router, self.host, '10.61.1', HOST_WAN),
                (self.join_router, self.joiner, '10.61.2', JOIN_WAN)):
            self.link(node, 'lan', router, 'inside')
            self.link(None, f'edge{router}', router, 'outside')
            self.run(['ip', 'link', 'set', f'edge{router}', 'master', 'wan'])
            for pid, dev, addr in ((node, 'lan', f'{subnet}.2/24'),
                                   (router, 'inside', f'{subnet}.1/24'),
                                   (router, 'outside', f'{public}/24')):
                self.run(['ip', 'addr', 'add', addr, 'dev', dev], pid)
            self.run(['ip', 'route', 'add', 'default', 'via', f'{subnet}.1'], node)
            self.run(['sysctl', '-qw', 'net.ipv4.ip_forward=1'], router)
            self.rules(router, '''table ip home {
 chain inbound { type nat hook prerouting priority dstnat; }
 chain outbound { type nat hook postrouting priority srcnat; oifname "outside" masquerade; }
 chain forward { type filter hook forward priority filter; policy drop;
   ct state established,related accept
   iifname "inside" oifname "outside" accept
 }
}''')

    @staticmethod
    def namespace(cleanup):
        process = subprocess.Popen(['unshare', '--net', 'sleep', 'infinity'])
        cleanup.callback(HomeNetworks.stop, process)
        ns = Path(f'/proc/{process.pid}/ns/net')
        parent = os.readlink('/proc/self/ns/net')
        until = time.monotonic() + 3
        while time.monotonic() < until and process.poll() is None:
            if os.readlink(ns) != parent:
                HomeNetworks.run(['ip', 'link', 'set', 'lo', 'up'], process.pid)
                return process.pid
            time.sleep(.02)
        raise RuntimeError('Unable to create a home network namespace')

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)

    @staticmethod
    def prefix(pid):
        return ['nsenter', '--net', '--target', str(pid), '--'] if pid is not None else []

    @staticmethod
    def run(args, pid=None, **kwargs):
        return subprocess.run(HomeNetworks.prefix(pid) + args, check=True, **kwargs)

    def rules(self, pid, rules):
        self.run(['nft', '-f', '-'], pid, input=rules, text=True)

    def link(self, left, name, right, peer):
        args = ['ip', 'link', 'add', name]
        if left is not None:
            args += ['netns', str(left)]
        self.run(args + ['type', 'veth', 'peer', 'name', peer, 'netns', str(right)])
        self.run(['ip', 'link', 'set', name, 'up'], left)
        self.run(['ip', 'link', 'set', peer, 'up'], right)

    def player_prefix(self, index):
        return self.prefix(self.host if index == 0 else self.joiner)

    @property
    def target(self):
        if self.transport == 'wireguard':
            return HOST_TUNNEL, self.port
        return HOST_WAN, self.wan_port

    @property
    def scope(self):
        return 'simulated-separate-nat-' + self.transport

    def forward(self, public_port, local_port):
        self.rules(self.host_router, f'add rule ip home inbound iifname "outside" udp dport {public_port} '
                                    f'dnat to {HOST_LAN}:{local_port}\n'
                                    f'add rule ip home forward iifname "outside" oifname "inside" '
                                    f'ip daddr {HOST_LAN} udp dport {local_port} accept\n')

    def allow(self, interface, port):
        self.rules(self.host, f'add rule ip host_filter inbound iifname "{interface}" udp dport {port} accept\n')

    def configure_wireguard(self):
        keys = [self.run(['wg', 'genkey'], capture_output=True, text=True).stdout for _ in range(2)]
        public = [self.run(['wg', 'pubkey'], input=key, capture_output=True, text=True).stdout.strip()
                  for key in keys]
        for index, (pid, address, other_address) in enumerate(
                ((self.host, HOST_TUNNEL, JOIN_TUNNEL), (self.joiner, JOIN_TUNNEL, HOST_TUNNEL))):
            self.run(['ip', 'link', 'add', 'qa-wg', 'type', 'wireguard'], pid)
            setting = ['listen-port', str(TUNNEL_PORT)] if index == 0 else []
            endpoint = ['endpoint', f'{HOST_WAN}:{TUNNEL_PORT}'] if index == 1 else []
            self.run(['wg', 'set', 'qa-wg', 'private-key', '/dev/stdin', *setting, 'peer', public[1 - index],
                      'allowed-ips', f'{other_address}/32', *endpoint], pid, input=keys[index], text=True)
            self.run(['ip', 'addr', 'add', f'{address}/32', 'dev', 'qa-wg'], pid)
            self.run(['ip', 'link', 'set', 'qa-wg', 'up'], pid)
            self.run(['ip', 'route', 'add', f'{other_address}/32', 'dev', 'qa-wg'], pid)
        self.forward(TUNNEL_PORT, TUNNEL_PORT)
        self.allow('lan', TUNNEL_PORT)
        self.allow('qa-wg', self.port)

    def send_from_unallocated_socket(self, payload):
        self.run([sys.executable, '-c',
                  'import socket, sys; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); '
                  's.sendto(bytes.fromhex(sys.argv[1]), (sys.argv[2], int(sys.argv[3])))',
                  payload.hex(), self.target[0], str(self.target[1])], self.joiner, timeout=5)

    def probe(self):
        server = '''import socket, sys
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(('0.0.0.0', int(sys.argv[1])))
    print('ready', flush=True)
    while True:
        payload, peer = sock.recvfrom(128)
        sock.sendto(peer[0].encode() + b':' + payload, peer)
'''
        client = '''import socket, sys
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.settimeout(0.7)
    sock.sendto(b'coop-network-check', (sys.argv[1], int(sys.argv[2])))
    try:
        received, peer = sock.recvfrom(128)
        print(peer[0] + ' ' + received.decode())
    except TimeoutError:
        print('blocked')
'''
        with ExitStack() as cleanup:
            echo = subprocess.Popen(self.prefix(self.host) + [sys.executable, '-c', server, str(self.port)],
                                    stdout=subprocess.PIPE, text=True)
            cleanup.callback(self.stop, echo)
            if echo.stdout.readline() != 'ready\n':
                raise RuntimeError('LAN echo server did not bind')
            def send(address, port):
                return self.run([sys.executable, '-c', client, address, str(port)], self.joiner,
                                capture_output=True, text=True, timeout=5).stdout.strip()

            if send(HOST_WAN, self.wan_port) != 'blocked':
                raise RuntimeError('UDP reached the host before port forwarding')
            self.rules(self.host, '''table ip host_filter {
 chain inbound { type filter hook input priority filter; policy drop;
   iifname "lo" accept
 }
}''')
            checks = ['game UDP blocked without a host port forward']
            if self.transport == 'direct':
                self.forward(self.wan_port, self.port)
                if send(*self.target) != 'blocked':
                    raise RuntimeError('Port forwarding bypassed the host firewall')
                self.allow('lan', self.port)
                if send(*self.target) != f'{HOST_WAN} {JOIN_WAN}:coop-network-check':
                    raise RuntimeError('UDP did not cross both NAT routers with the expected translated addresses')
                checks += ['forwarded UDP blocked by the host firewall',
                           'bidirectional UDP with source NAT and destination IP/port translation']
            else:
                self.configure_wireguard()
                if not any(send(*self.target) == f'{HOST_TUNNEL} {JOIN_TUNNEL}:coop-network-check'
                           for _ in range(3)):
                    raise RuntimeError('UDP did not reach the WireGuard peer and return')
                if any(send(HOST_WAN, port) != 'blocked' for port in {self.port, self.wan_port}):
                    raise RuntimeError('The public game port is reachable outside the VPN')
                checks += ['bidirectional game UDP over WireGuard',
                           'public game UDP still blocked with the tunnel active']
        return {'status': 'PASS', 'topology': 'two-home-networks', 'isolation': 'Linux network namespaces',
                'transport': self.transport, 'checks': checks, 'host_lan': HOST_LAN,
                'host_wan': HOST_WAN, 'joiner_wan': JOIN_WAN, 'join_address': list(self.target),
                'game_port': self.port, 'forwarded_udp_port': self.wan_port if self.transport == 'direct' else TUNNEL_PORT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=28960)
    parser.add_argument('--wan-port', type=int, default=3202)
    parser.add_argument('--transport', choices=('direct', 'wireguard'), default='direct')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('game_args', nargs=argparse.REMAINDER, help='optional qa_coop.py arguments after --')
    args = parser.parse_args()
    if not all(1024 <= port <= 65535 for port in (args.port, args.wan_port)):
        parser.error('ports must be between 1024 and 65535')
    if args.transport == 'wireguard' and TUNNEL_PORT in (args.port, args.wan_port):
        parser.error('the game ports must differ from the WireGuard listener')
    links = json.loads(subprocess.check_output(['ip', '-j', 'link']))
    if os.geteuid() != 0 or [link['ifname'] for link in links] != ['lo']:
        parser.error('start under unshare --user --map-root-user --net')
    game_args = args.game_args[1:] if args.game_args[:1] == ['--'] else args.game_args
    with ExitStack() as cleanup:
        try:
            network = HomeNetworks(cleanup, args.port, args.wan_port, args.transport)
            proof = network.probe()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            proof = {'status': 'FAIL', 'topology': 'two-home-networks',
                     'transport': args.transport, 'error': str(error)}
            args.report.write_text(json.dumps(proof, indent=2) + '\n')
            print(f'Home-network probe failed: {error}', file=sys.stderr)
            return 1
        args.report.write_text(json.dumps(proof, indent=2) + '\n')
        if game_args:
            import qa_coop
            return qa_coop.main([*game_args, '--port', str(args.port)], network=network)
    return 0


if __name__ == '__main__':
    sys.exit(main())
