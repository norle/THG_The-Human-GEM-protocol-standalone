"""Command-line interface for resumable THG runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ConfigError
from .lock import RunLockedError, unlock_run
from .manifest import ManifestError
from .registered_runner import RegisteredWorkflowError
from .runner import StageFailedError, WorkflowError, get_status, resume, start


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the THG resumable workflow.")
    commands = parser.add_subparsers(dest="command", required=True)

    start_parser = commands.add_parser("start", help="start a new run")
    start_parser.add_argument("config", type=Path, help="JSON run configuration")

    resume_parser = commands.add_parser("resume", help="resume an existing run")
    resume_parser.add_argument("run_dir", type=Path)
    resume_parser.add_argument("--force-step", choices=None, metavar="STAGE")

    status_parser = commands.add_parser("status", help="show validated run state")
    status_parser.add_argument("run_dir", type=Path)
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    unlock_parser = commands.add_parser(
        "unlock", help="remove a demonstrably stale lock"
    )
    unlock_parser.add_argument("run_dir", type=Path)
    unlock_parser.add_argument("--force", action="store_true")

    # Public names make the maintained workflow entry points discoverable
    # while retaining ``start`` for generic and legacy configurations.
    for workflow_id in ("beta1", "beta2", "validate", "compare"):
        workflow_parser = commands.add_parser(
            workflow_id, help=f"start a {workflow_id} registered workflow"
        )
        workflow_parser.add_argument(
            "config", type=Path, help="format-2 workflow configuration"
        )
    return parser


def _print_human_status(manifest: dict[str, object]) -> None:
    print(f"run {manifest['run_id']}: {manifest['overall_status']}")
    steps = manifest["steps"]
    if isinstance(steps, dict):
        for stage, entry in steps.items():
            if isinstance(entry, dict):
                print(f"{stage}: {entry['status']} (attempt {entry['attempt']})")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            print(f"run started: {start(args.config)}")
        elif args.command in {"beta1", "beta2", "validate", "compare"}:
            from .config import load_workflow_config

            config = load_workflow_config(args.config)
            if config.workflow != args.command:
                raise ConfigError(
                    f"configuration selects workflow '{config.workflow}', "
                    f"not '{args.command}'"
                )
            print(f"run started: {start(args.config)}")
        elif args.command == "resume":
            print(f"run resumed: {resume(args.run_dir, force_step=args.force_step)}")
        elif args.command == "status":
            manifest = get_status(args.run_dir)
            if args.as_json:
                print(json.dumps(manifest, indent=2, sort_keys=True))
            else:
                _print_human_status(dict(manifest))
        elif args.command == "unlock":
            unlock_run(args.run_dir, force=args.force)
            print(f"lock removed: {Path(args.run_dir).resolve()}")
        return 0
    except (
        ConfigError,
        ManifestError,
        RunLockedError,
        WorkflowError,
        RegisteredWorkflowError,
    ) as error:
        print(f"error: {error}", file=__import__("sys").stderr)
        if isinstance(error, RunLockedError):
            return 3
        if isinstance(error, StageFailedError):
            return 4
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
