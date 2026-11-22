import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_checkpoint_downed import assert_saved_role

class ExplicitSavedRole(unittest.TestCase):
    def fixture(self,downed):
        return {'state':{'players':[{}, {'downed':downed}]},'host':[{}, {'health':1,'entity_health':1,'pm_flags':1 if downed else 0}],
                'cvars':{'coop_actor_1_state':'INELIGIBLE' if downed else 'ELIGIBLE'}}
    def test_same_health_does_not_imply_same_role(self):
        for role in (False,True):
            r=self.fixture(role);assert_saved_role(r,1,role)
            with self.assertRaises(RuntimeError):assert_saved_role(r,1,not role)
    def test_wrong_eligibility_posture_and_reset_health_rejected(self):
        for role in (False,True):
            for mutate in ('health','entity_health','pm_flags','eligibility'):
                r=copy.deepcopy(self.fixture(role))
                if mutate=='eligibility':r['cvars']['coop_actor_1_state']='ELIGIBLE' if role else 'INELIGIBLE'
                elif mutate=='pm_flags':r['host'][1]['pm_flags']=2
                else:r['host'][1][mutate]=600
                with self.subTest(role=role,mutation=mutate),self.assertRaises(RuntimeError):assert_saved_role(r,1,role)
if __name__=='__main__':unittest.main()
