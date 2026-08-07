# Final THG — Merge and validate

## Inputs

Provide a verified β2/reference branch and an independently reconstructed Human
Database branch as COBRA JSON or SBML. Preserve both inputs and their checksums.

## Merge and repair

`generate_merge_plan` creates a reviewable semantic plan. Matching requires
compatible identifiers and compartments; ambiguous or conflicting matches stay
unresolved. `apply_merge_plan` applies approved decisions to a private copy.
The retained-base merge policy preserves base stoichiometry and bounds while
allowing non-empty annotations and missing GPRs to enrich it.

```python
from thg_protocol.merge import apply_merge_plan, generate_merge_plan

plan = generate_merge_plan("runs/beta2/model.json", "runs/human-db/network.json")
merged, report = apply_merge_plan(plan, output_path="runs/final-thg/candidate.json")
print(report)
```

## Validation and acceptance

Review collisions, retained stoichiometry, isolated-metabolite policy,
connectivity, formula/charge balance, configured solver checks, and optional
MEMOTE output. Task results are recorded separately from structural and MEMOTE
results. Use the [Validation workflow](validation.md) for the three validation
interfaces and their boundaries.

## CLI and configuration

Final THG currently uses `thg-run start` with `workflow: "final-thg"`; there is
no separate `thg-run final-thg` command. The configuration selects input
artifacts, merge policy, repair bounds, validation profile, and output directory.

The output is a candidate/final artifact only to the extent that the documented
scientific review and release criteria pass. It must not be described as an
exact publication-artifact reconstruction without separate evidence.

Canonical APIs: [`generate_merge_plan`][thg_protocol.merge.generate_merge_plan],
[`apply_merge_plan`][thg_protocol.merge.apply_merge_plan],
[`merge_models`][thg_protocol.merge.merge_models], and
[`validate_merged_model`][thg_protocol.merge.validate_merged_model].
