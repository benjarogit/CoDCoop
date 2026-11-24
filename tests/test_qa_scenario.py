import inspect
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import qa_coop

class ScenarioContractTests(unittest.TestCase):
    def test_explicit_python_keyword_only_and_bounded_evidence(self):
        self.assertEqual(inspect.signature(qa_coop.main).parameters['scenario'].kind,inspect.Parameter.KEYWORD_ONLY)
        report={'scope':'isolated native negative, not campaign','checks':['real connected players; actual rejected action'],'evidence':{'actor':1,'distance':75}}
        self.assertIs(qa_coop.validate_scenario_result(report),report)

    def test_result_cannot_return_status_only_or_omit_actual_checks(self):
        for report in ({'status':'PASS'},None,{'scope':'x','checks':[],'evidence':{}},
                       {'scope':'x','checks':['x'],'evidence':{},'status':'PASS'},
                       {'scope':'x\nmisleading scope','checks':['x'],'evidence':{}}):
            with self.subTest(report=report),self.assertRaises(ValueError):qa_coop.validate_scenario_result(report)

    def test_evidence_must_be_finite_bounded_json_object(self):
        for value in ({'value':float('nan')},{'value':object()},{'value':'x'*262144},['not a mapping']):
            with self.subTest(kind=type(value)),self.assertRaises(ValueError):
                qa_coop.validate_scenario_result({'scope':'x','checks':['x'],'evidence':value})

    def test_targeted_scenario_cannot_silently_skip_requested_checkpoints(self):
        with patch('sys.stderr'), self.assertRaises(SystemExit) as error:
            qa_coop.main(['--source','unused','--run','unused',
                          '--checkpoint-reloads','1'], scenario=lambda *_: None)
        self.assertEqual(error.exception.code,2)

    def test_only_explicit_joiner_departure_indices_are_allowed(self):
        report={'scope':'leave then real rejoin','checks':['fresh lease'],'evidence':{},'intentional_departures':[1]}
        self.assertIs(qa_coop.validate_scenario_result(report),report)
        for indices in ([0],[True],[4],[1,1],'1'):
            with self.subTest(indices=indices),self.assertRaises(ValueError):
                qa_coop.validate_scenario_result({**report,'intentional_departures':indices})

    def test_allowed_marker_covers_only_its_own_console_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Main').mkdir();log=root/'Main/console.log'
            marker="ERROR: Cannot precache 'xmodel/head_blane'"
            # the engine glues the next console output onto the same physical line
            log.write_text(marker+"      cvar set cg_thirdPerson 0\nERROR: Cannot precache 'xmodel/other'\n")
            self.assertEqual(len(qa_coop.process_log_errors(root)),2)
            self.assertEqual(qa_coop.process_log_errors(root,allowed=[marker]),
                             ["ERROR: Cannot precache 'xmodel/other'"])
            log.write_text(marker+"\nERROR: Cannot precache 'xmodel/other'\n")
            self.assertEqual(qa_coop.process_log_errors(root,allowed=[marker]),
                             ["ERROR: Cannot precache 'xmodel/other'"])
            log.write_text("CRASH native fault\n")
            self.assertTrue(qa_coop.process_log_errors(root,allowed=[marker]))
            self.assertEqual(qa_coop.process_log_errors(root,allowed=['']),["CRASH native fault"])

    def test_native_departure_banner_needs_marker_exact_count_and_explicit_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Main').mkdir();log=root/'Main/console.log'
            event='^3COOP: You left the co-op game.\n********************\nERROR: Getrennt\n'
            log.write_text(event)
            self.assertTrue(qa_coop.process_log_errors(root))
            self.assertEqual(qa_coop.process_log_errors(root,1),[])
            for bad in ('ERROR: Getrennt\n',event+event,event+'CRASH native fault\n',event+'ERROR: other\n',''):
                log.write_text(bad)
                with self.subTest(text=bad):self.assertTrue(qa_coop.process_log_errors(root,1))

if __name__=='__main__':unittest.main()
