# THGβ1 — Curate a reference GEM

## What this workflow does

THGβ1 inventories and curates a caller-owned COBRA JSON or SBML reference GEM
through explicit evidence, proposals, decisions, mutation, and validation.

The β1 core takes a caller-owned COBRA JSON or SBML model and performs an
offline, proposal-driven curation pass. It inventories the model, normalizes
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

Optional complex subunit evidence is kept as a separate, deterministic S-GPR
annotation and does not alter the Boolean GPR. For example, the registered
workflow accepts `subunit_stoichiometry: {"RXN": {"ENSG...": 2}}` and records
the canonical AST under `thg_s_gpr`.

No arbitrary numerical balancing is inferred. Ambiguous identity matches and
unresolved balance cases are retained in reports.

Generic groups, glycans, and polymers are not silently treated as ordinary
chemical formulas. Their audit class is recorded, and an explicit
`formula_policy` such as `{"glycan": "exclude"}` is required to classify that
case as intentionally excluded. Reaction identity conflicts produce
annotation-only flag proposals; they never silently change stoichiometry or
bounds.

When no service-backed evidence is configured, the registered workflow uses
existing model annotations as offline evidence. Reversed reaction matches are
recorded as annotation-only directionality proposals; stoichiometry and bounds
are not changed automatically. Duplicate cleanup uses deterministic IDs and
merges secondary annotations onto the retained object.

The registered `beta1` section also accepts `run_flux_consistency: true` for an
optional solver-backed blocked-reaction report. This report is diagnostic and
does not by itself satisfy the release gate.

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
  "run": {"name": "example-beta1", "output_dir": "runs/example-beta1"},
  "beta1": {
    "input_model": "input-model.json",
    "mode": "apply-all",
    "balance_strategy": "explicit-only"
  }
}
```

Run it with `thg-run beta1 config.json`. A configured model run executes the
explicit 16-stage scientific DAG, keeping evidence, proposals, application,
cleanup, and validation as separate resumable stages. A beta1 run exports
JSON/SBML candidates, a semantic signature, validation, ledger, and inventory
artifacts under the run directory. It also writes an explicit
`beta1-decisions.jsonl` artifact, including an empty record set when no
decision file is configured. The input path is never overwritten.

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
