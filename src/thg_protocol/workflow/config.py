"""Strict, self-contained configuration for resumable THG runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a workflow configuration is invalid."""


MODEL_SUFFIXES = {".json", ".xml", ".sbml"}

WORKFLOW_SECTION_KEYS = {
    "human_database": {
        "records",
        "mode",
        "model_id",
        "source_release",
        "cache_dir",
        "retries",
        "rate_limit",
    },
    "final_thg": {
        "beta2_model",
        "database_model",
        "beta2_upstream",
        "database_upstream",
        "source_precedence",
        "remove_isolated_metabolites",
        "direction",
        "proton_water",
        "formula_charge",
        "bounds",
        "gpr",
        "task_suite",
        "validation_profile",
        "max_repair_iterations",
    },
    "beta1": {
        "input_model",
        "mode",
        "balance_strategy",
        "corrections",
        "formula_corrections",
        "charge_corrections",
        "formula_policy",
        "remove_isolated",
        "remove_isolated_metabolites",
        "sanctioned_model",
        "metabolite_evidence",
        "metabolite_identities",
        "reaction_evidence",
        "reaction_targets",
        "reaction_identities",
        "proton_water_policy",
        "normalization_species",
        "gene_mapping",
        "subunit_stoichiometry",
        "decisions_file",
        "run_solver_checks",
        "run_blocked_reactions",
        "run_flux_consistency",
        "solver",
        "source_releases",
        "parser_version",
        "normalization_version",
        "license",
        "upstream",
    },
    "beta2": {
        "upstream",
        "input_model",
        "decisions_file",
        "mode",
        "gene_locations",
        "compartments",
        "catalysis_evidence",
        "external_beta1_equivalent",
        "compartment_ontology_version",
        "fallback_location",
        "uncertainty_policy",
        "subunit_stoichiometry",
        "run_solver_checks",
        "solver",
    },
    "validation": {
        "input_model",
        "upstream",
        "run_memote",
        "profile",
        "run_solver",
        "memote_threshold",
        "memote_command",
    },
    "compare": {"left", "right", "upstream"},
}


@dataclass(frozen=True)
class RunSettings:
    name: str
    output_dir: Path


@dataclass(frozen=True)
class WorkflowConfig:
    """Version 2 configuration shared by registered workflow DAGs.

    ``sections`` contains only the section(s) allowed by the selected
    workflow.  Values remain JSON-shaped so configuration snapshots are
    portable and auditable.
    """

    format_version: int
    workflow: str
    run: RunSettings
    sections: Mapping[str, object]
    source_path: Path | None = None


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"'{name}' must be an object")
    return value


def _keys(value: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"unknown key(s) in '{name}': {', '.join(unknown)}")


def _required_string(value: dict[str, Any], key: str, name: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ConfigError(f"'{name}.{key}' must be a non-empty string")
    return result


def _input_path(
    value: str, base: Path, label: str, suffixes: set[str] | None = None
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if suffixes is not None and path.suffix.lower() not in suffixes:
        allowed = ", ".join(sorted(suffixes))
        raise ConfigError(f"'{label}' must use one of: {allowed}")
    if not path.is_file():
        raise ConfigError(f"'{label}' must point to an existing regular file: {path}")
    return path


def _directory_path(value: str, base: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    """Load a format-2 config and validate sections against its workflow DAG."""
    source = Path(path).resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"could not read configuration: {source}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"configuration is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ConfigError("configuration must be a JSON object")
    return _parse_workflow(
        payload, source.parent, output_base=source.parent, source=source
    )


def _parse_workflow(
    payload: dict[str, Any],
    input_base: Path,
    *,
    output_base: Path,
    source: Path | None = None,
) -> WorkflowConfig:
    from .registry import WorkflowRegistryError, get_workflow

    allowed_base = {"format_version", "workflow", "run"}
    if payload.get("format_version") != 2:
        raise ConfigError("'format_version' must be 2 for a registered workflow")
    workflow = _required_string(payload, "workflow", "configuration")
    try:
        definition = get_workflow(workflow)
    except WorkflowRegistryError as error:
        raise ConfigError(str(error)) from error
    unknown = sorted(set(payload) - allowed_base - set(definition.allowed_sections))
    if unknown:
        raise ConfigError(
            f"configuration key(s) do not apply to workflow '{workflow}': "
            f"{', '.join(unknown)}"
        )
    run = _object(payload.get("run"), "run")
    _keys(run, {"name", "output_dir"}, "run")
    name = _required_string(run, "name", "run")
    output_value = _required_string(run, "output_dir", "run")
    sections: dict[str, object] = {}
    for section in sorted(definition.allowed_sections):
        if section in payload:
            value = payload[section]
            if not isinstance(value, dict):
                raise ConfigError(f"'{section}' must be an object")
            allowed_keys = WORKFLOW_SECTION_KEYS.get(section)
            if allowed_keys is not None:
                _keys(value, allowed_keys, section)
            if section == "beta1" and "input_model" in value:
                value = dict(value)
                value["input_model"] = str(
                    _input_path(
                        _required_string(value, "input_model", "beta1"),
                        input_base,
                        "beta1.input_model",
                        MODEL_SUFFIXES,
                    )
                )
            if section in {"beta2", "validation"} and "input_model" in value:
                value = dict(value)
                value["input_model"] = str(
                    _input_path(
                        _required_string(value, "input_model", section),
                        input_base,
                        f"{section}.input_model",
                        MODEL_SUFFIXES,
                    )
                )
            sections[section] = _resolve_workflow_paths(value, input_base)
    return WorkflowConfig(
        format_version=2,
        workflow=workflow,
        run=RunSettings(
            name=name, output_dir=_directory_path(output_value, output_base)
        ),
        sections=sections,
        source_path=source,
    )


def _resolve_workflow_paths(value: object, base: Path, *, key: str = "") -> object:
    """Resolve explicitly named external paths while preserving JSON shape."""
    if isinstance(value, dict):
        return {
            name: _resolve_workflow_paths(item, base, key=name)
            for name, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_workflow_paths(item, base, key=key) for item in value]
    if isinstance(value, str) and (
        key.endswith(("_file", "_path", "_dir"))
        or key
        in {
            "run_dir",
            "cache_dir",
            "input_model",
            "records",
            "beta2_model",
            "database_model",
            "task_suite",
        }
    ):
        path = Path(value)
        return str(path if path.is_absolute() else (base / path).resolve())
    return value


def workflow_config_to_dict(config: WorkflowConfig) -> dict[str, object]:
    """Return a normalized, JSON-safe format-2 snapshot."""
    return {
        "format_version": 2,
        "workflow": config.workflow,
        "run": {"name": config.run.name, "output_dir": str(config.run.output_dir)},
        **{key: value for key, value in sorted(config.sections.items())},
    }


def write_workflow_snapshot(config: WorkflowConfig, run_dir: Path) -> Path:
    path = run_dir / "config.snapshot.json"
    path.write_text(
        json.dumps(workflow_config_to_dict(config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_snapshot(run_dir: str | Path) -> WorkflowConfig:
    run_path = Path(run_dir).resolve()
    path = run_path / "config.snapshot.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(
            f"missing or unreadable configuration snapshot: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"configuration snapshot is not valid JSON: {error.msg}"
        ) from error
    if not isinstance(payload, dict):
        raise ConfigError("configuration snapshot must be a JSON object")
    config = _parse_workflow(payload, Path("/"), output_base=Path("/"), source=path)
    if config.run.output_dir != run_path:
        raise ConfigError(
            "configuration snapshot output_dir does not match run directory"
        )
    return config


load_any_snapshot = load_snapshot
