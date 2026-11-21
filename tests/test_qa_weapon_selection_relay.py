import importlib.util
from pathlib import Path
import struct

spec=importlib.util.spec_from_file_location('selection_relay',Path(__file__).parents[1]/'tools/qa_weapon_selection_relay.py')
relay=importlib.util.module_from_spec(spec);spec.loader.exec_module(relay)


def packet():
    data=bytearray(133);data[:5]=relay.CTRL+b's'
    struct.pack_into('<I',data,5,9);struct.pack_into('<QI',data,45,0x123456789,4)
    struct.pack_into('<IIHBB',data,57,21,13,98,2,0)
    data[69:81]=b'springfield\0'
    return bytes(data)


def test_only_explicit_mutation_changes_its_field():
    original=packet();assert relay.replay_packet(original,'duplicate')==original
    for mode,offset,size in [('wrong_ticket',61,4),('wrong_world',53,4),('wrong_session',45,8)]:
        altered=relay.replay_packet(original,mode)
        assert altered[:offset]==original[:offset] and altered[offset+size:]==original[offset+size:]
        assert altered[offset:offset+size]!=original[offset:offset+size]


def test_rejects_unbounded_wrong_protocol_and_engine_packets():
    original=packet();assert relay.request(original)['slot']==2
    for bad in [original[:-1],original+b'junk',relay.CTRL+b'z'+original[5:],original[:5]+struct.pack('<I',8)+original[9:]]:
        assert relay.request(bad) is None
        try:relay.replay_packet(bad,'duplicate')
        except ValueError:pass
        else:raise AssertionError('malformed request accepted')


def test_old_accept_simulation_removes_only_explicit_capability_tail():
    original=bytearray(packet());original[4]=ord('A');original[-8:]=struct.pack('<II',0x57534c31,7)
    assert relay.strip_accept_capability(bytes(original))==bytes(original[:-8])
    original[-8:]=struct.pack('<II',0,7)
    assert relay.strip_accept_capability(bytes(original))==bytes(original)
