from __future__ import annotations

from thg_protocol.workflow.hashing import (
    artifact_record,
    sha256_file,
    sha256_json,
    verify_artifact,
)


def test_hashing_is_deterministic_and_streamed_file_hash_matches(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("hello", encoding="utf-8")
    assert (
        sha256_file(path)
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    assert sha256_json({"a": 1, "b": 2}) == sha256_json({"b": 2, "a": 1})


def test_artifact_verification_catches_mutation_and_escape(tmp_path):
    run_dir = tmp_path / "run"
    artifact = run_dir / "artifacts" / "one.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("one", encoding="utf-8")
    record = artifact_record("result", artifact, run_dir)
    assert verify_artifact(record, run_dir)
    artifact.write_text("two", encoding="utf-8")
    assert not verify_artifact(record, run_dir)
    assert not verify_artifact({**record, "path": "../outside"}, run_dir)
