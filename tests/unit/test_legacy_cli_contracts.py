"""CLI contract comparisons for retained legacy entry points."""

from __future__ import annotations

from compare_models.compare_models import build_parser as legacy_compare_parser
from implement_pathway.pathway_implementation import (
    build_parser as legacy_pathway_parser,
)

from thg_protocol.analysis.compare_cli import build_parser as package_compare_parser
from thg_protocol.pathway.cli import build_parser as package_pathway_parser


def _option_strings(parser):
    return {
        option
        for action in parser._actions
        for option in action.option_strings
    }


def test_pathway_legacy_and_package_parsers_accept_the_same_options():
    assert _option_strings(legacy_pathway_parser()) == _option_strings(
        package_pathway_parser()
    )


def test_compare_legacy_and_package_parsers_preserve_input_and_filter_options():
    legacy = _option_strings(legacy_compare_parser())
    package = _option_strings(package_compare_parser())

    assert {"--include-blocked", "--no-include-blocked"} <= legacy
    assert {"--include-blocked", "--no-include-blocked"} <= package
    assert {"--output-dir"} <= legacy & package


def test_legacy_compare_output_requirement_is_documented_difference():
    legacy_action = next(
        action
        for action in legacy_compare_parser()._actions
        if action.dest == "output_dir"
    )
    package_action = next(
        action
        for action in package_compare_parser()._actions
        if action.dest == "output_dir"
    )

    assert legacy_action.required is True
    assert package_action.required is False
