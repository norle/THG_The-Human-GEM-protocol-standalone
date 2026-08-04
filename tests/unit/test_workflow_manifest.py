from __future__ import annotations

import json

import pytest

from thg_protocol.workflow.config import (
    DatabaseSettings,
    MergeSettings,
    ReferenceSettings,
    RunConfig,
    RunSettings,
    ValidationSettings,
)
from thg_protocol.workflow.manifest import (
    ManifestError,
    load_manifest,
    new_manifest,
    write_manifest_atomic,
)


def _config(tmp_path):
    return RunConfig(
        1,
        RunSettings("toy", tmp_path),
        ReferenceSettings("prebuilt", tmp_path / "reference.json"),
        DatabaseSettings(tmp_path / "records.json"),
        MergeSettings(),
        ValidationSettings(),
    )


def test_manifest_has_all_stages_and_atomic_round_trip(tmp_path):
    manifest = new_manifest(_config(tmp_path))
    write_manifest_atomic(tmp_path, manifest)
    assert load_manifest(tmp_path)["steps"]["reference"]["status"] == "pending"
    assert not (tmp_path / "manifest.json.tmp").exists()


def test_manifest_rejects_bad_version_and_step_shape(tmp_path):
    manifest = new_manifest(_config(tmp_path))
    manifest["format_version"] = 2
    with pytest.raises(ManifestError):
        write_manifest_atomic(tmp_path, manifest)
    manifest = new_manifest(_config(tmp_path))
    manifest["steps"]["reference"]["status"] = "unknown"
    with pytest.raises(ManifestError):
        write_manifest_atomic(tmp_path, manifest)


def test_failed_atomic_write_does_not_replace_previous_manifest(tmp_path, monkeypatch):
    manifest = new_manifest(_config(tmp_path))
    write_manifest_atomic(tmp_path, manifest)
    original = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    changed = new_manifest(_config(tmp_path))
    monkeypatch.setattr(
        "thg_protocol.workflow.manifest.os.replace",
        lambda *_: (_ for _ in ()).throw(OSError("stop")),
    )
    with pytest.raises(OSError):
        write_manifest_atomic(tmp_path, changed)
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == original
    assert json.loads(original)["format_version"] == 1
