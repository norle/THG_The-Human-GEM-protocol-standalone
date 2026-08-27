"""Proposal, decision, and scientific change-ledger primitives."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from thg_protocol.runtime.hashing import sha256_file, sha256_json


class ProposalError(ValueError):
    """Raised for invalid proposals, decisions, or application state."""


APPLICATION_MODES = {"apply-all", "report-only", "user-approved-only"}
DECISION_ACTIONS = {"approve", "reject", "replace", "defer"}


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    operation: str
    object_type: str
    object_id: str
    before: object
    after: object
    evidence: tuple[str, ...]
    confidence: str
    policy: str
    stage: str
    status: str = "proposed"
    reason: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ProposalError("proposal_id must be non-empty")
        if self.status not in {
            "proposed",
            "applied",
            "rejected",
            "deferred",
            "unresolved",
        }:
            raise ProposalError(f"invalid proposal status: {self.status}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Proposal:
        required = (
            "proposal_id",
            "operation",
            "object_type",
            "object_id",
            "before",
            "after",
            "evidence",
            "confidence",
            "policy",
            "stage",
            "status",
            "reason",
        )
        missing = [key for key in required if key not in value]
        if missing:
            raise ProposalError(f"proposal is missing: {', '.join(missing)}")
        text_fields = (
            "proposal_id",
            "operation",
            "object_type",
            "object_id",
            "confidence",
            "policy",
            "stage",
            "reason",
        )
        for key in text_fields:
            if not isinstance(value[key], str):
                raise ProposalError(f"proposal field '{key}' must be text")
        evidence = value["evidence"]
        if not isinstance(evidence, list) or not all(
            isinstance(x, str) for x in evidence
        ):
            raise ProposalError("proposal evidence must be a list of IDs")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ProposalError("proposal metadata must be an object")
        return cls(
            proposal_id=value["proposal_id"],
            operation=value["operation"],
            object_type=value["object_type"],
            object_id=value["object_id"],
            before=value["before"],
            after=value["after"],
            evidence=tuple(evidence),
            confidence=value["confidence"],
            policy=value["policy"],
            stage=value["stage"],
            status=value["status"],
            reason=value["reason"],
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "operation": self.operation,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "before": self.before,
            "after": self.after,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "policy": self.policy,
            "stage": self.stage,
            "status": self.status,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Decision:
    proposal_id: str
    action: str
    replacement: object | None = None
    reason: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Decision:
        proposal_id = value.get("proposal_id")
        action = value.get("action")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ProposalError("decision proposal_id must be non-empty text")
        if action not in DECISION_ACTIONS:
            raise ProposalError(
                f"decision action must be one of: {', '.join(sorted(DECISION_ACTIONS))}"
            )
        if action == "replace" and "replacement" not in value:
            raise ProposalError("replace decisions require a replacement")
        reason = value.get("reason", "")
        if not isinstance(reason, str):
            raise ProposalError("decision reason must be text")
        return cls(proposal_id, action, value.get("replacement"), reason)

    def to_dict(self) -> dict[str, object]:
        result = {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "reason": self.reason,
        }
        if self.replacement is not None:
            result["replacement"] = self.replacement
        return result


def proposal_id(
    *, operation: str, object_type: str, object_id: str, before: object, after: object
) -> str:
    return "prop-" + sha256_json(
        {
            "operation": operation,
            "object_type": object_type,
            "object_id": object_id,
            "before": before,
            "after": after,
        }
    )


def write_jsonl(path: str | Path, records: Iterable[Mapping[str, object]]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), sort_keys=True) + "\n")
    return destination


def read_proposals(path: str | Path) -> tuple[Proposal, ...]:
    source = Path(path)
    if not source.is_file():
        raise ProposalError(f"proposal file does not exist: {source}")
    result: list[Proposal] = []
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            result.append(Proposal.from_mapping(json.loads(line)))
        except (json.JSONDecodeError, ProposalError) as error:
            raise ProposalError(
                f"invalid proposal at line {line_number}: {error}"
            ) from error
    ids = [item.proposal_id for item in result]
    if len(ids) != len(set(ids)):
        raise ProposalError("proposal IDs must be unique")
    return tuple(result)


def write_proposals(path: str | Path, proposals: Iterable[Proposal]) -> Path:
    """Persist the complete proposal set before any application callback runs."""
    items = tuple(proposals)
    return write_jsonl(path, (item.to_dict() for item in items))


def read_decisions(path: str | Path) -> tuple[Decision, ...]:
    source = Path(path)
    if not source.is_file():
        return ()
    result: list[Decision] = []
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            result.append(Decision.from_mapping(json.loads(line)))
        except (json.JSONDecodeError, ProposalError) as error:
            raise ProposalError(
                f"invalid decision at line {line_number}: {error}"
            ) from error
    ids = [item.proposal_id for item in result]
    if len(ids) != len(set(ids)):
        raise ProposalError("decision proposal IDs must be unique")
    return tuple(result)


def decisions_fingerprint(path: str | Path) -> str:
    source = Path(path)
    return sha256_file(source) if source.exists() else sha256_json([])


def apply_proposals(
    proposals: Iterable[Proposal],
    *,
    mode: str = "apply-all",
    decisions: Iterable[Decision] = (),
    apply: Callable[[Proposal, object], None] | None = None,
) -> tuple[tuple[Proposal, ...], tuple[dict[str, object], ...]]:
    """Apply proposals under explicit policy and return applied items plus ledger.

    Proposal generation is deliberately outside this function; therefore all
    modes consume the same proposal set.  ``apply`` is called only for actual
    mutations, and a caller can use the returned ledger to persist a checkpoint.
    """
    if mode not in APPLICATION_MODES:
        raise ProposalError(
            f"mode must be one of: {', '.join(sorted(APPLICATION_MODES))}"
        )
    items = tuple(proposals)
    by_id = {item.proposal_id: item for item in items}
    decision_map: dict[str, Decision] = {}
    for decision in decisions:
        if decision.proposal_id not in by_id:
            raise ProposalError(
                f"decision references unknown proposal: {decision.proposal_id}"
            )
        decision_map[decision.proposal_id] = decision

    applied: list[Proposal] = []
    ledger: list[dict[str, object]] = []
    for item in items:
        decision = decision_map.get(item.proposal_id)
        action = decision.action if decision else None
        replacement = (
            decision.replacement
            if decision is not None and decision.action == "replace"
            else item.after
        )
        if action == "reject":
            status, reason = "rejected", decision.reason or "explicitly rejected"
        elif action == "defer":
            status, reason = "deferred", decision.reason or "explicitly deferred"
        elif mode == "report-only":
            status, reason = "unresolved", "report-only mode"
        elif mode == "user-approved-only" and action not in {"approve", "replace"}:
            status, reason = "unresolved", "requires explicit approval"
        else:
            if apply is not None:
                apply(item, replacement)
            applied.append(item)
            status, reason = (
                "applied",
                (decision.reason if decision else "valid proposal"),
            )
        ledger.append(
            {
                "proposal_id": item.proposal_id,
                "operation": item.operation,
                "object_type": item.object_type,
                "object_id": item.object_id,
                "before": item.before,
                "after": replacement if status == "applied" else item.after,
                "evidence": list(item.evidence),
                "stage": item.stage,
                "status": status,
                "reason": reason,
                "metadata": dict(item.metadata),
            }
        )
    return tuple(applied), tuple(ledger)


def apply_proposals_file(
    path: str | Path,
    *,
    mode: str = "apply-all",
    decisions: Iterable[Decision] = (),
    apply: Callable[[Proposal, object], None] | None = None,
) -> tuple[tuple[Proposal, ...], tuple[dict[str, object], ...]]:
    """Apply a previously persisted proposal artifact."""
    return apply_proposals(
        read_proposals(path), mode=mode, decisions=decisions, apply=apply
    )


class ChangeLedger:
    """Append-only JSONL ledger that makes proposal application auditable."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def entries(self) -> tuple[Mapping[str, object], ...]:
        if not self.path.exists():
            return ()
        entries: list[Mapping[str, object]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ProposalError(
                    f"invalid ledger JSON at line {line_number}"
                ) from error
            if not isinstance(value, dict) or not isinstance(
                value.get("proposal_id"), str
            ):
                raise ProposalError(f"invalid ledger entry at line {line_number}")
            entries.append(value)
        return tuple(entries)

    def append(self, entries: Iterable[Mapping[str, object]]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = {str(entry["proposal_id"]) for entry in self.entries()}
        with self.path.open("a", encoding="utf-8") as handle:
            for entry in entries:
                proposal = entry.get("proposal_id")
                if not isinstance(proposal, str) or not proposal:
                    raise ProposalError("ledger entries require proposal_id")
                if proposal in existing:
                    continue
                handle.write(json.dumps(dict(entry), sort_keys=True) + "\n")
                existing.add(proposal)
        return self.path

    def fingerprint(self) -> str:
        return sha256_file(self.path) if self.path.exists() else sha256_json([])
