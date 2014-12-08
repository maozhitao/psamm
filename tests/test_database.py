#!/usr/bin/env python

import unittest

from metnet.database import DictDatabase, ChainedDatabase
from metnet.reaction import ModelSEED, Compound, Reaction

class TestMetabolicDatabase(unittest.TestCase):
    def setUp(self):
        self.database = DictDatabase()
        self.database.set_reaction('rxn_1', ModelSEED.parse('=> (2) |A|'))
        self.database.set_reaction('rxn_2', ModelSEED.parse('|A| <=> |B|'))
        self.database.set_reaction('rxn_3', ModelSEED.parse('|A| => |D|'))
        self.database.set_reaction('rxn_4', ModelSEED.parse('|A| => |C|'))
        self.database.set_reaction('rxn_5', ModelSEED.parse('|C| => |D|'))
        self.database.set_reaction('rxn_6', ModelSEED.parse('|D| =>'))

    def test_reactions(self):
        self.assertEqual(set(self.database.reactions),
                            { 'rxn_1', 'rxn_2', 'rxn_3', 'rxn_4', 'rxn_5', 'rxn_6' })

    def test_compounds(self):
        self.assertEquals(set(self.database.compounds),
                            { Compound('A'), Compound('B'), Compound('C'), Compound('D') })

    def test_has_reaction_existing(self):
        self.assertTrue(self.database.has_reaction('rxn_3'))

    def test_has_reaction_not_existing(self):
        self.assertFalse(self.database.has_reaction('rxn_7'))

    def test_is_reversible_is_true(self):
        self.assertTrue(self.database.is_reversible('rxn_2'))

    def test_is_reversible_is_false(self):
        self.assertFalse(self.database.is_reversible('rxn_5'))

    def test_get_reaction_values(self):
        self.assertEquals(set(self.database.get_reaction_values('rxn_2')),
                            { (Compound('A'), -1), (Compound('B'), 1) })

    def test_get_compound_reactions(self):
        self.assertEquals(set(self.database.get_compound_reactions(Compound('A'))),
                            { 'rxn_1', 'rxn_2', 'rxn_3', 'rxn_4' })

    def test_reversible(self):
        self.assertEquals(set(self.database.reversible), { 'rxn_2' })

    def test_get_reaction(self):
        reaction = ModelSEED.parse('|A| => |D|')
        self.assertEqual(self.database.get_reaction('rxn_3'), reaction)

    def test_set_reaction_with_zero_coefficient(self):
        reaction = Reaction(Reaction.Bidir, [(Compound('A'), 1), (Compound('B'), 0)],
                                            [(Compound('C'), 1)])
        self.database.set_reaction('rxn_new', reaction)
        self.assertNotIn('rxn_new', self.database.get_compound_reactions(Compound('B')))

    def test_matrix_get_item(self):
        self.assertEqual(self.database.matrix[Compound('A'), 'rxn_1'], 2)
        self.assertEqual(self.database.matrix[Compound('A'), 'rxn_2'], -1)
        self.assertEqual(self.database.matrix[Compound('B'), 'rxn_2'], 1)
        self.assertEqual(self.database.matrix[Compound('A'), 'rxn_4'], -1)
        self.assertEqual(self.database.matrix[Compound('C'), 'rxn_4'], 1)
        self.assertEqual(self.database.matrix[Compound('C'), 'rxn_5'], -1)
        self.assertEqual(self.database.matrix[Compound('D'), 'rxn_5'], 1)

    def test_matrix_get_item_invalid_key(self):
        with self.assertRaises(KeyError):
            a = self.database.matrix[Compound('A'), 'rxn_5']
        with self.assertRaises(KeyError):
            b = self.database.matrix['rxn_1']

    def test_matrix_set_item_is_invalid(self):
        with self.assertRaises(TypeError):
            self.database.matrix[Compound('A'), 'rxn_1'] = 4

    def test_matrix_iter(self):
        matrix_keys = { (Compound('A'), 'rxn_1'),
                        (Compound('A'), 'rxn_2'),
                        (Compound('B'), 'rxn_2'),
                        (Compound('A'), 'rxn_3'),
                        (Compound('D'), 'rxn_3'),
                        (Compound('A'), 'rxn_4'),
                        (Compound('C'), 'rxn_4'),
                        (Compound('C'), 'rxn_5'),
                        (Compound('D'), 'rxn_5'),
                        (Compound('D'), 'rxn_6') }
        self.assertEqual(set(iter(self.database.matrix)), matrix_keys)

    def test_matrix_len(self):
        self.assertEqual(len(self.database.matrix), 10)

class TestChainedDatabase(unittest.TestCase):
    def setUp(self):
        database1 = DictDatabase()
        database1.set_reaction('rxn_1', ModelSEED.parse('|A| => |B|'))
        database1.set_reaction('rxn_2', ModelSEED.parse('|B| => |C| + |D|'))
        database1.set_reaction('rxn_3', ModelSEED.parse('|D| <=> |E|'))
        database1.set_reaction('rxn_4', ModelSEED.parse('|F| => |G|'))

        database2 = DictDatabase()
        database2.set_reaction('rxn_2', ModelSEED.parse('|B| => |C|'))
        database2.set_reaction('rxn_3', ModelSEED.parse('|C| => |D|'))
        database2.set_reaction('rxn_4', ModelSEED.parse('|F| <=> |G|'))
        database2.set_reaction('rxn_5', ModelSEED.parse('|G| + |I| <=> |H|'))

        self.database = ChainedDatabase(database2, database1)

    def test_has_reaction_in_lower_database(self):
        self.assertTrue(self.database.has_reaction('rxn_1'))

    def test_has_reaction_in_upper_new(self):
        self.assertTrue(self.database.has_reaction('rxn_5'))

    def test_has_reaction_in_upper_shadowing(self):
        self.assertTrue(self.database.has_reaction('rxn_3'))

    def test_is_reversible_in_lower_database(self):
        self.assertFalse(self.database.is_reversible('rxn_1'))

    def test_is_reversible_in_upper_new(self):
        self.assertTrue(self.database.is_reversible('rxn_5'))

    def test_is_reversible_in_upper_shadowing(self):
        self.assertFalse(self.database.is_reversible('rxn_3'))

    def test_get_compound_reactions_in_upper(self):
        reactions = set(self.database.get_compound_reactions(Compound('H')))
        self.assertEquals(reactions, { 'rxn_5' })

    def test_get_compound_reactions_in_lower(self):
        reactions = set(self.database.get_compound_reactions(Compound('A')))
        self.assertEquals(reactions, { 'rxn_1' })

    def test_get_compound_reactions_in_both(self):
        reactions = set(self.database.get_compound_reactions(Compound('B')))
        self.assertEquals(reactions, { 'rxn_1', 'rxn_2' })

    def test_get_compound_reactions_in_both_and_shadowed(self):
        reactions = set(self.database.get_compound_reactions(Compound('D')))
        self.assertEquals(reactions, { 'rxn_3' })

if __name__ == '__main__':
    unittest.main()
