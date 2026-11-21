#!/usr/bin/env python3
"""QA host-plan-only distinct inventory/fire/checkpoint proof; no lobby transport."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import struct
import time

import qa_coop
from build_campaign_patch import build
from uf_equipment_preferences import catalog_digest
from uf_equipment_catalog import roster_resources


def kit_fixture(players):
    if players == 2:
        return ([dict(primary=3, secondary=6, pistol=21, grenade=31), dict(primary=1, secondary=7, pistol=22, grenade=33)],
                [dict(primary='m1garand', primaryb='thompson', pistol='colt', grenade='fraggrenade'),
                 dict(primary='carbinem1s', primaryb='greaser', pistol='binoculars', grenade='land_mine')], ['primary', 'primary'])
    if players == 4:
        return ([dict(primary=9, secondary=6, pistol=22, grenade=34), dict(primary=5, secondary=1, pistol=21, grenade=33),
                 dict(primary=10, secondary=8, pistol=21, grenade=32), dict(primary=3, secondary=7, pistol=21, grenade=31)],
                [dict(primary='mg30cal', primaryb='thompson', pistol='binoculars', grenade='smokegrenade'),
                 dict(primary='springfield', primaryb='carbinem1s', pistol='colt', grenade='land_mine'),
                 dict(primary='bazooka', primaryb='bar', pistol='colt', grenade='satchelcharge'),
                 dict(primary='m1garand', primaryb='greaser', pistol='colt', grenade='fraggrenade')],
                ['primaryb', 'primary', 'primaryb', 'primary'])
    raise ValueError('Only actual two/four-player kit fixtures are supported')


def selection_ack_matches(values, slot):
    prefix = 'coop_select_%d_' % slot
    if values.get(prefix+'status') != 'APPLIED' or not values.get(prefix+'seq', '').isdigit() or int(values[prefix+'seq']) <= 0:
        return False
    return all(values.get(prefix+'ack_'+field) == values.get(prefix+field) and values.get(prefix+field) is not None
               for field in ('seq', 'ticket', 'world', 'session_a', 'session_b', 'session_c'))


def cgame_selection_matches(host, local, slot):
    cg = local.get('cgame', {})
    name = host.get('selected_weapon_name', '').lower()
    return bool(host.get('weapon') and name and name != 'none' and
                cg.get('snapshot_clientnum') == slot and cg.get('snapshot_server_time', 0) > 0 and
                all(cg.get(field, '').lower() == name for field in ('desired_name', 'predicted_name', 'snapshot_name')))


def preservation_publication_matches(values, slot, state):
    if slot not in range(4) or state not in ('FRESH','PRESERVED'):
        return False
    fields=[values.get('coop_spawn_session_'+part,'') for part in ('a','b','c')]
    ticket=values.get('coop_spawn_ticket_%d' % slot,'')
    world=values.get('coop_spawn_world','')
    if any(not re.fullmatch(r'0|[1-9][0-9]*', value) for value in fields+[ticket,world]):
        return False
    if int(fields[2])>3 or not any(map(int,fields)) or int(ticket)<=0 or int(world)<=0:
        return False
    identity='|'.join(fields+[str(slot),ticket,world])
    return (values.get('coop_inventory_%d_state' % slot)==state and
            values.get('coop_inventory_%d_identity' % slot)==identity)


def main():
    executed_source = Path(__file__).read_bytes()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--map', default='brecourt')
    parser.add_argument('--players', type=int, choices=(2,4), default=2)
    parser.add_argument('--port', type=int, default=29946)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--peer-item-bootstrap', action='store_true', help='QA-only exact host plan resources-only native item registration on peers before CG_Init; no peer kit application')
    parser.add_argument('--switch-before-save', action='store_true', help='actual remote user changes to another owned firearm; preserve that user choice through native checkpoint')
    parser.add_argument('--crossmap-before-load', choices=('pathfinder',), help='QA-only actual A->fresh Pathfinder B->native Save A retention regression')
    parser.add_argument('--crossmap-model-ledger', type=Path, help='immutable native-approved B model ledger; explicit offline QA media bootstrap')
    parser.add_argument('--selection-negatives', action='store_true', help='owned two-player relay replays authentic selections after user choice; reject stale contexts and invalid host requests')
    args = parser.parse_args()
    if args.selection_negatives and (args.players != 2 or not args.switch_before_save):
        parser.error('--selection-negatives requires --players 2 --switch-before-save')
    if args.crossmap_before_load and (args.players != 2 or args.crossmap_before_load == args.map or args.crossmap_model_ledger is None):
        parser.error('--crossmap-before-load requires two players, a different A map and explicit native B model ledger')
    output = args.run.resolve()
    base = ['--source', str(args.source.resolve()), '--run', str(output), '--runtime-dir', str(args.runtime_dir.resolve()),
            '--variant', 'united_fronts', '--map', args.map, '--players', str(args.players), '--timeout', str(args.timeout), '--port', str(args.port), '--checkpoint-reloads', '1']
    if qa_coop.main(base + ['--prepare-only']): return 1
    names = ['host'] + ['join%d' % index for index in range(1,args.players)]
    for name in names:
        game = output/name
        build(game/'UnitedFronts/ZUnitedFronts_1.1_beta.pk3', game/'UnitedFronts/zzzz_coop_campaign.pk3', 'united_fronts', world_policy='selected', qa_kits=True)
    catalog = json.loads((qa_coop.ROOT/'campaign_patches/uf_equipment_catalog.json').read_text())
    kits, expected, fire_slots = kit_fixture(args.players)
    epoch = 'qa-kit-' + str(time.time_ns())
    host_cvars = {'coop_qa_kit_enable': '1', 'coop_qa_kit_authority': 'host', 'coop_qa_kit_commit': '1',
                  'coop_qa_kit_catalog': catalog_digest(catalog), 'coop_qa_kit_map': args.map, 'coop_qa_kit_epoch': epoch}
    for slot, kit in enumerate(kits):
        prefix = 'coop_qa_kit_%d_' % slot
        host_cvars.update({prefix+'mode': 'manual', prefix+'family': 'american'})
        host_cvars.update({prefix+key: str(value) for key, value in kit.items()})
    report = {'coverage': __doc__, 'host_plan_cvars': host_cvars, 'expected_native_inventory': expected,
              'hunk_megabytes': 512, 'status': 'NOT_RUN', 'observations': []}
    report['players'] = args.players
    report['fire_slots'] = fire_slots
    report['fire_slots_initial'] = list(fire_slots)
    report['requested_user_choice_before_save'] = args.switch_before_save
    report['peer_item_bootstrap'] = args.peer_item_bootstrap
    report['wrapper_sha256'] = hashlib.sha256(executed_source).hexdigest()
    report['native_inputs'] = {}
    for name in names:
        exe = (output/name/'CoDUOSP.exe').read_bytes()
        exe_hash = hashlib.sha256(exe).hexdigest()
        if exe_hash not in {'c17e57c060f08ef65d7cddea738cced61ab7ccb6d98df95fe185b1ab8aa7e325','0a0c52e5aa3e15f4b7039bb22593b8b58f594db5061b4fd4e25a2b4ca3a10018'}:
            raise ValueError('Unreviewed UO QA executable: '+name)
        pe = struct.unpack_from('<I',exe,0x3c)[0]
        large_address_aware = bool(struct.unpack_from('<H',exe,pe+22)[0]&0x20)
        if not large_address_aware and not (output/name/'dontaskagain.LAA').exists():
            raise ValueError('Original raw QA executable needs an explicitly established YAP notification preference; use a reviewed prepared LAA installation or prepare the owned QA copy')
        report['native_inputs'][name]={'exe_sha256':exe_hash,'large_address_aware':large_address_aware,
            'yap_sha256':hashlib.sha256((output/name/'plugins/yap/DDRAW.dll').read_bytes()).hexdigest()}
    report['fire_scope'] = 'Original MG/bazooka inventory is verified; their secondary weapons are fired. This is not an MG deployment or launcher firing proof.' if args.players == 4 else 'Both distinct primary weapons fired through actual input'
    resources = roster_resources(catalog, [{'family': 'american', 'slots': kit} for kit in kits], {'sp_ally': 'us_inf', 'campaign': 'american', 'map': args.map})
    report['bootstrap'] = {'kind': 'QA-only offline exact approved roster resource union on both peers; no transport', 'resources': resources}
    preload_models = set(resources['required_media_models'])
    if args.crossmap_before_load:
        ledger = args.crossmap_model_ledger.read_bytes()
        ledger_names = ledger.decode('ascii').splitlines()
        if not ledger_names or len(ledger_names)>2048 or any(not re.fullmatch(r'xmodel/[A-Za-z0-9_./-]+', name) for name in ledger_names):
            raise ValueError('Malformed explicit offline B model ledger')
        preload_models.update(ledger_names)
        report['crossmap']={'map_a':args.map,'map_b':args.crossmap_before_load,'offline_ledger':str(args.crossmap_model_ledger.resolve()),'offline_ledger_sha256':hashlib.sha256(ledger).hexdigest(),'scope':'actual native map changes; explicit offline media union only, no production transfer claim'}
    for name in names:
        for target in ('qa-deferred-models.txt', 'qa-render-models.txt'):
            (output/name/target).write_text(''.join(model+'\n' for model in sorted(preload_models)))
        # An old per-map QA ledger must not silently supply missing resources.
        for old in (output/name).glob('qa-model-ledger-*.txt'): old.unlink()
    popen, assess, error_check, send_command = subprocess.Popen, qa_coop.assess_liveness, qa_coop.process_log_errors, qa_coop.command
    helper = output/'qa-kit-native-observer.exe'
    helper.unlink(missing_ok=True)
    observer_source = output/'qa-kit-native-observer.cpp'
    observer_source.write_bytes((qa_coop.ROOT/'campaign_patches/qa_uf_player_state.cpp').read_bytes())
    saved = None
    checkpoint_done = False
    controllers = []
    relay = None
    authentic_initial_selection = None
    crossmap_done = False
    if args.selection_negatives:
        from qa_weapon_selection_relay import OwnedSelectionRelay
        relay = OwnedSelectionRelay(('127.0.0.1',args.port))

    def launch(command, *pargs, **kwargs):
        if isinstance(command, list) and any(str(part).endswith('CoDUOSP.exe') for part in command):
            command = list(command)
            is_host = Path(kwargs['cwd']).name == 'host'
            if not is_host and relay is not None:
                command[command.index('+coopjoin')+1]='127.0.0.1:'+str(relay.port)
            if is_host or args.peer_item_bootstrap:
                index = command.index('+devmap')
                # The original command-line parser has a bounded command list;
                # a single exec avoids truncating devmap behind many +set lines.
                config = Path(kwargs['cwd'])/'UnitedFronts/coop_qa_kits.cfg'
                values = dict(host_cvars)
                if not is_host: values['coop_qa_kit_resources_only'] = '1'
                config.write_text(''.join('set %s "%s"\n' % (key,value) for key,value in values.items()))
                command[index:index] = ['+exec', 'coop_qa_kits.cfg']
            kwargs['env'] = dict(kwargs['env'], CODCOOP_QA_DEFER_MODELS='1', CODCOOP_QA_BORROW_TREES='1', CODCOOP_QA_DOBJ_BARRIER='1', CODCOOP_QA_MT_EPOCH='1')
        return popen(command, *pargs, **kwargs)

    def observe(validate=True):
        if not helper.exists():
            subprocess.run(['i686-w64-mingw32-g++', str(observer_source), '-o', str(helper), '-static', '-O2', '-std=c++17'], check=True)
        states = []
        env = dict(os.environ, WINEPREFIX=str(output/'prefix'), WINEDEBUG='-all')
        for slot in range(args.players):
            result = subprocess.run(['wine', str(helper), str(output/'host').replace('/', '\\'), str(slot)], env=env, capture_output=True, text=True, timeout=15, check=True)
            state = json.loads(result.stdout.strip())
            states.append(state)
        report['observations'].append(states)
        if validate:
            for slot, state in enumerate(states):
                if any(state['inventory'][key] != value for key, value in expected[slot].items()):
                    raise RuntimeError('Distinct kit mismatch at native host slot%d: %s' % (slot, state['inventory']))
        return states

    def observe_local(phase):
        env = dict(os.environ, WINEPREFIX=str(output/'prefix'), WINEDEBUG='-all')
        observations = {}
        for folder, slot in controllers:
            # The frozen local server still has local player0. Its CGame
            # current own HOST snapshot is independently checked against slot.
            result = subprocess.run(['wine',str(helper),str(folder).replace('/', '\\'),'0'], env=env,capture_output=True,text=True,timeout=15,check=True)
            observations[slot] = json.loads(result.stdout.strip())
        report.setdefault('local_cgame_observations', []).append({'phase':phase,'native_host_observation':len(report['observations'])-1,'slots':observations})
        return observations

    def stable_selection(phase, expected_names=None, validate_inventory=True):
        deadline = time.monotonic()+35
        last = None
        while time.monotonic()<deadline:
            found = error_check(output/'host')
            if found: raise RuntimeError('native engine error before selected-weapon acceptance: '+found[0])
            host = observe(validate=validate_inventory)
            local = observe_local(phase)
            last = {'host':[s.get('selected_weapon_name') for s in host], 'local':{slot:v.get('cgame') for slot,v in local.items()}}
            if all(cgame_selection_matches(host[slot],local[slot],slot) and
                   (expected_names is None or host[slot]['selected_weapon_name'].lower()==expected_names[slot].lower()) for slot in range(args.players)):
                return host, local
            time.sleep(.15)
        report['selection_failure_detail'] = last
        raise RuntimeError('Actual host/own CGame selected weapon did not stabilize: '+phase)

    def screenshot(phase):
        found = {}
        for folder, slot in controllers:
            directory = folder/'UnitedFronts/screenshots'
            before = set(directory.glob('*.tga'))
            send_command(folder,'screenshot',joiner=slot!=0)
            deadline = time.monotonic()+8
            while time.monotonic()<deadline:
                new = set(directory.glob('*.tga'))-before
                if new:
                    source = sorted(new)[-1]
                    target = output/('%s-slot%d.tga' % (phase,slot))
                    shutil.copy2(source,target); found[slot]=str(target); break
                time.sleep(.1)
            else: raise RuntimeError('No fresh native screenshot for '+folder.name)
        report.setdefault('screenshots',{})[phase]=found

    def attack_and_check(before, phase):
        for folder, slot in controllers: send_command(folder,'+attack',joiner=slot!=0)
        time.sleep(.4)
        for folder, slot in controllers: send_command(folder,'-attack',joiner=slot!=0)
        time.sleep(.5)
        fired, local = stable_selection(phase,[state['selected_weapon_name'] for state in before])
        if any(fired[i]['slot_ammo'][fire_slots[i]]['clip'] >= before[i]['slot_ammo'][fire_slots[i]]['clip'] for i in range(args.players)):
            raise RuntimeError('Every actual player must consume native chosen-weapon ammunition via attack: '+phase)
        return fired

    def command(folder, text, joiner=False):
        nonlocal saved, crossmap_done
        if Path(folder).resolve() == output/'host' and text.strip()=='loadgame coop_qa_checkpoint' and args.crossmap_before_load and not crossmap_done:
            visit_fresh_map_b()
            crossmap_done = True
        if Path(folder).resolve() == output/'host' and text.strip()=='savegame coop_qa_checkpoint':
            if args.switch_before_save and 'user_choice_before_save' not in report:
                previous = observe()
                choices = {1:'primaryb'} if args.players==2 else {1:'primaryb',2:'pistol',3:'primaryb'}
                for target, slot in controllers:
                    if slot in choices:
                        send_command(target,'weaponslot '+choices[slot],joiner=True)
                        fire_slots[slot]=choices[slot]
                selected = [expected[slot][fire_slots[slot]] for slot in range(args.players)]
                chosen, local = stable_selection('actual_local_user_choice_before_save',selected)
                if chosen[0]['selected_weapon_name'] != previous[0]['selected_weapon_name']:
                    raise RuntimeError('Remote local weapon choice unexpectedly changed host selection')
                report['user_choice_before_save']={'before':previous,'chosen':chosen,'local_cgame':local,'normal_input_slots':choices}
                if relay is not None:
                    run_selection_negatives(chosen)
            saved, local = stable_selection('immediately_before_native_save')
            report['immediately_before_save']={'host':saved,'local_cgame':local}
            screenshot('immediately-before-native-save')
        result=send_command(folder,text,joiner=joiner)
        if (Path(folder).resolve() == output/'host' and text.strip()=='loadgame coop_qa_checkpoint'
            and args.crossmap_before_load and crossmap_done):
            # The generic same-map oracle uses a clock rollback. Fresh B can
            # already have a lower clock than Save A, so require actual A and
            # a new native world before allowing that oracle to proceed.
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline:
                found=error_check(output/'host')
                if found:raise RuntimeError('native engine error loading cold Save A: '+found[0])
                state=qa_coop.read_state(output/'host');values=native_cvars()
                if (state and state['map']==args.map and preservation_publication_matches(values,0,'PRESERVED')
                    and values['coop_spawn_world']!=report['crossmap']['native_fresh_B']['coop_spawn_world']):
                    report['crossmap']['actual_A_native_world_recovered']=values['coop_spawn_world'];break
                time.sleep(.2)
            else:raise RuntimeError('Cold Save A did not recover its real map/new native PRESERVED world')
        return result

    def native_cvars():
        console=(output/'host/UnitedFronts/console.log').read_text(errors='replace')
        return dict(re.findall(r'^[ \t]*cvar set (coop_[a-z0-9_]+)[ \t]*(.*?)\r?$',console,re.M))

    def visit_fresh_map_b():
        # This is a deliberately labelled regression setup, not campaign progress.
        # Exact approved B media are supplied offline on both processes before A.
        a_values=native_cvars()
        for slot in range(args.players):
            if not preservation_publication_matches(a_values,slot,'FRESH'):
                raise RuntimeError('A starting kit lacks exact native FRESH proof')
        b_kits=[dict(kit,primary=kit['secondary'],secondary=kit['primary']) for kit in kits]
        b_resources=roster_resources(catalog,[{'family':'american','slots':kit} for kit in b_kits],{'sp_ally':'us_inf','campaign':'american','map':args.crossmap_before_load})
        if not set(b_resources['required_media_models']).issubset(preload_models):
            raise RuntimeError('Fresh B roster requires resources outside the explicit offline union')
        b_values=dict(host_cvars,coop_qa_kit_map=args.crossmap_before_load,coop_qa_kit_epoch=epoch+'-fresh-B')
        for slot,kit in enumerate(b_kits):
            b_values.update({'coop_qa_kit_%d_%s' % (slot,key):str(value) for key,value in kit.items()})
        for folder,slot in controllers:
            local_values=dict(b_values)
            if slot:local_values['coop_qa_kit_resources_only']='1'
            send_command(folder,'\n'.join('set %s "%s"' % item for item in local_values.items()),joiner=slot!=0)
        time.sleep(.3)
        send_command(output/'host','devmap '+args.crossmap_before_load)
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            for folder,slot in controllers:
                found=error_check(folder)
                if found:raise RuntimeError('native engine error during fresh B map: '+found[0])
            states=[qa_coop.read_state(folder) for folder,slot in controllers]
            if (all(states) and all(value['map']==args.crossmap_before_load for value in states)
                and all(value['joined'] and value['snapshot_num']>0 for value in states[1:])):
                values=native_cvars()
                if all(preservation_publication_matches(values,slot,'FRESH') for slot in range(args.players)):
                    if any(values['coop_spawn_ticket_%d' % slot]==a_values['coop_spawn_ticket_%d' % slot] for slot in range(args.players)):
                        raise RuntimeError('Fresh cross-map B did not allocate a new monotonic spawn ticket for each owner')
                    break
            time.sleep(.2)
        else:raise RuntimeError('Fresh B map did not complete actual party rejoin/FRESH identity')
        wanted=[expected[slot]['primaryb'] for slot in range(args.players)]
        b_host,b_local=stable_selection('fresh_B_distinct_starting_kits',wanted,validate_inventory=False)
        for slot in range(args.players):
            if b_host[slot]['inventory']['primary']!=expected[slot]['primaryb'] or b_host[slot]['inventory']['primaryb']!=expected[slot]['primary']:
                raise RuntimeError('Fresh B did not apply its own different approved starting kit')
        ready_deadline=time.monotonic()+35
        while any(state['weapon_state']!=0 for state in b_host):
            if time.monotonic()>=ready_deadline:
                raise RuntimeError('Fresh B original weapon raise/switch never reaches native ready state')
            time.sleep(.1)
            b_host,b_local=stable_selection('fresh_B_actual_weapon_ready',wanted,validate_inventory=False)
        for folder,slot in controllers:send_command(folder,'+attack',joiner=slot!=0)
        time.sleep(.4)
        for folder,slot in controllers:send_command(folder,'-attack',joiner=slot!=0)
        time.sleep(.5)
        b_fired,b_local=stable_selection('fresh_B_actual_fire',wanted,validate_inventory=False)
        if any(b_fired[slot]['slot_ammo']['primary']['clip']>=b_host[slot]['slot_ammo']['primary']['clip'] for slot in range(args.players)):
            raise RuntimeError('Each actual controller must fire its fresh B kit')
        screenshot('fresh-B-before-cold-save-A-load')
        report['crossmap'].update(native_fresh_A=a_values,native_fresh_B=values,fresh_B_before_fire=b_host,fresh_B_after_fire=b_fired)
        console=(output/'host/UnitedFronts/console.log').read_text(errors='replace')
        report['crossmap']['apply_counts_before_load']=[len(re.findall(r'(?m)^[ \t]*cvar set coop_qa_kit_applied_%d[ \t]+[^\r\n]+' % slot,console)) for slot in range(args.players)]
        if any(count<2 for count in report['crossmap']['apply_counts_before_load']):
            raise RuntimeError('Need actual A and fresh B kit application evidence for each owner')
        # Explicitly select the already approved A plan for its save. External
        # B identity receipts remain untouched: removing the native bridge must
        # reproduce a third Apply/refill and fail the saved-ammo oracle.
        for folder,slot in controllers:
            local_values=dict(host_cvars)
            if slot:local_values['coop_qa_kit_resources_only']='1'
            send_command(folder,'\n'.join('set %s "%s"' % item for item in local_values.items()),joiner=slot!=0)
        time.sleep(.2)

    def run_selection_negatives(chosen):
        if authentic_initial_selection is None: raise RuntimeError('No authentic initial native selection captured')
        selected=[state['selected_weapon_name'] for state in chosen]
        report['selection_negatives']=[]
        def stale_count():
            return qa_coop.read_state(output/'join1')['world_wire']['stale_by_type'].get('115',0)
        for mode in ('duplicate','wrong_ticket','wrong_world','wrong_session'):
            before=stale_count()
            relay.replay(mode,packet=authentic_initial_selection)
            time.sleep(.7)
            host,local=stable_selection('selection_negative_'+mode,selected)
            after=stale_count()
            if mode in ('wrong_world','wrong_session') and after<=before:
                raise RuntimeError('Wrong native selection context did not increment per-type stale counter: '+mode)
            report['selection_negatives'].append({'mode':mode,'status':'PASS','stale_before':before,'stale_after':after,'host':host,'local_cgame':local})
        console=(output/'host/UnitedFronts/console.log').read_text(errors='replace')
        values=dict(re.findall(r'^[ \t]*cvar set (coop_select_1_[a-z_]+)[ \t]*(.*?)\r?$',console,re.M))
        sequence=int(values['coop_select_1_seq'])
        old_session=int(values['coop_select_1_session_a'])
        for field,value in (('ticket',str(int(values['coop_select_1_ticket'])+1)),('session_a',str((old_session+1)&0x7fffffff))):
            sequence+=1
            offset=(output/'host/UnitedFronts/console.log').stat().st_size
            request_values={key:values['coop_select_1_'+key] for key in ('name','ticket','session_a','session_b','session_c','world','epoch')}
            request_values[field]=value
            commands=['set coop_select_1_%s %s' % item for item in request_values.items()]
            commands.append('set coop_select_1_seq %d' % sequence)
            send_command(output/'host','\n'.join(commands))
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                fresh=(output/'host/UnitedFronts/console.log').read_bytes()[offset:].decode(errors='replace')
                all_values=dict(re.findall(r'^[ \t]*cvar set (coop_select_1_[a-z_]+)[ \t]*(.*?)\r?$', (output/'host/UnitedFronts/console.log').read_text(errors='replace'), re.M))
                if (all_values.get('coop_select_1_status')=='REJECTED'
                    and 'cvar set coop_select_1_ack_seq '+str(sequence) in fresh
                    and all_values.get('coop_select_1_ack_seq')==str(sequence)): break
                time.sleep(.1)
            else: raise RuntimeError('Invalid fixed host selection request was not visibly rejected: '+field)
            host,local=stable_selection('invalid_host_request_'+field,selected)
            report['selection_negatives'].append({'mode':'invalid_host_'+field,'status':'PASS','host':host,'local_cgame':local,'rejection':fresh})

    def errors(folder):
        found = error_check(folder)
        if found and 'engine_error_observation' not in report:
            report['engine_error'] = found
            try: report['engine_error_observation'] = observe(validate=False)
            except Exception as error: report['engine_error_observation'] = {'observer_error': str(error)}
        return found

    def check(before, after, count):
        nonlocal saved, checkpoint_done, controllers, authentic_initial_selection
        assess(before, after, count)
        current = observe()
        if saved is None:
            controllers = [(output/name, qa_coop.read_state(output/name)['slot'] if name != 'host' else 0) for name in names]
            report['controller_native_slots'] = {folder.name: slot for folder,slot in controllers}
            deadline = time.monotonic()+35
            while time.monotonic()<deadline:
                console=(output/'host/UnitedFronts/console.log').read_text(errors='replace')
                values=dict(re.findall(r'^[ \t]*cvar set (coop_select_[1-3]_[a-z_]+)[ \t]*(.*?)\r?$',console,re.M))
                if all(selection_ack_matches(values,slot) for slot in range(1,args.players)):
                    report['fresh_selection_context_ack']=values; break
                time.sleep(.1)
            else: raise RuntimeError('Fresh actor selection lacks matching current session/world/ticket native ACK')
            if relay is not None:
                authentic_initial_selection=relay.latest()
                if authentic_initial_selection is None: raise RuntimeError('Relay did not capture authentic actor selection despite native ACK')
            stable_selection('starting_kit_before_user_switch')
            time.sleep(.7) # respect the original CGame weapon-switch debounce
            for folder, slot in controllers:
                send_command(folder, 'weaponslot '+fire_slots[slot], joiner=slot != 0)
            current, local = stable_selection('before_actual_fire',[expected[slot][fire_slots[slot]] for slot in range(args.players)])
            screenshot('before-checkpoint-stable-selection')
            fired = attack_and_check(current,'actual_fire_before_checkpoint')
            saved = fired
            report['distinct_kit_fire'] = 'PASS'
        else:
            current, local = stable_selection('after_native_checkpoint' if not checkpoint_done else 'final_stable_observation',[state['selected_weapon_name'] for state in saved])
            for slot in range(args.players):
                if current[slot]['slot_ammo'] != saved[slot]['slot_ammo']:
                    raise RuntimeError('Checkpoint changed actual kit ammo at slot%d' % slot)
                if current[slot]['weapon'] != saved[slot]['weapon'] or current[slot]['selected_weapon_name'] != saved[slot]['selected_weapon_name']:
                    report['active_weapon_retention'] = 'FAIL'
                    raise RuntimeError('Checkpoint lost active selected weapon at slot%d: %s -> %s' % (slot,saved[slot]['selected_weapon_name'],current[slot]['selected_weapon_name']))
                if current[slot]['viewmodel_name'] != saved[slot]['viewmodel_name']:
                    raise RuntimeError('Checkpoint changed actual native viewmodel at slot%d' % slot)
            if args.crossmap_before_load and not checkpoint_done:
                console=(output/'host/UnitedFronts/console.log').read_text(errors='replace')
                counts=[len(re.findall(r'(?m)^[ \t]*cvar set coop_qa_kit_applied_%d[ \t]+[^\r\n]+' % slot,console)) for slot in range(args.players)]
                if counts != report['crossmap']['apply_counts_before_load']:
                    raise RuntimeError('Cold save re-applied a starting kit instead of preserving numeric native inventory')
                values=native_cvars()
                for slot in range(args.players):
                    if not preservation_publication_matches(values,slot,'PRESERVED'):
                        raise RuntimeError('Cold save lacks exact native PRESERVED owner/world proof at slot%d' % slot)
                report['crossmap']['native_preserved_after_load']=values
                report['crossmap']['no_additional_apply']='PASS'
            report['active_weapon_retention'] = 'PASS'
            report['checkpoint_preserved_distinct_kits_ammo'] = 'PASS'
            if not checkpoint_done:
                screenshot('after-checkpoint-stable-selection')
                saved = attack_and_check(current,'actual_fire_after_checkpoint')
                report['real_fire_after_checkpoint']='PASS'
                checkpoint_done=True

    subprocess.Popen, qa_coop.assess_liveness, qa_coop.process_log_errors, qa_coop.command = launch, check, errors, command
    try:
        result = qa_coop.main(base)
        report['status'] = 'PASS' if result == 0 and report.get('distinct_kit_fire') == 'PASS' and report.get('checkpoint_preserved_distinct_kits_ammo') == 'PASS' and report.get('real_fire_after_checkpoint')=='PASS' else 'FAIL'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
    finally:
        subprocess.Popen, qa_coop.assess_liveness, qa_coop.process_log_errors, qa_coop.command = popen, assess, error_check, send_command
        (output/'uf-kit-proof.json').write_text(json.dumps(report, indent=2)+'\n')
        (output/Path(__file__).name).write_bytes(executed_source)
        if relay is not None:
            (output/'selection-relay-evidence.json').write_text(json.dumps(relay.evidence(),indent=2)+'\n')
            relay.close()
        for name in names:
            shutil.copy2(output/name/'UnitedFronts/zzzz_coop_campaign.pk3', output/(name+'-kit-overlay.pk3'))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
