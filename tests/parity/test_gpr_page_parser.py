"""Opt-in differential parity for deterministic GPR page parsing."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CASE_PATH = ROOT / "tests/fixtures/legacy_parity/gpr-page-parser.json"
LEGACY_COMMIT = "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f"


def _extract_legacy_modules(legacy_root: str, destination: Path) -> None:
    archive = subprocess.run(
        [
            "git",
            "-C",
            legacy_root,
            "archive",
            LEGACY_COMMIT,
            "functions/gpr/gpr_def.py",
            "functions/gpr/ast_gpr.py",
            "functions/gpr/__init__.py",
        ],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination, filter="data")


def _run_parser(source_root: Path | None, case: dict[str, object]) -> list[list[str]]:
    code = """
import json
import sys

case = json.loads(sys.argv[1])
if sys.argv[2] == "legacy":
    sys.path.insert(0, sys.argv[3])
    from functions.gpr.gpr_def import pattern_match_org_3
    result = pattern_match_org_3(case["page"])
else:
    from thg_protocol.gpr.lookup import parse_gene_pairs
    result = parse_gene_pairs(case["page"])
print(json.dumps(result), end="")
"""
    mode = "legacy" if source_root else "maintained"
    args = [sys.executable, "-c", code, json.dumps(case), mode]
    if source_root:
        args.append(str(source_root))
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


@pytest.mark.legacy_parity
def test_gpr_page_parser_matches_recorded_legacy_snapshot():
    legacy_root = os.environ.get("THG_LEGACY_CHECKOUT")
    if not legacy_root:
        pytest.skip("set THG_LEGACY_CHECKOUT to enable legacy parity")

    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="thg-legacy-gpr-") as temp_dir:
        source_root = Path(temp_dir)
        _extract_legacy_modules(legacy_root, source_root)
        maintained = _run_parser(None, case)
        legacy = _run_parser(source_root, case)

    assert maintained == case["expected"]
    assert legacy == case["expected"]
    assert maintained == legacy
