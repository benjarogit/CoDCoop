#!/usr/bin/env python3
"""Combined initial resource contract and strict saved native role/pose/vitals gate."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
import qa_coop as qa
import qa_checkpoint_downed as role

def main():
 args=sys.argv[1:]
 out=Path(args[args.index('--run')+1]).resolve()
 original=qa.subprocess.Popen
 frozen={p.name:p.read_bytes() for p in (Path(__file__),Path(qa.__file__),Path(role.__file__))}
 report={'status':'FAIL','scope':__doc__,'native_map_order':{}}
 def launch(command,*pos,**kw):
  if isinstance(command,list) and any(str(item).endswith(('CoDSP.exe','CoDUOSP.exe')) for item in command):
   command=list(command);kw['env']=dict(kw['env'])
   kw['env'].pop('CODCOOP_QA_NETWORK_ASSETS',None)
   kw['env']['CODCOOP_QA_MT_EPOCH']='1'
   if '+coopjoin' in command:
    i=command.index('+devmap');del command[i:i+2]
  return original(command,*pos,**kw)
 qa.subprocess.Popen=launch
 try:
  result=role.main()
  if result:return result
  for folder in (out/'host',out/'join1'):
   log=folder/('codcoop.log' if folder.name=='host' else 'codcoop_join.log')
   text=log.read_text(errors='replace')
   if folder.name=='join1':
    points=[text.find(key) for key in ('Resource bootstrap: SHA verified','QA native GAME_INIT','Resource bootstrap: native item/alt registration completed','Resource bootstrap: completed native Game/CG mapping verified','joiner: conectado')]
    if min(points)<0 or points!=sorted(points):raise RuntimeError('Resource/native first GAME_INIT order not proved')
    if text.count('Resource bootstrap: completed native Game/CG mapping verified')<2:raise RuntimeError('Checkpoint lacked second resource mapping')
    if text.count('native DObjs before host model IDs; native owners retained')<2:raise RuntimeError('Checkpoint lacked native mapping ownership barrier')
    report['native_map_order'][folder.name]=points
  report['status']='PASS';return 0
 finally:
  qa.subprocess.Popen=original
  out.mkdir(parents=True,exist_ok=True)
  (out/'merged-bootstrap-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')
  for name,body in frozen.items():(out/('executed-merged-'+name)).write_bytes(body)

if __name__=='__main__':raise SystemExit(main())
