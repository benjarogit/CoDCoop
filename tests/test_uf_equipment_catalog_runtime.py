"""The runtime planner must work without shipping source extraction tools."""
import subprocess
import sys
import unittest
from pathlib import Path


class CatalogRuntimeTests(unittest.TestCase):
    def test_runtime_resource_plan_does_not_import_campaign_builder(self):
        root=Path(__file__).resolve().parents[1]
        source='''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'tools'))
sys.modules['campaign_inventory']=None
sys.modules['build_campaign_patch']=None
from uf_equipment_catalog import roster_resources
catalog=json.loads((Path(sys.argv[1])/'campaign_patches/uf_equipment_catalog.json').read_text())
kit={'family':'american','slots':{'primary':9,'secondary':6,'pistol':22,'grenade':34}}
plan=roster_resources(catalog,[kit],{'map':'noville','campaign':'american','sp_ally':'us_inf'})
assert 'mg30cal' in plan['weapons']
assert plan['required_media_models']
assert sys.modules['campaign_inventory'] is None
assert sys.modules['build_campaign_patch'] is None
'''
        subprocess.run([sys.executable,'-c',source,str(root)],check=True,capture_output=True,text=True)


if __name__=='__main__':unittest.main()
