# Operations and data flow

THG Protocol reads model records, JSON or SBML models, and workflow-specific
configuration. Its operations produce revised models, reports, and figures.

```text
records / JSON or SBML models / pathway configuration
                         |
                         v
        construct, annotate, and curate a model
                         |
                         v
       compare, check, tailor, and summarize it
                         |
                         v
             models, reports, and figures
```

Construction turns normalized records into a model. Annotation checks or adds
biological identifiers. Pathway implementation, gapfill, and merging change
model content. Analysis inspects the resulting model; cell-specific modelling
and figures create derived models or visual output.

The [task guides](usage.md) describe when to use each operation.

## Inputs and outputs

You supply the paths for input models, output models, caches, and reports.
JSON and SBML are supported where noted in the individual guides. A workflow
does not overwrite the input model unless its guide explicitly says so.

## Optional capabilities

Most structural workflows run locally. Annotation and model-building operations
can use external biological databases and may require network access or
credentials. Solver-backed quality checks, cell-specific methods, MEMOTE, and
figure rendering are optional; each relevant guide identifies its requirements.

For implementation details, service-client behavior, and mutation guarantees,
see the [API reference](api/index.md).
