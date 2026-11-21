"""Bounded static PE inspection and staging identity guards; no DLL execution."""
import json
from pathlib import Path
import sys
import tempfile
import importlib.util
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import runtime_protocol as runtime
from pe_fixtures import core_pe,malformed_core


class RuntimeProtocol(unittest.TestCase):
    def test_readonly_data_export_is_read_without_loading_dll(self):
        self.assertEqual(runtime.pe_data_u32(core_pe(9),'Coop_Protocol'),9)
        self.assertEqual(runtime.pe_data_u32(core_pe(7),'Coop_Protocol'),7)

    def test_missing_forwarded_writable_executable_and_malformed_exports_are_rejected(self):
        for kind in ['missing','forwarded','writable','executable','out_of_bounds','export_count','ordinal','truncated']:
            with self.subTest(kind=kind),self.assertRaises(ValueError):runtime.pe_data_u32(malformed_core(kind),'Coop_Protocol')
        for value in [b'',b'MZ'+b'\0'*62,b'x'*(runtime.MAX_PE_SIZE+1)]:
            with self.assertRaises(ValueError):runtime.pe_data_u32(value,'Coop_Protocol')

    def test_stager_requires_core_checker_and_manifest_protocol_to_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'codcoop_core.dll').write_bytes(core_pe(9))
            with mock.patch.object(runtime,'checker_capabilities',return_value={'schema':1,'protocol':9}):
                self.assertEqual(runtime.require_runtime_protocol(root,9)['core_protocol'],9)
                for version in [7,8]:
                    (root/'codcoop_core.dll').write_bytes(core_pe(version))
                    with self.assertRaisesRegex(ValueError,'must match'):runtime.require_runtime_protocol(root,9)
            (root/'codcoop_core.dll').write_bytes(core_pe(9))
            for version in [7,8]:
                with mock.patch.object(runtime,'checker_capabilities',return_value={'schema':1,'protocol':version}):
                    with self.assertRaisesRegex(ValueError,'must match'):runtime.require_runtime_protocol(root,9)

    @unittest.skipIf(sys.platform=='win32','Linux checker requires explicit private Wine prefix')
    def test_native_checker_never_uses_default_wine_prefix(self):
        with mock.patch.object(runtime.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'isolated'):runtime.checker_capabilities('suite-check.exe')
            run.assert_not_called()

    def test_stale_core_is_rejected_before_stager_creates_output(self):
        spec=importlib.util.spec_from_file_location('stage_protocol_test',Path(__file__).resolve().parents[1]/'tools/stage_suite.py')
        stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game=root/'game';game.mkdir();runtime_root=root/'runtime';runtime_root.mkdir()
            (runtime_root/'codcoop_core.dll').write_bytes(core_pe(7));output=root/'payload'
            with mock.patch.object(stage,'sha256',side_effect=[stage.YAP_ZIP_SHA,stage.YAP_EXTRAS_SHA]),mock.patch.object(runtime,'checker_capabilities',return_value={'protocol':9}),mock.patch.object(stage.tempfile,'mkdtemp') as temporary:
                with self.assertRaisesRegex(ValueError,'must match'):
                    stage.stage(game,output,root/'yap.zip',root/'extras.7z',runtime_source=runtime_root)
                temporary.assert_not_called()
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
