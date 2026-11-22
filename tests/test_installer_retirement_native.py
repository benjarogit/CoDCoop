"""Actual Windows installer preflight/retirement, using tiny owned fixtures.

Optional compiled console adapter calls production functions; no game assets,
downloads, full setup bundle or native Windows gameplay are involved.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def sha(data):return hashlib.sha256(data).hexdigest()
def native(path):return str(Path(path).resolve()) if os.name=='nt' else 'Z:'+str(Path(path).resolve()).replace('/','\\')

@unittest.skipUnless(os.environ.get('COOP_NATIVE_RETIREMENT_PROBE') and (os.name=='nt' or os.environ.get('COOP_WINE_PREFIX')),'requires compiled retirement probe and private Wine prefix on Linux')
class NativeRetirement(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.game=self.root/'game';self.overlay=self.root/'suite'
        self.old=['main/ZzZzZ_cOdCoOp_TrIgGeRs.Pk3','main/ZZZZZ_COOP_TRIGGERS.PK3']
        self.old_pins={}
        for rel in self.old:self.write(self.game/rel,b'original owned '+rel.encode());self.old_pins[rel.upper()]=sha((self.game/rel).read_bytes())
        self.personal={'main/config.cfg':b'personal graphics/name binds','main/save/autosave/progress.svg':b'actual native-style nested save'}
        for rel,data in self.personal.items():self.write(self.game/rel,data);self.old_pins[rel]=sha(data)
        self.replace='Main/zzzz_coop_triggers.pk3';self.write(self.overlay/self.replace,b'new reviewed mission overlay')
        self.new={'files':{self.replace:sha((self.overlay/self.replace).read_bytes())}}
        self.write_json(self.overlay/'coop/variants.json',{'required':[{'path':self.replace}]})
        self.locks()
    def write(self,path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    def write_json(self,path,value):self.write(path,json.dumps(value).encode())
    def locks(self):self.write_json(self.game/'coop/runtime-lock.json',{'files':self.old_pins});self.write_json(self.overlay/'coop/runtime-lock.json',self.new)
    def tree(self):return {p.relative_to(self.game).as_posix():sha(p.read_bytes()) for p in self.game.rglob('*') if p.is_file()}
    def run_native(self,action,language='en'):
        exe=str(Path(os.environ['COOP_NATIVE_RETIREMENT_PROBE']).resolve());env=os.environ.copy();args=[action,native(self.game),native(self.overlay),language]
        if os.name=='nt':command=[exe,*args]
        else:env.update(WINEPREFIX=str(Path(env['COOP_WINE_PREFIX']).resolve()),WINEDEBUG='-all');command=['wine',exe,*args]
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
        self.assertIn(result.returncode,(0,1),(result.stdout,result.stderr));return result.returncode,json.loads(result.stdout)
    def assert_personal(self):
        for rel,data in self.personal.items():self.assertEqual((self.game/rel).read_bytes(),data)
    def test_casefold_both_legacy_names_retire_and_rollback_preserves_saves(self):
        baseline=self.tree();code,value=self.run_native('preflight');self.assertEqual(code,0);self.assertEqual(self.tree(),baseline)
        code,value=self.run_native('retire-rollback');self.assertEqual(code,0,value);self.assertEqual(value['changes'],2)
        for rel in self.old:self.assertTrue((self.game/rel).exists())
        self.assert_personal()
        code,value=self.run_native('retire');self.assertEqual(code,0,value);self.assertEqual(value['changes'],2)
        for rel in self.old:self.assertFalse((self.game/rel).exists())
        self.assert_personal()
    def test_modified_unowned_and_missing_ownership_abort_before_changes(self):
        original=dict(self.old_pins)
        for mode in ('modified','unowned','no-lock'):
            self.old_pins=dict(original)
            if mode=='modified':self.old_pins[self.old[0].upper()]='0'*64
            elif mode=='unowned':self.old_pins.pop(self.old[0].upper())
            self.locks()
            if mode=='no-lock':(self.game/'coop/runtime-lock.json').unlink()
            baseline=self.tree();code,value=self.run_native('retire')
            self.assertEqual(code,1);self.assertIn('back it up and remove it',value['error']);self.assertEqual(value['changes'],0);self.assertEqual(self.tree(),baseline)
    def test_replacement_missing_changed_or_unpinned_rejected_before_changes(self):
        replacement=self.overlay/self.replace;data=replacement.read_bytes()
        for mode in ('missing','changed','unpinned'):
            self.write(replacement,data);self.new={'files':{self.replace:sha(data)}}
            if mode=='missing':replacement.unlink()
            elif mode=='changed':replacement.write_bytes(b'corrupted replacement')
            else:self.new['files'].pop(self.replace)
            self.locks();baseline=self.tree();code,value=self.run_native('retire')
            self.assertEqual(code,1);self.assertIn('missing or changed',value['error']);self.assertEqual(value['changes'],0);self.assertEqual(self.tree(),baseline)
    def test_unknown_personal_content_retained_and_german_error_is_actionable(self):
        custom=self.game/'main/user_custom.pk3';self.write(custom,b'personal custom pack');self.old_pins['Main/user_custom.pk3']=sha(custom.read_bytes());self.locks()
        code,value=self.run_native('retire');self.assertEqual(code,0);self.assertEqual(custom.read_bytes(),b'personal custom pack');self.assert_personal()
        self.write(self.game/self.old[0],b'edited old script');baseline=self.tree();code,value=self.run_native('retire','de')
        self.assertEqual(code,1);self.assertIn('Bitte sichern',value['error']);self.assertIn('entfernen',value['error']);self.assertEqual(self.tree(),baseline)
    def test_case_colliding_ownership_is_rejected_before_any_backup(self):
        self.old_pins[self.old[0].lower()]=self.old_pins[self.old[0].upper()];self.locks();baseline=self.tree();code,value=self.run_native('retire')
        self.assertEqual(code,1);self.assertIn('ambiguous payload',value['error']);self.assertEqual(value['changes'],0);self.assertEqual(self.tree(),baseline)

if __name__=='__main__':unittest.main()
