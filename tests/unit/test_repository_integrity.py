"""Checks for tracked canonical artifacts and their recorded content."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKSUM_MANIFEST = ROOT / "docs/canonical-artifact-checksums.txt"
REQUIRED_ARTIFACTS = (
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


def test_required_artifacts_exist():
    missing = [path for path in REQUIRED_ARTIFACTS if not (ROOT / path).exists()]
    assert not missing, "required artifacts are missing: " + ", ".join(missing)


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
