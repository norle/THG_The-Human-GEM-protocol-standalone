def test_io_import_is_dependency_light() -> None:
    from thg_protocol.io import convert_json_to_sbml

    assert callable(convert_json_to_sbml)


def test_legacy_conversion_wrapper_has_help() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "utils/json_to_sbml.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "source COBRA JSON model" in result.stdout
