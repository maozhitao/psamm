
"""Module for reading and writing native formats

These formats are either table-based or YAML-based. Table-based formats
are space-separated and empty lines are ignored. Comments starting with
pound (#). YAML-based formats are structured data following the YAML
specification.
"""

from __future__ import absolute_import

import os
import logging
import re
import csv

import yaml

from ..reaction import Reaction, Compound
from . import modelseed


# Module-level logging
logger = logging.getLogger(__name__)

# Model files to try to open if a directory was specified
DEFAULT_MODEL = ('model.yaml', 'model.yml')
# Default directory to look for reaction files
DEFAULT_REACTIONS_DIR = 'reactions'


class ParseError(Exception):
    """Exception used to signal errors while parsing"""


class FilePathContext(object):
    """A file context that keeps track of contextual information

    When a file is loaded, all files specified in that file must be loaded
    relative to the first file. This is made possible by keeping a context
    that remembers where a file was loaded so that other files can be loaded
    relatively.
    """

    def __init__(self, arg):
        """Create new context from a path or existing context"""

        if isinstance(arg, basestring):
            self._filepath = arg
        else:
            self._filepath = arg.filepath
        self._basepath = os.path.dirname(self._filepath)

    @property
    def filepath(self):
        return self._filepath

    @property
    def basepath(self):
        return self._basepath

    def resolve(self, relpath):
        return FilePathContext(os.path.join(self.basepath, relpath))

    def __str__(self):
        return self.filepath


def whendefined(func, value):
    """Apply func to value if value is not None"""
    return func(value) if value is not None else None


class CompoundEntry(object):
    """Representation of a compound entry in a native model"""

    def __init__(self, id, properties):
        self._id = id
        self._properties = dict(properties)
        self._name = self._properties.get('name')
        self._formula = self._properties.get('formula')
        self._charge = whendefined(int, self._properties.get('charge'))

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def formula(self):
        return self._formula

    @property
    def charge(self):
        return self._charge

    @property
    def properties(self):
        return self._properties


class NativeModel(object):
    """Represents a model specified using the native data formats

    The model is created from a model file or from a directory containing a
    model file using the default file name (model.yaml or model.yml). This file
    can specify the model fully or refer to other files within the same
    directory subtree that specifes part of the model.
    """

    def __init__(self, path):
        """Create a model from the specified model file or directory"""

        if os.path.isfile(path):
            self._context = FilePathContext(path)
            with open(self._context.filepath, 'r') as f:
                self._model = yaml.load(f)
        else:
            # Try to open the default file
            for filename in DEFAULT_MODEL:
                try:
                    self._context = FilePathContext(
                        os.path.join(path, filename))
                    with open(self._context.filepath, 'r') as f:
                        self._model = yaml.load(f)
                        break
                except Exception as e:
                    logger.debug('Failed to load model file', exc_info=True)
            else:
                # No model could be loaded
                raise ParseError('No model file could be found ({})'.format(
                    ', '.join(DEFAULT_MODEL)))

    def get_biomass_reaction(self):
        """Return the biomass reaction specified by the model"""
        return self._model.get('biomass', None)

    def parse_reactions(self):
        """Yield tuples of reaction ID and reactions defined in the model"""

        # Parse reaction files in the reactions directory
        context = self._context.resolve(DEFAULT_REACTIONS_DIR)
        if os.path.isdir(context.filepath):
            for filename in os.listdir(context.filepath):
                filepath = os.path.join(context.filepath, filename)
                file_context = context.resolve(filepath)
                for reaction_id, reaction in parse_reaction_file(file_context):
                    yield reaction_id, reaction

        # Parse reactions defined in the main model file
        if 'reactions' in self._model:
            for reaction_id, reaction in parse_reaction_list(
                    self._context, self._model['reactions']):
                yield reaction_id, reaction

    def parse_model(self):
        """Yield reaction IDs of model reactions"""

        if 'model' in self._model:
            for reaction_id in parse_model_group_list(
                    self._context, self._model['model']):
                yield reaction_id
        else:
            for reaction_id, _ in self.parse_reactions():
                yield reaction_id

    def parse_limits(self):
        """Yield tuples of reaction ID, lower, and upper bound flux limits"""

        for limits_table in self._model.get('limits', []):
            limits_context = self._context.resolve(limits_table)
            for reaction_id, lower, upper in parse_limits_file(limits_context):
                yield reaction_id, lower, upper

    def parse_media(self):
        """Yield each medium defined in the model

        A medium is a generator of tuples of compound, lower, and upper bound
        flux limits
        """

        if 'media' in self._model:
            if not isinstance(self._model['media'], list):
                raise ParseError('Expected media to be a list')

            for medium in parse_medium_list(
                    self._context, self._model['media']):
                yield medium

    def parse_compounds(self):
        """Yield CompoundEntries for defined compounds"""

        if 'compounds' in self._model:
            for compound in parse_compound_list(
                    self._context, self._model['compounds']):
                yield compound


def parse_compound(compound_def):
    """Parse a structured compound definition as obtained from a YAML file

    Returns a CompoundEntry."""

    compound_id = compound_def.get('id')
    if compound_id is None:
        raise ParseError('Compound ID missing')

    return CompoundEntry(compound_id, compound_def)


def parse_compound_list(path, compounds):
    """Parse a structured list of compounds as obtained from a YAML file

    Yields CompoundEntries. Path can be given as a string or a context.
    """

    context = FilePathContext(path)

    for compound_def in compounds:
        if 'include' in compound_def:
            file_format = compound_def.get('format')
            include_context = context.resolve(compound_def['include'])
            for compound in parse_compound_file(include_context, file_format):
                yield compound
        else:
            yield parse_compound(compound_def)


def parse_compound_table_file(path, f):
    """Parse a space-separated file containing compound IDs and definitions

    The compound properties are parsed according to the list of properties.
    """

    for row in csv.DictReader(f, delimiter='\t'):
        if 'id' not in row or row['id'].strip() == '':
            raise ParseError('Expected `id` column in table')

        props = {key: value for key, value in row.iteritems() if value != ''}
        yield CompoundEntry(row['id'], props)


def parse_compound_yaml_file(path, f):
    """Parse a file as a YAML-format list of compounds

    Path can be given as a string or a context.
    """

    return parse_compound_list(path, yaml.load(f))


def parse_compound_file(path, format):
    """Open and parse reaction file based on file extension or given format

    Path can be given as a string or a context.
    """

    context = FilePathContext(path)

    # YAML files do not need to explicitly specify format
    if (re.match(r'.+\.(yml|yaml)$', context.filepath) and
            (format is None or format == 'yaml')):
        logger.debug('Parsing compound file {} as YAML'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for compound in parse_compound_yaml_file(context, f):
                yield compound
    elif format == 'modelseed':
        logger.debug('Parsing compound file {} as ModelSEED TSV'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for compound in modelseed.parse_compound_file(f):
                yield compound
    elif format.startswith('tsv'):
        logger.debug('Parsing compound file {} as TSV'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for compound in parse_compound_table_file(context, f):
                yield compound
    else:
        raise ParseError('Unable to detect format of compound file {}'.format(
            context.filepath))


def parse_reaction(reaction_def):
    """Parse a structured reaction definition as obtained from a YAML file

    Returns reaction ID and reaction representation.
    """

    reaction_id = reaction_def.get('id')
    if reaction_id is None:
        raise ParseError('Reaction ID missing')

    def parse_compound_list(l):
        """Parse a list of reactants or metabolites"""
        for compound_def in l:
            compound_id = compound_def.get('id')
            if compound_id is None:
                raise ParseError('Compound ID missing')

            value = compound_def.get('value')
            if value is None:
                raise ParseError('Missing value for compound {}'.format(
                    compound_id))

            compound_compartment = compound_def.get('compartment')
            if compound_compartment is None:
                compound_compartment = compartment

            compound = Compound(compound_id, compartment=compound_compartment)
            yield compound, value

    if 'equation' in reaction_def:
        if any(key in reaction_def for key in ('compartment', 'reversible',
                                               'left', 'right')):
            raise ParseError('Reaction {} contains ambiguous fields'.format(
                reaction_id))
        equation = reaction_def.get('equation')
        reaction = modelseed.parse_reaction(equation).normalized()
    else:
        compartment = reaction_def.get('compartment', None)
        reversible = bool(reaction_def.get('reversible', True))
        left = reaction_def.get('left', [])
        right = reaction_def.get('right', [])
        if len(left) == 0 and len(right) == 0:
            raise ParseError('Reaction values are missing')

        reaction = Reaction(Reaction.Bidir if reversible else Reaction.Right,
                            parse_compound_list(left),
                            parse_compound_list(right))

    return reaction_id, reaction


def parse_reaction_list(path, reactions):
    """Parse a structured list of reactions as obtained from a YAML file

    Yields tuples of reaction ID and reaction object. Path can be given as a
    string or a context.
    """

    context = FilePathContext(path)

    for reaction_def in reactions:
        if 'include' in reaction_def:
            include_context = context.resolve(reaction_def['include'])
            for reaction_id, reaction in parse_reaction_file(include_context):
                yield reaction_id, reaction
        else:
            yield parse_reaction(reaction_def)


def parse_reaction_yaml_file(path, f):
    """Parse a file as a YAML-format list of reactions

    Path can be given as a string or a context.
    """

    return parse_reaction_list(path, yaml.load(f))


def parse_reaction_table_file(f):
    """Parse a space-separated file containing reaction IDs and definitions

    The reaction definitions are parsed as ModelSEED format.
    """

    for lineno, line in enumerate(f):
        line, _, comment = line.partition('#')
        line = line.strip()
        if line == '':
            continue

        try:
            reaction_id, equation = line.split(None, 1)
        except ValueError:
            raise ParseError('Error parsing line {}: {}'.format(lineno, line))

        reaction = modelseed.parse_reaction(equation).normalized()
        yield reaction_id, reaction


def parse_reaction_file(path):
    """Open and parse reaction file based on file extension

    Path can be given as a string or a context.
    """

    context = FilePathContext(path)

    if re.match(r'.+\.tsv$', context.filepath):
        logger.debug('Parsing reaction file {} as TSV'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for reaction_id, reaction in parse_reaction_table_file(f):
                yield reaction_id, reaction
    elif re.match(r'.+\.(yml|yaml)$', context.filepath):
        logger.debug('Parsing reaction file {} as YAML'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for reaction_id, reaction in parse_reaction_yaml_file(context, f):
                yield reaction_id, reaction
    else:
        raise ParseError('Unable to detect format of reaction file {}'.format(
            context.filepath))


def parse_medium(medium_def):
    """Parse a structured medium definition as obtained from a YAML file

    Returns in iterator of compound, lower and upper bounds.
    """

    default_compartment = medium_def.get('compartment')

    for compound_def in medium_def.get('compounds', []):
        compartment = compound_def.get('compartment', default_compartment)
        compound = Compound(compound_def['id'], compartment=compartment)
        lower = compound_def.get('lower')
        upper = compound_def.get('upper')
        yield compound, lower, upper


def parse_medium_list(path, media):
    """Parse a structured list of media as obtained from a YAML file

    Yields tuples of compound, lower and upper flux bounds. Path can be given
    as a string or a context.
    """

    context = FilePathContext(path)

    for medium_def in media:
        if 'include' in medium_def:
            include_context = context.resolve(medium_def['include'])
            yield parse_medium_file(include_context)
        else:
            yield parse_medium(medium_def)


def parse_medium_yaml_file(path, f):
    """Parse a file as a YAML-format medium definition

    Path can be given as a string or a context.
    """

    return parse_medium(yaml.load(f))


def parse_medium_table_file(f):
    """Parse a space-separated file containing medium compound flux limits

    The first two columns contain compound IDs and compartment while the
    third column contains the lower flux limits. The fourth column is
    optional and contains the upper flux limit.
    """

    for line in f:
        line, _, comment = line.partition('#')
        line = line.strip()
        if line == '':
            continue

        # A line can specify lower limit only (useful for
        # exchange reactions), or both lower and upper limit.
        fields = line.split(None)
        if len(fields) < 2 or len(fields) > 4:
            raise ParseError('Malformed compound limit: {}'.format(fields))

        # Extend to four values and unpack
        fields.extend(['-']*(4-len(fields)))
        compound_id, compartment, lower, upper = fields

        compound = Compound(compound_id, compartment)
        lower = float(lower) if lower != '-' else None
        upper = float(upper) if upper != '-' else None

        yield compound, lower, upper


def parse_medium_file(path):
    """Parse a file as a list of medium compounds with flux limits

    The file format is detected and the file is parsed accordingly. Path can
    be given as a string or a context.
    """

    context = FilePathContext(path)

    if re.match(r'.+\.tsv$', context.filepath):
        logger.debug('Parsing medium file {} as TSV'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for compound, lower, upper in parse_medium_table_file(f):
                yield compound, lower, upper
    elif re.match(r'.+\.(yml|yaml)$', context.filepath):
        logger.debug('Parsing medium file {} as YAML'.format(
            context.filepath))
        with open(context.filepath, 'r') as f:
            for compound, lower, upper in parse_medium_yaml_file(context, f):
                yield compound, lower, upper
    else:
        raise ParseError('Unable to detect format of medium file {}'.format(
            context.filepath))


def parse_limits_table_file(f):
    """Parse a space-separated file containing reaction flux limits

    The first column contains reaction IDs while the second column contains
    the lower flux limits. The third column is optional and contains the
    upper flux limit.
    """

    for line in f:
        line, _, comment = line.partition('#')
        line = line.strip()
        if line == '':
            continue

        # A line can specify lower limit only (useful for
        # exchange reactions), or both lower and upper limit.
        fields = line.split(None)
        if len(fields) == 2:
            reaction_id, lower = fields
            yield reaction_id, float(lower), None
        elif len(fields) == 3:
            reaction_id, lower, upper = fields
            yield reaction_id, float(lower), float(upper)
        else:
            raise ParseError('Malformed reaction limit: {}'.format(fields))


def parse_limits_file(path):
    """Parse a file as a list of reaction flux limits

    The file format is detected and the file is parsed accordingly. Path can
    be given as a string or a context.
    """

    context = FilePathContext(path)
    logger.debug('Parsing limits file {}'.format(context.filepath))
    with open(context.filepath, 'r') as f:
        for reaction_id, lower, upper in parse_limits_table_file(f):
            yield reaction_id, lower, upper


def parse_model_group(path, group):
    """Parse a structured model group as obtained from a YAML file

    Path can be given as a string or a context.
    """

    context = FilePathContext(path)

    for reaction_id in group.get('reactions', []):
        yield reaction_id

    # Parse subgroups
    for reaction_id in parse_model_group_list(
            context, group.get('groups', [])):
        yield reaction_id


def parse_model_group_list(path, groups):
    """Parse a structured list of model groups as obtained from a YAML file

    Yields reaction IDs. Path can be given as a string or a context.
    """

    context = FilePathContext(path)
    for model_group in groups:
        if 'include' in model_group:
            include_context = context.resolve(model_group['include'])
            for reaction_id in parse_model_file(include_context):
                yield reaction_id
        else:
            for reaction_id in parse_model_group(context, model_group):
                yield reaction_id


def parse_model_yaml_file(path, f):
    """Parse a file as a YAML-format list of model reaction groups

    Path can be given as a string or a context.
    """
    return parse_model_group_list(path, yaml.load(f))


def parse_model_table_file(path, f):
    """Parse a file as a list of model reactions

    Yields reactions IDs. Path can be given as a string or a context.
    """

    for line in f:
        line, _, comment = line.partition('#')
        line = line.strip()
        if line == '':
            continue

        yield line


def parse_model_file(path):
    """Parse a file as a list of model reactions

    The file format is detected and the file is parsed accordinly. The file is
    specified as a file path that will be opened for reading. Path can be given
    as a string or a context.
    """

    context = FilePathContext(path)

    if re.match(r'.+\.tsv$', context.filepath):
        logger.debug('Parsing model file {} as TSV'.format(context.filepath))
        with open(context.filepath, 'r') as f:
            for reaction_id in parse_model_table_file(context, f):
                yield reaction_id
    elif re.match(r'.+\.(yml|yaml)$', context.filepath):
        logger.debug('Parsing model file {} as YAML'.format(context.filepath))
        with open(context.filepath, 'r') as f:
            for reaction_id in parse_model_yaml_file(context, f):
                yield reaction_id