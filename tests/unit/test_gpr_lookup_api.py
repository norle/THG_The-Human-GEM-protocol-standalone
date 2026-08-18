from pathlib import Path

from thg_protocol.gpr.lookup import get_gpr, get_gpr_evidence, parse_gene_pairs
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.kegg import StaticKeggClient


def test_parse_gene_pairs_and_static_lookup() -> None:
    page = "<b>Gene:</b> GENE1 ENSG000001<br>"
    assert parse_gene_pairs(page) == [("GENE1", "ENSG000001")]
    client = StaticBioCycClient(ec_pages={("HUMAN", "1.2.3.4"): page})
    result = get_gpr("1.2.3.4", biocyc_client=client, kegg_client=StaticKeggClient())
    assert result[0] == ["GENE1"]
    assert "GENE1" in result[-1]


def test_gpr_evidence_records_source_and_parser_metadata() -> None:
    client = StaticBioCycClient(
        ec_pages={("META", "1.2.3.4"): "<b>Gene:</b> GENE1 ENSG000001<br>"}
    )
    evidence = get_gpr_evidence(
        "1.2.3.4", biocyc_client=client, kegg_client=StaticKeggClient()
    )
    assert evidence["source"] == "metacyc"
    assert evidence["gene_identifiers"] == ["ENSG000001"]
    assert evidence["parser_version"]


def test_gpr_evidence_records_biocyc_access_warning_before_kegg_fallback() -> None:
    page = "<title>Subscription Required</title>"
    evidence = get_gpr_evidence(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(
            ec_pages={("HUMAN", "1.2.3.4"): page, ("META", "1.2.3.4"): page}
        ),
        kegg_client=StaticKeggClient(ec_pages={"1.2.3.4": "hsa:1234"}),
    )
    assert evidence["source"] == "kegg"
    assert evidence["warnings"][:2] == [
        "humancyc-access-required:subscription-required",
        "metacyc-access-required:subscription-required",
    ]


def test_empty_static_lookup_is_offline() -> None:
    assert get_gpr(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
    ) == ([], "", "", "", "")


def test_batched_kegg_empty_result_skips_serial_ec_page_fallback() -> None:
    evidence = get_gpr_evidence(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(ec_pages={"1.2.3.4": "hsa:1234"}),
        kegg_genes=[],
    )

    assert evidence["status"] == "unresolved"


def test_parser_ignores_enzyme_tooltip_and_keeps_gene_records() -> None:
    page = (
        Path(__file__).parents[1] / "fixtures/biocyc/ec-enzyme-and-gene.html"
    ).read_text()
    assert parse_gene_pairs(page) == [
        ("GENE1", "GENE1"),
        ("GENE2", "ENSG000002"),
    ]
