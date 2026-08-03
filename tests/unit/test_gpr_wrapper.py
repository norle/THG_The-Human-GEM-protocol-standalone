from thg_protocol.gpr import ast_gpr


def test_gpr_ast_api_is_package_owned():
    assert ast_gpr.sanitize_gpr("gene_a and gene_b") == "(gene_a and gene_b)"
    assert str(ast_gpr.reduce_gpr("gene_a or gene_a")) == "gene_a or gene_a"
