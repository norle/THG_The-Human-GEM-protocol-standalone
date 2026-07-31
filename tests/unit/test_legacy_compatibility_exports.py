"""Parity checks for legacy modules that are pure package re-export adapters."""

from __future__ import annotations

import importlib

import cobra
import pytest

_REEXPORTS = (
    (
        "functions",
        "thg_protocol.pathway",
        (
            "add_compartment",
            "build_reaction_from_config",
            "check_pathway_exists",
            "create_compartment_metabolites",
            "create_compartment_reactions",
            "find_metabolite_by_annotation",
            "find_metabolite_robust",
            "get_next_metabolite_id",
            "get_next_reaction_id",
            "parse_reaction_equation",
            "parse_universal_reaction",
            "select_pathway_metabolites",
            "substitute_compartment_abbreviations",
        ),
    ),
    (
        "functions.config",
        "thg_protocol.config",
        (
            "get_compartments",
            "get_model_paths",
            "get_project_root",
            "load_config",
            "resolve_all_compartments",
            "resolve_compartment_abbreviation",
        ),
    ),
    (
        "functions.pathway_builder",
        "thg_protocol.pathway.core",
        (
            "add_compartment",
            "build_reaction_from_config",
            "check_pathway_exists",
            "create_compartment_metabolites",
            "create_compartment_reactions",
            "create_metabolite_in_new_compartment",
            "find_metabolite_by_annotation",
            "find_metabolite_by_formula_in_model",
            "find_metabolite_robust",
            "get_metabolite_id_base",
            "get_next_metabolite_id",
            "get_next_reaction_id",
            "parse_reaction_equation",
            "parse_universal_reaction",
            "select_pathway_metabolites",
            "substitute_compartment_abbreviations",
        ),
    ),
    (
        "functions.gpr.ast_gpr",
        "thg_protocol.gpr.ast_gpr",
        (
            "compare_ast",
            "deduplicate_gpr",
            "divide_gpr_in_ors",
            "reduce_gpr",
            "sanitize_gpr",
        ),
    ),
    (
        "functions.function_reac_identification",
        "thg_protocol.annotation.reactions",
        (
            "execute_jaccard",
            "gather_kegg_metabolites",
            "identify_reaction",
            "jaccard",
            "process_jaccard",
            "process_reac",
            "replace_met_id_by_met_kegg",
        ),
    ),
    (
        "functions.function_metabolite_identification",
        "thg_protocol.annotation.metabolites",
        (
            "PubChemClient",
            "PubChemClientProtocol",
            "atom",
            "formula_similarity",
            "gather_metabolites",
            "global_met_annotation_file",
            "identify_metabolite",
            "remove_null_value",
            "setup_proxy",
        ),
    ),
    (
        "network_analysis.compaction",
        "thg_protocol.analysis.compaction",
        (
            "are_reactions_proportional",
            "combine_identical_reactions",
            "full_compaction",
        ),
    ),
    (
        "functions.functions_merge_metabolic_networks",
        "thg_protocol.merge",
        ("MergeReport", "merge_models", "merge_models_from_paths"),
    ),
    (
        "functions.functions_network_consistency",
        "thg_protocol.analysis.consistency",
        (
            "blocked_reactions",
            "charge_balance",
            "dead_end_metabolites",
            "metabolites_not_consumed",
            "metabolites_not_produced",
            "orphan_metabolites",
            "reaction_balance",
            "stoichiometrically_balanced_cycles",
            "unbalanced_reactions",
            "unbalanced_reactions_by_charge",
            "unbounded_reactions",
        ),
    ),
)


@pytest.mark.parametrize("legacy_path, package_path, symbols", _REEXPORTS)
def test_legacy_reexports_are_exact_package_symbols(
    legacy_path: str, package_path: str, symbols: tuple[str, ...]
):
    legacy = importlib.import_module(legacy_path)
    package = importlib.import_module(package_path)

    for symbol in symbols:
        assert getattr(legacy, symbol) is getattr(package, symbol)


@pytest.mark.parametrize(
    ("legacy_path", "package_path", "symbol", "args"),
    (
        (
            "functions.gpr.ast_gpr",
            "thg_protocol.gpr.ast_gpr",
            "sanitize_gpr",
            ("gene_a and (gene_b or gene_c)",),
        ),
        (
            "functions.function_reac_identification",
            "thg_protocol.annotation.reactions",
            "jaccard",
            (["A", "B"], ["B", "C"]),
        ),
    ),
)
def test_legacy_reexports_preserve_deterministic_behavior(
    legacy_path: str, package_path: str, symbol: str, args: tuple
):
    legacy = importlib.import_module(legacy_path)
    package = importlib.import_module(package_path)

    assert getattr(legacy, symbol)(*args) == getattr(package, symbol)(*args)


def test_legacy_compaction_reexport_preserves_reaction_behavior():
    legacy = importlib.import_module("network_analysis.compaction")
    package = importlib.import_module("thg_protocol.analysis.compaction")
    left = cobra.Reaction("left")
    right = cobra.Reaction("right")
    left.add_metabolites(
        {cobra.Metabolite("A"): -1.0, cobra.Metabolite("B"): 1.0}
    )
    right.add_metabolites(
        {cobra.Metabolite("A"): -2.0, cobra.Metabolite("B"): 2.0}
    )

    assert legacy.are_reactions_proportional(left, right) == (
        package.are_reactions_proportional(left, right)
    )
