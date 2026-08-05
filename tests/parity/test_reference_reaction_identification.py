"""Opt-in differential parity for the first approved reaction contract."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CASE_PATH = ROOT / "tests/fixtures/legacy_parity/reference-reaction-identification.json"
LEGACY_COMMIT = "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f"
CONTRACT_ID = "reference.reaction-identification"
NORMALIZATION_VERSION = "reaction-row-v1"


def _run_identification(source_path: Path | None, case: dict[str, object]) -> str:
    code = """
import importlib.util
import json
import sys

case = json.loads(sys.argv[1])
if sys.argv[2] == "legacy":
    spec = importlib.util.spec_from_file_location("legacy_reactions", sys.argv[3])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identify_reaction = module.identify_reaction
else:
    from thg_protocol.annotation.reactions import identify_reaction

print(identify_reaction(
    case["reaction"],
    case["row_number"],
    case["metabolite_pattern"],
    case["hydrogen_ids"],
    case["water_ids"],
), end="")
"""
    mode = "legacy" if source_path else "maintained"
    args = [sys.executable, "-c", code, json.dumps(case), mode]
    if source_path:
        args.append(str(source_path))
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout


def _normalize_row(row: str) -> str:
    fields = row.rstrip("\n").split(" ")
    for index in (2, 3):
        fields[index] = ",".join(sorted(fields[index].split(",")))
    return " ".join(fields) + "\n"


def _maintained_commit() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_result(
    result: dict[str, object], *, result_dir: Path, case_id: str
) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{case_id}.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result_path


@pytest.mark.legacy_parity
def test_reaction_identification_matches_recorded_legacy_snapshot(tmp_path):
    legacy_root = os.environ.get("THG_LEGACY_CHECKOUT")
    if not legacy_root:
        pytest.skip("set THG_LEGACY_CHECKOUT to enable legacy parity")

    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    source = subprocess.run(
        [
            "git",
            "-C",
            legacy_root,
            "show",
            f"{LEGACY_COMMIT}:functions/function_reac_identification.py",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    with tempfile.TemporaryDirectory(prefix="thg-legacy-parity-") as temp_dir:
        source_path = Path(temp_dir) / "legacy_reactions.py"
        source_path.write_text(source, encoding="utf-8")
        maintained = _run_identification(None, case)
        legacy = _run_identification(source_path, case)

    maintained_row = _normalize_row(maintained)
    legacy_row = _normalize_row(legacy)
    expected_row = str(case["expected"])
    result = {
        "contract_id": CONTRACT_ID,
        "legacy_commit": LEGACY_COMMIT,
        "maintained_commit": _maintained_commit(),
        "fixture_checksums": {
            CASE_PATH.relative_to(ROOT).as_posix(): hashlib.sha256(
                CASE_PATH.read_bytes()
            ).hexdigest()
        },
        "normalization_version": NORMALIZATION_VERSION,
        "matching_fields": ["normalized_reaction_row"],
        "intentional_differences": [],
        "unexpected_differences": (
            []
            if maintained_row == expected_row and legacy_row == expected_row
            else ["normalized_reaction_row"]
        ),
        "pass": maintained_row == expected_row and legacy_row == expected_row,
    }
    result_dir = Path(os.environ.get("THG_PARITY_RESULT_DIR", str(tmp_path)))
    result_path = _write_result(
        result,
        result_dir=result_dir,
        case_id="reference-reaction-identification.basic-filtered-row",
    )

    assert result["pass"], result_path.read_text(encoding="utf-8")
