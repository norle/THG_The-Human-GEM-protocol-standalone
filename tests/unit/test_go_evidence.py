from thg_protocol.curation.go import parse_obo, resolve_go_compartment
from thg_protocol.services.goa import parse_gaf
from thg_protocol.services.reactome import catalyst_candidate_gpr


def test_go_resolution_uses_only_is_a_and_part_of_and_preserves_path():
    graph = parse_obo(
        """
[Term]
id: GO:0005743
name: mitochondrial inner membrane
relationship: part_of GO:0005739 ! mitochondrion

[Term]
id: GO:0005739
name: mitochondrion
"""
    )
    result = resolve_go_compartment(
        "mitochondrial inner membrane",
        None,
        graph,
        {"x": "GO:0005739"},
        {"x": "Mitochondria"},
    )
    assert result["target_compartment_id"] == "x"
    assert result["resolution_path"][1]["relation"] == "part_of"


def test_go_resolution_rejects_equal_distance_targets():
    graph = parse_obo(
        """
[Term]
id: GO:0000001
name: ambiguous location
is_a: GO:0000002
is_a: GO:0000003

[Term]
id: GO:0000002
name: first

[Term]
id: GO:0000003
name: second
"""
    )
    result = resolve_go_compartment(
        "ambiguous location",
        None,
        graph,
        {"a": "GO:0000002", "b": "GO:0000003"},
    )
    assert result["reason"] == "ambiguous-compartment-resolution"


def test_goa_parser_keeps_cellular_component_evidence_and_drops_negation():
    row = "\t".join(
        [
            "UniProt",
            "P1",
            "GENE1",
            "",
            "GO:0005739",
            "PMID:1",
            "IDA",
            "",
            "C",
            "",
            "",
            "",
            "",
            "",
            "UniProt",
        ]
    )
    negated = row.replace("\tGENE1\t\tGO", "\tGENE2\tNOT\tGO")
    result = parse_gaf(row + "\n" + negated)
    assert len(result) == 1
    assert result[0].symbol == "GENE1"
    assert result[0].go_id == "GO:0005739"


def test_reactome_only_emits_and_for_an_explicit_complex():
    assert (
        catalyst_candidate_gpr(
            {
                "catalyst": {
                    "type": "complex",
                    "members": [{"gene": "A"}, {"gene": "B"}],
                }
            }
        )
        == "(A) and (B)"
    )
    assert (
        catalyst_candidate_gpr(
            {
                "catalyst": {
                    "type": "entity-set",
                    "members": [{"gene": "A"}, {"gene": "B"}],
                }
            }
        )
        == "(A) or (B)"
    )
