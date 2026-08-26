# CLI reference

| Command | Purpose |
| --- | --- |
| `thg-run start CONFIG` | Start a generic configured workflow, including Human Database and final THG |
| `thg-run beta1 CONFIG` | Start a registered β1 workflow |
| `thg-run beta2 CONFIG` | Start a registered β2 workflow |
| `thg-run gapfill CONFIG` | Start a standalone, checksum-tracked gapfill workflow |
| `thg-run reference CONFIG` | Run the canonical β1 → β2 → gapfilled reference workflow |
| `thg-run validate CONFIG` | Start a registered validation workflow |
| `thg-run compare CONFIG` | Start a registered comparison workflow |
| `thg-run resume RUN_DIR` | Resume valid stages |
| `thg-run status RUN_DIR [--json]` | Inspect run state |
| `thg-run unlock RUN_DIR [--force]` | Remove a stale lock deliberately |
| `thg-compare ...` | Compare models; add `--semantic` for semantic JSON output |
| `thg-gapfill --model MODEL --method {milp,greedy,deadends} --output-dir DIR` | Run standalone gap filling; optional `--parameters`, `--max-additions`, and repeated `--allowed-connection c:e` |
| `thg-pathway ...` | Apply a pathway configuration |

Add `-v`/`--verbose` to a starting or resume command to see live stage-level
progress. Repeat it as `-vv` for fingerprints, result summaries, and artifact
paths. For example: `thg-run beta1 configs/beta1.json -v` or
`thg-run resume runs/beta1 -vv`. Progress is written to stderr so stdout remains
available for the final result.

`thg-run human-database` and `thg-run final-thg` are not named commands;
those workflows currently use `thg-run start` with a corresponding `workflow`
value. CLI failures return non-zero status and preserve the run error/provenance
where a run directory exists. Use the [workflow guides](../workflows/index.md)
for task context and examples.

The generated parser API remains available on the [CLI API page](../api/cli.md).
