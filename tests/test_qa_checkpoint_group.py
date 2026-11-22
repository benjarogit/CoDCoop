import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_checkpoint_group import assert_owner_restore

class FourOwnerOracle(unittest.TestCase):
    def fixture(self):
        host=[];local=[]
        for slot in range(4):
            item={'clientnum':slot,'position':[100*slot,0,0],'viewangles':[0,slot*45,0],
                  'health':600-slot*50,'entity_health':600-slot*50,'inventory':{},'stock':[],'clip':[],
                  'selected':{'id':0,'name':'none'}}
            host.append(item)
            local.append({'cgame':{'snapshot_client':slot,'snapshot':item['selected'],'desired':item['selected'],
                'predicted':item['selected'],'predicted_position':item['position'],'predicted_angles':item['viewangles'],
                'snapshot_position':item['position']}})
        return {'host':host,'local':local}

    def test_each_saved_owner_and_own_camera_required(self):
        saved=self.fixture();self.assertEqual(len(assert_owner_restore(saved,copy.deepcopy(saved))),4)
        for mutation in ('clone','fresh_health','latest_position','wrong_camera'):
            restored=copy.deepcopy(saved)
            if mutation=='clone':restored['host'][2]=copy.deepcopy(restored['host'][1])
            if mutation=='fresh_health':restored['host'][2]['health']=600
            if mutation=='latest_position':restored['host'][2]['position'][0]+=80
            if mutation=='wrong_camera':restored['local'][2]['cgame']['snapshot_client']=1
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):assert_owner_restore(saved,restored)


class MixedRoleMetadataOracle(unittest.TestCase):
    def test_native_v2_role_slots_bind_svg_and_owner_leases(self):
        import hashlib,struct
        from qa_checkpoint_group import decode_role_v2
        svg=b'fixture native save bytes';data=bytearray(224)
        struct.pack_into('<IIQ',data,0,0x43535049,2,123)
        data[18:27]=b'training\0';data[82:147]=hashlib.sha256(svg).hexdigest().encode()+b'\0'
        for slot in range(1,4):struct.pack_into('<QIH',data,152+16*slot,slot,0x0100007f,29950+slot)
        data[216:220]=bytes([1,1,2,1])
        result=decode_role_v2(bytes(data),svg)
        self.assertEqual(result['roles'],[1,1,2,1]);self.assertEqual([o['slot'] for o in result['owners']],[0,1,2,3])
        for invalid in (bytes(data[:216]),bytes(data)+b'x'):
            with self.assertRaises(ValueError):decode_role_v2(invalid,svg)
        with self.assertRaises(ValueError):decode_role_v2(bytes(data),svg+b'changed')
        struct.pack_into('<Q',data,152+32,0)
        with self.assertRaises(ValueError):decode_role_v2(bytes(data),svg)

    def test_equal_health_mixed_roles_cannot_swap(self):
        from qa_checkpoint_group import assert_mixed_roles
        r={'state':{'players':[{'downed':i==2} for i in range(4)]},'host':[],
           'cvars':{f'coop_actor_{i}_state':'INELIGIBLE' if i==2 else 'ELIGIBLE' for i in range(4)}}
        for i,h in enumerate((600,1,1,450)):r['host'].append({'health':h,'entity_health':h,'pm_flags':1 if i==2 else 0})
        self.assertEqual(len(assert_mixed_roles(r)),4)
        r['state']['players'][1]['downed']=True
        with self.assertRaises(RuntimeError):assert_mixed_roles(r)

if __name__=='__main__':unittest.main()
