import pytest

from thg_protocol.gpr.location import resolve_locations
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.location import StaticLocationClient


def test_location_resolution_uses_static_page_and_compatibility_shape() -> None:
    client = StaticLocationClient(
        pages={
            "https://www.uniprot.org/uniprotkb/G1_HUMAN.txt": "mitochondria"
        }
    )
    result = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["G1"],
        allowed_locations={"Cytosol", "Mitochondria"},
        location_client=client,
    )
    assert result[0] == {"Mitochondria": "(GENE1*1)"}
    assert result[3] == {"G1": ["GENE1"]}


def test_location_resolution_preserves_complex_rules_and_ensembl_mapping():
    location_client = StaticLocationClient(
        pages={
            "https://www.uniprot.org/uniprotkb/G1_HUMAN.txt": "Mitochondria",
            "https://www.uniprot.org/uniprotkb/G2_HUMAN.txt": "Mitochondria",
        }
    )
    ensembl_client = StaticEnsemblClient(
        annotations={
            "GENE1": EnsemblAnnotation("ENSG000001"),
            "GENE2": EnsemblAnnotation("ENSG000002"),
        }
    )

    stoich, plain, ensembl, _ = resolve_locations(
        "GENE1 and GENE2",
        ["GENE1", "GENE2"],
        ["G1", "G2"],
        allowed_locations={"Cytosol", "Mitochondria"},
        location_client=location_client,
        ensembl_client=ensembl_client,
    )

    assert plain == {"Mitochondria": "((GENE1) and (GENE2))"}
    assert stoich == {"Mitochondria": "((GENE1*1) and (GENE2*1))"}
    assert ensembl == {"Mitochondria": "((ENSG000001) and (ENSG000002))"}


def test_location_resolution_does_not_treat_er_substrings_as_er():
    client = StaticLocationClient(
        pages={
            "https://www.uniprot.org/uniprotkb/G1_HUMAN.txt":
            "This protein has a perER-associated motif."
        }
    )

    result = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["G1"],
        allowed_locations={"Cytosol", "Endoplasmic reticulum"},
        location_client=client,
    )

    assert result[:3] == ({}, {}, {})
    assert result[3] == {"G1": ["GENE1"]}


def test_location_resolution_requires_explicit_fallback_for_unmatched_pages():
    client = StaticLocationClient()
    unresolved = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["G1"],
        allowed_locations={"Cytosol", "Nucleus"},
        location_client=client,
    )
    explicit = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["G1"],
        allowed_locations={"Cytosol", "Nucleus"},
        fallback_location="Nucleus",
        location_client=client,
    )

    assert unresolved[:3] == ({}, {}, {})
    assert explicit[1] == {"Nucleus": "(GENE1)"}


def test_location_resolution_rejects_malformed_nonempty_gpr():
    with pytest.raises(ValueError, match="could not be parsed"):
        resolve_locations(
            "GENE1 AND",
            ["GENE1"],
            ["G1"],
            location_client=StaticLocationClient(),
        )
