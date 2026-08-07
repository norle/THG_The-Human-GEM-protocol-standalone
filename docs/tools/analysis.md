# Model comparison and analysis

Use this area for cross-workflow analysis rather than lifecycle orchestration.
`thg-compare` supports ordinary reaction comparisons and `--semantic` model
comparisons. Network connectivity, balance, consistency, compaction, and
figure/report summaries are available as explicit APIs.

```bash
thg-compare model-a.json model-b.json --output-dir reports
thg-compare model-a.json model-b.json --semantic --output-dir reports
```

Semantic comparison includes model and selected validation/task artifact
changes. It does not decide whether a scientific candidate passes a release
gate; use the [Validation workflow](../workflows/validation.md) for that.
Exact functions are in the [analysis API](../api/analysis.md).

Canonical APIs: [`compare_models_from_files`][thg_protocol.analysis.compare.compare_models_from_files],
[`compare_model_files_semantically`][thg_protocol.analysis.compare.compare_model_files_semantically],
and [`find_network_components`][thg_protocol.analysis.network.find_network_components].
