"""Bounded replay of genuine protocol9 packets across one real world restart."""
import hashlib
import json
from pathlib import Path
import select
import socket
import threading
import time


def frame(data):
    if len(data) < 57 or len(data) > 65507 or data[:4] != b'\xfe\xff\xff\xff' or int.from_bytes(data[5:9], 'little') != 9:
        return None
    session = int.from_bytes(data[45:53], 'little')
    generation = int.from_bytes(data[53:57], 'little')
    return (data[4], session, generation) if session and generation else None


class ReplayGate:
    """Capture at most one packet per direction/type; never rewrite its tag."""
    TYPES = {'s2c': b'zDNECG', 'c2s': b'zri'}

    def __init__(self):
        self.initial = None
        self.current = None
        self.captured = {}
        self.replayed = False

    def feed(self, direction, data):
        decoded = frame(data)
        if decoded is None:
            return []
        kind, session, generation = decoded
        token = (session, generation)
        if self.initial is None and direction == 's2c' and kind == ord('K'):
            self.initial = token
        if self.initial is None:
            return []
        if token == self.initial and kind in self.TYPES.get(direction, b''):
            self.captured.setdefault((direction, kind), bytes(data))
        if not self.replayed and direction == 'c2s' and kind == ord('r') and session == self.initial[0] and token != self.initial:
            self.current = token
            self.replayed = True
            return [(key[0], key[1], payload) for key, payload in sorted(self.captured.items())]
        return []


class ReplayRelay:
    def __init__(self, host_port, output):
        self.target = ('127.0.0.1', host_port)
        self.down = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.down.bind(('127.0.0.1', 0))
        self.up.bind(('127.0.0.1', 0))
        self.port = self.down.getsockname()[1]
        self.peer = None
        self.gate = ReplayGate()
        self.delivered = False
        self.error = None
        self.counts = {'s2c': 0, 'c2s': 0}
        self.stop = threading.Event()
        self.output = Path(output)
        self.capture = self.output / 'replay-payloads' / str(time.time_ns())
        self.capture.mkdir(parents=True)
        self.log = (self.output / 'world-replay.jsonl').open('w')
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            while not self.stop.is_set():
                ready, _, _ = select.select([self.down, self.up], [], [], 0.1)
                for channel in ready:
                    data, source = channel.recvfrom(65536)
                    if channel is self.down:
                        if self.peer is None:
                            self.peer = source
                        if source != self.peer:
                            continue
                        direction = 'c2s'
                        self.up.sendto(data, self.target)
                    else:
                        if source != self.target or self.peer is None:
                            continue
                        direction = 's2c'
                        self.down.sendto(data, self.peer)
                    replay = self.gate.feed(direction, data)
                    if not replay:
                        continue
                    for route, kind, payload in replay:
                        if route == 'c2s':
                            self.up.sendto(payload, self.target)
                        else:
                            self.down.sendto(payload, self.peer)
                        self.counts[route] += 1
                        path = self.capture / ('%s-%02x.bin' % (route, kind))
                        path.write_bytes(payload)
                        self.log.write(json.dumps({'direction': route, 'type': chr(kind), 'bytes': len(payload),
                                                   'sha256': hashlib.sha256(payload).hexdigest(),
                                                   'old_world': self.gate.initial, 'new_world': self.gate.current,
                                                   'payload_path': str(path)}) + '\n')
                        self.log.flush()
                    self.delivered = True
        except (OSError, ValueError) as error:
            self.error = str(error)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        self.down.close()
        self.up.close()
        self.log.close()
