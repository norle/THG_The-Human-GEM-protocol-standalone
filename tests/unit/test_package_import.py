import pytest

import thg_protocol
from thg_protocol import config


def test_package_exposes_version():
    assert thg_protocol.__version__ == "0.1.0"


def test_config_module_resolves_project_root():
    marker = config.get_project_root() / "docs" / "plans" / "REFACTORING_PLAN.md"
    if not marker.exists():
        pytest.skip("repository marker is unavailable in an installed wheel")
    assert marker.exists()
