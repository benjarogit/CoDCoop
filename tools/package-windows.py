#!/usr/bin/env python3
"""Build the Windows release ZIP in the layout the installer discovers."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    suite = args.suite.resolve()
    output = args.output.resolve()
    if not args.installer.is_file():
        parser.error('--installer must be a file')
    for required in ('coop/variants.json', 'coop/runtime-lock.json',
                     'coop/launcher/CoD-Coop-Launcher.exe'):
        if not (suite / required).is_file():
            parser.error(f'Windows suite is missing {required}')
    if output.is_relative_to(suite):
        parser.error('--output must be outside the staged suite')

    entries = sorted(suite.rglob('*'))
    for entry in entries:
        if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
            parser.error(f'unsupported suite entry: {entry.relative_to(suite)}')

    destination = output.open('xb')
    try:
        with destination, ZipFile(destination, 'w', ZIP_DEFLATED, compresslevel=1) as archive:
            archive.write(args.installer, 'Install-CoD-Coop.exe')
            for entry in entries:
                archive.write(entry, Path('suite') / entry.relative_to(suite))
    except BaseException:
        output.unlink()
        raise


if __name__ == '__main__':
    main()
