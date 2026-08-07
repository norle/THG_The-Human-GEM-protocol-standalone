import thg_protocol.gpr as gpr


def test_gpr_package_import_is_lazy():
    assert "sanitize_gpr" in gpr.__all__
