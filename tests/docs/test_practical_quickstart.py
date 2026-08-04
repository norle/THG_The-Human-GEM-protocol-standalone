"""Execute the offline workflow published in docs/quickstart.md."""

from pathlib import Path

from cobra.io import load_json_model

from thg_protocol.analysis import find_network_components, write_component_report
from thg_protocol.analysis.compare import compare_models_from_files
from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.database import reconstruct_model_from_json
from thg_protocol.pathway import implement_pathway_files

FIXTURES = Path(__file__).parents[2] / "docs" / "examples"


def test_practical_quickstart_workflow_is_offline_and_writes_claimed_outputs(tmp_path):
    results = tmp_path / "practical-quickstart"
    results.mkdir()

    reference = results / "reference-model.json"
    model = reconstruct_model_from_json(
        FIXTURES / "records.json", output_path=reference
    )
    assert (model.id, len(model.metabolites), len(model.reactions)) == (
        "docs-toy",
        2,
        1,
    )
    assert analyze_model_annotations(reference) == {"chebi": 1}

    enriched = results / "enriched-model.json"
    pathway = implement_pathway_files(
        FIXTURES / "quickstart_model.json",
        FIXTURES / "pathway_config.json",
        FIXTURES / "metabolite_ids.json",
        enriched,
    )
    assert pathway["compartments_added"] == 1

    loaded = load_json_model(enriched)
    components = find_network_components(loaded)
    write_component_report(components, results / "components.json")
    assert not unbalanced_reactions(loaded)

    reports = compare_models_from_files(
        enriched, FIXTURES / "comparison_model.json", results / "comparison"
    )
    assert reports["raw"]["_summary"]["total_rxns_a"] == 2
    assert (results / "components.json").exists()
    assert (results / "comparison" / "compartments_comparison_raw.csv").exists()
