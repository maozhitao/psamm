#!/usr/bin/env python
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

from setuptools import setup, find_packages

# Read long description
with open('README.rst') as f:
    long_description = f.read()

setup(
    name='psamm',
    version='0.30',
    description='PSAMM metabolic modeling tools',
    maintainer='Jon Lund Steffensen',
    maintainer_email='jon_steffensen@uri.edu',
    url='https://github.com/zhanglab/psamm',
    license='GNU GPLv3+',

    long_description=long_description,

    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],

    packages=find_packages(),

    entry_points='''
        [console_scripts]
        psamm-model = psamm.command:main
        psamm-sbml-model = psamm.command:main_sbml
        psamm-list-lpsolvers = psamm.lpsolver.generic:list_solvers
        psamm-import = psamm.importer:main
        psamm-import-bigg = psamm.importer:main_bigg

        [psamm.commands]
        chargecheck = psamm.commands.chargecheck:ChargeBalanceCommand
        console = psamm.commands.console:ConsoleCommand
        duplicatescheck = psamm.commands.duplicatescheck:DuplicatesCheck
        excelexport = psamm.commands.excelexport:ExcelExportCommand
        fastgapfill = psamm.commands.fastgapfill:FastGapFillCommand
        fba = psamm.commands.fba:FluxBalanceCommand
        fluxcheck = psamm.commands.fluxcheck:FluxConsistencyCommand
        fluxcoupling = psamm.commands.fluxcoupling:FluxCouplingCommand
        formulacheck = psamm.commands.formulacheck:FormulaBalanceCommand
        fva = psamm.commands.fva:FluxVariabilityCommand
        gapcheck = psamm.commands.gapcheck:GapCheckCommand
        gapfill = psamm.commands.gapfill:GapFillCommand
        genedelete = psamm.commands.genedelete:GeneDeletionCommand
        masscheck = psamm.commands.masscheck:MassConsistencyCommand
        primarypairs = psamm.commands.primarypairs:PrimaryPairsCommand
        randomsparse = psamm.commands.randomsparse:RandomSparseNetworkCommand
        robustness = psamm.commands.robustness:RobustnessCommand
        sbmlexport = psamm.commands.sbmlexport:SBMLExport
        search = psamm.commands.search:SearchCommand
        tableexport = psamm.commands.tableexport:ExportTableCommand

        [psamm.importer]
        JSON = psamm.importers.cobrajson:Importer
        SBML = psamm.importers.sbml:NonstrictImporter
        SBML-strict = psamm.importers.sbml:StrictImporter
    ''',

    test_suite='psamm.tests',

    install_requires=[
        'PyYAML~=3.11',
        'six',
        'xlsxwriter'
    ],
    extras_require={
        'docs': ['sphinx', 'sphinx_rtd_theme', 'mock'],
        ':python_version=="2.7"': ['enum34'],
        ':python_version=="3.3"': ['enum34']
    })
