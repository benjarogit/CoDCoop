import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import coop_localization as locale
from build_coop_localization import INSTALLED_PATH,package_bytes
from unittest import mock
spec=importlib.util.spec_from_file_location('locale_installer',ROOT/'tools/install-linux.py');installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class CoopLocaleInstall(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.manifest=json.loads((ROOT/'content/variants.json').read_text());self.game=self.root/'game';self.game.mkdir()
        (self.game/'coop').mkdir();(self.game/'coop/variants.json').write_text(json.dumps(self.manifest))
    def test_generated_banks_default_en_without_any_ready_zip(self):
        info=locale.generate_banks(self.game,self.manifest);locale.preflight(self.game,self.manifest)
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('en'))
        self.assertEqual(info['source'],'codcoop_generator')
        self.assertFalse(list(self.root.rglob('*Ready*.zip')))
        for language in ('en','de'):
            data=(self.game/locale.BANKS[language]).read_bytes();self.assertEqual(data,package_bytes(language))
            with zipfile.ZipFile(self.game/locale.BANKS[language]) as z:self.assertEqual(z.namelist(),[locale.RESOURCE_PATH])
    def test_runtime_lock_pins_both_banks_without_freezing_active_language(self):
        from stage_suite import runtime_files
        locale.generate_banks(self.game,self.manifest);files=runtime_files(self.game)
        for language in ('en','de'):self.assertEqual(files[locale.BANKS[language]],hashlib.sha256(package_bytes(language)).hexdigest())
        self.assertNotIn(INSTALLED_PATH,files)
        (self.game/INSTALLED_PATH).write_bytes(package_bytes('de'))
        self.assertEqual(runtime_files(self.game),files)

    def test_language_swap_repair_update_rollback_preserves_personal_files(self):
        locale.generate_banks(self.game,self.manifest)
        personal={'Main/config.cfg':b'mygraphics and name','Main/save/autosave/progress.svg':b'native save payload'}
        for rel,data in personal.items():p=self.game/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        tx=installer.InstallTransaction(self.game);locale.apply(self.game,'de',tx)
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('de'));tx.rollback()
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('en'))
        (self.game/INSTALLED_PATH).write_bytes(b'broken active file')
        tx=installer.InstallTransaction(self.game);locale.apply(self.game,'de',tx);tx.complete()
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('de'))
        tx=installer.InstallTransaction(self.game);locale.apply(self.game,'en',tx);tx.rollback()
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('de'))
        for rel,data in personal.items():self.assertEqual((self.game/rel).read_bytes(),data)
    def test_missing_mutated_or_added_resource_fails_before_installer_transaction(self):
        locale.generate_banks(self.game,self.manifest)
        # Use just the real three owned requirements, not unrelated test-base content.
        small=json.loads(json.dumps(self.manifest));small['required']=[i for i in small['required'] if i.get('kind') in ['coop_localization','coop_locale_bank']]
        (self.game/'coop/variants.json').write_text(json.dumps(small))
        for language in ('en','de'):
            bank=self.game/locale.BANKS[language];bank.write_bytes(b'corrupt')
            with self.assertRaises((ValueError,OSError)):installer.require_suite_owned_patches(self.game)
            bank.write_bytes(package_bytes(language))
        with zipfile.ZipFile(self.game/locale.BANKS['en'],'a') as z:z.writestr('maps/injection.gsc','main() {}')
        with self.assertRaises(ValueError):installer.require_suite_owned_patches(self.game)
    def test_even_rehashed_extra_resource_and_unsafe_active_symlink_are_refused(self):
        import io
        data=io.BytesIO(package_bytes('en'))
        with zipfile.ZipFile(data,'a') as archive:archive.writestr('maps/injection.gsc','main() {}')
        raw=data.getvalue();changed=json.loads(json.dumps(self.manifest));item=next(i for i in changed['required'] if i['path']==INSTALLED_PATH)
        item['locales']['en']={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)};item['sha256_any'][0]=hashlib.sha256(raw).hexdigest();changed['approved_localizations'][INSTALLED_PATH][0]=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError,'exactly one'):locale.validate(raw,'en',changed)
        locale.generate_banks(self.game,self.manifest);active=self.game/INSTALLED_PATH;active.unlink();outside=self.root/'outside.pk3';outside.write_bytes(package_bytes('en'))
        try:active.symlink_to(outside)
        except OSError:self.skipTest('symlink creation unavailable')
        with self.assertRaisesRegex(ValueError,'unsafe'):locale.preflight(self.game,self.manifest)

    def test_bank_read_is_bounded_and_rejects_changes_during_read(self):
        locale.generate_banks(self.game,self.manifest);bank=self.game/locale.BANKS['en']
        with bank.open('wb') as output:output.truncate(locale.MAX_LOCALE_BYTES+1)
        with mock.patch.object(locale.os,'open',side_effect=AssertionError('oversized bank must fail before open')):
            with self.assertRaisesRegex(ValueError,'unsafe'):locale.preflight(self.game,self.manifest)
        bank.write_bytes(package_bytes('en'))
        actual=locale.os.fstat;calls=0
        def changed(fd):
            nonlocal calls
            calls+=1
            if calls==2:bank.write_bytes(b'changed after read')
            return actual(fd)
        with mock.patch.object(locale.os,'fstat',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'unsafe'):locale.read_bank(self.game,locale.BANKS['en'])

    def test_actual_backend_offline_repair_transaction_and_rollback_on_tiny_fixture(self):
        import test_coop_suite as fixtures
        from stage_suite import runtime_files
        f=fixtures.SuiteTest();f.setUp();self.addCleanup(f.doCleanups)
        # Fixture manifest pins synthetic base/runtime bytes; owned locale rows
        # use the REAL reviewed generated assets. No game executable is run.
        real={i['path']:i for i in self.manifest['required'] if i.get('kind') in ('coop_localization','coop_locale_bank')}
        f.manifest['required']=[real.get(i['path'],i) for i in f.manifest['required']]
        f.manifest['approved_localizations'][INSTALLED_PATH]=self.manifest['approved_localizations'][INSTALLED_PATH]
        for rel in ['Main/config.cfg','Main/save/autosave.svg','Main/localized_english_pak0.pk3']:(f.game/rel).unlink(missing_ok=True)
        for item in f.manifest['required']:
            if item['path'] not in real and 'size' in item:item['size']=(f.game/item['path']).stat().st_size
        info=locale.generate_banks(f.game,f.manifest)
        f.write('coop/variants.json',fixtures.suite.canonical(f.manifest))
        f.write('coop/languages/en/manifest.json',fixtures.suite.canonical({'schema':1,'language':'en','files':{INSTALLED_PATH:info}}))
        launcher = 'CoD-Coop-Launcher.exe' if os.name == 'nt' else 'CoD-Coop-Launcher'
        f.write('coop/launcher/' + launcher, b'fixture, never executed')
        (f.game/'coop/runtime-lock.json').unlink()
        lock={'suite_version':f.manifest['suite_version'],'manifest_sha256':fixtures.suite.sha256(f.game/'coop/variants.json'),'files':runtime_files(f.game)}
        f.write('coop/runtime-lock.json',fixtures.suite.canonical(lock))
        # Re-seal does not include the lock itself as an owned recursive hash.
        self.game.joinpath('CoDSP.exe').write_bytes(b'existing fixture')
        self.game.joinpath('CoDUOSP.exe').write_bytes(b'existing fixture')
        personal={'Main/config.cfg':b'preserve my actual fixture settings','Main/save/autosave/progress.svg':b'preserve existing fixture save'}
        for rel,data in personal.items():path=self.game/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        with mock.patch.object(installer,'download',side_effect=AssertionError('offline path must not download')):
            result=installer.suite_main(['--game',str(self.game),'--suite-source',str(f.game),'--language','en','--repair','--yes'])
        self.assertEqual(result,0);self.assertTrue(fixtures.suite.check_installation(self.game)['ok'])
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('en'))
        # Repair damaged active UI using this same production backend path.
        (self.game/INSTALLED_PATH).write_bytes(b'damaged current UI')
        with mock.patch.object(installer,'download',side_effect=AssertionError('offline path must not download')):
            self.assertEqual(installer.suite_main(['--game',str(self.game),'--suite-source',str(f.game),'--language','en','--repair','--yes']),0)
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),package_bytes('en'))
        self.assertEqual(installer.suite_main(['--game',str(self.game),'--rollback']),0)
        self.assertEqual((self.game/INSTALLED_PATH).read_bytes(),b'damaged current UI')
        for rel,data in personal.items():self.assertEqual((self.game/rel).read_bytes(),data)

    def test_english_inventory_accepts_generated_bank_independent_of_archive(self):
        generated=locale.generate_banks(self.game,self.manifest)
        (self.game/'coop/languages/en/manifest.json').write_text(json.dumps({'schema':1,'language':'en','files':{INSTALLED_PATH:generated}}))
        self.assertEqual(installer.canonical_english_files(self.game),[(self.game/locale.BANKS['en'],INSTALLED_PATH)])

if __name__=='__main__':unittest.main()
