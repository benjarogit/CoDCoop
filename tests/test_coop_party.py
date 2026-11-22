import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from coop_party import PartyNode,Identity,canonical,signed,encode_invite
from uf_equipment_preferences import default_preferences
from party_binding import require_native_party_binding


def worker(pipe,directory,invitation=None,loss=False):
    catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
    identity=Identity(directory)
    node=PartyNode(catalog,identity,invitation=invitation,world=None if invitation else {'variant':'united_fronts','package_id':'a'*64,'map':'noville','campaign':'american','sp_ally':'us_inf'})
    if loss:
        actual=node.sock
        class LossSocket:
            count=0;held=None
            def sendto(self,data,address):
                self.count+=1
                if self.count%4==1:return len(data)
                if self.count%4==2:self.held=(data,address);return len(data)
                result=actual.sendto(data,address)
                if self.held:actual.sendto(*self.held);self.held=None
                return result
            def __getattr__(self,key):return getattr(actual,key)
        node.sock=LossSocket()
    pipe.send({'started':True,'guid':identity.guid,'invite':encode_invite(node.invitation) if node.hosting else None})
    try:
        running=True
        while running:
            while pipe.poll():
                control=pipe.recv()
                if control.get('action')=='stop':running=False;break
                try:node.command(control)
                except (ValueError,KeyError,TypeError) as e:pipe.send({'phase':'local_reject','error':str(e)})
            if not running:break
            node.tick()
            for event in node.events:pipe.send(event)
            node.events.clear();time.sleep(.01)
    finally:node.close();pipe.close()


class PartyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.context=mp.get_context('spawn');self.processes=[];self.latest={};self.events={}
        self.addCleanup(self.stop_all)
    def start(self,name,invite=None,loss=False):
        a,b=self.context.Pipe();p=self.context.Process(target=worker,args=(b,str(Path(self.temp.name)/name),invite,loss));p.start();b.close()
        self.processes.append((p,a));self.assertTrue(a.poll(10));hello=a.recv();self.assertTrue(hello['started']);return a,hello
    def stop_all(self):
        for p,a in self.processes:
            if p.is_alive():
                try:a.send({'action':'stop'})
                except (BrokenPipeError,OSError):pass
        for p,a in self.processes:
            p.join(3)
            if p.is_alive():p.terminate();p.join(3)
            a.close()
    def wait(self,connections,predicate,timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            for c in connections:
                while c.poll():
                    value=c.recv();self.events.setdefault(c,[]).append(value)
                    if value.get('phase')=='party':self.latest[c]=value
            if predicate():return
            time.sleep(.015)
        self.fail('UDP party condition timed out: '+str({id(k):v for k,v in self.latest.items()}))
    def test_real_four_processes_loss_reorder_owned_confirmation_restart_and_cancel(self):
        host,hello=self.start('host');clients=[];guids=[]
        for n in range(3):
            client,peer=self.start('peer'+str(n),hello['invite'],loss=n==2);clients.append(client);guids.append(peer['guid'])
        all_=[host,*clients]
        self.wait(all_,lambda:all(len(self.latest.get(c,{}).get('members',[]))==4 for c in all_))
        # Every owner independently submits their four slots. Revisions are read
        # from the authoritative snapshot, never guessed or overwritten by host.
        for index,c in enumerate(all_):
            current=self.latest[c]['roster'];revision=current['revision']
            kit={'mode':'manual','family':'american','slots':{'primary':9,'secondary':6,'pistol':22,'grenade':34}}
            c.send({'action':'kit','revision':revision,'kit':kit})
            self.wait(all_,lambda:all(self.latest[x]['roster']['revision']>revision for x in all_))
        revision=self.latest[host]['roster']['revision'];plan=self.latest[host]['roster']['plan_sha256']
        for c in all_:c.send({'action':'confirm','revision':revision,'plan':plan,'ready':True})
        self.wait(all_,lambda:all(len(self.latest[c]['confirmed_slots'])==4 for c in all_))
        self.assertTrue(all(self.latest[c]['runtime_ready'] is False for c in all_))
        self.assertTrue(all(self.latest[c]['roster']['runtime_ready'] is False for c in all_))
        old=clients[0];old.send({'action':'stop'});self.processes[1][0].join(3)
        restarted,identity=self.start('peer0',hello['invite']);self.assertEqual(identity['guid'],guids[0]);all_=[host,restarted,*clients[1:]]
        self.wait(all_,lambda:restarted in self.latest and len(self.latest[restarted]['members'])==4)
        own=next(m['slot'] for m in self.latest[restarted]['members'] if m['guid']==guids[0]);self.assertEqual(own,1)
        # A host world revision clears every owner's confirmation.
        world=dict(self.latest[host]['roster']['world'],difficulty='2')
        host.send({'action':'world','revision':revision,'world':world})
        self.wait(all_,lambda:all(self.latest[c]['roster']['revision']>revision and not self.latest[c]['confirmed_slots'] for c in all_))
        host.send({'action':'cancel','revision':self.latest[host]['roster']['revision']})
        self.wait(all_,lambda:all(self.latest[c]['status']=='cancelled' for c in all_))
    def test_real_two_processes_stale_other_owner_host_world_and_content_negatives(self):
        host,hello=self.start('host');peer,_=self.start('peer',hello['invite']);all_=[host,peer]
        self.wait(all_,lambda:all(len(self.latest.get(c,{}).get('members',[]))==2 for c in all_))
        baseline=self.latest[host]['roster'];revision=baseline['revision']
        peer.send({'action':'kit','revision':revision,'target_slot':0,'kit':{'mode':'automatic'}})
        peer.send({'action':'world','revision':revision,'world':dict(baseline['world'],difficulty='3')})
        peer.send({'action':'confirm','revision':revision-1,'plan':baseline['plan_sha256'],'ready':True})
        self.wait(all_,lambda:sum(e.get('phase')=='party_error' for e in self.events.get(peer,[]))>=3)
        self.assertEqual(self.latest[host]['roster'],baseline)
        catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text());identity=Identity(Path(self.temp.name)/'attacker')
        # Actual signed but wrong-session and wrong-catalog UDP packets, plus
        # an unsigned claimed victim identity, cannot allocate a third slot.
        from coop_party import decode_invite
        invite=decode_invite(hello['invite']);address=(invite['host'],invite['port']);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        for field in ('session','catalog','package'):
            body={'wire':1,'session':invite['session'],'catalog':invite['catalog'],'package':invite['package'],'kind':'join','seq':1,'authorization':'0'*64};body[field]='b'*64
            sock.sendto(signed(identity,body),address)
        sock.sendto(canonical({'body':{'public':invite['host_public']},'signature':'00'*64}),address);sock.close()
        time.sleep(.2)
        self.wait(all_,lambda:len(self.latest[host]['members'])==2)
        self.assertEqual(self.latest[host]['roster'],baseline)
    def test_real_datagrams_replay_conflict_unknown_identity_and_bounded_decode(self):
        import hmac, zlib
        from coop_party import verify, MAX_MESSAGE
        catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
        host=PartyNode(catalog,Identity(Path(self.temp.name)/'h'),world={'variant':'united_fronts','package_id':'a'*64,'map':'noville','campaign':'american'})
        peer=PartyNode(catalog,Identity(Path(self.temp.name)/'p'),invitation=encode_invite(host.invitation))
        self.addCleanup(host.close);self.addCleanup(peer.close)
        def pump():
            for _ in range(12):host.tick();peer.tick();time.sleep(.005)
        pump();self.assertEqual(peer.slot,1)
        address=host.sock.getsockname();attacker=Identity(Path(self.temp.name)/'other')
        wrong=peer.base('join');wrong['session']='b'*64
        wrong['authorization']=hmac.new(bytes.fromhex(host.invitation['secret']),canonical(dict(wrong,public=attacker.public,epoch=attacker.epoch)),hashlib.sha256).hexdigest()
        peer.sock.sendto(signed(attacker,wrong),address)
        # Valid signature but no admitted identity cannot issue an owner action.
        peer.sock.sendto(signed(attacker,peer.base('request',request_id='b'*32,request={'action':'cancel','revision':host.state['revision']})),address)
        # A signature from another identity cannot claim the host public key.
        body=dict(peer.base('heartbeat'),public=host.identity.public,epoch=host.identity.epoch)
        forged=b'CP1'+zlib.compress(canonical({'body':body,'signature':attacker.key.sign(canonical(body)).hex()}));peer.sock.sendto(forged,address)
        before=host.stats['rejected'];pump();self.assertGreaterEqual(host.stats['rejected']-before,3);self.assertEqual(len(host.members),2)
        request={'action':'kit','revision':host.state['revision'],'kit':{'mode':'manual','family':'american','slots':{'primary':9,'secondary':6,'pistol':22,'grenade':31}}}
        peer.send(peer.base('request',request_id='c'*32,request=request),address);pump();revision=host.state['revision']
        conflict=dict(request,kit={'mode':'automatic'},revision=revision)
        before=host.stats['rejected'];peer.send(peer.base('request',request_id='c'*32,request=conflict),address);pump()
        self.assertEqual(host.state['revision'],revision);self.assertGreater(host.stats['rejected'],before)
        old=peer.base('request',request_id='d'*32,request=conflict);new=peer.base('heartbeat');peer.send(new,address);peer.send(old,address);pump();self.assertEqual(host.state['revision'],revision)
        # A malformed/unresolved resource choice never half-commits state.
        previous=json.loads(json.dumps(host.state))
        with self.assertRaises(ValueError):host.command({'action':'world','revision':revision,'world':dict(host.state['world'],difficulty='99')})
        with self.assertRaises(ValueError):host.command({'action':'kit','kit':{'mode':'automatic'}})
        self.assertEqual(host.state,previous)
        with self.assertRaises(ValueError):verify(b'CP1'+zlib.compress(b'x'*(MAX_MESSAGE+1)))
        with self.assertRaises(ValueError):verify(signed(attacker,peer.base('heartbeat'))+b'trailing')

    def test_heartbeat_wait_retains_owner_slot_and_recovers_without_shrinking(self):
        catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text());now=[0.0]
        host=PartyNode(catalog,Identity(Path(self.temp.name)/'h'),world={'variant':'united_fronts','package_id':'a'*64,'map':'noville'},clock=lambda:now[0])
        peer=PartyNode(catalog,Identity(Path(self.temp.name)/'p'),invitation=encode_invite(host.invitation),clock=lambda:now[0]);self.addCleanup(host.close);self.addCleanup(peer.close)
        for _ in range(4):host.tick();peer.tick()
        self.assertEqual(peer.slot,1);revision=host.state['revision']
        now[0]=9;host.tick();self.assertEqual(host.latest_view['status'],'waiting');self.assertEqual(host.latest_view['offline_slots'],[1]);self.assertEqual(len(host.members),2)
        peer.tick();host.tick();peer.tick();self.assertEqual(host.latest_view['status'],'connected');self.assertEqual(host.state['revision'],revision);self.assertEqual(peer.slot,1)
        host.command({'action':'kit','revision':revision,'target_slot':0,'kit':{'mode':'automatic'}})
        with self.assertRaises(ValueError):host.command({'action':'kit','revision':revision,'target_slot':1,'kit':{'mode':'automatic'}})

    def test_transient_send_failure_retains_request_and_real_udp_retry_recovers(self):
        import errno
        catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text());now=[1.0]
        host=PartyNode(catalog,Identity(Path(self.temp.name)/'h'),world={'variant':'united_fronts','package_id':'a'*64,'map':'noville'},clock=lambda:now[0]);peer=PartyNode(catalog,Identity(Path(self.temp.name)/'p'),invitation=encode_invite(host.invitation),clock=lambda:now[0]);self.addCleanup(host.close);self.addCleanup(peer.close)
        for _ in range(4):host.tick();peer.tick()
        actual=peer.sock
        class OnceDown:
            failed=False
            def sendto(self,*args):
                if not self.failed:self.failed=True;raise OSError(errno.ENETDOWN,'controlled network interruption')
                return actual.sendto(*args)
            def __getattr__(self,key):return getattr(actual,key)
        peer.sock=OnceDown();revision=host.state['revision']
        peer.command({'action':'confirm','revision':revision,'plan':peer.snapshot['plan_sha256'],'ready':True})
        self.assertEqual(len(peer.pending),1);self.assertTrue(any(e.get('phase')=='party_waiting' for e in peer.events))
        now[0]=2.0
        for _ in range(6):peer.tick();host.tick()
        self.assertFalse(peer.pending);self.assertIn(1,host.confirmed);self.assertEqual(peer.slot,1)

    def test_supervisor_party_option_fails_before_spawning_native(self):
        import coop_session
        from unittest import mock
        with mock.patch.object(coop_session,'supervise') as supervise, mock.patch.object(coop_session,'event') as event:
            self.assertEqual(coop_session.main(['--game',self.temp.name,'--variant','united_fronts','--party-equipment']),1)
            supervise.assert_not_called();self.assertIn('binding',event.call_args.kwargs['error'])

    def test_identity_private_mode_and_native_capability_cannot_fake_application(self):
        directory=Path(self.temp.name)/'identity';one=Identity(directory);two=Identity(directory)
        self.assertEqual(one.guid,two.guid);self.assertGreater(two.epoch,one.epoch)
        if sys.platform!='win32':self.assertEqual((directory/'identity.json').stat().st_mode&0o777,0o600)
        for cap in (None,{'features':31},{'party_binding':'uf-party-owner-plan-v1'}):
            with self.assertRaises(ValueError):require_native_party_binding({'runtime_ready':False},cap,{'ready':True})

if __name__=='__main__':unittest.main()
