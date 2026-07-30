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

It accepts injectable BioCyc, KEGG, and Ensembl clients for offline tests and
writes all generated caches and reports to caller-provided locations. The
normalized database workflow also exposes
`thg_protocol.database.reconstruct_model_with_services` for record-driven
construction.

The single and batch model builders remain compatibility workflows while their
reusable reconstruction core is exposed as
`thg_protocol.database.reconstruct_model`. Their service calls can receive
package-owned BioCyc, KEGG, and Ensembl clients, which makes offline tests
possible.

Normalized JSON record bundles can be reconstructed with
`thg_protocol.database.reconstruct_model_from_json`; the output path is
caller-provided and no repository-relative files are created.

Run the legacy scripts only with explicit input and output paths, and keep
large model inputs outside ordinary generated test fixtures. Credentials are
read from environment variables or local configuration outside Git.
