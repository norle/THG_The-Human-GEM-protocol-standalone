"""Dependency-free human-readable rendering of canonical validation JSON."""

# ruff: noqa: E501 - embedded HTML/CSS is clearer when kept intact.

from __future__ import annotations

import json
from collections.abc import Mapping
from html import escape


def _validation(report: Mapping[str, object]) -> Mapping[str, object]:
    after = report.get("after", {})
    value = report.get(
        "validation",
        after.get("validation", report) if isinstance(after, Mapping) else report,
    )
    return value if isinstance(value, Mapping) else {}


def _display(value: object) -> str:
    if isinstance(value, list):
        return f"{len(value):,} items"
    if isinstance(value, Mapping):
        return f"{len(value):,} entries"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _passed(report: Mapping[str, object]) -> bool:
    if report.get("status") in {"passed", "failed"}:
        return report["status"] == "passed"
    tasks = report.get("tasks", {})
    return _validation(report).get("passed") is True and not (
        isinstance(tasks, Mapping) and tasks.get("passed") is False
    )


def _status(check: Mapping[str, object]) -> str:
    status = str(check.get("status", "not-evaluated"))
    if status == "failed" and not check.get("release_blocking"):
        return "warning"
    return status


def render_validation_html(report: Mapping[str, object]) -> str:
    """Render one self-contained, safe HTML file without recomputing results."""
    validation = _validation(report)
    checks = validation.get("checks", [])
    checks = checks if isinstance(checks, list) else []
    passed = _passed(report)
    metrics = report.get("after", {})
    metrics = metrics if isinstance(metrics, Mapping) else {}
    deltas = report.get("metric_deltas", {})
    deltas = deltas if isinstance(deltas, Mapping) else {}

    cards = "".join(
        f'<div class="card"><span>{escape(str(key).replace("_", " "))}</span>'
        f"<strong>{escape(_display(value))}</strong></div>"
        for key, value in metrics.items()
        if key
        in {
            "reactions",
            "metabolites",
            "genes",
            "compartments",
            "blocked_reactions",
            "dead_end_metabolites",
            "network_components",
            "largest_component_fraction",
        }
    )
    rows = []
    for item in checks:
        if not isinstance(item, Mapping):
            continue
        details = json.dumps(
            item.get("details", {}), indent=2, sort_keys=True, default=str
        )
        status = _status(item)
        rows.append(
            f"<tr><td>{escape(str(item.get('family', '')))}</td>"
            f"<td>{escape(str(item.get('id', '')))}</td>"
            f'<td><span class="status {escape(status)}">{escape(status)}</span></td>'
            f"<td>{'blocking' if item.get('release_blocking') else 'diagnostic'}</td>"
            f"<td><details><summary>View evidence</summary><pre>{escape(details)}</pre></details></td></tr>"
        )
    delta_rows = (
        "".join(
            f"<tr><th>{escape(str(key).replace('_', ' '))}</th><td>{escape(_display(value))}</td></tr>"
            for key, value in deltas.items()
        )
        or '<tr><td colspan="2">No upstream comparison</td></tr>'
    )
    warnings = report.get("warnings", [])
    warning_text = (
        ", ".join(map(str, warnings)) if isinstance(warnings, list) else str(warnings)
    )
    provenance = {
        key: report.get(key)
        for key in (
            "schema",
            "schema_version",
            "model_id",
            "model_checksum",
            "source_model_checksum",
            "result_model_checksum",
            "validation_profile",
            "validation_profile_version",
            "software",
        )
        if report.get(key) is not None
    }
    gimme = "".join(
        f"<section><h2>{title}</h2><pre>{escape(json.dumps(report[key], indent=2, sort_keys=True, default=str))}</pre></section>"
        for key, title in (
            ("gimme_samples", "GIMME samples"),
            ("gimme_objectives", "GIMME objectives"),
        )
        if key in report
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>THG validation report</title><style>
:root{{--ok:#18794e;--bad:#c9372c;--warn:#a15c00;--muted:#59636e;--line:#d8dee4}}*{{box-sizing:border-box}}body{{margin:0;background:#f6f8fa;color:#1f2328;font:15px system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:32px}}h1{{margin-bottom:6px}}.lead{{color:var(--muted)}}.gate{{display:inline-block;padding:8px 12px;border-radius:8px;background:{"#dafbe1" if passed else "#ffebe9"};color:{"var(--ok)" if passed else "var(--bad)"};font-weight:700}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}}.card,section{{background:white;border:1px solid var(--line);border-radius:10px;padding:16px}}.card span{{display:block;color:var(--muted);text-transform:capitalize}}.card strong{{font-size:1.35rem}}section{{margin:16px 0;overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}.status{{font-weight:700}}.passed{{color:var(--ok)}}.failed,.error,.infrastructure-error{{color:var(--bad)}}.warning{{color:var(--warn)}}details pre{{max-height:360px;overflow:auto;white-space:pre-wrap}}code,pre{{font:13px ui-monospace,monospace}}@media(max-width:650px){{main{{padding:16px}}th:nth-child(1),td:nth-child(1),th:nth-child(4),td:nth-child(4){{display:none}}}}
</style></head><body><main><h1>THG validation report</h1>
<p class="lead">Profile: {escape(str(report.get("validation_profile", validation.get("profile", "unknown"))))}</p>
<p class="gate">{"PASSED" if passed else "FAILED"}</p>
<div class="cards">{cards}</div>
<section><h2>Checks</h2><table><thead><tr><th>Family</th><th>Check</th><th>Status</th><th>Policy</th><th>Evidence</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>
<section><h2>Changes from upstream</h2><table>{delta_rows}</table></section>
<section><h2>Tasks</h2><pre>{escape(json.dumps(report.get("tasks", {"status": "not-requested"}), indent=2, sort_keys=True, default=str))}</pre></section>
{gimme}
<section><h2>Solver</h2><pre>{escape(json.dumps(report.get("solver", validation.get("solver", {})), indent=2, sort_keys=True, default=str))}</pre></section>
<section><h2>MEMOTE</h2><pre>{escape(json.dumps(report.get("memote", {"status": "not-requested"}), indent=2, sort_keys=True, default=str))}</pre></section>
<section><h2>Warnings</h2><p>{escape(warning_text) if warning_text else "None"}</p></section>
<section><h2>Provenance</h2><pre>{escape(json.dumps(provenance, indent=2, sort_keys=True, default=str))}</pre></section>
</main></body></html>\n"""


def render_validation_summary(report: Mapping[str, object]) -> str:
    validation = _validation(report)
    checks = validation.get("checks", [])
    failures = (
        [
            str(item.get("id"))
            for item in checks
            if isinstance(item, Mapping) and item.get("passed") is not True
        ]
        if isinstance(checks, list)
        else []
    )
    lines = [
        "# THG validation",
        "",
        f"- Overall: **{'PASSED' if _passed(report) else 'FAILED'}**",
        f"- Profile: {report.get('validation_profile', validation.get('profile', 'unknown'))}",
        f"- Findings: {', '.join(failures) if failures else 'none'}",
    ]
    deltas = report.get("metric_deltas", {})
    if isinstance(deltas, Mapping) and deltas:
        lines.extend(["", "## Changes from upstream", ""])
        lines.extend(
            f"- {key.replace('_', ' ')}: {_display(value)}"
            for key, value in deltas.items()
        )
    return "\n".join(lines) + "\n"


__all__ = ["render_validation_html", "render_validation_summary"]
