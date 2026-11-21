#!/usr/bin/env python3
"""Build local-only, hash-pinned campaign compatibility overlays.

No original game/menu assets are checked into this repository. Only reviewed
functions are transformed; converting level.player mechanically would corrupt
host-owned state and one-shot mission progression. Output is not certification.
"""
import argparse
import csv
import io
import hashlib
import json
import re
import zipfile
from pathlib import Path

from campaign_inventory import uncomment


ROOT = Path(__file__).resolve().parent.parent
PROFILES = {
    'sp_improved': ('sp_improved', 'sp_improved_1.5.pk3'),
    'united_fronts': ('UnitedFronts', 'ZUnitedFronts_1.1_beta.pk3'),
}
MENU_HASHES = {
    # Populated from the shipped packages; only known menu revisions accepted.
    'sp_improved': '1a70096a8ceb921f9cc87d740f66e06f8f1bf0d20776d9eb17e2df61b863c5ef',
    'united_fronts': '57683b9f4bc5f6b97ecba7971fcade3e9f584a41154d3643f9fd53d640b1aa9f',
}
MARKER = '// CoDCoop local campaign menu overlay v1'
UF_WEAPONS_HASH = '7eb9e7251df248a50ce2c2b5db4196a9634221f0207e969d4549946b8a4d1fb2'
UF_LOAD_HASH = '74a0b1971d6baf6dede4e382d6b867cb04b713223494011264288737d7814ef7'
UF_PATHFINDER_HASH = '990f290ff4d69996efb333e0d3898cd722887c80897477718662c8c9ac2114ad'
UF_HELMET_ALIAS_HASH = '20abf485b01312bc2dc3d4d262a1c2abeeedc2a52f96c8b96be635b332286b7f'
UF_HELMET_MODELS = ('xmodel/gear_US_helmet_82nd', 'xmodel/gear_US_helmet_82nd_net',
                    'xmodel/gear_US_helmet_82nd_camo')
MAINLINE_BERLIN_HASH = '1561a1717779b2d51399897c54dc84f193e0de9b08faf988bd0ef7648c5736f0'
MAINLINE_CREDITS_HASH = '1dd840242c8ebee02910c6b1c7e198b6415a16f3a081da685467adc73f611e06'
MAINLINE_CREDITS = 'coop_cod1_credits'
MAINLINE_ASSET_HASHES = {
    'maps/credits.bsp': 'fdda2f3834f1563f724b35409b792aca94328fbe8861fc979ea65399f666cd02',
    'maps/credits.gsc': MAINLINE_CREDITS_HASH,
    'maps/credits_anim.gsc': '0150b621d1e4e35bf822ba4e7ca448bdd1b595eaf1a0adcc7e16c4a19a0546c0',
    'maps/credits_fx.gsc': '7e8910fdfb0b58a3afdd5e3238ba9afc74a76186cc441b8a6237886ff45b5c3d',
}
TRIGGER_PATCHES = {
    'animscripts/melee.gsc': ('MeleeCombat',
        r'\bif\s*\(\s*self\.enemy\s*==\s*player\s*\)\s*\{\s*enemypose\s*=\s*player\s+getstance\s*\(\s*\)\s*;',
        'if (maps\\_coop_players::is_player(self.enemy))\n'
        '        {\n            enemypose = self.enemy getstance();', {
        '5adfac46917628da4d9a06a4781615aecfa93d463a9a4615ade9a5d166484e1c'}),
    'maps/brecourt.gsc': ('explosives_objective_wait', r'\bother\s*==\s*level\.player\b',
                         r'maps\\_coop_players::is_player(other)', {
        '1dfd9f38766e6d0696a7f5dde81bb2ea9b86a029765d7fd71657fd3b5aa375da',
        'c8fe7a281f1bec11804f6ffddb84a3b92de2d8701b854a6a4ceb697d6d7886a4',
        '5a87c168f56e6836bd6577a1abbcf9850ff3003c07cabda9ef4527c74b72f05d'}),
    'maps/burnville.gsc': ('flak_dialogue_think', r'\bother\s*==\s*level\.player\b',
                          r'maps\\_coop_players::is_player(other)', {
        '91bdabbbf0a5f539c8406ef37582596a447db00afa106200bb647f2d735e948c',
        'e57c20c2a54c1b49e6157b0811322c515aeb79c5fc1d1e52e261d301cbe86546'}),
    'maps/dawnville.gsc': ('sequence_3', r'\bother\s*==\s*level\.player\b',
                          r'maps\\_coop_players::is_player(other)', {
        '4415b5224aefea999e1747ae57f4a8685e78960cde40ee71192938df6cd71026',
        'e406d18ec4a1e693f5fb09d9af585da7a6216bff66092791f6e09ff753dc136d',
        '19f0eaf90a023e627295901048d4f68a2eb84f112dadea5377318ad739d74bcd'}),
    'maps/pegasusnight.gsc': ('bunker_suppression_check', r'\blevel\.player\s*==\s*activator\b',
                             r'maps\\_coop_players::is_player(activator)', {
        'e5e92b0bca5251a92451366dbbdead9997e249181fe1c2369b556b5550dbc427',
        'dd8fa291efd6a52480228c6d01da0eb8c77d65d77c6259695ac8a7c8ef4023d4',
        'c5d80d6be0ba22d7256592b0178aa22473c1c8550c869ceb223f999b6ff0cfaf'}),
}


def blocks(text, kind):
    """Return lexical block extents; ignore braces in strings/comments."""
    cleaned = uncomment(text)
    lexical = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: ' ' * len(m[0]), cleaned)
    found = []
    for match in re.finditer(r'\b' + re.escape(kind) + r'\s*\{', lexical, re.I):
        opening = lexical.index('{', match.start())
        depth = 1
        end = opening + 1
        while end < len(lexical) and depth:
            depth += (lexical[end] == '{') - (lexical[end] == '}')
            end += 1
        if depth:
            raise ValueError('Unbalanced %s block' % kind)
        found.append((match.start(), opening, end))
    return found


def transform_menu(data, button=None, popup=None):
    text = data.decode('latin-1')
    if MARKER in text:
        raise ValueError('Input already patched; use the original package')
    if re.search(r'\bname\s+"?coop_popmenu\b', uncomment(text), re.I):
        raise ValueError('Input already contains a Coop menu')
    menus = blocks(text, 'menuDef')
    mains = [(start, opening, end) for start, opening, end in menus
             if re.match(r'\s*name\s+"?main"?(?:\s|$)', uncomment(text[opening + 1:end]), re.I)]
    if len(mains) != 1:
        raise ValueError('Expected exactly one main menu, found %d' % len(mains))
    _, opening, end = mains[0]
    # Engine pause is overridden during Coop hosting. Change only active cvar
    # predicates, never script actions and never tokens inside comments.
    clean = uncomment(text)
    edits = []
    for match in re.finditer(r'\bcvarTest\s+"cl_paused"', clean, re.I):
        edits.append((match.start(), match.end(), re.sub('cl_paused', 'ui_coop_paused', match[0], flags=re.I)))
    # Hosting state 2 is not in-game. Convert only predicates paired with the
    # Coop pause variable, not unrelated mod settings such as campaign order.
    for start, op, close in blocks(text, 'itemDef'):
        segment = clean[op:close]
        if not re.search(r'\bcvarTest\s+"(?:cl_paused|ui_coop_paused)"', segment, re.I):
            continue
        for match in re.finditer(r'\bshowCvar\s*\{\s*"0"\s*\}', segment, re.I):
            edits.append((op + match.start(), op + match.end(), 'hideCvar { "1" }'))
    if button is None:
        button = (ROOT / 'ui' / 'coop_button.menu').read_text(encoding='utf-8')
        # Reserve a row below the existing right-hand menu. Both known mods
        # already use the original Coop button's y=310 row for other actions.
        button = button.replace('rect 385 310 120 15', 'rect 385 450 120 15')
        button = button.replace('rect 385 424 240 12', 'rect 20 450 340 12')
    if popup is None:
        popup = (ROOT / 'ui' / 'coop_popmenu.menu').read_text(encoding='utf-8')
    # Insert before the final top-level closing brace, not a nested action.
    lexical = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: ' ' * len(m[0]), clean)
    closing = lexical.rfind('}')
    if closing < end - 1 or lexical[closing + 1:].strip():
        raise ValueError('Unexpected menu root layout')
    edits.extend([(end - 1, end - 1, '\n' + MARKER + '\n' + button + '\n'),
                  (closing, closing, '\n' + popup + '\n')])
    for start, stop, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + replacement + text[stop:]
    blocks(text, 'menuDef')  # ensure nested syntax still balances
    return text.encode('latin-1')


def function_span(text, name):
    """Locate exactly one top-level GSC function, preserving original offsets."""
    clean = uncomment(text)
    lexical = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: ' ' * len(m[0]), clean)
    matches = list(re.finditer(r'^\s*' + re.escape(name) + r'\s*\([^)]*\)\s*\{', lexical, re.M))
    if len(matches) != 1:
        raise ValueError('Expected exactly one function ' + name)
    match = matches[0]
    opening = lexical.index('{', match.start())
    depth, close = 1, opening + 1
    while close < len(lexical) and depth:
        depth += (lexical[close] == '{') - (lexical[close] == '}')
        close += 1
    if depth:
        raise ValueError('Unbalanced function ' + name)
    return opening + 1, close - 1


def replace_active(text, pattern, replacement, expected=None, flags=re.I):
    matches = list(re.finditer(pattern, uncomment(text), flags))
    if expected is not None and len(matches) != expected:
        raise ValueError('Unexpected script shape for %s: %d' % (pattern, len(matches)))
    for match in reversed(matches):
        value = replacement(match) if callable(replacement) else replacement
        text = text[:match.start()] + value + text[match.end():]
    return text


def transform_uf_binoculars(data, qa=False):
    """Adapt reviewed ammunition functions and their startup calls.

    World-wide grenade scanning and one-shot mission state stay host owned.
    Mine ownership comes from a native, authoritative projectile-owner export.
    """
    if hashlib.sha256(data).hexdigest() != UF_WEAPONS_HASH:
        raise ValueError('Unknown United Fronts weapons script revision')
    text = data.decode('latin-1')
    edits = []
    for name in ('Binoculars_Ammo', 'Reload', 'Infinite_Ammo'):
        start, end = function_span(text, name)
        body = text[start:end]
        body = replace_active(body, r'\blevel\.player\b', 'self')
        body = replace_active(body, r'\blevel\.stockpile\b', 'self.coop_binocular_stockpile')
        body = replace_active(body, r'\blevel\s+(notify|endon)\b', lambda m: 'self ' + m[1])
        if name == 'Binoculars_Ammo':
            body = replace_active(body, r'\bthread\s+Reload\s*\(', 'self thread Reload(', expected=1)
        if name in ('Binoculars_Ammo', 'Infinite_Ammo'):
            # Explicit entity-bound lifecycle; level unload also destroys them.
            body = '\n    self endon("death");\n' + body
        edits.append((start, end, body))
    for start, end, body in sorted(edits, reverse=True):
        text = text[:start] + body + text[end:]
    # Mines already have entity-bound handlers; repair only the calls that
    # incorrectly attributed every thrown mine to level.player.
    start, end = function_span(text, 'Check_Grenades')
    body = text[start:end]
    body = replace_active(body,
        r'\blevel\.player\s+thread\s+PlantMine\s*\(\s*\)\s*;\s*grenades\[i\]\.active\s*=\s*1\s*;\s*grenades\[i\]\s+delete\s*\(\s*\)\s*;',
        'mine_owner = Coop_GrenadeOwner(grenades[i]);\n'
        '                    if (isdefined(mine_owner))\n'
        '                    {\n'
        '                        mine_owner thread PlantMine();\n'
        '                        grenades[i].active = 1;\n'
        '                        grenades[i] delete();\n'
        '                    }', expected=1)
    text = text[:start] + body + text[end:]
    start, end = function_span(text, 'PlantMine')
    body = replace_active(text[start:end], r'\blevel\.player\b', 'self')
    body = '\n    if (!isdefined(self.placedMines)) self.placedMines = 0;\n' + body
    text = text[:start] + body + text[end:]
    # getPlant returns surface metadata. The supplied UF script aliases the
    # actual protagonist as a temporary struct, inadvertently moving the host.
    start, end = function_span(text, 'getPlant')
    body = replace_active(text[start:end], r'\btemp\s*=\s*level\.player\s*;', 'temp = spawnstruct();', expected=3)
    text = text[:start] + body + text[end:]
    # Mount placement and stance are player state, not world-global state.
    for name in ('Trigger_Mount', 'Trigger_Stance', 'Get_Stance', 'BipodPlaceable'):
        start, end = function_span(text, name)
        body = text[start:end]
        body = replace_active(body, r'\blevel\.player\b', 'self')
        body = replace_active(body, r'\blevel\.mount_mg\b', 'self.coop_mount_mg')
        body = replace_active(body, r'\blevel\.mount_pose\b', 'self.coop_mount_pose')
        body = replace_active(body, r'(?<!\w)\bGet_Stance\s*\(', 'self Get_Stance(')
        if name in ('Trigger_Mount', 'Trigger_Stance'):
            body = replace_active(body, r'\bspawn\s*\(\s*"trigger_mount"\s*,\s*\(\s*0\s*,\s*0\s*,\s*0\s*\)\s*,\s*([01])\s*\)',
                                  lambda m: 'self Coop_MakeMount(' + m[1] + ')', expected=2)
            body = '\n    self endon("death");\n' + body
        if name == 'Trigger_Mount':
            body = replace_active(body, r'\bthread\s+Trigger_Stance\s*\(', 'self thread Trigger_Stance(', expected=1)
            body = replace_active(body, r'\bwhile\s*\(\s*isAlive\s*\(\s*self\s*\)\s*\)\s*\{',
                'while (isalive(self)) {\n'
                '        if (isdefined(self.coop_mount_mg) && distance(self.origin, self.coop_mount_mg.coop_origin) > 12)\n'
                '        {\n'
                '            self.coop_mount_mg delete();\n'
                '            self.coop_mount_mg = undefined;\n'
                '        }', expected=1)
        text = text[:start] + body + text[end:]
    text = replace_active(text, r'\bthread\s+Binoculars_Ammo\s*\(\s*\)\s*;',
                          'thread Coop_BinocularPlayers();', expected=1)
    text = replace_active(text, r'\bthread\s+Infinite_Ammo\s*\(\s*\)\s*;', '', expected=1)
    text = replace_active(text, r'\bthread\s+Trigger_Mount\s*\(\s*\)\s*;', '', expected=1)
    helper = (ROOT / 'campaign_patches' / 'uf_binocular_players.gsc').read_text(encoding='utf-8')
    if qa:
        helper = helper.replace('level.coop_uf_players_started = true;',
                                'level.coop_uf_players_started = true;\n    thread Coop_QAProbe();\n    thread Coop_QAOwnerProbe();\n    thread Coop_QAMineProbe();\n    thread Coop_QAMovieProbe();\n    thread Coop_QAAIProbe();\n    thread Coop_QAMGProbe();\n    thread Coop_QAAirProbe();\n    thread Coop_QAArtilleryProbe();', 1)
        helper += '\n' + (ROOT / 'campaign_patches/uf_qa_probe.gsc').read_text(encoding='utf-8')
        helper += '\n' + (ROOT / 'campaign_patches/uf_support_qa.gsc').read_text(encoding='utf-8')
    return (text + '\n' + helper).encode('latin-1')


def transform_uf_load(data, qa=False):
    if hashlib.sha256(data).hexdigest() != UF_LOAD_HASH:
        raise ValueError('Unknown United Fronts load script revision')
    text = data.decode('latin-1')
    startup = ('level.player = player;\n    maps\\_UF_weapons::Coop_PrecacheMountModels();\n'
               '    maps\\_UF_weapons::Coop_InitMineResources();\n'
               '    maps\\_UF_weapons::Coop_PrecacheAirAssets();\n'
               '    thread maps\\_UF_weapons::Coop_BinocularPlayers();')
    if qa:
        startup += '\n    precacheItem("binoculars");\n    precacheItem("mg30cal");\n    precacheItem("mg30cal_de");'
    return replace_active(text, r'\blevel\.player\s*=\s*player\s*;', startup, expected=1).encode('latin-1')


def transform_uf_support(text, qa=False):
    """After the pinned weapons revision is checked, retain its original air
    resource selection independently of the protagonist's current grenade slot.
    World smoke/plane ordering remains shared; only radio origin follows caller.
    """
    start, end = function_span(text, 'main')
    body = text[start:end]
    active = uncomment(body)
    smoke = re.search(r'\bcase\s+"smokegrenade"\s*:', active)
    fire = re.search(r'level\._effect\s*\[\s*"firetrail"\s*\]\s*=\s*loadfx\s*\([^;]+\);', active)
    if not smoke or not fire or fire.start() < smoke.end():
        raise ValueError('Reviewed UF air-resource case not found')
    stop = re.match(r'\s*break\s*;', active[fire.end():])
    if not stop:
        raise ValueError('Reviewed UF air-resource case ending changed')
    case_end = fire.end() + stop.end()
    original_resources = body[smoke.end():fire.end()]
    body = body[:smoke.end()] + '\n        Coop_InitAirResources();\n        break;' + body[case_end:]
    body = '\n    Coop_InitAirResources();\n' + body
    text = text[:start] + body + text[end:]
    text += ('\n// Original UF resources, shared for any actual player carrying smoke.\n'
             'Coop_InitAirResources()\n{\n'
             '    if (isdefined(level.coop_air_resources_ready)) return;\n'
             '    Coop_PrecacheAirAssets();\n' + original_resources + '\n'
             '    level.coop_air_resources_ready = true;\n}\n')
    start, end = function_span(text, 'Airstrike')
    body = text[start:end]
    body = '\n    caller = undefined;\n' + body
    body = replace_active(body, r'while\s*\(\s*isdefined\(smoke\)\s*\)\s*\{',
                          'while (isdefined(smoke)) {\n'
                          '        if (!isdefined(caller)) caller = Coop_GrenadeOwner(smoke);', expected=1)
    body = replace_active(body, r'\bBomber\s*\(\s*org\s*\)\s*;', 'Bomber(org, caller);', expected=1)
    text = text[:start] + body + text[end:]
    text = replace_active(text, r'\bBomber\s*\(\s*target\s*\)\s*\{', 'Bomber(target, caller) {', expected=1)
    start, end = function_span(text, 'Bomber')
    body = replace_active(text[start:end],
        r'thread\s+playSoundinSpace\s*\(\s*level\.bomber_call\s*,\s*level\.player\.origin\s*\)\s*;',
        'radio_origin = target.origin;\n'
        '        if (isdefined(caller)) radio_origin = caller.origin;\n'
        '        thread playSoundinSpace(level.bomber_call, radio_origin);', expected=1)
    text = text[:start] + body + text[end:]
    if qa:
        start, end = function_span(text, 'Bomber')
        body = '\n    Coop_QAAirBomber(caller);\n' + text[start:end]
        body = replace_active(body, r'stuka\s+setmodel\s*\(\s*stuka\.type\s*\)\s*;',
                              'stuka setmodel(stuka.type);\n    Coop_QAAirPlane(stuka);', expected=1)
        text = text[:start] + body + text[end:]
        start, end = function_span(text, 'bomb_explosion')
        body = replace_active(text[start:end],
            r'radiusDamage\s*\(\s*self\.origin\s*,\s*damage_range\s*,\s*max_damage\s*,\s*min_damage\s*\)\s*;',
            'radiusDamage(self.origin, damage_range, max_damage, min_damage);\n    Coop_QAAirImpact();', expected=1)
        text = text[:start] + body + text[end:]
    return text


def select_uf_world_resources(text):
    """Experimental policy: preserve original selected/world equipment instead
    of reserving every optional item in the finite server model table.
    This does not decide whether a future party uses shared or individual kits.
    """
    for function in ('Coop_PrecacheMountModels', 'Coop_PrecacheAirAssets', 'Coop_InitMineResources'):
        start, end = function_span(text, function)
        body = text[start:end]
        expected = {'Coop_PrecacheMountModels': (7, 0, 0),
                    'Coop_PrecacheAirAssets': (2, 6, 1),
                    'Coop_InitMineResources': (1, 1, 0)}[function]
        for name, count in zip(('precacheItem', 'precacheModel', 'precacheturret'), expected):
            if count:
                body = replace_active(body, r'\b'+name+r'\s*\([^;]+\)\s*;', '', expected=count)
        text = text[:start]+body+text[end:]
    start, end = function_span(text, 'main')
    body = text[start:end]
    # Replace only the first unconditional call inserted by our transform;
    # the original smoke case still uses its original selected aircraft path.
    active = uncomment(body)
    first = re.search(r'\bCoop_InitAirResources\s*\(\s*\)\s*;', active)
    if not first: raise ValueError('Shared air initialization not found')
    body = body[:first.start()]+'Coop_InitReachableAirResources();'+body[first.end():]
    text = text[:start]+body+text[end:]
    text += """
// Candidate world policy: normal selected inventory and authored pickups.
Coop_InitReachableAirResources()
{
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
        if ((players[i] getweaponslotweapon("grenade")) == "smokegrenade")
        {
            Coop_InitAirResources();
            return;
        }
    pickups = getentarray("weapon_smokegrenade", "classname");
    if (pickups.size) Coop_InitAirResources();
}
"""
    return text


def transform_uf_pathfinder_assets(data):
    if hashlib.sha256(data).hexdigest() != UF_PATHFINDER_HASH:
        raise ValueError('Unknown United Fronts pathfinder revision')
    text = data.decode('latin-1')
    text = replace_active(text, r'\bprecacheModel\s*\(\s*"xmodel/gear_US_helmet_82"\s*\)\s*;',
        'precacheModel("' + UF_HELMET_MODELS[0] + '");\n\tprecacheModel("' + UF_HELMET_MODELS[1] + '");', expected=1)
    text = replace_active(text, r'\bprecacheModel\s*\(\s*"xmodel/helmet_us_82"\s*\)\s*;',
        'precacheModel("' + UF_HELMET_MODELS[2] + '");', expected=1)
    return text.encode('latin-1')


def transform_trigger(path, data):
    function, pattern, replacement, allowed = TRIGGER_PATCHES[path]
    if hashlib.sha256(data).hexdigest() not in allowed:
        raise ValueError('Unknown mission script revision: ' + path)
    text = data.decode('latin-1')
    start, end = function_span(text, function)
    body = replace_active(text[start:end], pattern, replacement.replace('\\\\', '\\'), expected=1)
    return (text[:start] + body + text[end:]).encode('latin-1')


def build_trigger_patch(game, output, profile):
    """Patch only reviewed trigger activator predicates in installed sources."""
    from campaign_inventory import layer_files
    if profile not in ('cod1', 'uo', *PROFILES):
        raise ValueError('Unknown campaign profile')
    groups = ['Main'] + ([] if profile == 'cod1' else ['uo'])
    if profile in PROFILES:
        groups.append(PROFILES[profile][0])
    sources = {}
    for group in groups:
        for package in layer_files(Path(game), group):
            try:
                with zipfile.ZipFile(package) as z:
                    for name in z.namelist():
                        if name.lower() in TRIGGER_PATCHES:
                            sources[name.lower()] = (package, z.read(name))
            except zipfile.BadZipFile:
                continue
    if set(sources) != set(TRIGGER_PATCHES):
        raise ValueError('Required mission scripts missing')
    output = Path(output)
    if any(p.resolve() == output.resolve() for p, _ in sources.values()):
        raise ValueError('Cannot overwrite source mission package')
    metadata = {'schema': 1, 'profile': profile, 'changes': ['reviewed-player-trigger-activators', 'ai-melee-remote-player-stance'],
                'runtime_verified': False,
                'sources': {name: hashlib.sha256(data).hexdigest() for name, (_, data) in sorted(sources.items())}}
    entries = [(name, transform_trigger(name, data)) for name, (_, data) in sorted(sources.items())]
    entries.append(('maps/_coop_players.gsc', (ROOT / 'campaign_patches/coop_players.gsc').read_bytes()))
    entries.append(('codcoop/trigger-overlay.json', (json.dumps(metadata, sort_keys=True) + '\n').encode()))
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + '.part')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            info = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    tmp.replace(output)
    return metadata


def transform_mainline_berlin(data):
    if hashlib.sha256(data).hexdigest() != MAINLINE_BERLIN_HASH:
        raise ValueError('Unknown SP Improved Berlin revision')
    text = data.decode('latin-1')
    start, end = function_span(text, 'objectives_wait2')
    body = replace_active(text[start:end], r'\bsetcvar\s*\(\s*"nextmap"\s*,\s*"map credits"\s*\)\s*;',
        'if (getcvar("coop_mainline") == "1")\n'
        '        {\n'
        '            game["coop_mainline_stage"] = "cod1_credits";\n'
        '            setcvar("nextmap", "map ' + MAINLINE_CREDITS + '");\n'
        '        }\n'
        '        else\n'
        '            setcvar("nextmap", "map credits");', expected=1)
    return (text[:start] + body + text[end:]).encode('latin-1')


def transform_mainline_credits(data):
    if hashlib.sha256(data).hexdigest() != MAINLINE_CREDITS_HASH:
        raise ValueError('Unknown original CoD credits revision')
    text = data.decode('latin-1')
    start, end = function_span(text, 'endLevel')
    body = replace_active(text[start:end], r'\bmissionSuccess\s*\(\s*"training"\s*,\s*false\s*\)\s*;',
                          'game["coop_mainline_stage"] = "uo";\n'
                          '    missionSuccess("bastogne1", false);', expected=1)
    return (text[:start] + body + text[end:]).encode('latin-1')


def build_mainline_patch(game, output):
    """Keep CoD credits distinct from UO credits and chain the real endings."""
    from campaign_inventory import layer_files
    game, output = Path(game), Path(output)
    base = {}
    sound_source = None
    packages = layer_files(game, 'Main')
    mod = game / 'sp_improved/sp_improved_1.5.pk3'
    if any(output.resolve() == p.resolve() for p in packages + [mod]):
        raise ValueError('Cannot overwrite original mainline source packages')
    for package in packages:
        try:
            with zipfile.ZipFile(package) as z:
                for name in z.namelist():
                    lower = name.lower()
                    if lower == 'maps/credits.bsp' or (lower.startswith('maps/credits') and lower.endswith('.gsc')):
                        base[lower] = z.read(name)
                    if lower == 'soundaliases/iw_sound.csv':
                        sound_source = z.read(name)
        except zipfile.BadZipFile:
            continue
    if not {'maps/credits.bsp', 'maps/credits.gsc'}.issubset(base):
        raise ValueError('Original CoD credits assets required for the mainline bridge')
    if set(base) != set(MAINLINE_ASSET_HASHES) or any(hashlib.sha256(data).hexdigest() != MAINLINE_ASSET_HASHES[name] for name, data in base.items()):
        raise ValueError('Unknown original CoD credits asset revision')
    if sound_source is None or hashlib.sha256(sound_source).hexdigest() != '5fc788128d85ac7199b9e80462d09259d580d6d0b0063326c46eb993b8ce4c3b':
        raise ValueError('Unknown original CoD credits sound aliases')
    with zipfile.ZipFile(mod) as z:
        berlin = z.read('maps/berlin.gsc')
    entries = [('maps/berlin.gsc', transform_mainline_berlin(berlin))]
    entries.extend(mainline_sound_entries(sound_source))
    for name, data in sorted(base.items()):
        target = name.replace('maps/credits', 'maps/' + MAINLINE_CREDITS, 1)
        if name == 'maps/credits.gsc':
            data = transform_mainline_credits(data)
        if name.endswith('.gsc'):
            # Rename only explicit credits-module calls, including backrefs from
            # credits_anim/fx to credits. Shared utility code remains unchanged.
            text = data.decode('latin-1')
            text = re.sub(r'\bmaps\\credits(?=\b|_)', lambda m: 'maps\\' + MAINLINE_CREDITS, text, flags=re.I)
            data = text.encode('latin-1')
        entries.append((target, data))
    metadata = {'schema': 1, 'profile': 'sp_improved',
                'changes': ['cod1-movie-original-credits-uo-mainline'],
                'runtime_verified': False,
                'source_berlin_sha256': hashlib.sha256(berlin).hexdigest(),
                'source_credits_sound_sha256': hashlib.sha256(sound_source).hexdigest(),
                'credits_sources': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(base.items())},
                'route': ['berlin', 'cod_end.roq', MAINLINE_CREDITS, 'bastogne1'],
                'enable_cvar': 'coop_mainline=1'}
    entries.append(('codcoop/mainline-overlay.json', (json.dumps(metadata, sort_keys=True) + '\n').encode()))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.part')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            info = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    temporary.replace(output)
    return metadata


def mainline_sound_entries(source):
    """Alias only map-filtered credits sounds; retain the engine default tables."""
    rows = list(csv.reader(io.StringIO(source.decode('latin-1'))))
    header = next(row for row in rows if row and row[0] == 'name')
    column = header.index('loadspec')
    selected = []
    for row in rows:
        if len(row) > column and 'credits' in row[column].split():
            copy = list(row)
            copy[column] = MAINLINE_CREDITS
            selected.append(copy)
    if len(selected) != 4:
        raise ValueError('Original CoD credits sound selection changed')
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(header)
    writer.writerows(selected)
    defaults = ['dialog_generic', 'gmi_dialog_generic', 'gmi_music', 'gmi_sound',
                'gmi_voiceovers', 'iw_music', 'iw_sound', 'iw_sound2', 'iw_voiceovers',
                'pi_sound', 'surface_gmi_sound', 'wep_gmi_sound', 'coop_cod1_credits']
    spec = ''.join(name + '.csv\r\n' for name in defaults).encode('ascii')
    return [('soundaliases/coop_cod1_credits.csv', output.getvalue().encode('latin-1')),
            ('soundloadspecs/sp/' + MAINLINE_CREDITS + '.csv', spec)]


UF_BROLIO_BSP_HASH = 'ddedaf03e3078933a9857909d2f6ebb23657af281b45774ad31476b7f3500f24'
UF_GREASER_HASH = 'a3793a9c7ad4a27da87ffbfff4f85747c3838a2531e137fc1bdff71eff97fc63'
UF_GREASE_MODEL_HASH = '1fce95a271b5a429901c65bf27ffe0223641244e415a73fbc63fd1890038957c'


def uf_asset_aliases(archive):
    # Brolio's original pickup entity names world_greasegun, absent from its
    # package. Its own Greaser weapon defines weapon_greasegun as world model.
    # Copy the owned asset into a generated alias; no BSP/item changes or
    # original game assets are stored in this source repository.
    required = {'maps/brolio_assault.bsp': UF_BROLIO_BSP_HASH,
                'weapons/sp/greaser': UF_GREASER_HASH,
                'xmodel/weapon_greasegun': UF_GREASE_MODEL_HASH}
    for member, digest in required.items():
        if hashlib.sha256(archive.read(member)).hexdigest() != digest:
            raise ValueError('Unknown United Fronts Brolio alias source: '+member)
    return [('xmodel/world_greasegun', archive.read('xmodel/weapon_greasegun'))]


def build(source, output, profile, qa=False, world_policy="universal"):
    if world_policy not in ("universal", "selected"):
        raise ValueError("Unknown world resource policy")
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Output must not overwrite source package')
    with zipfile.ZipFile(source) as z:
        menu = z.read('ui/main.menu')
        weapons = z.read('maps/_UF_weapons.gsc') if profile == 'united_fronts' else None
        load = z.read('maps/_load.gsc') if profile == 'united_fronts' else None
        pathfinder = z.read('maps/pathfinder.gsc') if profile == 'united_fronts' else None
        aliases = uf_asset_aliases(z) if profile == 'united_fronts' else []
        if profile == 'united_fronts':
            alias = z.read('xmodelalias/helmet_us_airborne_82nd.gsc')
            if hashlib.sha256(alias).hexdigest() != UF_HELMET_ALIAS_HASH:
                raise ValueError('Unknown United Fronts airborne helmet alias revision')
            members = {name.lower() for name in z.namelist()}
            if not all(model.lower() in members for model in UF_HELMET_MODELS):
                raise ValueError('Required United Fronts airborne helmet models missing')
    digest = hashlib.sha256(menu).hexdigest()
    if not MENU_HASHES[profile] or digest != MENU_HASHES[profile]:
        raise ValueError('Unknown %s menu revision (%s); review before patching' % (profile, digest))
    transformed = transform_menu(menu)
    transformed_weapons = (transform_uf_support(transform_uf_binoculars(weapons, qa=qa).decode('latin-1'), qa=qa).encode('latin-1')
                           if weapons is not None else None)
    if transformed_weapons is not None and world_policy == 'selected':
        transformed_weapons = select_uf_world_resources(transformed_weapons.decode('latin-1')).encode('latin-1')
    transformed_load = transform_uf_load(load, qa=qa) if load is not None else None
    transformed_pathfinder = transform_uf_pathfinder_assets(pathfinder) if pathfinder is not None else None
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + '.part')
    # Fixed entry metadata makes builds byte-identical. The private metadata is
    # outside ui/, so the game will not parse it as another menu.
    metadata = {'schema': 1, 'profile': profile, 'source_menu_sha256': digest,
                'changes': ['coop-menu-entry', 'host-pause-predicates'],
                'runtime_verified': False}
    if qa:
        metadata['qa_only'] = True
    if transformed_weapons is not None:
        metadata['world_resource_policy'] = world_policy
        metadata['world_resource_policy_status'] = 'experimental-candidate'
        metadata['source_weapons_sha256'] = UF_WEAPONS_HASH
        metadata['source_load_sha256'] = UF_LOAD_HASH
        metadata['source_pathfinder_sha256'] = UF_PATHFINDER_HASH
        metadata['source_helmet_alias_sha256'] = UF_HELMET_ALIAS_HASH
        metadata['mount_model_catalog'] = json.loads((ROOT / 'campaign_patches/uf_mount_models.json').read_text())
        metadata['mount_weapon_catalog'] = json.loads((ROOT / 'campaign_patches/uf_mg_weapons.json').read_text())
        metadata['changes'].append('uf-actor-local-binocular-accounting')
        metadata['changes'].extend(['uf-projectile-owner-mines', 'uf-mine-surface-data-no-player-mutation'])
        metadata['changes'].append('uf-player-local-bipod-triggers')
        metadata['changes'].append('uf-pathfinder-existing-helmet-precaches')
        metadata['changes'].append('uf-brolio-owned-greasegun-model-alias')
        metadata['model_aliases'] = {'xmodel/world_greasegun': {'source': 'xmodel/weapon_greasegun', 'sha256': UF_GREASE_MODEL_HASH}}
        metadata['changes'].append('uf-native-mg-item-and-media-precaches')
        metadata['changes'].extend(['uf-shared-air-assets-independent-of-host-grenade', 'uf-projectile-caller-radio'])
        metadata['air_asset_catalog'] = json.loads((ROOT / 'campaign_patches/uf_air_assets.json').read_text())
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        entries = [('ui/main.menu', transformed),
                   ('codcoop/menu-overlay.json', (json.dumps(metadata, sort_keys=True) + '\n').encode())]
        if transformed_weapons is not None:
            entries.append(('maps/_UF_weapons.gsc', transformed_weapons))
            entries.append(('maps/_load.gsc', transformed_load))
            entries.append(('maps/pathfinder.gsc', transformed_pathfinder))
        entries.extend(aliases)
        for name, data in entries:
            entry = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    tmp.replace(output)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--profile', choices=('cod1', 'uo', *PROFILES), required=True)
    parser.add_argument('--triggers-only', action='store_true', help='Build reviewed mission activator patches instead of menu/UF mechanics')
    parser.add_argument('--world-policy', choices=('universal', 'selected'), default='universal',
                        help='experimental UF world resource policy; selected does not decide party kit preferences')
    parser.add_argument('--qa', action='store_true', help='UF only: append isolated runtime test fixtures (never distribute)')
    parser.add_argument('--mainline', action='store_true', help='SP Improved only: preserve CoD ending/credits then follow into UO')
    parser.add_argument('--output', type=Path, required=True,
                        help='Local-only .pk3 in an isolated test installation; source is never overwritten')
    args = parser.parse_args()
    if args.mainline:
        if args.profile != 'sp_improved':
            parser.error('--mainline requires --profile sp_improved')
        result = build_mainline_patch(args.game, args.output)
    elif args.triggers_only or args.profile not in PROFILES:
        result = build_trigger_patch(args.game, args.output, args.profile)
    else:
        folder, name = PROFILES[args.profile]
        result = build(args.game / folder / name, args.output, args.profile, qa=args.qa, world_policy=args.world_policy)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
