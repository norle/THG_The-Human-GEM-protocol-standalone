"""Regression cases from reviews/2026-11-03-function-audit (finding numbers)."""

import ast
import copy
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from cobra import Metabolite, Model, Reaction
from cobra.core.gene import GPR

from thg_protocol.analysis.consistency import unbounded_reactions
from thg_protocol.annotation.metabolites import (
    atom,
    formula_similarity,
    identify_metabolite,
    process_annotation,
)
from thg_protocol.annotation.reactions import (
    execute_jaccard,
    process_jaccard,
    process_reac,
)
from thg_protocol.cell_specific import evaluate_gpr_activity
from thg_protocol.curation.beta1 import generate_curation_proposals
from thg_protocol.curation.beta2 import resolve_compartment
from thg_protocol.gapfill import gapfill_model
from thg_protocol.gpr.ast_gpr import compare_ast, reduce_gpr, sanitize_gpr
from thg_protocol.gpr.stoichiometry import sgpr_from_dict
from thg_protocol.model_build.mass_balance import nullity
from thg_protocol.pathway import (
    create_compartment_reactions,
    implement_pathway,
    parse_reaction_equation,
    parse_universal_reaction,
)
from thg_protocol.services.pubchem import StaticPubChemClient
from thg_protocol.workflow.config import ConfigError, load_workflow_config


def _pathway_model():
    return {
        "compartments": {"c": "cytosol"},
        "metabolites": [
            {"id": "MAM00001c", "name": "A", "compartment": "c", "formula": "C"},
            {"id": "MAM00002c", "name": "B", "compartment": "c", "formula": "CH2"},
        ],
        "reactions": [],
    }


def test_f01_rejects_malformed_terms_and_rolls_back_unresolved_equations():
    with pytest.raises(ValueError, match="malformed"):
        parse_reaction_equation("A[c] + malformed --> B[c]")
    model = _pathway_model()
    before = copy.deepcopy(model)
    with pytest.raises(ValueError, match=r"MISSING\[m\]"):
        parse_universal_reaction("A[m] + MISSING[m] --> B[c]", model, {})
    assert model == before


@pytest.mark.parametrize(
    ("left", "right"),
    [("C3H7NO2Se", "C3H7NO2S"), ("NaCl", "Cl"), ("Fe", "F"), ("C2H6", "C3H6")],
)
def test_f02_rejects_non_hydrogen_composition_changes(left, right):
    assert atom(left) != atom(right)
    assert formula_similarity(left, right) == 0
    client = StaticPubChemClient({"compound": {"cid": 1, "formula": right}})
    assert identify_metabolite("compound", left, "M1", client=client) is None


def test_f02_allows_protonation_but_rejects_unknown_formulas():
    assert formula_similarity("C3H7NO2Se", "C3H8NO2Se") == 1
    assert formula_similarity("C3H7NO2Se", "SeO2NH7C3") == 1
    assert formula_similarity("", "") == 0
    assert formula_similarity("invalid", "C") == 0


def _reaction_xml(left, right, identifier="R00001"):
    def side(entries):
        return "".join(
            f'<speciesReference species="{species}" stoichiometry="{coefficient}"/>'
            for species, coefficient in entries
        )

    return (
        '<reaction metaid="MAR0001" reversible="false"><annotation>'
        f'<rdf:li rdf:resource="http://identifiers.org/kegg.reaction/{identifier}"/>'
        "</annotation><listOfReactants>" + side(left) + "</listOfReactants>"
        "<listOfProducts>" + side(right) + "</listOfProducts></reaction>"
    )


def _reaction_table(tmp_path, name, left, right, identifier):
    path = tmp_path / name
    path.write_text(_reaction_xml(left, right, identifier))
    return process_reac(str(path), r"A[0-9]+c", "", "")


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (
            [("A00001c", "1.4"), ("A00002c", "1")],
            [("A00001c", "1.49"), ("A00002c", "1")],
            False,
        ),
        (
            [("A00001c", "1"), ("A00002c", "2")],
            [("A00002c", "1"), ("A00001c", "2")],
            False,
        ),
        (
            [("A00001c", "1"), ("A00002c", "2")],
            [("A00002c", "2"), ("A00001c", "1.0")],
            True,
        ),
    ],
)
def test_f03_matches_exact_species_coefficient_pairs(tmp_path, left, right, expected):
    product = [("A00003c", "1")]
    database = _reaction_table(tmp_path, "db.xml", left, product, "R00001")
    model = _reaction_table(tmp_path, "model.xml", right, product, "R00002")
    matches = execute_jaccard(database, model)
    result = process_jaccard(database.copy(), model.copy(), matches.copy())
    assert bool(result) is expected
    # Postfilter candidates supplied without coefficient filtering, too.
    candidates = execute_jaccard(database.drop(columns=7), model.drop(columns=7))
    assert bool(process_jaccard(database, model, candidates)) is expected


@pytest.mark.parametrize("coefficient,expected", [("3", True), ("2", False)])
def test_f03_repeated_species_keep_each_reference_coefficient(
    tmp_path, coefficient, expected
):
    product = [("A00003c", "1")]
    database = _reaction_table(
        tmp_path, "db.xml", [("A00001c", "1"), ("A00001c", "2")], product, "R00001"
    )
    model = _reaction_table(
        tmp_path, "model.xml", [("A00001c", coefficient)], product, "R00002"
    )
    assert (
        bool(process_jaccard(database, model, execute_jaccard(database, model)))
        is expected
    )


def test_f03_reverse_match_preserves_species_coefficient_pairs(tmp_path):
    left, right = [("A00001c", "1.4"), ("A00002c", "2")], [("A00003c", "3")]
    database = _reaction_table(tmp_path, "db.xml", left, right, "R00001")
    model = _reaction_table(tmp_path, "model.xml", right, left, "R00002")
    assert process_jaccard(database, model, execute_jaccard(database, model)) == {
        "MAR0001": {"kegg.reaction": "R00001"}
    }


def test_f03_checks_later_candidate_after_different_stoichiometry(tmp_path):
    product = [("A00003c", "1")]
    wrong = _reaction_table(
        tmp_path, "wrong.xml", [("A00001c", "2")], product, "R00001"
    )
    correct = _reaction_table(
        tmp_path, "correct.xml", [("A00001c", "1")], product, "R00002"
    )
    model = _reaction_table(
        tmp_path, "model.xml", [("A00001c", "1")], product, "R00003"
    )
    candidates = pd.concat([wrong, correct], ignore_index=True)
    assert execute_jaccard(model, candidates).iloc[0, 3] == "R00002"


@pytest.mark.parametrize(
    ("rule", "transform"),
    [
        ("(A or B) and (C or D)", lambda value: reduce_gpr(value).to_string()),
        ("(A and (B and C)) or (A and (B or C))", sanitize_gpr),
        ("(A and B) or (B and A) or C", sanitize_gpr),
    ],
)
def test_f04_f05_gpr_transformations_preserve_truth_tables(rule, transform):
    original = GPR.from_string(rule)
    result = GPR.from_string(transform(rule))
    for flags in itertools.product((False, True), repeat=len(original.genes)):
        knocked_out = {
            gene
            for gene, flag in zip(sorted(original.genes), flags, strict=True)
            if flag
        }
        assert original.eval(knocked_out) == result.eval(knocked_out)


def test_f05_comparison_requires_matching_operators_and_children():
    def tree(value):
        return ast.parse(value, mode="eval").body

    assert not compare_ast(tree("A and B"), tree("A or B"))
    assert not compare_ast(tree("A and B"), tree("A and B and C"))
    assert compare_ast(tree("A and B"), tree("B and A"))


def test_f06_annotated_subunit_curation_preserves_metadata_and_curated_rule():
    model = Model("subunits")
    reaction = Reaction("R")
    reaction.gene_reaction_rule = "G1 and G2"
    reaction.annotation = {"source": ["existing"]}
    model.add_reactions([reaction])
    proposals = generate_curation_proposals(
        model,
        gene_mapping={"G1": "G3"},
        subunit_stoichiometry={"R": {"G3": 2}},
    )
    result = next(item for item in proposals if item.operation == "annotate-s-gpr")
    assert result.after["source"] == ["existing"]
    assert result.after["thg_s_gpr"]["gpr"] == "G2 and G3"
    assert reaction.annotation == {"source": ["existing"]}


def test_f07_global_reactions_are_added_once_after_all_compartments():
    model = _pathway_model()
    result = implement_pathway(
        model,
        {
            "compartments": [
                {"abbreviation": "c", "name": "cytosol"},
                {"abbreviation": "m", "name": "mitochondria"},
            ],
            "reactions": [{"equation": "A[c] --> B[m]"}],
        },
        {},
    )
    assert result["reactions_added"] == 1
    assert len(result["model"]["reactions"]) == 1
    assert not model["reactions"]


def test_f08_generated_ids_reserve_later_explicit_ids():
    model = _pathway_model()
    config = {
        "reactions": [
            {"equation": "A[c] --> B[c]"},
            {"id": "MAR00001", "equation": "B[c] --> A[c]"},
        ]
    }
    assert create_compartment_reactions(model, {}, "c", config) == 2
    assert [row["id"] for row in model["reactions"]] == ["MAR00002", "MAR00001"]


def test_f08_rejects_conflicting_explicit_ids():
    model = _pathway_model()
    config = {
        "reactions": [
            {"id": "R", "equation": "A[c] --> B[c]"},
            {"id": "R", "equation": "B[c] --> A[c]"},
        ]
    }
    with pytest.raises(ValueError, match="Conflicting explicit reaction ID: R"):
        create_compartment_reactions(model, {}, "c", config)
    assert model == _pathway_model()


@pytest.mark.parametrize(
    "value", [-1, 0, True, "1", None, float("nan"), float("inf"), -float("inf")]
)
def test_f09_invalid_minimum_flux_cannot_report_gapfill_success(value):
    result = gapfill_model(
        _pathway_model(), method="milp", parameters={"minimum_flux": value}
    )
    assert result.status == "failed"
    assert "minimum_flux" in result.failure
    assert not result.selected


def test_f10_empty_annotation_report_is_a_valid_unresolved_result(tmp_path):
    path = tmp_path / "empty.tsv"
    path.touch()
    assert process_annotation(path) == {}


@pytest.mark.parametrize(
    "left,right", [([], [("A00001c", "1")]), ([("A00001c", "1")], [])]
)
def test_f11_boundary_reactions_do_not_abort_annotation(tmp_path, left, right):
    path = tmp_path / "boundary.xml"
    boundary = _reaction_xml(left, right)
    path.write_text(boundary)
    assert process_reac(str(path), r"A[0-9]+c", "", "").empty
    path.write_text(
        boundary.replace("<listOfReactants></listOfReactants>", "")
        + _reaction_xml([("A00001c", "1")], [("A00002c", "1")])
    )
    assert len(process_reac(str(path), r"A[0-9]+c", "", "")) == 1


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), True, "1"]
)
def test_f12_public_activity_evaluator_rejects_invalid_threshold(value):
    with pytest.raises(ValueError, match="threshold"):
        evaluate_gpr_activity("G1", {"G1": 1}, threshold=value)


def test_f12_configuration_rejects_nonfinite_threshold(tmp_path):
    (tmp_path / "model.json").write_text("{}")
    (tmp_path / "expression.tsv").write_text("gene\tvalue\nG1\t1\n")
    path = tmp_path / "config.json"
    for value in (float("nan"), float("inf"), -float("inf")):
        path.write_text(
            json.dumps(
                {
                    "workflow": "cell-specific",
                    "run": {"name": "audit", "output_dir": "out"},
                    "cell_specific": {
                        "input_model": "model.json",
                        "expression_file": "expression.tsv",
                        "gene_identifier_namespace": "ensembl",
                        "threshold": value,
                    },
                }
            )
        )
        with pytest.raises(ConfigError, match="threshold"):
            load_workflow_config(path)


def test_f13_containment_wins_equal_distance_and_cycles_terminate():
    graph = {
        "X": {"name": "thing", "component_of": ["C"], "superclasses": ["M"]},
        "C": {"name": "Cytosol", "component_of": ["X"]},
        "M": {"name": "Mitochondria"},
    }
    result = resolve_compartment(
        "thing", "X", graph, {"c": "Cytosol", "m": "Mitochondria"}
    )
    assert result["target_compartment_id"] == "c"
    assert result["resolution_method"] == "cco-component-of"


def test_f13_mixed_paths_are_ranked_by_their_least_authoritative_edge():
    graph = {
        "X": {"name": "thing", "component_of": ["Y", "Z"]},
        "Y": {"superclasses": ["C"]},
        "Z": {"component_of": ["M"]},
        "C": {"name": "Cytosol"},
        "M": {"name": "Mitochondria"},
    }
    result = resolve_compartment(
        "thing", "X", graph, {"c": "Cytosol", "m": "Mitochondria"}
    )
    assert result["target_compartment_id"] == "m"


def test_f14_validation_configuration_requires_input_model(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "workflow": "validate",
                "run": {"name": "audit", "output_dir": "out"},
                "validation": {},
            }
        )
    )
    with pytest.raises(ConfigError, match="input_model"):
        load_workflow_config(path)
    assert not (tmp_path / "out").exists()


def test_f15_finite_flux_caps_are_not_unbounded():
    model = Model("finite")
    a = Metabolite("a_c", compartment="c")
    source, drain = Reaction("source"), Reaction("drain")
    source.add_metabolites({a: 1})
    drain.add_metabolites({a: -1})
    model.add_reactions([source, drain])
    model.objective = drain
    ids, fraction, fva = unbounded_reactions(model)
    assert fva.loc["drain", "maximum"] == 1000
    assert ids == [] and fraction == 0


def _notebook_function(filename, cell_index, name):
    path = Path(__file__).parents[2] / "supplementary_material" / filename
    source = "".join(json.loads(path.read_text())["cells"][cell_index]["source"])
    node = next(
        item
        for item in ast.parse(source).body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace[name]


@pytest.mark.parametrize(
    "minimum,maximum,removed",
    [(-10, 0, True), (0, 0, False), (-1e-9, 1e-9, False), (0, 10, True)],
)
def test_f16_notebook_blockage_checks_both_flux_endpoints(minimum, maximum, removed):
    function = _notebook_function(
        "crucial_exchange_rs.ipynb", 29, "test_and_remove_rxns"
    )
    function.__globals__["flux_variability_analysis"] = lambda *a, **k: pd.DataFrame(
        {"minimum": [minimum], "maximum": [maximum]}
    )
    restored = []
    model = SimpleNamespace(
        tolerance=1e-7, remove_reactions=lambda _: None, add_reactions=restored.extend
    )
    result = function(model, [SimpleNamespace(id="sink")], [SimpleNamespace(id="R")])
    assert result == (["sink"] if removed else [])
    assert bool(restored) is not removed


@pytest.mark.parametrize(
    "bounds,expected",
    [
        ((-10, 10), ([], [], ["A_c"], [])),
        ((0, 10), (["A_c"], [], [], [])),
        ((-10, 0), ([], ["A_c"], [], [])),
        ((0, 0), ([], [], ["A_c"], [])),
    ],
)
def test_f17_notebook_deadends_respect_bounds(bounds, expected):
    function = _notebook_function("extra.ipynb", 4, "classify_deadend_in_final_model")
    model = Model("directions")
    a, b = Metabolite("A_c", compartment="c"), Metabolite("B_c", compartment="c")
    reaction = Reaction("R", lower_bound=bounds[0], upper_bound=bounds[1])
    reaction.add_metabolites({a: -1, b: 1})
    model.add_reactions([reaction])
    assert function(model, ["A_c"]) == expected


@pytest.mark.parametrize("value", [2.7, True, "2.7", float("nan"), float("inf"), 0, -1])
def test_f18_rejects_invalid_subunit_counts_before_conversion(value):
    with pytest.raises(ValueError):
        sgpr_from_dict({"type": "gene", "gene": "G1", "coefficient": value})


@pytest.mark.parametrize("value", [2, 2.0, "2"])
def test_f18_retains_exact_integer_representations(value):
    assert (
        sgpr_from_dict({"type": "gene", "gene": "G1", "coefficient": value}).coefficient
        == 2
    )


@pytest.mark.parametrize(
    "matrix", [[[0, 1]], [[1, 0], [2, 0]], [[0, 0, 0]], [[1, 2, 3], [2, 4, 6]]]
)
def test_f19_nullity_completion_is_invertible(matrix):
    completed, independent = nullity(matrix)
    width = len(matrix[0])
    assert completed.shape == (width, width)
    assert np.linalg.matrix_rank(completed) == width
    assert len(independent) == np.linalg.matrix_rank(matrix)
    np.testing.assert_allclose(
        completed @ np.linalg.inv(completed), np.eye(width), atol=1e-12
    )


def test_f15_solver_detects_true_unbounded_flux_and_preserves_objective():
    model = Model("unbounded")
    a = Metabolite("a_c", compartment="c")
    source = Reaction("source", upper_bound=float("inf"))
    drain = Reaction("drain", upper_bound=float("inf"))
    source.add_metabolites({a: 1})
    drain.add_metabolites({a: -1})
    model.add_reactions([source, drain])
    original_objective = str(model.objective.expression)
    ids, fraction, fva = unbounded_reactions(model)
    assert set(ids) == {"source", "drain"} and fraction == 1
    assert fva.loc["drain", "maximum"] == float("inf")
    assert str(model.objective.expression) == original_objective
