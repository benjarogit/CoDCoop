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

if __name__=='__main__':unittest.main()
