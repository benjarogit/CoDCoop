#!/usr/bin/env python3
"""QA-only missing-host-aircraft bootstrap/cache-preload experiment.

The negative control omits the catalog. The positive control uses an exact
native host export, before the peer's ordinary local map loading starts.
No guard flag, game model limit, production transport or gameplay value changes.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import time
import zipfile
import qa_coop as qa
from build_campaign_patch import build

TARGET = 'xmodel/v_rs_air_il2'


def fixture(folder):
    directory = folder / 'UnitedFronts'
    # A controlled local bootstrap divergence models the proposed contract.
    # Production script sources are unchanged; only this QA overlay is edited.
    overlay = directory / 'zzzz_coop_campaign.pk3'
    build(directory / 'ZUnitedFronts_1.1_beta.pk3', overlay, 'united_fronts', qa=False)
    with zipfile.ZipFile(overlay) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    load = files['maps/_load.gsc'].decode('latin1')
    call = '    maps\\_UF_weapons::Coop_PrecacheAirAssets();'
    if load.count(call) != 1:
        raise RuntimeError('QA fixture startup anchor changed')
    load = load.replace(call, '    maps\\_UF_weapons::Coop_QAHostOnlyModel();')
    files['maps/_load.gsc'] = load.encode('latin1')
    weapons = files['maps/_UF_weapons.gsc'].decode('latin1')
    weapons += '''
Coop_QAHostOnlyModel()
{
    if (getcvar("coop_qa_render_host") != "1") return;
    precacheModel("xmodel/v_rs_air_il2");
    thread Coop_QARenderModel();
}
Coop_QARenderModel()
{
    while (getcvar("coop_qa_render_fixture") != "run") wait 0.05;
    forward = anglesToForward(level.player.angles);
    plane = spawn("script_model", level.player.origin + vectorScale(forward, 350) + (0,0,64));
    plane.angles = level.player.angles + (0,90,0);
    plane setmodel("xmodel/v_rs_air_il2");
    setcvar("coop_qa_render_entity", plane getentitynumber());
}
'''
    # Identical script bytes on both seats: only their local startup selection
    # differs, reproducing the bootstrap contract gap without mismatched code.
    weapons, omitted = re.subn(r'\bprecachemodel\s*\(\s*"xmodel/v_rs_air_il2"\s*\)\s*;',
                               'Coop_QAConditionalIL2();', weapons, flags=re.I)
    if omitted < 1:
        raise RuntimeError('QA bootstrap gap did not replace any actual target precache')
    weapons += '''
Coop_QAConditionalIL2()
{
    if (getcvar("coop_qa_render_host") == "1") precacheModel("xmodel/v_rs_air_il2");
}
'''
    files['maps/_UF_weapons.gsc'] = weapons.encode('latin1')
    files['codcoop_renderer_probe.json'] = b'{"qa_only":true,"scope":"conditional local bootstrap asset contract fixture"}\n'
    with zipfile.ZipFile(overlay, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--port', type=int, default=29959)
    args = parser.parse_args(argv)
    output = args.run.resolve()
    host, peer = output / 'host', output / 'join1'
    smoke = ['--source', str(args.source.resolve()), '--run', str(output), '--runtime-dir', str(args.runtime_dir.resolve()),
             '--variant', 'united_fronts', '--map', 'pathfinder', '--players', '2', '--duration', '5',
             '--port', str(args.port), '--timeout', str(args.timeout)]
    if qa.main(smoke + ['--prepare-only']):
        return 1
    for folder in (host, peer):
        fixture(folder)
        for pattern in ('qa-model-*.txt', 'qa-model-*.json', 'qa-render-*.txt', 'qa-render-*.json'):
            for file in folder.glob(pattern):
                file.unlink()
    overlays = [hashlib.sha256((folder / 'UnitedFronts/zzzz_coop_campaign.pk3').read_bytes()).hexdigest() for folder in (host, peer)]
    if overlays[0] != overlays[1]:
        raise RuntimeError('the two seats do not have identical QA script packages')
    original_spawn, original_live, original_wait = qa.subprocess.Popen, qa.assess_liveness, qa.wait_for
    report = {'status': 'NOT_RUN', 'negative': args.negative, 'scope': 'QA cache-only native preload of actual missing host aircraft asset; no production transport or campaign acceptance'}
    report['identical_script_overlay_sha256'] = overlays[0]
    entered = False

    def read(path):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def launch(command, *a, **kw):
        if isinstance(command, list) and len(command) > 1 and Path(command[1]).name.lower() == 'coduosp.exe':
            folder = Path(kw['cwd'])
            command = list(command)
            if folder == host:
                at = command.index('+devmap')
                command[at:at] = ['+set', 'coop_qa_render_host', '1', '+set', 'sp_ally', 'us']
            else:
                def exported():
                    state = qa.read_state(host)
                    metadata = read(host / 'qa-model-export.json')
                    if state and metadata and state.get('map') == 'pathfinder' and state['server_time'] > 300 and metadata['map'] == 'pathfinder':
                        return metadata
                report['host_export'] = original_wait(exported, [], args.timeout, 'native host CS/registered weapon media export')
                catalog = (host / 'qa-model-export.txt').read_text()
                if TARGET not in catalog.splitlines():
                    raise RuntimeError('host did not register the required fixture model')
                (output / 'host-derived-catalog.txt').write_text(catalog)
                if not args.negative:
                    (peer / 'qa-render-models.txt').write_text(catalog)
        return original_spawn(command, *a, **kw)

    def waiting(predicate, processes, timeout, description):
        def checked():
            text = (peer / 'codcoop_join.log').read_text(errors='replace') if (peer / 'codcoop_join.log').exists() else ''
            if 'native world attachment failed' in text:
                raise RuntimeError('native attachment failed during cache preload experiment')
            return predicate()
        return original_wait(checked, processes, timeout, description)

    def probe(before, after, count):
        nonlocal entered
        original_live(before, after, count)
        if entered:
            return
        entered = True
        audit = read(peer / 'qa-render-preload.json')
        if not audit or audit.get('map') != 'pathfinder' or not audit.get('valid_catalog') or not audit.get('native_loading_allowed'):
            raise RuntimeError('no valid native early-registration audit: ' + repr(audit))
        if audit['loaded'] != audit['names'] or audit['game_cs_before'] != audit['game_cs_after'] or audit['game_cs_after'] > 255:
            raise RuntimeError('preload did not complete without game CS growth')
        if not audit['guards_unchanged'] or audit['strict_guard'] != 1 or not audit['fixture_missing_local_cs']:
            raise RuntimeError('native guard changed or fixture asset was already in local game CS')
        report['preload'] = audit
        qa.command(host, 'set coop_qa_render_fixture run')
        def entity_ready():
            state = qa.read_state(host)
            data = state.get('qa_render_fixture', {}) if state else {}
            return data['entity'] if data.get('dobj_model') else None
        entity = qa.wait_for(entity_ready, [], 15, 'real host aircraft model entity')
        qa.command(peer, 'set coop_qa_render_entity %d' % entity, joiner=True)
        report['replicated_aircraft'] = qa.wait_for(lambda: (s := qa.read_state(peer)) and s.get('qa_render_fixture', {}).get('dobj_model') and s,
                                                   [], 20, 'actual peer aircraft DObj with host-selected model')
        report['status'] = 'PASS'

    qa.subprocess.Popen, qa.assess_liveness, qa.wait_for = launch, probe, waiting
    try:
        result = qa.main(smoke)
        if args.negative:
            local = (peer / 'qa-model-local-at-end.txt').read_text().splitlines() if (peer / 'qa-model-local-at-end.txt').exists() else []
            logs = ''.join((peer / path).read_text(errors='replace') for path in ('codcoop_join.log', 'UnitedFronts/console.log') if (peer / path).exists())
            report['local_model_missing'] = TARGET not in local
            report['native_error'] = 'not precached' in logs
            report['missing_native_models'] = re.findall(r"model '([^']+)' not precached", logs)
            report['status'] = 'PASS_NEGATIVE' if result and report.get('host_export') and report['local_model_missing'] and report['native_error'] else 'FAIL'
        elif result:
            report['status'] = 'FAIL'
        (output / 'renderer-preload-probe.json').write_text(json.dumps(report, indent=2) + '\n')
        return 0 if report['status'] in ('PASS', 'PASS_NEGATIVE') else 1
    finally:
        qa.subprocess.Popen, qa.assess_liveness, qa.wait_for = original_spawn, original_live, original_wait


if __name__ == '__main__':
    raise SystemExit(main())
