from thg_protocol.gpr.selection import select_reaction_gpr


def _evidence(source, expression, *, status="resolved", confidence="strong"):
    return {
        "ec": "1.1.1.1",
        "source": source,
        "candidate_gpr": expression,
        "status": status,
        "confidence": confidence,
    }


def test_model_gpr_wins_and_external_conflict_is_retained():
    result = select_reaction_gpr(
        model_gpr="B and A",
        model_genes=("A", "B"),
        evidence=[_evidence("reactome", "C")],
    )

    assert result.gpr == "A and B"
    assert result.genes == ("A", "B")
    assert len(result.conflicts) == 1
    assert result.status == "conflict"


def test_external_sgpr_is_deterministic_and_preserves_stoichiometry():
    evidence = [
        {
            **_evidence("reactome", "A and B"),
            "candidate_sgpr": "A*2 and B*1",
        },
        {
            **_evidence("biocyc", "A or B"),
            "candidate_sgpr": "A*1 or B*1",
        },
    ]
    first = select_reaction_gpr(
        model_gpr="",
        model_genes=(),
        evidence=evidence,
    )
    second = select_reaction_gpr(
        model_gpr="",
        model_genes=(),
        evidence=reversed(evidence),
        configured_stoichiometry={"A": 9},
    )

    assert first.gpr == second.gpr == "A and B"
    assert first.genes == second.genes == ("A", "B")
    assert first.status == second.status == "conflict"
    assert first.subunit_stoichiometry == (("A", 2), ("B", 1))
    assert second.subunit_stoichiometry == (("A", 9),)


def test_invalid_sgpr_metadata_falls_back_to_accepted_gpr():
    result = select_reaction_gpr(
        model_gpr="",
        model_genes=(),
        evidence=[
            {
                **_evidence("biocyc", "G1"),
                "candidate_sgpr": "G1 * nope",
            }
        ],
    )

    assert result.gpr == "G1"
    assert result.genes == ("G1",)
    assert result.selected_source == "biocyc"


def test_unresolved_candidate_remains_available_for_sgpr_resolution():
    result = select_reaction_gpr(
        model_gpr="",
        model_genes=("MODEL_GENE",),
        evidence=[
            _evidence("unknown", "A @ B", status="resolved", confidence="strong"),
            _evidence("unknown", "A", status="unresolved", confidence="strong"),
        ],
    )

    assert result.gpr == ""
    assert result.genes == ("MODEL_GENE",)
    assert result.status == "unresolved"
    assert result.candidate_sgpr is not None
    assert result.sgpr_status == "unresolved"


def test_structured_candidates_obey_same_acceptance_policy_as_plain_gpr():
    for status, confidence in (
        ("resolved", "supporting"),
        ("candidate", "strong"),
        ("unresolved", "strong"),
    ):
        record = {
            **_evidence("reactome", "A and B", status=status, confidence=confidence),
            "candidate_sgpr": "A*2 and B*1",
        }
        result = select_reaction_gpr(model_gpr="", model_genes=(), evidence=[record])
        assert result.gpr == ""
        assert result.status == "unresolved"
        assert result.subunit_stoichiometry == ()
        assert result.candidate_sgpr is not None
        accepted = select_reaction_gpr(
            model_gpr="",
            model_genes=(),
            evidence=[{**record, "confidence": "reaction-matched"}],
        )
        assert accepted.gpr == "A and B"
        assert accepted.subunit_stoichiometry == (("A", 2), ("B", 1))


def test_selected_plain_gpr_does_not_inherit_rejected_sgpr_stoichiometry():
    accepted = _evidence("reactome", "A or B")
    rejected = {
        **_evidence("uniprot", "C and D", status="candidate"),
        "candidate_sgpr": "C*2 and D*1",
    }
    result = select_reaction_gpr(
        model_gpr="", model_genes=(), evidence=[accepted, rejected]
    )
    assert result.gpr == "A or B"
    assert result.subunit_stoichiometry == ()
