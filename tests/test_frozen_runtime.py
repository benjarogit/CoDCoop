import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import frozen_runtime as runtime


class FrozenRuntimeTests(unittest.TestCase):
    def test_source_runner_environment_is_preserved(self):
        env = {'LD_LIBRARY_PATH': '/user/libs', 'QT_PLUGIN_PATH': '/user/plugins', 'WINEPREFIX': '/wine'}
        with mock.patch.object(runtime.sys, 'frozen', False, create=True):
            self.assertEqual(runtime.external_environment(env), env)

    def test_frozen_restores_user_library_paths_and_preserves_wine_proton_settings(self):
        env = {'LD_LIBRARY_PATH': '/bundle/_internal:/user/libs', 'LD_LIBRARY_PATH_ORIG': '/user/libs',
               'QT_PLUGIN_PATH': os.pathsep.join(('/bundle/_internal/PySide6/Qt/plugins', '/user/qt')),
               'QML2_IMPORT_PATH': '/bundle/_internal/qml', 'PATH': os.pathsep.join(('/bundle/_internal', '/usr/bin', '/user/bin')),
               '_PYI_APPLICATION_HOME_DIR': '/bundle/_internal', 'WINEPREFIX': '/wine',
               'PROTON_LOG': '1', 'STEAM_COMPAT_DATA_PATH': '/proton/data', 'DXVK_HUD': 'fps'}
        with mock.patch.object(runtime.sys, 'frozen', True, create=True), \
             mock.patch.object(runtime.sys, '_MEIPASS', '/bundle/_internal', create=True):
            clean = runtime.external_environment(env)
            self.assertEqual(clean['LD_LIBRARY_PATH'], '/user/libs')
            self.assertEqual(clean['QT_PLUGIN_PATH'], '/user/qt')
            self.assertEqual(clean['PATH'], os.pathsep.join(('/usr/bin', '/user/bin')))
            self.assertNotIn('QML2_IMPORT_PATH', clean)
            self.assertNotIn('_PYI_APPLICATION_HOME_DIR', clean)
            self.assertEqual(runtime.external_environment(clean), clean)
            for name in ('WINEPREFIX', 'PROTON_LOG', 'STEAM_COMPAT_DATA_PATH', 'DXVK_HUD'):
                self.assertEqual(clean[name], env[name])
            self.assertIn('/bundle', env['LD_LIBRARY_PATH']) # caller dictionary unchanged

    def test_no_original_library_path_removes_only_bundle_search_state(self):
        with mock.patch.object(runtime.sys, 'frozen', True, create=True), \
             mock.patch.object(runtime.sys, '_MEIPASS', '/bundle', create=True):
            clean = runtime.external_environment({'LD_LIBRARY_PATH': '/bundle', 'QT_PLUGIN_PATH': '/bundle-other', 'CUSTOM': 'yes'})
        self.assertNotIn('LD_LIBRARY_PATH', clean)
        self.assertEqual(clean['QT_PLUGIN_PATH'], '/bundle-other')
        self.assertEqual(clean['CUSTOM'], 'yes')

    def test_windows_search_scope_restores_after_success_and_failed_spawn(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                calls = []
                kernel = mock.Mock()
                def get_directory(size, buffer):
                    if not size:
                        return len('C:\\bundle') + 1
                    buffer.value = 'C:\\bundle'
                    return len(buffer.value)
                kernel.GetDllDirectoryW.side_effect = get_directory
                kernel.SetDllDirectoryW.side_effect = lambda directory: calls.append(directory) or 1
                with mock.patch.object(runtime.sys, 'frozen', True, create=True), \
                     mock.patch.object(runtime.sys, 'platform', 'win32'), \
                     mock.patch.object(runtime, '_windows_kernel', return_value=kernel), \
                     mock.patch.object(runtime.subprocess, 'Popen', side_effect=OSError('fixture spawn failure') if failure else None) as popen:
                    if failure:
                        with self.assertRaisesRegex(OSError, 'fixture spawn failure'):
                            runtime.spawn_owned(['fixture-game'], env={'WINEPREFIX': '/wine'})
                    else:
                        runtime.spawn_owned(['fixture-game'], env={'WINEPREFIX': '/wine'})
                    popen.assert_called_once()
                self.assertEqual(calls, [None, 'C:\\bundle'])

    def test_windows_search_cannot_be_reset_prevents_spawn(self):
        kernel = mock.Mock()
        kernel.GetDllDirectoryW.return_value = 0
        kernel.SetDllDirectoryW.return_value = 0
        with mock.patch.object(runtime.sys, 'frozen', True, create=True), \
             mock.patch.object(runtime.sys, 'platform', 'win32'), \
             mock.patch.object(runtime, '_windows_kernel', return_value=kernel), \
             mock.patch.object(runtime.subprocess, 'Popen') as popen:
            with self.assertRaises(OSError):
                runtime.spawn_owned(['fixture-game'])
            popen.assert_not_called()

    def test_failed_restoration_does_not_orphan_successfully_spawned_game(self):
        kernel = mock.Mock()
        kernel.GetDllDirectoryW.return_value = 0
        kernel.SetDllDirectoryW.side_effect = [1, 0]
        process = mock.Mock()
        process.poll.return_value = None
        with mock.patch.object(runtime.sys, 'frozen', True, create=True), \
             mock.patch.object(runtime.sys, 'platform', 'win32'), \
             mock.patch.object(runtime, '_windows_kernel', return_value=kernel), \
             mock.patch.object(runtime.subprocess, 'Popen', return_value=process):
            with self.assertRaisesRegex(OSError, 'restore the frozen worker'):
                runtime.spawn_owned(['fixture-game'])
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
