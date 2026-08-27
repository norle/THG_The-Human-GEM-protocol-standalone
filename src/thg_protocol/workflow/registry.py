"""Workflow registry and dependency validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


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

    def register(
        self,
        definition: WorkflowDefinition,
    ) -> WorkflowDefinition:
        definition.validate()
        if definition.id in self._workflows:
            raise WorkflowRegistryError(f"duplicate workflow ID: {definition.id}")
        self._workflows[definition.id] = definition
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


REGISTRY = WorkflowRegistry()


def register_workflow(
    workflow_id: str,
    stages: Iterable[Any],
    *,
    allowed_sections: Iterable[str] = (),
    description: str = "",
) -> WorkflowDefinition:
    return REGISTRY.register(
        WorkflowDefinition(
            workflow_id,
            tuple(stages),
            frozenset(allowed_sections),
            description,
        ),
    )


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    return REGISTRY.get(workflow_id)


def list_workflows() -> tuple[str, ...]:
    return REGISTRY.ids()


def validate_workflow_dependencies(workflow_id: str) -> None:
    get_workflow(workflow_id).validate()


def register_builtin_workflows() -> None:
    """Register the built-in definitions from their owning workflow modules."""
    from .beta1.definition import BETA1_WORKFLOW
    from .beta2.definition import BETA2_WORKFLOW
    from .cell_specific import CELL_SPECIFIC_WORKFLOW
    from .compare import COMPARE_WORKFLOW
    from .final_thg import FINAL_THG_WORKFLOW
    from .foundation import fixture_stages
    from .gapfill import GAPFILL_WORKFLOW
    from .human_database import HUMAN_DATABASE_WORKFLOW
    from .pathway import PATHWAY_WORKFLOW
    from .reference import REFERENCE_WORKFLOW
    from .validation import validation_stages

    definitions = (
        HUMAN_DATABASE_WORKFLOW,
        FINAL_THG_WORKFLOW,
        BETA1_WORKFLOW,
        BETA2_WORKFLOW,
        GAPFILL_WORKFLOW,
        REFERENCE_WORKFLOW,
        WorkflowDefinition(
            "validate",
            fixture_stages("validate"),
            frozenset({"validation"}),
            "Validation foundation fixture",
            scientific_stages=validation_stages(),
        ),
        COMPARE_WORKFLOW,
        CELL_SPECIFIC_WORKFLOW,
        PATHWAY_WORKFLOW,
    )
    for definition in definitions:
        try:
            REGISTRY.register(definition)
        except WorkflowRegistryError as error:
            if "duplicate workflow ID" not in str(error):
                raise


register_builtin_workflows()
