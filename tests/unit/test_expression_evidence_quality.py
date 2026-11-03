"""Non-finite expression values and dropped genes are reported, not hidden."""

import json
from types import SimpleNamespace

import cobra

from thg_protocol.workflow import _scientific
from thg_protocol.workflow._scientific import CellSpecificStage


def _context(tmp_path, **section):
    return SimpleNamespace(
        config=SimpleNamespace(
            sections={
                "cell_specific": {"gene_identifier_namespace": "symbol", **section}
            }
        )
    )


def test_non_finite_expression_values_are_skipped_and_counted(tmp_path):
    source = tmp_path / "expression.json"
    source.write_text(
        json.dumps(
            [
                {"gene_id": "A", "value": 1.0},
                {"gene_id": "B", "value": float("nan")},
                {"gene_id": "C", "value": float("inf")},
                {"gene_id": "D", "value": 0},
            ]
        )
    )
    result = CellSpecificStage("collect-expression-evidence").run(
        _context(tmp_path, expression_file=str(source)), tmp_path
    )
    rows = [json.loads(line) for line in result.outputs[0][1].read_text().splitlines()]
    assert [row["gene_identifier"] for row in rows] == ["A", "D"]
    assert result.summary == {"records": 2, "skipped_non_finite": 2}


def test_genes_missing_from_the_model_are_counted_when_mapping(tmp_path, monkeypatch):
    model = cobra.Model("m")
    model.genes.append(cobra.Gene("A"))
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text(
        "".join(
            json.dumps(
                {"gene_identifier": gene, "sample_identifier": "s", "activity_value": 1}
            )
            + "\n"
            for gene in ("A", "X", "Y")
        )
    )
    monkeypatch.setattr(_scientific, "_load_cobra_model", lambda path: model)
    monkeypatch.setattr(
        _scientific,
        "_dependency_path",
        lambda context, stage, role: evidence if role == "evidence" else tmp_path,
    )
    for strategy in ("gimme", "gpr-threshold"):
        result = CellSpecificStage("map-expression-to-model").run(
            _context(tmp_path, reduction_strategy=strategy), tmp_path
        )
        assert result.summary["mapped_genes"] == 1
        assert result.summary["unmapped_genes"] == 2
