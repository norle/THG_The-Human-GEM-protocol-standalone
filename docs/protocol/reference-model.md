# Curate an existing GEM

!!! warning "Status: Partial"
    `thg_protocol.annotation`, `thg_protocol.model_build`, and GPR/location
    helpers are maintained and tested building blocks, but no supported command
    performs the complete reference-model branch through THGβ2.

## Scientific outcome

This branch improves a reference human GEM's identifiers, annotation,
mass-balance treatment, GPRs, and cellular locations before isoenzyme-based
expansion. In publication terminology it moves the reference model toward
THGβ1 and then THGβ2. The caller should keep each intermediate model and report
so every change remains reviewable.

## Acceptable starting formats

The package model-file workflows read COBRA JSON and SBML. Start with an
explicit input path, a caller-owned output directory, and a recorded model
version or checksum. The small files in [`docs/examples/`](../examples/README.md)
are demonstrations, not human reference models.

## Numbered procedure

1. **Preserve and inspect.** Copy the input to a working result path and use
   [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations]
   or the annotation guide to inventory identifiers. This inspection is local,
   does not mutate the file, and writes nothing unless the caller asks for it.
2. **Resolve identifiers.** Use the annotation and identification functions
   for selected metabolites/reactions. Static service clients make tests and
   offline runs deterministic; production PubChem, KEGG, or BioCyc clients can
   make network requests and may require credentials or rate-limit planning.
3. **Treat mass balance.** Use formula helpers such as
   [`formula_atoms`][thg_protocol.model_build.mass_balance.formula_atoms],
   [`reaction_balance`][thg_protocol.analysis.consistency.reaction_balance],
   and [`unbalanced_reactions`][thg_protocol.analysis.consistency.unbalanced_reactions]
   to identify and review imbalances. These helpers do not silently repair a
   scientific model; record any correction in a new output model.
4. **Build an annotated intermediate.** For service-backed enrichment, call
   [`build_model`][thg_protocol.model_build.build_model] with explicit input,
   output, cache, and error paths. Inject static clients for offline operation;
   otherwise the package lazily constructs service clients only when matching
   identifiers require them.
5. **Curate GPRs and locations.** Use
   [`get_gpr`][thg_protocol.gpr.lookup.get_gpr] and
   [`resolve_locations`][thg_protocol.gpr.location.resolve_locations] with
   injected clients where applicable. A GPR is a gene–protein–reaction rule;
   an S-GPR additionally represents stoichiometric protein requirements.
6. **Expand by isoenzyme and compartment.** Apply only the expansion logic
   supported by the model/pathway inputs in hand and save the resulting model.
   The current inventory does not establish a single THGβ2 orchestration, so
   do not label an arbitrary enriched model as publication THGβ2 without a
   documented mapping.
7. **Validate the checkpoint.** Re-run annotation inventory, formula-balance,
   connectivity, and comparison checks. Preserve the report, caches, service
   dates, and configuration before moving to [merge](merge-and-validate.md).

## Inputs, outputs, and ownership

Inputs are caller-owned and the package APIs use explicit paths. `build_model`
writes the enriched model, JSON caches under `cache_dir` (or the output's
`cache/` directory), and an optional error file. Merge and reduction APIs return
copies; pathway in-memory helpers intentionally mutate the mapping supplied to
them, so use `implement_pathway_files` and separate paths when ownership
matters.

## Offline and credentialed work

Pure record reconstruction, formula checks, static-client tests, and local
annotation inspection run offline. Calls to production service clients are the
network boundary. BioCyc credentials are not embedded in examples; use the
client's supported environment/configuration mechanism and record the query and
cache dates. An offline alternative is a normalized record bundle or injected
static client.

## Expected outputs and transition

At minimum, retain `reference-input.json`/SBML, each revised model, annotation or
error reports, caches, and a provenance file. Review the checkpoint before
combining the reference branch with the [Human Database](human-database.md).
Detailed operation instructions remain in [annotation](../workflows/annotation.md),
[model enrichment](../workflows/model-build.md), and [model reconstruction](../workflows/database.md).

