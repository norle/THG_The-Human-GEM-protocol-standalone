"""Run small offline examples of the lower-level THG Python APIs.

Run this file from any working directory after installing the package. Outputs
are placed in ``examples/output/api`` relative to the repository root.
"""

from __future__ import annotations

from pathlib import Path

from cobra.io import load_json_model

from thg_protocol.analysis import find_network_components, write_component_report
from thg_protocol.analysis.compare import compare_models_from_files
from thg_protocol.analysis.consistency import unbalanced_reactions
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.database import reconstruct_model_from_json
from thg_protocol.pathway import implement_pathway_files


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    fixtures = repository_root / "docs" / "examples"
    output = repository_root / "examples" / "output" / "api"
    output.mkdir(parents=True, exist_ok=True)

    reference_path = output / "reference-model.json"
    model = reconstruct_model_from_json(
        fixtures / "records.json", output_path=reference_path
    )
    print(f"reconstructed {model.id}: {len(model.reactions)} reactions")

    print("annotation coverage:", analyze_model_annotations(reference_path))

    enriched_path = output / "enriched-model.json"
    pathway_result = implement_pathway_files(
        fixtures / "quickstart_model.json",
        fixtures / "pathway_config.json",
        fixtures / "metabolite_ids.json",
        enriched_path,
    )
    print(f"added compartments: {pathway_result['compartments_added']}")

    enriched_model = load_json_model(enriched_path)
    component_result = find_network_components(enriched_model)
    write_component_report(component_result, output / "components.json")
    print("unbalanced reactions:", unbalanced_reactions(enriched_model))

    comparison = compare_models_from_files(
        enriched_path,
        fixtures / "comparison_model.json",
        output / "comparison",
    )
    print("comparison summary:", comparison["raw"]["_summary"])


if __name__ == "__main__":
    main()
