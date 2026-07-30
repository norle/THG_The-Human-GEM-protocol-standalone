"""Opt-in characterization of the archived BioCyc GPR fixture."""

import os
import re
from pathlib import Path

import pandas as pd
import pytest
from functions.gpr.auth_gpr import getGPR, setup_biocyc_session

pytestmark = [pytest.mark.online, pytest.mark.slow]

if not os.environ.get("BIOCYC_EMAIL") or not os.environ.get("BIOCYC_PASSWORD"):
    pytest.skip(
        "BioCyc credentials are required for the archived online GPR fixture",
        allow_module_level=True,
    )


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "test_algorithms/gpr_prediction/files"
)
_rows = []
for fixture in sorted(FIXTURE_ROOT.glob("gprs_ec*.tsv")):
    values = pd.read_csv(fixture, sep="\t")
    _rows.extend(values.itertuples(index=False, name=None))

# Keep the online gate representative and bounded; the complete historical
# fixture remains available in test_algorithms for a deliberate full run.
GPR_FIXTURES = _rows[:10]


@pytest.fixture(scope="module")
def biocyc_session():
    return setup_biocyc_session()


@pytest.mark.parametrize("ec_number,expected", GPR_FIXTURES)
def test_archived_gpr_fixture_uses_maintained_compatibility_api(
    biocyc_session, ec_number: str, expected: str
):
    result = getGPR(ec_number, biocyc_session)
    assert result is not None
    _, _, _, _, gpr = result
    for expected_gene in re.split("and|or", expected):
        assert expected_gene.strip().replace("(", "").replace(")", "") in gpr
