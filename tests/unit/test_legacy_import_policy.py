"""Executable gates for the final legacy-directory removal."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/legacy-api-inventory.md"
CHECKSUM_MANIFEST = ROOT / "docs/canonical-artifact-checksums.txt"
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
CANONICAL_ROOTS = (
    "supplementary_material/model_comparisons",
    "supplementary_material/figures/generate_figures",
    "files/pathway",
    "supplementary_material/pathway",
    "supplementary_material/metabolite_reaction",
    "docs/assets",
    "tests/fixtures/memote/data",
    "tests/fixtures/legacy_characterization",
)
LFS_CANONICAL_PATHS = {
    "files/pathway/inputs/endoA_250917_3.json",
    "files/MEMOTE_model_THG_endoA_reduced_2506.html",
    "supplementary_material/pathway/figures/Glycocalyx_Cytoskeleton_network_plotly.html",
}


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _python_sources(root: Path) -> list[tuple[Path, str]]:
    sources = []
    for path in root.rglob("*.py"):
        sources.append((path, path.read_text(encoding="utf-8")))
    for path in root.rglob("*.ipynb"):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for _index, cell in enumerate(notebook.get("cells", [])):
            if cell.get("cell_type") == "code":
                sources.append((path, "".join(cell.get("source", []))))
    return sources


def _legacy_imports(text: str, filename: str) -> list[tuple[int, str]]:
    tree = ast.parse(text, filename=filename)
    return _imported_modules_from_tree(tree)


def _imported_modules_from_tree(tree: ast.AST) -> list[tuple[int, str]]:
    imports = []
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


def test_maintained_sources_do_not_import_legacy_namespaces():
    violations = []
    roots = [
        ROOT / name for name in ("src", "tests", "examples", "supplementary_material")
    ]
    for root in roots:
        if not root.exists():
            continue
        for path, text in _python_sources(root):
            for line, module in _legacy_imports(text, str(path)):
                if module.split(".", 1)[0] in LEGACY_DIRECTORIES:
                    violations.append(f"{path.relative_to(ROOT)}:{line}: {module}")

    assert not violations, "maintained sources import legacy code:\n" + "\n".join(
        violations
    )


def test_documentation_snippets_do_not_import_legacy_namespaces():
    legacy = "|".join(map(re.escape, LEGACY_DIRECTORIES))
    patterns = (
        re.compile(r"^from\s+(?:" + legacy + r")(?:\.|\s+import)"),
        re.compile(r"^import\s+(?:" + legacy + r")(?:\.|\s+as|\s*$)"),
    )
    violations = []
    for root in (ROOT / "README.md", ROOT / "docs"):
        paths = [root] if root.is_file() else root.rglob("*.md")
        for path in paths:
            for line, text in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                fragments = [fragment.strip(" \"'") for fragment in text.split(";")]
                if any(
                    pattern.search(fragment)
                    for fragment in fragments
                    for pattern in patterns
                ):
                    violations.append(f"{path.relative_to(ROOT)}:{line}")
    assert not violations, "documentation imports legacy code:\n" + "\n".join(
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


def test_canonical_artifacts_are_tracked_and_checksums_match():
    checksums = {}
    for raw_line in CHECKSUM_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        relative_path, expected = raw_line.split(" | ", 1)
        checksums[relative_path] = expected

    tracked_paths = set()
    for root in CANONICAL_ROOTS:
        result = subprocess.run(
            ["git", "ls-files", "--", root],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_paths.update(result.stdout.splitlines())
    assert set(checksums) == tracked_paths - LFS_CANONICAL_PATHS

    for relative_path, expected in checksums.items():
        path = ROOT / relative_path
        assert path.is_file(), f"canonical artifact is missing: {relative_path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"checksum changed: {relative_path}"


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
