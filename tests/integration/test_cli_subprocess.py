"""Installed-style subprocess smoke tests for published CLI modules."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "thg_protocol.gapfill.cli",
        "thg_protocol.analysis.compare_cli",
        "thg_protocol.pathway.cli",
    ],
)
def test_cli_help_runs_from_outside_checkout(tmp_path, module):
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
