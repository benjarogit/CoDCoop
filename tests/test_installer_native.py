"""Opt-in interoperability test against the compiled Windows suite checker.

COOP_NATIVE_CHECKER=build/suite-check.exe COOP_WINE_PREFIX=<isolated-prefix>
On Windows COOP_NATIVE_CHECKER alone enables direct native execution.
DISPLAY=<test-display> python3 -m unittest discover -s tests -p test_installer_native.py
"""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock
from pe_fixtures import core_pe, malformed_core

import test_coop_suite as fixture_module
suite = fixture_module.suite


def native_path(path):
    path=Path(path).resolve()
    return str(path) if os.name=='nt' else 'Z:'+str(path).replace('/','\\')


@unittest.skipUnless(os.environ.get('COOP_NATIVE_CHECKER') and (os.name=='nt' or os.environ.get('COOP_WINE_PREFIX')),
                     'requires explicit native checker; Linux additionally needs an isolated Wine prefix')
class NativeInterop(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.SuiteTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.game=self.fixture.game

    def native(self,action,variant=None):
        env=os.environ.copy()
        exe=str(Path(env['COOP_NATIVE_CHECKER']).resolve())
        arguments=([action] if action=='capabilities' else [action,variant,native_path(self.game)] if variant is not None else [action,native_path(self.game)])
        if os.name=='nt':
            command=[exe]+arguments
        else:
            env['WINEPREFIX']=str(Path(env['COOP_WINE_PREFIX']).resolve())
            env['WINEDEBUG']='-all'
            command=['wine',exe]+arguments
        return subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)

    def test_checker_reports_machine_readable_protocol_without_game_argument(self):
        result=self.native('capabilities')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'kind':'codcoop_suite_checker','schema':1,'protocol':suite.PROTOCOL})

    @unittest.skipUnless(os.environ.get('COOP_LEGACY_CHECKER'),'requires preserved pre-enforcement protocol9 checker')
    def test_old_sealer_receipt_cannot_hide_a_stale_core_from_check_or_prepare(self):
        for protocol in (7,8):
            self.fixture.repin_core(core_pe(protocol))
            with mock.patch.dict(os.environ,{'COOP_NATIVE_CHECKER':os.environ['COOP_LEGACY_CHECKER']}):
                old=self.native('seal')
            self.assertEqual(old.returncode,0,old.stderr)  # genuine old API reproduces the historical packaging gap
            before=(self.game/'coop/profile.ini').read_bytes()
            current=suite.check_installation(self.game)
            self.assertFalse(current['ok'])
            self.assertTrue(any('Core protocol' in error for error in current['errors']))
            with self.assertRaises(ValueError):suite.prepare(self.game,'uo')
            self.assertNotEqual(self.native('check').returncode,0)
            self.assertNotEqual(self.native('prepare','uo').returncode,0)
            self.assertEqual((self.game/'coop/profile.ini').read_bytes(),before)

    def test_stale_or_malformed_core_cannot_be_sealed_even_when_hashes_match(self):
        for data in [core_pe(7),core_pe(8)]+[malformed_core(kind,suite.PROTOCOL) for kind in (
                'missing','forwarded','writable','executable','out_of_bounds','export_count','ordinal','truncated')]:
            self.fixture.repin_core(data)
            result=self.native('seal')
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertFalse((self.game/'coop/install.json').exists())

    def test_native_and_python_receipts_are_identical(self):
        python=suite.seal_installation(self.game)
        result=self.native('check')
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.native('seal')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),python)
        self.assertTrue(suite.check_installation(self.game)['ok'])

    def test_eweapon_json_changes_affect_gameplay_and_extra_json_is_rejected(self):
        root=self.game/'uo/eWeapons'
        root.mkdir(parents=True)
        weapon=root/'test.json'
        weapon.write_text('{"speed":1}')
        first=suite.seal_installation(self.game)['variants']
        result=self.native('check')
        self.assertEqual(result.returncode,0,result.stderr)
        weapon.write_text('{"speed":2}')
        second=suite.seal_installation(self.game)['variants']
        self.assertNotEqual(first['uo'],second['uo'])
        result=self.native('check')
        self.assertEqual(result.returncode,0,result.stderr)
        (root/'new.JSON').write_text('{}')
        result=self.native('check')
        self.assertNotEqual(result.returncode,0)

    def test_native_rollback_restores_only_journalled_files(self):
        path=self.game/'ddraw.dll'
        backup=self.game/'ddraw.dll.coop-backup.test'
        backup.write_bytes(path.read_bytes())
        original=backup.read_bytes()
        path.write_bytes(b'updated')
        save=self.game/'Main/save/autosave.svg'
        untouched=save.read_bytes()
        def windows(p): return native_path(p)
        config=self.game/'Main/config.cfg'
        config_backup=self.game/'Main/config.cfg.backup'
        config_backup.write_bytes(config.read_bytes())
        config.write_bytes(b'PLAYER_CHANGED_SETTINGS')
        (self.game/'coop/last-install-backup.json').write_text(json.dumps([
            {'path':windows(path),'backup':windows(backup),'existed':True},
            {'path':windows(config),'backup':windows(config_backup),'existed':True}]))
        result=self.native('rollback')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(save.read_bytes(),untouched)
        self.assertEqual(config.read_bytes(),b'PLAYER_CHANGED_SETTINGS')

    def test_same_size_change_rejected_and_lowercase_main_compatible(self):
        temporary=self.game/'main_case_swap'
        (self.game/'Main').rename(temporary)
        temporary.rename(self.game/'main')
        suite.seal_installation(self.game)
        result=self.native('check')
        self.assertEqual(result.returncode,0,result.stderr)
        path=self.game/'codcoop_core.dll'
        path.write_bytes(b'X'*path.stat().st_size)
        result=self.native('check')
        self.assertNotEqual(result.returncode,0)


    def test_canonical_backup_is_receipted_and_mixed_languages_share_gameplay_digest(self):
        relative='Main/localized_english_pak0.pk3'
        canonical='coop/languages/en/'+relative
        self.fixture.write(canonical,b'approved English')
        metadata='coop/languages/en/manifest.json'
        self.fixture.write(metadata,suite.canonical({'schema':1,'language':'en','files':{
            relative:{'sha256':suite.sha256(self.game/canonical)}}}))
        lock=json.loads((self.game/'coop/runtime-lock.json').read_text())
        lock['files'][metadata]=suite.sha256(self.game/metadata)
        self.fixture.write('coop/runtime-lock.json',suite.canonical(lock))
        english=suite.seal_installation(self.game)
        self.assertIn(canonical,english['files'])
        self.assertNotIn(canonical,lock['files'])
        result=self.native('check');self.assertEqual(result.returncode,0,result.stderr)
        self.fixture.write(relative,b'Deutsch')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        self.assertNotEqual(self.native('check').returncode,0)
        german=suite.seal_installation(self.game)
        self.assertEqual(german['variants'],english['variants'])
        self.assertEqual(self.native('check').returncode,0)
        self.assertEqual(self.native('seal').returncode,0)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),german)
        self.fixture.write(canonical,b'unapproved replacement')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        self.assertNotEqual(self.native('seal').returncode,0)

    def test_missing_essential_mission_package_cannot_be_sealed(self):
        (self.game/'Main/pak4.pk3').unlink()
        with self.assertRaises(ValueError): suite.seal_installation(self.game)
        result=self.native('seal')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.game/'coop/install.json').exists())

    def test_root_weapon_json_is_receipted_and_affects_only_yap_profiles(self):
        original=suite.seal_installation(self.game)
        self.fixture.write('eWeapons/nested/weapon.JSON',b'{"damage":31}')
        self.fixture.write('eWeapons/ignored.pk3',b'not a YAP JSON layer')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        self.assertNotEqual(self.native('check').returncode,0)
        changed=suite.seal_installation(self.game)
        self.assertNotIn('eWeapons/ignored.pk3',changed['files'])
        self.assertEqual(changed['variants']['cod1'],original['variants']['cod1'])
        self.assertNotEqual(changed['variants']['uo'],original['variants']['uo'])
        self.assertEqual(self.native('check').returncode,0)
        self.assertEqual(self.native('seal').returncode,0)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),changed)
        self.fixture.write('eWeapons/unreceipted.JSON',b'{"damage":99}')
        self.assertNotEqual(self.native('check').returncode,0)


    def test_unknown_and_modified_localization_cannot_hide_gameplay_changes(self):
        baseline=suite.seal_installation(self.game)
        self.fixture.write('Main/localized_english_pak0.pk3',b'gameplay changes hidden behind a language filename')
        modified=suite.seal_installation(self.game)
        self.assertNotEqual(modified['variants']['cod1'],baseline['variants']['cod1'])
        self.assertEqual(self.native('check').returncode,0)
        self.assertEqual(self.native('seal').returncode,0)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),modified)
        self.fixture.write('Main/localized_custom.pk3',b'additional gameplay archive')
        unknown=suite.seal_installation(self.game)
        self.assertNotEqual(unknown['variants']['cod1'],modified['variants']['cod1'])
        self.assertEqual(self.native('check').returncode,0)
        self.assertEqual(self.native('seal').returncode,0)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),unknown)


    def test_save_area_metadata_cannot_redirect_native_storage(self):
        manifest=json.loads((self.game/'coop/variants.json').read_text())
        manifest['variants'][2]['save_root']='Main/save'
        self.fixture.write('coop/variants.json',suite.canonical(manifest))
        lock=json.loads((self.game/'coop/runtime-lock.json').read_text())
        lock['manifest_sha256']=suite.sha256(self.game/'coop/variants.json')
        self.fixture.write('coop/runtime-lock.json',suite.canonical(lock))
        with self.assertRaises(ValueError): suite.seal_installation(self.game)
        self.assertNotEqual(self.native('seal').returncode,0)

    def test_multiplayer_filename_does_not_exempt_loaded_gameplay_archive(self):
        import io
        import zipfile
        baseline=suite.seal_installation(self.game)
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            archive.writestr('maps/_load.gsc','main() { level.changed_by_extra_package = true; }')
        self.fixture.write('uo/uomappack00.pk3',data.getvalue())
        self.assertFalse(suite.check_installation(self.game)['ok'])
        self.assertNotEqual(self.native('check').returncode,0)
        changed=suite.seal_installation(self.game)
        self.assertEqual(changed['variants']['cod1'],baseline['variants']['cod1'])
        self.assertNotEqual(changed['variants']['uo'],baseline['variants']['uo'])
        self.assertNotEqual(changed['variants']['united_fronts'],baseline['variants']['united_fronts'])
        self.assertEqual(self.native('check').returncode,0)
        self.assertEqual(self.native('seal').returncode,0)
        self.assertEqual(json.loads((self.game/'coop/install.json').read_text()),changed)

    @unittest.skipIf(os.name=='nt', 'requires a case-sensitive Wine backing filesystem')
    def test_case_colliding_content_roots_and_package_names_are_rejected(self):
        suite.seal_installation(self.game)
        alternate=self.game/'main'
        alternate.mkdir()
        (alternate/'zz_untracked.pk3').write_bytes(b'content visible through lowercase engine root')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        with self.assertRaises(ValueError): suite.seal_installation(self.game)
        self.assertNotEqual(self.native('check').returncode,0)
        self.assertNotEqual(self.native('seal').returncode,0)
        (alternate/'zz_untracked.pk3').unlink()
        alternate.rmdir()
        duplicate=self.game/'Main/PAK0.PK3'
        duplicate.write_bytes(b'different case alias of required package')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        with self.assertRaises(ValueError): suite.seal_installation(self.game)
        self.assertNotEqual(self.native('check').returncode,0)
        self.assertNotEqual(self.native('seal').returncode,0)
