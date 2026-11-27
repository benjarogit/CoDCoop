"""Check that the Steam shortcut path cannot consume supervised game arguments."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux launcher wrapper')
class LauncherWrapperTests(unittest.TestCase):
    def test_campaign_and_join_arguments_are_preserved(self):
        source = Path(__file__).resolve().parents[1] / 'tools/umu-run'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wrapper = root / 'wrapper'
            wrapper.write_text(source.read_text().replace('/usr/bin/umu-run', str(root / 'runner'))
                               .replace('/tmp/umu-run-args.log', str(root / 'wrapper.log')))
            scripts = {
                'steam': 'touch "$STEAM_TRIED"\n',
                'pgrep': '[ "$1" = "-x" ]\n',
                'cod-coop-steam-id': 'echo 123456789\n',
                'runner': 'printf "%s\\n" "$@"\n',
            }
            for name, body in scripts.items():
                script = root / name
                script.write_text('#!/bin/sh\n' + body)
                script.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       STEAM_TRIED=str(root / 'steam-started'))
            env.pop('COD_COOP_NO_STEAM', None)
            argv = ['My Game/CoDUOSP.exe', '+set', 'fs_game', 'sp_improved',
                    '+coopjoin', '192.168.1.2:28960']
            result = subprocess.run(['sh', str(wrapper), *argv], env=env, text=True,
                                    capture_output=True, timeout=4, check=True)
            self.assertEqual(result.stdout.splitlines(), argv)
            self.assertFalse((root / 'steam-started').exists())
