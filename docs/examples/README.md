# Documentation fixtures

These deliberately small JSON files are safe, deterministic inputs for the
quickstart and documentation tests. They are not representative GEMs and do
not replace canonical model or pathway artifacts.

- `records.json` is a normalized database bundle.
- `quickstart_model.json` is the JSON mapping used by gapfill and pathway
  examples.
- `pathway_config.json` and `metabolite_ids.json` are a minimal pathway
  configuration and lookup database.
- `comparison_model.json` is a second model for comparison examples.

Tests write all generated models, reports, caches, and figures under pytest's
temporary directory.
