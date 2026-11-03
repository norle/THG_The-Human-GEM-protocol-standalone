# Handwritten JavaScript audit

Reviewed every handwritten function, arrow callback, event handler, and IIFE in:

- `src/thg_protocol/validation_report.py`: `_FIX_JS` plus the report's inline search/toggle script.
- `docs/assets/component_visualization_template.html` and `docs/assets/mermaid-init.js`.
- `supplementary_material/pathway/figures/Glycocalyx_Cytoskeleton_network_d3.html`, lines 16730–16905 (the surrounding ~406 KB is embedded graph JSON).

The full ledger is `/tmp/thg-audit-javascript-coverage.json`: 103 function occurrences, including anonymous callbacks: 58 report-script, 12 template, 1 Mermaid, and 32 D3 graph functions/callbacks. All are marked functional reviewed. The 71 general UI callbacks are scientific N/A; the 32 graph-rendering functions are marked scientific reviewed for their model-to-visual mapping. Generated Plotly and MEMOTE vendor libraries were excluded.

## Findings

1. **Embedded graph data reaches tooltip HTML without escaping** (`supplementary_material/pathway/figures/Glycocalyx_Cytoskeleton_network_d3.html:16885-16898`). `showTooltip` interpolates model-derived `full_name`, `label`, `subsystem`, compartment, formula, and charge into a string passed to D3 `.html()`. Crafted metadata can inject markup or event-handler HTML when a node is hovered. The current graph values did not show `<` or `>` markup in the scanned string fields, but the rendering path is unsafe for imported or regenerated model data. Render these values as text or escape them before building the tooltip HTML.

2. **Graph arrows do not mean allowed flux direction, but the page does not explain that distinction** (`...Glycocalyx_Cytoskeleton_network_d3.html:16792-16818,16851-16856`). Substrate edges point metabolite → reaction and product edges reaction → metabolite, which matches the encoded reaction equation sides. The graph marks every edge with a single arrow in that orientation and ignores each edge's `reversible` flag in rendering. The edge data has 172 reversible edges, covering 85 distinct reaction IDs. Thus arrows show stoichiometric side orientation, not a claim that net flux can only run that way; the missing legend/tooltip explanation can mislead users. Counts are internally consistent: 312 metabolite nodes + 337 reaction nodes = 649 nodes, and 1,364 means stoichiometric incidence edges/connections, not distinct reactions or unique metabolite pairs.

No other confirmed issue found. The validation report's generated scripts escape inserted identifier data before `innerHTML`; embedded JSON replaces `<` with `\\u003c`. Decisions are persisted under a model-checksum key, stale choices are dropped against the current report's proposal IDs, and import maps only known proposal IDs into the local UI state. The component template lazily creates/destroys inactive networks and catches network-construction errors. The Mermaid initializer sets Mermaid's strict security level.

## Runtime dependencies and checks

The graph files load D3 from a CDN and the component template loads vis-network from unpkg. These are documented runtime dependencies in the HTML, not confirmed defects absent an offline-use guarantee; pinning exact versions and adding integrity metadata would improve reproducibility and supply-chain protection. Their remote contents were not downloaded or audited.

Extracted the two validation-report scripts, the component template script with valid placeholders, the Mermaid initializer, and the archived D3 graph script. `node --check` succeeded for all five. This is syntax checking only; no DOM/browser integration was run. No source files or repository tests were changed/run.
