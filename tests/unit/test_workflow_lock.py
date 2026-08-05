from __future__ import annotations

import json
import socket

import pytest

from thg_protocol.workflow.lock import (
    RunLockedError,
    acquire_run_lock,
    unlock_run,
)


def test_run_lock_is_exclusive_and_cleans_up_after_context(tmp_path):
    run_dir = tmp_path / "run"

    with acquire_run_lock(run_dir):
        assert (run_dir / "run.lock").is_file()
        with pytest.raises(RunLockedError, match="run is locked"):
            with acquire_run_lock(run_dir):
                pass

    assert not (run_dir / "run.lock").exists()


def test_unlock_removes_a_lock_after_owner_is_proven_dead(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock_path = run_dir / "run.lock"
    lock_path.write_text(
        json.dumps(
            {
                "pid": 424242,
                "hostname": socket.gethostname(),
                "started_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    def dead_process(pid, signal):
        del pid, signal
        raise ProcessLookupError

    monkeypatch.setattr("thg_protocol.workflow.lock.os.kill", dead_process)
    unlock_run(run_dir)

    assert not lock_path.exists()


def test_force_unlock_removes_malformed_lock(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock_path = run_dir / "run.lock"
    lock_path.write_text("not-json", encoding="utf-8")

    unlock_run(run_dir, force=True)

    assert not lock_path.exists()
