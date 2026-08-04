from __future__ import annotations

import json

import pytest

from thg_protocol.workflow.config import (
    ConfigError,
    config_to_dict,
    load_snapshot,
    load_start_config,
    write_snapshot,
)


def _payload(tmp_path):
    model = tmp_path / "inputs" / "reference.json"
    records = tmp_path / "inputs" / "records.json"
    model.parent.mkdir(exist_ok=True)
    model.write_text("{}", encoding="utf-8")
    records.write_text('{"model_id":"toy"}', encoding="utf-8")
    return {
        "format_version": 1,
        "run": {"name": "toy-run", "output_dir": "results/toy-run"},
        "reference": {"mode": "prebuilt", "input_model": "inputs/reference.json"},
        "database": {"records": "inputs/records.json"},
    }


def test_start_config_resolves_inputs_relative_to_config(tmp_path, monkeypatch):
    source = tmp_path / "config.json"
    source.write_text(json.dumps(_payload(tmp_path)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = load_start_config(source)

    assert (
        config.reference.input_model == (tmp_path / "inputs/reference.json").resolve()
    )
    assert config.database.records == (tmp_path / "inputs/records.json").resolve()
    assert config.run.output_dir == (tmp_path / "results/toy-run").resolve()


def test_unknown_keys_and_non_boolean_values_are_rejected(tmp_path):
    payload = _payload(tmp_path)
    payload["unknown"] = True
    source = tmp_path / "config.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown key"):
        load_start_config(source)

    payload = _payload(tmp_path)
    payload["merge"] = {"remove_isolated_metabolites": "false"}
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigError, match="must be boolean"):
        load_start_config(source)


def test_snapshot_is_normalized_and_self_contained(tmp_path, monkeypatch):
    source = tmp_path / "config.json"
    source.write_text(json.dumps(_payload(tmp_path)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = load_start_config(source)
    run_dir = config.run.output_dir
    run_dir.mkdir(parents=True)
    write_snapshot(config, run_dir)
    source.unlink()

    loaded = load_snapshot(run_dir)
    assert config_to_dict(loaded) == config_to_dict(config)
    assert "unknown" not in json.dumps(config_to_dict(loaded))
