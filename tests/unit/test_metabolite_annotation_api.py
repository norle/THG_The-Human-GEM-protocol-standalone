from functions import function_metabolite_identification as legacy_metabolites

import thg_protocol.annotation.metabolites as metabolites
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient


def test_metabolite_annotation_api_exposes_characterized_helper_names():
    assert "identify_metabolite" in metabolites.__all__
    assert "formula_similarity" in metabolites.__all__
    assert "process_annotation" in metabolites.__all__


def test_metabolite_annotation_legacy_wrapper_reexports_package_api():
    assert legacy_metabolites.identify_metabolite is metabolites.identify_metabolite
    assert legacy_metabolites.formula_similarity is metabolites.formula_similarity
    assert legacy_metabolites.process_annotation is metabolites.process_annotation


def test_generate_met_annotation_passes_an_injected_pubchem_client(tmp_path):
    output = tmp_path / "met_annotation.tsv"
    client = StaticPubChemClient(
        {
            "glucose": PubChemCompound(
                5793, "C6H12O6", ("glucose", "C00031"), "InChI=1S/glucose", "KEY"
            )
        }
    )

    annotated, unannotated = metabolites.generate_met_annotation(
        [("glucose", "C6H12O6", "", "MAM00001c")],
        out=output,
        client=client,
        delay_between_requests=0,
    )

    assert len(annotated) == 1
    assert not unannotated
    assert "5793" in output.read_text()
    assert (tmp_path / "met_annotation_failures.tsv").exists()
