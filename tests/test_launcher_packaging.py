import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launcher_builder', Path(__file__).resolve().parents[1] / 'tools/build-launcher.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class LauncherPackagingTests(unittest.TestCase):
    def test_dpkg_owner_suffix_cannot_reach_installer_payload_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / 'licenses/linux-packages/libbz2-1.0:amd64'
            # Windows cannot create the Linux path that the validator must reject.
            with patch.object(type(root), 'rglob', return_value=iter([bad])):
                with self.assertRaisesRegex(ValueError, 'unsafe installation path'):
                    builder.validate_bundle_paths(root)
            good = bad.with_name('libbz2-1.0_amd64')
            good.mkdir(parents=True)
            (good / 'copyright').write_text('fixture copyright')
            builder.validate_bundle_paths(root)
