# Model building

The package-native file workflow is available through
`thg_protocol.model_build.build_model`:

```python
from thg_protocol.model_build import build_model

report = build_model(
    "input.xml",
    "results/model.xml",
    cache_dir="results/cache",
    errors_path="results/errors.json",
)
```

Batch-oriented callers can use the same service boundary and retain the
historical cache filenames needed by existing automation:

```python
from thg_protocol.model_build import build_model_batch

report = build_model_batch(
    "input.xml",
    "results/model.xml",
    cache_dir="results/cache",
    output_errors="results/errors.tsv",
)
```

It accepts injectable BioCyc, KEGG, and Ensembl clients for offline tests and
writes all generated caches and reports to caller-provided locations. The
normalized database workflow also exposes
`thg_protocol.database.reconstruct_model_with_services` for record-driven
construction.

The single and batch model builders are package APIs. Their service calls can
receive package-owned BioCyc, KEGG, and Ensembl clients, which makes offline
tests possible. The former checkout scripts and README were retired after
this migration.

Normalized JSON record bundles can be reconstructed with
`thg_protocol.database.reconstruct_model_from_json`; the output path is
caller-provided and no repository-relative files are created.

Formula-only mass-balance helpers are available without COBRA or a solver:

```python
from thg_protocol.model_build import atom10, formula_atoms, missing_atoms

formula_atoms("C6H12O6")
atom10("C6H12O6")
missing_atoms("H2 + O2 -> H2O")
```

Use `reformulate_glycan_equation` with an injected KEGG client when glycan
resolution is needed.

Keep large model inputs outside ordinary generated test fixtures. Credentials
are read from environment variables or local configuration outside Git.
