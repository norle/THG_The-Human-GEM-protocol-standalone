"""Installed-style subprocess smoke tests for published CLI modules."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "thg_protocol.gapfill.cli",
        "thg_protocol.analysis.compare_cli",
        "thg_protocol.pathway.cli",
    ],
)
def test_cli_help_runs_from_outside_checkout(tmp_path, module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize(
    "script",
    [
        "compare_models/compare_models.py",
        "implement_pathway/pathway_implementation.py",
        "merge_metabolic_netowrks_and_network_consistency/merge_metabolic_networks.py",
        "build_model/build_model.py",
        "cell_type_specific_model/model_reduce.py",
        "generate_figures/create_figure.py",
        "generate_data-base/make_model_from_pkl.py",
        "generate_data-base/resume_db_gen.py",
        "generate_data-base/generate_db.py",
        "build_model/build_model_batch.py",
    ],
)
def test_legacy_workflow_help_is_import_safe(tmp_path, script):
    repository = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, str(repository / script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
