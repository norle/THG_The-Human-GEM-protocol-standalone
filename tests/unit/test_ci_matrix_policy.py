"""Executable checks for the supported package CI matrix contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"


def test_ci_declares_the_supported_python_matrix_and_constraints():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "fail-fast: false" in workflow
    for version in ("3.10", "3.11", "3.12"):
        assert f'python-version: "{version}"' in workflow
        assert f"constraints/py{version.replace('.', '')}-glpk.txt" in workflow


def test_ci_keeps_default_release_checks_offline_and_installed_smoke_scoped():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "pytest -m" in workflow
    for marker in ("slow", "online", "solver", "gurobi", "memote"):
        assert f"not {marker}" in workflow
    assert "python -m build" in workflow
    assert "pip install --no-deps dist/*.whl" in workflow
    for command in ("thg-gapfill", "thg-compare", "thg-pathway"):
        assert f'"$smoke_dir/venv/bin/{command}" --help' in workflow
