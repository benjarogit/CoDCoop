import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qa_model_mapping_relay import Gate,CTRL

def test_relay_only_drops_host_dobjs_after_checkpoint_gamestate():
    g=Gate(2)
    assert g.verdict(CTRL+b'D', 's2c',0)[1]=='forward'
    assert g.verdict(CTRL+b'G', 's2c',1)[1]=='forward'
    assert not g.armed
    g.verdict(CTRL+b'R','s2c',2)
    assert not g.armed
    g.verdict(CTRL+b'G','s2c',3)
    assert g.armed
    assert g.verdict(CTRL+b'D','s2c',4)[1]=='drop'
    for packet in (CTRL+b'E',CTRL+b'N',b'engine snapshot',CTRL+b'C'):
        assert g.verdict(packet,'s2c',4)[1]=='forward'
    assert g.verdict(CTRL+b'D','c2s',4)[1]=='forward'
    g.verdict(CTRL+b'G','s2c',4.9) # duplicate must not lengthen barrier
    assert g.verdict(CTRL+b'D','s2c',5)[1]=='forward'
