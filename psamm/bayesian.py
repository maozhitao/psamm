# This file is part of PSAMM.
#
# PSAMM is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PSAMM is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PSAMM.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2014-2015  Jon Lund Steffensen <jon_steffensen@uri.edu>
# Copyright 2018-2019  Jing Wang <wjingsjtu@gmail.com>

"""Calculate model mapping likelihood with bayesian."""
from __future__ import print_function, division
from future.utils import itervalues

from builtins import object, range
from itertools import product
from multiprocessing import Pool
import operator
import sys

import numpy as np
import pandas as pd

import psamm.bayesian_util as util
from functools import reduce


class BayesianCompoundPredictor(object):
    """Predict model compound mappings based on a Bayesian model."""

    def __init__(self, model1, model2, nproc, outpath, log, kegg):
        self._model1 = model1
        self._model2 = model2
        self._column_list = [
            'p', 'p_id', 'p_name', 'p_charge', 'p_formula', 'p_kegg']
        self._compound_map_p = map_model_compounds(
            self._model1, self._model2, nproc, outpath, log=log, kegg=kegg)

    @property
    def model1(self):
        return self._model1

    @property
    def model2(self):
        return self._model2

    def map(self, c1, c2):
        return self._compound_map_p[0][c1, c2]

    def get_raw_map(self):
        """Return pandas.DataFrame style of raw mapping table."""
        compound_result = pd.DataFrame({
            self._column_list[i]: self._compound_map_p[i]
            for i in range(len(self._column_list))
        })
        return compound_result

    def get_best_map(self, threshold_compound):
        """Return pandas.DataFrame style of best mapping for each query."""
        raw_map = self.get_raw_map()
        query = [i for i, j in raw_map.index.values]
        # use rank instead of idxmax to output multiple top-hitts
        best_index = raw_map.iloc[:, 0].groupby(query).rank(
            method='min', ascending=False).loc[lambda x: x == 1].index.values
        compound_best = raw_map.loc[best_index]
        compound_best.query(
            'p >= @threshold_compound', inplace=True)
        return compound_best


class BayesianReactionPredictor(object):
    """Predict model reaction mappings based on a Bayesian model."""

    def __init__(self, model1, model2, cpd_pred, nproc, outpath, log, gene):
        self._model1 = model1
        self._model2 = model2
        self._column_list = ['p', 'p_id', 'p_name', 'p_equation', 'p_genes']
        self._reaction_map_p = map_model_reactions(
            self._model1, self._model2, cpd_pred, nproc, outpath,
            log=log, gene=gene)

    @property
    def model1(self):
        return self._model1

    @property
    def model2(self):
        return self._model2

    def map(self, r1, r2):
        return self._reaction_map_p[0][r1, r2]

    def get_raw_map(self):
        """Return pandas.DataFrame style of raw mapping table."""
        reaction_result = pd.DataFrame({
            self._column_list[i]: self._reaction_map_p[i]
            for i in range(len(self._column_list))
        })
        return reaction_result

    def get_best_map(self, threshold_reaction):
        """Return pandas.DataFrame style of best mapping for each query."""
        raw_map = self.get_raw_map()
        query = [i for i, j in raw_map.index.values]
        # use rank instead of idxmax to output multiple top-hitts
        best_index = raw_map.iloc[:, 0].groupby(query).rank(
            method='min', ascending=False).loc[lambda x: x == 1].index.values
        reaction_best = raw_map.loc[best_index]
        reaction_best.query(
            'p >= @threshold_reaction', inplace=True)
        return reaction_best


def compound_id_likelihood(c1, c2, compound_prior, compound_id_marg):
    if util.id_equals(c1.id, c2.id):
        p_match = 0.65
        p_marg = compound_id_marg
        p_no_match = max(
            0, (p_marg - p_match * compound_prior) / (1.0 - compound_prior))
    else:
        p_match = 0.35
        p_marg = 1.0 - compound_id_marg
        p_no_match = max(
            0, (p_marg - p_match * compound_prior) / (1.0 - compound_prior))

    return p_match, p_no_match


def compound_name_likelihood(c1, c2, compound_prior, compound_name_marg):
    if util.name_equals(c1.name, c2.name):
        p_match = 0.60
        p_marg = compound_name_marg
        p_no_match = max(
            0, (p_marg - p_match * compound_prior) / (1.0 - compound_prior))
    else:
        p_match = 0.40
        p_marg = 1.0 - compound_name_marg
        p_no_match = max(
            0, (p_marg - p_match * compound_prior) / (1.0 - compound_prior))

    return p_match, p_no_match  # , p_marg


def compound_charge_likelihood(
        c1, c2, compound_prior,
        compound_charge_equal_marg, compound_charge_not_equal_marg):
    if c1.charge is None or c2.charge is None:
        # p value of observing undefined charge
        # it is independent of the condition of match or not
        p_match = 1
        p_no_match = 1
    elif c1.charge == c2.charge:
        p_match = 0.9
        p_no_match = max(
            0,
            ((compound_charge_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))
    else:
        p_match = 0.1
        p_no_match = max(
            0,
            ((compound_charge_not_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))

    return p_match, p_no_match


def compound_formula_likelihood(
        c1, c2, compound_prior,
        compound_formula_equal_marg, compound_formula_not_equal_marg):
    if c1.formula is None or c2.formula is None:
        # p value of observing undefined formula
        # it is independent of the condition of match or not
        p_match = 1
        p_no_match = 1
    elif util.formula_equals(c1.formula, c2.formula, c1.charge, c2.charge):
        p_match = 0.9
        p_no_match = max(
            0,
            ((compound_formula_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))
    else:
        p_match = 0.1
        p_no_match = max(
            0,
            ((compound_formula_not_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))

    return p_match, p_no_match


def compound_kegg_likelihood(
        c1, c2, compound_prior,
        compound_kegg_equal_marg, compound_kegg_not_equal_marg):
    if c1.kegg is None or c2.kegg is None:
        # p value of observing undefined KEGG
        # it is independent of the condition of match or not
        p_match = 1
        p_no_match = 1
    elif c1.kegg == c2.kegg:
        p_match = 0.65
        p_no_match = max(
            0,
            ((compound_kegg_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))
    else:
        p_match = 0.35
        p_no_match = max(
            0,
            ((compound_kegg_not_equal_marg - p_match * compound_prior) /
             (1.0 - compound_prior)))

    return p_match, p_no_match


def reaction_id_likelihood(
        r1, r2, reaction_prior,
        reaction_id_equal_marg, reaction_id_not_equal_marg):
    if util.id_equals(r1.id, r2.id):
        p_match = 0.52
        p_no_match = max(
            0,
            ((reaction_id_equal_marg - p_match * reaction_prior) /
             (1.0 - reaction_prior)))
    else:
        p_match = 0.48
        p_no_match = max(
            0,
            ((reaction_id_not_equal_marg - p_match * reaction_prior) /
             (1.0 - reaction_prior)))

    return p_match, p_no_match


def reaction_name_likelihood(r1, r2, reaction_prior, reaction_name_marg):
    if util.name_equals(r1.name, r2.name):
        p_match = 0.59
        p_no_match = max(
            0,
            ((reaction_name_marg - p_match * reaction_prior) /
             (1.0 - reaction_prior)))
    else:
        p_match = 0.41
        p_no_match = max(
            0,
            ((1.0 - reaction_name_marg - p_match * reaction_prior) /
             (1.0 - reaction_prior)))

    return p_match, p_no_match


def reaction_equation_mapping_approx_max_likelihood(
        cpd_set1, cpd_set2, cpd_pred):
    """Calculate equation likelihood based on compound mapping."""
    p_match = 0.0
    p_no_match = 0.0

    # get the possible best-match pairs
    pair_list = [
        (c1, c2)
        for c1, c2 in product(cpd_set1, cpd_set2)
        if (c1, c2) in cpd_pred.index]
    # get the p value for (c1, c2) pairs, high possibility first
    cpd_pred = (cpd_pred.loc[pair_list]
                .sort_values(ascending=False))

    if (len(cpd_pred) > 0):  # if best-hit pairs exist
        for c1, c2 in cpd_pred.index.values:
            if (c1 in cpd_set1) and (c2 in cpd_set2):
                score = cpd_pred[(c1, c2)]
                # the possibility that compounds are equal
                p_match += np.log(score * 0.9 + (1 - score) * 0.1)
                p_no_match += np.log(score * 0.1 + (1 - score) * 0.9)
                cpd_set1.remove(c1)
                cpd_set2.remove(c2)

    for c in cpd_set1:
        p_match += np.log(0.1)
        p_no_match += np.log(0.9)
    for c in cpd_set2:
        p_match += np.log(0.1)
        p_no_match += np.log(0.9)

    p_match = np.exp(p_match)
    p_no_match = np.exp(p_no_match)
    return p_match, p_no_match


def reaction_equation_compound_mapping_likelihood(r1, r2, cpd_pred):
    if r1.equation is None or r2.equation is None:
        # p value of observing undefined equation
        # it is independent of the condition of match or not
        p_match = 1
        p_no_match = 1
    else:
        p_match, p_no_match = get_best_p_value_set(r1, r2, cpd_pred)

    return p_match, p_no_match


def get_best_p_value_set(r1, r2, cpd_pred):
    """Assume equations may have reversed direction, report best mapping p."""
    cpd_set1_left = get_cpd_set(r1.equation, left=True)
    cpd_set1_right = get_cpd_set(r1.equation, left=False)
    cpd_set2_left = get_cpd_set(r2.equation, left=True)
    cpd_set2_right = get_cpd_set(r2.equation, left=False)

    # assume equations have the same direction
    p_forward_match, p_forward_no_match = merge_partial_p_set(
        cpd_set1_left, cpd_set2_left, cpd_pred,
        cpd_set1_right, cpd_set2_right)
    # assume equations have the reversed direction
    p_reverse_match, p_reverse_no_match = merge_partial_p_set(
        cpd_set1_left, cpd_set2_right, cpd_pred,
        cpd_set1_right, cpd_set2_left)

    # maintain the direction with better p values
    if (p_forward_match / p_forward_no_match
            >= p_reverse_match / p_reverse_no_match):
        p_match = p_forward_match
        p_no_match = p_forward_no_match
    else:
        p_match = p_reverse_match
        p_no_match = p_reverse_no_match

    return p_match, p_no_match


def merge_partial_p_set(cpd_set1_left, cpd_set2_left, cpd_pred,
                        cpd_set1_right, cpd_set2_right):
    """Merge the left hand side and right hand side p values together.

    The compound mapping is done separately on left hand side and
    right hand side.
    Then the corresponding p_match and p_no_match are merged together.
    """
    p_set_left = \
        reaction_equation_mapping_approx_max_likelihood(
            cpd_set1_left, cpd_set2_left, cpd_pred)
    p_set_right = \
        reaction_equation_mapping_approx_max_likelihood(
            cpd_set1_right, cpd_set2_right, cpd_pred)
    p_match = p_set_left[0] * p_set_right[0]
    p_no_match = p_set_left[1] * p_set_right[1]
    return p_match, p_no_match


def get_cpd_set(equation, left=True):
    if left:  # value of left-side compound is negtive
        coef = 1
    else:  # value of right-side compound is positive
        coef = -1
    # pick compounds at one side only
    cpd_set = set(
        compound.name
        for compound, value in equation.compounds
        if coef * value < 0)
    return cpd_set


def reaction_genes_likelihood(r1, r2):
    if r1.genes is None or r2.genes is None:
        # p value of observing undefined genes
        # it is independent of the condition of match or not
        p_match = 1
        p_no_match = 1
    else:
        # calculating p_match
        present = len(r1.genes & r2.genes)
        differ = len(r1.genes ^ r2.genes)
        # total = len(r1.genes | r2.genes)

        p_present = 0.99
        p_differ = 0.01
        p_match = p_present**present * p_differ**differ

        # calculating p_no_match
        p_present = 0.10
        p_differ = 0.90
        p_no_match = p_present**present * p_differ**differ

    return p_match, p_no_match


def fake_likelihood(e1, e2):
    """Generate fake likelihood if corresponding mapping is not required."""
    return 1, 1


def generate_likelihood(tasks):
    pair, likelihood, params = tasks
    e1, e2 = pair
    p1, p2 = likelihood(e1, e2, *params)
    return e1.id, e2.id, p1, p2


def pairwise_likelihood(pool, chunksize, model1, model2, likelihood, params):
    """Compute likelihood of all pairwise comparisons.

    Returns likelihoods as a dataframe with a column for each hypothesis.
    """
    tasks = (((e1, e2), likelihood, params)
             for e1, e2 in product(itervalues(model1), itervalues(model2)))
    result = pool.map(generate_likelihood, tasks, chunksize=chunksize)
    return pd.DataFrame.from_records(result, index=('e1', 'e2'),
                                     columns=('e1', 'e2', 'p1', 'p2'))


def likelihood_products(likelihood_dfs):
    """Combine likelihood dataframes."""
    return reduce(operator.mul, likelihood_dfs, 1.0)


def bayes_posterior(prior, likelihood_df):
    """Calculate posterior given likelihoods and prior."""
    p_1 = prior * likelihood_df.iloc[:, 0]
    p_2 = (1.0 - prior) * likelihood_df.iloc[:, 1]
    return p_1 / (p_1 + p_2)


def parallel_equel(tasks):
    func, params = tasks
    return func(*params)


def map_model_compounds(model1, model2, nproc, outpath, log, kegg):
    """Map compounds of two models."""
    compound_pairs = len(model1.compounds) * len(model2.compounds)

    # Compound prior
    # For the prior, use a guesstimate that 95% of the
    # smaller model can be mapped.
    compound_prior = (0.95 * min(len(model1.compounds),
                                 len(model2.compounds))) / compound_pairs

    # Initialize parallel pool of workers
    chunksize = compound_pairs // nproc
    pool = Pool(nproc)
    # Compound ID
    # Marginal probability of observing two equal compound IDs
    tasks = ((util.id_equals, (c1.id, c2.id)) for c1, c2 in product(
        itervalues(model1.compounds), itervalues(model2.compounds)))
    result = pool.map(parallel_equel, tasks, chunksize=chunksize)
    compound_id_marg = sum(result) / float(compound_pairs)

    print('Calculating compound ID likelihoods...')
    sys.stdout.flush()
    compound_id_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.compounds, model2.compounds,
        compound_id_likelihood, (compound_prior, compound_id_marg))

    # Compound name
    # Marginal probability of observing two similar names
    tasks = ((util.name_equals, (c1.name, c2.name)) for c1, c2 in product(
        itervalues(model1.compounds), itervalues(model2.compounds)))
    result = pool.map(parallel_equel, tasks, chunksize=chunksize)
    compound_name_marg = sum(result) / float(compound_pairs)

    print('Calculating compound name likelihoods...')
    sys.stdout.flush()
    compound_name_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.compounds, model2.compounds,
        compound_name_likelihood, (compound_prior, compound_name_marg))

    # Compound charge
    # Marginal probability of observing two compounds with the same charge
    compound_charge_equal_marg = sum(
        c1.charge is not None and
        c2.charge is not None and
        c1.charge == c2.charge
        for c1, c2 in product(
            itervalues(model1.compounds), itervalues(model2.compounds))
    ) / compound_pairs

    # Marginal probability of observing two compounds with different charge
    compound_charge_not_equal_marg = sum(
        c1.charge is not None and
        c2.charge is not None and
        c1.charge != c2.charge
        for c1, c2 in product(
            itervalues(model1.compounds), itervalues(model2.compounds))
    ) / compound_pairs

    print('Calculating compound charge likelihoods...')
    sys.stdout.flush()

    compound_charge_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.compounds, model2.compounds,
        compound_charge_likelihood, (
            compound_prior,
            compound_charge_equal_marg,
            compound_charge_not_equal_marg))

    # Compound formula
    # Marginal probability of observing two compounds with the same formula
    tasks = ((
        util.formula_equals,
        (c1.formula, c2.formula, c1.charge, c2.charge))
        for c1, c2 in product(
            itervalues(model1.compounds), itervalues(model2.compounds)))
    result = pool.map(parallel_equel, tasks, chunksize=chunksize)
    compound_formula_equal_marg = sum(result) / float(compound_pairs)

    # Marginal probability of observing two compounds with different formula
    compound_formula_not_equal_marg = 1.0 - compound_formula_equal_marg - (
        sum(c1.formula is None or c2.formula is None
            for c1, c2 in product(itervalues(model1.compounds),
                                  itervalues(model2.compounds))) /
        compound_pairs)

    print('Calculating compound formula likelihoods...')
    sys.stdout.flush()
    compound_formula_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.compounds, model2.compounds,
        compound_formula_likelihood, (
            compound_prior, compound_formula_equal_marg,
            compound_formula_not_equal_marg))

    # Compound KEGG id
    if kegg:  # run KEGG id mapping
        # Marginal probability of observing two compounds
        # where KEGG ids are equal
        compound_kegg_equal_marg = sum(
            c1.kegg is not None and
            c2.kegg is not None and
            c1.kegg == c2.kegg
            for c1, c2 in product(
                itervalues(model1.compounds),
                itervalues(model2.compounds))
        ) / compound_pairs

        # Marginal probability of observing two compounds
        # where KEGG ids are different
        compound_kegg_not_equal_marg = sum(
            c1.kegg is not None and
            c2.kegg is not None and
            c1.kegg != c2.kegg for c1, c2 in product(
                itervalues(model1.compounds),
                itervalues(model2.compounds))
        ) / compound_pairs

        print('Calculating compound KEGG ID likelihoods...')
        sys.stdout.flush()
        compound_kegg_likelihoods = pairwise_likelihood(
            pool, chunksize, model1.compounds, model2.compounds,
            compound_kegg_likelihood, (
                compound_prior, compound_kegg_equal_marg,
                compound_kegg_not_equal_marg))
    else:  # run fake mapping
        compound_kegg_likelihoods = pairwise_likelihood(
            pool, chunksize, model1.compounds, model2.compounds,
            fake_likelihood, ())

    pool.close()
    pool.join()

    if log:
        merge_result = pd.merge(compound_id_likelihoods,
                                compound_name_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_id', '_name'))
        merge_result = pd.merge(merge_result, compound_charge_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_name', '_charge'))
        merge_result = pd.merge(merge_result, compound_formula_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_charge', '_formula'))
        merge_result = pd.merge(merge_result, compound_kegg_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_formula', '_kegg'))

        merge_result.to_csv(outpath + '/compound_log.tsv', sep='\t')

    all_likelihoods = [compound_id_likelihoods,
                       compound_name_likelihoods,
                       compound_charge_likelihoods,
                       compound_formula_likelihoods,
                       compound_kegg_likelihoods]

    return (bayes_posterior(compound_prior,
                            likelihood_products(all_likelihoods)),
            bayes_posterior(compound_prior, compound_id_likelihoods),
            bayes_posterior(compound_prior, compound_name_likelihoods),
            bayes_posterior(compound_prior, compound_charge_likelihoods),
            bayes_posterior(compound_prior, compound_formula_likelihoods),
            bayes_posterior(compound_prior, compound_kegg_likelihoods))


def map_model_reactions(model1, model2, cpd_pred, nproc, outpath, log, gene):
    """Map reactions of two models."""
    # Mapping of reactions
    reaction_pairs = len(model1.reactions) * len(model2.reactions)

    # Reaction prior
    # For the prior, use a guesstimate that 95%
    # of the smaller model can be mapped.
    reaction_prior = (0.95 * min(len(model1.reactions),
                                 len(model2.reactions))) / reaction_pairs

    # Initialize parallel pool of workers
    chunksize = reaction_pairs // nproc
    pool = Pool(nproc)

    # Reaction ID
    # Marginal probability of observing two reactions with the same ids.
    tasks = ((util.id_equals, (r1.id, r2.id)) for r1, r2 in product(
        itervalues(model1.reactions),
        itervalues(model2.reactions)))
    result = pool.map(parallel_equel, tasks, chunksize=chunksize)
    reaction_id_equal_marg = sum(result) / float(reaction_pairs)

    # Marginal probability of observing two reactions with different ids.
    reaction_id_not_equal_marg = 1.0 - reaction_id_equal_marg

    print('Calculating reaction ID likelihoods...')
    sys.stdout.flush()
    reaction_id_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.reactions, model2.reactions,
        reaction_id_likelihood, (
            reaction_prior,
            reaction_id_equal_marg, reaction_id_not_equal_marg))

    # Reaction name
    # Marginal probability of observing two reactions with the same name.
    tasks = ((util.name_equals, (r1.name, r2.name)) for r1, r2 in product(
        itervalues(model1.reactions),
        itervalues(model2.reactions)))
    result = pool.map(parallel_equel, tasks, chunksize=chunksize)
    reaction_name_equal_marg = sum(result) / float(reaction_pairs)

    print('Calculating reaction name likelihoods...')
    sys.stdout.flush()
    reaction_name_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.reactions, model2.reactions,
        reaction_name_likelihood, (reaction_prior, reaction_name_equal_marg))

    # Reaction equation

    print('Calculating reaction equation likelihoods...')
    sys.stdout.flush()
    reaction_equation_likelihoods = pairwise_likelihood(
        pool, chunksize, model1.reactions, model2.reactions,
        reaction_equation_compound_mapping_likelihood,
        (cpd_pred, ))

    # Reaction genes
    # For each gene, the marginal probability of observing that gene
    # in each model. We use this as an approximation of the probability of
    # observing a pair of genes in two reactions given that the reaction
    # do _not_ match.
    if gene:
        print('Calculating reaction genes likelihoods...')
        sys.stdout.flush()
        reaction_genes_likelihoods = pairwise_likelihood(
            pool, chunksize, model1.reactions, model2.reactions,
            reaction_genes_likelihood, ())
    else:
        reaction_genes_likelihoods = pairwise_likelihood(
            pool, chunksize, model1.reactions, model2.reactions,
            fake_likelihood, ())

    pool.close()
    pool.join()

    if log:
        merge_result = pd.merge(reaction_id_likelihoods,
                                reaction_name_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_id', '_name'))
        merge_result = pd.merge(merge_result, reaction_equation_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_name', '_equation'))
        merge_result = pd.merge(merge_result, reaction_genes_likelihoods,
                                left_index=True, right_index=True,
                                suffixes=('_equation', '_genes'))

        merge_result.to_csv(outpath + '/reaction_log.tsv', sep='\t')

    all_likelihoods = [reaction_id_likelihoods,
                       reaction_name_likelihoods,
                       reaction_equation_likelihoods,
                       reaction_genes_likelihoods]

    return (bayes_posterior(reaction_prior,
                            likelihood_products(all_likelihoods)),
            bayes_posterior(reaction_prior, reaction_id_likelihoods),
            bayes_posterior(reaction_prior, reaction_name_likelihoods),
            bayes_posterior(reaction_prior, reaction_equation_likelihoods),
            bayes_posterior(reaction_prior, reaction_genes_likelihoods))
