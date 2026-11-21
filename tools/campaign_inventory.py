#!/usr/bin/env python3
"""Inventory local campaign packages without exporting game assets.

This is a static inventory, never a playthrough result. Run against an isolated
installation (or read-only source) and pass --output explicitly to save metadata.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
MAP = re.compile(r'^maps/([^/]+)\.bsp$', re.I)
TRANSITION = re.compile(r'\b(missionsuccess|changelevel)\s*\(\s*("[^"\n]*"|[^,;)\n]+)', re.I)
ASSUMPTIONS = {
    'host_global': re.compile(r'\blevel\.player\b', re.I),
    'single_player_lookup': re.compile(r'\bgetent\s*\(\s*"player"\s*,\s*"classname"', re.I),
    'host_distance_gate': re.compile(r'\bdistance(?:squared)?\s*\([^;\n]*level\.player', re.I),
    'host_use_gate': re.compile(r'\blevel\.player\s+usebuttonpressed\s*\(', re.I),
    'host_touch_gate': re.compile(r'\blevel\.player\s+istouching\s*\(', re.I),
}
MECHANICS = {
    'vehicle_link': re.compile(r'\b(?:playerlinkto|linkto|unlink)\s*\(', re.I),
    'artillery': re.compile(r'\b\w*(?:artillery|barrage)\w*\b', re.I),
    'airstrike': re.compile(r'\b\w*(?:airstrike|air_strike)\w*\b', re.I),
    'deployed_weapon': re.compile(r'\b\w*(?:bipod|deploy)\w*\b', re.I),
    'cinematic_camera': re.compile(r'\b(?:setviewmodel|setviewangles|setplayerangles|viewmodelanim|setorigin)\s*\(', re.I),
}


def uncomment(text):
    """Keep offsets/newlines and quoted strings while blanking C/GSC comments."""
    return TOKEN.sub(lambda m: m[0] if m[0].startswith('"') else re.sub(r'[^\n]', ' ', m[0]), text)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def find_folder(game, name):
    matches = [p for p in game.iterdir() if p.is_dir() and p.name.lower() == name.lower()]
    if len(matches) != 1:
        raise ValueError('Expected one %s directory, found %d' % (name, len(matches)))
    return matches[0]


def native_package_key(name, engine='uo'):
    """Ascending nonlocalized PK3 order, before native head insertion.

    CoD1 1.5 PathCmp424420 / UO1.51 PathCmp425840 use ASCII uppercase,
    not lowercase. CoD1 additionally sorts an authored sp_ prefix as zz_
    before restoring it for opening; UO does not perform that substitution.
    Localized packs have a separate native language ordering and are excluded.
    """
    if engine not in ('cod1','uo'): raise ValueError('Unknown package engine')
    if engine=='cod1' and name.startswith('sp_'): name='zz_'+name[3:]
    return name.translate(str.maketrans('abcdefghijklmnopqrstuvwxyz\\:',
                                      'ABCDEFGHIJKLMNOPQRSTUVWXYZ//'))


def layer_files(game, folder, engine='uo'):
    root = find_folder(game, folder)
    # Only shipping assets, not generated Coop overlays, define the inventory.
    return [p for p in sorted(root.glob('*.pk3'), key=lambda p: native_package_key(p.name,engine))
            if not p.name.lower().startswith('localized_')
            # CoD1 treats zz_ as its reserved sp_ alias, not this disk name.
            and not (engine=='cod1' and p.name.startswith(('zz_','mp_')))
            and not re.match(r'^(?:pakz+|z+)_(?:cod)?coop', p.name, re.I)]


def analyze_script(path, data, package):
    text = uncomment(data.decode('latin-1'))
    flags = {}
    for key, pattern in ASSUMPTIONS.items():
        lines = [text.count('\n', 0, m.start()) + 1 for m in pattern.finditer(text)]
        if lines:
            flags[key] = {'count': len(lines), 'lines': lines[:12]}
    mechanics = [key for key, pattern in MECHANICS.items() if pattern.search(text)]
    transitions = []
    for match in TRANSITION.finditer(text):
        arg = match[2].strip()
        transitions.append({'line': text.count('\n', 0, match.start()) + 1,
                            'operation': match[1].lower(),
                            'target': arg[1:-1].lower() if arg.startswith('"') else None,
                            'expression': None if arg.startswith('"') else arg})
    # UF dispatches transitions centrally. Preserve the declared branch index;
    # do not pretend that every candidate edge is unconditional.
    dispatch = []
    cases = []
    for match in re.finditer(r'\bcase\s+"([^"]+)"\s*:|\bnextmap\s*\[\s*(\d+)\s*\]\s*=\s*"([^"]+)"|\bbreak\s*;', text, re.I):
        if match[1] is not None:
            cases.append(match[1].lower())
        elif match[2] is not None:
            for source in cases:
                dispatch.append({'source': source, 'target': match[3].lower(),
                                 'branch': int(match[2]), 'line': text.count('\n', 0, match.start()) + 1})
        else:
            cases = []
    cvars = sorted(set(re.findall(r'\b(?:get|set)cvar\s*\(\s*"([^"]+)"', text, re.I)))
    ai_fields = {}
    if path.lower().startswith('aitype/'):
        for field, value in re.findall(r'\bself\.(accuracy|health|scariness|bravery|grenadeAmmo)\s*=\s*([0-9.]+)\s*;', text, re.I):
            ai_fields[field.lower()] = float(value)
    result = {'path': path, 'package': package, 'sha256': hashlib.sha256(data).hexdigest(),
            'assumptions': flags, 'mechanics': mechanics, 'transitions': transitions,
            'dispatch_edges': dispatch, 'cvars': cvars}
    if ai_fields:
        result['ai_fields'] = ai_fields
    return result


def inventory(game):
    game = Path(game).resolve()
    layers = {'cod1': layer_files(game, 'Main'), 'uo': layer_files(game, 'uo'),
              'sp_improved': layer_files(game, 'sp_improved'),
              'united_fronts': layer_files(game, 'UnitedFronts')}
    metadata, members = {}, {}
    for paths in layers.values():
        for package in paths:
            rel = package.relative_to(game).as_posix()
            try:
                with zipfile.ZipFile(package) as z:
                    entries = {}
                    for item in z.infolist():
                        name = item.filename.replace('\\', '/').lower()
                        if MAP.match(name) or name.endswith('.gsc') or name.startswith('ui/') and name.endswith('.menu'):
                            entries[name] = item.filename
                    members[rel] = entries
            except zipfile.BadZipFile:
                metadata[rel] = {'size': package.stat().st_size, 'sha256': sha256(package),
                                 'warning': 'invalid_archive'}
                continue
            metadata[rel] = {'size': package.stat().st_size, 'sha256': sha256(package)}

    result = {'schema': 1, 'evidence': 'static-package-inventory',
              'runtime_verified': False, 'packages': metadata, 'profiles': {}}
    profile_layers = {'cod1': ['cod1'], 'uo': ['cod1', 'uo'],
                      'sp_improved': ['cod1', 'uo', 'sp_improved'],
                      'united_fronts': ['cod1', 'uo', 'united_fronts']}
    for profile, groups in profile_layers.items():
        providers = {}
        for group in groups:
            folder={'cod1':'Main','uo':'uo','sp_improved':'sp_improved','united_fronts':'UnitedFronts'}[group]
            for package in layer_files(game,folder,'cod1' if profile=='cod1' else 'uo'):
                rel = package.relative_to(game).as_posix()
                providers.update({name: (rel, original) for name, original in members.get(rel, {}).items()})
        scripts = []
        # Read each archive once per profile; no game script text is retained.
        by_package = {}
        for name, (rel, original) in providers.items():
            if name.endswith('.gsc'):
                by_package.setdefault(rel, []).append((name, original))
        for rel, selected in sorted(by_package.items()):
            with zipfile.ZipFile(game / rel) as z:
                for name, original in sorted(selected):
                    scripts.append(analyze_script(name, z.read(original), rel))
        maps = []
        script_index = {s['path']: s for s in scripts}
        dispatch = [edge for script in scripts for edge in script['dispatch_edges']]
        for name, (rel, original) in sorted(providers.items()):
            match = MAP.match(name)
            if match:
                mapname = match[1].lower()
                script = script_index.get('maps/' + mapname + '.gsc')
                maps.append({'id': mapname, 'bsp_package': rel,
                             'script': script['path'] if script else None,
                             'transitions': script['transitions'] if script else [],
                             'dispatch_edges': [e for e in dispatch if e['source'] == mapname],
                             'playthrough': 'not-tested'})
        result['profiles'][profile] = {'layers': groups, 'maps': maps, 'scripts': scripts,
                                      'entrypoint_candidates': menu_starts(game, providers),
                                      'map_count': len(maps),
                                      'assumption_counts': {key: sum(s['assumptions'].get(key, {}).get('count', 0) for s in scripts)
                                                            for key in ASSUMPTIONS},
                                      'limitations': ['static layer model; verify effective asset precedence at runtime',
                                                      'map inventory includes intro, credits and cinematic maps',
                                                      'script transitions and dispatch edges are candidates, not proof of completion',
                                                      'localized packages excluded; no playthrough inferred']}
    return result


def menu_starts(game, providers):
    starts = {}
    by_package = {}
    for name, (rel, original) in providers.items():
        if name.startswith('ui/') and name.endswith('.menu'):
            by_package.setdefault(rel, []).append((name, original))
    for rel, selected in sorted(by_package.items()):
        with zipfile.ZipFile(game / rel) as z:
            for name, original in selected:
                text = uncomment(z.read(original).decode('latin-1'))
                for match in re.finditer(r'\b(?:spmap|devmap)\s+([\w-]+)', text, re.I):
                    starts.setdefault(match[1].lower(), []).append(name)
    return {name: sorted(set(paths)) for name, paths in sorted(starts.items())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = inventory(args.game)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({p: {'maps': v['map_count'], 'assumptions': v['assumption_counts']}
                      for p, v in result['profiles'].items()}, indent=2))


if __name__ == '__main__':
    main()
