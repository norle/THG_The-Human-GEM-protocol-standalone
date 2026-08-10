from __future__ import annotations

import json

from thg_protocol.workflow.runner import get_status, resume, start


def test_human_database_resume_invalidates_changed_records(tmp_path):
    records = tmp_path / "records.json"
    records.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metabolites": [{"id": "a_c", "formula": "C", "compartment": "c"}],
                "reactions": [],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "format_version": 2,
                "workflow": "human-database",
                "run": {
                    "name": "human-database",
                    "output_dir": str(tmp_path / "run"),
                },
                "human_database": {"records": str(records)},
            }
        ),
        encoding="utf-8",
    )

    run = start(config)
    before = get_status(run)
    records.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metabolites": [
                    {"id": "a_c", "formula": "C", "compartment": "c"},
                    {"id": "b_c", "formula": "C", "compartment": "c"},
                ],
                "reactions": [],
            }
        ),
        encoding="utf-8",
    )

    resume(run)
    after = get_status(run)
    for stage in before["steps"]:
        assert after["steps"][stage]["attempt"] == before["steps"][stage]["attempt"] + 1

    output = after["steps"]["human-database-reconstruct"]["outputs"][0]["path"]
    assert json.loads((run / output).read_text(encoding="utf-8"))["metabolites"]
