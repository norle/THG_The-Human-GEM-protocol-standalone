from __future__ import annotations

import json

from cobra import Metabolite, Model, Reaction
from cobra.io import save_json_model

from thg_protocol.workflow.runner import get_status, start


def test_beta2_uses_go_targets_with_arbitrary_model_ids(tmp_path):
    model = Model("go-beta2")
    left = Metabolite("left_c", formula="C", compartment="c")
    right = Metabolite("right_c", formula="C", compartment="c")
    reaction = Reaction("R_GO")
    reaction.add_metabolites({left: -1, right: 1})
    reaction.gene_reaction_rule = "G_A"
    reaction.annotation["ec-code"] = ["1.2.3.4"]
    model.add_reactions([reaction])
    candidate = Reaction("R_RHEA")
    candidate.add_metabolites({left: -1, right: 1})
    candidate.annotation["ec-code"] = ["1.2.3.4"]
    model.add_reactions([candidate])
    source = tmp_path / "beta1.json"
    save_json_model(model, source)
    goa = tmp_path / "goa.gaf"
    goa.write_text(
        "\t".join(
            [
                "UniProt",
                "P1",
                "G_A",
                "",
                "GO:0005743",
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
        + "\n",
        encoding="utf-8",
    )
    rhea = tmp_path / "rhea.json"
    rhea.write_text(
        json.dumps(
            {
                "by_ec": {"1.2.3.4": [{"rhea_id": "RHEA:1"}]},
                "proteins": {
                    "RHEA:1": [
                        {"gene": "G_RHEA", "uniprot": "P2", "organism": "Homo sapiens"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    run = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": "go-beta2", "output_dir": str(run)},
                "beta2": {
                    "input_model": str(source),
                    "external_beta1_equivalent": True,
                    "compartments": {"x": "mitochondria", "i": "cytosol"},
                    "compartment_go_terms": {
                        "x": "GO:0005739",
                        "i": "GO:0005829",
                    },
                    "go_graph": {
                        "GO:0005743": {
                            "name": "mitochondrial inner membrane",
                            "parents": [{"relation": "part_of", "id": "GO:0005739"}],
                        },
                        "GO:0005739": {"name": "mitochondrion", "parents": []},
                    },
                    "location_sources": ["goa"],
                    "go_annotation_file": str(goa),
                    "reaction_sources": ["rhea"],
                    "rhea_snapshot": str(rhea),
                    "run_solver_checks": False,
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    assert get_status(run)["overall_status"] == "completed"
    resolution = next(
        item
        for item in get_status(run)["steps"]["export-beta2"]["outputs"]
        if item["role"] == "compartment-resolution-evidence"
    )
    payload = json.loads((run / resolution["path"]).read_text(encoding="utf-8"))
    resolved = next(
        item for item in payload["evidence"] if item.get("gene_id") == "G_A"
    )
    assert resolved["target_compartment_id"] == "x"
    assert resolved["target_compartment_name"] == "Mitochondria"
    gpr_output = next(
        item
        for item in get_status(run)["steps"]["export-beta2"]["outputs"]
        if item["role"] == "gpr-evidence"
    )
    gpr_records = [
        json.loads(line)
        for line in (run / gpr_output["path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rhea_record = next(item for item in gpr_records if item["reaction_id"] == "R_RHEA")
    assert rhea_record["candidate_gpr"] == "(G_RHEA)"
    assert rhea_record["rhea_id"] == "RHEA:1"


def test_beta2_go_alias_resolves_cytoplasm_to_cytosol_only_at_the_exact_term(
    tmp_path,
):
    model = Model("go-alias")
    left = Metabolite("left_c", formula="C", compartment="c")
    right = Metabolite("right_c", formula="C", compartment="c")
    for reaction_id, gene in (("R_CYT", "G_CYT"), ("R_GRAN", "G_GRAN")):
        reaction = Reaction(reaction_id)
        reaction.add_metabolites({left: -1, right: 1})
        reaction.gene_reaction_rule = gene
        model.add_reactions([reaction])
    source = tmp_path / "beta1.json"
    save_json_model(model, source)
    goa = tmp_path / "goa.gaf"
    goa.write_text(
        "".join(
            "\t".join(
                ["UniProt", protein, gene, "", go_id, "PMID:1", "IDA", "", "C"]
                + [""] * 5
                + ["GOA"]
            )
            + "\n"
            for protein, gene, go_id in (
                ("P1", "G_CYT", "GO:0005737"),
                ("P2", "G_GRAN", "GO:0036464"),
            )
        ),
        encoding="utf-8",
    )
    run = tmp_path / "run"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "workflow": "beta2",
                "run": {"name": "go-alias", "output_dir": str(run)},
                "beta2": {
                    "input_model": str(source),
                    "external_beta1_equivalent": True,
                    "compartments": {"c": "cytosol", "m": "mitochondria"},
                    "compartment_go_terms": {
                        "c": "GO:0005829",
                        "m": "GO:0005739",
                    },
                    "compartment_go_aliases": {"GO:0005737": "c"},
                    "go_graph": {
                        "GO:0005737": {"name": "cytoplasm", "parents": []},
                        "GO:0005829": {"name": "cytosol", "parents": []},
                        "GO:0005739": {"name": "mitochondrion", "parents": []},
                        "GO:0036464": {
                            "name": "cytoplasmic ribonucleoprotein granule",
                            "parents": [{"relation": "part_of", "id": "GO:0005737"}],
                        },
                    },
                    "location_sources": ["goa"],
                    "go_annotation_file": str(goa),
                    "run_solver_checks": False,
                },
            }
        ),
        encoding="utf-8",
    )
    start(config)
    assert get_status(run)["overall_status"] == "completed"
    resolution = next(
        item
        for item in get_status(run)["steps"]["export-beta2"]["outputs"]
        if item["role"] == "compartment-resolution-evidence"
    )
    payload = json.loads((run / resolution["path"]).read_text(encoding="utf-8"))
    by_gene = {item.get("gene_id"): item for item in payload["evidence"]}
    assert by_gene["G_CYT"]["status"] == "resolved"
    assert by_gene["G_CYT"]["target_compartment_id"] == "c"
    assert by_gene["G_CYT"]["resolution_method"] == "configured-alias"
    # A child of cytoplasm does not inherit the alias through the upward walk.
    assert by_gene["G_GRAN"]["status"] == "rejected"
    assert by_gene["G_GRAN"]["reason"] == "location-not-in-registry"
