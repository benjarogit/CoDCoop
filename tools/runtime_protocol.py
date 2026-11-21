"""Read a Core protocol DATA export without loading or executing the DLL."""
import json
import os
from pathlib import Path
import struct
import subprocess

MAX_PE_SIZE = 32 * 1024 * 1024


def core_protocol(path):
    return core_data(path, 'Coop_Protocol')


def core_data(path, export_name):
    path = Path(path)
    if not 64 <= path.stat().st_size <= MAX_PE_SIZE:
        raise ValueError('Core PE size is outside the supported bound')
    with path.open('rb') as stream:
        data = stream.read(MAX_PE_SIZE + 1)
    return pe_data_u32(data, export_name)


def required_feature_mask(manifest):
    value=manifest.get('core_features_required',0)
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('Invalid required Core feature mask')
    return value


def require_core_features(path, required=0):
    if type(required) is not int or not 0 <= required <= 0xffffffff:
        raise ValueError('Invalid required Core feature mask')
    if not required:return None  # explicit legacy fixture/profile compatibility
    actual=core_data(path,'Coop_Features')
    if actual & required != required:
        raise ValueError('Core feature mask does not provide required compiled APIs')
    return actual


def pe_data_u32(data, export_name):
    if not isinstance(data, bytes) or not 64 <= len(data) <= MAX_PE_SIZE:
        raise ValueError('Invalid Core PE bytes')
    def read(fmt, offset):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError('Truncated Core PE structure')
        return struct.unpack_from(fmt, data, offset)
    if data[:2] != b'MZ':
        raise ValueError('Core is not a PE DLL')
    pe, = read('<I', 0x3c)
    if pe < 64 or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid Core PE signature')
    machine, count, _, _, _, optional_size, characteristics = read('<HHIIIHH', pe+4)
    if machine != 0x14c or not 1 <= count <= 96 or not characteristics & 0x2000:
        raise ValueError('Core must be a bounded x86 PE DLL')
    optional = pe + 24
    magic, = read('<H', optional)
    if magic != 0x10b or optional_size < 104 or optional + optional_size > len(data):
        raise ValueError('Unsupported Core PE optional header')
    directories, = read('<I', optional+92)
    export_rva, export_size = read('<II', optional+96)
    if directories < 1 or export_size < 40:
        raise ValueError('Core has no export directory')
    sections = []
    table = optional + optional_size
    for index in range(count):
        base = table + 40 * index
        if base + 40 > len(data):
            raise ValueError('Truncated Core PE section table')
        virtual_size, address, raw_size, raw_offset = read('<IIII', base+8)
        flags, = read('<I', base+36)
        if raw_size and (raw_offset < table + 40 * count or raw_offset + raw_size > len(data)):
            raise ValueError('Core PE section exceeds file bounds')
        sections.append((address, raw_size, raw_offset, flags))
    def mapped(rva, size):
        matches = [(raw+(rva-address), flags, raw+raw_size) for address,raw_size,raw,flags in sections
                   if rva >= address and rva-address <= raw_size and size <= raw_size-(rva-address)]
        if len(matches) != 1:
            raise ValueError('Core PE RVA is unmapped or ambiguous')
        return matches[0]
    directory, _, _ = mapped(export_rva, 40)
    functions, names, function_table, name_table, ordinal_table = read('<IIIII', directory+20)
    if not 1 <= functions <= 4096 or not 1 <= names <= 4096:
        raise ValueError('Core PE export count is outside the supported bound')
    functions_offset, _, _ = mapped(function_table, functions*4)
    names_offset, _, _ = mapped(name_table, names*4)
    ordinals_offset, _, _ = mapped(ordinal_table, names*2)
    found = []
    for index in range(names):
        name_rva, = read('<I', names_offset+4*index)
        offset, _, end = mapped(name_rva, 1)
        stop = data.find(b'\0', offset, min(end, offset+128))
        if stop < 0:
            raise ValueError('Unterminated Core PE export name')
        if data[offset:stop] != export_name.encode('ascii'):
            continue
        ordinal, = read('<H', ordinals_offset+2*index)
        if ordinal >= functions:
            raise ValueError('Core PE export ordinal is invalid')
        value_rva, = read('<I', functions_offset+4*ordinal)
        if export_rva <= value_rva < export_rva+export_size:
            raise ValueError('Core '+export_name+' cannot be a forwarded export')
        value_offset, flags, _ = mapped(value_rva, 4)
        if not flags & 0x40000000 or flags & (0x80000000 | 0x20000000):
            raise ValueError('Core '+export_name+' must be readable nonwritable nonexecutable DATA')
        found.append(read('<I', value_offset)[0])
    if len(found) != 1:
        raise ValueError('Core requires one readonly '+export_name+' DATA export; rebuild legacy Core inputs')
    return found[0]


def checker_capabilities(checker, wine_prefix=None):
    checker = Path(checker).resolve()
    env = os.environ.copy()
    command = [str(checker), 'capabilities']
    if os.name != 'nt':
        if wine_prefix is None or not (Path(wine_prefix)/'system.reg').is_file():
            raise ValueError('Provide an initialized isolated --checker-prefix for native checker metadata')
        env.update(WINEPREFIX=str(Path(wine_prefix).resolve()), WINEDEBUG='-all')
        command.insert(0, 'wine')
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30, check=True)
        value = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise ValueError('Native checker capabilities unavailable; rebuild the checker') from error
    if (not isinstance(value, dict) or value.get('kind') != 'codcoop_suite_checker'
            or type(value.get('schema')) is not int or value['schema'] != 1
            or type(value.get('protocol')) is not int or value['protocol'] < 1):
        raise ValueError('Unsupported native checker capabilities')
    return value


def require_runtime_protocol(runtime, manifest_protocol, wine_prefix=None, required_features=0):
    if type(manifest_protocol) is not int or manifest_protocol < 1:
        raise ValueError('Invalid manifest protocol')
    runtime = Path(runtime)
    core = core_protocol(runtime/'codcoop_core.dll')
    checker = checker_capabilities(runtime/'suite-check.exe', wine_prefix)
    if core != manifest_protocol or checker['protocol'] != manifest_protocol:
        raise ValueError('Core, native checker and manifest protocols must match')
    actual=require_core_features(runtime/'codcoop_core.dll',required_features)
    if required_features and checker.get('core_features_validation') is not True:
        raise ValueError('Native checker cannot validate required Core feature mask; rebuild the checker')
    return {'schema': 1, 'manifest_protocol': manifest_protocol, 'core_protocol': core,
            'checker_protocol': checker['protocol'], 'required_core_features':required_features,
            'core_features':actual}
