"""Opt-in characterization of the archived BioCyc GPR fixture."""

import os
import re
from pathlib import Path

import pandas as pd
import pytest

from thg_protocol.config import load_environment_files
from thg_protocol.gpr.lookup import get_gpr
from thg_protocol.services.biocyc import BioCycClient

load_environment_files()

pytestmark = [pytest.mark.online, pytest.mark.slow]

if not os.environ.get("BIOCYC_EMAIL") or not os.environ.get("BIOCYC_PASSWORD"):
    pytest.skip(
        "BioCyc credentials are required for the archived online GPR fixture",
        allow_module_level=True,
    )


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures/legacy_characterization/gpr_prediction/files"
)
_rows = []
for fixture in sorted(FIXTURE_ROOT.glob("gprs_ec*.tsv")):
    values = pd.read_csv(fixture, sep="\t")
    _rows.extend(values.itertuples(index=False, name=None))

# Keep the online gate representative and bounded; the complete fixture remains
# available under the maintained test-fixture owner for deliberate full runs.
GPR_FIXTURES = _rows[:10]


@pytest.fixture(scope="module")
def biocyc_session():
    return BioCycClient()


@pytest.mark.parametrize("ec_number,expected", GPR_FIXTURES)
def test_gpr_fixture_uses_maintained_package_api(
    biocyc_session, ec_number: str, expected: str
):
    result = get_gpr(ec_number, biocyc_session)
    assert result is not None
    _, _, _, _, gpr = result
    for expected_gene in re.split("and|or", expected):
        assert expected_gene.strip().replace("(", "").replace(")", "") in gpr
