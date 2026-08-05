# Merge and validate

!!! warning "Scope and evidence"
    Identifier-based merge and local structural reports are Implemented at
    their documented boundaries. A publication-compatible convergence loop is
    Not implemented; MEMOTE is an External integration and essential tasks are
    Archived.

## Inputs from both branches

Keep the reference branch output (conceptually THGβ2) and the independently
constructed Human Database/network unchanged. They must be readable as COBRA
JSON or SBML, use compatible identifiers and compartments, and have documented
model versions. Do not merge a working copy whose provenance is unknown.

## What the current merge API does

[`merge_models`][thg_protocol.merge.merge_models] copies the base model and
adds incoming metabolites and reactions by identifier. Overlaps retain base
stoichiometry and bounds; non-empty incoming names, annotations, and missing
GPRs enrich the base object. Inputs are not mutated. The returned
[`MergeReport`][thg_protocol.merge.MergeReport] records added and overlapping
objects, isolated-metabolite removal, and the optional output path.

```python
from cobra.io import load_json_model
from thg_protocol.merge import merge_models

base = load_json_model("results/reference/THG-beta2-like.json")
incoming = load_json_model("results/database/human-network.json")
merged, report = merge_models(
    base,
    incoming,
    output_path="results/merge/candidate-thg.json",
    remove_isolated_metabolites=False,
)
print(report)
```

### Intentional migration difference

The current API is not a similarity/identity-aware reproduction of every
historical merge heuristic. Its retained-base behavior is deliberate and
covered by the [API contracts](../api-contracts.md). Treat overlap counts and
retained stoichiometry as review items; use comparison for a separate diff.

## Separate validation activities

Do not conflate the following activities:

| Activity | Current boundary | Evidence/output |
| --- | --- | --- |
| Structural merge | Supported package API | `MergeReport` and selected JSON/SBML output |
| Model comparison/diff | Supported package operation | comparison mapping and optional CSVs |
| Network connectivity | Supported package analysis | component mapping/report |
| Reaction formula balance | Supported local analysis | `reaction_balance` and `unbalanced_reactions` |
| Stoichiometric consistency | Supported building-block checks; solver needs depend on check | consistency result saved by caller |
| MEMOTE quality assessment | External command | HTML report from `memote run` |
| Essential metabolic tasks | Archived historical workflow unless separately replaced | record status; do not infer success from MEMOTE |

## Validation sequence

1. Review `MergeReport`, collisions, retained stoichiometry, and any isolated
   metabolite removal decision.
2. Run [connectivity and formula checks](../workflows/network-analysis.md),
   saving JSON reports and the exact model checksum.
3. Run solver-backed stoichiometric checks only in the configured environment;
   record solver and version.
4. Install and run MEMOTE separately when required:

   ```bash
   python -m pip install 'memote'
   memote run --filename results/validation/memote.html results/merge/candidate-thg.json
   ```

5. Record essential-task validation as Archived when using the historical task
   implementation; a green structural or MEMOTE report is not a task result.
6. Repeat the merge/check cycle manually if scientific review requires an
   iteration. The package has no maintained convergence orchestrator.

## Acceptance checklist

- Both branch inputs are preserved unchanged.
- The merge report was reviewed.
- Identifier collisions and retained stoichiometry are understood.
- The isolated-metabolite removal decision is recorded.
- Connectivity and balance reports are saved.
- Stoichiometric-consistency results are saved with solver metadata.
- A MEMOTE report is saved when the external tool is used.
- Essential-task status is recorded separately.
- The final model is serialized to a caller-selected path.
- Package version, input model versions/checksums, service/cache dates, solver,
  and configuration are recorded.

The resulting file is a validated candidate or final THG model only to the
extent that the documented scientific review and current implementation-status
limitations support that claim.
