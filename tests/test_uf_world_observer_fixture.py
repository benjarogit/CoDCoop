import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from build_uf_world_observer_fixture import campaign_body,climate_body,levels_body,helper,instrument,ROOT
from campaign_inventory import uncomment

class SourceOnlyWorldWitness(unittest.TestCase):
    def test_campaign_keeps_one_actual_read_and_last_case_assignment(self):
        original='''level.campaign = "american";
spawners = getspawnerarray();
for (i=0; i<spawners.size; i++)
switch (spawners[i].classname) {
case "r": level.campaign = "russian"; break;
case "b": level.campaign = "british"; break;
case "a": level.campaign = "american"; break;
}'''
        transformed=campaign_body(original)
        self.assertEqual(transformed.count('getspawnerarray()'),1)
        self.assertEqual(transformed.count('spawners[i].classname'),1)
        self.assertEqual(re.findall(r'level\.campaign\s*=\s*"([^"]+)"',transformed),['american','russian','british','american'])
        self.assertEqual(transformed.count('coop_last_index = i;'),3)
        self.assertEqual(transformed.count('CampaignFacts('),1)
        self.assertNotIn('setcvar(',transformed.lower())
        self.assertGreater(transformed.index('CampaignFacts('),transformed.rfind('break;'))
        with self.assertRaises(ValueError):campaign_body(original.replace('getspawnerarray()','getentarray("actor")'))

    def test_climate_distinguishes_first_snow_from_later_map_override(self):
        original='''spawners = getspawnerarray();
for (i=0; i<spawners.size; i++) {
switch (spawners[i].classname) {case "snow":level.winter_map = 1;setcvar("sp_climate", "winter");break;}
}
switch (level.script) {case "wintermap":level.winter_map = 1;setcvar("sp_climate", "winter");break;}'''
        transformed=climate_body(original)
        self.assertEqual(transformed.count('getspawnerarray()'),1)
        self.assertEqual(transformed.count('spawners[i].classname'),1)
        self.assertEqual(transformed.count('if (coop_winter_index == -1)'),1)
        self.assertEqual(transformed.count('level.winter_map = 1;'),2)
        self.assertNotIn('coop_winter_index = i',transformed.split('switch (level.script)')[1])
        self.assertGreater(transformed.index('ClimateFacts('),transformed.rfind('setcvar('))

    def test_year_commit_is_before_first_special_return_not_after_give(self):
        original='''switch(level.script){case "map":setcvar("sp_year","1940");break;default:setcvar("sp_year","1944");break;}
switch(level.script){case "credits":return;}
level.player setViewmodel("hands");'''
        transformed=levels_body(original)
        self.assertGreater(transformed.index('YearObserved()'),transformed.rfind('setcvar'))
        self.assertLess(transformed.index('YearObserved()'),transformed.index('return;'))
        self.assertLess(transformed.index('YearObserved()'),transformed.index('setViewmodel'))

    def test_observer_writes_only_fixed_private_fields_and_no_world_ready(self):
        graph=json.loads((ROOT/'campaign_patches/uf_world_rules.json').read_text())
        data,digest=helper(graph);text=data.decode('latin1')
        self.assertEqual(digest,hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        writes=re.findall(r'setcvar\("([^"]+)"',text,re.I)
        self.assertTrue(writes);self.assertTrue(all(name.startswith('coop_uf_world_') for name in writes))
        active=uncomment(text)
        self.assertNotRegex(active,r'\b(?:level\.\w+\s*=|game\[|wait\s|thread\s|precacheItem\(|getspawnerarray\()')
        self.assertIn('level.script != getcvar("coop_uf_native_map")',active)
        self.assertNotIn('getcvar("coop_uf_native_preinit_world") != getcvar("sv_serverid")',active)
        for stage in ('campaign','climate','year'):
            self.assertIn('setcvar("coop_uf_world_'+stage+'_world", getcvar("sv_serverid"))',active)
        self.assertIn('coop_uf_native_preinit_world',text)
        self.assertNotIn('coop_uf_native_world"',text)
        self.assertLess(text.index('"coop_uf_world_status", "WAIT"'),text.index('"coop_uf_world_epoch", epoch'))
        self.assertIn('"coop_uf_world_status", "OBSERVED"',text)
        self.assertNotIn('"READY"',text)
        self.assertIn('"actor_ally_airborne_snow_BAR"',text)

    def test_actual_external_pinned_sources_and_unknown_revision_refusal(self):
        package=ROOT/'run/campaign-host/UnitedFronts/ZUnitedFronts_1.1_beta.pk3'
        if not package.is_file():self.skipTest('Owned original UF package unavailable; source fixture only')
        files,metadata=instrument(package)
        self.assertFalse(metadata['native_ready_capability'])
        self.assertEqual(set(files),{'maps/_UF_loadout.gsc','maps/_UF_mod.gsc','maps/_coop_uf_world_observer.gsc'})
        self.assertEqual(files['maps/_UF_loadout.gsc'].count(b'CampaignFacts('),1)
        composed,detail=instrument(package,compose_airborne_fix=True)
        self.assertEqual(detail['composition']['transform'],'uf_airborne_missing_load')
        self.assertIn(b'precacheModel("xmodel/gear_US_load1")',composed['maps/_UF_mod.gsc'])
        self.assertEqual(composed['maps/_UF_mod.gsc'].count(b'ClimateFacts('),1)
        self.assertNotEqual(detail['generated_sha256']['maps/_UF_mod.gsc'],metadata['generated_sha256']['maps/_UF_mod.gsc'])
        with tempfile.TemporaryDirectory() as directory:
            mutant=Path(directory)/'mutant.pk3'
            with zipfile.ZipFile(package) as source,zipfile.ZipFile(mutant,'w') as dest:
                for name in metadata['sources']:
                    data=source.read(name)
                    if name.endswith('_UF_loadout.gsc'):data+=b'\n// changed revision\n'
                    dest.writestr(name,data)
            with self.assertRaisesRegex(ValueError,'Unknown pinned'):instrument(mutant)

if __name__=='__main__':unittest.main()
