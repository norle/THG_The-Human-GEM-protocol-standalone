"""Contract tests for maintained package boundaries."""

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
    from thg_protocol.model_build.mass_balance import balance_equation

    assert balance_equation("H2 + O2 -> H2O") == ([2.0, 1.0], [2.0])


def test_legacy_merge_variants_delegate_to_non_mutating_package_merge():
    from thg_protocol.merge import merge_models

    base = _model("base")
    incoming = _model("incoming")
    incoming.add_metabolites(
        [cobra.Metabolite("C_c", compartment="c", formula="C")]
    )

    merged, report = merge_models(base, incoming)
    assert merged.metabolites.has_id("C_c")
    assert report.added_metabolites == 1
    assert not base.metabolites.has_id("C_c")
    assert merged.reactions.has_id("R1")
    assert report.overlapping_reactions == 1


def test_legacy_consistency_adapter_uses_structural_and_formula_checks():
    from thg_protocol.analysis.consistency import (
        orphan_metabolites,
        unbalanced_reactions,
    )

    model = _model("balanced", include_isolated=True)

    assert unbalanced_reactions(model) == []
    assert orphan_metabolites(model) == ["orphan_c"]


def test_network_compatibility_cleanup_and_report_are_explicit(tmp_path):
    from thg_protocol.analysis import find_network_components, write_component_report

    output_model = tmp_path / "cleaned.json"
    report_path = tmp_path / "components.json"
    result = find_network_components(_model("network", include_isolated=True))
    write_component_report(result, report_path)

    assert result["model"].metabolites.has_id("orphan_c")
    assert not output_model.exists()
    assert not json.loads(report_path.read_text())["is_fully_connected"]
