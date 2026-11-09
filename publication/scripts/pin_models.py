"""Pin publication model files without loading or modifying them.

Regenerate: python publication/scripts/pin_models.py
Missing/deferred models remain explicit; this inventory is not validation.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = [
    (
        "Human1",
        "models/Human-GEM_2022-06-21.xml",
        "2022-06-21 control; legacy commits fad16c2, 3ee4f60, 5ff6f1d, bbcae83; "
        "historical byte comparison recorded in publication plan",
    ),
    (
        "Human Database 2023",
        "models/Human Database.xml",
        "2023-02-25 legacy database; provenance comparison in publication plan; "
        "deferred benchmark",
    ),
    (
        "Human-GEM 2.1.1 with MAR20193 blocked",
        "runs/human211-patched/Human_211_patched.xml",
        "publication/scripts/patch_human211.py; inputs/models/Human_211.xml; "
        "MAR20193 bounds [0,0]; user decision",
    ),
    (
        "Human-GEM 2.1.1 unpatched",
        "inputs/models/Human_211.xml",
        "2.1.1 identity supplied by user; context for baseline intervention; "
        "download date/source tag not recorded",
    ),
    (
        "Human2 older release",
        "inputs/models/Human2.xml",
        "Believed 2.0 by user; version unverified; optional comparison deferred",
    ),
    (
        "THG-2023",
        "models/THG-2023-02-25.xml",
        "2023-02-25 legacy model; provenance comparison in publication plan; "
        "benchmark deferred",
    ),
    (
        "Legacy THG beta1",
        "models/THG-beta1.xml",
        "Legacy intermediate; benchmark deferred",
    ),
    (
        "Legacy THG beta2",
        "models/THG-beta2.xml",
        "Legacy intermediate; benchmark deferred",
    ),
]


MODELS.extend(
    [
        (
            "Archived standalone beta1 before shared-ID safeguard",
            "runs/thg-ws1-a/artifacts/export-beta1/attempt-0001/thg-beta1-candidate.json",
            "Historical numerical-failure and identity measurement; not a final model",
        ),
        (
            "Archived standalone beta2 passing control",
            "runs/thg-ws1-a/artifacts/export-beta2/attempt-0002/thg-beta2-candidate.json",
            "Numerical negative control; not a final model",
        ),
    ]
)


def pin(label, relative, provenance):
    path = ROOT / relative
    return {
        "label": label,
        "path": relative,
        "provenance": provenance,
        "status": "present" if path.is_file() else "missing",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        if path.is_file()
        else None,
    }


def main():
    rows = [pin(*entry) for entry in MODELS]
    for run in ("thg-ws1-a", "thg-ws1-b", "thg-ws1-c"):
        manifest_path = ROOT / "runs" / run / "manifest.json"
        if not manifest_path.is_file():
            rows.append({"label": run, "status": "not built", "sha256": None})
            continue
        manifest = json.loads(manifest_path.read_text())
        for stage in (
            "export-beta1",
            "export-beta2",
            "export-gapfilled-reference",
            "export-reference",
        ):
            state = manifest["steps"].get(stage, {})
            for artifact in state.get("outputs", []):
                if (
                    artifact["path"].endswith((".xml", ".json"))
                    and artifact["role"] == "model"
                ):
                    row = pin(
                        f"{run}:{stage}",
                        f"runs/{run}/{artifact['path']}",
                        f"{manifest_path.relative_to(ROOT)}; "
                        f"attempt {state['attempt']}; "
                        f"stage status {state['status']}; "
                        "candidate, not yet final-gated",
                    )
                    row["matches_ledger"] = row["sha256"] == artifact["sha256"]
                    rows.append(row)
    (ROOT / "publication/models.json").write_text(json.dumps(rows, indent=2) + "\n")
    assert all(row.get("matches_ledger", True) for row in rows), (
        "model differs from run ledger"
    )


if __name__ == "__main__":
    main()
