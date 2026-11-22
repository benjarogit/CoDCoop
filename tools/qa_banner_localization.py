#!/usr/bin/env python3
"""Manual owned EN/DE native banner assets; not installer/game-language acceptance."""
import argparse,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
import qa_coop as qa
from build_coop_localization import MESSAGES,INSTALLED_PATH,package_bytes
from stage_suite import laa_bytes,UOSP_LAA


def display_text(raw):
 return re.sub(r'\^[0-9]','',raw).replace('\\n','\n')


def assert_banner(raw,expected):
 text=display_text(raw)
 if 'UNLOCALIZED' in text or 'CODCOOP_' in text:raise RuntimeError('Native center-print key was not localized')
 matched=all(value in text for value in expected)
 if matched and any(len(line.encode('latin1'))>40 for line in raw.replace('\\n','\n').split('\n')):
  raise RuntimeError('Native center-print line exceeds actual forty-byte draw limit')
 return matched


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for flag in ('source','run','runtime-dir'):p.add_argument('--'+flag,type=Path,required=True)
 p.add_argument('--variant',choices=('cod1','uo'),default='cod1')
 p.add_argument('--ui-languages',required=True,help='exactly de,en or en,de for Host/peer local UI banks')
 p.add_argument('--port',type=int,default=29950);p.add_argument('--timeout',type=int,default=180)
 a=p.parse_args();langs=qa.parse_ui_languages(a.ui_languages,2)
 if sorted(langs)!=['de','en']:p.error('This Native mixed UI probe requires one en and one de bank')
 out=a.run.resolve();folders=[out/'host',out/'join1'];root='Main' if a.variant=='cod1' else 'uo'
 executed_source=Path(__file__).read_bytes()
 argv=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant',a.variant,'--map','training','--players','2','--ui-languages',a.ui_languages,'--port',str(a.port),'--timeout',str(a.timeout),'--duration','2']
 if qa.main(argv+['--prepare-only']):return 1
 report={'status':'FAIL','scope':__doc__,'variant':a.variant,'ui_languages':langs,'stages':[],
         'runner_sha256':hashlib.sha256(executed_source).hexdigest(),'native_inputs':{}}
 for folder,language in zip(folders,langs):
  bank=folder/INSTALLED_PATH
  if bank.read_bytes()!=package_bytes(language):raise RuntimeError('Prepared local UI bank differs from reviewed generator')
  row={'ui_bank_sha256':hashlib.sha256(bank.read_bytes()).hexdigest()}
  if a.variant=='uo':
   exe=folder/'CoDUOSP.exe';original=exe.read_bytes();reviewed=laa_bytes(original)
   if original!=reviewed:
    old=out/'native-input-history'/str(time.time_ns())/folder.name/'CoDUOSP.exe';old.parent.mkdir(parents=True);old.write_bytes(original);exe.write_bytes(reviewed)
   row.update(exe_before_sha256=hashlib.sha256(original).hexdigest(),exe_sha256=hashlib.sha256(reviewed).hexdigest(),large_address_aware=True,
              yap_sha256=hashlib.sha256((folder/'plugins/yap/DDRAW.dll').read_bytes()).hexdigest())
   if row['exe_sha256']!=UOSP_LAA:raise RuntimeError('Reviewed UO LAA fingerprint mismatch')
  report['native_inputs'][folder.name]=row
 observer=out/'qa-campaign-player.cpp';observer.write_bytes((qa.ROOT/'campaign_patches/qa_campaign_player.cpp').read_bytes())
 helper=out/'qa-campaign-player.exe'
 subprocess.run(['i686-w64-mingw32-g++',str(observer),'-o',str(helper),'-static','-O2','-std=c++17','-mwindows'],check=True)
 env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all')
 messages={language:{key:en if language=='en' else de for key,en,de in MESSAGES} for language in ('en','de')}
 def native(folder):
  result=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),'0',a.variant],env=env,capture_output=True,text=True,check=True,timeout=15)
  return json.loads(result.stdout)
 def wait(check,label,timeout=25):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   for folder in folders:
    errors=qa.process_log_errors(folder)
    if errors:raise RuntimeError(label+': '+errors[0])
   value=check()
   if value:return value
   time.sleep(.05)
  raise RuntimeError('Timeout: '+label)
 def stage(name,keys):
  expected=[[messages[language][key].replace('%s','2') for key in slotkeys] for language,slotkeys in zip(langs,keys)]
  last=[]
  def matched():
   last[:]=[native(f) for f in folders]
   report['last_banner_observation']={'stage':name,'expected':expected,'actual':last}
   return last if all(p['cgame']['snapshot_client']==slot and p['center_print_time']>0 and assert_banner(p['center_print'],values) for slot,(p,values) in enumerate(zip(last,expected))) else None
  actual=wait(matched,'actual native translated banners '+name,8)
  screenshots=[]
  for slot,folder in enumerate(folders):
   directory=folder/root/'screenshots';before=set(directory.glob('*')) if directory.exists() else set()
   qa.command(folder,'screenshot',joiner=slot!=0)
   screenshots.append((directory,before))
  def captured():return all(directory.exists() and set(directory.glob('*'))-before for directory,before in screenshots)
  wait(captured,'both actual native screenshots '+name,3)
  time.sleep(.15)
  shots=[]
  for directory,before in screenshots:
   path=max(set(directory.glob('*'))-before,key=lambda p:p.stat().st_mtime)
   shots.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  entry={'stage':name,'expected':expected,'actual':actual,'screenshots':shots};report['stages'].append(entry)
  return entry
 def scenario(_folders,processes,states):
  wait(lambda:all(p['pm_type']==0 and not p['linked'] and not p['downed'] for p in qa.read_state(folders[0])['players'][:2]),'two actual live ordinary owners')
  qa.command(folders[0],'coopgod 1 0\ncoopkill 1 100000')
  wait(lambda:qa.read_state(folders[0])['players'][1]['downed'],'real native damage creates downed guest')
  stage('downed',[['OTHER_DOWNED','OTHER_DOWNED_HINT'],['DOWNED_TITLE','DOWNED_HINT']])
  qa.command(folders[0],'cooplook 0 1 64');time.sleep(.3)
  began=time.monotonic();qa.command(folders[0],'+activate')
  try:
   stage('revive-progress',[['REVIVING_PLAYER'],['BEING_REVIVED']])
   wait(lambda:not qa.read_state(folders[0])['players'][1]['downed'] and qa.read_state(folders[0])['players'][1]['health']>1,'normal Host actual three-second Use revive',8)
  finally:qa.command(folders[0],'-activate')
  report['actual_use_seconds']=time.monotonic()-began
  stage('revived',[['REVIVED_OTHER'],['REVIVED_SELF']])
  for folder in folders:
   text=(folder/root/'console.log').read_text(errors='replace')
   bad=[line for line in text.splitlines() if 'UNLOCALIZED' in line or ('Could not translate' in line and ('CODCOOP' in line or 'Center Print' in line))]
   if bad:raise RuntimeError('Native localization warning: '+bad[0])
  report['functional']='PASS';raw=out/'banner-localization-native-evidence.json';raw.write_text(json.dumps(report,indent=2,ensure_ascii=True)+'\n')
  return {'scope':__doc__,'checks':['actual separate reviewed local EN/DE UI banks before game startup','actual downed and other-player decimal2 formatting in each client language','normal Host Use progresses three seconds with translated progress on both native screens','native revived self/other messages in each client language','no UNLOCALIZED or Center Print translation warning; global warning cvars untouched'],
          'evidence':{'raw':str(raw),'sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'ui_languages':langs,'stages':[{'stage':x['stage'],'actual':[p['center_print'] for p in x['actual']],'screenshots':x['screenshots']} for x in report['stages']]}}
 try:
  code=qa.main(argv,scenario=scenario);report['status']='PASS' if code==0 and report.get('functional')=='PASS' else 'FAIL'
 except Exception as error:report['error']=str(error)
 finally:
  (out/'banner-localization-proof.json').write_text(json.dumps(report,indent=2,ensure_ascii=True)+'\n')
  (out/Path(__file__).name).write_bytes(executed_source)
 return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
