"""Strict, self-contained configuration for resumable THG runs."""

from __future__ import annotations

import json
import re
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
        "reference_upstream",
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
    },
    "beta1": {
        "n_jobs",
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
        "n_jobs",
        "upstream",
        "input_model",
        "decisions_file",
        "mode",
        "gene_locations",
        "compartments",
        "catalysis_evidence",
        "evidence_mode",
        "evidence_file",
        "gpr_policy",
        "location_policy",
        "reaction_location_evidence",
        "cco_graph",
        "go_graph",
        "compartment_go_terms",
        "location_sources",
        "reaction_sources",
        "go_ontology_file",
        "go_ontology_url",
        "go_ontology_release",
        "go_annotation_file",
        "uniprot_snapshot",
        "rhea_snapshot",
        "reactome_snapshot",
        "source_releases",
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
    "cell_specific": {
        "input_model",
        "expression_file",
        "gene_identifier_namespace",
        "sample",
        "sample_aggregation",
        "activity_strategy",
        "reduction_strategy",
        "threshold",
        "unknown_gene_policy",
        "gene_mapping",
        "mapping_version",
        "preserved_reactions",
        "exchange_settings",
        "task_suite",
        "validation_profile",
        "matrix_key",
    },
    "pathway": {
        "input_model",
        "pathway_definition",
        "id_database",
        "validation_profile",
    },
    "gapfill": {
        "input_model",
        "external_input",
        "method",
        "max_additions",
        "allowed_connections",
        "candidate_types",
        "candidate_universe",
        "universal_model",
        "objective",
        "minimum_flux",
        "penalties",
        "validation_profile",
        "task_suite",
    },
}


@dataclass(frozen=True)
class RunSettings:
    name: str
    output_dir: Path


@dataclass(frozen=True)
class WorkflowConfig:
    """Configuration shared by registered workflow DAGs.

    ``sections`` contains only the section(s) allowed by the selected
    workflow.  Values remain JSON-shaped so configuration snapshots are
    portable and auditable.
    """

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


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"'{label}' must be a positive integer")
    return value


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
    """Load a workflow config and validate sections against its workflow DAG."""
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

    allowed_base = {"workflow", "run"}
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
    if workflow == "reference" and not {"beta1", "beta2", "gapfill"} <= set(payload):
        raise ConfigError(
            "reference workflow requires beta1, beta2, and gapfill sections"
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
            if "n_jobs" in value:
                value = dict(value)
                value["n_jobs"] = _positive_integer(
                    value["n_jobs"], f"{section}.n_jobs"
                )
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
            if section == "final_thg":
                value = dict(value)
                for key in ("beta2_model", "database_model"):
                    if key in value:
                        value[key] = str(
                            _input_path(
                                _required_string(value, key, "final_thg"),
                                input_base,
                                f"final_thg.{key}",
                                MODEL_SUFFIXES,
                            )
                        )
            if section == "cell_specific":
                value = dict(value)
                for key in ("input_model", "expression_file"):
                    value[key] = str(
                        _input_path(
                            _required_string(value, key, "cell_specific"),
                            input_base,
                            f"cell_specific.{key}",
                            MODEL_SUFFIXES if key == "input_model" else None,
                        )
                    )
                _required_string(value, "gene_identifier_namespace", "cell_specific")
                strategy = value.get("activity_strategy", "gpr-threshold")
                if strategy not in {"gpr-threshold", "activity-matrix"}:
                    raise ConfigError(
                        "'cell_specific.activity_strategy' must be "
                        "gpr-threshold or activity-matrix"
                    )
                reduction = value.get("reduction_strategy", strategy)
                if reduction not in {"gpr-threshold", "activity-matrix"}:
                    raise ConfigError(
                        "'cell_specific.reduction_strategy' must be "
                        "gpr-threshold or activity-matrix"
                    )
                policy = value.get("unknown_gene_policy", "uncertain-retain")
                if policy not in {"uncertain-retain", "inactive", "reject"}:
                    raise ConfigError(
                        "'cell_specific.unknown_gene_policy' must be "
                        "uncertain-retain, inactive, or reject"
                    )
                profile = value.get("validation_profile", "structural-fast")
                from thg_protocol.validation import PROFILES

                if profile not in PROFILES:
                    raise ConfigError(
                        f"unknown cell-specific validation profile: {profile}"
                    )
                threshold = value.get("threshold", 0.0)
                if isinstance(threshold, bool) or not isinstance(
                    threshold, (int, float)
                ):
                    raise ConfigError("'cell_specific.threshold' must be numeric")
                if not isinstance(value.get("preserved_reactions", []), list):
                    raise ConfigError(
                        "'cell_specific.preserved_reactions' must be a list"
                    )
                if "task_suite" in value:
                    value["task_suite"] = str(
                        _input_path(
                            _required_string(value, "task_suite", "cell_specific"),
                            input_base,
                        )
                    )
                if "gene_mapping" in value and not isinstance(
                    value["gene_mapping"], dict
                ):
                    raise ConfigError("'cell_specific.gene_mapping' must be an object")
                aggregation = value.get("sample_aggregation", "mean")
                if aggregation not in {"mean", "median", "max"}:
                    raise ConfigError(
                        "'cell_specific.sample_aggregation' must be mean, median, "
                        "or max"
                    )
            if section == "pathway":
                value = dict(value)
                for key in ("input_model", "pathway_definition", "id_database"):
                    value[key] = str(
                        _input_path(
                            _required_string(value, key, "pathway"),
                            input_base,
                            f"pathway.{key}",
                            MODEL_SUFFIXES if key == "input_model" else None,
                        )
                    )
                profile = value.get("validation_profile", "structural-fast")
                from thg_protocol.validation import PROFILES

                if profile not in PROFILES:
                    raise ConfigError(f"unknown pathway validation profile: {profile}")
            if section == "human_database":
                value = dict(value)
                value["records"] = str(
                    _input_path(
                        _required_string(value, "records", "human_database"),
                        input_base,
                        "human_database.records",
                    )
                )
                if value.get("mode", "offline") not in {"offline", "live"}:
                    raise ConfigError("'human_database.mode' must be offline or live")
            if section == "compare":
                value = dict(value)
                for key in ("left", "right"):
                    value[key] = str(
                        _input_path(
                            _required_string(value, key, "compare"),
                            input_base,
                            f"compare.{key}",
                            MODEL_SUFFIXES,
                        )
                    )
            if section == "gapfill":
                value = dict(value)
                method = value.get("method")
                if method not in {"greedy", "deadends", "milp"}:
                    raise ConfigError(
                        "'gapfill.method' must be greedy, deadends, or milp"
                    )
                profile = value.get("validation_profile")
                if not isinstance(profile, str) or not profile.strip():
                    raise ConfigError(
                        "'gapfill.validation_profile' must be a non-empty string"
                    )
                from thg_protocol.validation import PROFILES

                if profile not in PROFILES:
                    raise ConfigError(f"unknown gapfill validation profile: {profile}")
                if "max_additions" not in value:
                    raise ConfigError("'gapfill.max_additions' is required")
                value["max_additions"] = _positive_integer(
                    value["max_additions"], "gapfill.max_additions"
                )
                standalone = workflow == "gapfill"
                if standalone:
                    if value.get("external_input") is not True:
                        raise ConfigError(
                            "standalone gapfill requires external_input: true"
                        )
                    if "input_model" not in value:
                        raise ConfigError("standalone gapfill requires input_model")
                elif "input_model" in value or "external_input" in value:
                    raise ConfigError(
                        "reference gapfill must use the in-run β2 handoff"
                    )
                if "input_model" in value:
                    value["input_model"] = str(
                        _input_path(
                            _required_string(value, "input_model", "gapfill"),
                            input_base,
                            "gapfill.input_model",
                            MODEL_SUFFIXES,
                        )
                    )
                transport = {"greedy", "deadends"}
                if method in transport:
                    for key in ("allowed_connections", "candidate_types"):
                        if key not in value:
                            raise ConfigError(
                                f"'gapfill.{key}' is required for {method}"
                            )
                    connections = value["allowed_connections"]
                    if not isinstance(connections, list) or any(
                        not isinstance(pair, list)
                        or len(pair) != 2
                        or not all(
                            isinstance(item, str) and item.strip() for item in pair
                        )
                        for pair in connections
                    ):
                        raise ConfigError(
                            "'gapfill.allowed_connections' must contain "
                            "compartment pairs"
                        )
                    types = value["candidate_types"]
                    if (
                        not isinstance(types, list)
                        or not types
                        or set(types) - {"A", "B", "C"}
                    ):
                        raise ConfigError(
                            "'gapfill.candidate_types' must contain only A, B, or C"
                        )
                    incompatible = {
                        "universal_model",
                        "objective",
                        "minimum_flux",
                        "penalties",
                    }
                    if incompatible & set(value):
                        raise ConfigError(
                            f"gapfill {method} does not accept: "
                            + ", ".join(sorted(incompatible & set(value)))
                        )
                else:
                    for key in (
                        "universal_model",
                        "objective",
                        "minimum_flux",
                        "penalties",
                    ):
                        if key not in value:
                            raise ConfigError(f"'gapfill.{key}' is required for milp")
                    value["universal_model"] = str(
                        _input_path(
                            _required_string(value, "universal_model", "gapfill"),
                            input_base,
                            "gapfill.universal_model",
                            MODEL_SUFFIXES,
                        )
                    )
                    if (
                        not isinstance(value["objective"], str)
                        or not value["objective"].strip()
                    ):
                        raise ConfigError(
                            "'gapfill.objective' must be a non-empty string"
                        )
                    if (
                        isinstance(value["minimum_flux"], bool)
                        or not isinstance(value["minimum_flux"], (int, float))
                        or value["minimum_flux"] <= 0
                    ):
                        raise ConfigError("'gapfill.minimum_flux' must be positive")
                    if not isinstance(value["penalties"], dict):
                        raise ConfigError("'gapfill.penalties' must be an object")
                    incompatible = {"allowed_connections", "candidate_types"}
                    if incompatible & set(value):
                        raise ConfigError(
                            "gapfill milp does not accept: "
                            + ", ".join(sorted(incompatible & set(value)))
                        )
                for file_key in ("candidate_universe", "task_suite"):
                    if file_key in value:
                        value[file_key] = str(
                            _input_path(
                                _required_string(value, file_key, "gapfill"),
                                input_base,
                                f"gapfill.{file_key}",
                            )
                        )
            if section == "beta2":
                evidence_mode = value.get("evidence_mode", "provided")
                if evidence_mode not in {"provided", "snapshot", "live"}:
                    raise ConfigError(
                        "'beta2.evidence_mode' must be provided, snapshot, or live"
                    )
                if value.get("gpr_policy", "model-then-ec") != "model-then-ec":
                    raise ConfigError("unsupported 'beta2.gpr_policy'")
                if (
                    value.get("location_policy", "provided-then-evidence")
                    != "provided-then-evidence"
                ):
                    raise ConfigError("unsupported 'beta2.location_policy'")
                compartments = value.get("compartments")
                if compartments is not None and (
                    not isinstance(compartments, dict)
                    or not all(
                        isinstance(key, str)
                        and key.strip()
                        and isinstance(name, str)
                        and name.strip()
                        for key, name in compartments.items()
                    )
                ):
                    raise ConfigError(
                        "'beta2.compartments' must map non-empty IDs to names"
                    )
                go_targets = value.get("compartment_go_terms")
                if go_targets is not None:
                    if not isinstance(go_targets, dict):
                        raise ConfigError(
                            "'beta2.compartment_go_terms' must be an object"
                        )
                    if compartments is None or not set(go_targets) <= set(compartments):
                        raise ConfigError(
                            "'beta2.compartment_go_terms' keys must exist in "
                            "compartments"
                        )
                    if any(
                        not isinstance(item, str)
                        or not re.fullmatch(r"GO:\d{7}", item, re.IGNORECASE)
                        for item in go_targets.values()
                    ):
                        raise ConfigError(
                            "'beta2.compartment_go_terms' values must be valid GO IDs"
                        )
                    if len({item.upper() for item in go_targets.values()}) != len(
                        go_targets
                    ):
                        raise ConfigError(
                            "'beta2.compartment_go_terms' values must be unique"
                        )
                open_sources = value.get("location_sources", []) or value.get(
                    "reaction_sources", []
                )
                automatic_open_evidence = evidence_mode in {"snapshot", "live"} and (
                    bool(open_sources)
                    or "go_ontology_file" in value
                    or "go_ontology_url" in value
                )
                if automatic_open_evidence and (
                    not isinstance(compartments, dict)
                    or set(go_targets or {}) != set(compartments)
                ):
                    raise ConfigError(
                        "automatic open-evidence mode requires a GO target for every "
                        "configured compartment"
                    )
                source_releases = value.get("source_releases", {})
                if evidence_mode == "live" and open_sources:
                    if not isinstance(source_releases, dict):
                        raise ConfigError("'beta2.source_releases' must be an object")
                    for source_name in {str(item).lower() for item in open_sources}:
                        metadata = source_releases.get(source_name)
                        if (
                            not isinstance(metadata, dict)
                            or not str(metadata.get("release", "")).strip()
                        ):
                            raise ConfigError(
                                "live β2 evidence requires a release for "
                                f"'{source_name}'"
                            )
                if evidence_mode == "live" and go_targets:
                    go_release = source_releases.get(
                        "go", source_releases.get("go_ontology", {})
                    )
                    go_release = go_release if isinstance(go_release, dict) else {}
                    go_url = value.get("go_ontology_url", go_release.get("url", ""))
                    go_version = value.get(
                        "go_ontology_release", go_release.get("release", "")
                    )
                    if (
                        not isinstance(go_url, str)
                        or not go_url.strip()
                        or "current.geneontology.org" in go_url
                        or not isinstance(go_version, str)
                        or not go_version.strip()
                    ):
                        raise ConfigError(
                            "live GO evidence requires an immutable ontology URL "
                            "and release"
                        )
                if "evidence_file" in value:
                    value = dict(value)
                    evidence_path = Path(
                        _required_string(value, "evidence_file", "beta2")
                    )
                    if not evidence_path.is_absolute():
                        evidence_path = input_base / evidence_path
                    evidence_path = evidence_path.resolve()
                    if evidence_mode == "snapshot" and not evidence_path.is_file():
                        raise ConfigError(
                            "'beta2.evidence_file' must point to an existing snapshot: "
                            + str(evidence_path)
                        )
                    value["evidence_file"] = str(evidence_path)
                for file_key in (
                    "go_ontology_file",
                    "go_annotation_file",
                    "uniprot_snapshot",
                    "rhea_snapshot",
                    "reactome_snapshot",
                ):
                    if file_key not in value or not isinstance(value[file_key], str):
                        continue
                    candidate = Path(value[file_key])
                    if not candidate.is_absolute():
                        candidate = input_base / candidate
                    candidate = candidate.resolve()
                    if evidence_mode != "live" and not candidate.is_file():
                        raise ConfigError(
                            f"'beta2.{file_key}' must point to an existing regular "
                            "file: " + str(candidate)
                        )
                    value = dict(value)
                    value[file_key] = str(candidate)
            sections[section] = _resolve_workflow_paths(value, input_base)
    return WorkflowConfig(
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
            "uniprot_snapshot",
            "rhea_snapshot",
            "reactome_snapshot",
        }
    ):
        path = Path(value)
        return str(path if path.is_absolute() else (base / path).resolve())
    return value


def workflow_config_to_dict(config: WorkflowConfig) -> dict[str, object]:
    """Return a normalized, JSON-safe workflow configuration snapshot."""
    return {
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
