"""Original-menu validation and local-only preference persistence; no engine mocks."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import uf_equipment_preferences as preferences


class EquipmentPreferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())

    def manual(self):
        result=preferences.default_preferences(self.catalog)
        result['mode']='manual'
        result['manual']['slots']={'primary':9,'secondary':9,'pistol':22,'grenade':34}
        return result

    def capability(self):
        return {'id':preferences.CAPABILITY,'schema':1,'per_player':True,
                'ready_request':'uf-equipment-v1','catalog_sha256':preferences.catalog_digest(self.catalog),
                'modes':['automatic','manual']}

    def test_only_active_original_menu_choices_are_allowed(self):
        families=preferences.active_families(self.catalog)
        self.assertEqual(set(families),{'american','british','russian','german','italian'})
        value=self.manual();value['manual']['family']='polish'
        with self.assertRaises(ValueError):preferences.validate_preferences(value,self.catalog)
        value=self.manual();value['manual']['slots']['primary']=22  # binoculars belong in the original pistol slot
        with self.assertRaises(ValueError):preferences.validate_preferences(value,self.catalog)

    def test_four_slots_remain_independent_without_invented_mg_support_exclusion(self):
        value=self.manual()
        checked=preferences.validate_preferences(value,self.catalog)
        self.assertEqual(checked['manual']['slots'],{'primary':9,'secondary':9,'pistol':22,'grenade':34})
        checked['manual']['slots']['primary']=0
        self.assertEqual(value['manual']['slots']['primary'],9)
        for bad in (True,9.0,'9',999):
            wrong=self.manual();wrong['manual']['slots']['primary']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):preferences.validate_preferences(wrong,self.catalog)
        wrong=self.manual();del wrong['manual']['slots']['grenade']
        with self.assertRaises(ValueError):preferences.validate_preferences(wrong,self.catalog)

    def test_automatic_request_does_not_infer_or_send_manual_kit(self):
        value=self.manual();value['mode']='automatic'
        request=preferences.build_ready_request(value,self.catalog,self.capability())
        self.assertEqual(request['mode'],'automatic')
        self.assertNotIn('slots',request);self.assertNotIn('family',request)
        self.assertEqual(value['manual']['slots']['primary'],9)

    def test_protocol_number_or_a_manifest_claim_cannot_enable_future_ready_contract(self):
        for cap in (None,7,8,{'protocol':7},{'protocol':8},{'id':preferences.CAPABILITY},
                    {**self.capability(),'catalog_sha256':'0'*64},
                    {**self.capability(),'per_player':False},
                    {**self.capability(),'schema':True},
                    {**self.capability(),'modes':['automatic']}):
            with self.subTest(capability=cap),self.assertRaises(ValueError):preferences.build_ready_request(self.manual(),self.catalog,cap)
        result=preferences.build_ready_request(self.manual(),self.catalog,self.capability())
        self.assertEqual(set(result),{'kind','schema','scope','catalog_sha256','mode','family','slots'})
        self.assertEqual(result['scope'],'local-player')
        self.assertNotIn('player',result);self.assertNotIn('sp_campaign',result)

    def test_four_personal_preference_files_are_independent_and_preserve_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game=root/'game';game.mkdir()
            config=game/'config.cfg';config.write_bytes(b'personal settings')
            save=game/'autosave.svg';save.write_bytes(b'existing progress')
            paths=[root/'users'/str(i)/'equipment.json' for i in range(4)]
            values=[]
            for i,path in enumerate(paths):
                value=self.manual();value['manual']['slots']['primary']=i
                preferences.save_preferences(value,self.catalog,path);values.append(value)
            for path,value in zip(paths,values):self.assertEqual(preferences.load_preferences(self.catalog,path),value)
            preferences.save_preferences(preferences.default_preferences(self.catalog),self.catalog,paths[0])
            for path,value in zip(paths[1:],values[1:]):self.assertEqual(preferences.load_preferences(self.catalog,path),value)
            self.assertEqual(config.read_bytes(),b'personal settings');self.assertEqual(save.read_bytes(),b'existing progress')
            self.assertEqual(set(p.name for p in game.iterdir()),{'config.cfg','autosave.svg'})
            self.assertFalse(list(root.rglob('.equipment-*')))

    def test_bad_preferences_fail_without_overwriting_saved_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'equipment.json';preferences.save_preferences(self.manual(),self.catalog,path)
            before=path.read_bytes();bad=self.manual();bad['manual']['family']=[]
            with self.assertRaises(ValueError):preferences.save_preferences(bad,self.catalog,path)
            self.assertEqual(path.read_bytes(),before)
            path.write_text('{broken')
            with self.assertRaises(ValueError):preferences.load_preferences(self.catalog,path)
            self.assertEqual(path.read_text(),'{broken')

    def test_missing_catalog_weapon_is_rejected_and_all_choices_have_bilingual_names(self):
        broken=copy.deepcopy(self.catalog);broken['weapons']['mg30cal']={'missing':'weapons/sp/mg30cal'}
        with self.assertRaises(ValueError):preferences.validate_preferences(self.manual(),broken)
        for family in preferences.active_families(self.catalog).values():
            for slot in preferences.SLOTS:
                for choice in family['menu_slots'][slot]['choices'].values():
                    for language in ('en','de'):
                        label=preferences.choice_label(choice,language)
                        self.assertTrue(label);self.assertNotIn('@',label)
        self.assertIn('Fernglas',preferences.choice_label({'weapon':'binoculars'},'de'))

    @unittest.skipIf(os.name=='nt','Linux per-user config path')
    def test_default_storage_is_user_configuration_not_game_or_save(self):
        with mock.patch.dict(os.environ,{'XDG_CONFIG_HOME':'/tmp/coop-personal-config'}):
            self.assertEqual(preferences.preferences_path(),Path('/tmp/coop-personal-config/codcoop/equipment.json'))


if __name__=='__main__':unittest.main()
