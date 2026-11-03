What this repo does: The assigned code runs resumable metabolic-model workflows, validates COBRA models, records model artifacts and renders curator reports. I assumed local batch runs on one machine, with genome-scale human metabolic reconstructions and optional MEMOTE/solver checks.

Functional review: I traced the runtime engine, artifact hashing/verification, locks/manifests/stage contracts, proposal application, validation core and validation workflow/runner. I found one confirmed config failure below; the other reviewed paths had no confirmed defect. The apply-decisions path verifies the input model checksum and validates decisions before it saves the changed model; runtime artifacts are checked for containment, size and hash before reuse.

Scientific review: I traced validation profile gates, elemental/charge balance, formula and identity diagnostics, stoichiometric consistency, leakage and energy-cycle checks. The primary literature defines stoichiometric consistency by existence of a shared positive metabolite-mass assignment; it distinguishes minimal inconsistent net stoichiometries from simply blocked reactions ([Gevorgyan et al. 2008, journal record](https://openresearch.surrey.ac.uk/esploro/outputs/journalArticle/Detection-of-stoichiometric-inconsistencies-in-biomolecular/99513754502346?institution=44SUR_INST&recordUsage=false&skipUsageReporting=true), [primary-paper abstract/details](https://pubmed.ncbi.nlm.nih.gov/18697772/) (DOI: 10.1093/bioinformatics/btn425)). The implementation’s `minimal_inconsistent_sets` helper explicitly returns blocked-reaction singletons instead of claiming to compute mathematical MIS; its function docstring and `method` field state this, and the report renderer retires the old check. This is a limitation, not a newly confirmed defect. The MEMOTE-style leakage/energy checks close boundary reactions and respect flux direction; interpretation remains limited to the encoded bounds, exchange closure, annotations and modeled energy couples.

**Must fix**

1. **Validation accepts a config that crashes at run start** (`src/thg_protocol/workflow/config.py:379-397`, `src/thg_protocol/workflow/validation.py:40-41`)
   - **What this is:** The `validate` workflow always fingerprints an input model before running its first stage.
   - **Problem:** `validation.input_model` is only checked when present. A config with `"workflow":"validate"`, a valid `run` block, and `"validation":{}` loads successfully, then `ValidationScientificStage("validate-input").fingerprint_data(...)` raises `KeyError: 'input_model'`.
   - **Fix:** Require and resolve `validation.input_model` in `_parse_workflow` for the `validate` workflow, or support the advertised `upstream` source in the stage. The existing implementation only supports a path.
   - **If we skip it:** Invalid configs fail after the run has been created instead of producing a clear configuration error.

I reproduced the crash by loading that minimal config and calling the first stage's fingerprint method. I did not modify repository files or run tests (the parent is running the full suite).

2. **A non-finite activity threshold is accepted and can remove active reactions** (`src/thg_protocol/workflow/config.py:517-521`, `src/thg_protocol/cell_specific/__init__.py:37-47`)
   - **What this is:** The cell-specific workflow compares measured gene activity against a configured threshold before removing inactive reactions.
   - **Problem:** The config check only verifies that `threshold` is numeric. A JSON value of `1e309` becomes infinity and is accepted; `evaluate_gpr_activity` then considers every reaction with measured expression inactive because no finite score is greater than infinity. The workflow can therefore remove all such reactions as if that were valid evidence.
   - **Fix:** Reject non-finite thresholds with `math.isfinite(threshold)` during config validation.
   - **If we skip it:** A malformed threshold can silently turn an expression-driven reduction into broad reaction deletion.

A temporary config with `threshold: 1e309` loaded successfully and produced `inf`. The evaluator's strict `score > threshold` comparison confirms the resulting behavior.

I also reviewed the deterministic ID registry, workflow registry and evidence-store primitives, validation-report renderers and embedded decision UI, cell-specific/pathway/compare stages, and beta1/beta2 stage pipelines. The renderer escapes user-controlled content and embeds JSON with `<` escaped. The beta2 pipeline writes a candidate explicitly labeled as not release-ready; no additional confirmed issue emerged from these files. The validation workflow config path is covered by the finding above. The raw-evidence store validates recorded checksums but permits absolute or parent-relative raw-response paths; callers can intentionally point to external evidence snapshots, so I did not classify that as a boundary defect.

Coverage is intentionally explicit: `/tmp/thg-audit-workflows-validation-coverage.json` contains every inventory function in the assigned source paths. It marks all 365/365 functions functionally reviewed. It marks 274 as scientifically reviewed and the remaining 91 infrastructure-only functions as scientific N/A, with an explicit note for each. The inventory includes nested functions and methods, and generated `build/lib` copies were excluded.

Not checked: Test bodies were not deeply examined, and I did not rerun tests because the parent ran the full suite (2,430 passed). I reviewed the registered stage paths and callers in scope; core GIMME, beta2 curation and gapfill MILP implementations were checked at their workflow call boundaries, not re-audited internally.
