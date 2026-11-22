import sys
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from campaign_inventory import inventory,layer_files,native_package_key
from build_campaign_patch import quarantine_obsolete_qa_trigger_overlays, TRIGGER_OVERLAY_BASENAME


class NativePackageOrder(unittest.TestCase):
    def test_generated_mission_provider_overrides_variant_pathfinder(self):
        # Both real overlays contain this entry. More Zs lost to '_' in the
        # native ASCII-uppercase comparator; explicit T > C fixes precedence.
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'UnitedFronts';folder.mkdir()
            for name,body in [('ZUnitedFronts_1.1_beta.pk3',b'original'),
                              ('zzzz_coop_campaign.pk3',b'variant-asset-repair'),
                              ('zzzzz_codcoop_triggers.pk3',b'old-mission')]:
                with zipfile.ZipFile(folder/name,'w') as archive:
                    archive.writestr('maps/pathfinder.gsc',body)
            def provider():
                for package in sorted(folder.glob('*.pk3'),key=lambda p:native_package_key(p.name),reverse=True):
                    with zipfile.ZipFile(package) as archive:
                        if 'maps/pathfinder.gsc' in archive.namelist():
                            return package.name,archive.read('maps/pathfinder.gsc')
            self.assertEqual(provider(),('zzzz_coop_campaign.pk3',b'variant-asset-repair'))
            with zipfile.ZipFile(folder/TRIGGER_OVERLAY_BASENAME,'w') as archive:
                archive.writestr('maps/pathfinder.gsc',b'eligible-remote-use-and-helmet-repair')
            self.assertEqual(provider(),(TRIGGER_OVERLAY_BASENAME,b'eligible-remote-use-and-helmet-repair'))

    def test_qa_retirement_archives_only_known_generated_old_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);folder=game/'UnitedFronts';folder.mkdir()
            old=folder/'zzzzz_codcoop_triggers.pk3'
            marker={'schema':1,'profile':'united_fronts','sources':{'maps/pathfinder.gsc':'pin'},
                    'changes':['reviewed-player-trigger-activators']}
            with zipfile.ZipFile(old,'w') as archive:
                archive.writestr('codcoop/trigger-overlay.json',json.dumps(marker))
            original=old.read_bytes();current=folder/TRIGGER_OVERLAY_BASENAME;current.write_bytes(b'current')
            unknown=folder/'zzzzz_coop_triggers.pk3';unknown.write_bytes(b'unowned')
            with self.assertRaisesRegex(ValueError,'unrecognized'):quarantine_obsolete_qa_trigger_overlays(game)
            self.assertEqual(old.read_bytes(),original) # preflight before any move
            unknown.unlink()
            archived=quarantine_obsolete_qa_trigger_overlays(game)
            self.assertEqual(len(archived),1);self.assertEqual(Path(archived[0]).read_bytes(),original)
            self.assertFalse(old.exists());self.assertEqual(current.read_bytes(),b'current')

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
