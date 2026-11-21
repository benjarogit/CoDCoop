"""Preserve the original native menu preset, including health, before map load."""
import unittest
import test_coop_suite as fixtures

class DifficultyLaunchTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.SuiteTest('test_complete_seal_and_prepare')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        fixtures.suite.seal_installation(self.fixture.game)

    def test_original_presets_precede_map_for_every_engine_profile(self):
        health_values=(1200,600,300,200)
        for variant in ('cod1','uo','sp_improved','united_fronts'):
            for skill,health in enumerate(health_values):
                with self.subTest(variant=variant,skill=skill):
                    args,_=fixtures.suite.launch_arguments(self.fixture.game,variant,map_name='training',difficulty=skill)
                    self.assertEqual(args[args.index('g_gameskill')+1],str(skill))
                    self.assertEqual(args[args.index('g_player_maxhealth')+1],str(health))
                    self.assertLess(args.index('g_gameskill'),args.index('+spmap'))
                    self.assertLess(args.index('g_player_maxhealth'),args.index('+spmap'))
                    self.assertFalse(any(v.startswith('+difficulty') for v in args))
                    self.assertNotIn('+difficultyGimp',args)

    def test_default_menu_launch_matches_medium_native_values(self):
        args,_=fixtures.suite.launch_arguments(self.fixture.game,'uo')
        self.assertEqual(args[args.index('g_gameskill')+1],'1')
        self.assertEqual(args[args.index('g_player_maxhealth')+1],'600')
        self.assertNotIn('+spmap',args)

    def test_no_extra_gimp_level_or_untrusted_difficulty_command(self):
        for difficulty in (-1,4,'difficultyGimp','2;quit',None):
            with self.subTest(difficulty=difficulty):
                with self.assertRaisesRegex(ValueError,'invalid difficulty'):
                    fixtures.suite.launch_arguments(self.fixture.game,'uo',difficulty=difficulty)

if __name__=='__main__':unittest.main()
