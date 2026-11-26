"""Installer regression tests: payload preservation, rollback and pinned resume."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'tools/install-linux.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

LAUNCHER_NAME = 'CoD-Coop-Launcher.exe' if os.name == 'nt' else 'CoD-Coop-Launcher'


class Response(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content)
        self.status = status
        self.headers = headers or {}


class InstallerTests(unittest.TestCase):
    def test_same_size_file_is_replaced_and_rollback_restores_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / 'game'
            game.mkdir()
            (game / 'ddraw.dll').write_bytes(b'OLD!')
            source = root / 'new.dll'
            source.write_bytes(b'NEW!')
            tx = installer.InstallTransaction(game)
            tx.copy(source, 'ddraw.dll')
            self.assertEqual((game / 'ddraw.dll').read_bytes(), b'NEW!')
            tx.copy(source, 'new.dll')
            tx.rollback()
            self.assertEqual((game / 'ddraw.dll').read_bytes(), b'OLD!')
            self.assertFalse((game / 'new.dll').exists())
            self.assertEqual(json.loads((tx.root / 'journal.json').read_text())['state'], 'rolled-back')

    def test_completed_transaction_can_be_rolled_back_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'ddraw.dll').write_bytes(b'OLD')
            source=root/'payload'
            source.write_bytes(b'NEW')
            tx=installer.InstallTransaction(root)
            tx.copy(source,'ddraw.dll')
            tx.complete()
            installer.rollback_installation(root)
            self.assertEqual((root/'ddraw.dll').read_bytes(),b'OLD')

    def test_public_rollback_preserves_later_personal_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'Main').mkdir()
            config=root/'Main/config.cfg'
            config.write_bytes(b'ORIGINAL')
            tx=installer.InstallTransaction(root)
            tx.remember('Main/config.cfg')
            config.write_bytes(b'INSTALLER_SETTING')
            tx.complete()
            config.write_bytes(b'PLAYER_LATER_SETTING')
            installer.rollback_installation(root)
            self.assertEqual(config.read_bytes(),b'PLAYER_LATER_SETTING')

    def test_upgrade_retires_only_unchanged_publisher_owned_overlays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game=root/'game';payload=root/'payload'
            (game/'sp_improved').mkdir(parents=True);(game/'coop').mkdir();(payload/'coop').mkdir(parents=True)
            old=game/'sp_improved/pakzz_codcoop.pk3';old.write_bytes(b'OLD_PATCH')
            custom=game/'sp_improved/my_codcoop_texture.pk3';custom.write_bytes(b'USER_EDIT')
            files={'sp_improved/pakzz_codcoop.pk3':hashlib.sha256(b'OLD_PATCH').hexdigest(),
                   'sp_improved/my_codcoop_texture.pk3':hashlib.sha256(b'PUBLISHED_OLD').hexdigest()}
            (game/'coop/runtime-lock.json').write_text(json.dumps({'files':files}))
            (payload/'coop/runtime-lock.json').write_text(json.dumps({'files':{}}))
            tx=installer.InstallTransaction(game)
            installer.remove_obsolete_owned_files(game,payload,tx)
            self.assertFalse(old.exists());self.assertTrue(custom.exists())
            tx.rollback();self.assertEqual(old.read_bytes(),b'OLD_PATCH')

    def test_existing_personal_files_are_preserved(self):
        for rel in ('Main/config.cfg', 'uo/config_mp.cfg', 'sp_improved/uoconfig.cfg', 'uo/save/test.svg'):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                dst = root / rel
                dst.parent.mkdir(parents=True)
                dst.write_bytes(b'PERSONAL')
                source = root / 'payload.cfg'
                source.write_bytes(b'PACKAGE')
                tx = installer.InstallTransaction(root)
                tx.copy(source, rel)
                self.assertEqual(dst.read_bytes(), b'PERSONAL')
                self.assertFalse(tx.entries)

    def test_package_does_not_import_foreign_saves_or_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'payload'
            source.write_bytes(b'FOREIGN')
            tx=installer.InstallTransaction(root)
            for rel in ('Main/config.cfg','uo/save/autosave.svg'):
                tx.copy(source,rel)
                self.assertFalse((root/rel).exists())
            self.assertFalse(tx.entries)

    def test_lowercase_main_reuses_existing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            (game/'main').mkdir()
            (game/'main/config.cfg').write_bytes(b'PERSONAL')
            source=game/'payload.cfg'
            source.write_bytes(b'PACKAGE')
            tx=installer.InstallTransaction(game)
            tx.copy(source,'Main/config.cfg')
            self.assertEqual((game/'main/config.cfg').read_bytes(),b'PERSONAL')
            self.assertEqual([entry.name for entry in game.iterdir() if entry.is_dir()], ['main'])

    def test_path_traversal_and_external_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / 'game'
            game.mkdir()
            (game / 'escape').symlink_to(root, target_is_directory=True)
            tx = installer.InstallTransaction(game)
            for rel in ('../outside', '/outside', 'C:/outside', 'escape/outside'):
                with self.subTest(rel=rel), self.assertRaises(ValueError):
                    tx.remember(rel)

    def test_backup_directory_cannot_escape_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            game=root/'game'
            outside=root/'outside'
            game.mkdir();outside.mkdir()
            (game/'coop').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):
                installer.InstallTransaction(game)
            self.assertFalse(list(outside.iterdir()))

    def test_resume_appends_only_at_verified_offset(self):
        data = b'prefix-and-the-rest'
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'asset.zip'
            Path(str(dest) + '.part').write_bytes(data[:7])
            response = Response(data[7:], 206, {'Content-Range': 'bytes 7-18/19'})
            with mock.patch.object(installer.urllib.request, 'urlopen', return_value=response) as urlopen:
                installer.download('https://example.test/asset', str(dest), hashlib.sha256(data).hexdigest(), len(data))
            self.assertEqual(urlopen.call_args.args[0].get_header('Range'), 'bytes=7-')
            self.assertEqual(dest.read_bytes(), data)

    def test_server_ignoring_range_replaces_partial(self):
        data = b'complete-content'
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'asset.zip'
            Path(str(dest) + '.part').write_bytes(b'stale')
            with mock.patch.object(installer.urllib.request, 'urlopen', return_value=Response(data)):
                installer.download('https://example.test/asset', str(dest), hashlib.sha256(data).hexdigest(), len(data))
            self.assertEqual(dest.read_bytes(), data)

    def test_wrong_hash_never_replaces_verified_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'asset.zip'
            dest.write_bytes(b'old')
            with mock.patch.object(installer.urllib.request, 'urlopen', return_value=Response(b'BAD')):
                with self.assertRaises(ValueError):
                    installer.download('https://example.test/asset', str(dest), hashlib.sha256(b'new').hexdigest(), 3)
            self.assertEqual(dest.read_bytes(), b'old')
            self.assertFalse(Path(str(dest) + '.part').exists())

    def test_archive_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('../outside', 'bad')
            with self.assertRaises(ValueError):
                installer.safe_extract(archive)
            self.assertFalse((Path(tmp) / 'outside').exists())

    def test_incomplete_install_rolls_back_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game, payload = root/'game', root/'payload'
            for p in (game, payload/'coop', game/'sp_improved', game/'UnitedFronts'):
                p.mkdir(parents=True, exist_ok=True)
            for rel in ('CoDSP.exe','CoDUOSP.exe','sp_improved/sp_improved_1.5.pk3','UnitedFronts/ZUnitedFronts_1.1_beta.pk3'):
                (game/rel).write_bytes(b'existing')
            (game/'ddraw.dll').write_bytes(b'original')
            (payload/'coop/variants.json').write_text('{}')
            (payload/'coop/launcher').mkdir()
            (payload/'coop/launcher'/LAUNCHER_NAME).write_bytes(b'test-placeholder-not-executed')
            (payload/'ddraw.dll').write_bytes(b'replacement')
            with mock.patch.object(installer, 'run_suite_validator', return_value=1):
                result=installer.suite_main(['--game',str(game),'--suite-source',str(payload),'--yes','--repair'])
            self.assertEqual(result,2)
            self.assertEqual((game/'ddraw.dll').read_bytes(),b'original')
            self.assertFalse((game/'coop/install.json').exists())


class LocalizationTests(unittest.TestCase):
    def test_canonical_english_inventory_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            game=Path(folder);base=game/'coop/languages/en';(base/'Main').mkdir(parents=True)
            source=base/'Main/localized_english_pak1.pk3';source.write_bytes(b'English source')
            (base/'manifest.json').write_text(json.dumps({'schema':1,'language':'en','files':{
                'Main/localized_english_pak1.pk3':{'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}}))
            self.assertEqual(installer.canonical_english_files(game),[(source,'Main/localized_english_pak1.pk3')])
            source.write_bytes(b'German replacement')
            with self.assertRaises(ValueError): installer.canonical_english_files(game)

    def test_language_cleanup_preserves_personal_files_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            game=Path(folder);(game/'main/save').mkdir(parents=True);(game/'uo').mkdir()
            files={'main/localized_english_pak2.pk3':b'German overlay','main/localized_english_pak6.PK3':b'German voice fix',
                   'main/config.cfg':b'personal settings','main/save/a.svg':b'personal progress','main/pak0.pk3':b'gameplay'}
            for name,value in files.items(): (game/name).write_bytes(value)
            tx=installer.InstallTransaction(game);installer.remove_active_localizations(game,tx)
            self.assertFalse((game/'main/localized_english_pak2.pk3').exists())
            self.assertFalse((game/'main/localized_english_pak6.PK3').exists())
            self.assertEqual((game/'main/config.cfg').read_bytes(),b'personal settings')
            self.assertEqual((game/'main/save/a.svg').read_bytes(),b'personal progress')
            self.assertEqual((game/'main/pak0.pk3').read_bytes(),b'gameplay')
            tx.rollback()
            for name,value in files.items(): self.assertEqual((game/name).read_bytes(),value)


class BaseCompletenessTests(unittest.TestCase):
    def test_embedded_campaigns_cannot_skip_missing_required_suite_patches(self):
        for location in ('game','payload'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);game=root/'game';overlay=root/'payload'
                game.mkdir();(overlay/'coop/launcher').mkdir(parents=True)
                (game/'CoDSP.exe').write_bytes(b'owned game');(game/'ddraw.dll').write_bytes(b'old intact module')
                (overlay/'coop/launcher'/LAUNCHER_NAME).write_bytes(b'not executed')
                for name in ('sp_improved/sp_improved_1.5.pk3','UnitedFronts/ZUnitedFronts_1.1_beta.pk3'):
                    path=(game if location=='game' else overlay)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'campaign already present')
                (overlay/'coop/variants.json').write_text(json.dumps({'required':[{'path':'Main/zzz_patch.pk3','sha256':hashlib.sha256(b'reviewed').hexdigest(),'size':8,'install_source':'suite'}]}))
                with mock.patch.object(installer,'download') as download, \
                     mock.patch.object(installer,'InstallTransaction') as transaction, \
                     mock.patch.object(installer,'run_suite_validator') as validator:
                    result=installer.suite_main(['--game',str(game),'--suite-source',str(overlay),'--yes'])
                self.assertEqual(result,2);download.assert_not_called();transaction.assert_not_called();validator.assert_not_called()
                self.assertEqual((game/'ddraw.dll').read_bytes(),b'old intact module')
                self.assertFalse((game/'coop/backups').exists())

    def test_suite_patch_preflight_checks_actual_pin_even_when_file_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'coop').mkdir();(root/'Main').mkdir()
            patch=root/'Main/zzz_patch.pk3';patch.write_bytes(b'reviewed')
            (root/'coop/variants.json').write_text(json.dumps({'required':[{'path':'Main/zzz_patch.pk3','sha256':hashlib.sha256(b'reviewed').hexdigest(),'size':8,'install_source':'suite'}]}))
            installer.require_suite_owned_patches(root)
            patch.write_bytes(b'changed!')
            with self.assertRaisesRegex(ValueError,'missing or changed'):
                installer.require_suite_owned_patches(root)

    def test_missing_original_mission_data_aborts_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';overlay=root/'payload'
            game.mkdir();(overlay/'coop/launcher').mkdir(parents=True)
            (game/'CoDSP.exe').write_bytes(b'owned game')
            (game/'ddraw.dll').write_bytes(b'previous mod')
            (overlay/'coop/launcher'/LAUNCHER_NAME).write_bytes(b'not executed')
            (overlay/'coop/variants.json').write_text(json.dumps({'required':[{'path':'Main/pak4.pk3','kind':'base_content','engine':'cod1'}]}))
            with mock.patch.object(installer,'run_suite_validator') as validate:
                result=installer.suite_main(['--game',str(game),'--suite-source',str(overlay),'--yes'])
            self.assertEqual(result,2);validate.assert_not_called()
            self.assertEqual((game/'ddraw.dll').read_bytes(),b'previous mod')
            self.assertFalse((game/'coop/backups').exists())
            (overlay/'Main').mkdir();(overlay/'Main/pak4.pk3').write_bytes(b'verified full payload supplies the base')
            installer.require_original_campaign_source(game,overlay)

    def test_only_known_invalid_placeholder_is_removed_and_backed_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);game=root/'game';overlay=root/'payload';(game/'Main').mkdir(parents=True);(overlay/'coop').mkdir(parents=True)
            path=game/'Main/pakb.pk3';path.write_bytes(b' ')
            (overlay/'coop/variants.json').write_text(json.dumps({'ignored_placeholder':{'path':'Main/pakb.pk3','size':1,'sha256':hashlib.sha256(b' ').hexdigest()}}))
            tx=installer.InstallTransaction(game);installer.remove_known_invalid_placeholder(game,overlay,tx)
            self.assertFalse(path.exists());tx.rollback();self.assertEqual(path.read_bytes(),b' ')
            path.write_bytes(b'valid custom archive bytes are preserved')
            tx=installer.InstallTransaction(game);installer.remove_known_invalid_placeholder(game,overlay,tx)
            self.assertEqual(path.read_bytes(),b'valid custom archive bytes are preserved')


if __name__ == '__main__':
    unittest.main()
