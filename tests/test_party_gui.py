import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from party_gui import create_dialog,TEXT
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QProcess
    HAS_QT=True
except ImportError:HAS_QT=False

@unittest.skipUnless(HAS_QT,'PySide6 unavailable')
class PartyUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_bilingual_actual_controls_fail_closed_without_native_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            for language in ('en','de'):
                captured=[]
                def factory(kind,args):captured.append((kind,args));return ['/deliberately-missing-party-worker']
                d=create_dialog(None,language=language,game=Path(directory)/'game',map_name='pathfinder',difficulty=2,preferences=lambda:{'mode':'automatic'},command_factory=factory,settings_directory=Path(directory)/language)
                d.resize(680,720);d.show();self.app.processEvents()
                self.assertEqual(d.windowTitle(),TEXT[language]['title'])
                self.assertFalse(d.launch.isEnabled());self.assertFalse(d.confirm.isEnabled());self.assertFalse(d.submit.isEnabled())
                d.create.click();self.app.processEvents()
                self.assertEqual(captured[0][0],'party');self.assertIn('--host',captured[0][1]);self.assertIn('2',captured[0][1]);self.assertNotIn('--runner',captured[0][1])
                self.assertEqual(d.invite_path.stat().st_mode&0o777,0o600)
                d.reject();self.app.processEvents();self.assertFalse(d.invite_path.exists())
    def test_real_gui_workers_create_join_submit_and_confirm(self):
        import importlib.util, socket, time, zipfile
        from test_coop_suite import SuiteTest, suite
        spec=importlib.util.spec_from_file_location('party_launch_gui',ROOT/'tools/launch-gui.py')
        launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
        fixtures=[];dialogs=[]
        quarantine=tempfile.TemporaryDirectory();environment=mock.patch.dict(os.environ,{'XDG_CONFIG_HOME':quarantine.name,'LOCALAPPDATA':quarantine.name});environment.start()
        try:
            for index in range(2):
                fixture=SuiteTest();fixture.setUp();fixtures.append(fixture)
                with zipfile.ZipFile(fixture.game/'UnitedFronts/lobby_fixture.pk3','w') as archive:archive.writestr('maps/pathfinder.bsp',b'fixture map, never executed')
                suite.seal_installation(fixture.game)
                prefs={'schema':1,'mode':'manual','manual':{'family':'american','slots':{'primary':9,'secondary':6,'pistol':22,'grenade':34}}}
                d=create_dialog(None,language='en' if index==0 else 'de',game=fixture.game,map_name='pathfinder',difficulty=2,preferences=lambda:prefs,command_factory=launcher.worker_command,settings_directory=fixture.game.parent/('private-party-'+str(index)))
                dialogs.append(d);d.resize(680,720);d.show()
            host,peer=dialogs
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();host.port.setValue(port)
            def wait(condition):
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    self.app.processEvents()
                    if condition():return
                    time.sleep(.02)
                self.fail('Actual GUI party worker timed out: '+host.status.text()+' / '+peer.status.text())
            host.campaign.setCurrentIndex(host.campaign.findData('american'))
            host.create.click();wait(lambda:bool(host.invite.text()))
            peer.invite.setText(host.invite.text());peer.join.click()
            wait(lambda:all(d.view and len(d.view['members'])==2 for d in dialogs))
            for d in dialogs:
                revision=d.view['roster']['revision'];d.submit.click()
                wait(lambda:all(x.view['roster']['revision']>revision for x in dialogs))
            host.confirm.click();peer.confirm.click()
            wait(lambda:all(len(d.view['confirmed_slots'])==2 for d in dialogs))
            for d in dialogs:
                self.assertFalse(d.launch.isEnabled());self.assertFalse(d.view['runtime_ready'])
                self.assertEqual(d.view['roster']['world']['difficulty'],'2')
            if os.environ.get('COOP_PARTY_QA_SCREENSHOTS'):
                out=Path(os.environ['COOP_PARTY_QA_SCREENSHOTS']);out.mkdir(parents=True,exist_ok=True)
                for lang,d in zip(('en','de'),dialogs):
                    self.assertLessEqual(d.height(),720);self.assertTrue(d.grab().save(str(out/(lang+'.png'))))
        finally:
            for d in reversed(dialogs):d.reject();self.app.processEvents()
            for fixture in fixtures:fixture.doCleanups()
            environment.stop();quarantine.cleanup()

    def test_network_confirmation_is_not_native_readiness(self):
        # The start action remains disabled even with authenticated complete
        # confirmations: no test/user preference can assert the missing ACK.
        with tempfile.TemporaryDirectory() as directory:
            d=create_dialog(None,language='en',game=Path(directory),map_name='noville',difficulty=1,preferences=lambda:{'mode':'automatic'},command_factory=lambda *a:[],settings_directory=Path(directory))
            d.view={'confirmed_slots':[0,1,2,3],'runtime_ready':False}
            self.assertFalse(d.launch.isEnabled());self.assertIn('bootstrap',d.blocked.text());d.reject()

if __name__=='__main__':unittest.main()
