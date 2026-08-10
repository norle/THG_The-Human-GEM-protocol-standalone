# Runnable examples

This directory contains small, offline-first recipes for the maintained THG
workflow entry points. They are intended as starting points for users and as
smoke tests for the documented interfaces; they are not research-quality human
GEM reconstruction inputs.

Run the complete registered-workflow set from the repository root:

```bash
./examples/run_offline_workflows.sh
```

The script runs:

| Example | Command | Purpose |
| --- | --- | --- |
| β1 | `scripts/run_beta1.sh` | Curate a caller-owned reference model |
| β2 | `scripts/run_beta2.sh` | Expand a declared β1-equivalent model |
| Human Database | `scripts/run_human_database.sh` | Reconstruct a model from normalized records |
| Final THG | `scripts/run_final_thg.sh` | Merge two model branches and validate the candidate |
| Validation | `scripts/run_validation.sh` | Run the structural validation workflow |
| Comparison | `scripts/run_compare.sh` | Exercise the registered comparison run |

Generated run directories are written under `examples/output/`, which is
ignored by Git. Delete that directory when you want a clean rerun, or use
`thg-run resume` to continue an interrupted run.

The individual configurations live in [`configs/`](configs/). Their input
paths point at the stable toy fixtures in `docs/examples/`, so they can be
inspected or copied as templates. Run configurations from the repository root;
the workflow loader resolves input paths relative to each configuration file.
The Final THG template uses `structural-fast` because the toy models do not
represent a release-quality GEM; use `final-standard` for a real candidate.

Each workflow can also be run independently with its script in
`examples/scripts/`.

Python equivalents use the same configurations through the canonical runner
API:

```bash
python examples/scripts/run_beta1.py
python examples/scripts/run_beta2.py
python examples/scripts/run_human_database.py
python examples/scripts/run_final_thg.py
python examples/scripts/run_validation.py
python examples/scripts/run_compare.py
```

For lower-level Python APIs—reconstruction, pathway implementation, analysis,
and model comparison—run:

```bash
python examples/scripts/run_api_examples.py
```

These examples deliberately avoid network services, credentials, MEMOTE, and
solver-backed checks. Those capabilities have separate workflow guides and
must be enabled explicitly in a user's configuration.
