"""Packaging-only checks for a staged online/offline suite, never installation sealing."""
import argparse
import json
from pathlib import Path
import shutil
from coop_suite import (PROTOCOL, approved_localizations, content_files, load_manifest,
                        localization_inventory, read_lock, resolve, sha256)
from runtime_protocol import core_protocol, require_core_features, required_feature_mask

ROOT=Path(__file__).resolve().parents[1]

def embed_suite(source,destination,base_catalog=None):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists() or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('suite source and fresh destination must be separate')
    if any(path.is_symlink() for path in source.rglob('*')):
        raise ValueError('staged payload must contain regular copied files, not symlinks')
    manifest,mhash=load_manifest(source);lock=read_lock(source,manifest,mhash)
    if core_protocol(resolve(source,'codcoop_core.dll'))!=PROTOCOL:
        raise ValueError('staged Core protocol mismatch')
    require_core_features(resolve(source,'codcoop_core.dll'),required_feature_mask(manifest))
    files={p.relative_to(source).as_posix():sha256(p) for p in source.rglob('*') if p.is_file()}
    for name,digest in lock['files'].items():
        if sha256(resolve(source,name))!=digest:raise ValueError('staged hash mismatch: '+name)
    catalog=json.loads(Path(base_catalog or ROOT/'content/base-packages.json').read_text())
    optional={item['path'].lower() for item in catalog['packages']}
    missing=[]
    for item in manifest['required']:
        name=item['path'];path=resolve(source,name)
        if not path.is_file():
            if name.lower() not in optional:raise ValueError('missing required suite content: '+name)
            missing.append(name);continue
        allowed=item.get('sha256_any',[item['sha256']] if item.get('sha256') else [])
        if allowed and sha256(path) not in allowed:raise ValueError('wrong pinned content: '+name)
    approved=approved_localizations(manifest)
    backups={('coop/languages/en/'+name).lower():item['sha256']
             for name,item in localization_inventory(source).items()}
    locked={name.lower() for name in lock['files']}
    for name in content_files(source,manifest):
        if not resolve(source,name).is_file():continue  # reviewed missing base only, checked above
        digest=sha256(resolve(source,name))
        if name.lower() not in locked and digest not in approved.get(name.lower(),[]) and digest!=backups.get(name.lower()):
            raise ValueError('unowned staged gameplay content: '+name)
    inventory='coop/languages/en/manifest.json'
    if inventory not in lock['files']:raise ValueError('canonical English inventory is required')
    for name,item in localization_inventory(source).items():
        if sha256(resolve(source,'coop/languages/en/'+name))!=item['sha256']:
            raise ValueError('wrong English backup: '+name)
    launcher='coop/launcher/CoD-Coop-Launcher'
    if launcher not in lock['files'] or not resolve(source,launcher).is_file():
        raise ValueError('Linux launcher bundle is required')
    shutil.copytree(source,destination)
    return {'scope':'staged prerelease payload; full installation validation still required',
            'suite_version':manifest['suite_version'],'protocol':PROTOCOL,
            'manifest_sha256':mhash,'runtime_lock_sha256':sha256(source/'coop/runtime-lock.json'),
            'launcher_sha256':files[launcher],'missing_base_packages':missing,'source_files':files}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();report=embed_suite(args.source,args.destination)
    args.report.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
