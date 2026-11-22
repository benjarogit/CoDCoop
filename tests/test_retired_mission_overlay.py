"""Real update/rollback ownership checks for the corrected native PK3 precedence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('retired_installer',Path(__file__).parents[1]/'tools/install-linux.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class RetiredOverlay(unittest.TestCase):
    def fixture(self,root,basename='zzzzz_codcoop_triggers.pk3',owned=True):
        game=root/'game';payload=root/'payload'
        for tree in (game,payload):
            (tree/'coop').mkdir(parents=True);(tree/'main').mkdir()
        old=game/'main'/basename;old.write_bytes(b'OLD_SCRIPT')
        new=payload/'main/zzzz_coop_triggers.pk3';new.write_bytes(b'NEW_SCRIPT')
        pin=lambda data:hashlib.sha256(data).hexdigest()
        if owned:(game/'coop/runtime-lock.json').write_text(json.dumps({'files':{'Main/'+basename:pin(b'OLD_SCRIPT')}}))
        (payload/'coop/runtime-lock.json').write_text(json.dumps({'files':{'Main/zzzz_coop_triggers.pk3':pin(b'NEW_SCRIPT')}}))
        return game,payload,old,new

    def test_both_old_names_retired_once_and_rollback_restores_exact_bytes_and_saves(self):
        for basename in installer.RETIRED_TRIGGER_BASENAMES:
            with self.subTest(basename=basename),tempfile.TemporaryDirectory() as directory:
                game,payload,old,new=self.fixture(Path(directory),basename)
                save=game/'main/save/autosave/test.svg';save.parent.mkdir(parents=True);save.write_bytes(b'PERSONAL_SAVE')
                config=game/'main/config.cfg';config.write_bytes(b'PERSONAL_CONFIG')
                installer.preflight_retired_trigger_overlays(game,payload)
                self.assertFalse((game/'coop/backups').exists())
                tx=installer.InstallTransaction(game)
                installer.remove_obsolete_owned_files(game,payload,tx)
                self.assertFalse(old.exists())
                tx.copy(new,'Main/zzzz_coop_triggers.pk3')
                self.assertEqual((game/'main/zzzz_coop_triggers.pk3').read_bytes(),b'NEW_SCRIPT')
                tx.rollback()
                self.assertEqual(old.read_bytes(),b'OLD_SCRIPT')
                self.assertFalse((game/'main/zzzz_coop_triggers.pk3').exists())
                self.assertEqual(save.read_bytes(),b'PERSONAL_SAVE');self.assertEqual(config.read_bytes(),b'PERSONAL_CONFIG')

    def test_unowned_or_modified_old_overlay_blocks_before_any_mutation(self):
        for owned in (False,True):
            with self.subTest(owned=owned),tempfile.TemporaryDirectory() as directory:
                game,payload,old,_=self.fixture(Path(directory),owned=owned)
                if owned:old.write_bytes(b'USER_EDIT')
                before=old.read_bytes();tx=installer.InstallTransaction(game)
                with self.assertRaisesRegex(ValueError,'modified or not payload-owned'):
                    installer.remove_obsolete_owned_files(game,payload,tx)
                self.assertEqual(tx.entries,{})
                self.assertEqual(old.read_bytes(),before)
                self.assertFalse((game/'coop/backups').exists())

    def test_replacement_hash_is_verified_before_retiring_old_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            game,payload,old,new=self.fixture(Path(directory));new.write_bytes(b'BAD_SCRIPT')
            with self.assertRaisesRegex(ValueError,'replacement mission overlay'):
                installer.preflight_retired_trigger_overlays(game,payload)
            self.assertEqual(old.read_bytes(),b'OLD_SCRIPT')

    def test_retained_legacy_path_in_replacement_lock_is_not_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            game,payload,old,_=self.fixture(Path(directory))
            lock=payload/'coop/runtime-lock.json';data=json.loads(lock.read_text())
            data['files']['Main/'+old.name]=hashlib.sha256(old.read_bytes()).hexdigest();lock.write_text(json.dumps(data))
            tx=installer.InstallTransaction(game);installer.remove_obsolete_owned_files(game,payload,tx)
            self.assertTrue(old.exists());self.assertEqual(tx.entries,{})


if __name__=='__main__':unittest.main()
