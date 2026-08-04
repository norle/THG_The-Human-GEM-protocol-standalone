"""Stage adapters for the maintained THG APIs."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import RunConfig
from .hashing import sha256_file


@dataclass(frozen=True)
class StageContext:
    config: RunConfig
    run_dir: Path
    manifest: Mapping[str, object]
    log_path: Path | None = None


@dataclass(frozen=True)
class StageResult:
    outputs: tuple[tuple[str, Path], ...]
    summary: Mapping[str, object]


class Stage(Protocol):
    id: str
    dependencies: tuple[str, ...]
    implementation_version: int

    def enabled(self, config: RunConfig) -> bool: ...

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]: ...

    def run(self, context: StageContext, work_dir: Path) -> StageResult: ...

    def validate(self, result: StageResult) -> None: ...


def _load_cobra_model(path: str | Path) -> Any:
    from cobra.io import load_json_model, read_sbml_model

    source = Path(path)
    return (
        load_json_model(str(source))
        if source.suffix.lower() == ".json"
        else read_sbml_model(str(source))
    )


def _dependency_records(
    context: StageContext, stage_id: str
) -> list[Mapping[str, object]]:
    steps = context.manifest.get("steps")
    if not isinstance(steps, Mapping):
        raise RuntimeError("manifest has no steps")
    entry = steps.get(stage_id)
    if not isinstance(entry, Mapping):
        raise RuntimeError(f"missing dependency step: {stage_id}")
    outputs = entry.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise RuntimeError(f"dependency has no outputs: {stage_id}")
    return [item for item in outputs if isinstance(item, Mapping)]


def _dependency_path(context: StageContext, stage_id: str, role: str) -> Path:
    for record in _dependency_records(context, stage_id):
        if record.get("role") == role and isinstance(record.get("path"), str):
            return context.run_dir / str(record["path"])
    raise RuntimeError(f"dependency '{stage_id}' has no output role '{role}'")


def _dependency_hashes(
    context: StageContext, stage_ids: tuple[str, ...]
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for stage_id in stage_ids:
        result[stage_id] = [
            str(record.get("sha256"))
            for record in _dependency_records(context, stage_id)
            if isinstance(record.get("sha256"), str)
        ]
    return result


def _fingerprint(
    stage: str, version: int, data: Mapping[str, object]
) -> Mapping[str, object]:
    return {
        "stage": stage,
        "implementation_version": version,
        "package_version": _package_version(),
        "data": data,
    }


def _package_version() -> str:
    try:
        from thg_protocol import __version__

        return str(__version__)
    except Exception:  # pragma: no cover
        return "unknown"


def _report_path(path: str | Path, work_dir: Path) -> str:
    """Represent work-directory paths independently of temporary promotion."""
    candidate = Path(path).resolve()
    try:
        return candidate.relative_to(work_dir.resolve()).as_posix()
    except ValueError:
        return str(candidate)


class ReferenceStage:
    id = "reference"
    dependencies: tuple[str, ...] = ()
    implementation_version = 1

    def enabled(self, config: RunConfig) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        reference = context.config.reference
        return _fingerprint(
            self.id,
            self.implementation_version,
            {
                "configuration": {
                    "mode": reference.mode,
                    "cache_dir": (
                        str(reference.cache_dir)
                        if reference.cache_dir is not None
                        else None
                    ),
                },
                "input_suffix": reference.input_model.suffix.lower(),
                "input_sha256": sha256_file(reference.input_model),
            },
        )

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        reference = context.config.reference
        destination = (
            work_dir / f"reference-model{reference.input_model.suffix.lower()}"
        )
        if reference.mode == "prebuilt":
            shutil.copy2(reference.input_model, destination)
            _load_cobra_model(destination)
            return StageResult((("model", destination),), {"mode": "prebuilt"})

        from thg_protocol.model_build import build_model_batch

        errors = work_dir / "errors.tsv"
        cache = reference.cache_dir or (work_dir / "cache")
        report = build_model_batch(
            reference.input_model,
            destination,
            output_errors=errors,
            cache_dir=cache,
        )
        report_path = work_dir / "build-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "input_path": _report_path(report.input_path, work_dir),
                    "output_path": _report_path(report.output_path, work_dir),
                    "cache_dir": _report_path(report.cache_dir, work_dir),
                    "kegg_reactions": report.kegg_reactions,
                    "biocyc_ec_pages": report.biocyc_ec_pages,
                    "ensembl_genes": report.ensembl_genes,
                    "errors": list(report.errors),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _load_cobra_model(destination)
        return StageResult(
            (("model", destination), ("errors", errors), ("report", report_path)),
            {"mode": "build_model", "errors": len(report.errors)},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or not result.outputs[0][1].is_file():
            raise ValueError("reference stage did not produce a readable model")


class DatabaseStage:
    id = "database"
    dependencies: tuple[str, ...] = ()
    implementation_version = 1

    def enabled(self, config: RunConfig) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return _fingerprint(
            self.id,
            self.implementation_version,
            {"input_sha256": sha256_file(context.config.database.records)},
        )

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.database import reconstruct_model_from_json

        destination = work_dir / "human-database.json"
        model = reconstruct_model_from_json(
            context.config.database.records, output_path=destination
        )
        loaded = _load_cobra_model(destination)
        return StageResult(
            (("model", destination),),
            {
                "model_id": str(loaded.id),
                "metabolites": len(loaded.metabolites),
                "reactions": len(loaded.reactions),
                "genes": len(loaded.genes),
                "reconstructed_model_id": str(model.id),
            },
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or not result.outputs[0][1].is_file():
            raise ValueError("database stage did not produce a readable model")


class MergeStage:
    id = "merge"
    dependencies = ("reference", "database")
    implementation_version = 1

    def enabled(self, config: RunConfig) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return _fingerprint(
            self.id,
            self.implementation_version,
            {
                "configuration": {
                    "remove_isolated_metabolites": (
                        context.config.merge.remove_isolated_metabolites
                    )
                },
                "dependencies": _dependency_hashes(context, self.dependencies),
            },
        )

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.merge import merge_models_from_paths

        destination = work_dir / "candidate-thg.json"
        _, report = merge_models_from_paths(
            _dependency_path(context, "reference", "model"),
            _dependency_path(context, "database", "model"),
            destination,
            remove_isolated_metabolites=context.config.merge.remove_isolated_metabolites,
        )
        model = _load_cobra_model(destination)
        if not model.metabolites or not model.reactions:
            raise ValueError("merge produced a model with no metabolites or reactions")
        report_path = work_dir / "merge-report.json"
        report_path.write_text(
            json.dumps(
                {
                    "added_metabolites": report.added_metabolites,
                    "added_reactions": report.added_reactions,
                    "overlapping_metabolites": report.overlapping_metabolites,
                    "overlapping_reactions": report.overlapping_reactions,
                    "removed_isolated_metabolites": report.removed_isolated_metabolites,
                    "output_path": _report_path(destination, work_dir),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return StageResult(
            (("model", destination), ("report", report_path)),
            {"metabolites": len(model.metabolites), "reactions": len(model.reactions)},
        )

    def validate(self, result: StageResult) -> None:
        if not result.outputs or not result.outputs[0][1].is_file():
            raise ValueError("merge stage did not produce a readable model")


class ValidationStage:
    id = "validation"
    dependencies = ("merge",)
    implementation_version = 1

    def enabled(self, config: RunConfig) -> bool:
        del config
        return True

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return _fingerprint(
            self.id,
            self.implementation_version,
            {"dependencies": _dependency_hashes(context, self.dependencies)},
        )

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        from thg_protocol.analysis import (
            find_network_components,
            write_component_report,
        )
        from thg_protocol.analysis.consistency import (
            dead_end_metabolites,
            orphan_metabolites,
            unbalanced_reactions,
            unbalanced_reactions_by_charge,
        )

        model = _load_cobra_model(_dependency_path(context, "merge", "model"))
        components = find_network_components(model)
        components_path = work_dir / "components.json"
        write_component_report(components, components_path)
        consistency = {
            "unbalanced_reactions": sorted(unbalanced_reactions(model)),
            "unbalanced_reactions_by_charge": sorted(
                unbalanced_reactions_by_charge(model)
            ),
            "orphan_metabolites": sorted(orphan_metabolites(model)),
            "dead_end_metabolites": sorted(dead_end_metabolites(model)),
        }
        consistency_path = work_dir / "consistency.json"
        consistency_path.write_text(
            json.dumps(
                {
                    "counts": {key: len(value) for key, value in consistency.items()},
                    "results": consistency,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return StageResult(
            (("components", components_path), ("consistency", consistency_path)),
            {
                "component_count": len(components["components"]),
                "consistency": consistency["results"]
                if "results" in consistency
                else consistency,
            },
        )

    def validate(self, result: StageResult) -> None:
        if len(result.outputs) != 2 or any(
            not path.is_file() for _, path in result.outputs
        ):
            raise ValueError("validation stage did not produce both reports")


class MemoteStage:
    id = "memote"
    dependencies = ("merge",)
    implementation_version = 1

    def enabled(self, config: RunConfig) -> bool:
        return config.validation.run_memote

    def fingerprint_data(self, context: StageContext) -> Mapping[str, object]:
        return _fingerprint(
            self.id,
            self.implementation_version,
            {
                "dependencies": _dependency_hashes(context, self.dependencies),
                "enabled": True,
            },
        )

    def run(self, context: StageContext, work_dir: Path) -> StageResult:
        executable = shutil.which("memote")
        if executable is None:
            raise RuntimeError(
                "MEMOTE is enabled but 'memote' was not found; install it separately "
                "or disable validation.run_memote"
            )
        model_path = _dependency_path(context, "merge", "model")
        output = work_dir / "memote.html"
        log_path = context.log_path or (work_dir / "memote.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [executable, "run", "--filename", str(output), str(model_path)],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"MEMOTE failed with exit code {completed.returncode}")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("MEMOTE completed without a nonempty HTML report")
        version = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=False
        )
        return StageResult(
            (("html", output),),
            {
                "command": "memote",
                "version": (version.stdout or version.stderr).strip(),
            },
        )

    def validate(self, result: StageResult) -> None:
        if (
            len(result.outputs) != 1
            or not result.outputs[0][1].is_file()
            or result.outputs[0][1].stat().st_size == 0
        ):
            raise ValueError("MEMOTE did not produce a nonempty report")


STAGE_OBJECTS: tuple[Stage, ...] = (
    ReferenceStage(),
    DatabaseStage(),
    MergeStage(),
    ValidationStage(),
    MemoteStage(),
)


def validate_stage_order(stages: tuple[Stage, ...] = STAGE_OBJECTS) -> None:
    positions = {stage.id: index for index, stage in enumerate(stages)}
    if set(positions) != {"reference", "database", "merge", "validation", "memote"}:
        raise ValueError("workflow stage IDs do not match version 1")
    for stage in stages:
        for dependency in stage.dependencies:
            if (
                dependency not in positions
                or positions[dependency] >= positions[stage.id]
            ):
                raise ValueError(
                    f"stage dependency order is invalid: {dependency} -> {stage.id}"
                )
