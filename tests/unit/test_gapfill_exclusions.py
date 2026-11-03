"""Energy and redox cofactors are never proposed as free compartment transports."""

import pytest

from thg_protocol.gapfill.exclusions import (
    DEFAULT_EXCLUDED_METABOLITES,
    is_excluded,
)


def test_default_blocklist_matches_memote_energy_couples():
    consistency = pytest.importorskip("memote.support.consistency")
    couples = consistency.ENERGY_COUPLES
    expected = set(couples) | set(couples.values()) | {"MNXM1", "MNXM15"}
    assert set(DEFAULT_EXCLUDED_METABOLITES) == expected


def test_default_blocklist_covers_the_usual_suspects():
    # ATP/ADP, NADH/NAD+, NADPH/NADP+, FADH2/FAD, and the proton.
    assert {"MNXM3", "MNXM7", "MNXM10", "MNXM8", "MNXM6", "MNXM5", "MNXM1"} <= set(
        DEFAULT_EXCLUDED_METABOLITES
    )


@pytest.mark.parametrize(
    "annotation",
    [
        {"metanetx.chemical": "MNXM3"},
        {"metanetx.chemical": ["MNXM999", "MNXM3"]},
        {"metanetx.chemical": "https://identifiers.org/metanetx.chemical/MNXM3"},
    ],
)
def test_metabolite_is_excluded_by_cross_reference(annotation):
    assert is_excluded("atp_c", "atp", annotation, DEFAULT_EXCLUDED_METABOLITES)


def test_metabolite_is_excluded_by_id_or_base_id():
    assert is_excluded("CUSTOM_c", "CUSTOM", {}, ["CUSTOM_c"])
    assert is_excluded("CUSTOM_e", "CUSTOM", {}, ["CUSTOM"])


def test_unlisted_metabolite_is_allowed():
    assert not is_excluded("glc_c", "glc", {"metanetx.chemical": "MNXM41"}, ["MNXM3"])
    assert not is_excluded("glc_c", "glc", None, ["MNXM3"])
    assert not is_excluded("glc_c", "glc", {"metanetx.chemical": "MNXM41"}, [])
