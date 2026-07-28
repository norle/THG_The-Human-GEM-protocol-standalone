from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient


def test_static_ensembl_client_normalizes_and_omits_unknown_identifiers():
    client = StaticEnsemblClient(
        {
            "TP53": {
                "ensembl": "ENSG00000141510",
                "display_name": "TP53",
                "entrez": ["7157"],
                "uniprot": ["P04637"],
            }
        }
    )

    annotations = client.annotate(["TP53", "missing"])

    assert annotations == {
        "TP53": EnsemblAnnotation(
            ensembl="ENSG00000141510",
            display_name="TP53",
            entrez=("7157",),
            uniprot=("P04637",),
        )
    }
    assert annotations["TP53"].as_dict()["entrez"] == ["7157"]
