# Inputs, outputs, and file formats

This page describes caller-owned scientific inputs and generated outputs. Git
LFS and tracked-artifact policy belongs in the [maintainer records](artifact-inventory.md)
and [standalone repository runbook](git-lfs-standalone-repository.md).

## Model formats

| Format | Supported operations |
| --- | --- |
| COBRA JSON (`.json`) | Reconstruction, model-build, pathway, gapfill, comparison, merge, and analysis where the guide accepts JSON |
| SBML (`.xml`, other non-`.json` output suffixes) | COBRA model-build, comparison, merge, cell-specific reduction, and analysis through COBRA I/O |
| Normalized record JSON | `reconstruct_model_from_json`; see schema below |
| Historical pickle | `reconstruct_model_from_pickle` with the `database` extra; compatibility input, not a preferred interchange format |

## Normalized record format

The record bundle contains `model_id`, optional `model_name`, `metabolites`,
`reactions`, optional `genes`, and optional `pathways`. Metabolites require an
`id` and may include `compartment`, `name`, `formula`, `charge`, and an
`annotation` mapping. Reactions require an `id` and `stoichiometry` mapping and
may include bounds, a GPR, name, and annotation. A stoichiometry key must refer
to a metabolite in the same bundle.

See the complete minimal example in [`docs/examples/records.json`](examples/records.json)
and the [Human Database route](protocol/human-database.md).

## Pathway configuration

`implement_pathway_files` consumes a JSON model, pathway configuration, and
metabolite-ID mapping, then writes one explicit JSON output. The repository's
small configuration is [`pathway_config.json`](examples/pathway_config.json),
with its lookup input in [`metabolite_ids.json`](examples/metabolite_ids.json).
Configuration keys and model mapping behavior are documented in the
[pathway operation guide](workflows/pathway.md).

## Activity and expression inputs

Cell-specific reduction accepts a matrix-like value, CSV, or MAT file (the MAT
reader's default key is documented by the API). Gene/transcript annotation
helpers accept a model or XML annotation file as described in the
[cell-specific guide](workflows/cell-specific.md). Preserve the sample order,
units, preprocessing, and threshold configuration with the input.

## Output and cache conventions

Operations write only to caller-supplied output paths or directories. Common
outputs are revised JSON/SBML models, CSV comparison/gapfill reports, JSON
connectivity/error reports, SVG figures, and service caches. `build_model`
places service caches under its explicit `cache_dir` or an output-relative
`cache/` directory; retries can reuse those caches when the relevant API is
given the same location. MEMOTE writes an HTML report where its command is
directed.

## Mutation and ownership

Loaded-model merge and cell-specific reduction return copies and do not mutate
their inputs. `reconstruct_model` creates a new model. In-memory pathway
helpers mutate the mapping they receive; the file wrapper reads inputs and
writes a separate output. Analysis functions copy or inspect models without
claiming ownership. No operation should be assumed to write a file unless an
output path is supplied.

## Example output tree

```text
project/
├── inputs/
│   ├── reference-model.xml
│   ├── records.json
│   └── pathway-config.json
└── results/
    ├── reference/
    │   ├── curated-model.json
    │   ├── errors.json
    │   └── cache/
    ├── database/
    │   └── human-network.json
    ├── merge/
    │   ├── merged-model.xml
    │   └── merge-report.json
    └── validation/
        ├── components.json
        └── memote.html
```

The tree is a recommended ownership layout; filenames produced by a specific
API are listed in that operation's guide. Do not overwrite inputs in place.

## Reproducibility metadata

Preserve the package version and commit, input model checksums and versions,
record/pathway/configuration files, service/cache dates and database releases,
solver and version, optional dependency versions, command configuration, and
output model/report checksums. Live biological services can change, so a URL or
function name alone is not a reproducibility record.

## Downloadable examples

The deterministic fixtures are listed in [Examples](examples/README.md). They
are intentionally small and are not canonical THG model artifacts.
