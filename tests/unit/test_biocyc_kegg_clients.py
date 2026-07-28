from functions.gpr.gpr_def import getGPR
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.kegg import KeggClient, StaticKeggClient


def test_static_biocyc_client_returns_configured_ec_and_page_responses():
    client = StaticBioCycClient(
        ec_pages={("HUMAN", "1.2.3.4"): "human EC page"},
        pages={"https://example.test/gene": "gene page"},
    )

    assert client.get_ec_html("1.2.3.4", "HUMAN") == "human EC page"
    assert client.get_page("https://example.test/gene") == "gene page"
    assert client.get_ec_html("missing") == ""


def test_static_kegg_client_returns_configured_link_responses():
    client = StaticKeggClient(
        ec_pages={"1.2.3.4": "EC page"},
        ec_to_ko={"1.2.3.4": "ec:1.2.3.4\tko:K00001\n"},
        ko_to_genes={("ko:K00001",): "ko:K00001\thsa:1234\n"},
    )

    assert client.get_ec_html("1.2.3.4") == "EC page"
    assert client.link_ec_to_ko("1.2.3.4").endswith("K00001\n")
    assert client.link_ko_to_genes(["ko:K00001"]).endswith("hsa:1234\n")


def test_static_kegg_client_returns_configured_reaction_entries():
    client = StaticKeggClient(
        reaction_entries={
            "R00001": "ENTRY       R00001\nNAME        example\n",
        }
    )

    assert client.get_reaction_entries(["R00001", "R99999"]) == {
        "R00001": "ENTRY       R00001\nNAME        example\n"
    }


def test_static_kegg_client_supports_database_builder_pages_and_batches():
    client = StaticKeggClient(
        pages={"https://rest.kegg.jp/get/hsa00001/kgml": "<pathway />"},
        entries={"C00001": "ENTRY       C00001\nNAME        water\n"},
    )

    assert (
        client.get_page("https://rest.kegg.jp/get/hsa00001/kgml") == "<pathway />"
    )
    assert client.get_entries(["C00001", "C99999"], database="compound") == {
        "C00001": "ENTRY       C00001\nNAME        water\n"
    }


def test_kegg_reaction_batch_is_parsed_and_cached():
    class Response:
        status_code = 200
        text = (
            "ENTRY       R00001\nNAME        first\n"
            "\nENTRY       R00002\nNAME        second\n"
        )

        def raise_for_status(self):
            return None

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, timeout):
            self.calls.append((url, timeout))
            return Response()

    session = Session()
    client = KeggClient(session=session, retries=0)

    first = client.get_reaction_entries(
        ["R00001", "R00002"], batch_size=2, requests_per_second=1000
    )
    second = client.get_reaction_entries(
        ["R00001", "R00002"], batch_size=2, requests_per_second=1000
    )

    assert sorted(first) == ["R00001", "R00002"]
    assert second == first
    assert len(session.calls) == 1


def test_kegg_database_batch_uses_database_prefix():
    class Response:
        status_code = 200
        text = "ENTRY       C00001\nNAME        water\n///\n"

        def raise_for_status(self):
            return None

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, timeout):
            self.calls.append((url, timeout))
            return Response()

    session = Session()
    client = KeggClient(session=session, retries=0)

    assert client.get_entries(["C00001"], database="compound") == {
        "C00001": "ENTRY       C00001\nNAME        water\n"
    }
    assert session.calls[0][0] == "https://rest.kegg.jp/get/cpd:C00001"


def test_legacy_gpr_lookup_accepts_offline_service_clients():
    result = getGPR(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
    )

    assert result == ([], "", "", "", "")
