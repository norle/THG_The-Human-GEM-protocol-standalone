# Model enrichment

Use model enrichment to add information from BioCyc, KEGG, and Ensembl to an
existing JSON or SBML model. It writes the enriched model, caches collected
information when requested, and records any problems for review.

For a single model, use `thg_protocol.model_build.build_model`:

```python
from thg_protocol.model_build import build_model

report = build_model(
    "input.xml",
    "results/model.xml",
    cache_dir="results/cache",
    errors_path="results/errors.json",
)
```

For a batch-oriented process, use:

```python
from thg_protocol.model_build import build_model_batch

report = build_model_batch(
    "input.xml",
    "results/model.xml",
    cache_dir="results/cache",
    output_errors="results/errors.tsv",
)
```

You can supply BioCyc, KEGG, and Ensembl clients to control how information is
looked up. For record-driven construction rather than enrichment of an existing
model, use [model reconstruction](database.md).

Formula-only mass-balance helpers are available without COBRA or a solver:

```python
from thg_protocol.model_build import atom10, formula_atoms, missing_atoms

formula_atoms("C6H12O6")
atom10("C6H12O6")
missing_atoms("H2 + O2 -> H2O")
```

Use `reformulate_glycan_equation` with an injected KEGG client when glycan
resolution is needed.

## Prerequisites, output, and troubleshooting

The input must be JSON or SBML. The output is an annotated model, JSON service
caches, and an optional error report under the paths you select. If a service
error is reported, inspect the error file and cache contents before retrying.
