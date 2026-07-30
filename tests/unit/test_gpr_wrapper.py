import importlib

from thg_protocol.gpr import ast_gpr


def test_legacy_gpr_ast_wrapper_exports_package_api_without_path_injection():
    legacy = importlib.import_module("functions.gpr.ast_gpr")

    assert legacy.sanitize_gpr is ast_gpr.sanitize_gpr
    assert legacy.reduce_gpr is ast_gpr.reduce_gpr
