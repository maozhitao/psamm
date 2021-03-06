Reactant/Product Pair Prediction Using FindPrimaryPairs
========================================================

This tutorial will go over how to use the ``primarypairs`` function
in `PSAMM`. This functions can be used to predict reactant/product pairs in metabolic
models.

.. contents::
   :depth: 1
   :local:

Materials
---------

For information on how to install `PSAMM` and the associated requirements, as well
how to download the materials required for this tutorial, you can reference the
Installation and Materials section of the tutorial.

.. note::

   Graphviz download: https://www.graphviz.org/download/

   Graphviz python bindings: https://pypi.org/project/graphviz/
   or
   (psamm-env) $ pip install graphviz

For this part of the tutorial, we will be using a modified version of the *E. coli*
core metabolic model that has been used in the other sections of the tutorial.
This model has been modified to add in a new pathway for the utilization of
mannitol as a carbon source. To access this model and the other files needed you
will need to go into the tutorial-part-4 folder located in the psamm-tutorial folder.

.. code-block:: shell

    (psamm-env) $ cd <PATH>/tutorial-part-4/

Once in this folder, you should see a folder called E_coli_yaml which contains
all of the files required to run the commands in this tutorial.

To run the following tutorials, go into the E_coli_yaml/ directory:

.. code-block:: shell

   (psamm-env) $ cd E_coli_yaml/



Reactant/Product Pair Prediction using `PSAMM`
----------------------------------------------
Metabolism can be broken down into individual metabolic reactions, which transfer elements
between different metabolites. Take the following reaction as an example:

.. code-block:: shell

   Acetate + ATP <=> Acetyl-Phosphate + ADP

This reaction is catalyzed by the enzyme Acetate Kinase, which can convert acetate
to acetyl-phosphate through the addition of a phosphate group from ATP.
A basic understanding of phosphorylation and the biological role of ATP makes
it possible to manually predict that the primary element transfers for
non hydrogen elements are as follows:


===========================         ==============================
Reactant/Product Pair               Element Transfer
===========================         ==============================
Acetate -> Acetyl-Phosphate         carbon backbone
ATP -> ADP                          carbon backbone and phosphates
ATP -> Acetyl-Phosphate             phosphate group
Acetate -> ADP                      None
===========================         ==============================

While manually inferring thi for one or two simple reactions is possible,
genome scale models often contain hundreds or thousands of reactions,
making manual reactant/product pair prediction impractical.
In addition to this, reaction mechanisms are often not known, nor are patterns
of element transfer within reactions available for most metabolic reactions.

To address this problem the `FindPrimaryPairs` algorithm [Steffensen17]_ was
developed and implemented within the `PSAMM` function ``primarypairs``.

The `FindPrimaryPairs` is an iterative algorithm which is used to predict element
transferring reactant/product pairs in genome scale models. `FindPrimaryPairs` relies
on two sources of information, which are generally available in genome scale models:
reaction stoichiometry and metabolite formulas. From this information, `FindPrimaryPairs`
can make a global prediction of element transferring reactant/product pairs without any
additional information about reaction mechanisms.

.. _exclude-fpp:

Basic Use of the ``primarypairs`` Command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``primarypairs`` command in PSAMM can be used to perform an element transferring pair
prediction using the `FindPrimaryPairs` algorithm. The basic command can be run as the following:

.. code-block:: shell

   (psamm-env) $ psamm-model primarypairs --exclude @../additional_files/exclude.tsv


This function often requires a file to be provided through the ``--exclude`` option. This file
is a single column list of reaction IDs of any reactions the user wants to remove from the
model when doing the reactant/product pair prediction. the file path should be included in
the command with a '@' preceding it. Typically, this file should contain any
artificial reactions that might be in the model such as Biomass objective reactions, macromolecule
synthesis reactions, etc. While these reactions can be left in the model, the fractional stoichiometries
and presence of artificial metabolites in the reaction can cause the algorithm to take a much longer
time to find a solution. In this example of the *E. coli* core model the only reaction
like this is the biomass reaction ``Biomass_Ecoli_core_w_GAM``, which this is the only reaction listed
in the `exclude.tsv` file.

.. note::

   The `FindPrimaryPairs` algorithm relies on metabolite formulas to make its reactant/product pair
   predictions. If any reaction contains a metabolite that does not have a formula
   then it will be ignored.

The output of the above command will look like the following:

.. code-block:: shell

   INFO: Model: Ecoli_core_model
   INFO: Model version: 3ac8db4
   INFO: Using default element weights for fpp: C=1, H=0, *=0.82
   INFO: Iteration 1: 79 reactions...
   INFO: Iteration 2: 79 reactions...
   INFO: Iteration 3: 8 reactions...
   GLNS    nh4_c[c]        h_c[c]  H
   FBA     fdp_c[c]        g3p_c[c]        C3H5O6P
   ME2     mal_L_c[c]      nadph_c[c]      H
   MANNI1PDEH      manni1p[c]      nadh_c[c]       H
   PTAr    accoa_c[c]      coa_c[c]        C21H32N7O16P3S
   ....

Basic information about the model name and version is provided in the first few lines. In the next
line, the element weights used by the `FindPrimaryPairs` algorithm are listed.
Then, as the algorithm goes through multiple iterations, it will print out the iteration number and
how many reactions it is still figuring out the pairing for. A four
column table is then printed out that contains the following columns
from left to right: Reaction ID, reactant ID, product ID, and elements transferred.

From this output, the Acetate Kinase reaction from the above example can be compared to
the manual prediction of the element transfer. The reaction ID for this reaction is ACKr:

.. code-block:: shell

   ACKr    atp_c[c]        adp_c[c]        C10H12N5O10P2
   ACKr    atp_c[c]        actp_c[c]       O3P
   ACKr    ac_c[c] actp_c[c]       C2H3O2

From this result it can be seen that the prediction contains the same three element transferring pairs
as the above manual prediction; ATP -> ADP, ATP -> Acetyl-Phosphate, Acetate to Acetyl-Phosphate.

This basic usage of the ``primarypairs`` command allows for quick and accurate prediction of element
transferring pairs in any of the reactions in a genome scale model. Additionally, the function also has a few
other options that can be used to refine and adjust how the pair prediction work.

Modifying Element Weights
~~~~~~~~~~~~~~~~~~~~~~~~~
The metabolite pair prediction relies on a parameter called element weight to inform the algorithm
about what chemical elements should be considered more or less important when determining metabolite
similarity. An example of how this might be used can be seen in the default element weights that are
reported when running ``primarypairs``.

.. code-block:: shell

   INFO: Using default element weights for fpp: C=1, H=0, *=0.82


These element weights are the default weights used when running ``primarypairs`` with the `FindPrimaryPairs`
algorithm. In this case, a weight of 1 is given to carbon. Because carbon forms the structural backbone of many
metabolites this element is given the most weight. In contrast, hydrogen is not usually a major structural
element within metabolites. This leads to a weight of 0 being given to hydrogen, meaning that it is not considered
when comparing formulas between two metabolites. By default, all other elements are given an intermediate weight
of 0.82.

These default element weights can be adjusted using the ``--weights`` command line argument. For example, to adjust
the weight of the element nitrogen while keeping the other elements the same as the default settings, you
could use the following command:

.. code-block:: shell

   (psamm-env) $ psamm-model primarypairs --weights "N=0.2,C=1,H=0,*=0.82" --exclude @../additional_files/exclude.tsv

In the case of a small model like the *E. coli* core model, the results of `primarypairs` will likely not change
unless the weights are drastically altered. However, changes could be seen in larger models, especially if the
models include many reactions related to non-carbon metabolism such as sulfur or nitrogen metabolism.

Report Element
~~~~~~~~~~~~~~

By default, the `primarypairs` result is not filtered to show transfers of any specific element. In certain situations
it might be desirable to only get a subset of these results based on if the reactant/product pair transfers a target
element. To do this, the option ``--report-element`` can be used. In many cases, it might be desirable to only report
carbon transferring reactant/product pairs, to do this run the following on the *E. coli* model.

.. code-block:: shell

   (psamm-env) $ psamm-model primarypairs --report-element C --exclude @../additional_files/exclude.tsv

If the predicted pairs are looked at for one of the mannitol pathway reactions, MANNIDEH, the following can be seen:

.. code-block:: shell

   MANNIDEH        manni[c]        fru_c[c]        C6H12O6
   MANNIDEH        nad_c[c]        nadh_c[c]       C21H26N7O14P2

If this result is compared to the results without the ``--report-element C`` option, it can be seen that when
there are additional transfers in this reaction, but they only involve hydrogen.

.. code-block:: shell

   MANNIDEH        manni[c]        nadh_c[c]       H
   MANNIDEH        manni[c]        h_c[c]  H
   MANNIDEH        manni[c]        fru_c[c]        C6H12O6
   MANNIDEH        nad_c[c]        nadh_c[c]       C21H26N7O14P2


Pair Prediction Methods
~~~~~~~~~~~~~~~~~~~~~~~

Two reactant/product pair prediction algorithms are implemented in the `PSAMM` ``primarypairs`` command.
The default algorithm is the `FindPrimaryPairs` algorithm. The other algorithm that is
implemented is the `Mapmaker` algorithm. These algorithms can be chosen through the ``--method`` argument.

.. code-block:: shell

   $ psammm-model primarypairs --method fpp
   or
   $ psamm-model primarypairs --method mapmaker
