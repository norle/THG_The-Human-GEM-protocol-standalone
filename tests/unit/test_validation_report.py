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
