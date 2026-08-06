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
    scientific_stages: tuple[Any, ...] = ()

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)

    @property
    def scientific_stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.scientific_stages)

    def stages_for(self, *, scientific: bool = False) -> tuple[Any, ...]:
        """Select the detailed DAG only for a configured scientific run."""
        return (
            self.scientific_stages
            if scientific and self.scientific_stages
            else self.stages
        )

    def validate(self) -> None:
        for stages, label in (
            (self.stages, "fixture"),
            (self.scientific_stages, "scientific"),
        ):
            if not stages:
                continue
            ids = [stage.id for stage in stages]
            if not ids or len(ids) != len(set(ids)):
                raise WorkflowRegistryError(
                    f"workflow '{self.id}' {label} stages must have unique "
                    "non-empty IDs"
                )
            positions = {stage_id: index for index, stage_id in enumerate(ids)}
            for stage in stages:
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
        all_stages = definition.stages + definition.scientific_stages
        for stage in all_stages:
            if stage.id in self.contracts.as_mapping():
                continue
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
            workflows={
                item.id: item.stage_ids + item.scientific_stage_ids
                for item in self._workflows.values()
            }
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
