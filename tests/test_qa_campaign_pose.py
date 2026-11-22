import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qa_pathfinder_use import pose_difference

class PoseOracleTests(unittest.TestCase):
 def test_wrap_and_bounded_standing_drift(self):
  a={'position':[0,0,0],'viewangles':[0,359,0]};b={'position':[0,0,1],'viewangles':[0,1,0]}
  self.assertTrue(pose_difference(a,b)['within_tolerance'])
 def test_mapstart_respawn_cannot_pass_as_checkpoint_pose(self):
  a={'position':[-1359,5227,0],'viewangles':[51,137,0]};b={'position':[-1052,-68,-191],'viewangles':[0,30,0]}
  result=pose_difference(a,b);self.assertFalse(result['within_tolerance']);self.assertGreater(result['position_delta'],5000)
 def test_malformed_and_nonfinite_pose_rejected(self):
  valid={'position':[0,0,0],'viewangles':[0,0,0]}
  for value in ([0,0],[0,True,0],[0,float('nan'),0]):
   with self.subTest(value=value),self.assertRaises(ValueError):pose_difference({'position':value,'viewangles':[0,0,0]},valid)

if __name__=='__main__':unittest.main()
