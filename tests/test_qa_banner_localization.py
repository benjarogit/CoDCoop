from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from qa_banner_localization import assert_banner,display_text

class BannerNativeTextOracle(unittest.TestCase):
    def test_localized_german_glyphs_and_literal_newline(self):
        raw='^1Spieler 2 ist niedergeschlagen^7\\nGeh näher heran'
        self.assertTrue(assert_banner(raw,['Spieler 2 ist niedergeschlagen','Geh näher heran']))
        self.assertEqual(display_text(raw),'Spieler 2 ist niedergeschlagen\nGeh näher heran')
    def test_unresolved_keys_and_wrong_player_format_cannot_pass(self):
        for raw in ('^1UNLOCALIZED(YOU ARE DOWN)','CODCOOP_DOWNED_TITLE'):
            with self.assertRaises(RuntimeError):assert_banner(raw,['YOU ARE DOWN'])
        self.assertFalse(assert_banner('Player %s is down',['Player 2 is down']))
        self.assertFalse(assert_banner('Player 3 is down',['Player 2 is down']))

if __name__=='__main__':unittest.main()
