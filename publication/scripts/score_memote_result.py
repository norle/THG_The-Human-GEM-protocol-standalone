"""Render MEMOTE scores and snapshot HTML from a completed raw suite result."""

import hashlib
import json
import sys
from pathlib import Path

from memote.suite.reporting.config import ReportConfiguration
from memote.suite.reporting.snapshot import SnapshotReport
from memote.suite.results.result_manager import ResultManager


def main():
    source = Path(sys.argv[1])
    result = ResultManager().load(str(source))
    if not result.cases:
        raise ValueError(f"No MEMOTE tests in {source}")
    report = SnapshotReport(result=result, configuration=ReportConfiguration.load())
    summary = {
        "raw_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "tests": len(result.cases),
        "score": report.result["score"],
    }
    source.with_name("scores.json").write_text(json.dumps(summary, indent=2) + "\n")
    source.with_name("snapshot.html").write_text(report.render_html())


if __name__ == "__main__":
    main()
