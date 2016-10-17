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
# Copyright 2015  Keith Dufault-Thompson <keitht547@my.uri.edu>
# Copyright 2017  Jon Lund Steffensen <jon_steffensen@uri.edu>

from __future__ import unicode_literals

import logging

from six import text_type, itervalues

from ..command import Command

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

logger = logging.getLogger(__name__)


class ExcelExportCommand(Command):
    """Export the metabolic model as an Excel workbook."""

    @classmethod
    def init_parser(cls, parser):
        parser.add_argument(
            'file', type=text_type,
            help='File path for writing the Excel workbook')

    def run(self):
        model = self._model
        if xlsxwriter is None:
            self.fail(
                'Excel export requires the XlsxWriter python module'
                ' ("pip install xlsxwriter")')

        workbook = xlsxwriter.Workbook(self._args.file)
        reaction_sheet = workbook.add_worksheet(name='Reactions')

        property_set = set()
        for reaction in model.reactions:
            property_set.update(reaction.properties)
        property_list = list(property_set)
        property_list_sorted = sorted(property_list,
                                      key=lambda x: (x != 'id',
                                                     x != 'equation', x))
        model_reactions = set(model.model)
        for z, i in enumerate(property_list_sorted + ['in_model']):
            reaction_sheet.write_string(0, z, text_type(i))
        for x, i in enumerate(model.reactions):
            for y, j in enumerate(property_list_sorted):
                value = i.properties.get(j)
                if value is not None:
                    reaction_sheet.write_string(x+1, y, text_type(value))
            reaction_sheet.write_string(
                x+1, len(property_list_sorted),
                text_type(i.id in model_reactions))

        compound_sheet = workbook.add_worksheet(name='Compounds')

        compound_set = set()
        for compound in model.compounds:
            compound_set.update(compound.properties)

        compound_list_sorted = sorted(compound_set,
                                      key=lambda x: (x != 'id',
                                                     x != 'name', x))

        metabolic_model = self._model.create_metabolic_model()
        model_compounds = set(x.name for x in metabolic_model.compounds)
        for z, i in enumerate(compound_list_sorted + ['in_model']):
            compound_sheet.write_string(0, z, text_type(i))
        for x, i in enumerate(model.compounds):
            for y, j in enumerate(compound_list_sorted):
                value = i.properties.get(j)
                if value is not None:
                    compound_sheet.write_string(x+1, y, text_type(value))
            compound_sheet.write_string(
                x+1, len(compound_list_sorted),
                text_type(i.id in model_compounds))

        exchange_sheet = workbook.add_worksheet(name='Exchange')

        exchange_sheet.write_string(0, 0, 'Compound ID')
        exchange_sheet.write_string(0, 1, 'Reaction ID')
        exchange_sheet.write_string(0, 2, 'Lower Limit')
        exchange_sheet.write_string(0, 3, 'Upper Limit')

        default_flux = model.default_flux_limit

        for x, (compound, reaction, lower, upper) in enumerate(
                itervalues(model.exchange)):
            if lower is None:
                lower = -default_flux

            if upper is None:
                upper = default_flux

            exchange_sheet.write(x+1, 0, text_type(compound))
            exchange_sheet.write(x+1, 1, text_type(reaction))
            exchange_sheet.write(x+1, 2, text_type(lower))
            exchange_sheet.write(x+1, 3, text_type(upper))

        limits_sheet = workbook.add_worksheet(name='Limits')

        limits_sheet.write_string(0, 0, 'Reaction ID')
        limits_sheet.write_string(0, 1, 'Lower Limit')
        limits_sheet.write_string(0, 2, 'Upper Limit')

        for x, limit in enumerate(itervalues(model.limits)):
            reaction_id, lower, upper = limit
            if lower is None:
                lower = -default_flux

            if upper is None:
                upper = default_flux

            limits_sheet.write(x+1, 0, reaction_id)
            limits_sheet.write(x+1, 1, lower)
            limits_sheet.write(x+1, 2, upper)

        model_info = workbook.add_worksheet(name='Model Info')

        model_info.write(0, 0, ('Model Name: {}'.format(model.name)))
        model_info.write(
            1, 0, ('Biomass Reaction: {}'.format(model.biomass_reaction)))
        model_info.write(
            2, 0, ('Default Flux Limits: {}'.format(model.default_flux_limit)))
        if model.version_string is not None:
            model_info.write(
                3, 0, ('Version: {}'.format(model.version_string)))

        workbook.close()
