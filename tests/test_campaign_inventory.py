import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from campaign_inventory import inventory,layer_files,native_package_key


class NativePackageOrder(unittest.TestCase):
    def test_observed_native_search_order_is_not_lowercase_sort(self):
        # Exact order printed by the real CoD1 engine, highest priority first.
        observed=['zzz_patch.pk3','zzzzz_codcoop_triggers.pk3',
                  'zzzzzzz_kar98k_firing_anim_fix.pk3','zzzzzzzz_qa_brecourt.pk3','pakz_coop.pk3']
        self.assertEqual(sorted(observed,key=native_package_key,reverse=True),observed)
        self.assertNotEqual(sorted(observed,key=str.lower,reverse=True),observed)

    def test_native_ascii_fold_and_path_normalization(self):
        self.assertEqual(native_package_key('a:B\\c.pk3'),native_package_key('A/B/C.PK3'))
        with self.assertRaises(ValueError):native_package_key('a.pk3','cod2')

    def test_cod1_alias_is_engine_specific_and_not_a_loaded_disk_name(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);(game/'Main').mkdir()
            for name in ('sp_test.pk3','zzz_test.pk3','zz_alias.pk3','mp_test.pk3','localized_english_test.pk3'):
                (game/'Main'/name).touch()
            self.assertEqual([p.name for p in layer_files(game,'Main','cod1')],['zzz_test.pk3','sp_test.pk3'])
            self.assertEqual([p.name for p in layer_files(game,'Main','uo')],['mp_test.pk3','sp_test.pk3','zzz_test.pk3','zz_alias.pk3'])

    def test_effective_script_provider_uses_each_profile_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory)
            for folder in ('Main','uo','sp_improved','UnitedFronts'):(game/folder).mkdir()
            for name in ('sp_test.pk3','zzz_test.pk3'):
                with zipfile.ZipFile(game/'Main'/name,'w') as archive:
                    archive.writestr('maps/test.gsc','main() {}')
            report=inventory(game)
            self.assertEqual(report['profiles']['cod1']['scripts'][0]['package'],'Main/sp_test.pk3')
            self.assertEqual(report['profiles']['uo']['scripts'][0]['package'],'Main/zzz_test.pk3')


if __name__=='__main__':unittest.main()
