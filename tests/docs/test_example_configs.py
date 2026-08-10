from __future__ import annotations

from pathlib import Path

from thg_protocol.workflow.config import load_workflow_config


EXAMPLES = Path(__file__).parents[2] / "examples"


def test_runnable_workflow_configs_are_valid_and_resolve_inputs():
    expected_workflows = {
        "beta1.json": "beta1",
        "beta2.json": "beta2",
        "compare.json": "compare",
        "final-thg.json": "final-thg",
        "human-database.json": "human-database",
        "validation.json": "validate",
    }

    for filename, workflow_id in expected_workflows.items():
        config = load_workflow_config(EXAMPLES / "configs" / filename)
        assert config.workflow == workflow_id
        assert config.run.output_dir == (
            EXAMPLES.parent / "examples" / "output" / filename.removesuffix(".json")
        ).resolve()
