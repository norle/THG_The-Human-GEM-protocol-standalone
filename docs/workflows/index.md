# THG workflows

THG workflows move from a reference model and evidence to reviewable model
artifacts. The branches are composable: the Human Database can be built
independently, while β2 normally consumes a released β1 artifact.

| Workflow | Use it when | Main entry point |
| --- | --- | --- |
| [THGβ1](beta1.md) | Curating an existing reference GEM | `thg-run beta1 configs/beta1.json` |
| [THGβ2](beta2.md) | Expanding GPR and localization branches | `thg-run beta2 configs/beta2.json` |
| Gapfill | Create a validated reference from an explicit model | `thg-run gapfill CONFIG` |
| Reference | Run β1 → β2 → gapfill as one lineage | `thg-run reference CONFIG` |
| Cell-specific | Reduce an explicit GEM from normalized expression evidence | `thg-run cell-specific CONFIG` |
| Pathway | Apply a versioned pathway definition to a GEM | `thg-run pathway CONFIG` |
| Compare | Produce a semantic comparison of two model inputs | `thg-run compare CONFIG` |
| [Human Database](human-database.md) | Reconstructing from normalized records | `thg-run start configs/human-database.json` |
| [Final THG](final-thg.md) | Merging branches and validating a candidate | `thg-run start configs/final-thg.json` |
| [Validation](validation.md) | Running reusable checks or MEMOTE | `thg-run validate configs/validation.json` |
| [Runs](runs.md) | Resuming, auditing, or recovering a run | `thg-run resume RUN_DIR` |

The standalone `thg-compare` command remains useful for quick analysis; the
registered `compare` workflow records a reproducible comparison run.

The individual workflow pages document the required configuration sections
and the artifact and provenance flow. The [practical quickstart](../quickstart.md)
shows the repository's deterministic offline fixture workflow.

## Which workflow should I use?

- Start with β1 when the input is a COBRA JSON or SBML reference GEM.
- Continue with β2 only after a verified β1 artifact, or declare and document
  an external β1-equivalent input.
- Use Human Database for normalized pathway, metabolite, reaction, and gene
  records. Live collection requires an injected adapter and credentials.
- Use Final THG when both branches are available and you need an explicit merge
  plan and validation reports.
- Use Validation or the analysis tools independently for quality checks and
  comparisons.

The maintained workflows are not an automatic reproduction of the publication
artifact. Preserve input checksums, service/cache provenance, configuration,
and release-gate results for any scientific claim.
