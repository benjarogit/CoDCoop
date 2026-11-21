"""Owned localhost QA relay: delay only DObjs after a checkpoint gamestate."""
import hashlib
import select
import socket
import threading
import time

CTRL = b'\xfe\xff\xff\xff'

class Gate:
    def __init__(self, delay):
        if not 0 < delay <= 5: raise ValueError('QA DObj delay must be0..5 seconds')
        self.delay = delay
        self.reload_seen = False
        self.armed = False
        self.until = 0
    def verdict(self, data, direction, now):
        kind = chr(data[4]) if len(data) >= 5 and data[:4] == CTRL else None
        if direction == 's2c':
            if kind == 'R': self.reload_seen = True
            if kind == 'G' and self.reload_seen and not self.armed:
                self.armed = True
                self.until = now + self.delay
            if kind == 'D' and self.armed and now < self.until: return kind, 'drop'
        return kind, 'forward'

class OwnedRelay:
    def __init__(self, target, delay):
        self.target = target
        self.gate = Gate(delay)
        self.peer_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.host_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        for sock in (self.peer_socket,self.host_socket): sock.bind(('127.0.0.1',0))
        self.port = self.peer_socket.getsockname()[1]
        self.peer = None
        self.records = []
        self.started = time.monotonic()
        self.running = True
        self.thread = threading.Thread(target=self._run,daemon=True)
        self.thread.start()
    def _run(self):
        while self.running:
            ready,_,_ = select.select([self.peer_socket,self.host_socket],[],[],.1)
            for sock in ready:
                data,address = sock.recvfrom(65535)
                direction = 'c2s' if sock is self.peer_socket else 's2c'
                if direction == 'c2s': self.peer = address
                now = time.monotonic()
                kind,verdict = self.gate.verdict(data,direction,now)
                if kind in ('R','G','D'):
                    self.records.append({'elapsed_ms':(now-self.started)*1000,'direction':direction,'kind':kind,
                        'verdict':verdict,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
                if verdict == 'drop': continue
                if direction == 'c2s': self.host_socket.sendto(data,self.target)
                elif self.peer: self.peer_socket.sendto(data,self.peer)
    def close(self):
        self.running = False
        self.thread.join(2)
        for sock in (self.peer_socket,self.host_socket):sock.close()
    def evidence(self):
        return {'delay_seconds':self.gate.delay,'armed_after_reload':self.gate.armed,
                'dropped_dobjs':sum(r['kind']=='D' and r['verdict']=='drop' for r in self.records),
                'records':self.records}
