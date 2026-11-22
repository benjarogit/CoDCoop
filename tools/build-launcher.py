#!/usr/bin/env python3
"""Build the native campaign launcher on its target OS with PyInstaller.

Install tools/requirements-launcher.txt in an isolated build environment first.
This produces a self-contained directory, not an AppImage or a signed installer.
The AppImage/package build wraps this directory without changing its contents.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys


def validate_bundle_paths(bundle):
    for path in bundle.rglob('*'):
        relative = path.relative_to(bundle).as_posix()
        portable = PurePosixPath(relative.replace('\\', '/'))
        if ':' in relative or portable.is_absolute() or '..' in portable.parts:
            raise ValueError('bundle contains an unsafe installation path: ' + relative)


def collect_notices(root, bundle, analysis_toc=None):
    """Keep runtime and distro notices with the actual directory bundle."""
    notices = bundle / 'licenses'
    shutil.copytree(root / 'third_party/gui', notices / 'upstream', dirs_exist_ok=True)
    inventory = {'python': sys.version, 'platform': sys.platform, 'distributions': {}, 'linux_packages': {}}
    from PySide6.QtCore import qVersion
    inventory['qt_version'] = qVersion()
    for name in ('PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'PySide6_Pdf', 'PySide6_WebEngine', 'shiboken6',
                 'PyInstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'packaging', 'pefile', 'cryptography', 'cffi', 'pycparser'):
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        inventory['distributions'][name] = {'version': dist.version,
            'license': dist.metadata.get('License', ''), 'copyright': dist.metadata.get('Author', '')}
        for relative in dist.files or ():
            if not any('license' in p.lower() or 'copying' in p.lower() for p in relative.parts):
                continue
            source = Path(dist.locate_file(relative))
            if source.is_file():
                safe_parts = [part for part in relative.parts if part not in ('.', '..', '/', '\\')]
                target = notices / 'python-distributions' / name / Path(*safe_parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    # Identify the actual system libraries selected by PyInstaller, retaining
    # distro patches/source versions and their supplied copyright documents.
    if sys.platform.startswith('linux') and (shutil.which('pacman') or shutil.which('dpkg-query')):
        owners = set()
        toc = analysis_toc or root / ('build/launcher-work-' + sys.platform) / 'CoD-Coop-Launcher/Analysis-00.toc'
        debian = not shutil.which('pacman') and shutil.which('dpkg-query')
        if toc.is_file():
            import ast
            def paths(value):
                if isinstance(value, str) and value.startswith('/'):
                    yield Path(value)
                elif isinstance(value, (tuple, list)):
                    for item in value:
                        yield from paths(item)
            for source in set(paths(ast.literal_eval(toc.read_text()))):
                if not source.is_file():
                    continue
                command = ['dpkg-query', '-S'] if debian else ['pacman', '-Qoq']
                result = subprocess.run(command + [str(source)], capture_output=True, text=True)
                if debian and result.returncode and str(source).startswith('/usr/lib/'):
                    result = subprocess.run(command + [str(source)[4:]], capture_output=True, text=True)
                if result.returncode == 0:
                    if debian:
                        for line in result.stdout.splitlines():
                            owners.update(line.split(': ', 1)[0].split(', '))
                    else:
                        owners.update(result.stdout.split())
        for owner in sorted(owners):
            command = ['dpkg-query', '-W', '-f=${binary:Package}\n${Version}\n${source:Package}\n${source:Version}\n${Homepage}\n', owner] if debian else ['pacman', '-Qi', owner]
            metadata = subprocess.run(command, capture_output=True, text=True, check=True).stdout
            inventory['linux_packages'][owner] = metadata
            # Debian's :amd64 owner suffix is metadata, not a portable pathname.
            directory_name = re.sub(r'[^A-Za-z0-9._-]', '_', owner)
            inventory.setdefault('linux_notice_directories', {})[owner] = directory_name
            if debian:
                source = Path('/usr/share/doc') / owner.split(':', 1)[0] / 'copyright'
                if source.is_file():
                    target = notices / 'linux-packages' / directory_name / 'copyright'
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            else:
                source = Path('/usr/share/licenses') / owner
                if source.is_dir():
                    shutil.copytree(source, notices / 'linux-packages' / directory_name, dirs_exist_ok=True)
        common = Path('/usr/share/common-licenses')
        if debian and common.is_dir():
            shutil.copytree(common, notices / 'common-licenses', dirs_exist_ok=True)
    (notices / 'runtime-notices.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    validate_bundle_paths(bundle)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    for package, expected in (("PySide6", "6.12.0"), ("PyInstaller", "6.22.3"), ("cryptography", "50.0.2")):
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            parser.error("install tools/requirements-launcher.txt in the build environment first")
        if actual != expected:
            parser.error(f"{package} {expected} required; found {actual}")
    if not (root / "tools/coop_session.py").is_file():
        parser.error("coop_session.py is required before packaging the launcher")
    catalog = root / 'campaign_patches/uf_equipment_catalog.json'
    if not catalog.is_file():
        parser.error('the source-derived UF equipment catalog is required for launcher preferences')
    destination = (args.output or root / "build/launcher").resolve()
    name = "CoD-Coop-Launcher"
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
               "--name", name, "--distpath", str(destination),
               "--workpath", str(root / ("build/launcher-work-" + sys.platform)),
               "--specpath", str(root / "build/launcher-spec"),
               "--paths", str(root / "tools"), "--hidden-import", "coop_suite", "--hidden-import", "coop_session", "--hidden-import", "coop_party", "--hidden-import", "party_native_bridge",
               "--add-data", str(catalog) + os.pathsep + ".",
               str(root / "tools/launch-gui.py")]
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode:
        return result.returncode
    executable = destination / name / (name + (".exe" if sys.platform == "win32" else ""))
    if not executable.is_file():
        parser.error("PyInstaller did not produce the expected launcher")
    collect_notices(root, destination / name)
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
