#!/usr/bin/env python3
"""Verify helper fingerprints against a pinned DLL without loading its code.

Executes only the compiled standalone C++ test fixture. The licensed game DLL
is read as PE data, never loaded or executed. Output belongs in ignored run/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess

SHA256 = '9fd3665ba2b67426bfd76df673d7e6575e237224bd5e86c4b979a4287bbeb32e'


def mapped_image(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Unsupported native Game DLL revision')
    pe, = struct.unpack_from('<I', data, 0x3c)
    if data[:2] != b'MZ' or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE headers')
    machine, count = struct.unpack_from('<HH', data, pe+4)
    optional_size, = struct.unpack_from('<H', data, pe+20)
    optional = pe+24
    magic, = struct.unpack_from('<H', data, optional)
    size, headers = struct.unpack_from('<II', data, optional+56)
    if machine != 0x14c or magic != 0x10b or not 1 <= count <= 32 or not 0 < headers <= len(data) or not headers <= size <= 32*1024*1024:
        raise ValueError('Unreviewed PE image layout')
    result = bytearray(size)
    result[:headers] = data[:headers]
    for index in range(count):
        section = optional+optional_size+40*index
        address, raw_size, offset = struct.unpack_from('<III', data, section+12)
        if offset+raw_size > len(data) or address+raw_size > size:
            raise ValueError('PE section exceeds its verified source/image')
        result[address:address+raw_size] = data[offset:offset+raw_size]
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dll', type=Path, required=True)
    parser.add_argument('--test-executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runner', default='', help='Fixture runner, e.g. wine; no shell')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.game_dll.read_bytes()
    mapped = args.output/'pinned-game-mapped-image.bin'
    mapped.write_bytes(mapped_image(source))
    executable = args.test_executable.resolve()
    process = subprocess.run(shlex.split(args.runner)+[str(executable), str(mapped.resolve())],
                             text=True, capture_output=True, timeout=120, check=False)
    report = {'status': 'PASS' if process.returncode == 0 else 'FAIL',
              'scope': 'standalone helper fingerprint fixture; no game DLL execution or gameplay capability',
              'game_dll_sha256': hashlib.sha256(source).hexdigest(),
              'mapped_image_sha256': hashlib.sha256(mapped.read_bytes()).hexdigest(),
              'test_executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
              'exit_code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}
    (args.output/'code-map-proof.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
