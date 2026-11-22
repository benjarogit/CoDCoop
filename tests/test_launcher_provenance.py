import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import launcher_provenance as provenance

class LauncherGraph(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'source'
        for name in provenance.FILES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
        self.graph=provenance.capture(self.root)
        self.bundle=Path(self.temp.name)/'bundle';self.bundle.mkdir();self.exe=self.bundle/'CoD-Coop-Launcher';self.exe.write_bytes(b'not executable: mocked build fixture')
        self.receipt={'schema':1,'executable':self.exe.name,'executable_sha256':provenance.sha(self.exe),'source_graph':self.graph,'source_graph_sha256':provenance.digest(self.graph)}
        self.write_receipt()
    def write_receipt(self):(self.bundle/'launcher-build.json').write_bytes(provenance.canonical(self.receipt))
    def actual(self):return {'kind':'codcoop_launcher','schema':1,'protocol':self.graph['protocol'],'core_features_supported':self.graph['core_features_supported'],'capabilities':list(provenance.CAPABILITIES),'source_graph_sha256':provenance.digest(self.graph)}
    def require(self):return provenance.require_launcher(self.bundle,self.graph,self.graph['protocol'],self.graph['core_features_supported'])
    def test_captured_graph_mutations_cannot_be_silently_blessed(self):
        provenance.assert_sources(self.root,self.graph)
        (self.root/'tools/coop_party.py').write_text('changed while freezing')
        with self.assertRaisesRegex(ValueError,'changed'):provenance.assert_sources(self.root,self.graph)
        manifest=json.loads((self.root/'content/variants.json').read_text());manifest['protocol']+=1;(self.root/'content/variants.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'protocol'):provenance.capture(self.root)
    def test_actual_frozen_receipt_and_embedded_graph_required(self):
        with mock.patch.object(provenance.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps(self.actual()))) as run:
            result=self.require();self.assertEqual(result['source_graph_sha256'],provenance.digest(self.graph));self.assertEqual(run.call_args.args[0][1:],['--internal-command','capabilities'])
        for changes in ({'source_graph_sha256':'0'*64},{'protocol':7},{'core_features_supported':15},{'capabilities':[]},{'schema':True}):
            with mock.patch.object(provenance.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps(dict(self.actual(),**changes)))):
                with self.subTest(changes=changes),self.assertRaises(ValueError):self.require()
        self.exe.write_bytes(b'stale frozen executable')
        with mock.patch.object(provenance.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'executable'):self.require()
            run.assert_not_called()
    def test_old_receipt_missing_and_unregistered_executable_never_execute(self):
        (self.bundle/'launcher-build.json').unlink()
        with mock.patch.object(provenance.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'provenance'):self.require()
            run.assert_not_called()
        self.receipt['executable']='../arbitrary-command.exe';self.write_receipt()
        with mock.patch.object(provenance.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Unregistered'):self.require()
            run.assert_not_called()
    def test_actual_old_workers_are_rejected_readonly_without_provenance(self):
        for relative in ['run/worker9-api15-proof/linux','run/worker9-api15-proof/windows']:
            source=ROOT/relative
            if source.exists():
                with self.subTest(relative=relative),self.assertRaisesRegex(ValueError,'provenance'):provenance.require_launcher(source,self.graph,9,31)
    def test_stager_rejects_stale_launcher_before_any_payload_output(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('stage_graph_case',ROOT/'tools/stage_suite.py');stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
        graph_file=Path(self.temp.name)/'captured.json';graph_file.write_bytes(provenance.canonical(self.graph))
        (self.bundle/'launcher-build.json').unlink();game=Path(self.temp.name)/'game';game.mkdir();output=Path(self.temp.name)/'payload'
        with mock.patch.object(stage,'ROOT',self.root),mock.patch.object(stage,'sha256',side_effect=[stage.YAP_ZIP_SHA,stage.YAP_EXTRAS_SHA]),mock.patch.object(stage,'require_runtime_protocol'),mock.patch.object(stage.tempfile,'mkdtemp') as temporary:
            with self.assertRaisesRegex(ValueError,'provenance'):stage.stage(game,output,'yap.zip','extras.7z',launcher_source=self.bundle,source_graph=graph_file)
            temporary.assert_not_called()
        self.assertFalse(output.exists())

    def test_frozen_graph_comes_from_compiled_module_not_data_file(self):
        identity=mock.Mock(SOURCE_GRAPH_JSON=provenance.canonical(self.graph).decode())
        with mock.patch.object(sys,'frozen',True,create=True),mock.patch.object(provenance.importlib,'import_module',return_value=identity):
            self.assertEqual(provenance.capabilities(),self.actual())

if __name__=='__main__':unittest.main()
