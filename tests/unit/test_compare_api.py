from dataclasses import dataclass
from types import SimpleNamespace

from thg_protocol.analysis.compare import compare_reactions, compare_semantic_models
from thg_protocol.analysis.compare_cli import main


@dataclass(frozen=True)
class Metabolite:
    id: str
    formula: str
    charge: int
    compartment: str


def model(reaction_id, coefficient=1):
    metabolite = Metabolite("m_c", "C", 0, "c")
    reaction = SimpleNamespace(id=reaction_id, metabolites={metabolite: coefficient})
    return SimpleNamespace(reactions=[reaction])


def test_compare_reactions_reports_id_and_stoichiometry_overlap():
    comparison = compare_reactions(model("R1"), model("R1"))
    assert comparison["c"]["intersect_id"] == 1
    assert comparison["c"]["intersect_stoich"] == 1


def test_compare_cli_help_is_import_safe(capsys):
    try:
        main(["--help"])
    except SystemExit as error:
        assert error.code == 0
    assert "Compare reactions" in capsys.readouterr().out


def _cobra_model(*, formula="C", gpr="G1"):
    left = Metabolite("a_c", formula, 0, "c")
    right = Metabolite("b_c", "C", 0, "c")
    reaction = SimpleNamespace(
        id="R1", name=None, lower_bound=0, upper_bound=1000,
        metabolites={left: -1, right: 1}, gene_reaction_rule=gpr, annotation={}
    )
    return SimpleNamespace(
        id="semantic",
        name=None,
        compartments={"c": "cytosol"},
        metabolites=[left, right],
        reactions=[reaction],
        genes=[],
        groups=[],
    )


def test_semantic_comparison_classifies_formula_and_gpr_changes():
    comparison = compare_semantic_models(
        _cobra_model(), _cobra_model(formula="CO", gpr="G2")
    )
    assert not comparison["equal"]
    assert comparison["category_counts"]["formula_or_charge_correction"] == 1
    assert comparison["category_counts"]["gpr_correction"] == 1


def test_semantic_comparison_is_order_independent():
    first = _cobra_model()
    second = _cobra_model()
    assert compare_semantic_models(first, second)["equal"]
