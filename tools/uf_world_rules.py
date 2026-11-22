"""Independent, source-pinned UF startup graph. No native readiness capability.

The result is the synchronous Campaign/Cvars/Map_Climate/Levels stage, not a
claim that scripts, resource registration, or a mission have finished loading.
Ordered spawner facts must come from the Host's original getspawnerarray call;
declared party world fields are deliberately not accepted as resolver inputs.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / 'campaign_patches/uf_world_rules.json'
PINNED = {
    'maps/_UF_loadout.gsc': '3e03a533edc298d1432db2dfa7771c97c924be2e9da5171339ce539b60bd534e',
    'maps/_UF_mod.gsc': '4be5bb5c6849f7c2b762ccdd27c2020b8c99a70cf64e8e8be98acc387ec698cf',
    'maps/_UF_maps.gsc': 'd5db7c1056ac34082346c07e0cec3903d7ebdb9aa355b2b5cc11b0f34bdcab74',
}
FACTIONS = ('none', 'us_air', 'us_inf', 'ru', 'uk_air', 'uk_inf', 'uk_sas',
            'uk_raf', 'nl_resist', 'ger_heer', 'ger_ss', 'ger_para', 'ger_marine', 'ita')


def _function(text, name):
    match = re.search(r'(?m)^' + re.escape(name) + r'\s*\([^)]*\)\s*\{', text)
    if not match:
        raise ValueError('Missing pinned function: ' + name)
    start, depth, end = match.end(), 1, match.end()
    # Pinned GSC is comment-stripped; quoted braces are excluded from scanning.
    token = re.compile(r'"(?:\\.|[^"\\])*"|[{}]')
    for found in token.finditer(text, end):
        depth += (found[0] == '{') - (found[0] == '}')
        if not depth:
            return text[start:found.start()]
    raise ValueError('Unbalanced pinned function')


def _cases(text, assignment):
    """Extract ordered fallthrough case groups for a verified simple switch."""
    pending, result, default, is_default = [], {}, None, False
    pattern = re.compile(r'case\s+"([^"]+)"\s*:|\bdefault\s*:|' + assignment + r'|\bbreak\s*;')
    for match in pattern.finditer(text):
        if match[1] is not None:
            pending.append(match[1])
        elif match[0].startswith('default'):
            is_default = True
        elif match[0].startswith('break'):
            pending, is_default = [], False
        else:
            value = match[2]
            for key in pending:
                result[key] = value
            if is_default:
                default = value
            pending, is_default = [], False
    return result, default


def extract(package):
    from campaign_inventory import uncomment
    with zipfile.ZipFile(package) as archive:
        scripts = {}
        for member, expected in PINNED.items():
            data = archive.read(member)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Unsupported UF source revision: ' + member)
            scripts[member] = uncomment(data.decode('latin1'))
    loadout, mod = scripts['maps/_UF_loadout.gsc'], scripts['maps/_UF_mod.gsc']
    campaign = _function(loadout, 'Campaign')
    by_map, by_spawner = campaign.split('spawners = getspawnerarray();')
    assignment = r'level\.campaign\s*=\s*"([^"]+)"'
    maps, default = _cases(by_map, assignment)
    spawners, _ = _cases(by_spawner, assignment)
    years, year_default = _cases(_function(loadout, 'Levels'), r'setCvar\("sp_year",\s*"([^"]+)"\)')
    climate = _function(mod, 'Map_Climate')
    _, climate_maps = climate.split('switch (level.script)')
    climates, _ = _cases(climate_maps, r'setcvar\("sp_climate",\s*"([^"]+)"\)')
    snow = re.findall(r'class\[\d+\]\s*=\s*"([^"]+)"', climate)
    nations, _ = _cases(_function(mod, 'Cvars').split('default:')[0], r'nation\[i\]\s*=\s*"([^"]+)"')
    registered = json.loads((ROOT / 'content/campaign-inventory.json').read_text())
    registered = sorted(entry['id'] for entry in registered['profiles']['united_fronts']['maps'])
    if (len(spawners), len(snow), default, year_default) != (23, 10, 'american', '1944'):
        raise ValueError('Pinned source graph extraction changed')
    return dict(schema=1, sources=PINNED, registered_maps=registered,
                map_campaign=maps, default_campaign=default, spawner_campaign=spawners,
                map_year={key: int(value) for key, value in years.items()}, default_year=int(year_default),
                snow_spawners=snow, map_climate=climates, faction_nation=nations)


@dataclass(frozen=True)
class Inputs:
    # These are actual pre-load GSC input strings, not post-load derived CVars.
    ally: str = ''
    axis: str = ''
    ally_menu: str = ''
    axis_menu: str = ''
    order: str = ''
    ammo: str = ''
    history: str = ''
    forceweapons: str = ''
    campaign_menu: str = ''
    saved: bool = False

    def validate(self):
        for name in ('ally', 'axis'):
            if getattr(self, name) not in ('',) + FACTIONS:
                raise ValueError('Unreviewed raw faction input: ' + name)
        for name, allowed in [('order', ('', '0', '1')), ('ammo', ('', '0', '1')),
                              ('history', ('', '0', '1')), ('forceweapons', ('', '0', '1', '2')),
                              ('campaign_menu', ('', '0', '1', '2', '3', '4')),
                              ('ally_menu', ('',) + tuple(map(str, range(14)))),
                              ('axis_menu', ('',) + tuple(map(str, range(14))))]:
            if getattr(self, name) not in allowed:
                raise ValueError('Unreviewed input value: ' + name)


@dataclass(frozen=True)
class HostFacts:
    map: str
    native_world: int
    init_serial: int
    # None = unavailable; empty tuple = an observed empty ordered array.
    ordered_spawners: tuple[str, ...] | None


@dataclass(frozen=True)
class Resolution:
    map: str
    native_world: int
    init_serial: int
    year: int
    campaign: str | None
    ally_nation: str | None
    axis_nation: str | None
    climate: str | None
    winter: bool | None
    desert: bool | None
    last_campaign_spawner: int | None
    wait: tuple[str, ...]
    diagnostics: tuple[str, ...]


def resolve(facts: HostFacts, inputs: Inputs, graph=None):
    graph = graph or json.loads(GRAPH.read_text())
    inputs.validate()
    if (facts.map not in graph['registered_maps'] or type(facts.native_world) is not int or
            not 0 < facts.native_world <= 0xffffffff or type(facts.init_serial) is not int or facts.init_serial <= 0):
        raise ValueError('Unregistered map or missing native world/init binding')
    diagnostics, wait = [], []
    for raw, menu, label in [(inputs.ally, inputs.ally_menu, 'ally'), (inputs.axis, inputs.axis_menu, 'axis')]:
        if menu and (raw or 'none') != FACTIONS[int(menu)]:
            diagnostics.append(label + ' UI selector differs from actual GSC input; raw input retained')
    campaign = climate = winter = desert = last = None
    if facts.ordered_spawners is None:
        wait.append('ordered Host getspawnerarray facts unavailable')
    else:
        if (not isinstance(facts.ordered_spawners, tuple) or len(facts.ordered_spawners) > 4096 or
                any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,127}', value)
                    for value in facts.ordered_spawners)):
            raise ValueError('Malformed ordered Host spawner facts')
        campaign = graph['map_campaign'].get(facts.map, graph['default_campaign'])
        for index, classname in enumerate(facts.ordered_spawners):
            if classname in graph['spawner_campaign']:
                campaign, last = graph['spawner_campaign'][classname], index
        winter = any(value in graph['snow_spawners'] for value in facts.ordered_spawners)
        climate = graph['map_climate'].get(facts.map, 'winter' if winter else 'none')
        desert = climate == 'desert'
        winter = winter or climate == 'winter'
    ally = axis = None
    if inputs.saved:
        wait.append('saved level faction/nation/climate flags require verified native restored-world observation')
    elif campaign:
        defaults = ('german', 'american') if facts.map in ('gfm_omaha', 'sp_eugene') else (
            ('british', 'italian') if facts.map in ('sicily1', 'sicily2') else (campaign, 'german'))
        ally = graph['faction_nation'].get(inputs.ally, defaults[0])
        axis = graph['faction_nation'].get(inputs.axis, defaults[1])
    return Resolution(facts.map, facts.native_world, facts.init_serial,
                      graph['map_year'].get(facts.map, graph['default_year']), campaign,
                      ally, axis, climate, winter, desert, last, tuple(wait), tuple(diagnostics))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(extract(args.extract_package), indent=2, sort_keys=True) + '\n')
