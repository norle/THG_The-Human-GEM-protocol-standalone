from dataclasses import dataclass
from types import SimpleNamespace

from thg_protocol.analysis.compare import compare_reactions
from thg_protocol.analysis.compare_cli import main
from compare_models.compare_compartements import build_parser, comp_compare


@dataclass(frozen=True)
class Metabolite:
    id: str
    compartment: str


def model(reaction_id, coefficient=1):
    metabolite = Metabolite("m_c", "c")
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


def test_legacy_compartment_comparison_delegates_to_package_api():
    comparison = comp_compare(model("R1"), model("R1"))
    assert comparison["c"]["match_stoich_ids"] == ["R1"]


def test_legacy_compartment_comparison_requires_explicit_output_dir():
    actions = {action.dest: action for action in build_parser()._actions}
    assert actions["output_dir"].required is True
