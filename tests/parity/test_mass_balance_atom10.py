"""Opt-in differential parity for the deterministic atom10 primitive."""

from __future__ import annotations

import hashlib
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
CASE_PATH = ROOT / "tests/fixtures/legacy_parity/mass-balance-atom10.json"
LEGACY_COMMIT = "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f"
CONTRACT_ID = "reference.mass-balance.atom10"
NORMALIZATION_VERSION = "atom10-vector-v1"


def _extract_legacy_module(legacy_root: str, destination: Path) -> Path:
    archive = subprocess.run(
        [
            "git",
            "-C",
            legacy_root,
            "archive",
            LEGACY_COMMIT,
            "functions/equations_bm_gdb.py",
        ],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination, filter="data")
    return destination / "functions/equations_bm_gdb.py"


def _run_atom10(source_path: Path | None, formula: str) -> list[int]:
    code = """
import importlib.util
import json
import sys

formula = sys.argv[1]
if sys.argv[2] == "legacy":
    spec = importlib.util.spec_from_file_location("legacy_mass_balance", sys.argv[3])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.atom10(formula)
else:
    from thg_protocol.model_build.mass_balance import atom10
    result = atom10(formula)
print(json.dumps(result), end="")
"""
    mode = "legacy" if source_path else "maintained"
    args = [sys.executable, "-c", code, formula, mode]
    if source_path:
        args.append(str(source_path))
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _maintained_commit() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_result(result: dict[str, object], *, result_dir: Path, case_id: str) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{case_id}.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result_path


@pytest.mark.legacy_parity
def test_atom10_matches_recorded_legacy_snapshot(tmp_path):
    legacy_root = os.environ.get("THG_LEGACY_CHECKOUT")
    if not legacy_root:
        pytest.skip("set THG_LEGACY_CHECKOUT to enable legacy parity")

    fixture = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="thg-legacy-mass-balance-") as temp_dir:
        source_path = _extract_legacy_module(legacy_root, Path(temp_dir))
        maintained = [_run_atom10(None, case["formula"]) for case in fixture["cases"]]
        legacy = [
            _run_atom10(source_path, case["formula"]) for case in fixture["cases"]
        ]

    expected = [case["expected"] for case in fixture["cases"]]
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
        "matching_fields": ["atom10_vectors"],
        "intentional_differences": [],
        "unexpected_differences": (
            []
            if maintained == expected and legacy == expected and maintained == legacy
            else ["atom10_vectors"]
        ),
        "pass": maintained == expected and legacy == expected and maintained == legacy,
    }
    result_dir = Path(os.environ.get("THG_PARITY_RESULT_DIR", str(tmp_path)))
    result_path = _write_result(
        result,
        result_dir=result_dir,
        case_id="reference-mass-balance.atom10.basic-formulas",
    )

    assert result["pass"], result_path.read_text(encoding="utf-8")
