# Final THG — Candidate validation and release

## Inputs

The canonical input is the required gapfill output, optionally enriched through
Human Database integration between β2 and gapfill. Preserve the input model,
integration evidence when used, and all checksums.

## Merge and validation

The registered `final-thg` workflow currently combines a two-branch merge and
final acceptance. It runs `final-thg-merge-plan` → `final-thg-merge` →
`validate-final-thg` → `export-final-thg`. Because that command merges
immediately before validation, using it with separate β2 and Human Database
inputs is a standalone combined workflow, not the canonical ordering. In the
canonical pipeline, use the same merge-plan APIs for optional Human Database
integration before gapfill, then send the gapfilled THG candidate to the final
gate. `generate_merge_plan` creates a reviewable semantic plan. Matching requires
compatible identifiers and compartments; ambiguous or conflicting matches stay
unresolved. `apply_merge_plan` applies approved decisions to a private copy.
The retained-base merge policy preserves base stoichiometry and bounds while
allowing non-empty annotations and missing GPRs to enrich it.

```python
from thg_protocol.merge import apply_merge_plan, generate_merge_plan

plan = generate_merge_plan(
    "inputs/models/beta2.json", "inputs/models/human-database.json"
)
merged, report = apply_merge_plan(plan, output_path="runs/final-thg/candidate.json")
print(report)
```

## Validation and acceptance

The merged or non-integrated, gapfilled model is a **THG candidate** until the
final validation/release gate passes. Stage-level validation at β1, β2,
Human Database reconstruction, and gapfill supplies evidence to this gate but
does not itself confer the Final THG name.

Review collisions, retained stoichiometry, isolated-metabolite policy,
connectivity, formula/charge balance, configured solver checks, and optional
MEMOTE output. Task results are recorded separately from structural and MEMOTE
results. The configured THG gate status, not a MEMOTE score, determines
acceptance. Use the [Validation workflow](validation.md) for the three
validation interfaces and their boundaries. Only after this release gate
passes may the promoted artifact be called **Final THG**.

## CLI and configuration

Final THG currently uses `thg-run start` with `workflow: "final-thg"`; there is
no separate `thg-run final-thg` command. The configuration selects input
artifacts, merge policy, validation profile, and output directory.
Use `thg-run start configs/final-thg.json` for the resumable route; it resolves
the base and Human Database inputs through their recorded run artifact
references. This bundled merge route remains independently usable, but the
canonical sequence performs optional integration before required gapfill and
then applies the final gate to the resulting candidate.

Before acceptance the output is a THG candidate. After the documented release
criteria pass, it is a Final THG; neither name proves exact
publication-artifact reconstruction without separate evidence.

Canonical APIs: [`generate_merge_plan`][thg_protocol.merge.generate_merge_plan],
[`apply_merge_plan`][thg_protocol.merge.apply_merge_plan],
[`merge_models`][thg_protocol.merge.merge_models], and
[`validate_merged_model`][thg_protocol.merge.validate_merged_model].
