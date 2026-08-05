"""Opt-in differential parity for the metabolite-identification contract."""

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
CASE_PATH = (
    ROOT / "tests/fixtures/legacy_parity/reference-metabolite-identification.json"
)
LEGACY_COMMIT = "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f"


def _extract_legacy_modules(legacy_root: str, destination: Path) -> None:
    archive = subprocess.run(
        [
            "git",
            "-C",
            legacy_root,
            "archive",
            LEGACY_COMMIT,
            "functions/function_metabolite_identification.py",
            "functions/function_reac_identification.py",
        ],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination, filter="data")


def _run_maintained(case: dict[str, object]) -> str:
    code = """
import json
import sys

from thg_protocol.annotation.metabolites import identify_metabolite
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient

case = json.loads(sys.argv[1])
compound = case["compound"]
client = StaticPubChemClient({case["name"]: PubChemCompound(**compound)})
result = identify_metabolite(
    case["name"],
    case["formula"],
    case["identifier"],
    threshold=case["threshold"],
    client=client,
)
print(result or "", end="")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, json.dumps(case)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _run_legacy(source_root: Path, case: dict[str, object]) -> str:
    code = """
import json
import sys
import types

case = json.loads(sys.argv[1])
compound = case["compound"]
pubchempy = types.ModuleType("pubchempy")

class FakeCompound:
    cid = compound["cid"]
    molecular_formula = compound["molecular_formula"]
    synonyms = compound["synonyms"]
    inchi = compound["inchi"]
    inchikey = compound["inchikey"]

class Compound:
    @classmethod
    def from_cid(cls, cid):
        if isinstance(cid, list):
            cid = cid[0]
        assert int(cid) == int(compound["cid"])
        return FakeCompound()

pubchempy.Compound = Compound
pubchempy.get_cids = lambda name, namespace: [compound["cid"]]
sys.modules["pubchempy"] = pubchempy
sys.path.insert(0, sys.argv[2])
from functions.function_metabolite_identification import identify_metabolite

result = identify_metabolite(
    case["name"],
    case["formula"],
    case["identifier"],
    threshold=case["threshold"],
)
print(result or "", end="")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, json.dumps(case), str(source_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


@pytest.mark.legacy_parity
def test_metabolite_identification_matches_recorded_legacy_snapshot():
    legacy_root = os.environ.get("THG_LEGACY_CHECKOUT")
    if not legacy_root:
        pytest.skip("set THG_LEGACY_CHECKOUT to enable legacy parity")

    case = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="thg-legacy-metabolite-") as temp_dir:
        source_root = Path(temp_dir)
        _extract_legacy_modules(legacy_root, source_root)
        maintained = _run_maintained(case)
        legacy = _run_legacy(source_root, case)

    assert maintained == case["expected"]
    assert legacy == case["expected"]
    assert maintained == legacy
