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
