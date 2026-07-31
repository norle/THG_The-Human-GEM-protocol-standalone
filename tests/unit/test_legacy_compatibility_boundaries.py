"""Contract tests for source-checkout compatibility adapters."""

from __future__ import annotations

import json

import cobra


def _model(name: str, *, include_isolated: bool = False) -> cobra.Model:
    model = cobra.Model(name)
    left = cobra.Metabolite("A_c", compartment="c", formula="C")
    right = cobra.Metabolite("B_c", compartment="c", formula="C")
    reaction = cobra.Reaction("R1")
    reaction.add_metabolites({left: -1, right: 1})
    model.add_reactions([reaction])
    if include_isolated:
        model.add_metabolites([cobra.Metabolite("orphan_c", compartment="c")])
    return model


def test_legacy_mass_balance_adapter_returns_balanced_coefficients():
    from functions.functions_mass_balance import RxnBalance2

    result = RxnBalance2("H2 + O2 -> H2O", "R1")

    assert result[0:2] == ([2.0, 1.0], [2.0])
    assert result[-1] == 1


def test_legacy_merge_variants_delegate_to_non_mutating_package_merge():
    from functions.functions_merge_metabolic_networks import (
        network_metabolites_merge,
        network_reactions_merge_4,
    )

    base = _model("base")
    incoming = _model("incoming")
    incoming.add_metabolites(
        [cobra.Metabolite("C_c", compartment="c", formula="C")]
    )

    merged, mapping = network_metabolites_merge(base, incoming)
    assert merged.metabolites.has_id("C_c")
    assert mapping["A_c"] == "A_c"
    assert not base.metabolites.has_id("C_c")

    merged, overlap, new, inconsistent = network_reactions_merge_4(
        base, incoming, {}, {}
    )
    assert merged.reactions.has_id("R1")
    assert overlap == ["R1"]
    assert new == []
    assert inconsistent == []


def test_legacy_consistency_adapter_uses_structural_and_formula_checks():
    from functions.functions_network_consistency import (
        test_find_disconnected,
        test_reaction_mass_balance,
        test_stoichiometric_consistency,
    )

    model = _model("balanced", include_isolated=True)

    assert test_stoichiometric_consistency(model)
    assert test_reaction_mass_balance(model) == []
    assert test_find_disconnected(model) == ["orphan_c"]


def test_network_compatibility_cleanup_and_report_are_explicit(tmp_path):
    from network_analysis.find_components import find_network_components

    output_model = tmp_path / "cleaned.json"
    report_path = tmp_path / "components.json"
    result = find_network_components(
        _model("network", include_isolated=True),
        cleanup=True,
        cleanup_save_path=output_model,
        visualize=True,
        viz_output_path=report_path,
        verbose=False,
    )

    assert not result["model"].metabolites.has_id("orphan_c")
    assert output_model.exists()
    assert json.loads(report_path.read_text())["is_fully_connected"]
