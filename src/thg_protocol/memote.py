"""Safe MEMOTE command adapter with auditable artifacts."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .runtime.hashing import sha256_file


def run_memote(
    model: str | Path,
    output_dir: str | Path,
    *,
    command: Sequence[str] = ("memote", "run"),
    threshold: float | None = None,
) -> dict[str, object]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / "memote-result.json"
    report_path = destination / "memote-report.html"
    cmd = [*command, "--ignore-git", "--filename", str(result_path), str(model)]
    version = subprocess.run(
        [command[0], "--version"], capture_output=True, text=True, check=False
    )
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    payload: dict[str, object] = {
        "schema_version": 1,
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "status": "command-failed" if completed.returncode else "completed",
        "version": version.stdout.strip() or version.stderr.strip(),
    }
    report_command = [
        command[0],
        "report",
        "snapshot",
        "--filename",
        str(report_path),
        str(model),
    ]
    report_run = None
    if completed.returncode == 0:
        report_run = subprocess.run(
            report_command, capture_output=True, text=True, check=False
        )
        payload["report_returncode"] = report_run.returncode
        payload["report_stdout"] = report_run.stdout
        payload["report_stderr"] = report_run.stderr
        if report_run.returncode:
            payload["status"] = "report-command-failed"
    payload["report_command"] = report_command
    if result_path.is_file():
        try:
            payload["result"] = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload["status"] = "invalid-result"
    if threshold is not None:
        payload["threshold"] = threshold
        result = payload.get("result")
        score = result.get("score") if isinstance(result, dict) else None
        if isinstance(score, (int, float)):
            payload["threshold_passed"] = score >= threshold
        else:
            payload["threshold_status"] = "not-available"
    artifacts = {}
    for path in (result_path, report_path):
        if path.is_file():
            artifacts[path.name] = {
                "path": str(path),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
    payload["artifacts"] = artifacts
    (destination / "memote-run.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


__all__ = ["run_memote"]
