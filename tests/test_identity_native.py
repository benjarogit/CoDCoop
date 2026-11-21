"""Opt-in native CryptoAPI/profile test in a private fixture game directory."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('COOP_WINE_PREFIX') and shutil.which('i686-w64-mingw32-g++') and shutil.which('wine'),
                     'requires isolated Wine prefix and MinGW compiler')
class NativeIdentity(unittest.TestCase):
    def test_real_profile_loader_and_prepared_qa_do_not_bypass_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            exe = game / 'identity.exe'
            subprocess.run(['i686-w64-mingw32-g++', '-std=c++17', '-O2', '-static',
                            str(ROOT / 'tests/test_suite_identity.cpp'), '-ladvapi32', '-o', str(exe)],
                           check=True, capture_output=True, text=True, timeout=60)
            (game / '.identity-test-owned').write_text('temporary native identity test')
            env = os.environ.copy()
            env.update(WINEPREFIX=str(Path(env['COOP_WINE_PREFIX']).resolve()), WINEDEBUG='-all')
            result = subprocess.run(['wine', str(exe)], cwd=game, env=env,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('QA isolation: PASS', result.stdout)
