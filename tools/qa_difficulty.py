#!/usr/bin/env python3
"""Observe original difficulty handlers in isolated native menus, without Coop DLLs.

Shares only immutable PK3 inputs through hardlinks; all config/log/prefix writes
stay in a fresh owned run. This is not a campaign or gameplay test.
"""
import argparse, hashlib, json, os
from pathlib import Path
import re, shutil, subprocess, time

PRESETS=(('Easy',0,1200),('Medium',1,600),('Hard',2,300),('Fu',3,200))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=120)
    parser.add_argument('--mode',choices=('native-presets','startup-hard'),default='native-presets')
    args=parser.parse_args();source=args.source.resolve();out=args.run.resolve()
    if out.exists() or out.is_relative_to(source) or source.is_relative_to(out):
        parser.error('choose a fresh independent run directory')
    out.mkdir(parents=True);game=out/'native-menus';game.mkdir()
    report={'status':'FAIL','mode':args.mode,'scope':'original CoD1/UO native engine Cvar queries without Coop DLLs; training world only in startup-hard mode','source':str(source),'engines':{},'inputs':{}}
    for p in source.iterdir():
        if (p.is_file() and (p.name in ('CoDSP.exe','CoDUOSP.exe') or
                p.suffix.lower()=='.dll') and
                p.name.lower() not in ('ddraw.dll','codcoop_core.dll','steam_api.dll')):
            shutil.copy2(p,game/p.name)
    if (source/'miles').is_dir():shutil.copytree(source/'miles',game/'miles')
    for root in ('Main','uo'):
        (game/root).mkdir()
        for name in ('config.cfg','uoconfig.cfg'):
            if (source/root/name).is_file():
                shutil.copy2(source/root/name,game/root/name)
        for p in (source/root).iterdir():
            if p.is_file() and p.suffix.lower()=='.pk3':
                os.link(p,game/root/p.name)
                report['inputs'][root+'/'+p.name]={'size':p.stat().st_size,'shared_readonly_input':True}
    readfd,writefd=os.pipe();displaylog=open(out/'xvfb.log','wb')
    display=subprocess.Popen(['Xvfb','-displayfd',str(writefd),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(writefd,),stdout=displaylog,stderr=displaylog)
    os.close(writefd);number=os.read(readfd,32).decode().strip();os.close(readfd)
    env=os.environ.copy();env.update(DISPLAY=':'+number,WINEPREFIX=str(out/'prefix'),WINEDEBUG='-all',WINEDLLOVERRIDES='mscoree=;mshtml=',LIBGL_ALWAYS_SOFTWARE='1',MESA_EXTENSION_MAX_YEAR='2003',__GL_ExtensionStringVersion='15000')
    try:
        subprocess.run(['wineboot','-u'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90,check=True)
        for engine,exe,root in [('cod1','CoDSP.exe','Main'),('uo','CoDUOSP.exe','uo')]:
            # These original commands dispatch through the server-command
            # buffer. Yield frames before querying; an immediate quit would
            # discard the pending handlers and give a false negative.
            lines=['difficultyMedium','wait 2','echo PRESET_SETTER_ONLY','set g_player_maxhealth 777','set g_gameskill 2','g_gameskill','g_player_maxhealth','echo PRESET_END']
            for command,skill,health in PRESETS+(('Gimp',0,12000),):
                lines+=['echo PRESET_'+command,'set g_gameskill 99','set g_player_maxhealth 777','difficulty'+command,'wait 2','g_gameskill','g_player_maxhealth','echo PRESET_END']
            lines+=['quit']
            if args.mode=='startup-hard':
                config=game/root/('config.cfg' if engine=='cod1' else 'uoconfig.cfg')
                with config.open('a') as stream:
                    stream.write('\nseta g_gameskill "0"\nseta g_player_maxhealth "777"\n')
                shutil.copy2(config,out/(engine+'-baseline.cfg'))
                lines=['echo PRESET_MENU_HARD','g_gameskill','g_player_maxhealth','echo PRESET_END',
                       'spmap training','wait 120','echo PRESET_WORLD_HARD','g_gameskill','g_player_maxhealth',
                       'sv_running','mapname','echo PRESET_END','quit']
            (game/root/'difficulty_probe.cfg').write_text('\n'.join(lines)+'\n')
            console=game/root/'console.log';console.unlink(missing_ok=True)
            cmd=['wine',str(game/exe),'+set','fs_basepath',str(game),'+set','fs_homepath',str(game),'+set','fs_cdpath',str(game),'+set','fs_game','', '+set','com_introplayed','1','+set','com_recommendedSet','1','+set','r_fullscreen','0','+set','r_mode','-1','+set','r_customwidth','640','+set','r_customheight','480','+set','com_hunkmegs','256','+set','logfile','2','+exec','difficulty_probe.cfg']
            if args.mode=='startup-hard':
                cmd[-2:-2]=['+set','g_gameskill','2','+set','g_player_maxhealth','300']
            with open(out/(engine+'-stdout.log'),'wb') as stream:
                completed=subprocess.run(cmd,cwd=game,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=args.timeout)
            text=re.sub(r'\^[0-9]','',console.read_text(errors='replace'))
            shutil.copy2(console,out/(engine+'-console.log'))
            values={}
            for marker,body in re.findall(r'PRESET_(SETTER_ONLY|Easy|Medium|Hard|Fu|Gimp|MENU_HARD|WORLD_HARD)\s*\n(.*?)PRESET_END',text,re.S):
                skill=re.findall(r'"g_gameskill" is:\s*"([^"]*)"',body)
                health=re.findall(r'"g_player_maxhealth" is:\s*"([^"]*)"',body)
                if skill and health:values[marker]={'skill':int(skill[-1]),'health':int(health[-1])}
            expected={name:{'skill':skill,'health':health} for name,skill,health in PRESETS+(('Gimp',0,12000),)}
            expected['SETTER_ONLY']={'skill':1,'health':777}
            if args.mode=='startup-hard':
                expected={key:{'skill':2,'health':300} for key in ('MENU_HARD','WORLD_HARD')}
                if not re.search(r'"sv_running" is:\s*"1"',text) or not re.search(r'"mapname" is:\s*"training"',text):
                    raise RuntimeError(engine+' did not initialize the actual training world')
            report['engines'][engine]={'exit_code':completed.returncode,'exe_sha256':hashlib.sha256((game/exe).read_bytes()).hexdigest(),'observed':values,'expected':expected}
            if completed.returncode or values!=expected:raise RuntimeError(engine+' native preset query differs; inspect console evidence')
        report['status']='PASS'
    except Exception as error:report['error']=str(error)
    finally:
        subprocess.run(['wineserver','-k'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
        display.terminate();display.wait(timeout=10);displaylog.close()
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='inputs'},indent=2))
    return int(report['status']!='PASS')

if __name__=='__main__':raise SystemExit(main())
