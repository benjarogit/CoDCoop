#!/usr/bin/env python3
"""Build a LOCAL CoDCoop 0.6 payload from owned game files and pinned plugins.

This does not publish game assets. The source game and saves are never modified.
A successful payload build is not gameplay certification.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

from build_campaign_patch import (build as build_campaign_patch, PROFILES,
                                  build_trigger_patch, build_mainline_patch)
from coop_suite import canonical, sha256, resolve
from runtime_protocol import require_runtime_protocol, required_feature_mask

ROOT = Path(__file__).resolve().parents[1]
YAP_ZIP_SHA = 'cdc9131a189796143ace80f9ecb9f19c347bdb8553558b5fd26e6f7d08bb2ae9'
YAP_EXTRAS_SHA = '3e1fba1bbb7a71bdc5dd2532b7a366eb961dfe7372bd670ba3fcf241a45a74b2'
UOSP_ORIGINAL = 'c17e57c060f08ef65d7cddea738cced61ab7ccb6d98df95fe185b1ab8aa7e325'
UOSP_LAA = '0a0c52e5aa3e15f4b7039bb22593b8b58f594db5061b4fd4e25a2b4ca3a10018'


def copy_reviewed_visual_patches(game, output, inventory, manifest):
    """These shared pinned assets belong to every suite, not optional base data."""
    reviewed=[]
    for item in inventory['additional_visual_patches']:
        requirement=next((row for row in manifest['required'] if row['path']==item['path']),None)
        if (not requirement or requirement.get('install_source')!='suite' or
                requirement.get('sha256')!=item['sha256'] or requirement.get('size')!=item['size']):
            raise ValueError('visual patch manifest pin differs from reviewed inventory: '+item['path'])
        source=resolve(game,item['path'])
        if not source.is_file() or source.stat().st_size!=item['size'] or sha256(source)!=item['sha256']:
            raise ValueError('required reviewed visual patch missing or changed: '+item['path'])
        reviewed.append((source,Path(output)/item['path']))
    for source,destination in reviewed:
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)


def laa_bytes(original):
    """Modify the one reviewed executable flag, never bypass YAP's prompt."""
    digest = hashlib.sha256(original).hexdigest()
    if digest == UOSP_LAA:
        return original
    if digest != UOSP_ORIGINAL:
        raise ValueError('unrecognized CoDUOSP.exe; refusing an unreviewed binary patch')
    data = bytearray(original)
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[:2] != b'MZ' or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('invalid PE executable')
    flags = struct.unpack_from('<H', data, pe+22)[0]
    struct.pack_into('<H', data, pe+22, flags | 0x20)
    if hashlib.sha256(data).hexdigest() != UOSP_LAA:
        raise ValueError('unexpected LAA patch result')
    return bytes(data)


def stage(game, output, yap_archive, yap_extras, include_base=False, launcher_source=None, base_archive=None, runtime_source=None, checker_prefix=None):
    game, output = Path(game).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('output already exists; choose a fresh payload directory')
    if output.is_relative_to(game) or game.is_relative_to(output):
        raise ValueError('payload and source game must be separate trees')
    if sha256(yap_archive) != YAP_ZIP_SHA or sha256(yap_extras) != YAP_EXTRAS_SHA:
        raise ValueError('YAP release archive does not match the pinned r169 artifact')
    manifest = json.loads((ROOT/'content/variants.json').read_text())
    runtime_source = Path(runtime_source or ROOT/'build')
    if checker_prefix is not None:
        prefix = Path(checker_prefix).resolve()
        if prefix == game or prefix == output or game.is_relative_to(prefix) or output.is_relative_to(prefix):
            raise ValueError('native checker must use a separate isolated Wine prefix')
    # Reject stale binaries before copying or publishing any payload output.
    require_runtime_protocol(runtime_source, manifest['protocol'], checker_prefix, required_feature_mask(manifest))
    temporary = Path(tempfile.mkdtemp(prefix='codcoop-stage-', dir=output.parent))
    try:
        def copy(src, rel):
            src=Path(src)
            if not src.is_file():
                raise ValueError('missing payload input: '+str(src))
            dst=temporary/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        copy(ROOT/'content/variants.json','coop/variants.json')
        copy(ROOT/'tools/coop_suite.py','coop/coop_suite.py')
        copy(ROOT/'tools/coop_session.py','coop/coop_session.py')
        for name in ('coop_party.py','party_gui.py','party_binding.py','party_native_bridge.py','uf_equipment_roster.py','uf_equipment_catalog.py'):
            copy(ROOT/'tools'/name,'coop/'+name)
        copy(ROOT/'tools/frozen_runtime.py','coop/frozen_runtime.py')
        copy(ROOT/'tools/runtime_protocol.py','coop/runtime_protocol.py')
        copy(ROOT/'tools/launch-gui.py','coop/launch-gui.py')
        copy(ROOT/'tools/uf_equipment_preferences.py','coop/uf_equipment_preferences.py')
        copy(ROOT/'tools/uf_equipment_roster_view.py','coop/uf_equipment_roster_view.py')
        copy(ROOT/'campaign_patches/uf_equipment_catalog.json','coop/uf_equipment_catalog.json')
        copy(ROOT/'content/eWeapons-base.txt','eWeapons/README.txt')
        copy(ROOT/'content/eWeapons-sp-improved.txt','sp_improved/eWeapons/README.txt')
        launcher_source = Path(launcher_source or ROOT/'build/launcher/CoD-Coop-Launcher')
        if not launcher_source.is_dir():
            raise ValueError('native launcher bundle is missing; build tools/build-launcher.py first')
        if not any((launcher_source/name).is_file() for name in ('CoD-Coop-Launcher','CoD-Coop-Launcher.exe')):
            raise ValueError('native launcher executable is missing')
        for source in sorted(launcher_source.rglob('*')):
            if source.is_file():
                copy(source,'coop/launcher/'+source.relative_to(launcher_source).as_posix())
        for name in ('ddraw.dll','codcoop_core.dll','steam_api.dll','suite-check.exe'):
            copy(runtime_source/name,name if name!='suite-check.exe' else 'coop/suite-check.exe')
        # Keep runtime and original assets distinct. Extra campaigns retain their
        # original PK3 digests; compatibility overlays are additional packages.
        for rel in ('CoDSP.exe','gamex86.dll','cgamex86.dll','uix86.dll',
                    'uo_gamex86.dll','uo_cgamex86.dll','uo_uix86.dll',
                    'Main/pakz_coop.pk3','uo/pakz_coop.pk3','binkw32.dll'):
            copy(resolve(game,rel),rel)
        (temporary/'CoDUOSP.exe').write_bytes(laa_bytes(resolve(game,'CoDUOSP.exe').read_bytes()))
        for profile,(folder,filename) in PROFILES.items():
            rel=folder+'/'+filename
            copy(resolve(game,rel),rel)
            build_campaign_patch(temporary/rel,temporary/folder/'zzzz_codcoop.pk3',profile)
        for profile, folder in (('cod1', 'Main'), ('uo', 'uo'), ('sp_improved', 'sp_improved'), ('united_fronts', 'UnitedFronts')):
            build_trigger_patch(game, temporary/folder/'zzzz_coop_triggers.pk3', profile)
        build_mainline_patch(game, temporary/'sp_improved/zzzzzz_codcoop_mainline.pk3')
        for rel in ('sp_improved/readme.txt', 'sp_improved/description.txt', 'UnitedFronts/Readme-UnitedFronts.txt'):
            source = resolve(game, rel)
            if source.is_file():
                copy(source, rel)
        base_inventory=json.loads((ROOT/'content/base-packages.json').read_text())
        copy_reviewed_visual_patches(game, temporary, base_inventory, manifest)
        if include_base:
            for item in base_inventory['packages']:
                rel=item['path'];source=resolve(game,rel)
                if source.stat().st_size!=item['size'] or sha256(source)!=item['sha256']:
                    raise ValueError('base content differs from the reviewed owned inventory: '+rel)
                copy(source,rel)
            for rel in ('uo/version.inf',):
                copy(resolve(game,rel),rel)
        # Localized English-named packs in a German installation can contain
        # German replacements. Use reviewed content hashes and English text
        # evidence, never filenames as a language detector.
        locale = json.loads((ROOT/'content/localizations.json').read_text())
        base_archive = Path(base_archive or ROOT/'run/base-ready-v054.zip')
        if base_archive.stat().st_size != locale['ready_archive']['size'] or sha256(base_archive) != locale['ready_archive']['sha256']:
            raise ValueError('English UO source must be the pinned v0.5.4 Ready ZIP')
        with zipfile.ZipFile(base_archive) as archive:
            for rel, item in locale['files'].items():
                if item['source'] == 'v0.5.4_ready':
                    matches = [n for n in archive.namelist() if n.lower().endswith('/game/'+rel.lower())]
                    if len(matches) != 1: raise ValueError('English source missing/ambiguous: '+rel)
                    data = archive.read(matches[0])
                else:
                    data = resolve(game,rel).read_bytes()
                if hashlib.sha256(data).hexdigest() != item['sha256'] or len(data) != item['size']:
                    raise ValueError('unreviewed English localization: '+rel)
                evidence = locale['content_evidence'].get(rel)
                if evidence:
                    with zipfile.ZipFile(io.BytesIO(data)) as inner:
                        if evidence['text'] not in inner.read(evidence['member']).decode('latin1'):
                            raise ValueError('English content evidence failed: '+rel)
                target = temporary/'coop/languages/en'/rel
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        copy(ROOT/'content/localizations.json','coop/languages/en/manifest.json')
        with zipfile.ZipFile(yap_archive) as archive:
            for name in archive.namelist():
                if name.endswith('/'):
                    continue
                if name=='ddraw.dll':
                    rel='plugins/yap/DDRAW.dll'
                elif name.startswith(('menuwide/','uo/ui/','YAP_raw/')):
                    rel=name
                else:
                    continue
                dest=resolve(temporary,rel)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(archive.read(name))
        with tempfile.TemporaryDirectory(prefix='codcoop-yap-extras-') as scratch:
            subprocess.run(['7z','x','-y','-o'+scratch,str(Path(yap_extras).resolve())],
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
            for folder in ('uo/eWeapons','UnitedFronts/eWeapons'):
                base=Path(scratch)/folder
                if not base.is_dir():
                    raise ValueError('YAP extras missing '+folder)
                for source in sorted(base.rglob('*.json')):
                    copy(source,folder+'/'+source.relative_to(base).as_posix())
        for source in (ROOT/'third_party/yap').rglob('*'):
            if source.is_file():
                copy(source,'coop/licenses/yap/'+source.relative_to(ROOT/'third_party/yap').as_posix())
        copy(ROOT/'LICENSE','coop/licenses/CoDCoop-MIT.txt')
        copy(ROOT/'installer/vendor/LICENSE.nlohmann-json','coop/licenses/nlohmann-json-MIT.txt')
        files={p.relative_to(temporary).as_posix():sha256(p) for p in sorted(temporary.rglob('*')) if p.is_file() and not (p.name.lower().startswith('localized_') and p.suffix.lower()=='.pk3')}
        lock={'suite_version':manifest['suite_version'],'manifest_sha256':sha256(temporary/'coop/variants.json'),'files':files}
        (temporary/'coop/runtime-lock.json').write_bytes(canonical(lock)+b'\n')
        temporary.rename(output)
        return lock
    except BaseException:
        shutil.rmtree(temporary,ignore_errors=True)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--yap-archive',type=Path,default=ROOT/'run/yap-r169.zip')
    parser.add_argument('--yap-extras',type=Path,default=ROOT/'run/yap-extras-r169.7z')
    parser.add_argument('--launcher-source',type=Path,help='native target-OS launcher bundle directory')
    parser.add_argument('--include-base',action='store_true',help='include base PK3s plus reviewed English localization for a local offline payload')
    parser.add_argument('--base-archive',type=Path,default=ROOT/'run/base-ready-v054.zip',help='pinned v0.5.4 Ready ZIP supplying reviewed English UO files')
    parser.add_argument('--runtime-source',type=Path,help='immutable directory with the four reviewed build DLL/checker inputs; defaults to build/')
    parser.add_argument('--checker-prefix',type=Path,help='initialized isolated Wine prefix for native checker capabilities on Linux')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        lock=stage(args.game_source,args.output,args.yap_archive,args.yap_extras,args.include_base,args.launcher_source,args.base_archive,args.runtime_source,args.checker_prefix)
    except (OSError,ValueError,subprocess.SubprocessError,zipfile.BadZipFile) as error:
        parser.exit(1,'CoDCoop payload failed: '+str(error)+'\n')
    print('Local payload prepared:',args.output)
    print('Pinned files:',len(lock['files']))
    print('Not a gameplay acceptance result; install and verify before launch.')


if __name__=='__main__':
    main()
