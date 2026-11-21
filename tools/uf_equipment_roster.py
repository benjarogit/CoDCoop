"""Pure, deterministic future UF roster contract; no transport or kit application.

Slot IDs are the engine's 0..3; a party contains one to four unique IDs. The
caller must obtain actor_slot from its authenticated transport, never a payload.
Neither a syntactically valid approval nor ready_summary authorizes this build
to launch: native resource registration and per-player application are absent.
"""
from copy import deepcopy
import hashlib
import json

from uf_equipment_catalog import roster_resources
from uf_equipment_preferences import catalog_digest, validate_preferences

WORLD_FIELDS = {'variant', 'package_id', 'map', 'campaign', 'sp_ally', 'sp_axis',
                'sp_ally_nation', 'sp_year', 'sp_history', 'sp_order', 'difficulty'}


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def validate_world(world):
    if not isinstance(world, dict) or not {'variant', 'package_id', 'map'} <= world.keys() or not world.keys() <= WORLD_FIELDS:
        raise ValueError('Host world requires registered variant, package identity and map')
    if world['variant'] != 'united_fronts': raise ValueError('UF roster requires United Fronts world')
    for key, value in world.items():
        if not isinstance(value, str) or not value or len(value) > 160 or any(c in value for c in '\r\n;'):
            raise ValueError('Invalid host world value: ' + key)
    return dict(sorted(world.items()))


def validate_kit(kit, catalog):
    if not isinstance(kit, dict): raise ValueError('Invalid individual kit')
    if kit == {'mode': 'automatic'}: return {'mode': 'automatic'}
    if set(kit) != {'mode', 'family', 'slots'} or kit.get('mode') != 'manual':
        raise ValueError('Manual kit needs family and four original slots; automatic kit carries none')
    preference = validate_preferences({'schema': 1, 'mode': 'manual', 'manual': {'family': kit['family'], 'slots': kit['slots']}}, catalog)
    return {'mode': 'manual', **preference['manual']}


def validate_members(members, host_slot, catalog):
    if type(host_slot) is not int or host_slot not in range(4): raise ValueError('Invalid host slot')
    if not isinstance(members, list) or not 1 <= len(members) <= 4: raise ValueError('Party must contain one to four participants')
    seen, result = set(), []
    for member in members:
        if not isinstance(member, dict) or set(member) != {'slot_id', 'kit'}: raise ValueError('Participant needs slot ID and individual kit')
        slot = member['slot_id']
        if type(slot) is not int or slot not in range(4) or slot in seen: raise ValueError('Participant slot IDs must be unique integers 0..3')
        seen.add(slot)
        result.append({'slot_id': slot, 'kit': validate_kit(member['kit'], catalog)})
    if host_slot not in seen: raise ValueError('Party must include host')
    return sorted(result, key=lambda member: member['slot_id'])


def create_roster(catalog, host_slot, world, members):
    members = validate_members(members, host_slot, catalog)
    if any(member['slot_id'] != host_slot and member['kit'] != {'mode': 'automatic'} for member in members):
        raise ValueError('New peers start automatic; each peer must submit their own manual kit')
    return {'schema': 1, 'catalog_sha256': catalog_digest(catalog), 'host_slot': host_slot,
            'world': validate_world(world), 'members': members,
            'revision': 1, 'ready_slots': [], 'resource_approval': None}


def validate_state(state, catalog, expected_revision=None):
    if not isinstance(state, dict) or type(state.get('schema')) is not int or state['schema'] != 1 or state.get('catalog_sha256') != catalog_digest(catalog):
        raise ValueError('Roster/catalog identity mismatch')
    if type(state.get('revision')) is not int or state['revision'] < 1: raise ValueError('Invalid roster revision')
    if expected_revision is not None and (type(expected_revision) is not int or expected_revision != state['revision']):
        raise ValueError('Stale roster revision')
    validate_world(state['world'])
    validate_members(state['members'], state['host_slot'], catalog)
    ready = state.get('ready_slots')
    slots = {m['slot_id'] for m in state['members']}
    if not isinstance(ready, list) or any(type(slot) is not int or slot not in slots for slot in ready) or len(set(ready)) != len(ready):
        raise ValueError('Invalid ready participant IDs')


def plan(state, catalog):
    validate_state(state, catalog)
    manual = [member for member in state['members'] if member['kit']['mode'] == 'manual']
    unresolved = [member['slot_id'] for member in state['members'] if member['kit']['mode'] == 'automatic']
    resources = roster_resources(catalog, [{'family': m['kit']['family'], 'slots': m['kit']['slots']} for m in manual], state['world']) if manual else {'weapons': [], 'required_server_models': [], 'required_media_models': [], 'support': []}
    payload = {key: deepcopy(state[key]) for key in ('schema', 'catalog_sha256', 'host_slot', 'world', 'members', 'revision')}
    payload.update(unresolved_automatic_slots=unresolved,
                   required_weapons=resources['weapons'], required_server_models=resources['required_server_models'],
                   required_media_models=resources['required_media_models'], support=resources['support'])
    payload['plan_sha256'] = identity(payload)
    return payload


def changed(state, **fields):
    result = deepcopy(state)
    if all(result[key] == value for key, value in fields.items()): return result
    result.update(deepcopy(fields))
    result.update(revision=state['revision'] + 1, ready_slots=[], resource_approval=None)
    return result


def update_kit(state, catalog, actor_slot, target_slot, kit, expected_revision):
    validate_state(state, catalog, expected_revision)
    if type(actor_slot) is not int or actor_slot not in [m['slot_id'] for m in state['members']]: raise ValueError('Actor is not in party')
    if type(target_slot) is not int or target_slot not in range(4): raise ValueError('Invalid target participant ID')
    if actor_slot != target_slot: raise ValueError('Each participant owns their own submitted kit; host cannot select for peers')
    members = deepcopy(state['members'])
    target = next((m for m in members if m['slot_id'] == target_slot), None)
    if target is None: raise ValueError('Unknown target participant')
    target['kit'] = validate_kit(kit, catalog)
    return changed(state, members=members)


def update_world(state, catalog, actor_slot, world, expected_revision):
    validate_state(state, catalog, expected_revision)
    if type(actor_slot) is not int or actor_slot != state['host_slot']: raise ValueError('World settings are host-owned')
    return changed(state, world=validate_world(world))


def update_members(state, catalog, actor_slot, members, expected_revision):
    validate_state(state, catalog, expected_revision)
    if type(actor_slot) is not int or actor_slot != state['host_slot']: raise ValueError('Party membership is host-owned')
    members = validate_members(members, state['host_slot'], catalog)
    previous = {member['slot_id']: member['kit'] for member in state['members']}
    for member in members:
        if member['slot_id'] in previous:
            if member['kit'] != previous[member['slot_id']]: raise ValueError('Membership changes cannot edit submitted kits')
        elif member['kit'] != {'mode': 'automatic'}:
            raise ValueError('New peers start automatic; each peer must submit their own manual kit')
    return changed(state, members=members)


def approve_resources(state, catalog, actor_slot, expected_revision, plan_sha256,
                      approved_server_models, approved_media_models, evidence_id):
    """Record host resource verifier input; this pure module cannot verify it ran."""
    validate_state(state, catalog, expected_revision)
    if type(actor_slot) is not int or actor_slot != state['host_slot']: raise ValueError('Resource approval is host-owned')
    current = plan(state, catalog)
    if current['unresolved_automatic_slots']: raise ValueError('Authored automatic kits have not been resolved; do not guess their resources')
    if plan_sha256 != current['plan_sha256']: raise ValueError('Stale resource plan identity')
    for actual, expected in ((approved_server_models, current['required_server_models']), (approved_media_models, current['required_media_models'])):
        if not isinstance(actual, list) or any(not isinstance(value, str) for value in actual) or sorted(set(actual)) != expected:
            raise ValueError('Approved model union must exactly match current roster plan')
    if not isinstance(evidence_id, str) or not evidence_id.strip() or len(evidence_id) > 256: raise ValueError('Resource approval needs verifier evidence identity')
    result = deepcopy(state)
    approval = {'catalog_sha256': state['catalog_sha256'], 'plan_sha256': plan_sha256,
                'revision': state['revision'], 'server_models': current['required_server_models'],
                'media_models': current['required_media_models'], 'evidence_id': evidence_id}
    if result['resource_approval'] != approval: result['ready_slots'] = []
    result['resource_approval'] = approval
    return result


def mark_ready(state, catalog, actor_slot, expected_revision, plan_sha256, ready=True):
    validate_state(state, catalog, expected_revision)
    if type(actor_slot) is not int or actor_slot not in [m['slot_id'] for m in state['members']]: raise ValueError('Ready actor is not in party')
    if type(ready) is not bool: raise ValueError('Ready must be boolean')
    current = plan(state, catalog)
    approval = state.get('resource_approval')
    if plan_sha256 != current['plan_sha256'] or not approval or approval['plan_sha256'] != plan_sha256:
        raise ValueError('Ready requires current approved roster plan')
    result = deepcopy(state)
    slots = set(result['ready_slots'])
    if ready: slots.add(actor_slot)
    else: slots.discard(actor_slot)
    result['ready_slots'] = sorted(slots)
    return result


def ready_summary(state, catalog):
    current = plan(state, catalog)
    approval = state.get('resource_approval')
    approved = bool(approval and approval.get('plan_sha256') == current['plan_sha256'])
    waiting = sorted({m['slot_id'] for m in state['members']} - set(state['ready_slots']))
    return {'plan_sha256': current['plan_sha256'], 'revision': state['revision'],
            'waiting_slots': waiting, 'resource_plan_approved': approved,
            'unresolved_automatic_slots': current['unresolved_automatic_slots'],
            'contract_ready': approved and not waiting and not current['unresolved_automatic_slots'],
            'runtime_ready': False, 'runtime_blocker': 'Native individual-kit transport/application and model gate are not implemented by this contract'}


def public_snapshot(state, catalog):
    """Read-only projection for a future explicit native roster capability."""
    current = plan(state, catalog)
    summary = ready_summary(state, catalog)
    if current['unresolved_automatic_slots']: status = 'UNRESOLVED_AUTOMATIC'
    elif not summary['resource_plan_approved']: status = 'WAITING_RESOURCE_APPROVAL'
    elif summary['waiting_slots']: status = 'WAITING_PARTICIPANTS'
    else: status = 'CONTRACT_READY_RUNTIME_UNAVAILABLE'
    return {'kind': 'uf_equipment_roster', 'schema': 1,
            'catalog_sha256': state['catalog_sha256'], 'revision': state['revision'],
            'plan_sha256': current['plan_sha256'], 'host_slot': state['host_slot'],
            'world': deepcopy(state['world']),
            'members': [{**deepcopy(member), 'ready': member['slot_id'] in state['ready_slots']} for member in state['members']],
            'required_server_models': current['required_server_models'],
            'required_media_models': current['required_media_models'],
            'status': status, **summary}
