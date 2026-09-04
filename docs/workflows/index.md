# THG workflows

The canonical construction lineage is Reference GEM → THGβ1 → THGβ2 →
optional Human Database integration → required gapfill → THG candidate →
final validation/release gate → Final THG → cell-specific models. The Human
Database can be reconstructed independently, while β2 normally consumes a
released β1 artifact.

| Workflow | Use it when | Main entry point |
| --- | --- | --- |
| [THGβ1](beta1.md) | Curating an existing reference GEM | `thg-run beta1 configs/beta1.json` |
| [THGβ2](beta2.md) | Expanding GPR and localization branches | `thg-run beta2 configs/beta2.json` |
| [Gapfill](gapfill.md) | Create a validated reference from an explicit model | `thg-run gapfill CONFIG` |
| [Reference](gapfill.md) | Run β1 → β2 → gapfill as one lineage | `thg-run reference CONFIG` |
| [Cell-specific](cell-specific.md) | Reduce a validated Final THG, or an explicitly declared external GEM | `thg-run cell-specific CONFIG` |
| [Pathway](pathway.md) | Apply a versioned pathway definition to a GEM | `thg-run pathway CONFIG` |
| [Compare](../tools/analysis.md) | Produce a semantic comparison of two model inputs | `thg-run compare CONFIG` |
| [Human Database](human-database.md) | Reconstruct a model independently for optional integration before gapfill | `thg-run start configs/human-database.json` |
| [Final THG](final-thg.md) | Apply the final validation/release gate to a THG candidate | `thg-run start configs/final-thg.json` |
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
- Reconstruct the Human Database independently when normalized pathway,
  metabolite, reaction, and gene records are available, then optionally
  integrate it between β2 and gapfill. Live collection requires an injected
  adapter and credentials.
- Always gapfill the canonical lineage, then call its output a THG candidate
  until it passes the final validation/release gate.
- Generate cell-specific models from the validated Final THG. Use an explicitly
  declared external GEM only for standalone cell-specific work.
- Use Validation or the analysis tools independently for quality checks and
  comparisons.

The maintained workflows are not an automatic reproduction of the publication
artifact. Preserve input checksums, service/cache provenance, configuration,
and release-gate results for any scientific claim.
