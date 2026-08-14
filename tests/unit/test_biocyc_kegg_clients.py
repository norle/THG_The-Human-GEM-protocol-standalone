from thg_protocol.gpr.location import resolve_locations
from thg_protocol.gpr.lookup import get_gpr
from thg_protocol.model_build.mass_balance import reformulate_glycan_equation
from thg_protocol.services.biocyc import BioCycClient, StaticBioCycClient
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.kegg import KeggClient, StaticKeggClient
from thg_protocol.services.location import StaticLocationClient


def test_static_biocyc_client_returns_configured_ec_and_page_responses():
    client = StaticBioCycClient(
        ec_pages={("HUMAN", "1.2.3.4"): "human EC page"},
        pages={"https://example.test/gene": "gene page"},
    )

    assert client.get_ec_html("1.2.3.4", "HUMAN") == "human EC page"
    assert client.get_page("https://example.test/gene") == "gene page"
    assert client.get_ec_html("missing") == ""


def test_biocyc_client_logs_in_before_authenticated_requests():
    class Response:
        text = "<html>page</html>"

        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True}

    class Session:
        def __init__(self):
            self.calls = []

        def post(self, url, timeout, data):
            self.calls.append(("post", url, timeout, data))
            return Response()

        def get(self, url, timeout):
            self.calls.append(("get", url, timeout))
            return Response()

    session = Session()
    client = BioCycClient(
        session=session,
        retries=0,
        email="user@example.com",
        password="secret",
    )
    assert client.get_ec_html("1.2.3.4", "HUMAN") == "<html>page</html>"
    assert session.calls[0][0:2] == ("post", "https://websvc.biocyc.org/ajax-login")
    assert session.calls[1][0] == "get"


def test_package_gpr_lookup_uses_injected_biocyc_pages():
    client = StaticBioCycClient(
        ec_pages={("HUMAN", "1.2.3.4"): "<b>Gene:</b> GENE1 ENSG000001<br>"}
    )

    result = get_gpr("1.2.3.4", biocyc_client=client)

    assert result[0] == ["GENE1"]
    assert result[2] == "ENSG000001"
    assert result[-1] == "(GENE1)"


def test_static_kegg_client_returns_configured_link_responses():
    client = StaticKeggClient(
        ec_pages={"1.2.3.4": "EC page"},
        ec_to_ko={"1.2.3.4": "ec:1.2.3.4\tko:K00001\n"},
        ko_to_genes={("ko:K00001",): "ko:K00001\thsa:1234\n"},
    )

    assert client.get_ec_html("1.2.3.4") == "EC page"
    assert client.link_ec_to_ko("1.2.3.4").endswith("K00001\n")
    assert client.link_ko_to_genes(["ko:K00001"]).endswith("hsa:1234\n")


def test_static_kegg_client_returns_reaction_entries():
    client = StaticKeggClient(
        reaction_entries={"R00001": "ENTRY       R00001\nNAME        example\n"}
    )

    assert client.get_reaction_entries(["R00001", "R99999"]) == {
        "R00001": "ENTRY       R00001\nNAME        example\n"
    }


def test_static_kegg_client_supports_database_pages_and_batches():
    client = StaticKeggClient(
        pages={"https://rest.kegg.jp/get/hsa00001/kgml": "<pathway />"},
        entries={"C00001": "ENTRY       C00001\nNAME        water\n"},
    )

    assert client.get_page("https://rest.kegg.jp/get/hsa00001/kgml") == "<pathway />"
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


def test_kegg_reaction_batches_never_exceed_ten_identifiers():
    class Response:
        text = "".join(
            f"ENTRY       R{identifier:05d}\nNAME        example\n///\n"
            for identifier in range(1, 12)
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
    identifiers = [f"R{identifier:05d}" for identifier in range(1, 12)]

    assert (
        sorted(client.get_reaction_entries(identifiers, batch_size=50)) == identifiers
    )
    assert len(session.calls) == 2
    assert all(call[0].count("rn:") <= 10 for call in session.calls)


def test_kegg_database_batch_uses_database_prefix():
    class Response:
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


def test_static_location_client_and_package_location_resolution():
    client = StaticLocationClient(
        pages={
            "https://www.uniprot.org/uniprotkb/P12345_HUMAN.txt": (
                "SUBCELLULAR LOCATION: Mitochondria."
            )
        }
    )

    assert client.get_page("https://example.test/missing") == ""
    rules = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["P12345"],
        allowed_locations={"Mitochondria", "Cytosol"},
        location_client=client,
    )
    assert rules[1] == {"Mitochondria": "(GENE1)"}


def test_static_ensembl_client_is_used_by_package_model_builders():
    client = StaticEnsemblClient(annotations={"GENE1": EnsemblAnnotation("ENSG000001")})

    assert client.annotate(["GENE1"])["GENE1"].ensembl == "ENSG000001"


def test_package_glycan_reformulation_uses_static_kegg_client():
    client = StaticKeggClient(
        pages={
            "https://www.genome.jp/dbget-bin/www_bget?gl:G00001": "C00001",
            "https://www.genome.jp/entry/C00001": "C00001H2O",
        }
    )

    assert (
        reformulate_glycan_equation("G00001 -> G00001", client=client)
        == "A1B2C1 -> A1B2C1"
    )


def test_package_gpr_lookup_accepts_offline_service_clients():
    assert get_gpr(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
    ) == ([], "", "", "", "")
