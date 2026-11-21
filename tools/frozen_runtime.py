"""Keep a frozen GUI's private libraries out of external Wine/game processes."""
from contextlib import contextmanager
import os
import subprocess
import sys


def external_environment(environment=None):
    env = dict(os.environ if environment is None else environment)
    if not getattr(sys, 'frozen', False):
        return env
    # Retain ORIG so sanitizing an already prepared environment is idempotent.
    original = env.get('LD_LIBRARY_PATH_ORIG')
    if original:
        env['LD_LIBRARY_PATH'] = original
    else:
        env.pop('LD_LIBRARY_PATH', None)
    root = getattr(sys, '_MEIPASS', '')
    if root:
        root = os.path.normcase(os.path.abspath(root))

        def private(value):
            candidate = os.path.normcase(os.path.abspath(value))
            return candidate == root or candidate.startswith(root + os.sep)

        # Preserve custom user paths; remove only the bundle's private paths.
        for name in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'PATH'):
            if name not in env:
                continue
            retained = [part for part in env[name].split(os.pathsep) if not private(part)]
            if retained:
                env[name] = os.pathsep.join(retained)
            else:
                env.pop(name, None)
    for name in list(env):
        if name.startswith('_PYI_'):
            env.pop(name)
    return env


def _windows_kernel():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = [wintypes.DWORD, wintypes.LPWSTR]
    kernel.GetDllDirectoryW.restype = wintypes.DWORD
    kernel.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]
    kernel.SetDllDirectoryW.restype = wintypes.BOOL
    return kernel


@contextmanager
def external_dll_search():
    if not getattr(sys, 'frozen', False) or sys.platform != 'win32':
        yield
        return
    import ctypes
    kernel = _windows_kernel()
    size = kernel.GetDllDirectoryW(0, None)
    if size > 32767:
        raise OSError('invalid Windows DLL search directory')
    buffer = ctypes.create_unicode_buffer(size + 1)
    length = kernel.GetDllDirectoryW(len(buffer), buffer)
    if length >= len(buffer):
        raise OSError('Windows DLL search directory changed while reading')
    previous = buffer.value if length else None
    if not kernel.SetDllDirectoryW(None):
        raise OSError('could not restore normal Windows DLL search for the game')
    try:
        yield
    finally:
        if not kernel.SetDllDirectoryW(previous):
            raise OSError('could not restore the frozen worker DLL search directory')


def spawn_owned(command, **kwargs):
    kwargs['env'] = external_environment(kwargs.get('env'))
    process = None
    try:
        with external_dll_search():
            process = subprocess.Popen(command, **kwargs)
    except BaseException:
        # If restoring the worker DLL path failed after a successful spawn,
        # do not lose ownership of a game that the caller never received.
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            except OSError:
                pass
        raise
    return process
