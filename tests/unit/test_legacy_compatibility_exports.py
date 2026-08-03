"""Package export checks after removal of source-checkout adapters."""

from thg_protocol import config
from thg_protocol.analysis import consistency
from thg_protocol.annotation import reactions
from thg_protocol.gpr import ast_gpr
from thg_protocol.merge import MergeReport, merge_models, merge_models_from_paths
from thg_protocol.pathway import add_compartment, parse_reaction_equation


def test_package_exports_are_owned_by_supported_modules():
    assert config.load_config.__module__ == "thg_protocol.config"
    assert add_compartment.__module__ == "thg_protocol.pathway.core"
    assert parse_reaction_equation.__module__ == "thg_protocol.pathway.core"
    assert ast_gpr.sanitize_gpr.__module__ == "thg_protocol.gpr.ast_gpr"
    assert reactions.jaccard.__module__ == "thg_protocol.annotation.reactions"
    assert merge_models.__module__ == "thg_protocol.merge"
    assert merge_models_from_paths.__module__ == "thg_protocol.merge"
    assert MergeReport.__module__ == "thg_protocol.merge"


def test_package_analysis_exports_are_available():
    assert consistency.orphan_metabolites.__module__ == (
        "thg_protocol.analysis.consistency"
    )
    assert consistency.reaction_balance.__module__ == (
        "thg_protocol.analysis.consistency"
    )
