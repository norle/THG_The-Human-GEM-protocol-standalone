# Phase 0 workflow foundations

The workflow registry selects a DAG from the top-level `workflow` key and owns
its manifest, dependency checks, and resume behavior.

The registered workflows are `beta1`, `beta2`, `validate`, and `compare`.
`beta1` and `beta2` have separate scientific DAGs when model inputs are
configured; the shorter DAGs remain available as orchestration fixtures. A
release label still requires the gates in the functional implementation plan.

## Format-2 configuration

Save this example as `configs/beta2-fixture.json`:

```json
{
  "format_version": 2,
  "workflow": "beta2",
  "run": {
    "name": "beta2-fixture",
    "output_dir": "../runs/beta2-fixture"
  },
  "beta2": {
    "upstream": [
      {
        "run_dir": "../runs/beta1",
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
thg-run beta1 configs/beta1.json
thg-run beta2 configs/beta2.json
thg-run validate configs/validation.json
thg-run compare configs/comparison.json
```

Use `thg-run resume RUN_DIR --force-step STAGE_ID` to invalidate the selected
stage and its descendants. Existing successful attempt directories remain
untouched.
