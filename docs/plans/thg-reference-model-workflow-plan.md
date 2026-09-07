# THG Reference Model Workflow Plan

## Goal

Organize the user-facing documentation around two outcomes:

```text
Build the THG reference model → Build a cell-specific model
```

Use **THG reference model** as the public name for the validated, released
reference artifact currently called **Final THG**. Treat `final-thg` as a
compatibility identifier until a separate migration is justified.

## Vocabulary

| Concept | User-facing term | Compatibility identifier |
| --- | --- | --- |
| Model being prepared for release | THG candidate | Existing names unchanged |
| Validated and released model | THG reference model | `final-thg` |
| Model derived using contextual evidence | Cell-specific model | `cell-specific` |
| Acceptance state | Candidate → validated → released | Existing stage IDs unchanged |

Avoid **final** as a permanent model name. It may still describe the final
validation stage in a sequence.

Define the acceptance states against the existing validation/release contract:

- **Candidate**: a model awaiting acceptance by the final THG gate. Passing
  β1, β2, reconstruction, or gapfill checks does not confer reference-model status.
- **Validated**: the post-gapfill candidate has passed the configured final THG
  gate; stage-level validation alone does not satisfy this state.
- **Released**: the validated artifact has met the existing release criteria.
  Document whether passing the final gate also constitutes release or whether
  an existing export/promotion step is required, and identify the evidence that
  records completion. Do not introduce a new release requirement in this change.

## Documentation structure

1. **Build the THG reference model**
   - Curate the starting reference GEM with β1.
   - Expand gene, protein, and location evidence with β2.
   - Optionally integrate the Human Database reconstruction.
   - Gapfill the model.
   - Validate and release the THG reference model.
2. **Build a cell-specific model**
   - Start from the THG reference model or a declared external GEM.
   - Apply expression or contextual evidence.
   - Validate and export the derived model.
3. **Supporting tools**
   - Pathway implementation, comparison, standalone validation, provenance,
     resumption, and recovery.

β1, β2, Human Database integration, gapfill, and release remain independently
documented stages, but they are presented as parts of the first journey rather
than equal top-level outcomes.

Distinguish this complete construction journey from the existing commands:

- `thg-run reference CONFIG` covers β1 → β2 → gapfill. Its output still requires
  the final validation/release gate before becoming the THG reference model.
- The registered `final-thg` workflow bundles merge → validation → export.
  Its merge occurs immediately before validation; using separate β2 and Human
  Database inputs there is a standalone combined route. Canonical optional
  integration occurs before gapfill.

Neither command alone represents the complete journey. Document the supported
handoffs and final-gate entry point for a post-gapfill candidate using existing
interfaces; identify any implementation gap explicitly rather than implying
that renaming the documentation supplies end-to-end orchestration.

## Implementation phases

### 1. Align user-facing documentation

- Rename headings and prose in `docs/index.md`, `docs/workflows/index.md`, and
  the workflow navigation in `mkdocs.yml`.
- Update `docs/workflows/final-thg.md` and
  `docs/workflows/cell-specific.md` to use the new vocabulary.
- Update the repeated terminology in `docs/workflows/validation.md`,
  `docs/workflows/gapfill.md`, `docs/workflows/human-database.md`,
  `docs/workflows/pathway.md`, and `docs/tools/cell-specific.md`.
  Explicitly distinguish the `reference` workflow's gapfilled candidate from
  the released THG reference model.
- Update `README.md`, `configs/README.md`, and the CLI/configuration reference
  where they explain model meaning rather than literal identifiers.
- Preserve historical plans and protocol records; add a short note where an
  older plan intentionally uses the former terminology.

### 2. Clarify identifiers

- On first mention, write **THG reference model (`final-thg`)** when users must
  type the existing workflow or configuration name.
- Keep filenames, configuration values, stage IDs, Python modules, APIs, and
  commands unchanged.
- Do not add aliases or deprecation machinery during the documentation change.

### 3. Evaluate a code-level migration separately

Only propose renaming `final-thg` after reviewing compatibility for saved run
manifests, configuration files, stage dependencies, tests, and downstream
automation. If migration is warranted, support the old identifier for at least
one release and document its removal separately.

## Acceptance checks

- The homepage's outcome diagram shows only **THG reference model → Cell-specific
  model**; installation, quickstart, and reference links remain available.
- The workflow overview presents those two outcomes before construction stages
  and supporting tools.
- Current user documentation does not use **Final THG** as the artifact name.
- Every literal `final-thg` identifier is formatted as code and remains valid.
- Candidate, validated, and released describe states consistently, with the
  final gate and any existing release step and completion evidence identified.
- The workflow overview and stage pages distinguish the complete journey from
  the `reference` and `final-thg` commands, explain integration ordering, and
  document supported handoffs or explicitly identify missing orchestration.
- Existing commands and configuration files continue to work unchanged.
- `mkdocs build --strict` and `pytest -q tests/docs` pass.

## Non-goals

- Renaming internal code or persisted workflow identifiers.
- Changing scientific workflow order or validation requirements.
- Removing standalone workflows or advanced documentation.
- Rewriting historical records to use terminology adopted later.
