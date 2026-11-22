#!/usr/bin/env python3
"""Owned single-host UF epoch/witness/pregame observation, not joined gameplay."""
import argparse,hashlib,json,os,select,shutil,subprocess,time,zipfile
from pathlib import Path
import qa_coop as qa
from build_campaign_patch import build
from build_uf_world_observer_fixture import instrument
from stage_suite import laa_bytes,UOSP_LAA

def validate_context(context, map_name):
 fields=context['fields']
 if context.get('runtime_ready') is not False or not context['lifecycle_match'] or not context['native_init_complete']:
  raise RuntimeError('Observed context not native completed lifecycle')
 if context['native_map']!=map_name or fields['coop_uf_world_map']!=map_name:raise RuntimeError('Map mismatch')
 if (fields['coop_uf_world_epoch']!=context['native_epoch'] or len(context['native_epoch'])!=64
     or fields['coop_uf_world_init_serial']!=str(context['native_init_serial'])
     or fields['coop_uf_world_preinit_world']!=context['native_preinit_world']):raise RuntimeError('Native epoch/init mismatch')
 for stage in ('campaign','climate','year'):
  if fields['coop_uf_world_'+stage+'_world'] not in (context['native_preinit_world'],context['native_completed_world']):raise RuntimeError('Unknown stage native world')

def archive_cache_inputs(folder, archive, map_name):
 names=('qa-render-models.txt','qa-deferred-models.txt','qa-model-ledger-'+map_name+'.txt')
 if any((folder/name).is_symlink() for name in names):raise ValueError('Refusing symbolic QA cache input')
 records=[]
 for name in names:
  path=folder/name
  if path.exists():
   if not path.is_file():raise ValueError('QA cache input is not a file')
   records.append({'name':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':path.stat().st_size})
   shutil.copy2(path,archive/name);path.unlink()
 return records

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for field in ('source','run','runtime-dir'):p.add_argument('--'+field,type=Path,required=True)
 p.add_argument('--map',choices=('brecourt','foy','noville'),default='brecourt')
 p.add_argument('--world-policy',choices=('universal','selected'),default='universal',help='Selected is a diagnostic resource-policy counterfactual, not a production default')
 p.add_argument('--experimental-defer-models',action='store_true',help='QA-only existing six-caller deferral; no capacity or production registry claim')
 p.add_argument('--port',type=int,default=29968);p.add_argument('--timeout',type=int,default=120)
 a=p.parse_args();out=a.run.resolve()
 args=['--source',str(a.source.resolve()),'--run',str(out),'--runtime-dir',str(a.runtime_dir.resolve()),'--variant','united_fronts','--map',a.map,'--players','2','--prepare-only']
 qa.main(args)
 folder=out/'host';package=folder/'UnitedFronts/ZUnitedFronts_1.1_beta.pk3'
 previous=out/'observer-input-history'/str(time.time_ns());previous.mkdir(parents=True)
 archived_inputs=archive_cache_inputs(folder,previous,a.map)
 for name in ('qa-deferred-models.json','qa-render-preload.json','qa-model-export.json'):
  path=folder/name
  if path.is_symlink():raise ValueError('Refusing symbolic QA diagnostic output')
  if path.is_file():shutil.copy2(path,previous/name);path.unlink()
 for name in ('zzzz_coop_campaign.pk3','zzzzz_coop_triggers.pk3','zzzz_coop_triggers.pk3','zzzz_coop_world_observer.pk3'):
  old=folder/'UnitedFronts'/name
  if old.exists():shutil.copy2(old,previous/name)
  if old.exists() and name!='zzzz_coop_campaign.pk3':old.unlink()
 (folder/'qa-uf-world-context.json').unlink(missing_ok=True)
 build(package,folder/'UnitedFronts/zzzz_coop_campaign.pk3','united_fronts',world_policy=a.world_policy)
 files,composition=instrument(package,compose_airborne_fix=True)
 overlay=folder/'UnitedFronts/zzzz_coop_world_observer.pk3'
 with zipfile.ZipFile(overlay,'w',zipfile.ZIP_STORED) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2000,1,1,0,0,0));z.writestr(info,data)
 frozen=out/'runtime/witness-source';frozen.mkdir(parents=True,exist_ok=True)
 for source in ('tools/qa_uf_world_observer.py','tools/build_uf_world_observer_fixture.py','tools/build_campaign_patch.py','campaign_patches/uf_world_observer.gsc','campaign_patches/uf_world_rules.json','campaign_patches/qa_uf_player_state.cpp'):
  target=frozen/source;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(qa.ROOT/source,target)
 for source in (overlay,folder/'UnitedFronts/zzzz_coop_campaign.pk3'):shutil.copy2(source,frozen/source.name)
 exe=folder/'CoDUOSP.exe';exe.write_bytes(laa_bytes(exe.read_bytes()))
 if hashlib.sha256(exe.read_bytes()).hexdigest()!=UOSP_LAA:raise RuntimeError('Unknown UO executable')
 report={'status':'FAIL','scope':__doc__,'runtime_ready':False,'map':a.map,'composition':composition,
         'overlay_sha256':hashlib.sha256(overlay.read_bytes()).hexdigest(),'world_policy':a.world_policy,'hunk_megs':512,
         'selected_policy_is_diagnostic_only':a.world_policy=='selected',
         'experimental_defer_models':a.experimental_defer_models,'archived_cache_inputs':archived_inputs,
         'exe_sha256':UOSP_LAA,'yap_sha256':hashlib.sha256((folder/'plugins/yap/DDRAW.dll').read_bytes()).hexdigest()}
 (out/'executed_qa_uf_world_observer.py').write_bytes(Path(__file__).read_bytes())
 process=display=None;handles=[]
 try:
  env=dict(os.environ,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all',CODCOOP_QA='1',CODCOOP_QA_NO_STEAM='1',CODCOOP_QA_UF_WORLD_OBSERVER='1',WINEDLLOVERRIDES='ddraw=n,b;mscoree=;mshtml=',LIBGL_ALWAYS_SOFTWARE='1',MESA_EXTENSION_MAX_YEAR='2003',__GL_ExtensionStringVersion='15000')
  for name in ('CODCOOP_QA_DEFER_MODELS','CODCOOP_QA_BORROW_TREES','CODCOOP_QA_MT_EPOCH','CODCOOP_QA_HOST_BODY_GC','CODCOOP_QA_DOBJ_BARRIER'):env.pop(name,None)
  if a.experimental_defer_models:env['CODCOOP_QA_DEFER_MODELS']='1'
  read,write=os.pipe();log=open(out/'xvfb.log','wb');handles.append(log)
  display=subprocess.Popen(['Xvfb','-displayfd',str(write),'-screen','0','1280x800x24','-nolisten','tcp'],pass_fds=(write,),stdout=log,stderr=log);os.close(write)
  if not select.select([read],[],[],10)[0]:raise RuntimeError('Xvfb unavailable')
  env['DISPLAY']=':'+os.read(read,64).decode().strip();os.close(read)
  root=qa.zpath(folder)
  cmd=['wine',str(exe),'+set','fs_basepath',root,'+set','fs_homepath',root,'+set','fs_cdpath',root,'+set','fs_game','UnitedFronts','+set','r_fullscreen','0','+set','r_mode','-1','+set','r_mode_auto','0','+set','r_customwidth','640','+set','r_customheight','480','+set','com_hunkmegs','512','+set','logfile','2','+set','com_introplayed','1','+set','coop_expected_players','2','+coophost',str(a.port),'+devmap',a.map]
  report['command']=cmd
  log=open(out/'process0.log','wb');handles.append(log);process=subprocess.Popen(cmd,env=env,cwd=folder,stdout=log,stderr=log)
  def observed():
   if qa.process_log_errors(folder):raise RuntimeError('Native engine/script error before witness')
   core_log=folder/'codcoop.log'
   if core_log.exists() and 'QA deferred: ERROR' in core_log.read_text(errors='replace'):raise RuntimeError('Native experimental binding conflict')
   try:context=json.loads((folder/'qa-uf-world-context.json').read_text())
   except (OSError,ValueError):return None
   report['last_context']=context
   if context['fields'].get('coop_uf_world_status')=='OBSERVED' and context['lifecycle_match'] and context['native_init_complete']:return context
  context=qa.wait_for(observed,[process],a.timeout,'actual UF original-loop witness')
  report['observed']=context
  validate_context(context,a.map)
  fields=context['fields']
  samples=[]
  for unused in range(4):
   time.sleep(1);samples.append({'context':json.loads((folder/'qa-uf-world-context.json').read_text()),'state':qa.read_state(folder),
                              'observer_mtime_ns':(folder/'qa-uf-world-context.json').stat().st_mtime_ns})
  report['paused_samples']=samples
  times=[x['context']['server_time'] for x in samples]
  if len(set(times))!=1:raise RuntimeError('World advanced: original preparation is not paused')
  if len({x['observer_mtime_ns'] for x in samples})!=len(samples):raise RuntimeError('Observer/engine pump did not remain live during pause')
  if any(not x['state'] for x in samples):raise RuntimeError('Native state unavailable during pause')
  if any(bool(x['state']['deferred_models']['enabled'])!=a.experimental_defer_models for x in samples):raise RuntimeError('Deferred model test policy differs from explicit diagnostic request')
  if len({tuple(x['state']['players'][0]['position']) for x in samples})!=1:raise RuntimeError('Host actor moved during native pregame pause')
  if any(x['context']['fields']['cl_paused']!='1' for x in samples):raise RuntimeError('Native cl_paused does not prove genuine pause')
  helper=out/'qa-world-models.exe';helper_source=out/'qa-world-models.cpp'
  helper_source.write_bytes((qa.ROOT/'campaign_patches/qa_uf_player_state.cpp').read_bytes())
  subprocess.run(['i686-w64-mingw32-g++',str(helper_source),'-o',str(helper),'-static','-O2','-std=c++17'],check=True)
  native=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),'0','--models'],env=env,capture_output=True,text=True,timeout=10,check=True)
  models=json.loads(native.stdout.strip());report['server_model_count']=len(models['models'])
  (out/'uf-world-native-model-table.json').write_text(json.dumps(models,indent=2)+'\n')
  qa.command(folder,'screenshot');time.sleep(1)
  shots=list((folder/'UnitedFronts/screenshots').glob('*.tga'))
  if not shots:raise RuntimeError('Native pregame screenshot missing')
  screenshot=max(shots,key=lambda path:path.stat().st_mtime_ns)
  shutil.copy2(screenshot,out/('uf-world-'+a.map+'-pregame.tga'))
  report['pregame_screenshot']=str(screenshot)
  qa.command(folder,'coopuiclick 320 240\ncoopqastart')
  report['after_normal_start']=qa.wait_for(lambda: (state if (state:=qa.read_state(folder)) and state['server_time']>int(times[-1])+200 else None),[process],30,'ordinary original pregame Start advances native world')
  time.sleep(2)
  native=subprocess.run(['wine',str(helper),str(folder).replace('/','\\'),'0','--models'],env=env,capture_output=True,text=True,timeout=10,check=True)
  report['first_live_native']=json.loads(native.stdout.strip())
  report['first_live_model_count']=len(report['first_live_native']['models'])
  for name in ('qa-deferred-models.json','qa-render-preload.json','qa-model-export.json'):
   path=folder/name
   if path.is_file():shutil.copy2(path,out/('uf-world-'+name))
  if a.experimental_defer_models:
   audit=json.loads((folder/'qa-deferred-models.json').read_text());report['experimental_registration_audit']=audit
   if not audit['guards_unchanged'] or audit['strict']!=1 or audit['loaded']!=audit['approved'] or audit['cs_before']!=audit['cs_after'] or audit['cs_after']>255:
    raise RuntimeError('Experimental media preload incomplete or native guard/budget changed')
  qa.command(folder,'quit')
  if process.wait(timeout=20)!=0:raise RuntimeError('Nonzero native exit')
  if qa.process_log_errors(folder):raise RuntimeError('Native error in final logs')
  report['status']='PASS';report['checks']=['Native HOST before fresh GAME_INIT','composed GSC compiled/observed','same epoch/init world-bound facts','world clock held by native pregame pause','normal native exit0']
 except Exception as error:report['error']=str(error)
 finally:
  if process and process.poll() is None:
   try:qa.command(folder,'quit');process.wait(timeout=10)
   except Exception:process.terminate();process.wait(timeout=10)
  if display:display.terminate();display.wait(timeout=10)
  for handle in handles:handle.close()
  (out/'uf-world-observer-proof.json').write_text(json.dumps(report,indent=2)+'\n')
  (out/'result.json').write_text(json.dumps({'status':report['status'],'scope':__doc__,'error':report.get('error')},indent=2)+'\n')
 print(json.dumps({'status':report['status'],'error':report.get('error'),'proof':str(out/'uf-world-observer-proof.json')}))
 return int(report['status']!='PASS')

if __name__=='__main__':raise SystemExit(main())
