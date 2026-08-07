"""Offline smoke tests for the small examples published with the docs."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import cobra

from thg_protocol.analysis import find_network_components, full_compaction
from thg_protocol.analysis.compare import compare_models_from_files
from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.cell_specific import reduce_model_by_activity, replace_index_tokens
from thg_protocol.database import (
    reconstruct_model_from_json,
    reconstruct_model_from_pickle,
)
from thg_protocol.figures.models import model_component_summary
from thg_protocol.gapfill import run_pipeline
from thg_protocol.gpr import get_gpr
from thg_protocol.merge import merge_models
from thg_protocol.model_build import build_model, build_model_batch
from thg_protocol.pathway import implement_pathway_files
from thg_protocol.services.biocyc import StaticBioCycClient

FIXTURES = Path(__file__).parents[2] / "docs" / "examples"


def test_documented_construction_and_workflow_examples_are_offline(tmp_path):
    records_path = FIXTURES / "records.json"
    model = reconstruct_model_from_json(
        records_path, output_path=tmp_path / "model.json"
    )
    assert model.id == "docs-toy"
    assert (tmp_path / "model.json").exists()

    pickle_path = tmp_path / "records.pkl"
    pickle_path.write_bytes(
        pickle.dumps(
            {
                "id": "pickle-docs-toy",
                "mets_cl": {"A": {"ID2": "A", "Subcel": "c"}},
                "reactions_cl": {},
            }
        )
    )
    pickle_model = reconstruct_model_from_pickle(pickle_path)
    assert pickle_model.id == "pickle-docs-toy"

    single = build_model(
        tmp_path / "model.json",
        tmp_path / "built.json",
        cache_dir=tmp_path / "single-cache",
    )
    batch = build_model_batch(
        tmp_path / "model.json",
        tmp_path / "batch.json",
        cache_dir=tmp_path / "batch-cache",
        output_errors=tmp_path / "batch-errors.tsv",
    )
    assert single.output_path.exists() and batch.output_path.exists()

    gapfill = run_pipeline(
        FIXTURES / "quickstart_model.json", tmp_path / "gapfill", max_additions=1
    )
    assert gapfill["model"].exists()

    pathway = implement_pathway_files(
        FIXTURES / "quickstart_model.json",
        FIXTURES / "pathway_config.json",
        FIXTURES / "metabolite_ids.json",
        tmp_path / "pathway.json",
    )
    assert pathway["compartments_added"] == 1


def test_documented_analysis_annotation_and_transformation_examples(tmp_path):
    model_payload = json.loads((FIXTURES / "quickstart_model.json").read_text())
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(model_payload))
    result = compare_models_from_files(
        model_path, FIXTURES / "comparison_model.json", tmp_path / "comparison"
    )
    assert result["raw"]["_summary"]["total_rxns_a"] == 2
    assert analyze_model_annotations(model_path) == {}

    cobra_model = cobra.Model("docs-cobra")
    a = cobra.Metabolite("a_c", compartment="c")
    b = cobra.Metabolite("b_c", compartment="c")
    reaction = cobra.Reaction("R1")
    reaction.add_metabolites({a: -1, b: 1})
    reaction.gene_reaction_rule = "GENE1"
    cobra_model.add_reactions([reaction])
    merged, report = merge_models(
        cobra_model, cobra_model, output_path=tmp_path / "merged.json"
    )
    assert report.overlapping_reactions == 1
    assert not unbalanced_reactions(merged)
    components = find_network_components(merged)
    compacted, removed = full_compaction(merged)
    assert components["component_info"] and not removed
    assert compacted.reactions.R1.id == "R1"
    assert model_component_summary(merged).reactions == 1

    tailored, reduction = reduce_model_by_activity(
        merged, [[1.0]], output_path=tmp_path / "tailored.json"
    )
    assert reduction.retained_reactions == len(tailored.reactions)
    assert replace_index_tokens(merged, ["ENSG0001"]) == ["GENE1"]

    client = StaticBioCycClient(
        ec_pages={("HUMAN", "1.1.1.1"): "<b>Gene:</b> GENE1 ENSG0001<br>"}
    )
    assert get_gpr("1.1.1.1", biocyc_client=client)[-1] == "(GENE1)"
