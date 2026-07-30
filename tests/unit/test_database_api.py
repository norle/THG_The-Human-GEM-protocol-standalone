import json

import cobra

from thg_protocol.database import (
    GeneRecord,
    MetaboliteRecord,
    ReactionRecord,
    reconstruct_model,
    reconstruct_model_from_json,
    reconstruct_model_with_services,
)
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.kegg import StaticKeggClient


def test_reconstruct_model_builds_annotated_toy_model_and_writes_json(tmp_path):
    output = tmp_path / "nested" / "model.json"
    model = reconstruct_model(
        "toy",
        [
            MetaboliteRecord(
                "a_c",
                compartment="c",
                name="A",
                formula="C1",
                annotation={"kegg.compound": "C00001"},
            ),
            MetaboliteRecord("b_c", compartment="c", name="B", formula="C1"),
        ],
        [
            ReactionRecord(
                "R1",
                {"a_c": -1, "b_c": 1},
                name="A to B",
                gene_reaction_rule="G1",
                annotation={"ec-code": "1.1.1.1"},
            )
        ],
        [GeneRecord("G1", name="gene one", annotation={"ensembl": "ENSG1"})],
        pathways={"glycolysis": ["R1"]},
        output_path=output,
    )

    assert isinstance(model, cobra.Model)
    assert model.reactions.R1.gene_reaction_rule == "G1"
    assert model.reactions.R1.annotation["pathway"] == ["glycolysis"]
    assert model.metabolites.a_c.annotation["kegg.compound"] == "C00001"
    assert output.exists()


def test_reconstruct_model_rejects_unknown_reaction_metabolites():
    try:
        reconstruct_model("toy", [], [ReactionRecord("R1", {"missing_c": -1})])
    except KeyError as error:
        assert "missing_c" in str(error)
    else:
        raise AssertionError("unknown metabolite reference should fail")


def test_reconstruct_model_from_json_uses_explicit_output_path(tmp_path):
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps(
            {
                "model_id": "json-toy",
                "metabolites": [{"id": "a_c", "formula": "C1"}],
                "reactions": [
                    {"id": "R1", "stoichiometry": {"a_c": -1}}
                ],
            }
        )
    )
    output = tmp_path / "outputs" / "model.json"

    model = reconstruct_model_from_json(records, output_path=output)

    assert model.id == "json-toy"
    assert output.exists()


def test_reconstruct_model_with_services_enriches_records_offline(tmp_path):
    output = tmp_path / "service-toy.xml"
    model = reconstruct_model_with_services(
        "service-toy",
        [MetaboliteRecord("a_c", formula="C1")],
        [
            ReactionRecord(
                "R1",
                {"a_c": -1},
                annotation={"kegg.reaction": "R00001", "ec-code": "1.1.1.1"},
            )
        ],
        [GeneRecord("GENE1")],
        output_path=output,
        kegg_client=StaticKeggClient(reaction_entries={"R00001": "ENTRY R00001"}),
        biocyc_client=StaticBioCycClient(
            ec_pages={("META", "1.1.1.1"): "EC page"}
        ),
        ensembl_client=StaticEnsemblClient(
            annotations={"GENE1": EnsemblAnnotation("ENSG0001")}
        ),
    )

    assert json.loads(model.reactions.R1.annotation["kegg.reaction.entry"]) == {
        "R00001": "ENTRY R00001"
    }
    assert json.loads(model.reactions.R1.annotation["biocyc.ec.html"]) == {
        "1.1.1.1": "EC page"
    }
    assert model.genes.GENE1.annotation["ensembl"] == "ENSG0001"
    assert output.exists()
