from __future__ import annotations

import json

import cobra
import pytest
from cobra.io import save_json_model, write_sbml_model

from thg_protocol.workflow.runner import WorkflowError, start


def _model(path, reactions=1):
    model = cobra.Model("workflow-test")
    for index in range(reactions):
        model.add_reactions([cobra.Reaction(f"R{index}")])
    if path.suffix == ".xml":
        write_sbml_model(model, path)
    else:
        save_json_model(model, path)


@pytest.mark.parametrize("suffix", [".json", ".xml"])
def test_pathway_workflow_accepts_json_and_sbml_input(tmp_path, suffix):
    model = tmp_path / f"model{suffix}"
    _model(model)
    (tmp_path / "pathway.json").write_text(
        json.dumps({"compartments": []}), encoding="utf-8"
    )
    (tmp_path / "ids.json").write_text("{}", encoding="utf-8")
    config = {
        "workflow": "pathway",
        "run": {"name": "pathway", "output_dir": str(tmp_path / "run")},
        "pathway": {
            "input_model": str(model),
            "pathway_definition": str(tmp_path / "pathway.json"),
            "id_database": str(tmp_path / "ids.json"),
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    run = start(path)

    assert json.loads((run / "manifest.json").read_text())["overall_status"] == (
        "completed"
    )


def test_cell_specific_matrix_reduction_does_not_parse_matrix_as_gene_data(tmp_path):
    model = tmp_path / "model.json"
    _model(model, reactions=2)
    matrix = tmp_path / "activity.csv"
    matrix.write_text("1,0\n0,1\n", encoding="utf-8")
    config = {
        "workflow": "cell-specific",
        "run": {"name": "cell", "output_dir": str(tmp_path / "run")},
        "cell_specific": {
            "input_model": str(model),
            "expression_file": str(matrix),
            "gene_identifier_namespace": "reaction-order",
            "reduction_strategy": "activity-matrix",
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    run = start(path)

    assert json.loads((run / "manifest.json").read_text())["overall_status"] == (
        "completed"
    )


def test_human_database_live_mode_requires_an_adapter(tmp_path):
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps({"metabolites": [], "reactions": []}), encoding="utf-8"
    )
    config = {
        "workflow": "human-database",
        "run": {"name": "database", "output_dir": str(tmp_path / "run")},
        "human_database": {"records": str(records), "mode": "live"},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(WorkflowError, match="requires an injected"):
        start(path)
