"""Expression provenance hashes the source once, independent of row count."""

import json
from types import SimpleNamespace

from thg_protocol.workflow._scientific import CellSpecificStage


def test_expression_collection_hashes_source_once(tmp_path, monkeypatch):
    source = tmp_path / "expression.json"
    source.write_text(json.dumps([{"gene_id": f"G{i}", "value": i} for i in range(50)]))
    context = SimpleNamespace(
        config=SimpleNamespace(
            sections={
                "cell_specific": {
                    "expression_file": str(source),
                    "gene_identifier_namespace": "symbol",
                }
            }
        )
    )
    calls = []

    def checksum(path):
        calls.append(path)
        return "source-checksum"

    monkeypatch.setattr("thg_protocol.workflow._scientific.sha256_file", checksum)
    result = CellSpecificStage("collect-expression-evidence").run(context, tmp_path)
    rows = [json.loads(line) for line in result.outputs[0][1].read_text().splitlines()]
    assert calls == [source]
    assert len(rows) == 50
    assert {row["source_file_checksum"] for row in rows} == {"source-checksum"}
