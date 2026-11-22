import hashlib,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import build_campaign_patch as patch

class GMILoaderPrototype(unittest.TestCase):
 def source(self):
  return b'''main() { level.player = player;
setcvar("g_speed", "190");
maps\\_tank_gmi::main();
maps\\_UF_loadout::give_loadout();
maps\\_UF_mod::main(); }'''
 def test_prefix_only_keeps_original_gmi_order_and_world_rules(self):
  source=self.source()
  with mock.patch.object(patch,'UF_LOAD_GMI_HASH',hashlib.sha256(source).hexdigest()):
   text=patch.transform_uf_gmi_load(source).decode('latin1')
  original=source.decode('latin1')
  before,after=original.split('level.player = player;',1)
  self.assertTrue(text.startswith(before+'level.player = player;'))
  self.assertTrue(text.endswith(after))
  for name in ('Coop_PrecacheMountModels','Coop_InitMineResources','Coop_PrecacheAirAssets','Coop_BinocularPlayers'):
   self.assertEqual(text.count(name),1)
   self.assertLess(text.index(name),text.index('maps\\_tank_gmi::main()'))
  ordered=['setcvar("g_speed", "190")','maps\\_tank_gmi::main()','maps\\_UF_loadout::give_loadout()','maps\\_UF_mod::main()']
  self.assertEqual([text.index(value) for value in ordered],sorted(text.index(value) for value in ordered))
  self.assertNotIn('maps\\_tank::',text)
 def test_unknown_revision_and_missing_or_duplicate_binding_fail_closed(self):
  with self.assertRaises(ValueError):patch.transform_uf_gmi_load(self.source())
  for source in (self.source().replace(b'level.player = player;',b'level.player = somebody;'),self.source()+b'level.player = player;'):
   with mock.patch.object(patch,'UF_LOAD_GMI_HASH',hashlib.sha256(source).hexdigest()):
    with self.assertRaises(ValueError):patch.transform_uf_gmi_load(source)
 def test_build_option_requires_explicit_uf_kit_experiment(self):
  with self.assertRaisesRegex(ValueError,'QA GMI'):patch.build('/absent','/absent2','united_fronts',qa_gmi=True)
  with self.assertRaises(ValueError):patch.build('/absent','/absent2','sp_improved',qa_gmi=True,qa_kits=True)
 def test_pinned_real_gmi_composition_is_opt_in_and_deterministic(self):
  package=patch.ROOT/'run/campaign-host/UnitedFronts/ZUnitedFronts_1.1_beta.pk3'
  if not package.is_file():self.skipTest('Owned pinned UF archive unavailable')
  with zipfile.ZipFile(package) as original:
   data=original.read('maps/_load_gmi.gsc')
   self.assertEqual(hashlib.sha256(data).hexdigest(),patch.UF_LOAD_GMI_HASH)
   with self.assertRaises(ValueError):patch.transform_uf_gmi_load(data+b'\n// changed revision')
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);plain=root/'plain.pk3';explicit=root/'false.pk3';gmi=root/'gmi.pk3';again=root/'again.pk3'
   patch.build(package,plain,'united_fronts',qa_kits=True)
   patch.build(package,explicit,'united_fronts',qa_kits=True,qa_gmi=False)
   self.assertEqual(plain.read_bytes(),explicit.read_bytes())
   metadata=patch.build(package,gmi,'united_fronts',qa_kits=True,qa_gmi=True)
   patch.build(package,again,'united_fronts',qa_kits=True,qa_gmi=True)
   self.assertEqual(gmi.read_bytes(),again.read_bytes());self.assertTrue(metadata['qa_gmi_loader'])
   self.assertEqual(metadata['source_load_gmi_sha256'],patch.UF_LOAD_GMI_HASH)
   with zipfile.ZipFile(plain) as default,zipfile.ZipFile(gmi) as adapted:
    self.assertNotIn('maps/_load_gmi.gsc',default.namelist())
    self.assertEqual(set(adapted.namelist())-set(default.namelist()),{'maps/_load_gmi.gsc'})
    for name in default.namelist():
     if name!='codcoop/menu-overlay.json':self.assertEqual(default.read(name),adapted.read(name))
    text=adapted.read('maps/_load_gmi.gsc').decode('latin1')
    self.assertLess(text.index('maps\\_tank_gmi::main()'),text.index('maps\\_UF_loadout::give_loadout()'))
    self.assertLess(text.index('maps\\_UF_loadout::give_loadout()'),text.index('maps\\_coop_uf_kits::Start()'))
    self.assertLess(text.index('maps\\_coop_uf_kits::Start()'),text.index('maps\\_UF_mod::main()'))
   old=patch.ROOT/'run/qa-cod1-four/history/1795320581657023310/runtime/fresh-role-source/host-overlay.pk3'
   if old.is_file():self.assertEqual(plain.read_bytes(),old.read_bytes(),'Disabled option must reproduce the immutable original Noville crash payload')

if __name__=='__main__':unittest.main()
