# How the pieces fit together

THG Protocol is organized around the artifacts in a model-curation project:
records and models go in; revised models, reports, and figures come out.

```text
records / JSON or SBML models / pathway configuration
                         |
                         v
        build, annotate, and curate a model
                         |
                         v
       compare, check, tailor, and summarize it
                         |
                         v
             models, reports, and figures
```

Construction turns normalized records into a model. Annotation adds or checks
biological identifiers. Pathway implementation, gapfill, and merging make
defined changes to model content. Analysis helps you judge the result;
cell-specific modeling and figures adapt or communicate it.

The [workflow overview](workflow-overview.md) explains when to use each stage.

## Inputs and outputs

You choose the paths for input models, output models, caches, and reports.
This makes it natural to keep an auditable project structure: preserve the
starting model, save each curated version, and retain the report that explains
each change. JSON and SBML are supported where noted in the individual guides.

## Optional capabilities

Most structural workflows work locally. External biological databases are used
only for workflows that request annotation or enrichment; they may need network
access and credentials. Solver-backed quality checks, cell-specific methods,
MEMOTE, and figure rendering are optional and documented with the workflow
that uses them.

For implementation details, service-client behavior, and mutation guarantees,
see the [API reference](api/index.md).
