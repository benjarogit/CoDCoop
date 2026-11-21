import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('linux_abi', Path(__file__).resolve().parents[1] / 'tools/check-linux-abi.py')
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


class LinuxAbiTests(unittest.TestCase):
    def test_newer_bundled_dependency_fails_floor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'old.so').write_bytes(b'\x7fELFfixture')
            (root / 'new.so').write_bytes(b'\x7fELFfixture')
            with mock.patch.object(abi.subprocess, 'check_output', side_effect=['GLIBC_2.44', 'GLIBC_2.35']):
                result = abi.check(root)
            self.assertFalse(result['ok'])
            self.assertEqual(result['maximum_required'], '2.44')
            self.assertEqual(len(result['violations']), 1)

    def test_supported_floor_and_static_runtime_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'runtime').write_bytes(b'\x7fELFfixture')
            with mock.patch.object(abi.subprocess, 'check_output', return_value='GLIBC_2.34 GLIBC_2.35 GLIBCXX_3.4.30'):
                self.assertTrue(abi.check(root)['ok'])
            with mock.patch.object(abi.subprocess, 'check_output', return_value='No version information'):
                self.assertTrue(abi.check(root)['ok'])

    def test_empty_or_non_elf_bundle_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'readme').write_text('No executable here')
            self.assertFalse(abi.check(root)['ok'])
