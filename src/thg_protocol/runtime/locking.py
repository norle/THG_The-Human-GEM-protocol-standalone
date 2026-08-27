"""Filesystem lock for one mutating command per run."""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class RunLockedError(RuntimeError):
    """Raised when another process owns a run lock."""


def _metadata(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"raw": value}
    except Exception:
        return {"raw": "unreadable lock metadata"}


@contextmanager
def acquire_run_lock(run_dir: Path) -> Iterator[None]:
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "run.lock"
    metadata = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RunLockedError(
            f"run is locked: {json.dumps(_metadata(path), sort_keys=True)}"
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def unlock_run(run_dir: str | Path, *, force: bool = False) -> None:
    directory = Path(run_dir).resolve()
    path = directory / "run.lock"
    if not path.exists():
        return
    metadata = _metadata(path)
    if not force:
        if metadata.get("hostname") != socket.gethostname():
            raise RunLockedError(
                "refusing to remove a lock owned by another host; use --force"
            )
        pid = metadata.get("pid")
        if not isinstance(pid, int) or pid <= 0:
            raise RunLockedError("lock PID is invalid; use --force to remove it")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            raise RunLockedError(
                "lock owner cannot be proven dead; use --force"
            ) from error
        else:
            raise RunLockedError(f"lock owner is still alive (pid {pid}); use --force")
    path.unlink()


__all__ = ["RunLockedError", "acquire_run_lock", "unlock_run"]
