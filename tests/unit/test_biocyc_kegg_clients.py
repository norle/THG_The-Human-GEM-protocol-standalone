from functions.gpr.gpr_def import getGPR
from functions.equations_bm_gdb import Glycan, MissingAtom, Reformulation

from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import StaticEnsemblClient
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


def test_legacy_auth_gpr_uses_injected_biocyc_pages():
    from functions.gpr.auth_gpr import get_ecnumber_biocyc_html, get_html

    client = StaticBioCycClient(
        ec_pages={("HUMAN", "1.2.3.4"): "EC page"},
        pages={"https://example.test/gene": "gene page"},
    )

    assert (
        get_ecnumber_biocyc_html(
            "1.2.3.4", org="HUMAN", biocyc_client=client
        )
        == "EC page"
    )
    assert get_html("https://example.test/gene", biocyc_client=client) == "gene page"


def test_legacy_gene_modifier_uses_injected_ensembl_page_client():
    from functions.pattern_generate_database import DefMod

    class Gene:
        def Name(self):
            return "GENE1"

        def Entrez(self):
            return "1234"

        def Ensg(self):
            return "ENSG000001"

    client = StaticLocationClient(
        pages={
            "https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=ENSG000001":
                "ENST000001 ENSP000002"
        }
    )

    output = DefMod(Gene(), location_client=client)

    assert "ENST000001" in output
    assert "ENSP000002" in output


def test_legacy_html_helpers_use_injected_page_client_and_preserve_bytes():
    from functions.function_bm_gdb import getHtml, getHtmlS

    client = StaticLocationClient(pages={"https://example.test": "page"})

    assert getHtml("https://example.test", 1, page_client=client) == b"page"
    assert getHtmlS("https://example.test", 1, page_client=client) == b"page"


def test_legacy_html_upload_uses_injected_page_client(tmp_path):
    from functions.function_bm_gdb import getHtml

    upload = tmp_path / "upload.txt"
    upload.write_text("payload")
    client = StaticLocationClient(uploads={"https://example.test/upload": "result"})

    assert getHtml(
        "https://example.test/upload",
        1,
        file_data=("file", str(upload)),
        page_client=client,
    ) == b"result"


def test_static_kegg_client_returns_configured_link_responses():
    client = StaticKeggClient(
        ec_pages={"1.2.3.4": "EC page"},
        ec_to_ko={"1.2.3.4": "ec:1.2.3.4\tko:K00001\n"},
        ko_to_genes={("ko:K00001",): "ko:K00001\thsa:1234\n"},
    )

    assert client.get_ec_html("1.2.3.4") == "EC page"
    assert client.link_ec_to_ko("1.2.3.4").endswith("K00001\n")
    assert client.link_ko_to_genes(["ko:K00001"]).endswith("hsa:1234\n")


def test_legacy_auth_gpr_kegg_fallback_uses_injected_client():
    from functions.gpr.auth_gpr import _fetch_kegg_from_ec_html

    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/link/hsa/ec:1.2.3.4":
                "ec:1.2.3.4\thsa:1234\n"
        }
    )

    result = _fetch_kegg_from_ec_html("1.2.3.4", kegg_client=client)

    assert result[0] == ["1234"]
    assert result[1] == ["G1234"]


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


def test_legacy_pathway_fallback_uses_injected_kegg_page_client():
    from functions.function_bm_gdb import getLinkPath

    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/get/hsa00190": (
                "ENTRY       hsa00190\n"
                "REACTION     R00001 R00002\n"
            )
        }
    )

    _, reaction_links = getLinkPath(
        '<pathway name="path:hsa00190"></pathway>', kegg_client=client
    )

    assert {item[0][0] for item in reaction_links} == {"R00001", "R00002"}


def test_legacy_compound_primary_fallback_uses_injected_kegg_page_client(
    tmp_path, monkeypatch
):
    from collections import defaultdict

    import functions.function_bm_gdb as legacy_database

    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/get/C00001": (
                "ENTRY       C00001\n"
                "NAME        water;\n"
                "FORMULA     H2O\n"
            )
        }
    )
    monkeypatch.setattr(legacy_database, "recondict", lambda: defaultdict(list))

    result = legacy_database.getCompParamFromRestAPI(
        (
            "ENTRY       G00001\n"
            "NAME        glycan;\n"
            "FORMULA     C6H12O6\n"
            "REMARK      Same as: C00001\n"
        ),
        "G00001",
        0,
        [],
        str(tmp_path / "special-compounds"),
        "",
        kegg_client=client,
    )

    assert result[3] == ["water"]
    assert result[1] == [("H2O", "C6H12O6")]


def test_legacy_gpr_definition_html_uses_injected_biocyc_page_client():
    from functions.gpr.gpr_def import get_html

    client = StaticBioCycClient(pages={"https://example.test/page": "BioCyc page"})

    assert get_html("https://example.test/page", biocyc_client=client) == "BioCyc page"


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
            f"ENTRY       R{identifier:05d}\\nNAME        example\\n///\\n"
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

    assert sorted(client.get_reaction_entries(identifiers, batch_size=50)) == identifiers
    assert len(session.calls) == 2
    assert all(call[0].count("rn:") <= 10 for call in session.calls)


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


def test_legacy_batch_helper_uses_injected_kegg_boundary():
    from functions.function_bm_gdb import batch_fetch_kegg_entries

    client = StaticKeggClient(
        entries={"C00001": "ENTRY       C00001\nNAME        water\n"}
    )

    assert batch_fetch_kegg_entries(
        ["C00001", "C99999"], client=client
    ) == {"C00001": "ENTRY       C00001\nNAME        water\n"}


def test_legacy_database_gene_uses_injected_ensembl_boundary():
    from functions.class_generate_database import gene

    client = StaticEnsemblClient(annotations={"GENE1": {"ensembl": "ENSG000001"}})

    assert gene("GENE1", "unused", ensembl_client=client).Ensg() == "ENSG000001"


def test_static_location_client_returns_configured_pages_without_network():
    client = StaticLocationClient(pages={"https://example.test/location": "page"})

    assert client.get_page("https://example.test/location") == "page"
    assert client.get_page("https://example.test/missing") == ""


def test_legacy_equation_glycan_lookup_uses_static_kegg_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = StaticKeggClient(
        pages={
            "https://www.genome.jp/dbget-bin/www_bget?gl:G00001": "C00001",
            "https://www.genome.jp/entry/C00001": "C00001H2O",
        }
    )

    atoms = Glycan("G00001", kegg_client=client)

    assert (tmp_path / "Glycans").read_text() == "G00001,C00001,C00001H2O\n"
    assert atoms == [[['C', 1]], [['H', 2]], [['O', 1]]]
    assert Reformulation("G00001 -> G00001", kegg_client=client) == (
        "A1B2C1 -> A1B2C1"
    )


def test_archived_equation_module_import_is_dependency_light():
    import importlib

    module = importlib.import_module("functions.equations_bm_gdb")


def test_equation_wrapper_preserves_missing_atom_alias():
    import importlib

    module = importlib.import_module("functions.equations_bm_gdb")

    assert module.MissingAtom is MissingAtom
    assert module.Reformulation is not None


def test_legacy_mass_balance_glycan_lookup_uses_static_kegg_client(
    tmp_path, monkeypatch
):
    from functions.functions_mass_balance import Glycan

    monkeypatch.chdir(tmp_path)
    client = StaticKeggClient(
        pages={
            "https://www.genome.jp/dbget-bin/www_bget?gl:G00001": "C00001",
            "https://www.genome.jp/entry/C00001": "C00001H2O",
        }
    )

    Glycan("G00001", kegg_client=client)

    assert (tmp_path / "Glycans").read_text() == "G00001,C00001,C00001H2O\n"


def test_legacy_gpr_lookup_accepts_offline_service_clients():
    result = getGPR(
        "1.2.3.4",
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
    )

    assert result == ([], "", "", "", "")
