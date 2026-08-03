# MEMOTE and task analysis

Use MEMOTE and task analysis for a broader quality assessment of a model. These
optional tools complement structural checks such as connectivity and balance.

MEMOTE and task-analysis runs require the optional `memote` extra and, for
some checks, a configured solver:

```bash
python -m pip install 'thg-protocol[memote,solver]'
```

Use the report alongside [network analysis](network-analysis.md) and model
comparison to understand both model quality and content changes.

## Expected output and troubleshooting

Run a local diagnostic after installing the opt-in extras:

```bash
memote run --filename results/memote.html model.xml
```

Use a pinned constraint set for reproducible solver checks and keep generated
HTML with your project results. Solver or optimization errors usually indicate
an environment or solver-configuration issue.
