"""Strict, self-contained configuration for resumable THG runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a workflow configuration is invalid."""


MODEL_SUFFIXES = {".json", ".xml", ".sbml"}


@dataclass(frozen=True)
class RunSettings:
    name: str
    output_dir: Path


@dataclass(frozen=True)
class ReferenceSettings:
    mode: str
    input_model: Path
    cache_dir: Path | None = None


@dataclass(frozen=True)
class DatabaseSettings:
    records: Path


@dataclass(frozen=True)
class MergeSettings:
    remove_isolated_metabolites: bool = False


@dataclass(frozen=True)
class ValidationSettings:
    run_memote: bool = False


@dataclass(frozen=True)
class RunConfig:
    format_version: int
    run: RunSettings
    reference: ReferenceSettings
    database: DatabaseSettings
    merge: MergeSettings
    validation: ValidationSettings


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


def load_start_config(path: str | Path) -> RunConfig:
    """Load external JSON and resolve inputs relative to its directory."""
    source = Path(path).resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"could not read configuration: {source}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"configuration is not valid JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ConfigError("configuration must be a JSON object")
    return _parse(payload, source.parent, output_base=Path.cwd().resolve())


def _parse(
    payload: dict[str, Any], input_base: Path, *, output_base: Path
) -> RunConfig:
    _keys(
        payload,
        {"format_version", "run", "reference", "database", "merge", "validation"},
        "configuration",
    )
    if payload.get("format_version") != 1:
        raise ConfigError("'format_version' must be 1")

    run = _object(payload.get("run"), "run")
    _keys(run, {"name", "output_dir"}, "run")
    name = _required_string(run, "name", "run")
    output_value = _required_string(run, "output_dir", "run")

    reference = _object(payload.get("reference"), "reference")
    _keys(reference, {"mode", "input_model", "cache_dir"}, "reference")
    mode = _required_string(reference, "mode", "reference")
    if mode not in {"prebuilt", "build_model"}:
        raise ConfigError("'reference.mode' must be 'prebuilt' or 'build_model'")
    input_model = _input_path(
        _required_string(reference, "input_model", "reference"),
        input_base,
        "reference.input_model",
        MODEL_SUFFIXES,
    )
    cache_value = reference.get("cache_dir")
    if cache_value is not None and not isinstance(cache_value, str):
        raise ConfigError("'reference.cache_dir' must be a string")
    if cache_value and mode != "build_model":
        raise ConfigError("'reference.cache_dir' is only valid for build_model mode")
    cache_dir = _directory_path(cache_value, input_base) if cache_value else None

    database = _object(payload.get("database"), "database")
    _keys(database, {"records"}, "database")
    records = _input_path(
        _required_string(database, "records", "database"),
        input_base,
        "database.records",
        {".json"},
    )

    merge = _object(payload.get("merge", {}), "merge")
    _keys(merge, {"remove_isolated_metabolites"}, "merge")
    remove_isolated = merge.get("remove_isolated_metabolites", False)
    if not isinstance(remove_isolated, bool):
        raise ConfigError("'merge.remove_isolated_metabolites' must be boolean")

    validation = _object(payload.get("validation", {}), "validation")
    _keys(validation, {"run_memote"}, "validation")
    run_memote = validation.get("run_memote", False)
    if not isinstance(run_memote, bool):
        raise ConfigError("'validation.run_memote' must be boolean")

    return RunConfig(
        format_version=1,
        run=RunSettings(
            name=name, output_dir=_directory_path(output_value, output_base)
        ),
        reference=ReferenceSettings(
            mode=mode, input_model=input_model, cache_dir=cache_dir
        ),
        database=DatabaseSettings(records=records),
        merge=MergeSettings(remove_isolated_metabolites=remove_isolated),
        validation=ValidationSettings(run_memote=run_memote),
    )


def config_to_dict(config: RunConfig) -> dict[str, object]:
    """Return the normalized, JSON-safe snapshot representation."""
    return {
        "format_version": config.format_version,
        "run": {"name": config.run.name, "output_dir": str(config.run.output_dir)},
        "reference": {
            "mode": config.reference.mode,
            "input_model": str(config.reference.input_model),
            **(
                {"cache_dir": str(config.reference.cache_dir)}
                if config.reference.cache_dir
                else {}
            ),
        },
        "database": {"records": str(config.database.records)},
        "merge": {
            "remove_isolated_metabolites": config.merge.remove_isolated_metabolites
        },
        "validation": {"run_memote": config.validation.run_memote},
    }


def write_snapshot(config: RunConfig, run_dir: Path) -> Path:
    path = run_dir / "config.snapshot.json"
    path.write_text(
        json.dumps(config_to_dict(config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_snapshot(run_dir: str | Path) -> RunConfig:
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
    # Snapshot paths are already absolute.  The snapshot is deliberately
    # parsed using its own values, never by consulting the original config.
    config = _parse(payload, Path("/"), output_base=Path("/"))
    if config.run.output_dir != run_path:
        raise ConfigError(
            "configuration snapshot output_dir does not match run directory"
        )
    return config
