# API reference

The reference is generated from the maintained package with
`mkdocstrings[python]`. Public functions and classes are the supported Python
surface; names beginning with `_` are intentionally filtered from the site.

Common contracts:

- Functions accept explicit model, input, output, cache, and report paths.
- Network-capable operations accept injectable clients. Static clients are the
  offline test and documentation boundary.
- Analysis functions generally do not mutate models. The generated signatures
  and docstrings call out exceptions and ownership for transformation APIs.
- Solver, MEMOTE, plotting, and historical pickle support are optional extras.

See the [workflow guides](../usage.md) for end-to-end context and the
[architecture page](../architecture.md) for data flow and service ownership.

## Coverage matrix

| Area | Generated page | Main modules |
| --- | --- | --- |
| Core and I/O | [Core and I/O](core.md) | `config`, `glycan`, `reaction_config`, `io` |
| Construction | [Construction](construction.md) | `database`, `database_parsing`, `model_build` |
| Annotation and GPR | [Annotation](annotation.md) | `annotation`, `gpr` |
| Services | [Services](services.md) | BioCyc, KEGG, Ensembl, PubChem, Location |
| Workflows | [Workflows](workflows.md) | gapfill, pathway, merge, cell-specific |
| Analysis | [Analysis](analysis.md) | consistency, comparison, compaction, network |
| Figures | [Figures](figures.md) | comparison and model reports |
| Commands | [CLI commands](cli.md) | `thg-gapfill`, `thg-pathway`, `thg-compare` |
