"""Opt-in differential parity for one offline location-resolution branch."""

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
CASE_PATH = ROOT / "tests/fixtures/legacy_parity/location-resolution.json"
LEGACY_COMMIT = "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f"
CONTRACT_ID = "reference.gpr.location"
NORMALIZATION_VERSION = "location-rule-v1"


def _extract_legacy_modules(legacy_root: str, destination: Path) -> None:
    archive = subprocess.run(
        [
            "git",
            "-C",
            legacy_root,
            "archive",
            LEGACY_COMMIT,
            "functions/equations_bm_gdb.py",
            "functions/gpr/__init__.py",
            "functions/gpr/ast_gpr.py",
            "functions/gpr/gpr_def.py",
            "functions/gpr/get_location_def.py",
        ],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination, filter="data")


def _normalize_rule_map(result: list[dict[str, str]], index: int) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for location, rule in result[index].items():
        normalized[location.title()] = rule.strip("[]()").replace(" ", "")
    return dict(sorted(normalized.items()))


def _run_maintained(case: dict[str, object]) -> dict[str, object]:
    code = """
import json
import sys

from thg_protocol.gpr.location import resolve_locations
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.location import StaticLocationClient

case = json.loads(sys.argv[1])
client = StaticLocationClient({
    "https://www.uniprot.org/uniprotkb/G1_HUMAN.txt": case["location_page"]
})
ensembl = StaticEnsemblClient({
    "GENE1": EnsemblAnnotation(case["ensembl_id"])
})
result = resolve_locations(
    case["gpr"],
    case["gene_names"],
    case["gene_ids"],
    allowed_locations={"Cytosol", "Mitochondria"},
    location_client=client,
    ensembl_client=ensembl,
)
print(json.dumps({
    "locations": sorted(location.title() for location in result[0]),
    "stoich_rule": next(iter(result[0].values())).strip("[]()").replace(" ", ""),
    "plain_rule": next(iter(result[1].values())).strip("[]()").replace(" ", ""),
    "ensembl_rule": next(iter(result[2].values())).strip("[]()").replace(" ", ""),
}, sort_keys=True), end="")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, json.dumps(case)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _run_legacy(source_root: Path, case: dict[str, object]) -> dict[str, object]:
    code = """
import json
import sys
import types

case = json.loads(sys.argv[1])
sys.modules["pubchempy"] = types.ModuleType("pubchempy")
sys.modules["dill"] = types.ModuleType("dill")
sys.modules["functions.function_bm_gdb"] = types.ModuleType("functions.function_bm_gdb")
sys.path.insert(0, sys.argv[2])
import functions.gpr.get_location_def as module

class Response:
    def __init__(self, body):
        self.body = body
    def read(self):
        return self.body.encode()

class Session:
    def get(self, url):
        return types.SimpleNamespace(text="")

def urlopen(url):
    url = str(url)
    if "sp:GENE1_HUMAN" in url:
        return Response(case["legacy_uniprot_page"])
    if "hsa+GENE1" in url:
        return Response("gene=" + case["ensembl_id"])
    return Response("")

module.urllib.request.urlopen = urlopen
result = module.getLocationnew(
    case["gpr"], case["gene_names"], case["gene_ids"], 0, None, Session()
)
print(json.dumps({
    "locations": sorted(location.title() for location in result[0]),
    "stoich_rule": next(iter(result[0].values())).strip("[]()").replace(" ", ""),
    "plain_rule": next(iter(result[1].values())).strip("[]()").replace(" ", ""),
    "ensembl_rule": next(iter(result[2].values())).strip("[]()").replace(" ", ""),
}, sort_keys=True), end="")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, json.dumps(case), str(source_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


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
def test_location_resolution_matches_recorded_legacy_snapshot(tmp_path):
    legacy_root = os.environ.get("THG_LEGACY_CHECKOUT")
    if not legacy_root:
        pytest.skip("set THG_LEGACY_CHECKOUT to enable legacy parity")

    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="thg-legacy-location-") as temp_dir:
        source_root = Path(temp_dir)
        _extract_legacy_modules(legacy_root, source_root)
        maintained = _run_maintained(case)
        legacy = _run_legacy(source_root, case)

    expected = case["expected"]
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
        "matching_fields": ["locations", "stoich_rule", "plain_rule", "ensembl_rule"],
        "intentional_differences": [
            "gene-to-name mapping remains keyed by the supplied legacy identifier "
            "in the maintained compatibility tuple"
        ],
        "unexpected_differences": (
            [] if maintained == expected and legacy == expected else ["location_rules"]
        ),
        "pass": maintained == expected and legacy == expected and maintained == legacy,
    }
    result_dir = Path(os.environ.get("THG_PARITY_RESULT_DIR", str(tmp_path)))
    result_path = _write_result(
        result,
        result_dir=result_dir,
        case_id="reference-gpr-location.basic-mitochondria",
    )

    assert result["pass"], result_path.read_text(encoding="utf-8")
