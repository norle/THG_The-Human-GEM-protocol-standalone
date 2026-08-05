import json
import pickle

import cobra

from thg_protocol.database import (
    GeneRecord,
    MetaboliteRecord,
    ReactionRecord,
    reconstruct_model,
    reconstruct_model_from_json,
    reconstruct_model_from_pickle,
    reconstruct_model_with_services,
    summarize_biocyc_compartments,
)
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.kegg import StaticKeggClient


class _LegacyReactionWithSerializedFields:
    ID = "R1_c"
    Name = "A to B"
    GPR = ["", ""]
    EC = []
    subs = [[1, "A", "A"]]
    prods = [[1, "B", "B"]]

    def Substrate(self):
        raise NameError("generation-time global is unavailable")

    def Product(self):
        raise NameError("generation-time global is unavailable")


class _LegacyCompoundWithCallableId:
    Subcel = "c"

    def __init__(self, identifier):
        self.identifier = identifier

    def ID2(self):
        return self.identifier


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


def test_reconstruct_model_from_legacy_pickle_bundle(tmp_path):
    records = {
        "id": "/tmp/models/pickle-toy.xml",
        "name": "Pickle toy",
        "loc": {"cytosol": "c"},
        "mets_cl": {
            "A": {
                "ID2": "A",
                "Subcel": "cytosol",
                "Name": "A",
                "Formula1": "C1",
            },
            "B": {
                "ID2": "B",
                "Subcel": "cytosol",
                "Name": "B",
                "Formula1": "C1",
            },
        },
        "reactions_cl": {
            "R1_c": {
                "ID": "R1_c",
                "Name": "A to B",
                "subs": [[1, "A", "A"]],
                "prods": [[1, "B", "B"], [1, "missing", "missing"]],
                "GPR": ["gpr", "GENE1"],
                "EC": ["1.1.1.1"],
            }
        },
        "genes": {"GENE1": {"Name": "Gene one", "Entrez": "1"}},
        "pathways": {"toy pathway": "R1"},
    }
    records_path = tmp_path / "records.pkl"
    output = tmp_path / "out" / "model.json"
    with records_path.open("wb") as handle:
        pickle.dump(records, handle)

    model = reconstruct_model_from_pickle(records_path, output_path=output)

    assert model.id == "pickle-toy"
    assert model.reactions.R1_c.metabolites[model.metabolites.A_c] == -1
    assert model.reactions.R1_c.gene_reaction_rule == "GENE1"
    assert model.reactions.R1_c.annotation["pathway"] == ["toy pathway"]
    assert model.metabolites.missing_c.compartment == "c"
    assert model.groups.get_by_id("toy pathway").members == [model.reactions.R1_c]
    assert output.exists()


def test_reconstruct_model_from_pickle_prefers_serialized_compounds(tmp_path):
    records = {
        "id": "serialized-fields.xml",
        "mets_cl": {
            "A": _LegacyCompoundWithCallableId("A"),
            "B": _LegacyCompoundWithCallableId("B"),
        },
        "reactions_cl": {"R1_c": _LegacyReactionWithSerializedFields()},
    }
    records_path = tmp_path / "serialized-fields.pkl"
    with records_path.open("wb") as handle:
        pickle.dump(records, handle)

    model = reconstruct_model_from_pickle(records_path)

    assert model.reactions.R1_c.metabolites[model.metabolites.A_c] == -1
    assert model.reactions.R1_c.metabolites[model.metabolites.B_c] == 1


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


def test_summarize_biocyc_compartments_is_explicit_and_deterministic():
    summary = summarize_biocyc_compartments(
        {
            "P1": [
                {"orgid": "HUMAN", "frameid": "CCO-CYTOSOL"},
                {"orgid": "HUMAN", "frameid": "CCO-MITO"},
            ],
            "P2": [{"orgid": "OTHER", "frameid": "CCO-CYTOSOL"}],
            "invalid": "ignored",
        },
        {"HUMAN:CCO-CYTOSOL": "cytosol"},
        sample_size=1,
    )

    assert summary.entry_count == 3
    assert summary.frameid_count == 3
    assert summary.resolved_count == 3
    assert summary.resolved["HUMAN:CCO-MITO"] == "CCO-MITO"
    assert summary.unique_names == ("CCO-CYTOSOL", "CCO-MITO", "cytosol")
    assert len(summary.sample) == 1


def test_summarize_biocyc_compartments_zero_sample_size_returns_no_samples():
    summary = summarize_biocyc_compartments(
        {"P1": [{"frameid": "CCO-CYTOSOL"}]}, {}, sample_size=0
    )

    assert summary.sample == ()
