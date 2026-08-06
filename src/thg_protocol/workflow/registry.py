"""Workflow registry and dependency validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .contracts import ContractRegistry, StageContract, contract_for_stage


class WorkflowRegistryError(ValueError):
    """Raised for unknown workflows, duplicate IDs, or invalid DAGs."""


@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    stages: tuple[Any, ...]
    allowed_sections: frozenset[str] = frozenset()
    description: str = ""

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)

    def validate(self) -> None:
        ids = list(self.stage_ids)
        if not ids or len(ids) != len(set(ids)):
            raise WorkflowRegistryError(
                f"workflow '{self.id}' must have unique non-empty stage IDs"
            )
        positions = {stage_id: index for index, stage_id in enumerate(ids)}
        for stage in self.stages:
            for dependency in tuple(getattr(stage, "dependencies", ())):
                if dependency not in positions:
                    raise WorkflowRegistryError(
                        f"workflow '{self.id}' stage '{stage.id}' depends on "
                        f"unknown stage '{dependency}'"
                    )
                if positions[dependency] >= positions[stage.id]:
                    raise WorkflowRegistryError(
                        f"workflow '{self.id}' dependency order is invalid: "
                        f"{dependency} -> {stage.id}"
                    )


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}
        self.contracts = ContractRegistry()

    def register(
        self,
        definition: WorkflowDefinition,
        *,
        contracts: Iterable[StageContract] = (),
    ) -> WorkflowDefinition:
        definition.validate()
        if definition.id in self._workflows:
            raise WorkflowRegistryError(f"duplicate workflow ID: {definition.id}")
        self._workflows[definition.id] = definition
        contract_items = tuple(contracts)
        for stage in definition.stages:
            contract = next(
                (item for item in contract_items if item.id == stage.id), None
            )
            self.contracts.register(
                contract
                or contract_for_stage(
                    stage.id,
                    definition.id,
                    classification=str(getattr(stage, "kind", "analysis")),
                )
            )
        return definition

    def get(self, workflow_id: str) -> WorkflowDefinition:
        try:
            return self._workflows[workflow_id]
        except KeyError as error:
            raise WorkflowRegistryError(f"unknown workflow: {workflow_id}") from error

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._workflows))

    def validate_all(self) -> None:
        for definition in self._workflows.values():
            definition.validate()
        self.contracts.validate(
            workflows={item.id: item.stage_ids for item in self._workflows.values()}
        )


REGISTRY = WorkflowRegistry()


def register_workflow(
    workflow_id: str,
    stages: Iterable[Any],
    *,
    allowed_sections: Iterable[str] = (),
    description: str = "",
    contracts: Iterable[StageContract] = (),
) -> WorkflowDefinition:
    return REGISTRY.register(
        WorkflowDefinition(
            workflow_id,
            tuple(stages),
            frozenset(allowed_sections),
            description,
        ),
        contracts=contracts,
    )


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    return REGISTRY.get(workflow_id)


def list_workflows() -> tuple[str, ...]:
    return REGISTRY.ids()


def validate_workflow_dependencies(workflow_id: str) -> None:
    get_workflow(workflow_id).validate()


# Built-in fixture workflows are imported lazily after the registry exists.
from .foundation_stages import (  # noqa: E402
    register_builtin_workflows as _register_builtin_workflows,
)

_register_builtin_workflows(REGISTRY)
