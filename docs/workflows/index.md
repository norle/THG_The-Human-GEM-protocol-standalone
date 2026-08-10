# THG workflows

THG workflows move from a reference model and evidence to reviewable model
artifacts. The branches are composable: the Human Database can be built
independently, while β2 normally consumes a released β1 artifact.

| Workflow | Use it when | Main entry point |
| --- | --- | --- |
| [THGβ1](beta1.md) | Curating an existing reference GEM | `thg-run beta1 config.json` |
| [THGβ2](beta2.md) | Expanding GPR and localization branches | `thg-run beta2 config.json` |
| [Human Database](human-database.md) | Reconstructing from normalized records | `thg-run start config.json` with `workflow: "human-database"` |
| [Final THG](final-thg.md) | Merging branches and validating a candidate | `thg-run start config.json` with `workflow: "final-thg"` |
| [Validation](validation.md) | Running reusable checks or MEMOTE | `thg-run validate config.json` |
| [Runs](runs.md) | Resuming, auditing, or recovering a run | `thg-run resume RUN_DIR` |

Comparison is a cross-workflow tool; use [model comparison and analysis](../tools/analysis.md).

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
  plan, bounded repair, and validation reports.
- Use Validation or the analysis tools independently for quality checks and
  comparisons.

The maintained workflows are not an automatic reproduction of the publication
artifact. Preserve input checksums, service/cache provenance, configuration,
and release-gate results for any scientific claim.
