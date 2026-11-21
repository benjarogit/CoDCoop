import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from qa_partition_probe import partition_evidence


class PartitionEvidence(unittest.TestCase):
    def evidence(self, events):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'packets.jsonl'
            path.write_text('\n'.join(json.dumps(event) for event in events))
            return partition_evidence(path)

    def test_actual_native_reload_drop_is_required(self):
        packet = {'dir': 's2c', 'head': 'feffffff520700',
                  'verdict': 'drop', 'reason': 'partition'}
        self.assertEqual(self.evidence([packet])['dropped_reload_controls'], 1)
        for changes in ({'dir': 'c2s'}, {'head': 'feffffff430700'},
                        {'verdict': 'fwd'}, {'reason': 'loss'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.evidence([{**packet, **changes}])['dropped_reload_controls'], 0)

    def test_relay_start_and_partition_marker_do_not_prove_packet_loss(self):
        evidence = self.evidence([{'format': 'coopchaos-packetlog'},
                                 {'event': 'partition', 'dir': 's2c', 'on': True}])
        self.assertEqual(evidence['reload_controls'], 0)
        self.assertEqual(evidence['dropped_reload_controls'], 0)
        self.assertEqual(len(evidence['partitions']), 1)
        self.assertIsNone(evidence['observed_partition_ms'])

    def test_partition_duration_comes_from_relay_events(self):
        evidence = self.evidence([
            {'event': 'partition', 'dir': 's2c', 'on': True, 't': 10000},
            {'event': 'partition', 'dir': 's2c', 'on': False, 't': 12001}])
        self.assertEqual(evidence['observed_partition_ms'], 2001)

    def test_only_dropped_reload_ack_counts_for_reverse_partition(self):
        packet = {'dir': 'c2s', 'head': 'feffffff740800',
                  'verdict': 'drop', 'reason': 'partition'}
        evidence = self.evidence([packet])
        self.assertEqual(evidence['dropped_reload_acknowledgements'], 1)
        self.assertEqual(evidence['dropped_reload_controls'], 0)
        self.assertEqual(self.evidence([{**packet, 'reason': 'loss'}])['dropped_reload_acknowledgements'], 0)
