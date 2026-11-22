import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from qa_tree_watch import parse_created


class TreeWatchParser(unittest.TestCase):
    def test_reads_created_definition_and_ignores_empty_or_unrelated(self):
        line = ('QA tree trace phase=create-owned pid=4242 entity=341 tree=00975400 '
                'definition=3016db60 nodes=988 treeReadable=1 defReadable=1 loaded=1 '
                'nativeEpoch=1 init=7 world=3')
        self.assertEqual(parse_created(line), dict(pid=4242, entity=341, tree='00975400',
                                                   definition='3016db60', nodes=988, init=7, world=3))
        legacy = ('QA tree trace phase=create-owned pid=4242 entity=341 tree=00975400 '
                  'definition=3016db60 nodes=988 treeReadable=1')
        self.assertEqual(parse_created(legacy), dict(pid=4242, entity=341, tree='00975400',
                                                     definition='3016db60', nodes=988, init=0, world=0))
        empty = ('QA tree trace phase=create-owned pid=1 entity=5 tree=00000000 '
                 'definition=00000000 nodes=0 treeReadable=0')
        self.assertIsNone(parse_created(empty))
        self.assertIsNone(parse_created('unrelated log line'))
        self.assertIsNone(parse_created(line.replace('pid=4242', 'pid=x')))


if __name__ == '__main__':
    unittest.main()
