"""Executable gates for the legacy inventory and package import boundary."""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/legacy-api-inventory.md"
LEGACY_DIRECTORIES = (
    "build_model",
    "cell_type_specific_model",
    "compare_models",
    "functions",
    "gapfill",
    "generate_data-base",
    "generate_figures",
    "implement_pathway",
    "memote_and_task_analysis",
    "merge_metabolic_netowrks_and_network_consistency",
    "metabolite_reac_identification",
    "network_analysis",
    "test_algorithms",
    "tools",
    "utils",
)
LEGACY_MODULE_ROOTS = tuple(LEGACY_DIRECTORIES)
ARCHIVED_WORKFLOWS = (
    "build_model/test_biovelo_query.py",
    "cell_type_specific_model/gimme_parallel.py",
    "cell_type_specific_model/ptr_multi_round.py",
    "cell_type_specific_model/ptr_one_round.py",
    "cell_type_specific_model/transcriptomics.py",
    "functions/add_reaction.py",
    "functions/class_generate_database.py",
    "functions/function_bm_gdb.py",
    "functions/functions_compare_models.py",
    "functions/functions_create_figure.py",
    "functions/pattern_generate_database.py",
    "gapfill/phase1_connect_components.py",
    "gapfill/phase2_minimal_connector.py",
    "gapfill/phase2_prioritized_connector.py",
    "gapfill/phase3_blocked_optimizer.py",
    "gapfill/phase3_component_milp.py",
    "gapfill/phase3_greedy_optimizer.py",
    "gapfill/phase3_milp_optimizer.py",
    "gapfill/phase3_sink_milp_original.py",
    "gapfill/phase3_tiered_milp.py",
    "implement_pathway/validate.py",
    "implement_pathway/visualize.py",
    "memote_and_task_analysis/metabolic_tasks/evaluation.py",
    "memote_and_task_analysis/metabolic_tasks/task.py",
    "memote_and_task_analysis/tests_extra/test_metabolic_tasks.py",
    "network_analysis/loop_removal.py",
)


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def test_package_code_does_not_import_legacy_namespaces():
    violations = []
    for path in (ROOT / "src/thg_protocol").rglob("*.py"):
        for line, module in _imported_modules(path):
            if module.split(".", 1)[0] in LEGACY_MODULE_ROOTS:
                violations.append(f"{path.relative_to(ROOT)}:{line}: {module}")

    assert not violations, "maintained package imports legacy code:\n" + "\n".join(
        violations
    )


def test_inventory_lists_every_legacy_python_file():
    inventory = INVENTORY.read_text(encoding="utf-8")
    files = []
    for directory in LEGACY_DIRECTORIES:
        files.extend(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / directory).rglob("*.py")
        )

    assert len(files) == 82
    missing = sorted(path for path in files if path not in inventory)
    assert not missing, "legacy files missing from inventory:\n" + "\n".join(missing)

    manifest_header = "## Complete exact-file manifest"
    manifest = inventory.split(manifest_header, 1)[1].split("```text", 1)[1]
    manifest = manifest.split("```", 1)[0]
    listed = [line.strip() for line in manifest.splitlines() if line.strip()]
    assert len(listed) == len(set(listed)) == 82
    assert set(listed) == set(files)


def test_inventory_and_contracts_define_the_required_evidence_fields():
    inventory = INVENTORY.read_text(encoding="utf-8")
    contracts = (ROOT / "docs/api-contracts.md").read_text(encoding="utf-8")

    for field in (
        "Legacy path/import path",
        "Package replacement",
        "Status",
        "Evidence",
        "Consumers",
        "Removal condition",
    ):
        assert field.lower() in inventory.lower()
    for group in range(1, 10):
        assert f"| `C{group}`" in contracts

    assert "No replacement" in inventory
    assert "Intentional difference" in inventory
    assert "Archived" in inventory


def test_closeout_plan_is_referenced_by_supported_documentation():
    for relative_path in ("README.md", "docs/index.md", "CURRENT_STATE.md"):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "REFACTORING_PLAN_NEXT.md" in text


def test_archived_workflows_declare_their_unsupported_status_in_docstrings():
    missing_status = []
    for relative_path in ARCHIVED_WORKFLOWS:
        with warnings.catch_warnings():
            # Historical scripts contain invalid escape sequences in regular
            # expressions. Their source status, not warning hygiene, is what
            # this syntax-only audit is checking.
            warnings.simplefilter("ignore")
            tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        docstring = (ast.get_docstring(tree) or "").lower()
        if "archived" not in docstring or "installed" not in docstring:
            missing_status.append(relative_path)

    assert not missing_status, (
        "archived workflows lack explicit module status:\n"
        + "\n".join(missing_status)
    )
