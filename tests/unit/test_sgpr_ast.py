from thg_protocol.gpr import (
    AndNode,
    GeneNode,
    OrNode,
    SgprEvidence,
    merge_sgpr_evidence,
    parse_sgpr,
    to_gpr,
    to_legacy_sgpr,
    to_sgpr,
    unambiguous_stoichiometry,
)
from thg_protocol.gpr.sources.biocyc import biocyc_sgpr_evidence
from thg_protocol.gpr.sources.kegg import kegg_sgpr_evidence
from thg_protocol.gpr.sources.reactome import reactome_sgpr_evidence


def test_canonical_serializers_keep_branch_local_coefficients():
    node = OrNode(
        (
            AndNode((GeneNode("A", 2, "observed"), GeneNode("B", 1, "observed"))),
            AndNode((GeneNode("A", 1, "observed"), GeneNode("C", 3, "observed"))),
        )
    )
    assert to_gpr(node) == "(A and B) or (A and C)"
    assert to_sgpr(node) == "(A*2 and B*1) or (A*1 and C*3)"
    assert to_legacy_sgpr(OrNode((GeneNode("A"), GeneNode("B")))) == "(A*1) or (B*1)"
    assert parse_sgpr("(A*2 and B) or C") == OrNode(
        (AndNode((GeneNode("A", 2), GeneNode("B"))), GeneNode("C"))
    )


def test_merge_reports_complete_structure_conflicts():
    left = SgprEvidence(
        "biocyc", "1.1.1.1", AndNode((GeneNode("A"), GeneNode("B"))),
        "strong", "resolved"
    )
    right = SgprEvidence(
        "reactome", "1.1.1.1", OrNode((GeneNode("A"), GeneNode("B"))),
        "strong", "resolved"
    )
    result = merge_sgpr_evidence([left, right])
    assert result.status == "conflict"
    assert result.sources == ("biocyc", "reactome")


def test_source_adapters_preserve_complexes_and_unknown_kegg_coefficients():
    record = {
        "enzymes": [
            {"components": [{"gene": "A", "coefficient": 2}, {"gene": "B"}]},
            {"gene": "C"},
        ]
    }
    biocyc = type("BioCyc", (), {"get_ec_records": lambda self, ec: record})()
    evidence = biocyc_sgpr_evidence("1.1.1.1", biocyc_client=biocyc)
    assert evidence.to_dict()["candidate_sgpr"] == "(A*2 and B) or C"

    reactome = reactome_sgpr_evidence(
        {
            "ec": "1.1.1.1",
            "catalyst": {
                "type": "complex",
                "members": [{"gene": "A", "coefficient": 2}, {"gene": "B"}],
            },
        }
    )
    assert reactome.to_dict()["candidate_sgpr"] == "A*2 and B"

    kegg = kegg_sgpr_evidence("1.1.1.1", kegg_client=object(), kegg_genes=["A", "B"])
    assert kegg.to_dict()["candidate_sgpr"] == "A or B"
    assert kegg.sgpr.children[0].coefficient_status == "unknown"


def test_repeated_reactome_members_infer_a_branch_local_coefficient():
    evidence = reactome_sgpr_evidence(
        {
            "catalyst": {
                "type": "complex",
                "members": [{"gene": "A"}, {"gene": "A"}, {"gene": "B"}],
            }
        }
    )
    assert evidence.to_dict()["candidate_sgpr"] == "A*2 and B"


def test_lower_precedence_rhea_candidates_do_not_conflict_with_reactome_structure():
    result = merge_sgpr_evidence(
        [
            SgprEvidence("rhea", "1.1.1.1", OrNode((GeneNode("A"), GeneNode("B")))),
            SgprEvidence(
                "reactome",
                "1.1.1.1",
                AndNode((GeneNode("A"), GeneNode("B"))),
                "strong",
                "resolved",
            ),
        ]
    )
    assert result.status == "resolved"
    assert to_gpr(result.sgpr) == "A and B"


def test_flat_stoichiometry_refuses_unknown_coefficients():
    assert unambiguous_stoichiometry(AndNode((GeneNode("A"), GeneNode("B")))) is None
