import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import qa_coop
from build_coop_localization import package_bytes,INSTALLED_PATH

class QaUiLanguages(unittest.TestCase):
    def test_exact_player_count_and_explicit_default_english(self):
        self.assertEqual(qa_coop.parse_ui_languages(None,2),['en','en'])
        self.assertEqual(qa_coop.parse_ui_languages('de,en,de,en',4),['de','en','de','en'])
        for value in ('','en','en,','en,en,en','EN,de','en,fr',',de'):
            with self.subTest(value=value),self.assertRaises(ValueError):qa_coop.parse_ui_languages(value,2)
        with self.assertRaises(ValueError):qa_coop.parse_ui_languages(None,3)
        with patch('sys.stderr'),self.assertRaises(SystemExit):
            qa_coop.main(['--source','unused','--run','unused','--players','4','--ui-languages','en,de','--prepare-only'])

    def owned(self,root):
        output=root/'run';folder=output/'host';(folder/'Main').mkdir(parents=True)
        (output/'.codcoop-qa-owned').write_text('isolated CoDCoop QA\n')
        return output,folder

    def test_reviewed_banks_kept_or_archived_before_explicit_change(self):
        with tempfile.TemporaryDirectory() as directory:
            output,folder=self.owned(Path(directory))
            a=qa_coop.prepare_qa_ui_locale(output,folder,'de')
            target=folder/INSTALLED_PATH
            self.assertEqual(target.read_bytes(),package_bytes('de'))
            self.assertEqual(a['scope'],'OWNED_GENERATED_QA_LOCALE_BANK_ONLY')
            self.assertFalse(a['installer_language_selection_verified'])
            b=qa_coop.prepare_qa_ui_locale(output,folder,'de')
            self.assertEqual(b['action'],'kept-reviewed-bank')
            c=qa_coop.prepare_qa_ui_locale(output,folder,'en')
            self.assertEqual(c['previous_language'],'de')
            self.assertEqual(Path(c['previous_archived']).read_bytes(),package_bytes('de'))
            self.assertEqual(target.read_bytes(),package_bytes('en'))
            self.assertEqual(c['sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
            target.write_bytes(b'unknown mod')
            with self.assertRaisesRegex(ValueError,'unknown'):qa_coop.prepare_qa_ui_locale(output,folder,'en')
            self.assertEqual(target.read_bytes(),b'unknown mod')

    def test_no_live_or_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output,folder=self.owned(root)
            (output/'.codcoop-qa-owned').unlink()
            with self.assertRaisesRegex(ValueError,'owned'):qa_coop.prepare_qa_ui_locale(output,folder,'en')
            (output/'.codcoop-qa-owned').touch()
            (folder/'Main').rmdir();live=root/'live';live.mkdir();sentinel=live/Path(INSTALLED_PATH).name;sentinel.write_bytes(b'live')
            (folder/'Main').symlink_to(live,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'Unsafe'):qa_coop.prepare_qa_ui_locale(output,folder,'en')
            self.assertEqual(sentinel.read_bytes(),b'live')
            with self.assertRaisesRegex(ValueError,'owned'):qa_coop.prepare_qa_ui_locale(output,live,'en')

    def test_prepare_only_generates_each_folder_before_launch_without_source_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';(source/'Main').mkdir(parents=True)
            (source/'Main/source.txt').write_text('original')
            runtime=root/'immutable';runtime.mkdir()
            for name in ('ddraw.dll','codcoop_core.dll'):(runtime/name).write_bytes(b'fixture runtime; not executed')
            output=root/'qa';argv=['--source',str(source),'--run',str(output),'--runtime-dir',str(runtime),'--prepare-only']
            self.assertEqual(qa_coop.main(argv+['--ui-languages','de,en']),0)
            report=json.loads((output/'provenance.json').read_text())
            self.assertEqual(report['ui_languages'],['de','en'])
            self.assertEqual((output/'host'/INSTALLED_PATH).read_bytes(),package_bytes('de'))
            self.assertEqual((output/'join1'/INSTALLED_PATH).read_bytes(),package_bytes('en'))
            self.assertFalse((source/INSTALLED_PATH).exists())
            self.assertEqual(qa_coop.main(argv),0)
            report=json.loads((output/'provenance.json').read_text())
            self.assertEqual(report['ui_languages'],['en','en'])
            self.assertEqual(report['ui_locale_banks'][0]['previous_language'],'de')
            self.assertTrue(Path(report['ui_locale_banks'][0]['previous_archived']).is_file())
            for name in ('host','join1'):self.assertEqual((output/name/INSTALLED_PATH).read_bytes(),package_bytes('en'))
            self.assertEqual((source/'Main/source.txt').read_text(),'original')

if __name__=='__main__':unittest.main()
