"""Assert-only reproductions for the workflow audit; writes only temporary files."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from thg_protocol.cell_specific import evaluate_gpr_activity
from thg_protocol.workflow.config import load_workflow_config
from thg_protocol.workflow.registry import register_builtin_workflows
from thg_protocol.workflow.validation import ValidationScientificStage


register_builtin_workflows()

with tempfile.TemporaryDirectory(prefix="thg-audit-") as temporary:
    root = Path(temporary)

    # Validation config passes parsing, then crashes when its first stage fingerprints.
    validation_config = root / "validation.json"
    validation_config.write_text(
        json.dumps({"workflow": "validate", "run": {"name": "audit", "output_dir": "out"}, "validation": {}})
    )
    config = load_workflow_config(validation_config)
    context = SimpleNamespace(config=config, manifest={})
    try:
        ValidationScientificStage("validate-input").fingerprint_data(context)
    except KeyError as error:
        assert error.args == ("input_model",)
    else:
        raise AssertionError("missing validation.input_model did not reproduce")

    # 1e309 parses as infinity, passes config validation and deactivates a finite-score GPR.
    model = root / "model.json"
    model.write_text("{}")
    expression = root / "expression.tsv"
    expression.write_text("gene\tvalue\ng1\t1\n")
    cell_config = root / "cell.json"
    cell_config.write_text(
        json.dumps(
            {
                "workflow": "cell-specific",
                "run": {"name": "audit", "output_dir": "out"},
                "cell_specific": {
                    "input_model": "model.json",
                    "expression_file": "expression.tsv",
                    "gene_identifier_namespace": "ensembl",
                    "threshold": 1e309,
                },
            }
        )
    )
    cell = load_workflow_config(cell_config).sections["cell_specific"]
    assert cell["threshold"] == float("inf")
    active, missing = evaluate_gpr_activity("g1", {"g1": 1.0}, threshold=cell["threshold"])
    assert not active and not missing

print("confirmed: missing validation model crashes at fingerprint; infinite threshold deactivates finite activity")
