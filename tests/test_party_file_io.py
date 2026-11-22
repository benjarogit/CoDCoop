"""Atomic party record replacement and actual Windows delete-sharing."""
import json,os,sys,tempfile,unittest,threading,time
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import coop_party as party
from party_native_bridge import FixedFiles,_shared_read_fd
class PartyFileIO(unittest.TestCase):
 def test_transient_windows_sharing_denial_retries_same_atomic_temporary(self):
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/'party.json';target.write_text('original')
   replace=party.os.replace;attempts=[]
   def sharing(source,destination):
    attempts.append(str(source));self.assertEqual(target.read_text(),'original')
    if len(attempts)<3:
     error=PermissionError('temporary sharing denial');error.winerror=32;raise error
    return replace(source,destination)
   with mock.patch.object(party.os,'replace',side_effect=sharing):party.atomic_private(target,{'revision':2})
   self.assertEqual(json.loads(target.read_text()),{'revision':2});self.assertEqual(len(set(attempts)),1);self.assertEqual(list(Path(folder).iterdir()),[target])
 def test_permanent_denial_preserves_original_cleans_temp_and_is_bounded(self):
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/'party.json';target.write_text('original');error=PermissionError('denied');error.winerror=5
   with mock.patch.object(party.os,'replace',side_effect=error),mock.patch.object(party.time,'monotonic',side_effect=[0,0,.3]),mock.patch.object(party.time,'sleep') as sleep:
    with self.assertRaises(PermissionError):party.atomic_private(target,{'revision':2})
   self.assertEqual(target.read_text(),'original');self.assertEqual(list(Path(folder).iterdir()),[target]);sleep.assert_called_once_with(.01)
 def test_other_permission_error_is_not_retried(self):
  with mock.patch.object(party.os,'replace',side_effect=PermissionError('not Windows sharing')) as replace:
   with self.assertRaises(PermissionError):party._replace_private('source','target')
   self.assertEqual(replace.call_count,1)
 @unittest.skipUnless(os.name=='nt','actual Windows handle sharing test')
 def test_windows_short_read_snapshot_allows_bounded_atomic_replacement(self):
  with tempfile.TemporaryDirectory() as folder:
   files=FixedFiles(folder);files.write('client.json',{'revision':1});path=files.path('client.json');fd=_shared_read_fd(path)
   self.assertEqual(json.loads(os.read(fd,4096)),{'revision':1})
   # Wine can deny replace even with FILE_SHARE_DELETE. The reader's bounded
   # lifetime must recover through retry, retaining the same atomic temporary.
   closed=threading.Event()
   def close_snapshot():
    time.sleep(.05);os.close(fd);closed.set()
   thread=threading.Thread(target=close_snapshot);thread.start()
   try:
    files.write('client.json',{'revision':2})
    self.assertEqual(files.read('client.json'),{'revision':2})
   finally:thread.join()
   self.assertTrue(closed.is_set())
if __name__=='__main__':unittest.main()
