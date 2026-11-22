"""Opt-in production native setup rollback with tiny files, no game."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
@unittest.skipUnless(os.environ.get('COOP_PUBLIC_ROLLBACK_PROBE') and (os.name=='nt' or os.environ.get('COOP_WINE_PREFIX')),'requires native rollback probe and private Wine prefix')
class PublicRollback(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.game=self.root/'game';self.game.mkdir()
  self.before={'ddraw.dll':b'original runtime','Main/zzzz_coop_triggers.pk3':b'old mission overlay','Main/config.cfg':b'old config','Main/save/autosave/progress.svg':b'old save'}
  for rel,data in self.before.items():self.write(rel,data)
  (self.game/'coop').mkdir();self.assertEqual(self.call('record')[0],0)
  self.journal_path=self.game/'coop/last-install-backup.json';self.journal=json.loads(self.journal_path.read_text());self.assertEqual(self.journal['schema'],2)
 def write(self,rel,data):p=self.game/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 def tree(self):return {p.relative_to(self.game).as_posix():sha(p) for p in self.game.rglob('*') if p.is_file()}
 def call(self,action):
  exe=os.environ['COOP_PUBLIC_ROLLBACK_PROBE'];command=[exe,action,str(self.game)];env=os.environ.copy()
  if os.name!='nt':
   prefix=Path(os.environ['COOP_WINE_PREFIX']).resolve();self.assertNotEqual(prefix,Path.home()/'.wine');env.update(WINEPREFIX=str(prefix),WINEDEBUG='-all');command=['wine',exe,action,'Z:'+str(self.game).replace('/','\\')]
  p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30);return p.returncode,json.loads(p.stdout)
 def save_journal(self):self.journal_path.write_text(json.dumps(self.journal))
 def refused_unchanged(self):
  before=self.tree();code,result=self.call('rollback');self.assertEqual(code,1,result);self.assertFalse(result['ok']);self.assertEqual(self.tree(),before);return result['error']
 def test_restore_runtime_and_remove_new_file_preserves_current_config_save_edits(self):
  self.write('Main/config.cfg',b'USER EDIT AFTER CONFIGURE');self.write('Main/save/autosave/progress.svg',b'NEWER USER SAVE')
  self.assertEqual(set(self.journal['retained_personal']),{'Main/config.cfg','Main/save/autosave/progress.svg'})
  self.assertFalse(any(x['path'] in self.journal['retained_personal'] for x in self.journal['entries']))
  code,result=self.call('rollback');self.assertEqual(code,0,result)
  for rel in ('ddraw.dll','Main/zzzz_coop_triggers.pk3'):self.assertEqual((self.game/rel).read_bytes(),self.before[rel])
  self.assertFalse((self.game/'coop/new-runtime.txt').exists());self.assertEqual((self.game/'Main/config.cfg').read_bytes(),b'USER EDIT AFTER CONFIGURE');self.assertEqual((self.game/'Main/save/autosave/progress.svg').read_bytes(),b'NEWER USER SAVE');self.assertEqual(json.loads(self.journal_path.read_text())['state'],'rolled_back')
  self.assertIn('guarded',self.refused_unchanged())
 def test_modified_runtime_fails_before_any_mutation(self):
  self.write('ddraw.dll',b'USER CUSTOM DLL');self.assertIn('runtime changed',self.refused_unchanged())
 def test_modified_missing_and_unowned_backup_refused(self):
  entry=next(x for x in self.journal['entries'] if x['existed']);backup=self.game/entry['backup'];original=backup.read_bytes();backup.write_bytes(b'MODIFIED');self.assertIn('backup missing or changed',self.refused_unchanged());backup.unlink();self.refused_unchanged();backup.write_bytes(original)
  entry['backup']='Main/config.cfg';self.save_journal();self.assertIn('unowned',self.refused_unchanged())
 def test_legacy_array_and_unexpected_schema_refused(self):
  self.journal_path.write_text('[]');self.assertIn('Legacy',self.refused_unchanged());self.journal['schema']=2.0;self.save_journal();self.refused_unchanged()
 def test_outside_path_and_case_duplicate_refused(self):
  old=self.journal['entries'][0]['path']
  for path in ('../outside.dll','Z:/outside.dll','/outside.dll','ddraw.dll\x00hidden','ddraw.dll.','Main/CON'):
   self.journal['entries'][0]['path']=path;self.save_journal();self.refused_unchanged()
  self.journal['entries'][0]['path']=old;duplicate=dict(self.journal['entries'][0]);duplicate['path']=old.upper();self.journal['entries'].append(duplicate);self.save_journal();self.assertIn('duplicate',self.refused_unchanged())
 def test_personal_backup_changes_do_not_block_runtime_rollback(self):
  # Personal backups remain for manual recovery, but public undo never reads
  # them or overwrites current data, even if original setup configured them.
  for p in self.game.rglob('*.coop-backup.*'):
   if 'config.cfg' in p.name or '.svg.coop-backup.' in p.name:p.write_bytes(b'user retained backup changed')
  self.write('Main/config.cfg',b'current config');self.write('Main/save/autosave/progress.svg',b'current save');self.assertEqual(self.call('rollback')[0],0);self.assertEqual((self.game/'Main/config.cfg').read_bytes(),b'current config')
 def test_personal_symlink_is_retained_without_blocking_runtime_rollback(self):
  config=self.game/'Main/config.cfg';config.unlink();outside=self.root/'user-settings';outside.write_bytes(b'current linked user settings')
  try:config.symlink_to(outside)
  except OSError:self.skipTest('symlink creation unavailable')
  self.assertEqual(self.call('rollback')[0],0);self.assertTrue(config.is_symlink());self.assertEqual(outside.read_bytes(),b'current linked user settings')
 def test_runtime_and_backup_symlinks_refused_before_mutation(self):
  entry=next(x for x in self.journal['entries'] if x['existed']);backup=self.game/entry['backup'];data=backup.read_bytes();outside=self.root/'outside-runtime';outside.write_bytes(data);backup.unlink()
  try:backup.symlink_to(outside)
  except OSError:self.skipTest('symlink creation unavailable')
  self.refused_unchanged();self.assertEqual(outside.read_bytes(),data)
  backup.unlink();backup.write_bytes(data);target=self.game/entry['path'];installed=target.read_bytes();target.unlink();outside.write_bytes(installed);target.symlink_to(outside);self.refused_unchanged();self.assertEqual(outside.read_bytes(),installed)
 def test_mid_restore_failure_restores_prior_runtime_state(self):
  before=self.tree();code,result=self.call('rollback-fail-mid');self.assertEqual(code,1,result)
  after=self.tree()
  for rel,digest in before.items():self.assertEqual(after.get(rel),digest,rel)
  self.assertEqual(json.loads(self.journal_path.read_text())['state'],'complete')
 @unittest.skipUnless(os.environ.get('COOP_LEGACY_ROLLBACK_CHECKER'),'requires frozen old checker opt-in')
 def test_old_checker_rejects_new_journal_before_mutation(self):
  exe=os.environ['COOP_LEGACY_ROLLBACK_CHECKER'];command=[exe,'rollback',str(self.game)];env=os.environ.copy()
  if os.name!='nt':env.update(WINEPREFIX=os.environ['COOP_WINE_PREFIX'],WINEDEBUG='-all');command=['wine',exe,'rollback','Z:'+str(self.game).replace('/','\\')]
  before=self.tree();result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,1);self.assertIn('invalid backup journal',result.stderr);self.assertEqual(self.tree(),before)
if __name__=='__main__':unittest.main()
