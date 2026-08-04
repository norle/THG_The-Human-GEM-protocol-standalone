# Metabolite and reaction identification

## What this workflow is for

Inventory model identifiers, enrich metabolites or reactions, and resolve
gene–protein–reaction (GPR) rules before curation or analysis.

## When not to use it

Use [model enrichment](model-build.md) for the complete external-service
pipeline, or [network analysis](network-analysis.md) for purely structural
connectivity and balance checks.

## Prerequisites and inputs

Provide a JSON model, annotation targets, and optional report paths. Live
clients may require credentials, network access, and service-specific rate
limits; static clients are preferred for tests.

## Python API

Start with [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations]
and [`extract_metabolite_annotations`][thg_protocol.annotation.model_annotations.extract_metabolite_annotations]:

```python
from thg_protocol.annotation import analyze_model_annotations, extract_metabolite_annotations

counts = analyze_model_annotations("inputs/model.json")
annotations, missing = extract_metabolite_annotations("inputs/model.json", ["ATP", "H2O"])
```

Resolve GPRs with [`get_gpr`][thg_protocol.gpr.lookup.get_gpr] and locations
with [`resolve_locations`][thg_protocol.gpr.location.resolve_locations].
The lower-level model and reaction APIs are available as
[`annotate_cobra_model`][thg_protocol.annotation.model.annotate_cobra_model],
[`identify_reaction`][thg_protocol.annotation.reactions.identify_reaction],
and [`run_metabolite_reaction_identification`][thg_protocol.annotation.metabolite_reactions.run_metabolite_reaction_identification].

## Outputs

Results are inventories, transformed rules, or optional JSON reports. Missing
fields are reported as unmatched targets; input models are not silently
rewritten.

## Common errors

No lookup result usually means an identifier namespace or compartment mismatch.
Check target IDs and metadata before changing service settings.

## Next workflow

Continue with [network analysis](network-analysis.md), or use
[model comparison](comparison.md) to review changes between model versions.
