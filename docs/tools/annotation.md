# Annotation and GPRs

This tool area covers metabolite and reaction identification, annotation
inventory, GPR normalization, and location lookup. Service clients are injected
at the boundary; static clients and cached responses make tests reproducible.

Use [`analyze_model_annotations`][thg_protocol.annotation.model_annotations.analyze_model_annotations]
for an inventory, [`get_gpr`][thg_protocol.gpr.lookup.get_gpr] for lookup, and
[`resolve_locations`][thg_protocol.gpr.location.resolve_locations] for explicit
location resolution. β1/β2 orchestration remains in the [workflow guides](../workflows/index.md).
