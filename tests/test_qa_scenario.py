import inspect
import sys
import unittest
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

if __name__=='__main__':unittest.main()
