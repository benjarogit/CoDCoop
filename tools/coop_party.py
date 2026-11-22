#!/usr/bin/env python3
"""Authenticated pre-mission UDP lobby. This does not apply equipment in-game.

Only the invitation is a bearer secret. Installation Ed25519 keys authenticate
own-slot actions; replay epochs survive worker restarts. No network message is
interpreted as a filesystem path, executable, console command or native ACK.
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import hmac
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
import zlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
import uf_equipment_roster as roster
from uf_equipment_preferences import catalog_digest, preferences_path

MAX_PACKET = 16384
MAX_MESSAGE = 131072
WIRE = 1
HEARTBEAT = 1.0
WAIT_AFTER = 8.0
RETRY = .4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _replace_private(temporary, path):
    # Windows readers (including a briefly open UI/antivirus handle) may deny
    # replacement. Keep the original intact and bound retry to 250 ms.
    deadline=time.monotonic()+.25
    while True:
        try:
            os.replace(temporary,path)
            return
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32,33) or time.monotonic()>=deadline:
                raise
            time.sleep(.01)


def atomic_private(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        _replace_private(temporary, path)
        if os.name != 'nt': path.chmod(0o600)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def identity_directory(game):
    # Personal identity is outside the replaceable game suite and save folders.
    installation = hashlib.sha256(str(Path(game).resolve()).encode()).hexdigest()[:24]
    return preferences_path().parent / 'parties' / installation


class Identity:
    def __init__(self, directory):
        self.path = Path(directory) / 'identity.json'
        if self.path.is_symlink(): raise ValueError('Identity file must not be a symlink')
        if self.path.exists():
            value = json.loads(self.path.read_text())
            if set(value) != {'private', 'epoch'} or type(value['epoch']) is not int or value['epoch'] < 0:
                raise ValueError('Invalid stored party identity')
            self.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(value['private']))
            epoch = value['epoch'] + 1
        else:
            self.key = Ed25519PrivateKey.generate(); epoch = 1
        self.public = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.guid = hashlib.sha256(bytes.fromhex(self.public)).hexdigest()
        self.epoch = epoch
        atomic_private(self.path, {'private': self.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex(), 'epoch': epoch})


def signed(identity, body):
    result = dict(body, public=identity.public, epoch=identity.epoch)
    message = canonical({'body': result, 'signature': identity.key.sign(canonical(result)).hex()})
    if len(message) > MAX_MESSAGE: raise ValueError('Party message too large')
    return b'CP1' + zlib.compress(message)


def verify(data):
    if len(data) > MAX_PACKET: raise ValueError('Party packet too large')
    if data[:3] != b'CP1': raise ValueError('Unknown party wire encoding')
    try:
        decoder = zlib.decompressobj(); message = decoder.decompress(data[3:], MAX_MESSAGE + 1)
    except zlib.error as error: raise ValueError('Invalid party wire compression') from error
    if len(message) > MAX_MESSAGE or not decoder.eof or decoder.unused_data: raise ValueError('Party decompression limit exceeded')
    value = json.loads(message)
    if set(value) != {'body', 'signature'} or not isinstance(value['body'], dict): raise ValueError('Invalid signed envelope')
    body = value['body']; public = bytes.fromhex(body['public'])
    if len(public) != 32 or type(body['epoch']) is not int or not 1 <= body['epoch'] < 2**53: raise ValueError('Invalid identity')
    Ed25519PublicKey.from_public_bytes(public).verify(bytes.fromhex(value['signature']), canonical(body))
    return body, hashlib.sha256(public).hexdigest()


def encode_invite(value): return base64.urlsafe_b64encode(canonical(value)).decode().rstrip('=')


def decode_invite(text):
    if not isinstance(text, str) or len(text) > 2048: raise ValueError('Invalid invitation')
    value = json.loads(base64.urlsafe_b64decode(text + '=' * (-len(text) % 4)))
    if set(value) != {'schema', 'session', 'host_public', 'secret', 'host', 'port', 'catalog', 'package'} or value['schema'] != WIRE:
        raise ValueError('Unsupported party invitation')
    for key in ('session', 'host_public', 'secret', 'catalog', 'package'):
        if not isinstance(value[key], str) or len(value[key]) != 64 or any(c not in '0123456789abcdef' for c in value[key]):
            raise ValueError('Invalid invitation identity')
    socket.inet_pton(socket.AF_INET, value['host'])
    if type(value['port']) is not int or not 1 <= value['port'] <= 65535: raise ValueError('Invalid party port')
    return value


def validate_party_world(world):
    world = roster.validate_world(world)
    if not re.fullmatch('[a-zA-Z0-9_-]{1,63}', world['map']): raise ValueError('Invalid registered mission name')
    if not re.fullmatch('[0-9a-f]{64}', world['package_id']): raise ValueError('Invalid package digest')
    if 'difficulty' in world and world['difficulty'] not in ('0','1','2','3'): raise ValueError('Invalid original difficulty')
    if 'campaign' in world and world['campaign'] not in ('american','british','russian'): raise ValueError('Invalid original campaign faction')
    return world


class PartyNode:
    def __init__(self, catalog, identity, *, world=None, invitation=None, bind=('127.0.0.1', 0), advertise=None, clock=time.monotonic):
        self.catalog = catalog; self.identity = identity; self.clock = clock
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.sock.bind(bind); self.sock.setblocking(False)
        self.hosting = invitation is None; self.sequence = 0; self.pending = {}; self.peers = {}; self.replays = {}; self.events = []
        self.closed = False; self.cancelled = False; self.last_send = 0; self.last_host = clock(); self.snapshot = None; self.confirmed = {}; self.last_error = None
        self.event_serial = 0; self.last_host_serial = 0; self.stats = {'accepted':0, 'rejected':0}
        if self.hosting:
            world = validate_party_world(world)
            if len(world['package_id']) != 64 or any(c not in '0123456789abcdef' for c in world['package_id']): raise ValueError('Package identity must be SHA256')
            self.invitation = {'schema': WIRE, 'session': secrets.token_hex(32), 'host_public': identity.public, 'secret': secrets.token_hex(32),
                               'host': advertise or self.sock.getsockname()[0], 'port': self.sock.getsockname()[1], 'catalog': catalog_digest(catalog), 'package': world['package_id']}
            decode_invite(encode_invite(self.invitation))
            self.state = roster.create_roster(catalog, 0, world, [{'slot_id': 0, 'kit': {'mode': 'automatic'}}])
            self.members = {identity.guid: {'slot': 0, 'public': identity.public, 'epoch': identity.epoch}}
            self.publish()
        else:
            self.invitation = decode_invite(invitation)
            if self.invitation['catalog'] != catalog_digest(catalog): raise ValueError('Party equipment catalog mismatch')
            self.host_address = (self.invitation['host'], self.invitation['port']); self.state = None; self.members = {}; self.slot = None
            self.send_join()

    def base(self, kind, **fields):
        self.sequence += 1
        return {'wire': WIRE, 'session': self.invitation['session'], 'catalog': self.invitation['catalog'], 'package': self.invitation['package'],
                'kind': kind, 'seq': self.sequence, **fields}

    def send(self, body, address):
        data = signed(self.identity, body)
        if len(data) > MAX_PACKET: raise ValueError('Party snapshot exceeds bounded packet size')
        try:
            self.sock.sendto(data, address)
            self.network_error = None
            return True
        except OSError as error:
            if getattr(self, 'network_error', None) != error.errno:
                self.events.append({'phase':'party_waiting','error':'Network unavailable; party identity and pending requests are retained'})
            self.network_error = error.errno
            return False

    def send_join(self):
        body = self.base('join')
        body['authorization'] = hmac.new(bytes.fromhex(self.invitation['secret']), canonical(dict(body, public=self.identity.public, epoch=self.identity.epoch)), hashlib.sha256).hexdigest()
        self.send(body, self.host_address); self.last_send = self.clock()

    def publish(self):
        self.event_serial += 1
        self.snapshot = roster.public_snapshot(self.state, self.catalog)
        waiting = sorted(self.members[guid]['slot'] for guid, peer in self.peers.items() if self.clock() - peer['last'] >= WAIT_AFTER)
        view = {'phase': 'party', 'status': 'cancelled' if self.cancelled else 'waiting' if waiting else 'connected', 'offline_slots': waiting, 'serial': self.event_serial,
                'roster': deepcopy(self.snapshot), 'members': [{'guid': guid, 'slot': value['slot']} for guid, value in sorted(self.members.items(), key=lambda pair: pair[1]['slot'])],
                'confirmed_slots': sorted(slot for slot, revision in self.confirmed.items() if revision == self.state['revision']),
                'runtime_ready': False, 'runtime_blocker': 'Native authenticated roster/plan/resource binding has not been implemented'}
        self.latest_view = view
        self.events.append(dict(view, local_slot=0))
        for peer in self.peers.values(): self.send(self.base('snapshot', view=view), peer['address'])

    def changed(self, new):
        # Validate the full derived plan before committing state. Invalid/unresolved
        # resource input must not leave a half-updated invisible roster.
        roster.public_snapshot(new, self.catalog)
        if new['revision'] != self.state['revision']: self.confirmed.clear()
        self.state = new; self.publish()

    def apply(self, guid, request):
        if self.cancelled: raise ValueError('Party has been cancelled')
        actor = self.members[guid]['slot']; action = request.get('action')
        if set(request) - {'action', 'revision', 'plan', 'kit', 'ready', 'world', 'target_slot'}: raise ValueError('Unknown party action fields')
        revision = request.get('revision')
        if type(revision) is not int or revision < 1: raise ValueError('Current roster revision is required')
        roster.validate_state(self.state, self.catalog, revision)
        if 'target_slot' in request and request['target_slot'] != actor: raise ValueError('Another participant owns this slot')
        if action == 'kit': self.changed(roster.update_kit(self.state, self.catalog, actor, actor, request['kit'], revision))
        elif action == 'world':
            world = validate_party_world(request['world'])
            if world.get('package_id') != self.invitation['package']: raise ValueError('Changing package requires a new party')
            self.changed(roster.update_world(self.state, self.catalog, actor, world, revision))
        elif action == 'confirm':
            if type(request.get('ready')) is not bool or request.get('plan') != roster.plan(self.state, self.catalog)['plan_sha256']:
                raise ValueError('Stale plan or invalid confirmation')
            if request['ready']: self.confirmed[actor] = revision
            else: self.confirmed.pop(actor, None)
            self.publish()
        elif action == 'leave':
            if actor == 0:
                self.cancelled = True; self.publish()
            else:
                members = [m for m in self.state['members'] if m['slot_id'] != actor]
                self.members.pop(guid); self.peers.pop(guid, None)
                self.changed(roster.update_members(self.state, self.catalog, 0, members, revision))
        elif action == 'cancel':
            if actor != 0: raise ValueError('Only the host can cancel the party')
            self.cancelled = True; self.publish()
        else: raise ValueError('Unsupported party action')

    def command(self, request):
        if self.hosting:
            self.apply(self.identity.guid, request)
        else:
            if self.slot is None: raise ValueError('Waiting for party admission')
            if len(self.pending) >= 32: raise ValueError('Wait for pending party requests or retry the connection')
            request_id = secrets.token_hex(16)
            self.pending[request_id] = {'request': deepcopy(request), 'last': 0}
            self.flush_requests()

    def flush_requests(self):
        for request_id, value in self.pending.items():
            if self.clock() - value['last'] >= RETRY:
                self.send(self.base('request', request_id=request_id, request=value['request']), self.host_address); value['last'] = self.clock()

    def receive_host(self, body, guid, address):
        kind = body['kind']
        if kind == 'join':
            auth = body.get('authorization'); unsigned = dict(body); unsigned.pop('authorization', None)
            expected = hmac.new(bytes.fromhex(self.invitation['secret']), canonical(unsigned), hashlib.sha256).hexdigest()
            if not isinstance(auth, str) or not hmac.compare_digest(auth, expected): raise ValueError('Invitation authorization rejected')
            if guid not in self.members:
                if len(self.members) >= 4: raise ValueError('Party is full')
                slot = min(set(range(4)) - {v['slot'] for v in self.members.values()})
                self.members[guid] = {'slot': slot, 'public': body['public'], 'epoch': body['epoch']}
                self.changed(roster.update_members(self.state, self.catalog, 0, self.state['members'] + [{'slot_id': slot, 'kit': {'mode': 'automatic'}}], self.state['revision']))
            else:
                if self.members[guid]['public'] != body['public']: raise ValueError('Member identity conflict')
                self.members[guid]['epoch'] = body['epoch']
            self.peers[guid] = {'address': address, 'last': self.clock(), 'requests': {}}
            self.publish()
            return
        peer = self.peers.get(guid)
        if not peer or peer['address'] != address: raise ValueError('Unknown party member or endpoint')
        peer['last'] = self.clock()
        if kind == 'heartbeat':
            self.send(self.base('snapshot', view=self.latest_view), address)
        elif kind == 'native_proof':
            if not hasattr(self, 'bridge'): raise ValueError('Native party proof bridge is unavailable')
            self.bridge.proof(guid, body['proof'])
        elif kind == 'request':
            request_id = body.get('request_id')
            if not isinstance(request_id, str) or len(request_id) != 32: raise ValueError('Invalid request ID')
            digest = hashlib.sha256(canonical(body['request'])).hexdigest()
            previous = peer['requests'].get(request_id)
            if previous:
                if previous['digest'] != digest: raise ValueError('Conflicting request ID')
                reply = previous['reply']
            else:
                try:
                    self.apply(guid, body['request']); reply = {'ok': True}
                except (ValueError, KeyError, TypeError) as error: reply = {'ok': False, 'error': str(error)}
                if len(peer['requests']) >= 128: peer['requests'].pop(next(iter(peer['requests'])))
                peer['requests'][request_id] = {'digest': digest, 'reply': reply}
            self.send(self.base('reply', request_id=request_id, **reply), address)
        else: raise ValueError('Unknown party packet kind')

    def receive_peer(self, body, guid, address):
        if address != self.host_address or body['public'] != self.invitation['host_public']: raise ValueError('Untrusted party host')
        self.last_host = self.clock()
        if body['kind'] == 'snapshot':
            view = body['view']
            if type(view.get('serial')) is not int or view['serial'] < self.last_host_serial: raise ValueError('Stale party snapshot')
            snapshot = view['roster']; validate_party_world(snapshot['world'])
            if snapshot['world']['package_id'] != self.invitation['package'] or snapshot['catalog_sha256'] != self.invitation['catalog']:
                raise ValueError('Authoritative party content mismatch')
            # The public projection validator independently checks all slots,
            # models and readiness; signing does not make malformed data valid.
            from uf_equipment_roster_view import validate_snapshot
            capability = {'id': 'uf.individual_equipment.v1', 'schema': 1, 'per_player': True, 'catalog_sha256': self.invitation['catalog'], 'roster_snapshot': 'uf-equipment-roster-v1'}
            validate_snapshot(snapshot, self.catalog, capability, self.snapshot)
            members = view['members']
            if (not isinstance(members, list) or len(members) != len(snapshot['members'])
                    or any(not isinstance(m,dict) or set(m) != {'guid','slot'} or not isinstance(m['guid'],str) or len(m['guid']) != 64 or any(c not in '0123456789abcdef' for c in m['guid']) or type(m['slot']) is not int for m in members)
                    or len({m['guid'] for m in members}) != len(members)
                    or sorted(m['slot'] for m in members) != [m['slot_id'] for m in snapshot['members']]
                    or not any(m['slot'] == snapshot['host_slot'] and m['guid'] == guid for m in members)):
                raise ValueError('Invalid authenticated party membership')
            own = next((m for m in members if m['guid'] == self.identity.guid), None)
            if own is None or own['slot'] not in [m['slot_id'] for m in snapshot['members']]: raise ValueError('Own party slot missing')
            if view.get('runtime_ready') is not False: raise ValueError('Network cannot grant native runtime readiness')
            self.last_host_serial = view['serial']; self.snapshot = deepcopy(snapshot); self.slot = own['slot']; self.cancelled = view['status'] == 'cancelled'; self.public_view=deepcopy(view);self.events.append(dict(deepcopy(view), local_slot=self.slot))
        elif body['kind'] == 'native_challenge':
            if not hasattr(self, 'bridge'): raise ValueError('Native party proof bridge is unavailable')
            self.bridge.challenge(guid,body['challenge'])
        elif body['kind'] == 'reply':
            self.pending.pop(body.get('request_id'), None)
            if body.get('ok') is not True: self.events.append({'phase': 'party_error', 'error': body.get('error', 'Request rejected')})
        else: raise ValueError('Unsupported host packet')

    def tick(self):
        for _ in range(64):
            try:
                data, address = self.sock.recvfrom(MAX_PACKET + 1)
                self.receive_error = False
            except BlockingIOError: break
            except OSError:
                if not getattr(self, 'receive_error', False):
                    self.events.append({'phase':'party_waiting','error':'Network receive unavailable; retrying'})
                self.receive_error = True
                break
            try:
                body, guid = verify(data)
                if any(body.get(key) != value for key, value in (('wire', WIRE), ('session', self.invitation['session']), ('catalog', self.invitation['catalog']), ('package', self.invitation['package']))):
                    raise ValueError('Party session/content mismatch')
                if type(body.get('seq')) is not int or not 1 <= body['seq'] < 2**53: raise ValueError('Invalid sequence')
                previous = self.replays.get(guid, (0, 0)); current = (body['epoch'], body['seq'])
                if current <= previous: raise ValueError('Replayed or reordered party packet')
                # Authenticate first. Unknown identities cannot consume replay
                # storage or steal an existing member's sequence namespace.
                if self.hosting: self.receive_host(body, guid, address)
                else: self.receive_peer(body, guid, address)
                self.replays[guid] = current
                self.stats['accepted'] += 1
            except (ValueError, KeyError, TypeError, InvalidSignature, UnicodeError, RecursionError):
                # Do not reflect unauthenticated packets or print secrets.
                self.stats['rejected'] += 1
        now = self.clock()
        if not self.hosting and not self.cancelled:
            if now - self.last_send >= HEARTBEAT:
                if self.slot is None: self.send_join()
                else: self.send(self.base('heartbeat'), self.host_address); self.last_send = now
            self.flush_requests()
            if now - self.last_host >= WAIT_AFTER and self.last_error != 'waiting':
                self.events.append({'phase': 'party_waiting', 'error': 'Host heartbeat missing; retry or leave the lobby'}); self.last_error = 'waiting'
            elif now - self.last_host < WAIT_AFTER: self.last_error = None
        elif self.hosting:
            waiting = sorted(self.members[guid]['slot'] for guid, peer in self.peers.items() if now - peer['last'] >= WAIT_AFTER)
            if waiting != getattr(self, 'waiting', []):
                self.waiting = waiting
                self.publish()

    def close(self):
        self.sock.close(); self.closed = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, type=Path)
    parser.add_argument('--host', action='store_true')
    parser.add_argument('--bind', default='0.0.0.0'); parser.add_argument('--advertise', default='127.0.0.1'); parser.add_argument('--port', type=int, default=28961)
    parser.add_argument('--invitation-file', required=True, type=Path)
    parser.add_argument('--campaign', choices=('american','british','russian'))
    parser.add_argument('--map', default='pathfinder'); parser.add_argument('--difficulty', type=int, choices=range(4), default=1)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('party port must be1..65535')
    from coop_suite import check_installation, load_manifest
    result = check_installation(args.game)
    if not result['ok']: print(json.dumps({'phase': 'party_error', 'error': '; '.join(result['errors'])}), flush=True); return 1
    manifest, _ = load_manifest(args.game)
    sibling = Path(__file__).with_name('uf_equipment_catalog.json'); source = Path(__file__).resolve().parents[1] / 'campaign_patches/uf_equipment_catalog.json'
    catalog = json.loads((Path(sys._MEIPASS)/'uf_equipment_catalog.json' if getattr(sys,'frozen',False) else sibling if sibling.exists() else source).read_text())
    digest = result['variants']['united_fronts']
    identity = Identity(identity_directory(args.game))
    if args.host:
        # Mission is a bounded registered map name; no network-selected paths.
        from coop_session import target_map_exists
        if not target_map_exists(args.game, 'united_fronts', args.map): raise ValueError('Unknown UF mission')
        world={'variant':'united_fronts','package_id':digest,'map':args.map,'difficulty':str(args.difficulty)}
        if args.campaign: world['campaign']=args.campaign
        node = PartyNode(catalog, identity, world=world, bind=(args.bind,args.port),advertise=args.advertise)
        atomic_private(args.invitation_file, {'invitation':encode_invite(node.invitation)})
    else:
        invitation = json.loads(args.invitation_file.read_text())['invitation']
        if decode_invite(invitation)['package'] != digest: raise ValueError('Party installation package mismatch')
        node = PartyNode(catalog, identity, invitation=invitation)
    from party_native_bridge import NativePartyBridge
    node.bridge = NativePartyBridge(node,args.game)
    controls = queue.Queue(maxsize=64); stop_deadline = None
    def reader():
        while True:
            line = sys.stdin.readline(MAX_PACKET + 1)
            if not line: break
            if len(line) > MAX_PACKET:
                while line and not line.endswith('\n'): line = sys.stdin.readline(MAX_PACKET + 1)
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict) and isinstance(value.get('action'), str): controls.put(value)
            except (ValueError,RecursionError): pass
        controls.put({'action':'stop'})
    threading.Thread(target=reader,daemon=True).start()
    try:
        while True:
            while not controls.empty():
                command=controls.get()
                if command.get('action')=='stop':
                    if stop_deadline is None:
                        if node.snapshot and not node.cancelled:
                            node.command({'action':'leave','revision':node.snapshot['revision']})
                        stop_deadline = time.monotonic() + 2
                    continue
                try:
                    if command.get('action')=='retry' and not node.hosting: node.send_join()
                    else:
                        if command.get('action') == 'world' and node.hosting:
                            if not target_map_exists(args.game, 'united_fronts', command.get('world', {}).get('map')):
                                raise ValueError('Unknown UF mission')
                        node.command(command)
                except (ValueError,KeyError,TypeError) as error: print(json.dumps({'phase':'party_error','error':str(error)}),flush=True)
            node.tick();node.bridge.poll()
            for view in node.events: print(json.dumps(view),flush=True)
            node.events.clear()
            if stop_deadline is not None and (node.hosting or not node.pending or time.monotonic() >= stop_deadline): return 0
            time.sleep(.03)
    finally: node.close()


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,KeyError) as error:
        print(json.dumps({'phase':'party_error','error':str(error)}),flush=True); raise SystemExit(1)
