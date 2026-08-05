# Annotation and identification

!!! info "Status: Supported"
    Maintained annotation, reaction-identification, and GPR/location helpers
    are covered by current tests; the complete curation sequence from the 2023
    protocol paper is composed manually.

## Outcome

Inspect annotation coverage, resolve metabolite/reaction identifiers, and
derive GPR or cellular-location information for review. Location resolution
preserves Boolean GPR structure and leaves unmatched pages unresolved unless
the caller explicitly supplies a documented fallback location.

## Place in the THG protocol

Core reference-model curation building block and a standalone inspection tool.

## When to use it

Use it before and after model enrichment or when unresolved identifiers need a
separate report.

## When not to use it

Use [model reconstruction](database.md) for normalized records or
[model enrichment](model-build.md) for a multi-service model-file pipeline.

## Inputs

Inputs are model paths, metabolite/reaction records, target identifiers, and
optional injected `PubChemClient`, BioCyc, KEGG, Ensembl, or location clients.
The exact required fields are defined by the linked API references.

## Requirements

Coverage inspection is offline. Live identifier/GPR/location lookup uses the
selected service and may need network, credentials, pacing, and caches. Static
clients provide deterministic offline tests. No solver is required.

## Run from the command line

No installed annotation CLI exists. Use the package APIs or the explicit
model-identification workflow function from Python.

## Run from Python

```python
from thg_protocol.annotation import analyze_model_annotations
from thg_protocol.gpr import get_gpr
from thg_protocol.services.biocyc import StaticBioCycClient

counts = analyze_model_annotations("docs/examples/quickstart_model.json")
client = StaticBioCycClient(
    ec_pages={("HUMAN", "1.1.1.1"): "<b>Gene:</b> GENE1 ENSG0001<br>"}
)
gpr = get_gpr("1.1.1.1", biocyc_client=client)
print(counts, gpr)
```

## Outputs

Inspection returns mappings and does not mutate or write the input. The
metabolite/reaction workflow returns `MetaboliteReactionResult` and writes
model, normalized-model, annotation, and failure files under explicit output
locations. Service caches are caller-owned where the API exposes them.

## Inspect the result

Review annotation counts, unresolved records, generated GPR syntax, location
sets, and failure reports. For resumable metabolite annotation, the checkpoint
sidecar is tied to the input fingerprint and is removed only after successful
finalization. Compare before/after model files and then run balance and
connectivity checks.

## Common problems

Empty results can mean the model has no matching annotations, not that a service
call succeeded. Check client fixtures, identifier prefixes, service responses,
and failure files. Never put credentials in examples.

## Next step

Continue with [model enrichment](model-build.md) or the
[reference-model protocol route](../protocol/reference-model.md).

## API references

Use [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations],
[`extract_metabolite_annotations`][thg_protocol.annotation.model_annotations.extract_metabolite_annotations],
[`get_gpr`][thg_protocol.gpr.lookup.get_gpr], and
[`resolve_locations`][thg_protocol.gpr.location.resolve_locations].

## Differences from the historical workflow

Current package boundaries require explicit paths and injected clients; retired
checkout wrappers and implicit repository outputs are Archived.
