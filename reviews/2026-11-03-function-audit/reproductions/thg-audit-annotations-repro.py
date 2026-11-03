"""Assert-based, read-only reproductions for confirmed annotation/GPR findings."""
from pathlib import Path
from tempfile import TemporaryDirectory

from thg_protocol.gpr.ast_gpr import reduce_gpr, sanitize_gpr
from thg_protocol.annotation.metabolites import (
    atom,
    formula_similarity,
    identify_metabolite,
    process_annotation,
)
from thg_protocol.curation.beta1 import generate_curation_proposals
from thg_protocol.curation.beta2 import resolve_compartment
from thg_protocol.services.pubchem import StaticPubChemClient
from cobra import Metabolite, Model, Reaction
from thg_protocol.annotation.reactions import execute_jaccard, process_jaccard, process_reac


def sbml_reaction(rxn_id, species_coefficients):
    reactants = ''.join(
        f'<speciesReference species="{species}" stoichiometry="{coefficient}"/>'
        for species, coefficient in species_coefficients[:2]
    )
    products = ''.join(
        f'<speciesReference species="{species}" stoichiometry="{coefficient}"/>'
        for species, coefficient in species_coefficients[2:]
    )
    return (
        '<model><reaction metaid="MAR0001" reversible="false"><annotation>'
        f'<rdf:li rdf:resource="http://identifiers.org/kegg.reaction/{rxn_id}"/>'
        '<rdf:li rdf:resource="http://identifiers.org/ec-code/+1.2.3.4"/>'
        f'</annotation><listOfReactants>{reactants}</listOfReactants>'
        f'<listOfProducts>{products}</listOfProducts></reaction></model>'
    )


def run_match(left, right, root, case):
    db_path, model_path = root / f'{case}-db.xml', root / f'{case}-model.xml'
    db_path.write_text(sbml_reaction('R00001', left), encoding='utf-8')
    model_path.write_text(sbml_reaction('R00002', right), encoding='utf-8')
    pattern = r'([A-Z][0-9]+[a-z][0-9]*)'
    db = process_reac(str(db_path), pattern, '', '')
    model = process_reac(str(model_path), pattern, '', '')
    matches = execute_jaccard(db, model)
    assigned = process_jaccard(db.copy(), model.copy(), matches.copy())
    return db, model, matches, assigned


# AND and OR are distinct logical operators. Deduplication currently erases
# the broader second branch, so the resulting rule is logically narrower.
rule = '(A and (B and C)) or (A and (B or C))'
assert sanitize_gpr(rule) == '(A and (B and C))'

# OR branches under AND must not be flattened across the parent operator.
assert reduce_gpr('(A or B) and (C or D)').to_string() == '(A or B or C or D)'

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    # 1.4 and 1.49 both round to 1 in `identify_reaction`; the full matching
    # pipeline nevertheless assigns the database reaction to the model one.
    db, model, matches, assigned = run_match(
        [('A00001c', '1.4'), ('A00002c', '1'), ('A00003c', '1')],
        [('A00001c', '1.49'), ('A00002c', '1'), ('A00003c', '1')],
        root,
        'rounding',
    )
    assert db.iloc[0, 8] == model.iloc[0, 8] == '1,1,1'
    assert db.iloc[0, 9] == model.iloc[0, 9] == '1.2.3.4'  # EC is column 9.
    assert not matches.empty and assigned == {'MAR0001': {'kegg.reaction': 'R00001'}}

    # Reordering species references while swapping which species has which
    # coefficient preserves the coefficient list. Set-based species matching
    # plus the independent list comparison accepts different equations.
    db, model, matches, assigned = run_match(
        [('A00001c', '1'), ('A00002c', '2'), ('A00003c', '1')],
        [('A00002c', '1'), ('A00001c', '2'), ('A00003c', '1')],
        root,
        'permutation',
    )
    assert set(db.iloc[0, 5].split(',')) == set(model.iloc[0, 5].split(','))
    assert db.iloc[0, 8] == model.iloc[0, 8] == '1,2,1'
    assert not matches.empty and assigned == {'MAR0001': {'kegg.reaction': 'R00001'}}

# Selenium and sulfur formulas collide in the handpicked atom parser, and the
# resulting wrong CID survives the full candidate check.
selenium, sulfur = 'C3H7NO2Se', 'C3H7NO2S'
assert atom(selenium) == atom(sulfur)
assert formula_similarity(selenium, sulfur) == 1.0
client = StaticPubChemClient({
    'selenocysteine': {'cid': 1, 'formula': sulfur, 'synonyms': ['selenocysteine']}
})
assert '1' in identify_metabolite('selenocysteine', selenium, 'M1', client=client)

# Existing annotation metadata is accidentally passed as the GPR AST input.
model = Model('m')
reaction = Reaction('R')
reaction.add_metabolites({Metabolite('a_c'): -1})
reaction.gene_reaction_rule = 'G1 and G2'
reaction.annotation = {'source': ['existing']}
model.add_reactions([reaction])
try:
    generate_curation_proposals(model, subunit_stoichiometry={'R': {'G1': 2}})
except AttributeError as error:
    assert 'kind' in str(error)
else:
    raise AssertionError('annotated S-GPR proposal failure was not reproduced')

# Equal-distance CCO paths lose the component_of edge preference.
graph = {
    'X': {'name': 'thing', 'component_of': ['C'], 'superclasses': ['M']},
    'C': {'name': 'Cytosol'},
    'M': {'name': 'Mitochondria'},
}
resolution = resolve_compartment(
    'thing', 'X', graph, {'c': 'Cytosol', 'm': 'Mitochondria'}
)
assert resolution['reason'] == 'ambiguous-compartment-resolution'

# An empty annotation report aborts downstream parsing when every lookup fails.
with TemporaryDirectory() as temporary:
    empty = Path(temporary) / 'empty.tsv'
    empty.write_text('', encoding='utf-8')
    try:
        process_annotation(empty)
    except Exception as error:
        assert type(error).__name__ == 'EmptyDataError'
    else:
        raise AssertionError('empty annotation failure was not reproduced')

# A valid boundary reaction with an empty reactant list currently aborts parsing.
with TemporaryDirectory() as temporary:
    path = Path(temporary) / 'boundary.xml'
    path.write_text(
        '<model><reaction id="sink" reversible="false">'
        '<listOfReactants></listOfReactants>'
        '<listOfProducts><speciesReference species="MAM00001c" stoichiometry="1"/>'
        '</listOfProducts></reaction></model>',
        encoding='utf-8',
    )
    try:
        process_reac(str(path), r'MAM[0-9]+[a-z][0-9]*', '', '')
    except IndexError:
        pass
    else:
        raise AssertionError('empty-sided reaction should reproduce current parser failure')

print('All full-pipeline assertions reproduced.')
