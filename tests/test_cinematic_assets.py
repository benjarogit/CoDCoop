"""Exercise the native bounded PK3 lookup with real central directories."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class CinematicAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('g++')
        if not compiler:
            raise unittest.SkipTest('native C++ compiler unavailable')
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        source = cls.work / 'probe.cpp'
        source.write_text('#include "cinematic_assets.h"\nint main(int n,char**v){return n==3 && campaign_cinematics::PackageHasMovie(v[1],v[2]) ? 0 : 1;}\n')
        cls.probe = cls.work / 'probe'
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'src'),
                        str(source), '-o', str(cls.probe)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def has_movie(self, package, name='video/cod_end.roq'):
        return subprocess.run([self.probe, package, name], check=False).returncode == 0

    def test_compressed_localized_member_is_found_case_insensitively(self):
        package = self.work / 'localized.pk3'
        with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('video/COD_END.roq', b'fixture movie payload' * 20)
            archive.comment = b'PK\x05\x06 fake signature in archive comment'
        self.assertTrue(self.has_movie(package))
        self.assertFalse(self.has_movie(package, 'video/missing.roq'))

    def test_invalid_placeholder_truncation_and_empty_member_fail_closed(self):
        package = self.work / 'invalid.pk3'
        package.write_bytes(b'\0')
        self.assertFalse(self.has_movie(package))
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('video/cod_end.roq', b'')
        self.assertFalse(self.has_movie(package))
        data = package.read_bytes()
        package.write_bytes(data[:-3])
        self.assertFalse(self.has_movie(package))

    def test_oversized_directory_is_rejected_before_allocation(self):
        package = self.work / 'bounded.pk3'
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('video/cod_end.roq', b'fixture')
        data = bytearray(package.read_bytes())
        data[-10:-6] = (0xffffffff).to_bytes(4, 'little')
        package.write_bytes(data)
        self.assertFalse(self.has_movie(package))
