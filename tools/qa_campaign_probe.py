#!/usr/bin/env python3
"""Real two-player UF worker/native-trigger probe, never a campaign playthrough.

Run against an owned installation with the pinned YAP plugin already installed.
The shared smoke harness owns all copies/processes. Test fixtures stay in --run.
"""
import argparse
import json
import re
import os
import subprocess
from pathlib import Path
import time
import zipfile

import qa_coop
from build_campaign_patch import build, build_trigger_patch


def read_new_log(path, offset):
    # Engine logs use CRLF. Offsets from stat() are bytes, not text-mode
    # character offsets (which silently strip carriage returns on Linux).
    return path.read_bytes()[offset:].decode('utf-8', errors='replace')


def final_probe_status(smoke_result, report):
    """A successful scenario also needs real-client liveness/error checks.
    Support-only scenarios deliberately skip the inventory-mutating ammo fixture.
    """
    if smoke_result != 0:
        return 'FAIL'
    if not (report.get('requested_airstrike') or report.get('requested_artillery')) and report.get('status') != 'PASS':
        return 'FAIL'
    required = {
        'requested_projectile_owner': {'projectile_owner': 'PASS'},
        'requested_mines': {'mine_placement': 'PASS', 'mine_pickup': 'PASS', 'mine_detonation': 'PASS'},
        'requested_autonomous_ai': {'ai_remote': 'PASS'},
        'requested_mg_deployment': {'mg_deployment': 'PASS_native_deploy_animation_then_full_ADS',
                                    'mg_fire': 'PASS_actual_attack_ammo_consumed'},
        'requested_airstrike': {'airstrike': 'PASS_actual_owner_cost_plane_original_impact'},
        'requested_artillery': {'artillery': 'PASS_native_cost_cooldown_actor_refill',
                                'artillery_projectiles': 'PASS_actual_remote_native_missiles'},
    }
    for requested, fields in required.items():
        if report.get(requested) and any(report.get(key) != value for key, value in fields.items()):
            return 'FAIL'
    return 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--port', default=29864, type=int)
    parser.add_argument('--map', default='pathfinder',
                        help='brecourt provides normal combat actors for mine/AI fixtures; pathfinder starts with scripted scene actors')
    parser.add_argument('--runtime-dir', type=Path,
                        help='pin archived ddraw.dll/core DLLs instead of the concurrently changing workspace build')
    parser.add_argument('--timeout', default=180, type=int)
    parser.add_argument('--projectile-owner', action='store_true',
                        help='also throw a grenade using actual joiner input and resolve its native owner')
    parser.add_argument('--mine-mechanics', action='store_true',
                        help='also throw a real remote land mine with the host grenade loadout unchanged')
    parser.add_argument('--artillery', action='store_true',
                        help='actual remote spotter fire, native projectile ownership and real 180-second replenishment')
    parser.add_argument('--airstrike', action='store_true',
                        help='throw actual remote smoke, preserve native ammo cost and original plane/impact timing')
    parser.add_argument('--mg-deployment', action='store_true',
                        help='deploy and fire a real remote MG on BSP terrain with native read-only state proof')
    parser.add_argument('--ai-remote', action='store_true',
                        help='observe native enemy choice and actual AI-attributed damage to the remote')
    parser.add_argument('--mutant-host-stockpile', action='store_true',
                        help='negative control: give both players shared stockpile; the mechanics probe must fail')
    args = parser.parse_args()
    if args.artillery and (args.airstrike or args.projectile_owner or args.mine_mechanics or args.ai_remote or args.mg_deployment):
        parser.error('--artillery is an independent scenario')
    if args.airstrike and (args.projectile_owner or args.mine_mechanics or args.ai_remote or args.mg_deployment):
        parser.error('--airstrike is an independent scenario')
    if args.mg_deployment and (args.projectile_owner or args.mine_mechanics or args.ai_remote):
        parser.error('--mg-deployment is an independent scenario; run owner/mine/AI probes separately')
    if args.mine_mechanics:
        args.projectile_owner = True
    output = args.run.resolve()
    smoke_args = ['--source', str(args.source.resolve()), '--run', str(output),
                  '--variant', 'united_fronts', '--map', args.map, '--players', '2',
                  '--timeout', str(args.timeout), '--duration', '12', '--port', str(args.port)]
    if args.runtime_dir:
        smoke_args += ['--runtime-dir', str(args.runtime_dir.resolve())]
    if qa_coop.main(smoke_args + ['--prepare-only']) != 0:
        return 1
    (output / 'uf-probe.json').unlink(missing_ok=True)
    for name in ('host', 'join1'):
        folder = output / name
        overlay = folder / 'UnitedFronts/zzzz_coop_campaign.pk3'
        build(folder / 'UnitedFronts/ZUnitedFronts_1.1_beta.pk3', overlay, 'united_fronts', qa=True)
        build_trigger_patch(folder, folder / 'UnitedFronts/zzzzz_coop_triggers.pk3', 'united_fronts')
        if args.mutant_host_stockpile:
            with zipfile.ZipFile(overlay) as z:
                entries = [(info, z.read(info.filename)) for info in z.infolist()]
            with zipfile.ZipFile(overlay, 'w') as z:
                for info, data in entries:
                    if info.filename == 'maps/_UF_weapons.gsc':
                        # Mutate the workers, never the scorer's per-player reads.
                        boundary = data.index(b'// Test fixture only:')
                        data = data[:boundary].replace(b'self.coop_binocular_stockpile', b'level.coop_binocular_stockpile') + data[boundary:]
                    z.writestr(info, data)
    original = qa_coop.assess_liveness
    original_errors = qa_coop.process_log_errors
    report = {'status': 'NOT_RUN', 'negative_control': args.mutant_host_stockpile,
              'coverage': 'real two-player asynchronous binocular ammo isolation and independent native mount entities',
              'requested_projectile_owner': args.projectile_owner,
              'requested_mines': args.mine_mechanics, 'requested_autonomous_ai': args.ai_remote,
              'requested_mg_deployment': args.mg_deployment, 'requested_airstrike': args.airstrike,
              'requested_artillery': args.artillery}
    entered = False
    owner_entered = False

    def capture_model_table():
        helper = output / 'qa-uf-player-state.exe'
        subprocess.run(['i686-w64-mingw32-g++', str(qa_coop.ROOT / 'campaign_patches/qa_uf_player_state.cpp'),
                        '-o', str(helper), '-static', '-O2', '-std=c++17'], check=True)
        env = dict(os.environ, WINEPREFIX=str(output / 'prefix'), WINEDEBUG='-all')
        result = subprocess.run(['wine', str(helper), str(output / 'host').replace('/', '\\'), '1', '--models'],
                                env=env, capture_output=True, text=True, timeout=10, check=True)
        models = json.loads(result.stdout.strip())
        report['server_model_count'] = len(models['models'])
        (output / 'uf-model-table.json').write_text(json.dumps(models, indent=2)+'\n')

    def artillery_probe():
        capture_model_table()
        helper = output / 'qa-uf-player-state.exe'
        env = dict(os.environ, WINEPREFIX=str(output / 'prefix'), WINEDEBUG='-all')
        host = output / 'host'
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(host, 'set coop_uf_arty_probe arm')
        deadline = time.monotonic() + 205
        equipped = False
        fired = False
        fired_at = None
        missiles = []
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if 'cvar set coop_uf_arty_phase FAIL_' in text:
                report['artillery'] = 'FAIL'
                raise RuntimeError('actual remote artillery probe failed; inspect phase telemetry')
            if not equipped and 'cvar set coop_uf_arty_phase EQUIP' in text:
                time.sleep(0.6)
                qa_coop.command(output / 'join1', 'weaponslot pistol', joiner=True)
                equipped = True
            if not fired and 'cvar set coop_uf_arty_phase READY_FIRE' in text:
                qa_coop.command(output / 'join1', 'toggle cl_run', joiner=True)
                time.sleep(0.6)
                qa_coop.command(output / 'join1', '+attack', joiner=True)
                time.sleep(0.4)
                qa_coop.command(output / 'join1', '-attack', joiner=True)
                time.sleep(0.8)
                qa_coop.command(output / 'join1', '+attack', joiner=True)
                time.sleep(0.2)
                qa_coop.command(output / 'join1', '-attack', joiner=True)
                fired = True; fired_at = time.monotonic()
            if fired and time.monotonic()-fired_at < 50:
                observed = subprocess.run(['wine', str(helper), str(host).replace('/', '\\'), '1', '--missiles'],
                                          env=env, capture_output=True, text=True, timeout=10, check=True)
                state = json.loads(observed.stdout.strip())
                if state.get('missiles'):
                    missiles.append(state)
                    if any(missile['owner'] == 1 for missile in state['missiles']):
                        report['artillery_projectiles'] = 'PASS_actual_remote_native_missiles'
                    (output/'uf-arty-native-missiles.json').write_text(json.dumps(missiles, indent=2)+'\n')
            if 'cvar set coop_uf_arty_phase PASS_native_cost_cooldown_actor_refill' in text:
                report['artillery'] = 'PASS_native_cost_cooldown_actor_refill'
                report['artillery_wall_seconds_after_retry'] = round(time.monotonic()-fired_at, 3)
                if report.get('artillery_projectiles') != 'PASS_actual_remote_native_missiles':
                    raise RuntimeError('normal artillery cost/refill passed but actual remote native projectile ownership was not observed')
                return
            time.sleep(.1)
        report['artillery'] = 'TIMEOUT'
        raise RuntimeError('original 180-second artillery replenishment did not complete')

    def air_probe():
        capture_model_table()
        host = output / 'host'
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(host, 'set coop_uf_air_probe arm')
        deadline = time.monotonic() + 95
        thrown = False
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if 'cvar set coop_uf_air_phase FAIL_' in text:
                report['airstrike'] = 'FAIL'
                raise RuntimeError('actual remote airstrike probe failed; inspect support phase telemetry')
            if not thrown and 'cvar set coop_uf_air_phase READY_THROW' in text:
                time.sleep(0.6)
                qa_coop.command(output / 'join1', 'weaponslot grenade', joiner=True)
                time.sleep(1)
                qa_coop.command(output / 'join1', '+attack', joiner=True)
                time.sleep(0.6)
                qa_coop.command(output / 'join1', '-attack', joiner=True)
                # Ordinary movement gives the group time to leave the marked
                # blast area during UF's unchanged aircraft approach delay.
                qa_coop.command(output / 'join1', '+back', joiner=True)
                qa_coop.command(host, '+back')
                time.sleep(6)
                qa_coop.command(output / 'join1', '-back', joiner=True)
                qa_coop.command(host, '-back')
                thrown = True
            if 'cvar set coop_uf_air_phase PASS_remote_smoke_original_airstrike' in text:
                report['airstrike'] = 'PASS_actual_owner_cost_plane_original_impact'
                return
            time.sleep(0.1)
        report['airstrike'] = 'FAIL_timeout'
        raise RuntimeError('actual remote smoke airstrike did not complete within its bounded observation')

    def mg_probe():
        helper = output / 'qa-uf-player-state.exe'
        subprocess.run(['i686-w64-mingw32-g++', str(qa_coop.ROOT / 'campaign_patches/qa_uf_player_state.cpp'),
                        '-o', str(helper), '-static', '-O2', '-std=c++17'], check=True)
        env = dict(os.environ, WINEPREFIX=str(output / 'prefix'), WINEDEBUG='-all')
        host = output / 'host'
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(output / 'join1', 'gocrouch', joiner=True)
        time.sleep(0.6)
        qa_coop.command(host, 'set coop_uf_mg_probe arm')
        deadline = time.monotonic() + 45
        equipped = False
        mode_selected = False
        deployment_requested = False
        states = []
        saw_native_deploy = False
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if 'cvar set coop_uf_mg_phase FAIL_' in text:
                report['mg_deployment'] = 'FAIL'
                raise RuntimeError('real terrain/deployment fixture failed; inspect phase telemetry')
            if not equipped and 'cvar set coop_uf_mg_phase EQUIP' in text:
                time.sleep(0.6)  # let real inventory snapshots arrive before normal slot input
                slots = re.findall(r'cvar set coop_uf_mg_slot (primaryb?)', text)
                if not slots:
                    raise RuntimeError('MG fixture did not report a real primary inventory slot')
                qa_coop.command(output / 'join1', 'weaponslot '+slots[-1], joiner=True)
                equipped = True
            if not mode_selected and 'cvar set coop_uf_mg_phase SELECT_DEPLOYABLE_MODE' in text:
                qa_coop.command(output / 'join1', 'weapalt', joiner=True)
                mode_selected = True
            if 'cvar set coop_uf_mg_phase READY_NATIVE_DEPLOY' in text:
                if not deployment_requested:
                    qa_coop.command(output / 'join1', 'toggle cl_run', joiner=True)
                    deployment_requested = True
                result = subprocess.run(['wine', str(helper), str(host).replace('/', '\\'), '1'], env=env,
                                        capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    raise RuntimeError('read-only native remote weapon-animation/state observer failed: '+result.stderr)
                state = json.loads(result.stdout.strip())
                states.append(state)
                report['mg_native_states'] = states
                (output / 'uf-mg-native-states.json').write_text(json.dumps(states, indent=2)+'\n')
                saw_native_deploy |= state['clientnum'] == 1 and state['weapon_anim'] == 19 and state['weapon_state'] == 12
                if (saw_native_deploy and state['clientnum'] == 1 and state['weapon_state'] == 0
                        and state['pm_flags'] & 0x20 and state['ads_fraction'] >= 0.999):
                    report['mg_deployment'] = 'PASS_native_deploy_animation_then_full_ADS'
                    qa_coop.command(output / 'join1', '+attack', joiner=True)
                    time.sleep(0.6)
                    qa_coop.command(output / 'join1', '-attack', joiner=True)
                    qa_coop.command(host, 'set coop_uf_mg_probe fired')
                    break
            time.sleep(0.1)
        else:
            report['mg_deployment'] = 'FAIL_native_deploy_not_observed'
            raise RuntimeError('native remote deploy animation followed by complete ADS not observed')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if 'cvar set coop_uf_mg_phase PASS_real_remote_ammo_consumed' in text:
                report['mg_fire'] = 'PASS_actual_attack_ammo_consumed'
                return
            if 'cvar set coop_uf_mg_phase FAIL_' in text:
                break
            time.sleep(0.1)
        report['mg_fire'] = 'FAIL'
        raise RuntimeError('deployed real remote MG did not consume ammunition')

    def ai_probe():
        host = output / 'host'
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(host, 'set coop_uf_ai_probe arm')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if 'cvar set coop_uf_ai_result PASS_native_choice_attacker_damage' in text:
                report['ai_remote'] = 'PASS'
                return
            if 'cvar set coop_uf_ai_result FAIL_' in text:
                report['ai_remote'] = 'FAIL'
                raise RuntimeError('native autonomous remote AI attack probe failed')
            time.sleep(0.1)
        report['ai_remote'] = 'TIMEOUT'
        raise RuntimeError('native autonomous remote AI attack probe timed out')

    def mine_probe():
        host = output / 'host'
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(host, 'set coop_uf_mine_probe arm')
        deadline = time.monotonic() + 40
        fired = False
        fired_second = False
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if not fired and 'cvar set coop_uf_mine_result READY' in text:
                qa_coop.command(output / 'join1', 'weaponslot grenade', joiner=True)
                time.sleep(1)
                qa_coop.command(output / 'join1', '+attack', joiner=True)
                time.sleep(0.6)
                qa_coop.command(output / 'join1', '-attack', joiner=True)
                fired = True
            if 'cvar set coop_uf_mine_result PASS_actual_remote_mine_host_unchanged' in text:
                report['mine_placement'] = 'PASS'
            if 'cvar set coop_uf_mine_pickup PASS_actual_remote_pickup' in text:
                report['mine_pickup'] = 'PASS'
            if not fired_second and 'cvar set coop_uf_mine_detonation READY' in text:
                qa_coop.command(output / 'join1', 'weaponslot grenade', joiner=True)
                time.sleep(1)
                qa_coop.command(output / 'join1', '+attack', joiner=True)
                time.sleep(0.6)
                qa_coop.command(output / 'join1', '-attack', joiner=True)
                fired_second = True
            if 'cvar set coop_uf_mine_detonation PASS_real_enemy_proximity_damage' in text:
                report['mine_detonation'] = 'PASS'
                return
            if 'cvar set coop_uf_mine_detonation FAIL_' in text:
                report['mine_detonation'] = 'FAIL'
                raise RuntimeError('actual remote mine detonation probe failed')
            if 'cvar set coop_uf_mine_pickup FAIL_' in text:
                report['mine_pickup'] = 'FAIL'
                raise RuntimeError('actual remote mine pickup probe failed')
            if 'cvar set coop_uf_mine_result FAIL_' in text:
                report['mine_placement'] = 'FAIL'
                raise RuntimeError('actual remote mine placement probe failed')
            time.sleep(0.1)
        report['mine_placement'] = 'TIMEOUT'
        raise RuntimeError('actual remote mine placement probe timed out')

    def probe(before, after, count):
        nonlocal entered, owner_entered
        original(before, after, count)
        if entered:
            if args.artillery and not owner_entered:
                owner_entered = True
                artillery_probe()
                return
            if args.airstrike and not owner_entered:
                owner_entered = True
                air_probe()
                return
            if args.mg_deployment and not owner_entered:
                owner_entered = True
                mg_probe()
                return
            if args.ai_remote and not args.projectile_owner and not owner_entered:
                owner_entered = True
                ai_probe()
                return
            if args.projectile_owner and not owner_entered:
                owner_entered = True
                host = output / 'host'
                log = host / 'UnitedFronts/console.log'
                offset = log.stat().st_size
                qa_coop.command(host, 'set coop_uf_owner_probe arm')
                deadline = time.monotonic() + 20
                fired = False
                while time.monotonic() < deadline:
                    text = read_new_log(log, offset)
                    if not fired and 'cvar set coop_uf_owner_result READY' in text:
                        qa_coop.command(output / 'join1', 'weaponslot grenade', joiner=True)
                        time.sleep(1)
                        qa_coop.command(output / 'join1', '+attack', joiner=True)
                        time.sleep(0.6)
                        qa_coop.command(output / 'join1', '-attack', joiner=True)
                        fired = True
                    if 'cvar set coop_uf_owner_result PASS_actual_remote_projectile' in text:
                        report['projectile_owner'] = 'PASS'
                        mine_error = None
                        if args.mine_mechanics:
                            try:
                                mine_probe()
                            except RuntimeError as error:
                                mine_error = error
                        if args.ai_remote:
                            ai_probe()
                        if mine_error is not None:
                            raise mine_error
                        return
                    if 'cvar set coop_uf_owner_result FAIL_' in text:
                        report['projectile_owner'] = 'FAIL'
                        raise RuntimeError('actual remote projectile ownership probe failed')
                    time.sleep(0.1)
                report['projectile_owner'] = 'TIMEOUT'
                raise RuntimeError('actual remote projectile ownership probe timed out')
            return
        entered = True
        if args.airstrike or args.artillery:
            return  # keep initial ammunition/inventory untouched for the support-cost probe
        host = output / 'host'
        # Initial snapshots can precede a scripted parachute/Jeep loadout.
        # Wait for both actual actors to leave their original special role so
        # the fixture cannot race the mission's normal inventory initialization.
        control_deadline = time.monotonic() + args.timeout
        while time.monotonic() < control_deadline:
            state = qa_coop.read_state(host)
            if state and all(p.get('pm_type') == 0 and not p.get('linked') for p in state['players'][:2]):
                time.sleep(2)
                break
            time.sleep(0.2)
        else:
            raise RuntimeError('original intro did not release both actors before mechanics fixture')
        log = host / 'UnitedFronts/console.log'
        offset = log.stat().st_size
        qa_coop.command(host, 'developer 1\ncoop_uf_workers\nset coop_uf_probe run')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            text = read_new_log(log, offset)
            if ('COOP_UF_QA PASS ammo_isolation_native_mounts' in text or
                    'cvar set coop_uf_probe_result PASS_ammo_isolation_native_mounts' in text):
                report['status'] = 'PASS'
                if args.mutant_host_stockpile:
                    raise RuntimeError('negative control escaped detection')
                return
            if 'COOP_UF_QA FAIL' in text or 'cvar set coop_uf_probe_result FAIL_' in text:
                report['status'] = 'FAIL'
                raise RuntimeError('UF actor-local mechanics probe failed')
            time.sleep(0.2)
        report['status'] = 'TIMEOUT'
        raise RuntimeError('UF mechanics probe did not produce a result')

    qa_coop.assess_liveness = probe
    def script_errors(folder):
        errors = original_errors(folder)
        console = folder / 'UnitedFronts/console.log'
        if console.exists():
            lines = console.read_text(errors='replace').splitlines()
            for i, line in enumerate(lines):
                if 'script runtime error' in line.lower():
                    errors.append('GSC: ' + (lines[i + 1] if i + 1 < len(lines) else line))
        return errors
    qa_coop.process_log_errors = script_errors
    try:
        if args.runtime_dir:
            report['requested_runtime_dir'] = str(args.runtime_dir.resolve())
        result = qa_coop.main(smoke_args)
        if not args.mutant_host_stockpile:
            report['status'] = final_probe_status(result, report)
    finally:
        qa_coop.assess_liveness = original
        qa_coop.process_log_errors = original_errors
        report['runtime'] = json.loads((output / 'provenance.json').read_text())['runtime']
        console = output / 'host/UnitedFronts/console.log'
        if console.exists():
            report['telemetry'] = dict(re.findall(r'cvar set (coop_uf_(?:mine_|ai_|mg_|air_|arty_)[a-z_]+) ([^\r\n]*)', console.read_text(errors='replace')))
        (output / 'uf-probe.json').write_text(json.dumps(report, indent=2) + '\n')
    if args.mutant_host_stockpile:
        caught = result != 0 and report['status'] == 'FAIL'
        print('DETECTOR: ' + ('PASS (shared stockpile rejected)' if caught else 'FAIL'))
        return 0 if caught else 1
    return 0 if result == 0 and report['status'] == 'PASS' and (not args.projectile_owner or report.get('projectile_owner') == 'PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
