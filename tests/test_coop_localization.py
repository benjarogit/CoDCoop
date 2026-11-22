import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from build_coop_localization import build,package_bytes,string_resource,KEYS,RESOURCE_PATH,INSTALLED_PATH,MAX_DISPLAY_CHARS,MESSAGES
from coop_suite import fingerprints

ROOT=Path(__file__).parents[1]

class NativeBannerLocaleAssets(unittest.TestCase):
    def test_english_default_and_deterministic_stored_single_resource(self):
        self.assertEqual(package_bytes(),package_bytes('en'))
        with tempfile.TemporaryDirectory() as directory:
            for language in ('en','de'):
                first=Path(directory)/'one'/language/'file.pk3'
                second=Path(directory)/'two'/language/'file.pk3'
                a=build(first,language);b=build(second,language)
                self.assertEqual(first.read_bytes(),second.read_bytes())
                self.assertEqual(a,b);self.assertFalse(a['native_rendering_verified'])
                self.assertEqual(a['installed_path'],INSTALLED_PATH)
                with zipfile.ZipFile(io.BytesIO(first.read_bytes())) as archive:
                    self.assertEqual(archive.namelist(),[RESOURCE_PATH])
                    info=archive.infolist()[0]
                    self.assertEqual(info.compress_type,zipfile.ZIP_STORED)
                    self.assertEqual(info.date_time,(2000,1,1,0,0,0))
                    self.assertEqual(info.extra,b'');self.assertEqual(archive.comment,b'')
                    self.assertEqual(archive.read(RESOURCE_PATH),string_resource(language))
                self.assertFalse(first.with_suffix('.pk3.part').exists())
        with self.assertRaises(ValueError):package_bytes('fr')

    def test_same_native_keys_and_template_arguments_in_english_channel(self):
        resources={}
        for language in ('en','de'):
            raw=string_resource(language)
            self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
            text=raw.decode('latin1')
            self.assertIn('VERSION "1"\r\n',text);self.assertTrue(text.endswith('ENDMARKER\r\n'))
            self.assertNotIn('LANG_GERMAN',text)
            rows=re.findall(r'^REFERENCE ([A-Z_]+)\r\nLANG_ENGLISH "([^"\r\n]*)"',text,re.M)
            resources[language]={key:value for key,value in rows}
            self.assertEqual(['CODCOOP_'+key for key,_ in rows],list(KEYS))
            self.assertEqual(len(rows),10)
            for _,value in rows:
                self.assertLess(len(value.encode('latin1')),128)
                self.assertNotIn('%d',value);self.assertNotIn('&&1',value)
        for key in resources['en']:
            self.assertEqual(re.findall(r'%[a-zA-Z]',resources['en'][key]),re.findall(r'%[a-zA-Z]',resources['de'][key]))
        templates={key for key,value in resources['en'].items() if '%s' in value}
        self.assertEqual(templates,{'OTHER_DOWNED','REVIVED_OTHER','REVIVING_PLAYER','DISCONNECTED'})
        self.assertIn(b'k\xf6nnen',string_resource('de'))
        self.assertNotEqual(resources['en'],resources['de'])

    def test_native_line_budget_with_real_one_digit_player_substitution(self):
        for _,en,de in MESSAGES:
            for value in (en,de):
                for player in ('1','2','3','4'):
                    self.assertLessEqual(len(value.replace('%s',player).encode('latin1')),MAX_DISPLAY_CHARS)
        with patch('build_coop_localization.MESSAGES',(('DOWNED_HINT','x'*38,'kurz'),)):
            with self.assertRaisesRegex(ValueError,'display bound'):package_bytes('en')
        with patch('build_coop_localization.MESSAGES',(('OTHER_DOWNED','Player %d','Spieler %s'),)):
            with self.assertRaisesRegex(ValueError,'substitution'):package_bytes('en')

    def test_only_reviewed_generated_locale_hashes_share_gameplay_identity(self):
        manifest=json.loads((ROOT/'content/variants.json').read_text())
        actual=[hashlib.sha256(package_bytes(lang)).hexdigest() for lang in ('en','de')]
        self.assertEqual(manifest['approved_localizations'][INSTALLED_PATH],actual)
        en=fingerprints(None,manifest,{INSTALLED_PATH:actual[0]})
        de=fingerprints(None,manifest,{INSTALLED_PATH:actual[1]})
        self.assertEqual(en,de)
        # A modified package can carry arbitrary assets; its new hash MUST
        # participate in gameplay identity rather than inheriting exemption.
        data=io.BytesIO(package_bytes('de'))
        with zipfile.ZipFile(data,'a') as archive:archive.writestr('maps/injected.gsc','main() {}')
        modified=hashlib.sha256(data.getvalue()).hexdigest()
        self.assertNotIn(modified,actual)
        bad=fingerprints(None,manifest,{INSTALLED_PATH:modified})
        for variant in en:self.assertNotEqual(en[variant],bad[variant])

if __name__=='__main__':unittest.main()
