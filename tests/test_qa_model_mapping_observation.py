import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qa_model_mapping_observation import analyze

def test_loading_cls2_is_preserved_but_not_counted_as_joined_rendering():
    base=datetime(2026,11,21,13,0).timestamp()
    log='\n'.join(['13:00:00.000 joiner: conectado al host como slot 1 en foy',
                    '13:00:02.000 joiner: el host carga foy (checkpoint), lo cargo y vuelvo a entrar',
                    '13:00:05.000 joiner: conectado al host como slot 1 en foy',
                    '13:00:07.000 cmd: quit'])
    def sample(second,mismatches):
        return {'observed_time':base+second,'cls_state':2,'server_time':123,'model_mapping_mismatches':mismatches}
    result=analyze([sample(1,0),sample(3,322),sample(6,0)],log)
    assert result['joined_samples']==2 and result['max_joined_model_mismatches']==0
    assert result['max_all_cls2_model_mismatches']==322 and len(result['unjoined_transition_outliers'])==1
    result=analyze([sample(1,15),sample(3,322),sample(6,0)],log)
    assert result['max_joined_model_mismatches']==15
