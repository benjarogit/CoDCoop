"""Opt-in actual Wine POSIX-link check; no game/runtime execution."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.name!='nt' and os.environ.get('COOP_WINDOWS_PYTHON') and os.environ.get('COOP_WINE_PREFIX'),'private Wine Python opt-in required')
class WinePartyPathSafety(unittest.TestCase):
 def test_actual_posix_file_and_directory_links_rejected_regular_record_readable(self):
  prefix=Path(os.environ['COOP_WINE_PREFIX']).resolve()
  self.assertNotEqual(prefix,Path.home()/'.wine');self.assertTrue(prefix.is_dir())
  with tempfile.TemporaryDirectory(dir=ROOT/'run') as folder:
   base=Path(folder);outside=base/'outside';outside.mkdir();(outside/'client.json').write_text('{"outside":true}')
   for name in ('regular','record-link','bridge-link','coop-link'):
    game=base/name;game.mkdir()
    if name=='coop-link':
     (outside/'party-bridge').mkdir(exist_ok=True);(outside/'party-bridge/client.json').write_text('{"outside":true}');(game/'coop').symlink_to(outside,target_is_directory=True)
    else:
     (game/'coop').mkdir()
     if name=='bridge-link':(game/'coop/party-bridge').symlink_to(outside,target_is_directory=True)
     else:
      (game/'coop/party-bridge').mkdir()
      p=game/'coop/party-bridge/client.json'
      if name=='record-link':p.symlink_to(outside/'client.json')
      else:p.write_text('{"inside":true}')
   script=base/'probe.py';script.write_text("import sys,json\nfrom pathlib import Path\nsys.path.insert(0,"+repr('Z:'+str(ROOT/'tools').replace('/','\\'))+")\nfrom party_native_bridge import FixedFiles\nresults={}\nfor name in ['regular','record-link','bridge-link','coop-link']:\n try:\n  value=FixedFiles(Path(__file__).parent/name).read('client.json');results[name]={'read':True,'inside':value.get('inside',False)}\n except (ValueError,OSError):results[name]={'read':False}\nprint(json.dumps(results))\n")
   env=dict(os.environ,WINEPREFIX=str(prefix),WINEDEBUG='-all')
   result=subprocess.run(['wine',os.environ['COOP_WINDOWS_PYTHON'],'Z:'+str(script).replace('/','\\')],env=env,capture_output=True,text=True,timeout=45)
   self.assertEqual(result.returncode,0,result.stderr)
   values=json.loads(result.stdout);self.assertEqual(values['regular'],{'read':True,'inside':True})
   for name in ('record-link','bridge-link','coop-link'):self.assertEqual(values[name],{'read':False})
if __name__=='__main__':unittest.main()
