"""Strict presentation projection for a future authenticated UF roster feed.

Validation here is not authentication, resource approval or launch permission.
The future native/session controller must verify those before calling the GUI.
No session stdout event is connected to this adapter.
"""
from copy import deepcopy
import hashlib
import json
import re

from uf_equipment_preferences import CAPABILITY, catalog_digest, validate_preferences

WORLD_FIELDS = {'variant', 'package_id', 'map', 'campaign', 'sp_ally', 'sp_axis',
                'sp_ally_nation', 'sp_year', 'sp_history', 'sp_order', 'difficulty'}
FIELDS = {'kind', 'schema', 'catalog_sha256', 'revision', 'plan_sha256', 'host_slot',
          'world', 'members', 'required_server_models', 'required_media_models',
          'resource_plan_approved', 'waiting_slots', 'unresolved_automatic_slots',
          'contract_ready', 'runtime_ready', 'runtime_blocker', 'status'}
PLAN_FIELDS = ('catalog_sha256', 'host_slot', 'world', 'required_server_models', 'required_media_models')


def plan_identity(snapshot):
    """Local consistency key; does not replace the authoritative plan digest."""
    data = {name: snapshot[name] for name in PLAN_FIELDS}
    data['members'] = [{'slot_id': member['slot_id'], 'kit': member['kit']} for member in snapshot['members']]
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def validate_snapshot(snapshot, catalog, capability, previous=None):
    expected = catalog_digest(catalog)
    if (not isinstance(capability, dict) or capability.get('id') != CAPABILITY
            or type(capability.get('schema')) is not int or capability['schema'] != 1
            or capability.get('per_player') is not True
            or capability.get('catalog_sha256') != expected
            or capability.get('roster_snapshot') != 'uf-equipment-roster-v1'):
        raise ValueError('Explicit native roster-display capability is unavailable')
    if not isinstance(snapshot, dict) or set(snapshot) != FIELDS:
        raise ValueError('Unsupported roster projection')
    if (snapshot['kind'] != 'uf_equipment_roster' or type(snapshot['schema']) is not int or snapshot['schema'] != 1
            or snapshot['catalog_sha256'] != expected or type(snapshot['revision']) is not int or snapshot['revision'] < 1
            or not isinstance(snapshot['plan_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', snapshot['plan_sha256'])):
        raise ValueError('Roster/catalog/revision identity mismatch')
    world = snapshot['world']
    if (not isinstance(world, dict) or not {'variant', 'package_id', 'map'} <= world.keys()
            or not world.keys() <= WORLD_FIELDS or world['variant'] != 'united_fronts'
            or any(not isinstance(value, str) or not value or len(value) > 160 or any(c in value for c in '\r\n;') for value in world.values())):
        raise ValueError('Invalid authoritative world projection')
    members = snapshot['members']
    if not isinstance(members, list) or not 1 <= len(members) <= 4:
        raise ValueError('Roster must contain one to four participants')
    slots = []
    for member in members:
        if not isinstance(member, dict) or set(member) != {'slot_id', 'kit', 'ready'}:
            raise ValueError('Invalid participant projection')
        slot = member['slot_id']
        if type(slot) is not int or slot not in range(4) or slot in slots or type(member['ready']) is not bool:
            raise ValueError('Invalid participant identity/readiness')
        slots.append(slot)
        kit = member['kit']
        if kit != {'mode': 'automatic'}:
            if not isinstance(kit, dict) or set(kit) != {'mode', 'family', 'slots'} or kit.get('mode') != 'manual':
                raise ValueError('Invalid individual kit projection')
            validate_preferences({'schema': 1, 'mode': 'manual', 'manual': {'family': kit['family'], 'slots': kit['slots']}}, catalog)
    if slots != sorted(slots) or type(snapshot['host_slot']) is not int or snapshot['host_slot'] not in slots:
        raise ValueError('Invalid host or participant order')
    allowed_models = {entry['member'].lower() for entry in catalog['air_models'].values()}
    for weapon in catalog['weapons'].values():
        allowed_models.update(entry['member'].lower() for entry in weapon.get('models', {}).values())
    for field in ('required_server_models', 'required_media_models'):
        models = snapshot[field]
        if (not isinstance(models, list) or any(not isinstance(name, str) for name in models)
                or models != sorted(set(models)) or not set(models) <= allowed_models):
            raise ValueError('Invalid roster model union')
    if any(type(snapshot[field]) is not bool for field in ('resource_plan_approved', 'contract_ready', 'runtime_ready')):
        raise ValueError('Readiness flags must be boolean')
    waiting = [member['slot_id'] for member in members if not member['ready']]
    unresolved = [member['slot_id'] for member in members if member['kit']['mode'] == 'automatic']
    for field, actual in (('waiting_slots', waiting), ('unresolved_automatic_slots', unresolved)):
        reported = snapshot[field]
        if not isinstance(reported, list) or any(type(slot) is not int for slot in reported) or reported != actual:
            raise ValueError('Roster readiness summary mismatch')
    approved = snapshot['resource_plan_approved']
    if (unresolved and approved) or (not approved and any(member['ready'] for member in members)):
        raise ValueError('Participant readiness lacks a resolved resource plan')
    ready = approved and not waiting and not unresolved
    status = ('UNRESOLVED_AUTOMATIC' if unresolved else 'WAITING_RESOURCE_APPROVAL' if not approved
              else 'WAITING_PARTICIPANTS' if waiting else 'CONTRACT_READY_RUNTIME_UNAVAILABLE')
    if snapshot['contract_ready'] is not ready or snapshot['status'] != status:
        raise ValueError('Roster status mismatch')
    if snapshot['runtime_ready'] is not False or not isinstance(snapshot['runtime_blocker'], str) or not 1 <= len(snapshot['runtime_blocker']) <= 512:
        raise ValueError('This projection cannot grant native equipment application')
    if previous is not None:
        if snapshot['revision'] < previous['revision']:
            raise ValueError('Stale roster revision')
        if snapshot['revision'] > previous['revision'] and snapshot['plan_sha256'] == previous['plan_sha256']:
            raise ValueError('New roster revision reused an old plan digest')
        if snapshot['revision'] == previous['revision'] and (snapshot['plan_sha256'] != previous['plan_sha256'] or plan_identity(snapshot) != plan_identity(previous)):
            raise ValueError('Roster plan changed without a new revision')
    return deepcopy(snapshot)
