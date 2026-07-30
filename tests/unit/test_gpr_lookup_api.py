from thg_protocol.gpr.lookup import get_gpr, parse_gene_pairs
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.kegg import StaticKeggClient


def test_parse_gene_pairs_and_static_lookup() -> None:
    page = "<b>Gene:</b> GENE1 ENSG000001<br>"
    assert parse_gene_pairs(page) == [("GENE1", "ENSG000001")]
    client = StaticBioCycClient(ec_pages={("HUMAN", "1.2.3.4"): page})
    result = get_gpr("1.2.3.4", biocyc_client=client, kegg_client=StaticKeggClient())
    assert result[0] == ["GENE1"]
    assert "GENE1" in result[-1]


def test_empty_static_lookup_is_offline() -> None:
    assert get_gpr(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
    ) == ([], "", "", "", "")
