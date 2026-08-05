from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from thg_protocol.workflow.config import (
    DatabaseSettings,
    MergeSettings,
    ReferenceSettings,
    RunConfig,
    RunSettings,
    ValidationSettings,
)
from thg_protocol.workflow.stages import MemoteStage, ReferenceStage, StageContext


def _config(tmp_path: Path, cache_dir: Path | None = None) -> RunConfig:
    model = tmp_path / "reference.json"
    records = tmp_path / "records.json"
    model.write_text("{}", encoding="utf-8")
    records.write_text("{}", encoding="utf-8")
    return RunConfig(
        1,
        RunSettings("toy", tmp_path / "run"),
        ReferenceSettings("build_model", model, cache_dir),
        DatabaseSettings(records),
        MergeSettings(),
        ValidationSettings(),
    )


def test_reference_fingerprint_includes_configured_cache(tmp_path):
    cache_dir = tmp_path / "shared-cache"
    config = _config(tmp_path, cache_dir)
    fingerprint = ReferenceStage().fingerprint_data(
        StageContext(config, config.run.output_dir, {})
    )

    assert fingerprint["data"]["configuration"]["cache_dir"] == str(cache_dir)


def test_reference_uses_configured_cache_and_portable_report(tmp_path, monkeypatch):
    cache_dir = tmp_path / "shared-cache"
    config = _config(tmp_path, cache_dir)
    work_dir = tmp_path / "work"
    seen: dict[str, Path] = {}

    def fake_build_model_batch(
        input_path, output_path, *, output_errors, cache_dir, **kwargs
    ):
        del kwargs
        seen["cache_dir"] = Path(cache_dir)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("{}", encoding="utf-8")
        Path(output_errors).write_text("service\terror\n", encoding="utf-8")
        Path(cache_dir).mkdir(parents=True)
        return SimpleNamespace(
            input_path=Path(input_path),
            output_path=Path(output_path),
            cache_dir=Path(cache_dir),
            kegg_reactions=0,
            biocyc_ec_pages=0,
            ensembl_genes=0,
            errors=[],
        )

    monkeypatch.setattr(
        "thg_protocol.model_build.build_model_batch", fake_build_model_batch
    )
    monkeypatch.setattr(
        "thg_protocol.workflow.stages._load_cobra_model", lambda path: object()
    )

    ReferenceStage().run(StageContext(config, tmp_path / "run", {}), work_dir)

    assert seen["cache_dir"] == cache_dir
    report = json.loads((work_dir / "build-report.json").read_text(encoding="utf-8"))
    assert report["output_path"] == "reference-model.json"
    assert report["cache_dir"] == str(cache_dir)
    cache_manifest = json.loads(
        (work_dir / "cache-manifest.json").read_text(encoding="utf-8")
    )
    assert cache_manifest["ownership"] == "external"


def _memote_context(config: RunConfig, run_dir: Path) -> StageContext:
    merge_model = run_dir / "candidate-thg.json"
    merge_model.parent.mkdir(parents=True, exist_ok=True)
    merge_model.write_text("{}", encoding="utf-8")
    manifest = {
        "steps": {
            "merge": {
                "outputs": [{"role": "model", "path": merge_model.name}]
            }
        }
    }
    return StageContext(config, run_dir, manifest, run_dir / "memote.log")


def test_memote_stage_records_version_and_html_output(tmp_path, monkeypatch):
    config = _config(tmp_path)
    context = _memote_context(config, tmp_path / "run")
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    monkeypatch.setattr("thg_protocol.workflow.stages.shutil.which", lambda name: name)

    def fake_run(command, **kwargs):
        del kwargs
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="memote 0.15", stderr="")
        output = Path(command[command.index("--filename") + 1])
        output.write_text("<html>report</html>", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("thg_protocol.workflow.stages.subprocess.run", fake_run)

    result = MemoteStage().run(context, work_dir)

    assert result.summary["version"] == "memote 0.15"
    assert result.outputs[0][1].read_text() == "<html>report</html>"


def test_memote_stage_rejects_nonzero_exit(tmp_path, monkeypatch):
    config = _config(tmp_path)
    context = _memote_context(config, tmp_path / "run")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.setattr("thg_protocol.workflow.stages.shutil.which", lambda name: name)
    monkeypatch.setattr(
        "thg_protocol.workflow.stages.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(returncode=3, stdout="", stderr=""),
    )

    with pytest.raises(RuntimeError, match="exit code 3"):
        MemoteStage().run(context, work_dir)


def test_memote_stage_rejects_missing_report(tmp_path, monkeypatch):
    config = _config(tmp_path)
    context = _memote_context(config, tmp_path / "run")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.setattr("thg_protocol.workflow.stages.shutil.which", lambda name: name)

    def fake_run(command, **kwargs):
        del kwargs
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="memote 0.15", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("thg_protocol.workflow.stages.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="without a nonempty HTML report"):
        MemoteStage().run(context, work_dir)
