"""Executable checks for the supported package CI matrix contract."""

import json
import re
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
    for command in ("thg-gapfill", "thg-compare", "thg-pathway", "thg-run"):
        assert f'"$smoke_dir/venv/bin/{command}" --help' in workflow


def test_installed_commands_match_packaging_and_api_inventory():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scripts_section = pyproject.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
    scripts = dict(
        re.findall(r'^([A-Za-z0-9-]+)\s*=\s*"([^"]+)"$', scripts_section, re.M)
    )
    inventory = json.loads(
        (ROOT / "docs/api/api-inventory.json").read_text(encoding="utf-8")
    )
    inventory_scripts = {}
    for module in inventory["modules"]:
        for name, target in scripts.items():
            target_module, target_symbol = target.split(":", 1)
            if (
                target_module == module["module"]
                and target_symbol in module["symbols"]
            ):
                inventory_scripts[name] = target

    assert inventory_scripts == scripts
    cli_page = (ROOT / "docs/api/cli.md").read_text(encoding="utf-8")
    assert all(f"`{command}`" in cli_page for command in scripts)
