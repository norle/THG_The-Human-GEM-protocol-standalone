import pytest

from thg_protocol.validation_report import (
    render_validation_html,
    render_validation_summary,
)


def test_report_is_safe_and_surfaces_gate_and_findings():
    report = {
        "validation_profile": "structural-fast",
        "validation": {
            "passed": False,
            "checks": [
                {
                    "id": "unsafe-</pre><script>alert(1)</script>",
                    "family": "structural",
                    "status": "failed",
                    "passed": False,
                    "release_blocking": True,
                    "details": {"ids": ["x"]},
                }
            ],
        },
    }

    html = render_validation_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "unsafe-&lt;/pre&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "FAILED" in html
    assert "unsafe-</pre><script>alert(1)</script>" in render_validation_summary(report)


@pytest.mark.parametrize("failure", ["tasks", "gimme_samples", "gimme_objectives"])
def test_cell_specific_report_preserves_overall_failure(failure):
    report = {
        "status": "failed",
        "after": {"validation": {"passed": True, "checks": []}},
        failure: {"passed": False, "evidence": "failed-evidence"},
    }
    html = render_validation_html(report)
    assert '<p class="gate">FAILED</p>' in html
    assert "failed-evidence" in html
    assert "Overall: **FAILED**" in render_validation_summary(report)


def test_gapfill_report_includes_task_failure_in_overall_result():
    report = {
        "validation": {"passed": True, "checks": []},
        "tasks": {"passed": False},
    }
    assert '<p class="gate">FAILED</p>' in render_validation_html(report)
    assert "Overall: **FAILED**" in render_validation_summary(report)


def test_report_explains_checks_and_summarises_large_evidence():
    statuses = {f"R{index}": "balanced" for index in range(300)} | {
        "R_bad": "unbalanced"
    }
    report = {
        "validation": {
            "passed": True,
            "checks": [
                {
                    "id": "mass-balance",
                    "family": "chemical",
                    "status": "failed",
                    "passed": False,
                    "release_blocking": False,
                    "details": {"statuses": statuses, "unbalanced": ["R_bad"]},
                }
            ],
        },
    }
    html = render_validation_html(report)
    assert (
        '<p class="explain">Compares element counts across internal reactions.' in html
    )
    assert "Why it matters" not in html
    assert "An unbalanced reaction can create or destroy atoms" not in html
    assert "How it works" not in html
    assert "What it checks" not in html
    assert "1 of 301 evaluated reactions are unbalanced." in html
    assert "R_bad" in html
    # The per-reaction map is summarised as counts, not dumped.
    assert "R299" not in html
    assert '"statuses"' not in html


def _proposal(proposal_id, object_id, after, checks, operation="set-stoichiometry"):
    return {
        "proposal_id": proposal_id,
        "operation": operation,
        "object_type": "reaction" if operation == "set-stoichiometry" else "metabolite",
        "object_id": object_id,
        "before": {},
        "after": after,
        "evidence": [],
        "confidence": "low",
        "policy": "integer-stoichiometry",
        "stage": "conservation",
        "status": "proposed",
        "reason": "test </script> reason",
        "metadata": {"rule": "integer-stoichiometry"},
        "checks": checks,
    }


def _report_with_fixes():
    check = {"family": "chemical", "status": "failed", "passed": False}
    return {
        "model_checksum": "abc",
        "validation": {
            "passed": True,
            "checks": [
                {**check, "id": "mass-balance", "details": {"unbalanced": ["R1"]}},
                {**check, "id": "fractional-coefficients", "details": {}},
            ],
            "proposals": [
                _proposal(
                    "prop-a",
                    "R1",
                    {"x": 1},
                    ["mass-balance", "fractional-coefficients"],
                ),
                _proposal("prop-b", "R1", {"x": 2}, ["fractional-coefficients"]),
                _proposal("prop-c", "M1", "C2H4O", ["mass-balance"], "set-formula"),
            ],
            "index": {
                "reactions": {
                    "R1": {
                        "name": "",
                        "equation": "x --> y",
                        "equation_names": "x --> y",
                        "subsystem": "Glycolysis",
                        "bounds": [0, 1000],
                    }
                },
                "metabolites": {},
            },
        },
    }


def test_report_renders_decision_controls_for_proposals():
    html = render_validation_html(_report_with_fixes())
    # Alternatives for one reaction share a fieldset; each check lists it.
    assert html.count('data-group="reaction|R1|"') == 2
    assert html.count('data-group="metabolite|M1|formula"') == 1
    assert html.count('value="prop-b"') == 2
    assert "also suggested by Fractional coefficients" in html
    assert 'class="decision-bar"' in html
    assert '"key": "thg-review:abc"' in html
    assert 'id="thg-index"' in html
    # Embedded JSON cannot close its script element early.
    assert (
        "test </script> reason"
        not in html.split('id="thg-review"')[1].split("</script>")[0]
    )
    assert "thg-run apply-decisions" in html


def test_report_without_proposals_has_no_decision_bar():
    report = _report_with_fixes()
    del report["validation"]["proposals"]
    html = render_validation_html(report)
    assert 'class="decision-bar"' not in html
    assert "<fieldset" not in html


def _check(check_id, details):
    return {
        "id": check_id,
        "family": "chemical",
        "status": "failed",
        "passed": False,
        "release_blocking": False,
        "details": details,
    }


def test_balance_evidence_separates_pool_reactions():
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "checks": [
                    _check(
                        "mass-balance",
                        {
                            "statuses": {
                                "R1": "unbalanced",
                                "P1": "unbalanced-by-design",
                            },
                            "unbalanced": ["R1"],
                            "unbalanced_by_design": {"P1": "pseudo-subsystem"},
                            "imbalance": {"R1": {"H": -2.0}, "P1": {"C": 3.5}},
                        },
                    )
                ],
            }
        }
    )
    assert "Metabolic reactions" in html
    assert "Pool and pseudo-reactions" in html
    assert "Pool or artificial reaction" in html
    assert "H -2" in html and "C +3.5" in html
    assert "1 pool or pseudo-reactions are unbalanced by design" in html


def test_formula_evidence_compares_values_per_compartment():
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "compartments": {"names": {"c": "Cytosol", "m": "Mitochondria"}},
                "checks": [
                    _check(
                        "formula-disagreement",
                        {
                            "across_compartments": {
                                "a": {
                                    "differs": ["formula"],
                                    "metabolites": {
                                        "a_c": {"formula": "C2H6O", "charge": 0},
                                        "a_x": {"formula": "C2H6O", "charge": 0},
                                        "a_m": {"formula": "C2H5O", "charge": 0},
                                    },
                                }
                            },
                            "against_reference": {},
                        },
                    )
                ],
            }
        }
    )
    assert "Values and compartments" in html
    assert '<span class="diff">H -1</span>' in html
    assert ">Mitochondria<" in html


def test_formula_evidence_ranks_equivalent_formulas_together():
    formulas = ["C2H6O", "C2H6O", "H6C2O", "H6C2O", "C2H4O", "C2H4O", "C2H4O"]
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "checks": [
                    _check(
                        "formula-disagreement",
                        {
                            "across_compartments": {
                                "a": {
                                    "differs": ["formula"],
                                    "metabolites": {
                                        f"a_{i}": {"formula": formula, "charge": 0}
                                        for i, formula in enumerate(formulas)
                                    },
                                }
                            },
                            "against_reference": {},
                        },
                    )
                ],
            }
        }
    )
    assert html.count('class="variant"') == 2
    assert '<code>C2H4O</code> <span class="diff">H -2</span>' in html
    assert "H +2" not in html
    assert all(f'title="a_{i}"' in html for i in range(len(formulas)))


def test_blocked_reactions_are_counted_per_compartment():
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "compartments": {
                    "names": {"c": "Cytosol", "m": "Mitochondria"},
                    "reactions": {"c": 10, "c+m": 4},
                },
                "checks": [
                    {
                        **_check(
                            "flux-consistency",
                            {
                                "blocked": ["R1", "R2", "T1"],
                                "by_compartment": {"c": ["R1", "R2"], "c+m": ["T1"]},
                            },
                        ),
                        "family": "solver",
                    },
                    _check("blocked-reaction-singletons", {"sets": [["R1"]]}),
                ],
            }
        }
    )
    assert "Cytosol + Mitochondria" in html
    assert "20%" in html and "25%" in html
    assert "All compartments" in html
    assert "check-blocked-reaction-singletons" not in html


def test_fix_controls_offer_accept_and_reject_only():
    html = render_validation_html(_report_with_fixes())
    assert "Accept this option" in html and "Reject all options" in html
    assert 'value="defer"' not in html and "Undecided" not in html


def test_leak_and_energy_cycle_checks_have_titles_and_headlines():
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "compartments": {
                    "names": {"c": "Cytosol", "m": "Mitochondria"},
                    "metabolites": {"c": 10, "m": 5},
                },
                "checks": [
                    _check(
                        "metabolite-leaks",
                        {
                            "produced": ["h_c", "h_m"],
                            "consumed": [],
                            "by_compartment": {
                                "produced": {"c": ["h_c"], "m": ["h_m"]},
                                "consumed": {},
                            },
                        },
                    ),
                    _check(
                        "energy-generating-cycles",
                        {
                            "cycles": {"nadh_c": ["R1", "R2"]},
                            "tested": ["atp_c", "nadh_c"],
                            "not_found": {"MNXM51": "missing"},
                        },
                    ),
                ],
            }
        }
    )
    assert "Metabolite leaks" in html
    assert "2 made from nothing, 0 destroyed." in html
    assert "Energy-generating cycles" in html
    assert "1 of 2 energy metabolites can be charged without uptake." in html


def test_closed_medium_fva_from_older_reports_is_hidden():
    html = render_validation_html(
        {
            "validation": {
                "passed": True,
                "checks": [
                    {
                        **_check("energy-generating-cycles", {"reactions": ["R1"]}),
                        "family": "solver",
                    }
                ],
            }
        }
    )
    assert "check-energy-generating-cycles" not in html
