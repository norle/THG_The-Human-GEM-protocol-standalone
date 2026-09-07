# THG reference model (`final-thg`) — validation and release

## Inputs

The canonical input is the required gapfill output, optionally enriched through
Human Database integration between β2 and gapfill. Preserve the input model,
integration evidence when used, and all checksums.

## Merge and validation

The registered `final-thg` workflow currently combines a two-branch merge,
final validation, and export. It runs `final-thg-merge-plan` → `final-thg-merge` →
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

In canonical construction, the post-gapfill model is a **THG candidate** until
the final validation gate passes. Stage-level validation at β1, β2,
Human Database reconstruction, and gapfill supplies evidence to this gate but
does not itself confer THG reference-model status.

Review collisions, retained stoichiometry, isolated-metabolite policy,
connectivity, formula/charge balance, configured solver checks, and optional
MEMOTE output. Task results are recorded separately from structural and MEMOTE
results. The configured THG gate status, not a MEMOTE score, determines
acceptance. Use the [Validation workflow](validation.md) for the three
validation interfaces and their boundaries. Only after this validation gate
passes, the model is **validated**. A registered promotion and export handoff is
still required before that post-gapfill candidate can be called **released**.
The existing `export-final-thg` stage belongs to the standalone compatibility
route described below and does not provide that handoff.

## Handoffs and current boundary

`thg-run reference CONFIG` supplies the supported β1 → β2 → gapfill handoff
and exports a post-gapfill THG candidate. `thg-run validate CONFIG` can run a
final profile against that candidate and records its validation report, but it
does not promote or export a THG reference model. The registered `final-thg`
workflow accepts β2 and Human Database artifacts for its own merge immediately
before validation, so it is not a post-gapfill-candidate entry point. A
registered handoff from `reference` to final validation and release is an
implementation gap; this documentation does not imply one exists.

## Standalone compatibility workflow

The registered `final-thg` workflow uses `thg-run start` with
`workflow: "final-thg"`; there is
no separate `thg-run final-thg` command. The configuration selects input
artifacts, merge policy, validation profile, and output directory.
Use `thg-run start configs/final-thg.json` for the resumable route; it resolves
the base and Human Database inputs through their recorded run artifact
references. This bundled merge route remains independently usable, but the
canonical sequence performs optional integration before required gapfill and
then applies the final gate to the resulting candidate.

Because this route merges immediately before validation and does not perform
required gapfill, its export is not the canonical released THG reference model.
Neither its name nor its validation result proves exact publication-artifact
reconstruction without separate evidence.

Canonical APIs: [`generate_merge_plan`][thg_protocol.merge.generate_merge_plan],
[`apply_merge_plan`][thg_protocol.merge.apply_merge_plan],
[`merge_models`][thg_protocol.merge.merge_models], and
[`validate_merged_model`][thg_protocol.merge.validate_merged_model].
