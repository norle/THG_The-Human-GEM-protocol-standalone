# Quickstart

Run the included example data through the installed command-line tools. This
is an offline smoke test and does not need credentials or a solver.

## Prerequisites

From the repository root, using Python 3.10–3.12:

```bash
python -m pip install -e .
```

## Run it

Create a directory for the generated files, then apply the fixture pathway:

```bash
mkdir -p runs/practical-quickstart

thg-pathway \
  --model docs/examples/quickstart_model.json \
  --config docs/examples/pathway_config.json \
  --database docs/examples/metabolite_ids.json \
  --output runs/practical-quickstart/enriched-model.json
```

Run a regular and semantic model comparison:

```bash
thg-compare \
  runs/practical-quickstart/enriched-model.json \
  docs/examples/comparison_model.json \
  --output-dir runs/practical-quickstart/comparison

thg-compare \
  runs/practical-quickstart/enriched-model.json \
  docs/examples/comparison_model.json \
  --semantic \
  --output-dir runs/practical-quickstart/semantic
```

Finally, run the standalone offline gapfill example:

```bash
thg-gapfill \
  --model docs/examples/quickstart_model.json \
  --method greedy \
  --max-additions 1 \
  --allowed-connection c:e \
  --output-dir runs/practical-quickstart/gapfill
```

The commands print a short summary and leave the source fixtures unchanged.
The gapfill fixture reports `partial`; that is expected for this intentionally
small model.

## Files after execution

```text
runs/practical-quickstart/
├── enriched-model.json
├── gapfill/
│   ├── gapfill-report.json
│   ├── gapfill-selected-reactions.jsonl
│   ├── gapfilled-model.json
│   └── gapfilled-model.xml
├── comparison/
│   ├── compartments_comparison_raw.csv
│   └── compartments_comparison_no_blocked.csv
└── semantic/
    └── semantic-comparison.json
```

These are demonstration fixtures, not a research-quality human GEM. Next,
[choose a workflow](workflows/index.md) for your own model or evidence.

## Python API

For library usage—such as database reconstruction, direct analysis, or release
gates—see the [construction](api/construction.md), [analysis](api/analysis.md),
and [workflow API](api/workflows.md) references. The quickstart uses the CLI so
that the normal user path does not require writing Python code.
