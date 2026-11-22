import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_uf_world_observer import validate_context,archive_cache_inputs

class NativeWitnessOracle(unittest.TestCase):
 def test_cache_cleanup_is_map_scoped_and_symlink_refuses_before_mutation(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);folder=root/'game';archive=root/'archive';folder.mkdir();archive.mkdir()
   for name in ('qa-render-models.txt','qa-model-ledger-foy.txt','qa-model-ledger-noville.txt'):(folder/name).write_bytes(b'owned cache')
   target=root/'external';target.write_bytes(b'untouched');(folder/'qa-deferred-models.txt').symlink_to(target)
   with self.assertRaises(ValueError):archive_cache_inputs(folder,archive,'foy')
   self.assertTrue((folder/'qa-render-models.txt').exists());self.assertFalse(list(archive.iterdir()))
   (folder/'qa-deferred-models.txt').unlink();records=archive_cache_inputs(folder,archive,'foy')
   self.assertEqual(len(records),2);self.assertEqual(target.read_bytes(),b'untouched')
   self.assertTrue((folder/'qa-model-ledger-noville.txt').is_file());self.assertFalse((folder/'qa-model-ledger-foy.txt').exists())
 def context(self):
  return dict(runtime_ready=False,lifecycle_match=True,native_init_complete=True,native_map='foy',native_epoch='a'*64,native_init_serial=4,native_preinit_world='100',native_completed_world='200',fields={
   'coop_uf_world_map':'foy','coop_uf_world_epoch':'a'*64,'coop_uf_world_init_serial':'4','coop_uf_world_preinit_world':'100',
   'coop_uf_world_campaign_world':'100','coop_uf_world_climate_world':'200','coop_uf_world_year_world':'200'})
 def test_actual_pre_and_completed_ids_both_accepted(self):validate_context(self.context(),'foy')
 def test_stale_or_incomplete_world_never_accepted(self):
  for field,value in [('native_init_complete',False),('lifecycle_match',False),('runtime_ready',True),('native_map','noville'),('native_epoch','b'*64),('native_init_serial',3)]:
   context=self.context();context[field]=value
   with self.subTest(field=field),self.assertRaises(RuntimeError):validate_context(context,'foy')
  context=self.context();context['fields']['coop_uf_world_year_world']='300'
  with self.assertRaises(RuntimeError):validate_context(context,'foy')

if __name__=='__main__':unittest.main()
