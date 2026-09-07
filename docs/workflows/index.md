# THG workflows

Build a **THG reference model**, then build a **cell-specific model** from it.

| Main workflow | Use it when | Entry point |
| --- | --- | --- |
| [THG reference model](final-thg.md) | Build, validate, and release the canonical reference model | No end-to-end command yet |
| [Cell-specific model](cell-specific.md) | Derive a model from the THG reference model or a declared external GEM | `thg-run cell-specific CONFIG` |

## Construction and supporting workflows

Use these pages when you need to build the inputs, inspect a model, or manage a
run. You do not need to follow every page to create a cell-specific model from
an existing THG reference model.

| Workflow | Use it when | Entry point |
| --- | --- | --- |
| [THGβ1](beta1.md) | Curating an existing reference GEM | `thg-run beta1 configs/beta1.json` |
| [THGβ2](beta2.md) | Expanding GPR and localization branches | `thg-run beta2 configs/beta2.json` |
| [Gapfill](gapfill.md) | Gapfill an explicit model | `thg-run gapfill CONFIG` |
| [Reference](gapfill.md) | Run β1 → β2 → gapfill as one lineage | `thg-run reference CONFIG` |
| [Pathway](pathway.md) | Apply a versioned pathway definition to a GEM | `thg-run pathway CONFIG` |
| [Compare](../tools/analysis.md) | Produce a semantic comparison of two model inputs | `thg-run compare CONFIG` |
| [Human Database](human-database.md) | Reconstruct a model independently for optional integration before gapfill | `thg-run start configs/human-database.json` |
| [Validation](validation.md) | Running reusable checks or MEMOTE | `thg-run validate configs/validation.json` |
| [Runs](runs.md) | Resuming, auditing, or recovering a run | `thg-run resume RUN_DIR` |

The standalone `thg-compare` command remains useful for quick analysis; the
registered `compare` workflow records a reproducible comparison run.

The individual workflow pages document the required configuration sections
and the artifact and provenance flow. The [practical quickstart](../quickstart.md)
shows the repository's deterministic offline fixture workflow.

## Build the THG reference model

The full construction lineage is Reference GEM → THGβ1 → THGβ2 → optional
Human Database integration → required gapfill → THG candidate → final
validation → release export → THG reference model.

- Start with β1 when the input is a COBRA JSON or SBML reference GEM.
- Continue with β2 only after a verified β1 artifact, or declare and document
  an external β1-equivalent input.
- Reconstruct the Human Database independently when normalized pathway,
  metabolite, reaction, and gene records are available, then optionally
  integrate it between β2 and gapfill. Live collection requires an injected
  adapter and credentials.
- Always gapfill the canonical lineage, then call its output a THG candidate
  until it passes the final validation gate and export step.
- Use Validation or the analysis tools independently for quality checks and
  comparisons.

The maintained workflows are not an automatic reproduction of the publication
artifact. Preserve input checksums, service/cache provenance, configuration,
and release-gate results for any scientific claim.
