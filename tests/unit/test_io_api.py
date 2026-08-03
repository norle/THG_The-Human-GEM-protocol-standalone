def test_io_import_is_dependency_light() -> None:
    from thg_protocol.io import convert_json_to_sbml

    assert callable(convert_json_to_sbml)
