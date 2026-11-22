"""Captured launcher build graph + actual frozen capability coherence gate.

Only a fixed local launcher filename is executed, never a path/command obtained
from a manifest. Capabilities describe worker support, never native kit readiness.
"""
import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

CAPABILITIES=('campaign-supervisor-v1','installation-receipt-v1','native-party-proof-worker-v1','signed-party-v1')
FILES=('tools/build-launcher.py','tools/launcher_provenance.py','tools/stage_suite.py',
       'tools/launch-gui.py','tools/coop_suite.py','tools/coop_session.py','tools/frozen_runtime.py','tools/runtime_protocol.py',
       'tools/coop_party.py','tools/party_gui.py','tools/party_binding.py','tools/party_native_bridge.py',
       'tools/uf_equipment_catalog.py','tools/uf_equipment_preferences.py','tools/uf_equipment_roster.py','tools/uf_equipment_roster_view.py',
       'tools/campaign_inventory.py','tools/build_campaign_patch.py','campaign_patches/uf_equipment_catalog.json','content/variants.json',
       'tools/requirements-launcher.txt','tools/requirements-launcher-linux.lock','tools/portable-linux/party-dependencies.lock',
       'tools/portable-linux/Dockerfile','tools/portable-linux/apt-packages.lock','tools/build-portable-linux.sh','tools/check-linux-abi.py')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(graph):
    if not isinstance(graph,dict) or set(graph)!={'schema','protocol','core_features_supported','capabilities','files'} or type(graph['schema']) is not int or graph['schema']!=1:
        raise ValueError('Invalid captured launcher source graph')
    if type(graph['protocol']) is not int or graph['protocol']<1 or type(graph['core_features_supported']) is not int or not 0<=graph['core_features_supported']<2**32:
        raise ValueError('Invalid launcher build protocol/features')
    if graph['capabilities']!=list(CAPABILITIES) or not isinstance(graph['files'],dict) or set(graph['files'])!=set(FILES):
        raise ValueError('Incomplete launcher build graph/capabilities')
    if any(not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h) for h in graph['files'].values()):
        raise ValueError('Invalid launcher graph file digest')
    return graph


def capture(root):
    root=Path(root);manifest=json.loads((root/'content/variants.json').read_text())
    values=[node.value.value for node in ast.parse((root/'tools/coop_suite.py').read_text()).body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROTOCOL' for t in node.targets) and isinstance(node.value,ast.Constant)]
    if values!=[manifest['protocol']]:raise ValueError('Source worker protocol differs from captured manifest')
    graph={'schema':1,'protocol':manifest['protocol'],'core_features_supported':manifest.get('core_features_required',0),
           'capabilities':list(CAPABILITIES),'files':{name:sha(root/name) for name in FILES}}
    return validate(graph)


def load(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Capture a source graph before building/staging the launcher: '+str(path))
    return validate(json.loads(path.read_text()))


def assert_sources(root,expected):
    # Compare against an explicitly captured immutable input, not a freshly
    # inferred graph which could bless a half-edited working tree.
    if capture(root)!=validate(expected):raise ValueError('Launcher source files changed since captured build graph')


def capabilities():
    # Actual loaded runtime dependency probe, with no sockets, settings or key
    # files. A missing frozen Rust/cffi/parser library must not advertise party.
    import cffi
    import typing_extensions
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key=Ed25519PrivateKey.generate();message=b'CoDCoop launcher capability self-test'
    key.public_key().verify(key.sign(message),message)
    ffi=cffi.FFI();ffi.cdef('int coop_capability_probe(void);')
    if ffi.sizeof('int')!=4:raise ValueError('Invalid frozen cffi backend')
    if getattr(sys,'frozen',False):
        # Pure constant module is compiled INTO the executable PYZ, not mutable
        # external --add-data JSON. Its bytes bind the actual executable hash.
        graph=validate(json.loads(importlib.import_module('launcher_build_identity').SOURCE_GRAPH_JSON))
    else:graph=capture(Path(__file__).resolve().parents[1])
    return {'kind':'codcoop_launcher','schema':1,'protocol':graph['protocol'],'core_features_supported':graph['core_features_supported'],
            'capabilities':graph['capabilities'],'source_graph_sha256':digest(graph)}


def require_launcher(source,expected,protocol,required_features,wine_prefix=None):
    source=Path(source);expected=validate(expected);receipt=source/'launcher-build.json'
    if not receipt.is_file():raise ValueError('Launcher build provenance is missing; rebuild current worker')
    value=json.loads(receipt.read_text())
    if not isinstance(value,dict) or set(value)!={'schema','executable','executable_sha256','source_graph','source_graph_sha256'} or type(value['schema']) is not int or value['schema']!=1:
        raise ValueError('Invalid launcher build provenance')
    name=value['executable']
    if name not in ('CoD-Coop-Launcher','CoD-Coop-Launcher.exe'):raise ValueError('Unregistered launcher filename')
    executable=source/name
    if not executable.is_file() or sha(executable)!=value['executable_sha256']:raise ValueError('Launcher executable does not match build provenance')
    if value['source_graph']!=expected or value['source_graph_sha256']!=digest(expected):raise ValueError('Launcher captured build graph differs from expected source snapshot')
    command=[str(executable),'--internal-command','capabilities'];env=os.environ.copy()
    from frozen_runtime import external_environment
    env=external_environment(env)
    if name.endswith('.exe') and os.name!='nt':
        if not wine_prefix:raise ValueError('Windows launcher capability check needs an isolated Wine prefix')
        prefix=Path(wine_prefix).resolve()
        if prefix==Path.home()/'.wine':raise ValueError('Use an isolated Wine prefix for launcher validation')
        env.update(WINEPREFIX=str(prefix),WINEDEBUG='-all');command=['wine',*command]
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=60)
    if result.returncode!=0:raise ValueError('Frozen launcher lacks current machine-readable capabilities')
    try:actual=json.loads(result.stdout)
    except (ValueError,TypeError) as error:raise ValueError('Invalid actual launcher capabilities') from error
    wanted={'kind':'codcoop_launcher','schema':1,'protocol':protocol,'core_features_supported':expected['core_features_supported'],
            'capabilities':list(CAPABILITIES),'source_graph_sha256':digest(expected)}
    if not isinstance(actual,dict) or type(actual.get('schema')) is not int or type(actual.get('protocol')) is not int or type(actual.get('core_features_supported')) is not int:raise ValueError('Invalid typed actual launcher capabilities')
    if actual!=wanted or required_features&expected['core_features_supported']!=required_features:
        raise ValueError('Actual frozen launcher graph/protocol/feature support differs from captured source')
    return {'executable_sha256':value['executable_sha256'],'source_graph_sha256':digest(expected),'actual':actual}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('source graph output exists; choose a fresh snapshot file')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(canonical(capture(args.root))+b'\n');return 0

if __name__=='__main__':raise SystemExit(main())
