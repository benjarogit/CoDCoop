"""Personal UF equipment preferences and a future ready-request contract.

This module neither writes engine CVars nor applies a loadout. A launcher must
not forward preferences without explicit native/session capability. A reload
control protocol number never provides that equipment capability.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

SLOTS = ('primary', 'secondary', 'pistol', 'grenade')
CAPABILITY = 'uf.individual_equipment.v1'


def catalog_digest(catalog):
    return hashlib.sha256(json.dumps(catalog, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def active_families(catalog):
    if not isinstance(catalog, dict) or type(catalog.get('schema')) is not int or catalog['schema'] != 1 or not isinstance(catalog.get('families'), dict):
        raise ValueError('Unsupported equipment catalog')
    result = {}
    for name, family in catalog['families'].items():
        if not isinstance(name, str) or not isinstance(family, dict):
            raise ValueError('Invalid equipment family')
        if family.get('active_campaign_menu') is not True:
            continue
        if set(family.get('menu_slots', {})) != set(SLOTS):
            raise ValueError('Equipment catalog must expose the four original slots')
        for slot in SLOTS:
            choices = family['menu_slots'][slot].get('choices')
            if not isinstance(choices, dict) or not choices:
                raise ValueError('Equipment catalog has an empty slot')
            for number, choice in choices.items():
                if not isinstance(number, str) or not number.isascii() or not number.isdigit() or str(int(number)) != number or not isinstance(choice, dict):
                    raise ValueError('Equipment catalog has an invalid original enum')
                weapon = choice.get('weapon')
                if not isinstance(choice.get('label'), str) or (weapon is not None and not isinstance(weapon, str)):
                    raise ValueError('Equipment catalog has an invalid choice')
                if weapon and weapon != 'none':
                    weapons = catalog.get('weapons', {})
                    entry = weapons.get(weapon.lower()) if isinstance(weapons, dict) else None
                    if not isinstance(entry, dict) or not entry or 'missing' in entry:
                        raise ValueError('Equipment catalog references a missing weapon')
        result[name] = family
    if not result:
        raise ValueError('Equipment catalog has no active families')
    return result


def default_preferences(catalog):
    families = active_families(catalog)
    family = 'american' if 'american' in families else sorted(families)[0]
    slots = {slot: min(map(int, families[family]['menu_slots'][slot]['choices'])) for slot in SLOTS}
    return {'schema': 1, 'mode': 'automatic', 'manual': {'family': family, 'slots': slots}}


def validate_preferences(value, catalog):
    families = active_families(catalog)
    if not isinstance(value, dict) or set(value) != {'schema', 'mode', 'manual'} or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('Unsupported equipment preferences')
    if not isinstance(value['mode'], str) or value['mode'] not in ('automatic', 'manual'):
        raise ValueError('Choose automatic or manual equipment')
    manual = value['manual']
    if not isinstance(manual, dict) or set(manual) != {'family', 'slots'} or not isinstance(manual['family'], str) or manual['family'] not in families:
        raise ValueError('Equipment family is not in the active original menu')
    slots = manual['slots']
    if not isinstance(slots, dict) or set(slots) != set(SLOTS):
        raise ValueError('Specify all four original equipment slots')
    choices = families[manual['family']]['menu_slots']
    for slot, number in slots.items():
        if type(number) is not int or str(number) not in choices[slot]['choices']:
            raise ValueError('Unavailable original equipment choice: ' + slot)
    # Return independent JSON data, not aliases into a mutable GUI or catalog.
    return {'schema': 1, 'mode': value['mode'], 'manual': {'family': manual['family'], 'slots': {slot: slots[slot] for slot in SLOTS}}}


def preferences_path():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
        return base / 'CoDCoop/equipment.json'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'codcoop/equipment.json'


def load_preferences(catalog, path=None):
    path = Path(path) if path is not None else preferences_path()
    if not path.exists():
        return default_preferences(catalog)
    if path.stat().st_size > 16384:
        raise ValueError('Equipment preferences file is too large')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as error:
        raise ValueError('Equipment preferences file is unreadable') from error
    return validate_preferences(value, catalog)


def save_preferences(value, catalog, path=None):
    value = validate_preferences(value, catalog)
    path = Path(path) if path is not None else preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.equipment-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


def build_ready_request(value, catalog, capability):
    """Build data for a future ready exchange; never apply or send it here.

    Identity is deliberately absent: the transport must bind the request to the
    authenticated local participant, rather than letting it select another slot.
    A bare protocol number or manifest claim is not a native capability.
    """
    value = validate_preferences(value, catalog)
    if (not isinstance(capability, dict) or capability.get('id') != CAPABILITY
            or type(capability.get('schema')) is not int or capability['schema'] != 1 or capability.get('per_player') is not True
            or capability.get('ready_request') != 'uf-equipment-v1'
            or capability.get('catalog_sha256') != catalog_digest(catalog)
            or not isinstance(capability.get('modes'), list) or value['mode'] not in capability['modes']):
        raise ValueError('Native per-player equipment capability is unavailable or incompatible')
    request = {'kind': 'uf_equipment', 'schema': 1, 'scope': 'local-player',
               'catalog_sha256': catalog_digest(catalog), 'mode': value['mode']}
    if value['mode'] == 'manual':
        request.update(value['manual'])
    return request

# Weapon names stay recognizable in both languages; descriptive equipment and
# optic labels are translated. Internal script aliases are never shown as names.
WEAPON_NAMES = {
    'carbinem1s': 'M1 Carbine', 'm1carbine': 'M1A1 Carbine', 'm1garand': 'M1 Garand',
    'springfielda1_un': 'Springfield M1903A1', 'springfield': 'Springfield M1903A1',
    'thompson': 'Thompson', 'thompsonm1': 'Thompson M1', 'thompson28': 'Thompson M1928',
    'greaser': 'M3 Grease Gun', 'bar': 'BAR', 'mg30cal': '.30 cal MG', 'bazooka': 'Bazooka', 'colt': 'Colt .45',
    'webley': 'Webley', 'welrod': 'Welrod', 'enfield': 'Lee-Enfield', 'enfieldscoped': 'Lee-Enfield',
    'piat': 'PIAT', 'delisle': 'De Lisle', 'sten': 'Sten', 'sten_silenced': 'Sten', 'stenmk5': 'Sten Mk V',
    'bren': 'Bren', 'luger': 'Luger', 'p38': 'Walther P38', 'mauser_c96': 'Mauser C96', 'kar98k': 'Kar98k',
    'kar98k_sniper': 'Kar98k', 'fg42': 'FG42', 'bubbles': 'FG42', 'mg34': 'MG34', 'mg42': 'MG42',
    'panzerfaust': 'Panzerfaust', 'panzerschreck': 'Panzerschreck', 'g41': 'Gewehr 41',
    'gewehr43': 'Gewehr 43', 'gewehr43_scoped': 'Gewehr 43', 'mp38': 'MP38', 'mp40': 'MP40',
    'mp41': 'MP41', 'mp44': 'MP44', 'beretta': 'Beretta', 'carcano': 'Carcano', 'mab': 'MAB', 'breda': 'Breda',
    'tt33': 'TT-33', 'mosin_nagant': 'Mosin-Nagant', 'mosin_nagant_sniper': 'Mosin-Nagant',
    'svt40': 'SVT-40', 'ppsh': 'PPSh-41', 'ppsh43': 'PPS-43', 'dp28_un': 'DP-28', 'ppshv2': 'PPSh-41 (V2)',
}


def choice_label(choice, language='en'):
    weapon = (choice.get('weapon') or 'none').lower()
    translated = {
        'none': ('None', 'Keine'), 'fraggrenade': ('Fragmentation grenade', 'Splittergranate'),
        'mk1britishfrag': ('British fragmentation grenade', 'Britische Splittergranate'),
        'stielhandgranate': ('Stick grenade', 'Stielhandgranate'),
        'rgd-33russianfrag': ('RGD-33 grenade', 'RGD-33-Granate'),
        'satchelcharge': ('Satchel charge', 'Sprengladung'), 'land_mine': ('Land mine', 'Landmine'),
        'smokegrenade': ('Smoke grenade (air support)', 'Rauchgranate (Luftunterstützung)'),
        'binoculars': ('Binoculars (artillery)', 'Fernglas (Artillerie)'),
        'flamethrower': ('Flamethrower', 'Flammenwerfer'),
    }
    if weapon in translated:
        return translated[weapon][language == 'de']
    if weapon not in WEAPON_NAMES:
        raise ValueError('Equipment choice needs a reviewed display name')
    name = WEAPON_NAMES[weapon]
    if weapon in {'springfield', 'enfieldscoped', 'kar98k_sniper', 'gewehr43_scoped', 'mosin_nagant_sniper', 'fg42'}:
        name += ' (Zielfernrohr)' if language == 'de' else ' (scope)'
    elif weapon == 'sten_silenced':
        name += ' (schallgedämpft)' if language == 'de' else ' (silenced)'
    return name
