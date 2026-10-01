"""Execute the offline CLI workflow published in docs/quickstart.md."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[2] / "docs" / "examples"


def test_practical_quickstart_workflow_is_offline_and_writes_claimed_outputs(tmp_path):
    results = tmp_path / "practical-quickstart"
    results.mkdir()

    pathway = results / "enriched-model.json"
    _run_cli(
        "thg-pathway",
        "--model",
        str(FIXTURES / "quickstart_model.json"),
        "--config",
        str(FIXTURES / "pathway_config.json"),
        "--database",
        str(FIXTURES / "metabolite_ids.json"),
        "--output",
        str(pathway),
    )
    comparison = results / "comparison"
    _run_cli(
        "thg-compare",
        str(pathway),
        str(FIXTURES / "comparison_model.json"),
        "--output-dir",
        str(comparison),
    )
    _run_cli(
        "thg-compare",
        str(pathway),
        str(FIXTURES / "comparison_model.json"),
        "--semantic",
        "--output-dir",
        str(results / "semantic"),
    )
    _run_cli(
        "thg-gapfill",
        "--model",
        str(FIXTURES / "quickstart_model.json"),
        "--method",
        "greedy",
        "--max-additions",
        "1",
        "--allowed-connection",
        "c:e",
        "--output-dir",
        str(results / "gapfill"),
    )

    assert pathway.exists()
    assert (comparison / "compartments_comparison_raw.csv").exists()
    assert (results / "semantic" / "semantic-comparison.json").exists()
    assert (results / "gapfill" / "gapfilled-model.json").exists()


def _run_cli(command: str, *args: str) -> None:
    result = subprocess.run(
        [command, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
