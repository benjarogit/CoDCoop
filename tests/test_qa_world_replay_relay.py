import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('world_replay', Path(__file__).resolve().parents[1] / 'tools/qa_world_replay_relay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def packet(kind, generation=1, session=123, protocol=9):
    data = bytearray(60)
    data[:4] = b'\xfe\xff\xff\xff'; data[4] = ord(kind)
    data[5:9] = protocol.to_bytes(4, 'little')
    data[45:53] = session.to_bytes(8, 'little')
    data[53:57] = generation.to_bytes(4, 'little')
    return bytes(data)


class ReplayTests(unittest.TestCase):
    def test_requires_actual_new_world_ready_and_keeps_original_bytes(self):
        gate = replay.ReplayGate()
        gate.feed('s2c', packet('K'))
        old = packet('D')
        gate.feed('s2c', old)
        gate.feed('s2c', packet('D') + b'newer payload')
        self.assertEqual(gate.feed('c2s', packet('r')), [])
        self.assertEqual(gate.feed('s2c', packet('G', 2)), [])
        self.assertEqual(gate.feed('c2s', packet('r', 2, session=999)), [])
        self.assertEqual(gate.feed('c2s', packet('r', 2)),
                         [('c2s', ord('r'), packet('r')), ('s2c', ord('D'), old)])
        self.assertEqual(gate.feed('c2s', packet('r', 3)), [])

    def test_capture_is_bounded_and_rejects_legacy_truncated_and_zero_tokens(self):
        gate = replay.ReplayGate()
        self.assertEqual(gate.feed('c2s', packet('r', 2)), [])
        for payload in (packet('K', protocol=8), packet('K')[:56], packet('K', generation=0), packet('K', session=0)):
            self.assertIsNone(replay.frame(payload))
            gate.feed('s2c', payload)
            self.assertIsNone(gate.initial)
        gate.feed('s2c', packet('K'))
        for _ in range(100):
            for direction, types in gate.TYPES.items():
                for kind in types:
                    gate.feed(direction, packet(chr(kind)))
        self.assertEqual(len(gate.captured), 9)
        gate.feed('other', packet('z'))
        self.assertEqual(len(gate.captured), 9)
