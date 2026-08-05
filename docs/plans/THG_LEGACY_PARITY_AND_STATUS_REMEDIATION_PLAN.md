# THG legacy-parity audit and status remediation plan

## Goal

Replace the ambiguous `Partial` label with evidence-based capability reporting,
audit the maintained implementation against the original legacy workflow, fix
unintended behavioral gaps, and state clearly what is implemented, what matches
legacy behavior, and what has reproduced a published-stage artifact.

This plan is written for a coding agent that needs explicit, sequential work.
The agent must not change scientific status labels merely to make the
documentation sound more complete. Labels change only after the corresponding
evidence exists.

## Execution checkpoint — 2026-08-05

The first remediation slice is present in the current working tree and remains
uncommitted. It has established the evidence registry and orthogonal status
matrix, added the parity-contract/result skeleton, added the semantic COBRA
model signature, and hardened the resumable v1 runner and MEMOTE stage at their
documented boundaries. The focused evidence, signature, workflow-stage, lock,
and resumable-run tests pass (`20 passed`); the complete offline suite passes
(`1888 passed, 7 skipped`, including the five default-skipped opt-in parity
cases), Ruff is clean, and a source/wheel build succeeds
from a writable temporary checkout.

Five approved differential contracts and fixtures now exist for reaction
identification, metabolite identification, deterministic GPR page parsing,
the dependency-light mass-balance `atom10` primitive, and one offline GPR
location branch. With
`THG_LEGACY_CHECKOUT` pointed at the adjacent legacy checkout, all five
isolated parity cases pass (`5 passed`); without that explicit environment they
are skipped by default. Reaction comparison normalizes only set-derived
compartment fields and preserves species/stoichiometry order; metabolite
comparison uses a synthetic normalized PubChem response in both subprocesses;
GPR page comparison is limited to sorted gene/identifier pairs, mass-balance
comparison is limited to four formulas whose legacy token scan is unambiguous,
and location comparison is limited to one static Mitochondria branch.

The status-matrix test now compares every Markdown known-difference cell
exactly with the registry, preventing evidence wording from drifting after a
new parity case is added.

CI now has a separate pinned `legacy-parity` job that checks out the recorded
legacy commit and runs the deterministic parity marker. This is source
configuration evidence only; a hosted CI result is still pending.

This does not advance any legacy-equivalence or publication-reproduction
claim. The registry records the maintained baseline commit and the committed
legacy comparison snapshot `b474d80a34ef3bda9754bad3e24a21dc6cf3e57f`; the
legacy working tree is dirty and must not be used as a parity input. No frozen
publication artifact is available. Differential parity, authentic
legacy-pickle comparison, live Human Database harvesting,
publication-compatible merge, and full beta1/beta2 construction therefore
remain explicitly unverified or not implemented.

The adjacent legacy checkout contains ignored local `pre_sbml_raw.pk` and
`pre_sbml_pos_comp.pk` files, but neither is present in the recorded legacy
commit and neither is suitable as a reproducible parity fixture. A local
Python 3.10 diagnostic can load the positive-compartment file and the
maintained adapter now reaches a 1,279-metabolite/1,041-reaction/1,318-gene/
86-group model by preferring serialized compound fields over generation-time
methods and resolving callable legacy `ID2` values. This is diagnostic evidence
only; authentic pickle parity remains pending a sanitized committed snapshot.

The current consistency contract now pins sorted structural reports, boundary
exclusion for charge checks, and directional produced/consumed semantics. This
is maintained-only evidence and does not establish parity with the archived
solver-backed consistency/task suite.

Next evidence-preserving slice: obtain or authorize a sanitized committed
legacy-pickle snapshot, freeze its schema, and run both reconstruction paths in
isolated processes before changing any parity status. The current five
cases do not establish broad legacy equivalence for their surrounding
workflows. In particular, legacy substring handling for overlapping element
symbols, complex/multi-location semantics, and the remaining mass-balance
equation operations remain unverified; authentic database reconstruction parity
also remains pending.

## Audit conclusion to treat as the starting baseline

The maintained repository is cleaner at package boundaries, path ownership,
service injection, and offline testing. It is not currently equivalent to the
complete legacy THG construction.

High-confidence findings from source comparison:

1. `thg_protocol.model_build.build_model` enriches annotations on an existing
   network. The legacy `build_model.py` also mass-balanced reactions, generated
   GPR/location-specific reactions, expanded compartments, updated groups,
   removed duplicates, and produced THG beta artifacts. These are different
   workflows.
2. The maintained GPR lookup reduces discovered genes to OR alternatives with
   coefficient 1. The legacy code represented complexes, AND relationships,
   subunit stoichiometry, isoforms, transferred EC numbers, and additional
   fallbacks.
3. `resolve_locations` ignores its supplied GPR and Ensembl client. It loses
   complex/AND relationships, contains a probable unbounded `ER` regex false
   positive, and has a nondeterministic non-Cytosol fallback.
4. The maintained Human Database API reconstructs already-normalized records.
   It does not perform the legacy live database harvesting and construction.
   The legacy-pickle adapter also has concrete annotation, glycan/equivalence,
   and multi-compartment pathway differences.
5. Current merge behavior is identifier-based. The legacy merge matched
   metabolites, genes, and reactions across different identifiers and used
   annotations, formulas, names, compartments, stoichiometric similarity,
   reversals, GPR mapping, and consistency checks.
6. Current consistency functions are a smaller and semantically different
   subset. Missing formulas, boundary reactions, reversibility, open exchanges,
   stoichiometric consistency, unconserved metabolites, minimal inconsistent
   sets, and energy-generating cycles do not all match legacy behavior.
7. MEMOTE now has a maintained subprocess integration in `thg-run`, but the
   legacy custom essential-task suite remains absent/archived.
8. The resumable v1 DAG is a real implemented engineering capability. Its
   integration test demonstrates checksum-based reuse and restart. It does not
   execute the complete publication construction.
9. Existing parity evidence is mostly toy tests and characterization through
   package APIs. It generally does not execute old and new implementations on
   the same input and compare the results.

Therefore, do not describe the current package as legacy-equivalent until the
differential tests required below pass.

## Required replacement for `Partial`

Delete `Partial` as a status value. Use independent columns so implementation,
parity, orchestration, and publication reproduction cannot be confused.

### Controlled vocabulary

| Axis | Allowed values | Meaning |
| --- | --- | --- |
| Implementation | `Implemented`, `External integration`, `Archived`, `Not implemented` | Whether a maintained API/CLI exists for the named capability |
| Verification | `Unit-tested`, `Integration-tested`, `Parity-tested`, `Artifact-reproduction-tested`, `Not yet verified` | Strongest evidence that actually exists |
| Workflow coverage | `Operation`, `Orchestrated stage`, `Workflow-complete for documented scope`, `Published stage complete`, `N/A` | The callable scope |
| Legacy relationship | `Verified equivalent`, `Intentional difference`, `No replacement`, `No legacy target`, `Not assessed` | Relationship to historical code |
| Published reproduction | `Verified`, `Not yet verified`, `N/A` | Whether a frozen run reproduced the declared published-stage target |

Rules:

- `Parity-tested` means a test executed both legacy and maintained behavior on
  the same fixture and compared a written contract. A test that only runs the
  maintained package on an old fixture is not parity evidence.
- `Artifact-reproduction-tested` means a declared full model artifact was
  compared using a semantic model signature, documented counts, and, when
  stable, a byte checksum.
- `Implemented` does not imply legacy equivalence.
- `Intentional difference` must name the exact difference and its migration
  path.
- Broad publication stages must be split into separately assessable operations.

### Baseline matrix to publish before parity fixes

| Capability | Implementation | Verification | Workflow coverage | Legacy relationship | Published reproduction |
| --- | --- | --- | --- | --- | --- |
| Reference annotation operations | Implemented | Unit/integration-tested | Operation | Mixed; not fully assessed | Not yet verified |
| Complete THG beta1 construction | Not implemented | Not yet verified | Operation composition only | Not assessed | Not yet verified |
| Normalized-record reconstruction | Implemented | Unit/integration-tested | Orchestrated stage | Intentional difference | Not yet verified |
| Live Human Database construction | Not implemented | Not yet verified | N/A | No replacement | Not yet verified |
| GPR/location helper APIs | Implemented | Unit-tested | Operation | Intentional difference | Not yet verified |
| Complete THG beta2 construction | Not implemented | Not yet verified | Operation composition only | Not assessed | Not yet verified |
| Identifier-based merge | Implemented | Unit/integration-tested | Orchestrated stage | Intentional difference | Not yet verified |
| Legacy similarity-aware merge | Not implemented as maintained API | Not yet verified | N/A | No replacement | Not yet verified |
| Structural network reports | Implemented | Unit/integration-tested | Orchestrated stage | Intentional difference | N/A |
| MEMOTE invocation | External integration | Integration evidence required | Optional orchestrated stage | N/A | N/A |
| Essential metabolic tasks | Archived | Not yet verified | N/A | No replacement | Not yet verified |
| Resumable v1 engineering DAG | Implemented | Integration-tested | Workflow-complete for documented v1 scope | No legacy target | N/A |
| Exact published THG reconstruction | Not implemented as a complete workflow | Not yet verified | N/A | Not assessed | Not yet verified |

This baseline is more honest and more informative than `Partial`.

## Repository and safety rules

1. Freeze and record exact source commits before comparing anything:
   - maintained repository and branch;
   - original `MarindeMasLab/THG_The-Human-GEM-protocol` commit;
   - any `biosustain/THG` artifact commit used as a target.
2. Do not change an existing maintained API's semantics silently. Add an
   explicit legacy/publication-compatible API when compatibility would conflict
   with the safer current contract.
3. Do not use live biological services in default tests. Use recorded,
   checksum-pinned responses or static clients.
4. Do not put credentials in fixtures, logs, manifests, or documentation.
5. Preserve current explicit-path, non-mutating, and injected-client design
   unless the legacy side effect is itself part of an explicitly supported
   compatibility adapter.
6. Do not treat SBML byte equality as the only model-equivalence test.
7. Do not commit, push, open a pull request, or alter GitHub issues without
   separate authorization.

## Deliverables

Add:

```text
docs/protocol/capability-evidence.json
docs/protocol/capability-status.md
docs/parity/README.md
docs/parity/contracts/
tests/parity/
tests/fixtures/legacy_parity/
src/thg_protocol/analysis/model_signature.py
```

Update at minimum:

```text
README.md
CURRENT_STATE.md
docs/protocol/index.md
docs/protocol/implementation-status.md
docs/api-contracts.md
docs/legacy-api-inventory.md
docs/legacy-workflows.md
docs/workflows/resumable-run.md
docs/workflows/memote.md
docs/api/index.md
docs/api/cli.md
docs/api/workflows.md
docs/api/api-inventory.json
docs/api/workflow-api-inventory.json
docs/installation.md
docs/release-validation.md
.github/workflows/ci.yml
```

Rename `implementation-status.md` only if redirects or MkDocs links are updated
in the same change. Keeping the filename while changing its title to
`Capability and evidence status` is safer.

## Phase 1: create a machine-readable evidence registry

Create `docs/protocol/capability-evidence.json`. Each entry must contain:

```json
{
  "id": "reference.build_model_annotation",
  "publication_concept": "Reference annotation",
  "current_entry_points": ["thg_protocol.model_build.build_model"],
  "implementation": "Implemented",
  "verification": "Unit-tested",
  "workflow_coverage": "Operation",
  "legacy_relationship": "Intentional difference",
  "published_reproduction": "Not yet verified",
  "legacy_sources": ["build_model/build_model.py"],
  "current_sources": ["src/thg_protocol/model_build/__init__.py"],
  "tests": ["tests/unit/test_model_build_api.py"],
  "known_differences": ["Only annotation enrichment is performed"],
  "evidence_commit": "<maintained commit SHA>"
}
```

Requirements:

- One entry per actual operation, not one overloaded entry per broad
  publication diagram box.
- Validate controlled values in a unit test.
- Validate that every listed current source and test path exists.
- Validate that every public protocol-status table row references a registry
  ID.
- Generate or verify the Markdown matrix from the registry so the JSON and docs
  cannot drift.

## Phase 2: define parity contracts before writing parity tests

For every operation being compared, create one Markdown contract under
`docs/parity/contracts/`. A contract must state:

- exact legacy functions/scripts and maintained entry points;
- accepted inputs and default values;
- returned values and schemas;
- model mutation and object ownership;
- files created, modified, or deleted;
- network, credentials, cache, solver, and subprocess behavior;
- ordering and identifier rules;
- warnings and exceptions;
- which differences are intended;
- normalization used for comparison;
- pass/fail criteria.

Do not write a test called parity without an approved contract.

Start with these contracts:

```text
reference-reaction-identification.md
reference-metabolite-identification.md
mass-balance.md
gpr-lookup.md
location-resolution.md
reference-model-build.md
database-reconstruction.md
database-harvesting.md
model-merge.md
network-consistency.md
metabolic-tasks.md
```

## Phase 3: build the differential parity harness

### Isolate implementations

The legacy checkout and maintained package have conflicting module names and
different dependency expectations. Run each side in a separate subprocess or
virtual environment. Exchange only JSON, TSV, SBML, and normalized report
files. Do not import both implementations into one interpreter unless a test
proves isolation is safe.

### Record service inputs

For KEGG, BioCyc, PubChem, UniProt, Ensembl, and location pages:

1. Create small, license-safe recorded fixtures or synthetic responses covering
   documented parsing branches.
2. Store source, retrieval date, redaction status, and SHA-256 metadata.
3. Inject or monkeypatch the same responses into both implementations.
4. Never make live network access part of the default parity gate.

### Add a semantic COBRA model signature

Implement `thg_protocol.analysis.model_signature.model_signature(model)`. It
must return deterministic JSON containing sorted:

- model ID/name and compartments;
- metabolite IDs, names, formulas, charges, compartments, and normalized
  annotations;
- reaction IDs, names, bounds, sorted stoichiometry, normalized GPR AST, and
  normalized annotations;
- gene IDs, names, and normalized annotations;
- group IDs and sorted member IDs;
- objective coefficients where applicable.

Also implement a structured diff that reports added, removed, and changed
objects. Use this for model parity; record SBML checksums separately.

### Required harness result

Every parity case writes a JSON result with:

```text
contract ID
legacy commit
maintained commit
fixture checksums
normalization version
matching fields
intentional differences
unexpected differences
pass/fail
```

## Phase 4: audit and fix reference annotation

1. Differentially test reaction extraction, Jaccard/reversal classification,
   metabolite identification, annotation writing, and unresolved-record output.
2. Decide whether maintained set-based Jaccard is an intentional correctness
   fix. If yes, document and test the exact behavior difference.
3. Fix `generate_met_annotation` so advertised delay, checkpoint, and resume
   parameters either work or are removed from the public contract. It currently
   overwrites output and does not implement the advertised resume behavior.
4. Add multiple fixtures: exact match, reverse match, duplicate reactants,
   missing formula, parenthesized names, PubChem miss, and service failure.
5. Upgrade registry verification only for operations whose differential tests
   pass.

## Phase 5: separate annotation build from full reference construction

The name `build_model` currently suggests broader behavior than it performs.

1. Keep `build_model` backward compatible for its current documented contract.
2. Add or expose a clearer name such as `annotate_model_file`; retain
   `build_model` as a documented alias if needed.
3. Do not claim THG beta1/beta2 construction from this function.
4. Design a separate `construct_reference_branch` workflow for the legacy
   scientific sequence.
5. Port each legacy phase independently:
   - formula and mass-balance review/correction;
   - GPR resolution;
   - location resolution;
   - compartment/isoenzyme reaction expansion;
   - group membership updates;
   - duplicate and isolated-object cleanup;
   - beta1 and beta2 artifact selection.
6. Save a model signature and phase report after every transformation.
7. Add differential tests for every phase before composing the complete branch.

## Phase 6: repair and verify GPR/location behavior

### GPR lookup

1. Represent GPRs with the maintained AST utilities instead of joining every
   gene with OR.
2. Preserve complexes, AND/OR structure, isoforms, and stoichiometric subunit
   counts from recorded legacy cases.
3. Cover HumanCyc, MetaCyc, KEGG fallback, transferred EC numbers, empty pages,
   and malformed pages.
4. Compare normalized ASTs and SGPR coefficient structures, not gene substring
   presence.

### Location resolution

1. Stop discarding `gpr` and `ensembl_client`.
2. Preserve Boolean complex relationships when splitting rules by location.
3. Define the accepted identifier type for every lookup boundary.
4. Replace the unbounded `ER` regex with a boundary-safe expression.
5. Replace `next(iter(set))` fallback with a deterministic policy.
6. Do not silently assign Cytosol merely because lookup failed. Return an
   explicit unresolved result unless the contract deliberately requests a
   fallback.
7. Add tests for complexes, multiple locations, missing pages, Ensembl mapping,
   identifier mismatch, ER false positives, and deterministic fallback.

Only mark these operations `Verified equivalent` after complete structured
comparisons pass. Otherwise use `Intentional difference` with exact details.

## Phase 7: split Human Database reconstruction from harvesting

1. Keep `reconstruct_model_from_json` as the deterministic reconstruction API.
2. Test `reconstruct_model_from_pickle` with at least one authentic sanitized
   legacy `pre_sbml_*.pk` or dill snapshot, not only a hand-built dictionary.
3. Compare model signatures and fix or explicitly document:
   - missing `kegg.reaction` annotation;
   - alternate glycan-formula behavior;
   - metabolite-equivalence transformations;
   - reaction identifier normalization;
   - multi-compartment pathway membership;
   - missing referenced metabolites;
   - gene annotation differences.
4. Treat live harvesting as its own capability. Either:
   - implement a maintained `harvest_human_database_records` workflow using
     injected clients and resumable response caches; or
   - label it `Not implemented` and `No replacement`.
5. Never describe reconstruction from prepared records as construction from
   live databases.

## Phase 8: preserve current merge and add a publication-compatible merge

Do not silently replace the current safe identifier-based `merge_models`
contract.

1. Rename its documentation row to `Identifier-based merge`.
2. Add focused tests for conflicting formulas, charges, bounds, stoichiometry,
   GPRs, and annotations so the current intentional behavior is fully defined.
3. Implement a separate API such as `merge_models_publication_compatible` for
   the legacy scientific merge.
4. Port and test legacy phases separately:
   - cross-ID metabolite identity mapping;
   - compartment-aware metabolite mapping;
   - gene mapping;
   - EC/KEGG reaction matching;
   - reactant/product similarity and reversal matching;
   - GPR and identifier rewriting;
   - stoichiometry/bounds decisions;
   - consistency-gated reaction acceptance;
   - cleanup and report generation.
5. Use tiny adversarial models where IDs differ but chemistry matches, and where
   IDs match but stoichiometry conflicts.
6. Compare structured mappings and final model signatures against legacy.

Do not call the current ID-based merge similarity-aware.

## Phase 9: define exact consistency semantics

1. Give every check a precise biological and computational definition.
2. Separate structural sign-based checks from solver-backed checks.
3. Add explicit functions or modes for legacy semantics rather than changing
   current functions invisibly.
4. Cover:
   - missing formulas;
   - boundary-reaction inclusion/exclusion;
   - charge balance;
   - consumed-not-produced versus disconnected metabolites;
   - bounds and reversibility;
   - open-exchange blocked-reaction behavior;
   - stoichiometric consistency;
   - unconserved metabolites;
   - minimal inconsistent sets;
   - energy-generating cycles.
5. Add cases where current and legacy definitions deliberately disagree and
   assert the documented difference.
6. Create an explicit acceptance-policy object for the orchestrator. Report
   generation alone must not be called scientific convergence.

## Phase 10: MEMOTE and essential tasks

1. Correct the documentation: MEMOTE is an external dependency with a
   maintained `thg-run` integration.
2. Add direct tests for `MemoteStage` with a fake executable, nonzero exit,
   missing output, version output, and successful HTML output.
3. Decide whether essential tasks will be restored.
4. If restored, port them into a maintained optional module with explicit task
   definitions and solver requirements; compare results against the legacy
   custom MEMOTE tests.
5. If not restored, retain `Archived` and `No replacement`; do not infer task
   success from ordinary MEMOTE or structural reports.

## Phase 11: harden the resumable orchestrator

The v1 runner is implemented, but the evidence and documentation need cleanup.

1. Add the missing focused runner, stage, and lock tests. The repository has an
   end-to-end integration test but does not currently contain the planned
   `test_workflow_runner.py`, stage, and lock suites.
2. Refuse a nonempty start directory without a manifest, or explicitly define
   safe reuse behavior.
3. Handle or document SIGTERM and stale-lock recovery.
4. Record run-owned caches as checksummed artifacts. Clearly document external
   cache behavior.
5. Preserve attempt history in the manifest or stop claiming that the manifest
   retains complete attempt history; directories alone are not structured
   history.
6. Reword the claim that all hand-edited manifests are rejected. The current
   implementation validates structure, configuration hash, and artifact hashes;
   it does not authenticate every well-formed state edit.
7. Add `thg-run` to wheel smoke tests, CI policy tests, API inventories, CLI
   docs, installation docs, release validation, and `CURRENT_STATE.md`.
8. Once these pass, label the v1 DAG `Implemented`, `Integration-tested`, and
   `Workflow-complete for documented v1 scope`.

## Phase 12: compose and verify publication stages

Only begin this phase after the operation-level parity contracts are resolved.

1. Freeze an input Human1 model and every auxiliary file with checksums.
2. Freeze or record all allowed service responses and database release dates.
3. Run the reference branch to beta1 and beta2 with checkpoint reports.
4. Run Human Database harvesting/reconstruction with checkpoint reports.
5. Run the publication-compatible merge and validation policy.
6. Run MEMOTE and essential tasks when they are part of the declared target.
7. Compare each named artifact using:
   - semantic model signature;
   - reaction/metabolite/gene/GPR/compartment counts;
   - annotations and group membership;
   - task and consistency results;
   - serialized checksum when stable.
8. Document acceptable differences before the run, not afterward.
9. Mark `Published stage complete` or `Published reproduction: Verified` only
   when the declared golden comparison passes in a reproducible environment.

If original live responses or artifacts are unavailable, state `Not yet
verified` and name the missing evidence. Do not use `Partial`.

## Phase 13: replace status documentation everywhere

1. Change the title of `implementation-status.md` to `Capability and evidence
   status` while keeping the path for link stability.
2. Replace the single status column with the five controlled axes.
3. Split broad rows into operation and published-stage rows.
4. Add direct links to contracts, tests, code, and evidence commits.
5. Replace every `Status: Partial` admonition with a precise scope statement,
   for example:

   ```text
   Engineering workflow: Implemented and integration-tested.
   Published THG beta2 construction: Not implemented as a complete workflow.
   Published artifact reproduction: Not yet verified.
   ```

6. Correct the merge wording from `Similarity/identity-aware merge` to
   `Identifier-based merge` for the current API.
7. Update all documentation and API inventories to include `thg-run` and
   `thg_protocol.workflow`.
8. Refresh `CURRENT_STATE.md` from the new evidence registry rather than
   patching its old three-command snapshot.
9. Add a docs test that fails if `Partial` is reintroduced as a status value.
10. Add tests that fail when installed commands and API inventories drift from
    `pyproject.toml`.

## Test and CI markers

Add markers:

```text
legacy_parity: executes isolated legacy and maintained implementations
artifact_reproduction: compares a frozen full-stage or final artifact
recorded_service: uses checksum-pinned recorded service responses
```

Default CI must run deterministic operation-level parity cases that have no
restricted data or heavy solver requirement. Full artifact reproduction may be
a separate scheduled/manual gate, but its last result and evidence commit must
be recorded. Live network is never the parity oracle.

Required general gates:

```bash
python -m pytest
ruff check src tests
python -m build
```

Required package smoke checks after wheel installation:

```bash
thg-gapfill --help
thg-compare --help
thg-pathway --help
thg-run --help
```

## Recommended execution order for a simpler agent

Complete only one numbered item at a time:

1. Freeze commit SHAs and add the evidence registry schema/test.
2. Rewrite the status matrix from existing evidence without changing code
   claims.
3. Fix stale `thg-run` API/CLI/CI documentation and smoke checks.
4. Add the semantic model signature and its tests.
5. Write reference annotation parity contracts and differential tests.
6. Fix the annotation checkpoint/resume mismatch.
7. Write and test GPR lookup parity.
8. Fix and test location resolution.
9. Write and test authentic database reconstruction parity.
10. Define the current identifier-based merge contract and adversarial tests.
11. Implement publication-compatible merge in isolated phases.
12. Define and test consistency semantics.
13. Add MEMOTE stage tests and decide essential-task ownership.
14. Harden runner/stage/lock tests and claims.
15. Implement the reference construction branch.
16. Implement or explicitly decline live Human Database harvesting.
17. Compose the frozen end-to-end publication-stage run.
18. Update evidence levels only after each corresponding gate passes.

After every item, run focused tests, then the complete offline suite. Stop if a
new unexpected difference appears; update the contract before changing code.

## Definition of done

- `Partial` is no longer a status value anywhere in maintained documentation.
- Every status claim is decomposed into implementation, verification, workflow
  coverage, legacy relationship, and published reproduction.
- Every `Verified equivalent` claim has a differential legacy/current test.
- The current identifier-based merge is no longer described as
  similarity-aware.
- GPR/location behavior preserves or explicitly documents complex/stoichiometric
  differences.
- Human Database reconstruction is not confused with live harvesting.
- Resumable v1 workflow claims match its actual code and tests.
- All four installed commands are represented in docs, inventories, CI, and
  wheel smoke tests.
- A semantic model signature supports reproducible model comparisons.
- Complete THG beta1, beta2, Human Database, merge, and final-artifact claims
  remain `Not implemented` or `Not yet verified` until their declared gates
  pass.
- Full offline tests, Ruff, builds, and outside-wheel command checks pass.

## Short handoff prompt

> Implement `THG_LEGACY_PARITY_AND_STATUS_REMEDIATION_PLAN.md` sequentially.
> Begin by freezing source commits and creating the machine-readable evidence
> registry. Replace the ambiguous `Partial` status with orthogonal evidence
> fields based only on current proof. Do not claim legacy parity unless the old
> and new implementations run on the same fixture and pass a written contract.
> Preserve current safer APIs; add explicit publication-compatible operations
> where legacy behavior differs. Keep default tests offline, do not use
> credentials, and do not commit or publish changes.
