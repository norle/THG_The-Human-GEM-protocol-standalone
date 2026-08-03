"""Characterize archived algorithm fixtures through maintained package APIs."""

from pathlib import Path

import pandas as pd
import pytest

from thg_protocol.annotation.metabolites import identify_metabolite
from thg_protocol.annotation.reactions import (
    execute_jaccard,
    identify_reaction,
    process_reac,
)
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/legacy_characterization"
REACTION_FIXTURES = list(
    pd.read_csv(
        FIXTURE_ROOT / "reac_identification/files/ec-number.tsv", sep="\t"
    ).itertuples(index=False, name=None)
)
METABOLITE_FIXTURES = list(
    pd.read_csv(
        FIXTURE_ROOT / "metabolite_identification/files/kegg.tsv", sep="\t"
    ).itertuples(index=False, name=None)
)


@pytest.mark.parametrize("reaction,expected", REACTION_FIXTURES)
def test_archived_reaction_fixture_uses_package_annotation_api(reaction, expected):
    result = identify_reaction(
        reaction,
        0,
        r"[A-Z]+[0-9]+[a-z]+[0-9]*",
        "MAM02040",
        "MAM02039",
    )
    assert expected in result


@pytest.mark.parametrize("name,formula,identifier,expected", METABOLITE_FIXTURES)
def test_archived_metabolite_fixture_uses_static_pubchem_boundary(
    name, formula, identifier, expected
):
    client = StaticPubChemClient(
        compounds={
            name: PubChemCompound(
                cid=int(expected), molecular_formula=formula, synonyms=(name,)
            )
        }
    )

    result = identify_metabolite(
        name, formula, identifier, threshold=0.70, client=client
    )

    assert result is not None
    assert str(expected) in result


def test_small_sbml_reaction_models_use_package_jaccard_workflow(tmp_path):
    reaction_template = """
    <model>
      <reaction metaid="MAR0001" reversible="false">
        <annotation><rdf:li rdf:resource="http://identifiers.org/kegg.reaction/R00001"/></annotation>
        <listOfReactants>
          <speciesReference species="MAM00001c" stoichiometry="1"/>
        </listOfReactants>
        <listOfProducts>
          <speciesReference species="MAM00002c" stoichiometry="1"/>
        </listOfProducts>
      </reaction>
    </model>
    """
    reverse_template = reaction_template.replace(
        'species="MAM00001c"', 'species="MAM00002c"', 1
    ).replace('species="MAM00002c"', 'species="MAM00001c"', 1)
    left_path = tmp_path / "left.xml"
    right_path = tmp_path / "right.xml"
    left_path.write_text(reaction_template)
    right_path.write_text(reverse_template)

    left = process_reac(str(left_path), r"[A-Z]+[0-9]+[a-z][0-9]*", "", "")
    right = process_reac(str(right_path), r"[A-Z]+[0-9]+[a-z][0-9]*", "", "")
    matches = execute_jaccard(left, right)

    assert matches.shape == (1, 7)
    assert matches.iloc[0, 6] == 2.0
