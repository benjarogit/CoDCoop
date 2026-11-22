"""Worker half of an asynchronous, fixed-path native party proof bridge.

IDL is private/draft until the native counterpart is integrated and tested.
This module never grants equipment runtime readiness. A worker approval only
answers ONE native pending challenge; Native must independently enforce its
monotone deadline, consume the ACK once and perform allocation/kit ownership.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from coop_party import atomic_private, canonical
import uf_equipment_roster as roster

IDL = 'coop-party-native-1'
MAX_LOCAL_BYTES = 131072
MAX_PENDING = 3  # remote pending index; not the assigned native player slot
MAX_TTL_MS = 30000
HEX64 = re.compile('[0-9a-f]{64}')
CHALLENGE_FIELDS = {'schema','kind','pending_index','nonce','client_join_nonce','native_session','native_world','challenge_serial',
                    'engine','variant','map','client_target','client_endpoint','party_session','catalog_sha256',
                    'package_sha256','world_sha256','member_guid','roster_revision','plan_sha256',
                    'resource_sha256','created_unix_ms','expires_unix_ms'}
CONTEXT_FIELDS = ('native_session','native_world','engine','variant','map','party_session',
                  'catalog_sha256','package_sha256','world_sha256','roster_revision','plan_sha256','resource_sha256')


def hex_value(value, count):
    return isinstance(value,str) and len(value)==count and all(c in '0123456789abcdef' for c in value)


def endpoint(value):
    if not isinstance(value,str) or len(value)>21: raise ValueError('Invalid IPv4 native endpoint')
    match=re.fullmatch(r'(\d{1,3}(?:\.\d{1,3}){3}):([1-9]\d{0,4})',value)
    if not match: raise ValueError('Invalid IPv4 native endpoint')
    octets=match[1].split('.')
    if any(str(int(part))!=part or int(part)>255 for part in octets) or not 1<=int(match[2])<=65535:
        raise ValueError('Invalid IPv4 native endpoint')
    return value


def validate_challenge(value, now_ms=None):
    if not isinstance(value,dict) or set(value)!=CHALLENGE_FIELDS or type(value['schema']) is not int or value['schema']!=1 or value['kind']!=IDL:
        raise ValueError('Unsupported native party challenge')
    if type(value['pending_index']) is not int or not 0<=value['pending_index']<MAX_PENDING:
        raise ValueError('Invalid native pending index')
    for field in ('nonce','client_join_nonce','party_session','catalog_sha256','package_sha256','world_sha256','member_guid','plan_sha256','resource_sha256'):
        if not hex_value(value[field],64): raise ValueError('Invalid native challenge digest or nonce')
    if not hex_value(value['challenge_serial'],16) or value['challenge_serial']=='0'*16:raise ValueError('Invalid native challenge serial')
    if not hex_value(value['native_session'],16) or not hex_value(value['native_world'],8):raise ValueError('Invalid native world identity')
    if value['nonce']=='0'*64 or value['client_join_nonce']=='0'*64:raise ValueError('Missing native unpredictable nonce')
    if value['native_session']=='0'*16 or value['native_world']=='0'*8:raise ValueError('Missing native world identity')
    if value['engine']!='uo' or value['variant']!='united_fronts' or not isinstance(value['map'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,63}',value['map']):
        raise ValueError('Unsupported native party mission')
    endpoint(value['client_target']);endpoint(value['client_endpoint'])
    if type(value['roster_revision']) is not int or not 1<=value['roster_revision']<=0x7fffffff:raise ValueError('Invalid party revision')
    created,expires=value['created_unix_ms'],value['expires_unix_ms']
    if (type(created) is not int or type(expires) is not int or not 0<created<2**53 or
            not created<expires<2**53 or (now_ms is not None and not created<=now_ms<expires) or not 0<expires-created<=MAX_TTL_MS):
        raise ValueError('Expired or future native challenge')
    return deepcopy(value)


def encode_resources(resources):
    """Exact asset_bootstrap::EncodeResources bytes, not a package/plan digest."""
    if not isinstance(resources,dict) or set(resources)!={'models','weapons'}:raise ValueError('Invalid native resource inventory')
    models=resources['models'];weapons=resources['weapons']
    if not isinstance(models,list) or not 1<=len(models)<=512 or not isinstance(weapons,list) or len(weapons)>127:raise ValueError('Invalid native resource count')
    for model in models:
        if (not isinstance(model,str) or not 7<len(model)<64 or not model.startswith('xmodel/') or '..' in model or '//' in model or model.endswith('/') or not re.fullmatch('[A-Za-z0-9_/()\\-]+',model)):
            raise ValueError('Invalid native model name')
    canonical_models=sorted(set(model.lower() for model in models))
    model_text=''.join(model+'\n' for model in canonical_models)
    if len(model_text)>32768:raise ValueError('Native model inventory exceeds limit')
    text='codcoop-assets-1\n'+''.join('m\t'+model+'\n' for model in canonical_models);seen=set()
    for index,weapon in enumerate(weapons,1):
        if (not isinstance(weapon,dict) or set(weapon)!={'index','name','registered'} or type(weapon['index']) is not int or weapon['index']!=index or
                type(weapon['registered']) is not bool or not isinstance(weapon['name'],str) or not re.fullmatch('[a-z0-9_-]{1,63}',weapon['name']) or weapon['name']=='none' or weapon['name'] in seen):
            raise ValueError('Native weapon index/registration mismatch')
        seen.add(weapon['name']);text+=f"w\t{index:03d}\t{int(weapon['registered'])}\t{weapon['name']}\n"
    encoded=text.encode('ascii')
    if len(encoded)>49152:raise ValueError('Native resource inventory exceeds limit')
    return encoded


class FixedFiles:
    def __init__(self, game):
        self.root=Path(game).absolute()/'coop'/'party-bridge'
    def path(self,name):
        if not re.fullmatch(r'(?:host-[012]|ack-[012]|client|host-ready|party)\.json',name):raise ValueError('Unknown bridge path')
        for path in (self.root.parent,self.root):
            if path.is_symlink() or (path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Native bridge directory cannot be a symlink')
            if path.exists() and (not path.is_dir() or (os.name!='nt' and (path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o022))):
                raise ValueError('Native bridge directory is not owned safely')
        result=self.root/name
        if result.is_symlink() or (result.exists() and getattr(result.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Native bridge record cannot be a symlink')
        return result
    def read(self,name):
        path=self.path(name)
        flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0)
        fd=os.open(path,flags)
        try:
            info=os.fstat(fd)
            if getattr(info,'st_file_attributes',0)&0x400 or not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=MAX_LOCAL_BYTES or (os.name!='nt' and (info.st_uid!=os.getuid() or info.st_mode&0o022)):
                raise ValueError('Unsafe native bridge record')
            with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(MAX_LOCAL_BYTES+1)
            if len(data)!=info.st_size or len(data)>MAX_LOCAL_BYTES:raise ValueError('Native bridge record changed during read')
            def unique(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise ValueError('Duplicate native bridge field')
                    result[key]=value
                return result
            value=json.loads(data,object_pairs_hook=unique)
            if not isinstance(value,dict):raise ValueError('Invalid native bridge record')
            return value
        finally:os.close(fd)
    def write(self,name,value):
        path=self.path(name);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        atomic_private(path,value)


class NativeSerialLedger:
    """Three per-index highwater records; no lifetime nonce-count budget.

    activate() is called only after a matching trusted local Native record is
    checked. Network fields never select/reset the native session epoch.
    Native globally increasing serials also increase independently per index;
    therefore lower serials on OTHER live indices remain valid out of order.
    """
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.session=None;self.records=[None]*MAX_PENDING
    def activate(self,native_session):
        if not hex_value(native_session,16) or native_session=='0'*16:raise ValueError('Invalid trusted native session')
        if native_session!=self.session:
            self.session=native_session;self.records=[None]*MAX_PENDING
    def admit(self,challenge,first_seen=None):
        if challenge['native_session']!=self.session:raise ValueError('Untrusted native serial epoch')
        index=challenge['pending_index'];serial=int(challenge['challenge_serial'],16)
        if type(index) is not int or not 0<=index<MAX_PENDING or serial<=0:raise ValueError('Invalid native serial index')
        digest=hashlib.sha256(canonical(challenge)).hexdigest();before=self.records[index]
        if before is not None:
            if serial<before['serial']:raise ValueError('Retired native challenge serial')
            if serial==before['serial']:
                if digest!=before['digest']:raise ValueError('Native reused a serial for a conflicting challenge')
                if self.clock()-before['seen']>MAX_TTL_MS/1000:raise ValueError('Native monotone worker deadline elapsed')
                return before
        # A higher locally issued serial on this index retires the previous
        # descriptor, even while other indices still have older live serials.
        seen=self.clock() if first_seen is None else min(self.clock(),first_seen)
        record={'serial':serial,'digest':digest,'seen':seen,'consumed':False}
        self.records[index]=record
        return record


class NativePartyBridge:
    def __init__(self,node,game,wall_clock=time.time,clock=time.monotonic):
        self.node=node;self.files=FixedFiles(game);self.wall_clock=wall_clock;self.clock=clock
        self.pending={};self.ledger=NativeSerialLedger(clock);self.latest_plan=None;self.last_error=None;self.last_context_write=0
        self.stats={'challenges':0,'proofs':0,'approvals':0,'rejected':0}
    def now_ms(self):return int(self.wall_clock()*1000)
    def current(self):
        node=self.node;snapshot=node.snapshot
        if node.cancelled or snapshot is None:raise ValueError('No active authenticated party')
        members={m['slot']:m['guid'] for m in node.latest_view['members']} if node.hosting else {m['slot']:m['guid'] for m in node.public_view['members']}
        view=node.latest_view if node.hosting else node.public_view
        if view['status']!='connected' or sorted(view['confirmed_slots'])!=sorted(m['slot_id'] for m in snapshot['members']):raise ValueError('Waiting for all current owner confirmations')
        if snapshot['unresolved_automatic_slots']:raise ValueError('Original automatic equipment is not natively resolved')
        return snapshot,members
    def current_plan(self,snapshot):
        # Rebuild the EXACT canonical plan on both host and peer. The peer
        # projection contains authenticated own-kit submissions; readiness is
        # deliberately not a native approval and is excluded from the plan.
        state={'schema':snapshot['schema'],'catalog_sha256':snapshot['catalog_sha256'],
               'host_slot':snapshot['host_slot'],'world':deepcopy(snapshot['world']),
               'members':[{'slot_id':m['slot_id'],'kit':deepcopy(m['kit'])} for m in snapshot['members']],
               'revision':snapshot['revision'],'ready_slots':[],'resource_approval':None}
        plan=roster.plan(state,self.node.catalog)
        if plan['plan_sha256']!=snapshot['plan_sha256']:
            raise ValueError('Authenticated roster does not match its canonical plan')
        return plan
    def matches_party(self,challenge):
        snapshot,members=self.current()
        expected={'party_session':self.node.invitation['session'],'catalog_sha256':snapshot['catalog_sha256'],'package_sha256':snapshot['world']['package_id'],
                  'world_sha256':roster.identity(snapshot['world']),'plan_sha256':snapshot['plan_sha256'],'roster_revision':snapshot['revision'],
                  'engine':'uo','variant':snapshot['world']['variant'],'map':snapshot['world']['map']}
        if any(challenge[field]!=value for field,value in expected.items()):raise ValueError('Native challenge differs from current confirmed party/world/plan')
        if challenge['member_guid'] not in members.values():raise ValueError('Native challenge names an unknown party owner')
        if challenge['member_guid']==members[0]:raise ValueError('Host native slot0 cannot be a remote join owner')
        return snapshot,members
    def host_ready(self,challenge):
        ready=self.files.read('host-ready.json')
        if set(ready)!={'schema','kind','phase','context','resources'} or type(ready['schema']) is not int or ready['schema']!=1 or ready['kind']!=IDL or type(ready['phase']) is not int or ready['phase']!=2:
            raise ValueError('Native phase2 resource context is unavailable')
        if not isinstance(ready['context'],dict) or set(ready['context'])!=set(CONTEXT_FIELDS) or any(ready['context'][key]!=challenge[key] for key in CONTEXT_FIELDS):
            raise ValueError('Native phase2 context mismatch')
        encoded=encode_resources(ready['resources'])
        if hashlib.sha256(encoded).hexdigest()!=challenge['resource_sha256']:raise ValueError('Native resource SHA mismatch')
        plan=roster.plan(self.node.state,self.node.catalog)
        if not set(plan['required_server_models']+plan['required_media_models'])<=set(model.lower() for model in ready['resources']['models']):
            raise ValueError('Native resources omit current kit models')
        registered={w['name'] for w in ready['resources']['weapons'] if w['registered']}
        if not set(plan['required_weapons'])<=registered:raise ValueError('Native resource table omits registered kit weapons')
        self.ledger.activate(ready['context']['native_session'])
    def read_pending(self,index):
        challenge=validate_challenge(self.files.read(f'host-{index}.json'),self.now_ms())
        if challenge['pending_index']!=index:raise ValueError('Native pending index mismatch')
        self.matches_party(challenge);self.host_ready(challenge)
        return challenge
    def challenge(self,guid,challenge):
        """Called ONLY after the existing signed host UDP envelope is verified."""
        if self.node.hosting:raise ValueError('Host cannot sign a remote-owner proof')
        challenge=validate_challenge(challenge);self.matches_party(challenge)
        if challenge['member_guid']!=self.node.identity.guid:raise ValueError('Native challenge belongs to another owner')
        previous=self.pending.get(challenge['nonce'])
        if previous and previous['challenge']!=challenge:raise ValueError('Native reused a nonce for another challenge')
        # Do not advance the serial fence from a network-only challenge.
        # Local JoinerCore intent/receipt must authenticate its epoch first.
        if not previous:self.pending[challenge['nonce']]={'challenge':challenge,'seen':self.clock(),'last':0}
        if len(self.pending)>MAX_PENDING:self.pending.pop(next(iter(self.pending)))
    def peer_proof(self,challenge):
        local=self.files.read('client.json')
        if set(local)!={'schema','kind','intent','received_challenge','phase','received_unix_ms','received_source'} or type(local['schema']) is not int or local['schema']!=1 or local['kind']!=IDL or type(local['phase']) is not int or local['phase']!=2:
            raise ValueError('Waiting for local JoinerCore intent and actual socket challenge')
        if endpoint(local['received_source'])!=challenge['client_target']:raise ValueError('Local native packet source differs from current target')
        received=local['received_unix_ms']
        if type(received) is not int or not 0<=self.now_ms()-received<MAX_TTL_MS:raise ValueError('Local native socket receipt expired')
        if local['received_challenge']!=challenge:raise ValueError('The local native socket received a different challenge')
        # This record is produced by local Native on its current own socket,
        # not by a party packet. client_target is echoed through NAT; Native
        # must separately have checked the received packet's actual source.
        fields=('client_join_nonce','native_session','native_world','engine','variant','map','client_target','member_guid','party_session','catalog_sha256','package_sha256','world_sha256','roster_revision','plan_sha256','resource_sha256')
        if not isinstance(local['intent'],dict) or set(local['intent'])!=set(fields) or any(local['intent'][key]!=challenge[key] for key in fields):
            raise ValueError('Native challenge does not match local current join intent')
        self.ledger.activate(local['intent']['native_session'])
        pending=self.pending.get(challenge['nonce'])
        record=self.ledger.admit(challenge,pending['seen'] if pending else None)
        if record['consumed']:raise ValueError('Native proof already completed')
        message=canonical(challenge)
        return {'schema':1,'challenge':deepcopy(challenge),'public':self.node.identity.public,'signature':self.node.identity.key.sign(message).hex()}
    def proof(self,guid,proof):
        """Called ONLY after a signed, admitted peer UDP envelope is verified."""
        if not self.node.hosting or not isinstance(proof,dict) or set(proof)!={'schema','challenge','public','signature'} or type(proof['schema']) is not int or proof['schema']!=1:
            raise ValueError('Invalid native owner proof')
        challenge=validate_challenge(proof['challenge'],self.now_ms());self.matches_party(challenge)
        nonce=challenge['nonce']
        if challenge!=self.read_pending(challenge['pending_index']):raise ValueError('Native pending challenge changed')
        if guid!=challenge['member_guid'] or self.node.members[guid]['public']!=proof['public'] or hashlib.sha256(bytes.fromhex(proof['public'])).hexdigest()!=guid:
            raise ValueError('Native proof does not belong to admitted owner')
        try:Ed25519PublicKey.from_public_bytes(bytes.fromhex(proof['public'])).verify(bytes.fromhex(proof['signature']),canonical(challenge))
        except (InvalidSignature,ValueError,TypeError) as error:raise ValueError('Invalid native owner signature') from error
        pending=self.pending.get(nonce)
        if not pending or pending['challenge']!=challenge or self.clock()-pending['seen']>MAX_TTL_MS/1000:
            raise ValueError('Native pending monotone worker deadline elapsed')
        record=self.ledger.admit(challenge,pending['seen'])
        if record['consumed']:raise ValueError('Native challenge was already consumed')
        # ACK contains no paths/commands and is written only under a fixed host
        # directory. Native must compare its pending tuple and own monotone
        # deadline, atomically consume once, then allocate its own slot.
        ack={'schema':1,'kind':IDL,'decision':'approve','challenge':challenge,'challenge_sha256':hashlib.sha256(canonical(challenge)).hexdigest(),
             'owner_public':proof['public'],'owner_signature':proof['signature']}
        # Fence before publishing. A write failure may require Native to issue
        # its next serial, but can never recreate an already visible ACK.
        record['consumed']=True
        try:self.files.write(f"ack-{challenge['pending_index']}.json",ack)
        except OSError as error:
            self.node.events.append({'phase':'party_native_waiting','error':'Local approval write failed; waiting for a new native challenge','runtime_ready':False})
            raise ValueError('Native approval could not be published safely') from error
        self.pending.pop(nonce,None);self.stats['approvals']+=1
        self.node.events.append({'phase':'party_native_proof','status':'owner-proof-approved','runtime_ready':False,'pending_index':challenge['pending_index'],'serial_records':sum(record is not None for record in self.ledger.records)})
    def poll(self):
        now=self.now_ms()
        # Each native pending index retains one serial fence. No total-party
        # request count accumulates across mission/checkpoint transitions.
        try:
            snapshot,members=self.current()
            view=self.node.latest_view if self.node.hosting else self.node.public_view
            # Public local context contains no invitation secret/private keys.
            context={'schema':1,'kind':IDL,'party_session':self.node.invitation['session'],'catalog_sha256':snapshot['catalog_sha256'],
                     'package_sha256':snapshot['world']['package_id'],'world':snapshot['world'],'world_sha256':roster.identity(snapshot['world']),
                     'revision':snapshot['revision'],'plan_sha256':snapshot['plan_sha256'],'members':view['members'],'local_guid':self.node.identity.guid,
                     'confirmed_slots':view['confirmed_slots'],'plan':self.current_plan(snapshot),'runtime_ready':False}
            digest=hashlib.sha256(canonical(context)).hexdigest()
            if self.latest_plan!=digest or self.clock()-self.last_context_write>=1:
                context.update(worker_pid=os.getpid(),updated_unix_ms=now,expires_unix_ms=now+5000)
                self.files.write('party.json',context);self.latest_plan=digest;self.last_context_write=self.clock()
            if self.node.hosting:
                active=set()
                for index in range(MAX_PENDING):
                    try:challenge=self.read_pending(index)
                    except FileNotFoundError:continue
                    except (OSError,ValueError,KeyError,TypeError,RecursionError):self.stats['rejected']+=1;continue
                    nonce=challenge['nonce'];active.add(nonce)
                    try:record=self.ledger.admit(challenge)
                    except ValueError:self.stats['rejected']+=1;continue
                    if record['consumed']:continue
                    if nonce not in self.pending:self.pending[nonce]={'challenge':challenge,'seen':record['seen'],'last':0};self.stats['challenges']+=1
                    pending=self.pending[nonce]
                    if pending['challenge']!=challenge:raise ValueError('Native reused a nonce for another challenge')
                    if self.clock()-pending['seen']>MAX_TTL_MS/1000:continue
                    if self.clock()-pending['last']>=.4:
                        peer=self.node.peers.get(challenge['member_guid'])
                        if peer:self.node.send(self.node.base('native_challenge',challenge=challenge),peer['address']);pending['last']=self.clock()
                # Never accumulate more than the native's fixed pending slots.
                self.pending={k:v for k,v in self.pending.items() if k in active and v['challenge']['expires_unix_ms']>now}
                if len(self.pending)>MAX_PENDING:raise ValueError('Native pending challenge limit exceeded')
            else:
                for nonce,pending in list(self.pending.items()):
                    challenge=pending['challenge']
                    if self.clock()-pending['seen']>MAX_TTL_MS/1000:self.pending.pop(nonce,None);continue
                    if self.clock()-pending['last']<.4:continue
                    try:proof=self.peer_proof(challenge)
                    except (FileNotFoundError,OSError,ValueError,KeyError,TypeError):continue
                    self.node.send(self.node.base('native_proof',proof=proof),self.node.host_address);pending['last']=self.clock();self.stats['proofs']+=1
            self.last_error=None
        except (FileNotFoundError,OSError,ValueError,KeyError,TypeError,RecursionError) as error:
            if self.latest_plan is not None:
                try:self.files.write('party.json',{'schema':1,'kind':IDL,'status':'waiting','runtime_ready':False})
                except (OSError,ValueError):pass
                self.latest_plan=None
            if self.last_error!=str(error):self.node.events.append({'phase':'party_native_waiting','error':str(error),'runtime_ready':False})
            self.last_error=str(error)
