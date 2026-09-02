import gzip
import hashlib

from thg_protocol.curation.go import parse_obo, resolve_go_compartment
from thg_protocol.services import biocyc, goa, reactome, rhea, uniprot
from thg_protocol.services.goa import parse_gaf
from thg_protocol.services.reactome import catalyst_candidate_gpr
from thg_protocol.services.uniprot import StaticUniProtClient


def test_go_resolution_uses_only_is_a_and_part_of_and_preserves_path():
    graph = parse_obo(
        """
[Term]
id: GO:0005743
name: mitochondrial inner membrane
relationship: part_of GO:0005739 ! mitochondrion

[Term]
id: GO:0005739
name: mitochondrion
"""
    )
    result = resolve_go_compartment(
        "mitochondrial inner membrane",
        None,
        graph,
        {"x": "GO:0005739"},
        {"x": "Mitochondria"},
    )
    assert result["target_compartment_id"] == "x"
    assert result["resolution_path"][1]["relation"] == "part_of"


def test_go_resolution_rejects_equal_distance_targets():
    graph = parse_obo(
        """
[Term]
id: GO:0000001
name: ambiguous location
is_a: GO:0000002
is_a: GO:0000003

[Term]
id: GO:0000002
name: first

[Term]
id: GO:0000003
name: second
"""
    )
    result = resolve_go_compartment(
        "ambiguous location",
        None,
        graph,
        {"a": "GO:0000002", "b": "GO:0000003"},
    )
    assert result["reason"] == "ambiguous-compartment-resolution"


def test_goa_parser_keeps_cellular_component_evidence_and_drops_negation():
    row = "\t".join(
        [
            "UniProt",
            "P1",
            "GENE1",
            "",
            "GO:0005739",
            "PMID:1",
            "IDA",
            "",
            "C",
            "",
            "",
            "",
            "",
            "",
            "UniProt",
        ]
    )
    negated = row.replace("\tGENE1\t\tGO", "\tGENE2\tNOT\tGO")
    result = parse_gaf(row + "\n" + negated)
    assert len(result) == 1
    assert result[0].symbol == "GENE1"
    assert result[0].go_id == "GO:0005739"


def test_reactome_only_emits_and_for_an_explicit_complex():
    assert (
        catalyst_candidate_gpr(
            {
                "catalyst": {
                    "type": "complex",
                    "members": [{"gene": "A"}, {"gene": "B"}],
                }
            }
        )
        == "(A) and (B)"
    )
    assert (
        catalyst_candidate_gpr(
            {
                "catalyst": {
                    "type": "entity-set",
                    "members": [{"gene": "A"}, {"gene": "B"}],
                }
            }
        )
        == "(A) or (B)"
    )
    assert (
        catalyst_candidate_gpr(
            {"catalyst": {"type": "unknown", "members": [{"gene": "A"}]}}
        )
        == ""
    )


def test_reactome_search_uses_content_service_endpoint_for_numeric_rhea_ids(
    monkeypatch,
):
    calls = []

    class Response:
        content = b'{"results": [{"entries": [{"stId": "R-HSA-1"}]}]}'

        def json(self):
            return {"results": [{"entries": [{"stId": "R-HSA-1"}]}]}

    def fake_request(_session, _method, url, **_kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(reactome, "request", fake_request)

    result = reactome.ReactomeClient(session=object()).reactions_for_rhea("34019")

    assert result == [{"stId": "R-HSA-1"}]
    assert calls == [
        "https://reactome.org/ContentService/search/query?query=RHEA%3A34019&types=Reaction"
    ]


def test_reactome_search_treats_no_match_as_empty(monkeypatch):
    class Error(Exception):
        response = type("Response", (), {"status_code": 404})()

    def fake_request(_session, _method, _url, **_kwargs):
        raise Error("not found")

    monkeypatch.setattr(reactome, "request", fake_request)

    assert reactome.ReactomeClient(session=object()).reactions_for_rhea("34019") == []


def test_reactome_search_skips_unavailable_requests(monkeypatch):
    class Error(Exception):
        response = type("Response", (), {"status_code": 521})()

    def fake_request(_session, _method, _url, **_kwargs):
        raise Error("unavailable")

    monkeypatch.setattr(reactome, "request", fake_request)

    client = reactome.ReactomeClient(session=object())
    assert client.reactions_for_rhea("34019") == []
    assert client.failed_requests == 1


def test_rhea_search_skips_invalid_json(monkeypatch):
    def fake_request(_session, _method, _url, **_kwargs):
        raise ValueError("empty response")

    monkeypatch.setattr(rhea, "request", fake_request)

    client = rhea.RheaClient(session=object())
    assert client.reactions_for_ec("1.1.1.1") == []
    assert client.failed_requests == 1


def test_uniprot_search_deduplicates_and_batches_identifiers(monkeypatch):
    calls = []

    class Response:
        content = b'{"results": []}'

        def json(self):
            return {"results": []}

    def fake_request(_session, _method, _url, **kwargs):
        calls.append(kwargs["params"]["query"])
        return Response()

    monkeypatch.setattr(uniprot, "request", fake_request)

    identifiers = [f"GENE{index}" for index in range(101)] + ["GENE0"]
    assert uniprot.UniProtClient(session=object()).annotations_for(identifiers) == []
    assert [query.count("gene:") for query in calls] == [100, 1]
    assert " OR " in calls[0]
    assert calls[0].split(" OR ").count("gene:GENE0") == 1


def test_uniprot_search_uses_cross_references_for_ensembl_identifiers(monkeypatch):
    class Response:
        content = b'{"results": []}'

        def json(self):
            return {"results": []}

    calls = []

    def fake_request(_session, _method, _url, **kwargs):
        calls.append(kwargs["params"]["query"])
        return Response()

    monkeypatch.setattr(uniprot, "request", fake_request)

    uniprot.UniProtClient(session=object()).annotations_for(
        ["ENSG00000000419", "DPM1"]
    )

    assert calls == ["gene:DPM1 OR xref:ensembl-ENSG00000000419"]


def test_uniprot_search_preserves_matched_ensembl_gene_identifier(monkeypatch):
    class Response:
        content = b'{"results": []}'

        def json(self):
            return {
                "results": [
                    {
                        "primaryAccession": "Q5QPJ9",
                        "genes": [{"geneName": {"value": "DPM1"}}],
                        "uniProtKBCrossReferences": [
                            {
                                "database": "Ensembl",
                                "id": "ENST00000413082.1",
                                "properties": [
                                    {
                                        "key": "GeneId",
                                        "value": "ENSG00000000419.15",
                                    }
                                ],
                            }
                        ],
                        "comments": [
                            {
                                "commentType": "SUBCELLULAR LOCATION",
                                "subcellularLocations": [
                                    {
                                        "location": {
                                            "value": "Cytoplasm",
                                            "id": "SL-0086",
                                        }
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr(uniprot, "request", lambda *_args, **_kwargs: Response())

    annotations = uniprot.UniProtClient(session=object()).annotations_for(
        ["ENSG00000000419"]
    )
    assert [item.gene_id for item in annotations] == ["ENSG00000000419"]
    assert StaticUniProtClient(annotations).annotations_for(["ENSG00000000419"])


def test_uniprot_sl_to_go_mapping_is_location_specific():
    result = StaticUniProtClient(
        [
            {
                "gene": "GENE1",
                "location": "mitochondrion",
                "sl_id": "SL-001",
                "sl_to_go": {
                    "SL-001": ["GO:0005739"],
                    "SL-002": ["GO:0005829"],
                },
            }
        ]
    ).annotations_for(["GENE1"])
    assert [(item.sl_id, item.go_id) for item in result] == [
        ("SL-001", "GO:0005739")
    ]


def test_live_provider_metadata_records_release_and_raw_checksum(monkeypatch):
    gaf = "!gaf-version: 2.2\n" + "\t".join(
        [
            "UniProt",
            "P1",
            "GENE1",
            "",
            "GO:0005739",
            "PMID:1",
            "IDA",
            "",
            "C",
            "",
            "",
            "",
            "",
            "",
            "GOA",
        ]
    )

    class Response:
        def __init__(self, content, payload=None):
            self.content = content
            self.text = content.decode(errors="replace")
            self._payload = payload

        def json(self):
            return self._payload

    def fake_request(_session, _method, url, **_kwargs):
        if "goa" in url:
            return Response(gzip.compress(gaf.encode(), mtime=0))
        if "uniprot" in url:
            return Response(b'{"results": []}', {"results": []})
        if "rhea" in url:
            return Response(b"[]", [])
        if "reactome" in url:
            return Response(b'{"results": []}', {"results": []})
        return Response(b"<html/>")

    for module in (biocyc, goa, reactome, rhea, uniprot):
        monkeypatch.setattr(module, "request", fake_request)

    clients = (
        (goa.GOAClient(session=object(), release="goa-1"), "goa"),
        (uniprot.UniProtClient(session=object(), release="uniprot-1"), "uniprot"),
        (rhea.RheaClient(session=object(), release="rhea-1"), "rhea"),
        (reactome.ReactomeClient(session=object(), release="reactome-1"), "reactome"),
        (
            biocyc.BioCycClient(
                session=object(), email="", password="", release="biocyc-1"
            ),
            "biocyc",
        ),
    )
    clients[0][0].annotations_for(["GENE1"])
    clients[1][0].annotations_for(["GENE1"])
    clients[2][0].reactions_for_ec("1.1.1.1")
    clients[3][0].reactions_for_rhea("RHEA:1")
    clients[4][0].get_ec_html("1.1.1.1")

    for client, source in clients:
        metadata = client.metadata
        assert metadata["source"].lower() == source
        assert metadata["release"] == f"{source}-1"
        assert metadata["raw_response_sha256"] == hashlib.sha256(
            client_metadata_payload(source)
        ).hexdigest()


def client_metadata_payload(source):
    return {
        "goa": gzip.compress(
            ("!gaf-version: 2.2\n" + "\t".join(
                [
                    "UniProt",
                    "P1",
                    "GENE1",
                    "",
                    "GO:0005739",
                    "PMID:1",
                    "IDA",
                    "",
                    "C",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "GOA",
                ]
            )
        ).encode(),
            mtime=0,
        ),
        "uniprot": b'{"results": []}',
        "rhea": b"[]",
        "reactome": b'{"results": []}',
        "biocyc": b"<html/>",
    }[source]
