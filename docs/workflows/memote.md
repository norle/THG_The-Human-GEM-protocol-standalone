# MEMOTE and task analysis

## What this workflow is for

Run a broad quality assessment alongside structural connectivity and balance
checks.

## When not to use it

Use [network analysis](network-analysis.md) for a dependency-light local
diagnostic, or [model comparison](comparison.md) when the question is what
changed between two models.

## Prerequisites and inputs

Install the optional tools and configure a solver where required:

```bash
python -m pip install 'thg-protocol[memote,solver]'
```

The input is a model file and a caller-selected report location.

## CLI

```bash
memote run --filename results/memote.html model.xml
```

The `memote` command is the primary CLI reference for this workflow; it is
recorded in the [workflow API inventory](../api/workflow-api-inventory.json).

## Outputs

MEMOTE writes an HTML diagnostic report. Keep generated reports with project
results and use pinned solver constraints for reproducibility.

## Common errors

Solver or optimization errors generally indicate an environment or solver
configuration issue. Validate the solver independently before interpreting
model findings.

## Next workflow

Return to [usage](../usage.md) to select the next task, or use
[figures and reports](figures.md) to present selected results.
