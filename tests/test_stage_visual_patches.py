"""Reviewed visual patches are fixed suite content, independent of base inclusion."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage_suite as stage

class VisualPatchStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.game=Path(self.temp.name)/'owned';self.game.mkdir();self.out=Path(self.temp.name)/'payload'
        items=[]
        for name in ['Main/zzz_patch.pk3','Main/zzzzzzz_kar98k_firing_anim_fix.pk3']:
            path=self.game/name;path.parent.mkdir(exist_ok=True);path.write_bytes(('reviewed '+name).encode())
            items.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':path.stat().st_size})
        self.catalog={'additional_visual_patches':items}
        self.manifest={'required':[dict(item,install_source='suite') for item in items]}

    def test_online_stage_copies_both_without_any_original_base_package(self):
        stage.copy_reviewed_visual_patches(self.game,self.out,self.catalog,self.manifest)
        for item in self.catalog['additional_visual_patches']:
            self.assertEqual((self.out/item['path']).read_bytes(),(self.game/item['path']).read_bytes())
        self.assertFalse((self.out/'Main/pak0.pk3').exists())

    def test_missing_or_changed_patch_fails_without_cache_or_partial_output(self):
        patch=self.game/self.catalog['additional_visual_patches'][1]['path']
        patch.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'missing or changed'):
            stage.copy_reviewed_visual_patches(self.game,self.out,self.catalog,self.manifest)
        self.assertFalse(self.out.exists())
        patch.unlink()
        with self.assertRaisesRegex(ValueError,'missing or changed'):
            stage.copy_reviewed_visual_patches(self.game,self.out,self.catalog,self.manifest)

    def test_inventory_and_required_manifest_must_agree(self):
        self.manifest['required'][1]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'manifest pin differs'):
            stage.copy_reviewed_visual_patches(self.game,self.out,self.catalog,self.manifest)
        self.assertFalse(self.out.exists())

    def test_production_requirements_pin_every_reviewed_visual_for_both_platforms(self):
        root=Path(__file__).resolve().parents[1]
        manifest=json.loads((root/'content/variants.json').read_text())
        catalog=json.loads((root/'content/base-packages.json').read_text())
        for patch in catalog['additional_visual_patches']:
            item=next(row for row in manifest['required'] if row['path']==patch['path'])
            self.assertEqual(item['install_source'],'suite')
            self.assertEqual(item['sha256'],patch['sha256'])
            self.assertEqual(item['size'],patch['size'])

if __name__=='__main__':unittest.main()
