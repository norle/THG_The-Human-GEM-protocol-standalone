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
    assert "What it checks." in html
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
