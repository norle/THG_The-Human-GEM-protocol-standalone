# Phase 0 workflow foundations

Phase 0 adds a format-2 registry without breaking the existing format-1
resumable runner. Format 1 remains the compatibility path for the historical
`reference → database → merge → validation → memote` manifest. Format 2 is
selected explicitly with a top-level `workflow` key and uses the registered
DAG for its manifest, dependency checks, and resume behavior.

The maintained fixture workflows are `beta1`, `beta2`, `validate`, and
`compare`. They exercise orchestration contracts only; they do not claim to be
scientific THGβ1 or THGβ2 releases. A release label requires the gates in the
functional implementation plan.

## Format-2 configuration

```json
{
  "format_version": 2,
  "workflow": "beta2",
  "run": {
    "name": "beta2-fixture",
    "output_dir": "runs/beta2-fixture"
  },
  "beta2": {
    "upstream": [
      {
        "run_dir": "../beta1-fixture",
        "stage_id": "beta1-export",
        "role": "model"
      }
    ]
  }
}
```

Only the section for the selected workflow is accepted. Artifact references
must name a run directory, stage ID, and unique artifact role. The runner
requires the upstream stage to be completed and verifies the recorded output
checksum before a downstream stage runs. It records the upstream artifact and
manifest fingerprints in the downstream stage output.

## Shared records

- Stage contracts are validated machine-readable boundaries covering inputs,
  outputs, mutation, side effects, provenance, and validation.
- Evidence is append-only JSONL. Raw responses can be stored in a
  SHA-256-addressed cache, while normalized results carry their own checksum.
- Proposals are generated independently of application mode. `apply-all`,
  `report-only`, and `user-approved-only` share proposal IDs; decisions support
  approval, rejection, replacement, and deferral. The JSONL change ledger is
  idempotent on resume.
- Generated IDs are derived from object type, source identity, compartment,
  and the versioned ID policy. Mappings are persisted and collisions fail.

Use the public aliases for registered starts:

```bash
thg-run beta1 path/to/beta1.json
thg-run beta2 path/to/beta2.json
thg-run validate path/to/validation.json
thg-run compare path/to/comparison.json
```

Use `thg-run resume RUN_DIR --force-step STAGE_ID` to invalidate the selected
stage and its descendants. Existing successful attempt directories remain
untouched.
