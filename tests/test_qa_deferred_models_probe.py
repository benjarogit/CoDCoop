import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qa_deferred_models_probe import fire_evidence_complete

def test_requested_fire_cannot_pass_with_missing_observer_events():
    assert not fire_evidence_complete(True,[],1)
    assert not fire_evidence_complete(True,[{'actual_fire': True}],2)
    assert fire_evidence_complete(True,[{},{}],2)
    assert fire_evidence_complete(False,[],2)
