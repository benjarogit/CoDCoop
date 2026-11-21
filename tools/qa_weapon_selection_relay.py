"""Owned localhost protocol9 relay for actual selection replay negatives.

Passes every original datagram unchanged. Only explicit replay() injects a copy
of a genuinely captured host request through the authenticated relay endpoint.
"""
import hashlib
import select
import socket
import struct
import threading
import time

CTRL=b'\xfe\xff\xff\xff'
HEADER=57


def request(data):
    if len(data)!=HEADER+76 or data[:5]!=CTRL+b's' or struct.unpack_from('<I',data,5)[0]!=9:
        return None
    return {'session':struct.unpack_from('<Q',data,45)[0],
            'world':struct.unpack_from('<I',data,53)[0],
            'serial':struct.unpack_from('<I',data,57)[0],
            'ticket':struct.unpack_from('<I',data,61)[0],
            'weapon':struct.unpack_from('<H',data,65)[0],
            'slot':data[67]}


def replay_packet(data,mode):
    found=request(data)
    if found is None:raise ValueError('expected genuine bounded protocol9 selection request')
    result=bytearray(data)
    if mode=='duplicate':pass
    elif mode=='wrong_ticket':struct.pack_into('<I',result,61,found['ticket']+1 if found['ticket']<0x7fffffff else 1)
    elif mode=='wrong_world':struct.pack_into('<I',result,53,(found['world']+1)&0xffffffff or 1)
    elif mode=='wrong_session':struct.pack_into('<Q',result,45,found['session']^1 or 2)
    else:raise ValueError('unsupported explicit QA replay mode')
    return bytes(result)


def strip_accept_capability(data):
    if len(data)>HEADER+8 and data[:5]==CTRL+b'A' and struct.unpack_from('<I',data,5)[0]==9 and struct.unpack_from('<I',data,len(data)-8)[0]==0x57534c31:
        return data[:-8]
    return data


class OwnedSelectionRelay:
    def __init__(self,target,strip_capability=False):
        if target[0]!='127.0.0.1' or not 0<target[1]<65536:raise ValueError('owned localhost target required')
        self.target=target
        self.strip_capability=strip_capability
        self.peer_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.host_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        for sock in (self.peer_socket,self.host_socket):sock.bind(('127.0.0.1',0))
        self.port=self.peer_socket.getsockname()[1]
        self.peer=None;self.packets=[];self.records=[];self.errors=[];self.running=True
        self.lock=threading.Lock();self.started=time.monotonic()
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()

    def _run(self):
        try:
            while self.running:
                ready,_,_=select.select([self.peer_socket,self.host_socket],[],[],.1)
                for sock in ready:
                    data,address=sock.recvfrom(65535)
                    if sock is self.peer_socket:
                        if self.peer is None:self.peer=address
                        if address!=self.peer:continue
                        self.host_socket.sendto(data,self.target)
                    elif address==self.target and self.peer:
                        found=request(data)
                        if found:
                            with self.lock:
                                if not self.packets or self.packets[-1]!=data:
                                    if len(self.packets)>=128:raise RuntimeError('selection capture bound exceeded')
                                    self.packets.append(data)
                                    self.records.append(dict(found,kind='captured',sha256=hashlib.sha256(data).hexdigest()))
                        if self.strip_capability:
                            stripped=strip_accept_capability(data)
                            if stripped!=data:
                                self.records.append({'kind':'capability_stripped','original_sha256':hashlib.sha256(data).hexdigest(),
                                                     'forwarded_sha256':hashlib.sha256(stripped).hexdigest(),'removed_bytes':8})
                                data=stripped
                        self.peer_socket.sendto(data,self.peer)
        except (OSError,RuntimeError) as error:
            if self.running:self.errors.append(str(error))

    def latest(self):
        with self.lock:return self.packets[-1] if self.packets else None

    def replay(self,mode,packet=None):
        if not self.running or not self.thread.is_alive() or self.errors:raise RuntimeError('selection relay is not healthy')
        packet=packet if packet is not None else self.latest()
        if packet is None or self.peer is None:raise RuntimeError('no actual host selection has been captured')
        data=replay_packet(packet,mode)
        self.peer_socket.sendto(data,self.peer)
        self.records.append(dict(request(data),kind='injected',mode=mode,sha256=hashlib.sha256(data).hexdigest(),
                                 elapsed_ms=(time.monotonic()-self.started)*1000))

    def evidence(self):
        with self.lock:return {'errors':list(self.errors),'records':list(self.records),
                               'captured_packets_hex':[data.hex() for data in self.packets]}

    def close(self):
        self.running=False;self.thread.join(2)
        for sock in (self.peer_socket,self.host_socket):sock.close()
