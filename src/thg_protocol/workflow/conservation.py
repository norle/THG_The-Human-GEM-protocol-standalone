"""Conservation workflow: detect, localize, propose, apply and re-check.

Run once to get ``proposals.jsonl``; write decisions on those proposals; run
again with the same configuration to apply the approved fixes to a copy of the
model and re-check it. Decisions exported from the validation report may cover
other checks' fixes too and are applied with ``thg-run apply-decisions``.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thg_protocol.io.models import load_model as _load_cobra_model
from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.runtime.stage import StageContext, StageResult, dump_json
from thg_protocol.runtime.stage import dependency_path as _dependency_path

from .registry import WorkflowDefinition


def _section(context: StageContext) -> Mapping[str, Any]:
    section = context.config.sections.get("conservation", {})
    return section if isinstance(section, Mapping) else {}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class ConservationStage:
    """One stage of the unconserved-metabolite review flow."""

    implementation_version = 4

    def __init__(self, stage_id: str, dependencies: tuple[str, ...] = ()) -> None:
        self.id, self.dependencies = stage_id, dependencies

    def enabled(self, config: Any) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        section = _section(context)
        result: dict[str, object] = {
            "stage": self.id,
            "version": self.implementation_version,
            "configuration": dict(section),
        }
        if self.id == "conservation-input":
            for key in ("input_model", "comparison_model"):
                value = section.get(key)
                if isinstance(value, str) and Path(value).is_file():
                    result[f"{key}_sha256"] = sha256_file(value)
        if self.id == "conservation-apply":
            from .proposals import decisions_fingerprint

            decisions = section.get("decisions_file")
            if isinstance(decisions, str):
                result["decisions_sha256"] = decisions_fingerprint(decisions)
        return result

    def _models(self, context: StageContext) -> tuple[Any, Any | None]:
        model = _load_cobra_model(
            _dependency_path(context, "conservation-input", "model")
        )
        comparison = None
        if _section(context).get("comparison_model"):
            comparison = _load_cobra_model(
                _dependency_path(context, "conservation-input", "comparison")
            )
        return model, comparison

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.analysis import conservation

        section = _section(context)
        configured = [str(item) for item in section.get("exclusions", [])]
        if self.id == "conservation-input":
            outputs = []
            for key, role in (
                ("input_model", "model"),
                ("comparison_model", "comparison"),
            ):
                value = section.get(key)
                if not value:
                    continue
                source = Path(str(value))
                destination = work_dir / f"{role}{source.suffix.lower()}"
                shutil.copy2(source, destination)
                _load_cobra_model(destination)
                outputs.append((role, destination))
            return StageResult(tuple(outputs), {"comparison": len(outputs) > 1})

        if self.id == "conservation-detect":
            model, comparison = self._models(context)
            report: dict[str, object] = {
                "model": conservation.find_unconserved_metabolites(
                    model, input_model=comparison, configured=configured
                ),
                "comparison": (
                    conservation.find_unconserved_metabolites(
                        comparison, configured=configured
                    )
                    if comparison is not None
                    else None
                ),
            }
            output = dump_json(work_dir / "detection.json", report)
            return StageResult(
                (("detection", output),),
                {
                    "consistent": report["model"]["consistent"],
                    "unconserved": len(report["model"]["unconserved"]),
                },
            )

        if self.id == "conservation-localize":
            model, comparison = self._models(context)
            detection = _read(
                _dependency_path(context, "conservation-detect", "detection")
            )
            localization = conservation.localize(
                model,
                detection["model"],
                input_model=comparison,
                input_detection=detection["comparison"],
            )
            output = dump_json(work_dir / "localization.json", localization)
            return StageResult(
                (("localization", output),),
                {
                    "blamed": len(localization["blamed"]),
                    "new": len(localization["new"]),
                    "inherited": len(localization["inherited"]),
                },
            )

        if self.id == "conservation-propose":
            from .proposals import write_proposals

            model, comparison = self._models(context)
            detection = _read(
                _dependency_path(context, "conservation-detect", "detection")
            )
            localization = _read(
                _dependency_path(context, "conservation-localize", "localization")
            )
            proposals = conservation.propose_fixes(
                model,
                localization,
                exclusions=detection["model"]["excluded"],
                input_model=comparison,
            )
            path = write_proposals(work_dir / "proposals.jsonl", proposals)
            return StageResult((("proposals", path),), {"proposals": len(proposals)})

        if self.id == "conservation-apply":
            from thg_protocol.io.models import save_model

            from .proposals import ChangeLedger, read_decisions, read_proposals

            model, comparison = self._models(context)
            proposals = read_proposals(
                _dependency_path(context, "conservation-propose", "proposals")
            )
            decisions_file = section.get("decisions_file")
            decisions = read_decisions(str(decisions_file)) if decisions_file else ()
            fixed, applied, ledger = conservation.apply_conservation_fixes(
                model, proposals, decisions, input_model=comparison
            )
            source = _dependency_path(context, "conservation-input", "model")
            output = save_model(fixed, work_dir / f"model-fixed{source.suffix}")
            ledger_path = ChangeLedger(work_dir / "change-ledger.jsonl").append(ledger)
            applied_path = dump_json(
                work_dir / "applied.json",
                [item.proposal_id for item in applied],
            )
            return StageResult(
                (
                    ("model", output),
                    ("ledger", ledger_path),
                    ("applied", applied_path),
                ),
                {"applied": len(applied), "decisions": len(decisions)},
            )

        if self.id == "conservation-recheck":
            from .proposals import read_proposals

            detection = _read(
                _dependency_path(context, "conservation-detect", "detection")
            )
            fixed = _load_cobra_model(
                _dependency_path(context, "conservation-apply", "model")
            )
            _, comparison = self._models(context)
            after = conservation.find_unconserved_metabolites(
                fixed, input_model=comparison, configured=configured
            )
            applied_ids = set(
                _read(_dependency_path(context, "conservation-apply", "applied"))
            )
            applied = [
                item
                for item in read_proposals(
                    _dependency_path(context, "conservation-propose", "proposals")
                )
                if item.proposal_id in applied_ids
            ]
            still_blamed = (
                {}
                if after["consistent"]
                else conservation.blame_reactions(
                    fixed,
                    exclusions=after["excluded"],
                    prefer=conservation.chemically_suspect(fixed, after["excluded"]),
                )["reactions"]
            )
            report = {
                "after": after,
                "still_blamed": still_blamed,
                "comparison": conservation.compare_detections(
                    detection["model"], after, applied, still_blamed
                ),
            }
            output = dump_json(work_dir / "recheck.json", report)
            summary = report["comparison"]
            return StageResult(
                (("recheck", output),),
                {
                    "before": len(summary["before"]),
                    "after": len(summary["after"]),
                    "ineffective_fixes": len(summary["ineffective_fixes"]),
                },
            )
        raise ValueError(f"unknown conservation stage: {self.id}")

    def validate(self, result: StageResult) -> None:
        if not result.outputs or any(not path.is_file() for _, path in result.outputs):
            raise ValueError(f"stage '{self.id}' produced incomplete artifacts")


def conservation_stages() -> tuple[ConservationStage, ...]:
    return (
        ConservationStage("conservation-input"),
        ConservationStage("conservation-detect", ("conservation-input",)),
        ConservationStage("conservation-localize", ("conservation-detect",)),
        ConservationStage("conservation-propose", ("conservation-localize",)),
        ConservationStage("conservation-apply", ("conservation-propose",)),
        ConservationStage("conservation-recheck", ("conservation-apply",)),
    )


CONSERVATION_WORKFLOW = WorkflowDefinition(
    "conservation",
    conservation_stages(),
    frozenset({"conservation"}),
    "Unconserved metabolites: detect, localize, propose, review and apply fixes",
)

__all__ = ["CONSERVATION_WORKFLOW", "ConservationStage", "conservation_stages"]
