# Stoichiometric GPR evidence

THG represents enzyme evidence as one canonical tree:

```text
(A*2 and B*1) or (A*1 and C*3)
```

`AND` means the members are required by the same enzyme complex. `OR` means
alternative enzymes. Coefficients are branch-local, so the same gene may have
different multiplicities in alternative complexes.

Each gene node records a coefficient and its status:

- `observed`: explicitly stated by the source;
- `inferred`: derived unambiguously from source structure;
- `defaulted`: compatibility value, normally `1`;
- `unknown`: no biological coefficient is asserted.

The canonical serializers are `to_gpr(node)` and `to_sgpr(node)`. Unknown
coefficients are omitted by the latter by default. `to_legacy_sgpr(node)` is
the explicit compatibility serializer and may emit `*1`; those values are not
observations.

Reactome and structured BioCyc records can provide complex membership and
multiplicity. Rhea and KEGG normally provide reaction-matched or EC-to-gene
alternatives only, so their coefficients remain unknown. UniProt can enrich
protein identifiers and supporting subunit evidence; free-text subunit claims
are not converted to exact counts without an explicit parsing rule. GOA is
localization evidence and never generates sGPR structure.

Evidence is merged by complete structure, not by unioning gene lists. The
highest-precedence structural sources resolve deterministically and retain all
provenance; lower-structure Rhea, KEGG, and UniProt candidates are supporting
evidence. Different top-precedence structures or coefficients produce
`conflict` status rather than being silently averaged.

The legacy `get_gpr(...)` five-field tuple remains available. New callers can
use `get_sgpr_evidence(...)`, `resolve_sgpr(...)`, or the AST and merge APIs in
`thg_protocol.gpr`.
