"""Actual child exit status must survive an explicit supervisor stop."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import coop_session as session


class NativeStopStatus(unittest.TestCase):
    def test_real_nonzero_child_is_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(.1);raise SystemExit(7)'])
            try:
                with mock.patch.object(session,'send_command',return_value=True),mock.patch.object(session,'event') as event:
                    session.stop_owned(Path(directory),process,False)
                    session.stop_owned(Path(directory),process,False)
                    event.assert_called_once_with('game_stopped',pid=process.pid,code=7,forced=False)
                self.assertEqual(process.returncode,7)
            finally:
                if process.poll() is None:process.kill();process.wait()

    def test_already_exited_real_child_keeps_its_status(self):
        process=subprocess.Popen([sys.executable,'-c','raise SystemExit(9)']);process.wait()
        with mock.patch.object(session,'send_command') as command,mock.patch.object(session,'event') as event:
            session.stop_owned(Path('/unused'),process,False)
            command.assert_not_called()
            event.assert_called_once_with('game_stopped',pid=process.pid,code=9,forced=False)


if __name__=='__main__':unittest.main()
