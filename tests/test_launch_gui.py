"""Launcher behavior checks; no game process or personal settings are used."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("launch_gui", ROOT / "tools/launch-gui.py")
gui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gui)
try:
    from PySide6.QtCore import QProcess, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    HAS_QT = True
except ImportError:
    HAS_QT = False


class WorkerCommands(unittest.TestCase):
    def test_source_worker_uses_registered_script_without_shell(self):
        command = gui.worker_command("session", ["--game", "a path with spaces", "--variant", "uo"])
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]).name, "coop_session.py")
        self.assertEqual(command[2:4], ["--game", "a path with spaces"])
        with self.assertRaises(ValueError):
            gui.worker_command("unknown", [])

    def test_frozen_worker_reenters_bundle_dispatch(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            command = gui.worker_command("suite", ["check", "--game", "x"])
        self.assertEqual(command[1:], ["--internal-command", "suite", "check", "--game", "x"])


@unittest.skipUnless(HAS_QT, "PySide6 GUI dependency is not installed")
class LauncherBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["CoDCoop launcher tests"])

    def run_window(self, operation, complete=lambda window: True, preferences=None):
        failures = []
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.ini"
            if preferences is not None:
                settings.with_name('equipment.json').write_text(preferences if isinstance(preferences,str) else json.dumps(preferences))
            started = time.monotonic()

            def finish(window):
                if window.process.state() != window.process.ProcessState.NotRunning:
                    window.process.kill()
                    window.process.waitForFinished(3000)
                window.set_busy(False)
                window.close()
                self.app.quit()

            def poll(window):
                try:
                    if complete(window):
                        finish(window)
                        return
                    if time.monotonic() - started > 8:
                        raise AssertionError("GUI operation timed out")
                    QTimer.singleShot(20, lambda: poll(window))
                except Exception as error:
                    failures.append(error)
                    finish(window)

            def begin():
                window = next(w for w in self.app.topLevelWidgets() if hasattr(w, "validate") and w.isVisible())
                try:
                    operation(window)
                    poll(window)
                except Exception as error:
                    failures.append(error)
                    finish(window)

            QTimer.singleShot(0, begin)
            gui.main(["--settings-file", str(settings), "--language", "en"])
        if failures:
            raise failures[0]

    def test_join_requires_host_before_starting_worker(self):
        def operation(window):
            window.folder.setText("/not-a-real-coop-installation")
            window.mode.setCurrentIndex(1)
            window.host.clear()
            window.validate(True)
            self.assertEqual(window.status_key, "need_host")
            self.assertFalse(window.busy)
            self.assertFalse(window.session)
        self.run_window(operation)

    def test_new_launcher_defaults_to_improved_main_campaign(self):
        def operation(window):
            self.assertEqual(gui.VARIANTS[window.campaigns.currentRow()], "sp_improved")
            self.assertIn("CoD + UO", window.variant_label.text())
            self.assertIn("SP Improved 1.5", window.description.text())
        self.run_window(operation)

    def test_verified_summary_follows_variant_and_is_cleared_for_another_folder(self):
        def operation(window):
            window.folder.setText('/checked-game')
            window.verified_summary = {'suite_version': '0.6.0-test', 'local_saves': {
                'cod1': {'latest': {'name': 'cod-checkpoint.svg', 'modified': '2026-11-21T12:00:00+00:00'}},
                'sp_improved': {'latest': None}}}
            window.campaigns.setCurrentRow(gui.VARIANTS.index('cod1'))
            self.assertIn('0.6.0-test', window.installation_info.text())
            self.assertIn('cod-checkpoint.svg', window.save_info.text())
            window.campaigns.setCurrentRow(gui.VARIANTS.index('sp_improved'))
            self.assertNotIn('cod-checkpoint.svg', window.save_info.text())
            window.mode.setCurrentIndex(1)
            self.assertIn("host's progress", window.save_info.text())
            window.folder.setText('/different-game')
            self.assertIsNone(window.verified_summary)
            self.assertNotIn('0.6.0-test', window.installation_info.text())
            self.assertEqual(window.save_info.text(), '')
        self.run_window(operation)

    def test_invalid_installation_cannot_launch_a_session(self):
        def operation(window):
            window.folder.setText("/not-a-real-coop-installation")
            window.validate(True)
            self.assertTrue(window.busy)
            self.assertFalse(window.start.isEnabled())

        def complete(window):
            if window.busy:
                return False
            self.assertEqual(window.status_key, "invalid")
            self.assertFalse(window.session)
            self.assertTrue(window.details.isVisible())
            self.assertTrue(window.start.isEnabled())
            result = json.loads(window.output)
            self.assertIs(result["ok"], False)
            self.assertTrue(result["errors"])
            return True
        self.run_window(operation, complete)

    def test_host_switch_is_explicit_and_uses_registered_variant_id(self):
        def operation(window):
            window.session = True
            window.active_variant = "cod1"
            window.set_busy(True)
            with mock.patch.object(window.process, "write", return_value=1) as write:
                window.campaigns.setCurrentRow(1)
                write.assert_not_called()  # selecting alone must not change the group
                with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                    window.switch_campaign()
                write.assert_not_called()
                with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                    window.switch_campaign()
                self.assertEqual(json.loads(bytes(write.call_args.args[0])), {"action": "switch", "variant": "uo", "map": "", "difficulty": 1})
                self.assertTrue(window.switching)
                self.assertFalse(window.switch.isEnabled())
            window.set_busy(False)
        self.run_window(operation)

    def test_host_start_passes_numeric_difficulty_to_supervisor(self):
        def operation(window):
            self.assertEqual(window.difficulty.currentData(), 1)
            window.folder.setText("/checked-test-installation")
            window.difficulty.setCurrentIndex(2)
            window.pending_launch = True
            window.output = '{"ok":true}'
            with mock.patch.object(window, "read_output"), mock.patch.object(window, "run_worker") as run:
                window.finished(0, QProcess.ExitStatus.NormalExit)
            kind, arguments = run.call_args.args
            self.assertEqual(kind, "session")
            self.assertEqual(arguments[arguments.index("--difficulty") + 1], "2")
            window.set_busy(False)
        self.run_window(operation)

    def test_switch_includes_target_mission_and_numeric_difficulty(self):
        def operation(window):
            window.session = True
            window.active_variant = "cod1"
            window.set_busy(True)
            self.assertTrue(window.difficulty.isEnabled())
            self.assertTrue(window.map.isEnabled())
            window.campaigns.setCurrentRow(3)
            window.map.setText("pathfinder")
            window.difficulty.setCurrentIndex(3)
            with mock.patch.object(window.process, "write", return_value=1) as write:
                with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as question:
                    window.switch_campaign()
                self.assertIn("pathfinder", question.call_args.args[2])
                self.assertIn("Veteran", question.call_args.args[2])
                self.assertEqual(json.loads(bytes(write.call_args.args[0])),
                                 {"action": "switch", "variant": "united_fronts", "map": "pathfinder", "difficulty": 3})
            window.set_busy(False)
        self.run_window(operation)

    def test_joiner_cannot_request_group_switch(self):
        def operation(window):
            window.mode.setCurrentIndex(1)
            window.session = True
            window.active_variant = "cod1"
            window.set_busy(True)
            window.campaigns.setCurrentRow(1)
            with mock.patch.object(window.process, "write", return_value=1) as write:
                window.switch_campaign()
                write.assert_not_called()
            self.assertFalse(window.campaigns.isEnabled())
            self.assertFalse(window.difficulty.isEnabled())
            self.assertFalse(window.map.isEnabled())
            self.assertFalse(window.switch.isVisible())
            window.set_busy(False)
        self.run_window(operation)

    def equipment_dialog(self, window, operation):
        failures=[]
        def inspect():
            dialog=window.equipment_dialog
            try: operation(dialog)
            except Exception as error: failures.append(error)
            finally:
                if dialog.isVisible(): dialog.reject()
        QTimer.singleShot(0,inspect)
        window.edit_equipment()
        if failures: raise failures[0]

    def test_equipment_dialog_saves_only_local_preferences_and_excludes_hidden_families(self):
        def operation(window):
            self.assertFalse(window.equipment_button.isVisible())
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertTrue(window.equipment_button.isVisible())
            self.assertIn('cannot apply',window.equipment_note.text())
            def select(dialog):
                self.assertEqual(dialog.mode.currentData(),'automatic')
                self.assertEqual(dialog.family.count(),5)
                self.assertEqual(dialog.family.findData('polish'),-1)
                dialog.mode.setCurrentIndex(1)
                for slot,value in {'primary':9,'secondary':9,'pistol':22,'grenade':34}.items():
                    dialog.slots[slot].setCurrentIndex(dialog.slots[slot].findData(value))
                self.assertTrue(dialog.duplicate_note.isVisible())
                dialog.save.click()
            with mock.patch.object(window,'run_worker') as run:
                self.equipment_dialog(window,select)
                run.assert_not_called()
            value=json.loads(window.equipment_path.read_text())
            self.assertEqual(value['manual']['slots'],{'primary':9,'secondary':9,'pistol':22,'grenade':34})
            self.assertEqual(value['mode'],'manual')
            self.assertIn('not applied',window.equipment_note.text())
        self.run_window(operation)

    def test_manual_equipment_preferences_are_not_forwarded_to_unsupported_session(self):
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            window.equipment_preferences['mode']='manual'
            window.equipment_preferences['manual']['slots']['primary']=9
            window.folder.setText('/checked-test-installation')
            window.pending_launch=True;window.output='{"ok":true}'
            with mock.patch.object(window,'read_output'),mock.patch.object(window,'run_worker') as run:
                window.finished(0,QProcess.ExitStatus.NormalExit)
            self.assertEqual(run.call_args.args[0],'session')
            self.assertNotIn('equipment',' '.join(run.call_args.args[1]))
            self.assertIn('cannot apply',window.equipment_note.text())
            self.assertFalse(window.equipment_button.isEnabled())
            window.set_busy(False)
        self.run_window(operation)

    def test_cancelled_equipment_changes_do_not_persist_and_automatic_keeps_manual_draft(self):
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            def cancel(dialog):
                dialog.mode.setCurrentIndex(1)
                dialog.slots['primary'].setCurrentIndex(dialog.slots['primary'].findData(9))
                dialog.reject()
            self.equipment_dialog(window,cancel)
            self.assertFalse(window.equipment_path.exists())
            self.assertEqual(window.equipment_preferences['mode'],'automatic')
            def save_automatic(dialog):
                dialog.mode.setCurrentIndex(1)
                dialog.slots['primary'].setCurrentIndex(dialog.slots['primary'].findData(9))
                dialog.mode.setCurrentIndex(0)
                dialog.save.click()
            self.equipment_dialog(window,save_automatic)
            value=json.loads(window.equipment_path.read_text())
            self.assertEqual(value['mode'],'automatic')
            self.assertEqual(value['manual']['slots']['primary'],9)
        self.run_window(operation)

    def test_missing_equipment_catalog_does_not_break_existing_launcher_flow(self):
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertFalse(window.equipment_button.isEnabled())
            self.assertIn('catalog unavailable',window.equipment_note.text())
            self.assertTrue(window.start.isEnabled())
        with mock.patch.object(gui,'load_equipment_catalog',side_effect=ValueError('bad catalog')):
            self.run_window(operation)

    def test_saved_personal_kit_is_loaded_on_launcher_start(self):
        value=gui.equipment.default_preferences(gui.load_equipment_catalog())
        value['mode']='manual';value['manual']['slots']['primary']=9
        def operation(window):
            self.assertEqual(window.equipment_preferences,value)
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            def inspect(dialog):
                self.assertEqual(dialog.mode.currentData(),'manual')
                self.assertEqual(dialog.slots['primary'].currentData(),9)
            self.equipment_dialog(window,inspect)
        self.run_window(operation,preferences=value)

    def test_corrupt_preferences_remain_untouched_until_explicit_save(self):
        def operation(window):
            self.assertEqual(window.equipment_error,'load_error')
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertIn('could not be loaded',window.equipment_note.text())
            self.equipment_dialog(window,lambda dialog:dialog.reject())
            self.assertEqual(window.equipment_path.read_text(),'{broken')
        self.run_window(operation,preferences='{broken')

    def test_future_roster_capability_displays_read_only_roles_and_world_change_clears_ready(self):
        from test_uf_equipment_roster_view import fixture
        import uf_equipment_roster as contract
        catalog,state,capability=fixture()
        snapshot=contract.public_snapshot(state,catalog)
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertFalse(window.roster_button.isVisible())
            self.assertTrue(window.present_authoritative_roster(snapshot,capability))
            self.assertIn('4/4',window.roster_button.text())
            failures=[]
            def inspect():
                try:
                    dialog=window.roster_dialog
                    self.assertEqual(len(dialog.rows),4)
                    self.assertIn('Host',dialog.rows[0].text())
                    self.assertIn('Teammate',dialog.rows[1].text())
                    self.assertIn('unavailable',dialog.summary.text())
                    changed=contract.update_world(state,catalog,0,{**state['world'],'map':'tropez'},state['revision'])
                    self.assertTrue(window.present_authoritative_roster(contract.public_snapshot(changed,catalog),capability))
                    self.assertTrue(all('Confirmation pending' in row.text() for row in dialog.rows))
                    self.assertIn('tropez',dialog.world.text())
                    self.assertIn('0/4',window.roster_button.text())
                except Exception as error:failures.append(error)
                finally:window.roster_dialog.reject()
            QTimer.singleShot(0,inspect)
            with mock.patch.object(window,'send_control') as control:
                window.show_authoritative_roster()
                control.assert_not_called()
            if failures:raise failures[0]
        self.run_window(operation)

    def test_stale_roster_is_not_reenabled_by_replaying_it_after_a_rejection(self):
        from test_uf_equipment_roster_view import fixture
        import uf_equipment_roster as contract
        catalog,state,capability=fixture();old=contract.public_snapshot(state,catalog)
        changed=contract.update_world(state,catalog,0,{**state['world'],'map':'tropez'},state['revision'])
        current=contract.public_snapshot(changed,catalog)
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertTrue(window.present_authoritative_roster(current,capability))
            self.assertFalse(window.present_authoritative_roster(old,capability))
            self.assertIsNone(window.authoritative_roster)
            self.assertFalse(window.roster_button.isVisible())
            self.assertFalse(window.present_authoritative_roster(old,capability))
            self.assertTrue(window.present_authoritative_roster(current,capability))
            window.folder.setText('/new-session-folder')
            self.assertIsNone(window.roster_checkpoint)
            self.assertIsNone(window.authoritative_roster)
        self.run_window(operation)

    def test_protocol8_metadata_and_unspecified_stdout_events_do_not_enable_roster(self):
        from test_uf_equipment_roster_view import fixture
        import uf_equipment_roster as contract
        catalog,state,capability=fixture();snapshot=contract.public_snapshot(state,catalog)
        def operation(window):
            window.campaigns.setCurrentRow(gui.VARIANTS.index('united_fronts'))
            self.assertFalse(window.present_authoritative_roster(snapshot,{'protocol':8}))
            window.clear_authoritative_roster()
            window.session=True
            event={'phase':'uf_equipment_roster','snapshot':snapshot,'capability':capability}
            with mock.patch.object(window.process,'readAllStandardOutput',return_value=(json.dumps(event)+'\n').encode()):window.read_output()
            self.assertIsNone(window.authoritative_roster)
            self.assertFalse(window.roster_button.isVisible())
            self.assertIn('cannot apply',window.equipment_note.text())
            window.set_busy(False)
        self.run_window(operation)


if __name__ == "__main__":
    unittest.main()
