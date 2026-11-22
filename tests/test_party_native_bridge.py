"""Real source-worker UDP+fixed-file bridge tests; file producer is a harness,
not an actual native Core. These tests do not certify native slot allocation.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from coop_party import canonical,atomic_private
from party_native_bridge import IDL,CONTEXT_FIELDS,encode_resources,FixedFiles,validate_challenge
import test_coop_suite as suite_fixture
import uf_equipment_roster as roster


class Worker:
    def __init__(self,args,env):
        self.process=subprocess.Popen([sys.executable,str(ROOT/'tools/coop_party.py'),*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        self.events=queue.Queue();self.latest=None
        def reader():
            for line in self.process.stdout:
                try:self.events.put(json.loads(line))
                except ValueError:pass
        threading.Thread(target=reader,daemon=True).start()
    def send(self,value):self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush()
    def drain(self):
        while not self.events.empty():
            event=self.events.get()
            if event.get('phase')=='party':self.latest=event
    def stop(self):
        if self.process.poll() is None:
            self.send({'action':'stop'})
            try:self.process.wait(5)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(3)
        code=self.process.returncode
        self.process.stdin.close();self.process.stdout.close();self.process.stderr.close()
        if code!=0:raise AssertionError('Owned source party worker did not exit cleanly: '+str(code))


class NativeBridgeWorkers(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.workers=[];self.fixtures=[];self.addCleanup(self.cleanup)
        self.env=dict(os.environ,XDG_CONFIG_HOME=str(self.base/'user'),LOCALAPPDATA=str(self.base/'user'),PYTHONDONTWRITEBYTECODE='1')
        for _ in range(2):
            f=suite_fixture.SuiteTest();f.setUp();self.fixtures.append(f)
            import zipfile
            with zipfile.ZipFile(f.game/'UnitedFronts/bridge_fixture.pk3','w') as z:z.writestr('maps/noville.bsp',b'fixture, never executed')
            suite_fixture.suite.seal_installation(f.game)
        self.host_game,self.peer_game=[f.game for f in self.fixtures]
    def cleanup(self):
        for w in reversed(self.workers):w.stop()
        for f in self.fixtures:f.doCleanups()
    def wait(self,predicate,timeout=12):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            for worker in self.workers:worker.drain()
            if predicate():return
            if any(w.process.poll() is not None for w in self.workers):self.fail('Source party worker exited unexpectedly')
            time.sleep(.02)
        self.fail('Native bridge condition timed out')
    def party(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        invite=self.base/'invitation.json'
        host=Worker(['--game',str(self.host_game),'--host','--bind','127.0.0.1','--port',str(port),'--map','noville','--campaign','american','--invitation-file',str(invite)],self.env);self.workers.append(host)
        self.wait(lambda:invite.exists())
        peer=Worker(['--game',str(self.peer_game),'--invitation-file',str(invite)],self.env);self.workers.append(peer)
        self.wait(lambda:all(w.latest and len(w.latest['members'])==2 for w in self.workers))
        kit={'mode':'manual','family':'american','slots':{'primary':9,'secondary':6,'pistol':22,'grenade':31}}
        for w in self.workers:
            revision=w.latest['roster']['revision'];w.send({'action':'kit','revision':revision,'kit':kit});self.wait(lambda:all(x.latest['roster']['revision']>revision for x in self.workers))
        for w in self.workers:w.send({'action':'confirm','revision':w.latest['roster']['revision'],'plan':w.latest['roster']['plan_sha256'],'ready':True})
        self.wait(lambda:all(len(w.latest['confirmed_slots'])==2 for w in self.workers))
        self.wait(lambda:(self.host_game/'coop/party-bridge/party.json').exists() and (self.peer_game/'coop/party-bridge/party.json').exists())
        self.host_files=FixedFiles(self.host_game);self.peer_files=FixedFiles(self.peer_game)
        context=self.host_files.read('party.json');view=host.latest['roster'];catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
        state=roster.create_roster(catalog,0,view['world'],[{'slot_id':0,'kit':view['members'][0]['kit']},{'slot_id':1,'kit':{'mode':'automatic'}}])
        state=roster.update_kit(state,catalog,1,1,view['members'][1]['kit'],state['revision']);plan=roster.plan(state,catalog)
        resources={'models':sorted(set(plan['required_server_models']+plan['required_media_models'])),'weapons':[{'index':i,'name':name,'registered':True} for i,name in enumerate(plan['required_weapons'],1)]}
        now=int(time.time()*1000)
        c={'schema':1,'kind':IDL,'pending_index':0,'nonce':'1'*64,'client_join_nonce':'2'*64,'native_session':'1234567890abcdef','native_world':'1234abcd','engine':'uo','variant':'united_fronts','map':'noville',
           'client_target':'127.0.0.1:28960','client_endpoint':'127.0.0.1:31000','party_session':context['party_session'],'catalog_sha256':context['catalog_sha256'],'package_sha256':context['package_sha256'],
           'world_sha256':context['world_sha256'],'member_guid':next(m['guid'] for m in host.latest['members'] if m['slot']==1),'roster_revision':view['revision'],'plan_sha256':view['plan_sha256'],
           'resource_sha256':hashlib.sha256(encode_resources(resources)).hexdigest(),'created_unix_ms':now,'expires_unix_ms':now+20000}
        ready={'schema':1,'kind':IDL,'phase':2,'context':{key:c[key] for key in CONTEXT_FIELDS},'resources':resources}
        self.host_files.write('host-ready.json',ready);self.host_files.write('host-0.json',c)
        return host,peer,c,ready
    def local_intent(self,c):
        fields=('client_join_nonce','native_session','native_world','engine','variant','map','client_target','member_guid','party_session','catalog_sha256','package_sha256','world_sha256','roster_revision','plan_sha256','resource_sha256')
        return {'schema':1,'kind':IDL,'phase':2,'received_unix_ms':int(time.time()*1000),'received_source':c['client_target'],'intent':{key:c[key] for key in fields},'received_challenge':c}
    def test_actual_workers_require_received_socket_challenge_then_one_use_approval(self):
        host,peer,c,ready=self.party();ack=self.host_game/'coop/party-bridge/ack-0.json'
        # A signed host UDP challenge alone must NEVER trigger a peer proof.
        time.sleep(.7);self.assertFalse(ack.exists())
        wrong=self.local_intent(c);wrong['received_challenge']=dict(c,client_endpoint='127.0.0.1:32000');self.peer_files.write('client.json',wrong)
        time.sleep(.6);self.assertFalse(ack.exists())
        wrong=self.local_intent(c);wrong['intent']['client_join_nonce']='9'*64;self.peer_files.write('client.json',wrong)
        time.sleep(.6);self.assertFalse(ack.exists())
        wrong=self.local_intent(c);wrong['received_source']='127.0.0.1:29999';self.peer_files.write('client.json',wrong)
        time.sleep(.6);self.assertFalse(ack.exists())
        self.peer_files.write('client.json',self.local_intent(c));self.wait(ack.exists)
        value=json.loads(ack.read_text());self.assertEqual(value['challenge'],c);self.assertEqual(value['decision'],'approve');self.assertEqual(value['challenge_sha256'],hashlib.sha256(canonical(c)).hexdigest())
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(value['owner_public'])).verify(bytes.fromhex(value['owner_signature']),canonical(c))
        # Native consumes ACK; duplicate UDP proofs cannot recreate it.
        ack.unlink();time.sleep(.8);self.assertFalse(ack.exists())
        self.assertTrue(all(w.latest['runtime_ready'] is False for w in self.workers))
    def test_actual_workers_reject_resource_and_plan_drift(self):
        host,peer,c,ready=self.party();ack=self.host_game/'coop/party-bridge/ack-0.json'
        # Host-ready context's resource table, not a caller boolean, must match.
        ready['resources']['weapons'][0]['registered']=False;self.host_files.write('host-ready.json',ready)
        self.peer_files.write('client.json',self.local_intent(c))
        time.sleep(.6);self.assertFalse(ack.exists())
        # Changing a current kit clears confirmations and invalidates the plan.
        revision=host.latest['roster']['revision'];host.send({'action':'kit','revision':revision,'kit':{'mode':'automatic'}})
        self.wait(lambda:host.latest['roster']['revision']>revision)
        ready['resources']['weapons'][0]['registered']=True;self.host_files.write('host-ready.json',ready)
        time.sleep(.6);self.assertFalse(ack.exists())
        self.wait(lambda:self.host_files.read('party.json').get('status')=='waiting')
    def test_actual_workers_expired_challenge_never_approves_then_fresh_nonce_recovers(self):
        host,peer,c,ready=self.party();ack=self.host_game/'coop/party-bridge/ack-0.json'
        now=int(time.time()*1000);expired=dict(c,created_unix_ms=now-2000,expires_unix_ms=now-1)
        self.host_files.write('host-0.json',expired);self.peer_files.write('client.json',self.local_intent(expired))
        time.sleep(.6);self.assertFalse(ack.exists())
        fresh=dict(c,nonce='4'*64,client_join_nonce='5'*64,created_unix_ms=int(time.time()*1000),expires_unix_ms=int(time.time()*1000)+20000)
        self.host_files.write('host-0.json',fresh);self.peer_files.write('client.json',self.local_intent(fresh));self.wait(ack.exists)
        self.assertEqual(json.loads(ack.read_text())['challenge']['nonce'],'4'*64)
        for changes in ({'schema':True},{'pending_index':3},{'nonce':'0'*64},{'native_session':'0'*16},{'client_target':'../arbitrary.exe'},{'engine':'cod2'},{'created_unix_ms':int(time.time()*1000)+100000}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):validate_challenge(dict(fresh,**changes),int(time.time()*1000))

    def test_python_resource_bytes_match_actual_cpp_encoder(self):
        import shutil
        compiler=shutil.which('g++') or shutil.which('c++')
        if not compiler:self.skipTest('C++ source encoder compiler unavailable')
        cpp=self.base/'encoder.cpp';exe=self.base/('encoder.exe' if os.name=='nt' else 'encoder')
        cpp.write_text('#include "asset_bootstrap.h"\n#include <iostream>\nint main(){asset_bootstrap::Resources r;r.models={"xmodel/Example","xmodel/example","xmodel/a_test"};r.weapons={{1,"alpha",true},{2,"beta_alt",false}};std::string out;uint16_t count=0;if(!asset_bootstrap::EncodeResources(r,out,count))return 1;std::cout<<out;return 0;}\n')
        subprocess.run([compiler,'-std=c++17','-I',str(ROOT/'src'),str(cpp),'-o',str(exe)],check=True,capture_output=True)
        actual=subprocess.check_output([str(exe)])
        expected=encode_resources({'models':['xmodel/Example','xmodel/example','xmodel/a_test'],'weapons':[{'index':1,'name':'alpha','registered':True},{'index':2,'name':'beta_alt','registered':False}]})
        self.assertEqual(actual,expected)

    def test_actual_workers_reject_unknown_and_host_owner_then_valid_owner_recovers(self):
        host,peer,c,ready=self.party();ack=self.host_game/'coop/party-bridge/ack-0.json'
        for owner in ('f'*64,next(m['guid'] for m in host.latest['members'] if m['slot']==0)):
            wrong=dict(c,member_guid=owner);self.host_files.write('host-0.json',wrong);self.peer_files.write('client.json',self.local_intent(wrong))
            time.sleep(.5);self.assertFalse(ack.exists())
        valid=dict(c,nonce='6'*64,client_join_nonce='7'*64);self.host_files.write('host-0.json',valid);self.peer_files.write('client.json',self.local_intent(valid));self.wait(ack.exists)
        self.assertEqual(json.loads(ack.read_text())['challenge']['member_guid'],c['member_guid'])

    def test_monotone_deadline_cannot_be_reset_by_retries_or_wall_rollback(self):
        from party_native_bridge import NativePartyBridge
        now=[10.0];bridge=NativePartyBridge(None,self.host_game,wall_clock=lambda:1,clock=lambda:now[0])
        value={'nonce':'8'*64,'binding':'fixed private helper fixture'}
        self.assertEqual(bridge.remember(value),10)
        now[0]=20;self.assertEqual(bridge.remember(value),10)
        with self.assertRaises(ValueError):bridge.remember(dict(value,binding='conflicting'))
        now[0]=41
        with self.assertRaises(ValueError):bridge.remember(value)
        # Tombstones are not expired using untrusted/rolled-back wall time.
        self.assertIn(value['nonce'],bridge.seen)

    def test_fixed_paths_and_exact_native_resource_encoding(self):
        files=FixedFiles(self.host_game)
        for path in ('../ack.json','ack-3.json','host-9.json','arbitrary.exe'):
            with self.assertRaises(ValueError):files.path(path)
        value={'models':['xmodel/Example','xmodel/example'],'weapons':[{'index':1,'name':'test_weapon','registered':True}]}
        self.assertEqual(encode_resources(value),b'codcoop-assets-1\nm\txmodel/example\nw\t001\t1\ttest_weapon\n')
        value['weapons'][0]['index']=2
        with self.assertRaises(ValueError):encode_resources(value)
        files.root.parent.mkdir(exist_ok=True);outside=self.base/'outside';outside.mkdir();files.root.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):files.write('ack-0.json',{'decision':'approve'})

if __name__=='__main__':unittest.main()
