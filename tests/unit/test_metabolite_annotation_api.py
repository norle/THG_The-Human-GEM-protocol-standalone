from functions import function_metabolite_identification as legacy_metabolites

import thg_protocol.annotation.metabolites as metabolites


def test_metabolite_annotation_api_exposes_characterized_helper_names():
    assert "identify_metabolite" in metabolites.__all__
    assert "formula_similarity" in metabolites.__all__
    assert "process_annotation" in metabolites.__all__


def test_metabolite_annotation_legacy_wrapper_reexports_package_api():
    assert legacy_metabolites.identify_metabolite is metabolites.identify_metabolite
    assert legacy_metabolites.formula_similarity is metabolites.formula_similarity
    assert legacy_metabolites.process_annotation is metabolites.process_annotation
