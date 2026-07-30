# Figures and reports

Figure workflows accept explicit model and report paths through
`thg_protocol.figures`. Report summaries are dependency-light; rendering uses
the optional plotting extra:

```bash
python -m pip install 'thg-protocol[figures]'
```

The legacy figure script is an explicit-path compatibility wrapper. Optional
MEMOTE and algorithm score data must be supplied rather than hard-coded.
