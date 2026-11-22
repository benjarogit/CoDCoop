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

class ActualSaveBoundaryTrace(unittest.TestCase):
    def trace(self,open_flags=0,close_flags=0,role=2):
        return '\n'.join(f'save-observe: phase={phase} save=save/temp.svg slot=1 role={role} flags={flags} health=1 view=0,32,0 prone=0,0,0' for phase,flags in [('open',open_flags),('close',close_flags)])
    def test_requires_actual_open_and_close_downed_but_not_prone(self):
        from qa_checkpoint_downed import parse_nonprone_save_boundary
        self.assertTrue(parse_nonprone_save_boundary(self.trace(),1)['valid_nonprone_downed_source'])
        for text in (self.trace(1,1),self.trace(0,1),self.trace(role=1),self.trace().splitlines()[0]):
            with self.subTest(trace=text):self.assertFalse(parse_nonprone_save_boundary(text,1)['valid_nonprone_downed_source'])
        self.assertFalse(parse_nonprone_save_boundary(self.trace(),0)['valid_nonprone_downed_source'])

if __name__=='__main__':unittest.main()
