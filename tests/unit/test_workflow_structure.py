from __future__ import annotations

import ast
from pathlib import Path

from thg_protocol.workflow.registry import list_workflows
from thg_protocol.workflow.runner import get_status, resume, start

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/thg_protocol/runtime"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_runtime_isolated_from_workflow_and_domain_packages():
    forbidden = (
        "thg_protocol.workflow",
        "thg_protocol.curation",
        "thg_protocol.gapfill",
        "thg_protocol.pathway",
        "thg_protocol.cell_specific",
    )
    violations = {
        f"{path.name}: {module}"
        for path in RUNTIME.glob("*.py")
        for module in _imports(path)
        if module == forbidden[0]
        or module.startswith(forbidden[0] + ".")
        or any(
            module == name or module.startswith(name + ".") for name in forbidden[1:]
        )
    }
    assert not violations


def test_public_runner_and_builtin_registry_contract():
    assert callable(start)
    assert callable(resume)
    assert callable(get_status)
    assert set(list_workflows()) == {
        "beta1",
        "beta2",
        "gapfill",
        "reference",
        "validate",
        "compare",
        "cell-specific",
        "pathway",
        "human-database",
        "final-thg",
    }
