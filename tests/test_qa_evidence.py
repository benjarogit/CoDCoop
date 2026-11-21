import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import qa_coop
import qa_party_probe


class EvidenceTests(unittest.TestCase):
    def test_retry_preserves_failed_result_runtime_and_engine_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime').mkdir()
            (root / 'runtime/codcoop_core.dll').write_bytes(b'failed-run-version')
            (root / 'result.json').write_text(json.dumps({'status': 'FAIL'}))
            (root / 'mainline-probe.json').write_text('{"coverage":"natural credits"}')
            (root / 'host/Main/save').mkdir(parents=True)
            (root / 'host/Main/console.log').write_text('engine error')
            (root / 'host/Main/save/keep.svg').write_bytes(b'checkpoint')
            qa_coop.archive_previous(root)
            saved = next((root / 'history').iterdir())
            self.assertEqual(json.loads((saved / 'result.json').read_text())['status'], 'FAIL')
            self.assertEqual((saved / 'runtime/codcoop_core.dll').read_bytes(), b'failed-run-version')
            self.assertEqual(json.loads((saved / 'mainline-probe.json').read_text())['coverage'], 'natural credits')
            self.assertEqual((saved / 'host/Main/console.log').read_text(), 'engine error')
            self.assertEqual((root / 'host/Main/save/keep.svg').read_bytes(), b'checkpoint')
            self.assertFalse((root / 'result.json').exists())

    def test_native_script_and_snapshot_errors_are_not_a_smoke_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Main').mkdir()
            for line in ('******* script runtime error *******',
                         'ERROR: Getrennt',
                         'ERROR: CG_ProcessSnapshots: Server time went backwards',
                         'MT_AllocIndex: failed allocation of 9206 bytes'):
                (root / 'Main/console.log').write_text(line)
                with self.subTest(error=line):
                    self.assertTrue(qa_coop.process_log_errors(root))
            (root / 'Main/console.log').write_text('normal initialization complete')
            self.assertEqual(qa_coop.process_log_errors(root), [])

    def test_acknowledged_explicit_departure_cannot_hide_a_second_disconnect(self):
        notice = 'ERROR: Getrennt'
        filter_notice = qa_party_probe.remove_acknowledged_departure
        self.assertEqual(filter_notice([notice], notice), [])
        self.assertEqual(filter_notice([notice, notice], notice), [notice])
        self.assertEqual(filter_notice([notice, 'ERROR: native failure'], notice), ['ERROR: native failure'])
        self.assertEqual(filter_notice([notice], None), [notice])


if __name__ == '__main__':
    unittest.main()
