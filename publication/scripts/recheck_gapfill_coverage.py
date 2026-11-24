"""Run current coverage serially on rebuilt B and compare saved coverage."""

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from thg_protocol.runtime.stage import StageContext, dependency_path
from thg_protocol.workflow.config import load_workflow_config
from thg_protocol.workflow.gapfill import GapfillStage


def records(path):
    with path.open() as stream:
        assert "fingerprint" in json.loads(next(stream))
        return {row["component"]: row for line in stream if (row := json.loads(line))}


def main():
    run, config_path, out = map(Path, sys.argv[1:])
    config = load_workflow_config(config_path)
    config = replace(
        config,
        sections=config.sections
        | {
            "gapfill": config.sections["gapfill"] | {"coverage_workers": 1},
        },
    )
    context = StageContext(config, run, json.loads((run / "manifest.json").read_text()))
    original = dependency_path(context, "compute-gapfill-coverage", "coverage")
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    stage = GapfillStage(
        "compute-gapfill-coverage",
        (
            "load-gapfill-source",
            "generate-gapfill-candidates",
            "select-gapfill-connectors",
        ),
    )
    result = stage.run(context, out)
    actual = dict(result.outputs)["coverage"]
    left, right = records(original), records(actual)
    differences = [
        key
        for key in sorted(left.keys() | right.keys())
        if left.get(key) != right.get(key)
    ]
    summary = {
        "parallel_file": str(original),
        "serial_file": str(actual),
        "serial_elapsed_seconds": round(time.monotonic() - started, 2),
        "components_in_parallel": len(left),
        "components_in_serial": len(right),
        "different_components": differences,
        **result.summary,
    }
    (out / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert result.summary["reused_components"] == 0, "Serial timing reused saved work"
    assert not differences, f"Coverage differs for components {differences}"


if __name__ == "__main__":
    main()
