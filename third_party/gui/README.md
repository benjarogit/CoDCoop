# Launcher runtime notices

The native launcher bundles CPython, PySide6/Shiboken6 and dynamically loaded
Qt libraries. PyInstaller constructs the bundle; its bootloader exception is
included in `PyInstaller-COPYING.txt`. The original copyright/license headers
for the included PySide6 and Shiboken6 bindings are retained in this folder.
The open-source binding license is LGPL-3.0-only (alternatively GPL-2.0-only or
GPL-3.0-only); the bundled LGPL and GPL texts include their complete terms.
The presence of Qt's alternative commercial-license text grants no commercial
license to this project or its users.

Upstream source and exact-version retrieval:

- CPython: https://github.com/python/cpython (matching the `runtime-notices.json`
  Python version; official Windows embedded runtime uses Python 3.12.10).
- PySide6/Shiboken6 6.12.0:
  https://code.qt.io/cgit/pyside/pyside-setup.git/?h=6.12.0
- Qt 6.12.0: https://code.qt.io/cgit/qt/qtbase.git/?h=6.12.0 and the matching
  module repositories under https://code.qt.io/cgit/qt/.
- PyInstaller 6.22.3: https://github.com/pyinstaller/pyinstaller/tree/v6.22.3
- Altgraph 0.17.5: https://github.com/ronaldoussoren/altgraph

`tools/build-launcher.py` writes actual runtime versions and collects installed
distribution notices into each generated bundle's `licenses` directory. Linux
builds additionally retain the installed package metadata and available license
directories of the actual bundled shared libraries/plugins. Distribution-added
patches and source packages can be retrieved from the package sources identified
there. License texts are included as supplied, including alternatives and
third-party notices; their inclusion does not assert that every license applies
to every executable.

Qt is dynamically linked. The directory bundle keeps its Qt/shared libraries
as separate files; compatible replacements can be installed there. Launcher
source and build instructions are in `tools/launch-gui.py` and
`tools/build-launcher.py`, and `tools/requirements-launcher.txt` pins its Python
dependencies. No changes to Qt, PySide6, Shiboken6, CPython or PyInstaller are
made by this project. Linux distribution changes, if any, are described by the
captured package metadata. Native Windows hardware testing is a separate
acceptance item.
