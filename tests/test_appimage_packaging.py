"""Staged online payload packaging must not weaken full-install validation."""
import json
from pathlib import Path
import tempfile
import unittest
import test_coop_suite as fixtures
import package_appimage_suite as package

class AppImageSuiteTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.SuiteTest('test_complete_seal_and_prepare');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.destination=Path(self.temp.name)/'suite'
        self.f.write('coop/launcher/CoD-Coop-Launcher',b'fixture Linux launcher')
        self.f.write('coop/languages/en/Main/localized_english_pak0.pk3',b'English')
        self.f.write('coop/languages/en/manifest.json',fixtures.suite.canonical({'schema':1,'language':'en','files':{'Main/localized_english_pak0.pk3':{'sha256':fixtures.suite.sha256(self.f.game/'Main/localized_english_pak0.pk3')}}}))
        lock=json.loads((self.f.game/'coop/runtime-lock.json').read_text())
        for name in ['coop/launcher/CoD-Coop-Launcher','coop/languages/en/manifest.json']:
            lock['files'][name]=fixtures.suite.sha256(self.f.game/name)
        for item in self.f.manifest['required']:
            lock['files'][item['path']]=fixtures.suite.sha256(self.f.game/item['path'])
        self.f.write('coop/runtime-lock.json',fixtures.suite.canonical(lock))

    def test_online_payload_keeps_only_reviewed_missing_base_as_requirement(self):
        path=self.f.game/'Main/pak0.pk3';path.unlink()
        lock=json.loads((self.f.game/'coop/runtime-lock.json').read_text());lock['files'].pop('Main/pak0.pk3')
        self.f.write('coop/runtime-lock.json',fixtures.suite.canonical(lock))
        report=package.embed_suite(self.f.game,self.destination)
        self.assertIn('Main/pak0.pk3',report['missing_base_packages'])
        self.assertEqual((self.destination/'coop/launcher/CoD-Coop-Launcher').read_bytes(),b'fixture Linux launcher')
        self.assertFalse((self.destination/'coop/install.json').exists())
        with self.assertRaises(ValueError):fixtures.suite.seal_installation(self.destination)

    def test_corrupt_owned_runtime_cannot_be_embedded(self):
        self.f.write('ddraw.dll',b'wrong')
        with self.assertRaises(ValueError):package.embed_suite(self.f.game,self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_mod_cannot_be_relabelled_as_online_base_download(self):
        name='UnitedFronts/ZUnitedFronts_1.1_beta.pk3';(self.f.game/name).unlink()
        lock=json.loads((self.f.game/'coop/runtime-lock.json').read_text());lock['files'].pop(name)
        self.f.write('coop/runtime-lock.json',fixtures.suite.canonical(lock))
        with self.assertRaisesRegex(ValueError,'missing required suite content'):
            package.embed_suite(self.f.game,self.destination)
        self.assertFalse(self.destination.exists())

    def test_unknown_gameplay_pk3_is_not_hidden_by_packaging(self):
        self.f.write('uo/unowned.pk3',b'foreign rules')
        with self.assertRaisesRegex(ValueError,'unowned staged gameplay content'):
            package.embed_suite(self.f.game,self.destination)
        self.assertFalse(self.destination.exists())

    def test_reviewed_visual_patch_is_required_in_online_payload_too(self):
        name='Main/zzz_patch.pk3';(self.f.game/name).unlink()
        lock=json.loads((self.f.game/'coop/runtime-lock.json').read_text());lock['files'].pop(name)
        self.f.write('coop/runtime-lock.json',fixtures.suite.canonical(lock))
        with self.assertRaisesRegex(ValueError,'missing required suite content'):
            package.embed_suite(self.f.game,self.destination)
        self.assertFalse(self.destination.exists())

    def test_unowned_symlink_cannot_copy_external_files_into_artifact(self):
        outside=Path(self.temp.name)/'private.txt';outside.write_text('outside source')
        (self.f.game/'unowned.txt').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'symlinks'):
            package.embed_suite(self.f.game,self.destination)
        self.assertFalse(self.destination.exists())

if __name__=='__main__':unittest.main()
