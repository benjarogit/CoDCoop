"""Read-only future roster presentation guards, not native transport acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import uf_equipment_roster as roster
import uf_equipment_preferences as preferences
import uf_equipment_roster_view as view


def fixture():
    catalog=json.loads((ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
    kit={'mode':'manual','family':'american','slots':{'primary':3,'secondary':0,'pistol':0,'grenade':0}}
    world={'variant':'united_fronts','package_id':'fixture-package','map':'noville','campaign':'american','sp_ally':'us_inf'}
    state=roster.create_roster(catalog,0,world,[{'slot_id':i,'kit':deepcopy(kit) if i==0 else {'mode':'automatic'}} for i in range(4)])
    for slot,primary in [(1,6),(2,8),(3,9)]:
        chosen=deepcopy(kit);chosen['slots']['primary']=primary
        state=roster.update_kit(state,catalog,slot,slot,chosen,state['revision'])
    plan=roster.plan(state,catalog)
    state=roster.approve_resources(state,catalog,0,state['revision'],plan['plan_sha256'],plan['required_server_models'],plan['required_media_models'],'fixture-not-native-evidence')
    for slot in range(4):state=roster.mark_ready(state,catalog,slot,state['revision'],plan['plan_sha256'])
    capability={'id':preferences.CAPABILITY,'schema':1,'per_player':True,'catalog_sha256':preferences.catalog_digest(catalog),'roster_snapshot':'uf-equipment-roster-v1'}
    return catalog,state,capability


class RosterView(unittest.TestCase):
    def setUp(self):
        self.catalog,self.state,self.capability=fixture()
        self.snapshot=roster.public_snapshot(self.state,self.catalog)

    def test_four_owner_confirmed_roles_are_read_only_and_never_runtime_permission(self):
        result=view.validate_snapshot(self.snapshot,self.catalog,self.capability)
        self.assertEqual([m['slot_id'] for m in result['members']],[0,1,2,3])
        self.assertTrue(result['contract_ready']);self.assertFalse(result['runtime_ready'])
        result['members'][0]['ready']=False
        self.assertTrue(self.snapshot['members'][0]['ready'])
        false_permission=deepcopy(self.snapshot);false_permission['runtime_ready']=True
        with self.assertRaises(ValueError):view.validate_snapshot(false_permission,self.catalog,self.capability)

    def test_protocol_or_manifest_metadata_is_not_roster_capability(self):
        for cap in (None,{'protocol':7},{'protocol':8},{'id':preferences.CAPABILITY},
                    {**self.capability,'per_player':1},{**self.capability,'schema':True},
                    {**self.capability,'roster_snapshot':'unknown'},{**self.capability,'catalog_sha256':'0'*64}):
            with self.subTest(capability=cap),self.assertRaises(ValueError):view.validate_snapshot(self.snapshot,self.catalog,cap)

    def test_world_changes_invalidate_all_displayed_readiness_and_stale_plan_is_rejected(self):
        state=roster.update_world(self.state,self.catalog,0,{**self.state['world'],'map':'tropez'},self.state['revision'])
        changed=roster.public_snapshot(state,self.catalog)
        result=view.validate_snapshot(changed,self.catalog,self.capability,self.snapshot)
        self.assertFalse(any(m['ready'] for m in result['members']))
        with self.assertRaises(ValueError):view.validate_snapshot(self.snapshot,self.catalog,self.capability,result)
        tampered=deepcopy(result);tampered['world']['map']='noville'
        with self.assertRaises(ValueError):view.validate_snapshot(tampered,self.catalog,self.capability,result)
        reused=deepcopy(self.snapshot);reused['revision']+=1
        with self.assertRaises(ValueError):view.validate_snapshot(reused,self.catalog,self.capability,self.snapshot)

    def test_summary_identity_and_original_slot_guards_reject_malformed_projection(self):
        cases=[]
        duplicate=deepcopy(self.snapshot);duplicate['members'][1]['slot_id']=0;cases.append(duplicate)
        hidden=deepcopy(self.snapshot);hidden['members'][1]['kit']['family']='polish';cases.append(hidden)
        summary=deepcopy(self.snapshot);summary['waiting_slots']=[1];cases.append(summary)
        media=deepcopy(self.snapshot);media['required_media_models'].append('xmodel/unreviewed');cases.append(media)
        bool_slot=deepcopy(self.snapshot);bool_slot['members'][0]['slot_id']=False;cases.append(bool_slot)
        for snapshot in cases:
            with self.subTest(snapshot=snapshot),self.assertRaises(ValueError):view.validate_snapshot(snapshot,self.catalog,self.capability)

    def test_automatic_participants_remain_unresolved_not_inferred_ready(self):
        kit={'mode':'manual','family':'american','slots':{'primary':3,'secondary':0,'pistol':0,'grenade':0}}
        state=roster.create_roster(self.catalog,0,self.state['world'],[{'slot_id':0,'kit':kit},{'slot_id':2,'kit':{'mode':'automatic'}}])
        snapshot=roster.public_snapshot(state,self.catalog)
        checked=view.validate_snapshot(snapshot,self.catalog,self.capability)
        self.assertEqual(checked['unresolved_automatic_slots'],[2]);self.assertFalse(checked['contract_ready'])

    def test_owner_can_withdraw_confirmation_without_changing_the_plan(self):
        state=roster.mark_ready(self.state,self.catalog,2,self.state['revision'],self.snapshot['plan_sha256'],ready=False)
        changed=roster.public_snapshot(state,self.catalog)
        checked=view.validate_snapshot(changed,self.catalog,self.capability,self.snapshot)
        self.assertEqual(checked['revision'],self.snapshot['revision'])
        self.assertEqual(checked['waiting_slots'],[2])
        self.assertFalse(checked['members'][2]['ready'])


if __name__=='__main__':unittest.main()
