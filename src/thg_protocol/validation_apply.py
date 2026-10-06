"""Apply decisions made in a validation report, then validate again.

The validation report embeds fix proposals; the curator's decisions come back
as the ``decisions.jsonl`` the report page exports. Applying them refuses a
model other than the one the report describes, writes nothing when any
decision is invalid, and leaves a ledger and a new report next to the fixed
model.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.workflow.proposals import (
    ChangeLedger,
    Proposal,
    ProposalError,
    read_decisions,
)


def _validation(report: Mapping[str, Any]) -> Mapping[str, Any]:
    value = report.get("validation", report)
    return value if isinstance(value, Mapping) else {}


def report_payload(
    model: Any,
    model_path: Path,
    validation: Mapping[str, object],
    *,
    previous: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Wrap a ``validate_model`` result in the report schema the page reads."""
    previous = previous or {}
    payload: dict[str, object] = {
        "schema": "thg.validation.report/v1",
        "schema_version": 1,
        "model_id": model.id,
        "model_checksum": sha256_file(model_path),
        "validation_profile": validation["profile"],
        "validation_profile_version": 1,
        "software": {"python": platform.python_version()},
        "after": {
            "reactions": len(model.reactions),
            "metabolites": len(model.metabolites),
            "genes": len(model.genes),
            "compartments": len(model.compartments),
        },
        "validation": dict(validation),
        "solver": validation.get("solver", {}),
        "tasks": {"status": "not-requested", "tasks": [], "passed": None},
        "memote": {"status": "not-requested", "artifacts": {}},
        "warnings": sorted(
            str(item["id"])
            for item in validation.get("checks", [])
            if item.get("passed") is not True and not item.get("release_blocking")
        ),
    }
    for key in ("reference_model", "conservation_exclusions"):
        if previous.get(key) is not None:
            payload[key] = previous[key]
    return payload


def apply_decisions(
    report_path: str | Path,
    decisions_path: str | Path,
    model_path: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    """Apply a report's approved fixes to ``model_path`` and re-validate.

    Writes the fixed model to ``output_path``, the ledger to
    ``<output stem>.ledger.jsonl`` and the new report to
    ``<output stem>.validation-report.json``/``.html``. Returns a summary with
    the applied proposal IDs and the checks whose status changed. Raises
    ``ProposalError`` before writing anything when the model is not the one
    the report describes or a decision is invalid.
    """
    from thg_protocol.analysis.conservation import apply_conservation_fixes
    from thg_protocol.io.models import save_model
    from thg_protocol.validation import load_model, validate_model
    from thg_protocol.validation_report import render_validation_html

    report_path, decisions_path = Path(report_path), Path(decisions_path)
    model_path, output_path = Path(model_path), Path(output_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProposalError(
            f"cannot read validation report {report_path}: {error}"
        ) from error
    if not isinstance(report, Mapping):
        raise ProposalError(f"not a validation report: {report_path}")
    expected = report.get("model_checksum") or report.get("result_model_checksum")
    if not expected:
        raise ProposalError(
            f"{report_path} records no model checksum, so the decisions cannot "
            "be matched to a model; use the report a validation run wrote"
        )
    actual = sha256_file(model_path)
    if actual != expected:
        raise ProposalError(
            f"{model_path} (sha256 {actual}) is not the model the report "
            f"describes (sha256 {expected})"
        )
    if not decisions_path.is_file():
        raise ProposalError(f"decisions file does not exist: {decisions_path}")
    if output_path.resolve() == model_path.resolve():
        raise ProposalError("the output path must differ from the input model")

    validation = _validation(report)
    proposals = [
        Proposal.from_mapping({k: v for k, v in item.items() if k != "checks"})
        for item in validation.get("proposals", [])
        if isinstance(item, Mapping)
    ]
    decisions = read_decisions(decisions_path)
    reference = None
    if report.get("reference_model"):
        reference_path = Path(str(report["reference_model"]))
        if not reference_path.is_file():
            raise ProposalError(
                f"the report's reference model is missing: {reference_path}"
            )
        reference = load_model(reference_path)
    exclusions = [str(item) for item in report.get("conservation_exclusions", [])]

    model = load_model(model_path)
    fixed, applied, ledger = apply_conservation_fixes(
        model, proposals, decisions, input_model=reference
    )

    save_model(fixed, output_path)
    stem = output_path.with_suffix("")
    # The ledger describes this output only; a rerun must not keep old entries.
    ledger_path = stem.with_name(f"{stem.name}.ledger.jsonl")
    ledger_path.unlink(missing_ok=True)
    ChangeLedger(ledger_path).append(ledger)
    profile = str(report.get("validation_profile") or validation.get("profile"))
    solver = validation.get("solver")
    requested = solver.get("requested") if isinstance(solver, Mapping) else None
    revalidated = validate_model(
        fixed,
        profile,
        run_solver=requested if isinstance(requested, bool) else None,
        run_loop_detection=validation.get("run_loop_detection", True),
        reference_model=reference,
        conservation_exclusions=exclusions,
        propose_fixes=True,
    )
    payload = report_payload(fixed, output_path, revalidated, previous=report)
    payload["source_model_checksum"] = expected
    payload["applied_decisions"] = {
        "decisions": str(decisions_path),
        "applied": [item.proposal_id for item in applied],
        "ledger": str(ledger_path),
    }
    json_path = stem.with_name(f"{stem.name}.validation-report.json")
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    html_path = json_path.with_suffix(".html")
    html_path.write_text(render_validation_html(payload), encoding="utf-8")

    before = {
        str(item.get("id")): item.get("status") for item in validation.get("checks", [])
    }
    changed = {
        str(item["id"]): {
            "before": before.get(str(item["id"])),
            "after": item["status"],
        }
        for item in revalidated["checks"]
        if before.get(str(item["id"])) != item["status"]
    }
    return {
        "model": str(output_path),
        "ledger": str(ledger_path),
        "report": str(json_path),
        "html": str(html_path),
        "applied": [item.proposal_id for item in applied],
        "decisions": len(decisions),
        "passed": revalidated["passed"],
        "changed": changed,
    }


__all__ = ["apply_decisions", "report_payload"]
