"""CLI contracts for maintained installed entry points."""

from __future__ import annotations

from thg_protocol.analysis.compare_cli import build_parser as package_compare_parser
from thg_protocol.pathway.cli import build_parser as package_pathway_parser


def _option_strings(parser):
    return {option for action in parser._actions for option in action.option_strings}


def test_pathway_parser_exposes_explicit_inputs_and_output():
    assert {"--model", "--config", "--database", "--output"} <= _option_strings(
        package_pathway_parser()
    )


def test_compare_legacy_and_package_parsers_preserve_input_and_filter_options():
    package = _option_strings(package_compare_parser())

    assert {"--include-blocked", "--no-include-blocked"} <= package
    assert "--output-dir" in package
