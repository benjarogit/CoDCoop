import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile
from unittest import mock
from pe_fixtures import core_pe, malformed_core, malformed_feature

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('coop_suite', ROOT / 'tools/coop_suite.py')
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


class SuiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        self.manifest = json.loads((ROOT / 'content/variants.json').read_text())
        for item in self.manifest['required']:
            p = self.game / item['path']
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(core_pe(suite.PROTOCOL) if item['path']=='codcoop_core.dll' else item['path'].encode())
            item['sha256'] = suite.sha256(p)
            item.pop('sha256_any', None)
        for root in ('Main', 'uo', 'sp_improved', 'UnitedFronts'):
            (self.game / root).mkdir(exist_ok=True)
        self.write('Main/localized_english_pak0.pk3', b'English')
        self.manifest['approved_localizations'] = {
            'Main/localized_english_pak0.pk3': [hashlib.sha256(value).hexdigest() for value in (b'English', b'Deutsch')]}
        self.write('Main/config.cfg', b'player settings')
        self.write('Main/save/autosave.svg', b'important save')
        self.write('coop/variants.json', suite.canonical(self.manifest))
        self.write('coop/runtime-lock.json', suite.canonical({
            'suite_version': self.manifest['suite_version'],
            'manifest_sha256': suite.sha256(self.game / 'coop/variants.json'),
            'files': {p: suite.sha256(self.game / p) for p in suite.RUNTIME}}))

    def write(self, name, data):
        path = self.game / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def repin_core(self, data):
        """Simulate a package author pinning a stale/malformed Core's bytes."""
        self.write('codcoop_core.dll',data)
        for item in self.manifest['required']:
            if item['path']=='codcoop_core.dll': item['sha256']=suite.sha256(self.game/'codcoop_core.dll')
        self.write('coop/variants.json',suite.canonical(self.manifest))
        lock=json.loads((self.game/'coop/runtime-lock.json').read_text())
        lock['manifest_sha256']=suite.sha256(self.game/'coop/variants.json')
        lock['files']['codcoop_core.dll']=suite.sha256(self.game/'codcoop_core.dll')
        self.write('coop/runtime-lock.json',suite.canonical(lock))

    def test_stale_or_malformed_core_cannot_be_sealed_even_with_matching_package_hashes(self):
        examples=[core_pe(7),core_pe(8)]+[malformed_core(kind,suite.PROTOCOL) for kind in (
            'missing','forwarded','writable','executable','out_of_bounds','export_count','ordinal','truncated')]
        for data in examples:
            with self.subTest(core=data[:16]):
                self.repin_core(data)
                with self.assertRaises(ValueError): suite.seal_installation(self.game)
                self.assertFalse((self.game/'coop/install.json').exists())

    def test_complete_seal_and_prepare(self):
        suite.seal_installation(self.game)
        self.assertTrue(suite.check_installation(self.game)['ok'])
        suite.prepare(self.game, 'united_fronts')
        config = (self.game / 'coop/profile.ini').read_text()
        self.assertIn('variant=united_fronts', config)
        self.assertEqual((self.game / 'Main/save/autosave.svg').read_bytes(), b'important save')
        self.assertEqual((self.game / 'Main/config.cfg').read_bytes(), b'player settings')

    def test_missing_partial_or_unsafe_compiled_features_cannot_be_sealed_or_prepared(self):
        examples=[core_pe(suite.PROTOCOL,bits) for bits in (None,0,1,3,7)]
        examples += [malformed_feature(kind,suite.PROTOCOL) for kind in ('forwarded','writable','executable','out_of_bounds','ordinal')]
        for data in examples:
            with self.subTest(core=data[-8:]):
                self.repin_core(data)
                with self.assertRaises(ValueError):suite.seal_installation(self.game)
                with self.assertRaises(ValueError):suite.prepare(self.game,'uo')
                self.assertFalse(suite.check_installation(self.game)['ok'])
                self.assertFalse((self.game/'coop/install.json').exists())

    def test_legacy_zero_features_requirement_does_not_claim_compiled_readiness(self):
        self.manifest['core_features_required']=0
        self.repin_core(core_pe(suite.PROTOCOL,None))
        self.assertTrue(suite.seal_installation(self.game))
        self.assertTrue(suite.check_installation(self.game)['ok'])

    def test_install_seals_once_but_later_launch_rechecks_content(self):
        with mock.patch.object(suite, 'collect', wraps=suite.collect) as collect:
            suite.seal_and_prepare(self.game, 'sp_improved')
            self.assertEqual(collect.call_count, 1)
        profile = (self.game / 'coop/profile.ini').read_bytes()
        self.write('uo/pakuo00.pk3', b'corrupted after installation')
        with self.assertRaises(ValueError):
            suite.prepare(self.game, 'sp_improved')
        self.assertEqual((self.game / 'coop/profile.ini').read_bytes(), profile)

    def test_modified_pinned_content_and_runtime_cannot_be_sealed(self):
        self.write('UnitedFronts/ZUnitedFronts_1.1_beta.pk3', b'changed')
        with self.assertRaisesRegex(ValueError, 'wrong pinned'):
            suite.seal_installation(self.game)
        self.write('UnitedFronts/ZUnitedFronts_1.1_beta.pk3', b'UnitedFronts/ZUnitedFronts_1.1_beta.pk3')
        self.write('codcoop_core.dll', b'old runtime')
        with self.assertRaises(ValueError):
            suite.seal_installation(self.game)

    def test_added_content_rejected_after_seal(self):
        suite.seal_installation(self.game)
        self.write('uo/zzz_extra.pk3', b'changes rules')
        self.assertFalse(suite.check_installation(self.game)['ok'])

    def test_global_yap_weapon_layer_is_verified_and_compared_for_uo_profiles(self):
        self.write('eWeapons/override.json', b'{"damage":1}')
        first = suite.seal_installation(self.game)['variants']
        self.write('eWeapons/override.json', b'{"damage":9}')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        second = suite.seal_installation(self.game)['variants']
        self.assertEqual(first['cod1'], second['cod1'])
        for variant in ('uo', 'sp_improved', 'united_fronts'):
            self.assertNotEqual(first[variant], second[variant])
        self.write('eWeapons/extra.JSON', b'{}')
        self.assertFalse(suite.check_installation(self.game)['ok'])

    def test_unrelated_settings_do_not_invalidate_receipt(self):
        suite.seal_installation(self.game)
        self.write('Main/config.cfg', b'new resolution')
        self.assertTrue(suite.check_installation(self.game)['ok'])

    def test_save_summary_is_variant_local_and_does_not_change_gameplay_identity(self):
        receipt = suite.seal_installation(self.game)
        os.utime(self.game / 'Main/save/autosave.svg', (100, 100))
        self.write('Main/save/later.SVG', b'native save')
        os.utime(self.game / 'Main/save/later.SVG', (200, 200))
        self.write('uo/save/expansion.svg', b'independent native save')
        checked = suite.check_installation(self.game)
        self.assertTrue(checked['ok'])
        self.assertEqual(checked['variants'], receipt['variants'])
        saved = checked['local_saves']
        self.assertEqual(saved['cod1']['count'], 2)
        self.assertEqual(saved['cod1']['latest']['name'], 'later.SVG')
        self.assertEqual(saved['uo']['latest']['name'], 'expansion.svg')
        self.assertEqual(saved['united_fronts'], {'count': 0, 'latest': None})

    def test_declared_save_area_cannot_point_at_another_variant(self):
        self.manifest['variants'][0]['save_root'] = 'uo/save'
        self.write('coop/variants.json', suite.canonical(self.manifest))
        with self.assertRaisesRegex(ValueError, 'save area'):
            suite.load_manifest(self.game)

    def test_native_autosave_subfolders_count_with_safe_relative_latest_name(self):
        receipt=suite.seal_installation(self.game)
        self.write('sp_improved/save/autosave/pathfinder.svg',b'actual-file native autosave layout')
        self.write('sp_improved/save/manual/Slot A.SVG',b'independent manual save')
        self.write('UnitedFronts/save/autosave/pathfinder.svg',b'other variant progress')
        os.utime(self.game/'sp_improved/save/autosave/pathfinder.svg',(300,300))
        os.utime(self.game/'sp_improved/save/manual/Slot A.SVG',(200,200))
        checked=suite.check_installation(self.game)
        self.assertEqual(checked['variants'],receipt['variants'])
        self.assertEqual(checked['local_saves']['sp_improved'],{'count':2,'latest':{'name':'autosave/pathfinder.svg','modified':'1970-01-01T00:05:00+00:00'}})
        self.assertEqual(checked['local_saves']['united_fronts']['latest']['name'],'autosave/pathfinder.svg')
        self.assertEqual(checked['local_saves']['uo'],{'count':0,'latest':None})

    def test_save_summary_never_follows_symlink_files_or_directories(self):
        with tempfile.TemporaryDirectory() as external:
            outside=Path(external);(outside/'private.svg').write_bytes(b'not variant progress')
            save=self.game/'Main/save'
            try:
                (save/'foreign.svg').symlink_to(outside/'private.svg')
                (save/'external').symlink_to(outside,target_is_directory=True)
                (save/'loop').symlink_to(save,target_is_directory=True)
            except OSError as error:self.skipTest('symlink privilege unavailable: '+str(error))
            summary=suite.local_save_summary(self.game,self.manifest)
            self.assertEqual(summary['cod1']['count'],1)
            self.assertEqual(summary['cod1']['latest']['name'],'autosave.svg')

    def test_languages_keep_gameplay_fingerprint_but_are_locally_verified(self):
        before = suite.seal_installation(self.game)['variants']
        self.write('Main/localized_english_pak0.pk3', b'Deutsch')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        after = suite.seal_installation(self.game)['variants']
        self.assertEqual(before, after)

    def test_unknown_or_modified_localized_content_changes_gameplay_fingerprint(self):
        before = suite.seal_installation(self.game)['variants']
        self.write('Main/localized_english_pak0.pk3', b'gameplay override hidden behind a language filename')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        modified = suite.seal_installation(self.game)['variants']
        self.assertNotEqual(before, modified)
        self.write('Main/localized_english_pak0.pk3', b'English')
        self.write('Main/localized_custom.pk3', b'unreviewed gameplay')
        unknown = suite.seal_installation(self.game)['variants']
        self.assertNotEqual(before, unknown)
        self.write('Main/localized_custom.pk3', b'changed gameplay')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        self.assertNotEqual(unknown, suite.seal_installation(self.game)['variants'])

    def test_multiplayer_filename_cannot_exempt_a_loaded_gameplay_override(self):
        before = suite.seal_installation(self.game)['variants']
        path = self.game / 'uo/uomappack00.pk3'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('maps/_load.gsc', 'main() { level.changed_rules = true; }')
        changed = suite.seal_installation(self.game)['variants']
        self.assertEqual(before['cod1'], changed['cod1'])
        for variant in ('uo', 'sp_improved', 'united_fronts'):
            self.assertNotEqual(before[variant], changed[variant])

    @unittest.skipIf(os.name == 'nt', 'requires a case-sensitive fixture filesystem')
    def test_case_equivalent_root_and_package_cannot_shadow_hashed_content(self):
        lower = self.game / 'main'
        lower.mkdir()
        with zipfile.ZipFile(lower / 'zz_shadow.pk3', 'w') as archive:
            archive.writestr('maps/_load.gsc', 'main() { level.changed_rules = true; }')
        with self.assertRaisesRegex(ValueError, 'ambiguous path'):
            suite.seal_installation(self.game)
        (lower / 'zz_shadow.pk3').unlink()
        lower.rmdir()
        self.write('Main/PAK0.PK3', b'shadowed package')
        with self.assertRaisesRegex(ValueError, 'ambiguous path'):
            suite.seal_installation(self.game)

    def test_localization_catalog_rejects_unsafe_or_malformed_exemptions(self):
        for catalog in ([], {'Main/../localized_bad.pk3': ['0' * 64]},
                        {'uo/localized_bad.pk3': ['not a hash']},
                        {'Main/weapon.pk3': ['0' * 64]},
                        {'Main/localized_\u212a.pk3': ['0' * 64]}):
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                suite.approved_localizations({'approved_localizations': catalog})

    def test_english_backup_is_verified_without_affecting_gameplay_identity(self):
        before = suite.seal_installation(self.game)['variants']
        name = 'Main/localized_english_pak0.pk3'
        self.write('coop/languages/en/' + name, b'canonical English')
        inventory = {'schema': 1, 'language': 'en', 'files': {
            name: {'sha256': suite.sha256(self.game / ('coop/languages/en/' + name))}}}
        self.write('coop/languages/en/manifest.json', suite.canonical(inventory))
        with self.assertRaisesRegex(ValueError, 'unowned canonical English inventory'):
            suite.seal_installation(self.game)
        lock = json.loads((self.game / 'coop/runtime-lock.json').read_text())
        lock['files']['coop/languages/en/manifest.json'] = suite.sha256(self.game / 'coop/languages/en/manifest.json')
        self.write('coop/runtime-lock.json', suite.canonical(lock))
        receipt = suite.seal_installation(self.game)
        self.assertEqual(receipt['variants'], before)
        self.assertIn('coop/languages/en/' + name, receipt['files'])
        self.assertTrue(suite.check_installation(self.game)['ok'])
        self.write('coop/languages/en/' + name, b'corrupted English')
        self.assertFalse(suite.check_installation(self.game)['ok'])
        with self.assertRaisesRegex(ValueError, 'canonical English backup'):
            suite.seal_installation(self.game)
        inventory['files']['../escape.pk3'] = inventory['files'][name]
        self.write('coop/languages/en/manifest.json', suite.canonical(inventory))
        with self.assertRaisesRegex(ValueError, 'unsafe canonical English path'):
            suite.seal_installation(self.game)

    def test_incomplete_and_unsafe_lock_rejected(self):
        (self.game / 'plugins/yap/DDRAW.dll').unlink()
        with self.assertRaises(ValueError):
            suite.seal_installation(self.game)
        for path in ('../secret', '/etc/passwd', 'C:/evil', 'foo\\bar'):
            with self.assertRaises(ValueError):
                suite.resolve(self.game, path)

    def test_missing_receipt_fails_closed(self):
        self.assertFalse(suite.check_installation(self.game)['ok'])

    def test_case_insensitive_main(self):
        (self.game / 'Main').rename(self.game / 'main')
        suite.seal_installation(self.game)
        self.assertTrue(suite.check_installation(self.game)['ok'])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            (self.game / 'escape').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                suite.resolve(self.game, 'escape/data.pk3')


if __name__ == '__main__':
    unittest.main()
