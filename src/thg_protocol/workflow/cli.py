"""Command-line interface for resumable THG runs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from thg_protocol.runtime.locking import RunLockedError, unlock_run
from thg_protocol.runtime.manifest import ManifestError

from .config import ConfigError
from .runner import WorkflowError, get_status, resume, start


class _CompactProgressFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING or bool(
            getattr(record, "thg_compact", False)
        )


def _add_verbosity_argument(
    parser: argparse.ArgumentParser,
    *,
    default: int | str = 0,
    quiet_default: bool | str = False,
) -> None:
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=default,
        help="show stage progress; repeat (-vv) for fingerprints and outputs",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=quiet_default,
        help="show only warnings and errors",
    )


def _configure_logging(verbosity: int, *, quiet: bool = False) -> None:
    logger = logging.getLogger("thg_protocol.workflow")
    for existing in tuple(logger.handlers):
        if getattr(existing, "_thg_cli_handler", False):
            logger.removeHandler(existing)
    logger.setLevel(logging.DEBUG if verbosity > 1 else logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler._thg_cli_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    )
    if verbosity == 0 and not quiet:
        handler.addFilter(_CompactProgressFilter())
        handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(
        logging.WARNING if quiet else logging.DEBUG if verbosity > 1 else logging.INFO
    )
    logger.addHandler(handler)
    logger.propagate = False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the THG resumable workflow.")
    _add_verbosity_argument(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    start_parser = commands.add_parser("start", help="start or resume a run")
    start_parser.add_argument("config", type=Path, help="JSON run configuration")
    _add_verbosity_argument(
        start_parser,
        default=argparse.SUPPRESS,
        quiet_default=argparse.SUPPRESS,
    )

    resume_parser = commands.add_parser("resume", help="resume an existing run")
    resume_parser.add_argument("run_dir", type=Path)
    resume_parser.add_argument("--force-step", choices=None, metavar="STAGE")
    _add_verbosity_argument(
        resume_parser,
        default=argparse.SUPPRESS,
        quiet_default=argparse.SUPPRESS,
    )

    status_parser = commands.add_parser("status", help="show validated run state")
    status_parser.add_argument("run_dir", type=Path)
    status_parser.add_argument("--json", action="store_true", dest="as_json")

    unlock_parser = commands.add_parser(
        "unlock", help="remove a demonstrably stale lock"
    )
    unlock_parser.add_argument("run_dir", type=Path)
    unlock_parser.add_argument("--force", action="store_true")

    # Public names make the maintained workflow entry points discoverable.
    for workflow_id in (
        "beta1",
        "beta2",
        "gapfill",
        "reference",
        "validate",
        "compare",
        "cell-specific",
        "pathway",
    ):
        workflow_parser = commands.add_parser(
            workflow_id, help=f"start a {workflow_id} registered workflow"
        )
        workflow_parser.add_argument(
            "config", type=Path, help="workflow configuration"
        )
        _add_verbosity_argument(
            workflow_parser,
            default=argparse.SUPPRESS,
            quiet_default=argparse.SUPPRESS,
        )
    return parser


def _print_human_status(manifest: dict[str, object]) -> None:
    print(f"run {manifest['run_id']}: {manifest['overall_status']}")
    steps = manifest["steps"]
    if isinstance(steps, dict):
        for stage, entry in steps.items():
            if isinstance(entry, dict):
                print(f"{stage}: {entry['status']} (attempt {entry['attempt']})")


def _print_final_report(run_dir: Path) -> None:
    manifest = get_status(run_dir)
    steps = manifest.get("steps", {})
    final = (
        steps.get("export-gapfilled-reference", {}) if isinstance(steps, dict) else {}
    )
    records = final.get("outputs", []) if isinstance(final, dict) else []
    report = next(
        (
            run_dir / str(item["path"])
            for item in records
            if isinstance(item, dict) and item.get("role") == "validation"
        ),
        None,
    )
    if report is None:
        gate = steps.get("gate-gapfill", {}) if isinstance(steps, dict) else {}
        records = gate.get("outputs", []) if isinstance(gate, dict) else []
        report = next(
            (
                run_dir / str(item["path"])
                for item in records
                if isinstance(item, dict) and item.get("role") == "gate"
            ),
            None,
        )
    gate_path = next(
        (
            run_dir / str(item["path"])
            for item in records
            if isinstance(item, dict) and item.get("role") in {"gate", "gapfill-gate"}
        ),
        None,
    )
    status = manifest["overall_status"]
    if gate_path is not None and gate_path.is_file():
        status = json.loads(gate_path.read_text(encoding="utf-8")).get(
            "status", status
        )
    print(f"final report: {report or run_dir}; status: {status}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(
        getattr(args, "verbose", 0), quiet=getattr(args, "quiet", False)
    )
    try:
        if args.command == "start":
            print(f"run started/resumed: {start(args.config)}")
        elif args.command in {
            "beta1",
            "beta2",
            "gapfill",
            "reference",
            "validate",
            "compare",
            "cell-specific",
            "pathway",
        }:
            from .config import load_workflow_config

            config = load_workflow_config(args.config)
            if config.workflow != args.command:
                raise ConfigError(
                    f"configuration selects workflow '{config.workflow}', "
                    f"not '{args.command}'"
                )
            run = start(args.config)
            print(f"run started/resumed: {run}")
            if args.command in {"gapfill", "reference"}:
                _print_final_report(run)
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
    ) as error:
        print(f"error: {error}", file=__import__("sys").stderr)
        if isinstance(error, RunLockedError):
            return 3
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
