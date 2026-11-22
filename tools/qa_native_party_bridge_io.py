#!/usr/bin/env python3
"""Actual MinGW/Wine helper-file contract; no game, socket or kit activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from coop_party import canonical
from party_native_bridge import validate_challenge
import uf_equipment_roster as roster
from uf_equipment_preferences import catalog_digest

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--prefix',type=Path,required=True,help='Existing exclusively owned Wine prefix; never killed by this helper')
    args=parser.parse_args();out=args.run.resolve();out.mkdir(parents=True,exist_ok=True)
    for name in ('native-io-proof.json','native-fixture.log','fixture.exe','unit.exe','source'):
        path=out/name
        if path.exists():
            archive=out/'history'/str(time.time_ns());archive.mkdir(parents=True);path.rename(archive/name)
    snapshot=out/'source';(snapshot/'tests').mkdir(parents=True)
    shutil.copytree(ROOT/'src',snapshot/'src')
    for name in ('party_native_bridge_fixture.cpp','test_party_native_bridge.cpp'):shutil.copy2(ROOT/'tests'/name,snapshot/'tests'/name)
    shutil.copy2(Path(__file__),snapshot/Path(__file__).name)
    exe=out/'fixture.exe';unit=out/'unit.exe'
    subprocess.run(['i686-w64-mingw32-g++','-std=c++17','-O2','-static',str(snapshot/'tests/party_native_bridge_fixture.cpp'),'-ladvapi32','-o',str(exe)],check=True)
    subprocess.run(['i686-w64-mingw32-g++','-std=c++17','-O2','-static',str(snapshot/'tests/test_party_native_bridge.cpp'),'-o',str(unit)],check=True)
    catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
    world={'variant':'united_fronts','package_id':'c'*64,'map':'brecourt','campaign':'american','sp_ally':'us_inf'}
    state=roster.create_roster(catalog,0,world,[{'slot_id':slot,'kit':{'mode':'automatic'}} for slot in range(4)])
    for slot,values in enumerate(((9,6,22,34),(5,1,21,33),(10,8,21,32),(3,7,21,31))):
        kit={'mode':'manual','family':'american','slots':dict(zip(('primary','secondary','pistol','grenade'),values))}
        state=roster.update_kit(state,catalog,slot,slot,kit,state['revision'])
    plan=roster.plan(state,catalog)
    party={'schema':1,'kind':'coop-party-native-1','party_session':'a'*64,'catalog_sha256':catalog_digest(catalog),
           'package_sha256':'c'*64,'world':world,'world_sha256':roster.identity(world),'revision':plan['revision'],
           'plan_sha256':plan['plan_sha256'],'members':[{'guid':str(slot+1)*64,'slot':slot} for slot in range(4)],
           'local_guid':'1'*64,'confirmed_slots':[0,1,2,3],'plan':plan,'runtime_ready':False,
           'worker_pid':123,'updated_unix_ms':100000,'expires_unix_ms':105000}
    for name,value in (('party.json',party),('world.json',world),('catalog.json',catalog)):(out/name).write_text(json.dumps(value))
    game=out/'game';game.mkdir(exist_ok=True)
    env=dict(os.environ,WINEPREFIX=str(args.prefix.resolve()),WINEDEBUG='-all',LIBGL_ALWAYS_SOFTWARE='1')
    z=lambda p:'Z:'+str(p).replace('/','\\')
    report={'status':'FAIL','scope':__doc__,'checks':[],'source_sha256':{str(p.relative_to(snapshot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*') if p.is_file()},'fixture_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
    def run(command,data=None):
        result=subprocess.run(['wine',*map(str,command)],input=data,env=env,capture_output=True,timeout=30)
        with (out/'native-fixture.log').open('ab') as log:log.write(result.stderr)
        if result.returncode:raise RuntimeError(f'Native fixture exit{result.returncode}: {command!r}; {result.stderr.decode(errors="replace")}')
        return result.stdout
    def reject_path():run([z(exe),'--reject-client-path',z(game)])
    try:
        # Leftover diagnostic symlinks are never silently removed from the fixture.
        client=game/'coop/party-bridge/client.json'
        if client.exists() or client.is_symlink():raise RuntimeError('Fixture client path already exists; preserve or remove its previous evidence explicitly')
        report['io']=json.loads(run([z(exe),'--fixed-io',z(game)]))
        report['checks']+=['fixed enum paths and native/worker write ownership','atomic replace; failed replace keeps original','oversized131073byte record refused','native CryptoAPI SHA256/random nonce']
        run([z(unit)]);raw=run([z(unit),'--canonical']);challenge=json.loads(raw);validate_challenge(challenge)
        if raw!=canonical(challenge):raise RuntimeError('Native canonical JSON differs from Python IDL')
        digest=run([z(exe),'--hash'],raw).decode()
        if digest!=hashlib.sha256(raw).hexdigest():raise RuntimeError('Native CryptoAPI SHA differs')
        report['canonical_sha256']=digest;report['checks']+=['native transaction/deadline/heartbeat/replay/slot tests','native canonical JSON+CryptoAPI exact Python SHA parity']
        report['plan']=json.loads(run([z(exe),'--plan',z(out/'party.json'),z(out/'catalog.json'),z(out/'world.json'),'c'*64]))
        report['checks']+=['native four-kit pinned catalog/plan/world digest and exact resource/support closure fixture']
        outside=out/'outside-owned-fixture.txt';outside.write_text('owned fixture sentinel')
        client.symlink_to(outside)
        try:
            reject_path()
            if outside.read_text()!='owned fixture sentinel':raise RuntimeError('Symlink target modified')
        finally:client.unlink()
        client.mkdir()
        try:reject_path()
        finally:client.rmdir()
        report['checks']+=['external POSIX symlink read/write refused and target unchanged','directory disguised as record refused']
        client.write_text('owned unsafe-permission sentinel');client.chmod(0o666)
        try:
            reject_path()
            if client.read_text()!='owned unsafe-permission sentinel':raise RuntimeError('Unsafe-permission record overwritten')
        finally:client.chmod(0o600);client.unlink()
        report['checks']+=['record writable by non-owner refused']
        bridge=game/'coop/party-bridge';saved=game/'coop/saved-owned-bridge';bridge.rename(saved)
        external=out/'outside-owned-bridge';external.mkdir(exist_ok=True);(external/'client.json').write_text('owned external bridge sentinel');bridge.symlink_to(external,target_is_directory=True)
        try:reject_path()
        finally:bridge.unlink();saved.rename(bridge)
        report['checks']+=['symlinked bridge directory refused']
        report['status']='PASS'
    except Exception as error:report['error']=str(error)
    finally:(out/'native-io-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
    if 'error' in report:print(report['error'])
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
