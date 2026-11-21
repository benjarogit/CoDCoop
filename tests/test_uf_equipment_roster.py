import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import uf_equipment_roster as roster


class EquipmentRosterTests(unittest.TestCase):
    def state_for(self, members):
        initial = [{'slot_id': m['slot_id'], 'kit': m['kit'] if m['slot_id'] == 0 else {'mode': 'automatic'}} for m in members]
        state = roster.create_roster(self.catalog, 0, self.world, initial)
        for member in sorted(members, key=lambda m: m['slot_id']):
            if member['slot_id'] != 0:
                state = roster.update_kit(state, self.catalog, member['slot_id'], member['slot_id'], member['kit'], state['revision'])
        return state

    def setUp(self):
        self.catalog = json.loads((Path(__file__).resolve().parents[1] / 'campaign_patches/uf_equipment_catalog.json').read_text())
        self.world = {'variant': 'united_fronts', 'package_id': 'pinned-uf', 'map': 'noville', 'campaign': 'american', 'sp_ally': 'us_inf', 'sp_year': '1944'}
        self.kit = {'mode': 'manual', 'family': 'american', 'slots': {'primary': 9, 'secondary': 6, 'pistol': 22, 'grenade': 34}}
        self.members = [{'slot_id': 0, 'kit': self.kit}, {'slot_id': 1, 'kit': {'mode': 'manual', 'family': 'american', 'slots': {'primary': 5, 'secondary': 1, 'pistol': 21, 'grenade': 33}}}]
        self.state = self.state_for(self.members)

    def approved(self):
        plan = roster.plan(self.state, self.catalog)
        return roster.approve_resources(self.state, self.catalog, 0, 2, plan['plan_sha256'], plan['required_server_models'], plan['required_media_models'], 'test-fixture-not-native-evidence')

    def test_deterministic_identity_and_independent_copy(self):
        plan = roster.plan(self.state, self.catalog)
        reordered = self.state_for(list(reversed(self.members)))
        self.assertEqual(plan, roster.plan(reordered, self.catalog))
        self.members[0]['kit']['slots']['primary'] = 0
        self.assertEqual(self.state['members'][0]['kit']['slots']['primary'], 9)
        self.assertNotEqual(plan['members'][0]['kit'], plan['members'][1]['kit'])

    def test_duplicate_bool_out_of_range_or_absent_host_slots_rejected(self):
        for slots in ([0, 0], [0, True], [0, 4], [1], []):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                roster.create_roster(self.catalog, 0, self.world, [{'slot_id': slot, 'kit': self.kit} for slot in slots])

    def test_host_world_and_other_kit_authority(self):
        with self.assertRaisesRegex(ValueError, 'host-owned'):
            roster.update_world(self.state, self.catalog, 1, dict(self.world, sp_year='1945'), 2)
        for actor, target in ((1, 0), (0, 1)):
            with self.assertRaisesRegex(ValueError, 'own submitted kit'):
                roster.update_kit(self.state, self.catalog, actor, target, self.kit, 2)
        updated = roster.update_kit(self.state, self.catalog, 1, 1, self.kit, 2)
        self.assertEqual(updated['revision'], 3)
        self.assertEqual(updated['world'], self.world)

    def test_any_kit_world_or_membership_change_invalidates_all_ready_and_approval(self):
        state = self.approved()
        plan = roster.plan(state, self.catalog)
        for slot in (0, 1): state = roster.mark_ready(state, self.catalog, slot, 2, plan['plan_sha256'])
        self.assertTrue(roster.ready_summary(state, self.catalog)['contract_ready'])
        changes = [
            roster.update_kit(state, self.catalog, 1, 1, self.kit, 2),
            roster.update_world(state, self.catalog, 0, dict(self.world, map='foy'), 2),
            roster.update_members(state, self.catalog, 0, self.members[:1], 2),
        ]
        for changed in changes:
            self.assertEqual(changed['revision'], 3)
            self.assertEqual(changed['ready_slots'], [])
            self.assertIsNone(changed['resource_approval'])
            with self.assertRaisesRegex(ValueError, 'Stale'):
                roster.mark_ready(changed, self.catalog, 1, 2, plan['plan_sha256'])

    def test_catalog_and_approved_union_must_match_exact_current_plan(self):
        altered = json.loads(json.dumps(self.catalog)); altered['status'] = 'different catalog'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): roster.plan(self.state, altered)
        plan = roster.plan(self.state, self.catalog)
        for media in (plan['required_media_models'][:-1], plan['required_media_models'] + ['xmodel/unrequested']):
            with self.assertRaisesRegex(ValueError, 'exactly match'):
                roster.approve_resources(self.state, self.catalog, 0, 2, plan['plan_sha256'], plan['required_server_models'], media, 'test')
        with self.assertRaisesRegex(ValueError, 'host-owned'):
            roster.approve_resources(self.state, self.catalog, 1, 2, plan['plan_sha256'], plan['required_server_models'], plan['required_media_models'], 'test')

    def test_automatic_is_unresolved_not_an_invented_authored_loadout(self):
        state = roster.update_kit(self.state, self.catalog, 1, 1, {'mode': 'automatic'}, 2)
        plan = roster.plan(state, self.catalog)
        self.assertEqual(plan['unresolved_automatic_slots'], [1])
        self.assertEqual(plan['members'][1]['kit'], {'mode': 'automatic'})
        with self.assertRaisesRegex(ValueError, 'not been resolved'):
            roster.approve_resources(state, self.catalog, 0, 3, plan['plan_sha256'], plan['required_server_models'], plan['required_media_models'], 'test')

    def test_ready_needs_approval_and_never_claims_runtime_application(self):
        plan = roster.plan(self.state, self.catalog)
        with self.assertRaisesRegex(ValueError, 'approved roster'):
            roster.mark_ready(self.state, self.catalog, 0, 2, plan['plan_sha256'])
        state = self.approved()
        for slot in (0, 1): state = roster.mark_ready(state, self.catalog, slot, 2, plan['plan_sha256'])
        summary = roster.ready_summary(state, self.catalog)
        self.assertTrue(summary['contract_ready'])
        self.assertFalse(summary['runtime_ready'])
        with self.assertRaisesRegex(ValueError, 'not in party'):
            roster.mark_ready(state, self.catalog, 3, 2, plan['plan_sha256'])

    def test_four_actual_roles_keep_union_and_projection_ids_without_runtime_capability(self):
        choices = [(9, 6, 22, 34), (5, 1, 21, 33), (10, 8, 21, 32), (3, 7, 21, 31)]
        members = [{'slot_id': slot, 'kit': {'mode': 'manual', 'family': 'american',
                    'slots': dict(zip(('primary', 'secondary', 'pistol', 'grenade'), choice))}}
                   for slot, choice in enumerate(choices)]
        state = self.state_for(members)
        snapshot = roster.public_snapshot(state, self.catalog)
        self.assertEqual([m['slot_id'] for m in snapshot['members']], [0, 1, 2, 3])
        self.assertEqual(len(snapshot['required_server_models']), 23)
        self.assertEqual(len(snapshot['required_media_models']), 39)
        self.assertEqual(snapshot['status'], 'WAITING_RESOURCE_APPROVAL')
        self.assertFalse(snapshot['runtime_ready'])
        snapshot['members'][0]['kit']['slots']['primary'] = 0
        self.assertEqual(state['members'][0]['kit']['slots']['primary'], 9)

    def test_host_cannot_bypass_personal_ownership_through_initial_or_membership_payload(self):
        with self.assertRaisesRegex(ValueError, 'New peers start automatic'):
            roster.create_roster(self.catalog, 0, self.world, self.members)
        modified = json.loads(json.dumps(self.members))
        modified[1]['kit'] = self.kit
        with self.assertRaisesRegex(ValueError, 'cannot edit submitted kits'):
            roster.update_members(self.state, self.catalog, 0, modified, 2)
        with self.assertRaisesRegex(ValueError, 'New peers start automatic'):
            roster.update_members(self.state, self.catalog, 0, self.members + [{'slot_id': 2, 'kit': self.kit}], 2)
        state = roster.update_members(self.state, self.catalog, 0, self.members + [{'slot_id': 2, 'kit': {'mode': 'automatic'}}], 2)
        self.assertEqual(roster.plan(state, self.catalog)['unresolved_automatic_slots'], [2])


if __name__ == '__main__': unittest.main()
