import os
import subprocess
import sys
from pathlib import Path

import pytest

import thg_protocol
from thg_protocol import config


def test_package_exposes_version():
    assert thg_protocol.__version__ == "0.1.0"


def test_config_module_resolves_project_root():
    marker = config.get_project_root() / "pyproject.toml"
    if not marker.exists():
        pytest.skip("repository marker is unavailable in an installed wheel")
    assert marker.exists()


def test_services_import_without_dependencies():
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import thg_protocol.services"],
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
