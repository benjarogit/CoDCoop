"""C++ local bridge contract fixtures, never actual game/slot acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import uf_equipment_roster as roster
from uf_equipment_preferences import catalog_digest
from party_native_bridge import validate_challenge
from coop_party import canonical


class NativePartyBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('g++') or not Path('/usr/include/openssl/sha.h').exists():
            raise unittest.SkipTest('Native C++/OpenSSL contract fixture prerequisites unavailable')
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.fixture=cls.folder/'fixture';cls.unit=cls.folder/'unit'
        subprocess.run(['g++','-std=c++17','-O1',str(ROOT/'tests/party_native_bridge_fixture.cpp'),'-lcrypto','-o',str(cls.fixture)],check=True)
        subprocess.run(['g++','-std=c++17','-O1',str(ROOT/'tests/test_party_native_bridge.cpp'),'-o',str(cls.unit)],check=True)
        cls.catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
        cls.catalog_path=cls.folder/'catalog.json';cls.catalog_path.write_text(json.dumps(cls.catalog))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'temp'):cls.temp.cleanup()

    def heartbeat(self):
        world={'variant':'united_fronts','package_id':'c'*64,'map':'brecourt','campaign':'american','sp_ally':'us_inf'}
        state=roster.create_roster(self.catalog,0,world,[{'slot_id':slot,'kit':{'mode':'automatic'}} for slot in range(4)])
        choices=[(9,6,22,34),(5,1,21,33),(10,8,21,32),(3,7,21,31)]
        for slot,values in enumerate(choices):
            kit={'mode':'manual','family':'american','slots':dict(zip(('primary','secondary','pistol','grenade'),values))}
            state=roster.update_kit(state,self.catalog,slot,slot,kit,state['revision'])
        plan=roster.plan(state,self.catalog)
        return {'schema':1,'kind':'coop-party-native-1','party_session':'a'*64,'catalog_sha256':catalog_digest(self.catalog),
                'package_sha256':'c'*64,'world':world,'world_sha256':roster.identity(world),'revision':plan['revision'],
                'plan_sha256':plan['plan_sha256'],'members':[{'guid':str(slot+1)*64,'slot':slot} for slot in range(4)],
                'local_guid':'1'*64,'confirmed_slots':[0,1,2,3],'plan':plan,'runtime_ready':False,
                'worker_pid':123,'updated_unix_ms':100000,'expires_unix_ms':105000}

    def evaluate(self,value,world=None):
        party=self.folder/'party.json';actual=self.folder/'native-world-fixture.json'
        party.write_text(json.dumps(value));actual.write_text(json.dumps(world if world is not None else self.heartbeat()['world']))
        result=subprocess.run([str(self.fixture),'--plan',str(party),str(self.catalog_path),str(actual),'c'*64],capture_output=True,text=True)
        self.assertIn(result.returncode,(0,1),result.stderr)
        return json.loads(result.stdout)['valid']

    def rehash(self,value):
        unhashed=copy.deepcopy(value['plan']);unhashed.pop('plan_sha256')
        digest=roster.identity(unhashed);value['plan']['plan_sha256']=digest;value['plan_sha256']=digest

    def test_actual_cpp_canonical_and_transactions(self):
        subprocess.run([str(self.unit)],check=True)
        raw=subprocess.check_output([str(self.unit),'--canonical'])
        challenge=json.loads(raw);validate_challenge(challenge)
        self.assertEqual(raw,canonical(challenge))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'c4d43ca051b796de112579f240c8aee365c19e74246a7387521963d78ec42730')

    def test_all_four_actual_catalog_kits_and_support_union(self):
        self.assertTrue(self.evaluate(self.heartbeat()))

    def test_modified_kit_without_rehash(self):
        value=self.heartbeat();value['plan']['members'][1]['kit']['slots']['primary']=3
        self.assertFalse(self.evaluate(value))

    def test_rehashed_invalid_original_enum_and_inactive_family(self):
        for change in ('enum','family'):
            with self.subTest(change=change):
                value=self.heartbeat();kit=value['plan']['members'][1]['kit']
                if change=='enum':kit['slots']['primary']=65535
                else:kit['family']='italian'
                self.rehash(value);self.assertFalse(self.evaluate(value))

    def test_rehashed_omitted_resource_or_support(self):
        for field in ('required_weapons','required_server_models','required_media_models','support'):
            with self.subTest(field=field):
                value=self.heartbeat();self.assertTrue(value['plan'][field]);value['plan'][field].pop()
                self.rehash(value);self.assertFalse(self.evaluate(value))

    def test_confirmed_owner_mapping_is_required(self):
        for change in ('confirmation','duplicate_guid','foreign_local'):
            with self.subTest(change=change):
                value=self.heartbeat()
                if change=='confirmation':value['confirmed_slots'].pop()
                elif change=='duplicate_guid':value['members'][1]['guid']=value['members'][0]['guid']
                else:value['local_guid']='f'*64
                self.assertFalse(self.evaluate(value))

    def test_actual_native_world_must_equal_declared_graph(self):
        value=self.heartbeat();world=copy.deepcopy(value['world']);world['sp_ally']='ger_heer'
        self.assertFalse(self.evaluate(value,world))

    def test_unresolved_automatic_never_guessed(self):
        value=self.heartbeat();value['plan']['members'][1]['kit']={'mode':'automatic'};value['plan']['unresolved_automatic_slots']=[1]
        self.rehash(value);self.assertFalse(self.evaluate(value))

    def test_runtime_claim_or_invalid_heartbeat_rejected(self):
        value=self.heartbeat();value['runtime_ready']=True;self.assertFalse(self.evaluate(value))
        value=self.heartbeat();value['expires_unix_ms']=value['updated_unix_ms']+5001;self.assertFalse(self.evaluate(value))


if __name__=='__main__':unittest.main()
