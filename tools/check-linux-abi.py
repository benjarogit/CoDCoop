#!/usr/bin/env python3
"""Fail when any bundled ELF requires glibc newer than the supported floor."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def check(root, maximum=(2, 35)):
    files = [root] if root.is_file() else sorted(p for p in root.rglob('*') if p.is_file())
    result = {'root': str(root), 'maximum_allowed': '.'.join(map(str, maximum)), 'elf_files': 0,
              'maximum_required': '0.0', 'violations': []}
    peak = (0, 0)
    for path in files:
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        result['elf_files'] += 1
        output = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
        versions = [tuple(map(int, version.split('.'))) for version in re.findall(r'GLIBC_([0-9]+\.[0-9]+)', output)]
        needed = max(versions, default=(0, 0))
        peak = max(peak, needed)
        if needed > maximum:
            result['violations'].append({'file': str(path.relative_to(root) if root.is_dir() else path),
                                         'requires': '.'.join(map(str, needed))})
    result['maximum_required'] = '.'.join(map(str, peak))
    result['ok'] = result['elf_files'] > 0 and not result['violations']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--maximum', default='2.35')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.root, tuple(map(int, args.maximum.split('.'))))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
