from __future__ import annotations

import json

import cobra
import pytest

from thg_protocol.runtime.hashing import sha256_file
from thg_protocol.validation import validate_model
from thg_protocol.validation_apply import apply_decisions, report_payload
from thg_protocol.workflow.cli import main
from thg_protocol.workflow.proposals import ProposalError


def _model(r2):
    model = cobra.Model("toy")
    model.add_metabolites(
        [
            cobra.Metabolite("a_c", formula="C2H6O", charge=0, compartment="c"),
            cobra.Metabolite("b_c", formula="C2H4O", charge=0, compartment="c"),
            cobra.Metabolite("h2_c", formula="H2", charge=0, compartment="c"),
        ]
    )
    reaction = cobra.Reaction("R2")
    reaction.add_metabolites({model.metabolites.get_by_id(k): v for k, v in r2.items()})
    model.add_reactions([reaction])
    return model


@pytest.fixture
def validated(tmp_path):
    reference = _model({"a_c": -1, "b_c": 1, "h2_c": 1})
    model = _model({"a_c": -1, "b_c": 1})
    model_path, reference_path = tmp_path / "model.json", tmp_path / "reference.json"
    cobra.io.save_json_model(model, str(model_path))
    cobra.io.save_json_model(reference, str(reference_path))
    validation = validate_model(
        model, "structural-fast", reference_model=reference, propose_fixes=True
    )
    payload = report_payload(
        model,
        model_path,
        validation,
        previous={"reference_model": str(reference_path)},
    )
    report = tmp_path / "validation-report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    (proposal,) = validation["proposals"]
    return tmp_path, model_path, report, proposal


def _decide(path, *decisions):
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in decisions), encoding="utf-8"
    )
    return path


def test_apply_decisions_fixes_the_model_and_revalidates(validated):
    tmp_path, model_path, report, proposal = validated
    decisions = _decide(
        tmp_path / "decisions.jsonl",
        {"proposal_id": proposal["proposal_id"], "action": "approve"},
    )
    output = tmp_path / "model-fixed.json"
    result = apply_decisions(report, decisions, model_path, output)
    fixed = cobra.io.load_json_model(str(output))
    assert len(fixed.reactions.R2.metabolites) == 3
    assert result["applied"] == [proposal["proposal_id"]]
    assert result["changed"]["mass-balance"] == {"before": "failed", "after": "passed"}
    ledger = (tmp_path / "model-fixed.ledger.jsonl").read_text().splitlines()
    assert json.loads(ledger[0])["status"] == "applied"
    new = json.loads((tmp_path / "model-fixed.validation-report.json").read_text())
    assert new["model_checksum"] == sha256_file(output)
    assert new["source_model_checksum"] == sha256_file(model_path)
    assert new["reference_model"].endswith("reference.json")
    assert (tmp_path / "model-fixed.validation-report.html").is_file()


def test_rerun_replaces_the_ledger(validated):
    tmp_path, model_path, report, proposal = validated
    output = tmp_path / "model-fixed.json"
    decide = {"proposal_id": proposal["proposal_id"]}
    apply_decisions(
        report,
        _decide(tmp_path / "d.jsonl", {**decide, "action": "reject"}),
        model_path,
        output,
    )
    apply_decisions(
        report,
        _decide(tmp_path / "d.jsonl", {**decide, "action": "approve"}),
        model_path,
        output,
    )
    ledger = (tmp_path / "model-fixed.ledger.jsonl").read_text().splitlines()
    assert [json.loads(line)["status"] for line in ledger] == ["applied"]


def test_revalidation_keeps_the_solver_setting(validated, monkeypatch):
    import thg_protocol.validation as validation

    tmp_path, model_path, report, proposal = validated
    seen = []
    original = validation.validate_model

    def spy(*args, **kwargs):
        seen.append(kwargs.get("run_solver"))
        return original(*args, **kwargs)

    monkeypatch.setattr(validation, "validate_model", spy)
    apply_decisions(
        report,
        _decide(
            tmp_path / "d.jsonl",
            {"proposal_id": proposal["proposal_id"], "action": "approve"},
        ),
        model_path,
        tmp_path / "model-fixed.json",
    )
    assert seen == [False]


def test_cli_reports_an_unreadable_report(validated, capsys):
    tmp_path, model_path, _, proposal = validated
    decisions = _decide(
        tmp_path / "d.jsonl",
        {"proposal_id": proposal["proposal_id"], "action": "approve"},
    )
    args = [str(decisions), "--model", str(model_path), "-o", str(tmp_path / "f.json")]
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert main(["apply-decisions", str(tmp_path / "missing.json"), *args]) == 2
    assert main(["apply-decisions", str(tmp_path / "broken.json"), *args]) == 2
    assert "cannot read validation report" in capsys.readouterr().err


def test_apply_decisions_refuses_another_model(validated):
    tmp_path, model_path, report, proposal = validated
    other = tmp_path / "other.json"
    cobra.io.save_json_model(_model({"a_c": -1, "h2_c": 1}), str(other))
    decisions = _decide(
        tmp_path / "decisions.jsonl",
        {"proposal_id": proposal["proposal_id"], "action": "approve"},
    )
    with pytest.raises(ProposalError, match="is not the model the report describes"):
        apply_decisions(report, decisions, other, tmp_path / "out.json")
    assert not (tmp_path / "out.json").exists()


def test_invalid_decision_writes_nothing(validated):
    tmp_path, model_path, report, _ = validated
    decisions = _decide(
        tmp_path / "decisions.jsonl",
        {"proposal_id": "prop-unknown", "action": "approve"},
    )
    with pytest.raises(ProposalError, match="unknown proposal"):
        apply_decisions(report, decisions, model_path, tmp_path / "out.json")
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "decisions.jsonl",
        "model.json",
        "reference.json",
        "validation-report.json",
    ]


def test_cli_apply_decisions(validated, capsys):
    tmp_path, model_path, report, proposal = validated
    decisions = _decide(
        tmp_path / "decisions.jsonl",
        {"proposal_id": proposal["proposal_id"], "action": "approve"},
    )
    code = main(
        [
            "apply-decisions",
            str(report),
            str(decisions),
            "--model",
            str(model_path),
            "-o",
            str(tmp_path / "fixed.json"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "applied 1 of 1 decisions" in out
    assert "mass-balance: failed -> passed" in out
    assert (
        main(
            [
                "apply-decisions",
                str(report),
                str(decisions),
                "--model",
                str(tmp_path / "fixed.json"),
                "-o",
                str(tmp_path / "again.json"),
            ]
        )
        == 2
    )
