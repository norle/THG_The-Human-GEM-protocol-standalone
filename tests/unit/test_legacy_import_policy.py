"""Executable gates for the final legacy-directory removal."""

from __future__ import annotations

import ast
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
CANONICAL_ARTIFACTS = (
    "supplementary_material/model_comparisons/THG_vs_Human1.xlsx",
    "supplementary_material/figures/generate_figures",
    "files/pathway/config/config_glycocalyx_cytoskeleton.json",
    "files/pathway/config/pathway-specific/config_hyaluronan.json",
    "files/pathway/inputs/config_example.json",
    "files/pathway/inputs/endoA_250917_3.json",
    "supplementary_material/pathway/reports",
    "tests/fixtures/memote/data",
    "supplementary_material/metabolite_reaction/met_annotation.tsv",
    "docs/assets/component_visualization_template.html",
    "tests/fixtures/legacy_characterization/reac_identification/files/ec-number.tsv",
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
            if module.split(".", 1)[0] in LEGACY_DIRECTORIES:
                violations.append(f"{path.relative_to(ROOT)}:{line}: {module}")

    assert not violations, "maintained package imports legacy code:\n" + "\n".join(
        violations
    )


def test_all_legacy_directories_are_closed():
    remaining = [
        directory for directory in LEGACY_DIRECTORIES if (ROOT / directory).exists()
    ]
    assert not remaining, "legacy directories remain: " + ", ".join(remaining)


def test_closed_directory_artifacts_have_canonical_owners():
    missing = [path for path in CANONICAL_ARTIFACTS if not (ROOT / path).exists()]
    assert not missing, "relocated artifacts are missing: " + ", ".join(missing)


def test_relocated_pathway_artifacts_are_tracked_at_their_canonical_paths():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "files/pathway/inputs/endoA_250917_3.json filter=lfs" in attributes
    assert "implement_pathway/examples/inputs/endoA_250917_3.json" not in attributes
    assert "!/files/pathway/**" in ignore_rules


def test_inventory_records_every_removed_legacy_python_file():
    inventory = INVENTORY.read_text(encoding="utf-8")
    manifest = inventory.split("## Final removal manifest", 1)[1]
    manifest = manifest.split("```text", 1)[1].split("```", 1)[0]
    lines = [line.strip() for line in manifest.splitlines() if line.strip()]
    paths = [line.split(" | ", 1)[0] for line in lines]
    assert len(paths) == len(set(paths)) == 82
    assert all(" | Removed | " in line for line in lines)


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
