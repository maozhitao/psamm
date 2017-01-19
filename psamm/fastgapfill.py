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
# Copyright 2014-2017  Jon Lund Steffensen <jon_steffensen@uri.edu>
# Copyright 2016  Chao Liu <lcddzyx@gmail.com>

"""Implementation of fastGapFill.

Described in [Thiele14]_.
"""

from __future__ import unicode_literals

import logging

from six import iteritems
from .fastcore import fastcore

logger = logging.getLogger(__name__)


def create_extended_model(model, db_penalty=None, ex_penalty=None,
                          tp_penalty=None, penalties=None):
    """Create an extended model for FastGapFill algorithm.

    Create a :class:`psamm.metabolicmodel.MetabolicModel` with
    all reactions added (the reaction database in the model is taken
    to be the universal database) and also with artificial exchange
    and transport reactions added. Return the extended
    :class:`psamm.metabolicmodel.MetabolicModel`
    and a weight dictionary for added reactions in that model.

    Args:
        model: :class:`psamm.datasource.native.NativeModel`.
        db_penalty: penalty score for database reactions, default is `None`.
        ex_penalty: penalty score for exchange reactions, default is `None`.
        tb_penalty: penalty score for transport reactions, default is `None`.
        penalties: a dictionary of penalty scores for database reactions.
    """

    # Create metabolic model
    model_extended = model.create_metabolic_model()
    extra_compartment = model.extracellular_compartment
    compartments, boundaries = model.parse_compartments()

    compartment_ids = set(c.id for c in compartments)

    # Add database reactions to extended model
    if len(compartment_ids) > 0:
        logger.info(
            'Using all database reactions in compartments: {}...'.format(
                ', '.join('{}'.format(c) for c in compartment_ids)))
        db_added = model_extended.add_all_database_reactions(compartment_ids)
    else:
        logger.warning(
            'No compartments specified in the model; database reactions will'
            ' not be used! Add compartment specification to model to include'
            ' database reactions for those compartments.')
        db_added = set()

    # Add exchange reactions to extended model
    logger.info(
        'Using artificial exchange reactions for compartment: {}...'.format(
            extra_compartment))
    ex_added = model_extended.add_all_exchange_reactions(
        extra_compartment, allow_duplicates=True)

    # Add transport reactions to extended model
    if len(boundaries) > 0:
        logger.info(
            'Using artificial transport reactions for the compartment'
            ' boundaries: {}...'.format(
                '; '.join('{}<->{}'.format(c1, c2) for c1, c2 in boundaries)))
        tp_added = model_extended.add_all_transport_reactions(
            boundaries, allow_duplicates=True)
    else:
        logger.warning(
            'No compartment boundaries specified in the model;'
            ' artificial transport reactions will not be used!')
        tp_added = set()

    # Add penalty weights on reactions
    weights = {}
    if db_penalty is not None:
        weights.update((rxnid, db_penalty) for rxnid in db_added)
    if tp_penalty is not None:
        weights.update((rxnid, tp_penalty) for rxnid in tp_added)
    if ex_penalty is not None:
        weights.update((rxnid, ex_penalty) for rxnid in ex_added)

    if penalties is not None:
        for rxnid, penalty in iteritems(penalties):
            weights[rxnid] = penalty
    return model_extended, weights


def fastgapfill(model_extended, core, solver, weights={}, epsilon=1e-5):
    """Run FastGapFill gap-filling algorithm by calling
    :func:`psamm.fastcore.fastcore`.

    FastGapFill will try to find a minimum subset of reactions that includes
    the core reactions and it also has no blocked reactions.
    Return the set of reactions in the minimum subset. An extended model that
    includes artificial transport and exchange reactions can be generated by
    calling :func:`.create_extended_model`.

    Args:
        model: :class:`psamm.metabolicmodel.MetabolicModel`.
        core: reactions in the original metabolic model.
        weights: a weight dictionary for reactions in the model.
        solver: linear programming library to use.
        epsilon: float number, threshold for Fastcore algorithm.
    """

    # Run Fastcore and print the induced reaction set
    logger.info('Calculating Fastcore induced set on model')
    induced = fastcore(
        model_extended, core, epsilon=1e-5, weights=weights, solver=solver)
    logger.debug('Result: |A| = {}, A = {}'.format(len(induced), induced))
    added_reactions = induced - core
    logger.debug('Extended: |E| = {}, E = {}'.format(
        len(added_reactions), added_reactions))
    return induced
