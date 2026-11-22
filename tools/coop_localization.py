"""Pinned owned native-UI locale banks shared by staging and Linux setup."""
import hashlib
import io
import json
import os
import stat
from pathlib import Path
import zipfile
from build_coop_localization import INSTALLED_PATH,RESOURCE_PATH,package_bytes

MAX_LOCALE_BYTES=64*1024

BANKS={lang:f'coop/languages/{lang}/{INSTALLED_PATH}' for lang in ('en','de')}


def requirement(manifest):
    items=[item for item in manifest.get('required',[]) if item.get('path')==INSTALLED_PATH]
    if len(items)!=1:raise ValueError('Mandatory CoDCoop UI localization requirement is missing')
    item=items[0]
    if set(item.get('locales',{}))!={'en','de'}:raise ValueError('CoDCoop UI locale pins are missing')
    expected=[item['locales'][lang]['sha256'] for lang in ('en','de')]
    if item.get('sha256_any')!=expected or manifest.get('approved_localizations',{}).get(INSTALLED_PATH)!=expected:
        raise ValueError('CoDCoop UI locale approval differs from required pins')
    return item


def validate(data,language,manifest):
    item=requirement(manifest);pin=item['locales'][language]
    if len(data)!=pin['size'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:
        raise ValueError('CoDCoop UI locale missing or changed: '+language)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist()!=[RESOURCE_PATH] or archive.comment or archive.infolist()[0].compress_type!=zipfile.ZIP_STORED:
            raise ValueError('CoDCoop UI package must contain exactly one owned stored resource')
        archive.read(RESOURCE_PATH) # CRC/size validation
    return data


def generate_banks(output,manifest):
    root=Path(output);item=requirement(manifest)
    for language,relative in BANKS.items():
        data=validate(package_bytes(language),language,manifest)
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    path=root/INSTALLED_PATH;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((root/BANKS['en']).read_bytes())
    return {'sha256':item['locales']['en']['sha256'],'size':item['locales']['en']['size'],'source':'codcoop_generator'}


def read_bank(root,relative):
    root=Path(root).resolve();path=root/relative
    unsafe='CoDCoop UI locale bank missing or unsafe: '+relative
    try:
        if path.is_symlink() or not path.parent.resolve().is_relative_to(root):raise ValueError(unsafe)
        before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_LOCALE_BYTES:raise ValueError(unsafe)
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as source:
            opened=os.fstat(source.fileno())
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if identity(before)!=identity(opened) or not stat.S_ISREG(opened.st_mode):raise ValueError(unsafe)
            data=source.read(MAX_LOCALE_BYTES+1)
            after=os.fstat(source.fileno())
            if len(data)>MAX_LOCALE_BYTES or len(data)!=opened.st_size or identity(opened)!=identity(after) or identity(after)!=identity(path.lstat()):raise ValueError(unsafe)
        if path.is_symlink() or not path.parent.resolve().is_relative_to(root):raise ValueError(unsafe)
        return data
    except OSError as exc:
        raise ValueError(unsafe) from exc


def preflight(root,manifest):
    root=Path(root);requirement(manifest)
    for language,relative in BANKS.items():
        validate(read_bank(root,relative),language,manifest)
    validate(read_bank(root,INSTALLED_PATH),'en',manifest) # every new payload defaults English


def apply(game,language,transaction):
    game=Path(game);manifest=json.loads((game/'coop/variants.json').read_text())
    data=validate(read_bank(game,BANKS[language]),language,manifest)
    # Transaction owns the old active pack, including a prior locale choice.
    path=transaction.remember(INSTALLED_PATH);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
