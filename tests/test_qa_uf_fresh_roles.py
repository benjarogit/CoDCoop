import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_uf_fresh_roles import require_body_models

class FreshRoleBodyOracle(unittest.TestCase):
 def fixture(self):
  host=[{'selected_world_model':'xmodel/gun%d'%slot} for slot in range(4)]
  observer={'references_complete':True,'reference_layout_valid':True,'cgame':{'snapshot_clientnum':0},'live_dobjs':[
   {'entity':slot,'side':side,'model_names':['body','gun%d'%slot],'cs_model_names':['xmodel/body','xmodel/gun%d'%slot],'client_cs_model_names':['xmodel/body','xmodel/gun%d'%slot],'raw_model_flags':[-1,-slot-2]} for slot in range(4) for side in ('server','client')]}
  observer['native_model_slots']=[{'index':index,'server_cs':'xmodel/'+name,'client_cs':'xmodel/'+name,'cache_name':name} for index,name in [(1,'body')]+[(slot+2,'gun%d'%slot) for slot in range(4)]]
  peer=copy.deepcopy(observer);peer['cgame']['snapshot_clientnum']=1;peer['live_dobjs']=[obj for obj in peer['live_dobjs'] if obj['entity']!=1]
  return host,{'host':observer,'join1':peer}
 def test_native_model_and_negative_cs_must_both_match(self):
  host,observers=self.fixture();require_body_models(host,observers)
  for field,value in [('model_names',['body','wrong']),('cs_model_names',['xmodel/body','xmodel/wrong']),('client_cs_model_names',['xmodel/body','xmodel/wrong']),('raw_model_flags',[-1,7])]:
   mutant=copy.deepcopy(observers);mutant['join1']['live_dobjs'][5][field]=value
   with self.subTest(field=field),self.assertRaises(RuntimeError):require_body_models(host,mutant)
 def test_missing_shadow_or_client_never_passes(self):
  host,observers=self.fixture();observers['join1']['live_dobjs'].pop()
  with self.assertRaises(RuntimeError):require_body_models(host,observers)
 def test_wrong_native_cache_never_passes_even_when_model_and_both_cs_match(self):
  host,observers=self.fixture();observers['join1']['native_model_slots'][0]['cache_name']='other_body'
  with self.assertRaises(RuntimeError):require_body_models(host,observers)

if __name__=='__main__':unittest.main()
