"""Owned localhost bootstrap ordering/loss observation; no game state writes."""
import select
import socket
import struct
import threading
import time
import json

CTRL=b'\xfe\xff\xff\xff'
HEADER=57


def describe(data):
    if len(data)<HEADER or data[:4]!=CTRL:return None
    kind=data[4]
    if kind not in (0xb0,0xb1,0xb2,0xb3,ord('H'),ord('K'),ord('M'),ord('J'),ord('A'),ord('G'),ord('D')):return None
    value={'type':kind,'bytes':len(data),'session':struct.unpack_from('<Q',data,45)[0],'world':struct.unpack_from('<I',data,53)[0]}
    if kind==0xb2 and len(data)>=HEADER+6:
        value.update(serial=struct.unpack_from('<I',data,57)[0],part=struct.unpack_from('<H',data,61)[0])
    elif kind==0xb3 and len(data)==HEADER+41:
        value.update(serial=struct.unpack_from('<I',data,57)[0],nonce=struct.unpack_from('<I',data,61)[0],phase=data[65])
    return value


class OwnedBootstrapRelay:
    def __init__(self,target,drop_first_part=False,initial_dobj_delay=0,strip_ready_capability=False,invalid_ack_host=None,corrupt_first_part=False):
        if target[0]!='127.0.0.1' or not 0<target[1]<65536:raise ValueError('owned localhost target required')
        if not 0<=initial_dobj_delay<=5:raise ValueError('bounded initial DObj delay required')
        self.target=target;self.drop_first_part=drop_first_part;self.dropped=False
        self.initial_dobj_delay=initial_dobj_delay;self.dobj_until=0
        self.strip_ready_capability=strip_ready_capability;self.stripped=0
        self.invalid_ack_host=invalid_ack_host;self.ack_until=0;self.ack_injected=[];self.ack_guard_samples=[]
        self.corrupt_first_part=corrupt_first_part;self.corrupted=False
        self.front=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.back=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        for sock in (self.front,self.back):sock.bind(('127.0.0.1',0))
        self.port=self.front.getsockname()[1];self.peer=None;self.running=True;self.records=[];self.errors=[];self.started=time.monotonic()
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()

    def _run(self):
        try:
            while self.running:
                ready,_,_=select.select([self.front,self.back],[],[],.1)
                for sock in ready:
                    data,address=sock.recvfrom(65535)
                    if sock is self.front:
                        if self.peer is None:self.peer=address
                        if address!=self.peer:continue
                        direction='c2s';target=self.target;sender=self.back
                    else:
                        if address!=self.target or self.peer is None:continue
                        direction='s2c';target=self.peer;sender=self.front
                    item=describe(data);drop=False
                    if item:
                        if self.corrupt_first_part and not self.corrupted and direction=='s2c' and item['type']==0xb2 and len(data)>HEADER+6:
                            altered=bytearray(data);altered[HEADER+6]^=0x01;data=altered;self.corrupted=True;item['corrupted_payload']=True
                        if self.invalid_ack_host and direction=='c2s' and item['type']==0xb3 and item.get('phase')==2:
                            if not self.ack_until:
                                self.ack_until=time.monotonic()+1.5
                                for label,offset in (('wrong_nonce',61),('wrong_digest',66),('wrong_world',53)):
                                    altered=bytearray(data);altered[offset]^=0x40;sender.sendto(altered,target);self.ack_injected.append(label)
                                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as stranger:
                                    stranger.bind(('127.0.0.1',0));stranger.sendto(data,self.target);self.ack_injected.append('wrong_socket')
                            if time.monotonic()<self.ack_until:
                                drop=True
                                try:
                                    state=json.loads(self.invalid_ack_host.read_text())
                                    self.ack_guard_samples.append({'active':[p['active'] for p in state['players'][1:]],'seconds':time.monotonic()-self.started})
                                except (OSError,ValueError,KeyError):pass
                        if self.strip_ready_capability and direction=='s2c' and item['type']==ord('K') and len(data)==HEADER+6:
                            data=data[:HEADER];self.stripped+=1;item['removed_capability_bytes']=6
                        if direction=='s2c' and item['type']==ord('G') and not self.dobj_until and self.initial_dobj_delay:self.dobj_until=time.monotonic()+self.initial_dobj_delay
                        if direction=='s2c' and item['type']==ord('D') and time.monotonic()<self.dobj_until:drop=True
                        if self.drop_first_part and not self.dropped and direction=='s2c' and item['type']==0xb2:
                            drop=True;self.dropped=True
                        item.update(direction=direction,seconds=time.monotonic()-self.started,dropped=drop)
                        if len(self.records)<5000:self.records.append(item)
                    if not drop:sender.sendto(data,target)
        except OSError as error:
            if self.running:self.errors.append(repr(error))

    def close(self):
        self.running=False;self.thread.join(timeout=2);self.front.close();self.back.close()

    def evidence(self):return {'records':list(self.records),'errors':list(self.errors),'dropped_first_part':self.dropped,'corrupted_first_part':self.corrupted,'stripped_capabilities':self.stripped,'invalid_acks':self.ack_injected,'ack_guard_samples':self.ack_guard_samples}


def verify_order(records,allow_pending_join_probe=False):
    delivered=[r for r in records if not r.get('dropped')]
    def first(direction,kind,phase=None):
        return next((i for i,r in enumerate(delivered) if r['direction']==direction and r['type']==kind and (phase is None or r.get('phase')==phase)),None)
    transfer=first('c2s',0xb3,1);native=first('c2s',0xb3,2);mapping=first('s2c',ord('M'));joining=first('c2s',ord('J'));accept=first('s2c',ord('A'))
    if allow_pending_join_probe and native is not None:
        joining=next((i for i,r in enumerate(delivered) if i>native and r['direction']=='c2s' and r['type']==ord('J')),None)
    return all(v is not None for v in (transfer,native,mapping,joining,accept)) and transfer<mapping<native<joining<accept


def verify_refresh(records):
    for i,old in enumerate(records):
        if old['direction']!='c2s' or old['type']!=0xb0:continue
        for j,ready in enumerate(records[i+1:],i+1):
            if ready['direction']!='s2c' or ready['type']!=ord('K') or ready['session']!=old['session'] or ready['world']<=old['world']:continue
            if any(new['direction']=='c2s' and new['type']==0xb0 and new['session']==ready['session'] and new['world']==ready['world'] for new in records[j+1:]):return True
    return False
