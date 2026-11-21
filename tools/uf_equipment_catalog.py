#!/usr/bin/env python3
"""Extract original UF kit menus and native weapon resources, without game assets.

The roster planner is a resource calculation, not permission to start a map:
an exact map/world/kit baseline and early native media preload are still required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from campaign_inventory import layer_files, uncomment
from build_campaign_patch import blocks


def digest(data):
    return hashlib.sha256(data).hexdigest()


def processors(text):
    clean = uncomment(text)
    matches = list(re.finditer(r'(?m)^process_weapon_(\w+)\s*\([^\n]*\)\s*\{', clean))
    result = {}
    for match in matches:
        opening = clean.index('{', match.start())
        depth, end = 1, opening + 1
        while depth:
            if end >= len(clean): raise ValueError('Unbalanced equipment processor')
            depth += (clean[end] == '{') - (clean[end] == '}')
            end += 1
        body = clean[opening:end]
        entries = {}
        for case in re.finditer(r'case\s+(\d+)\s*:(.*?)(?=\bcase\s+\d+\s*:|\bdefault\s*:|$)', body, re.S):
            weapon = re.search(r'\bweapon\s*=\s*"([^"]+)"', case[2])
            entries[int(case[1])] = weapon[1] if weapon else None
        calls = set(re.findall(r'process_weapon_' + re.escape(match[1]) + r'\("([^"]+)","([^"]+)"\)', clean))
        result[match[1].lower()] = {'enum': entries, 'slots': {slot: cvar for cvar, slot in sorted(calls)}}
    if len(result) != 6: raise ValueError('Expected six original equipment processors')
    return result


def menu_choices(text):
    clean = uncomment(text)
    result = []
    for start, _, end in blocks(clean, 'itemDef'):
        item = clean[start:end]
        cvar = re.search(r'\bcvar\s+"([^"]+)"', item, re.I)
        choices = re.search(r'\bcvarfloatlist\s*\{([^}]+)\}', item, re.I)
        if not cvar or not choices: continue
        values = [{'label': label, 'value': int(value)} for label, value in
                  re.findall(r'"([^"]*)"\s+(-?\d+)', choices[1])]
        if not values or not any(v['label'].strip() for v in values): continue
        condition = re.search(r'\bcvarTest\s+"([^"]+)"', item, re.I)
        show = re.search(r'\b(showcvar|hidecvar)\s*\{([^}]+)\}', item, re.I)
        result.append({'cvar': cvar[1], 'choices': values,
                       'visibility': {'cvar': condition[1], 'operator': show[1].lower(),
                                      'values': re.findall(r'"([^"]+)"', show[2])}
                       if condition and show else None})
    return result


def weapon_fields(data):
    fields = data.decode('latin1').split('\\')
    if fields[0] != 'WEAPONFILE': raise ValueError('Unknown weapon definition format')
    return dict(zip(fields[1::2], fields[2::2]))


def extract(game):
    game = Path(game)
    effective, archives, invalid = {}, [], []
    try:
        for folder in ('Main', 'uo', 'UnitedFronts'):
            for path in layer_files(game, folder):
                try:
                    archive = zipfile.ZipFile(path)
                except zipfile.BadZipFile:
                    invalid.append({'package': path.relative_to(game).as_posix(), 'sha256': digest(path.read_bytes())})
                    continue
                archives.append(archive)
                for name in archive.namelist():
                    effective[name.lower()] = (path.relative_to(game).as_posix(), archive, name)

        def resource(name):
            if name.lower() not in effective: raise ValueError('Missing original resource: ' + name)
            package, archive, member = effective[name.lower()]
            data = archive.read(member)
            return data, {'package': package, 'member': member, 'sha256': digest(data)}

        loadout, revision = resource('maps/_UF_loadout.gsc')
        families = processors(loadout.decode('latin1'))
        sources, menus = [revision], []
        for name in ('ui/options_mod.menu', 'ui/victoryscreen.menu'):
            data, source = resource(name)
            sources.append(source)
            for entry in menu_choices(data.decode('latin1')):
                entry['source'] = name
                menus.append(entry)
        weapons = {}

        def add_weapon(name):
            if name.lower() in weapons: return
            if ('weapons/sp/' + name).lower() not in effective:
                weapons[name.lower()] = {'missing': 'weapons/sp/' + name, 'models': {}, 'server_model_fields': [], 'alt_weapon': None}
                return
            data, source = resource('weapons/sp/' + name)
            fields = weapon_fields(data)
            models = {}
            for key, value in fields.items():
                if key.lower().endswith('model') and value:
                    _, model = resource(value if value.startswith('xmodel/') else 'xmodel/' + value)
                    models[key] = model
            weapons[name.lower()] = {'source': source, 'models': models,
                'server_model_fields': [key for key in ('worldModel', 'pickupModel', 'projectileModel') if key in models],
                'alt_weapon': fields.get('altWeapon') or None}
            if fields.get('altWeapon'): add_weapon(fields['altWeapon'])

        for nation, family in families.items():
            family['active_campaign_menu'] = nation != 'polish'
            family['enum'] = {str(key): value for key, value in family['enum'].items()}
            family['menu_slots'] = {}
            for slot, cvar in family['slots'].items():
                found = [entry for entry in menus if entry['cvar'] == cvar]
                choices = {}
                for entry in found:
                    for choice in entry['choices']:
                        key = str(choice['value'])
                        if key not in family['enum']: raise ValueError('Menu enum absent from processor: ' + cvar + ':' + key)
                        choices[key] = {'label': choice['label'], 'weapon': family['enum'][key]}
                family['menu_slots'][slot] = {'cvar': cvar, 'choices': choices,
                    'menu_evidence': [{'source': e['source'], 'visibility': e['visibility']} for e in found]}
            for name in family['enum'].values():
                if name and name != 'none': add_weapon(name)
        add_weapon('Stuka_guns')
        air_names = ('vehicle_plane_stuka', 'v_us_air_p47', 'v_br_air_spitfire',
                     'v_rs_air_il2', 'vehicle_tank_panzeriv_machinegun', 'o_ge_prp_stukabomb')
        air = {name: resource('xmodel/' + name)[1] for name in air_names}
        _, weapon_source = resource('maps/_UF_weapons.gsc')
        sources.append(weapon_source)
        return {'schema': 1, 'status': 'source-derived-catalog-not-runtime-acceptance',
            'sources': sources, 'ignored_invalid_archives': invalid, 'families': families, 'weapons': weapons,
            'air_models': air,
            'world_authority': ['sp_ally', 'sp_axis', 'sp_ally_nation', 'sp_year', 'sp_history', 'sp_order'],
            'selection_rules': {
                'force_mode_2': 'sp_campaign 0=british,1=russian,2=american,3=german,4=italian,5=polish; Polish is script-only, absent from active campaign menu',
                'other_force_modes': 'sp_ally_nation, then level.campaign; dutch uses British processor; fallback American',
                'history_year': 'Manual processors contain no year/history restriction; automatic authored loadouts do. Do not infer automatic kits from manual enum.',
                'slots': 'Original four independent menu selections; no MG/binocular/smoke exclusion. Same native weapon selected twice does not create two copies.',
                'coop': '1–4 independently chosen kits; world faction/year/order remains host-owned. Runtime roster transport/application not certified by this catalog.'}}
    finally:
        for archive in archives: archive.close()


def chosen_aircraft(world):
    """Literal original _UF_weapons smoke-case decision; no caller-kit override."""
    factions = {'us_air': 'v_us_air_p47', 'us_inf': 'v_us_air_p47',
                'uk_air': 'v_br_air_spitfire', 'uk_inf': 'v_br_air_spitfire',
                'uk_sas': 'v_br_air_spitfire', 'uk_raf': 'v_br_air_spitfire', 'nl_resist': 'v_br_air_spitfire',
                'ru': 'v_rs_air_il2', 'ita': 'vehicle_plane_stuka', 'ger_para': 'vehicle_plane_stuka',
                'ger_heer': 'vehicle_plane_stuka', 'ger_ss': 'vehicle_plane_stuka', 'ger_marine': 'vehicle_plane_stuka'}
    if world.get('sp_ally') in factions: return factions[world['sp_ally']]
    campaign = world.get('campaign')
    if campaign == 'american':
        return 'vehicle_plane_stuka' if world.get('map') in ('sp_eugene', 'gfm_omaha') else 'v_us_air_p47'
    if campaign == 'british': return 'v_br_air_spitfire'
    if campaign == 'russian': return 'v_rs_air_il2'
    raise ValueError('Original UF aircraft choice unresolved; supply actual host sp_ally/campaign/map')


def roster_resources(catalog, kits, world=None):
    if not 1 <= len(kits) <= 4: raise ValueError('Expected one to four individual kits')
    selected, weapons, models, media = [], set(), {}, {}
    for player, kit in enumerate(kits):
        family = catalog['families'].get(kit.get('family'))
        if not family: raise ValueError('Unknown equipment family')
        if not family['active_campaign_menu']: raise ValueError('Equipment family has no active original campaign menu')
        if set(kit.get('slots', {})) != set(family['menu_slots']):
            raise ValueError('Each individual kit must specify all four slots')
        chosen = {}
        for slot, value in kit['slots'].items():
            choice = family['menu_slots'][slot]['choices'].get(str(value))
            if choice is None: raise ValueError('Unavailable menu choice: ' + kit['family'] + '/' + slot + '/' + str(value))
            chosen[slot] = choice['weapon']
            if choice['weapon'] and choice['weapon'] != 'none': weapons.add(choice['weapon'].lower())
        selected.append({'player': player, 'family': kit['family'], 'weapons': chosen})
    support = []
    if 'smokegrenade' in weapons:
        if world is None: raise ValueError('Smoke kit requires resolved host world for aircraft resources')
        plane = chosen_aircraft(world)
        for name in (plane, 'vehicle_tank_panzeriv_machinegun', 'o_ge_prp_stukabomb'):
            source = catalog['air_models'][name]
            models[source['member'].lower()] = source
            media[source['member'].lower()] = source
        weapons.add('stuka_guns')
        support.append({'mechanic': 'airstrike', 'aircraft': plane, 'authority': 'host-world', 'caller': 'actual-projectile-owner'})
    if 'land_mine' in weapons: support.append({'mechanic': 'mine', 'authority': 'host-world', 'owner': 'actual-projectile-owner'})
    if 'binoculars' in weapons: support.append({'mechanic': 'artillery', 'availability': 'original per-player charge/cooldown rules'})
    pending = list(weapons)
    while pending:
        name = pending.pop()
        weapon = catalog['weapons'][name]
        if 'missing' in weapon: raise ValueError('Selected original weapon resource is missing: ' + weapon['missing'])
        for field in weapon['server_model_fields']:
            source = weapon['models'][field]
            models[source['member'].lower()] = source
        for source in weapon['models'].values(): media[source['member'].lower()] = source
        alt = weapon['alt_weapon']
        if alt and alt.lower() not in weapons:
            weapons.add(alt.lower()); pending.append(alt.lower())
    return {'kits': selected, 'host_world': world, 'weapons': sorted(weapons), 'support': support,
            'required_server_models': sorted(models), 'required_media_models': sorted(media),
            'status': 'requires-exact-world-baseline-and-native-early-media-preload',
            'remaining_gates': ['map scripts and character alias choices must be present in exact baseline',
                'all peer renderer/XModel media must preload before native registration closes',
                'normal item registration and individual kit application must be runtime-verified']}


def budget(baseline, required):
    """Exact-name union only; no capacity claim if baseline has not been measured."""
    baseline = {name.lower().removeprefix('xmodel/') for name in baseline}
    required = {name.lower().removeprefix('xmodel/') for name in required}
    union = baseline | required
    return {'baseline_count': len(baseline), 'additional_models': sorted(required - baseline),
            'total': len(union), 'capacity': 255, 'remaining': 255 - len(union),
            'status': 'OVER_BUDGET' if len(union) > 255 else 'FITS_MODEL_TABLE_ONLY'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--roster', type=Path)
    parser.add_argument('--world', type=Path, help='resolved host map/campaign/sp_ally JSON; never personal kit settings')
    parser.add_argument('--baseline-model-table', type=Path, help='read-only native observer JSON for exact same host world')
    args = parser.parse_args()
    result = extract(args.game)
    if args.roster:
        roster = roster_resources(result, json.loads(args.roster.read_text()), json.loads(args.world.read_text()) if args.world else None)
        if args.baseline_model_table:
            baseline = json.loads(args.baseline_model_table.read_text())
            roster['model_budget'] = budget([entry['name'] for entry in baseline['models']], roster['required_server_models'])
            roster['model_budget']['baseline_source'] = str(args.baseline_model_table)
            roster['model_budget']['baseline_sha256'] = digest(args.baseline_model_table.read_bytes())
            roster['model_budget']['world_match_verified'] = False
        result['roster_resources'] = roster
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__': main()
