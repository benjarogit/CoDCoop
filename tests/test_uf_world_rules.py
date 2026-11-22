import dataclasses
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import uf_world_rules as rules


class WorldRulesTests(unittest.TestCase):
    def facts(self, map='brecourt', spawners=()):
        return rules.HostFacts(map, 123, 17, spawners)

    def test_ordered_spawners_override_map_last_wins(self):
        russian = 'actor_ally_russianarmy_mosin'
        british = 'actor_ally_british_commando_enfield'
        first = rules.resolve(self.facts(spawners=(russian, british)), rules.Inputs())
        second = rules.resolve(self.facts(spawners=(british, russian)), rules.Inputs())
        self.assertEqual((first.campaign, first.last_campaign_spawner), ('british', 1))
        self.assertEqual(second.campaign, 'russian')
        self.assertEqual(first.ally_nation, 'british')

    def test_missing_is_not_observed_empty(self):
        missing = rules.resolve(self.facts(spawners=None), rules.Inputs())
        empty = rules.resolve(self.facts(), rules.Inputs())
        self.assertIsNone(missing.campaign)
        self.assertTrue(missing.wait)
        self.assertEqual(empty.campaign, 'american')
        self.assertFalse(empty.wait)

    def test_exact_source_years_not_declared_party_year(self):
        for map, year in [('training', 1942), ('brecourt', 1944), ('foy', 1945),
                          ('noville', 1945), ('dendre1', 1940), ('bomber', 1941)]:
            self.assertEqual(rules.resolve(self.facts(map), rules.Inputs()).year, year)

    def test_raw_faction_is_not_ui_selector(self):
        value = rules.resolve(self.facts(), rules.Inputs(ally='ru', ally_menu='2'))
        self.assertEqual(value.ally_nation, 'russian')
        self.assertTrue(value.diagnostics)
        matching = rules.resolve(self.facts(), rules.Inputs(ally='us_inf', ally_menu='2'))
        self.assertFalse(matching.diagnostics)

    def test_special_default_nations_and_explicit_override(self):
        german = rules.resolve(self.facts('sp_eugene'), rules.Inputs())
        self.assertEqual((german.campaign, german.ally_nation, german.axis_nation),
                         ('american', 'german', 'american'))
        italian = rules.resolve(self.facts('sicily1'), rules.Inputs(axis='ru'))
        self.assertEqual((italian.ally_nation, italian.axis_nation), ('british', 'russian'))

    def test_climate_flags_are_not_mutually_exclusive(self):
        value = rules.resolve(self.facts('afrika1', ('actor_ally_airborne_snow_BAR',)), rules.Inputs())
        self.assertEqual(value.climate, 'desert')
        self.assertTrue(value.winter)
        self.assertTrue(value.desert)
        # Native source compares class strings exactly, including uppercase BAR.
        value = rules.resolve(self.facts(spawners=('actor_ally_airborne_snow_bar',)), rules.Inputs())
        self.assertFalse(value.winter)

    def test_saved_world_does_not_reconstruct_saved_nation_from_raw_menu(self):
        result = rules.resolve(self.facts(), rules.Inputs(ally='ru', saved=True))
        self.assertIsNone(result.ally_nation)
        self.assertTrue(any('saved' in entry for entry in result.wait))

    def test_unreviewed_values_and_context_are_rejected_without_clamping(self):
        for inputs in [rules.Inputs(ally='bogus'), rules.Inputs(order='2'),
                       rules.Inputs(ammo='true'), rules.Inputs(campaign_menu='5'),
                       rules.Inputs(forceweapons='-1'), rules.Inputs(axis_menu='01')]:
            with self.assertRaises(ValueError):
                rules.resolve(self.facts(), inputs)
        for facts in [self.facts('../noville'), dataclasses.replace(self.facts(), native_world=0),
                      self.facts(spawners=('x;quit',)), self.facts(spawners=['actor_ally_airborne_garand'])]:
            with self.assertRaises(ValueError):
                rules.resolve(facts, rules.Inputs())

    def test_order_is_progression_not_year_override(self):
        zero = rules.resolve(self.facts('noville'), rules.Inputs(order='0'))
        one = rules.resolve(self.facts('noville'), rules.Inputs(order='1'))
        self.assertEqual(zero, one)

    def test_extractor_discards_commented_or_unrelated_switch_cases(self):
        text = 'case "bad": other(); break; case "one": case "two": out="yes"; break; default: out="no";'
        cases, default = rules._cases(text, r'out="([^"]+)"')
        self.assertEqual(cases, {'one': 'yes', 'two': 'yes'})
        self.assertEqual(default, 'no')

    def test_unknown_original_revision_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mod.pk3'
            with zipfile.ZipFile(path, 'w') as archive:
                for member in rules.PINNED:
                    archive.writestr(member, 'Campaign() { modified(); }')
            with self.assertRaisesRegex(ValueError, 'Unsupported UF source revision'):
                rules.extract(path)

    def test_pinned_extraction_facts(self):
        graph = json.loads(rules.GRAPH.read_text())
        self.assertEqual(graph['sources'], rules.PINNED)
        self.assertEqual(len(graph['spawner_campaign']), 23)
        self.assertEqual(len(graph['snow_spawners']), 10)
        self.assertEqual(len(graph['registered_maps']), 122)
        self.assertEqual(graph['faction_nation']['ger_marine'], 'german')


if __name__ == '__main__':
    unittest.main()
