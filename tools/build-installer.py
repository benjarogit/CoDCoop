#!/usr/bin/env python3
"""Build native Windows setup from reviewed runtime and receipted base inputs.

No game installation is changed. CoD 2 assets are deliberately outside this
normal 0.6 build. The complete target-OS suite payload remains a separate input
beside setup; a successful compiler run is not installation acceptance.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from coop_suite import resolve, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-source', required=True, type=Path)
    parser.add_argument('--runtime-source', type=Path, default=ROOT/'build', help='immutable directory containing the reviewed DLL build inputs')
    parser.add_argument('--output', type=Path, default=ROOT/'build/Install-CoD-Coop.exe')
    args = parser.parse_args()
    game = args.game_source.resolve()
    try:
        # Resource inputs can come from a previously installed protocol. They
        # are checked against that installation's recorded manifest and hashes;
        # requiring the *new* protocol here would prevent building its updater.
        # This deliberately does not certify the source installation as ready.
        manifest_path = resolve(game, 'coop/variants.json')
        manifest = json.loads(manifest_path.read_text())
        manifest_hash = sha256(manifest_path)
        if manifest.get('schema') != 1 or not isinstance(manifest.get('suite_version'), str):
            raise ValueError('source has no recognized resource manifest')
        receipt = json.loads(resolve(game, 'coop/install.json').read_text())
        if receipt.get('manifest_sha256') != manifest_hash or receipt.get('suite_version') != manifest['suite_version']:
            raise ValueError('source receipt does not match its manifest')
        stage = ROOT/'build/installer-input'
        provenance = {'source':str(game),'manifest_sha256':manifest_hash,'files':{}}
        for relative in ('CoDSP.exe', 'Main/pakz_coop.pk3', 'uo/pakz_coop.pk3'):
            source = resolve(game, relative)
            actual = sha256(source)
            if receipt['files'].get(relative) != actual:
                raise ValueError('source changed since installation: '+relative)
            destination = stage/'game'/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256(destination) != actual:
                raise ValueError('resource copy differs: '+relative)
            provenance['files'][relative]=actual
        stage.mkdir(parents=True, exist_ok=True)
        resource = stage/'installer.rc'
        resource_text=(ROOT/'installer/installer.rc').read_text().replace('"game/', '"build/installer-input/game/')
        for name in ('ddraw.dll','codcoop_core.dll','steam_api.dll'):
            resource_text=resource_text.replace('"build/'+name+'"','"'+(args.runtime_source.resolve()/name).as_posix()+'"')
        resource.write_text(resource_text)
        provenance['runtime_source']=str(args.runtime_source.resolve())
        for name in ('ddraw.dll','codcoop_core.dll','steam_api.dll'):
            provenance['files']['build/'+name]=sha256(args.runtime_source/name)
        (stage/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['i686-w64-mingw32-windres','-i',str(resource),'-o','build/installer_res.o'],cwd=ROOT,check=True)
        subprocess.run(['i686-w64-mingw32-g++','-std=c++17','-O2','-s','-static','-mwindows','-municode','-Wl,--no-insert-timestamp',
                        '-o',str(args.output.resolve()),'installer/installer.cpp','build/installer_res.o',
                        '-lole32','-lshell32','-lurlmon','-lcomctl32','-loleaut32','-luuid','-ladvapi32'],cwd=ROOT,check=True)
        provenance['setup_sha256']=sha256(args.output)
        provenance['sources']={name:sha256(ROOT/name) for name in (
            'installer/installer.cpp','installer/installer_rollback.h','installer/suite_check.h','installer/installer.rc',
            'installer/README.txt','tools/build-installer.py')}
        # Keep each candidate's proof beside its binary, rather than only in the
        # shared intermediate directory overwritten by a later build.
        args.output.with_suffix('.provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        print('Native setup built:',args.output)
        print('SHA256:',sha256(args.output))
        print('Install validation and native Windows acceptance remain separate checks.')
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        parser.exit(1,'Windows setup build failed: '+str(error)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
