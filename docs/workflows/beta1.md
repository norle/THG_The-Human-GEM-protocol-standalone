# THGβ1 — Curate a reference GEM

## Workflow scope

THGβ1 performs an offline, proposal-driven curation pass on a caller-owned COBRA
JSON or SBML model. It inventories the model, normalizes
identities and GPRs supplied by the caller, audits formula and charge balance,
applies only configured corrections, consolidates exact duplicates, and
writes a reproducible artifact bundle.

## Run with Python

```python
from thg_protocol.curation.beta1 import run_beta1

result = run_beta1(
    "input-model.json",
    "runs/example-beta1",
    mode="report-only",
)
print(result["outputs"]["validation"])
```

`apply-all` is the default. `report-only` leaves the copied model unchanged,
and `user-approved-only` applies only proposals referenced by a decisions
JSONL file when using the workflow runner. Explicit corrections are supplied
as mappings, for example:

```python
run_beta1(
    "input-model.json",
    "runs/example-beta1",
    corrections={"RXN": {"h_c": 1.0}},
    formula_corrections={"met_c": "C6H12O6"},
    charge_corrections={"met_c": 0},
)
```

- Complex subunit evidence is stored under `thg_s_gpr` without changing Boolean GPRs.
- Ambiguous identities and unresolved balance cases remain in reports.
- Cross-database metabolite references are preserved together; one canonical
  reference is selected for reporting, while conflicting IDs within the same
  namespace remain unresolved.
- Generic groups, glycans, and polymers require an explicit `formula_policy`.
- Reaction conflicts and reversed matches create annotation-only proposals.
- Without service evidence, the workflow uses existing model annotations.
- `run_flux_consistency: true` adds a diagnostic blocked-reaction report.

API details: [`run_beta1`][thg_protocol.curation.beta1.run_beta1],
[`inventory_model`][thg_protocol.curation.beta1.inventory_model],
[`audit_model`][thg_protocol.curation.beta1.audit_model], and
[`generate_balance_proposals`][thg_protocol.curation.beta1.generate_balance_proposals].
S-GPR metadata uses
[`serialize_s_gpr`][thg_protocol.curation.beta1.serialize_s_gpr].

After a sanctioned run passes the gate, use
[`release_beta1`][thg_protocol.curation.beta1.release_beta1] to promote the
candidate files to `thg-beta1.json` and `thg-beta1.xml`.

## Configuration and CLI

```json
{
  "format_version": 2,
  "workflow": "beta1",
  "run": {"name": "example-beta1", "output_dir": "../runs/example-beta1"},
  "beta1": {
    "n_jobs": 1,
    "input_model": "../inputs/models/input-model.json",
    "mode": "apply-all",
    "balance_strategy": "explicit-only"
  }
}
```

Save it as `configs/beta1.json` and run it with `thg-run beta1
configs/beta1.json`. A configured model run executes the
explicit 16-stage scientific DAG, keeping evidence, proposals, application,
cleanup, and validation as separate resumable stages. A beta1 run exports
JSON/SBML candidates, a semantic signature, validation, ledger, and inventory
artifacts under the run directory. It also writes an explicit
`beta1-decisions.jsonl` artifact, including an empty record set when no
decision file is configured. Set `n_jobs` above 1 to parallelize the
CPU-bound per-metabolite and per-reaction analysis; mutation and solver work
remains serial. The input path is never overwritten.

## Candidate and release-gate lifecycle

Runs produce candidate artifacts. `beta1_release_gate` checks the required
validation and provenance conditions; `release_beta1` then promotes the bundle
to `thg-beta1.json` and `thg-beta1.xml`. A run does not automatically make
every candidate file a released artifact.

## Evidence boundary

The curation core accepts normalized evidence and injected mappings; it does
not silently call live services. Service-backed evidence should be cached in
the shared evidence format before proposals are generated. A sanctioned
human-reference fixture, solver-backed validation when enabled, and the final
THGβ1 release gate are required before publishing the β1 label. The maintained fixture in
`tests/fixtures/beta1/sanctioned_human_reference.json` is the sanctioned input
for the current release; this is not a claim of publication-artifact
reproduction.
