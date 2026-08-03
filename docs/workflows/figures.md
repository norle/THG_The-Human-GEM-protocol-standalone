# Figures and reports

Figure workflows accept explicit model and report paths through
`thg_protocol.figures`. Report summaries are dependency-light; rendering uses
the optional plotting extra:

```bash
python -m pip install 'thg-protocol[figures]'
```

The former legacy figure script was retired with the checkout-only workflows.
Optional MEMOTE and algorithm score data must be supplied rather than
hard-coded.
