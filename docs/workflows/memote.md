# MEMOTE and task analysis

!!! info "Status: External"
    MEMOTE quality assessment is performed with the separately installed
    `memote` command; it is not a maintained THG package API.

## Outcome

Produce a broad MEMOTE HTML quality report and keep essential metabolic-task
status as a separate record.

## Place in the THG protocol

External validation alongside package connectivity, formula-balance, and
stoichiometric checks. It is not a replacement for those checks.

## When to use it

Use MEMOTE after saving a candidate model and its provenance. Use task analysis
only when a maintained, separately identified implementation is available.

## When not to use it

Do not infer that a MEMOTE score proves the publication's essential metabolic
tasks. Do not present the historical task implementation as a current THG API.

## Inputs

An SBML or JSON model accepted by the installed MEMOTE version and a caller-
selected HTML output path. Task files/configuration must be preserved too.

## Requirements

Install and pin MEMOTE separately; solver support may be needed by selected
checks. The package's `memote` extra provides the dependency but does not add a
THG command. Network is not inherently required after installation.

## Run from the command line

```bash
python -m pip install 'memote'
memote run --filename results/validation/memote.html results/model.xml
```

## Run from Python

No maintained THG Python wrapper exists. Invoke the external command from a
caller-owned workflow and record its version/configuration.

## Outputs

MEMOTE writes the requested HTML report and may write tool-managed intermediate
files according to its version/configuration. Historical essential-task output
is **Archived** in this repository unless separately replaced.

## Inspect the result

Review category failures, warnings, model loading errors, solver details, and
the exact command. Compare with package balance/consistency reports and record
task status independently.

## Common problems

Solver errors are environment/configuration failures until investigated.
Version drift can change reports, so pin MEMOTE and preserve its configuration.

## Next step

Use [network analysis](network-analysis.md) for local diagnostics or
[figures](figures.md) only after retaining the raw report.

## Differences from the historical workflow

The publication combined MEMOTE and metabolic-task assessment in its research
workflow. Current support separates external MEMOTE from the Archived task
implementation and does not provide one THG orchestration.
