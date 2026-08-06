"""Machine-readable contracts for scientific workflow stages.

Contracts are intentionally small and JSON/YAML-shaped.  They describe the
boundary of a stage without coupling the workflow runner to a particular
model implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


class ContractError(ValueError):
    """Raised when a stage contract is missing required information."""


CONTRACT_FIELDS = (
    "id",
    "workflow",
    "purpose",
    "inputs",
    "outputs",
    "preconditions",
    "postconditions",
    "mutation",
    "side_effects",
    "failure_policy",
    "configuration",
    "provenance",
    "validation",
)


@dataclass(frozen=True)
class StageContract:
    """Validated contract for one public stage."""

    id: str
    workflow: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]
    mutation: str
    side_effects: tuple[str, ...]
    failure_policy: str
    configuration: tuple[str, ...]
    provenance: tuple[str, ...]
    validation: tuple[str, ...]
    classification: str = "analysis"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StageContract:
        missing = [key for key in CONTRACT_FIELDS if key not in value]
        if missing:
            raise ContractError(
                f"contract is missing required field(s): {', '.join(missing)}"
            )

        def text(key: str) -> str:
            result = value[key]
            if not isinstance(result, str) or not result.strip():
                raise ContractError(f"contract field '{key}' must be non-empty text")
            return result

        def texts(key: str) -> tuple[str, ...]:
            result = value[key]
            if not isinstance(result, (list, tuple)) or not all(
                isinstance(item, str) and item.strip() for item in result
            ):
                raise ContractError(f"contract field '{key}' must be a list of text")
            return tuple(result)

        return cls(
            id=text("id"),
            workflow=text("workflow"),
            purpose=text("purpose"),
            inputs=texts("inputs"),
            outputs=texts("outputs"),
            preconditions=texts("preconditions"),
            postconditions=texts("postconditions"),
            mutation=text("mutation"),
            side_effects=texts("side_effects"),
            failure_policy=text("failure_policy"),
            configuration=texts("configuration"),
            provenance=texts("provenance"),
            validation=texts("validation"),
            classification=(
                text("classification") if "classification" in value else "analysis"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workflow": self.workflow,
            "purpose": self.purpose,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "preconditions": list(self.preconditions),
            "postconditions": list(self.postconditions),
            "mutation": self.mutation,
            "side_effects": list(self.side_effects),
            "failure_policy": self.failure_policy,
            "configuration": list(self.configuration),
            "provenance": list(self.provenance),
            "validation": list(self.validation),
            "classification": self.classification,
        }


class ContractRegistry:
    """Deterministic registry of stage contracts."""

    def __init__(self, contracts: Mapping[str, StageContract] | None = None):
        self._contracts: dict[str, StageContract] = dict(contracts or {})

    def register(self, contract: StageContract | Mapping[str, Any]) -> StageContract:
        item = (
            contract
            if isinstance(contract, StageContract)
            else StageContract.from_mapping(contract)
        )
        if item.id in self._contracts:
            raise ContractError(f"duplicate stage contract: {item.id}")
        self._contracts[item.id] = item
        return item

    def get(self, contract_id: str) -> StageContract:
        try:
            return self._contracts[contract_id]
        except KeyError as error:
            raise ContractError(
                f"no stage contract registered for '{contract_id}'"
            ) from error

    def validate(
        self, *, workflows: Mapping[str, tuple[str, ...]] | None = None
    ) -> None:
        for contract in self._contracts.values():
            if workflows is not None and contract.workflow in workflows:
                missing = set(workflows[contract.workflow]) - {
                    item.id
                    for item in self._contracts.values()
                    if item.workflow == contract.workflow
                }
                if missing:
                    raise ContractError(
                        f"workflow '{contract.workflow}' lacks contracts: "
                        f"{', '.join(sorted(missing))}"
                    )

    def as_mapping(self) -> Mapping[str, StageContract]:
        return MappingProxyType(dict(self._contracts))


def contract_for_stage(
    stage_id: str,
    workflow: str,
    *,
    purpose: str = "Execute a workflow stage.",
    classification: str = "analysis",
) -> StageContract:
    """Create a conservative default contract for a registered infrastructure stage."""
    return StageContract.from_mapping(
        {
            "id": stage_id,
            "workflow": workflow,
            "purpose": purpose,
            "classification": classification,
            "inputs": ["workflow configuration and completed dependencies"],
            "outputs": ["machine-readable stage artifacts"],
            "preconditions": ["configuration and dependency checks pass"],
            "postconditions": ["declared artifacts are complete and checksummed"],
            "mutation": "does not mutate caller-owned inputs",
            "side_effects": ["writes only inside the run directory"],
            "failure_policy": "fail the stage and preserve the previous checkpoint",
            "configuration": ["workflow-specific configuration section"],
            "provenance": [
                "configuration, dependencies, implementation version, output checksums"
            ],
            "validation": ["artifact existence and checksum validation"],
        }
    )
