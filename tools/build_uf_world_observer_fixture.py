#!/usr/bin/env python3
"""Source-review fixture ONLY: do not mount over existing compatibility overlays.

No production builder or install integration. Original Campaign/Climate reads
are compacted in function-local variables and published once, not reread later.
Native publisher ABI and actual GSC compile/runtime remain pending review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
from build_campaign_patch import function_span, replace_active, uf_airborne_missing_load
from uf_world_rules import PINNED

ROOT=Path(__file__).resolve().parents[1]
MODULE=r'maps\_coop_uf_world_observer::'


def rewrite_function(text,name,transform):
    start,end=function_span(text,name)
    return text[:start]+transform(text[start:end])+text[end:]


def campaign_body(body):
    body=replace_active(body,r'\bspawners\s*=\s*getspawnerarray\(\)\s*;',
        'spawners = getspawnerarray();\n    coop_last_index = -1; coop_last_class = "";',expected=1)
    body=replace_active(body,r'for\s*\(i\s*=\s*0;\s*i\s*<\s*spawners\.size;\s*i\+\+\)\s*switch\s*\(spawners\[i\]\.classname\)\s*\{',
        'for (i=0; i<spawners.size; i++)\n    {\n    coop_observed_class = spawners[i].classname;\n    switch (coop_observed_class)\n    {',expected=1)
    # The three original case groups alone define recognition. No second scan.
    assignment=r'(level\.campaign\s*=\s*"(?:american|british|russian)"\s*;)'
    start=body.index('coop_observed_class =')
    prefix,suffix=body[:start],body[start:]
    suffix=replace_active(suffix,assignment,
        lambda m:'coop_last_index = i; coop_last_class = coop_observed_class;\n            '+m[0],expected=3)
    return prefix+suffix+'\n    }\n    '+MODULE+'CampaignFacts(spawners.size, coop_last_index, coop_last_class, level.campaign);\n'


def climate_body(body):
    body=replace_active(body,r'\bspawners\s*=\s*getspawnerarray\(\)\s*;',
        'spawners = getspawnerarray();\n    coop_winter_index = -1; coop_winter_class = "";',expected=1)
    body=replace_active(body,r'switch\s*\(spawners\[i\]\.classname\)',
        'coop_observed_class = spawners[i].classname;\n        switch (coop_observed_class)',expected=1)
    body=replace_active(body,r'(level\.winter_map\s*=\s*1\s*;)',
        lambda m:'if (coop_winter_index == -1) { coop_winter_index = i; coop_winter_class = coop_observed_class; }\n                '+m[0],expected=2)
    # The second occurrence is the map override, where i/class are stale. Keep
    # instrumentation ONLY in the original snow-spawner case branch.
    insertion='if (coop_winter_index == -1) { coop_winter_index = i; coop_winter_class = coop_observed_class; }\n                '
    at=body.rfind(insertion)
    body=body[:at]+body[at:].replace(insertion,'',1)
    return body+'\n    '+MODULE+'ClimateFacts(spawners.size, coop_winter_index, coop_winter_class, getcvar("sp_climate"));\n'


def levels_body(body):
    # The reviewed year switch precedes this first special-return switch.
    marker=r'(?=switch\s*\(level\.script\)\s*\{\s*case\s*"credits"\s*:)'
    return replace_active(body,marker,MODULE+'YearObserved();\n\n    ',expected=1)


def helper(graph):
    text=(ROOT/'campaign_patches/uf_world_observer.gsc').read_text()
    digest=hashlib.sha256(json.dumps(graph,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    text+='\nGraphIdentity() { return "'+digest+'"; }\n'
    for function,values in [('KnownCampaignClass',graph['spawner_campaign']),('KnownWinterClass',graph['snow_spawners'])]:
        text+='\n'+function+'(value)\n{\n    switch(value)\n    {\n'
        for value in sorted(values):
            if not re.fullmatch(r'[A-Za-z0-9_]{1,127}',value):raise ValueError('Unreviewed class token')
            text+='        case "'+value+'":\n'
        text+='            return true;\n    }\n    return false;\n}\n'
    return text.encode('latin1'),digest


def instrument(package, *, compose_airborne_fix=False):
    graph=json.loads((ROOT/'campaign_patches/uf_world_rules.json').read_text())
    if graph['sources']!=PINNED:raise ValueError('Independent graph/source identity changed')
    with zipfile.ZipFile(package) as archive:
        data={name:archive.read(name) for name in PINNED}
    if any(hashlib.sha256(data[name]).hexdigest()!=digest for name,digest in PINNED.items()):raise ValueError('Unknown pinned UF world source')
    load=data['maps/_UF_loadout.gsc'].decode('latin1');mod=data['maps/_UF_mod.gsc'].decode('latin1')
    composition = None
    if compose_airborne_fix:
        repaired=uf_airborne_missing_load(data['maps/_UF_mod.gsc'])
        mod=repaired.decode('latin1')
        composition={'transform':'uf_airborne_missing_load','input_sha256':PINNED['maps/_UF_mod.gsc'],
                     'repaired_sha256':hashlib.sha256(repaired).hexdigest()}
    load=rewrite_function(load,'give_loadout',lambda body:'\n    '+MODULE+'Begin();\n'+body)
    load=rewrite_function(load,'Campaign',campaign_body)
    load=rewrite_function(load,'Levels',levels_body)
    mod=rewrite_function(mod,'Map_Climate',climate_body)
    mod=rewrite_function(mod,'Cvars',lambda body:body+'\n    '+MODULE+'CvarsObserved();\n')
    observer,digest=helper(graph)
    return {'maps/_UF_loadout.gsc':load.encode('latin1'),'maps/_UF_mod.gsc':mod.encode('latin1'),
            'maps/_coop_uf_world_observer.gsc':observer}, {'schema':1,'sources':PINNED,'graph_sha256':digest,
            'scope':'source-only witness proposal; not packaged, compiled, installed or native verified','native_ready_capability':False,
            'composition':composition,
            'generated_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in
                [('maps/_UF_loadout.gsc',load.encode('latin1')),('maps/_UF_mod.gsc',mod.encode('latin1')),('maps/_coop_uf_world_observer.gsc',observer)]}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-package',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();files,metadata=instrument(args.source_package)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        target=args.output_dir/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (args.output_dir/'witness-source-review.json').write_text(json.dumps(metadata,indent=2)+'\n')

if __name__=='__main__':main()
