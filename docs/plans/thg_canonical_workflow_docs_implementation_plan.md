# THG Canonical Workflow Documentation Update Plan

> Historical terminology note: this superseded plan intentionally uses “Final
> THG,” the public artifact name at the time it was written.

## Goal

Update the THG documentation so the canonical model-construction flow is:

```text
Reference GEM
→ THGβ1
→ THGβ2
→ optional Human Database integration
→ required Gapfill
→ THG candidate
→ Final validation / release gate
→ Final THG
→ Cell-specific model(s)
```

Human Database reconstruction, standalone gapfill, standalone validation, and cell-specific workflows may still be run independently, but the documentation should clearly distinguish those uses from the canonical THG pipeline.

## Implementation

1. **Update the main workflow overview**
   - Replace the workflow diagram in `docs/index.md`.
   - Add a short explanation of the canonical pipeline versus standalone workflows.
   - Make gapfill mandatory in the canonical pipeline.
   - Place cell-specific model generation after validated Final THG.

2. **Clarify Human Database terminology**
   - Keep **Human Database reconstruction** as an independent workflow.
   - Introduce **Human Database integration** as the optional enrichment step between β2 and gapfill.
   - Update `docs/workflows/human-database.md` and `docs/workflows/final-thg.md` accordingly.

3. **Update gapfill documentation**
   - Remove statements that gapfill is optional in the canonical THG protocol.
   - Preserve standalone gapfill as an independently usable tool.
   - Update:
     - `docs/workflows/gapfill.md`
     - `docs/workflows/beta2.md`
     - `docs/tools/pathways-gapfill.md`

4. **Clarify validation and Final THG**
   - Distinguish stage-level validation from the final validation/release gate.
   - Refer to the model before final acceptance as a **THG candidate**.
   - Reserve **Final THG** for the model that has passed the final release gate.
   - Align this terminology with the validation-quality-report plan.

5. **Update cell-specific documentation**
   - Make validated Final THG the recommended/canonical parent model.
   - Retain support for explicitly declared external GEMs as a standalone mode.
   - Update `docs/workflows/cell-specific.md`.

6. **Update workflow and CLI reference pages**
   - Reword `reference` as the core β1 → β2 → gapfill path unless it is extended to include optional Human Database integration.
   - Update `docs/workflows/index.md`, `docs/reference/cli.md`, and `docs/reference/io-and-config.md`.

## Consistency check

After editing:

- Search the documentation for statements describing gapfill as optional.
- Search for diagrams or text showing Human Database merging only at Final THG.
- Search for cell-specific models branching directly from the original Reference GEM.
- Verify that “Final THG” consistently means a model that has passed the final validation/release gate.
- Run `mkdocs build --strict` and the documentation tests.
